"""ทดสอบระบบสำรองฐานข้อมูล (ข้อ 1) — run_backup สำรองถูก + หมุนเวียนเก็บ 7 ชุด"""
import os
import sqlite3

import bot.models.player_model as player_model
from bot.cogs import db_backup as bk


def test_backup_creates_valid_copy(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(player_model, "DB_NAME", str(tmp_path / "game.db"))
    player_model.init_db()
    uid = 42
    player_model.get_player(uid)
    player_model.update_player_field(uid, "cash", 12345)

    dest = bk.run_backup()
    assert os.path.exists(dest)
    # ไฟล์สำรองเปิดอ่านได้จริงและข้อมูลครบ
    conn = sqlite3.connect(dest)
    cash = conn.execute("SELECT cash FROM players WHERE user_id = ?", (uid,)).fetchone()[0]
    conn.close()
    assert cash == 12345


def test_backup_rotation_keeps_last_seven(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(player_model, "DB_NAME", str(tmp_path / "game.db"))
    player_model.init_db()

    os.makedirs(bk.BACKUP_DIR, exist_ok=True)
    # จำลองไฟล์สำรองเก่า 10 ชุด (ชื่อเรียงเวลา)
    for i in range(10):
        with open(os.path.join(bk.BACKUP_DIR, f"game_data-2026010{i if i < 10 else 0}-00000{i}.db"), "wb") as f:
            f.write(b"old")

    bk.run_backup()
    remaining = sorted(f for f in os.listdir(bk.BACKUP_DIR) if f.endswith(".db"))
    assert len(remaining) == bk.KEEP_LAST
    # ชุดใหม่ล่าสุดต้องยังอยู่ (ชื่อขึ้นด้วยปีปัจจุบัน > 20260...)
    assert remaining[-1] > "game_data-20260109"
    # ไฟล์อื่นในโฟลเดอร์ที่ไม่ใช่ backup ต้องไม่ถูกลบ
    with open(os.path.join(bk.BACKUP_DIR, "note.txt"), "w") as f:
        f.write("x")
    bk.run_backup()
    assert os.path.exists(os.path.join(bk.BACKUP_DIR, "note.txt"))


def test_vine_cutter_price_adjusted():
    import json
    items = json.load(open(os.path.join(os.path.dirname(__file__), "..", "config.example.json"),
                           encoding="utf-8"))["item_catalog"]["items"]
    assert items["54"]["buy"] == 800 and items["54"]["sell"] == 160
