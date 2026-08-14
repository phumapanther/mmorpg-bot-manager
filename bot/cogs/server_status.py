# 📡 แจ้งเตือนเปิด-ปิดเซิร์ฟ — ตั้งห้องได้ในแท็บ Channels ของ panel (key: server_status)
# เปิด: ประกาศตอนบอทออนไลน์ | ปิด: panel วางไฟล์ธง shutdown_request.flag → บอทประกาศแล้วปิดตัวเองอย่างสุภาพ
import asyncio
import os
import time

from discord.ext import commands, tasks

from app_paths import get_shutdown_flag
from bot import config_loader

SHUTDOWN_FLAG = get_shutdown_flag()
FLAG_MAX_AGE = 30   # ธงเก่ากว่านี้ = ไม่ใช่คำสั่งสดจาก panel (ไฟล์ค้าง/ถูกซิงค์กลับมา) ห้ามเชื่อ


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
        try:
            age = time.time() - os.path.getmtime(SHUTDOWN_FLAG)
        except OSError:
            return                      # ไม่มีธง = ปกติ (เคสส่วนใหญ่)
        try:
            os.remove(SHUTDOWN_FLAG)
        except OSError:
            pass
        if age > FLAG_MAX_AGE:
            print(f"⚠️ [SHUTDOWN] เจอธงปิดเซิร์ฟค้างเก่า {int(age)} วิ — ไม่ใช่คำสั่งจริง ทิ้งแล้วรันต่อ")
            return
        print("🔴 [SHUTDOWN] ได้รับคำสั่งปิดจาก Panel — กำลังประกาศแล้วปิดตัวเอง")
        channel = self._channel()
        if channel:
            try:
                await channel.send("🔴 **เซิร์ฟเวอร์ปิดปรับปรุงชั่วคราว** — ข้อมูลทุกอย่างถูกบันทึกแล้ว แล้วพบกันใหม่เร็ว ๆ นี้!")
            except Exception:
                pass
        # ปิดให้ครบทุกบอทในโปรเซส (เกม + บอทแจก) ไม่งั้นโปรเซสไม่จบ
        # แล้ว Panel ต้องรอหมดเวลาก่อนบังคับฆ่า — ปุ่ม Stop เลยดูเหมือนค้าง 8 วินาที
        # ปิดในงานแยก ห้าม await ตรงนี้!
        # bot.close() จะ unload cog ทุกตัว ซึ่งรวมถึง cog นี้ → cog_unload สั่ง cancel
        # ลูป watch_shutdown ที่กำลังรันคำสั่งนี้อยู่ = งานตัวเองถูกยกเลิกกลางคัน
        # close() จึงทำไม่จบ บอทไม่ปิด โปรเซสค้าง พาแนลต้องรอหมดเวลาแล้วบังคับฆ่า
        from bot import bot_registry
        asyncio.create_task(bot_registry.close_all())

    @watch_shutdown.before_loop
    async def _wait_ready(self):
        await self.bot.wait_until_ready()


async def setup(bot):
    await bot.add_cog(ServerStatus(bot))
