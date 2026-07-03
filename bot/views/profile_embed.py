# profile_embed.py
import discord
import models.player_model as player_model

# ─── 🧬 คลังข้อมูลเผ่าพันธุ์ (สลักชื่อตรงตามยศในเซิร์ฟเวอร์ดิสคอร์ด 100%) ───
GAME_RACES = [
    "、👲🏻 • มนุษย์",
    "、 🧝🏻‍♂️ • เอลฟ์",
    "、👹 • ยักษ์",     
    "、🚶🏽 • คนแคระ",
    "、🐉 • มังกร",
    "、🧚 • ภูติ",
    "、🧜🏼‍♀️ • เงือก",
    "、🐾 • เผ่ามิ้ง"
]

# 👹 คลังยศฝ่ายปีศาจ/มอนสเตอร์ (อ้างอิงตรงตามยศในเซิร์ฟเวอร์ดิสคอร์ด 100%)
MONSTER_RACES = [
    "• Dragon 🐉",
    "• Unicon 🦄",
    "•  Slime 🪼⋆",
    "• Ogre 👹",
    "• Orc 🧌",
    "• Goblins🧝",
    "• Lich 🧙🏽‍♂️",
    "•  Skeleton 🦴",
    "•  Zombie🧟"
]

GAME_CLASSES = ["Warrior", "Mage", "Rogue", "Cleric"]

TEAMWORK_CLASSES = ["꒰ PL ꒱ อัศวิน ⚔️", "꒰ DT ꒱ นักบวช .⋆♱", "꒰ PR ꒱ ผู้ส่งสาร", "꒰ EN ꒱ นักกวี 𝄞⋆"]
# บัพพาสซีพทีมงาน 
# อัศวิน ลูกเต่าเพิ่ม 2 ลูก 
# นักบวช เลอดต่ำกว่า 50 % เพิ่มเลือด 25%
# ผู้ส่งสาร เพิ่มโอกาสหลบหลีก 15% และเพิ่ม gold ที่ได้รับจากการพิมแชท 100%
# นักกวี เพิ่มโอกาสหลบหลีก 15% และเพิ่ม EXP ที่ได้รับจากการพูดคุยในห้องเสียงอีก 100%

CLASS_SKILLS = {
    "Warrior": ["🛡️ Shield Bash", "⚔️ Heavy Strike"],
    "Mage": ["🔥 Fireball", "❄️ Frostbolt"],
    "Rogue": ["🗡️ Backstab", "💨 Evasion"],
    "Cleric": ["✨ Heal", "🛡️ Holy Aura"],
    "Unknown": ["❓ ไม่มีสกิล (กรุณารับยศคลาสอาชีพก่อน)"]
}

# ข้อมูลเกราะ (เพิ่ม Visibility และ Max Durability)
ARMOR_STATS = {
    "None":      {"name": "👕 เสื้อผ้าธรรมดา", "hp": 0,   "eva": 85, "dur": 100, "vis": 1},
    "Leather_L": {"name": "🟫 เกราะหนังเบา",   "hp": 20,  "eva": 70, "dur": 150, "vis": 3},
    "Leather_H": {"name": "🟫 เกราะหนังหนัก",  "hp": 30,  "eva": 60, "dur": 200, "vis": 5},
    "Steel_L":   {"name": "⬜ เกราะเหล็กเบา",  "hp": 50,  "eva": 40, "dur": 300, "vis": 7},
    "Steel_H":   {"name": "⬜ เกราะเหล็กหนัก", "hp": 100, "eva": 20, "dur": 500, "vis": 9}
}

# ข้อมูลอาวุธ
WEAPON_STATS = {
    "Wooden_Weapon": {"name": "🪵 อาวุธไม้",     "atk": 10, "dur": 50},
    "Iron_Weapon":   {"name": "⚔️ อาวุธเหล็ก",   "atk": 30, "dur": 150},
    "Legen_Weapon":  {"name": "🗡️ อาวุธในตำนาน", "atk": 999, "dur": 1000}
}

# ข้อมูลกระเป๋า
BAG_STATS = {
    "Small_Bag": {"name": "🎒 กระเป๋าเล็ก", "capacity": 10},
    "Medium_Bag": {"name": "🎒 กระเป๋ากลาง", "capacity": 50},
    "Large_Bag": {"name": "🎒 กระเป๋าใหญ่", "capacity": 100},
    "Magic_Bag": {"name": "🎒 กระเป๋าเวทมนตร์", "capacity": 0}
}

