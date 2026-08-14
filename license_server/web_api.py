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
                   "sanity": p.get("sanity"), "state": p.get("current_state") or "idle"},
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
