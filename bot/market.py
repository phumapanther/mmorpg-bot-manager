# 🏪 ตลาดผู้เล่น (C5) — ฝากขายไอเทมให้ผู้เล่นคนอื่นซื้อด้วยทองในเกม
#
# กติกาความปลอดภัย (แตะเงินกับของจริง ห้ามพลาด):
#  1. ฝากของจริง — ลงขาย = ของออกจากกระเป๋าทันที มาอยู่ในแถวประกาศขาย ไม่มีทางมีสองที่พร้อมกัน
#  2. ซื้อทั้งหมดอยู่ใน transaction เดียว (ตารางเดียวกับ players) — ตัดเงิน จ่ายคนขาย ส่งของ
#     สำเร็จหรือไม่เกิดอะไรเลยเท่านั้น ไม่มีสภาพครึ่ง ๆ
#  3. ปิดการขายด้วย compare-and-swap (UPDATE ... WHERE status='open') — สองคนกดซื้อพร้อมกัน
#     คนที่สองจะได้ rowcount 0 แล้วยกเลิกทั้งชุด เงินไม่ถูกตัด
#  4. ยกเลิกได้เฉพาะเจ้าของ และคืนของกลับกระเป๋าเสมอ
import json
import sqlite3
import time

import discord

import bot.models.player_model as player_model
from bot import config_loader


def _cfg(key, default=None):
    return config_loader.get_config().get("market", {}).get(key, default)


def _connect():
    conn = sqlite3.connect(player_model.DB_NAME)
    conn.execute("""CREATE TABLE IF NOT EXISTS market (
        listing_id INTEGER PRIMARY KEY AUTOINCREMENT,
        seller_id INTEGER, item_id TEXT, price INTEGER,
        status TEXT DEFAULT 'open',
        created_at INTEGER, buyer_id INTEGER, sold_at INTEGER)""")
    return conn


def _item_name(item_id):
    return config_loader.get_item_config(str(item_id)).get("name", f"ไอเทม {item_id}")


def open_listings(limit=25):
    conn = _connect()
    rows = conn.execute("""SELECT listing_id, seller_id, item_id, price FROM market
                           WHERE status = 'open' ORDER BY listing_id DESC LIMIT ?""",
                        (limit,)).fetchall()
    conn.close()
    return rows


def my_listings(user_id):
    conn = _connect()
    rows = conn.execute("""SELECT listing_id, item_id, price FROM market
                           WHERE seller_id = ? AND status = 'open' ORDER BY listing_id""",
                        (user_id,)).fetchall()
    conn.close()
    return rows


def list_item(user_id, item_id, price):
    """ลงขาย — ของออกจากกระเป๋าทันที (ฝากไว้กับระบบ) กันขายซ้ำ/ขายแล้วยังใช้ได้"""
    if not _cfg("enabled", True):
        return False, "❌ ตอนนี้ปิดตลาดผู้เล่นอยู่"
    item_id = str(item_id)
    try:
        price = int(price)
    except (TypeError, ValueError):
        return False, "❌ ราคาต้องเป็นตัวเลข!"

    lo, hi = int(_cfg("min_price", 1) or 1), int(_cfg("max_price", 10**12) or 10**12)
    if not (lo <= price <= hi):
        return False, f"❌ ราคาต้องอยู่ระหว่าง `{lo:,}` ถึง `{hi:,}` ทอง"

    player = player_model.get_player(user_id)
    if not player:
        return False, "❌ ไม่พบข้อมูลตัวละครของคุณ!"
    inv = player_model.load_inventory(player.get("inventory", ""))
    if item_id not in inv:
        return False, "❌ คุณไม่มีไอเทมชิ้นนี้ในกระเป๋า!"

    max_slots = int(_cfg("max_listings_per_player", 5) or 5)
    if len(my_listings(user_id)) >= max_slots:
        return False, f"❌ ลงขายได้สูงสุด {max_slots} รายการพร้อมกัน — ปิดของเก่าก่อน (`!market mine`)"

    inv.remove(item_id)
    conn = _connect()
    try:
        with conn:                       # ถอดของกับสร้างประกาศต้องเกิดพร้อมกัน
            conn.execute("UPDATE players SET inventory = ? WHERE user_id = ?",
                         (json.dumps(inv), user_id))
            cur = conn.execute("""INSERT INTO market (seller_id, item_id, price, status, created_at)
                                  VALUES (?, ?, ?, 'open', ?)""",
                               (user_id, item_id, price, int(time.time())))
            listing_id = cur.lastrowid
    finally:
        conn.close()
    return True, (f"🏪 ลงขาย **{_item_name(item_id)}** ราคา 🪙 `{price:,}` ทอง แล้ว!\n"
                  f"เลขรายการ `#{listing_id}` — ยกเลิกได้ด้วย `!market cancel {listing_id}`")


