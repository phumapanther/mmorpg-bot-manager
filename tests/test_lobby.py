"""🎪 ล็อบบี้กลาง — ห้องที่ทุกเกมใช้ร่วมกันได้

เจ้าของเกมเคาะ (09-02): ทำระบบกลางก่อน แล้วย้ายทั้งสนามรบและ UNO มาใช้
"""
import pytest

from bot import lobby


@pytest.fixture(autouse=True)
def db(tmp_path, monkeypatch):
    """ฐานข้อมูลใหม่ทุกเทส — ไม่ให้ห้องจากเทสก่อนหน้าค้างมากวน"""
    import sqlite3

    from license_server import web_db

    path = tmp_path / "web.db"

    def _connect():
        conn = sqlite3.connect(str(path), timeout=5)
        conn.row_factory = sqlite3.Row
        conn.executescript(web_db._SCHEMA)
        return conn

    monkeypatch.setattr(web_db, "connect", _connect)
    yield


def _seat(uid, name="ผู้เล่น"):
    return {"uid": str(uid), "name": name}


def test_สร้างห้องแล้วได้รหัสกับที่นั่งแรก():
    st = lobby.create("worms", 1, _seat(1, "เอ"))
    assert len(st["room"]) == 5
    assert st["host"] == "1"
    assert st["game"] == "worms"
    assert [s["name"] for s in st["seats"]] == ["เอ"]
    assert st["started"] is False


def test_รหัสห้องไม่มีตัวที่อ่านสับสน():
    # 0/O และ 1/I พิมพ์ตามกันแล้วผิด — ตัดออกตั้งแต่ต้น
    for _ in range(200):
        assert not (set(lobby.new_code()) & set("O0I1"))


def test_เข้าห้องด้วยรหัสแล้วนั่งเพิ่ม():
    st = lobby.create("worms", 1, _seat(1, "เอ"))
    ok, got = lobby.join("worms", 2, st["room"], _seat(2, "บี"))
    assert ok
    assert [s["name"] for s in got["seats"]] == ["เอ", "บี"]


def test_รหัสผิดเข้าไม่ได้():
    ok, got = lobby.join("worms", 2, "ZZZZZ", _seat(2))
    assert not ok and "error" in got


def test_ห้องเต็มเข้าไม่ได้():
    st = lobby.create("worms", 1, _seat(1))
    for uid in range(2, lobby.MAX_SEATS + 1):
        assert lobby.join("worms", uid, st["room"], _seat(uid))[0]
    ok, got = lobby.join("worms", 99, st["room"], _seat(99))
    assert not ok and "เต็ม" in got["error"]


def test_เริ่มเล่นแล้วเข้าไม่ได้():
    st = lobby.create("worms", 1, _seat(1))
    st["started"] = True
    lobby.save(st["room"], st)
    ok, got = lobby.join("worms", 2, st["room"], _seat(2))
    assert not ok


def test_คนเดิมเข้าซ้ำไม่เพิ่มที่นั่ง():
    # เน็ตหลุดแล้วกดเข้าใหม่ ต้องกลับเข้าที่เดิม ไม่ใช่นั่งซ้ำสองที่
    st = lobby.create("worms", 1, _seat(1))
    lobby.join("worms", 2, st["room"], _seat(2))
    ok, got = lobby.join("worms", 2, st["room"], _seat(2))
    assert ok and len(got["seats"]) == 2


def test_ออกห้องแล้วที่นั่งหาย():
    st = lobby.create("worms", 1, _seat(1))
    lobby.join("worms", 2, st["room"], _seat(2))
    lobby.leave("worms", 2)
    assert len(lobby.load(st["room"])["seats"]) == 1
    assert lobby.room_of("worms", 2) is None


def test_หัวห้องออกยกให้คนถัดไป():
    st = lobby.create("worms", 1, _seat(1))
    lobby.join("worms", 2, st["room"], _seat(2))
    lobby.leave("worms", 1)
    assert lobby.load(st["room"])["host"] == "2"


def test_คนสุดท้ายออกห้องหายไปเลย():
    st = lobby.create("worms", 1, _seat(1))
    lobby.leave("worms", 1)
    assert lobby.load(st["room"]) is None


def test_คนเดียวอยู่ได้เกมละห้อง():
    """เล่น UNO อยู่แล้วเข้าห้องสนามรบพร้อมกันได้ — ของเดิมทำไม่ได้"""
    a = lobby.create("worms", 1, _seat(1))
    b = lobby.create("uno", 1, _seat(1))
    assert lobby.room_of("worms", 1) == a["room"]
    assert lobby.room_of("uno", 1) == b["room"]
    assert a["room"] != b["room"]


