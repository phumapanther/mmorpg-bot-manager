import discord
from collections import Counter
from discord.ext import commands
import random
import bot.models.player_model as player_model
import time
import sqlite3
from contextlib import contextmanager
from bot.utils import not_arrested, allowed_channel
from bot.views.profile_embed import GAME_CLASSES
from bot import config_loader
from bot import game_modifiers
from bot.views.game_views import DeathRespawnView
import json
import traceback # อย่าลืม import อันนี้ที่ด้านบนสุดของไฟล์นะครับ


_SET_STATE_DESC = {
    "warp_village": "วาปกลับหมู่บ้านทันที", "warp_dungeon": "วาปเข้าดันเจี้ยน",
    "mini_summon": "เรียกมินิบอสมาสู้", "main_summon": "เรียกบอสหลักมาสู้",
    "unbeatable_summon": "เรียกบอสไร้พ่าย (คิดดี ๆ)", "scan_box": "สแกนหากล่องสมบัติรอบตัว",
}


def _item_effect_desc(it):
    """สรุปผลไอเทมเป็นข้อความ — อ่านจาก effect ใน item_catalog + STATUS_EFFECTS"""
    eff, val = it.get("effect"), it.get("effect_value")
    if eff == "heal":
        return f"ฟื้น HP +{it.get('effect_amount', 0)}"
    if eff == "repair":
        return "ซ่อมความทนทานอาวุธ/เกราะ"
    if eff == "revive":
        return "ชุบชีวิตเมื่อตาย"
    if eff == "set_state":
        return _SET_STATE_DESC.get(val, str(val))
    if eff == "cure_status":
        keys = val if isinstance(val, list) else [val]
        labels = [game_modifiers.STATUS_EFFECTS[k]["label"] for k in keys if k in game_modifiers.STATUS_EFFECTS]
        return "ล้างสถานะ: " + ", ".join(labels) if labels else "ล้างสถานะ"
    if eff == "apply_status":
        cfg = game_modifiers.STATUS_EFFECTS.get(str(val), {})
        unit = "ก้าว" if cfg.get("tick") == "step" else "ไฟต์"
        return f"ติดบัฟ {cfg.get('label', val)} ({cfg.get('default_turns', 1)} {unit})"
    if eff == "emergency_ration":
        return "ฟื้น 50% MaxHP + ล้างเชื้อซอมบี้"
    if eff == "dye_profile":
        return "ย้อมสี embed โปรไฟล์/กระเป๋า"
    if eff == "equip_artifact":
        return game_modifiers.STATUS_EFFECTS.get(str(val), {}).get("desc", "อาร์ติแฟกต์ถาวร")
    if eff == "random_continent":
        return "วาร์ปสุ่มทวีป (ไม่รู้ปลายทาง!)"
    if eff == "choose_continent":
        return "เลือกทวีปปลายทางได้เอง"
    return None


def _monster_element_desc(data):
    """สรุปความสามารถธาตุฝั่งมอนเป็นข้อความ — อ่านจาก ELEMENTS ตรง ๆ เพิ่มธาตุใหม่แล้วขึ้นเอง"""
    parts = []
    if data.get("dmg_mult", 1.0) > 1.0:
        parts.append(f"ตีแรง ×{data['dmg_mult']:g}")
    if data.get("lifesteal"):
        parts.append(f"ดูดเลือด {int(data['lifesteal'] * 100)}%")
    if data.get("hp_mult", 1.0) > 1.0:
        parts.append(f"เลือดหนา ×{data['hp_mult']:g}")
    if data.get("dice_bonus"):
        parts.append(f"เต๋ามอน +{data['dice_bonus'][0]}-{data['dice_bonus'][1]}")
    if data.get("root_chance"):
        parts.append(f"{data['root_chance']}% รากล็อกเต๋าคุณ = 0")
    on_hit = data.get("on_hit_status")
    if on_hit:
        parts.append(f"{on_hit['chance']}% ตีติด {game_modifiers.STATUS_EFFECTS[on_hit['key']]['label']}")
    if data.get("pre_enraged"):
        parts.append("คลั่งตั้งแต่เทิร์นแรก")
    if data.get("monster_flee_chance"):
        parts.append(f"หนีเก่ง {data['monster_flee_chance']}%")
    if data.get("gold_mult", 1.0) > 1.0:
        parts.append(f"ล้มได้ทอง ×{data['gold_mult']:g}")
    return ", ".join(parts) or "-"


