"""เฟส 0 ของเว็บเกม: บอทกับเว็บต้องเขียน/อ่าน game_data.db พร้อมกันได้

โหมด delete เดิม = ใครเปิด transaction เขียนอยู่ คนอื่นอ่านไม่ได้เลย (database is locked)
WAL = อ่านได้ตลอดแม้มีคนกำลังเขียน — จำเป็นก่อนให้เว็บแตะ DB เดียวกับบอท
"""
import sqlite3

import pytest

import bot.models.player_model as pm


@pytest.fixture
def db(tmp_path, monkeypatch):
    monkeypatch.setattr(pm, "DB_NAME", str(tmp_path / "g.db"))
    pm.init_db()
    return pm.DB_NAME


def test_init_db_turns_on_wal(db):
    conn = sqlite3.connect(db)
    try:
        assert conn.execute("PRAGMA journal_mode").fetchone()[0].lower() == "wal"
    finally:
        conn.close()


def test_busy_timeout_is_not_zero(db):
    """ค่าเริ่มต้นของ sqlite3 ใน Python = 5 วินาที — ถ้าเป็น 0 คนที่สองจะเด้ง error ทันที"""
    conn = sqlite3.connect(db)
    try:
        assert conn.execute("PRAGMA busy_timeout").fetchone()[0] >= 1000
    finally:
        conn.close()


def test_write_while_another_connection_holds_a_read(db):
    """หัวใจของเฟส 0 — เคสที่จะเกิดจริงทุกวันเมื่อเว็บขึ้น:

    เว็บเปิด transaction อ่านค้างไว้ (กำลังเรนเดอร์หน้าโปรไฟล์) แล้วบอทต้องเขียน (ผู้เล่นได้ทอง)
    โหมด delete: บอทเขียนไม่ได้ → "database is locked" (ยืนยันแล้วว่าพังจริง)
    WAL: เขียนได้ทันที ไม่ต้องรอ
    """
    pm.get_player(111)

    reader = sqlite3.connect(db)
    writer = sqlite3.connect(db, timeout=1)
    try:
        reader.execute("BEGIN")
        reader.execute("SELECT cash FROM players WHERE user_id = ?", (111,)).fetchone()
        writer.execute("UPDATE players SET cash = 999 WHERE user_id = ?", (111,))
        writer.commit()                     # โหมด delete จะโยน OperationalError ตรงนี้
        assert pm.get_player(111)["cash"] == 999
    finally:
        reader.close()
        writer.close()
