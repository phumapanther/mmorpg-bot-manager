# bot/cogs/web_link.py
"""สะพานเว็บไซต์เกม ↔ ดิสคอร์ด — !weblogin (ยืนยันโค้ดล็อกอินเว็บ) + !web (ส่งลิงก์เว็บ)

โหลดเฉพาะเซิร์ฟหลัก และทำงานเฉพาะเครื่องที่มีโฟลเดอร์ license_server (เครื่องผู้พัฒนา/เจ้าของเกม)
— เครื่องลูกค้าที่ลงจาก exe ไม่มีโฟลเดอร์นี้ cog จะข้ามตัวเองเงียบๆ ไม่กระทบอะไร
"""
import os
import re
import sqlite3
import time

import discord
from discord.ext import commands

from bot.utils import main_server_only

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
WEB_DB = os.path.join(_ROOT, "license_server", "web.db")
URL_FILE = os.path.join(_ROOT, "LICENSE_SERVER_URL.txt")
_CODE_RE = re.compile(r"^[A-Z0-9]{6}$")


def confirm_login_code(code, discord_id, db_path=None):
    """ยืนยันโค้ดล็อกอินเว็บ — คืน (สำเร็จไหม, ข้อความตอบผู้เล่น) — แยกจาก discord เพื่อเทสตรงได้"""
    code = (code or "").strip().upper()
    if not _CODE_RE.match(code):
        return False, "❌ รูปแบบโค้ดไม่ถูกต้อง — ต้องเป็นโค้ด 6 ตัวจากหน้าเว็บ เช่น `!weblogin AB12CD`"
    path = db_path or WEB_DB
    if not os.path.exists(path):
        return False, "❌ ระบบเว็บยังไม่เปิดใช้งานบนเซิร์ฟนี้"
    conn = sqlite3.connect(path, timeout=5)
    try:
        conn.execute("PRAGMA busy_timeout=5000")
        cur = conn.execute(
            "UPDATE login_codes SET discord_id=? "
            "WHERE code=? AND discord_id IS NULL AND used=0 AND expires_at > ?",
            (str(discord_id), code, time.time()))
        conn.commit()
        if cur.rowcount == 0:
            return False, "❌ โค้ดไม่ถูกต้องหรือหมดอายุแล้ว — กลับไปกดขอโค้ดใหม่ที่หน้าเว็บ"
        return True, "✅ **ล็อกอินสำเร็จ!** กลับไปที่หน้าเว็บได้เลย ระบบจะพาเข้าโปรไฟล์อัตโนมัติ"
    finally:
        conn.close()


def website_url():
    try:
        return open(URL_FILE, encoding="utf-8").read().strip()
    except OSError:
        return ""


class WebLink(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="weblogin")
    @main_server_only()
    async def weblogin(self, ctx, code: str = ""):
        ok, msg = confirm_login_code(code, ctx.author.id)
        try:
            await ctx.message.delete()   # ลบโค้ดออกจากแชท (best-effort)
        except Exception:
            pass
        await ctx.send(f"{ctx.author.mention} {msg}", delete_after=30 if ok else 20)

    @commands.command(name="web")
    async def web(self, ctx):
        url = website_url()
        if not url:
            return await ctx.send("🌐 เว็บไซต์ยังไม่เปิดให้บริการตอนนี้ครับ")
        embed = discord.Embed(
            title="🌐 เว็บไซต์เกม",
            description=(f"ข่าวสาร · อัพเดทแพทช์ · ข้อมูลเกม · เติมเกม · โปรไฟล์\n{url}\n\n"
                         f"🔑 ล็อกอินเว็บ: กดขอโค้ดที่หน้าเว็บ แล้วพิมพ์ `!weblogin <โค้ด>` ที่นี่"),
            color=0xd93b2b)
        await ctx.send(embed=embed)


async def setup(bot):
    if not os.path.isdir(os.path.join(_ROOT, "license_server")):
        print("🌐 [web_link] เครื่องนี้ไม่มี license_server — ข้าม cog เว็บ")
        return
    await bot.add_cog(WebLink(bot))
