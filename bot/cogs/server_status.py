# 📡 แจ้งเตือนเปิด-ปิดเซิร์ฟ — ตั้งห้องได้ในแท็บ Channels ของ panel (key: server_status)
# เปิด: ประกาศตอนบอทออนไลน์ | ปิด: panel วางไฟล์ธง shutdown_request.flag → บอทประกาศแล้วปิดตัวเองอย่างสุภาพ
import os

from discord.ext import commands, tasks

from app_paths import get_app_root
from bot import config_loader

SHUTDOWN_FLAG = os.path.join(get_app_root(), "shutdown_request.flag")


class ServerStatus(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self._announced_open = False
        # เก็บกวาดธงค้างจากรอบก่อน (กันเปิดบอทมาแล้วปิดตัวเองทันที)
        try:
            if os.path.exists(SHUTDOWN_FLAG):
                os.remove(SHUTDOWN_FLAG)
        except OSError:
            pass
        self.watch_shutdown.start()
        print("[LOG] [LOAD_COG] โหลดโมดูลแจ้งเตือนเปิด-ปิดเซิร์ฟเรียบร้อยแล้ว")

    def cog_unload(self):
        self.watch_shutdown.cancel()

    def _channel(self):
        cid = config_loader.get_channel_id("server_status")
        return self.bot.get_channel(cid) if cid else None

    @commands.Cog.listener()
    async def on_ready(self):
        if self._announced_open:
            return  # reconnect ไม่ประกาศซ้ำ — ครั้งเดียวต่อการเปิดเซิร์ฟ
        self._announced_open = True
        channel = self._channel()
        if channel:
            await channel.send("🟢 **เซิร์ฟเวอร์เปิดแล้ว!** โลกแห่งการผจญภัยกลับมาออนไลน์ — `!play` ลุยกันเลย!")

    @tasks.loop(seconds=2)
    async def watch_shutdown(self):
        """เฝ้าไฟล์ธงจากปุ่ม Stop ของ panel — เจอแล้วประกาศลา + ปิดตัวเองอย่างสุภาพ"""
        if not os.path.exists(SHUTDOWN_FLAG):
            return
        try:
            os.remove(SHUTDOWN_FLAG)
        except OSError:
            pass
        channel = self._channel()
        if channel:
            try:
                await channel.send("🔴 **เซิร์ฟเวอร์ปิดปรับปรุงชั่วคราว** — ข้อมูลทุกอย่างถูกบันทึกแล้ว แล้วพบกันใหม่เร็ว ๆ นี้!")
            except Exception:
                pass
        await self.bot.close()

    @watch_shutdown.before_loop
    async def _wait_ready(self):
        await self.bot.wait_until_ready()


async def setup(bot):
    await bot.add_cog(ServerStatus(bot))
