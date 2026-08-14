# license_server/web_api.py
"""API เว็บไซต์เกม (prefix /api/web) — ข่าว/ล็อกอิน/โปรไฟล์/เติมเงิน/แอดมิน

auth ทั้งหมดเป็น cookie ลงชื่อ HMAC-SHA256 (คีย์ = admin secret ของ license_server)
- web_admin  : {"role": "admin", "exp": ...} อายุ 7 วัน
- web_session: {"uid": "<discord_id>", "exp": ...} อายุ 30 วัน
(สเปค: docs/superpowers/specs/2026-08-05-game-website-design.md)
"""
import base64
import hashlib
import hmac
import json
import time

from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel

from license_server import web_db

router = APIRouter(prefix="/api/web")

_ADMIN_TTL = 7 * 86400
_SESSION_TTL = 30 * 86400


def _key():
    from license_server.api import get_or_create_admin_secret
    return get_or_create_admin_secret().encode()


def sign(payload):
    raw = base64.urlsafe_b64encode(json.dumps(payload).encode()).decode()
    sig = hmac.new(_key(), raw.encode(), hashlib.sha256).hexdigest()
    return f"{raw}.{sig}"


def verify(token):
    """คืน payload ถ้าลายเซ็นถูกและยังไม่หมดอายุ — อย่างอื่นคืน None"""
    try:
        raw, sig = token.rsplit(".", 1)
        expect = hmac.new(_key(), raw.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(sig, expect):
            return None
        data = json.loads(base64.urlsafe_b64decode(raw))
        if float(data.get("exp", 0)) < time.time():
            return None
        return data
    except Exception:
        return None


def _set_cookie(response, name, payload):
    response.set_cookie(name, sign(payload), httponly=True, samesite="lax",
                        max_age=int(payload["exp"] - time.time()))


def require_admin(request: Request):
    data = verify(request.cookies.get("web_admin", ""))
    if not data or data.get("role") != "admin":
        raise HTTPException(401, "ต้องล็อกอินแอดมินก่อน")
    return data


def require_player(request: Request):
    data = verify(request.cookies.get("web_session", ""))
    if not data or not data.get("uid"):
        raise HTTPException(401, "ต้องล็อกอินก่อน")
    return data


# ── ข้อมูลเกม (อ่านจากข้อมูลเกมจริง — อัพเดทเกมแล้วเว็บตรงเสมอ) ──

_ELEMENT_DESC = {
    "fire": "สายบู๊ ตีแรงขึ้น 50%", "water": "ดูดเลือดคืน 35% ของดาเมจ",
    "earth": "ถึกอึด เลือดหนา 2 เท่า", "wind": "ไวเป็นพายุ โบนัสแต้มเต๋า",
    "wood": "รากพันธนาการล็อกเต๋าศัตรู", "dark": "คลั่งตั้งแต่เทิร์นแรก",
    "light": "หายากสุด ล้มได้ทองมหาศาล",
}


@router.get("/gamedata")
def gamedata():
    from bot.game_data import CONTINENTS, WEEKLY_THEMES
    from bot.game_modifiers import ELEMENTS
    from bot import config_loader

    continents = []
    for key, c in CONTINENTS.items():
        pool = c.get("mods", {}).get("monster_pool", {})
        monsters = [{"name": n, "rank": rank} for rank, names in pool.items() for n in names]
        continents.append({"key": key, "label": c["label"],
                           "arrival_text": c.get("arrival_text", ""), "monsters": monsters})
    elements = [{"key": k, "label": v["label"], "desc": _ELEMENT_DESC.get(k, "")}
                for k, v in ELEMENTS.items()]
    themes = [{"key": t["key"], "label": t["label"], "description": t.get("description", "")}
              for t in WEEKLY_THEMES]
    return {"continents": continents, "elements": elements, "themes": themes,
            "invite": config_loader.get_main_server_invite() or ""}


# ── ล็อกอินผ่านบอท (device-code — ไม่ต้องมีโดเมน/OAuth) ──

import re
import secrets

_CODE_RE = re.compile(r"^[A-Z0-9]{6}$")
_CODE_TTL = 300  # โค้ดอายุ 5 นาที
_CODE_CHARS = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"  # ตัดตัวที่อ่านสับสน (I/O/0/1)


@router.post("/login/code")
def login_code():
    code = "".join(secrets.choice(_CODE_CHARS) for _ in range(6))
    with web_db.connect() as conn:
        conn.execute("INSERT INTO login_codes(code, expires_at) VALUES (?, ?)",
                     (code, time.time() + _CODE_TTL))
    return {"code": code, "expires_in": _CODE_TTL}


@router.get("/login/status")
def login_status(code: str, response: Response):
    if not _CODE_RE.match((code or "").upper()):
        raise HTTPException(400, "รูปแบบโค้ดไม่ถูกต้อง")
    code = code.upper()
    with web_db.connect() as conn:
        row = conn.execute("SELECT * FROM login_codes WHERE code=?", (code,)).fetchone()
        if not row or row["used"] or row["expires_at"] < time.time():
            raise HTTPException(400, "โค้ดหมดอายุหรือถูกใช้แล้ว — กดขอโค้ดใหม่")
        if not row["discord_id"]:
            return {"status": "waiting"}
        conn.execute("UPDATE login_codes SET used=1 WHERE code=?", (code,))
    _set_cookie(response, "web_session", {"uid": str(row["discord_id"]),
                                          "exp": time.time() + _SESSION_TTL})
    return {"status": "ok"}


@router.get("/me/session")
def me_session(request: Request):
    return {"discord_id": require_player(request)["uid"]}


@router.post("/logout")
def logout(response: Response):
    response.delete_cookie("web_session")
    return {"ok": True}


@router.post("/admin/logout")
def admin_logout(response: Response):
    response.delete_cookie("web_admin")
    return {"ok": True}


# ── โปรไฟล์ผู้เล่น (อ่าน game_data.db แบบ read-only เท่านั้น) ──

import sqlite3
from pathlib import Path

GAME_DB_PATH = Path(__file__).resolve().parent.parent / "game_data.db"


def _game_conn(readonly=True):
    if not GAME_DB_PATH.exists():
        raise HTTPException(503, "ยังไม่มีข้อมูลเกมบนเครื่องนี้")
    mode = "?mode=ro" if readonly else ""
    conn = sqlite3.connect(f"file:{GAME_DB_PATH}{mode}", uri=True, timeout=5)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA busy_timeout=5000")
    return conn


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
        bag.append({"id": iid, "name": it.get("name", f"ไอเทม {iid}"), "count": n,
                    "type": it.get("type", ""), "sell": it.get("sell", 0),
                    "usable": bool(it.get("effect")) and it.get("type") == "use"})
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
        "vitals": {"hp": p.get("hp"), "max_hp": p.get("max_hp"),
                   "sanity": p.get("sanity"), "state": p.get("current_state") or "idle",
                   # 💎 เม็ดคริสตัลที่เหลือวันนี้ — คิดที่เซิร์ฟเวอร์รวมการเติมข้ามวันแล้ว
                   **{k: v for k, v in _mana_view(p).items()}},
        "money": {"cash": p.get("cash", 0), "bank": p.get("bank", 0)},
        "gear": {
            "armor": {"key": armor_key, "name": armor.get("name", armor_key),
                      "hp": armor.get("hp", 0), "eva": armor.get("eva", 0),
                      "dur": p.get("armor_dur")},
            "weapon": {"key": weapon_key, "name": weapon.get("name", weapon_key or "— มือเปล่า —"),
                       "dur": p.get("weapon_dur")},
            "artifact_slots": p.get("artifact_slots", 1),
        },
        "bag": {"capacity": p.get("capacity", 0), "used": len(inv), "items": bag},
        "buffs": buffs,
    }


