# 💍 คู่หู/แต่งงาน (C7) — จับคู่กันแล้วได้โบนัสตอนล่ามอน
#
# หัวใจของฟีเจอร์: โบนัสเต็มจะได้ก็ต่อเมื่อ "คู่ของคุณเข้ามาเล่นวันนี้ด้วย"
# → รู้ว่าคู่เล่นวันนี้ไหมจากแถวเควสรายวัน (C1) ที่มีอยู่แล้ว ไม่ต้องเก็บเวลาล็อกอินเพิ่ม
# → เป็นเหตุผลให้คู่กันตามกันมาเล่น ซึ่งคือจุดประสงค์ของฟีเจอร์นี้
import json
import sqlite3
import time

import discord

import bot.models.player_model as player_model
from bot import config_loader


def _cfg(key, default=None):
    return config_loader.get_config().get("partner", {}).get(key, default)


def _connect():
    conn = sqlite3.connect(player_model.DB_NAME)
    conn.execute("""CREATE TABLE IF NOT EXISTS partners (
        user_id INTEGER PRIMARY KEY, partner_id INTEGER, since INTEGER)""")
    # 📜 ประวัติ: จดทุกครั้งที่แต่ง/หย่า — เก็บไว้เฉย ๆ ไม่มีคำสั่งไหนเอามาโชว์
    # (ไว้ให้เจ้าของเซิร์ฟย้อนดูเองใน DB เวลามีเรื่องต้องเคลียร์ เช่น "ใครแต่งกับใครมาก่อน")
    conn.execute("""CREATE TABLE IF NOT EXISTS partner_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER, partner_id INTEGER, action TEXT, at INTEGER)""")
    return conn


def _log(conn, a_id, b_id, action, when):
    """จดประวัติสองทาง (คนละแถวต่อฝ่าย) — ใช้ connection เดียวกับ transaction ที่กำลังทำอยู่"""
    conn.execute("INSERT INTO partner_history (user_id, partner_id, action, at) VALUES (?, ?, ?, ?)",
                 (a_id, b_id, action, when))
    conn.execute("INSERT INTO partner_history (user_id, partner_id, action, at) VALUES (?, ?, ?, ?)",
                 (b_id, a_id, action, when))


def history_of(user_id):
    """ประวัติแต่ง/หย่าทั้งหมดของคนนี้ — ไม่มีคำสั่งในเกมเรียกใช้ มีไว้ให้แอดมินเรียกดูเอง"""
    conn = _connect()
    rows = conn.execute("""SELECT partner_id, action, at FROM partner_history
                           WHERE user_id = ? ORDER BY id""", (user_id,)).fetchall()
    conn.close()
    return rows


def partner_of(user_id):
    conn = _connect()
    row = conn.execute("SELECT partner_id, since FROM partners WHERE user_id = ?", (user_id,)).fetchone()
    conn.close()
    return row          # (partner_id, since) หรือ None


def ring_id():
    """เลขไอเทมแหวนแต่งงาน — ตั้งเป็นค่าว่างใน Panel = ไม่ต้องใช้แหวน"""
    return str(_cfg("ring_item", "") or "")


def ring_name():
    return config_loader.get_item_config(ring_id()).get("name", "💍 แหวนแต่งงาน")


def ring_price():
    return int(config_loader.get_item_config(ring_id()).get("buy", 0) or 0)


def has_ring(user_id):
    """ต้องมีแหวนถึงจะขอแต่งได้ — ไม่ได้ตั้งแหวนไว้ = ผ่านตลอด"""
    if not ring_id():
        return True
    player = player_model.get_player(user_id)
    if not player:
        return False
    return ring_id() in player_model.load_inventory(player.get("inventory", ""))


def marry(a_id, b_id):
    """ผูกคู่สองทาง + หักค่าจัดงานจากทั้งคู่ + ใช้แหวนของคนที่ขอ

    ทุกอย่างอยู่ใน transaction เดียว — ล้มเหลวคือไม่เสียทั้งเงินและแหวน
    """
    if a_id == b_id:
        return False, "❌ แต่งกับตัวเองไม่ได้นะ..."
    if partner_of(a_id):
        return False, "❌ คุณมีคู่อยู่แล้ว! หย่าก่อนด้วย `!divorce`"
    if partner_of(b_id):
        return False, "❌ อีกฝ่ายมีคู่อยู่แล้ว!"

    cost = int(_cfg("wedding_cost", 0) or 0)
    for uid in (a_id, b_id):
        player = player_model.get_player(uid)
        if not player:
            return False, "❌ ไม่พบข้อมูลตัวละครของฝ่ายใดฝ่ายหนึ่ง!"
        if player.get("cash", 0) < cost:
            return False, f"❌ <@{uid}> มีเงินสดไม่พอค่าจัดงาน 🪙 `{cost:,}` ทอง (คนละเท่ากัน)"

    # 💍 แหวนอยู่กับคนที่เป็นฝ่ายขอ (a_id) — ต้องมีจริงตอนกดยืนยัน ไม่ใช่แค่ตอนพิมพ์คำสั่ง
    ring = ring_id()
    proposer_inv = None
    if ring:
        proposer = player_model.get_player(a_id)
        proposer_inv = player_model.load_inventory((proposer or {}).get("inventory", ""))
        if ring not in proposer_inv:
            return False, (f"❌ <@{a_id}> ไม่มี **{ring_name()}** ในกระเป๋าแล้ว!\n"
                           f"ซื้อได้ที่ `!shop` ราคา 🪙 `{ring_price():,}` ทอง")
        proposer_inv.remove(ring)

    now = int(time.time())
    conn = _connect()
    try:
        with conn:      # ผูกคู่ + หักเงินสองฝ่าย + ใช้แหวน พร้อมกันทั้งชุด
            conn.execute("INSERT OR REPLACE INTO partners VALUES (?, ?, ?)", (a_id, b_id, now))
            conn.execute("INSERT OR REPLACE INTO partners VALUES (?, ?, ?)", (b_id, a_id, now))
            if cost:
                conn.execute("UPDATE players SET cash = cash - ? WHERE user_id IN (?, ?)",
                             (cost, a_id, b_id))
            if ring:
                conn.execute("UPDATE players SET inventory = ? WHERE user_id = ?",
                             (json.dumps(proposer_inv), a_id))
            _log(conn, a_id, b_id, "marry", now)
    finally:
        conn.close()
    ring_line = f"\n**{ring_name()}** ถูกสวมให้ <@{b_id}> เรียบร้อย" if ring else ""   # ชื่อไอเทมมีอีโมจิอยู่แล้ว
    return True, (f"💍 **<@{a_id}> กับ <@{b_id}> เป็นคู่หูกันแล้ว!**{ring_line}\n"
                  f"ออกล่าในวันเดียวกันเพื่อรับโบนัสคู่เต็ม ๆ — ดูสถานะที่ `!partner`")


