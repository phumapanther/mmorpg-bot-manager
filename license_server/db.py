"""ฐานข้อมูลคีย์ไลเซนส์ — รันบนเครื่องผู้พัฒนา/แอดมินเท่านั้น ไม่แจกจ่ายไปกับตัวบอท"""
import os
import secrets
import sqlite3
import time

_HERE = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(_HERE, "licenses.db")


def init_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS license_keys (
            key TEXT PRIMARY KEY,
            created_at REAL NOT NULL,
            used INTEGER NOT NULL DEFAULT 0,
            used_at REAL,
            machine_id TEXT,
            bot_token_hash TEXT,
            last_seen_at REAL,
            note TEXT
        )
    """)
    conn.commit()
    conn.close()


def generate_key(note=""):
    """สร้างคีย์ใหม่แบบสุ่ม รูปแบบ XXXX-XXXX-XXXX-XXXX ยังไม่ถูกใช้งาน"""
    raw = secrets.token_hex(8).upper()  # 16 hex chars
    key = "-".join(raw[i:i + 4] for i in range(0, 16, 4))
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO license_keys (key, created_at, used, note) VALUES (?, ?, 0, ?)",
        (key, time.time(), note),
    )
    conn.commit()
    conn.close()
    return key


def get_key(key):
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM license_keys WHERE key = ?", (key,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None


def redeem_key(key, machine_id, bot_token_hash):
    """ผูกคีย์กับเครื่อง — คืน (ok: bool, reason: str)
    เรียกซ้ำได้จากเครื่องเดิม (idempotent) เพราะบอทต้องเช็คซ้ำทุกครั้งที่สตาร์ท
    """
    row = get_key(key)
    if row is None:
        return False, "invalid_key"

    now = time.time()
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    if row["used"]:
        if row["machine_id"] != machine_id:
            conn.close()
            return False, "already_used_elsewhere"
        cursor.execute("UPDATE license_keys SET last_seen_at = ? WHERE key = ?", (now, key))
        conn.commit()
        conn.close()
        return True, "ok"

    cursor.execute(
        "UPDATE license_keys SET used = 1, used_at = ?, machine_id = ?, bot_token_hash = ?, last_seen_at = ? WHERE key = ?",
        (now, machine_id, bot_token_hash, now, key),
    )
    conn.commit()
    conn.close()
    return True, "ok"


def list_keys():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM license_keys ORDER BY created_at DESC")
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]
