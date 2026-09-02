"""ย้ายไป bot/apps/bot_worker/voice_chat_tracker.py แล้ว (รื้อโครงสร้าง 09-02)

เหลือไว้เป็นสะพานให้ bot/main.py กับเทสที่ยัง import ทางเดิมไม่พัง
"""
from bot.apps.bot_worker.voice_chat_tracker import *  # noqa: F401,F403
from bot.apps.bot_worker.voice_chat_tracker import setup  # noqa: F401
# tests/test_voice_chat_tracker.py เรียก voice_chat_tracker._stacked_multiplier ตรง ๆ
# (import * ไม่ดึงชื่อขึ้นต้นด้วย _ ให้ — ต้องดึงมาเพิ่มเองตรงนี้)
from bot.apps.bot_worker.voice_chat_tracker import _stacked_multiplier  # noqa: F401
