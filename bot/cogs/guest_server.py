"""ย้ายไป bot/apps/bot_admin/guest_server.py แล้ว (รื้อโครงสร้าง 09-02)

เหลือไว้เป็นสะพานให้ bot/main.py กับเทสที่ยัง import ทางเดิมไม่พัง
"""
from bot.apps.bot_admin.guest_server import *  # noqa: F401,F403
from bot.apps.bot_admin.guest_server import setup  # noqa: F401
