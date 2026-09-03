# license_server/web_api.py
"""API เว็บไซต์เกม (prefix /api/web) — ข่าว/ล็อกอิน/โปรไฟล์/เติมเงิน/แอดมิน

auth ทั้งหมดเป็น cookie ลงชื่อ HMAC-SHA256 (คีย์ = admin secret ของ license_server)
- web_admin  : {"role": "admin", "exp": ...} อายุ 7 วัน
- web_session: {"uid": "<discord_id>", "exp": ...} อายุ 30 วัน
(สเปค: docs/superpowers/specs/2026-08-05-game-website-design.md)

⚠️ กำลังรื้อโครงสร้าง (09-02 ขั้นที่ 4) — ย้าย route ออกไปที่ license_server/api_web/
ทีละหมวด ตัวช่วยกลาง (sign/verify/require_admin/require_player/_game_conn ฯลฯ)
ย้ายไปอยู่ api_web/deps.py แล้ว ไฟล์นี้ import กลับมาใช้ + re-export ไว้
เผื่อเทส/โค้ดเก่าเรียก web_api.sign(...) ตรง ๆ อยู่
"""
import hmac
import time

from fastapi import HTTPException, Request, Response
from pydantic import BaseModel

from license_server import web_db
from license_server.api_web import router  # ตัวเดียวกับ api_web.router (รื้อโครงสร้าง 09-02)
from license_server.api_web.deps import (  # noqa: F401  (re-export ให้โค้ด/เทสเก่าเรียกผ่าน web_api ได้)
    GAME_DB_PATH, _ADMIN_TTL, _SESSION_TTL, _game_conn, _key, _money_now,
    _set_cookie, _user_lock, player_model_get, require_admin, require_player, sign, verify,
)
from license_server.api_web.auth import _CODE_CHARS, _CODE_RE, _CODE_TTL, _TICKET_RE  # noqa: F401
from license_server.api_web.topup import _slip_path  # me_profile โชว์ has_slip ในประวัติเติมเงิน


@router.get("/me/profile")
def me_profile(request: Request):
    uid = require_player(request)["uid"]
    conn = _game_conn()
    try:
        row = conn.execute("SELECT * FROM players WHERE user_id=?", (int(uid),)).fetchone()
    finally:
        conn.close()
    if not row:
        return {"new_player": True}
    d = dict(row)
    from bot.game_data import CONTINENTS
    cont = d.get("continent") or "main"
    profile = {k: d.get(k) for k in ("level", "exp", "rank", "hp", "max_hp",
                                     "cash", "bank", "pet", "title")}
    profile["continent"] = cont
    profile["continent_label"] = CONTINENTS.get(cont, {}).get("label", cont)
    with web_db.connect() as wconn:
        tops = wconn.execute(
            "SELECT id, amount_thb, gold, status, created_at FROM topups "
            "WHERE discord_id=? ORDER BY id DESC LIMIT 10", (uid,)).fetchall()
    return {"profile": profile,
            "topups": [dict(t) | {"has_slip": _slip_path(t["id"]).is_file()} for t in tops]}


def _dur_pct(cur, full):
    """ความทนทานเป็น % จากของเต็มของชิ้นนั้น — None ถ้าไม่มีข้อมูล"""
    if cur is None:
        return None
    full = int(full or 0)
    if full <= 0:
        return 100 if int(cur or 0) > 0 else 0
    return max(0, min(100, round(int(cur or 0) / full * 100)))


def _role_names_of(p):
    """ชื่อยศที่มีผลจริงของผู้เล่น — เว็บไม่มี Discord roles จึงอ่านจาก DB"""
    from bot import identity
    return identity.effective_role_names([], p)


