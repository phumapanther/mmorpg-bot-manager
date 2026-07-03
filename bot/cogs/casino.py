import discord
from discord.ext import commands
import random
import asyncio

import models.player_model as player_model
from utils import not_arrested, allowed_channels

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
        print(f"\n[LOG] [HILO_PLAY] 👆 {self.user.display_name} กดปุ่มเลือกแทง: {choice}")
        try:
            # 🔍 1. เช็คยอดเงินผู้เล่นก่อนเริ่มทอยเต๋า
            player = player_model.get_player(self.user.id)
            current_cash = player.get("cash", 0) if player else 0
            print(f"[LOG] [HILO_CHECK] ยอดเงินปัจจุบัน: {current_cash} ทอง | ต้องการใช้: {self.bet} ทอง")

            if current_cash < self.bet:
                print(f"[LOG] [HILO_FAIL] ❌ {self.user.display_name} เงินไม่พอตอนกดปุ่ม (อาจจะเอาไปเล่นอย่างอื่นหมดแล้ว)")
                return await interaction.response.send_message("❌ เงินคุณไม่พอแล้ว!", ephemeral=True)

            # 💸 2. หักเงินเดิมพันทันที
            player_model.increment_player_field(self.user.id, "cash", -self.bet)
            print(f"[LOG] [HILO_PAY] 💸 หักเงินสำเร็จ! เหลือ {current_cash - self.bet} ทอง")
            
            # ----------------------------------------------------
            # 😈 ระบบเจ้ามือตุกติก: ยิ่งเดิมพันสูง โอกาสแพ้บังคับยิ่งเยอะ
            # ----------------------------------------------------
            rig_chance = min(0.85, (self.bet / 10000.0) * 0.15)
            is_rigged = random.random() < rig_chance
            
            d1, d2, d3 = random.randint(1, 6), random.randint(1, 6), random.randint(1, 6)
            total = d1 + d2 + d3
            actual_result = "11hilo" if total == 11 else ("low" if total <= 10 else "high")

            if is_rigged and choice == actual_result:
                print(f"[LOG] [HILO_RIG] 😈 ระบบตุกติกทำงาน! บอทกำลังล็อคผลไม่ให้ {self.user.display_name} ชนะ...")
                attempts = 0
                while choice == actual_result and attempts < 10:
                    d1, d2, d3 = random.randint(1, 6), random.randint(1, 6), random.randint(1, 6)
                    total = d1 + d2 + d3
                    actual_result = "11hilo" if total == 11 else ("low" if total <= 10 else "high")
                    attempts += 1
            
            winnings = 0
            log_msg = f"🎲 ทอยได้ **[{d1}] [{d2}] [{d3}]** (รวม: {total})"
            
            # 🏆 3. เช็คผลแพ้ชนะและมอบรางวัล
            if choice == actual_result:
                if choice == "11hilo":
                    winnings = self.bet * 7 
                    result_text = f"🎉 **แจ็คพอตแตก!! 11 ไฮโล!!** ได้รับ `{winnings}` ทอง!"
                else:
                    winnings = self.bet * 2 
                    result_text = f"✅ **คุณชนะ!** แทงถูกรับไป `{winnings}` ทอง!"
                    
                player_model.increment_player_field(self.user.id, "cash", winnings)
                print(f"[LOG] [HILO_WIN] 🏆 {self.user.display_name} ชนะไฮโล! รับเงินเพิ่ม {winnings} ทอง")
            else:
                result_text = f"❌ **คุณแพ้!** เสีย `{self.bet}` ทอง"
                print(f"[LOG] [HILO_LOSE] 💀 {self.user.display_name} แพ้ไฮโล (ทาย {choice} แต่หน้าเต๋าออก {actual_result})")

            for item in self.children:
                item.disabled = True
            
            embed = discord.Embed(title="🎲 ผลการทอยไฮโล", color=discord.Color.gold() if winnings > 0 else discord.Color.red())
            embed.description = f"{log_msg}\n\n{result_text}"
            await interaction.response.edit_message(embed=embed, view=self)
            self.stop()

            # 💰 4. เช็คยอดเงินสรุปจบเกม
            updated_player = player_model.get_player(self.user.id)
            final_cash = updated_player.get("cash", 0) if updated_player else 0
            print(f"[LOG] [HILO_END] 🛑 จบเทิร์นไฮโล! ยอดเงินคงเหลือของ {self.user.display_name} คือ: {final_cash} ทอง\n")

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

    @allowed_channels(["🎲-hilo-🎲"]) 
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

    @allowed_channels(["🎰-slots-🎰"]) 
    @not_arrested() 
    @commands.command(name="slots")
    async def slots_game(self, ctx, bet: int):
        print(f"\n[LOG] [CMD_SLOTS] 🎰 {ctx.author.display_name} พิมพ์คำสั่ง !slots {bet}")
        try:
            if bet <= 0:
                print(f"[LOG] [CMD_SLOTS] ❌ ปฏิเสธ: เดิมพันติดลบหรือเท่ากับ 0")
                return await ctx.send("❌ เดิมพันต้องมากกว่า 0 ทอง!")
            
            # 🔍 1. เช็คยอดเงินก่อนหมุนสล็อต
            player = player_model.get_player(ctx.author.id)
            current_cash = player.get("cash", 0) if player else 0
            print(f"[LOG] [SLOTS_CHECK] ยอดเงินปัจจุบัน: {current_cash} ทอง | ต้องการใช้: {bet} ทอง")

            if current_cash < bet:
                print(f"[LOG] [CMD_SLOTS] ❌ ปฏิเสธ: เงินไม่พอ (มี {current_cash} ทอง)")
                return await ctx.send("❌ เงินในกระเป๋าของคุณไม่พอ!")

            # 💸 2. หักเงินค่าหมุนสล็อตทันที
            player_model.increment_player_field(ctx.author.id, "cash", -bet)
            print(f"[LOG] [SLOTS_PAY] 💸 หักเงินค่าหมุนสล็อตสำเร็จ! เหลือ {current_cash - bet} ทอง")

            embed = discord.Embed(title="🎰 สล็อตแมชชีนกำลังหมุน...", description="[ 🌀 | 🌀 | 🌀 ]", color=discord.Color.gold())
            msg = await ctx.send(embed=embed)

            await asyncio.sleep(1.5)

            # ----------------------------------------------------
            rig_chance = min(0.90, (bet / 10000.0) * 0.15)
            is_rigged = random.random() < rig_chance

            emojis = ["🍒", "🍇", "🍊", "💎", "🔔", "💰"]
            weights = [30, 25, 20, 10, 10, 5]

            def check_win(s1, s2, s3):
                return s1 == s2 or s2 == s3 or s1 == s3

            r1 = random.choices(emojis, weights=weights)[0]
            r2 = random.choices(emojis, weights=weights)[0]
            r3 = random.choices(emojis, weights=weights)[0]

            if is_rigged and check_win(r1, r2, r3):
                print(f"[LOG] [SLOTS_RIG] 😈 ระบบตุกติกทำงาน! บอทกำลังล็อคผลสล็อตไม่ให้ตรงกัน...")
                attempts = 0
                while check_win(r1, r2, r3) and attempts < 10:
                    r1 = random.choices(emojis, weights=weights)[0]
                    r2 = random.choices(emojis, weights=weights)[0]
                    r3 = random.choices(emojis, weights=weights)[0]
                    attempts += 1

            result_string = f"[ {r1} | {r2} | {r3} ]"
            winnings = 0
            win_text = ""

            # 🏆 3. เช็คผลแพ้ชนะสล็อต
            if r1 == r2 == r3:
                if r1 == "💰": multiplier = 15
                elif r1 == "💎": multiplier = 10
                elif r1 == "🔔": multiplier = 7
                else: multiplier = 5
                
                winnings = bet * multiplier
                win_text = f"🎉 **แจ็คพอต!!** ได้สัญลักษณ์ตรงกัน 3 ตัว!\nรับรางวัล `{winnings}` ทอง (x{multiplier})"
            
            elif r1 == r2 or r2 == r3 or r1 == r3:
                multiplier = 1.5
                winnings = int(bet * multiplier)
                win_text = f"✨ **เกือบแจ็คพอต!** ได้สัญลักษณ์ตรงกัน 2 ตัว!\nรับรางวัล `{winnings}` ทอง (x{multiplier})"
            
            else:
                win_text = f"❌ **เสียใจด้วย!** คุณเสีย `{bet}` ทอง"

            if winnings > 0:
                player_model.increment_player_field(ctx.author.id, "cash", winnings)
                print(f"[LOG] [SLOTS_WIN] 🏆 {ctx.author.display_name} ชนะสล็อต! รับเงินเพิ่ม {winnings} ทอง")
            else:
                print(f"[LOG] [SLOTS_LOSE] 💀 {ctx.author.display_name} แพ้สล็อต")

            embed.title = "🎰 ผลการหมุนสล็อต"
            embed.description = f"{result_string}\n\n{win_text}"
            embed.color = discord.Color.green() if winnings > 0 else discord.Color.red()
            
            await msg.edit(embed=embed)

            # 💰 4. เช็คยอดเงินสรุปจบเกม
            updated_player = player_model.get_player(ctx.author.id)
            final_cash = updated_player.get("cash", 0) if updated_player else 0
            print(f"[LOG] [SLOTS_END] 🛑 จบเทิร์นสล็อต! ยอดเงินคงเหลือของ {ctx.author.display_name} คือ: {final_cash} ทอง\n")

        except Exception as e:
            print(f"[ERROR] [SLOTS_CMD] ❌ เกิดข้อผิดพลาดในสล็อตแมชชีน: {e}")
            await ctx.send("❌ เกิดข้อผิดพลาดของระบบคาสิโน!")

async def setup(bot):
    try:
        await bot.add_cog(Casino(bot))
    except Exception as e:
        print(f"[ERROR] [SETUP_CASINO] โหลด Casino ล้มเหลว: {e}")