def divorce(user_id):
    row = partner_of(user_id)
    if not row:
        return False, "❌ คุณยังไม่มีคู่"
    partner_id = row[0]
    cost = int(_cfg("divorce_cost", 0) or 0)
    player = player_model.get_player(user_id)
    if cost and (player or {}).get("cash", 0) < cost:
        return False, f"❌ ค่าดำเนินการหย่า 🪙 `{cost:,}` ทอง — เงินสดไม่พอ"
    conn = _connect()
    try:
        with conn:
            conn.execute("DELETE FROM partners WHERE user_id IN (?, ?)", (user_id, partner_id))
            if cost:
                conn.execute("UPDATE players SET cash = cash - ? WHERE user_id = ?", (cost, user_id))
            _log(conn, user_id, partner_id, "divorce", int(time.time()))
    finally:
        conn.close()
    return True, f"💔 หย่ากับ <@{partner_id}> เรียบร้อยแล้ว"


def played_today(user_id):
    """คู่เข้ามาเล่นวันนี้ไหม — อ่านจากความคืบหน้าเควสรายวัน (C1) ไม่ต้องเก็บอะไรเพิ่ม"""
    try:
        return bool(player_model.get_daily_progress(user_id))
    except Exception:
        return False


def bonus_for(user_id):
    """คืน (ตัวคูณรางวัล, ข้อความอธิบาย) — ไม่มีคู่ = (1.0, "")"""
    row = partner_of(user_id)
    if not row:
        return 1.0, ""
    partner_id = row[0]
    together = played_today(partner_id)
    pct = int((_cfg("together_bonus_percent", 0) if together else _cfg("solo_bonus_percent", 0)) or 0)
    if not pct:
        return 1.0, ""
    note = (f"💞 **คู่หูออกล่าวันเดียวกัน!** รางวัล +{pct}%\n" if together
            else f"💍 **พรจากคู่หู** รางวัล +{pct}% *(ชวนคู่มาเล่นวันนี้ รับ "
                 f"+{int(_cfg('together_bonus_percent', 0) or 0)}%)*\n")
    return 1 + pct / 100, note


def build_partner_embed(user_id, display_name):
    row = partner_of(user_id)
    solo = int(_cfg("solo_bonus_percent", 0) or 0)
    duo = int(_cfg("together_bonus_percent", 0) or 0)
    if not row:
        ring_line = ""
        if ring_id():
            ring_line = (f"\nต้องมี **{ring_name()}** ก่อน — ซื้อที่ `!shop` "
                         f"ราคา 🪙 `{ring_price():,}` ทอง"
                         + ("\n✅ คุณมีแหวนแล้ว พร้อมขอได้เลย!" if has_ring(user_id)
                            else "\n❌ ตอนนี้คุณยังไม่มีแหวน"))
        embed = discord.Embed(
            title=f"💍 คู่หูของ {display_name}",
            color=0x95a5a6,
            description=("ยังไม่มีคู่หู\n\nชวนใครสักคนด้วย `!marry @ชื่อ`\n"
                         f"ค่าจัดงานคนละ 🪙 `{int(_cfg('wedding_cost', 0) or 0):,}` ทอง"
                         + ring_line))
        embed.add_field(name="ได้อะไรบ้าง",
                        value=f"💍 มีคู่: รางวัลจากการล่า **+{solo}%**\n"
                              f"💞 คู่เล่นวันเดียวกัน: **+{duo}%**", inline=False)
        return embed

    partner_id, since = row
    days = max(0, (int(time.time()) - int(since or 0)) // 86400)
    together = played_today(partner_id)
    embed = discord.Embed(
        title=f"💞 คู่หูของ {display_name}",
        color=0xe91e63,
        description=f"คู่ของคุณ: <@{partner_id}>\nอยู่ด้วยกันมาแล้ว **{days:,} วัน**")
    embed.add_field(
        name="สถานะวันนี้",
        value=(f"✅ คู่ของคุณออกล่าวันนี้แล้ว — รับโบนัสเต็ม **+{duo}%**" if together
               else f"💤 คู่ยังไม่ได้เข้ามาเล่นวันนี้ — ตอนนี้ได้ **+{solo}%**\n"
                    f"ชวนมาเล่นแล้วขึ้นเป็น **+{duo}%** ทั้งคู่!"),
        inline=False)
    embed.set_footer(text="โบนัสมีผลกับทองและ EXP ที่ได้จากการล่ามอน · เลิกได้ด้วย !divorce")
    return embed
