"""ย้ายไป bot/games/casino/hilo/core.py + bot/games/casino/slots/core.py แล้ว
(รื้อโครงสร้าง 2026-09-02 — แยกไฮโล/สล็อตออกจากกัน + _take_bet ไปอยู่ shared.py)

ไฟล์นี้เหลือไว้เป็นสะพานให้โค้ดเก่าที่ยัง import ทางเดิมอยู่ ไม่พัง
โค้ดใหม่ให้ import จาก bot.games.casino.hilo.core / bot.games.casino.slots.core โดยตรง

⚠️ อย่าลบไฟล์นี้ทิ้งดื้อ ๆ — hilo/core.py::play_hilo ยังอ้อมเรียก roll_hilo
ผ่านชื่อสะพานนี้อยู่ (ดูคอมเมนต์ ponytail ในไฟล์นั้น) เพราะ tests/test_casino_core.py
monkeypatch cc.roll_hilo ผ่านชื่อเดิมนี้ ถ้าลบไฟล์นี้ก่อนย้ายเทสไปที่ใหม่ก่อน
play_hilo จะ import ไม่ได้
"""
from bot.games.casino.hilo.core import *   # noqa: F401,F403
from bot.games.casino.slots.core import *  # noqa: F401,F403
from bot.games.casino.shared import _take_bet  # noqa: F401
