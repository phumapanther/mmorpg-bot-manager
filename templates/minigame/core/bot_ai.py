"""🤖 บอทผลัดทาย — ขั้น 3 ของเกมทายเลข 1-10

ทำไมต้องมีบอท: ไม่มีบอท = ต้องรอเพื่อนออนไลน์พร้อมกันก่อนถึงจะทดสอบเกมได้
ทำบอทก่อนโหมดหลายคนเสมอ — เทสคนเดียวได้ (ดู tests/test_engine.py) งานเดินเร็วกว่ามาก

🔒 กติกาเหล็ก (ยกมาจาก UNO — bot/games/casino/uno/bot_ai.py):
   บอทควรรับแค่ "สิ่งที่ทุกคนบนโต๊ะเห็นได้" ไม่ใช่ทั้งก้อน state
   เกมนี้ทายเลขไม่มีของลับให้บอทแอบดู (secret คือของลับ ไม่ใช่ "มือ" ของใคร)
   แต่ยังฝึกวินัยเดิม: choose()/narrow() ไล่ทวนแค่ "ประวัติการทายของตัวเอง"
   ไม่แอบอ่าน st["secret"] ตรง ๆ ทั้งที่ทำได้ (เพราะมี state ทั้งก้อนอยู่ในมือ)
"""
import random

from . import rules as R

BOT_NAME = "🤖 บอท"


def is_bot(name):
    """ชื่อนี้เป็นบอทไหม — เทียบชื่อเต็ม (โต๊ะหลายบอทชื่อจะมีเลขต่อท้าย)"""
    return str(name or "").startswith(BOT_NAME)


def bot_names(count):
    """ชื่อบอทหลายตัวไม่ให้ซ้ำกัน"""
    if count <= 1:
        return [BOT_NAME] if count == 1 else []
    return [f"{BOT_NAME} {i + 1}" for i in range(count)]


def narrow(low, high, guess, result):
    """แคบช่วงที่เป็นไปได้ลงหลังรู้ผลทาย — ใช้ตัดสินตาถัดไป"""
    if result == "higher":
        return max(low, guess + 1), high
    if result == "lower":
        return low, min(high, guess - 1)
    return low, high


def choose(low=R.MIN_NUM, high=R.MAX_NUM, rng=None):
    """บอทจะทายเลขไหนต่อ — รับแค่ช่วงที่เป็นไปได้ตอนนี้

    กลยุทธ์ทายกึ่งกลาง (binary search) — ไล่บี้ช่วงให้แคบเร็วที่สุด
    ไม่ต้องฉลาดมาก แค่ไม่เดามั่วก็พอสูสีกับคนเล่นจริงแล้ว
    """
    rng = rng or random.Random()
    return (low + high) // 2


def take_turn(engine, st, rng=None):
    """ให้บอทที่ถึงตาทายหนึ่งครั้ง — คืน (ok, ผล)

    รับ engine เข้ามาเพื่อไม่ให้ไฟล์นี้ต้อง import วนกลับไปหา engine.py
    (engine.py เป็นคนเรียกใช้บอท ไม่ใช่ทางกลับกัน — แบบเดียวกับ UNO)
    """
    rng = rng or random.Random()
    i = st["turn"]
    mine = st["players"][i]["guesses"]     # ประวัติการทายของ "ตัวเองเท่านั้น"
    low, high = R.MIN_NUM, R.MAX_NUM
    for g in mine:
        low, high = narrow(low, high, g["n"], g["result"])
    number = choose(low, high, rng)
    return engine.guess(st, number)