ITEM_CONFIG = {
    # --- ไอเทมกดใช้ (Consumables) ---
    "1": {"name": "💉 ยาฮีล", "buy": 300, "sell": 100, "type": "use"}, 
    "2": {"name": "🛠️ ใบซ่อมแซม", "buy": 500, "sell": 150, "type": "use"}, 
    
    # --- หมวดชุดเกราะ (Armors) - ปรับราคาให้มีความก้าวหน้า ---
    "3": {"name": "🟫 เกราะหนังเบา", "buy": 1000, "sell": 300, "type": "armor", "equip_key": "Leather_L"},
    "4": {"name": "🟫 เกราะหนังหนัก", "buy": 3000, "sell": 900, "type": "armor", "equip_key": "Leather_H"},
    "5": {"name": "⬜ เกราะเหล็กเบา", "buy": 8000, "sell": 2400, "type": "armor", "equip_key": "Steel_L"},
    "6": {"name": "⬜ เกราะเหล็กหนัก", "buy": 20000, "sell": 6000, "type": "armor", "equip_key": "Steel_H"},
    
    # ---   ป (Weapons) ---
    "7": {"name": "⚔️ อาวุธเหล็ก", "buy": 6000, "sell": 1800, "type": "weapon", "equip_key": "Iron_Weapon"},
    "8": {"name": "🗡️ อาวุธในตำนาน", "buy": 9999999, "sell": 1, "type": "weapon", "equip_key": "Legen_Weapon"},

    # --- หมวดไอเทมขยะ (Junk) 
    "9": {"name": "🦴 เศษกระดูก", "buy": 100, "sell": 10, "type": "junk", "purchasable": False},
    "10": {"name": "🕸️ ใยแมงมุม", "buy": 150, "sell": 15, "type": "junk", "purchasable": False},
    "11": {"name": "💎 เศษอัญมณีหมองหม่น", "buy": 500, "sell": 50, "type": "junk", "purchasable": False},
    "12": {"name": "🪨 เศษหิน", "buy": 50, "sell": 5, "type": "junk", "purchasable": False},
    "13": {"name": "🪵 เศษไม้", "buy": 30, "sell": 3, "type": "junk", "purchasable": False},
    "14": {"name": "🧪 ขวดสารเคมี", "buy": 200, "sell": 20, "type": "junk", "purchasable": False},
    "15": {"name": "🧵 เศษด้าย", "buy": 20, "sell": 2, "type": "junk", "purchasable": False},
    "16": {"name": "🪶 ขนนก", "buy": 40, "sell": 4, "type": "junk", "purchasable": False},
    "17": {"name": "🪙 เหรียญเก่า", "buy": 100, "sell": 10, "type": "junk", "purchasable": False},
    "18": {"name": "🧱 ก้อนอิฐ", "buy": 60, "sell": 6, "type": "junk", "purchasable": False},

    # --- หมวดกระเป๋า (Bag) ---
    "19": {"name": "👜 กระเป๋ากลาง", "buy": 15000, "sell": 3000, "type": "bag", "equip_key": "Medium_Bag"},
    "20": {"name": "👜 กระเป๋าใหญ่", "buy": 40000, "sell": 8000, "type": "bag", "equip_key": "Large_Bag"},
    "21": {"name": "🌌 กระเป๋าเวทมนตร์", "buy": 9999999, "sell": 1, "type": "bag", "equip_key": "Magic_Bag"},

    # --- หมวดไอเทมกดใช้เวทมนตร์ (Consumables Magic) ---
    "22": {"name": "📜ใบวาปเมือง", "buy": 500, "sell": 50, "type": "drop", "purchasable": False},
    "23": {"name": "🔑กุญแจวาปดันเจี้ยน", "buy": 2000, "sell": 200, "type": "drop", "purchasable": False},
    "24": {"name": "📃ใบเชิญมินิบอส", "buy": 8000, "sell": 1, "type": "drop", "purchasable": False},
    "25": {"name": "📃ใบเชิญบอสหลัก", "buy": 35000, "sell": 1, "type": "drop", "purchasable": False},
    "26": {"name": "📃ใบเชิญบอสไร้พ่าย", "buy": 80000, "sell": 1, "type": "drop", "purchasable": False},
    "27": {"name": "📡เรดาร์สแกนกล่องสมบัติ", "buy": 3000, "sell": 300, "type": "drop", "purchasable": False},
    "28": {"name": "💌ใบชุบชีวิต", "buy": 5000, "sell": 500, "type": "drop", "purchasable": False},
}

