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
    assert r.status_code == 200 and "Fragment Rift" in r.text


def test_news_category_filter(client):
    _admin(client)
    client.post("/api/web/admin/news", json={"title": "ข่าว", "category": "news", "body": ""})
    client.post("/api/web/admin/news", json={"title": "แพทช์", "category": "patch", "body": ""})
    only = client.get("/api/web/news?category=patch").json()["news"]
    assert len(only) == 1 and only[0]["title"] == "แพทช์"


# ── ล็อกอิน device-code ──

def _bot_confirm(code, discord_id="123456789"):
    """จำลองบอทเขียน discord_id ลงโค้ด (เหมือน !weblogin)"""
    from bot.cogs.web_link import confirm_login_code
    return confirm_login_code(code, discord_id, db_path=str(web_db.DB_PATH))


def test_login_full_flow(client):
    code = client.post("/api/web/login/code").json()["code"]
    assert client.get(f"/api/web/login/status?code={code}").json()["status"] == "waiting"

    ok, _msg = _bot_confirm(code)
    assert ok
    r = client.get(f"/api/web/login/status?code={code}")
    assert r.json()["status"] == "ok" and "web_session" in client.cookies
    assert client.get("/api/web/me/session").json()["discord_id"] == "123456789"
    # โค้ดใช้แล้วใช้ซ้ำไม่ได้
    assert client.get(f"/api/web/login/status?code={code}").status_code == 400


def test_login_bad_codes(client):
    assert client.get("/api/web/login/status?code=ผิดๆ").status_code == 400
    assert client.get("/api/web/login/status?code=ZZZZZZ").status_code == 400   # ไม่มีจริง
    import time
    with web_db.connect() as conn:
        conn.execute("INSERT INTO login_codes(code, expires_at) VALUES ('AAAAAA', ?)", (time.time() - 1,))
    ok, msg = _bot_confirm("AAAAAA")
    assert not ok and "หมดอายุ" in msg                                          # บอทปฏิเสธโค้ดหมดอายุ
    assert client.get("/api/web/login/status?code=AAAAAA").status_code == 400


def test_session_endpoint_requires_login(client):
    assert client.get("/api/web/me/session").status_code == 401


# ── โปรไฟล์ ──

def _login(client, discord_id="555000111"):
    code = client.post("/api/web/login/code").json()["code"]
    _bot_confirm(code, discord_id)
    assert client.get(f"/api/web/login/status?code={code}").json()["status"] == "ok"


def _fake_game_db(tmp_path, monkeypatch, uid=555000111):
    import sqlite3
    from license_server import web_api
    p = tmp_path / "game_data.db"
    conn = sqlite3.connect(p)
    conn.execute("""CREATE TABLE players (user_id INTEGER PRIMARY KEY, level INTEGER, exp INTEGER,
        rank TEXT, hp INTEGER, max_hp INTEGER, cash INTEGER, bank INTEGER,
        continent TEXT, pet TEXT, title TEXT)""")
    conn.execute("INSERT INTO players VALUES (?, 42, 1234, 'S', 80, 120, 5000, 99000, 'frozen', 'dragon', 'ผู้กล้า')",
                 (uid,))
    conn.commit()
    conn.close()
    monkeypatch.setattr(web_api, "GAME_DB_PATH", p)
    return p


def test_profile_requires_login(client):
    assert client.get("/api/web/me/profile").status_code == 401


def test_profile_reads_game_db(client, tmp_path, monkeypatch):
    _fake_game_db(tmp_path, monkeypatch)
    _login(client)
    p = client.get("/api/web/me/profile").json()["profile"]
    assert p["level"] == 42 and p["bank"] == 99000 and p["cash"] == 5000
    assert "น้ำแข็ง" in p["continent_label"]


def test_profile_unknown_player(client, tmp_path, monkeypatch):
    _fake_game_db(tmp_path, monkeypatch)
    _login(client, discord_id="999")
    assert client.get("/api/web/me/profile").json().get("new_player") is True


# ── เติมเงินผ่านเว็บ ──

def _payment_config(monkeypatch):
    from bot import config_loader
    monkeypatch.setattr(config_loader, "get_config", lambda: {"payment": {
        "exchange_rate": 100, "min_amount": 20, "max_amount": 1000,
        "promptpay": {"enabled": True, "id": "0812345678", "name": "ร้านเกม"},
    }})


