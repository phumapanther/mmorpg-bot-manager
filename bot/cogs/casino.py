import discord
from discord.ext import commands
import random
import asyncio

import bot.models.player_model as player_model
from bot import config_loader
from bot.utils import not_arrested, allowed_channel, main_server_gate

# ==========================================
# 🎲 UI View สำหรับเกม ไฮโล (Hi-Lo)
# ==========================================
class HiloView(discord.ui.View):
    def __init__(self, user, bet_amount):
        super().__init__(timeout=60.0)
        self.user = user
        self.bet = bet_amount
        print(f"\n[LOG] [HILO_INIT] 🟢 สร้างกระดานไฮโลให้ {user.display_name} เดิมพัน: {bet_amount} ทอง")

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.user.id:
            await interaction.response.send_message("❌ นี่ไม่ใช่กระดานไฮโลของคุณ!", ephemeral=True)
            return False
        return True

    async def on_timeout(self):
        print(f"[LOG] [HILO_TIMEOUT] ⏳ กระดานไฮโลของ {self.user.display_name} หมดเวลา!")
        for item in self.children:
            item.disabled = True
        try:
            await self.message.edit(content="⏳ กระดานไฮโลหมดเวลาแล้ว โปรดพิมพ์คำสั่งใหม่", view=self)
        except: pass

    async def play_hilo(self, interaction: discord.Interaction, choice: str):
        """ปุ่มไฮโล — ตรรกะอยู่ใน casino_core (ใช้ร่วมกับหน้าคาสิโนบนเว็บ)"""
        from bot import casino_core
        try:
            ok, out = casino_core.play_hilo(self.user.id, choice, self.bet)
            if not ok:
                return await interaction.response.send_message(out["message"], ephemeral=True)

            d1, d2, d3 = out["dice"]
            for item in self.children:
                item.disabled = True
            embed = discord.Embed(
                title="🎲 ผลการทอยไฮโล",
                color=discord.Color.gold() if out["winnings"] else discord.Color.red(),
                description=(f"🎲 ทอยได้ **[{d1}] [{d2}] [{d3}]** (รวม: {out['total']})"
                             f"\n\n{out['message']}"))
            await interaction.response.edit_message(embed=embed, view=self)
            self.stop()
        except Exception as e:
            print(f"[ERROR] [HILO_PLAY] ❌ เกิดข้อผิดพลาดตอนทอยไฮโล: {e}")
            await interaction.response.send_message("❌ เกิดข้อผิดพลาดของระบบคาสิโน!", ephemeral=True)

    @discord.ui.button(label="⬆️ สูง (12-18)", style=discord.ButtonStyle.primary)
    async def btn_high(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.play_hilo(interaction, "high")

    @discord.ui.button(label="⬇️ ต่ำ (3-10)", style=discord.ButtonStyle.primary)
    async def btn_low(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.play_hilo(interaction, "low")

    @discord.ui.button(label="🎯 11 ไฮโล (x7)", style=discord.ButtonStyle.success)
    async def btn_11hilo(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.play_hilo(interaction, "11hilo")


# ==========================================
# 🎰 ระบบหลักของคาสิโน (Cog)
# ==========================================
class Casino(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        print(f"[LOG] [SETUP] 🎰 โหลดโมดูล Casino เรียบร้อยแล้ว")

    async def cog_check(self, ctx):
        """P8: ฟีเจอร์นี้เล่นได้เฉพาะเซิร์ฟหลัก (เซิร์ฟรองเล่นได้แค่ผจญภัย)"""
        return await main_server_gate(ctx)

    @allowed_channel("casino_hilo") 
    @not_arrested() 
    @commands.command(name="hilo")
    async def hilo_game(self, ctx, bet: int):
        print(f"\n[LOG] [CMD_HILO] 💬 {ctx.author.display_name} พิมพ์คำสั่ง !hilo {bet}")
        try:
            if bet <= 0:
                print(f"[LOG] [CMD_HILO] ❌ ปฏิเสธ: เดิมพันติดลบหรือเท่ากับ 0")
                return await ctx.send("❌ เดิมพันต้องมากกว่า 0 ทอง!")
            
            player = player_model.get_player(ctx.author.id)
            current_cash = player.get("cash", 0) if player else 0
            
            if current_cash < bet:
                print(f"[LOG] [CMD_HILO] ❌ ปฏิเสธ: เงินไม่พอ (มี {current_cash} แต่จะเล่น {bet})")
                return await ctx.send("❌ เงินในกระเป๋าของคุณไม่พอ!")

            embed = discord.Embed(title="🎲 โต๊ะไฮโล VIP", description=f"**ผู้เล่น:** {ctx.author.mention}\n**เงินเดิมพัน:** `{bet}` ทอง\n\nโปรดเลือกแทง สูง, ต่ำ หรือ 11 ไฮโล!", color=discord.Color.blue())
            view = HiloView(ctx.author, bet)
            
            msg = await ctx.send(embed=embed, view=view)
            view.message = msg 
            print(f"[LOG] [CMD_HILO] ✅ โพสต์กระดานไฮโลสำเร็จ รอผู้เล่นกดปุ่ม...")
            
        except Exception as e:
            print(f"[ERROR] [CMD_HILO] คำสั่ง !hilo พัง: {e}")

    @allowed_channel("casino_slots") 
    @not_arrested() 
    @commands.command(name="slots")
    async def slots_game(self, ctx, bet: int):
        """หมุนสล็อต — ตรรกะอยู่ใน casino_core (ใช้ร่วมกับหน้าคาสิโนบนเว็บ)"""
        from bot import casino_core
        try:
            embed = discord.Embed(title="🎰 สล็อตแมชชีนกำลังหมุน...",
                                  description="[ 🌀 | 🌀 | 🌀 ]", color=discord.Color.gold())
            ok, out = casino_core.play_slots(ctx.author.id, bet)
            if not ok:
                return await ctx.send(out["message"])

            msg = await ctx.send(embed=embed)
            await asyncio.sleep(1.5)                 # ปล่อยให้ลุ้นก่อนเฉลย

            r1, r2, r3 = out["reels"]
            embed.title = "🎰 ผลการหมุนสล็อต"
            embed.description = f"[ {r1} | {r2} | {r3} ]\n\n{out['message']}"
            embed.color = discord.Color.green() if out["winnings"] else discord.Color.red()
            await msg.edit(embed=embed)

        except Exception as e:
            print(f"[ERROR] [SLOTS_CMD] ❌ เกิดข้อผิดพลาดในสล็อตแมชชีน: {e}")
            await ctx.send("❌ เกิดข้อผิดพลาดของระบบคาสิโน!")

async def setup(bot):
    try:
        await bot.add_cog(Casino(bot))
    except Exception as e:
        print(f"[ERROR] [SETUP_CASINO] โหลด Casino ล้มเหลว: {e}")