# ══ การกระทำในเกมจากเว็บ (เว็บเกม เฟส 2) ══
# ทุก endpoint ในโซนนี้เรียก "ฟังก์ชันชุดเดียวกับที่บอท Discord ใช้" ไม่มีกฎเกมเขียนซ้ำที่นี่

import threading

_user_locks = {}
_locks_guard = threading.Lock()


def _user_lock(uid):
    """ล็อกต่อผู้เล่นหนึ่งคน — กันกดรัวปุ่มแล้วสองคำขอชนกันจนเงินเด้ง

    ponytail: dict โตตามจำนวนผู้เล่นที่เคยยิง API (ล็อกละไม่กี่ไบต์) ไม่ต้องเคลียร์
    """
    with _locks_guard:
        return _user_locks.setdefault(str(uid), threading.Lock())


def _money_now(uid):
    conn = _game_conn()
    try:
        row = conn.execute("SELECT cash, bank FROM players WHERE user_id=?", (int(uid),)).fetchone()
    finally:
        conn.close()
    return {"cash": row["cash"] if row else 0, "bank": row["bank"] if row else 0}


class BankBody(BaseModel):
    action: str
    amount: int
    target_id: str = ""


@router.post("/bank")
def bank(body: BankBody, request: Request):
    """ฝาก/ถอน/โอน — เรียก bank_action() ตัวเดียวกับปุ่มธนาคารในดิส (ค่าธรรมเนียมคิดในนั้น)"""
    uid = require_player(request)["uid"]
    if body.action not in ("deposit", "withdraw", "transfer"):
        raise HTTPException(400, "ไม่รู้จักธุรกรรมนี้")
    if body.amount <= 0:
        raise HTTPException(400, "จำนวนเงินต้องมากกว่า 0")

    target = None
    if body.action == "transfer":
        if not str(body.target_id).isdigit():
            raise HTTPException(400, "ใส่ไอดี Discord ของผู้รับเป็นตัวเลข")
        target = int(body.target_id)

    from bot.cogs.player_commands import bank_action
    with _user_lock(uid):
        ok, msg = bank_action(int(uid), body.action, body.amount, target_id=target)
    return {"ok": ok, "message": msg, "money": _money_now(uid)}


