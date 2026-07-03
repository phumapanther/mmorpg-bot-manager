import discord
from discord.ui import View
import random
import models.player_model as player_model
from views.profile_embed import ARMOR_STATS, GAME_CLASSES ,WEAPON_STATS,ITEM_CONFIG
import traceback # เอาไว้ดูว่า Error บรรทัดไหน
import json  

# ==========================================================
# 📊 [SKILL BALANCE CONFIG] คลังศูนย์กลางคุมบาลานซ์สกิลแบบละเอียด 100%
# ==========================================================
SKILL_CONFIG = {
    "Warrior": {
        "heavy_strike": {
            "chance_base": 80,          # โอกาสติดพื้นฐาน (%)
            "chance_lvl_scale": 1,      # โอกาสติดเพิ่มขึ้นต่อเลเวล (เช่น +1% ต่อ 1 เลเวล)
            "damage_multiplier": 2      # ตัวคูณความเสียหายเมื่อสำเร็จ
        },
        "shield_bash": {
            "duration": 3,              # ระยะเวลาติดสถานะ (เทิร์น)
            "reduction_base": 0.50,     # อัตราลดดาเมจพื้นฐาน (50%)
            "reduction_lvl_scale": 0.005 # อัตราลดดาเมจเพิ่มขึ้นต่อเลเวล (+0.5% ต่อ 1 เลเวล)
        }
    },
    "Mage": {
        "fireball": {
            "duration": 2,              # ระยะเวลาติดไฟ (เทิร์น)
            "burn_base": 0.05,          # พลังเผาไหม้พื้นฐานอิงตาม HP บอส (5%)
            "burn_lvl_scale": 0.002     # พลังเผาเพิ่มขึ้นต่อเลเวล (+0.2% ต่อ 1 เลเวล)
        },
        "frostbolt": {
            "duration_base": 1,         # ระยะเวลาแช่แข็งพื้นฐาน (เทิร์น)
            "duration_lvl_scale": 0.05,  # ระยะเวลาแช่แข็งเพิ่มขึ้นต่อเลเวล (เช่น ทุก 20 เลเวลเพิ่ม 1 เทิร์น)
            "damage_reduce": 0.75       # อัตราหักล้างดาเมจของบอส (75%)
        }
    },
    "Rogue": {
        "backstab": {
            "chance_base": 50,          # โอกาสติดพื้นฐาน (%)
            "chance_lvl_scale": 0.5,      # โอกาสติดเพิ่มขึ้นต่อเลเวล (+0.5% ต่อ 1 เลเวล)
            "damage_reflect_mult": 1.5  # ตัวคูณดาเมจคริติคอลสะท้อนสวนกลับบอส
        },
        "evasion": {
            "chance_base": 100,          # โอกาสวิ่งหนีสำเร็จพื้นฐาน (%)
            "chance_lvl_scale": 0.0       # โอกาสวิ่งหนีสำเร็จเพิ่มขึ้นต่อเลเวล (+0.5% ต่อ 1 เลเวล)
        }
    },
    "Cleric": {
        "heal": {
            "heal_percent_base": 0.40,  # อัตราฮีลพื้นฐานอิงจาก Max HP (40%)
            "heal_lvl_scale": 0.01      # อัตราฮีลเพิ่มขึ้นต่อเลเวล (+1% ต่อ 1 เลเวล)
        },
        "holy_aura": {
            "chance_base": 50,          # โอกาสบล็อกดาเมจเป็น 0 พืนฐาน (%)
            "chance_lvl_scale": 1       # โอกาสบล็อกดาเมจเพิ่มขึ้นต่อเลเวล (+1% ต่อ 1 เลเวล)
        }
    }
}

# ตารางสัดส่วนน้ำหนักเหตุการณ์ (อ้างอิงจาก last_event)
EVENT_WEIGHTS = {
    "village":            [2,   0,        3,      1,       90,       4],
    "dungeon_inside":     [45,  5,        35,     0,       5,        10],
    "monster":            [25,  25,       20,     10,      10,       10],
    "treasure":           [30,  20,       10,     15,      15,       10],
    "npc":                [20,  40,       15,     10,      5,        10],
    "trap":               [35,  15,       15,     10,      10,       15],
    "none":               [25,  25,       20,     15,      10,       5]
}
EVENT_LIST = ["monster", "village", "treasure", "dungeon", "npc", "trap"]

# โครงสร้างข้อมูลระดับความโหดของมอนสเตอร์
MONSTER_RANKS = {
    "Common":      {"name": "🟢 มอนสเตอร์ทั่วไป (Common)",      "dice_count": 1, "hp_range": (40, 100),   "flee_chance": 85,  "gold_mult": 2,   "exp_reward": 25},
    "Mini-Boss":   {"name": "🟡 มินิบอส (Mini-Boss)",          "dice_count": 2, "hp_range": (100, 500),  "flee_chance": 60,  "gold_mult": 5,  "exp_reward": 50},
    "Main-Boss":   {"name": "🔴 บอสหลัก (Main-Boss)",          "dice_count": 3, "hp_range": (500, 1000), "flee_chance": 30,  "gold_mult": 10,  "exp_reward": 250},
    "Secret":      {"name": "🟣 มอนสเตอร์ลับ (Secret)",          "dice_count": 2, "hp_range": (100, 1000), "flee_chance": 50,  "gold_mult": 15,  "exp_reward": 250},
    "Unbeatable":  {"name": "💀 ไร้พ่าย (Unbeatable)",         "dice_count": 5, "hp_range": (1000, 2000), "flee_chance": 5,   "gold_mult": 1000, "exp_reward": 1000}
}


# ==========================================================
# 🎮 INTERACTIVE VIEWS
# ==========================================================

