"""ย้ายไป bot/games/pvp/match.py แล้ว (รื้อโครงสร้าง 2026-09-02)

ไฟล์นี้เหลือไว้เป็นสะพานให้โค้ด/เทสที่ยัง import ทางเดิมอยู่ไม่พัง
โค้ดใหม่ให้ import จาก bot.games.pvp.match โดยตรง
"""
from bot.games.pvp.match import *  # noqa: F401,F403

# import * ไม่ดึงชื่อขึ้นต้นด้วย _ ให้ - เทส test_worms_*.py เรียกข้ามไฟล์
# ผ่านชื่อพวกนี้อยู่ ต้องดึงมาเพิ่มเองในสะพาน
from bot.games.pvp.match import (  # noqa: F401
    _bodies,
    _bot_aim,
    _bot_attack,
    _check_over,
    _death_blasts,
    _explode,
    _fall_hurt,
    _knock_back,
    _open_chests,
    _ride_ferry,
    _rise_disaster,
    _settle_everyone,
    _supply_drop,
    _use_skill,
)