@router.get("/bank/fee")
def bank_fee_preview(amount: int, request: Request):
    """ดูค่าธรรมเนียมก่อนยืนยัน — คิดด้วย bank_fee() ตัวเดียวกับตอนทำจริง

    มีไว้ให้หน้ายืนยันบอกตัวเลขจริงได้ ไม่ต้องให้เบราว์เซอร์คำนวณเอง (จะเพี้ยนจากของจริง)
    """
    require_player(request)
    if amount <= 0:
        raise HTTPException(400, "จำนวนเงินต้องมากกว่า 0")
    from bot.cogs.player_commands import bank_fee
    fee, pct = bank_fee(amount)
    return {"amount": amount, "fee": fee, "pct": pct, "net": amount - fee}


class BarBody(BaseModel):
    action: str
    item_id: str


@router.post("/goldbar")
def goldbar(body: BarBody, request: Request):
    """แลกซื้อ/ขายคืนทองคำแท่ง — เรียก gold_bars ตัวเดียวกับปุ่ม 🧈 ในดิส"""
    uid = require_player(request)["uid"]
    if body.action not in ("buy", "sell"):
        raise HTTPException(400, "ไม่รู้จักคำสั่งนี้")

    from bot import gold_bars
    with _user_lock(uid):
        fn = gold_bars.buy_bar if body.action == "buy" else gold_bars.sell_bar
        ok, msg = fn(int(uid), body.item_id)
    return {"ok": ok, "message": msg, "money": _money_now(uid)}


@router.get("/goldbar/prices")
def goldbar_prices():
    """ราคาซื้อ/ขายคืนของแท่งทองแต่ละขนาด — คิดค่าธรรมเนียมมาให้แล้ว"""
    from bot import config_loader, gold_bars
    pct = gold_bars.fee_pct()
    out = []
    for iid, face in gold_bars.bar_items().items():
        fee = face * pct // 100
        out.append({"id": iid, "name": config_loader.get_item_config(iid).get("name", iid),
                    "face": face, "buy": face + fee, "sell": face - fee})
    return {"fee_pct": pct, "bars": out}