class MonsterEventView(View):
    def __init__(self, user_id, member_roles, monster_rank=None, monster_hp=None, active_buffs=None, turn_count=1):
        super().__init__(timeout=60)
        self.user_id = user_id
        self.member_roles = member_roles
        self.active_buffs = active_buffs if active_buffs else {}
        self.turn_count = turn_count
        
        if monster_rank is None:
            # 1. ดึงข้อมูลผู้เล่นเพื่อเช็กเลเวลปัจจุบัน
            # (ถ้าในคลาสใช้ชื่อตัวแปรอื่น เช่น self.user_id ให้เปลี่ยนตามความเหมาะสมครับ)
            player = player_model.get_player(user_id) 
            player_level = player.get("level", 0)
            last_evt = player.get("last_event", "none")
            rank_keys = list(MONSTER_RANKS.keys())
            
            # 2. 🛠️ กำหนดน้ำหนักการสุ่ม (Weights)
            # ตำแหน่งของเรท: [คอมมอน, มินิ, เมน, ซีเคร็ท, ไร้พ่าย]
            
            if last_evt == "mini_summon":
                # ล็อกเป้า 100% เจอ มินิบอส (ตำแหน่งที่ 2)
                spawn_weights = [0, 100, 0, 0, 0]
                player_model.update_player_field(user_id, "last_event", "monster")
                
            elif last_evt == "main_summon":
                # ล็อกเป้า 100% เจอ บอสหลัก (ตำแหน่งที่ 3)
                spawn_weights = [0, 0, 100, 0, 0]
                player_model.update_player_field(user_id, "last_event", "monster")
                
            elif last_evt == "unbeatable_summon":
                # ล็อกเป้า 100% เจอ บอสไร้พ่าย (ตำแหน่งที่ 5)
                spawn_weights = [0, 0, 0, 0, 100]
                player_model.update_player_field(user_id, "last_event", "monster")
                
            else:
                # ถ้าไม่ได้ใช้ใบเรียกบอส ให้สุ่มตามช่วงเลเวลปกติ
                if player_level >= 100:
                    spawn_weights = [10, 30, 20, 25, 15]
                elif player_level >= 90:
                    spawn_weights = [30, 20, 20, 20, 10]
                elif player_level >= 50:
                    spawn_weights = [50, 20, 20, 8, 2]
                elif player_level >= 20:
                    spawn_weights = [70, 20, 5, 3, 2]
                elif player_level >= 10:
                    spawn_weights = [80, 10, 5, 3, 2]
                else:
                    # กรณีเลเวล 0 ถึง 9 (เจอมอนสเตอร์ระดับต่ำสุด)
                    spawn_weights = [95, 2, 1, 1, 1]
                
            # 3. สุ่มมอนสเตอร์ตามน้ำหนักที่ได้จากเงื่อนไขด้านบน
            self.monster_rank = random.choices(rank_keys, weights=spawn_weights, k=1)[0]
            self.m_stats = MONSTER_RANKS[self.monster_rank]
            self.monster_hp = random.randint(self.m_stats["hp_range"][0], self.m_stats["hp_range"][1])
            
            # [ระบบเช็กไฟล์/แคช]
            # print(f"DEBUG: [มอนสเตอร์] เลเวล {player_level} -> ใช้เรท {spawn_weights} -> สุ่มได้ {self.monster_rank}")
            
        else:
            self.monster_rank = monster_rank
            self.m_stats = MONSTER_RANKS[self.monster_rank]
            self.monster_hp = monster_hp

        self.player_class = "Unknown"
        for role in self.member_roles:
            if role.name in GAME_CLASSES:
                self.player_class = role.name
                break

        self.add_skill_buttons()

    def add_skill_buttons(self):
        skills_map = {
            "Warrior": [("🛡️ Shield Bash", "skill_shield_bash"), ("⚔️ Heavy Strike", "skill_heavy_strike")],
            "Mage":    [("🔥 Fireball", "skill_fireball"),       ("❄️ Frostbolt", "skill_frostbolt")],
            "Rogue":   [("🗡️ Backstab", "skill_backstab"),       ("💨 Evasion", "skill_evasion")],
            "Cleric":  [("✨ Heal", "skill_heal"),               ("🛡️ Holy Aura", "skill_holy_aura")]
        }

        if self.player_class in skills_map:
            for label, custom_id in skills_map[self.player_class]:
                btn = discord.ui.Button(label=label, style=discord.ButtonStyle.primary, custom_id=custom_id, row=1)
                btn.callback = self.skill_callback 
                self.add_item(btn)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("❌ นี่ไม่ใช่การต่อสู้ของคุณ! พิมพ์ `!play` เพื่อเปิดบอร์ดตัวเองนะจ๊ะ", ephemeral=True)
            return False
        return True

    async def process_turn(self, interaction: discord.Interaction, skill_used=None):
        try:
            player = player_model.get_player(self.user_id)
            if not player:
                return await interaction.response.send_message("❌ ไม่พบข้อมูลตัวละครของคุณในระบบ!", ephemeral=True)

            p_lvl = player.get("level", 1)
            
            # 1. 🛡️ ดึงข้อมูลอุปกรณ์
            w_id = player.get("weapon", "Wooden_Weapon")
            a_id = player.get("armor", "None")
            w_stat = WEAPON_STATS.get(w_id, WEAPON_STATS.get("Wooden_Weapon", {"atk": 1}))
            a_stat = ARMOR_STATS.get(a_id, ARMOR_STATS.get("None", {"hp": 0}))
            
            # 2. 🛡️ คำนวณพลังโจมตี (ถ้าความทนทานเป็น 0 พลังโจมตีหาย)
            curr_atk = w_stat.get("atk", 0) if player.get("weapon_dur", 0) > 0 else 0
            
            # 3. 🛠️ กำหนดค่าความทนทานเริ่มต้นเป็น 0 เพื่อป้องกันบั๊ก
            durability_lost_w = 3 if skill_used else 1 
            damage_to_armor = 0 
            
            player_roll = random.randint(1, 20)
            monster_roll = sum(random.randint(1, 20) for _ in range(self.m_stats.get("dice_count", 1)))
            
            skill_log = ""
            combat_log = ""
            db_updates = {}
            
            enrage_bonus = 0
            if self.turn_count > 3:
                rank_danger = {"Common": 2, "Mini-Boss": 5, "Main-Boss": 10, "Secret": 8, "Unbeatable": 25}
                enrage_bonus = (self.turn_count - 3) * rank_danger.get(self.monster_rank, 2)
                skill_log += f"😡 **{self.m_stats.get('name', 'บอส')} กำลังคลั่ง!** บอสสะสมความโกรธเพิ่มพลังโจมตีเด็ดขาด `+{enrage_bonus}` หน่วยในเทิร์นนี้!\n"

            damage_multiplier = 1

            # ─── ⚔️ ระบบคำนวณสกิลช่วงต้นเทิร์น ───
            try:
                if skill_used == "skill_heavy_strike":
                    w_cfg = SKILL_CONFIG["Warrior"]["heavy_strike"]
                    chance = w_cfg["chance_base"] + (p_lvl * w_cfg["chance_lvl_scale"])
                    if random.randint(1, 100) <= chance:
                        damage_multiplier = w_cfg["damage_multiplier"]
                        skill_log += f"✨ **Heavy Strike สำเร็จ!** การโจมตีในเทิร์นนี้จะแรงขึ้น {damage_multiplier} เท่า!\n"
                    else:
                        skill_log += "💨 **Heavy Strike ล้มเหลว!** ทอยเต๋าพลาดสมาธิหลุด\n"

                elif skill_used == "skill_evasion":
                    r_cfg = SKILL_CONFIG["Rogue"]["evasion"]
                    chance = r_cfg["chance_base"] + (p_lvl * r_cfg["chance_lvl_scale"])
                    if random.randint(1, 100) <= chance:
                        player_model.update_player_field(self.user_id, "current_state", "idle")
                        await interaction.response.edit_message(content=f"💨 **Evasion สำเร็จ!** คุณม้วนตัวหนีออกจากสู้กับ **{self.m_stats.get('name', 'มอนสเตอร์')}** ได้สำเร็จ!", view=AdventureView(author_id=self.user_id))
                        return
                    else:
                        skill_log += "⚠️ **Evasion ล้มเหลว!** มอนสเตอร์ดักทางเท้าไว้ได้\n"

                elif skill_used == "skill_heal":
                    c_cfg = SKILL_CONFIG["Cleric"]["heal"]
                    heal_percent = c_cfg["heal_percent_base"] + (p_lvl * c_cfg["heal_lvl_scale"])
                    heal_amount = int(player.get("max_hp", 100) * heal_percent)
                    
                    if self.monster_rank in ["Main-Boss", "Unbeatable"]:
                        stolen_heal = int(heal_amount * 0.3)
                        heal_amount -= stolen_heal
                        self.monster_hp = min(self.m_stats.get("hp_range", [0,100])[1], self.monster_hp + stolen_heal)
                        skill_log += f"💔 **คำสาปบอสทำงาน!** บอสสูบกลืนแสงฮีลของคุณไป `+{stolen_heal}` HP! "
                    
                    new_hp = min(player.get("max_hp", 100), player.get("hp", 100) + heal_amount)
                    player["hp"] = new_hp 
                    skill_log += f"✨ **Heal!** พลังชีวิตของคุณฟื้นฟู `+ {heal_amount}` หน่วย (❤️ HP: {new_hp})\n"

                if skill_used == "skill_shield_bash": 
                    self.active_buffs["shield_bash"] = SKILL_CONFIG["Warrior"]["shield_bash"]["duration"]
                elif skill_used == "skill_fireball": 
                    self.active_buffs["fireball"] = SKILL_CONFIG["Mage"]["fireball"]["duration"]
                elif skill_used == "skill_frostbolt": 
                    f_cfg = SKILL_CONFIG["Mage"]["frostbolt"]
                    self.active_buffs["frostbolt"] = f_cfg["duration_base"] + int(p_lvl * f_cfg["duration_lvl_scale"])
                elif skill_used == "skill_holy_aura": 
                    self.active_buffs["holy_aura"] = 3
                elif skill_used == "skill_backstab":
                    r_b_cfg = SKILL_CONFIG["Rogue"]["backstab"]
                    if random.randint(1, 100) <= (r_b_cfg["chance_base"] + (p_lvl * r_b_cfg["chance_lvl_scale"])): 
                        self.active_buffs["backstab"] = 1
            except KeyError as e:
                print(f"⚠️ [WARNING] ตั้งค่าสกิลขาดหาย: {e}")

            # 🔥 คิดเอฟเฟกต์เผาไหม้ของ Fireball
            if self.active_buffs.get("fireball", 0) > 0:
                try:
                    m_cfg = SKILL_CONFIG["Mage"]["fireball"]
                    burn_percent = m_cfg["burn_base"] + (p_lvl * m_cfg["burn_lvl_scale"])
                    burn_damage = int(self.m_stats.get("hp_range", [0,100])[1] * burn_percent)
                    self.monster_hp = max(0, self.monster_hp - burn_damage)
                    combat_log += f"🔥 *เอฟเฟกต์เผาไหม้:* บอสโดนไฟบอลเผาเสีย HP `- {burn_damage}` หน่วย (บอสเหลือ HP: {self.monster_hp})\n"
                    self.active_buffs["fireball"] -= 1
                except Exception as e: pass

            # ⚔ คุณทอยได้เต๋าชนะบอส
            if player_roll >= monster_roll:
                damage_to_monster = int((player_roll + curr_atk) * 5 * damage_multiplier)
                self.monster_hp = max(0, self.monster_hp - damage_to_monster)
                combat_log += f"⚔️ คุณทอยได้ **🎲 {player_roll}/บอส({monster_roll})** (+{curr_atk} ดาบ) สร้างความเสียหายใส่บอส `- {damage_to_monster}` หน่วย\n"
            
            # 👾 บอสทอยได้เต๋าชนะ
            else:
                damage_to_player = random.randint(10, 25) + enrage_bonus
                
                if player.get("armor_dur", 0) > 0:
                    damage_to_armor = max(1, int(damage_to_player / 10))
                    reduction = int(damage_to_player * 0.2)
                    damage_to_player -= reduction
                    combat_log += f"🛡️ เกราะรับดาเมจแทนคุณ `- {reduction}` หน่วย!\n"
                
                try:
                    if self.active_buffs.get("frostbolt", 0) > 0:
                        f_reduce = SKILL_CONFIG["Mage"]["frostbolt"]["damage_reduce"]
                        damage_to_player = int(damage_to_player * (1 - f_reduce))
                        combat_log += f"❄️ *น้ำแข็งเกาะ:* บอสติดแช่แข็ง พลังโจมตีลดลง {int(f_reduce*100)}%! (โดนดาเมจเบา ๆ `- {damage_to_player}`)\n"
                        
                    elif self.active_buffs.get("holy_aura", 0) > 0 and random.randint(1, 100) <= (SKILL_CONFIG["Cleric"]["holy_aura"]["chance_base"] + (p_lvl * SKILL_CONFIG["Cleric"]["holy_aura"]["chance_lvl_scale"])):
                        damage_to_player = 0
                        combat_log += "✨ *Holy Aura ทำงาน:* ร่างกายส่องแสงบล็อคพลังโจมตีของบอสกลายเป็น 0!\n"
                        
                    elif self.active_buffs.get("backstab", 0) > 0:
                        damage_to_player = int(damage_to_player * 0.2)
                        rogue_reflect = int(player_roll * 5 * SKILL_CONFIG["Rogue"]["backstab"]["damage_reflect_mult"])
                        self.monster_hp = max(0, self.monster_hp - rogue_reflect)
                        combat_log += f"🗡️ *Backstab คุมเชิง:* ดาเมจสวนกลับลดลง 80% (โดนแค่ `- {damage_to_player}`) พร้อมวาร์ปตลบหลังแทงบอสสวนกลับหงายหลังฟาด `- {rogue_reflect}` หน่วย! (บอสเหลือ HP: {self.monster_hp})\n"
                        
                    elif self.active_buffs.get("shield_bash", 0) > 0:
                        s_b_cfg = SKILL_CONFIG["Warrior"]["shield_bash"]
                        reduction = s_b_cfg["reduction_base"] + (p_lvl * s_b_cfg["reduction_lvl_scale"])
                        damage_to_player = int(damage_to_player * (1 - min(0.9, reduction)))
                        combat_log += f"🛡️ *Shield Bash บล็อก:* ดาเมจลดลงครอบคลุมเกราะ (โดนแค่ `- {damage_to_player}`)\n"
                except Exception: pass

                if damage_to_player > 0:
                    player["hp"] = max(0, player.get("hp", 100) - damage_to_player)
                    combat_log += f"⚔️ คุณทอยได้ **🎲 {player_roll}/บอส({monster_roll})** 💥 บอสโจมตีสวน! เสีย HP `- {damage_to_player}` (เกราะเสื่อมสภาพ `- {damage_to_armor}`)\n"

            # 6. 💾 คำนวณค่าทนทานใหม่
            new_w_dur = max(0, player.get("weapon_dur", 0) - durability_lost_w)
            new_a_dur = max(0, player.get("armor_dur", 0) - damage_to_armor)

            db_updates["weapon_dur"] = new_w_dur
            db_updates["armor_dur"] = new_a_dur
            db_updates["hp"] = player.get("hp", 100)

            # 7. 🚨 แจ้งเตือนของพัง
            if new_w_dur == 0 and player.get("weapon_dur", 0) > 0:
                combat_log += "🚨 **อาวุธของคุณพังแตกหัก!**\n"
            if new_a_dur == 0 and player.get("armor_dur", 0) > 0:
                combat_log += "🚨 **ชุดเกราะของคุณพังยับเยิน!**\n"

            # หักเทิร์นสถานะบัฟ
            if self.active_buffs.get("frostbolt", 0) > 0: self.active_buffs["frostbolt"] -= 1
            if self.active_buffs.get("holy_aura", 0) > 0: self.active_buffs["holy_aura"] -= 1
            if self.active_buffs.get("shield_bash", 0) > 0: self.active_buffs["shield_bash"] -= 1
            if self.active_buffs.get("backstab", 0) > 0: self.active_buffs["backstab"] -= 1

            # =================================================================
            # 🏆 กรณี: ผู้เล่นชนะ (บอสตาย)
            # =================================================================
            if self.monster_hp <= 0:
                reward = int(random.randint(1, 25) * self.m_stats.get("gold_mult", 1.0))
                gained_exp = self.m_stats.get("exp_reward", 10) + random.randint(5, 15)
                
                db_updates["cash"] = player.get("cash", 0) + reward
                db_updates["sanity"] = player.get("sanity", 100) + 1
                db_updates["last_event"] = "monster"
                db_updates["current_state"] = "idle"
                
                dropped_item_msg = ""
                try:
                    fresh_player = player_model.get_player(self.user_id)
                    raw_inv = fresh_player.get("inventory", "[]")
                    
                    if isinstance(raw_inv, str):
                        try:
                            import json
                            parsed_inv = json.loads(raw_inv)
                            if isinstance(parsed_inv, list): inv_list = parsed_inv
                            else: inv_list = [str(parsed_inv)] 
                        except:
                            inv_list = raw_inv.split(",") if "," in raw_inv else ([raw_inv] if raw_inv and raw_inv not in ["None", "null", ""] else [])
                    elif isinstance(raw_inv, list):
                        inv_list = raw_inv
                    else:
                        inv_list = []
                    
                    inv_list = [str(i).strip() for i in inv_list if str(i).strip() and str(i).strip() not in ["None", "null", "[]"]]

                    m_tier = getattr(self, "monster_rank", "Common")
                    dropped_item_id = None
                    
                    if m_tier in ["Secret", "Unbeatable"] and random.random() <= 0.01:
                        dropped_item_id = random.choice(["8", "21"])
                    elif random.random() <= 0.70:
                        if m_tier == "Common":
                            drop_pool = ["9", "10", "11", "12", "13", "14", "15", "16", "17", "18"]
                        else:
                            drop_pool = ["9", "10", "11", "12", "13", "14", "15", "16", "17", "18", 
                                         "22", "23", "24", "25", "26", "27", "28", "3", "4", "5", "6", "7"]
                        weights = [100000 / ITEM_CONFIG.get(i, {}).get("buy", 100) for i in drop_pool]
                        dropped_item_id = random.choices(drop_pool, weights=weights, k=1)[0]

                    if dropped_item_id:
                        dropped_item_name = ITEM_CONFIG.get(dropped_item_id, {}).get("name", "ไอเทมปริศนา")
                        capacity = fresh_player.get("capacity", 10)
                        current_count = len(inv_list)
                        
                        if capacity == 0 or current_count < capacity:
                            inv_list.append(str(dropped_item_id))
                            import json
                            db_updates["inventory"] = json.dumps(inv_list)
                            
                            capacity_display = "(Unlimited)" if capacity == 0 else f"({current_count + 1}/{capacity})"
                            
                            if dropped_item_id in ["8", "21"]:
                                dropped_item_msg = f"\n🌟 **[ULTRA RARE DROP!]** พระเจ้ายิ้มรับ! คุณได้รับ `{dropped_item_name}` 1 ชิ้น!"
                            else:
                                dropped_item_msg = f"\n📦 **ดรอปไอเทม:** ได้รับ `{dropped_item_name}` 1 ชิ้น! {capacity_display}"
                        else:
                            dropped_item_msg = (
                                f"\n⚠️ **กระเป๋าเต็ม!** มอนสเตอร์ดรอป `{dropped_item_name}` "
                                f"แต่กระเป๋าของคุณเต็ม ({current_count}/{capacity})\n"
                                f"👉 **วิธีแก้:** พิมพ์ `!drop` เพื่อทิ้งของเก่า หรือไปขายของที่ร้านค้าในเมือง!"
                            )

                except Exception as e:
                    print(f"❌ [ERROR] ระบบดรอปไอเทมพัง: {e}")

                if player.get("current_state") == "dungeon_choice" or player.get("dungeon_steps", 0) > 0:
                    next_view = AdventureView(author_id=self.user_id) 
                    battle_end_log = f"\n⚔️ มอนสเตอร์ในชั้นนี้ถูกกำจัดแล้ว! เตรียมตัวเดินทางลึกเข้าไปในดันเจี้ยนขั้นถัดไป..."
                else:
                    next_view = AdventureView(author_id=self.user_id)
                    battle_end_log = ""

                current_exp = player.get("exp", 0) + gained_exp
                current_level = player.get("level", 1)
                max_hp = player.get("max_hp", 100)
                is_lv_up = False
                
                try:
                    loop_failsafe = 0 
                    while loop_failsafe < 100:
                        loop_failsafe += 1
                        if current_level >= 100:
                            current_exp = 0
                            break
                        
                        required_exp = (current_level ** 2) * 70
                        if current_exp >= required_exp:
                            current_exp -= required_exp
                            current_level += 1
                            max_hp += 20
                            is_lv_up = True
                        else:
                            break
                    
                    db_updates["exp"] = current_exp
                    db_updates["level"] = current_level
                    if is_lv_up:
                        db_updates["max_hp"] = max_hp
                        db_updates["hp"] = max_hp 
                except Exception as e:
                    print(f"❌ [ERROR] ระบบคำนวณ EXP พัง: {e}")

                rank_msg = ""
                try:
                    old_rank = player.get("rank", "F")
                    if current_level >= 100: new_rank = "SSS"
                    elif current_level >= 80: new_rank = "A"
                    elif current_level >= 50: new_rank = "B"
                    elif current_level >= 20: new_rank = "C"
                    elif current_level >= 10: new_rank = "D"
                    elif current_level >= 5: new_rank = "E"
                    else: new_rank = "F"
                    
                    if old_rank != new_rank:
                        db_updates["rank"] = new_rank
                    
                    player_model.update_player_fields(self.user_id, db_updates)
                    
                    if old_rank != new_rank:
                        guild = interaction.guild
                        member = interaction.user
                        if guild and isinstance(member, discord.Member):
                            role_name = f"นักผจญภัยแรงค์ {new_rank}"
                            role = discord.utils.get(guild.roles, name=role_name)
                            if role:
                                try:
                                    await member.add_roles(role)
                                    rank_msg = f"\n🎖️ **สมาคมนักผจญภัยได้เลื่อนขั้นให้คุณเป็น: {role_name}!**"
                                except Exception: pass
                except Exception as e:
                    print(f"❌ [ERROR] ระบบแรงค์พัง: {e}")

                # -----------------------------------------------------------------
                # 📩 จบการทำงาน (ส่งข้อความชนะแบบต้นฉบับ 100%)
                # -----------------------------------------------------------------
                try:
                    lv_up_msg = f"\n✨🎉 **LEVEL UP!! คุณเลเวลเพิ่มขึ้นเป็น Lv.{current_level}** พลังชีวิตสูงสุดเพิ่มขึ้น เลือดฟื้นฟูเต็มเปี่ยม! ✨🎉" if is_lv_up else ""
                    required_xp_display = (current_level ** 2) * 70
                    
                    final_content = f"{skill_log}{combat_log}🎉 **ยินดีด้วย! คุณสามารถโค่น {self.m_stats.get('name', 'มอนสเตอร์')} ลงได้สำเร็จ!**\n💰 ได้รับเงินรางวัล `{reward}` ทอง\n🔷 ได้รับค่าประสบการณ์ `+{gained_exp}` EXP *(สะสมปัจจุบัน: {current_exp}/{required_xp_display} XP)*{lv_up_msg}{rank_msg}{dropped_item_msg}{battle_end_log}"
                    
                    if not interaction.response.is_done():
                        await interaction.response.edit_message(content=final_content, view=next_view)
                    else:
                        await interaction.followup.edit_message(message_id=interaction.message.id, content=final_content, view=next_view)
                
                except discord.NotFound:
                    print("⚠️ [WARNING] สู้จบนานเกินไป Interaction หมดอายุ กำลังส่งเป็นข้อความธรรมดาแทน...")
                    try:
                        await interaction.channel.send(content=f"<@{self.user_id}> {final_content}", view=next_view)
                    except Exception as e:
                        print(f"❌ [ERROR] ไม่สามารถส่งข้อความแทนได้: {e}")
                except Exception as e:
                    print(f"❌ [ERROR] ไม่สามารถแก้ไขข้อความตอนจบได้: {e}")

            # =================================================================
            # 💀 กรณี: ผู้เล่นแพ้ (เลือดหมด)
            # =================================================================
            elif db_updates.get("hp", player.get("hp", 0)) <= 0:
                try:
                    db_updates["current_state"] = "dead"
                    player_model.update_player_fields(self.user_id, db_updates)
                    
                    fail_msg = f"{skill_log}{combat_log}💀 **คุณหมดสติลงกลางสนามรบเนื่องจากทนความโกรธของบอสไม่ไหว...**"
                    if not interaction.response.is_done():
                        await interaction.response.edit_message(content=fail_msg, view=RespawnView(self.user_id))
                    else:
                        await interaction.followup.edit_message(message_id=interaction.message.id, content=fail_msg, view=RespawnView(self.user_id))
                except Exception as e:
                    print(f"❌ [ERROR] การแจ้งเตือนความตายพัง: {e}")

            # =================================================================
            # 🔄 กรณี: ยังไม่มีใครตาย (ไปเทิร์นถัดไป)
            # =================================================================
            else:
                try:
                    player_model.update_player_fields(self.user_id, db_updates)
                    next_turn = self.turn_count + 1
                    
                    next_msg = f"⚔️ **[เทิร์นที่ {self.turn_count}] การต่อสู้ทวีความรุนแรง!**\n👾 ศัตรู: **{self.m_stats.get('name','?')}** (🩸 HP คงเหลือ: **{self.monster_hp}**)\n❤️ เลือดร่างกายของคุณ: **{db_updates['hp']}/{player.get('max_hp',100)}**\n\n{skill_log}{combat_log}----------------------------------------\nบอสจะแกร่งขึ้นเรื่อยๆ เลือกแอคชั่นหรือสกิลที่จะใช้ถัดไป:"
                    
                    if not interaction.response.is_done():
                        await interaction.response.edit_message(content=next_msg, view=MonsterEventView(self.user_id, self.member_roles, self.monster_rank, self.monster_hp, self.active_buffs, turn_count=next_turn))
                    else:
                        await interaction.followup.edit_message(message_id=interaction.message.id, content=next_msg, view=MonsterEventView(self.user_id, self.member_roles, self.monster_rank, self.monster_hp, self.active_buffs, turn_count=next_turn))
                except Exception as e:
                    print(f"❌ [ERROR] การไปเทิร์นถัดไปพัง: {e}")

        # 🚨 CATCH-ALL: ดักจับ Error ขั้นรุนแรง 🚨
        except Exception as global_e:
            print(f"💥 [CRITICAL ERROR] ฟังก์ชัน process_turn ล่มสลาย!: {global_e}")
            import traceback
            traceback.print_exc() 
            
            try:
                error_msg = f"❌ **เกิดข้อผิดพลาดร้ายแรงระหว่างการต่อสู้!**\nระบบขัดข้องชั่วคราว โปรดแคปจอแจ้งแอดมิน: `{str(global_e)}`"
                if not interaction.response.is_done():
                    await interaction.response.send_message(error_msg, ephemeral=True)
                else:
                    await interaction.followup.send(error_msg, ephemeral=True)
            except Exception: pass

    @discord.ui.button(label="⚔️ สู้ต่อ (ทอยเต๋าปกติ)", style=discord.ButtonStyle.danger, row=0)
    async def fight_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.process_turn(interaction)

    @discord.ui.button(label="🏃 วิ่งหนี!", style=discord.ButtonStyle.secondary, row=0)
    async def flee(self, interaction: discord.Interaction, button: discord.ui.Button):
        flee_roll = random.randint(1, 100)
        
        # ถ้าหนีสำเร็จ
        if flee_roll <= self.m_stats["flee_chance"]:
            player_model.update_player_field(self.user_id, "current_state", "idle")
            await interaction.response.edit_message(content=f"💨 **หนีสำเร็จ!** สลัดหลุดจากมอนสเตอร์สำเร็จ!", view=AdventureView(author_id=self.user_id))
        
        # ถ้าหนีไม่สำเร็จ (โดนโจมตีสวน)
        else:
            player = player_model.get_player(self.user_id)
            damage = random.randint(15, 30)
            new_hp = max(0, player["hp"] - damage)
            
            # 🛡️ คำนวณความเสียหายของเกราะ (โดนตี = เกราะลด)
            if player.get("armor_dur", 0) > 0:
                damage_to_armor = max(1, int(damage / 10))
                new_armor_dur = max(0, player.get("armor_dur", 0) - damage_to_armor)
            else:
                # ถ้าเกราะพังอยู่แล้ว ก็ไม่ต้องลด และไม่ต้องแสดงค่าความเสื่อมสภาพ
                damage_to_armor = 0
                new_armor_dur = 0
            
            # อัปเดตข้อมูลทั้งหมดในรอบเดียว
            db_updates = {
                "hp": new_hp,
                "armor_dur": new_armor_dur,
                "current_state": "fighting"
            }
            
            if new_hp <= 0:
                db_updates["current_state"] = "dead"
                player_model.update_player_fields(self.user_id, db_updates)
                await interaction.response.edit_message(content="💥 หนีไม่พ้นและโดนตบตายคาที่!", view=RespawnView(self.user_id))
            else:
                player_model.update_player_fields(self.user_id, db_updates)
                next_turn = self.turn_count + 1
                msg = f"💥 หนีไม่พ้น! โดนสวนหลังฟาดกระอักเลือด `- {damage}`! (เกราะเสียหาย `- {damage_to_armor}`)"
                
                # เพิ่มข้อความแจ้งเตือนถ้าเกราะพัง
                if new_armor_dur == 0 and player.get("armor_dur", 0) > 0:
                    msg += "\n🚨 **ชุดเกราะของคุณพังยับเยิน!**"
                    
                await interaction.response.edit_message(content=msg, view=MonsterEventView(self.user_id, self.member_roles, self.monster_rank, self.monster_hp, self.active_buffs, turn_count=next_turn))

    async def skill_callback(self, interaction: discord.Interaction):
        if not await self.interaction_check(interaction): return
        await self.process_turn(interaction, skill_used=interaction.data["custom_id"])

