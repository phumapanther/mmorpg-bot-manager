"""🔐 เข้าหน้า admin ด้วยรหัสแอดมินซีเคร็ท

พังมาแล้ว: หน้า /admin ยิง admin/ping ถามก่อนว่าเคยล็อกอินไว้ไหม
พอตอบ 401 (ซึ่งถูกต้อง — ยังไม่ได้ล็อกอิน) ตัวห่อ api() ดันเหมาว่า session หมดอายุ
แล้วเด้งป้าย "หมดเวลาเข้าสู่ระบบ" เต็มจอทับฟอร์มกรอกรหัส กดอะไรไม่ได้เลย
"""
import pathlib

import pytest
from fastapi.testclient import TestClient

from license_server import web_api

WEB = pathlib.Path("license_server/web_static")
JS = (WEB / "web.js").read_text(encoding="utf-8")
ADMIN = (WEB / "admin.html").read_text(encoding="utf-8")
SECRET = "ซีเคร็ทของจริง-1234"


@pytest.fixture
def client(monkeypatch, tmp_path):
    import license_server.api as lapi

    monkeypatch.setattr(lapi, "get_or_create_admin_secret", lambda: SECRET)
    from fastapi import FastAPI

    app = FastAPI()
    app.include_router(web_api.router)
    return TestClient(app)


# ── ทางที่คนใช้จริง ──

def test_the_right_secret_gets_you_in(client):
    r = client.post("/api/web/admin/login", json={"secret": SECRET})
    assert r.status_code == 200, f"กรอกรหัสถูกแล้วยังเข้าไม่ได้: {r.text}"
    assert client.cookies.get("web_admin"), "ล็อกอินผ่านแต่ไม่ได้ cookie"
    assert client.get("/api/web/admin/ping").status_code == 200, "ได้ cookie แล้วแต่ ping ยังไม่ผ่าน"


def test_a_wrong_secret_is_refused(client):
    assert client.post("/api/web/admin/login", json={"secret": "มั่ว"}).status_code == 401
    assert not client.cookies.get("web_admin")


def test_ping_says_401_before_you_log_in(client):
    """อันนี้คือพฤติกรรมที่ถูก — หน้าเว็บต่างหากที่ต้องไม่ตีความว่า session หมดอายุ"""
    assert client.get("/api/web/admin/ping").status_code == 401


def test_logging_out_really_drops_the_cookie(client):
    client.post("/api/web/admin/login", json={"secret": SECRET})
    client.post("/api/web/admin/logout")
    assert client.get("/api/web/admin/ping").status_code == 401


def test_an_admin_page_needs_the_cookie(client):
    assert client.get("/api/web/admin/topups?status=pending").status_code == 401
    client.post("/api/web/admin/login", json={"secret": SECRET})
    assert client.get("/api/web/admin/topups?status=pending").status_code == 200


def test_a_forged_cookie_does_not_work(client):
    import base64
    import json

    raw = base64.urlsafe_b64encode(json.dumps({"role": "admin", "exp": 9e9}).encode()).decode()
    client.cookies.set("web_admin", raw + "." + "0" * 64)   # ลายเซ็นมั่ว
    assert client.get("/api/web/admin/ping").status_code == 401, "cookie ปลอมเข้าได้!"


# ── ฝั่งหน้าเว็บ ──

def test_asking_whether_you_are_logged_in_never_shows_the_expired_screen():
    body = JS[JS.index("async function api("):JS.index("let _expiredShown")]
    assert "AUTH_PROBES.some" in body, "ยัง 401 ทีไรก็เด้งป้ายหมดเวลาทุกที"
    for probe in ("/admin/ping", "/admin/login", "/me/session"):
        assert probe in JS, f"ไม่ได้ยกเว้น {probe}"


def test_a_wrong_secret_leaves_the_form_usable():
    """กรอกผิดต้องขึ้นแค่ 'รหัสไม่ถูกต้อง' ให้กรอกใหม่ ไม่ใช่ป้ายเต็มจอทับ"""
    assert '"/admin/login"' in JS.split("async function api(")[0], \
        "admin/login ไม่อยู่ในรายการยกเว้น — กรอกผิดครั้งเดียวก็ต้องรีเฟรชหน้า"
    assert "รหัสไม่ถูกต้อง" in ADMIN


def test_an_expired_admin_goes_back_to_the_admin_page():
    body = JS[JS.index("function onSessionExpired()"):]
    body = body[:body.index("\n}")]
    assert 'location.pathname.startsWith("/admin")' in body, \
        "แอดมินหมดอายุแล้วถูกส่งไปหน้าล็อกอินผู้เล่น ซึ่งกรอกรหัสแอดมินไม่ได้"


def test_the_page_still_skips_the_form_when_the_cookie_is_good():
    assert 'api("GET", "/api/web/admin/ping").then(enter)' in ADMIN, \
        "เคยล็อกอินไว้แล้วยังต้องกรอกรหัสใหม่ทุกครั้ง"