class UseBody(BaseModel):
    item_id: str


@router.post("/item/use")
def item_use(body: UseBody, request: Request):
    """ใช้ไอเทมจากกระเป๋า — เรียก apply_item_effect() ตัวเดียวกับปุ่ม 🧪 ในดิส"""
    uid = require_player(request)["uid"]
    from bot.cogs.player_commands import apply_item_effect
    with _user_lock(uid):
        ok, msg = apply_item_effect(int(uid), str(body.item_id))
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
    out = [{"id": iid, "name": d.get("name", iid), "buy": int(d.get("buy", 0)),
            "sell": int(d.get("sell", 0)), "type": d.get("type", ""),
            "usable": bool(d.get("effect")) and d.get("type") == "use"}
           for iid, d in config_loader.get_all_items().items()
           if d.get("purchasable", True)]
    out.sort(key=lambda x: x["buy"])
    return {"items": out}


class ShopBody(BaseModel):
    action: str
    item_id: str


@router.post("/shop")
def shop(body: ShopBody, request: Request):
    """ซื้อ/ขายไอเทมกับร้าน — buy_item_for()/sell_item_for() ตัวเดียวกับปุ่มร้านในดิส"""
    uid = require_player(request)["uid"]
    if body.action not in ("buy", "sell"):
        raise HTTPException(400, "ไม่รู้จักคำสั่งนี้")

    from bot.cogs.player_commands import buy_item_for, sell_item_for
    with _user_lock(uid):
        fn = buy_item_for if body.action == "buy" else sell_item_for
        ok, msg = fn(int(uid), body.item_id)
    return {"ok": ok, "message": msg, "money": _money_now(uid)}


@router.get("/craft/list")
def craft_list(request: Request):
    """สูตรที่วัตถุดิบครบพร้อมคราฟตอนนี้ — craftable_now() ตัวเดียวกับปุ่ม 🔨 ในดิส"""
    uid = require_player(request)["uid"]
    from bot.cogs.player_commands import craftable_now
    rows = craftable_now(int(uid))
    return {"recipes": [{"id": i, "name": n, "materials": m} for i, n, m in rows]}


class CraftBody(BaseModel):
    item_id: str


@router.post("/craft")
def craft(body: CraftBody, request: Request):
    """คราฟของ — craft_for() ตัวเดียวกับในดิส (มีโอกาสล้มเหลวตามสูตร)"""
    uid = require_player(request)["uid"]
    from bot.cogs.player_commands import craft_for
    with _user_lock(uid):
        ok, msg = craft_for(int(uid), str(body.item_id))
    return {"ok": ok, "message": msg}


@router.post("/bag/sell-junk")
def sell_junk(request: Request):
    """เทขายวัสดุ/ของขยะทั้งกระเป๋า — sell_all_junk() ตัวเดียวกับปุ่ม 🧱 ในดิส"""
    uid = require_player(request)["uid"]
    from bot.cogs.player_commands import sell_all_junk
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
    from bot.cogs.player_commands import drop_item_for
    with _user_lock(uid):
        ok, msg = drop_item_for(int(uid), str(body.item_id), body.amount)
    return {"ok": ok, "message": msg}


# ── เติมเงินผ่านเว็บ (เงินทุกบาทต้องผ่านมือแอดมิน — ไม่มีอนุมัติอัตโนมัติ) ──

class TopupBody(BaseModel):
    amount_thb: float


class DecideBody(BaseModel):
    note: str = ""


@router.get("/topup/rate")
def topup_rate():
    """เรทแลกทอง (public) — หน้า /topup โชว์ว่าเติมเท่าไหร่ได้กี่ทองก่อนกดสร้าง QR"""
    from bot import config_loader
    pay = config_loader.get_config().get("payment", {})
    return {"rate": float(pay.get("exchange_rate") or 0),
            "min_amount": float(pay.get("min_amount") or 0),
            "max_amount": float(pay.get("max_amount") or 0)}


