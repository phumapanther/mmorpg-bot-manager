# license_server/api_web/admin.py
"""แอดมิน — login/ping + log คำสั่ง/เติมเงิน + ข่าว (ย้ายจาก web_api.py 09-02)"""
import hmac
import time

from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel

from license_server import web_db
from license_server.api_web.deps import _ADMIN_TTL, _set_cookie, require_admin

router = APIRouter()


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
