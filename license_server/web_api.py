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
    return {"profile": profile, "topups": [dict(t) for t in tops]}


# ── เติมเงินผ่านเว็บ (เงินทุกบาทต้องผ่านมือแอดมิน — ไม่มีอนุมัติอัตโนมัติ) ──

class TopupBody(BaseModel):
    amount_thb: float


class DecideBody(BaseModel):
    note: str = ""


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
    with web_db.connect() as conn:
        cur = conn.execute("INSERT INTO topups(discord_id, amount_thb, gold) VALUES (?,?,?)",
                           (uid, amt, gold))
    return {"id": cur.lastrowid, "gold": gold, "qr": qr,
            "promptpay_name": pp.get("name", ""), "promptpay_id": pp.get("id", "")}


@router.get("/admin/topups")
def list_topups(request: Request, status: str = "pending"):
    require_admin(request)
    with web_db.connect() as conn:
        rows = conn.execute("SELECT * FROM topups WHERE status=? ORDER BY id", (status,)).fetchall()
    return {"topups": [dict(r) for r in rows]}


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