@router.post("/topup")
def create_topup(body: TopupBody, request: Request):
    uid = require_player(request)["uid"]
    from bot import config_loader
    pay = config_loader.get_config().get("payment", {})
    pp = pay.get("promptpay", {})
    if not pp.get("enabled") or not pp.get("id"):
        raise HTTPException(400, "ยังไม่เปิดรับเติมเงินผ่านเว็บ (แอดมินยังไม่ตั้งค่า PromptPay)")
    amt = float(body.amount_thb)
    mn = float(pay.get("min_amount") or 0)
    mx = float(pay.get("max_amount") or 0)
    if amt <= 0 or (mn and amt < mn) or (mx and amt > mx):
        raise HTTPException(400, f"จำนวนเงินต้องอยู่ระหว่าง {mn:g} - {mx:g} บาท")
    gold = int(amt * float(pay.get("exchange_rate") or 0))
    if gold <= 0:
        raise HTTPException(400, "อัตราแลกเปลี่ยนยังไม่ถูกตั้งค่า — แจ้งแอดมิน")
    from bot.promptpay import build_qr_png
    qr = base64.b64encode(build_qr_png(pp["id"], amt).getvalue()).decode()
    # จดเครื่องที่ทำรายการ — หลัง cloudflared IP จริงอยู่ใน cf-connecting-ip (ตรงๆ = client.host)
    ip = (request.headers.get("cf-connecting-ip")
          or (request.headers.get("x-forwarded-for") or "").split(",")[0].strip()
          or (request.client.host if request.client else ""))
    ua = request.headers.get("user-agent", "")[:300]
    with web_db.connect() as conn:
        cur = conn.execute(
            "INSERT INTO topups(discord_id, amount_thb, gold, ip, user_agent) VALUES (?,?,?,?,?)",
            (uid, amt, gold, ip, ua))
    return {"id": cur.lastrowid, "gold": gold, "qr": qr,
            "promptpay_name": pp.get("name", ""), "promptpay_id": pp.get("id", "")}


@router.get("/topup/{topup_id}/qr")
def topup_qr(topup_id: int, request: Request):
    """เปิด QR ของรายการตัวเองซ้ำ — เฉพาะรายการที่ยังรอตรวจ (จบแล้วไม่ควรมีใครโอนเพิ่ม)"""
    uid = require_player(request)["uid"]
    with web_db.connect() as conn:
        row = conn.execute("SELECT * FROM topups WHERE id=? AND discord_id=?",
                           (topup_id, uid)).fetchone()
    if not row:
        raise HTTPException(404, "ไม่พบรายการนี้ของคุณ")
    if row["status"] != "pending":
        raise HTTPException(400, "รายการนี้ถูกตัดสินไปแล้ว — สร้างรายการใหม่ได้ที่หน้าเติมเกม")
    from bot import config_loader
    pp = config_loader.get_config().get("payment", {}).get("promptpay", {})
    if not pp.get("id"):
        raise HTTPException(400, "ระบบเติมเงินปิดอยู่")
    from bot.promptpay import build_qr_png
    qr = base64.b64encode(build_qr_png(pp["id"], row["amount_thb"]).getvalue()).decode()
    return {"id": row["id"], "gold": row["gold"], "amount_thb": row["amount_thb"], "qr": qr,
            "promptpay_name": pp.get("name", ""), "promptpay_id": pp.get("id", "")}


# สลิปหลักฐานโอน — เก็บเป็นไฟล์ตามเลขรายการ (ไม่ต้องแก้ schema): web_uploads/slip_<id>.jpg
UPLOAD_DIR = Path(__file__).resolve().parent / "web_uploads"
_SLIP_MAX = 5 * 1024 * 1024


def _slip_path(topup_id):
    return UPLOAD_DIR / f"slip_{int(topup_id)}.jpg"


