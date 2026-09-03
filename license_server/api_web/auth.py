# license_server/api_web/auth.py
"""ล็อกอิน/ล็อกเอาท์ — device-code ผ่านบอท + ตั๋วคลิกเดียว (ย้ายจาก web_api.py 09-02)"""
import re
import secrets
import time

from fastapi import APIRouter, HTTPException, Request, Response

from license_server import web_db
from license_server.api_web.deps import _SESSION_TTL, _set_cookie, require_player

router = APIRouter()

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


_TICKET_RE = re.compile(r"^[A-Za-z0-9_-]{20,64}$")


@router.get("/login/t/{token}")
def login_ticket(token: str):
    """🔑 เข้าเกมคลิกเดียวจากปุ่มในดิสคอร์ด — ตั๋วใช้ได้ครั้งเดียวและอายุสั้น

    ตัวตนมาจากตอนบอทออกตั๋ว (บอทรู้อยู่แล้วว่าใครกดปุ่ม) หน้าเว็บจึงไม่ต้องถามอะไรอีก
    ตั๋วรั่วก็ใช้ได้แค่ครั้งเดียวและหมดอายุใน 2 นาที
    """
    from fastapi.responses import RedirectResponse

    tok = (token or "").strip()
    if not _TICKET_RE.match(tok):
        raise HTTPException(400, "ลิงก์เข้าเกมไม่ถูกต้อง")
    with web_db.connect() as conn:
        row = conn.execute("SELECT discord_id, expires_at, used FROM login_tickets WHERE token=?",
                           (tok,)).fetchone()
        if not row or row["used"] or row["expires_at"] < time.time():
            raise HTTPException(400, "ลิงก์นี้ถูกใช้ไปแล้วหรือหมดอายุ — "
                                     "พิมพ์คำสั่งขอลิงก์ใหม่ในดิสคอร์ดได้เลย")
        conn.execute("UPDATE login_tickets SET used=1 WHERE token=?", (tok,))

    resp = RedirectResponse("/play", status_code=303)
    _set_cookie(resp, "web_session", {"uid": str(row["discord_id"]),
                                      "exp": time.time() + _SESSION_TTL})
    return resp


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