# 2. เหตุการณ์ หมู่บ้าน (Village)
class VillageEventView(View):
    def __init__(self, user_id):
        super().__init__(timeout=60)
        self.user_id = user_id

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("❌ คุณไม่ใช่เจ้าของแผงพักแรมนี้! พิมพ์ `!play` เพื่อสั่งงานบอร์ดตัวเองน้า", ephemeral=True)
            return False
        return True

    @discord.ui.button(label="🛏️ พักแรม (2000 ทอง)", style=discord.ButtonStyle.primary)
    async def rest(self, interaction: discord.Interaction, button: discord.ui.Button):
        player = player_model.get_player(self.user_id)
        if player["cash"] < 2000:
            await interaction.response.send_message("❌ เงินสดกลางไม่พอจ่ายค่าห้องนอน!", ephemeral=True)
            return
        
        # ดึงข้อมูลจากฐานข้อมูล
        armor_key = player.get("armor", "None")
        current_dur = player.get("armor_dur", 0) # ดึงค่าความคงทนมาเช็กด้วย
        # ดึงข้อมูล Config เกราะ
        armor_info = ARMOR_STATS.get(armor_key, ARMOR_STATS["None"])
        armor_hp_bonus = armor_info.get("hp", 0)
        # 🛡️ เงื่อนไขพิเศษ: ถ้าความคงทนเป็น 0 ให้โบนัส HP เป็น 0
        if current_dur <= 0:
            effective_hp_bonus = 0
            # print(f"DEBUG: เกราะ {armor_key} พัง (Dur: {current_dur}) -> โบนัส HP: 0")
        else:
            effective_hp_bonus = armor_hp_bonus
            # print(f"DEBUG: เกราะ {armor_key} ปกติ (Dur: {current_dur}) -> โบนัส HP: {effective_hp_bonus}")
        # คำนวณ HP รวม
        max_hp_total = player["max_hp"] + effective_hp_bonus
            
        player_model.update_player_field(self.user_id, "cash", player["cash"] - 2000)
        player_model.update_player_field(self.user_id, "hp", max_hp_total)
        player_model.update_player_field(self.user_id, "current_state", "idle")
        player_model.update_player_field(self.user_id, "last_event", "village")
        
        await interaction.response.edit_message(
            content="💤 คุณนอนพักผ่อนอย่างเต็มอิ่ม ฟื้นฟู HP จนเต็ม!\n----------------------------------------\nคุณต้องการไปต่อหรือไม่?", 
            view=AdventureView(author_id=self.user_id)
        )

    @discord.ui.button(label="🏪 ร้านค้าประจำ", style=discord.ButtonStyle.primary)
    async def shop(self, interaction: discord.Interaction, button: discord.ui.Button):
        # เปลี่ยนหน้าจาก Village ไปยัง Shop
        await interaction.response.edit_message(
            content="🏪 ยินดีต้อนรับสู่ร้านค้าประจำหมู่บ้าน! คุณต้องการซื้อหรือขายไอเทมอะไรดี?",
            view=ShopEventView(self.user_id) # เรียกใช้ View ร้านค้าที่ผมร่างให้ก่อนหน้านี้
        )

    @discord.ui.button(label="🚶 ออกเดินทางต่อ", style=discord.ButtonStyle.secondary)
    async def leave(self, interaction: discord.Interaction, button: discord.ui.Button):
        player_model.update_player_field(self.user_id, "current_state", "idle")
        player_model.update_player_field(self.user_id, "last_event", "village")
        
        await interaction.response.edit_message(
            content="🚶 คุณก้าวเท้าเดินออกจากหมู่บ้านมุ่งสู่เส้นทางหลัก...\n----------------------------------------\nคุณต้องการไปต่อหรือไม่?", 
            view=AdventureView(author_id=self.user_id)
        )