@router.post("/topup/{topup_id}/slip")
async def upload_slip(topup_id: int, request: Request):
    from PIL import Image
    import io
    uid = require_player(request)["uid"]
    with web_db.connect() as conn:
        row = conn.execute("SELECT * FROM topups WHERE id=? AND discord_id=?",
                           (topup_id, uid)).fetchone()
    if not row:
        raise HTTPException(404, "ไม่พบรายการนี้ของคุณ")
    if row["status"] != "pending":
        raise HTTPException(400, "รายการนี้ถูกตัดสินไปแล้ว")
    data = await request.body()
    if len(data) > _SLIP_MAX:
        raise HTTPException(400, "ไฟล์ใหญ่เกิน 5MB")
    try:
        img = Image.open(io.BytesIO(data))
        img.load()
    except Exception:
        raise HTTPException(400, "ไฟล์นี้เปิดเป็นรูปภาพไม่ได้ (รองรับ png/jpg/webp)")
    img = img.convert("RGB")
    img.thumbnail((1280, 1280))   # ย่อรูปสลิปใหญ่ๆ ให้พอดี ประหยัดที่
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    img.save(_slip_path(topup_id), format="JPEG", quality=85)
    return {"ok": True}


@router.get("/topup/{topup_id}/slip")
def get_slip(topup_id: int, request: Request):
    from fastapi.responses import FileResponse
    p = _slip_path(topup_id)
    if not p.is_file():
        raise HTTPException(404, "ยังไม่มีสลิปของรายการนี้")
    # แอดมินเปิดได้ทุกใบ — ผู้เล่นเปิดได้เฉพาะรายการตัวเอง
    if not verify(request.cookies.get("web_admin", "")):
        uid = require_player(request)["uid"]
        with web_db.connect() as conn:
            row = conn.execute("SELECT id FROM topups WHERE id=? AND discord_id=?",
                               (topup_id, uid)).fetchone()
        if not row:
            raise HTTPException(404, "ไม่พบรายการนี้ของคุณ")
    return FileResponse(str(p), media_type="image/jpeg")


@router.get("/admin/topups")
def list_topups(request: Request, status: str = "pending", q: str = ""):
    """log เติมเงิน — status=all ดูทุกสถานะ, q ค้นหาด้วยเศษ discord_id หรือเลขรายการ"""
    require_admin(request)
    sql = "SELECT * FROM topups"
    where, args = [], []
    if status != "all":
        where.append("status=?")
        args.append(status)
    if q.strip():
        where.append("(discord_id LIKE ? OR CAST(id AS TEXT)=?)")
        args += [f"%{q.strip()}%", q.strip()]
    if where:
        sql += " WHERE " + " AND ".join(where)
    with web_db.connect() as conn:
        rows = conn.execute(sql + " ORDER BY id DESC LIMIT 300", args).fetchall()
        s = conn.execute(
            "SELECT COUNT(*) AS count, "
            "COALESCE(SUM(CASE WHEN status='approved' THEN amount_thb END), 0) AS approved_thb, "
            "COALESCE(SUM(CASE WHEN status='approved' THEN gold END), 0) AS approved_gold "
            "FROM topups").fetchone()
    return {"topups": [dict(r) | {"has_slip": _slip_path(r["id"]).is_file()} for r in rows],
            "summary": dict(s)}


def _decide_topup(topup_id, new_status, note):
    """CAS เปลี่ยนสถานะจาก pending — คืนแถวเดิม; ถูกตัดสินไปแล้ว → 409 (กันอนุมัติ/ทองเข้าซ้ำ)"""
    with web_db.connect() as conn:
        row = conn.execute("SELECT * FROM topups WHERE id=?", (topup_id,)).fetchone()
        if not row:
            raise HTTPException(404, "ไม่พบรายการนี้")
        cur = conn.execute(
            "UPDATE topups SET status=?, decided_at=datetime('now','localtime'), "
            "decided_by='admin', note=? WHERE id=? AND status='pending'",
            (new_status, note, topup_id))
        if cur.rowcount == 0:
            raise HTTPException(409, f"รายการนี้ถูกตัดสินไปแล้ว (สถานะ: {row['status']})")
    return row


