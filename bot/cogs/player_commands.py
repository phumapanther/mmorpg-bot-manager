"""ย้ายไป bot/apps/bot_game/player_commands.py แล้ว (รื้อโครงสร้าง 09-02)

เหลือไว้เป็นสะพานให้ bot/main.py กับเทสที่ยัง import ทางเดิมไม่พัง
"""
from bot.apps.bot_game.player_commands import *  # noqa: F401,F403
from bot.apps.bot_game.player_commands import setup  # noqa: F401
# tests/test_codex_is_current.py เรียก player_commands._item_effect_desc ตรง ๆ
# (import * ไม่ดึงชื่อขึ้นต้นด้วย _ ให้ — ต้องดึงมาเพิ่มเองตรงนี้)
from bot.apps.bot_game.player_commands import _item_effect_desc  # noqa: F401
