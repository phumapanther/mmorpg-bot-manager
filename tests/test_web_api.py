# tests/test_web_api.py
"""API เว็บไซต์เกมบน license_server — auth/ข่าว/ล็อกอิน/โปรไฟล์/เติมเงิน"""
import pytest
from starlette.testclient import TestClient

import license_server.web_db as web_db
from license_server.api import app, get_or_create_admin_secret


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(web_db, "DB_PATH", tmp_path / "web.db")
    c = TestClient(app)
    return c


def _admin(c):
    r = c.post("/api/web/admin/login", json={"secret": get_or_create_admin_secret()})
    assert r.status_code == 200
    return c


# ── แอดมิน auth ──

def test_admin_login_wrong_secret(client):
    assert client.post("/api/web/admin/login", json={"secret": "เดามั่ว"}).status_code == 401


def test_admin_login_sets_cookie(client):
    _admin(client)
    assert "web_admin" in client.cookies


# ── token ลงชื่อ HMAC ──

def test_token_sign_verify_roundtrip():
    from license_server import web_api
    import time
    tok = web_api.sign({"uid": "42", "exp": time.time() + 60})
    assert web_api.verify(tok)["uid"] == "42"
    assert web_api.verify(tok + "x") is None                       # ลายเซ็นพัง
    assert web_api.verify("aaaa.bbbb") is None                     # token มั่ว
    expired = web_api.sign({"uid": "42", "exp": time.time() - 1})
    assert web_api.verify(expired) is None                         # หมดอายุ


# ── ข่าว ──

def test_news_crud_requires_admin(client):
    assert client.post("/api/web/admin/news", json={"title": "x", "body": "y"}).status_code == 401


def test_news_crud_and_public_read(client):
    _admin(client)
    r = client.post("/api/web/admin/news", json={"title": "เปิดเซิร์ฟ!", "category": "news", "body": "# สวัสดี"})
    assert r.status_code == 200
    nid = r.json()["id"]

    lst = client.get("/api/web/news").json()["news"]
    assert any(n["id"] == nid and n["title"] == "เปิดเซิร์ฟ!" for n in lst)
    assert client.get(f"/api/web/news/{nid}").json()["body"] == "# สวัสดี"

    assert client.put(f"/api/web/admin/news/{nid}", json={"title": "แก้แล้ว", "category": "patch", "body": "b2"}).status_code == 200
    assert client.get(f"/api/web/news/{nid}").json()["title"] == "แก้แล้ว"

    assert client.delete(f"/api/web/admin/news/{nid}").status_code == 200
    assert client.get(f"/api/web/news/{nid}").status_code == 404


# ── ข้อมูลเกม + หน้าเว็บ ──

def test_gamedata_complete(client):
    g = client.get("/api/web/gamedata").json()
    assert len(g["continents"]) == 9
    assert len(g["elements"]) == 7
    assert len(g["themes"]) == 13
    keys = {c["key"] for c in g["continents"]}
    assert {"main", "frozen", "demon", "ocean"} <= keys
    assert all(t["label"] for t in g["themes"])


def test_homepage_serves(client):
    r = client.get("/")
    assert r.status_code == 200 and "PanTher" in r.text


def test_news_category_filter(client):
    _admin(client)
    client.post("/api/web/admin/news", json={"title": "ข่าว", "category": "news", "body": ""})
    client.post("/api/web/admin/news", json={"title": "แพทช์", "category": "patch", "body": ""})
    only = client.get("/api/web/news?category=patch").json()["news"]
    assert len(only) == 1 and only[0]["title"] == "แพทช์"
