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
    return player_model.week_key(when)          # แหล่งเดียวกับตารางแต้มรายสัปดาห์ (C3)


def previous_week_key(when=None):
    return current_week_key((when or datetime.date.today()) - datetime.timedelta(days=7))


def pay_weekly_ranking(week):
    """จ่ายรางวัลท็อป 3 ของสัปดาห์ที่ปิดไปแล้ว — คืน [(user_id, แต้ม, ทอง, exp), ...]

    เรียกซ้ำได้ปลอดภัย: ตัวเรียกเป็นคนจด paid_week กันจ่ายซ้ำ
    """
    if not config_loader.get_weekly_ranking("enabled", True):
        return []
    rewards = config_loader.get_weekly_ranking("rewards", []) or []
    min_points = int(config_loader.get_weekly_ranking("min_points", 0) or 0)
    paid = []
    for (uid, points), reward in zip(player_model.get_weekly_top(len(rewards), week), rewards):
        if points < min_points:
            break                              # แต้มน้อยเกินเกณฑ์ = ไม่มีใครถัดไปผ่านแน่ (เรียงมากไปน้อย)
        player = player_model.get_player(uid)
        if not player:
            continue
        gold, exp = int(reward.get("gold", 0)), int(reward.get("exp", 0))
        player_model.update_player_field(uid, "bank", player.get("bank", 0) + gold)   # เข้าธนาคาร ตายแล้วไม่หาย
        if exp:
            player_model.add_exp(uid, exp)
        paid.append((uid, points, gold, exp))
    return paid


def build_ranking_embed(week, paid):
    embed = discord.Embed(
        title="🏆 ปิดอันดับประจำสัปดาห์แล้ว!",
        description=f"ผลอันดับนักผจญภัยแห่งสัปดาห์ **{week}**\nรางวัลโอนเข้า **ธนาคาร** ให้เรียบร้อยแล้ว 🏦",
        color=0xf1c40f)
    medals = ["🥇", "🥈", "🥉"]
    for i, (uid, points, gold, exp) in enumerate(paid):
        embed.add_field(name=f"{medals[i] if i < len(medals) else '🎖️'} อันดับ {i + 1}",
                        value=f"<@{uid}> — {points:,} แต้ม\n🪙 +{gold:,} ทอง · 🔷 +{exp:,} EXP",
                        inline=False)
    embed.set_footer(text="สัปดาห์ใหม่เริ่มนับใหม่ตั้งแต่ตอนนี้ — แต้มมาจาก EXP ที่หาได้ทั้งสัปดาห์!")
    return embed


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
        await self._payout_last_week()
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

    async def _payout_last_week(self):
        """🗓️ C3: ขึ้นสัปดาห์ใหม่ = ปิดอันดับสัปดาห์ก่อน จ่ายท็อป 3 แล้วประกาศ (ครั้งเดียวตลอดกาล)"""
        try:
            last = previous_week_key()
            if get_state("paid_week") == last:
                return
            paid = pay_weekly_ranking(last)
            set_state("paid_week", last)          # จดทันทีแม้ไม่มีใครได้ กันวนเช็คทุก 30 นาที
            if not paid:
                return
            print(f"🏆 [WeeklyRank] จ่ายรางวัลสัปดาห์ {last} ให้ {len(paid)} คน")
            channel_id = config_loader.get_channel_id("weekly_event")
            channel = self.bot.get_channel(channel_id) if channel_id else None
            if channel:
                await channel.send(embed=build_ranking_embed(last, paid))
        except Exception as e:
            print(f"⚠️ [WeeklyRank] จ่ายรางวัลรายสัปดาห์พัง: {e}")

    @check_week.before_loop
    async def before_check(self):
        await self.bot.wait_until_ready()


async def setup(bot):
    await bot.add_cog(WeeklyEvent(bot))
