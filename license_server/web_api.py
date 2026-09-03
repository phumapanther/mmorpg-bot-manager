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
from fastapi import HTTPException, Request
from pydantic import BaseModel

from license_server import web_db
from license_server.api_web import router  # ตัวเดียวกับ api_web.router (รื้อโครงสร้าง 09-02)
from license_server.api_web.deps import (  # noqa: F401  (re-export ให้โค้ด/เทสเก่าเรียกผ่าน web_api ได้)
    GAME_DB_PATH, _ADMIN_TTL, _SESSION_TTL, _game_conn, _key, _money_now,
    _set_cookie, _user_lock, player_model_get, require_admin, require_player, sign, verify,
)
from license_server.api_web.auth import _CODE_CHARS, _CODE_RE, _CODE_TTL, _TICKET_RE  # noqa: F401
from license_server.api_web.topup import _slip_path  # me_profile โชว์ has_slip ในประวัติเติมเงิน
from license_server.api_web.adventure import _finish_special  # noqa: F401  (เทสเก่าเรียกตรง ๆ)


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
