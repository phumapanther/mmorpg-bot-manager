import discord
from discord.ext import commands
import random
import time
from collections import defaultdict
from utils import has_role_or_owner

import models.player_model as player_model
from views.game_views import SKILL_CONFIG

class BossView(discord.ui.View):
    def __init__(self, boss_data):
        super().__init__(timeout=None)
        self.boss = boss_data
        self.contributors = defaultdict(int)
        self.cooldowns = {}
        print(f"[LOG] [INIT] BossView เริ่มทำงานสแตนด์บายสำหรับบอส: {boss_data.get('name')}")

    # ฟังก์ชันสุ่มและดึงข้อมูลสกิล พร้อมระบบ Log ทุกเงื่อนไข
    def get_random_skill(self, class_name):
        try:
            if class_name not in SKILL_CONFIG:
                print(f"[LOG] [SKILL] ไม่พบค่าคอนฟิกสำหรับคลาส: {class_name} (ข้ามระบบสกิล)")
                return None, None
            
            skills = list(SKILL_CONFIG[class_name].keys())
            chosen_skill = random.choice(skills)
            config = SKILL_CONFIG[class_name][chosen_skill]
            
            roll = random.randint(1, 100)
            chance = config.get("chance", 0)
            
            if roll <= chance:
                print(f"[LOG] [SKILL] คลาส {class_name} ทอยเต๋าสกิลได้ {roll}/{chance} -> [สุ่มติดสกิล: {chosen_skill}]")
                return chosen_skill, config
            else:
                print(f"[LOG] [SKILL] คลาส {class_name} ทอยเต๋าสกิลได้ {roll}/{chance} -> [สกิลวืด/ไม่ติด: {chosen_skill}]")
                return chosen_skill, None 
        except Exception as e:
            print(f"[ERROR] [get_random_skill] เกิดข้อผิดพลาด: {e}")
            return None, None

    @discord.ui.button(label="⚔️ โจมตีบอส!", style=discord.ButtonStyle.danger, custom_id="boss_attack_button")
    async def attack(self, interaction: discord.Interaction, button: discord.ui.Button):
        try:
            user = interaction.user
            user_id = user.id
            print(f"\n[LOG] [ATTACK_TRIGGER] ผู้เล่น {user.display_name} ({user_id}) กดปุ่มโจมตีบอส")
            
            # ⏱️ 1. เช็กคูลดาวน์ (ตีได้ 1 ครั้ง ทุกๆ 3 วินาที)
            if user_id in self.cooldowns:
                time_passed = time.time() - self.cooldowns[user_id]
                if time_passed < 3.0:
                    print(f"[LOG] [COOLDOWN_REJECT] {user.display_name} กดเร็วเกินไป (เพิ่งผ่านไป {time_passed:.2f} วินาที) -> บล็อกการทำงาน")
                    return await interaction.response.send_message("⏳ ใจเย็นๆ ผู้กล้า! อาวุธคุณยังไม่พร้อม (คูลดาวน์ 3 วินาที)", ephemeral=True)
            
            # อัปเดตเวลาล่าสุดที่กดตีหลังจากผ่านคูลดาวน์
            self.cooldowns[user_id] = time.time()
            print(f"[LOG] [COOLDOWN_PASS] {user.display_name} ผ่านการตรวจสอบคูลดาวน์")

            # 2. หาวิชคลาสของผู้เล่นจากบทบาท (Roles)
            user_roles = [r.name for r in user.roles]
            player_class = "None"
            for c in ["Warrior", "Mage", "Rogue", "Cleric"]:
                if c in user_roles:
                    player_class = c
                    break
            print(f"[LOG] [CLASS_CHECK] ตรวจพบการทำงานคลาสของ {user.display_name} -> [{player_class}]")

            # 3. ทอยเต๋าพื้นฐาน
            base_dmg = sum(random.randint(1, self.boss['dice_sides']) for _ in range(self.boss['dice_count']))
            final_dmg = max(1, base_dmg)
            
            combat_log = f"🎲 คุณทอยได้ **{base_dmg}** ดาเมจพื้นฐาน!\n"

            # 4. สุ่มและคำนวณสกิล
            skill_used, skill_data = self.get_random_skill(player_class)

            if skill_used:
                if not skill_data:
                    combat_log += f"💨 คุณพยายามร่าย **{skill_used}** แต่พลาดกระบวนท่า!\n"
                    print(f"[LOG] [COMBAT_EFFECT] {user.display_name} ใช้สกิล [{skill_used}] แต่ผลลัพธ์คือ วืด/พลาด")
                else:
                    print(f"[LOG] [COMBAT_EFFECT] {user.display_name} เปิดใช้งานสกิล [{skill_used}] สำเร็จ กำลังคำนวณบัฟ...")
                    if skill_used == "heavy_strike":
                        final_dmg = int(final_dmg * skill_data["damage_multiplier"])
                        combat_log += f"✨ **Heavy Strike สำเร็จ!** ดาเมจทวีคูณเป็น **{final_dmg}** หน่วย!\n"
                    elif skill_used == "backstab":
                        final_dmg = int(final_dmg * skill_data["damage_multiplier"])
                        combat_log += f"🗡️ **Backstab สำเร็จ!** แอบแทงข้างหลัง ดาเมจคริติคอล **{final_dmg}** หน่วย!\n"
                    elif skill_used == "fireball":
                        final_dmg += skill_data["burn_damage"]
                        combat_log += f"🔥 **Fireball เข้าเป้า!** เผาไหม้บอสเพิ่มอีก {skill_data['burn_damage']} ดาเมจ! รวมเป็น **{final_dmg}**\n"
                    elif skill_used == "heal":
                        heal_amt = skill_data["heal_amount"]
                        combat_log += f"✨ **Heal ทำงาน!** คุณฟื้นฟูเลือดตัวเอง **+{heal_amt} HP** และตีบอสไป **{final_dmg}** ดาเมจ!\n"
                    elif skill_used in ["shield_bash", "frostbolt", "holy_aura", "evasion"]:
                        combat_log += f"🛡️ ร่ายสกิล **{skill_used}** ป้องกันการโจมตีสวนกลับของบอสในตาต่อไป!\n"
            else:
                combat_log += "⚔️ คุณพุ่งเข้าโจมตีด้วยท่าทางปกติ\n"
                print(f"[LOG] [COMBAT_EFFECT] {user.display_name} ไม่เข้าเงื่อนไขสกิล โจมตีแบบธรรมดาด้วยดาเมจพื้นฐาน")

            # 5. หักเลือดบอสและบันทึกผล
            self.boss['hp'] -= final_dmg
            self.contributors[user_id] += final_dmg
            print(f"[LOG] [DAMAGE_DEALT] {user.display_name} ทำดาเมจสุทธิ: {final_dmg} | HP บอสปัจจุบันเหลือ: {self.boss['hp']}/{self.boss['max_hp']}")
            
            # 6. อัปเดตบอร์ดหลักและการเช็กเงื่อนไขการตาย
            if self.boss['hp'] <= 0:
                self.boss['hp'] = 0
                button.disabled = True
                print(f"[LOG] [BOSS_DEATH] บอส {self.boss['name']} พ่ายแพ้แล้ว! กำลังเปลี่ยนสถานะ Embed และแจกของรางวัล...")
                
                embed = self.get_boss_embed()
                embed.title = f"💀 บอส {self.boss['name']} ถูกกำจัดแล้ว!"
                embed.description = "รางวัลถูกแจกจ่ายตามสัดส่วนความเสียหาย!"
                await interaction.response.edit_message(embed=embed, view=self)
                
                await interaction.followup.send(f"{combat_log}🎯 คุณทำดาเมจรวมปิดท้าย **{final_dmg}** หน่วย!", ephemeral=True)
                await self.distribute_rewards(interaction)
                self.stop()
            else:
                print(f"[LOG] [BOSS_SURVIVE] บอสยังไม่ตาย กำลังส่งข้อความ Ephemeral อัปเดตดาเมจผู้เล่นรายบุคคล")
                embed = self.get_boss_embed()
                await interaction.response.edit_message(embed=embed, view=self)
                await interaction.followup.send(combat_log + f"💥 คุณทำดาเมจรวมได้ **{final_dmg}** หน่วย!", ephemeral=True)

        except Exception as e:
            print(f"[ERROR] [attack_button] เกิดข้อผิดพลาดรุนแรงในระบบปุ่มกดโจมตี: {e}")
            await interaction.response.send_message("❌ เกิดข้อผิดพลาดภายในระบบในการคำนวณการโจมตีบอส!", ephemeral=True)

    def get_boss_embed(self):
        try:
            hp_percent = max(0, (self.boss['hp'] / self.boss['max_hp']) * 100)
            embed = discord.Embed(title=f"👹 บอส: {self.boss['name']}", color=0xFF0000)
            embed.add_field(name="HP", value=f"{self.boss['hp']} / {self.boss['max_hp']} ({hp_percent:.1f}%)", inline=False)
            embed.add_field(name="ผู้เข้าร่วม", value=f"{len(self.contributors)} คน", inline=False)
            return embed
        except Exception as e:
            print(f"[ERROR] [get_boss_embed] พลอตข้อมูลเรนเดอร์ล้มเหลว: {e}")
            return discord.Embed(title="❌ เกิดข้อผิดพลาดในการแสดงผลบอส", color=discord.Color.red())

    async def distribute_rewards(self, interaction):
        try:
            total_dmg = sum(self.contributors.values())
            print(f"[LOG] [REWARDS_START] เริ่มแจกจ่ายรางวัลสำหรับบอส ดาเมจรวมทั้งหมดจากผู้เล่น: {total_dmg}")
            
            if total_dmg <= 0: 
                print(f"[LOG] [REWARDS_ABORT] ดาเมจรวมเป็น 0 หรือติดลบ ไม่สามารถคำนวณส่วนแบ่งได้")
                return 

            msg = "🎁 **สรุปรางวัล:**\n"
            for user_id, dmg in self.contributors.items():
                member = interaction.guild.get_member(user_id)
                if not member: 
                    print(f"[LOG] [REWARDS_SKIP] ไม่พบตัวตนผู้เล่น {user_id} ในเซิร์ฟเวอร์ขณะแจกรางวัล (อาจจะออฟไลน์หรือออกจากดิสคอร์ด)")
                    continue 
                
                try:
                    ratio = dmg / total_dmg
                    gold_reward = int(self.boss['gold'] * ratio)
                    exp_reward = int(self.boss['exp'] * ratio)
                    
                    # บันทึกข้อมูลลงฐานข้อมูลจริง
                    player_model.add_exp(user_id, exp_reward)
                    player_model.increment_player_field(user_id, "cash", gold_reward)
                    
                    msg += f"• {member.display_name}: {gold_reward} ทอง, {exp_reward} EXP\n"
                    print(f"[LOG] [DATABASE_SAVED] แจกรางวัลสำเร็จ -> ผู้เล่น: {member.display_name} | ได้รับ {gold_reward} ทอง | ได้รับ {exp_reward} EXP (สัดส่วนดาเมจ: {ratio*100:.1f}%)")
                except Exception as db_err:
                    print(f"[ERROR] [REWARDS_DB_UPDATE_FAIL] ไม่สามารถอัปเดตข้อมูลผู้เล่น {user_id} ลงดาต้าเบสได้: {db_err}")
            
            await interaction.followup.send(msg)
            print(f"[LOG] [REWARDS_END] ส่งข้อความสรุปตารางรับของรางวัลลงห้องแชทเรียบร้อยแล้ว")
        except Exception as e:
            print(f"[ERROR] [distribute_rewards] เกิดข้อผิดพลาดภาพรวมระบบแจกรางวัล: {e}")