class DeathRespawnView(discord.ui.View):
    def __init__(self, user_id):
        super().__init__(timeout=120) # ให้เวลาตัดสินใจ 2 นาที
        self.user_id = user_id
        self.message = None

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("❌ วิญญาณดวงนี้ไม่ใช่ของคุณ!", ephemeral=True)
            return False
        return True

    @discord.ui.button(label="🏥 กลับไปเกิดที่หมู่บ้าน (-1000 ทอง)", style=discord.ButtonStyle.danger)
    async def force_respawn(self, interaction: discord.Interaction, button: discord.ui.Button):
        player = player_model.get_player(self.user_id)
        
        # หักเงิน 1,000 ทองตามเงื่อนไข (และคำนวณเลือดพื้นฐาน 30% ให้เหมือนระบบปกติ)
        new_cash = player.get("cash", 0) - 1000
        respawn_hp = int(player.get("max_hp", 100) * 0.3)
        
        # อัปเดตข้อมูลกลับเข้า Database
        player_model.update_player_field(self.user_id, "hp", respawn_hp)
        player_model.update_player_field(self.user_id, "cash", new_cash)
        player_model.update_player_field(self.user_id, "current_state", "village")
        player_model.update_player_field(self.user_id, "last_event", "village") # 👈 เพิ่มบรรทัดนี้เพื่อรีเซ็ตความจำ
        player_model.update_player_field(self.user_id, "dungeon_steps", 0)
        
        cash_text = f"`{new_cash:,}` ทอง" if new_cash >= 0 else f"`{new_cash:,}` ทอง ⚠️ (ติดหนี้สมาคม!)"
            
        # 1. แจ้งเตือนผู้เล่นแบบส่วนตัว (Ephemeral) ว่าชุบชีวิตสำเร็จแล้ว
        await interaction.response.send_message(
            content=f"✨ **ฟื้นคืนชีพสำเร็จ!** วิญญาณของคุณถูกดึงกลับมาที่หมู่บ้านอุ่นใจ\n"
                    f"💸 หักค่าธรรมเนียมชุบชีวิตฉุกเฉิน `-1,000` ทอง (เงินคงเหลือ: {cash_text})",
            ephemeral=True
        )
        
        # 2. ลบข้อความแจ้งเตือนที่มีปุ่มนี้ทิ้งไปจากหน้าแชทหลัก
        await interaction.message.delete()
        
    async def on_timeout(self):
        for item in self.children:
            item.disabled = True
        if self.message:
            try:
                await self.message.edit(content="👻 วิญญาณของคุณยังคงล่องลอยอยู่... (หน้าต่างเกิดใหม่หมดอายุ)", view=self)
            except:
                pass

