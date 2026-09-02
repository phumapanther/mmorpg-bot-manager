#cogs/bj24 สำหรับผู้เล่น
import discord
from discord.ext import commands
import random
import json
from bot.utils import not_arrested, allowed_channel,has_permission, main_server_gate
from bot.controller.trainer import train_alpha_bot
# นำเข้าระบบจัดการผู้เล่นของคุณอาเธอร์
import bot.models.player_model as player_model

# นำเข้าระบบ AI ของคุณ
from bot.controller.bot_brain import BlackjackBot
from bot.controller import db_manager

# ตรรกะเกมทั้งหมด (แจกไพ่/ตุกติก/ตัดสิน/สอนสมองกล) ย้ายไป bot/blackjack_core.py
# เพื่อให้เว็บเรียกชุดเดียวกัน — ที่เหลือในไฟล์นี้คือหน้าตาฝั่ง Discord ล้วนๆ
# re-export ไว้ให้โค้ด/เทสเดิมที่อ้างจากไฟล์นี้ยังใช้ได้
from bot.blackjack_core import rig_chance_for, stack_bot_hand   # noqa: F401


def _fmt_hand(cards):
    return " ".join(f"[{c[0]}]" for c in cards)


class BJ24View(discord.ui.View):
    """ปุ่มจั่ว/พอ — สถานะเกมอยู่ใน DB (blackjack_core) ไม่ได้เก็บใน View แล้ว
    ผลพลอยได้: เปิดโต๊ะในดิสแล้วไปเล่นต่อบนเว็บได้"""

    def __init__(self, user):
        super().__init__(timeout=180.0)
        self.user = user

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.user.id:
            await interaction.response.send_message("❌ นี่ไม่ใช่โต๊ะไพ่ของคุณ!", ephemeral=True)
            return False
        return True

    async def on_timeout(self):
        for item in self.children:
            item.disabled = True
        try:
            await self.message.edit(content="⏳ หมดเวลาตัดสินใจ — โต๊ะยังค้างอยู่ "
                                            "พิมพ์ `!bj` ใหม่หรือไปเล่นต่อบนเว็บได้", view=self)
        except Exception as e:
            print(f"[ERROR] [BJ24_TIMEOUT] แก้ไขข้อความตอนหมดเวลาไม่ได้: {e}")

    @staticmethod
    def embed_for(view):
        over = view.get("over")
        color = discord.Color.blue()
        if over:
            color = {"win": discord.Color.green(), "lose": discord.Color.red(),
                     "draw": discord.Color.gold(), "bust": discord.Color.red()}.get(
                         view.get("result"), discord.Color.blue())
        e = discord.Embed(title="🃏 Blackjack 24 (ML Edition)", color=color)
        e.add_field(name=f"👤 ไพ่ของคุณ ({view['player_score']} แต้ม)",
                    value=_fmt_hand(view["player"]), inline=False)
        if over:
            e.add_field(name=f"🤖 ไพ่ของบอท ({view['bot_score']} แต้ม)",
                        value=_fmt_hand(view["bot"]), inline=False)
            body = "\n".join(view.get("bot_log") or [])
            e.description = f"**สรุปผล:**\n{view['message']}" + (f"\n{body}" if body else "")
        else:
            e.add_field(name="🤖 ไพ่ของบอท", value=f"[{view['bot'][0][0]}] [❓]", inline=False)
            e.description = (f"เงินเดิมพัน: `{view['bet']:,}` ทอง\n"
                             "เลือกการกระทำของคุณด้านล่าง!")
        return e

    async def _act(self, interaction, fn):
        ok, out = fn(self.user.id)
        if not ok:
            return await interaction.response.send_message(out["message"], ephemeral=True)
        if out.get("over"):
            for item in self.children:
                item.disabled = True
            self.stop()
        await interaction.response.edit_message(embed=self.embed_for(out), view=self)

    @discord.ui.button(label="👇 Hit (จั่ว)", style=discord.ButtonStyle.primary, custom_id="bj_hit")
    async def hit(self, interaction: discord.Interaction, button: discord.ui.Button):
        from bot import blackjack_core
        await self._act(interaction, blackjack_core.hit)

    @discord.ui.button(label="✋ Stand (พอ)", style=discord.ButtonStyle.success, custom_id="bj_stand")
    async def stand(self, interaction: discord.Interaction, button: discord.ui.Button):
        from bot import blackjack_core
        await self._act(interaction, blackjack_core.stand)


class BJ24Game(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.bot_brain = BlackjackBot()

    # --- คำสั่งเล่นเกม ---
    @allowed_channel("casino_bj")
    @not_arrested()
    @commands.command(name="bj")
    async def play_bj(self, ctx, bet: int):
        try:
            print(f"[LOG] [BJ_COMMAND] {ctx.author.name} เริ่มเกมด้วยเงิน {bet}")

            from bot import blackjack_core
            ok, out = blackjack_core.start(ctx.author.id, bet)   # ตรวจเงิน/หักเงิน/แจกไพ่ อยู่ใน core
            if not ok:
                return await ctx.send(out["message"])

            view = BJ24View(ctx.author)
            msg = await ctx.send(embed=BJ24View.embed_for(out), view=view)
            view.message = msg  # จำเป็นสำหรับ on_timeout

        except Exception as e:
            print(f"[ERROR] [BJ_COMMAND] {e}")
            await ctx.send("❌ เกิดข้อผิดพลาดในการเริ่มเกม!")

    # --- คำสั่งเทรนบอท (Admin Only) ---
    @has_permission("admin")
    @commands.has_permissions(administrator=True)
    @commands.command(name="train")
    async def train_bot(self, ctx, iterations: int = 1000):
        await ctx.send(f"🤖 กำลังฝึกสมอง AlphaBot {iterations} รอบ...")
        try:
            train_alpha_bot(iterations)
            # รีโหลดสมองใหม่
            self.bot_brain = BlackjackBot()
            await ctx.send(f"✅ ฝึกเสร็จสิ้น! บอทฉลาดขึ้นแล้ว")
        except Exception as e:
            await ctx.send(f"❌ เทรนล้มเหลว: {e}")

async def setup(bot):

    async def cog_check(self, ctx):
        """P8: ฟีเจอร์นี้เล่นได้เฉพาะเซิร์ฟหลัก (เซิร์ฟรองเล่นได้แค่ผจญภัย)"""
        return await main_server_gate(ctx)
    await bot.add_cog(BJ24Game(bot))