def test_ออกเกมหนึ่งไม่กระทบอีกเกม():
    lobby.create("worms", 1, _seat(1))
    b = lobby.create("uno", 1, _seat(1))
    lobby.leave("worms", 1)
    assert lobby.room_of("worms", 1) is None
    assert lobby.room_of("uno", 1) == b["room"]


def test_เข้าห้องเกมอื่นด้วยรหัสข้ามเกมไม่ได้():
    """รหัสห้อง UNO เอาไปกรอกในสนามรบไม่ได้ — กันเข้าผิดห้อง"""
    st = lobby.create("uno", 1, _seat(1))
    ok, got = lobby.join("worms", 2, st["room"], _seat(2))
    assert not ok


def test_สร้างห้องใหม่ทิ้งห้องเก่าของเกมเดียวกัน():
    a = lobby.create("worms", 1, _seat(1))
    b = lobby.create("worms", 1, _seat(1))
    assert a["room"] != b["room"]
    assert lobby.load(a["room"]) is None       # ห้องเก่าไม่มีคนแล้ว = หายไป
    assert lobby.room_of("worms", 1) == b["room"]


def test_extra_เก็บของเฉพาะเกมได้():
    st = lobby.create("uno", 1, _seat(1), {"bet": 1000})
    assert lobby.load(st["room"])["extra"]["bet"] == 1000


def test_ห้องร้างโดนกวาดทิ้ง(monkeypatch):
    import time as _t
    st = lobby.create("worms", 1, _seat(1))
    # แกล้งทำเป็นว่าเวลาผ่านไปเกินอายุห้อง (snapshot เวลาจริงไว้ก่อน ไม่งั้น lambda เรียกตัวเองซ้ำ)
    future = _t.time() + lobby.ROOM_TTL + 10
    monkeypatch.setattr(lobby.time, "time", lambda: future)
    assert lobby.room_of("worms", 1) is None


def test_view_ไม่อยู่ห้องไหน():
    got = lobby.view("worms", 1)
    assert got["in_room"] is False


def test_view_บอกว่าใครเป็นเราและใครเป็นหัวห้อง():
    st = lobby.create("worms", 1, _seat(1, "เอ"))
    lobby.join("worms", 2, st["room"], _seat(2, "บี"))
    got = lobby.view("worms", 2)
    assert got["in_room"] is True
    assert got["code"] == st["room"]
    assert got["host"] is False               # คนที่ 2 ไม่ใช่หัวห้อง
    me = [s for s in got["seats"] if s["you"]]
    assert len(me) == 1 and me[0]["name"] == "บี"


# ── ย้าย rooms.py มาใช้ชั้นกลางแล้วต้องไม่มีอะไรพัง ──

def test_rooms_ยังมีชื่อเดิมครบ():
    """match.py กับ web_api.py เรียกชื่อพวกนี้อยู่ — เปลี่ยนชื่อ = พังทันที"""
    from bot.pvp import rooms
    for name in ("new_code", "room_of", "load", "save", "create", "join",
                 "leave", "set_plan", "set_team", "plan_ready", "view"):
        assert callable(getattr(rooms, name, None)), f"หายไป: {name}"
    for name in ("MAX_SEATS", "ROOM_TTL", "TEAM_NAME", "TEAM_PLANS"):
        assert getattr(rooms, name, None) is not None, f"หายไป: {name}"


def test_rooms_ลายเซ็นเดิมไม่มี_game():
    """ของเดิมเรียก rooms.create(uid, name, look) — เปลือกต้องเติม worms ให้เอง"""
    import inspect
    from bot.pvp import rooms
    assert list(inspect.signature(rooms.create).parameters) == ["uid", "name", "look"]
    assert list(inspect.signature(rooms.leave).parameters) == ["uid"]
    assert list(inspect.signature(rooms.room_of).parameters) == ["uid"]


def test_rooms_ใช้ชั้นกลางจริง():
    from bot.pvp import rooms
    st = rooms.create(1, "เอ", {})
    assert lobby.load(st["room"])["game"] == "worms"


def test_rooms_ห้องสนามรบไม่ชนกับ_uno():
    from bot.pvp import rooms
    w = rooms.create(1, "เอ", {})
    u = lobby.create("uno", 1, {"uid": "1", "name": "เอ"})
    assert rooms.room_of(1) == w["room"]
    assert lobby.room_of("uno", 1) == u["room"]
