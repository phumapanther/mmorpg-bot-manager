"""🎭 ห้องปาร์ตี้ 5 คน — นั่งบนล็อบบี้กลาง (bot/lobby.py)

⚠️ lobby.MAX_SEATS = 6 (ค่าของสนามรบ) แต่เจ้าของเกมเคาะว่าปาร์ตี้ 5 คน
   ชั้นนี้ต้องคุม 5 เอง ห้ามไปแก้ค่าในล็อบบี้กลาง — สนามรบใช้อยู่
"""
import sqlite3

import pytest

from bot.games.party import room


@pytest.fixture(autouse=True)
def db(tmp_path, monkeypatch):
    """ฐานข้อมูลใหม่ทุกเทส — ห้องจากเทสก่อนหน้าห้ามค้างมากวน"""
    from license_server import web_db
    path = tmp_path / "web.db"

    def _connect():
        conn = sqlite3.connect(str(path), timeout=5)
        conn.row_factory = sqlite3.Row
        conn.executescript(web_db._SCHEMA)
        return conn

    monkeypatch.setattr(web_db, "connect", _connect)
    yield


def _full_party():
    """ปาร์ตี้เต็ม 5 คน — คืนสถานะห้อง"""
    _, st = room.open_party(1, "เอ")
    for uid in range(2, 6):
        room.join_party(uid, f"P{uid}", st["room"])
    return st


# ── เปิด/เข้า/ออก ──

def test_เปิดปาร์ตี้ได้รหัสห้อง():
    ok, st = room.open_party(1, "เอ")
    assert ok
    assert len(st["room"]) == 5
    assert st["host"] == "1"


def test_เพื่อนเข้าด้วยรหัสได้():
    _, st = room.open_party(1, "เอ")
    ok, got = room.join_party(2, "บี", st["room"])
    assert ok
    assert [s["name"] for s in got["seats"]] == ["เอ", "บี"]


def test_ปาร์ตี้เต็มที่_5_คน():
    """lobby ยอม 6 แต่ปาร์ตี้ต้อง 5 — ชั้นนี้ต้องดักเอง"""
    st = _full_party()
    ok, got = room.join_party(99, "เกิน", st["room"])
    assert not ok, "คนที่ 6 ต้องเข้าไม่ได้"
    assert "เต็ม" in got["error"]


def test_คนเดิมกลับเข้ามาได้แม้ปาร์ตี้เต็ม():
    """สเปกข้อ 4: หลุดแล้วกลับเข้ามาได้ — ห้ามให้ 'เต็ม' บล็อกคนที่มีที่นั่งอยู่แล้ว"""
    st = _full_party()
    ok, _ = room.join_party(3, "P3", st["room"])
    assert ok, "คนที่มีที่นั่งอยู่แล้วต้องกลับเข้ามาได้เสมอ"


def test_รหัสผิดเข้าไม่ได้():
    ok, got = room.join_party(2, "บี", "ZZZZZ")
    assert not ok and "error" in got


def test_รหัสพิมพ์เล็กก็เข้าได้():
    """คนก๊อปรหัสไปแล้วพิมพ์เล็ก ไม่ควรเข้าไม่ได้"""
    _, st = room.open_party(1, "เอ")
    ok, _ = room.join_party(2, "บี", st["room"].lower())
    assert ok


def test_ออกแล้วที่นั่งหาย():
    _, st = room.open_party(1, "เอ")
    room.join_party(2, "บี", st["room"])
    room.leave_party(2)
    assert len(room.view(1)["seats"]) == 1


def test_ออกแล้วมีที่ว่างให้คนใหม่เข้า():
    st = _full_party()
    room.leave_party(3)
    ok, _ = room.join_party(99, "คนใหม่", st["room"])
    assert ok


# ── เริ่มเกม ──

def test_คนเดียวเริ่มไม่ได้():
    room.open_party(1, "เอ")
    ok, got = room.begin(1)
    assert not ok and "2 คน" in got["error"]


def test_เฉพาะหัวห้องเริ่มได้():
    _, st = room.open_party(1, "เอ")
    room.join_party(2, "บี", st["room"])
    ok, got = room.begin(2)
    assert not ok and "หัวห้อง" in got["error"]


def test_หัวห้องเริ่มได้เมื่อครบ_2_คน():
    _, st = room.open_party(1, "เอ")
    room.join_party(2, "บี", st["room"])
    ok, _ = room.begin(1)
    assert ok


def test_เริ่มแล้วคนใหม่เข้าไม่ได้():
    _, st = room.open_party(1, "เอ")
    room.join_party(2, "บี", st["room"])
    room.begin(1)
    ok, _ = room.join_party(3, "ซี", st["room"])
    assert not ok


def test_คนนอกห้องเริ่มไม่ได้():
    """กันคนยิง API ตรง ๆ"""
    room.open_party(1, "เอ")
    ok, got = room.begin(999)
    assert not ok


# ── ประตูเดียว view() ──

def test_view_ไม่อยู่ห้องไหน():
    assert room.view(1)["in_room"] is False


def test_view_บอกจำนวนสูงสุด_5_ไม่ใช่_6():
    """หน้าเว็บเอาเลขนี้ไปโชว์ — ถ้าโชว์ 6 ผู้เล่นจะเข้าใจผิด"""
    room.open_party(1, "เอ")
    assert room.view(1)["max"] == 5


def test_view_บอกว่าใครเป็นเราและใครเป็นหัวห้อง():
    _, st = room.open_party(1, "เอ")
    room.join_party(2, "บี", st["room"])
    got = room.view(2)
    assert got["host"] is False
    me = [s for s in got["seats"] if s["you"]]
    assert len(me) == 1 and me[0]["name"] == "บี"


def test_view_บอกสถานะห้อง():
    _, st = room.open_party(1, "เอ")
    assert room.view(1)["phase"] == "lobby"
    room.join_party(2, "บี", st["room"])
    room.begin(1)
    assert room.view(1)["phase"] == "battle"


# ── อยู่ร่วมกับเกมอื่นได้ ──

def test_เล่นปาร์ตี้อยู่แล้วเข้าเกมอื่นได้():
    """ล็อบบี้กลางผูกห้องกับ 'เกม' — ปาร์ตี้กับ UNO อยู่คนละห้องพร้อมกันได้"""
    from bot import lobby
    _, st = room.open_party(1, "เอ")
    u = lobby.create("uno", 1, {"uid": "1", "name": "เอ"})
    assert lobby.room_of("party", 1) == st["room"]
    assert lobby.room_of("uno", 1) == u["room"]
    assert st["room"] != u["room"]


def test_รหัสห้องเกมอื่นเอามาใช้กับปาร์ตี้ไม่ได้():
    from bot import lobby
    u = lobby.create("uno", 1, {"uid": "1", "name": "เอ"})
    ok, _ = room.join_party(2, "บี", u["room"])
    assert not ok
