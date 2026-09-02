"""ย้ายไป bot/apps/bot_game/guild.py แล้ว (รื้อโครงสร้าง 09-02)

เหลือไว้เป็นสะพานให้ bot/main.py กับเทสที่ยัง import ทางเดิมไม่พัง
"""
from bot.apps.bot_game.guild import *  # noqa: F401,F403
from bot.apps.bot_game.guild import setup  # noqa: F401
# bot/apps/bot_game/guild_war.py เรียก guild._is_leader ตรง ๆ ผ่านสะพานนี้
# (import * ไม่ดึงชื่อขึ้นต้นด้วย _ ให้ — ต้องดึงมาเพิ่มเองตรงนี้)
from bot.apps.bot_game.guild import _is_leader  # noqa: F401
