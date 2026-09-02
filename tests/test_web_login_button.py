"""🔑 ล็อกอินเข้าเว็บด้วยปุ่มในดิสคอร์ด

ลิงก์ที่ออกมา "คือตัวตนผู้เล่น" — ใครเปิดก็เข้าเป็นคนนั้น เทสชุดนี้จึงคุมสองเรื่องหลัก
(1) ตั๋วใช้ได้ครั้งเดียวและหมดอายุจริง (2) ลิงก์ต้องไม่หลุดไปอยู่บนข้อความสาธารณะ
"""
import asyncio
import inspect
import pathlib
import time

import pytest

import bot.cogs.web_link as wl

COG = pathlib.Path("bot/apps/bot_game/web_link.py").read_text(encoding="utf-8")


@pytest.fixture
def web(tmp_path, monkeypatch):
    """web.db เปล่า + API พร้อมยิง"""
    import license_server.web_db as web_db
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from license_server import web_api

    db = tmp_path / "web.db"
    monkeypatch.setattr(web_db, "DB_PATH", db)
    web_db.connect().close()
    app = FastAPI()
    app.include_router(web_api.router)
    return TestClient(app, follow_redirects=False), str(db)


# ── ตั๋ว ──

def test_a_ticket_logs_you_in_exactly_once(web):
    client, db = web
    ok, token = wl.issue_login_ticket(555, db_path=db)
    assert ok and len(token) >= 20

    r = client.get(f"/api/web/login/t/{token}")
    assert r.status_code == 303 and r.headers["location"] == "/play"
    assert "web_session=" in r.headers.get("set-cookie", ""), "ไม่ได้ตั้ง session ให้"

    again = client.get(f"/api/web/login/t/{token}")
    assert again.status_code == 400, "ตั๋วเดิมใช้ซ้ำได้ = ใครก็อปลิงก์ไปก็สวมร่างได้"


def test_the_session_really_is_that_player(web):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from license_server import web_api

    client, db = web
    ok, token = wl.issue_login_ticket(777, db_path=db)
    cookie = client.get(f"/api/web/login/t/{token}").headers["set-cookie"]
    sid = cookie.split("web_session=")[1].split(";")[0]

    app = FastAPI()
    app.include_router(web_api.router)
    c2 = TestClient(app)
    c2.cookies.set("web_session", sid)
    assert c2.get("/api/web/me/session").json()["discord_id"] == "777"


def test_an_expired_ticket_is_refused(web):
    client, db = web
    ok, token = wl.issue_login_ticket(555, db_path=db, ttl=-1)
    assert client.get(f"/api/web/login/t/{token}").status_code == 400


@pytest.mark.parametrize("bad", ["xxx", "a" * 200, "../../etc/passwd", "with space"])
def test_a_made_up_ticket_is_refused(web, bad):
    client, _db = web
    assert client.get(f"/api/web/login/t/{bad}").status_code in (400, 404)


def test_tickets_are_not_guessable():
    """สุ่มสั้นไป = เดาได้ = สวมร่างคนอื่นได้"""
    src = inspect.getsource(wl.issue_login_ticket)
    assert "secrets.token_urlsafe(32)" in src, "ต้องสุ่มด้วย secrets ความยาวพอ"


def test_old_tickets_are_swept_away(web):
    """ตั๋วหมดอายุค้างใน DB ไปเรื่อย ๆ ไม่ดี — ออกตั๋วใหม่ทีก็กวาดทิ้งที"""
    import sqlite3
    client, db = web
    wl.issue_login_ticket(1, db_path=db, ttl=-1)
    wl.issue_login_ticket(2, db_path=db)
    conn = sqlite3.connect(db)
    left = conn.execute("SELECT COUNT(*) FROM login_tickets").fetchone()[0]
    conn.close()
    assert left == 1, "ตั๋วหมดอายุยังค้างอยู่"


# ── ปุ่มในดิสคอร์ด ──

def test_only_the_person_who_typed_the_command_can_press():
    view = wl.WebLoginView(author_id=111)

    class FakeResp:
        def __init__(self): self.sent = []
        async def send_message(self, msg, **kw): self.sent.append((msg, kw))

    class FakeItx:
        def __init__(self, uid): self.user = type("U", (), {"id": uid})(); self.response = FakeResp()

    mine = FakeItx(111)
    assert asyncio.run(view.interaction_check(mine)) is True

    other = FakeItx(222)
    assert asyncio.run(view.interaction_check(other)) is False
    assert other.response.sent[0][1].get("ephemeral") is True, "ต้องเตือนแบบเห็นคนเดียว"


def test_the_public_message_never_carries_the_link():
    """ถ้าแปะลิงก์ไว้บนข้อความสาธารณะ คนอื่นในห้องคลิกก็เข้าเป็นเราได้เลย
    ลิงก์ต้องออกตอนคนที่ใช่กดปุ่ม แล้วส่งแบบเห็นคนเดียวเท่านั้น"""
    cmd = COG[COG.index("async def login(self, ctx)"):COG.index("@login.error")]
    assert "issue_login_ticket" not in cmd, "ออกตั๋วตั้งแต่ตอนพิมพ์คำสั่ง = ลิงก์ลอยอยู่ก่อนใครกด"
    assert "login_url" not in cmd, "ลิงก์ไม่ควรโผล่ในข้อความสาธารณะ"

    press = COG[COG.index("async def go(self, interaction"):]
    assert "issue_login_ticket(interaction.user.id)" in press[:400], "ต้องออกตั๋วให้คนที่กดจริง"
    assert "ephemeral=True" in press[:1200], "ลิงก์ต้องส่งแบบเห็นคนเดียว"


def test_the_button_disappears_by_itself():
    assert wl.WebLoginView(1).timeout == wl.BUTTON_TTL == 10
    cmd = COG[COG.index("async def login(self, ctx)"):COG.index("@login.error")]
    assert "delete_after=BUTTON_TTL" in cmd, "ข้อความต้องลบตัวเองใน 10 วิ"
    assert "async def on_timeout" in COG, "หมดเวลาแล้วต้องเก็บกวาดปุ่มด้วย"


def test_the_command_is_locked_to_the_adventure_channel():
    """ห้องเดียวกับ !adv — อ่านจาก config ไม่ใช่ฝังเลขไว้ในโค้ด"""
    cmd_head = COG[COG.index('@commands.command(name="login"'):COG.index("async def login(self, ctx)")]
    assert 'allowed_channel("adventure")' in cmd_head
    assert "1516704860785873007" not in COG, "ห้ามฝังเลขห้องไว้ในโค้ด (ตั้งใน Panel ได้)"

    from bot import config_loader
    assert config_loader.get_channel_id("adventure"), "config ยังไม่ได้ตั้งห้องผจญภัย"


def test_the_command_has_a_cooldown():
    cmd_head = COG[COG.index('@commands.command(name="login"'):COG.index("async def login(self, ctx)")]
    assert "commands.cooldown(1, BUTTON_TTL, commands.BucketType.user)" in cmd_head
    assert "CommandOnCooldown" in COG, "ติดคูลดาวน์แล้วต้องบอกผู้เล่น ไม่ใช่เงียบ"