@router.post("/admin/topups/{topup_id}/approve")
def approve_topup(topup_id: int, body: DecideBody, request: Request):
    require_admin(request)
    row = _decide_topup(topup_id, "approved", body.note)
    # เพิ่มทองเข้าธนาคารผู้เล่น — จุดเดียวที่เว็บเขียน game_data.db
    gconn = _game_conn(readonly=False)
    try:
        with gconn:
            cur = gconn.execute("UPDATE players SET bank = bank + ? WHERE user_id=?",
                                (row["gold"], int(row["discord_id"])))
        if cur.rowcount == 0:
            # ผู้เล่นหายจากเกม — คืนสถานะ pending ให้แอดมินตามเรื่องต่อ (ทองยังไม่เข้า)
            with web_db.connect() as conn:
                conn.execute("UPDATE topups SET status='pending', decided_at=NULL WHERE id=?",
                             (topup_id,))
            raise HTTPException(400, "ไม่พบผู้เล่นนี้ในเกม — ทองยังไม่ถูกเพิ่ม รายการกลับเป็นรอตรวจ")
    finally:
        gconn.close()
    return {"ok": True, "gold": row["gold"]}


@router.post("/admin/topups/{topup_id}/reject")
def reject_topup(topup_id: int, body: DecideBody, request: Request):
    require_admin(request)
    _decide_topup(topup_id, "rejected", body.note)
    return {"ok": True}


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


# ── Codex (คู่มือเกมชุดเดียวกับ !codex ในเกม — เว็บตรงกับเกมเสมอ) ──

_CODEX_TOPICS = ["วิธีเล่น", "ทวีป", "ธาตุ", "สถานะ", "ไอเทม", "คราฟ",
                 "อาร์ติแฟกต์", "กิลด์", "รางวัล", "สะสม", "สังคม", "คำสั่ง"]


@router.get("/codex")
def codex():
    from bot.cogs.player_commands import build_codex_embed
    topics = []
    for t in _CODEX_TOPICS:
        e = build_codex_embed(t)
        topics.append({"topic": t, "title": e.title or t, "description": e.description or "",
                       "fields": [{"name": f.name, "value": f.value} for f in e.fields]})
    return {"topics": topics}


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


