"""🎴 บอททัก DM ชวนเพื่อนเข้าห้อง (งานที่ 5)

เช็คหลัก:
  - เซิร์ฟเวอร์ตัดสินสิทธิ์ทั้งหมด (เพื่อนกันไหม / อยู่ห้องจริงไหม / ห้องเต็ม-เริ่มไปแล้วไหม / สแปม)
  - เพื่อนปิด DM ต้องไม่ crash — บอกรหัสห้องกลับมาให้ก๊อปเอง
  - ปุ่มคำเชิญกันคนอื่นกดแทนกัน (interaction_check)
  - API ห้ามรับ from_uid/code จาก body — เอาจาก session + lobby.room_of() เท่านั้น
"""
import asyncio
import sqlite3
import time
from unittest.mock import AsyncMock, MagicMock

import discord
import pytest

from bot import friends, lobby
from bot.cogs import lobby_invite

ME, PAL, STRANGER = 500100000000000001, 500200000000000002, 500300000000000003


@pytest.fixture(autouse=True)
def db(tmp_path, monkeypatch):
    """ฐานข้อมูลใหม่ทุกเทส — แยก web.db (ล็อบบี้+คิว) กับ player db (เพื่อน)"""
    import bot.models.player_model as pm
    from license_server import web_db

    path = tmp_path / "web.db"

    def _connect():
        conn = sqlite3.connect(str(path), timeout=5)
        conn.row_factory = sqlite3.Row
        conn.executescript(web_db._SCHEMA)
        return conn

    monkeypatch.setattr(web_db, "connect", _connect)
    monkeypatch.setattr(pm, "DB_NAME", str(tmp_path / "players.db"))
    pm.init_db()
    for uid, name in ((ME, "ฉันเอง"), (PAL, "เพื่อนซี้"), (STRANGER, "คนแปลกหน้า")):
        pm.get_player(uid)
        pm.update_player_fields(uid, {"rank": name})

    lobby_invite.reset_rate_limit()
    yield
    lobby_invite.reset_rate_limit()


def _seat(uid, name="ผู้เล่น"):
    return {"uid": str(uid), "name": name}


def _make_room(host=ME, game="uno"):
    st = lobby.create(game, host, _seat(host, "ฉันเอง"))
    return st["room"]


# ── ตรรกะสิทธิ์ (validate) ──

def test_ชวนคนที่ไม่ใช่เพื่อนไม่ได้():
    code = _make_room()
    ok, msg = lobby_invite.validate(ME, STRANGER, "uno", code)
    assert not ok and "เพื่อน" in msg


def test_ชวนตัวเองไม่ได้():
    code = _make_room()
    ok, msg = lobby_invite.validate(ME, ME, "uno", code)
    assert not ok and "ตัวเอง" in msg


def test_คนที่ไม่ได้อยู่ในห้องนั้นชวนคนเข้าห้องไม่ได้():
    friends.add(ME, str(PAL))
    code = _make_room(host=PAL)          # ห้องเป็นของ PAL ไม่ใช่ ME
    ok, msg = lobby_invite.validate(ME, PAL, "uno", code)
    assert not ok and "ไม่ได้อยู่ในห้องนี้" in msg


def test_หองเต็มแล้วชวนไม่ได้():
    friends.add(ME, str(PAL))
    code = _make_room()
    for uid in range(2, lobby.MAX_SEATS + 1):
        lobby.join("uno", uid, code, _seat(uid))
    ok, msg = lobby_invite.validate(ME, PAL, "uno", code)
    assert not ok and "เต็ม" in msg


def test_หองเริ่มเกมแล้วชวนไม่ได้():
    friends.add(ME, str(PAL))
    code = _make_room()
    st = lobby.load(code)
    st["started"] = True
    lobby.save(code, st)
    ok, msg = lobby_invite.validate(ME, PAL, "uno", code)
    assert not ok and "เริ่ม" in msg


def test_สแปมชวนรัวๆโดนจำกัดความถี่():
    friends.add(ME, str(PAL))
    code = _make_room()
    results = [lobby_invite.validate(ME, PAL, "uno", code)[0] for _ in range(lobby_invite.INVITE_LIMIT + 3)]
    assert results.count(True) == lobby_invite.INVITE_LIMIT
    assert results[-1] is False


# ── ส่ง DM จริง (mock bot) ──

def _fake_bot(member=None, forbidden=False):
    bot = MagicMock()
    bot.guilds = []
    fake_member = member
    if forbidden:
        fake_member = MagicMock()
        fake_member.send = AsyncMock(side_effect=discord.Forbidden(MagicMock(status=403), "no dm"))
    bot.fetch_user = AsyncMock(return_value=fake_member)
    return bot


def test_เพื่อนปิดDMไม่crashแต่บอกรหัสห้องกลับมา():
    friends.add(ME, str(PAL))
    code = _make_room()
    bot = _fake_bot(forbidden=True)
    ok, msg = asyncio.run(lobby_invite.send_invite(bot, ME, PAL, "uno", code))
    assert not ok
    assert code in msg and "DM" in msg


