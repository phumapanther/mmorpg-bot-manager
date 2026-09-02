"""เทสห้องทายเลขหลายคนบนล็อบบี้กลาง (bot/lobby.py)

🔒 เทสที่สำคัญที่สุดในไฟล์นี้: เลขลับต้องไม่รั่วออกจาก view() ก่อนเกมจบ
   (ชั้นที่ 2 ของเทสเดียวกันอยู่ที่ tests/test_template_minigame.py — เช็คคำตอบ
   ระดับ HTTP ผ่าน api/routes.py.snippet)
"""
import sqlite3

import pytest

from bot import lobby
from templates.minigame.core import room as G


@pytest.fixture(autouse=True)
def db(tmp_path, monkeypatch):
    """ฐานข้อมูลใหม่ทุกเทส — ไม่ให้ห้องจากเทสก่อนหน้าค้างมากวน (ลอกจาก tests/test_lobby.py)"""
    from license_server import web_db

    path = tmp_path / "web.db"

    def _connect():
        conn = sqlite3.connect(str(path), timeout=5)
        conn.row_factory = sqlite3.Row
        conn.executescript(web_db._SCHEMA)
        return conn

    monkeypatch.setattr(web_db, "connect", _connect)
    yield


def test_เปิดห้องแล้วชวนเพื่อนเข้าเล่นได้():
    st = G.open_room(1, "เอ")
    ok, st2 = G.sit(2, "บี", st["room"])
    assert ok and len(st2["seats"]) == 2


def test_เริ่มเกมได้ต่อเมื่อมีอย่างน้อย_2_คน():
    st = G.open_room(1, "เอ")
    ok, _r = G.begin(1)
    assert not ok, "มีคนเดียวห้ามเริ่ม"

    G.sit(2, "บี", st["room"])
    ok, st2 = G.begin(1)
    assert ok and st2["extra"]["game"] is not None


def test_view_ไม่ส่งเลขลับก่อนเกมจบ():
    st = G.open_room(1, "เอ")
    G.sit(2, "บี", st["room"])
    G.begin(1)

    v = G.view(1)
    assert "secret" not in v, "เกมยังไม่จบ ห้ามส่งเลขลับลงเบราว์เซอร์"


def test_ทายถูกจบเกมและเฉลยเลขลับ():
    st = G.open_room(1, "เอ")
    G.sit(2, "บี", st["room"])
    G.begin(1)

    room = lobby.load(st["room"])
    secret = room["extra"]["game"]["secret"]
    ok, r = G.guess(1, secret)
    assert ok and r["room"]["over"]
    assert r["room"]["secret"] == secret, "เกมจบแล้วต้องเฉลยเลขลับได้"


def test_ยังไม่ถึงตาทายไม่ได้():
    st = G.open_room(1, "เอ")
    G.sit(2, "บี", st["room"])
    G.begin(1)

    ok, r = G.guess(2, 5)     # ตาแรกเป็นของ uid 1 (หัวห้อง) เสมอ
    assert not ok and "error" in r


def test_คนนอกห้องทายไม่ได้():
    st = G.open_room(1, "เอ")
    G.sit(2, "บี", st["room"])
    G.begin(1)

    ok, r = G.guess(3, 5)
    assert not ok and "error" in r