# ระบบร้านค้า      
class ShopEventView(View):
    def __init__(self, user_id):
        super().__init__(timeout=60)
        self.user_id = user_id

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        return interaction.user.id == self.user_id

    # --- หน้าหลัก ---
    @discord.ui.button(label="💰 ซื้อไอเทม", style=discord.ButtonStyle.green)
    async def buy_menu(self, interaction: discord.Interaction, button: discord.ui.Button):
        # 🛠️ กรองแสดงเฉพาะของที่ตั้งค่า purchasable ไม่เท่ากับ False
        content = "🛒 เลือกไอเทมที่ต้องการซื้อ:\n" + "\n".join([f"**เลข {k}:** {v['name']} ({v['buy']} ทอง)" for k, v in ITEM_CONFIG.items() if v.get("purchasable", True)])
        await interaction.response.edit_message(content=content, view=BuySelectView(self.user_id))

    @discord.ui.button(label="📦 ขายไอเทม", style=discord.ButtonStyle.red)
    async def sell_menu(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.edit_message(content="เลือกไอเทมที่จะขาย:", view=SellSelectView(self.user_id))

    @discord.ui.button(label="⬅️ กลับไปหมู่บ้าน", style=discord.ButtonStyle.secondary)
    async def back(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.edit_message(content="คุณเดินกลับไปยังจุดพักแรม...", view=VillageEventView(self.user_id))

# --- ระบบซื้อ ---
class BuySelectView(View):
    def __init__(self, user_id):
        super().__init__(timeout=60)
        self.user_id = user_id
        
        # [ระบบเช็กไฟล์/แคช]
        # print(f"DEBUG: [ร้านค้า] กำลังโหลดหน้า ซื้อไอเทม ให้ User ID: {user_id}")
        
        try:
            for item_id, data in ITEM_CONFIG.items():
                # 🛠️ สร้างปุ่มเฉพาะของที่อนุญาตให้ซื้อ
                if data.get("purchasable", True):
                    btn = discord.ui.Button(label=f"เลข {item_id}", custom_id=item_id)
                    btn.callback = self.buy_callback
                    self.add_item(btn)
            
            # 🚨 จุดที่แก้ไข: ต้องสร้างปุ่มก่อน แล้วค่อยผูกฟังก์ชัน callback 
            back_btn = discord.ui.Button(label="🔙 ย้อนกลับ", style=discord.ButtonStyle.secondary)
            back_btn.callback = self.back_callback
            self.add_item(back_btn)
            
        except Exception as e:
            print(f"ERROR: [ร้านค้า] โหลดหน้าซื้อล้มเหลว: {e}")

    # 🛒 แก้ไขระบบซื้อ
    async def buy_callback(self, interaction: discord.Interaction):
        # 🛡️ 1. สั่ง Defer ทันทีที่กดปุ่ม
        await interaction.response.defer()
        
        item_id = str(interaction.data["custom_id"])
        player = player_model.get_player(self.user_id)
        item_data = ITEM_CONFIG.get(item_id)
        
        if not item_data:
            return await interaction.followup.send("❌ ไอเทมนี้ไม่มีอยู่ในระบบ!", ephemeral=True)

        price = item_data["buy"]
        
        # 🛡️ เช็กเงิน
        if player["cash"] < price:
            await interaction.followup.send("❌ เงินไม่พอ!", ephemeral=True)
            return
        
        # 🛡️ เช็กว่าขายได้ไหม
        if not item_data.get("purchasable", True):
            await interaction.followup.send("❌ ไอเทมนี้ไม่สามารถซื้อจากร้านค้าได้!", ephemeral=True)
            return

        # 🧹 ดึงข้อมูลกระเป๋าและถอดรหัส
        raw_inv = player.get("inventory", [])
        # ตรวจสอบรูปแบบข้อมูลกระเป๋า (ต้องเป็น List เท่านั้น)
        if isinstance(raw_inv, str):
            inv = raw_inv.split(",") if raw_inv else []
        elif isinstance(raw_inv, list):
            inv = raw_inv
        else:
            inv = []

        # 🛡️ 2. เช็กความจุ (Capacity) ก่อนซื้อ
        capacity = player.get("capacity", 10)
        # ถ้า capacity เป็น 0 คือไม่จำกัด (Unlimited)
        if capacity != 0 and len(inv) >= capacity:
            await interaction.followup.send(f"❌ กระเป๋าเต็มแล้ว! ({len(inv)}/{capacity}) กรุณาจัดการของในกระเป๋าก่อนซื้อเพิ่ม", ephemeral=True)
            return

        # 💰 ดำเนินการซื้อ (หักเงิน + เพิ่มไอเทม)
        inv.append(item_id)
        player["cash"] -= price
        
        # อัปเดตฐานข้อมูล
        player_model.update_player_field(self.user_id, "cash", player["cash"])
        player_model.update_player_field(self.user_id, "inventory", ",".join(inv)) # เก็บเป็น String คอมม่า
        
        # 🛠️ รีเฟรชข้อความร้านค้า
        # กรองเฉพาะไอเทมที่ซื้อได้มาแสดงผล
        market_list = [f"**เลข {k}:** {v['name']} ({v['buy']} ทอง)" for k, v in ITEM_CONFIG.items() if v.get("purchasable", True)]
        content = f"🛒 เลือกไอเทมที่ต้องการซื้อ: (เงินคงเหลือ: {player['cash']:,} ทอง)\n\n" + "\n".join(market_list)
        
        await interaction.edit_original_response(content=content, view=self)
        await interaction.followup.send(f"✅ ซื้อ {item_data['name']} เข้ากระเป๋าเรียบร้อย!", ephemeral=True)

    async def back_callback(self, interaction: discord.Interaction):
        await interaction.response.edit_message(view=ShopEventView(self.user_id))

# --- ระบบขาย ---
class SellSelectView(View):
    def __init__(self, user_id):
        super().__init__(timeout=None)
        self.user_id = user_id
        player = player_model.get_player(user_id)
        
        try:
            # 🛠️ ระบบกรองทำความสะอาดข้อมูลกระเป๋า
            raw_inv = player.get("inventory", "")
            clean_inv = str(raw_inv)
            for char in ["(", ")", "[", "]", "'", '"', " "]:
                clean_inv = clean_inv.replace(char, "")
                
            inv = clean_inv.split(",") if clean_inv and clean_inv not in ["None", "null"] else []
            
            unique_items = set(inv)
            
            for item_id in unique_items:
                if item_id in ITEM_CONFIG:
                    btn = discord.ui.Button(label=ITEM_CONFIG[item_id]["name"], custom_id=str(item_id))
                    btn.callback = self.sell_callback
                    self.add_item(btn)
                    
            back_btn = discord.ui.Button(label="🔙 ย้อนกลับ", style=discord.ButtonStyle.secondary)
            back_btn.callback = self.back_callback
            self.add_item(back_btn)
            
        except Exception as e:
            print(f"ERROR: [ร้านค้า] โหลดหน้าขายล้มเหลว: {e}")

    # 💰 แก้ไขระบบขาย
    async def sell_callback(self, interaction: discord.Interaction):
        # 🛡️ 1. สั่ง Defer ทันทีที่กดปุ่ม
        await interaction.response.defer()

        item_id = str(interaction.data["custom_id"])
        player = player_model.get_player(self.user_id)
        
        raw_inv = player.get("inventory", "")
        clean_inv = str(raw_inv)
        for char in ["(", ")", "[", "]", "'", '"', " "]:
            clean_inv = clean_inv.replace(char, "")
            
        inv = clean_inv.split(",") if clean_inv and clean_inv not in ["None", "null"] else []
        
        if item_id in inv:
            inv.remove(item_id)
            player["cash"] += ITEM_CONFIG[item_id]["sell"]
            
            player_model.update_player_field(self.user_id, "cash", player["cash"])
            player_model.update_player_field(self.user_id, "inventory", ",".join(inv))
            
            content = f"📦 เลือกไอเทมที่จะขาย: (เงินคงเหลือ: {player['cash']} ทอง)"
            # 🛡️ 2. เปลี่ยนมาใช้ edit_original_response
            await interaction.edit_original_response(content=content, view=SellSelectView(self.user_id))
            
            await interaction.followup.send(f"✅ ขาย {ITEM_CONFIG[item_id]['name']} แล้ว! ได้เงินมา {ITEM_CONFIG[item_id]['sell']} ทอง", ephemeral=True)
        else:
            await interaction.followup.send("❌ คุณไม่มีไอเทมชิ้นนี้ให้ขายแล้ว!", ephemeral=True)
            
    async def back_callback(self, interaction: discord.Interaction):
        await interaction.response.edit_message(view=ShopEventView(self.user_id))
        
# 3. เหตุการณ์ กล่องสมบัติ (Treasure)
class TreasureEventView(View):
    def __init__(self, user_id):
        super().__init__(timeout=60)
        self.user_id = user_id

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("❌ หีบสมบัตินี้ถูกค้นพบโดยคนอื่น! พิมพ์ `!play` เพื่อออกล่าหีบของตัวเองครับ", ephemeral=True)
            return False
        return True

    @discord.ui.button(label="📦 เปิดกล่องสมบัติ", style=discord.ButtonStyle.success)
    async def open_box(self, interaction: discord.Interaction, button: discord.ui.Button):
        player = player_model.get_player(self.user_id)
        
        # 🗡️ เช็กว่าผู้เล่นมีโรล Rogue หรือไม่
        is_rogue = any(role.name == "Rogue" for role in interaction.user.roles)
        
        # 🚨 แก้บั๊กทับซ้อน: คำนวณครั้งเดียว ถ้าเป็น Rogue is_trap จะเป็น False เสมอ
        is_trap = random.random() < 0.25 and not is_rogue

        if is_trap:
            player_model.update_player_field(self.user_id, "current_state", "idle")
            player_model.update_player_field(self.user_id, "last_event", "treasure_trap")
            
            # [ระบบเช็กไฟล์/แคช]
            # print(f"DEBUG: [Treasure] User {self.user_id} โดนกับดัก Mimic!")
            
            await interaction.response.edit_message(
                content="💥 **มันคือหีบกับดักมิมิก (Mimic)!** กลไกกับดักทำงานครอบงำคุณ! (ครั้งหน้าคุณจะเจอกับดักชัวร์ๆ 100%)\n----------------------------------------\nคุณต้องการไปต่อหรือไม่?", 
                view=AdventureView(author_id=self.user_id)
            )
        else:
            player_model.update_player_field(self.user_id, "current_state", "idle")
            player_model.update_player_field(self.user_id, "last_event", "treasure")
            
            # 🎁 สุ่มประเภทของรางวัล: เงิน (80%) หรือ ไอเทม (20%)
            # ปรับสัดส่วนตรง weights=[80, 20] ได้ตามความต้องการครับ
            reward_type = random.choices(["gold", "item"], weights=[80, 20], k=1)[0]

            if reward_type == "gold":
                gold = random.randint(50, 150)
                player_model.update_player_field(self.user_id, "cash", player["cash"] + gold)
                
                # print(f"DEBUG: [Treasure] User {self.user_id} เปิดได้เงิน {gold} ทอง")
                
                await interaction.response.edit_message(
                    content=f"🎉 โชคดีมาก! ด้านในเป็นหีบสมบัติแท้ คุณได้รับเงินสกุลกลาง `{gold}` ทอง!\n----------------------------------------\nคุณต้องการไปต่อหรือไม่?", 
                    view=AdventureView(author_id=self.user_id)
                )
            else:
                # 📦 กรณีโชคดีได้ไอเทมฟรี (ใช้ตรรกะออกยากตามราคาแบบเดียวกับ Shop)
                item_ids = list(ITEM_CONFIG.keys())
                weights = [1.0 / max(ITEM_CONFIG[i]["buy"], 1) for i in item_ids] 

                chosen_item_id = random.choices(item_ids, weights=weights, k=1)[0]
                chosen_item = ITEM_CONFIG[chosen_item_id]

                # 🛠️ ทำความสะอาดข้อมูลกระเป๋า (ทำให้เป็น List ที่มั่นคง)
                raw_inv = player.get("inventory", [])
                if isinstance(raw_inv, str):
                    # กรณีเป็น String (เช่น "15,12") หรือค่าว่าง
                    inv_array = raw_inv.split(",") if raw_inv and raw_inv not in ["None", "null"] else []
                else:
                    # กรณีเป็น List อยู่แล้ว
                    inv_array = raw_inv

                # กรองค่าว่างทิ้ง
                inv_array = [str(i).strip() for i in inv_array if str(i).strip()]

                # 🛡️ เช็กกระเป๋าเต็มก่อนรับของ
                capacity = player.get("capacity", 10)
                if capacity == 0 or len(inv_array) < capacity:
                    # กระเป๋ายังว่าง (หรือใส่ไม่จำกัด)
                    inv_array.append(str(chosen_item_id))
                    player_model.update_player_field(self.user_id, "inventory", ",".join(inv_array))
                    # inv_array.append(chosen_item_id)
                    # player_model.update_player_field(self.user_id, "inventory", ",".join(inv_array))
                    success_msg = (
                        f"🎉 แจ็คพอต!! หีบมี **{chosen_item['name']}** ซ่อนอยู่!\n"
                        f"✅ คุณเก็บไอเทมล้ำค่าชิ้นนี้เข้ากระเป๋าไปได้ฟรีๆ!"
                    )
                else:
                    # กระเป๋าเต็ม
                    success_msg = (
                        f"🎉 แจ็คพอต!! คุณเปิดหีบได้ **{chosen_item['name']}**!\n"
                        f"⚠️ **แต่กระเป๋าของคุณเต็ม ({len(inv_array)}/{capacity}) เลยเก็บไม่ได้!**\n"
                        f"👉 ลองพิมพ์ `!drop` เพื่อทิ้งของเก่า หรือขายของที่ร้านค้าในเมืองดูนะ!"
                    )

                await interaction.response.edit_message(
                    content=f"{success_msg}\n----------------------------------------\nคุณต้องการไปต่อหรือไม่?", 
                    view=AdventureView(author_id=self.user_id)
                )

    @discord.ui.button(label="❌ เมินเฉยและเดินผ่าน", style=discord.ButtonStyle.secondary)
    async def ignore(self, interaction: discord.Interaction, button: discord.ui.Button):
        player_model.update_player_field(self.user_id, "current_state", "idle")
        player_model.update_player_field(self.user_id, "last_event", "treasure")
        await interaction.response.edit_message(
            content="👀 คุณเลือกที่จะละสายตาจากกล่องและเดินผ่านไปเนิบๆ\n----------------------------------------\nคุณต้องการไปต่อหรือไม่?", 
            view=AdventureView(author_id=self.user_id)
        )

class QuestConfirmView(View):
    def __init__(self, user_id, requested_items, reward_item_id, reward_cash):
        super().__init__(timeout=60)
        self.user_id = user_id
        self.requested_items = requested_items # List ของไอเทมที่ NPC อยากได้
        self.reward_item_id = reward_item_id   # ไอเทมที่จะให้เป็นรางวัล (ถ้ามี)
        self.reward_cash = reward_cash         # เงินที่จะให้เป็นรางวัล

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("❌ ไม่ใช่ข้อเสนอของคุณ!", ephemeral=True)
            return False
        return True

    @discord.ui.button(label="✅ แลกเปลี่ยน", style=discord.ButtonStyle.success)
    async def accept(self, interaction: discord.Interaction, button: discord.ui.Button):
        player = player_model.get_player(self.user_id)
        inv_list = player_model.load_inventory(player.get("inventory", "[]"))

        # 1. เช็กให้ชัวร์อีกครั้งว่าของยังอยู่ครบ (เผื่อแอบเอาของไปเก็บ)
        has_all = True
        temp_inv = inv_list.copy()
        for item in self.requested_items:
            if item in temp_inv:
                temp_inv.remove(item)
            else:
                has_all = False
                break

        if not has_all:
            player_model.update_player_fields(self.user_id, {"current_state": "idle", "last_event": "npc"})
            return await interaction.response.edit_message(
                content="❌ ไอเทมในกระเป๋าของคุณไม่ครบตามที่ตกลงไว้! NPC โกรธและเดินหนีไป\n----------------------------------------\nคุณต้องการไปต่อหรือไม่?",
                view=AdventureView(author_id=self.user_id)
            )

        # 2. ลบของเก่าออก และยัดของรางวัลเข้ากระเป๋า
        inv_list = temp_inv
        if self.reward_item_id:
            inv_list.append(self.reward_item_id)

        # 3. อัปเดตเงินและบันทึกลงฐานข้อมูล
        new_cash = player.get("cash", 0) + self.reward_cash
        player_model.update_player_fields(self.user_id, {
            "inventory": ",".join(inv_list) if inv_list else "[]",
            "cash": new_cash,
            "current_state": "idle",
            "last_event": "npc"
        })

        await interaction.response.edit_message(
            content=f"🤝 **แลกเปลี่ยนสำเร็จ!** คุณได้รับของรางวัลและ NPC เดินจากไปอย่างมีความสุข\n----------------------------------------\nคุณต้องการไปต่อหรือไม่?",
            view=AdventureView(author_id=self.user_id)
        )

    @discord.ui.button(label="❌ ปฏิเสธ", style=discord.ButtonStyle.danger)
    async def decline(self, interaction: discord.Interaction, button: discord.ui.Button):
        player_model.update_player_fields(self.user_id, {"current_state": "idle", "last_event": "npc"})
        await interaction.response.edit_message(
            content="🙅‍♂️ คุณส่ายหัวปฏิเสธ NPC จึงเก็บของแล้วเดินจากไป\n----------------------------------------\nคุณต้องการไปต่อหรือไม่?",
            view=AdventureView(author_id=self.user_id)
        )

# 4. เหตุการณ์ เควส NPC
class NpcEventView(View):
    def __init__(self, user_id):
        super().__init__(timeout=60)
        self.user_id = user_id

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("❌ NPC กำลังสนทนากับนักผจญภัยท่านอื่นอยู่ รบกวนพิมพ์ `!play` แยกน้า", ephemeral=True)
            return False
        return True

    # ==========================================
    # ปุ่ม 1: พูดคุยปกติ (สุ่มให้เงิน / ขายของ / ไม่มีอะไร)
    # ==========================================
    @discord.ui.button(label="💬 เข้าไปพูดคุย", style=discord.ButtonStyle.primary)
    async def talk(self, interaction: discord.Interaction, button: discord.ui.Button):
        player = player_model.get_player(self.user_id)
        outcome = random.choice(["gift", "shop", "nothing"])
        
        player_model.update_player_field(self.user_id, "current_state", "idle")
        player_model.update_player_field(self.user_id, "last_event", "npc")

        if outcome == "gift":
            gold_gift = random.randint(30, 70)
            player_model.update_player_field(self.user_id, "cash", player["cash"] + gold_gift)
            await interaction.response.edit_message(
                content=f"🧓 NPC ถูกชะตาในตัวคุณ! เขาใจดีมอบเศษเงินทุนกลางจำนวน `{gold_gift}` ทองให้ฟรี!\n----------------------------------------\nคุณต้องการไปต่อหรือไม่?", 
                view=AdventureView(author_id=self.user_id)
            )
            
        elif outcome == "shop":
            item_ids = list(ITEM_CONFIG.keys())
            weights = [1.0 / max(ITEM_CONFIG[i]["buy"], 1) for i in item_ids] 
            
            chosen_item_id = random.choices(item_ids, weights=weights, k=1)[0]
            chosen_item = ITEM_CONFIG[chosen_item_id]
            
            original_price = chosen_item["buy"]
            offered_price = random.randint(0, original_price * 2)
            
            inv_list = player_model.load_inventory(player.get("inventory", "[]"))
            capacity = player.get("capacity", 10) 

            if player["cash"] < offered_price:
                msg = f"🧓 NPC พ่อค้าเร่เสนอขาย **{chosen_item['name']}** ให้คุณในราคา `{offered_price:,}` ทอง!\n❌ **แต่เงินในกระเป๋าของคุณไม่พอ!** NPC จึงเดินจากไป...\n----------------------------------------\nคุณต้องการไปต่อหรือไม่?"
            elif capacity != 0 and len(inv_list) >= capacity:
                msg = f"🧓 NPC พ่อค้าเร่เสนอขาย **{chosen_item['name']}** ในราคา `{offered_price:,}` ทอง!\n⚠️ **แต่กระเป๋าของคุณเต็ม!** NPC จึงเดินจากไป...\n----------------------------------------\nคุณต้องการไปต่อหรือไม่?"
            else:
                inv_list.append(chosen_item_id)
                new_cash = player["cash"] - offered_price
                player_model.update_player_field(self.user_id, "cash", new_cash)
                player_model.update_player_field(self.user_id, "inventory", ",".join(inv_list))
                
                price_text = f"`{offered_price:,}` ทอง" if offered_price > 0 else "**ฟรี!!**"
                msg = f"🧓 NPC พ่อค้าเร่เสนอขาย **{chosen_item['name']}** ในราคา {price_text}!\n✅ **คุณมีเงินและที่ว่างพอ จึงจ่ายเงินและรับของมาโดยอัตโนมัติ**\n----------------------------------------\nคุณต้องการไปต่อหรือไม่?"

            await interaction.response.edit_message(content=msg, view=AdventureView(author_id=self.user_id))
            
        else:
            await interaction.response.edit_message(
                content="💤 NPC แค่บ่นพึมพำเรื่องฟ้าฝนชวนคุยแก้เหงาเฉยๆ ไม่มีอะไรเกิดขึ้น\n----------------------------------------\nคุณต้องการไปต่อหรือไม่?", 
                view=AdventureView(author_id=self.user_id)
            )

    # ==========================================
    # ปุ่ม 2: รับเควสแลกเปลี่ยน (Gacha Exchange)
    # ==========================================
    @discord.ui.button(label="📜 ฟังข้อเสนอเควส", style=discord.ButtonStyle.success)
    async def quest_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        player = player_model.get_player(self.user_id)
        inv_list = player_model.load_inventory(player.get("inventory", "[]"))

        if not inv_list:
            player_model.update_player_fields(self.user_id, {"current_state": "idle", "last_event": "npc"})
            return await interaction.response.edit_message(
                content="🧓 NPC มองกระเป๋าที่ว่างเปล่าของคุณแล้วส่ายหัว 'เจ้าไม่มีสิ่งใดที่ข้าต้องการเลย...' \n----------------------------------------\nคุณต้องการไปต่อหรือไม่?",
                view=AdventureView(author_id=self.user_id)
            )

        # 1. สุ่มหยิบของจากกระเป๋า (1 ชิ้น ถึง ทั้งหมด)
        num_items = random.randint(1, len(inv_list))
        requested_items = random.sample(inv_list, num_items)

        # จัดกลุ่มชื่อไอเทมให้แสดงผลสวยๆ (เช่น ไม้ x2, หิน x1)
        req_counts = {}
        for i in requested_items:
            req_counts[i] = req_counts.get(i, 0) + 1
        req_text = ", ".join([f"**{ITEM_CONFIG.get(i, {}).get('name', '???')}** x{c}" for i, c in req_counts.items()])

        # 2. คำนวณมูลค่าของที่ NPC ขอ
        req_value = sum([ITEM_CONFIG.get(i, {}).get("buy", 0) for i in requested_items])

        # 3. สุ่มมูลค่าตอบแทน 50% - 1000%
        reward_val = random.randint(int(req_value * 0.5), int(req_value * 2))

        # 4. หาไอเทมตอบแทน (ต้องมีมูลค่าไม่เกิน reward_val)
        valid_items = [i for i, data in ITEM_CONFIG.items() if 0 < data.get("buy", 0) <= reward_val]
        
        reward_item_id = None
        reward_item_val = 0
        if valid_items:
            reward_item_id = random.choice(valid_items)
            reward_item_val = ITEM_CONFIG[reward_item_id]["buy"]

        # 5. มูลค่าที่เหลือจ่ายเป็นเงิน
        reward_cash = reward_val - reward_item_val

        reward_text = f"`{reward_cash:,}` ทอง"
        if reward_item_id:
            reward_text = f"**{ITEM_CONFIG[reward_item_id]['name']}** และเงิน `{reward_cash:,}` ทอง"

        msg = (
            f"🧓 **NPC พ่อค้าลึกลับยื่นข้อเสนอสุดเร้าใจ!**\n\n"
            f"👇 **เขาต้องการ:**\n{req_text} (ประเมินมูลค่า: `{req_value:,}` ทอง)\n\n"
            f"🎁 **สิ่งที่จะนำมาแลกเปลี่ยน:**\n{reward_text} (มูลค่ารวม: `{reward_val:,}` ทอง)\n\n"
            f"คุณจะรับข้อเสนอนี้หรือไม่?"
        )

        # เปลี่ยนหน้าต่างไปยัง View ยืนยัน
        await interaction.response.edit_message(
            content=msg,
            view=QuestConfirmView(self.user_id, requested_items, reward_item_id, reward_cash)
        )

    # ==========================================
    # ปุ่ม 3: เมินใส่
    # ==========================================
    @discord.ui.button(label="🤫 เมินใส่", style=discord.ButtonStyle.secondary)
    async def ignore(self, interaction: discord.Interaction, button: discord.ui.Button):
        player_model.update_player_fields(self.user_id, {"current_state": "idle", "last_event": "npc"})
        await interaction.response.edit_message(
            content="🤫 คุณแกล้งทำเป็นมองไม่เห็นและเดินผ่าน NPC ไปอย่างรวดเร็ว\n----------------------------------------\nคุณต้องการไปต่อหรือไม่?", 
            view=AdventureView(author_id=self.user_id)
        )


# 5. เหตุการณ์ ดันเจี้ยน (Dungeon)
class DungeonEventView(View):
    def __init__(self, user_id):
        super().__init__(timeout=60)
        self.user_id = user_id

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("❌ นี่คือทางเข้าดันเจี้ยนของนักผจญภัยเจ้าของคำสั่งเท่านั้นครับ!", ephemeral=True)
            return False
        return True

    @discord.ui.button(label="🚪 บุกเข้าดันเจี้ยน", style=discord.ButtonStyle.danger)
    async def enter(self, interaction: discord.Interaction, button: discord.ui.Button):
        player_model.update_player_field(self.user_id, "current_state", "idle")
        player_model.update_player_field(self.user_id, "last_event", "dungeon_inside") 
        player_model.update_player_field(self.user_id, "dungeon_steps", 10) 
        await interaction.response.edit_message(
            content="💀 คุณก้าวเท้าเข้าสู่ประตูดันเจี้ยนสุดมืดมิด! มีไอชั่วร้ายแผ่ออกมา... ต่อจากนี้คุณต้องสู้กับมอนสเตอร์ต่อเนื่อง 10 ตา!\n----------------------------------------\nคุณต้องการเริ่มสำรวจ (ไปต่อ) หรือไม่?", 
            view=AdventureView(author_id=self.user_id)
        )

    @discord.ui.button(label="🏃 ไม่เข้าดีกว่า", style=discord.ButtonStyle.secondary)
    async def leave(self, interaction: discord.Interaction, button: discord.ui.Button):
        player_model.update_player_field(self.user_id, "current_state", "idle")
        player_model.update_player_field(self.user_id, "last_event", "dungeon")
        await interaction.response.edit_message(
            content="🏃 ปลอดภัยไว้ก่อน คุณตัดสินใจเดินหันหลังกลับช้าๆ\n----------------------------------------\nคุณต้องการไปต่อหรือไม่?", 
            view=AdventureView(author_id=self.user_id)
        )


# 6. เหตุการณ์ กับดัก (Trap)
class TrapEventView(View):
    def __init__(self, user_id, member_roles):
        super().__init__(timeout=60)
        self.user_id = user_id
        self.member_roles = member_roles

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("❌ กับดักนี้ดีดใส่ตัวละครอื่นอยู่! ตัวเองรอดแล้วอย่ามากดแทนเพื่อนน้าา", ephemeral=True)
            return False
        return True

    @discord.ui.button(label="🎲 ทอยเต๋าหลบกับดัก", style=discord.ButtonStyle.primary)
    async def dodge(self, interaction: discord.Interaction, button: discord.ui.Button):
        # 1. แจ้ง Discord ว่าบอทได้รับคำสั่งแล้วทันที (กัน Interaction ล้มเหลว)
        await interaction.response.defer()

        player = player_model.get_player(self.user_id)
        # ป้องกันกรณี player ไม่มีข้อมูล (เช่น พิมพ์ !play แล้วไม่อยู่ใน DB)
        if not player:
            await interaction.followup.send("❌ ไม่พบข้อมูลตัวละครของคุณ!", ephemeral=True)
            return

        is_rogue = any(role.name == "Rogue" for role in self.member_roles)
        # อัปเดตสถานะพื้นฐาน
        player_model.update_player_field(self.user_id, "current_state", "idle")
        player_model.update_player_field(self.user_id, "last_event", "trap")
        if is_rogue:
            await interaction.edit_original_response(
                content="💨 **พรสวรรค์คลาส Rogue ทำงาน!** คุณกระโดดม้วนตัวหลบกลไกกับดักพ้นได้อย่างงดงาม 100%!\n----------------------------------------\nคุณต้องการไปต่อหรือไม่?", 
                view=AdventureView(author_id=self.user_id)
            )
            return

        # แก้บรรทัดเดิมของคุณอาเธอร์เป็นชุดนี้ครับ:
        armor_key = player.get("armor", "None")
        armor_data = ARMOR_STATS.get(armor_key)
        
        # ถ้าหาเกราะไม่เจอ ให้ใช้ "None" เป็นค่าเริ่มต้น
        if not armor_data:
            armor_data = ARMOR_STATS["None"]

        armor_evasion = armor_data.get("eva", 0) 
        
        roll_chance = random.randint(1, 100)
        
        if roll_chance <= armor_evasion:
            await interaction.edit_original_response(
                content=f"🎉 รอดหวุดหวิด! (เต๋าสุ่ม {roll_chance} vs อัตราเกราะ {armor_evasion}%) คุณก้าวขาหลบใบมีดกับดักพ้นสำเร็จ!\n----------------------------------------\nคุณต้องการไปต่อหรือไม่?", 
                view=AdventureView(author_id=self.user_id)
            )
        else:
            damage = random.randint(15, 35)
            new_hp = max(0, player["hp"] - damage)
            
            # คำนวณความเสื่อมสภาพเกราะ
            current_armor_dur = player.get("armor_dur", 0)
            if current_armor_dur > 0:
                damage_to_armor = max(1, int(damage / 10))
                new_armor_dur = max(0, current_armor_dur - damage_to_armor)
            else:
                damage_to_armor = 0
                new_armor_dur = 0
            
            # 💾 อัปเดตข้อมูลแยกบรรทัด เพื่อความปลอดภัย (ใช้ update_player_field แบบเดิม)
            player_model.update_player_field(self.user_id, "hp", new_hp)
            player_model.update_player_field(self.user_id, "armor_dur", new_armor_dur)
            
            # 🚨 เช็กว่าเกราะพังหรือไม่
            # armor_alert = "\n🚨 **ชุดเกราะของคุณพังยับเยินจากกับดัก!**" if (new_armor_dur == 0 and current_armor_dur > 0) else ""

            await interaction.edit_original_response(
                content=f"💥 พลาดท่ากระแทกกับดัก! โดนหนามแทงเสีย HP `- {damage}` หน่วย! (เลือดคงเหลือ: {new_hp})\n----------------------------------------\nคุณต้องการไปต่อหรือไม่?", 
                view=AdventureView(author_id=self.user_id)
        )


# 🏥 VIEW พิเศษ: ฟื้นคืนชีพเมื่อผู้เล่นหมดสติ (Respawn System)
class RespawnView(View):
    def __init__(self, user_id):
        super().__init__(timeout=60)
        self.user_id = user_id

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("❌ วิญญาณนี้ไม่ใช่ของคุณ! ปล่อยให้เจ้าตัวเขากดฟื้นตัวเองนะครับ", ephemeral=True)
            return False
        return True

    @discord.ui.button(label="🏥 ฟื้นตัวและกลับหมู่บ้าน", style=discord.ButtonStyle.green)
    async def respawn(self, interaction: discord.Interaction, button: discord.ui.Button):
        player = player_model.get_player(self.user_id)
        player_level = player.get("level", 0)
        respawn_hp = int(player["max_hp"] * 0.3)
        # 🛠️ คำนวณค่าธรรมเนียมชุบชีวิตตามเลเวล
        if player_level >= 100:
            penalty_fee = 10000  # เลเวล 100+ จ่ายหนักสุด
        elif player_level >= 90:
            penalty_fee = 5000   # เลเวล 90-99
        elif player_level >= 50:
            penalty_fee = 2500   # เลเวล 50-89
        elif player_level >= 20:
            penalty_fee = 1000    # เลเวล 20-49
        elif player_level >= 10:
            penalty_fee = 500    # เลเวล 10-19
        else:
            penalty_fee = 0      # เลเวล 0-9 ชุบฟรี! (ช่วยเหลือผู้เล่นใหม่)

        new_cash = player.get("cash", 0) - penalty_fee
        
        player_model.update_player_field(self.user_id, "hp", respawn_hp)
        player_model.update_player_field(self.user_id, "cash", new_cash) 
        player_model.update_player_field(self.user_id, "current_state", "village")
        player_model.update_player_field(self.user_id, "last_event", "village")
        player_model.update_player_field(self.user_id, "dungeon_steps", 0) 

        cash_status = f"`{new_cash}` ทอง" if new_cash >= 0 else f"`{new_cash}` ทอง ⚠️ (คุณกำลังติดหนี้สมาคมนักผจญภัย!)"

        await interaction.response.edit_message(
            content=f"😇 **ปาฏิหาริย์!** มีนักเดินทางใจดีช่วยแบกร่างอันหมดสติของคุณมาส่งที่ **'หมู่บ้านอุ่นใจ'**...\n"
                    f"🩸 คุณฟื้นตัวขึ้นมาพร้อมพลังชีวิตเบื้องต้น `❤️ {respawn_hp}` หน่วย\n"
                    f"💸 เสียค่าธรรมเนียมชุบชีวิตและย้ายส่งโรงหมอ `- {penalty_fee}` ทอง (เงินคงเหลือปัจจุบัน: {cash_status})\n"
                    f"----------------------------------------\n"
                    f"ตอนนี้คุณอยู่ในหมู่บ้านแล้ว จะเอาอย่างไรต่อดี?",
            view=VillageEventView(self.user_id) 
        )


# 🧭 VIEW หลักในการเริ่มเดินทาง (!play)
class AdventureView(View):
    def __init__(self, author_id: int):
        super().__init__(timeout=60)
        self.author_id = author_id
        self.message = None # 💡 1. เพิ่มตัวแปรไว้เก็บข้อความเพื่อรอการ Edit

    # ==========================================
    # ⏰ ดักจับเวลาผู้เล่นไม่กดปุ่ม "เริ่มออกเดินทาง" ใน 1 นาที
    # ==========================================
    async def on_timeout(self):
        for item in self.children:
            item.disabled = True # ปิดปุ่ม
            
        if self.message:
            try:
                await self.message.edit(content="⏰ **หน้าต่างนี้หมดอายุแล้ว!** รบกวนพิมพ์คำสั่งผจญภัยเพื่อเรียกหน้าต่างใหม่นะครับ", view=self)
            except Exception:
                pass

    # ==========================================
    # ⚠️ ดักจับเวลาปุ่มพังฉุกเฉิน (Soft-lock safeguard)
    # ==========================================
    async def on_error(self, interaction: discord.Interaction, error: Exception, item: discord.ui.Item):
        print(f"🚨 ERROR [AdventureView]: {error}")
        
        # ปลดล็อกสถานะใน DB ทันที
        player_model.update_player_field(self.author_id, "current_state", "idle")
        err_msg = "⚠️ บอร์ดผจญภัยเกิดข้อผิดพลาด! ระบบได้รีเซ็ตสถานะของคุณให้กลับเป็นปกติแล้วครับ"
        
        if not interaction.response.is_done():
            await interaction.response.send_message(err_msg, ephemeral=True)
        else:
            await interaction.followup.send(err_msg, ephemeral=True)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.author_id:
            await interaction.response.send_message("❌ บอร์ดออกเดินทางนี้ไม่ใช่ของคุณ! รบกวนพิมพ์ `!play` เพื่อทริกเกอร์บอร์ดของตัวเองนะครับ", ephemeral=True)
            return False
        return True

    @discord.ui.button(label="🧭 เริ่มออกเดินทาง", style=discord.ButtonStyle.green)
    async def start_adv(self, interaction: discord.Interaction, button: discord.ui.Button):
        user_id = interaction.user.id
        player = player_model.get_player(user_id)

        if player["current_state"] != "idle":
            await interaction.response.send_message("⚠️ คุณกำลังติดเหตุการณ์อื่นอยู่!", ephemeral=True)
            return

        await interaction.response.edit_message(content="✨ คุณเริ่มก้าวเท้าออกเดินทางตรวจตราเส้นทาง...", view=None)

        current_cooldown = player.get("village_cooldown", 0)
        if current_cooldown > 0:
            current_cooldown -= 1
            player_model.update_player_field(user_id, "village_cooldown", current_cooldown)

        # 1. ดึงข้อมูล
        dg_steps = player.get("dungeon_steps", 0)
        last_evt = player.get("last_event", "none")

        # 2. จัดลำดับความสำคัญ (Priority Order)
        
        # [Priority 1: วาปกลับเมือง] - สำคัญที่สุด ต้องทำก่อนเสมอ
        if last_evt == "warp_village":
            chosen_event = "village"
            dg_steps = 0  # รีเซ็ตดันเจี้ยนทิ้งทันที
            player_model.update_player_field(user_id, "dungeon_steps", 0)
            
        # [Priority 2: สแกนกล่องสมบัติ] - อยู่ในดันเจี้ยนได้ แต่ไม่ลบเทิร์น
        elif last_evt == "scan_box":
            chosen_event = "treasure"
            # ไม่มีการลบ dg_steps
            
        # [Priority 3: เช็กสถานะอยู่ในดันเจี้ยน หรือ ใช้ใบเรียกบอส]
        # เงื่อนไข: ถ้าอยู่ในดันเจี้ยน (dg_steps > 0) หรือ ใช้ใบเรียกบอส
        elif dg_steps > 0 or last_evt in ["mini_summon", "main_summon", "unbeatable_summon"]:
            
            # ดักเคส: ถ้าอยู่ในดันเจี้ยน ห้ามใช้ warp_dungeon (Error/Block ไว้)
            if dg_steps > 0 and last_evt == "warp_dungeon":
                chosen_event = "monster" # บังคับสู้ต่อ
            else:
                chosen_event = "monster"
            
            # ถ้าอยู่ในดันเจี้ยน และเป็นเหตุการณ์มอนสเตอร์ ให้ลบเทิร์น
            if dg_steps > 0:
                dg_steps = max(0, dg_steps - 1)
                player_model.update_player_field(user_id, "dungeon_steps", dg_steps)

        # [Priority 4: เหตุการณ์พิเศษอื่นๆ ที่ไม่มีผลกับดันเจี้ยน]
        elif last_evt == "treasure_trap":
            chosen_event = "trap"
        elif last_evt == "revive":
            chosen_event = "village"
        elif last_evt == "warp_dungeon":
            # กรณีวาปเข้าดันเจี้ยน (เข้าได้เฉพาะตอนอยู่นอกดันเจี้ยน)
            chosen_event = "dungeon"

        # [Priority 5: สุ่มปกติ]
        else:
            if last_evt not in EVENT_WEIGHTS: 
                last_evt = "none"
            current_weights = list(EVENT_WEIGHTS[last_evt])
            if current_cooldown > 0:
                current_weights[1] = 0 
            chosen_event = random.choices(EVENT_LIST, weights=current_weights, k=1)[0]

        summon_events = ["mini_summon", "main_summon", "unbeatable_summon"]
        # 4. อัปเดต last_event
        if chosen_event == "monster" and last_evt in summon_events:
            pass # ไม่ต้องทำอะไร ปล่อย last_event เป็นค่าเรียกบอสเหมือนเดิม
        else:
            # ถ้าเป็นเหตุการณ์อื่นๆ ให้บันทึกลงฐานข้อมูลตามปกติ
            player_model.update_player_field(user_id, "last_event", chosen_event)
        
        if chosen_event == "village":
            player_model.update_player_field(user_id, "village_cooldown", 10)


        # ==========================================
        # 🛠️ จุดที่แก้ไข: ท่าส่งข้อความแบบฝัง Timeout ให้เหตุการณ์ถัดไป
        # ==========================================
        if chosen_event == "monster":
            player_model.update_player_field(user_id, "current_state", "fighting")
            status_msg = f"*(เหลืออีก {dg_steps} ตาในดันเจี้ยน)*" if dg_steps > 0 or player.get("dungeon_steps", 0) > 0 else f"*(คูลดาวน์หมู่บ้านเหลือ: {current_cooldown} ตา)*"
            
            # สร้าง View -> ส่งข้อความรอรับค่า -> ยัดข้อความกลับเข้า View
            next_view = MonsterEventView(user_id, interaction.user.roles)
            sent_msg = await interaction.followup.send(content=f"👹 มีเงาปริศนาพุ่งออกมากระโจนขวางทางคุณ! เลือกแอคชั่นหรือคลาสสกิลของคุณ: {status_msg}", view=next_view, wait=True)
            next_view.message = sent_msg
            
        elif chosen_event == "village":
            player_model.update_player_field(user_id, "current_state", "village")
            
            next_view = VillageEventView(user_id)
            sent_msg = await interaction.followup.send(content="🏡 คุณเดินทางมาพบ **'หมู่บ้านอุ่นใจ'** เลือกแอคชั่นของคุณ:", view=next_view, wait=True)
            next_view.message = sent_msg

        elif chosen_event == "treasure":
            player_model.update_player_field(user_id, "current_state", "treasure_choice")
            
            next_view = TreasureEventView(user_id)
            sent_msg = await interaction.followup.send(content=f"📦 คุณพบ **'หีบสมบัติปริศนาลงอักขระโบราณ'** เลือกแอคชั่นของคุณ: *(คูลดาวน์หมู่บ้านเหลือ: {current_cooldown} ตา)*", view=next_view, wait=True)
            next_view.message = sent_msg

        elif chosen_event == "npc":
            player_model.update_player_field(user_id, "current_state", "npc_choice")
            
            next_view = NpcEventView(user_id)
            sent_msg = await interaction.followup.send(content=f"🧓 คุณเจอนักเดินทางพเนจร (NPC) นั่งอยู่ข้างกองไฟ เลือกแอคชั่นของคุณ: *(คูลดาวน์หมู่บ้านเหลือ: {current_cooldown} ตา)*", view=next_view, wait=True)
            next_view.message = sent_msg

        elif chosen_event == "dungeon":
            player_model.update_player_field(user_id, "current_state", "dungeon_choice")
            
            next_view = DungeonEventView(user_id)
            sent_msg = await interaction.followup.send(content=f"💀 คุณส่องเห็น **'ช่องอุโมงค์ถ้ำใต้พิภพ (Dungeon)'** เลือกแอคชั่นของคุณ: *(คูลดาวน์หมู่บ้านเหลือ: {current_cooldown} ตา)*", view=next_view, wait=True)
            next_view.message = sent_msg

        elif chosen_event == "trap":
            player_model.update_player_field(user_id, "current_state", "trap_defense")
            
            next_view = TrapEventView(user_id, interaction.user.roles)
            sent_msg = await interaction.followup.send(content=f"⚠️ *แก๊ก!* คุณพลาดก้าวขาไปเกี่ยวสายสลิง **'กับดักโบราณ'** เข้าให้แล้ว! เตรียมรับมือแอคชั่นหลบหลีก: *(คูลดาวน์หมู่บ้านเหลือ: {current_cooldown} ตา)*", view=next_view, wait=True)
            next_view.message = sent_msg