def test_ส่งสำเร็จเรียกsendพร้อมview():
    friends.add(ME, str(PAL))
    code = _make_room()
    member = MagicMock()
    member.send = AsyncMock()
    bot = _fake_bot(member=member)
    ok, msg = asyncio.run(lobby_invite.send_invite(bot, ME, PAL, "uno", code))
    assert ok, msg
    member.send.assert_awaited_once()
    _, kwargs = member.send.call_args
    assert isinstance(kwargs.get("view"), lobby_invite.LobbyInviteView)


def test_ไม่เจอสมาชิกเลยก็ไมcrashแค่บอกรหัสห้อง():
    friends.add(ME, str(PAL))
    code = _make_room()
    bot = _fake_bot(member=None)
    ok, msg = asyncio.run(lobby_invite.send_invite(bot, ME, PAL, "uno", code))
    assert not ok and code in msg


def test_ไม่ผ่านสิทธิ์ไม่ยิงDMเลย():
    code = _make_room()          # ไม่ได้เป็นเพื่อนกัน
    bot = _fake_bot()
    ok, msg = asyncio.run(lobby_invite.send_invite(bot, ME, STRANGER, "uno", code))
    assert not ok
    bot.fetch_user.assert_not_called()


# ── ปุ่มคำเชิญ ──

def _mock_interaction(user_id):
    interaction = MagicMock()
    interaction.user.id = user_id
    interaction.response.send_message = AsyncMock()
    interaction.response.edit_message = AsyncMock()
    return interaction


def test_คนอื่นกดปุ่มคำเชิญของเราไม่ได้():
    view = lobby_invite.LobbyInviteView(PAL, "uno", "ABCDE")
    stranger_interaction = _mock_interaction(STRANGER)
    allowed = asyncio.run(view.interaction_check(stranger_interaction))
    assert allowed is False
    stranger_interaction.response.send_message.assert_awaited_once()


def test_เจ้าของคำเชิญกดปุ่มได้():
    view = lobby_invite.LobbyInviteView(PAL, "uno", "ABCDE")
    owner_interaction = _mock_interaction(PAL)
    allowed = asyncio.run(view.interaction_check(owner_interaction))
    assert allowed is True


# ── API เว็บ ──

@pytest.fixture
def web(tmp_path, monkeypatch):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from license_server import web_api

    monkeypatch.setattr(web_api, "GAME_DB_PATH", tmp_path / "players.db")
    app = FastAPI()
    app.include_router(web_api.router)

    def _client_for(uid):
        c = TestClient(app)
        c.cookies.set("web_session", web_api.sign({"uid": str(uid), "exp": time.time() + 3600}))
        return c

    return _client_for


def test_apiต้องล็อกอินก่อน(web):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from license_server import web_api

    app = FastAPI()
    app.include_router(web_api.router)
    c = TestClient(app)
    r = c.post("/api/web/lobby/invite", json={"game": "uno", "to": str(PAL)})
    assert r.status_code in (401, 403)


def test_apiไม่รับ_from_uid_หรือ_code_จาก_body(web):
    """เจตนา: ยิง from_uid/code ปลอมมาต้องไม่มีผล — ยึด session + lobby.room_of() เท่านั้น"""
    friends.add(ME, str(PAL))
    code = _make_room(host=ME)

    alice = web(ME)
    # ยิง from_uid ปลอม (STRANGER) กับ code ห้องอื่นมาด้วย — ต้องถูกเพิกเฉย
    r = alice.post("/api/web/lobby/invite",
                    json={"game": "uno", "to": str(PAL),
                          "from_uid": str(STRANGER), "code": "ZZZZZ"})
    assert r.status_code == 200, r.text
    from license_server import web_db
    with web_db.connect() as conn:
        row = conn.execute("SELECT * FROM lobby_invite_queue").fetchone()
    assert row["from_uid"] == str(ME), "ต้องใช้ uid จาก session เท่านั้น"
    assert row["code"] == code, "ต้องหา code จาก lobby.room_of() เอง ไม่ใช่จาก body"


def test_apiสำเร็จลงคิวให้บอทไปส่งต่อ(web):
    friends.add(ME, str(PAL))
    _make_room(host=ME)
    alice = web(ME)
    r = alice.post("/api/web/lobby/invite", json={"game": "uno", "to": str(PAL)})
    assert r.status_code == 200 and r.json()["ok"] is True

    from license_server import web_db
    with web_db.connect() as conn:
        rows = conn.execute("SELECT * FROM lobby_invite_queue").fetchall()
    assert len(rows) == 1 and rows[0]["status"] == "pending"


def test_apiปฏิเสธถ้าไม่ใช่เพื่อนกัน(web):
    _make_room(host=ME)
    alice = web(ME)
    r = alice.post("/api/web/lobby/invite", json={"game": "uno", "to": str(STRANGER)})
    assert r.status_code == 400


def test_apiปฏิเสธถ้าไม่ได้อยู่ห้องเกมนั้น(web):
    friends.add(ME, str(PAL))
    alice = web(ME)               # ยังไม่ได้เปิด/เข้าห้อง uno ใดๆ
    r = alice.post("/api/web/lobby/invite", json={"game": "uno", "to": str(PAL)})
    assert r.status_code == 400