def cancel_listing(user_id, listing_id):
    """ยกเลิกประกาศของตัวเอง — ของกลับเข้ากระเป๋าเสมอ"""
    conn = _connect()
    try:
        with conn:
            row = conn.execute("SELECT seller_id, item_id, status FROM market WHERE listing_id = ?",
                               (listing_id,)).fetchone()
            if not row:
                return False, f"❌ ไม่พบรายการ #{listing_id}"
            seller_id, item_id, status = row
            if seller_id != user_id:
                return False, "❌ ยกเลิกได้เฉพาะรายการของตัวเองเท่านั้น"
            if status != "open":
                return False, f"❌ รายการ #{listing_id} ปิดไปแล้ว (สถานะ: {status})"

            changed = conn.execute(
                "UPDATE market SET status = 'cancelled' WHERE listing_id = ? AND status = 'open'",
                (listing_id,)).rowcount
            if not changed:
                return False, "❌ รายการนี้เพิ่งถูกซื้อไปพอดี"

            inv_raw = conn.execute("SELECT inventory FROM players WHERE user_id = ?",
                                   (user_id,)).fetchone()
            inv = player_model.load_inventory(inv_raw[0] if inv_raw else "")
            inv.append(str(item_id))
            conn.execute("UPDATE players SET inventory = ? WHERE user_id = ?",
                         (json.dumps(inv), user_id))
    finally:
        conn.close()
    return True, f"↩️ ยกเลิกรายการ #{listing_id} แล้ว — **{_item_name(item_id)}** กลับเข้ากระเป๋าเรียบร้อย"


def buy_listing(buyer_id, listing_id):
    """ซื้อของ — ตัดเงิน จ่ายคนขาย ส่งของ ทั้งหมดใน transaction เดียว"""
    conn = _connect()
    try:
        with conn:
            row = conn.execute("""SELECT seller_id, item_id, price, status FROM market
                                  WHERE listing_id = ?""", (listing_id,)).fetchone()
            if not row:
                return False, f"❌ ไม่พบรายการ #{listing_id}"
            seller_id, item_id, price, status = row
            if status != "open":
                return False, f"❌ รายการ #{listing_id} ถูกซื้อหรือยกเลิกไปแล้ว"
            if seller_id == buyer_id:
                return False, "❌ ซื้อของตัวเองไม่ได้! ถ้าจะเอาคืนใช้ `!market cancel`"

            buyer = conn.execute("SELECT cash, inventory, capacity FROM players WHERE user_id = ?",
                                 (buyer_id,)).fetchone()
            if not buyer:
                return False, "❌ ไม่พบข้อมูลตัวละครของคุณ!"
            cash, inv_raw, capacity = buyer[0] or 0, buyer[1], buyer[2] or 0
            if cash < price:
                return False, f"❌ เงินสดไม่พอ! ต้องใช้ 🪙 `{price:,}` (มี `{cash:,}`)"

            inv = player_model.load_inventory(inv_raw)
            if capacity and len(inv) >= capacity:
                return False, f"❌ กระเป๋าเต็ม ({len(inv)}/{capacity}) — ทิ้งของก่อนค่อยซื้อ"

            # ปิดการขายก่อนแตะเงิน: สองคนกดพร้อมกัน คนที่สองได้ 0 แถว = ถอยทั้งชุด
            if not conn.execute(
                    "UPDATE market SET status='sold', buyer_id=?, sold_at=? "
                    "WHERE listing_id=? AND status='open'",
                    (buyer_id, int(time.time()), listing_id)).rowcount:
                return False, "❌ มีคนซื้อตัดหน้าไปพอดี!"

            tax = price * int(_cfg("tax_percent", 0) or 0) // 100
            inv.append(str(item_id))
            conn.execute("UPDATE players SET cash = cash - ?, inventory = ? WHERE user_id = ?",
                         (price, json.dumps(inv), buyer_id))
            conn.execute("UPDATE players SET bank = bank + ? WHERE user_id = ?",
                         (price - tax, seller_id))   # เข้าธนาคารคนขาย ตายแล้วไม่หาย
    finally:
        conn.close()

    note = f"\n💸 หักค่าธรรมเนียมตลาด {int(_cfg('tax_percent', 0) or 0)}% — คนขายได้ `{price - tax:,}`" if tax else ""
    return True, (f"✅ ซื้อ **{_item_name(item_id)}** สำเร็จ! จ่าย 🪙 `{price:,}` ทอง{note}\n"
                  f"ของเข้ากระเป๋าแล้ว — เงินโอนเข้าธนาคาร <@{seller_id}> เรียบร้อย")


def build_market_embed(viewer_id):
    rows = open_listings()
    embed = discord.Embed(
        title="🏪 ตลาดผู้เล่น",
        color=0x16a085,
        description=("*ยังไม่มีใครลงขายอะไรเลย — ลงขายได้ด้วย `!market sell [เลขไอเทม] [ราคา]`*"
                     if not rows else "เลือกจากเมนูด้านล่างเพื่อซื้อ"))
    for listing_id, seller_id, item_id, price in rows:
        mine = " ⬅️ **ของคุณ**" if seller_id == viewer_id else ""
        embed.add_field(name=f"#{listing_id} · {_item_name(item_id)}",
                        value=f"🪙 `{price:,}` ทอง — ผู้ขาย <@{seller_id}>{mine}", inline=False)
    tax = int(_cfg("tax_percent", 0) or 0)
    embed.set_footer(text=(f"ค่าธรรมเนียม {tax}% หักจากคนขาย · " if tax else "")
                     + "ลงขาย: !market sell [เลขไอเทม] [ราคา] · ของคุณ: !market mine")
    return embed
