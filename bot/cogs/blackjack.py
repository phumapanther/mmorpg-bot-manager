#cogs/bj24 สำหรับผู้เล่น
import discord
from discord.ext import commands
import random
import json
from utils import not_arrested, allowed_channels,has_role_or_owner
from controller.trainer import train_alpha_bot
# นำเข้าระบบจัดการผู้เล่นของคุณอาเธอร์
import models.player_model as player_model

# นำเข้าระบบ AI ของคุณ
from controller.bot_brain import BlackjackBot
from controller import db_manager

# ==========================================
# 🃏 UI View สำหรับเกม Blackjack 24
# ==========================================
class BJ24View(discord.ui.View):
    def __init__(self, user, bet_amount, bot_brain):
        super().__init__(timeout=60.0)
        self.user = user
        self.bet = bet_amount
        self.brain = bot_brain # สมอง ML
        
        self.deck = self.create_deck()
        self.player_hand = [self.deck.pop(), self.deck.pop()]
        self.bot_hand = [self.deck.pop(), self.deck.pop()]
        print(f"[LOG] [BJ24_START] 🃏 เปิดโต๊ะแบล็คแจ็ค 24 ให้ {user.display_name} | เดิมพัน: {bet_amount} ทอง")
        
    def create_deck(self):
        ranks = ['A', '2', '3', '4', '5', '6', '7', '8', '9', '10', 'J', 'Q', 'K']
        values = {'A': 1, '2': 2, '3': 3, '4': 4, '5': 5, '6': 6, '7': 7, '8': 8, '9': 9, '10': 10, 'J': 10, 'Q': 10, 'K': 10}
        deck = [(r, values[r]) for r in ranks for _ in range(4)]
        random.shuffle(deck)
        return deck

    def get_score(self, hand):
        return sum(card[1] for card in hand)

    def generate_embed(self, game_over=False, result_text="", color=discord.Color.blue()):
        try:
            p_score = self.get_score(self.player_hand)
            p_cards = " ".join([f"[{c[0]}]" for c in self.player_hand])
            
            embed = discord.Embed(title="🃏 Blackjack 24 (ML Edition)", color=color)
            embed.add_field(name=f"👤 ไพ่ของคุณ ({p_score} แต้ม)", value=p_cards, inline=False)
            
            if not game_over:
                # ซ่อนไพ่ใบที่สองของบอทตอนยังไม่จบเกม
                b_cards = f"[{self.bot_hand[0][0]}] [❓]"
                embed.add_field(name="🤖 ไพ่ของบอท", value=b_cards, inline=False)
                embed.description = f"เงินเดิมพัน: `{self.bet}` ทอง\nเลือกการกระทำของคุณด้านล่าง!"
            else:
                b_score = self.get_score(self.bot_hand)
                b_cards = " ".join([f"[{c[0]}]" for c in self.bot_hand])
                embed.add_field(name=f"🤖 ไพ่ของบอท ({b_score} แต้ม)", value=b_cards, inline=False)
                embed.description = f"**สรุปผล:**\n{result_text}"
                
            return embed
        except Exception as e:
            print(f"[ERROR] [BJ24_EMBED] เกิดข้อผิดพลาดตอนสร้างหน้าจอ Embed: {e}")
            return discord.Embed(title="❌ เกิดข้อผิดพลาดในการแสดงผลไพ่", color=discord.Color.red())

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.user.id:
            print(f"[LOG] [BJ24_INTERCEPT] ⚠️ {interaction.user.display_name} พยายามกดปุ่มโต๊ะไพ่ของคนอื่น")
            await interaction.response.send_message("❌ นี่ไม่ใช่โต๊ะไพ่ของคุณ!", ephemeral=True)
            return False
        return True

    async def on_timeout(self):
        print(f"[LOG] [BJ24_TIMEOUT] ⏳ โต๊ะของ {self.user.display_name} หมดเวลาตัดสินใจ (พับกระดาน)")
        for item in self.children:
            item.disabled = True
        try:
            await self.message.edit(content="⏳ หมดเวลาการตัดสินใจ โต๊ะถูกพับแล้ว! (เสียเงินเดิมพัน)", view=self)
        except Exception as e:
            print(f"[ERROR] [BJ24_TIMEOUT] แก้ไขข้อความตอนหมดเวลาไม่ได้: {e}")

    # --- ปุ่ม Hit (จั่วไพ่) ---
    # --- ปุ่ม Hit (จั่วไพ่) ---
    @discord.ui.button(label="👇 Hit (จั่ว)", style=discord.ButtonStyle.primary, custom_id="bj_hit")
    async def hit(self, interaction: discord.Interaction, button: discord.ui.Button):
        try:
            drawn_card = self.deck.pop()
            self.player_hand.append(drawn_card)
            p_score = self.get_score(self.player_hand)
            print(f"[LOG] [BJ24_HIT] {self.user.display_name} จั่วไพ่ได้ [{drawn_card[0]}] | แต้มรวมตอนนี้: {p_score}")
            
            if p_score > 24:
                reward = 1
                
                # --- แก้ไขตรงนี้: สร้าง state ก่อนเรียก learn ---
                state = f"{self.get_score(self.bot_hand)}-{self.player_hand[0][1]}"
                
                # เรียก learn ด้วย 3 arguments (state, action, reward)
                self.brain.learn(state, "!c", reward)
                # ---------------------------------------------
                
                self.save_bot_memory()
                
                result_text = f"💥 **เกิน 24! (Bust)** คุณแพ้และเสียเงินเดิมพัน `{self.bet}` ทอง!"
                embed = self.generate_embed(game_over=True, result_text=result_text, color=discord.Color.red())
                
                for item in self.children: item.disabled = True
                await interaction.response.edit_message(embed=embed, view=self)
                self.stop()
            else:
                embed = self.generate_embed()
                await interaction.response.edit_message(embed=embed, view=self)
                
        except Exception as e:
            print(f"[ERROR] [BJ24_HIT] บัคขณะผู้เล่นกดจั่วไพ่: {e}")
            await interaction.response.send_message("❌ เกิดข้อผิดพลาดของระบบไพ่!", ephemeral=True)
    # --- ปุ่ม Stand (พอ) และ ตาของบอท ---
    @discord.ui.button(label="✋ Stand (พอ)", style=discord.ButtonStyle.success, custom_id="bj_stand")
    async def stand(self, interaction: discord.Interaction, button: discord.ui.Button):
        try:
            p_score = self.get_score(self.player_hand)
            print(f"[LOG] [BJ24_STAND] ✋ {self.user.display_name} สั่งหยุดที่แต้ม {p_score} | เริ่มต้นตาของ AI บอท...")
            
            bot_history = []
            bot_log = ""
            
            # 🤖 ตาของบอททำงานด้วย Machine Learning
            while True:
                b_score = self.get_score(self.bot_hand)
                if b_score > 24:
                    print(f"[LOG] [BJ24_BOT_BUST] 🤖 แต้มบอทเกิน 24 ({b_score}) บอทพัง!")
                    break
                    
                action = self.brain.get_action(b_score, self.player_hand[0][1])
                bot_history.append((b_score, action))
                
                if action == "!hit":
                    drawn_card = self.deck.pop()
                    self.bot_hand.append(drawn_card)
                    bot_log += f"🤖 บอทตัดสินใจจั่วได้ไพ่ [{drawn_card[0]}]\n"
                    print(f"[LOG] [BJ24_BOT_THINK] 🤖 สมองกลสั่ง: จั่วไพ่เพิ่ม (!hit) -> ได้ {drawn_card[0]}")
                else:
                    bot_log += "🤖 บอทตัดสินใจพอแค่นี้!\n"
                    print(f"[LOG] [BJ24_BOT_THINK] 🤖 สมองกลสั่ง: หยุดไพ่ (!c) ที่แต้ม {b_score}")
                    break

            b_score = self.get_score(self.bot_hand)
            winnings = 0
            reward = 0
            
            # คำนวณผู้ชนะและตั้งค่า Reward ให้สมองกล
            if b_score > 24 or (p_score <= 24 and p_score > b_score):
                reward = -1 # บอทแพ้ (โดนลงโทษ -1)
                winnings = self.bet * 2
                result_text = f"🏆 **คุณชนะ!** รับเงินรางวัล `{winnings}` ทอง\n{bot_log}"
                color = discord.Color.green()
                player_model.increment_player_field(self.user.id, "cash", winnings)
                print(f"[LOG] [BJ24_RESULT] 🏆 ผู้เล่นชนะ! (บอทโดนสอน Reward: -1)")
                
            elif p_score < b_score:
                reward = 1 # บอทชนะ (ได้รางวัล +1)
                result_text = f"❌ **บอทชนะ!** บอทแต้มสูงกว่า คุณเสียเงินเดิมพัน\n{bot_log}"
                color = discord.Color.red()
                print(f"[LOG] [BJ24_RESULT] ❌ บอทชนะ! (บอทเรียนรู้ความสำเร็จ Reward: +1)")
                
            else:
                reward = 0.1 # เสมอ (ให้รางวัลปลอบใจ 0.1)
                winnings = self.bet
                result_text = f"🤝 **เสมอ!** คืนเงินทุน `{winnings}` ทอง\n{bot_log}"
                color = discord.Color.gold()
                player_model.increment_player_field(self.user.id, "cash", winnings)
                print(f"[LOG] [BJ24_RESULT] 🤝 เสมอ (บอทเรียนรู้แบบกลางๆ Reward: +0.1)")

            # 🧠 สอนบอทตาม History ในตานี้
            print(f"[LOG] [BJ24_LEARNING] 🧠 เริ่มกระบวนการอัปเดต Q-Table ของ AlphaBot...")
            # ดึงไพ่ใบแรกของเจ้ามือมาเป็นตัวอ้างอิง
            dealer_upcard = self.bot_hand[0][1] 
            
            for score, act in bot_history:
                # รวม score และ dealer_upcard เป็น String (State)
                state = f"{score}-{dealer_upcard}"
                # ส่งค่าเข้าไป 3 ค่า (self ไม่นับ) ตามฟังก์ชัน learn ตัวใหม่
                self.brain.learn(state, act, reward)
            
            self.save_bot_memory()

            embed = self.generate_embed(game_over=True, result_text=result_text, color=color)
            for item in self.children: item.disabled = True
            await interaction.response.edit_message(embed=embed, view=self)
            self.stop()
            
        except Exception as e:
            print(f"[ERROR] [BJ24_STAND] เกิดข้อผิดพลาดขณะจบเกมและสอนบอท: {e}")
            await interaction.response.send_message("❌ เกิดข้อผิดพลาดในการประมวลผลของ AI!", ephemeral=True)

    def save_bot_memory(self):
        try:
            memory_to_save = json.dumps(self.brain.q_table)
            db_manager.save_bot_memory(memory_to_save, 'AlphaBot')
            print(f"[LOG] [ML_TRAIN] ✅ อัปเดตและบันทึกความจำ AlphaBot ลง Database เสร็จสิ้น")
        except Exception as e:
            print(f"[ERROR] [ML_TRAIN] ⚠️ ไม่สามารถบันทึกความจำบอทได้: {e}")