def test_topup_requires_login(client):
    assert client.post("/api/web/topup", json={"amount_thb": 50}).status_code == 401


def test_topup_create_and_approve_once(client, tmp_path, monkeypatch):
    import sqlite3
    gdb = _fake_game_db(tmp_path, monkeypatch)
    _payment_config(monkeypatch)
    _login(client)

    r = client.post("/api/web/topup", json={"amount_thb": 50})
    assert r.status_code == 200
    d = r.json()
    assert d["gold"] == 5000 and d["qr"]                       # 50 บาท × เรท 100

    _admin(client)
    rows = client.get("/api/web/admin/topups?status=pending").json()["topups"]
    assert rows and rows[0]["id"] == d["id"]

    assert client.post(f"/api/web/admin/topups/{d['id']}/approve", json={"note": ""}).status_code == 200
    conn = sqlite3.connect(gdb)
    bank = conn.execute("SELECT bank FROM players WHERE user_id=555000111").fetchone()[0]
    conn.close()
    assert bank == 99000 + 5000                                # ทองเข้าธนาคารถูกคนถูกจำนวน

    # อนุมัติซ้ำ → 409 และทองต้องไม่เข้าซ้ำ
    assert client.post(f"/api/web/admin/topups/{d['id']}/approve", json={"note": ""}).status_code == 409
    conn = sqlite3.connect(gdb)
    assert conn.execute("SELECT bank FROM players WHERE user_id=555000111").fetchone()[0] == 104000
    conn.close()


def test_topup_reject_no_gold(client, tmp_path, monkeypatch):
    import sqlite3
    gdb = _fake_game_db(tmp_path, monkeypatch)
    _payment_config(monkeypatch)
    _login(client)
    tid = client.post("/api/web/topup", json={"amount_thb": 30}).json()["id"]
    _admin(client)
    assert client.post(f"/api/web/admin/topups/{tid}/reject", json={"note": "สลิปปลอม"}).status_code == 200
    conn = sqlite3.connect(gdb)
    assert conn.execute("SELECT bank FROM players WHERE user_id=555000111").fetchone()[0] == 99000
    conn.close()
    assert client.post(f"/api/web/admin/topups/{tid}/approve", json={"note": ""}).status_code == 409


def test_topup_amount_limits(client, tmp_path, monkeypatch):
    _fake_game_db(tmp_path, monkeypatch)
    _payment_config(monkeypatch)
    _login(client)
    for bad in (-5, 0, 5, 5000):                               # ติดลบ/ศูนย์/ต่ำกว่า min/เกิน max
        assert client.post("/api/web/topup", json={"amount_thb": bad}).status_code == 400


def test_topup_disabled_without_promptpay(client, tmp_path, monkeypatch):
    from bot import config_loader
    _fake_game_db(tmp_path, monkeypatch)
    monkeypatch.setattr(config_loader, "get_config", lambda: {"payment": {}})
    _login(client)
    assert client.post("/api/web/topup", json={"amount_thb": 50}).status_code == 400


def test_topup_qr_revisit_only_own_pending(client, tmp_path, monkeypatch):
    _fake_game_db(tmp_path, monkeypatch)
    _payment_config(monkeypatch)
    _login(client)
    tid = client.post("/api/web/topup", json={"amount_thb": 40}).json()["id"]
    r = client.get(f"/api/web/topup/{tid}/qr")
    assert r.status_code == 200 and r.json()["qr"]              # เปิด QR ซ้ำได้ตอนยัง pending
    _admin(client)
    client.post(f"/api/web/admin/topups/{tid}/reject", json={"note": ""})
    assert client.get(f"/api/web/topup/{tid}/qr").status_code == 400   # จบแล้วดู QR ไม่ได้
    _login(client, discord_id="777")                            # คนอื่นดูรายการเราไม่ได้
    tid2 = None
    assert client.get(f"/api/web/topup/{tid}/qr").status_code in (400, 404)


def test_codex_endpoint(client):
    topics = client.get("/api/web/codex").json()["topics"]
    assert len(topics) == 12
    assert all(t["title"] and (t["fields"] or t["description"]) for t in topics)
    assert any("ธาตุ" in t["title"] for t in topics)


def test_logout_clears_session(client, tmp_path, monkeypatch):
    _fake_game_db(tmp_path, monkeypatch)
    _login(client)
    assert client.get("/api/web/me/session").status_code == 200
    client.post("/api/web/logout")
    assert client.get("/api/web/me/session").status_code == 401