class WorldBoss(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        print(f"[LOG] [LOAD_COG] โหลดโมดูลระบบ WorldBoss เรียบร้อยแล้ว")

    @has_role_or_owner("คนบ้า")
    @commands.command(name="spawn_boss")
    @commands.has_permissions(administrator=True)
    async def spawn_boss(self, ctx, name, hp: int, dice_count: int, dice_sides: int, exp: int, gold: int):
        try:
            print(f"[LOG] [COMMAND_SPAWN] แดมิน {ctx.author.name} เรียกใช้คำสั่งเสกบอส: {name} (HP: {hp}, เต๋า: {dice_count}d{dice_sides})")
            
            # เช็กเงื่อนไขค่าติดลบ
            if hp <= 0 or dice_count <= 0 or dice_sides <= 0:
                print(f"[LOG] [COMMAND_VALIDATION_FAIL] แอดมินระบุค่าผิดพลาด (มีค่าติดลบหรือเท่ากับ 0) สกัดกั้นการเสก")
                return await ctx.send("❌ ค่าบอสต้องเป็นเลขบวก!")

            boss_data = {
                'name': name, 'hp': hp, 'max_hp': hp, 
                'dice_count': dice_count, 'dice_sides': dice_sides, 
                'exp': exp, 'gold': gold
            }
            
            view = BossView(boss_data)
            embed = view.get_boss_embed()
            embed.description = "คลิกปุ่มด้านล่างเพื่อเข้าโจมตี!"
            
            await ctx.send(embed=embed, view=view)
            print(f"[LOG] [COMMAND_SUCCESS] ส่งการ์ด World Boss [{name}] ลงสนามเรียบร้อย")
        except Exception as e:
            print(f"[ERROR] [spawn_boss_command] เกิดข้อผิดพลาดของคำสั่ง: {e}")
            await ctx.send("❌ เกิดความผิดพลาดทางเทคนิคในการสร้างบอส!")

async def setup(bot):
    try:
        await bot.add_cog(WorldBoss(bot))
        print(f"[LOG] [SETUP] ติดตั้ง Cog WorldBoss เข้ากับระบบหลักสมบูรณ์")
    except Exception as e:
        print(f"[ERROR] [setup_cog] โหลด Extension ล้มเหลว: {e}")