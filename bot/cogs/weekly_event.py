"""ประกาศธีมอีเวนต์ประจำสัปดาห์ (Weekly Chaos) อัตโนมัติเมื่อขึ้นสัปดาห์ใหม่

ธีมถูกเลือกแบบ deterministic จากเลขสัปดาห์ ISO (game_modifiers.get_weekly_theme)
cog นี้มีหน้าที่เดียว: เห็นสัปดาห์ใหม่ครั้งแรก → โพสต์ประกาศในห้องที่ตั้ง แล้วจดกันประกาศซ้ำ
"""
import datetime
import sqlite3

import discord
from discord.ext import commands, tasks

import bot.models.player_model as player_model
from bot import config_loader, game_modifiers


def _connect():
    conn = sqlite3.connect(player_model.DB_NAME)
    conn.execute("CREATE TABLE IF NOT EXISTS weekly_state (key TEXT PRIMARY KEY, value TEXT)")
    return conn


def get_state(key):
    conn = _connect()
    try:
        row = conn.execute("SELECT value FROM weekly_state WHERE key = ?", (key,)).fetchone()
        return row[0] if row else None
    finally:
        conn.close()


def set_state(key, value):
    conn = _connect()
    try:
        conn.execute("INSERT OR REPLACE INTO weekly_state (key, value) VALUES (?, ?)", (key, value))
        conn.commit()
    finally:
        conn.close()


def current_week_key(when=None):
    year, week, _ = (when or datetime.date.today()).isocalendar()
    return f"{year}-W{week}"


def build_announce_embed(theme):
    embed = discord.Embed(
        title=f"🎪 อีเวนต์ประจำสัปดาห์: {theme['label']}",
        description=theme.get("description", ""),
        color=0xed8936,
    )
    embed.set_footer(text="ธีมจะเปลี่ยนใหม่ทุกวันจันทร์ — มีผลอัตโนมัติทั้งเซิร์ฟ")
    return embed


class WeeklyEvent(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.check_week.start()

    def cog_unload(self):
        self.check_week.cancel()

    @tasks.loop(minutes=30)
    async def check_week(self):
        try:
            theme = game_modifiers.get_weekly_theme()
            if not theme:
                return  # ยังไม่มีธีมในคลัง (หรือปิดระบบ) — เงียบไว้

            week_key = current_week_key()
            if get_state("announced_week") == week_key:
                return  # สัปดาห์นี้ประกาศแล้ว (กัน restart ประกาศซ้ำ)

            channel_id = config_loader.get_channel_id("weekly_event")
            if not channel_id:
                return  # ไม่ตั้งห้องประกาศ = ธีมทำงานเงียบๆ

            channel = self.bot.get_channel(channel_id)
            if not channel:
                print(f"⚠️ [WeeklyEvent] หาห้องประกาศ id={channel_id} ไม่เจอ")
                return

            await channel.send(embed=build_announce_embed(theme))
            set_state("announced_week", week_key)
            print(f"📅 [WeeklyEvent] ประกาศธีมสัปดาห์ {week_key}: {theme['label']}")
        except Exception as e:
            print(f"⚠️ [WeeklyEvent] loop ผิดพลาด: {e}")

    @check_week.before_loop
    async def before_check(self):
        await self.bot.wait_until_ready()


async def setup(bot):
    await bot.add_cog(WeeklyEvent(bot))
