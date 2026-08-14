"""ทะเบียนบอทที่กำลังรันในโปรเซสนี้ — ปุ่ม Stop ของ Panel ต้องปิดให้ครบทุกตัว

ทำไมต้องแยกเป็นไฟล์ของตัวเอง:
บอทถูกรันด้วย `python -m bot.main` โมดูลนั้นจึงกลายเป็น `__main__`
ถ้า cog สั่ง `from bot.main import ...` Python จะโหลด bot/main.py ขึ้นมา "อีกตัวหนึ่ง"
ตัวแปรจึงเป็นคนละก้อนกัน ทะเบียนที่เก็บไว้ฝั่ง __main__ จะมองไม่เห็นจากฝั่ง cog เลย
(เคสจริง 2026-08-14: ใส่ ACTIVE_BOTS ไว้ใน bot/main.py แล้ว cog อ่านได้ลิสต์ว่าง
 บอทเลยไม่ถูกปิด ปุ่ม Stop ค้าง 8 วินาทีทุกครั้ง)
ไฟล์นี้ไม่มีใครรันเป็น __main__ ทุกฝั่งจึง import ได้ก้อนเดียวกันเสมอ
"""

ACTIVE_BOTS = []
_shutting_down = False


def register(bot):
    if bot not in ACTIVE_BOTS:
        ACTIVE_BOTS.append(bot)
    return bot


def is_shutting_down():
    """สั่งปิดไปแล้วหรือยัง — ลูปลองเปิดใหม่ต้องเช็คก่อนเสมอ

    ตอนปิดคอนเนกชัน discord.py อาจโยน error สายเน็ตออกมา ถ้าลูป retry จับไว้แล้ว
    นั่งรอเปิดใหม่ โปรเซสจะไม่มีวันจบ พาแนลต้องรอหมดเวลาแล้วบังคับฆ่า
    """
    return _shutting_down


async def close_all():
    """ปิดบอททุกตัวในโปรเซส — ตัวหนึ่งพังต้องไม่ทำให้ตัวอื่นไม่ถูกปิด"""
    global _shutting_down
    _shutting_down = True
    for b in list(ACTIVE_BOTS):
        try:
            if not b.is_closed():
                await b.close()
        except Exception as e:
            print(f"⚠️ [SHUTDOWN] ปิดบอท {getattr(b, 'bot_type', '?')} ไม่สำเร็จ: {e}")
