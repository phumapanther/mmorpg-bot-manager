"""ย้ายไป bot/games/casino/uno/table.py แล้ว (รื้อโครงสร้าง 2026-09-02)

ไฟล์นี้เหลือไว้เป็นสะพานให้โค้ดเก่าที่ยัง import ทางเดิมอยู่ ไม่พัง
โค้ดใหม่ให้ import จาก bot.games.casino.uno.table โดยตรง
"""
from bot.games.casino.uno.table import *  # noqa: F401,F403
from bot.games.casino.uno.table import _run_bots  # noqa: F401  (tests/test_uno_web.py ใช้ผ่าน inspect.getsource)