def apply_item_effect(user_id, item_id):
    """ใช้ไอเทมตาม effect ที่ตั้งค่าไว้ใน config — คืนค่า (success: bool, message: str)
    ดึงออกมาเป็นฟังก์ชันระดับโมดูล เพื่อให้ทั้งคำสั่ง !use และปุ่มเมนู (game_views) เรียกใช้ตรรกะเดียวกันได้
    """
    player = player_model.get_player(user_id)
    if not player:
        return False, "❌ ไม่พบข้อมูลตัวละครของคุณ!"

    inv_array = player_model.load_inventory(player.get("inventory", ""))

    if item_id not in inv_array:
        return False, f"❌ คุณไม่มีไอเทมหมายเลข `{item_id}` ในกระเป๋า! (พิมพ์ `!bag` เพื่อเช็ก)"

    if not config_loader.get_item_config(item_id):
        return False, "❌ ไม่มีข้อมูลไอเทมนี้ในระบบเซิร์ฟเวอร์!"

    item_info = config_loader.get_item_config(item_id)
    item_name = item_info["name"]
    item_type = item_info.get("type", "unknown")

    msg = ""

    # 🧪 กรณี: ใช้ยาฮีล (ตั้งค่าได้ผ่าน effect: "heal" + effect_amount)
    if item_info.get("effect") == "heal":
        heal_amount = item_info.get("effect_amount", 50)
        armor_key = player.get("armor", "None")
        current_dur = player.get("armor_dur", 0)

        armor_info_stats = config_loader.get_armor_stats(armor_key) or config_loader.get_armor_stats("None")

        armor_hp_bonus = armor_info_stats.get("hp", 0) if current_dur > 0 else 0
        max_hp_total = player.get("max_hp", 100) + armor_hp_bonus
        current_hp = player.get("hp", 0)

        if current_hp >= max_hp_total:
            return False, f"❌ เลือดของคุณเต็มอยู่แล้ว! (`{current_hp}/{max_hp_total}`) ไม่สามารถใช้ {item_name} ได้"

        new_hp = min(current_hp + heal_amount, max_hp_total)
        player_model.update_player_field(user_id, "hp", new_hp)
        msg = f"🧪 คุณดื่ม **{item_name}** ฟื้นฟูพลังชีวิต! (HP: `{current_hp}` ➔ `{new_hp}/{max_hp_total}`)"

    # 🛠️ กรณี: ใช้ใบซ่อมแซม (ตั้งค่าได้ผ่าน effect: "repair")
    elif item_info.get("effect") == "repair":
        armor_key = player.get("armor", "None")
        weapon_key = player.get("weapon", "None")

        armor_info_stats = config_loader.get_armor_stats(armor_key)
        max_armor_dur = armor_info_stats.get("dur", 100)
        current_armor_dur = player.get("armor_dur", 0)

        weapon_info_stats = config_loader.get_weapon_stats(weapon_key)
        max_weapon_dur = weapon_info_stats.get("dur", 50)
        current_weapon_dur = player.get("weapon_dur", 0)

        needs_armor_repair = (armor_key != "None" and current_armor_dur < max_armor_dur)
        needs_weapon_repair = (weapon_key != "None" and current_weapon_dur < max_weapon_dur)

        if not needs_armor_repair and not needs_weapon_repair:
            return False, f"❌ อุปกรณ์ทั้งหมดของคุณสภาพสมบูรณ์อยู่แล้ว (หรือไม่ได้สวมใส่)! ไม่สามารถใช้ {item_name} ได้"

        repaired_items = []
        if needs_armor_repair:
            player_model.update_player_field(user_id, "armor_dur", max_armor_dur)
            repaired_items.append(f"เกราะ **{armor_info_stats.get('name', armor_key)}** (`{max_armor_dur}/{max_armor_dur}`)")

        if needs_weapon_repair:
            player_model.update_player_field(user_id, "weapon_dur", max_weapon_dur)
            repaired_items.append(f"อาวุธ **{weapon_info_stats.get('name', weapon_key)}** (`{max_weapon_dur}/{max_weapon_dur}`)")

        repair_text = " และ ".join(repaired_items)
        msg = f"🛠️ คุณใช้ **{item_name}** ซ่อมแซม {repair_text} กลับมาสภาพสมบูรณ์!"

    # 🛡️ กรณี: สวมใส่ชุดเกราะ (อ่านค่า type อัตโนมัติจาก ITEM_CONFIG)
    elif item_type == "armor":
        equip_key = item_info["equip_key"]
        armor_stats = config_loader.get_armor_stats(equip_key)
        max_dur = armor_stats.get("dur", 100)

        player_model.update_player_field(user_id, "armor", equip_key)
        player_model.update_player_field(user_id, "armor_dur", max_dur)

        current_hp = player.get("hp", 0)
        new_max_hp = player.get("max_hp", 100) + armor_stats.get("hp", 0)
        if current_hp > new_max_hp:
            player_model.update_player_field(user_id, "hp", new_max_hp)

        msg = f"🛡️ คุณสวมใส่ **{item_name}** เรียบร้อยแล้ว! (ความคงทน: `{max_dur}/{max_dur}`)"

    # ⚔️ กรณี: สวมใส่อาวุธ
    elif item_type == "weapon":
        equip_key = item_info["equip_key"]
        weapon_stats = config_loader.get_weapon_stats(equip_key)
        max_dur = weapon_stats.get("dur", 50)

        player_model.update_player_field(user_id, "weapon", equip_key)
        player_model.update_player_field(user_id, "weapon_dur", max_dur)

        msg = f"⚔️ คุณสวมใส่ **{item_name}** เรียบร้อยแล้ว! (ความคงทน: `{max_dur}/{max_dur}`)"

    elif item_type == "bag":
        equip_key = item_info["equip_key"]
        bag_status = config_loader.get_bag_stats(equip_key)
        bag_limit = bag_status.get("capacity", 10)

        player_model.update_player_field(user_id, "bag", equip_key)
        player_model.update_player_field(user_id, "capacity", bag_limit)

        msg = f"⚔️ คุณสวมใส่ **{item_name}** เรียบร้อยแล้ว! (ความจุกระเป๋า: `{'ไม่จำกัด' if bag_limit == 0 else bag_limit}`)"

    elif item_type == "drop":
        # 1. เช็กเคสพิเศษ: ไอเทมชุบชีวิต ต้องเช็กว่าตายไหม (ตั้งค่าได้ผ่าน effect: "revive")
        if item_info.get("effect") == "revive":
            if player.get("hp") > 0 and player.get("current_state") != "death":
                return False, "❌ คุณยังไม่ได้ตาย จะใช้ใบชุบชีวิตไปทำไมล่ะเนี่ย! เก็บไว้ใช้ตอนตายดีหน้า!"

            max_hp = player.get("max_hp", 100)
            player_model.update_player_field(user_id, "hp", max_hp)
            player_model.update_player_field(user_id, "current_state", "idle")
            player_model.update_player_field(user_id, "last_event", "revive")

            msg = "✨ คุณใช้ `💌ใบชุบชีวิต`! ฟื้นคืนชีพและฟื้นฟู HP เต็มแล้ว! พร้อมลุยต่อแล้วครับ!"

        # 2. เคสไอเทมตั้งค่า last_event อื่นๆ (ต้องเป็น idle เท่านั้น) — ตั้งค่าได้ผ่าน effect: "set_state" + effect_value
        elif item_info.get("effect") == "set_state":
            if player.get("current_state") != "idle":
                return False, "❌ คุณไม่สามารถใช้ไอเทมนี้ได้ในขณะที่กำลังทำกิจกรรมอื่นอยู่ (ต้องอยู่ในสถานะว่างก่อนกดปุ่ม 🧭 เริ่มออกเดินทาง)!"

            new_state = item_info.get("effect_value")
            if new_state:
                player_model.update_player_field(user_id, "last_event", new_state)
                msg = f"✨ คุณได้เปิดใช้งาน `{item_name}` แล้ว! เตรียมพบกับเหตุการณ์ถัดไป..."
            else:
                msg = "❌ ไอเทมนี้ยังไม่ถูกตั้งค่าการใช้งาน!"  # ponytail: คงพฤติกรรมเดิม (ไอเทมถูกใช้/หักออกแม้ยังไม่ตั้งค่า effect_value)
        else:
            return False, f"❌ ไอเทม **{item_name}** ยังไม่สามารถกดใช้งานได้ในตอนนี้ (ยังไม่ได้ตั้งค่า effect ให้ถูกต้อง)"

    # ✨ กรณี: ไอเทมแก้สถานะ (effect: "cure_status" + effect_value: key เดียว, ลิสต์หลาย key, หรือ "all")
    elif item_info.get("effect") == "cure_status":
        statuses = game_modifiers.parse_statuses(player)
        target = item_info.get("effect_value", "all")
        targets = target if isinstance(target, list) else [target]
        if "all" in targets:
            # ล้างทุกสถานะ ยกเว้นอาร์ติแฟกต์ที่สวมอยู่
            to_remove = [k for k in statuses if not game_modifiers.STATUS_EFFECTS[k].get("artifact")]
        else:
            to_remove = [k for k in targets if k in statuses]
        if not to_remove:
            return False, f"❌ ตอนนี้คุณไม่มีสถานะที่ **{item_name}** รักษาได้"
        names = " ".join(game_modifiers.STATUS_EFFECTS.get(k, {}).get("label", k) for k in to_remove)
        statuses = {k: v for k, v in statuses.items() if k not in to_remove}
        player_model.update_player_field(user_id, "status_effects", statuses)
        msg = f"✨ คุณใช้ **{item_name}** — {names} หายเป็นปกติ!"

    # 🧬 กรณี: ไอเทมเสกสถานะใส่ตัวเอง (effect: "apply_status" + effect_value: key + effect_amount: เทิร์น)
    elif item_info.get("effect") == "apply_status":
        key = str(item_info.get("effect_value", ""))
        cfg = game_modifiers.STATUS_EFFECTS.get(key)
        if not cfg:
            return False, "❌ ไอเทมนี้ตั้งค่าสถานะไว้ไม่ถูกต้อง (แจ้งแอดมินตรวจ config)"
        statuses = game_modifiers.apply_status(game_modifiers.parse_statuses(player), key, item_info.get("effect_amount"))
        player_model.update_player_field(user_id, "status_effects", statuses)
        msg = f"🧬 คุณใช้ **{item_name}** — ได้รับสถานะ {cfg['label']} (`{statuses[key]}` เทิร์น)!"

    # 🥫 กรณี: เสบียงฉุกเฉิน (effect: "emergency_ration" — ฮีล 50% MaxHP + ล้างเชื้อซอมบี้)
    elif item_info.get("effect") == "emergency_ration":
        max_hp = player.get("max_hp", 100)
        new_hp = min(max_hp, player.get("hp", 0) + max_hp // 2)
        player_model.update_player_field(user_id, "hp", new_hp)
        cured_note = ""
        statuses = game_modifiers.parse_statuses(player)
        zombie_keys = [k for k in ("zombie_parasite", "zombie_frenzy") if k in statuses]
        if zombie_keys:
            statuses = {k: v for k, v in statuses.items() if k not in zombie_keys}
            player_model.update_player_field(user_id, "status_effects", statuses)
            cured_note = " และล้างเชื้อซอมบี้ออกจากร่างกายจนหมดจด!"
        msg = f"🥫 คุณกิน **{item_name}** ฟื้นพลังชีวิต ➔ `{new_hp}/{max_hp}`{cured_note}"

    # 🌀 กรณี: ประตูวาร์ปมิติ (effect: "random_continent" — วาร์ปทันทีไปทวีปสุ่ม ไม่ซ้ำที่ยืนอยู่)
    elif item_info.get("effect") == "random_continent":
        if player.get("current_state") in ("fighting", "dead") or player.get("dungeon_steps", 0) > 0:
            return False, "❌ ตอนนี้เปิดประตูมิติไม่ได้! (ติดการต่อสู้/อยู่ในดันเจี้ยน — เคลียร์ให้จบก่อน)"
        import random as _rng
        current_continent = player.get("continent") or "main"
        dest = _rng.choice([k for k in game_modifiers.CONTINENTS if k != current_continent])
        dest_info = game_modifiers.CONTINENTS[dest]
        player_model.update_player_fields(user_id, {"continent": dest, "last_event": "none", "current_state": "idle"})
        msg = (
            f"🌀 **ประตูมิติเปิดออกกลางอากาศ ดูดร่างคุณหายวับ!**\n"
            f"{dest_info['arrival_text']}\n"
            f"🗺️ ปลายทาง: {dest_info['label']} (พิมพ์ `!play` เพื่อออกสำรวจ)"
        )

    # 🗺️ กรณี: ตั๋ววาร์ปเจาะจง — ต้องใช้ผ่าน !use เพื่อเปิดเมนูเลือกทวีป (ตั๋วถูกหักตอนยืนยันใน view)
    elif item_info.get("effect") == "choose_continent":
        return False, "🗺️ ไอเทมนี้ใช้ผ่านคำสั่ง `!use` ในห้องแชทเท่านั้น — จะมีเมนูให้เลือกทวีปปลายทาง"

    # 🎨 กรณี: ผงสีย้อมโปรไฟล์ — ต้องใช้ผ่าน !use เพื่อเปิดเมนูเลือกสี (ผงถูกหักตอนยืนยันใน view)
    elif item_info.get("effect") == "dye_profile":
        return False, "🎨 ไอเทมนี้ใช้ผ่านคำสั่ง `!use` ในห้องแชทเท่านั้น — จะมีเมนูให้เลือกสีย้อมโปรไฟล์"

    # 🏺 กรณี: สวมอาร์ติแฟกต์ (effect: "equip_artifact" — ช่องเดียว สวมทับ = ของเก่าถูกทำลายถาวร)
    elif item_info.get("effect") == "equip_artifact":
        art_key = str(item_info.get("effect_value", ""))
        art_cfg = game_modifiers.STATUS_EFFECTS.get(art_key)
        if not art_cfg or not art_cfg.get("artifact"):
            return False, "❌ ไอเทมนี้ตั้งค่าอาร์ติแฟกต์ไว้ไม่ถูกต้อง (แจ้งแอดมินตรวจ config)"
        statuses = game_modifiers.parse_statuses(player)
        destroyed = [k for k in statuses if game_modifiers.STATUS_EFFECTS[k].get("artifact")]
        statuses = {k: v for k, v in statuses.items() if k not in destroyed}
        statuses = game_modifiers.apply_status(statuses, art_key)
        player_model.update_player_field(user_id, "status_effects", statuses)
        destroy_note = ""
        if destroyed:
            names = " ".join(game_modifiers.STATUS_EFFECTS[k]["label"] for k in destroyed)
            destroy_note = f"\n💥 **{names} ที่สวมอยู่แตกสลายเป็นผุยผง!** (สวมทับแล้วไม่มีวันได้คืน)"
        msg = f"🏺 คุณสวม **{item_name}** เข้าช่องอาร์ติแฟกต์ — พลังถาวรไหลเวียนทั่วร่าง!{destroy_note}"

    else:
        return False, f"❌ ไอเทม **{item_name}** ยังไม่สามารถกดใช้งานได้ในตอนนี้"

    inv_array.remove(item_id)
    player_model.update_player_field(user_id, "inventory", inv_array)
    return True, msg


def build_bank_embed(player):
    """สร้าง Embed บัญชีธนาคาร — ใช้ร่วมกันระหว่างคำสั่ง !bank และปุ่มเมนู"""
    bank_balance = player.get("bank", 0)
    cash_balance = player.get("cash", 0)
    embed = discord.Embed(title="🏦 บัญชีธนาคารของคุณ", color=discord.Color.gold())
    embed.add_field(name="💰 เงินสดติดตัว", value=f"`{cash_balance:,}` ทอง", inline=True)
    embed.add_field(name="🏦 เงินในธนาคาร", value=f"`{bank_balance:,}` ทอง", inline=True)
    embed.set_footer(text="ใช้คำสั่ง !deposit [จำนวน] เพื่อฝากเงิน (ถ้ามี)")
    return embed


def build_bag_embed(display_name, avatar_url, player):
    """สร้าง Embed กระเป๋าเดินทาง — ใช้ร่วมกันระหว่างคำสั่ง !bag และปุ่มเมนู"""
    inv_array = player_model.load_inventory(player.get("inventory", ""))

    embed = discord.Embed(
        title=f"🎒 กระเป๋าเดินทางของ {display_name}",
        description=f"💰 **เงินสดกลาง:** {player.get('cash', 0):,} ทอง",
        color=discord.Color(player.get("profile_color") or 0x3498DB)  # 🎨 สีย้อมส่วนตัว (ไม่เคยย้อม = ฟ้าเดิม)
    )

    capacity = player.get("capacity", 10)
    current_count = len(inv_array)
    cap_display = "ไม่จำกัด" if capacity == 0 else f"{current_count} / {capacity}"

    if not inv_array:
        embed.add_field(
            name=f"📦 ไอเทมในกระเป๋า ({cap_display})",
            value="*~ กระเป๋าว่างเปล่า ไม่มีไอเทมเลย ~*",
            inline=False
        )
    else:
        item_counts = Counter(inv_array)
        all_items = config_loader.get_all_items()

        def _sort_key(item_id):
            return (0, int(item_id)) if str(item_id).isdigit() else (1, 0)

        lines = []
        for item_id in sorted(item_counts, key=_sort_key):
            count = item_counts[item_id]
            item_name = all_items[item_id]["name"] if item_id in all_items else "❓ ไอเทมปริศนา"
            lines.append(f"**[{item_id}]** {item_name} x`{count}` ชิ้น")

        # Discord จำกัด field ละ 1024 ตัวอักษร (และ embed รวม 6000) — ซอยรายการเป็นหลาย field
        chunks = []
        current = ""
        for line in lines:
            if len(current) + len(line) + 1 > 1024:
                chunks.append(current)
                current = ""
            current += line + "\n"
        if current:
            chunks.append(current)

        header = f"📦 ไอเทมในกระเป๋า ({len(inv_array)} / {'ไม่จำกัด' if capacity == 0 else capacity})"
        for i, chunk in enumerate(chunks[:5]):
            embed.add_field(name=header if i == 0 else "📦 (ต่อ)", value=chunk, inline=False)
        if len(chunks) > 5:
            embed.add_field(
                name="⚠️ ของเยอะเกินจอ",
                value="รายการที่เหลือแสดงไม่หมด แต่ยังใช้งานผ่าน `!use <เลขไอเทม>` ได้ปกติ",
                inline=False)

    embed.set_thumbnail(url=avatar_url)
    return embed


class PlayerCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db_path = "game_data.db"
        self.pk_cooldowns = {} #

    # --- Database Context Manager ---
    @contextmanager
    def get_db(self):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        try:
            yield cursor
            conn.commit()
        finally:
            conn.close()

    # --- ฟังก์ชันเสริม: ดึงข้อมูลชื่อผู้เล่นแบบมีประสิทธิภาพ ---
    async def get_user_name(self, uid):
        user = self.bot.get_user(uid) or await self.bot.fetch_user(uid)
        return user.name if user else f"User {uid}"

    # 1. ฝากเงิน: ย้ายเงินจาก Cash -> Bank
    @not_arrested() 
    @commands.command(name="deposit")
    @allowed_channel("bank")
    async def deposit(self, ctx, amount: int):
        player = player_model.get_player(ctx.author.id)
        if amount <= 0 or player["cash"] < amount:
            return await ctx.send("❌ เงินไม่พอหรือจำนวนไม่ถูกต้อง!")
        
        player_model.update_player_field(ctx.author.id, "cash", player["cash"] - amount)
        player_model.update_player_field(ctx.author.id, "bank", player.get("bank", 0) + amount)
        await ctx.send(f"💰 ฝากเงินเข้าธนาคารเรียบร้อย: `{amount}` ทอง")
        
    @not_arrested() 
    @commands.command(name="withdraw")
    @allowed_channel("bank")
    async def withdraw(self, ctx, amount: int):
        player = player_model.get_player(ctx.author.id)
        
        if amount <= 0:
            return await ctx.send("❌ จำนวนเงินต้องมากกว่า 0!")
        
        if player.get("bank", 0) < amount:
            return await ctx.send("❌ เงินในธนาคารไม่พอถอนครับ!")
        
        player_model.update_player_field(ctx.author.id, "bank", player["bank"] - amount)
        player_model.update_player_field(ctx.author.id, "cash", player["cash"] + amount)
        
        await ctx.send(f"💸 ถอนเงินออกจากธนาคารเรียบร้อย: `{amount:,}` ทอง")
    
    # 2. โอนเงิน: โอนจาก Bank -> ผู้เล่นอื่น
    @not_arrested() 
    @commands.command(name="transfer")
    @allowed_channel("bank")
    async def transfer(self, ctx, member: discord.Member, amount: int):
        sender = player_model.get_player(ctx.author.id)
        if sender.get("bank", 0) < amount:
            return await ctx.send("❌ เงินในธนาคารไม่พอโอน!")
        
        target = player_model.get_player(member.id)
        if not target: return await ctx.send("❌ ไม่พบข้อมูลผู้เล่นปลายทาง")

        player_model.update_player_field(ctx.author.id, "bank", sender["bank"] - amount)
        player_model.update_player_field(member.id, "bank", target.get("bank", 0) + amount)
        await ctx.send(f"💸 โอนเงิน `{amount}` ทอง ให้ {member.mention} สำเร็จ!")

    # 3. ขอเงิน (Beg)
    @not_arrested() 
    @commands.command(name="beg")
    @allowed_channel("bank")
    async def beg(self, ctx):
        if not any(role.name == "ขอทาน" for role in ctx.author.roles):
            return await ctx.send("❌ เฉพาะคนมียศ 'ขอทาน' เท่านั้นที่จะขอเงินคนอื่นได้!")

        top_players = player_model.get_all_players_sorted_by_wealth()[:10] 
        if not top_players: return await ctx.send("❌ ไม่มีเศรษฐีให้ขอเลย...")

        target = random.choice(top_players)
        tax = int(target.get("bank", 0) * 0.01)
        
        player_model.update_player_field(target["user_id"], "bank", target["bank"] - tax)
        player_model.update_player_field(ctx.author.id, "cash", player_model.get_player(ctx.author.id)["cash"] + tax)
        await ctx.send(f"🤲 ขอทานได้เงิน `{tax}` ทอง จากเศรษฐี {target['username']}!")

    # 4. ปล้น (Rob)
    @not_arrested() 
    @commands.command(name="rob")
    @allowed_channel("bank")
    async def rob(self, ctx, member: discord.Member):
        if member.id == ctx.author.id:
            return await ctx.send("❌ จะปล้นตัวเองทำไมล่ะ!")

        player = player_model.get_player(ctx.author.id)
        if player.get("current_state") == "arrested":
            if time.time() < player.get("arrest_until", 0):
                return await ctx.send("❌ คุณกำลังติดคุกอยู่! ยังไม่ถึงเวลาพ้นโทษ")
            else:
                player_model.update_player_field(ctx.author.id, "current_state", "idle")

        if random.random() <= 0.05:
            victim = player_model.get_player(member.id)
            rob_amount = int(victim.get("cash", 0) * 0.5)
            player_model.update_player_field(member.id, "cash", victim["cash"] - rob_amount)
            player_model.update_player_field(ctx.author.id, "cash", player["cash"] + rob_amount)
            await ctx.send(f"🥷 ปล้นสำเร็จ! คุณได้เงินจาก {member.mention} มา `{rob_amount:,}` ทอง")
        else:
            jail_time = int(time.time() + 180)
            player_model.update_player_field(ctx.author.id, "current_state", "arrested")
            player_model.update_player_field(ctx.author.id, "arrest_until", jail_time)
            await ctx.send(f"👮 **ปล้นพลาด!** คุณถูกตำรวจจับ! ถูกขังคุกเป็นเวลา 3 นาที")

    # 5. rich
    @commands.command(name="rich")
    @allowed_channel("bank")
    async def rich(self, ctx):
        # ดึง ID ของเจ้าของเซิร์ฟเวอร์
        owner_id = ctx.guild.owner_id 
        
        with self.get_db() as cursor:
            # เพิ่ม WHERE user_id != ? เพื่อยกเว้นเจ้าของเซิร์ฟเวอร์
            cursor.execute("""
                SELECT user_id, (bank + cash) as total 
                FROM players 
                WHERE user_id != ? 
                ORDER BY total DESC 
                LIMIT 10
            """, (owner_id,))
            rows = cursor.fetchall()
        
        msg = "🏆 **10 อันดับมหาเศรษฐี (ไม่รวมเจ้าของเซิร์ฟ)** 🏆\n"
        for i, (uid, total) in enumerate(rows, 1):
            name = await self.get_user_name(uid)
            msg += f"{i}. **{name}**: `{total:,}` ทอง\n"
        await ctx.send(msg)

    # 6. toplvl
    @commands.command(name="toplvl")
    @allowed_channel("bank")
    async def toplvl(self, ctx):
        # ดึง ID ของเจ้าของเซิร์ฟเวอร์
        owner_id = ctx.guild.owner_id 
        
        with self.get_db() as cursor:
            # เพิ่ม WHERE user_id != ? เพื่อยกเว้นเจ้าของเซิร์ฟเวอร์
            cursor.execute("""
                SELECT user_id, level, exp 
                FROM players 
                WHERE user_id != ? 
                ORDER BY level DESC, exp DESC 
                LIMIT 10
            """, (owner_id,))
            rows = cursor.fetchall()

        msg = "⚔️ **10 อันดับผู้กล้าเลเวลสูง (ไม่รวมเจ้าของเซิร์ฟ)** ⚔️\n"
        for i, (uid, lvl, exp) in enumerate(rows, 1):
            name = await self.get_user_name(uid)
            msg += f"{i}. **{name}**: เลเวล `{lvl}` (EXP: `{exp}`)\n"
        await ctx.send(msg)
    
    # ==========================================
    # 💬 คำสั่งเช็กสถิติการพิมพ์ของตัวเอง (!mytext)
    # ==========================================
    @commands.command(name="mytext")
    @allowed_channel("bank")
    async def check_my_text(self, ctx):
        player = player_model.get_player(ctx.author.id)
        if not player:
            return await ctx.send("❌ ไม่พบข้อมูลตัวละครของคุณในระบบ!")
        
        total_text = player.get("total_text", 0)
        event_text = player.get("event_text", 0)
        
        embed = discord.Embed(
            title="📊 สถิติการพิมพ์แชทของคุณ", 
            color=discord.Color.blue()
        )
        
        # ใส่รูปโปรไฟล์ของผู้เล่น
        if ctx.author.avatar:
            embed.set_thumbnail(url=ctx.author.avatar.url)
            
        embed.add_field(name="💬 ข้อความทั้งหมด (ตลอดชีพ)", value=f"`{total_text:,}` ข้อความ", inline=False)
        embed.add_field(name="🏆 ข้อความกิจกรรม (ซีซั่นนี้)", value=f"`{event_text:,}` ข้อความ", inline=False)
        
        await ctx.send(embed=embed)


    # ==========================================
    # 🏆 คำสั่งเช็ก 10 อันดับคนพิมพ์เยอะที่สุด (!toptext)
    # ==========================================
    @commands.command(name="toptext")
    @allowed_channel("bank")
    async def top_text_leaderboard(self, ctx):
        # เรียกใช้ฟังก์ชันดึง Top 10 ที่เราเพิ่งสร้าง
        top_players = player_model.get_top_text_players(10)
        
        if not top_players:
            return await ctx.send("❌ ยังไม่มีสถิติการพิมพ์ในเซิร์ฟเวอร์เลย! (ไปพิมพ์แชทกันก่อนนะ)")
            
        embed = discord.Embed(
            title="🏆 TOP 10 นักแชทแห่งเซิร์ฟเวอร์ 🏆", 
            description="รายชื่อนักผจญภัยที่พูดคุยเยอะที่สุดในดินแดนนี้!", 
            color=discord.Color.gold()
        )
        
        board_text = ""
        for index, (user_id, total, event) in enumerate(top_players, start=1):
            # จัดการเหรียญรางวัลให้อันดับ 1-3
            if index == 1:
                medal = "🥇"
            elif index == 2:
                medal = "🥈"
            elif index == 3:
                medal = "🥉"
            else:
                medal = f"**{index}.**"
            
            # ใช้ <@user_id> เพื่อให้ Discord แท็ก (Mention) โชว์ชื่อผู้เล่นปัจจุบันอัตโนมัติ
            board_text += f"{medal} <@{user_id}>\n"
            board_text += f"└ 💬 รวม: `{total:,}` | 🏆 กิจกรรม: `{event:,}`\n\n"
            
        embed.add_field(name="อันดับกระดานผู้นำ", value=board_text, inline=False)
        embed.set_footer(text="ระบบจะนับเฉพาะข้อความที่พิมพ์ในช่องแชททั่วไปเท่านั้น")
        
        await ctx.send(embed=embed)
    
    @commands.command(name="bank")
    @allowed_channel("bank")
    async def check_bank(self, ctx):
        player = player_model.get_player(ctx.author.id)
        await ctx.send(embed=build_bank_embed(player))

    # ==========================================
    # 🎖️ คำสั่งรับรางวัลตามยศ (!reward) — รวมรางวัลทุกยศที่มีสิทธิ์ในครั้งเดียว
    # ponytail: คูลดาวน์เดียวรวมทุกยศ (ไม่ใช่แยกคูลดาวน์ต่อยศ) — ง่ายกว่าและพอสำหรับสเปกปัจจุบัน
    # ==========================================
    @not_arrested()
    @commands.command(name="reward")
    async def claim_rank_reward(self, ctx):
        user_id = ctx.author.id
        player = player_model.get_player(user_id)
        if not player:
            return await ctx.send("❌ ไม่พบข้อมูลตัวละครของคุณ! พิมพ์ `!play` เพื่อสร้างตัวละครก่อนน้า")

        my_role_ids = {role.id for role in ctx.author.roles}
        matched = [r for r in config_loader.get_rank_rewards() if r.get("role_id") in my_role_ids]
        if not matched:
            return await ctx.send("❌ ยศของคุณยังไม่มีรางวัลให้รับในตอนนี้!")

        cooldown_seconds = config_loader.get_rank_reward_cooldown_hours() * 3600
        last_claim = player.get("last_reward_claim", 0) or 0
        now = time.time()
        remaining = cooldown_seconds - (now - last_claim)
        if remaining > 0:
            hours = int(remaining // 3600)
            minutes = int((remaining % 3600) // 60)
            return await ctx.send(f"⏳ คุณรับรางวัลไปแล้ว! กรุณารออีก `{hours}` ชั่วโมง `{minutes}` นาที")

        total_cash = sum(int(r.get("cash", 0)) for r in matched)
        total_exp = sum(int(r.get("exp", 0)) for r in matched)
        item_grants = Counter()
        for r in matched:
            for it in r.get("items", []):
                item_grants[str(it.get("item_id"))] += int(it.get("amount", 1))

        if total_cash:
            player_model.increment_player_field(user_id, "cash", total_cash)
        is_lvl_up, new_level, _ = (False, None, None)
        if total_exp:
            is_lvl_up, new_level, _ = player_model.add_exp(user_id, total_exp)

        if item_grants:
            inv_list = player_model.load_inventory(player.get("inventory", ""))
            all_items = config_loader.get_all_items()
            for item_id, amount in item_grants.items():
                if item_id not in all_items:
                    continue
                inv_list.extend([item_id] * amount)
            player_model.update_player_field(user_id, "inventory", inv_list)

        player_model.update_player_field(user_id, "last_reward_claim", int(now))

        labels = ", ".join(r.get("label", "ยศ") for r in matched)
        lines = [f"🎖️ **รับรางวัลจากยศสำเร็จ!** ({labels})"]
        if total_cash:
            lines.append(f"💰 เงินสด: `+{total_cash:,}` ทอง")
        if total_exp:
            lvl_txt = f" (✨ Level Up! → {new_level})" if is_lvl_up else ""
            lines.append(f"⭐ EXP: `+{total_exp}`{lvl_txt}")
        all_items = config_loader.get_all_items()
        for item_id, amount in item_grants.items():
            name = all_items.get(item_id, {}).get("name", f"ไอเทม {item_id}")
            lines.append(f"📦 {name} x`{amount}`")
        await ctx.send("\n".join(lines))

    # --- 📖 !codex: สารานุกรมกติกา (ธาตุ/สถานะ/ทวีป) — สร้างจาก data ใน game_modifiers/config เสมอ ไม่ต้องอัปเดตมือ ---
    @commands.command(name="codex")
    async def codex(self, ctx, *, topic: str = ""):
        topic = topic.strip().lower()

        if topic in ("ธาตุ", "element", "elements"):
            embed = discord.Embed(
                title="📖 Codex — ธาตุทั้ง 7", color=0x9b59b6,
                description="ธาตุประจำตัวมาจาก **ยศเผ่า** — ถือหลายเผ่าได้หลายธาตุ, สองธาตุข่มเป้าเดียวกัน = ดาเมจ ×2.0")
            for key, data in game_modifiers.ELEMENTS.items():
                prey = [game_modifiers.ELEMENTS[t]["label"] for t in game_modifiers.ELEMENT_ADVANTAGE.get(key, [])]
                resist = [game_modifiers.ELEMENTS[t]["label"] for t in game_modifiers.ELEMENT_RESIST.get(key, [])]
                lines = [f"👤 ติดตัวผู้เล่น: {data['player']['desc']}",
                         f"👹 ฝั่งมอนสเตอร์: {_monster_element_desc(data)}"]
                if prey:
                    lines.append(f"⚔️ ข่ม (×1.5): {', '.join(prey)}")
                if resist:
                    lines.append(f"🛡️ รับเบา (×0.75): {', '.join(resist)}")
                embed.add_field(name=data["label"], value="\n".join(lines), inline=False)
            return await ctx.send(embed=embed)

        if topic in ("วิธีเล่น", "เริ่มเล่น", "howto", "guide"):
            embed = discord.Embed(
                title="📖 Codex — วิธีเล่นฉบับเริ่มต้น", color=0x9b59b6,
                description="โลกนี้เดินด้วย **ลูกเต๋า** — ทุกการผจญภัยคือการทอยวัดดวงกับโชคชะตา")
            embed.add_field(name="1️⃣ เกิดใหม่ในโลกนี้", inline=False, value=(
                "รับ **ยศเผ่า** และ **ยศคลาสอาชีพ** จากเซิร์ฟก่อน (เผ่ากำหนดธาตุประจำตัว ดู `!codex ธาตุ`)\n"
                "พิมพ์ `!adv` สร้างห้องผจญภัยส่วนตัว แล้ว `!play` เพื่อออกเดินทาง"))
            embed.add_field(name="2️⃣ ออกเดินทาง", inline=False, value=(
                "กดปุ่ม **ไปต่อ** เพื่อเดินทีละก้าว — สุ่มเจอมอนสเตอร์ กับดัก สมบัติ หมู่บ้าน NPC "
                "หรือพาหนะข้ามทวีป (ทางเดียวที่จะไปทวีปอื่น!)\n"
                "เจอมอน = ทอยเต๋าสู้กันเป็นเทิร์น ชนะได้ทอง+EXP แพ้เต๋า = โดนสวน"))
            embed.add_field(name="3️⃣ ของติดตัวคือชีวิต", inline=False, value=(
                "`!bag` ดูกระเป๋า / `!use <เลขไอเทม>` ใช้ของ / `!craft` คราฟ\n"
                "พกยาแก้สถานะให้ตรงทวีป (ดู `!codex สถานะ`) และหา **อาร์ติแฟกต์** มาสวม "
                "(มีช่องเดียว — สวมทับแล้วของเก่าถูกทำลายถาวร คิดก่อนสวม!)"))
            embed.add_field(name="4️⃣ เงินและเมือง", inline=False, value=(
                "ทองที่ถือตายแล้วหาย — ฝากธนาคารด้วย `!deposit` ไว้ก่อน\n"
                "`!shop` ซื้อของ / คาสิโนมี `!bj` `!hilo` `!slots` เสี่ยงดวงเพิ่ม (หรือหมดตัว)"))
            embed.add_field(name="5️⃣ โลกที่หมุนเอง", inline=False, value=(
                "ทุกสัปดาห์มี **ธีมโลก** สุ่มใหม่ (ประกาศวันจันทร์) เปลี่ยนมอน/เรท/อีเวนต์ทั้งเซิร์ฟ\n"
                "แต่ละทวีปมีธาตุ สถานะ และบอสประจำถิ่น — `!codex ทวีป` ก่อนออกเดิน"))
            return await ctx.send(embed=embed)

        if topic in ("คำสั่ง", "commands", "cmd"):
            embed = discord.Embed(
                title="📖 Codex — คำสั่งผู้เล่นทั้งหมด", color=0x9b59b6,
                description="พิมพ์ในห้องที่เซิร์ฟกำหนดไว้ (บางคำสั่งจำกัดห้อง) — `!menu` มีปุ่มลัดของที่ใช้บ่อย")
            embed.add_field(name="🗺️ ผจญภัย", inline=False, value=(
                "`!adv` สร้างห้องผจญภัยส่วนตัว • `!play` เริ่มออกเดินทาง\n"
                "`!profile` (`!info`) โปรไฟล์+ธาตุ+อาร์ติแฟกต์ • `!scan @คน` ส่องข้อมูลคนอื่น\n"
                "`!codex <หมวด>` สารานุกรมกติกา • `!reward` รับรางวัลประจำยศ"))
            embed.add_field(name="🎒 กระเป๋า & ไอเทม", inline=False, value=(
                "`!bag` ดูกระเป๋า • `!use <เลข>` ใช้ไอเทม • `!drop <เลข>` ทิ้ง\n"
                "`!give @คน <เลข>` ส่งของให้เพื่อน • `!recipes` สูตรคราฟ • `!craft <เลข>` คราฟของ"))
            embed.add_field(name="💰 เงิน & ธนาคาร", inline=False, value=(
                "`!bank` ยอดธนาคาร • `!deposit <จำนวน>` ฝาก • `!withdraw <จำนวน>` ถอน\n"
                "`!transfer @คน <จำนวน>` โอน • `!beg` ขอทาน • `!rob @คน` ปล้น (เสี่ยงติดคุก!)\n"
                "`!rich` `!toplvl` `!mytext` `!toptext` `!mytime` `!toptime` อันดับ/แต้มกิจกรรม"))
            embed.add_field(name="🎰 คาสิโน & PvP", inline=False, value=(
                "`!bj <เงินเดิมพัน>` แบล็กแจ็ก • `!hilo` ไฮโล • `!slots` สล็อต\n"
                "`!att @คน` เปิดฉากปล้นกลางเมือง (ต้องอยู่ห้องเสียง) • `!challenge @คน` ท้าดวล PvP"))
            embed.add_field(name="🏪 ร้านค้า & อื่น ๆ", inline=False, value=(
                "`!shop` ร้านไอเทม • `!darkshop` / `!lightshop` ร้านยศสองฝ่าย\n"
                "`!rent` เช่าห้องส่วนตัว (`!extend` ต่ออายุ, `!set_room` ตั้งค่า)\n"
                "`!payment` เติมเงิน • `!my_orders` เช็คคำสั่งซื้อ • `!menu` เมนูปุ่มลัด"))
            return await ctx.send(embed=embed)

        if topic in ("สถานะ", "status"):
            cures, guards, cure_all = {}, {}, []
            for iid, it in config_loader.get_all_items().items():
                name, eff, val = it.get("name", f"#{iid}"), it.get("effect"), it.get("effect_value")
                if eff == "cure_status":
                    if val == "all":
                        cure_all.append(name)
                    else:
                        for k in (val if isinstance(val, list) else [val]):
                            cures.setdefault(k, []).append(name)
                elif eff in ("apply_status", "equip_artifact"):
                    for k in game_modifiers.STATUS_EFFECTS.get(str(val), {}).get("blocks", []):
                        guards.setdefault(k, []).append(name)
            lines = []
            for key, cfg in game_modifiers.STATUS_EFFECTS.items():
                if cfg.get("artifact"):
                    continue
                extra = []
                if key in cures:
                    extra.append("แก้: " + ", ".join(cures[key]))
                if key in guards:
                    extra.append("กัน: " + ", ".join(guards[key]))
                unit = "ก้าว" if cfg.get("tick") == "step" else "ไฟต์"
                lines.append(f"{cfg['label']} `{cfg.get('default_turns', 1)} {unit}`"
                             + (" — " + " / ".join(extra) if extra else ""))
            desc = "สถานะหมดเองเมื่อครบเวลา (นับเป็นก้าวเดิน/ไฟต์)"
            if cure_all:
                desc += f"\n💊 ล้างได้ทุกสถานะ: {', '.join(cure_all)}"
            embed = discord.Embed(title="📖 Codex — สถานะติดตัว", color=0x9b59b6, description=desc)
            chunk = ""
            for line in lines:  # ตัดลง field ละ ≤1024 ตัวอักษร (ลิมิต Discord — บทเรียนจาก !bag)
                if len(chunk) + len(line) + 1 > 1024:
                    embed.add_field(name="​", value=chunk, inline=False)
                    chunk = ""
                chunk += line + "\n"
            if chunk:
                embed.add_field(name="​", value=chunk, inline=False)
            return await ctx.send(embed=embed)

        if topic in ("ไอเทม", "ของ", "item", "items"):
            groups = {"use": [], "artifact": [], "equip": [], "material": []}
            for iid, it in sorted(config_loader.get_all_items().items(), key=lambda kv: int(kv[0])):
                name, eff = it.get("name", f"#{iid}"), it.get("effect")
                desc = _item_effect_desc(it)
                if str(iid) == "38":  # แว่นส่องสัจจะ: ไม่มี effect ใน config — ถูกหักอัตโนมัติตอนกดปุ่มตรวจ NPC (game_views อ้าง id 38 ตรง ๆ)
                    desc = "พกไว้เฉย ๆ — ใช้เองอัตโนมัติตอนตรวจตัวตน NPC งานหน้ากาก (ฟรี, เลนส์แตกหลังใช้)"
                price = f"💰{it['buy']:,}" if it.get("purchasable", True) and it.get("buy") else "ดรอป/คราฟเท่านั้น"
                if eff == "equip_artifact":
                    groups["artifact"].append(f"`{iid}` {name} — {desc}")
                elif desc:
                    groups["use"].append(f"`{iid}` {name} — {desc} ({price})")
                elif it.get("equip_key"):
                    groups["equip"].append(f"`{iid}` {name} ({price})")
                else:
                    groups["material"].append(f"`{iid}` {name} (ขายร้าน 💰{it.get('sell', 0):,})")
            embed = discord.Embed(
                title="📖 Codex — ไอเทมทั้งหมด", color=0x9b59b6,
                description="ใช้ของด้วย `!use <เลข>` — เลขไอเทมคือตัวหน้าแต่ละบรรทัด")
            sections = [("💊 ของใช้", groups["use"]), ("🏺 อาร์ติแฟกต์ (มีช่องเดียว — สวมทับ ของเก่าถูกทำลายถาวร!)", groups["artifact"]),
                        ("⚔️ อุปกรณ์สวมใส่", groups["equip"]), ("🧱 วัสดุคราฟ/ของขายร้าน", groups["material"])]
            for title, lines in sections:
                chunk, first = "", True
                for line in lines:  # ตัดท่อนละ ≤1024 (ลิมิต Discord)
                    if len(chunk) + len(line) + 1 > 1024:
                        embed.add_field(name=title if first else "​", value=chunk, inline=False)
                        chunk, first = "", False
                    chunk += line + "\n"
                if chunk:
                    embed.add_field(name=title if first else "​", value=chunk, inline=False)
            return await ctx.send(embed=embed)

        if topic in ("ทวีป", "continent", "continents"):
            embed = discord.Embed(
                title="📖 Codex — ทวีปทั้ง 9", color=0x9b59b6,
                description="การข้ามทวีปมีทางเดียว: **สุ่มเจอพาหนะ** ระหว่างผจญภัย (รู้ปลายทางเมื่อไปถึง)")
            for key, c in game_modifiers.CONTINENTS.items():
                weights = (c.get("mods") or {}).get("element_weights") or {}
                top = sorted(weights, key=weights.get, reverse=True)[:2]
                elem_txt = " ".join(game_modifiers.ELEMENTS[t]["label"] for t in top if t in game_modifiers.ELEMENTS) or "สมดุลทุกธาตุ"
                embed.add_field(name=c["label"], value=f"ธาตุชุกชุม: {elem_txt}", inline=True)
            return await ctx.send(embed=embed)

        embed = discord.Embed(
            title="📖 Codex — สารานุกรมนักผจญภัย", color=0x9b59b6,
            description=("เลือกหมวดที่อยากอ่าน:\n"
                         "`!codex วิธีเล่น` — ไกด์เริ่มต้นตั้งแต่เกิดจนออกผจญภัย\n"
                         "`!codex คำสั่ง` — คำสั่งผู้เล่นทั้งหมดแยกหมวด\n"
                         "`!codex ธาตุ` — ธาตุทั้ง 7, ตารางข่ม, passive ประจำเผ่า\n"
                         "`!codex สถานะ` — สถานะทั้งหมด + ไอเทมที่ใช้แก้/กัน\n"
                         "`!codex ไอเทม` — ไอเทมทุกชิ้น ใช้ทำอะไร ราคาเท่าไหร่\n"
                         "`!codex ทวีป` — ทวีปทั้ง 9 และธาตุประจำถิ่น"))
        await ctx.send(embed=embed)

    # --- โค้ดคำสั่ง !bag ---
    @commands.command(name="bag")
    async def check_bag(self, ctx): # 🚨 จุดสำคัญ: เติม self ลงไปตรงนี้ครับ
        user_id = ctx.author.id
        player = player_model.get_player(user_id)

        if not player:
            print(f"ERROR: [Bag] ไม่พบข้อมูลผู้เล่นสำหรับ User ID: {user_id}")
            await ctx.send("❌ ไม่พบข้อมูลตัวละครของคุณ! พิมพ์ `!play` เพื่อสร้างตัวละครก่อนน้า")
            return

        embed = build_bag_embed(ctx.author.display_name, ctx.author.display_avatar.url, player)
        await ctx.send(embed=embed)
    
    # ⏱️ เช็กเวลาออนไลน์ของตัวเอง
    @commands.command(name="mytime")
    @allowed_channel("bank")
    async def check_my_time(self, ctx):
        player = player_model.get_player(ctx.author.id)
        if not player:
            return await ctx.send("❌ คุณยังไม่มีข้อมูลในระบบ!")
        
        total_minutes = player.get("total_online_time", 0)
        hours = total_minutes // 60
        minutes = total_minutes % 60
        
        await ctx.send(f"👤 **{ctx.author.name}**\n⏱️ เวลาออนไลน์ทั้งหมดของคุณ: **{hours} ชั่วโมง {minutes} นาที**")

    # 🏆 เช็กอันดับ Top 10 เวลาออนไลน์
    @commands.command(name="toptime")
    @allowed_channel("bank")
    async def top_online_time(self, ctx):
        all_players = player_model.get_all_players() 
        
        if not all_players:
            return await ctx.send("❌ ยังไม่มีข้อมูลผู้เล่นในระบบ!")

        # เรียงลำดับจากมากไปน้อย
        top_players = sorted(all_players, key=lambda x: x.get("total_online_time", 0), reverse=True)[:10]
        
        embed = discord.Embed(title="🏆 10 อันดับนักผจญภัยที่ออนไลน์นานที่สุด", color=discord.Color.gold())
        
        msg = ""
        for i, p in enumerate(top_players, 1):
            user_id = p.get("user_id")
            time_m = p.get("total_online_time", 0)
            
            # ใช้ <@user_id> เพื่อแท็กชื่อผู้เล่นอัตโนมัติ
            msg += f"{i}. <@{user_id}> - `{time_m // 60} ชม. {time_m % 60} นาที`\n"
            
        embed.description = msg
        await ctx.send(embed=embed)
        
    # --- คำสั่ง !use <เลขไอเทม> ---
    @commands.command(name="use")
    async def use_item(self, ctx, item_id: str):
        item_cfg = config_loader.get_item_config(item_id)

        # 🧪 ยาพลิกธาตุ: ต้องมีธาตุประจำเผ่าก่อน (เช็คจากยศ — ทำได้เฉพาะตรงนี้ที่เห็น roles)
        if item_cfg and item_cfg.get("effect") == "apply_status" and item_cfg.get("effect_value") == "element_flux":
            player_elements = game_modifiers.resolve_player_elements([r.name for r in ctx.author.roles])
            if not player_elements:
                return await ctx.send("❌ **ยาพลิกธาตุต้องอาศัยพลังธาตุประจำเผ่า!** คุณยังไม่มียศเผ่า — รับยศเผ่าก่อนแล้วค่อยใช้ (ยายังอยู่ในกระเป๋า)")

        # 🎨 ผงสีรุ้ง: เปิดเมนูเลือกสีย้อมโปรไฟล์ (ผงถูกหักตอนยืนยันใน view)
        if item_cfg and item_cfg.get("effect") == "dye_profile":
            player = player_model.get_player(ctx.author.id)
            inv = player_model.load_inventory(player.get("inventory", ""))
            if str(item_id) not in inv:
                return await ctx.send(f"❌ คุณไม่มีไอเทมหมายเลข `{item_id}` ในกระเป๋า! (พิมพ์ `!bag` เพื่อเช็ก)")
            from bot.views.game_views import ProfileDyeView
            view = ProfileDyeView(ctx.author.id, item_id)
            view.message = await ctx.send("🎨 **เทผงสีรุ้งลงจานผสม** — เลือกสีที่จะย้อมโปรไฟล์ (ผงถูกใช้เมื่อยืนยัน):", view=view)
            return

        # 🎫 ตั๋วเรือเหมาลำ: เปิดเมนูเลือกทวีป (ตั๋วถูกหักตอนยืนยันใน view ไม่ใช่ตอนนี้)
        if item_cfg and item_cfg.get("effect") == "choose_continent":
            player = player_model.get_player(ctx.author.id)
            inv = player_model.load_inventory(player.get("inventory", ""))
            if str(item_id) not in inv:
                return await ctx.send(f"❌ คุณไม่มีไอเทมหมายเลข `{item_id}` ในกระเป๋า! (พิมพ์ `!bag` เพื่อเช็ก)")
            if player.get("current_state") in ("fighting", "dead") or player.get("dungeon_steps", 0) > 0:
                return await ctx.send("❌ ตอนนี้ออกเรือไม่ได้! (ติดการต่อสู้/อยู่ในดันเจี้ยน — เคลียร์ให้จบก่อน)")
            from bot.views.game_views import ContinentWarpView
            view = ContinentWarpView(ctx.author.id, item_id)
            view.message = await ctx.send(
                "🎫 **กัปตันเรือเหมาลำกางแผนที่โลก** — เลือกทวีปปลายทางได้เลย (ตั๋วจะถูกใช้เมื่อยืนยัน):",
                view=view)
            return

        ok, msg = apply_item_effect(ctx.author.id, item_id)
        await ctx.send(msg)

    @commands.command(name="drop")
    async def drop_item(self, ctx, item_id: str = None, amount: int = None):
        user_id = ctx.author.id
        player = player_model.get_player(user_id)
        
        if not player:
            return await ctx.send("❌ ไม่พบข้อมูลตัวละครของคุณ! พิมพ์ `!play` ก่อนนะ")

        # ---------------------------------------------------------
        # 1. 🧹 ถอดรหัสกระเป๋า (ใช้ Logic เดียวกับ !bag ของคุณอาเธอร์เป๊ะๆ)
        # ---------------------------------------------------------
        raw_inv = player.get("inventory", "")
        clean_inv = str(raw_inv)
        for char in ["(", ")", "[", "]", "'", '"', " "]:
            clean_inv = clean_inv.replace(char, "")
            
        inv_array = clean_inv.split(",") if clean_inv and clean_inv not in ["None", "null"] else []
        inv_array = [i for i in inv_array if i] # กันเหนียว กรองพวกค่าว่างที่อาจจะหลุดมาทิ้งไป
        
        capacity = player.get("capacity", 10)

        # ---------------------------------------------------------
        # 2. 🧳 กรณีที่พิมพ์แค่ !drop (แสดงรายการกระเป๋า)
        # ---------------------------------------------------------
        if item_id is None:
            from collections import Counter
            item_counts = Counter(inv_array)
            
            embed = discord.Embed(title="🗑️ โยนไอเทมทิ้ง", color=discord.Color.red())
            embed.add_field(name="ความจุกระเป๋า", value=f"{len(inv_array)} / {'ไม่จำกัด' if capacity == 0 else capacity}", inline=False)
            
            if not inv_array:
                embed.description = "*~ กระเป๋าว่างเปล่า ไม่มีอะไรให้ทิ้ง ~*"
            else:
                drop_text = "💡 **วิธีใช้:** พิมพ์ `!drop [เลขไอเทม] [จำนวน]` เพื่อทิ้งของ\n\n**รายการที่มี:**\n"
                all_items = config_loader.get_all_items()
                for i_id, count in item_counts.items():
                    if i_id in all_items:
                        item_name = all_items[i_id]["name"]
                        drop_text += f"**[{i_id}]** {item_name} x`{count}`\n"
                    else:
                        drop_text += f"**[{i_id}]** ❓ ไอเทมปริศนา x`{count}`\n"
                embed.description = drop_text
                
            embed.set_thumbnail(url=ctx.author.display_avatar.url)
            return await ctx.send(embed=embed)

        # ---------------------------------------------------------
        # 3. 🗑️ กรณีที่พิมพ์เพื่อทิ้งของ (เช่น !drop 22 1)
        # ---------------------------------------------------------
        if amount is None or amount <= 0:
            return await ctx.send("❌ โปรดระบุจำนวนที่ต้องการทิ้งให้ถูกต้อง เช่น `!drop 22 1`")

        # ตรวจสอบว่าในกระเป๋ามีของนี้พอไหม
        current_count = inv_array.count(item_id)
        if current_count < amount:
            item_name = config_loader.get_item_config(item_id).get("name", f"ไอเทมรหัส {item_id}")
            return await ctx.send(f"❌ คุณมี {item_name} ไม่พอให้ทิ้ง! (ในกระเป๋ามีแค่ {current_count} ชิ้น)")

        # ทำการลบไอเทมตามจำนวนที่ระบุ
        for _ in range(amount):
            inv_array.remove(item_id)
            
        # บันทึกข้อมูลกลับลงฐานข้อมูล (inv_array เป็น list แล้ว update_player_field จะแปลงเป็น JSON ให้เอง)
        player_model.update_player_field(user_id, "inventory", inv_array)
        
        # แสดงข้อความยืนยัน
        item_name = config_loader.get_item_config(item_id).get("name", "ไอเทมปริศนา")
        await ctx.send(f"🗑️ คุณได้โยน **{item_name}** ทิ้งไปจำนวน `{amount}` ชิ้นเรียบร้อยแล้ว!")
    
    @commands.command(name="give")
    async def give_item_to_player(self, ctx, member: discord.Member = None, item_id: str = None, amount: int = 1):
        # 1. เช็กความถูกต้องเบื้องต้น
        if member is None or item_id is None:
            return await ctx.send("❌ วิธีใช้: `!give @ชื่อเพื่อน [เลขไอเทม] [จำนวน]`\n💡 เช่น: `!give @Arthur 1 5`")
            
        if amount <= 0:
            return await ctx.send("❌ จำนวนไอเทมต้องมากกว่า 0!")
            
        if member.id == ctx.author.id:
            return await ctx.send("❌ คุณจะโอนของให้ตัวเองทำไมเนี่ย!")
            
        if member.bot:
            return await ctx.send("❌ บอทไม่ต้องการไอเทมของคุณหรอกนะ!")

        if not config_loader.get_item_config(item_id):
            return await ctx.send(f"❌ ไม่พบไอเทมรหัส `{item_id}` ในระบบ!")

        # 2. ดึงข้อมูลและถอดรหัสกระเป๋า "คนส่ง" (ตัวเราเอง)
        sender_id = ctx.author.id
        sender = player_model.get_player(sender_id)
        
        raw_inv_s = sender.get("inventory", "")
        clean_inv_s = str(raw_inv_s)
        for char in ["(", ")", "[", "]", "'", '"', " "]:
            clean_inv_s = clean_inv_s.replace(char, "")
        sender_inv = clean_inv_s.split(",") if clean_inv_s and clean_inv_s not in ["None", "null"] else []
        sender_inv = [i for i in sender_inv if i]

        # ตรวจสอบว่าคนส่งมีของพอไหม
        sender_item_count = sender_inv.count(item_id)
        item_name = config_loader.get_item_config(item_id)["name"]
        
        if sender_item_count < amount:
            return await ctx.send(f"❌ คุณมี {item_name} ไม่พอโอน! (ในกระเป๋าคุณมีแค่ {sender_item_count} ชิ้น)")

        # 3. ดึงข้อมูลและถอดรหัสกระเป๋า "คนรับ" (เพื่อน)
        receiver = player_model.get_player(member.id)
        if not receiver:
            return await ctx.send(f"❌ ไม่พบข้อมูลของ {member.display_name} ในระบบ (เขาต้องเคยพิมพ์เริ่มเล่นเกมก่อน)")

        raw_inv_r = receiver.get("inventory", "")
        clean_inv_r = str(raw_inv_r)
        for char in ["(", ")", "[", "]", "'", '"', " "]:
            clean_inv_r = clean_inv_r.replace(char, "")
        receiver_inv = clean_inv_r.split(",") if clean_inv_r and clean_inv_r not in ["None", "null"] else []
        receiver_inv = [i for i in receiver_inv if i]

        # เช็กความจุกระเป๋าคนรับ
        receiver_capacity = receiver.get("capacity", 10)
        if len(receiver_inv) + amount > receiver_capacity:
            free_space = receiver_capacity - len(receiver_inv)
            return await ctx.send(f"❌ กระเป๋าของ {member.display_name} เต็มแล้ว! (รับเพิ่มได้อีกแค่ {free_space} ชิ้น)")

        # 4. ทำการโอนย้ายไอเทม (หักจากเรา -> ย้ายไปเพื่อน)
        for _ in range(amount):
            sender_inv.remove(item_id)
            receiver_inv.append(item_id)

        # 5. บันทึกข้อมูลกลับลงฐานข้อมูลทั้ง 2 คน
        player_model.update_player_field(sender_id, "inventory", sender_inv)
        player_model.update_player_field(member.id, "inventory", receiver_inv)

        # 6. แจ้งเตือนความสำเร็จ
        await ctx.send(f"🤝 **โอนไอเทมสำเร็จ!**\nคุณได้มอบ `{item_name}` จำนวน `{amount}` ชิ้น ให้กับ {member.mention} เรียบร้อยแล้ว!")

    # ==========================================
    # ⚔️ คำสั่ง PVP (!att @ผู้ใช้)
    # ==========================================
    @allowed_channel("arena") # 🛠️ ใช้ Decorator บล็อกห้อง
    @not_arrested() # 🛠️ บล็อกคนติดคุก
    @commands.command(name="att")
    async def pvp_attack(self, ctx, member: discord.Member):
        # 1. ป้องกันการตีตัวเอง
        if member.id == ctx.author.id:
            return await ctx.send("❌ คุณไม่สามารถเปิดฉากโจมตีตัวเองได้!")

        # 2. เช็กสถานะผู้โจมตี (ต้องอยู่ในห้องเสียง)
        if not ctx.author.voice or not ctx.author.voice.channel:
            return await ctx.send(f"❌ {ctx.author.mention} **การประลองถูกยกเลิก!** คุณต้องอยู่ในห้องเสียงก่อนถึงจะท้าดวลได้!")

        # 3. เช็กสถานะเป้าหมาย (ต้องออนไลน์อยู่)
        if member.status == discord.Status.offline:
            return await ctx.send(f"⚠️ **ล้มเหลว!** เป้าหมาย {member.mention} ไม่ได้ออนไลน์อยู่! (ลูกผู้ชายเขาไม่ลอบโจมตีคนหลับกันหรอกนะ!)")
        
        # 4.เช็กว่าเป้าหมายต้องอยู่ในห้องเสียงด้วย
        if not member.voice or not member.voice.channel:
            return await ctx.send(f"⚠️ {member.mention} ไม่ได้อยู่ในห้องเสียง เลยท้าดวลไม่ได้นะ!")

        # โหลดข้อมูลผู้เล่นทั้งสองฝ่าย
        attacker = player_model.get_player(ctx.author.id)
        defender = player_model.get_player(member.id)
        
        if not attacker or not defender:
            return await ctx.send("❌ ไม่พบข้อมูลตัวละครของฝ่ายใดฝ่ายหนึ่งในฐานข้อมูล!")

        # 5. เช็กสถานะห้ามต่อสู้ (village หรือ death)
        if attacker.get("current_state") in ["village", "death"] or defender.get("current_state") in ["village", "death"]:
            return await ctx.send("❌ ไม่สามารถต่อสู้ได้เนื่องจากมีฝ่ายใดฝ่ายหนึ่งอยู่ในเซฟโซนหมู่บ้าน หรืออยู่ในสถานะเสียชีวิตแล้ว!")

        # 6. เช็กเงื่อนไขเลเวลต่ำกว่า 20
        if attacker.get("level", 0) < 20 or defender.get("level", 0) < 20:
            return await ctx.send("❌ ระบบ PVP รองรับเฉพาะผู้กล้าเลเวล 20 ขึ้นไปเท่านั้น! (และห้ามรังแกผู้เล่นเลเวลต่ำกว่า 20)")
        
        now = time.time()
        if ctx.author.id in self.pk_cooldowns:
            cooldown_end = self.pk_cooldowns[ctx.author.id]
            if now < cooldown_end:
                remaining = int(cooldown_end - now)
                minutes = remaining // 60
                seconds = remaining % 60
                return await ctx.send(f"⏳ **คุณอยู่ในช่วงพักทำใจหลังการสังหาร!** โปรดรออีก `{minutes} นาที {seconds} วินาที` จึงจะสั่งโจมตีครั้งถัดไปได้")
        
        #คำนวณความห่างของเลเวลเพื่อเพิ่มความยากในการทอย
        lv_diff = attacker.get("level", 0) - defender.get("level", 0)
        
        # แต้มเต๋าพื้นฐาน 1-20 บวกรวมแต้มโบนัสตามระดับเลเวล
        atk_bonus = lv_diff if lv_diff > 0 else 0
        def_bonus = abs(lv_diff) if lv_diff < 0 else 0

        atk_roll = random.randint(1, 20) + atk_bonus
        def_roll = random.randint(1, 20) + def_bonus

        # หาผู้ชนะจากการทอยเต๋า
        if atk_roll == def_roll:
            return await ctx.send(f"⚔️ **{ctx.author.display_name}** บุกโจมตี **{member.display_name}** แต่แต้มเต๋าเสมอกันที่ `{atk_roll}` แต้ม! ทั้งคู่ตั้งรับและปัดป้องอาวุธไว้ได้!")

        if atk_roll > def_roll:
            winner, loser = attacker, defender
            w_member, l_member = ctx.author, member
            base_dmg = atk_roll
        else:
            winner, loser = defender, attacker
            w_member, l_member = member, ctx.author
            base_dmg = def_roll

        # 4. คำนวณพลังโจมตีอาวุธผู้ชนะ และ พลังป้องกันเกราะผู้แพ้
        w_weapon = winner.get("weapon", "None")
        w_atk_bonus = config_loader.get_weapon_stats(w_weapon).get("atk", 0)

        l_armor = loser.get("armor", "None")
        l_def_bonus = int(config_loader.get_armor_stats(l_armor).get("hp", 0) * 0.2)

        # สรุปความเสียหายรวม (ขั้นต่ำ 1 ดาเมจ)
        final_damage = max(1, base_dmg + w_atk_bonus - l_def_bonus)
        
        # หักลบพลังชีวิตผู้แพ้
        loser_current_hp = loser.get("hp", 100)
        loser_new_hp = max(0, loser_current_hp - final_damage)
        player_model.update_player_field(l_member.id, "hp", loser_new_hp)

        # 5. เช็กผลการตาย (HP เหลือ 0) และการให้รางวัล
        death_status_text = ""
        reward_text = "" 

        if loser_new_hp <= 0:
            # --- 🏆 ระบบให้รางวัลผู้ชนะ ---
            reward_exp = 100 + (loser.get("level", 1) * 1000)  
            reward_gold = 500 + (loser.get("level", 1) * 500) 
            
            is_lvl_up, new_lvl, new_exp = player_model.add_exp(w_member.id, reward_exp)
            
            new_winner_cash = winner.get("cash", 0) + reward_gold
            player_model.update_player_field(w_member.id, "cash", new_winner_cash)
            
            lvl_up_msg = f"\n✨ **Level Up!** คุณเลเวลอัปเป็น {new_lvl}!" if is_lvl_up else ""
            reward_text = f"\n💰 **ได้รับรางวัล:** `{reward_gold}` ทอง | `EXP +{reward_exp}`{lvl_up_msg}"
            
            cooldown_seconds = random.randint(300, 600) # สุ่ม 5 ถึง 10 นาที
            self.pk_cooldowns[ctx.author.id] = time.time() + cooldown_seconds
            player_model.update_player_field(l_member.id, "current_state", "death")
            death_status_text = f"\n💀 **☠️ สิ้นชีพ!** พลังชีวิตของ {l_member.mention} หมดลงและเข้าสู่สถานะเสียชีวิต!"

        # ==========================================
        # 🧠 6. ระบบสูญเสียสติ (Sanity) ของผู้โจมตี
        # ==========================================
        sanity_loss = 5 + int(attacker.get("level", 1) * 0.25)
        current_sanity = attacker.get("sanity", 100)
        new_sanity = current_sanity - sanity_loss
        
        # อัปเดตสติลงฐานข้อมูล
        player_model.update_player_field(ctx.author.id, "sanity", new_sanity)
        sanity_text = f"\n🧠 **สติสัมปชัญญะ (ผู้โจมตี):** ลดลง `{sanity_loss}` หน่วย (ปัจจุบัน: {new_sanity})"
        karma_text = ""

        # เช็กเงื่อนไขสติแตก (ค่าสติติดลบ) - จะเช็กเฉพาะตอนผู้โจมตีเป็นฝ่ายเปิด
        if new_sanity < 0:
            deficit = abs(new_sanity) 
            trigger_chance = min(0.90, 0.10 + (deficit * 0.02))
            
            if random.random() < trigger_chance:                
                event_type = random.choice(["arrest", "execute"])
                
                if event_type == "arrest":
                    jail_mins = 10 + (deficit * 3)
                    jail_until = time.time() + (jail_mins * 60)
                    
                    player_model.update_player_fields(ctx.author.id, {
                        "current_state": "arrested",
                        "arrest_until": jail_until
                    })
                    karma_text = f"\n\n🚨 **เวรกรรมตามสนอง!** ความคลุ้มคลั่งทำให้ {ctx.author.mention} ถูกจับเข้าคุกเป็นเวลา `{jail_mins}` นาที!"
                    
                elif event_type == "execute":
                    money_penalty = 1000 + (deficit * 200)
                    level_penalty = 1 + int(deficit / 10)
                    
                    atk_current_cash = attacker.get("cash", 0)
                    atk_current_level = attacker.get("level", 1)
                    
                    new_cash = max(0, atk_current_cash - money_penalty)
                    new_level = max(1, atk_current_level - level_penalty)
                    
                    player_model.update_player_fields(ctx.author.id, {
                        "cash": new_cash,
                        "level": new_level,
                        "current_state": "death",
                        "hp": 0
                    })
                    karma_text = f"\n\n⚖️ **ถูกทางการวิสามัญ!** {ctx.author.mention} คลุ้มคลั่งจนถูกทหารรักษาพระนครประหารชีวิต!\n💸 ถูกยึดทรัพย์ `{money_penalty}` ทอง และถูกลดเลเวลลง `{level_penalty}` ระดับ!"

        # 7. ส่งข้อความสรุปผลการประลอง (นำ Sanity Text เข้ามารวมแล้ว)
        embed = discord.Embed(
            title="⚔️ ผลการดวลศัสตราวุธ ลานประลอง ⚔️",
            description=f"**{w_member.display_name}** ทอยได้ `{base_dmg}` แต้ม ชนะการประลองในตานี้!\n"
                        f"💥 สร้างความเสียหายใส่ **{l_member.display_name}** จำนวน `💥 {final_damage}` หน่วย\n"
                        f"🩸 พลังชีวิตของ {l_member.display_name}: `{loser_current_hp}` ➔ `{loser_new_hp}`"
                        f"{death_status_text}"
                        f"{reward_text}"
                        f"\n{'-'*30}"
                        f"{sanity_text}"
                        f"{karma_text}",
            color=discord.Color.red()
        )
        await ctx.send(embed=embed)

    # ==========================================
    # 👻 ระบบดักจับวิญญาณ (ห้ามคนตายพิมพ์แชทช่องอื่น)
    # ==========================================
    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot:
            return

        player = player_model.get_player(message.author.id)
        if not player:
            return

        if player.get("current_state") == "death":
            # 1. ยกเว้น: ถ้าเป็นแชทโลก
            if message.channel.name == "⌒🌍chat╯แชทโลก":
                return
            
            # 2. ยกเว้น: ถ้าผู้เล่นพิมพ์ !use 28 เพื่อใช้ใบชุบ (เช็กจากข้อความ)
            if message.content.strip() == "!use 28":
                return # ปล่อยผ่านให้ระบบคำสั่งไปทำงานต่อเอง
            
            # 3. ถ้าไม่ใช่แชทโลก และไม่ใช่การพิมพ์ใช้ใบชุบ ให้ลบข้อความ
            try:
                await message.delete()
            except discord.Forbidden:
                pass
                
            # 4. ส่งข้อความเตือน (เช็กสถานะ last_event)
            if player.get("last_event") != "death_warned":
                view = DeathRespawnView(message.author.id)
                warning_msg = await message.channel.send(
                    f"👻 {message.author.mention} **คุณเสียชีวิตอยู่!** วิญญาณไม่สามารถสื่อสารในช่องทางนี้ได้\n"
                    f"ต้องการจ่ายเงิน `1,000` ทอง เพื่อกลับไปเกิดใหม่ หรือใช้ใบชุบชีวิต (`!use 28`) หรือไม่?",
                    view=view
                )
                view.message = warning_msg
                player_model.update_player_field(message.author.id, "last_event", "death_warned")

    # 📜 คำสั่งเช็กสูตรคราฟ (ปรับให้ดึงจากโครงสร้างใหม่)
    @commands.command(name="recipes")
    async def show_recipes(self, ctx):
        msg = "📜 **สูตรการคราฟไอเทม (พิมพ์ `!craft [เลขไอเทม]` เพื่อเริ่มคราฟ):**\n"
        all_items = config_loader.get_all_items()
        for item_id in all_items:
            data = config_loader.get_crafting_recipe(item_id)
            if not data:
                continue
            name = all_items[item_id]['name']
            recipe = data["recipe"]
            fail_rate = int(data["fail_rate"] * 100)
            ing_list = [f"{all_items[ing_id]['name']} x{amt}" for ing_id, amt in recipe.items()]
            # เพิ่ม [ID: item_id] เข้าไปหน้าชื่อ
            msg += f"• **[ID: {item_id}] {name}** (Fail: {fail_rate}%): ใช้ {', '.join(ing_list)}\n"
        await ctx.send(msg)

    # 🛠️ คำสั่งคราฟไอเทม (ปรับให้ใช้ fail_rate ของแต่ละไอเทม)
    @commands.command(name="craft")
    async def craft_item(self, ctx, item_id: str = None):
        # เริ่มการ Debug
        print(f"🔧 [DEBUG] เริ่มต้นการคราฟ | User: {ctx.author.id} | ไอเทม ID: {item_id}")
        
        try:
            if not item_id or not config_loader.get_crafting_recipe(item_id):
                return await ctx.send("❌ รหัสไอเทมนี้ไม่มีสูตรคราฟ หรือรหัสไม่ถูกต้อง!")

            player = player_model.get_player(ctx.author.id)
            raw_inv = player.get("inventory", [])

            # 🛠️ เรียกใช้ผ่าน player_model ได้เลย!
            inv_list = player_model.load_inventory(raw_inv)

            recipe_data = config_loader.get_crafting_recipe(item_id)
            recipe = recipe_data["recipe"]
            fail_rate = recipe_data.get("fail_rate", 0.2)
            
            # 1. เช็กวัตถุดิบ
            for ing_id, amount in recipe.items():
                ing_id_str = str(ing_id)
                current_count = inv_list.count(ing_id_str)
                if current_count < amount:
                    needed_name = config_loader.get_item_config(ing_id_str).get("name", "Unknown")
                    return await ctx.send(f"❌ วัตถุดิบไม่พอ! คุณขาด `{needed_name}`")

            # 2. เช็กกระเป๋าเต็ม
            capacity = player.get("capacity", 10)
            if capacity != 0 and len(inv_list) >= capacity:
                return await ctx.send("⚠️ กระเป๋าของคุณเต็ม!")

            # 3. โอกาสล้มเหลว
            if random.random() < fail_rate:
                for ing_id, amount in recipe.items():
                    ing_id_str = str(ing_id)
                    for _ in range((amount + 1) // 2): # เสียครึ่งนึง
                        if ing_id_str in inv_list: inv_list.remove(ing_id_str)
                player_model.update_player_field(ctx.author.id, "inventory", json.dumps(inv_list))
                return await ctx.send(f"💥 **ล้มเหลว ({int(fail_rate*100)}%)!** วัตถุดิบเสียหายไปบางส่วน!")

            # 4. คราฟสำเร็จ
            for ing_id, amount in recipe.items():
                ing_id_str = str(ing_id)
                for _ in range(amount):
                    inv_list.remove(ing_id_str)
                    
            inv_list.append(str(item_id))
            player_model.update_player_field(ctx.author.id, "inventory", json.dumps(inv_list))
            
            craft_name = config_loader.get_item_config(item_id)["name"]
            await ctx.send(f"✨ คราฟสำเร็จ! คุณได้รับ `{craft_name}` 1 ชิ้น!")

        except Exception as e:
            # ส่วนนี้คือไม้ตาย! ถ้าโค้ดพังตรงไหน มันจะเด้งมาที่นี่
            print(f"❌ [CRITICAL ERROR] การคราฟพัง! สาเหตุ: {e}")
            traceback.print_exc() # แสดงบรรทัดที่พังใน Console
            await ctx.send(f"⚠️ ระบบคราฟมีปัญหาทางเทคนิค! (Error: {str(e)})")
            
    # สแกนผู้เล่นว่าตีได้หรือไม่
    @allowed_channel("arena") # 🛠️ ใช้ Decorator บล็อกห้อง
    @not_arrested() # 🛠️ บล็อกคนติดคุก
    @commands.command(name="scan")
    async def scan_target(self, ctx, member: discord.Member):
        # 1. โหลดข้อมูลเป้าหมายจาก DB
        target = player_model.get_player(member.id)
        if not target:
            return await ctx.send(f"❌ ไม่พบข้อมูลของ {member.name} ในฐานข้อมูล!")

        # 2. ตรวจสอบสถานะและเงื่อนไข
        lvl = target.get("level", 1)
        state = target.get("current_state", "unknown")
        is_online = member.status != discord.Status.offline
        in_voice = member.voice is not None
        
        # 3. สรุปผล
        can_attack = (lvl >= 20 and state not in ["village", "death"] and is_online and in_voice)
        
        status_msg = (
            f"🔍 **รายงานการสแกนเป้าหมาย: {member.name}**\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"📊 **เลเวล:** {lvl} {'✅' if lvl >= 20 else '❌'}\n"
            f"📍 **สถานที่:** {state} {'✅' if state not in ['village', 'death'] else '❌'}\n"
            f"🟢 **ออนไลน์:** {'ใช่' if is_online else 'ไม่ใช่'} {'✅' if is_online else '❌'}\n"
            f"🎧 **อยู่ในห้องเสียง:** {'ใช่' if in_voice else 'ไม่ใช่'} {'✅' if in_voice else '❌'}\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"⚔️ **ผลลัพธ์:** {'**[ตีได้! ล่าได้เลย!]**' if can_attack else '**[ยังตีไม่ได้/เงื่อนไขไม่ครบ]**'}"
        )
        
        await ctx.send(status_msg)

# 🚨 ลบอันที่ซ้ำออกเหลือแค่อันเดียว
async def setup(bot):
    await bot.add_cog(PlayerCommands(bot))