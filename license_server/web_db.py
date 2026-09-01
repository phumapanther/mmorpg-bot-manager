# license_server/web_db.py
"""ฐานข้อมูลเว็บไซต์เกม (web.db) — แยกจาก licenses.db เด็ดขาด

ตาราง: news (ข่าว) · login_codes (โค้ดล็อกอินผ่านบอท) · topups (รายการเติมเงิน = audit log ในตัว)
       role_grant_queue (สะพานให้บอทแจกยศแทนเว็บ — เว็บแจกยศ Discord เองไม่ได้)
"""
import sqlite3
import time
from pathlib import Path

# บนคลาวด์ชี้มาที่ /app/data (volume) ไม่งั้นข้อมูลหายทุกครั้งที่ deploy ใหม่
# ไม่ตั้ง env = ใช้ที่เดิม (รันในเครื่องตัวเองเหมือนเดิมเป๊ะ)
import os
DB_PATH = Path(os.environ.get("WEB_DB_PATH") or (Path(__file__).resolve().parent / "web.db"))

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
-- 🔑 ตั๋วล็อกอินคลิกเดียวจากปุ่มในดิสคอร์ด — ใช้ได้ครั้งเดียว อายุสั้น
-- ต่างจาก login_codes ตรงที่ตัวตนถูกผูกไว้ตั้งแต่ตอนสร้าง (บอทรู้อยู่แล้วว่าใครกด)
CREATE TABLE IF NOT EXISTS login_tickets (
    token TEXT PRIMARY KEY,
    discord_id TEXT NOT NULL,
    created_at TEXT DEFAULT (datetime('now', 'localtime')),
    expires_at REAL NOT NULL,
    used INTEGER DEFAULT 0
);
CREATE TABLE IF NOT EXISTS admin_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    discord_id TEXT NOT NULL,
    user_name TEXT DEFAULT '',
    command TEXT NOT NULL,
    full_text TEXT DEFAULT '',
    channel TEXT DEFAULT '',
    guild TEXT DEFAULT '',
    used_at TEXT DEFAULT (datetime('now', 'localtime'))
);
CREATE TABLE IF NOT EXISTS role_grant_queue (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    discord_id TEXT NOT NULL,
    role_id INTEGER NOT NULL,
    label TEXT DEFAULT '',
    price INTEGER DEFAULT 0,          -- ไว้คืนเงินถ้าแจกไม่สำเร็จ
    kind TEXT DEFAULT 'buy',          -- buy = ซื้อเจาะจง | gacha = หมุนได้มา
    status TEXT DEFAULT 'pending',    -- pending | done | duplicate | failed | refunded
    note TEXT DEFAULT '',
    created_at TEXT DEFAULT (datetime('now', 'localtime')),
    resolved_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_grant_pending ON role_grant_queue(status, id);
-- 💓 บอทยังออนไลน์อยู่ไหม — แถวเดียวจบ บอทประทับเวลาทุกรอบที่ไล่คิวแจกยศ
-- เว็บใช้ตัดสินว่า "ซื้อยศได้ไหม" เพราะยศต้องให้บอทเป็นคนแจก บอทดับ = ซื้อแล้วค้าง
CREATE TABLE IF NOT EXISTS bot_heartbeat (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    beat_at REAL NOT NULL
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
    note TEXT DEFAULT '',
    ip TEXT DEFAULT '',
    user_agent TEXT DEFAULT ''
);
"""


def connect():
    """เปิด connection พร้อมสร้างตารางที่ยังไม่มี — busy_timeout กันชนกับบอทที่เขียน login_codes"""
    conn = sqlite3.connect(str(DB_PATH), timeout=5)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA busy_timeout=5000")
    conn.executescript(_SCHEMA)
    # migration เบาๆ: web.db เก่าที่ไม่มีคอลัมน์ใหม่ → เติมให้ (มีแล้ว = ข้ามเงียบ)
    for col in ("ip TEXT DEFAULT ''", "user_agent TEXT DEFAULT ''"):
        try:
            conn.execute(f"ALTER TABLE topups ADD COLUMN {col}")
        except sqlite3.OperationalError:
            pass
    return conn


# 💓 บอทออนไลน์ไหม
# บอทเต้นทุก 15 วิ (POLL_SECONDS ของ role_grant_worker) ให้อภัย 3 จังหวะก่อนตัดสินว่าดับ
BEAT_TIMEOUT = 45


def bot_ping():
    """บอทบอกว่า 'ยังอยู่' — เรียกจากลูปที่ทำงานได้ก็ต่อเมื่อบอทต่อดิสคอร์ดติดแล้วเท่านั้น"""
    with connect() as conn:
        conn.execute("INSERT INTO bot_heartbeat(id, beat_at) VALUES (1, ?) "
                     "ON CONFLICT(id) DO UPDATE SET beat_at=excluded.beat_at", (time.time(),))


def bot_alive(timeout=BEAT_TIMEOUT):
    """บอทยังเต้นอยู่ไหม — อ่านไม่ได้ก็ถือว่าดับ (ปลอดภัยกว่าปล่อยให้ซื้อแล้วค้าง)"""
    try:
        with connect() as conn:
            row = conn.execute("SELECT beat_at FROM bot_heartbeat WHERE id=1").fetchone()
    except sqlite3.Error:
        return False
    return bool(row) and (time.time() - float(row["beat_at"])) < timeout
