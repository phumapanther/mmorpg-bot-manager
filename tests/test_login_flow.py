"""🔑 ล็อกอินเข้าเว็บ + เข้าระบบแอดมิน

บั๊กที่ผู้เล่นเจอ: "ระบบล็อกอินมีปัญหา และเข้าแอดมินไม่ได้"
ต้นเหตุจริง — หน้าล็อกอินหมุนถามสถานะทุก 2.5 วินาที เพื่อรอผู้ใช้ไปพิมพ์โค้ดในดิส
แต่ถูกจัดอยู่กลุ่มจำกัดอัตราเดียวกับ "การขอโค้ด" ซึ่งให้แค่ 10 ครั้งต่อ 5 นาที
= หน้าเว็บค้างใน 25 วินาที ก่อนผู้ใช้จะพิมพ์ในดิสทันด้วยซ้ำ

ไฟล์นี้คุมทั้งวงจรล็อกอินและวงจรแอดมิน ไม่ใช่แค่ตัวจำกัดอัตรา
"""
import pathlib
import re
import time

import pytest

import bot.models.player_model as pm
from license_server import rate_limit as R, web_db

DISCORD_ID = "500100000000000001"
LOGIN_PAGE = pathlib.Path("license_server/web_static/login.html").read_text(encoding="utf-8")


@pytest.fixture
def web(tmp_path, monkeypatch):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from license_server import web_api

    monkeypatch.setattr(pm, "DB_NAME", str(tmp_path / "g.db"))
    monkeypatch.setattr(web_db, "DB_PATH", tmp_path / "w.db")
    from license_server.api_web import deps as _api_web_deps

    monkeypatch.setattr(_api_web_deps, "GAME_DB_PATH", tmp_path / "g.db")

    monkeypatch.setattr(web_api, "GAME_DB_PATH", tmp_path / "g.db")  # เผื่อโค้ดเก่าอ่านผ่าน web_api
    pm.init_db()
    app = FastAPI()
    app.include_router(web_api.router)
    R.reset()
    return TestClient(app)


def _confirm(code, uid=DISCORD_ID):
    """จำลองว่าผู้ใช้ไปพิมพ์โค้ดในดิสแล้ว แล้วบอทเติมไอดีให้"""
    with web_db.connect() as conn:
        conn.execute("UPDATE login_codes SET discord_id=? WHERE code=?", (uid, code))


# ── วงจรล็อกอินด้วยโค้ด ──

def test_the_whole_login_loop_works(web):
    code = web.post("/api/web/login/code").json()["code"]
    assert len(code) == 6

    assert web.get(f"/api/web/login/status?code={code}").json()["status"] == "waiting", \
        "ยังไม่ได้ยืนยันในดิสแต่ปล่อยให้เข้าแล้ว"
    assert web.get("/api/web/me/game").status_code in (401, 403)

    _confirm(code)
    assert web.get(f"/api/web/login/status?code={code}").json()["status"] == "ok"
    assert "web_session" in web.cookies, "ยืนยันแล้วแต่ไม่ได้ตั้งคุกกี้ให้"
    assert web.get("/api/web/me/game").status_code == 200, "ล็อกอินแล้วยังเข้าไม่ได้"


def test_a_made_up_code_never_logs_you_in(web):
    r = web.get("/api/web/login/status?code=ZZZZZZ")
    assert r.json().get("status") != "ok"
    assert "web_session" not in web.cookies


def test_an_expired_code_is_refused(web):
    code = web.post("/api/web/login/code").json()["code"]
    _confirm(code)
    with web_db.connect() as conn:
        conn.execute("UPDATE login_codes SET expires_at=? WHERE code=?",
                     (time.time() - 1, code))
    assert web.get(f"/api/web/login/status?code={code}").json().get("status") != "ok", \
        "โค้ดหมดอายุแล้วยังใช้ล็อกอินได้"


# ── 🚦 ที่ทำให้ล็อกอินพังจริง ──

def test_polling_for_five_minutes_never_gets_blocked():
    """หน้าล็อกอินหมุนถามจนกว่าผู้ใช้จะพิมพ์โค้ดในดิสเสร็จ ต้องรอดตลอด 5 นาที"""
    every = _poll_seconds()
    ttl = 300
    R.reset()
    blocked = [i for i in range(int(ttl / every) + 2)
               if not R.check("u", "/api/web/login/status", "GET", now=i * every)[0]]
    R.reset()
    assert not blocked, f"หมุนถามทุก {every} วิ แล้วโดนบล็อก {len(blocked)} ครั้ง"


