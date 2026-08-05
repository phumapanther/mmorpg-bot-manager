# license_server/web_db.py
"""ฐานข้อมูลเว็บไซต์เกม (web.db) — แยกจาก licenses.db เด็ดขาด

ตาราง: news (ข่าว) · login_codes (โค้ดล็อกอินผ่านบอท) · topups (รายการเติมเงิน = audit log ในตัว)
"""
import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent / "web.db"

_SCHEMA = """
CREATE TABLE IF NOT EXISTS news (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    category TEXT DEFAULT 'news',
    body TEXT DEFAULT '',
    created_at TEXT DEFAULT (datetime('now', 'localtime')),
    updated_at TEXT DEFAULT (datetime('now', 'localtime')),
    published INTEGER DEFAULT 1
);
CREATE TABLE IF NOT EXISTS login_codes (
    code TEXT PRIMARY KEY,
    discord_id TEXT,
    created_at TEXT DEFAULT (datetime('now', 'localtime')),
    expires_at REAL NOT NULL,
    used INTEGER DEFAULT 0
);
CREATE TABLE IF NOT EXISTS topups (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    discord_id TEXT NOT NULL,
    amount_thb REAL NOT NULL,
    gold INTEGER NOT NULL,
    status TEXT DEFAULT 'pending',
    created_at TEXT DEFAULT (datetime('now', 'localtime')),
    decided_at TEXT,
    decided_by TEXT,
    note TEXT DEFAULT ''
);
"""


def connect():
    """เปิด connection พร้อมสร้างตารางที่ยังไม่มี — busy_timeout กันชนกับบอทที่เขียน login_codes"""
    conn = sqlite3.connect(str(DB_PATH), timeout=5)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA busy_timeout=5000")
    conn.executescript(_SCHEMA)
    return conn