def _dice_view(p, role_names):
    """🎲 สรุปเต๋าของผู้เล่น ณ ตอนนี้ (ปรับ 2026-08-14 — ทอยหลายลูกได้แล้ว)

    ฐาน 1 ลูก + 1 ลูกทุก 25 เลเวล + ลูกจากสัตว์เลี้ยง
    เต๋าของตัวเองทอยเต็มช่วง (ตีปกติ 8-18 / สกิล 1-20)
    เต๋าสัตว์เลี้ยงเป็นลูกเล็ก 1-6 กันแต้มเฟ้อ
    """
    from bot import adventure_core, config_loader, game_modifiers, pets
    from bot.models.player_model import MAX_LEVEL
    lo = int(config_loader.get_balance("dice.normal_min", 8))
    hi = int(config_loader.get_balance("dice.normal_max", 18))
    skill_max = int(config_loader.get_balance("dice.skill_max", 20))
    pet_max = int(config_loader.get_balance("dice.pet_die_max", 6))
    per = int(config_loader.get_balance("dice.level_per_die", 25))

    total, lvl_dice, pet_dice = adventure_core.player_dice_count(p)
    own = max(1, total - pet_dice)

    els = game_modifiers.resolve_player_elements(role_names)
    bonus = []
    wind = game_modifiers.player_passive_sum(els, "roll_bonus")
    if wind:
        bonus.append({"from": "💨 ธาตุลมประจำตัว", "value": wind})
    st_b = game_modifiers.status_roll_bonus(game_modifiers.parse_statuses(p))
    if st_b:
        bonus.append({"from": "👝 สถานะติดตัว", "value": st_b})
    flat = sum(b["value"] for b in bonus)

    pet_name = next((x["name"] for x in pets.all_pets() if x["key"] == p.get("pet")), "")
    lvl = int(p.get("level", 1) or 1)
    return {
        "dice_count": total, "own_dice": own, "level_dice": lvl_dice, "pet_dice": pet_dice,
        "pet_name": pet_name, "level_per_die": per,
        # ลูกถัดไปจะได้ตอนเลเวลเท่าไหร่ — ไม่มีแล้วถ้าเลเวลเต็มหรือชนเพดานจำนวนลูก
        "next_die_at": (((lvl // per) + 1) * per
                        if per > 0 and lvl < MAX_LEVEL and own < int(
                            config_loader.get_balance("dice.max_dice", 8))
                        else None),
        "normal_min": lo, "normal_max": hi, "skill_max": skill_max, "pet_die_max": pet_max,
        "bonus": bonus, "bonus_total": flat,
        "normal_cap": own * hi + pet_dice * pet_max + flat,
        "skill_cap": own * skill_max + pet_dice * pet_max + flat,
    }


def _mana_view(p):
    """สรุปมานาแบบพร้อมแสดงผล — อ่านอย่างเดียว ไม่เขียน DB (endpoint นี้ต้อง read-only)"""
    from bot import mana as _mana
    full = _mana.max_mana(p.get("level", 1))
    fresh = p.get("mana_date") == _mana._today()
    cur = min(full, int(p.get("mana", 0) or 0)) if fresh else full   # ข้ามวันแล้ว = เต็ม
    return {"mana": max(0, cur), "mana_max": full, "mana_bar": _mana.bar(max(0, cur), full)}


@router.get("/me/game")
def me_game(request: Request):
    """ข้อมูลตัวละครเต็มสำหรับหน้าเล่นเกม (เว็บเกม เฟส 1.1)

    คืนข้อมูล "พร้อมแสดงผล" ทั้งหมด — ชื่อไอเทม ชื่อเกราะ ป้ายบัฟ แปลงมาจากคอนฟิกฝั่งนี้แล้ว
    เบราว์เซอร์จึงไม่ต้องรู้กฎเกมอะไรเลย (หลักการข้อ 1 ของแผน)
    อ่านอย่างเดียว ไม่เขียน DB
    """
    uid = require_player(request)["uid"]
    conn = _game_conn()
    try:
        row = conn.execute("SELECT * FROM players WHERE user_id=?", (int(uid),)).fetchone()
    finally:
        conn.close()
    if not row:
        return {"new_player": True}

    from bot import config_loader, game_modifiers
    from bot.game_data import CONTINENTS
    from bot.models.player_model import MAX_LEVEL, exp_required, load_inventory
    from core.services.items import usable_kind
    from bot import season as _season
    from bot import fashion as _fashion

    p = dict(row)
    items = config_loader.get_all_items()
    cont = p.get("continent") or "main"
    armor_key, weapon_key = p.get("armor") or "None", p.get("weapon") or ""
    armor = config_loader.get_armor_stats(armor_key) or config_loader.get_armor_stats("None")
    weapon = config_loader.get_weapon_stats(weapon_key)

    # กระเป๋า: รวมของชนิดเดียวกันเป็นชิ้นเดียวพร้อมจำนวน (เหมือนที่เมนูในดิสแสดง)
    inv = load_inventory(p.get("inventory", ""))
    counts = {}
    for iid in inv:
        counts[str(iid)] = counts.get(str(iid), 0) + 1
    bag = []
    for iid, n in counts.items():
        it = items.get(iid, {})
        kind = usable_kind(it)
        bag.append({"id": iid, "name": it.get("name", f"ไอเทม {iid}"), "count": n,
                    "type": it.get("type", ""), "sell": it.get("sell", 0),
                    "kind": kind, "usable": bool(kind)})
    bag.sort(key=lambda b: (not b["usable"], b["name"]))

    # บัฟ/สถานะติดตัว — เอาป้ายกับหน่วยนับมาจากตารางกลาง ไม่ให้เว็บเดาเอง
    buffs = []
    for key, turns in game_modifiers.parse_statuses(p).items():
        cfg = game_modifiers.STATUS_EFFECTS.get(key, {})
        buffs.append({"key": key, "label": cfg.get("label", key), "turns": turns,
                      "unit": "ก้าว" if cfg.get("tick") == "step" else "ไฟต์",
                      "no_tick": bool(cfg.get("no_tick"))})

    return {
        "identity": {
            "discord_id": str(uid),
            "level": p.get("level"), "exp": p.get("exp"), "rank": p.get("rank"),
            # แถบ EXP: exp ใน DB คือความคืบหน้าในเลเวลนี้ (เกมหักออกทุกครั้งที่อัป)
            # คิด % ให้เสร็จฝั่งนี้ เบราว์เซอร์ไม่ต้องรู้สูตร
            "exp_required": exp_required(p.get("level") or 1),
            "exp_pct": (round(min(100.0, (p.get("exp") or 0) * 100.0
                                  / exp_required(p.get("level") or 1)), 1)
                        if exp_required(p.get("level") or 1) else 100.0),
            "max_level": (p.get("level") or 1) >= MAX_LEVEL,
            "race": p.get("race"), "class_name": p.get("class_name"),
            "title": p.get("title"), "pet": p.get("pet"),
            "continent": cont,
            "continent_label": CONTINENTS.get(cont, {}).get("label", cont),
        },
        # current_state บอกว่าตอนนี้ค้างอะไรอยู่ในดิส — ใช้ตัดสินกติกาเล่นสองแพลตฟอร์ม
        "dice": _dice_view(p, _role_names_of(p)),
        "vitals": {"hp": p.get("hp"),
                   # HP เต็มจริงต้องรวมโบนัสจากเกราะ (เกราะพัง = ไม่ได้โบนัส)
                   # ไม่งั้นหน้าโปรไฟล์โชว์ "380 / 280" ซึ่งอ่านแล้วงง
                   "max_hp": int(p.get("max_hp", 0) or 0)
                             + (armor.get("hp", 0) if p.get("armor_dur", 0) > 0 else 0),
                   "base_max_hp": p.get("max_hp"),
                   "sanity": p.get("sanity"), "state": p.get("current_state") or "idle",
                   "pet": p.get("pet") or "",
                   # 💎 เม็ดคริสตัลที่เหลือวันนี้ — คิดที่เซิร์ฟเวอร์รวมการเติมข้ามวันแล้ว
                   **{k: v for k, v in _mana_view(p).items()}},
        "money": {"cash": p.get("cash", 0), "bank": p.get("bank", 0)},
        "gear": {
            # ⚠️ dur ใน DB เป็น "หน่วยความทนทานดิบ" ไม่ใช่เปอร์เซ็นต์
            # ของเต็มต่างกันตามชิ้น (อาวุธไม้ 50 · เหล็ก 150 · ตำนาน 1000
            #  เกราะผ้า 100 ... เหล็กหนัก 500) ต้องส่งของเต็มไปด้วยถึงจะคิด % ถูก
            # เคยโชว์ "เกราะ 367%" เพราะเอาเลขดิบไปติด % ตรง ๆ
            "armor": {"key": armor_key, "name": armor.get("name", armor_key),
                      "hp": armor.get("hp", 0), "eva": armor.get("eva", 0),
                      "dur": p.get("armor_dur"), "dur_max": armor.get("dur", 100),
                      "dur_pct": _dur_pct(p.get("armor_dur"), armor.get("dur", 100))},
            "weapon": {"key": weapon_key, "name": weapon.get("name", weapon_key or "— มือเปล่า —"),
                       "dur": p.get("weapon_dur"), "dur_max": weapon.get("dur", 100),
                       "dur_pct": _dur_pct(p.get("weapon_dur"), weapon.get("dur", 100))},
            "artifact_slots": p.get("artifact_slots", 1),
        },
        # ป้าย "มีของค้างรับ" บนปุ่มเมนู — ต้องเห็นตั้งแต่ยังไม่กดเข้าไปดู
        "season": {"claimable": _season.season_view(uid)["claimable"]},
        "fashion": _fashion.worn(p),      # 👗 ใส่อะไรอยู่ — ตัววาดเอาไปสวมทับ
        "bag": {"capacity": p.get("capacity", 0), "used": len(inv), "items": bag},
        "buffs": buffs,
    }


# ══ การกระทำในเกมจากเว็บ (เว็บเกม เฟส 2) ══
# ทุก endpoint ในโซนนี้เรียก "ฟังก์ชันชุดเดียวกับที่บอท Discord ใช้" ไม่มีกฎเกมเขียนซ้ำที่นี่
# _user_lock/_money_now ย้ายไป api_web/deps.py แล้ว (import ไว้ด้านบน — ต้องเป็น dict ใบเดียวกับ
# ที่ bank.py ฯลฯ ใช้ ไม่งั้นล็อกกันคนละตัวจะเสียการันตี mutual-exclusion)


class UseBody(BaseModel):
    item_id: str


@router.post("/item/use")
def item_use(body: UseBody, request: Request):
    """ใช้ไอเทมจากกระเป๋า — เรียก apply_item_effect() ตัวเดียวกับปุ่ม 🧪 ในดิส"""
    uid = require_player(request)["uid"]
    from bot import adventure_core
    from core.services.items import apply_item_effect
    with _user_lock(uid):
        ok, msg = apply_item_effect(int(uid), str(body.item_id))
        # แวะกินยาระหว่างสู้ = ยังอยู่กับไฟต์นั้น ต่ออายุให้ ไม่งั้นกลับมาแล้วมอนหายไป
        adventure_core.touch_pending(int(uid))
    return {"ok": ok, "message": msg}


class CasinoBody(BaseModel):
    game: str
    bet: int
    choice: str = ""


@router.post("/casino")
def casino(body: CasinoBody, request: Request):
    """เล่นคาสิโนหนึ่งตา — casino_core ตัวเดียวกับปุ่ม !hilo / !slots ในดิส

    ผลออกที่เซิร์ฟเวอร์ทั้งหมดรวมถึงระบบเจ้ามือตุกติก เบราว์เซอร์แค่เอาไปเล่นอนิเมชัน
    """
    uid = require_player(request)["uid"]
    if body.game not in ("hilo", "slots"):
        raise HTTPException(400, "ไม่รู้จักเกมนี้")
    if body.bet <= 0:
        raise HTTPException(400, "เดิมพันต้องมากกว่า 0")

    from bot import casino_core
    with _user_lock(uid):
        if body.game == "hilo":
            ok, out = casino_core.play_hilo(int(uid), body.choice, body.bet)
        else:
            ok, out = casino_core.play_slots(int(uid), body.bet)
    return {"ok": ok, "result": out, "money": _money_now(uid)}


class BjBody(BaseModel):
    action: str
    bet: int = 0


@router.post("/blackjack")
def blackjack(body: BjBody, request: Request):
    """แบล็กแจ็ค 24 — blackjack_core ตัวเดียวกับปุ่มในดิส

    สถานะโต๊ะอยู่ใน DB เปิดมือในดิสแล้วมาเล่นต่อที่นี่ได้เลย
    """
    uid = require_player(request)["uid"]
    if body.action not in ("start", "hit", "stand"):
        raise HTTPException(400, "ไม่รู้จักคำสั่งนี้")

    from bot import blackjack_core
    with _user_lock(uid):
        if body.action == "start":
            if body.bet <= 0:
                raise HTTPException(400, "เดิมพันต้องมากกว่า 0")
            ok, out = blackjack_core.start(int(uid), body.bet)
        elif body.action == "hit":
            ok, out = blackjack_core.hit(int(uid))
        else:
            ok, out = blackjack_core.stand(int(uid))
    return {"ok": ok, "game": out, "money": _money_now(uid)}


class UnoBody(BaseModel):
    action: str = "view"       # start | play | draw | take | pass | uno | quit
    index: int = 0             # ไพ่ใบที่เท่าไหร่ในมือ
    suit: str = ""             # สีที่เลือกตอนวางไวลด์
    bots: int = 1


@router.post("/uno")
def uno(body: UnoBody, request: Request):
    """🎴 ศึกไพ่รูน — ซ้อมกับบอท

    🔒 เบราว์เซอร์ส่งมาแค่ "กดอะไร" — กติกาทั้งหมดตัดสินที่เซิร์ฟเวอร์
       ไพ่ในมือคนอื่นไม่เคยถูกส่งลงมา (uno_table.view คัดออกให้แล้ว)
    """
    uid = int(require_player(request)["uid"])
    from bot.cards import uno_table

    with _user_lock(uid):
        if body.action == "start":
            return {"ok": True, "table": uno_table.view(uid, uno_table.start(uid, bots=body.bots))}
        if body.action == "quit":
            uno_table.clear(uid)
            return {"ok": True, "table": {"playing": False}}
        if body.action == "view":
            return {"ok": True, "table": uno_table.view(uid)}

        if body.action == "play":
            ok, r = uno_table.play(uid, body.index, suit=body.suit or None)
        elif body.action == "draw":
            ok, r = uno_table.draw(uid)
        elif body.action == "take":
            ok, r = uno_table.take_stack(uid)
        elif body.action == "pass":
            ok, r = uno_table.passes(uid)
        elif body.action == "uno":
            ok, r = uno_table.say_uno(uid)
        else:
            raise HTTPException(400, "ไม่รู้จักคำสั่งนี้")
    if not ok:
        raise HTTPException(400, r["error"])
    return {"ok": True, **r}


@router.get("/uno")
def uno_current(request: Request):
    """โต๊ะที่ค้างอยู่ (ถ้ามี) — เปิดหน้าเว็บมาเจอโต๊ะเดิม"""
    uid = int(require_player(request)["uid"])
    from bot.cards import uno_table
    return {"ok": True, "table": uno_table.view(uid)}


class UnoRoomBody(BaseModel):
    action: str = "view"       # view | create | join | leave | start | play | draw | take_stack | pass | say_uno
    code: str = ""             # รหัสห้องตอน join
    bet: int = 0                # เดิมพันตอน create
    index: int = 0              # ไพ่ใบที่เท่าไหร่ในมือ ตอน play
    suit: str = ""              # สีที่เลือกตอนวางไวลด์


@router.post("/uno/room")
def uno_room_do(body: UnoRoomBody, request: Request):
    """🎴 โต๊ะ UNO เดิมพัน — ชวนเพื่อนเล่น แยกขาดจากปุ่มซ้อมกับบอท

    🔒 ทุกคำสั่งผูกกับ uid ที่ล็อกอินอยู่เท่านั้น เบราว์เซอร์ระบุแทนคนอื่นไม่ได้
    ตอบกลับด้วย uno_room.view(uid) เท่านั้น — ไม่ส่ง state ดิบ
    """
    uid = int(require_player(request)["uid"])
    from bot.cards import uno_room

    def _name():
        p = player_model_get(uid)
        return p.get("rank") or f"ผู้เล่น {uid}"

    with _user_lock(uid):
        if body.action == "create":
            ok, r = uno_room.open_table(uid, _name(), body.bet)
            if not ok:
                raise HTTPException(400, r["error"])
        elif body.action == "join":
            ok, r = uno_room.sit(uid, _name(), body.code)
            if not ok:
                raise HTTPException(400, r["error"])
        elif body.action == "leave":
            uno_room.stand(uid)
        elif body.action == "start":
            ok, r = uno_room.begin(uid)
            if not ok:
                raise HTTPException(400, r["error"])
        elif body.action == "play":
            ok, r = uno_room.play(uid, body.index, suit=body.suit or None)
            if not ok:
                raise HTTPException(400, r["error"])
        elif body.action == "draw":
            ok, r = uno_room.draw(uid)
            if not ok:
                raise HTTPException(400, r["error"])
        elif body.action == "take_stack":
            ok, r = uno_room.take_stack(uid)
            if not ok:
                raise HTTPException(400, r["error"])
        elif body.action == "pass":
            ok, r = uno_room.passes(uid)
            if not ok:
                raise HTTPException(400, r["error"])
        elif body.action == "say_uno":
            ok, r = uno_room.say_uno(uid)
            if not ok:
                raise HTTPException(400, r["error"])
        elif body.action != "view":
            raise HTTPException(400, "ไม่รู้จักคำสั่งนี้")
        return uno_room.view(uid)


@router.get("/uno/room")
def uno_room_state(request: Request):
    uid = int(require_player(request)["uid"])
    from bot.cards import uno_room
    return uno_room.view(uid)


@router.get("/blackjack")
def blackjack_current(request: Request):
    """โต๊ะที่ค้างอยู่ (ถ้ามี) — เปิดหน้าเว็บมาเจอมือที่เปิดค้างไว้ในดิสได้"""
    uid = require_player(request)["uid"]
    from bot import blackjack_core
    state = blackjack_core.load_game(int(uid))
    if not state:
        return {"playing": False}
    return {"playing": True, "game": blackjack_core._view(state)}


@router.get("/shop/items")
def shop_items(request: Request):
    """ของที่ร้านขาย — กรอง purchasable เหมือนหน้าร้านในดิสเป๊ะ"""
    require_player(request)
    from bot import config_loader
    from core.services.items import usable_kind
    out = [{"id": iid, "name": d.get("name", iid), "buy": int(d.get("buy", 0)),
            "sell": int(d.get("sell", 0)), "type": d.get("type", ""),
            "kind": usable_kind(d), "usable": bool(usable_kind(d))}
           for iid, d in config_loader.get_all_items().items()
           if d.get("purchasable", True)]
    out.sort(key=lambda x: x["buy"])
    return {"items": out}


class ShopBody(BaseModel):
    action: str
    item_id: str
    count: int = 1


@router.post("/shop")
def shop(body: ShopBody, request: Request):
    """ซื้อ/ขายไอเทมกับร้าน — buy_item_for()/sell_item_for() ตัวเดียวกับปุ่มร้านในดิส

    ซื้อได้ทีละหลายชิ้น (จำนวนถูกตรวจซ้ำใน buy_item_for เสมอ — เบราว์เซอร์ส่งอะไรมาก็ไม่เชื่อ)
    """
    uid = require_player(request)["uid"]
    if body.action not in ("buy", "sell"):
        raise HTTPException(400, "ไม่รู้จักคำสั่งนี้")

    from bot import adventure_core
    from core.services.items import buy_item_for, sell_item_for
    with _user_lock(uid):
        if body.action == "buy":
            ok, msg = buy_item_for(int(uid), body.item_id, body.count)
        else:
            ok, msg = sell_item_for(int(uid), body.item_id)
        adventure_core.touch_pending(int(uid))    # แวะซื้อของระหว่างสู้ = ยังอยู่กับไฟต์นั้น
    return {"ok": ok, "message": msg, "money": _money_now(uid)}


@router.get("/market")
def market_list(request: Request):
    """🏪 ตลาดผู้เล่น — แผงขายที่เปิดอยู่ + ของเราที่ฝากขายไว้ + ของในกระเป๋าที่ลงขายได้

    ไม่ส่งไอดีคนขายออกไป (บอกแค่ว่า "ของคุณ" ไหม) — หน้าเว็บไม่มีเหตุผลต้องรู้ว่าใครเป็นใคร
    """
    uid = int(require_player(request)["uid"])
    from bot import config_loader, market
    from core.services.items import usable_kind
    from bot.models.player_model import get_player, load_inventory

    items = config_loader.get_all_items()
    name = lambda i: items.get(str(i), {}).get("name", f"ไอเทม {i}")

    listings = [{"id": lid, "item_id": str(iid), "name": name(iid), "price": int(price),
                 "mine": sid == uid}
                for lid, sid, iid, price in market.open_listings()]
    mine = [{"id": lid, "item_id": str(iid), "name": name(iid), "price": int(price)}
            for lid, iid, price in market.my_listings(uid)]

    # ของในกระเป๋าที่ลงขายได้ — รวมชิ้นซ้ำเป็นแถวเดียวเหมือนหน้ากระเป๋า
    counts = {}
    for i in load_inventory((get_player(uid) or {}).get("inventory", "")):
        counts[str(i)] = counts.get(str(i), 0) + 1
    bag = [{"id": i, "name": name(i), "count": n, "kind": usable_kind(items.get(i, {})),
            "sell": int(items.get(i, {}).get("sell", 0))}
           for i, n in sorted(counts.items(), key=lambda kv: name(kv[0]))]

    cfg = config_loader.get_config().get("market", {})
    return {"enabled": bool(cfg.get("enabled", True)),
            "tax_percent": int(cfg.get("tax_percent", 0) or 0),
            "min_price": int(cfg.get("min_price", 1) or 1),
            "max_price": int(cfg.get("max_price", 10**12) or 10**12),
            "max_listings": int(cfg.get("max_listings_per_player", 5) or 5),
            "listings": listings, "mine": mine, "bag": bag}


class MarketBody(BaseModel):
    action: str
    listing_id: int = 0
    item_id: str = ""
    price: int = 0


@router.post("/market")
def market_action(body: MarketBody, request: Request):
    """ลงขาย / ยกเลิก / ซื้อ — market.py ตัวเดียวกับ !market ในดิส

    เงินกับของทั้งหมดขยับใน transaction เดียวฝั่ง market.py — เว็บไม่แตะเองสักบรรทัด
    (ปิดการขายด้วย compare-and-swap แล้ว สองคนกดซื้อพร้อมกันคนที่สองจะถูกปฏิเสธ)
    """
    uid = int(require_player(request)["uid"])
    if body.action not in ("list", "cancel", "buy"):
        raise HTTPException(400, "ไม่รู้จักคำสั่งนี้")

    from bot import market
    with _user_lock(uid):
        if body.action == "list":
            ok, msg = market.list_item(uid, body.item_id, body.price)
        elif body.action == "cancel":
            ok, msg = market.cancel_listing(uid, body.listing_id)
        else:
            ok, msg = market.buy_listing(uid, body.listing_id)
    if not ok:
        raise HTTPException(400, msg)
    return {"ok": True, "message": msg, "money": _money_now(uid)}


@router.get("/craft/list")
def craft_list(request: Request):
    """สูตรที่วัตถุดิบครบพร้อมคราฟตอนนี้ — craftable_now() ตัวเดียวกับปุ่ม 🔨 ในดิส"""
    uid = require_player(request)["uid"]
    from core.services.crafting import craftable_now
    rows = craftable_now(int(uid))
    return {"recipes": [{"id": i, "name": n, "materials": m} for i, n, m in rows]}


class CraftBody(BaseModel):
    item_id: str


@router.post("/craft")
def craft(body: CraftBody, request: Request):
    """คราฟของ — craft_for() ตัวเดียวกับในดิส (มีโอกาสล้มเหลวตามสูตร)"""
    uid = require_player(request)["uid"]
    from bot import adventure_core
    from core.services.crafting import craft_for
    with _user_lock(uid):
        ok, msg = craft_for(int(uid), str(body.item_id))
        adventure_core.touch_pending(int(uid))    # แวะคราฟระหว่างสู้ = ยังอยู่กับไฟต์นั้น
    return {"ok": ok, "message": msg}


@router.post("/bag/sell-junk")
def sell_junk(request: Request):
    """เทขายวัสดุ/ของขยะทั้งกระเป๋า — sell_all_junk() ตัวเดียวกับปุ่ม 🧱 ในดิส"""
    uid = require_player(request)["uid"]
    from core.services.items import sell_all_junk
    with _user_lock(uid):
        sold, gold, msg = sell_all_junk(int(uid))
    return {"ok": sold > 0, "sold": sold, "gold": gold, "message": msg,
            "money": _money_now(uid)}


@router.get("/bag/junk-preview")
def junk_preview(request: Request):
    """ดูก่อนยืนยันว่าจะขายอะไรไปบ้าง ได้เงินเท่าไหร่

    ใช้เกณฑ์ 'ของขยะ' ชุดเดียวกับ sell_all_junk() — ของกดใช้ได้/อุปกรณ์/ทองคำแท่ง ปลอดภัยเสมอ
    """
    uid = require_player(request)["uid"]
    from bot import config_loader
    from bot.models.player_model import load_inventory

    conn = _game_conn()
    try:
        row = conn.execute("SELECT inventory FROM players WHERE user_id=?", (int(uid),)).fetchone()
    finally:
        conn.close()
    if not row:
        return {"items": [], "gold": 0, "count": 0}

    items = config_loader.get_all_items()
    counts = {}
    for iid in load_inventory(row["inventory"]):
        counts[str(iid)] = counts.get(str(iid), 0) + 1

    out, gold = [], 0
    for iid, n in counts.items():
        d = items.get(iid, {})
        is_junk = (d and not d.get("effect") and not d.get("equip_key")
                   and d.get("type") != "use" and not d.get("bar_value"))
        if not is_junk:
            continue
        each = int(d.get("sell", 0))
        gold += each * n
        out.append({"id": iid, "name": d.get("name", iid), "count": n, "each": each})
    out.sort(key=lambda x: -x["each"] * x["count"])
    return {"items": out, "gold": gold, "count": sum(i["count"] for i in out)}


class DropBody(BaseModel):
    item_id: str
    amount: int = 1


@router.post("/item/drop")
def item_drop(body: DropBody, request: Request):
    """ทิ้งไอเทม — เรียก drop_item_for() ตัวเดียวกับปุ่ม 🗑️ ในดิส (ของหายถาวร)"""
    uid = require_player(request)["uid"]
    if body.amount <= 0:
        raise HTTPException(400, "จำนวนต้องมากกว่า 0")
    from core.services.items import drop_item_for
    with _user_lock(uid):
        ok, msg = drop_item_for(int(uid), str(body.item_id), body.amount)
    return {"ok": ok, "message": msg}


@router.get("/admin/cmdlog")
def admin_cmdlog(request: Request, q: str = ""):
    """log คำสั่งแอดมินในเกม — ค้นด้วยเศษชื่อคน/discord_id/ชื่อคำสั่ง/ข้อความ"""
    require_admin(request)
    sql = "SELECT * FROM admin_logs"
    args = []
    if q.strip():
        like = f"%{q.strip()}%"
        sql += " WHERE discord_id LIKE ? OR user_name LIKE ? OR command LIKE ? OR full_text LIKE ?"
        args = [like, like, like, like]
    with web_db.connect() as conn:
        rows = conn.execute(sql + " ORDER BY id DESC LIMIT 300", args).fetchall()
        total = conn.execute("SELECT COUNT(*) FROM admin_logs").fetchone()[0]
    return {"logs": [dict(r) for r in rows], "total": total}


# ── แอดมิน ──

class AdminLogin(BaseModel):
    secret: str


@router.get("/admin/ping")
def admin_ping(request: Request):
    """เช็คว่า cookie แอดมินยังใช้ได้ — หน้า /admin ใช้ข้ามฟอร์ม login"""
    require_admin(request)
    return {"ok": True}


@router.post("/admin/login")
def admin_login(body: AdminLogin, response: Response):
    from license_server.api import get_or_create_admin_secret
    if not hmac.compare_digest(body.secret.encode(), get_or_create_admin_secret().encode()):
        raise HTTPException(401, "รหัสแอดมินไม่ถูกต้อง")
    _set_cookie(response, "web_admin", {"role": "admin", "exp": time.time() + _ADMIN_TTL})
    return {"ok": True}


# ── ข่าว ──

_CATEGORIES = {"news", "patch", "event"}


class NewsBody(BaseModel):
    title: str
    category: str = "news"
    body: str = ""
    published: bool = True


@router.get("/news")
def list_news(category: str = ""):
    with web_db.connect() as conn:
        sql = "SELECT id, title, category, created_at, substr(body, 1, 200) AS excerpt FROM news WHERE published=1"
        args = []
        if category:
            sql += " AND category=?"
            args.append(category)
        rows = conn.execute(sql + " ORDER BY id DESC", args).fetchall()
    return {"news": [dict(r) for r in rows]}


@router.get("/news/{news_id}")
def get_news(news_id: int):
    with web_db.connect() as conn:
        row = conn.execute("SELECT * FROM news WHERE id=? AND published=1", (news_id,)).fetchone()
    if not row:
        raise HTTPException(404, "ไม่พบข่าวนี้")
    return dict(row)


@router.post("/admin/news")
def create_news(body: NewsBody, request: Request):
    require_admin(request)
    if body.category not in _CATEGORIES:
        raise HTTPException(400, "หมวดต้องเป็น news / patch / event")
    with web_db.connect() as conn:
        cur = conn.execute("INSERT INTO news(title, category, body, published) VALUES (?,?,?,?)",
                           (body.title.strip(), body.category, body.body, int(body.published)))
    return {"ok": True, "id": cur.lastrowid}


@router.put("/admin/news/{news_id}")
def update_news(news_id: int, body: NewsBody, request: Request):
    require_admin(request)
    if body.category not in _CATEGORIES:
        raise HTTPException(400, "หมวดต้องเป็น news / patch / event")
    with web_db.connect() as conn:
        cur = conn.execute(
            "UPDATE news SET title=?, category=?, body=?, published=?, updated_at=datetime('now','localtime') WHERE id=?",
            (body.title.strip(), body.category, body.body, int(body.published), news_id))
    if cur.rowcount == 0:
        raise HTTPException(404, "ไม่พบข่าวนี้")
    return {"ok": True}


@router.delete("/admin/news/{news_id}")
def delete_news(news_id: int, request: Request):
    require_admin(request)
    with web_db.connect() as conn:
        cur = conn.execute("DELETE FROM news WHERE id=?", (news_id,))
    if cur.rowcount == 0:
        raise HTTPException(404, "ไม่พบข่าวนี้")
    return {"ok": True}


# ─────────────────────────────────────────────────────────────────────────────
# 🧭 ผจญภัยบนเว็บ (เว็บเกม เฟส 5.4)
# ทุกผลออกที่เซิร์ฟเวอร์ด้วย adventure_core ตัวเดียวกับ !play ในดิส
# เบราว์เซอร์แค่เอาไปวาดฉากกับเล่นอนิเมชัน — ไม่รู้กฎเกมอะไรเลย
#
# เหตุการณ์ที่เว็บยังเล่นเองไม่ได้ (มอนสเตอร์ / NPC / อีเวนต์พิเศษ) จะ "ไม่ล็อกสถานะ"
# ผู้เล่นจึงไม่มีทางค้างจนเล่นไม่ได้ทั้งสองแพลตฟอร์ม — รอเฟส 5.5-5.6 มาเปิดเพิ่ม
# ─────────────────────────────────────────────────────────────────────────────

_WEB_PLAYABLE = {                     # เหตุการณ์ -> สถานะที่ล็อกไว้ระหว่างรอผู้เล่นเลือก
    "village": "village", "treasure": "treasure_choice", "dungeon": "dungeon_choice",
    "trap": "trap_defense", "travel": "travel_choice", "mugging": "mugging",
    "npc": "npc_choice", "special": "special_choice", "monster": "fighting",
}
_WEB_INSTANT = ("calm", "bank_robbery")     # จบในตัว ไม่ต้องเลือกอะไร

# สถานะที่ถือว่า "ค้างได้แต่ปลดได้" — ตรงกับ lock_states ของ !play ในดิส
# ปลดเฉพาะตอนไม่มีเหตุการณ์รออยู่จริง ไม่งั้นจะกลายเป็นช่องให้รีเฟรชหนีกับดัก
_STALE_STATES = ("village", "npc_choice", "treasure_choice", "dungeon_choice",
                 "trap_defense", "shopping", "travel_choice", "special_choice")


def _is_rogue(player):
    return (player.get("class_name") or "") == "Rogue"


def _start_ambush_fight(uid, text):
    """เข้าไฟต์กลางคันจากเหตุการณ์อื่น (มอนปลอมตัวฉีกคราบ) — เกิดมอนแล้วส่งการ์ดให้เว็บวาด"""
    from bot import adventure_core
    data = adventure_core.spawn_monster(uid, ())
    adventure_core.set_pending(uid, "monster", data)
    return {"text": text, "pending": "monster", "monster": _monster_card(data),
            "money": _money_now(uid)}


def _finish_special(uid, out, outcome, died):
    """ปิดท้ายอีเวนต์พิเศษ — ตาย / ลากเข้าไฟต์ / จบเฉย ๆ

    กติกาชุดเดียวกับ SpecialEventView._finish() ในดิส: ถ้า outcome สั่ง start_fight
    ต้องเกิดมอนแล้วเข้าไฟต์ทันที ไม่ใช่ปล่อยผ่าน
    """
    from bot import adventure_core
    from bot.models import player_model

    if died:
        player_model.update_player_fields(uid, {"current_state": "dead", "last_event": "none"})
        adventure_core.clear_pending(uid)
        out["died"] = True
        return out

    if outcome.get("start_fight"):
        data = adventure_core.spawn_monster(uid, ())
        player_model.update_player_fields(uid, {"current_state": "fighting", "last_event": "none"})
        adventure_core.set_pending(uid, "monster", data)
        out["pending"] = "monster"
        out["monster"] = _monster_card(data)
        out["text"] += "\n👹 **ศัตรูไม่ให้เวลาคุณหายใจ — เข้าสู่การต่อสู้ทันที!**"
        return out

    player_model.update_player_fields(uid, {"current_state": "idle", "last_event": "none"})
    adventure_core.clear_pending(uid)
    return out


@router.post("/adventure/walk")
def adventure_walk(request: Request, steps: int = 1):
    """เดินหนึ่งก้าว — ตรรกะเดียวกับปุ่ม 🧭 ในดิสทุกบรรทัด

    steps>1 = ⏩ เดินเร็ว: เดินรวดจนเจอเหตุการณ์ที่ต้องตัดสินใจจริง
    (มอน/ดันเจี้ยน/โจร/หมู่บ้าน/กับดัก/พาหนะข้ามทวีป) — กติกาเดียวกับปุ่ม ⏩ ในดิส
    """
    uid = int(require_player(request)["uid"])
    from bot import adventure_core, game_modifiers, robbery
    from bot.models import player_model

    with _user_lock(uid):
        # หน้าต่างเหตุการณ์ในดิสมี timeout ของมันเอง เว็บไม่มี จึงต้องหมดอายุเองก่อนเดินก้าวใหม่
        expired_note = adventure_core.expire_pending(uid)

        # สถานะค้างที่ "ไม่มีเหตุการณ์รออยู่จริง" = ของเก่าตกค้าง ปลดให้เหมือนที่ !play ทำ
        # (เช่นฟื้นคืนชีพเสร็จแล้วสถานะเป็น village — ถ้าไม่ปลด ผู้เล่นเดินต่อไม่ได้เลย)
        _p = player_model.get_player(uid) or {}
        if _p.get("current_state") in _STALE_STATES and not adventure_core.get_pending(uid)[0]:
            player_model.update_player_field(uid, "current_state", "idle")

        player = player_model.get_player(uid)
        if not player:
            raise HTTPException(400, "ยังไม่มีตัวละคร — ทักบอทในดิสคอร์ดก่อนหนึ่งครั้ง")
        if player["current_state"] != "idle":
            pending, data = adventure_core.get_pending(uid)
            raise HTTPException(409, f"คุณกำลังติดเหตุการณ์อื่นอยู่ ({pending or player['current_state']})")

        elements = game_modifiers.resolve_player_elements(
            [player.get("race") or "", player.get("class_name") or ""])
        # ⏩ เดินเร็ว: เดินไปเรื่อย ๆ จน "เจอเหตุการณ์ที่ต้องหยุด" เท่านั้น
        # ถ้าหลุดออกมาโดยยังไม่เจอ (เลือดต่ำ/ชนเพดานกันวน) ต้องไม่เอาเหตุการณ์ที่ข้ามมาโชว์
        # ไม่งั้นเดินเร็วจะไปโผล่หีบ/NPC/อีเวนต์พิเศษ ซึ่งผิดกติกา
        fast = int(steps or 1) > 1
        budget = adventure_core.FAST_WALK_MAX if fast else 1
        notes, walked, stopped = [], 0, not fast
        while True:
            pre = adventure_core.step_prelude(uid, player, elements)
            notes.extend(pre["notes"])
            walked += 1
            if pre["dead"]:
                return {"event": "death", "notes": notes, "walked": walked,
                        "text": "💀 คุณล้มลงกลางทาง... พิษกัดกินร่างกายจนหมดสติ"}

            player, statuses, mods = pre["player"], pre["statuses"], pre["mods"]
            event, special, dg_steps = adventure_core.decide_event(
                uid, player, statuses, mods, pre["dg_steps"], pre["last_evt"], pre["cooldown"])
            adventure_core.commit_event(uid, event, pre["last_evt"])

            if not fast:
                break
            if adventure_core.fast_walk_stops_here(event, pre["last_evt"]):
                stopped = True
                break
            if player.get("hp", 0) <= player.get("max_hp", 100) * 0.3:
                notes.append("⚠️ **เลือดต่ำกว่า 30% — หยุดเดินเร็วเพื่อความปลอดภัย** (กินยาก่อนไปต่อ!)")
                break
            if walked >= budget:
                break
            player = player_model.get_player(uid) or player

        if fast and not stopped:
            # เดินมาแล้วแต่ยังไม่เจออะไรที่ต้องหยุด — จบแบบไม่มีเหตุการณ์ (ไม่ล็อกสถานะ)
            player_model.update_player_field(uid, "current_state", "idle")
            return {"event": "fastwalk", "notes": notes, "walked": walked, "fast": True,
                    "continent": player.get("continent") or "main", "playable": True,
                    "pending": None,
                    "text": f"⏩ **เดินเร็วมาแล้ว {walked} ก้าว** — ยังไม่เจออะไรที่ต้องหยุด "
                            "กดเดินต่อได้เลย"} | {"money": _money_now(uid)}

        if expired_note:
            notes.insert(0, expired_note)

        out = {"event": event, "notes": notes, "continent": player.get("continent") or "main",
               "dungeon_steps": dg_steps, "cooldown": pre["cooldown"],
               "walked": walked, "fast": fast,   # เดินมากี่ก้าวก่อนจะเจออันนี้
               "playable": True,      # เว็บจัดการเหตุการณ์นี้เองได้ไหม
               "pending": None}       # ค้างรอผู้เล่นเลือก (None = จบในก้าวเดียว)

        if event == "calm":
            # 🧘 ไม่มีอะไรเกิดขึ้น = ได้พักหายใจ คืนเม็ดคริสตัลให้ (เต็มแล้วไม่ได้อะไร)
            mana_note, _left = adventure_core.calm_bonus(uid, player)
            out["text"] = game_modifiers.pick_calm_text() + ("\n" + mana_note if mana_note else "")
        elif event == "bank_robbery":
            r = robbery.resolve_bank_robbery(uid, player)
            out["text"] = (f"🏦💥 **โจรปล้นธนาคาร!** แก๊งโจรมือโปรเจาะตู้นิรภัยสาขาที่คุณฝากเงินไว้!\n"
                           f"เงินฝากหายไป `{r['lost']:,}` ทอง — เหลือในบัญชี `{r['left']:,}` ทอง{r['theft']}\n"
                           f"*(กันได้ด้วย 🪪 บัตรประกัน — หาซื้อที่ร้านค้าประจำหมู่บ้าน)*")
        elif event == "npc" and adventure_core.npc_disguise(player)[0]:
            # 🎭 สัปดาห์ธีม Masquerade — NPC อาจฉีกคราบเป็นมอน ตัดสินตอนนี้แล้วเก็บไว้ฝั่งเซิร์ฟเวอร์
            # (ห้ามส่งออกไปให้เบราว์เซอร์รู้ ไม่งั้นเปิดดูก็รู้ว่าตัวไหนปลอม)
            masq_cfg, disguised = adventure_core.npc_disguise(player)
            fee = int(masq_cfg.get("inspect_fee", 1500))
            data = {"disguised": disguised, "fee": fee}
            out["encounter"] = {"masquerade": True, "inspect_fee": fee}
            out["text"] = ("🧓 นักเดินทางพเนจรนั่งอยู่ข้างกองไฟ... "
                           "🎭 *สัปดาห์นี้มีธีมปลอมตัว — จ่ายเงินตรวจตัวตนก่อนก็ได้*")
            player_model.update_player_field(uid, "current_state", _WEB_PLAYABLE["npc"])
            adventure_core.set_pending(uid, "npc", data)
            out["pending"] = "npc"
        elif event == "special" and special.get("template") == "instant":
            # ไม่มีสิทธิ์เลือก — จ่ายผลทันทีเหมือนในดิส (เช่น งานเลี้ยงบรรพชน)
            outcome = adventure_core.resolve_instant_special(special)
            lines, died = adventure_core.execute_special_outcome(uid, outcome)
            out["text"] = "\n".join(
                [special.get("intro", "✨ มีบางอย่างเกิดขึ้นตรงหน้าคุณ...")] + lines)
            _finish_special(uid, out, outcome, died)
        elif event in _WEB_PLAYABLE:
            data = {}
            if event == "special":
                data = special
                out["text"] = special.get("intro", "✨ มีบางอย่างเกิดขึ้นตรงหน้าคุณ...")
                out["choices"] = ([c["label"] for c in special.get("choices", [])]
                                  if special.get("template") == "choice" else [])
            elif event == "monster":
                data = adventure_core.spawn_monster(uid, ())
                out["monster"] = _monster_card(data)
                out["text"] = "👹 มีเงาปริศนาพุ่งออกมากระโจนขวางทางคุณ!"
            elif event == "npc":
                out["text"] = "🧓 คุณเจอนักเดินทางพเนจร (NPC) นั่งอยู่ข้างกองไฟ"
            elif event == "travel":
                data = game_modifiers.roll_travel_encounter(player.get("cash", 0))
                out["encounter"] = data
                out["text"] = (f"🧭 ระหว่างทาง... **{data['label']}** ปรากฏขึ้นตรงหน้าคุณ!\n"
                               f"💰 ค่าโดยสาร: `{data['fare']:,}` ทอง (จ่ายจากเงินสดในกระเป๋า)")
            elif event == "mugging":
                total = int(player.get("cash", 0) or 0) + int(player.get("bank", 0) or 0)
                out["win_pct"] = robbery.mug_win_chance(total)
                out["text"] = (f"🥷 **โดนดักปล้น!** โจรถือมีดโผล่จากพุ่มไม้ "
                               f"จ้องถุงทอง `{player.get('cash', 0):,}` ทองของคุณ! "
                               f"*(โอกาสชนะ {out['win_pct']}% — เงินยิ่งหนักยิ่งถ่วงแข้งขา)*")
            else:
                out["text"] = {
                    "village": "🏡 คุณเดินทางมาพบ **'หมู่บ้านอุ่นใจ'**",
                    "treasure": mods["theme_texts"].get("treasure", "📦 คุณพบ **'หีบสมบัติปริศนาลงอักขระโบราณ'**"),
                    "dungeon": "💀 คุณส่องเห็น **'ช่องอุโมงค์ถ้ำใต้พิภพ (Dungeon)'**",
                    "trap": mods["theme_texts"].get("trap", "⚠️ *แก๊ก!* คุณพลาดก้าวขาไปเกี่ยวสายสลิง **'กับดักโบราณ'** เข้าให้แล้ว!"),
                }[event]
            player_model.update_player_field(uid, "current_state", _WEB_PLAYABLE[event])
            adventure_core.set_pending(uid, event, data)
            out["pending"] = event
        else:
            # มอนสเตอร์ / NPC / อีเวนต์พิเศษ — ยังไม่เปิดบนเว็บ ปล่อยสถานะ idle ไว้ ห้ามล็อก
            out["playable"] = False
            out["text"] = "🌫️ มีบางอย่างเคลื่อนไหวอยู่ในเงา... แต่คุณเดินผ่านไปเงียบ ๆ *(เหตุการณ์นี้ยังเล่นได้เฉพาะในดิสคอร์ด)*"

    return out | {"money": _money_now(uid)}


class ActBody(BaseModel):
    action: str = ""


@router.post("/adventure/act")
def adventure_act(body: ActBody, request: Request):
    """ตอบเหตุการณ์ที่ค้างอยู่ — ปุ่มบนเว็บส่ง action มาที่นี่ตัวเดียว"""
    uid = int(require_player(request)["uid"])
    from bot import adventure_core, robbery
    from bot.models import player_model

    with _user_lock(uid):
        event, data = adventure_core.get_pending(uid)
        if not event:
            raise HTTPException(409, "ไม่มีเหตุการณ์ค้างอยู่")
        player = player_model.get_player(uid) or {}
        # กันกดซ้ำ: สถานะต้องยังตรงกับเหตุการณ์ที่ค้างอยู่จริง
        # (ถ้าไม่เช็ค แล้วมีอะไรปลดสถานะไปก่อน จะเปิดหีบ/พักแรมซ้ำได้ฟรี ๆ)
        expected = _WEB_PLAYABLE.get("npc" if event == "npc_quest" else event)
        if player.get("current_state") != expected:
            adventure_core.clear_pending(uid)
            raise HTTPException(409, "เหตุการณ์นี้จบไปแล้ว — กดออกเดินทางใหม่ได้เลย")
        rogue = _is_rogue(player)

        if event == "village":
            r = adventure_core.resolve_village(uid, body.action)
        elif event == "treasure":
            r = adventure_core.resolve_treasure(uid, body.action, rogue)
        elif event == "dungeon":
            r = adventure_core.resolve_dungeon(uid, body.action)
        elif event == "trap":
            r = adventure_core.resolve_trap(uid, rogue)
            # หน้าตากับดักต่างกันตามทวีป — ฝั่งเซิร์ฟเวอร์เป็นคนบอก เบราว์เซอร์แค่วาดตาม
            r["fx"] = {"kind": player.get("continent") or "main", "hit": not r.get("dodged")}
            if "roll" in r:      # ทอยต่ำกว่าค่าหลบของเกราะ = รอด (กติกาสวนทางกับเต๋าไฟต์)
                r["roll"] = {"player_roll": r["roll"], "monster_roll": r["eva"],
                             "labels": ["🎲 ทอยหลบ", "🛡️ ค่าเกราะ"], "win": r["dodged"],
                             "verdict": "หลบพ้น!" if r["dodged"] else "โดนเต็ม ๆ",
                             "player_parts": ["ทอยได้"], "monster_parts": ["ต้องทอยไม่เกินนี้"]}
        elif event == "travel":
            r = adventure_core.resolve_travel(uid, data, body.action)
        elif event == "npc":
            # 🎭 สัปดาห์ปลอมตัว: เข้าไปคุย/ฟังเควสกับตัวปลอม = โดนซุ่มตีก่อนแล้วเข้าไฟต์
            masq = bool((data or {}).get("disguised"))
            if body.action == "inspect":
                r = adventure_core.npc_inspect(uid, masq, (data or {}).get("fee", 1500))
                if not r["ok"]:                       # เงินไม่พอ ยังยืนอยู่ที่เดิม กดใหม่ได้
                    raise HTTPException(400, r["text"])
                if not r["start_fight"]:              # เป็นตัวจริง — คุยต่อได้ ยังไม่จบเหตุการณ์
                    return {"text": r["text"], "pending": "npc",
                            "encounter": {"masquerade": False}, "money": _money_now(uid)}
                return _start_ambush_fight(uid, r["text"])
            if masq and body.action in ("talk", "quest"):
                a = adventure_core.npc_ambush(uid)
                if a["died"]:
                    adventure_core.clear_pending(uid)
                    return {"text": a["text"], "died": True, "money": _money_now(uid)}
                return _start_ambush_fight(uid, a["text"])
            if body.action == "talk":
                r = adventure_core.npc_talk(uid)
            elif body.action == "quest":
                offer = adventure_core.npc_quest_offer(uid)
                if not offer:
                    r = {"text": "🧓 NPC มองกระเป๋าที่ว่างเปล่าของคุณแล้วส่ายหัว "
                                 "'เจ้าไม่มีสิ่งใดที่ข้าต้องการเลย...'"}
                else:
                    # ข้อเสนอเป็นขั้นที่สอง — เก็บไว้ฝั่งเซิร์ฟเวอร์ ห้ามให้เบราว์เซอร์ส่งกลับมาเอง
                    adventure_core.set_pending(uid, "npc_quest", offer)
                    return {"text": offer["text"], "pending": "npc_quest",
                            "money": _money_now(uid)}
            else:
                adventure_core._done(uid, "npc")
                r = {"text": "🤫 คุณแกล้งทำเป็นมองไม่เห็นและเดินผ่าน NPC ไปอย่างรวดเร็ว"}
        elif event == "monster":
            return _fight_action(uid, data, body.action)
        elif event == "npc_quest":
            r = adventure_core.npc_quest_settle(uid, data, body.action == "accept")
        elif event == "special":
            outcome, prefix = adventure_core.special_pick_outcome(data, body.action)
            lines, died = adventure_core.execute_special_outcome(uid, outcome)
            if prefix:
                lines.insert(0, prefix)
            r = {"text": "\n".join(lines) or "…ไม่มีอะไรเกิดขึ้น", "died": died}
            _finish_special(uid, r, outcome, died)
            if r.get("pending") == "monster":
                # ลากเข้าไฟต์ต่อทันที — ห้ามให้ clear_pending ท้ายฟังก์ชันมาล้างมอนทิ้ง
                return r | {"money": _money_now(uid)}
        elif event == "mugging":
            m = robbery.resolve_mugging(uid, body.action)
            if body.action == "flee":
                r = {"text": f"🏃💨 คุณโยนถุงทองสกัดโจรแล้ววิ่งสุดชีวิต — เสีย `{m['lost']:,}` ทอง "
                             f"(เหลือ `{m['cash']:,}`){m['theft']}"}
            elif m["won"]:
                r = {"text": f"⚔️🏆 **คุณสู้จนโจรเผ่นหนี!** ริบของกลางจากโจรได้ `{m['gain']:,}` ทอง "
                             f"(ติดตัวตอนนี้ `{m['cash']:,}`){m['theft']}"}
            else:
                r = {"text": f"⚔️💀 **เงินถ่วงแข้งขาจนสู้ไม่ไหว...** "
                             f"โจรกวาดเงินติดตัวไปหมด `{m['lost']:,}` ทอง!{m['theft']}"}
            r |= m
            if m.get("roll"):
                r["roll"] = {"player_roll": m["roll"], "monster_roll": m["win_pct"],
                             "labels": ["🎲 ทอยสู้", "🥷 โอกาสชนะ"], "win": m["won"],
                             "verdict": "ชนะโจร!" if m["won"] else "สู้ไม่ไหว...",
                             "player_parts": ["ทอยได้"], "monster_parts": ["ต้องทอยไม่เกินนี้"]}
        else:
            raise HTTPException(400, f"เหตุการณ์ {event} ยังเล่นบนเว็บไม่ได้")

        if r.get("error"):                     # เงินไม่พอ ฯลฯ — ยังค้างอยู่ที่เดิม กดใหม่ได้
            raise HTTPException(400, r["error"])
        adventure_core.clear_pending(uid)

    return r | {"money": _money_now(uid)}


@router.get("/adventure/state")
def adventure_state(request: Request):
    """เหตุการณ์ที่ค้างอยู่ — เว็บเรียกตอนเปิดหน้า/รีเฟรช จะได้กลับมาเล่นต่อจุดเดิมได้

    ไม่มีอันนี้ = รีเฟรชแล้วสถานะค้างจนเล่นไม่ได้ทั้งเว็บและดิส
    """
    uid = int(require_player(request)["uid"])
    from bot import adventure_core
    from bot.models import player_model

    adventure_core.expire_pending(uid)
    event, data = adventure_core.get_pending(uid)
    state = (player_model.get_player(uid) or {}).get("current_state", "idle")
    if not event:
        return {"pending": None, "state": state}
    if event == "npc" and isinstance(data, dict) and "disguised" in data:
        # 🎭 ห้ามส่งคำเฉลยออกไป — เปิด devtools ดูก็รู้ทันทีว่าตัวไหนปลอม
        data = {"masquerade": True, "inspect_fee": data.get("fee", 1500)}
    return {"pending": event, "data": data, "state": state}



def _monster_card(f):
    """ข้อมูลมอนที่หน้าจอต้องใช้ — ชื่อ แรงค์ ธาตุ หลอดเลือด (ไม่ส่งสถานะภายในออกไป)"""
    return {"name": f["stats"].get("name", "มอนสเตอร์"), "rank": f["rank"],
            "element": f.get("element"), "hp": f["hp"], "hp_max": f.get("hp_max", f["hp"]),
            "turn": f.get("turn", 1)}


def _fight_action(uid, fight, action):
    """หนึ่งการกระทำในไฟต์บนเว็บ — โจมตี / สกิล / หนี

    ผลทั้งหมดออกที่ adventure_core ตัวเดียวกับปุ่มในดิส เบราว์เซอร์แค่เอาไปเล่นอนิเมชัน
    ยศแรงค์ที่เลื่อนขั้นบนเว็บให้เองไม่ได้ — บอทจะซิงก์ให้ตอนผู้เล่นเข้าเซิร์ฟดิสครั้งถัดไป
    """
    from bot import adventure_core
    from bot.models import player_model

    if action == "flee":
        r = adventure_core.fight_flee(uid, fight)
        if r["outcome"] == "blocked":
            raise HTTPException(400, r["text"])

        # 🎲 โชว์เต๋าที่ทอยจริงเสมอ — เดิมหนีแล้วไม่เห็นอะไรเลย ไม่รู้ว่าเฉียดหรือห่าง
        # (กติกาสวนทางกับเต๋าไฟต์: ทอย "ไม่เกิน" ค่าโอกาสหนี = รอด แบบเดียวกับกับดัก)
        out = {"text": r["text"], "money": _money_now(uid)}
        if "roll" in r:
            fled = r["outcome"] == "fled"
            out["roll"] = {"player_roll": r["roll"], "monster_roll": r["need"],
                           "labels": ["🎲 ทอยหนี", "🏃 โอกาสรอด"], "win": fled,
                           "verdict": "หนีรอด!" if fled else "หนีไม่พ้น!",
                           "player_parts": ["ทอยได้"], "monster_parts": ["ต้องทอยไม่เกินนี้"]}

        if r["outcome"] == "hit":                       # หนีไม่พ้น สู้ต่อ
            adventure_core.set_pending(uid, "monster", r["fight"])
            return out | {"pending": "monster", "outcome": "continue",
                          "monster": _monster_card(r["fight"])}
        adventure_core.clear_pending(uid)
        return out | {"outcome": r["outcome"]}

    skill = action if action.startswith("skill_") else None
    if action != "attack" and not skill:
        raise HTTPException(400, "ไม่รู้จักแอคชั่นนี้")

    t = adventure_core.fight_turn(uid, fight, (), skill)
    if t["outcome"] in ("no_player", "no_mana"):     # ไม่กินเทิร์น กดปุ่มอื่นต่อได้เลย
        raise HTTPException(400, t["text"])

    out = {"outcome": t["outcome"], "monster": _monster_card(t.get("fight", fight)),
           "log": (t.get("skill_log", "") + t.get("combat_log", "")).strip(),
           "roll": {"player_roll": t.get("player_roll", 0), "monster_roll": t.get("monster_roll", 0),
                    "player_parts": t.get("player_parts", []),
                    "monster_parts": t.get("monster_parts", [])},
           "damage_to_monster": t.get("damage_to_monster", 0),
           "damage_to_player": t.get("damage_to_player", 0),
           "healed": t.get("healed", 0), "mana": t.get("mana"),
           "mana_spent": t.get("mana_spent", 0),
           "player_hp": t.get("player_hp", 0)}

    if t["outcome"] in ("monster_fled", "player_fled"):
        adventure_core.clear_pending(uid)
        out["text"] = t["text"]
        return out | {"money": _money_now(uid)}

    if t["outcome"] == "win":
        # carry = ผลของเทิร์นที่ล้มมอน (เลือดที่เพิ่งฮีล/เกราะที่เพิ่งสึก) ต้องเขียนด้วย
        v = adventure_core.fight_victory(uid, t["fight"], carry=t.get("db_updates"))
        adventure_core.clear_pending(uid)
        # โชว์ผลเทิร์นสุดท้ายก่อนสรุปชัยชนะ — ผู้เล่นต้องเห็นว่าตีไปเท่าไหร่ถึงล้ม
        # (ดิสโชว์อยู่ในช่อง "📜 เทิร์นสุดท้าย" ของ embed ชนะ เว็บเคยข้ามไปเลย)
        out["text"] = ((out["log"] + "\n" if out["log"] else "")
                       + f"🏅 **โค่น {t['fight']['stats'].get('name', 'มอนสเตอร์')} สำเร็จ!**\n"
                       f"💰 **+{v['reward']:,}** ทอง   🔷 **+{v['exp']:,}** EXP"
                       + ("\n✨🎉 **LEVEL UP!!** เลเวลเพิ่มเป็น Lv." + str(v["level"]) if v["level_up"] else "")
                       + v["rank_msg"] + v["drops"] + v["battle_end_log"])
        out["reward"] = {"gold": v["reward"], "exp": v["exp"], "level": v["level"],
                         "level_up": v["level_up"]}
        out["got_item"] = bool(v.get("drops"))    # มอนดรอปของ — หน้าเว็บจะได้เล่นเสียงเก็บของ
        return out | {"money": _money_now(uid)}

    if t["outcome"] == "lose":
        player_model.update_player_fields(uid, dict(t.get("db_updates") or {}, current_state="dead"))
        adventure_core.clear_pending(uid)
        out["text"] = "💀 **คุณหมดสติลงกลางสนามรบ...** กดฟื้นคืนชีพเพื่อกลับหมู่บ้าน"
        return out | {"money": _money_now(uid)}

    player_model.update_player_fields(uid, t.get("db_updates") or {})
    adventure_core.set_pending(uid, "monster", t["fight"])
    out["pending"] = "monster"
    out["text"] = out["log"] or "⚔️ ยังไม่มีใครล้ม — สู้ต่อ!"
    return out | {"money": _money_now(uid)}


# ─────────────────────────────────────────────────────────────────────────────
# 🛒 ร้านขายยศ + กาชา (เว็บเกม เฟส 7.4)
# เว็บแจกยศ Discord เองไม่ได้ — หักเงินแล้วโยนเข้า role_grant_queue ให้บอทมาแจก
# แจกไม่สำเร็จบอทจะคืนเงินให้เอง (ดู bot/cogs/role_grant_worker.py)
# ─────────────────────────────────────────────────────────────────────────────

_FACTIONS = ("dark", "light")

BOT_OFFLINE = ("🔌 บอทดิสคอร์ดออฟไลน์อยู่ตอนนี้ — ยศต้องให้บอทเป็นคนมอบ "
               "ถ้าซื้อตอนนี้เงินจะหักไปแล้วยศไม่มา ลองใหม่อีกครั้งเมื่อบอทกลับมา")


@router.get("/roleshop")
def roleshop(faction: str, request: Request):
    """รายการยศ + ราคา + ตู้กาชาของฝ่ายนั้น (อ่านอย่างเดียว)"""
    uid = int(require_player(request)["uid"])
    if faction not in _FACTIONS:
        raise HTTPException(400, "ฝ่ายต้องเป็น dark หรือ light")
    from bot import role_shop_core
    return role_shop_core.shop_view(faction, uid) | {"bot_online": web_db.bot_alive()}


class RoleBuyBody(BaseModel):
    faction: str
    value: str = ""
    action: str = "buy"          # buy = ซื้อเจาะจง | gacha = หมุนตู้


def _queue_grant(uid, data):
    with web_db.connect() as conn:
        cur = conn.execute(
            "INSERT INTO role_grant_queue(discord_id, role_id, label, price, kind) "
            "VALUES (?,?,?,?,?)",
            (str(uid), int(data["role_id"]), data["label"], int(data["price"]), data["kind"]))
    return cur.lastrowid


@router.post("/roleshop")
def roleshop_buy(body: RoleBuyBody, request: Request):
    """ซื้อยศ / หมุนกาชา — ตรรกะเดียวกับปุ่มใน !darkshop / !lightshop"""
    uid = int(require_player(request)["uid"])
    if body.faction not in _FACTIONS:
        raise HTTPException(400, "ฝ่ายต้องเป็น dark หรือ light")
    # บอทดับ = ไม่มีใครแจกยศ ต้องกันตั้งแต่ก่อนหักเงิน ไม่ใช่หักแล้วค่อยไปค้างในคิว
    if not web_db.bot_alive():
        raise HTTPException(503, BOT_OFFLINE)
    from bot import role_shop_core

    with _user_lock(uid):
        if body.action == "gacha":
            ok, data = role_shop_core.prepare_gacha(uid, body.faction)
        elif body.action == "buy":
            ok, data = role_shop_core.prepare_buy(uid, body.faction, body.value)
        else:
            raise HTTPException(400, "ไม่รู้จักแอคชั่นนี้")
        if not ok:
            raise HTTPException(400, data["error"])
        ticket = _queue_grant(uid, data)

    return {"ok": True, "ticket": ticket, "kind": data["kind"], "label": data["label"],
            "price": data["price"], "money": _money_now(uid),
            "text": ("🎲 หมุนกาชาแล้ว! บอทกำลังนำยศไปมอบให้ในดิสคอร์ด"
                     if data["kind"] == "gacha" else
                     "🎉 ซื้อสำเร็จ! บอทกำลังนำยศไปมอบให้ในดิสคอร์ด")}


@router.get("/roleshop/ticket/{ticket_id}")
def roleshop_ticket(ticket_id: int, request: Request):
    """เช็คว่าบอทแจกยศให้แล้วหรือยัง — หน้าเว็บถามซ้ำจนกว่าจะไม่ pending"""
    uid = str(require_player(request)["uid"])
    with web_db.connect() as conn:
        row = conn.execute("SELECT * FROM role_grant_queue WHERE id=? AND discord_id=?",
                           (ticket_id, uid)).fetchone()
    if not row:
        raise HTTPException(404, "ไม่พบรายการนี้")
    return {"status": row["status"], "label": row["label"], "kind": row["kind"],
            "note": row["note"] or "", "money": _money_now(int(uid))}


@router.post("/adventure/respawn")
def adventure_respawn(request: Request):
    """💀 ฟื้นคืนชีพกลับหมู่บ้าน — ตรรกะเดียวกับปุ่มฟื้นในดิส

    ตายบนเว็บแล้วเดิมไม่มีทางฟื้น ค้างที่สถานะ dead จนต้องไปกด !play ในดิส
    """
    uid = int(require_player(request)["uid"])
    from bot import adventure_core
    from bot.models import player_model

    with _user_lock(uid):
        player = player_model.get_player(uid) or {}
        if player.get("current_state") != "dead" and player.get("hp", 1) > 0:
            raise HTTPException(400, "ยังไม่ได้หมดสติ ไม่ต้องฟื้น")
        r = adventure_core.respawn(uid)
        if not r:
            raise HTTPException(400, "ไม่พบข้อมูลตัวละคร")
        # ฟื้นแล้วยืนอยู่ในหมู่บ้านจริง ๆ — เปิดเมนูหมู่บ้านให้เลย จะได้พักแรมฟื้นเลือดต่อได้
        # (เกิดใหม่ได้แค่ 30% ของเลือดเต็ม ไม่ให้เมนูก็ต้องออกเดินทางทั้งที่เลือดน้อย)
        adventure_core.set_pending(uid, "village", {})

    return {"ok": True, "money": _money_now(uid), "hp": r["hp"], "fee": r["fee"],
            "pending": "village",
            "text": (f"🏥 **หมอผีประจำหมู่บ้านดึงวิญญาณคุณกลับมา**\n"
                     f"❤️ ฟื้นที่ `{r['hp']:,}/{r['max_hp']:,}` HP ({r['hp_pct']}% ของเลือดเต็ม)\n"
                     f"💰 ค่าทำพิธี `{r['fee']:,}` ทอง (เหลือ `{r['cash']:,}`)"
                     + (f"\n💀 ความคืบหน้าในดันเจี้ยนหายไป {r['lost_steps']} ตา"
                        if r["lost_steps"] else "")
                     + "\n💎 เม็ดคริสตัลเต็มอีกครั้ง")}


# ─────────────────────────────────────────────────────────────────────────────
# 🎲 กระดานทอยเต๋ารายวัน (เว็บเกม เฟส 8.4)
# โควตา 3 ครั้ง/วัน ใช้ร่วมกับ !board ในดิส — ทอยที่ไหนก็หักโควตาเดียวกัน
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/board")
def board_state(request: Request):
    """กระดานของสัปดาห์นี้ + ตำแหน่งหมาก + โควตาที่เหลือ (อ่านอย่างเดียว)"""
    uid = int(require_player(request)["uid"])
    from bot import dice_board
    return dice_board.state(uid)


@router.post("/board/roll")
def board_roll(request: Request):
    """ทอยหนึ่งครั้ง — โควตาถูกหักในจังหวะเดียวกับการทอย กดรัวไม่ได้ของเกิน"""
    uid = int(require_player(request)["uid"])
    from bot import dice_board
    with _user_lock(uid):
        ok, r = dice_board.roll(uid)
    if not ok:
        raise HTTPException(400, r["error"])
    return r | {"money": _money_now(uid)}


# ─────────────────────────────────────────────────────────────────────────────
# 📚 เมนูสะสม/รางวัล ที่มีในดิสอยู่แล้ว — ต่อขึ้นเว็บ (เว็บเกม รอบเก็บเมนู)
# ทุกอันเรียกโมดูลเดียวกับคำสั่งในดิส เว็บแค่แปลงเป็น JSON พร้อมแสดงผล
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/me/fashion")
def me_fashion(request: Request):
    """👗 ตู้เสื้อผ้า — มีอะไร ใส่อะไรอยู่ (แฟชั่นไม่มีผลต่อค่าต่อสู้เลย)"""
    uid = int(require_player(request)["uid"])
    from bot import fashion
    return fashion.wardrobe(uid)


class FashionBody(BaseModel):
    action: str            # wear | off
    key: str = ""          # รหัสแฟชั่น (ตอนใส่)
    slot: str = ""         # ช่อง (ตอนถอด)


@router.post("/me/fashion")
def me_fashion_set(body: FashionBody, request: Request):
    """ใส่/ถอดแฟชั่น — เช็คว่ามีของจริงที่เซิร์ฟเวอร์เสมอ ห้ามเชื่อเบราว์เซอร์"""
    uid = int(require_player(request)["uid"])
    from bot import fashion
    with _user_lock(uid):
        if body.action == "wear":
            ok, msg = fashion.wear(uid, body.key)
        elif body.action == "off":
            ok, msg = fashion.take_off(uid, body.slot)
        else:
            raise HTTPException(400, "ไม่รู้จักคำสั่งนี้")
    if not ok:
        raise HTTPException(400, msg)
    return {"ok": True, "message": msg, "worn": fashion.worn(player_model_get(uid))}


# player_model_get ย้ายไป api_web/deps.py แล้ว (import ไว้ด้านบน — uno_room_do/worms ก็ใช้ตัวนี้)


# ─────────────────────────────────────────────────────────────────────────────
# 👥 ระบบเพื่อน — ฐานของหมวด PVP (ชวนกันเข้าล็อบบี้)
# เพิ่มด้วยไอดี Discord ที่คัดลอกมาวาง · โปรไฟล์เปิดให้ดูเฉพาะเพื่อนเท่านั้น
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/me/friends")
def me_friends(request: Request):
    uid = int(require_player(request)["uid"])
    from bot import friends
    return friends.list_of(uid)


class FriendBody(BaseModel):
    action: str = "add"        # add | remove
    id: str = ""               # ไอดี Discord ที่คัดลอกมาวาง


@router.post("/me/friends")
def me_friends_edit(body: FriendBody, request: Request):
    uid = int(require_player(request)["uid"])
    from bot import friends
    with _user_lock(uid):
        if body.action == "add":
            ok, msg = friends.add(uid, body.id)
        elif body.action == "remove":
            ok, msg = friends.remove(uid, body.id)
        else:
            raise HTTPException(400, "ไม่รู้จักคำสั่งนี้")
    if not ok:
        raise HTTPException(400, msg)
    return {"ok": True, "message": msg} | friends.list_of(uid)


# ── 🎴 ชวนเพื่อนเข้าห้อง (งานที่ 5) — บอททัก DM ────────────────────────────
# เว็บกับบอทเป็นคนละโปรเซส ตรวจสิทธิ์ที่นี่แล้วโยนคิวให้บอทไปยิง DM จริง
# (แบบแผนเดียวกับ role_grant_queue → bot/cogs/role_grant_worker.py)

class LobbyInviteBody(BaseModel):
    game: str = ""
    to: str = ""
    # ⚠️ ห้ามเพิ่ม from_uid/code ที่นี่เด็ดขาด — ต้องมาจาก session + lobby.room_of() เท่านั้น
    # (ไม่งั้นคนยิง API ตรง ๆ ชวนเข้าห้องคนอื่น หรือปลอมตัวเป็นคนอื่นชวนได้)


@router.post("/lobby/invite")
def lobby_invite(body: LobbyInviteBody, request: Request):
    """🔒 uid คนชวนมาจาก session เท่านั้น · code หาเองจาก lobby.room_of()
    ห้ามรับ from_uid/code จาก body ไม่งั้นคนยิง API ตรง ๆ ชวนเข้าห้องคนอื่นได้"""
    uid = int(require_player(request)["uid"])
    from core.services.lobby_invite import validate
    from bot import friends, lobby

    to_uid = friends.parse_id(body.to)
    game = str(body.game or "")
    code = lobby.room_of(game, uid)
    if not code:
        raise HTTPException(400, "❌ คุณไม่ได้อยู่ในห้องเกมนี้")

    ok, msg = validate(uid, to_uid, game, code)
    if not ok:
        raise HTTPException(400, msg)

    with web_db.connect() as conn:
        conn.execute(
            "INSERT INTO lobby_invite_queue(from_uid, to_uid, game, code) VALUES (?,?,?,?)",
            (str(uid), str(to_uid), game, code))
    return {"ok": True, "message": "📨 ส่งคำเชิญแล้ว รอเพื่อนกดรับในดิสคอร์ด"}


# ─────────────────────────────────────────────────────────────────────────────
# 🪱 สนามรบผลัดเทิร์น — แผนที่ (หมวด PVP เฟส A)
# แผนที่สร้างที่เซิร์ฟเวอร์เสมอ เบราว์เซอร์แค่วาดตาม
# ไม่งั้นเปิด devtools แล้วแก้ให้ตัวเองยืนกลางอากาศได้ทันที
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/pvp/worms/map")
def worms_map(request: Request, seed: int = 0, continent: str = "", players: int = 2):
    """แผนที่หนึ่งใบ — เมล็ดเดียวกันได้แผนที่เดียวกันเป๊ะ (แชร์รหัสแผนที่กับเพื่อนได้)"""
    require_player(request)
    import random as _r

    from bot.game_data import CONTINENTS
    from bot.pvp import terrain

    if continent not in CONTINENTS:
        continent = _r.choice(list(CONTINENTS))
    seed = int(seed) or _r.randrange(1, 10 ** 14)
    return terrain.view(seed, continent, max(2, min(8, int(players))))


class WormsBody(BaseModel):
    action: str = "walk"       # new | walk | jump | attack | end | timeout
    dir: int = 1               # -1 ซ้าย · 1 ขวา
    steps: int = 1
    seed: int = 0
    skill: str = ""            # สกิลที่ใช้ (ตอน attack)
    angle: float | None = None   # มุมเล็ง องศา · ไม่ส่งมาก็ใช้ค่าตั้งต้นตามชนิดท่า
    power: float = 70          # แรงยิง 10-100
    jump_power: float = 1      # แรงกระโดด 0-1 (กดค้างนานยิ่งไกล)
    lean: float = 0            # เอนตัวกลางอากาศ -1..1


@router.post("/pvp/worms/match")
def worms_match(body: WormsBody, request: Request):
    """🤖 ซ้อมกับบอท — ตำแหน่งทุกตัวตัดสินที่เซิร์ฟเวอร์ เบราว์เซอร์ส่งมาแค่ปุ่มที่กด"""
    uid = int(require_player(request)["uid"])
    from bot.pvp import match

    with _user_lock(uid):
        if body.action == "new":
            p = player_model_get(uid)
            from bot import fashion as _fashion
            look = {"race": p.get("race"), "cls": p.get("class_name"),
                    "armor": p.get("armor") or "None", "weapon": p.get("weapon") or "",
                    "fashion": _fashion.worn(p)}
            return match.view(uid, match.new_practice(uid, look, body.seed))
        if body.action == "surrender":
            ok, r = match.surrender(uid)
            if not ok:
                raise HTTPException(400, r["error"])
            return r
        if body.action == "quit":
            match.drop(uid)          # ทิ้งแมตช์ทิ้งไปเลย จะได้กลับมาเจอหน้าเริ่มเกม
            return match.view(uid)
        if body.action in ("end", "timeout"):
            # timeout = เบราว์เซอร์บอกว่านาฬิกาหมด แต่เซิร์ฟเวอร์เช็คเวลาเองอีกที
            # (ปรับนาฬิกาเครื่องตัวเองแล้วขอเทิร์นเพิ่มไม่ได้)
            ok, r = match.end_turn(uid, auto=body.action == "timeout")
        elif body.action == "attack":
            ok, r = match.attack(uid, body.skill, body.angle, body.power, body.dir)
        elif body.action in ("walk", "jump"):
            ok, r = match.move(uid, body.action, body.dir, body.steps,
                               body.jump_power, body.lean)
        else:
            raise HTTPException(400, "ไม่รู้จักคำสั่งนี้")
    if not ok:
        raise HTTPException(400, r["error"])
    return r


@router.get("/pvp/worms/match")
def worms_match_state(request: Request):
    uid = int(require_player(request)["uid"])
    from bot.pvp import match
    return match.view(uid)


class RoomBody(BaseModel):
    action: str = "view"       # view | create | join | leave | plan | team | start
    code: str = ""             # รหัสห้องตอน join
    plan: str = ""             # ffa | 3v3 | 2v2v2
    team: int = 0
    seed: int = 0


@router.post("/pvp/worms/room")
def worms_room(body: RoomBody, request: Request):
    """🎪 ห้องเล่นหลายคน — แยกขาดจากปุ่มซ้อมกับบอท

    🔒 ทุกคำสั่งผูกกับ uid ที่ล็อกอินอยู่เท่านั้น เบราว์เซอร์ระบุแทนคนอื่นไม่ได้
    """
    uid = int(require_player(request)["uid"])
    from bot.pvp import match, rooms

    def _look():
        p = player_model_get(uid)
        from bot import fashion as _fashion
        return {"race": p.get("race"), "cls": p.get("class_name"),
                "armor": p.get("armor") or "None", "weapon": p.get("weapon") or "",
                "fashion": _fashion.worn(p)}

    def _name():
        # ใช้ยศเป็นชื่อเรียกเหมือนหน้าโปรไฟล์เพื่อน (bot/friends.py) ไม่มีก็ใช้ไอดี
        p = player_model_get(uid)
        return p.get("rank") or f"ผู้เล่น {uid}"

    with _user_lock(uid):
        if body.action == "create":
            rooms.create(uid, _name(), _look())
        elif body.action == "join":
            ok, r = rooms.join(uid, body.code, _name(), _look())
            if not ok:
                raise HTTPException(400, r["error"])
        elif body.action == "leave":
            rooms.leave(uid)
        elif body.action == "plan":
            ok, r = rooms.set_plan(uid, body.plan)
            if not ok:
                raise HTTPException(400, r["error"])
        elif body.action == "team":
            ok, r = rooms.set_team(uid, body.team)
            if not ok:
                raise HTTPException(400, r["error"])
        elif body.action == "start":
            ok, r = match.start_room(uid, body.seed)
            if not ok:
                raise HTTPException(400, r["error"])
        elif body.action != "view":
            raise HTTPException(400, "ไม่รู้จักคำสั่งนี้")
        return rooms.view(uid)


@router.get("/pvp/worms/room")
def worms_room_state(request: Request):
    uid = int(require_player(request)["uid"])
    from bot.pvp import rooms
    return rooms.view(uid)


@router.get("/friends/{target_id}/profile")
def friend_profile(target_id: str, request: Request):
    """โปรไฟล์สาธารณะของเพื่อน — ไม่มีทอง/ธนาคาร/ของในกระเป๋าเด็ดขาด"""
    uid = int(require_player(request)["uid"])
    from bot import friends
    ok, data = friends.profile_of(uid, target_id)
    if not ok:
        raise HTTPException(403, data)
    return data


@router.get("/fashion/gacha")
def fashion_gacha(request: Request):
    """🎁 หน้าตู้กาชาแฟชั่น — ปุ่มหมุน เรท ของหน้าตู้ อัญมณีที่มี"""
    uid = int(require_player(request)["uid"])
    from bot import fashion
    return fashion.gacha_view(uid)


class GachaBody(BaseModel):
    action: str = "pull"   # pull | exchange
    tier: str = ""         # ปุ่มหมุน (ตอน pull)
    key: str = ""          # รหัสแฟชั่นที่จะแลก (ตอน exchange)


@router.post("/fashion/gacha")
def fashion_gacha_go(body: GachaBody, request: Request):
    """หมุนกาชา / แลกอัญมณี — หักทองกับสุ่มอยู่ใต้ล็อกเดียวกัน กดรัวสองจอไม่ได้ของฟรี"""
    uid = int(require_player(request)["uid"])
    from bot import fashion
    with _user_lock(uid):
        if body.action == "exchange":
            ok, msg = fashion.exchange(uid, body.key)
            if not ok:
                raise HTTPException(400, msg)
            return {"ok": True, "message": msg} | fashion.gacha_view(uid)
        if body.action != "pull":
            raise HTTPException(400, "ไม่รู้จักคำสั่งนี้")
        ok, r = fashion.pull(uid, body.tier)
    if not ok:
        raise HTTPException(400, r["error"])
    return r | {"money": _money_now(uid)}


@router.get("/me/pets")
def me_pets(request: Request):
    """🐾 สัตว์เลี้ยงที่จับได้ + ตัวที่ติดอยู่"""
    uid = int(require_player(request)["uid"])
    from bot import pets
    from bot.models import player_model
    owned = pets.owned(uid)
    active = (player_model.get_player(uid) or {}).get("pet", "")
    return {"active": active,
            "pets": [{"key": p["key"], "name": p["name"], "dice": p.get("dice", 0),
                      "from_rank": p.get("from_rank", ""), "owned": p["key"] in owned,
                      "active": p["key"] == active}
                     for p in pets.all_pets()]}


class PetBody(BaseModel):
    key: str = ""


@router.post("/me/pets")
def me_pets_equip(body: PetBody, request: Request):
    """ติด/ปล่อยสัตว์เลี้ยง — ตรรกะเดียวกับปุ่มในดิส (มีแล้วเท่านั้นถึงติดได้)"""
    uid = int(require_player(request)["uid"])
    from bot import pets
    with _user_lock(uid):
        ok, msg = pets.set_active(uid, body.key)
    if not ok:
        raise HTTPException(400, msg)
    return {"ok": True, "message": msg}


@router.get("/me/daily")
def me_daily(request: Request):
    """📅 เควสรายวัน + ความคืบหน้า + streak"""
    uid = int(require_player(request)["uid"])
    from bot import config_loader
    from bot.models import player_model
    progress = player_model.get_daily_progress(uid)
    streak, best, _new = player_model.touch_login_streak(uid)
    quests = []
    for q in config_loader.get_daily_quests():
        cur, claimed = progress.get(q["key"], (0, False))
        target = int(q.get("target", 1))
        quests.append({"key": q["key"], "label": q.get("label", q["key"]),
                       "cur": min(cur, target), "target": target, "claimed": bool(claimed),
                       "ready": cur >= target and not claimed,
                       "gold": q.get("gold", 0), "exp": q.get("exp", 0)})
    return {"quests": quests, "streak": streak, "best": best,
            "claimable": any(q["ready"] for q in quests)}


@router.post("/me/daily/claim")
def me_daily_claim(request: Request):
    uid = int(require_player(request)["uid"])
    from bot import daily
    with _user_lock(uid):
        msg = daily.claim_all(uid)
    return {"ok": True, "message": msg, "money": _money_now(uid)}


@router.get("/me/achievements")
def me_achievements(request: Request):
    """🏅 ความสำเร็จ + ฉายาที่ปลดแล้ว"""
    uid = int(require_player(request)["uid"])
    from bot import achievements, config_loader
    from bot.models import player_model
    stats = achievements.player_stats(uid)
    done = achievements.unlocked_keys(uid)
    cur_title = (player_model.get_player(uid) or {}).get("title", "")
    items = []
    for a in config_loader.get_config().get("achievements", []):
        cur = int(stats.get(a.get("stat", ""), 0) or 0)
        target = int(a.get("target", 1))
        items.append({"key": a["key"], "label": a.get("label", a["key"]),
                      "desc": a.get("desc", ""), "cur": min(cur, target), "target": target,
                      "done": a["key"] in done, "gold": a.get("gold", 0),
                      "title": a.get("title", "")})
    return {"achievements": items, "titles": sorted(achievements.unlocked_titles(uid)),
            "title": cur_title, "stats": stats}


class TitleBody(BaseModel):
    title: str = ""


@router.post("/me/title")
def me_set_title(body: TitleBody, request: Request):
    """เปลี่ยนฉายา — ต้องปลดจากความสำเร็จมาแล้วเท่านั้น"""
    uid = int(require_player(request)["uid"])
    from bot import achievements
    with _user_lock(uid):
        ok, msg = achievements.set_title(uid, body.title)
    if not ok:
        raise HTTPException(400, msg)
    return {"ok": True, "message": msg}


@router.get("/me/books")
def me_books(request: Request):
    """📕 สมุดมอน + 🧬 สมุดธาตุ — สองสมุดในคำขอเดียว (หน้าเดียวกันอ่านทั้งคู่)"""
    uid = int(require_player(request)["uid"])
    from bot import game_modifiers
    from bot.models import player_model
    from bot.adventure_core import MONSTER_RANKS
    ranks = list(MONSTER_RANKS)
    conts = list(game_modifiers.CONTINENTS)
    elements = list(game_modifiers.ELEMENTS)

    bestiary = player_model.get_bestiary(uid)          # {(ทวีป, แรงค์): จำนวน}
    book = player_model.get_element_book(uid)          # {(ทวีป, แรงค์, ธาตุ): จำนวน}

    elem_label = {e: game_modifiers.ELEMENTS[e]["label"] for e in elements}
    out = []
    for c in conts:
        cdata = game_modifiers.CONTINENTS[c]
        pool = (cdata.get("mods", {}) or {}).get("monster_pool", {}) or {}
        out.append({
            "key": c, "label": cdata["label"],
            "done": game_modifiers.element_continent_done(book, c),
            "ranks": [{
                "rank": r,
                "kills": int(bestiary.get((c, r), 0)),
                "monsters": list(pool.get(r, [])),          # ชื่อมอนที่มีในทวีปนี้
                "rank_done": game_modifiers.element_rank_done(book, c, r),
                "elements": [{"key": e, "label": elem_label[e],
                              "got": int(book.get((c, r, e), 0) or 0)} for e in elements],
            } for r in ranks],
        })
    return {
        "ranks": ranks, "elements": elements, "element_labels": elem_label,
        "continents": out,
        "complete": game_modifiers.element_book_complete(book),
        "total_kills": sum(int(v) for v in bestiary.values()),
        "elements_done": sum(1 for c in conts for r in ranks
                             if game_modifiers.element_rank_done(book, c, r)),
        "elements_total": len(conts) * len(ranks),
    }


@router.get("/me/season")
def me_season(request: Request):
    """🎟️ ซีซั่นพาส + ⭐ สายพรีเมียม (ระบบเดียวกัน สองแทร็ก)

    ใช้ season_view() ตัวเดียวกับเอมเบดในดิส — ช่องไหนรับแล้ว/ยังไม่ถึง/ต้องเปิดพรีเมียม
    ต้องตรงกันทั้งสองที่ ห้ามเว็บคำนวณเอง
    """
    uid = int(require_player(request)["uid"])
    from bot import season
    return season.season_view(uid)


@router.post("/me/season/claim")
def me_season_claim(request: Request):
    uid = int(require_player(request)["uid"])
    from bot import season
    with _user_lock(uid):
        msg = season.claim_all(uid)
    return {"ok": True, "message": msg, "money": _money_now(uid)}


@router.post("/me/season/premium")
def me_season_premium(request: Request):
    """ซื้อสายพรีเมียมของซีซั่นนี้"""
    uid = int(require_player(request)["uid"])
    from bot import season
    with _user_lock(uid):
        ok, msg = season.buy_premium(uid)
    if not ok:
        raise HTTPException(400, msg)
    return {"ok": True, "message": msg, "money": _money_now(uid)}


@router.get("/me/partner")
def me_partner(request: Request):
    """💍 คู่หู — ดูสถานะ/โบนัส/ประวัติ (ขอแต่งงานยังต้องทำในดิส เพราะต้องแท็กอีกฝ่าย)"""
    uid = int(require_player(request)["uid"])
    from bot import partner
    pid = partner.partner_of(uid)
    mult, note = partner.bonus_for(uid)
    return {"partner_id": str(pid) if pid else None, "bonus_mult": mult, "note": note,
            "played_today": partner.played_today(uid) if pid else False,
            "history": [str(h) for h in (partner.history_of(uid) or [])],
            "ring": {"name": partner.ring_name(), "price": partner.ring_price(),
                     "has": partner.has_ring(uid)}}
