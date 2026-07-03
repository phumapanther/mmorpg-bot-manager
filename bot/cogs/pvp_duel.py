import discord
from discord.ext import commands
import models.player_model as player_model
import random
import asyncio
from utils import not_arrested, allowed_channels
from views.profile_embed import ARMOR_STATS ,WEAPON_STATS

class DuelView(discord.ui.View):
    def __init__(self, challenger, target, timeout=60):
        super().__init__(timeout=timeout)
        self.challenger = challenger
        self.target = target

    @discord.ui.button(label="ยอมรับการท้าดวล", style=discord.ButtonStyle.green)
    async def accept(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.target.id:
            return await interaction.response.send_message("ไม่ใช่คำท้าของคุณ!", ephemeral=True)
        
        await interaction.response.send_message(f"⚔️ {self.target.mention} ยอมรับคำท้า! การต่อสู้เริ่มขึ้นแล้ว!")
        await self.start_duel(interaction)

    @discord.ui.button(label="ปฏิเสธ", style=discord.ButtonStyle.red)
    async def reject(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.target.id:
            return await interaction.response.send_message("ไม่ใช่คำท้าของคุณ!", ephemeral=True)
        await interaction.response.send_message(f"{self.target.mention} ปฏิเสธคำท้า...")
        self.stop()

    async def start_duel(self, interaction):
        # 🛡️ ข้อมูลอุปกรณ์ (นำมาอ้างอิงในฟังก์ชัน)

        # ดึงข้อมูลจากฐานข้อมูล
        p1 = player_model.get_player(self.challenger.id)
        p2 = player_model.get_player(self.target.id)

        # เช็กเงินเดิมพัน (ต้องมีคนละอย่างน้อย 2000)
        if p1.get("cash", 0) < 2000 or p2.get("cash", 0) < 2000:
            return await interaction.channel.send("❌ การดวลถูกยกเลิก! ผู้เล่นทั้งสองฝ่ายต้องมีเงินอย่างน้อย 2,000 ทองสำหรับเดิมพัน")

        # ==========================================
        # 1. ฟังก์ชันช่วยคำนวณสเตตัสรวม (Base Stats + อุปกรณ์)
        # ==========================================
        def get_combat_stats(p_data, user_obj):
            # ดึงชื่อคีย์อุปกรณ์ที่ใส่ (ถ้าไม่มีให้เป็นของเริ่มต้น)
            armor_key = p_data.get("armor", "None")
            weapon_key = p_data.get("weapon", "Wooden_Weapon")
            
            armor = ARMOR_STATS.get(armor_key, ARMOR_STATS["None"])
            weapon = WEAPON_STATS.get(weapon_key, {"name": "✊ มือเปล่า", "atk": 5})

            level = p_data.get("level", 1)
            base_max_hp = p_data.get("max_hp", 100) # ใช้ max_hp แทน hp เดิม
            base_atk = p_data.get("attack", 5)

            return {
                "user": user_obj,
                "name": user_obj.name,
                "level": level,
                "hp": base_max_hp + armor["hp"],    # เลือดจำลอง = MaxHP ฐาน + โบนัสเกราะ
                "max_hp": base_max_hp + armor["hp"],
                "atk": base_atk + weapon["atk"],    # พลังโจมตี = โจมตีฐาน + โบนัสอาวุธ
                "eva": armor["eva"],                # ค่าความพริ้วหลบหลีก
                "gear_text": f"[{weapon['name']} / {armor['name']}]"
            }

        # เสกตัวละครลงสนาม
        c1 = get_combat_stats(p1, self.challenger)
        c2 = get_combat_stats(p2, self.target)

        log = f"⚔️ **การประลองเริ่มต้นขึ้น! (จำลองการต่อสู้ ไม่ถึงกับตายหรอกนะ!)**\n"
        log += f"🔴 **{c1['name']}** (Lv.{c1['level']}) {c1['gear_text']} | HP: {c1['hp']} | ATK: {c1['atk']}\n"
        log += f"🔵 **{c2['name']}** (Lv.{c2['level']}) {c2['gear_text']} | HP: {c2['hp']} | ATK: {c2['atk']}\n"
        log += "--------------------------------------\n"

        # ==========================================
        # 2. ลูปการประลอง (เพิ่มเป็นสู้ 5 รอบ เพื่อให้สมกับเลือดที่เยอะขึ้น)
        # ==========================================
        max_rounds = 5
        for turn in range(1, max_rounds + 1):
            log += f"**[รอบที่ {turn}]**\n"
            
            # ---------------------------
            # 🔴 ผู้ท้าชิง โจมตี เป้าหมาย
            # ---------------------------
            lvl_diff_1 = c1['level'] - c2['level']
            # โบนัสเลเวล: เลเวลห่าง 1 เลเวล = ดาเมจแรงขึ้น 5%, ทะลวงหลบหลีกศัตรู 3%
            dmg_multiplier_1 = 1.0 + (max(0, lvl_diff_1) * 0.05)
            c2_eva = max(5, c2['eva'] - (max(0, lvl_diff_1) * 3)) # หลบหลีกศัตรูขั้นต่ำเหลือ 5%

            # คำนวณหลบหลีก (ปรับค่า eva ให้สมดุลหาร 2 เช่น เสื้อผ้าธรรมดา eva 85 จะมีโอกาสหลบจริง 42.5%)
            if random.randint(1, 100) <= (c2_eva * 0.5):
                log += f"💨 {c1['name']} ฟันพลาด! {c2['name']} พริ้วหลบได้อย่างสวยงาม\n"
            else:
                base_dmg_1 = random.randint(int(c1['atk'] * 0.7), c1['atk']) # ดาเมจสวิงที่ 70-100%
                final_dmg_1 = int(base_dmg_1 * dmg_multiplier_1)
                c2['hp'] -= final_dmg_1
                log += f"💥 {c1['name']} โจมตีเข้าเป้า! สร้างความเสียหาย {final_dmg_1} หน่วย (HP {c2['name']}: {max(0, c2['hp'])})\n"

            if c2['hp'] <= 0: break

            # ---------------------------
            # 🔵 เป้าหมาย โจมตีสวนกลับ ผู้ท้าชิง
            # ---------------------------
            lvl_diff_2 = c2['level'] - c1['level']
            dmg_multiplier_2 = 1.0 + (max(0, lvl_diff_2) * 0.05)
            c1_eva = max(5, c1['eva'] - (max(0, lvl_diff_2) * 3))

            if random.randint(1, 100) <= (c1_eva * 0.5):
                log += f"💨 {c2['name']} สวนกลับพลาด! {c1['name']} กลิ้งหลบได้ทัน\n"
            else:
                base_dmg_2 = random.randint(int(c2['atk'] * 0.7), c2['atk'])
                final_dmg_2 = int(base_dmg_2 * dmg_multiplier_2)
                c1['hp'] -= final_dmg_2
                log += f"💢 {c2['name']} สวนกลับเน้นๆ! สร้างความเสียหาย {final_dmg_2} หน่วย (HP {c1['name']}: {max(0, c1['hp'])})\n"

            if c1['hp'] <= 0: break

        log += "--------------------------------------\n"

        # ==========================================
        # 3. สรุปผล
        # ==========================================
        if c1['hp'] > c2['hp']:
            winner, loser = c1, c2
        elif c2['hp'] > c1['hp']:
            winner, loser = c2, c1
        else:
            return await interaction.channel.send(log + "\n🤝 **การประลองจบลงด้วยผลเสมอ!** (เลือดเหลือเท่ากัน) ไม่มีใครเสียเงินเดิมพัน")

        # 4. หักเงินและโอนเงิน
        player_model.increment_player_field(loser['user'].id, "cash", -2000)
        player_model.increment_player_field(winner['user'].id, "cash", 2000)

        log += f"🏆 **ผู้ชนะคือ: {winner['name']}!** (เหลือ HP {max(0, winner['hp'])})\n"
        log += f"💸 {loser['name']} จ่ายค่าเดิมพัน 2,000 ทองให้ {winner['name']} แล้ว!"
        
        await interaction.channel.send(log)

class PvpDuel(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @allowed_channels(["⚒-แชทลานประลอง-⚒"])
    @not_arrested() # 🛠️ บล็อกคนติดคุก
    @commands.command(name="challenge")
    async def challenge(self, ctx, member: discord.Member):
        if member.id == ctx.author.id:
            return await ctx.send("❌ ท้าดวลตัวเองเนี่ยนะ?")
        
        # เช็กข้อมูลตัวละครก่อน
        attacker = player_model.get_player(ctx.author.id)
        defender = player_model.get_player(member.id)
        
        if not attacker or not defender:
            return await ctx.send("❌ ข้อมูลตัวละครไม่ครบ!")

        await ctx.send(f"🥊 {ctx.author.mention} ท้าดวลกับ {member.mention}! คุณจะยอมรับไหม?", 
                       view=DuelView(ctx.author, member))

async def setup(bot):
    await bot.add_cog(PvpDuel(bot))