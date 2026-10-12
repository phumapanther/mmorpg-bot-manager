"""สำรองฐานข้อมูลเกมอัตโนมัติ — วันละครั้ง เก็บ 7 ชุดล่าสุด
(กันเซฟผู้เล่น/ของแรร์หายถาวร — ไฟล์อยู่ในโฟลเดอร์ backups/ ข้างตัวเกม)

ใช้ sqlite backup API สำรองแบบ hot-safe: ปลอดภัยแม้บอทกำลังเขียน DB อยู่
"""
import os
import sqlite3
from datetime import datetime

from discord.ext import commands, tasks

from app_paths import get_app_root
import bot.models.player_model as player_model

# Docker/NAS: ชี้เข้า volume ผ่าน BACKUP_DIR — ไม่งั้น backup อยู่ใน container layer หายพร้อม DB ตอน build ใหม่
BACKUP_DIR = os.environ.get("BACKUP_DIR") or os.path.join(get_app_root(), "backups")
KEEP_LAST = 7


def run_backup():
    """สำรอง DB หนึ่งชุด + หมุนเวียนลบชุดเก่าเกิน KEEP_LAST — คืน path ไฟล์ที่สร้าง"""
    os.makedirs(BACKUP_DIR, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    dest_path = os.path.join(BACKUP_DIR, f"game_data-{stamp}.db")

    src = sqlite3.connect(player_model.DB_NAME)
    dest = sqlite3.connect(dest_path)
    try:
        src.backup(dest)
    finally:
        dest.close()
        src.close()

    backups = sorted(f for f in os.listdir(BACKUP_DIR)
                     if f.startswith("game_data-") and f.endswith(".db"))
    for old_file in backups[:-KEEP_LAST]:
        try:
            os.remove(os.path.join(BACKUP_DIR, old_file))
        except OSError:
            pass
    return dest_path


class DbBackup(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.daily_backup.start()

    def cog_unload(self):
        self.daily_backup.cancel()

    @tasks.loop(hours=24)
    async def daily_backup(self):
        # รอบแรกยิงทันทีหลังบอทพร้อม → มี backup สดเสมอหลังเปิดบอท
        try:
            path = run_backup()
            print(f"💾 [Backup] สำรองฐานข้อมูลเกมแล้ว: {path}")
        except Exception as e:
            print(f"⚠️ [Backup] สำรองฐานข้อมูลล้มเหลว: {e}")

    @daily_backup.before_loop
    async def before_backup(self):
        await self.bot.wait_until_ready()


async def setup(bot):
    await bot.add_cog(DbBackup(bot))
