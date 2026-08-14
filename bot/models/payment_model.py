import sqlite3
import time

import os

from app_paths import get_app_root

# path เต็มเสมอ — โปรเซสที่ cwd ต่างกัน (เว็บ/พาแนล/บอท) ต้องเห็น game_data.db ไฟล์เดียวกัน
# ถ้าปล่อยเป็น path สัมพัทธ์ ฝั่งที่ cwd ไม่ตรงจะไปสร้างไฟล์เปล่าใหม่เงียบๆ เงินผู้เล่นหาย
DB_NAME = os.path.join(get_app_root(), "game_data.db")


def init_db():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS payment_orders (
            order_id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            amount REAL NOT NULL,
            currency TEXT NOT NULL,
            gold INTEGER NOT NULL,
            method TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'pending',
            created_at REAL NOT NULL,
            confirmed_at REAL,
            confirmed_by INTEGER
        )
    """)
    conn.commit()
    conn.close()


def create_order(user_id, amount, currency, gold, method):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO payment_orders (user_id, amount, currency, gold, method, status, created_at) "
        "VALUES (?, ?, ?, ?, ?, 'pending', ?)",
        (user_id, amount, currency, gold, method, time.time()),
    )
    conn.commit()
    order_id = cursor.lastrowid
    conn.close()
    return order_id


def get_order(order_id):
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM payment_orders WHERE order_id = ?", (order_id,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None


def set_order_status(order_id, status, confirmed_by=None):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE payment_orders SET status = ?, confirmed_at = ?, confirmed_by = ? WHERE order_id = ?",
        (status, time.time(), confirmed_by, order_id),
    )
    conn.commit()
    conn.close()


def get_pending_orders_for_user(user_id):
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute(
        "SELECT * FROM payment_orders WHERE user_id = ? AND status = 'pending' ORDER BY created_at DESC",
        (user_id,),
    )
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]