CRAFTING_RECIPES = {
    # 💉 ยาฮีล (1): โอกาสล้มเหลว 10%
    "1": {"recipe": {"9": 2, "12": 1}, "fail_rate": 0.1},
    # 🛠️ ใบซ่อมแซม (2): โอกาสล้มเหลว 15%
    "2": {"recipe": {"18": 1, "14": 1}, "fail_rate": 0.15},
    # 🟫 เกราะหนังเบา (3): โอกาสล้มเหลว 25% (ยากขึ้น)
    "3": {"recipe": {"15": 5, "10": 3}, "fail_rate": 0.25},
    # ⚔️ อาวุธเหล็ก (7): โอกาสล้มเหลว 40% (ยากมาก)
    "7": {"recipe": {"9": 5, "11": 1}, "fail_rate": 0.4},
}
CRAFTING_RECIPES.update({
    # --- ไอเทมกดใช้เวทมนตร์ (Consumables Magic) ---
    # 22: ใบวาปเมือง (ราคา 500) - คราฟง่าย
    "22": {"recipe": {"9": 3, "12": 2}, "fail_rate": 0.05},
    # 23: กุญแจวาปดันเจี้ยน (ราคา 2000) - เริ่มใช้ของเคมี
    "23": {"recipe": {"14": 2, "13": 3}, "fail_rate": 0.15},
    # 24: ใบเชิญมินิบอส (ราคา 8000) - ต้องใช้เกราะหนังเบาด้วย
    "24": {"recipe": {"11": 1, "14": 3, "3": 1}, "fail_rate": 0.25},
    # 25: ใบเชิญบอสหลัก (ราคา 35000) - ต้องใช้เงินและของแรร์
    "25": {"recipe": {"11": 3, "7": 1, "14": 5}, "fail_rate": 0.4},
    # 26: ใบเชิญบอสไร้พ่าย (ราคา 80000) - โหดที่สุด
    "26": {"recipe": {"11": 5, "6": 1, "27": 1}, "fail_rate": 0.6},
    # 27: เรดาร์สแกนกล่อง (ราคา 3000) - ใช้เศษหินและเคมี
    "27": {"recipe": {"14": 3, "12": 5}, "fail_rate": 0.2},
    # 28: ใบชุบชีวิต (ราคา 5000) - ใช้กระดูกและอัญมณี
    "28": {"recipe": {"9": 10, "11": 2}, "fail_rate": 0.3},
})

