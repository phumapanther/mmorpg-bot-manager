"""ย้ายไป bot/games/pvp/terrain.py แล้ว (รื้อโครงสร้าง 2026-09-02)

ไฟล์นี้เหลือไว้เป็นสะพานให้โค้ด/เทสที่ยัง import ทางเดิมอยู่ไม่พัง
โค้ดใหม่ให้ import จาก bot.games.pvp.terrain โดยตรง
"""
from bot.games.pvp.terrain import *  # noqa: F401,F403
from bot.games.pvp.terrain import (  # noqa: F401
    _building,   # test_worms_move.py, test_worms_props.py ใช้
    _open_spots,  # test_worms_attack.py, test_worms_predict.py ใช้
    _standable,  # test_worms_props.py ใช้
    _tree,       # test_worms_props.py ใช้
)
