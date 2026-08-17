# 👥 ระบบเพื่อน — ฐานของหมวด PVP (ชวนกันเข้าล็อบบี้)
#
# เพิ่มเพื่อนด้วยการ "คัดลอกไอดี Discord มาวาง" เท่านั้น ไม่มีระบบค้นหาชื่อ
# ทำได้เพราะไอดี Discord **คือ** user_id ในตาราง players อยู่แล้ว — วางแล้วเช็คว่ามีไหม จบ
#
# ตัดสินใจ: เพิ่มแล้วเป็นเพื่อนกันทันทีทั้งสองฝั่ง ไม่มีระบบขอ-อนุมัติ
#   เป็นเพื่อนแล้วทำได้แค่ "ชวนเข้าล็อบบี้" กับ "ดูโปรไฟล์" ซึ่งไม่มีอันตราย
#   ระบบอนุมัติทำให้โค้ดเพิ่มเท่าตัวและต้องมีหน้าแจ้งเตือนอีกชุด
#   ponytail: มีคนกวนเมื่อไหร่ค่อยเพิ่มปุ่มบล็อก ถูกกว่าทำระบบอนุมัติมาก
#
# ⚠️ โปรไฟล์เพื่อนโชว์ได้เฉพาะของสาธารณะ — ทอง/ธนาคาร/กระเป๋า ไม่ใช่เรื่องของคนอื่น
#    (มีเทสบังคับใน tests/test_friends.py)
import sqlite3
import time

import bot.models.player_model as player_model

MAX_FRIENDS = 200          # กันคนกดเพิ่มรัวจนตารางบวม (ปรับได้ที่ balance friends.max)