# ==========================================
# 🎰 ระบบหลัก (Cog)
# ==========================================
class BJ24Game(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.bot_brain = BlackjackBot()

    # --- คำสั่งเล่นเกม ---
    @allowed_channels(["🃏blackjack🃏"])
    @not_arrested()
    @commands.command(name="bj")
    async def play_bj(self, ctx, bet: int):
        try:
            print(f"[LOG] [BJ_COMMAND] {ctx.author.name} เริ่มเกมด้วยเงิน {bet}")

            # 1. ตรวจสอบสมองบอท
            if not self.bot_brain:
                return await ctx.send("❌ ระบบสมองกล (ML) ออฟไลน์ โปรดแจ้งแอดมิน!")

            # 2. ตรวจสอบเงินเดิมพัน
            if bet <= 0:
                return await ctx.send("❌ เดิมพันต้องมากกว่า 0 ทอง!")
            
            player = player_model.get_player(ctx.author.id)
            if not player or player.get("cash", 0) < bet:
                return await ctx.send("❌ เงินในกระเป๋าของคุณไม่พอ!")

            # 3. หักเงินและเริ่มเกม
            player_model.increment_player_field(ctx.author.id, "cash", -bet)
            
            # เริ่มเกม
            view = BJ24View(ctx.author, bet, self.bot_brain)
            embed = view.generate_embed()
            
            msg = await ctx.send(embed=embed, view=view)
            view.message = msg # จำเป็นสำหรับ on_timeout
            
        except Exception as e:
            print(f"[ERROR] [BJ_COMMAND] {e}")
            await ctx.send("❌ เกิดข้อผิดพลาดในการเริ่มเกม!")

    # --- คำสั่งเทรนบอท (Admin Only) ---
    @has_role_or_owner("คนบ้า")
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
    await bot.add_cog(BJ24Game(bot))