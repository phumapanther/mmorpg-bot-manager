# profile_embed.py
import discord
import bot.models.player_model as player_model
from bot import config_loader
from bot import game_modifiers

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

CLASS_SKILLS = {
    "Warrior": ["🛡️ Shield Bash", "⚔️ Heavy Strike"],
    "Mage": ["🔥 Fireball", "❄️ Frostbolt"],
    "Rogue": ["🗡️ Backstab", "💨 Evasion"],
    "Cleric": ["✨ Heal", "🛡️ Holy Aura"],
    "Unknown": ["❓ ไม่มีสกิล (กรุณารับยศคลาสอาชีพก่อน)"]
}

def create_profile_embed(target_member, player_data, page="status"):
    """หน้าโปรไฟล์ (B2) — page: status / equip / progress"""
    player_level = player_data.get("level", 1)
    rank = player_data.get("rank", "None")
    
    # 🛡️ ดึงข้อมูลอุปกรณ์
    armor_key = player_data.get("armor", "None")
    weapon_key = player_data.get("weapon", "Wooden_Weapon")
    
    # ตรวจสอบความถูกต้องของ Key
    armor_info = config_loader.get_armor_stats(armor_key) or config_loader.get_armor_stats("None")
    weapon_info = config_loader.get_weapon_stats(weapon_key) or config_loader.get_weapon_stats("Wooden_Weapon")
    
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
    # 🧬 P8: ใช้ชื่อยศ "ที่มีผลจริง" — เซิร์ฟรองไม่มียศ ก็อ่านเผ่า/คลาสจาก DB มาแสดงแทน
    from bot import identity
    for role_name in identity.effective_role_names(target_member.roles, player_data):
        role = type("R", (), {"name": role_name})
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

    # 🎨 สีโปรไฟล์ส่วนตัว (ย้อมด้วยผงสีรุ้ง) — ไม่เคยย้อม = สีม่วงมาตรฐาน
    profile_color = player_data.get("profile_color") or 0x9b59b6
    page_title = {"status": "👤 สถานะตัวละคร", "equip": "🛡️ อุปกรณ์ & สกิล",
                  "progress": "📊 ความคืบหน้า"}.get(page, "👤 ข้อมูลตัวละคร")
    embed = discord.Embed(title=f"{page_title}: {target_member.display_name}", color=profile_color)
    embed.set_thumbnail(url=target_member.display_avatar.url)
    
    # 📊 สเตตัสหลัก
    embed.add_field(name="🎯 เลเวล", value=f"⭐ Lv. {player_level} ({rank})", inline=True)
    embed.add_field(name="🩸 พลังชีวิตรวม", value=f"❤️ {current_hp}/{total_max_hp} *(+{armor_info['hp']})*", inline=True)
    embed.add_field(name="💰 เงินสด", value=f"🪙 {player_data.get('cash', 0)} ทอง", inline=True)
    
    # 🧬 เผ่าพันธุ์ & อาชีพ
    embed.add_field(name="🧬 เผ่าพันธุ์", value=f"🟢 {detected_race}\n\n\n\n👑 **{player_faction} (สติ {sanity})**", inline=True)
    embed.add_field(name="⚔️ คลาสอาชีพ", value=f"🔵 {detected_class}", inline=True)
 
    # 🛡️ B2: อุปกรณ์/สกิล อยู่หน้า "อุปกรณ์" (กดปุ่มสลับ) — หน้าแรกเหลือเฉพาะสถานะตัวละคร
    if page == "equip":
        embed.add_field(name="⚔️ อาวุธที่ถือ", value=f"**{weapon_info['name']}**\nความทนทาน: `{player_data.get('weapon_dur', 0)}/{weapon_info['dur']}`", inline=True)
        embed.add_field(name="🛡️ เกราะที่สวม", value=f"**{armor_info['name']}**\nความทนทาน: `{player_data.get('armor_dur', 0)}/{armor_info['dur']}`", inline=True)
        embed.add_field(name="🎒 กระเป๋าสัมภาระ", value=f"บรรจุไอเทมอยู่: `{len(inv_list)} / {cap_display}` ชิ้น", inline=False)
        embed.add_field(name="💨 หลบหลีก / 👁️ มองเห็น", value=f"🏃 {armor_info['eva']}% / ⚠️ ระดับ: {armor_info['vis']}", inline=False)
        embed.add_field(name="🔥 สกิลประจำคลาส", value=f"```\n{skills_text}\n```", inline=False)
        return embed

    # ─── 🌍 โลก & ธาตุ & ของติดตัว (ระบบขยายใหญ่) ───
    continent_label = game_modifiers.get_continent(player_data)["label"]

    role_names = identity.effective_role_names(getattr(target_member, "roles", []), player_data)
    player_elements = game_modifiers.resolve_player_elements(role_names)
    if player_elements:
        element_labels = " ".join(game_modifiers.ELEMENTS[e]["label"] for e in player_elements)
        prey = sorted({t for e in player_elements for t in game_modifiers.ELEMENT_ADVANTAGE.get(e, [])})
        prey_labels = ", ".join(game_modifiers.ELEMENTS[t]["label"] for t in prey) if prey else "-"
        passives = " / ".join(
            game_modifiers.ELEMENTS[e]["player"]["desc"] for e in player_elements
            if game_modifiers.ELEMENTS[e].get("player", {}).get("desc"))
        element_text = f"{element_labels}\n⚔️ ข่ม: {prey_labels}"
        if passives:
            element_text += f"\n✨ ติดตัว: {passives}"
    else:
        element_text = "— ยังไม่มี (รับยศเผ่าเพื่อปลดล็อกธาตุ)"

    statuses = game_modifiers.parse_statuses(player_data)
    artifact_keys = [k for k in statuses if game_modifiers.STATUS_EFFECTS[k].get("artifact")]
    normal_statuses = {k: v for k, v in statuses.items() if k not in artifact_keys}
    artifact_text = game_modifiers.STATUS_EFFECTS[artifact_keys[0]]["label"] if artifact_keys else "- ว่าง -"

    if page == "progress":
        # 📊 B2/B4: หน้าความคืบหน้า — EXP / สมุดล่า / กิลด์
        import bot.models.player_model as _pm
        need_xp = (player_level ** 2) * 70
        cur_xp = player_data.get("exp", 0)
        filled = round(min(cur_xp / max(1, need_xp), 1) * 12)
        embed.add_field(name="📊 ประสบการณ์",
                        value=f"`{'█' * filled}{'░' * (12 - filled)}` `{cur_xp:,}/{need_xp:,}` XP", inline=False)
        try:
            book = _pm.get_bestiary(target_member.id)
            slots = sum(1 for c in game_modifiers.CONTINENTS for r in game_modifiers.BESTIARY_RANKS if (c, r) in book)
            embed.add_field(name="📕 สมุดล่ามอน",
                            value=f"ช่องสมุด `{slots}/36` · ล้มสะสม `{sum(book.values()):,}` ตัว  (`!bestiary`)",
                            inline=False)
            g = _pm.get_guild_of(target_member.id)
            embed.add_field(name="🏰 กิลด์",
                            value=(f"{g['icon']} **{g['name']}** · คลัง `{g['treasury']:,}` ทอง" if g
                                   else "ยังไม่มีกิลด์ — `!guild create <ชื่อ>`"), inline=False)
        except Exception:
            pass
        embed.add_field(name="🗺️ ทวีปปัจจุบัน", value=continent_label, inline=True)
        return embed

    embed.add_field(name="🗺️ ทวีปปัจจุบัน", value=continent_label, inline=True)
    embed.add_field(name="🧬 ธาตุประจำตัว", value=element_text, inline=True)
    embed.add_field(name="🏺 อาร์ติแฟกต์", value=artifact_text, inline=True)
    if normal_statuses:
        embed.add_field(name="🩸 สถานะติดตัว", value=game_modifiers.format_status_line(normal_statuses), inline=False)

    return embed
