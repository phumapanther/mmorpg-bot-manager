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