def _connect():
    conn = sqlite3.connect(player_model.DB_NAME, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("""CREATE TABLE IF NOT EXISTS friends (
        user_id INTEGER NOT NULL,
        friend_id INTEGER NOT NULL,
        since INTEGER NOT NULL,
        PRIMARY KEY (user_id, friend_id))""")
    return conn


def _max_friends():
    from bot import config_loader
    return int(config_loader.get_balance("friends.max", MAX_FRIENDS))


def parse_id(raw):
    """แปลงสิ่งที่ผู้เล่นวางมาเป็นไอดี — คืน 0 ถ้าไม่ใช่ไอดี

    รับทั้งไอดีเปล่า ๆ และรูปแบบที่ Discord คัดลอกมาให้ เช่น `<@123>` หรือมีช่องว่างติดมา
    """
    s = str(raw or "").strip().strip("<>@!&")
    # ต้อง isascii() ด้วย — "๑๒๓๔๕" ผ่าน isdigit() และแปลงเป็นเลขได้จริงใน Python
    return int(s) if s.isascii() and s.isdigit() and len(s) >= 5 else 0


def exists(user_id):
    """ไอดีนี้เคยเล่นเกมนี้ไหม

    ⚠️ ห้ามใช้ get_player() ถามแทน — มันสร้างตัวละครใหม่ให้ทันทีถ้ายังไม่มี
    วางไอดีมั่ว ๆ แล้วกดเพิ่มจะกลายเป็นปั๊มตัวละครเปล่าเข้าฐานข้อมูล
    """
    conn = _connect()
    try:
        return bool(conn.execute("SELECT 1 FROM players WHERE user_id=?",
                                 (int(user_id),)).fetchone())
    finally:
        conn.close()


def ids_of(user_id):
    """ไอดีเพื่อนทั้งหมด เรียงตามเพิ่งเพิ่มล่าสุด"""
    conn = _connect()
    try:
        return [int(r["friend_id"]) for r in conn.execute(
            "SELECT friend_id FROM friends WHERE user_id=? ORDER BY since DESC",
            (int(user_id),))]
    finally:
        conn.close()


def are_friends(a_id, b_id):
    conn = _connect()
    try:
        return bool(conn.execute(
            "SELECT 1 FROM friends WHERE user_id=? AND friend_id=?",
            (int(a_id), int(b_id))).fetchone())
    finally:
        conn.close()


def add(user_id, raw_id):
    """เพิ่มเพื่อนด้วยไอดีที่วางมา — คืน (ok, ข้อความ)"""
    user_id = int(user_id)
    fid = parse_id(raw_id)
    if not fid:
        return False, "❌ ไอดีไม่ถูกต้อง — คัดลอกไอดี Discord มาวาง (ตัวเลขล้วน)"
    if fid == user_id:
        return False, "❌ เพิ่มตัวเองเป็นเพื่อนไม่ได้นะ"
    if not exists(fid):
        return False, "❌ ไอดีนี้ยังไม่เคยเล่นเกมนี้ — ชวนเขามาสร้างตัวละครก่อน"
    if are_friends(user_id, fid):
        return False, "❌ เป็นเพื่อนกันอยู่แล้ว"

    cap = _max_friends()
    conn = _connect()
    try:
        for a, b in ((user_id, fid), (fid, user_id)):
            n = conn.execute("SELECT COUNT(*) c FROM friends WHERE user_id=?", (a,)).fetchone()["c"]
            if n >= cap:
                who = "คุณ" if a == user_id else "เขา"
                return False, f"❌ รายชื่อเพื่อนของ{who}เต็มแล้ว (สูงสุด {cap} คน)"
        # เพิ่มสองทางในทีเดียว ไม่งั้นฝั่งหนึ่งชวนได้ อีกฝั่งชวนไม่ได้
        now = int(time.time())
        conn.executemany("INSERT OR IGNORE INTO friends(user_id, friend_id, since) VALUES (?,?,?)",
                         [(user_id, fid, now), (fid, user_id, now)])
        conn.commit()
    finally:
        conn.close()

    name = (player_model.get_player(fid) or {}).get("rank") or f"ไอดี {fid}"
    return True, f"👥 เพิ่ม **{name}** เป็นเพื่อนแล้ว! ชวนเข้าห้อง PVP ได้เลย"


def remove(user_id, friend_id):
    """ลบเพื่อน — ตัดทั้งสองทาง คืน (ok, ข้อความ)"""
    user_id, fid = int(user_id), parse_id(friend_id)
    if not fid or not are_friends(user_id, fid):
        return False, "❌ ไม่ได้เป็นเพื่อนกันอยู่แล้ว"
    conn = _connect()
    try:
        conn.executemany("DELETE FROM friends WHERE user_id=? AND friend_id=?",
                         [(user_id, fid), (fid, user_id)])
        conn.commit()
    finally:
        conn.close()
    return True, "👋 ลบออกจากรายชื่อเพื่อนแล้ว"


def _public(player):
    """ข้อมูลสาธารณะของผู้เล่นหนึ่งคน — ตัดทุกอย่างที่เป็นเรื่องส่วนตัวออก"""
    from bot import config_loader, fashion, pets
    from bot.game_data import CONTINENTS

    p = player or {}
    cont = p.get("continent") or "main"
    pet_key = p.get("pet") or ""
    pet = next((x for x in (pets.all_pets() or []) if x.get("key") == pet_key), {})
    guild = player_model.get_guild_of(int(p.get("user_id", 0) or 0)) or {}
    return {
        "id": str(p.get("user_id", "")),
        "name": p.get("rank") or f"ไอดี {p.get('user_id', '')}",
        "level": int(p.get("level", 1) or 1),
        "race": p.get("race") or "",
        "class_name": p.get("class_name") or "",
        "title": p.get("title") or "",
        "continent": cont,
        "continent_label": CONTINENTS.get(cont, {}).get("label", cont),
        "pet": pet.get("name", "") if pet_key else "",
        "guild": guild.get("name", ""),
        "fashion": fashion.worn(p),          # ไว้วาดตัวละครให้ดูหน้าตาจริง
        "armor": p.get("armor") or "None",
        "weapon": p.get("weapon") or "",
        "hp": int(p.get("hp", 0) or 0),
        "max_hp": int(p.get("max_hp", 0) or 0),
        "married": bool(_partner_id(int(p.get("user_id", 0) or 0))),
    }


def _partner_id(user_id):
    from bot import partner
    try:
        return partner.partner_of(user_id)
    except Exception:
        return None


def profile_of(viewer_id, target_id):
    """ดูโปรไฟล์เพื่อน — คืน (ok, ข้อมูล|ข้อความ)

    ดูได้เฉพาะเพื่อนกับตัวเอง ไม่งั้นใครก็ไล่ส่องไอดีคนอื่นทั้งเซิร์ฟได้
    """
    viewer_id, tid = int(viewer_id), parse_id(target_id)
    if not tid:
        return False, "❌ ไอดีไม่ถูกต้อง"
    if tid != viewer_id and not are_friends(viewer_id, tid):
        return False, "❌ ดูได้เฉพาะโปรไฟล์ของเพื่อนเท่านั้น"
    p = player_model.get_player(tid) if exists(tid) else None
    if not p:
        return False, "❌ ไม่พบตัวละครของไอดีนี้"
    return True, _public(p)


def list_of(user_id):
    """รายชื่อเพื่อนพร้อมข้อมูลย่อสำหรับหน้าเว็บ"""
    friends = []
    for fid in ids_of(user_id):
        p = player_model.get_player(fid) if exists(fid) else None
        if p:
            friends.append(_public(p))
    return {"friends": friends, "count": len(friends), "max": _max_friends(),
            "my_id": str(int(user_id))}
