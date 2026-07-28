# 🌍 บอทแจก (P8) — โหลดเฉพาะ bot_type "guest": ตั้งห้องเล่นรายเซิร์ฟ + ด่านห้อง + ปุ่มไปเซิร์ฟหลัก
# เซิร์ฟรองเล่นได้เฉพาะห้องที่แอดมินเซิร์ฟนั้นผูกไว้ (ตั้งได้หลายห้อง)
import discord
from discord.ext import commands

import bot.models.player_model as player_model
from bot import config_loader
from bot.utils import is_main_server

# คำสั่งที่อนุญาตให้ใช้ "นอกห้องเล่น" ได้ (คำสั่งตั้งค่าของแอดมินเซิร์ฟ)
SETUP_COMMANDS = {"set_adv_channel", "unset_adv_channel", "adv_channels"}


class GuestServer(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        bot.add_check(self.channel_gate)
        print("[LOG] [LOAD_COG] โหลดโมดูลบอทแจก (เซิร์ฟรอง) เรียบร้อยแล้ว")

    def cog_unload(self):
        self.bot.remove_check(self.channel_gate)

    async def channel_gate(self, ctx):
        """ด่านกลางของบอทแจก: เล่นได้เฉพาะห้องที่ผูกไว้ (เซิร์ฟหลักไม่ถูกจำกัด)"""
        if not ctx.guild or is_main_server(ctx):
            return True
        if ctx.command and ctx.command.name in SETUP_COMMANDS:
            return True
        allowed = player_model.get_adv_channels(ctx.guild.id)
        if not allowed:
            await ctx.send("⚠️ เซิร์ฟนี้ยังไม่ได้ตั้งห้องผจญภัย — แอดมินพิมพ์ `!set_adv_channel` ในห้องที่ต้องการก่อนนะ")
            return False
        if ctx.channel.id not in allowed:
            rooms = " ".join(f"<#{cid}>" for cid in allowed[:5])
            await ctx.send(f"❌ **ผิดห้อง!** เล่นได้ที่ {rooms} เท่านั้น", delete_after=8)
            return False
        return True

    # ── คำสั่งตั้งค่าของแอดมินเซิร์ฟรอง ──
    @commands.command(name="set_adv_channel")
    @commands.has_permissions(administrator=True)
    async def set_adv_channel(self, ctx, channel: discord.TextChannel = None):
        target = channel or ctx.channel
        if player_model.add_adv_channel(ctx.guild.id, target.id):
            await ctx.send(f"✅ ตั้ง {target.mention} เป็นห้องผจญภัยแล้ว! (ตั้งได้หลายห้อง — พิมพ์ซ้ำในห้องอื่นได้เลย)\n"
                           f"ผู้เล่นเริ่มด้วย `!play` ได้ทันที")
        else:
            await ctx.send(f"ℹ️ {target.mention} เป็นห้องผจญภัยอยู่แล้ว")

    @commands.command(name="unset_adv_channel")
    @commands.has_permissions(administrator=True)
    async def unset_adv_channel(self, ctx, channel: discord.TextChannel = None):
        target = channel or ctx.channel
        if player_model.remove_adv_channel(ctx.guild.id, target.id):
            await ctx.send(f"🗑️ ถอด {target.mention} ออกจากห้องผจญภัยแล้ว")
        else:
            await ctx.send(f"ℹ️ {target.mention} ไม่ได้เป็นห้องผจญภัยอยู่แล้ว")

    @commands.command(name="adv_channels")
    async def adv_channels(self, ctx):
        allowed = player_model.get_adv_channels(ctx.guild.id)
        invite = config_loader.get_main_server_invite()
        embed = discord.Embed(
            title="🌍 ห้องผจญภัยของเซิร์ฟนี้", color=0x2ecc71,
            description=("\n".join(f"• <#{cid}>" for cid in allowed) if allowed
                         else "ยังไม่ได้ตั้ง — แอดมินพิมพ์ `!set_adv_channel` ในห้องที่ต้องการ"))
        if invite:
            embed.add_field(
                name="✨ อยากได้ระบบเต็ม?",
                value=(f"รางวัลรายวัน ร้านค้า คาสิโน กิลด์ PvP และอื่น ๆ เล่นได้ที่**เซิร์ฟหลัก**เท่านั้น\n{invite}"),
                inline=False)
        await ctx.send(embed=embed)


async def setup(bot):
    await bot.add_cog(GuestServer(bot))
