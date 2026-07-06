from fastapi.testclient import TestClient

from license_server import db
from license_server.api import create_app


def _fresh_db(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DB_PATH", str(tmp_path / "licenses.db"))
    db.init_db()


def test_generate_key_is_unused(tmp_path, monkeypatch):
    _fresh_db(tmp_path, monkeypatch)
    key = db.generate_key("test customer")
    row = db.get_key(key)
    assert row["used"] == 0
    assert row["note"] == "test customer"


def test_redeem_binds_key_to_machine(tmp_path, monkeypatch):
    _fresh_db(tmp_path, monkeypatch)
    key = db.generate_key()
    ok, reason = db.redeem_key(key, "machine-A", "tokenhash1")
    assert ok is True and reason == "ok"
    row = db.get_key(key)
    assert row["used"] == 1
    assert row["machine_id"] == "machine-A"


def test_redeem_same_machine_is_idempotent(tmp_path, monkeypatch):
    _fresh_db(tmp_path, monkeypatch)
    key = db.generate_key()
    db.redeem_key(key, "machine-A", "hash1")
    ok, reason = db.redeem_key(key, "machine-A", "hash1")
    assert ok is True and reason == "ok"


def test_redeem_different_machine_rejected(tmp_path, monkeypatch):
    _fresh_db(tmp_path, monkeypatch)
    key = db.generate_key()
    db.redeem_key(key, "machine-A", "hash1")
    ok, reason = db.redeem_key(key, "machine-B", "hash1")
    assert ok is False and reason == "already_used_elsewhere"
    row = db.get_key(key)
    assert row["machine_id"] == "machine-A"  # unchanged


def test_redeem_invalid_key_rejected(tmp_path, monkeypatch):
    _fresh_db(tmp_path, monkeypatch)
    ok, reason = db.redeem_key("NOT-A-REAL-KEY", "machine-A", "hash1")
    assert ok is False and reason == "invalid_key"


def test_api_redeem_end_to_end(tmp_path, monkeypatch):
    """สร้างคีย์จริง ยิงผ่าน HTTP /redeem จริง (ไม่ mock) เพื่อเช็คว่า api.py + db.py ต่อกันถูกต้อง"""
    _fresh_db(tmp_path, monkeypatch)
    key = db.generate_key()
    client = TestClient(create_app())

    r1 = client.post("/redeem", json={"key": key, "machine_id": "machine-A", "bot_token_hash": "h1"})
    assert r1.status_code == 200 and r1.json()["ok"] is True

    r2 = client.post("/redeem", json={"key": key, "machine_id": "machine-B", "bot_token_hash": "h1"})
    assert r2.status_code == 403

    r3 = client.post("/redeem", json={"key": "NOPE", "machine_id": "machine-A", "bot_token_hash": "h1"})
    assert r3.status_code == 404