def create_profile_embed(target_member, player_data):
    player_level = player_data.get("level", 1)
    rank = player_data.get("rank", "None")
    
    # 🛡️ ดึงข้อมูลอุปกรณ์
    armor_key = player_data.get("armor", "None")
    weapon_key = player_data.get("weapon", "Wooden_Weapon")
    
    # ตรวจสอบความถูกต้องของ Key
    armor_info = ARMOR_STATS.get(armor_key, ARMOR_STATS["None"])
    weapon_info = WEAPON_STATS.get(weapon_key, WEAPON_STATS["Wooden_Weapon"])
    
    # คำนวณ HP รวม (ใช้ค่า 'hp' จากตารางใหม่)
    total_max_hp = player_data.get("max_hp", 100)
    current_hp = min(player_data.get("hp", 100), total_max_hp)

    #ดึงค่าสติ
    sanity = player_data.get("sanity", 100)

    detected_race = "ไม่ระบุเผ่า"
    detected_class = "ไม่ระบุอาชีพ"
    player_faction = "⏳ กำลังระบุฝ่าย"
    
    # ➕ เพิ่มตัวแปรสำหรับเก็บรายชื่อเผ่าที่เจอ และตัวนับจำนวนเผ่า
    found_races = []

    # 🔍 ลูปเช็กยศของสมาชิกเพื่อระบุ เผ่าพันธุ์, อาชีพ และ ฝ่าย สังกัด
    for role in target_member.roles:
        if role.name in GAME_RACES:
            found_races.append(role.name)
            # เซ็ตค่าเริ่มต้นกรณีเจอเผ่าเดียวก่อน
            if len(found_races) == 1:
                detected_race = role.name
                player_faction = "🔵 ฝ่ายมนุษย์"
        elif role.name in MONSTER_RACES:
            found_races.append(role.name)
            # เซ็ตค่าเริ่มต้นกรณีเจอเผ่าเดียวก่อน
            if len(found_races) == 1:
                detected_race = role.name
                player_faction = "🔴 ฝ่ายปีศาจ"
        elif role.name in GAME_CLASSES:
            detected_class = role.name

    raw_inv = player_data.get("inventory", "[]")
    capacity = player_data.get("capacity", 10)
    
    # 2. ส่งค่า raw_inv เข้าฟังก์ชัน load_inventory เพื่อแปลงเป็น List
    # (ถ้า load_inventory อยู่ใน player_model ก็เรียก player_model.load_inventory)
    inv_list = player_model.load_inventory(raw_inv) 
    
    # 3. จัดการเรื่องแสดงผลความจุกระเป๋า (ใช้ Ternary ที่เราทำกันไว้)
    cap_display = 'ไม่จำกัด' if capacity == 0 else capacity

    # 🧬 [ระบบคำนวณลูกผสม] ถ้าเช็กแล้วพบว่ามียศเผ่าพันธุ์รวมกันตั้งแต่ 2 เผ่าขึ้นไป
    if len(found_races) >= 2:
        # ดึงเฉพาะชื่อสั้นมาโชว์คู่กัน เช่น เอลฟ์ + Slime
        short_names = [r.replace("、", "").replace("•", "").strip() for r in found_races]
        detected_race = f"ลูกผสม ({' + '.join(short_names)})"
        player_faction = "🟣 ฝ่ายอิสระ (ลูกผสม)"

    skills = CLASS_SKILLS.get(detected_class, CLASS_SKILLS["Unknown"])
    skills_text = "\n".join(skills)

    embed = discord.Embed(title=f"👤 ข้อมูลตัวละคร: {target_member.display_name}", color=0x9b59b6)
    embed.set_thumbnail(url=target_member.display_avatar.url)
    
    # 📊 สเตตัสหลัก
    embed.add_field(name="🎯 เลเวล", value=f"⭐ Lv. {player_level} ({rank})", inline=True)
    embed.add_field(name="🩸 พลังชีวิตรวม", value=f"❤️ {current_hp}/{total_max_hp} *(+{armor_info['hp']})*", inline=True)
    embed.add_field(name="💰 เงินสด", value=f"🪙 {player_data.get('cash', 0)} ทอง", inline=True)
    
    # 🧬 เผ่าพันธุ์ & อาชีพ
    embed.add_field(name="🧬 เผ่าพันธุ์", value=f"🟢 {detected_race}\n\n\n\n👑 **{player_faction} (สติ {sanity})**", inline=True)
    embed.add_field(name="⚔️ คลาสอาชีพ", value=f"🔵 {detected_class}", inline=True)
 
    embed.add_field(name="​", value="​", inline=False) 

    # 🛡️ อุปกรณ์ & ความทนทาน (เพิ่มอาวุธและความทนทาน)
    embed.add_field(name="⚔️ อาวุธที่ถือ", value=f"**{weapon_info['name']}**\nความทนทาน: `{player_data.get('weapon_dur', 0)}/{weapon_info['dur']}`", inline=True)
    embed.add_field(name="🛡️ เกราะที่สวม", value=f"**{armor_info['name']}**\nความทนทาน: `{player_data.get('armor_dur', 0)}/{armor_info['dur']}`", inline=True)
    
    embed.add_field(
        name="🎒 กระเป๋าสัมภาระ", 
        value=f"บรรจุไอเทมอยู่: `{len(inv_list)} / {cap_display}` ชิ้น\n\n", 
        inline=False
    )

    # 💨 สถานะการป้องกัน/การซ่อนตัว
    embed.add_field(name="💨 หลบหลีก / 👁️ มองเห็น", value=f"🏃 {armor_info['eva']}% / ⚠️ ระดับ: {armor_info['vis']}", inline=False)
    
    # 🔥 สกิล
    embed.add_field(name="🔥 สกิลประจำคลาส", value=f"```\n{skills_text}\n```", inline=False)
    
    return embed
    
    return embed