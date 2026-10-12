"""🛠️ Panel ตั้งค่าบอทใต้ /manage — ต้องอยู่หลังล็อกอินแอดมินเสมอ (เปิดบนลิงก์สาธารณะ)

panel แก้ bot_token / ตั้งค่าเกม / อัปรูปได้ทั้งหมด — ถ้าหลุด auth = ยึดบอทได้ทันที
"""
import importlib

import pytest


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("ADMIN_SECRET", "z" * 32)
    monkeypatch.setenv("CONFIG_PATH", str(tmp_path / "config.json"))
    (tmp_path / "config.json").write_text('{"bot_token":"SECRET-TOKEN","guild_id":1}', encoding="utf-8")
    import license_server.web_db as web_db
    monkeypatch.setattr(web_db, "DB_PATH", tmp_path / "web.db")
    # config_store/routes_config อ่าน CONFIG_PATH ตอน import — reload ให้รับ env ของเทสนี้
    # (บน container ไม่ต้องทำ: env มาก่อน Python เริ่ม จึง import ถูกตั้งแต่แรก)
    import panel.config_store
    importlib.reload(panel.config_store)
    import panel.routes_config
    importlib.reload(panel.routes_config)
    import license_server.api as api
    importlib.reload(api)
    from starlette.testclient import TestClient
    c = TestClient(api.create_app())
    yield c, api
    importlib.reload(api)


def test_ไม่ล็อกอินเข้า_panel_ไม่ได้(client):
    c, _ = client
    # หน้า /manage → redirect ไปล็อกอินแอดมิน
    r = c.get("/manage", follow_redirects=False)
    assert r.status_code == 302 and "/admin" in r.headers["location"]
    # ทุก API ลับ → 401 (ไม่หลุดค่า token/ตั้งค่า)
    assert c.get("/manage/api/config").status_code == 401
    assert c.put("/manage/api/config", json={"bot_token": "HACK"}).status_code == 401
    assert c.get("/manage/api/discord/guilds").status_code == 401
    assert c.get("/manage/api/event-images").status_code == 401
    assert c.post("/manage/api/bot/start").status_code == 401


def test_แอดมินล็อกอินแล้วใช้_panel_ได้(client):
    c, api = client
    r = c.post("/api/web/admin/login", json={"secret": "z" * 32})
    assert r.status_code == 200, r.text
    cfg = c.get("/manage/api/config")
    assert cfg.status_code == 200
    assert cfg.json().get("bot_token") == "SECRET-TOKEN"
    # แก้ตั้งค่าแล้วเซฟได้ (config.json อยู่ใน volume — os.replace ไม่พัง)
    data = cfg.json()
    data["guild_id"] = 999
    assert c.put("/manage/api/config", json=data).status_code == 200
    assert c.get("/manage/api/config").json()["guild_id"] == 999


def test_ทุก_route_ลับใต้_manage_api_มี_require_admin(client):
    """กันคนเพิ่ม route ใหม่ใต้ /manage/api แล้วลืมใส่ล็อก (loop ลงทะเบียนข้าม websocket ได้)"""
    c, _ = client
    from license_server.api_web.deps import require_admin
    bad = []
    for r in c.app.routes:
        path = getattr(r, "path", "")
        if path.startswith("/manage/api/"):
            deps = getattr(getattr(r, "dependant", None), "dependencies", [])
            if require_admin not in [d.call for d in deps]:
                bad.append(path)
    assert not bad, f"route ใต้ /manage/api ไม่มี require_admin: {bad}"


def test_ปุ่มคุมบอทไม่เปิดบอทซ้ำ(client):
    """start/stop/restart เป็น stub — บน NAS บอทรันใน container ถ้าเปิดซ้ำจะชนโทเค็น"""
    c, _ = client
    c.post("/api/web/admin/login", json={"secret": "z" * 32})
    assert c.get("/manage/api/bot/status").json()["running"] is True
    # ไม่ throw / ไม่ spawn อะไร
    assert c.post("/manage/api/bot/start").status_code == 200
    assert c.post("/manage/api/bot/restart").status_code == 200
