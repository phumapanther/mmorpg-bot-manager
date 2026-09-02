# tests/test_topup_ingame.py
"""เติมเงินจากในเกม (ปุ่มเมนู + !slip) — เทสตรรกะตรงๆ ไม่ต้องรัน discord จริง"""
import io

import pytest
from PIL import Image

import license_server.web_db as web_db
# ⚠️ ต้อง import จากโมดูลจริง (bot.apps.bot_game.web_link) ไม่ใช่สะพาน bot.cogs.web_link
# เพราะ monkeypatch.setattr(web_link, "UPLOAD_DIR", ...) ด้านล่างต้อง patch ตัวแปร global
# ของไฟล์ที่ create_topup() นิยามจริง ไม่ใช่ของสะพาน (แพตช์ที่สะพานจะไม่มีผล)
from bot.apps.bot_game import web_link


@pytest.fixture
def env(tmp_path, monkeypatch):
    from bot import config_loader
    monkeypatch.setattr(web_db, "DB_PATH", tmp_path / "web.db")
    monkeypatch.setattr(web_link, "UPLOAD_DIR", tmp_path / "uploads")
    monkeypatch.setattr(config_loader, "get_config", lambda: {"payment": {
        "exchange_rate": 100, "min_amount": 20, "max_amount": 1000,
        "promptpay": {"enabled": True, "id": "0812345678", "name": "ร้านเกม"},
    }})
    return tmp_path


def _png(size=(900, 1600)):
    buf = io.BytesIO()
    Image.new("RGB", size, (30, 30, 200)).save(buf, "PNG")
    return buf.getvalue()


def test_create_topup_ingame(env):
    ok, msg, data = web_link.create_topup("111222333", 50)
    assert ok and data["gold"] == 5000 and data["id"] >= 1
    assert data["qr"].getvalue()[:4] == b"\x89PNG"              # ได้ QR จริง
    with web_db.connect() as conn:
        row = conn.execute("SELECT * FROM topups WHERE id=?", (data["id"],)).fetchone()
    assert row["discord_id"] == "111222333" and row["status"] == "pending"
    assert row["ip"] == "discord"                               # log บอกว่ามาจากในเกม


def test_create_topup_validates_amount(env):
    for bad in (-5, 0, 5, 5000, "abc"):
        ok, msg, _ = web_link.create_topup("111", bad)
        assert not ok


def test_create_topup_needs_promptpay(env, monkeypatch):
    from bot import config_loader
    monkeypatch.setattr(config_loader, "get_config", lambda: {"payment": {}})
    ok, msg, _ = web_link.create_topup("111", 50)
    assert not ok and "เติมเงิน" in msg


def test_save_slip_from_chat(env):
    _ok, _msg, data = web_link.create_topup("111222333", 50)
    ok, msg = web_link.save_slip("111222333", data["id"], _png())
    assert ok
    p = env / "uploads" / f"slip_{data['id']}.jpg"
    assert p.is_file()
    assert max(Image.open(p).size) <= 1280                      # ย่อรูปให้เล็ก


def test_admin_command_logging(env):
    """log คำสั่งแอดมิน: จดลง web.db + ตัวจับคำสั่งที่ล็อกสิทธิ์แอดมินทำงานถูก"""
    assert web_link.log_admin_command("99", "Watch#1", "spawn", "!spawn @cat 66 1", "แชทหลัก", "เซิร์ฟหลัก")
    with web_db.connect() as conn:
        row = conn.execute("SELECT * FROM admin_logs").fetchone()
    assert row["command"] == "spawn" and row["full_text"] == "!spawn @cat 66 1"
    assert row["used_at"] and row["guild"] == "เซิร์ฟหลัก"

    # ตัวจับ: check ที่มาจาก has_permission/has_permissions → ถือเป็นคำสั่งแอดมิน
    class FakeCmd:
        checks = []
    def predicate(ctx):
        pass
    predicate.__qualname__ = "has_permission.<locals>.predicate"
    FakeCmd.checks = [predicate]
    assert web_link.is_admin_gated(FakeCmd)
    predicate.__qualname__ = "has_permissions.<locals>.predicate"
    assert web_link.is_admin_gated(FakeCmd)
    def normal(ctx):
        pass
    FakeCmd.checks = [normal]
    assert not web_link.is_admin_gated(FakeCmd)
    FakeCmd.checks = []
    assert not web_link.is_admin_gated(FakeCmd)


def test_save_slip_guards(env):
    _ok, _msg, data = web_link.create_topup("111222333", 50)
    ok, msg = web_link.save_slip("999", data["id"], _png())     # คนอื่นแนบแทนไม่ได้
    assert not ok
    ok, msg = web_link.save_slip("111222333", 4444, _png())     # เลขรายการมั่ว
    assert not ok
    ok, msg = web_link.save_slip("111222333", data["id"], "ไม่ใช่รูป".encode())
    assert not ok and "รูป" in msg
