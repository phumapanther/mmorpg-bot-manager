# license_server/api_web/deps.py
"""ตัวช่วยกลางที่ทุก controller ใน api_web/ ใช้ร่วมกัน

ย้ายมาจาก license_server/web_api.py (รื้อโครงสร้าง 09-02 ขั้นที่ 4)
ห้าม import จาก controller อื่นใน api_web/ — กัน import วน
"""
import base64
import hashlib
import hmac
import json
import os
import sqlite3
import threading
import time
from pathlib import Path

from fastapi import HTTPException, Request

from license_server import web_db

_ADMIN_TTL = 7 * 86400
_SESSION_TTL = 30 * 86400

GAME_DB_PATH = Path(__file__).resolve().parent.parent.parent / "game_data.db"


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


def _game_conn(readonly=True):
    if not GAME_DB_PATH.exists():
        raise HTTPException(503, "ยังไม่มีข้อมูลเกมบนเครื่องนี้")
    mode = "?mode=ro" if readonly else ""
    conn = sqlite3.connect(f"file:{GAME_DB_PATH}{mode}", uri=True, timeout=5)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA busy_timeout=5000")
    return conn


# ── ล็อกต่อผู้เล่นหนึ่งคน — กันกดรัวปุ่มแล้วสองคำขอชนกันจนเงินเด้ง ──

_user_locks = {}
_locks_guard = threading.Lock()


def _user_lock(uid):
    """ponytail: dict โตตามจำนวนผู้เล่นที่เคยยิง API (ล็อกละไม่กี่ไบต์) ไม่ต้องเคลียร์"""
    with _locks_guard:
        return _user_locks.setdefault(str(uid), threading.Lock())


def _money_now(uid):
    conn = _game_conn()
    try:
        row = conn.execute("SELECT cash, bank FROM players WHERE user_id=?", (int(uid),)).fetchone()
    finally:
        conn.close()
    return {"cash": row["cash"] if row else 0, "bank": row["bank"] if row else 0}


def player_model_get(uid):
    from bot.models import player_model
    return player_model.get_player(uid) or {}