@router.post("/adventure/walk")
def adventure_walk(request: Request):
    """เดินหนึ่งก้าว — ตรรกะเดียวกับปุ่ม 🧭 ในดิสทุกบรรทัด"""
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
        pre = adventure_core.step_prelude(uid, player, elements)
        if pre["dead"]:
            return {"event": "death", "notes": pre["notes"],
                    "text": "💀 คุณล้มลงกลางทาง... พิษกัดกินร่างกายจนหมดสติ"}

        player, statuses, mods = pre["player"], pre["statuses"], pre["mods"]
        event, special, dg_steps = adventure_core.decide_event(
            uid, player, statuses, mods, pre["dg_steps"], pre["last_evt"], pre["cooldown"])
        adventure_core.commit_event(uid, event, pre["last_evt"])

        if expired_note:
            pre["notes"].insert(0, expired_note)

        out = {"event": event, "notes": pre["notes"], "continent": player.get("continent") or "main",
               "dungeon_steps": dg_steps, "cooldown": pre["cooldown"],
               "playable": True,      # เว็บจัดการเหตุการณ์นี้เองได้ไหม
               "pending": None}       # ค้างรอผู้เล่นเลือก (None = จบในก้าวเดียว)

        if event == "calm":
            out["text"] = game_modifiers.pick_calm_text()
        elif event == "bank_robbery":
            r = robbery.resolve_bank_robbery(uid, player)
            out["text"] = (f"🏦💥 **โจรปล้นธนาคาร!** แก๊งโจรมือโปรเจาะตู้นิรภัยสาขาที่คุณฝากเงินไว้!\n"
                           f"เงินฝากหายไป `{r['lost']:,}` ทอง — เหลือในบัญชี `{r['left']:,}` ทอง{r['theft']}\n"
                           f"*(กันได้ด้วย 🪪 บัตรประกัน — หาซื้อที่ร้านค้าประจำหมู่บ้าน)*")
        elif event == "npc" and adventure_core.npc_disguise(player)[0]:
            # 🎭 สัปดาห์ธีม Masquerade — NPC อาจฉีกคราบเป็นมอนแล้วลากเข้าไฟต์ ซึ่งเว็บยังสู้ไม่ได้
            out["playable"] = False
            out["text"] = ("🧓 นักเดินทางพเนจรนั่งอยู่ข้างกองไฟ... แต่บางอย่างดูผิดปกติ "
                           "คุณเลือกเดินเลี่ยงไป *(สัปดาห์นี้มีธีมปลอมตัว — คุยกับ NPC ได้เฉพาะในดิสคอร์ด)*")
        elif event == "special" and (special.get("template") == "instant"
                                     or adventure_core.special_leads_to_fight(special)):
            # instant จ่ายผลทันทีตั้งแต่ในดิส / อีเวนต์ที่ลากเข้าไฟต์ = เว็บยังไม่รองรับ
            out["playable"] = False
            out["text"] = ("✨ มีบางอย่างเกิดขึ้นตรงหน้าคุณ... แต่คุณเดินผ่านไป "
                           "*(อีเวนต์พิเศษแบบนี้ยังเล่นได้เฉพาะในดิสคอร์ด)*")
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
            player_model.update_player_fields(
                uid, {"current_state": "dead" if died else "idle", "last_event": "none"})
            r = {"text": "\n".join(lines) or "…ไม่มีอะไรเกิดขึ้น", "died": died}
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
        if r["outcome"] == "hit":                       # หนีไม่พ้น สู้ต่อ
            adventure_core.set_pending(uid, "monster", r["fight"])
            return {"text": r["text"], "pending": "monster", "outcome": "continue",
                    "monster": _monster_card(r["fight"]), "money": _money_now(uid)}
        adventure_core.clear_pending(uid)
        return {"text": r["text"], "outcome": r["outcome"], "money": _money_now(uid)}

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
        return out | {"money": _money_now(uid)}

    if t["outcome"] == "lose":
        player_model.update_player_fields(uid, dict(t.get("db_updates") or {}, current_state="dead"))
        adventure_core.clear_pending(uid)
        out["text"] = "💀 **คุณหมดสติลงกลางสนามรบ...** ไปกดฟื้นคืนชีพในดิสคอร์ดด้วย `!play`"
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


@router.get("/roleshop")
def roleshop(faction: str, request: Request):
    """รายการยศ + ราคา + ตู้กาชาของฝ่ายนั้น (อ่านอย่างเดียว)"""
    uid = int(require_player(request)["uid"])
    if faction not in _FACTIONS:
        raise HTTPException(400, "ฝ่ายต้องเป็น dark หรือ light")
    from bot import role_shop_core
    return role_shop_core.shop_view(faction, uid)


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
    return {
        "ranks": ranks, "elements": elements,
        "continents": [{"key": c, "label": game_modifiers.CONTINENTS[c]["label"],
                        "done": game_modifiers.element_continent_done(book, c),
                        "kills": {r: int(bestiary.get((c, r), 0)) for r in ranks},
                        "elements": {r: [e for e in elements if book.get((c, r, e))]
                                     for r in ranks}}
                       for c in conts],
        "complete": game_modifiers.element_book_complete(book),
        "total_kills": sum(int(v) for v in bestiary.values()),
    }


@router.get("/me/season")
def me_season(request: Request):
    """🎟️ ซีซั่นพาส + ⭐ สายพรีเมียม (ระบบเดียวกัน สองแทร็ก)"""
    uid = int(require_player(request)["uid"])
    from bot import config_loader, season
    from bot.models import player_model
    points = int(player_model.get_season_points(uid) or 0)
    premium = season.is_premium(uid)
    tiers = []
    for i, t in enumerate(season.tiers()):
        need = int(t.get("points", 0))
        tiers.append({"index": i, "points": need, "reached": points >= need,
                      "free": t.get("free") or {}, "premium": t.get("premium") or {}})
    return {"points": points, "premium": premium, "tiers": tiers,
            "premium_price": int(config_loader.get_balance("season.premium_price", 0) or 0)}


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