def test_asking_for_codes_is_still_held_tight():
    """แยกกลุ่มแล้วต้องไม่เผลอปล่อยการ 'ขอโค้ด' ตามไปด้วย"""
    R.reset()
    blocked = [i for i in range(40)
               if not R.check("u", "/api/web/login/code", "POST", now=i * 2)[0]]
    R.reset()
    assert blocked, "กดขอโค้ดรัว 40 ครั้งแล้วไม่โดนบล็อกเลย"
    assert R.LIMITS["auth"][0] <= 15, "เพดานการขอโค้ดหลวมเกินไป"


def test_polling_is_still_too_slow_to_guess_someone_elses_code():
    """โค้ด 6 หลัก — ปล่อยให้หมุนถามได้ แต่ต้องเดาไม่ทันอยู่ดี"""
    from license_server import web_api

    space = len(web_api._CODE_CHARS) ** 6
    limit, window = R.LIMITS["poll"]
    years = space / (limit / window) / 31_536_000
    assert years > 5, f"เดาโค้ดครบทุกแบบใช้แค่ {years:.1f} ปี — หลวมเกินไป"


def test_the_two_login_routes_are_in_different_buckets():
    assert R.group_for("/api/web/login/status", "GET") == "poll"
    assert R.group_for("/api/web/login/code", "POST") == "auth"
    assert R.group_for("/api/web/login/t/abc", "GET") == "auth", \
        "ตั๋วคลิกเดียวควรคุมแน่นเหมือนการขอโค้ด"


def test_the_page_really_polls_that_often():
    """ถ้าหน้าเว็บเปลี่ยนจังหวะหมุนถาม เพดานต้องตามไปด้วย — เทสนี้ผูกสองอย่างเข้าหากัน"""
    assert _poll_seconds() <= 10, "หมุนถามช้าเกินไป ผู้ใช้จะรู้สึกว่าค้าง"
    need = 300 / _poll_seconds()
    assert R.LIMITS["poll"][0] > need, \
        f"หน้าเว็บยิง {need:.0f} ครั้งใน 5 นาที แต่เพดานมีแค่ {R.LIMITS['poll'][0]}"


def _poll_seconds():
    m = re.search(r"setInterval\(poll,\s*(\d+)\)", LOGIN_PAGE)
    assert m, "หาจังหวะหมุนถามใน login.html ไม่เจอ"
    return int(m.group(1)) / 1000


# ── 🔐 แอดมิน ──

def test_the_admin_login_works(web):
    from license_server.api import get_or_create_admin_secret

    assert web.get("/api/web/admin/ping").status_code == 401, "ยังไม่ล็อกอินแต่เข้าได้"
    assert web.post("/api/web/admin/login", json={"secret": "ผิด"}).status_code == 401
    r = web.post("/api/web/admin/login", json={"secret": get_or_create_admin_secret()})
    assert r.status_code == 200, r.text
    assert "web_admin" in web.cookies, "ล็อกอินแอดมินแล้วไม่ได้คุกกี้"
    assert web.get("/api/web/admin/ping").status_code == 200


def test_a_player_session_is_not_an_admin_session(web):
    """คุกกี้ผู้เล่นต้องเปิดหน้าแอดมินไม่ได้ แม้จะเซ็นด้วยกุญแจดอกเดียวกัน"""
    code = web.post("/api/web/login/code").json()["code"]
    _confirm(code)
    web.get(f"/api/web/login/status?code={code}")
    assert web.get("/api/web/me/game").status_code == 200
    assert web.get("/api/web/admin/ping").status_code == 401, "คุกกี้ผู้เล่นเข้าแอดมินได้"


def test_logging_out_of_admin_really_logs_you_out(web):
    from license_server.api import get_or_create_admin_secret

    web.post("/api/web/admin/login", json={"secret": get_or_create_admin_secret()})
    assert web.get("/api/web/admin/ping").status_code == 200
    web.post("/api/web/admin/logout")
    assert web.get("/api/web/admin/ping").status_code == 401, "ออกจากระบบแล้วยังเข้าได้"


def test_admin_login_is_not_rate_limited_into_uselessness():
    """พิมพ์รหัสผิดสองสามครั้งแล้วต้องยังลองใหม่ได้"""
    R.reset()
    blocked = [i for i in range(6)
               if not R.check("u", "/api/web/admin/login", "POST", now=i * 3)[0]]
    R.reset()
    assert not blocked, "พิมพ์รหัสแอดมินผิดไม่กี่ครั้งก็โดนบล็อกแล้ว"
