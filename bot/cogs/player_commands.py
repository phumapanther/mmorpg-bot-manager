import discord
from collections import Counter
from discord.ext import commands
import random
import bot.models.player_model as player_model
import time
import sqlite3
from contextlib import contextmanager
from bot.utils import not_arrested, allowed_channel, main_server_only, adventure_room_only, has_permission
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
        cfg = game_modifiers.status_cfg(str(val))   # โชว์เทิร์นตามที่ตั้งใน Panel
        unit = "ก้าว" if cfg.get("tick") == "step" else "ไฟต์"
        return f"ติดบัฟ {cfg.get('label', val)} ({cfg.get('default_turns', 1)} {unit})"
    if eff == "gamble_status":
        chance = it.get("effect_amount", 50)
        return f"เสี่ยงดวง {chance}/{100 - chance}: สุ่มบัฟดี 1 ตัว หรือสุ่มสถานะร้าย 1 ตัว"
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


def bank_action(user_id, action, amount, target_id=None):
    """ฝาก/ถอน/โอน — ตรรกะกลางที่ทั้งคำสั่งพิมพ์ (!deposit/!withdraw/!transfer) และปุ่มเมนูเรียกใช้
    คืน (สำเร็จ: bool, ข้อความ: str) — เช็คติดคุกในนี้ด้วย เพราะปุ่มไม่ผ่าน decorator @not_arrested"""
    player = player_model.get_player(user_id)
    if not player:
        return False, "❌ ไม่พบข้อมูลตัวละครของคุณ! พิมพ์ `!play` ก่อนนะ"
    if player.get("current_state") == "arrested" and time.time() < int(player.get("arrest_until", 0) or 0):
        return False, "❌ คุณติดคุกอยู่ ทำธุรกรรมไม่ได้! รอพ้นโทษก่อนนะ"
    if amount <= 0:
        return False, "❌ จำนวนเงินต้องมากกว่า 0!"

    if action == "deposit":
        if player.get("cash", 0) < amount:
            return False, "❌ เงินสดไม่พอฝาก!"
        player_model.update_player_field(user_id, "cash", player["cash"] - amount)
        player_model.update_player_field(user_id, "bank", player.get("bank", 0) + amount)
        return True, f"💰 ฝากเงินเข้าธนาคารเรียบร้อย: `{amount:,}` ทอง"

    if action == "withdraw":
        if player.get("bank", 0) < amount:
            return False, "❌ เงินในธนาคารไม่พอถอนครับ!"
        player_model.update_player_field(user_id, "bank", player["bank"] - amount)
        player_model.update_player_field(user_id, "cash", player.get("cash", 0) + amount)
        return True, f"💸 ถอนเงินออกจากธนาคารเรียบร้อย: `{amount:,}` ทอง"

    if action == "transfer":
        if target_id == user_id:
            return False, "❌ โอนให้ตัวเองไม่ได้นะ!"
        if player.get("bank", 0) < amount:
            return False, "❌ เงินในธนาคารไม่พอโอน!"
        target = player_model.get_player(target_id)
        if not target:
            return False, "❌ ไม่พบข้อมูลผู้เล่นปลายทาง"
        player_model.update_player_field(user_id, "bank", player["bank"] - amount)
        player_model.update_player_field(target_id, "bank", target.get("bank", 0) + amount)
        return True, f"💸 โอนเงิน `{amount:,}` ทอง ให้ <@{target_id}> สำเร็จ!"

    return False, "❌ ไม่รู้จักธุรกรรมนี้"


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
            # โชว์สถานะที่มีจริงตอนนี้ — กันงงกรณี "ราก" สองชนิด (รากล็อกเต๋าชั่วขณะไม่ใช่สถานะ รักษาไม่ได้/ไม่ต้องรักษา)
            now = " ".join(game_modifiers.STATUS_EFFECTS[k]["label"] for k in statuses) or "ไม่มีสถานะติดตัวเลย"
            return False, (f"❌ ตอนนี้คุณไม่มีสถานะที่ **{item_name}** รักษาได้ (ไอเทมไม่ถูกใช้)\n"
                           f"🔎 สถานะปัจจุบันของคุณ: {now}")
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

    # 🧪 กรณี: ยาสุ่มของแม่มด (effect: "gamble_status" + effect_value: {good: [...], bad: [...]}
    #    + effect_amount: % โอกาสออกดี, ไม่ตั้ง = 50) — พนันสถานะ 1 ตัวจาก pool
    elif item_info.get("effect") == "gamble_status":
        pool_cfg = item_info.get("effect_value") or {}
        good = [k for k in pool_cfg.get("good", []) if k in game_modifiers.STATUS_EFFECTS]
        bad = [k for k in pool_cfg.get("bad", []) if k in game_modifiers.STATUS_EFFECTS]
        if not good or not bad:
            return False, "❌ ไอเทมนี้ตั้งค่า pool สถานะไว้ไม่ถูกต้อง (แจ้งแอดมินตรวจ config)"
        good_chance = item_info.get("effect_amount", 50)
        if random.randint(1, 100) <= good_chance:
            key, flavor = random.choice(good), "✨ **ยาเรืองประกายสีทองอร่าม!** โชคเข้าข้างคุณ"
        else:
            key, flavor = random.choice(bad), "💀 **ยาขุ่นดำกลายเป็นสีม่วงเน่า...** แม่มดหัวเราะแหลมลั่น"
        statuses = game_modifiers.apply_status(game_modifiers.parse_statuses(player), key)
        player_model.update_player_field(user_id, "status_effects", statuses)
        label = game_modifiers.STATUS_EFFECTS[key]["label"]
        if key in statuses:
            msg = f"🧪 คุณกรอกยาสุ่มของแม่มดลงคอ... {flavor} — ได้รับสถานะ {label}!"
        else:
            msg = f"🧪 คุณกรอกยาสุ่มของแม่มดลงคอ... {flavor} — แต่ร่างกายคุณต้านทาน {label} ไว้ได้!"

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
    # 📅 C1: นับเควสรายวัน (ใช้ไอเทม)
    try:
        from bot import daily as _daily
        _daily.track(user_id, "item", 1)
    except Exception as _e:
        print(f"⚠️ [daily] นับเควสใช้ไอเทมพัง: {_e}")
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

        # 🎒 B5: จัดกลุ่มตามประเภท — หาของที่ต้องการเจอเร็วขึ้นมาก
        groups = {"use": [], "equip": [], "artifact": [], "junk": []}
        junk_value = 0
        for item_id in sorted(item_counts, key=_sort_key):
            count = item_counts[item_id]
            data = all_items.get(item_id, {})
            name = data.get("name", "❓ ไอเทมปริศนา")
            line = f"`{item_id}` {name} ×**{count}**"
            eff = data.get("effect")
            if eff == "equip_artifact":
                groups["artifact"].append(line)
            elif data.get("equip_key"):
                groups["equip"].append(line)
            elif eff or data.get("type") == "use":
                groups["use"].append(line)
            else:
                groups["junk"].append(line + f" *(ขายได้ {data.get('sell', 0):,}/ชิ้น)*")
                junk_value += int(data.get("sell", 0)) * count

        cap_line = f"({len(inv_array)} / {'ไม่จำกัด' if capacity == 0 else capacity})"
        sections = [
            (f"💊 ของใช้ {cap_line}", groups["use"]),
            ("🏺 อาร์ติแฟกต์", groups["artifact"]),
            ("⚔️ อุปกรณ์สวมใส่", groups["equip"]),
            (f"🧱 วัสดุ/ของขาย — ขายหมดได้ **{junk_value:,}** ทอง", groups["junk"]),
        ]
        for title, lines in sections:
            if not lines:
                continue
            chunk, first = "", True
            for line in lines:  # ตัดท่อนละ ≤1024 ตามลิมิต Discord
                if len(chunk) + len(line) + 1 > 1024:
                    embed.add_field(name=title if first else "​", value=chunk, inline=False)
                    chunk, first = "", False
                chunk += line + "\n"
            if chunk:
                embed.add_field(name=title if first else "​", value=chunk, inline=False)

    embed.set_thumbnail(url=avatar_url)
    return embed


def build_codex_embed(topic=""):
    """สร้าง embed คู่มือรายหัวข้อ — ใช้ร่วมกันระหว่าง !codex และปุ่ม 📖 ในเมนู"""
    topic = (topic or "").strip().lower()

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
        return embed

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
        embed.add_field(name="6️⃣ เส้นทางสายเทพ (ระบบปลายเกม)", inline=False, value=(
            "📕 `!bestiary` สมุดล่ามอน — เก็บครบทวีปรับแสน ครบสมุดรับล้าน\n"
            "🎯 `!bounty` ล่าหัวคนสติติดลบ รับทองไม่บาป • ⚔️ `!war` สงครามฝ่ายมนุษย์↔ปีศาจ (ธีมพิเศษ)\n"
            "🏰 `!guild` ก่อตั้งกิลด์ + ประกาศศึก `!warguild` ชิงเดิมพันคลัง — `!codex กิลด์`"))
        return embed

    if topic in ("กิลด์", "guild", "กิลด์วอร์"):
        embed = discord.Embed(
            title="📖 Codex — กิลด์ & กิลด์วอร์", color=0x9b59b6,
            description="รวมตัวตั้งแก๊ง สร้างบ้าน สะสมคลัง แล้วเปิดศึกชิงเงินกิลด์อื่น")
        embed.add_field(name="🏰 ก่อตั้งกิลด์", inline=False, value=(
            "`!guild create <ชื่อ>` — ค่าก่อตั้ง `3,000,000,000` ทอง**สด**\n"
            "ได้ทันที: ยศกิลด์ (สีสุ่ม) + ห้องเสียงส่วนตัวเฉพาะสมาชิก\n"
            "`!guild rename <ชื่อใหม่>` เปลี่ยนชื่อ (ค่าธรรมเนียม `100,000,000`)"))
        embed.add_field(name="👥 สมาชิก", inline=False, value=(
            "หัวหน้า: `!guild invite @คน` (มีปุ่มยืนยัน) / `!guild kick @คน`\n"
            "สมาชิก: `!guild leave` ออกเอง • ทุกคนอยู่ได้ **1 กิลด์เท่านั้น**\n"
            "`!guild info` หน้ากิลด์ • `!guild disband` ยุบ (หัวหน้า — คลังคืนธนาคารหัวหน้า)"))
        embed.add_field(name="💰 คลังกิลด์", inline=False, value=(
            "`!guild deposit <จำนวน>` ทุกคนฝากได้ (หักธนาคารตัวเอง) — **ฝากแล้วถอนเองไม่ได้**\n"
            "หัวหน้าเท่านั้น: `!guild withdraw <จำนวน>` / `!guild pay @สมาชิก <จำนวน>`"))
        embed.add_field(name="⚔️ กิลด์วอร์", inline=False, value=(
            "`!warguild @หัวหน้ากิลด์อื่น [เดิมพัน]` — หัวหน้าท้าหัวหน้า วางเดิมพันคลังเท่ากัน\n"
            "รับคำท้า → เปิด**ห้องรบ 30 นาที** (เงียบเกิน 1 นาที = จบศึกทันที)\n"
            "`!fight` ในห้องรบ: ⚔️ ทหารศัตรู `+1` • 👑 หัวหน้า `+10` • 🛡️ ป้อม = ศัตรู `-10` • 🏰 ปราสาท = ศัตรู `-100`\n"
            "จบศึก: แต้มมากกว่าชนะ **รับกองกลาง 2×เดิมพัน** เข้าคลังกิลด์ (เสมอ = คืนเดิมพัน)"))
        return embed

    if topic in ("คำสั่ง", "commands", "cmd"):
        embed = discord.Embed(
            title="📖 Codex — คำสั่งผู้เล่นทั้งหมด", color=0x9b59b6,
            description="พิมพ์ในห้องที่เซิร์ฟกำหนดไว้ (บางคำสั่งจำกัดห้อง) — `!menu` มีปุ่มลัดของที่ใช้บ่อย")
        embed.add_field(name="🗺️ ผจญภัย", inline=False, value=(
            "`!adv` สร้างห้องผจญภัยส่วนตัว • `!play` เริ่มออกเดินทาง\n"
            "`!profile` (`!info`) โปรไฟล์+ธาตุ+อาร์ติแฟกต์ • `!scan @คน` ส่องข้อมูลคนอื่น\n"
            "`!codex <หมวด>` สารานุกรมกติกา • `!reward` รับรางวัลประจำยศ\n"
            "`!bestiary` สมุดสะสมมอนสเตอร์ (ล่าครบมีโบนัสทอง)\n"
            "`!daily` **ภารกิจรายวัน + เช็คอินต่อเนื่อง** — ทำครบรับทองก้อนโต!\n"
            "`!season` **ซีซั่นพาสรายเดือน** • `!ach` **ความสำเร็จ + ตำแหน่งอวด**\n"
            "`!pet` **สัตว์เลี้ยง** ที่จับมาได้ — ติดตัวช่วยหนุนเต๋าตอนสู้"))
        embed.add_field(name="🎒 กระเป๋า & ไอเทม", inline=False, value=(
            "`!bag` ดูกระเป๋า *(มีปุ่ม 🔨 คราฟ · 🗑️ ทิ้ง · 🧱 ขายวัสดุ ในตัว)* • `!use <เลข>` • `!drop <เลข>`\n"
            "`!give @คน <เลข>` ส่งของให้เพื่อน • `!recipes` สูตรคราฟ • `!craft <เลข>` คราฟของ"))
        embed.add_field(name="💰 เงิน & ธนาคาร", inline=False, value=(
            "`!bank` ยอดธนาคาร *(มีปุ่ม 💰 ฝาก · 💸 ถอน · 🤝 โอน ในตัว)* • `!deposit` • `!withdraw`\n"
            "`!transfer @คน <จำนวน>` โอน • `!beg` ขอทาน • `!rob @คน` ปล้น (เสี่ยงติดคุก!)\n"
            "`!top` **อันดับรวมทุกหมวด** (🗓️ สัปดาห์นี้/เศรษฐี/เลเวล/แชท/ออนไลน์ — กดปุ่มสลับได้)\n"
            "`!market` **ตลาดผู้เล่น** — `sell` ลงขาย · `buy` ซื้อ · `cancel` เอาคืน · `mine` ของฉัน\n"
            "`!mytext` `!mytime` สถิติตัวเอง"))
        embed.add_field(name="🎰 คาสิโน & PvP", inline=False, value=(
            "`!bj <เงินเดิมพัน>` แบล็กแจ็ก • `!hilo` ไฮโล • `!slots` สล็อต\n"
            "`!att @คน` เปิดฉากปล้นกลางเมือง (ต้องอยู่ห้องเสียง) • `!challenge @คน` ท้าดวล PvP\n"
            "`!bounty` กระดานล่าค่าหัว — ฆ่าคนสติติดลบรับทอง ไม่เสียสติ\n"
            "`!war` สกอร์สงครามฝ่าย มนุษย์↔ปีศาจ (ธีมสงคราม)\n"
            "`!warguild @หัวหน้า [เดิมพัน]` ประกาศกิลด์วอร์ 30 นาที • `!fight` สู้ในห้องรบ"))
        embed.add_field(name="🏪 ร้านค้า & อื่น ๆ", inline=False, value=(
            "`!shop` ร้านไอเทม • `!darkshop` / `!lightshop` ร้านยศสองฝ่าย\n"
            "`!rent` เช่าห้องส่วนตัว (`!extend` ต่ออายุ, `!set_room` ตั้งค่า)\n"
            "`!guild` ระบบกิลด์: create/invite/deposit/pay (ก่อตั้ง 3,000,000,000 ทองสด)\n"
            "`!marry @คน` **ชวนเป็นคู่หู** • `!partner` สถานะคู่ • `!divorce` เลิก\n"
            "`!payment` เติมเงิน • `!my_orders` เช็คคำสั่งซื้อ • `!menu` เมนูปุ่มลัด"))
        return embed

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
        for key in game_modifiers.STATUS_EFFECTS:
            cfg = game_modifiers.status_cfg(key)    # คู่มือต้องบอกเทิร์นตามที่ตั้งใน Panel
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
        return embed

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
            description="ใช้ของด้วย `!use <เลข>` — เลขไอเทมคือตัวหน้าแต่ละบรรทัด\n"
                        "รายละเอียดว่าบัฟแต่ละตัวกัน/ทำอะไร → `!codex สถานะ`")
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
        return embed

    if topic in ("ทวีป", "continent", "continents"):
        embed = discord.Embed(
            title="📖 Codex — ทวีปทั้ง 9", color=0x9b59b6,
            description="การข้ามทวีปมีทางเดียว: **สุ่มเจอพาหนะ** ระหว่างผจญภัย (รู้ปลายทางเมื่อไปถึง)")
        for key, c in game_modifiers.CONTINENTS.items():
            weights = (c.get("mods") or {}).get("element_weights") or {}
            top = sorted(weights, key=weights.get, reverse=True)[:2]
            elem_txt = " ".join(game_modifiers.ELEMENTS[t]["label"] for t in top if t in game_modifiers.ELEMENTS) or "สมดุลทุกธาตุ"
            embed.add_field(name=c["label"], value=f"ธาตุชุกชุม: {elem_txt}", inline=True)
        return embed

    if topic in ("รางวัล", "กิจกรรม", "daily", "season"):
        cfg = config_loader.get_config()
        embed = discord.Embed(
            title="📖 Codex — รางวัลรายวัน · ซีซั่นพาส · อันดับสัปดาห์", color=0x9b59b6,
            description="สามระบบนี้ให้รางวัลจาก **การเล่นปกติ** ไม่ต้องทำอะไรพิเศษ — แค่เข้ามาเล่นทุกวัน")

        quests = config_loader.get_daily_quests()
        bonus = config_loader.get_daily_cfg("all_clear_bonus", {}) or {}
        embed.add_field(name="📅 ภารกิจรายวัน (`!daily`)", inline=False, value=(
            "\n".join(f"• {q['label']} {int(q.get('target', 1)):,} ครั้ง → 🪙 {int(q.get('gold', 0)):,}"
                      for q in quests)
            + (f"\n🏆 เคลียร์ครบทุกข้อ → 🪙 **{int(bonus.get('gold', 0)):,}**" if bonus else "")
            + "\n*ความคืบหน้านับเองจากการเล่นปกติ · รีเซ็ตเที่ยงคืน*"))

        streak = sorted(config_loader.get_daily_cfg("streak_rewards", []) or [], key=lambda r: r["day"])
        if streak:
            embed.add_field(name="🔥 ล็อกอินต่อเนื่อง", inline=False, value=(
                " · ".join(f"**{int(r['day'])} วัน** 🪙 {int(r.get('gold', 0)):,}" for r in streak)
                + "\n*ขาดวันเดียวนับใหม่หมด แต่สถิติสูงสุดยังอยู่*"))

        season = cfg.get("season_pass", {}) or {}
        if season.get("enabled", True):
            tiers = season.get("tiers", []) or []
            embed.add_field(name="🎟️ ซีซั่นพาส (`!season`)", inline=False, value=(
                f"แต้ม = **EXP ที่หาได้ในเดือนนี้** · มี {len(tiers)} ขั้น\n"
                f"🆓 สายฟรีทุกคนได้ · ⭐ สายพรีเมียม {int(season.get('price_gold', 0)):,} ทอง "
                "(ซื้อแล้วย้อนเก็บขั้นที่ปลดไปแล้วได้ทันที)\n"
                "*ขึ้นเดือนใหม่ = ซีซั่นใหม่ แต้มเริ่มศูนย์ พรีเมียมต้องซื้อใหม่*"))

        weekly = cfg.get("weekly_ranking", {}) or {}
        if weekly.get("enabled", True):
            rw = weekly.get("rewards", []) or []
            embed.add_field(name="🗓️ อันดับรายสัปดาห์ (`!top` → 🗓️)", inline=False, value=(
                "แต้ม = **EXP ที่หาได้ในสัปดาห์นี้** · ปิดอันดับเช้าวันจันทร์\n"
                + " · ".join(f"{m} 🪙 {int(r.get('gold', 0)):,}" for m, r in zip(MEDALS, rw))
                + "\n*รางวัลโอนเข้าธนาคารอัตโนมัติ ตายแล้วไม่หาย*"))
        return embed

    if topic in ("สะสม", "ความสำเร็จ", "สัตว์เลี้ยง", "pet", "achievement"):
        cfg = config_loader.get_config()
        embed = discord.Embed(
            title="📖 Codex — ความสำเร็จ & สัตว์เลี้ยง", color=0x9b59b6,
            description="ของสะสมระยะยาว — เก็บไปเรื่อย ๆ ระหว่างเล่นปกติ ไม่ต้องไล่เก็บเป็นพิเศษ")

        achs = cfg.get("achievements", []) or []
        if achs:
            embed.add_field(name=f"🏅 ความสำเร็จ {len(achs)} รายการ (`!ach`)", inline=False, value=(
                "นับย้อนหลังให้อัตโนมัติ — เล่นมานานแล้วเปิดครั้งแรกได้เลยหลายอัน\n"
                + "\n".join(f"• {a['label']} — {a.get('desc', '')}" for a in achs[:6])
                + (f"\n*...และอีก {len(achs) - 6} รายการ ดูครบที่ `!ach`*" if len(achs) > 6 else "")
                + "\n🎖️ ปลดแล้วได้ **ตำแหน่ง** เลือกติดโชว์ใต้ชื่อในโปรไฟล์"))

        pets = (cfg.get("pets", {}) or {}).get("list", []) or []
        chances = (cfg.get("pets", {}) or {}).get("tame_chance", {}) or {}
        if pets:
            rank_th = {"Common": "มอนธรรมดา", "Mini-Boss": "มินิบอส", "Main-Boss": "บอสใหญ่",
                       "Secret": "มอนลับ", "Unbeatable": "ไร้พ่าย"}
            embed.add_field(name=f"🐾 สัตว์เลี้ยง {len(pets)} ตัว (`!pet`)", inline=False, value=(
                "**ล้มมอนแล้วลุ้นจับมาเลี้ยง** — ยิ่งมอนโหด ตัวที่ได้ยิ่งแรง ติดตัวได้ทีละตัว\n"
                + "\n".join(f"• {p['name']} — 🎲 เต๋า +{int(p.get('dice', 0))} "
                            f"(ล้ม{rank_th.get(p.get('from_rank'), '?')} โอกาส {int(chances.get(p.get('from_rank'), 0))}%)"
                            for p in pets)
                + "\n*ตัวที่มีแล้วจะไม่ออกซ้ำ · ตัวแรกติดให้อัตโนมัติ*"))
        return embed

    if topic in ("สังคม", "ตลาด", "คู่หู", "market", "partner"):
        cfg = config_loader.get_config()
        market = cfg.get("market", {}) or {}
        partner = cfg.get("partner", {}) or {}
        embed = discord.Embed(
            title="📖 Codex — ตลาดผู้เล่น & คู่หู", color=0x9b59b6,
            description="สองระบบที่ต้องมีคนอื่นถึงจะได้ประโยชน์เต็ม")
        if market.get("enabled", True):
            embed.add_field(name="🏪 ตลาดผู้เล่น (`!market`)", inline=False, value=(
                "ฝากขายไอเทมให้ผู้เล่นคนอื่นซื้อด้วยทองในเกม\n"
                "`!market sell <เลขไอเทม> <ราคา>` ลงขาย *(ของออกจากกระเป๋าทันที)*\n"
                "`!market buy <เลขรายการ>` ซื้อ • `!market cancel <เลขรายการ>` เอาของคืน\n"
                "`!market mine` ดูของที่ตัวเองลงขายอยู่\n"
                f"💸 ค่าธรรมเนียม **{int(market.get('tax_percent', 0))}%** หักจากคนขาย · "
                f"ราคา {int(market.get('min_price', 0)):,}–{int(market.get('max_price', 0)):,} ทอง · "
                f"ลงขายพร้อมกันได้ {int(market.get('max_listings_per_player', 0))} รายการ\n"
                "*เงินคนขายเข้าธนาคาร · ขายไปแล้วยกเลิกไม่ได้*"))
        embed.add_field(name="💍 คู่หู (`!marry` / `!partner` / `!divorce`)", inline=False, value=(
            f"ชวนใครสักคนเป็นคู่ (อีกฝ่ายต้องกดยืนยัน) ค่าจัดงานคนละ 🪙 {int(partner.get('wedding_cost', 0)):,}\n"
            f"💍 มีคู่: รางวัลจากการล่า **+{int(partner.get('solo_bonus_percent', 0))}%**\n"
            f"💞 **คู่เข้ามาเล่นวันเดียวกัน: +{int(partner.get('together_bonus_percent', 0))}%** ทั้งสองฝ่าย\n"
            f"*เลิกได้ด้วย `!divorce` (ค่าดำเนินการ {int(partner.get('divorce_cost', 0)):,} ทอง หักจากคนขอ)*"))
        return embed

    embed = discord.Embed(
        title="📖 Codex — สารานุกรมนักผจญภัย", color=0x9b59b6,
        description=("เลือกหมวดที่อยากอ่าน:\n"
                     "`!codex วิธีเล่น` — ไกด์เริ่มต้นตั้งแต่เกิดจนออกผจญภัย\n"
                     "`!codex คำสั่ง` — คำสั่งผู้เล่นทั้งหมดแยกหมวด\n"
                     "`!codex ธาตุ` — ธาตุทั้ง 7, ตารางข่ม, passive ประจำเผ่า\n"
                     "`!codex สถานะ` — สถานะทั้งหมด + ไอเทมที่ใช้แก้/กัน\n"
                     "`!codex ไอเทม` — ไอเทมทุกชิ้น ใช้ทำอะไร ราคาเท่าไหร่\n"
                     "`!codex ทวีป` — ทวีปทั้ง 9 และธาตุประจำถิ่น\n"
                     "`!codex กิลด์` — ก่อตั้งกิลด์ คลังกิลด์ และกิลด์วอร์\n"
                     "`!codex รางวัล` — ภารกิจรายวัน ซีซั่นพาส อันดับสัปดาห์\n"
                     "`!codex สะสม` — ความสำเร็จ + สัตว์เลี้ยง\n"
                     "`!codex สังคม` — ตลาดผู้เล่น + ระบบคู่หู"))
    return embed



def build_bestiary_embed(user_id, display_name, avatar_url):
    """สมุดสะสมมอนสเตอร์รายคน — ใช้ร่วมกันระหว่าง !bestiary และปุ่ม 📕 ในเมนู"""
    book = player_model.get_bestiary(user_id)
    embed = discord.Embed(
        title=f"📕 สมุดสะสมมอนสเตอร์ — {display_name}", color=0x8d6e63,
        description=("ล้มมอนแรงค์ไหนในทวีปไหน ช่องนั้นติ๊ก ✅\n"
                     "ครบ 4 แรงค์/ทวีป `+100,000` • ⭐ ไร้พ่าย `+200,000` • ครบทั้งสมุด `+1,000,000` + 💊"))
    rank_icons = [("Common", "🟢"), ("Mini-Boss", "🟡"), ("Main-Boss", "🔴"), ("Secret", "🟣")]
    done_slots, stars, total_kills = 0, 0, 0
    for key, c in game_modifiers.CONTINENTS.items():
        marks = []
        for rank, icon in rank_icons:
            have = (key, rank) in book
            done_slots += 1 if have else 0
            marks.append(f"{icon}{'✅' if have else '▫️'}")
        star = (key, "Unbeatable") in book
        stars += 1 if star else 0
        kills = sum(v for (c2, _r), v in book.items() if c2 == key)
        total_kills += kills
        line = " ".join(marks) + (" ⭐" if star else "") + (f" — ล้มสะสม `{kills:,}`" if kills else "")
        embed.add_field(name=c["label"], value=line, inline=False)
    embed.add_field(name="📊 ความคืบหน้า",
                    value=f"ช่องสมุด `{done_slots}/36` | ดาวไร้พ่าย `{stars}/9` | ล้มรวมทั้งหมด `{total_kills:,}` ตัว",
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
        _, msg = bank_action(ctx.author.id, "deposit", amount)
        await ctx.send(msg)
        
    @not_arrested() 
    @commands.command(name="withdraw")
    @allowed_channel("bank")
    async def withdraw(self, ctx, amount: int):
        _, msg = bank_action(ctx.author.id, "withdraw", amount)
        await ctx.send(msg)
    
    # 2. โอนเงิน: โอนจาก Bank -> ผู้เล่นอื่น
    @not_arrested() 
    @main_server_only()   # P8: เซิร์ฟหลักเท่านั้น
    @commands.command(name="transfer")
    @allowed_channel("bank")
    async def transfer(self, ctx, member: discord.Member, amount: int):
        _, msg = bank_action(ctx.author.id, "transfer", amount, target_id=member.id)
        await ctx.send(msg)

    # 3. ขอเงิน (Beg)
    @not_arrested() 
    @main_server_only()   # P8: เซิร์ฟหลักเท่านั้น
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
    @main_server_only()   # P8: เซิร์ฟหลักเท่านั้น
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
    @main_server_only()   # P8: เซิร์ฟหลักเท่านั้น
    @main_server_only()   # P8: เซิร์ฟหลักเท่านั้น
    @main_server_only()   # P8: เซิร์ฟหลักเท่านั้น
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
    @main_server_only()   # P8: เซิร์ฟหลักเท่านั้น
    @commands.command(name="bank")
    @allowed_channel("bank")
    async def check_bank(self, ctx):
        player = player_model.get_player(ctx.author.id)
        from bot.views.menu_view import BankActionView   # B1: พิมพ์ !bank ก็ได้ปุ่มธุรกรรมเหมือนกดจากเมนู
        await ctx.send(embed=build_bank_embed(player), view=BankActionView())

    # ==========================================
    # 🎖️ คำสั่งรับรางวัลตามยศ (!reward) — รวมรางวัลทุกยศที่มีสิทธิ์ในครั้งเดียว
    # ponytail: คูลดาวน์เดียวรวมทุกยศ (ไม่ใช่แยกคูลดาวน์ต่อยศ) — ง่ายกว่าและพอสำหรับสเปกปัจจุบัน
    # ==========================================
    @not_arrested()
    @main_server_only()   # P8: เซิร์ฟหลักเท่านั้น
    @adventure_room_only()   # P8: เซิร์ฟหลักใช้ได้เฉพาะมิติส่วนตัว
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

    # --- 📖 !codex: สารานุกรมกติกา — เนื้อหาจริงอยู่ใน build_codex_embed (แชร์กับปุ่มเมนู) ---
    @adventure_room_only()   # P8: เซิร์ฟหลักใช้ได้เฉพาะมิติส่วนตัว
    @commands.command(name="codex")
    async def codex(self, ctx, *, topic: str = ""):
        await ctx.send(embed=build_codex_embed(topic))

    # --- ⚔️ !war: สกอร์สงครามฝ่ายประจำสัปดาห์ (ธีม faction_war) ---
    @adventure_room_only()   # P8: เซิร์ฟหลักใช้ได้เฉพาะมิติส่วนตัว
    @commands.command(name="war", aliases=["สงคราม"])
    async def war_scores(self, ctx):
        scores = player_model.get_faction_war_scores()
        h, d = scores.get("human", 0), scores.get("demon", 0)
        theme = game_modifiers.get_weekly_theme()
        active = bool(theme and theme.get("key") == "faction_war")
        if h > d:
            headline = "🔵 **ฝ่ายมนุษย์กำลังนำ!**"
        elif d > h:
            headline = "🔴 **ฝ่ายปีศาจกำลังนำ!**"
        else:
            headline = "⚖️ **สูสีคู่คี่ ไม่มีใครยอมใคร!**"
        embed = discord.Embed(
            title="⚔️ สกอร์สงครามฝ่าย — สัปดาห์นี้", color=0x992d22,
            description=(f"{headline}\n\n🔵 ฝ่ายมนุษย์ `{h:,}` แต้ม\n🔴 ฝ่ายปีศาจ `{d:,}` แต้ม\n\n"
                         + ("🔥 ธีมสงครามฝ่ายกำลังลุกโหม — ออกล่าแชมเปี้ยนได้เลย!" if active
                            else "🕊️ สัปดาห์นี้ไม่ใช่ธีมสงคราม — แต้มจะเริ่มนับเมื่อธีม ⚔️ สงครามฝ่าย มาถึง")))
        await ctx.send(embed=embed)

    # --- 📅 !daily: ภารกิจรายวัน + ล็อกอินต่อเนื่อง (C1) ---
    @adventure_room_only()   # เล่นในมิติส่วนตัวเหมือนคำสั่งผู้เล่นอื่น
    @commands.command(name="daily", aliases=["เควส", "quest"])
    async def daily_quests(self, ctx):
        from bot import daily
        from bot.views.menu_view import DailyView
        streak, _best, is_new = player_model.touch_login_streak(ctx.author.id)
        if is_new:
            bonus_gold = int(config_loader.get_daily_cfg("streak_daily_gold", 0))
            if bonus_gold:
                player = player_model.get_player(ctx.author.id)
                player_model.update_player_field(ctx.author.id, "cash", player.get("cash", 0) + bonus_gold)
                await ctx.send(f"🌅 **เช็คอินวันใหม่!** รับ 🪙 `{bonus_gold:,}` ทอง (ต่อเนื่องวันที่ {streak})")
            milestone = daily.claim_streak_reward(ctx.author.id, streak)
            if milestone:
                await ctx.send(milestone)
        await ctx.send(embed=daily.build_daily_embed(ctx.author.id, ctx.author.display_name),
                       view=DailyView(ctx.author.id))

    # --- 🏆 !top: อันดับรวมทุกหมวด (O6 — ยุบจาก 4 คำสั่งเดิม ชื่อเดิมยังใช้เป็นทางลัดได้) ---
    @main_server_only()   # P8: เซิร์ฟหลักเท่านั้น
    @commands.command(name="top", aliases=["rich", "toplvl", "toptext", "toptime", "อันดับ"])
    @allowed_channel("bank")
    async def top_board(self, ctx, kind: str = None):
        from bot.views.menu_view import TopBoardView
        alias_map = {"rich": "rich", "toplvl": "level", "toptext": "text", "toptime": "time"}
        # !top เปล่า ๆ เปิดหมวดสัปดาห์นี้ก่อน (C3) — หมวดที่มีของรางวัลรออยู่ | alias เดิมยังพาไปหมวดเดิม
        start = alias_map.get(ctx.invoked_with, None) or {
            "เงิน": "rich", "เลเวล": "level", "แชท": "text", "เวลา": "time",
            "สัปดาห์": "weekly", "week": "weekly"}.get(kind or "", "weekly")
        await ctx.send(embed=build_top_embed(start, ctx.author.id),
                       view=TopBoardView(ctx.author.id, current=start))

    # --- 🎯 !bounty: กระดานล่าค่าหัว (คนสติติดลบ = อาชญากร) ---
    @main_server_only()   # P8: เซิร์ฟหลักเท่านั้น
    @commands.command(name="bounty", aliases=["wanted", "ล่าหัว"])
    @allowed_channel("arena")   # อยู่ห้องเดียวกับ !att/!scan — เช็คกระดานแล้วตีต่อได้เลย
    async def bounty_board(self, ctx):
        outlaws = player_model.get_outlaws()
        embed = discord.Embed(
            title="🎯 กระดานล่าค่าหัว", color=0xc0392b,
            description=("ผู้คลุ้มคลั่ง (สติติดลบ) มีค่าหัวรอนักล่า — สังหารด้วย `!att` รับทองเต็ม ๆ\n"
                         "ปราบอาชญากรไม่เสียสติ แถมฆ่าสำเร็จได้สติคืน `+10`"))
        if not outlaws:
            embed.description += "\n\n🕊️ **บ้านเมืองสงบสุข** — ยังไม่มีหัวให้ล่าในตอนนี้"
        else:
            lines = []
            for uid, sanity in outlaws[:15]:  # โชว์ 15 หัวแรก (เรียงจากคลั่งสุด)
                lines.append(f"💀 <@{uid}> — สติ `{sanity}` | ค่าหัว 💰 `{game_modifiers.bounty_for(sanity):,}` ทอง")
            embed.add_field(name=f"หมายหัว {len(outlaws)} ราย", value="\n".join(lines), inline=False)
        await ctx.send(embed=embed)

    # --- 📕 !bestiary: สมุดสะสมมอนสเตอร์ — เนื้อหาจริงอยู่ใน build_bestiary_embed (แชร์กับปุ่มเมนู) ---
    @adventure_room_only()   # P8: เซิร์ฟหลักใช้ได้เฉพาะมิติส่วนตัว
    @commands.command(name="bestiary", aliases=["สมุดมอน"])
    async def bestiary(self, ctx):
        await ctx.send(embed=build_bestiary_embed(
            ctx.author.id, ctx.author.display_name, ctx.author.display_avatar.url))

    # --- 💍 !marry / !partner / !divorce: คู่หู (C7) ---
    @adventure_room_only()   # P8: เซิร์ฟหลักใช้ได้เฉพาะมิติส่วนตัว
    @commands.command(name="partner", aliases=["คู่หู", "couple"])
    async def partner_status(self, ctx):
        from bot import partner
        await ctx.send(embed=partner.build_partner_embed(ctx.author.id, ctx.author.display_name))

    @adventure_room_only()
    @commands.command(name="marry", aliases=["แต่งงาน"])
    async def marry_cmd(self, ctx, member: discord.Member = None):
        from bot import partner
        from bot.views.menu_view import ProposalView
        if member is None:
            return await ctx.send("❓ **วิธีใช้:** `!marry @ผู้เล่น` — ชวนเป็นคู่หู (อีกฝ่ายต้องกดยืนยัน)")
        if member.bot or member.id == ctx.author.id:
            return await ctx.send("❌ เลือกผู้เล่นคนอื่นที่ไม่ใช่บอทนะ")
        if partner.partner_of(ctx.author.id):
            return await ctx.send("❌ คุณมีคู่อยู่แล้ว! หย่าก่อนด้วย `!divorce`")
        if partner.partner_of(member.id):
            return await ctx.send(f"❌ {member.display_name} มีคู่อยู่แล้ว")
        cost = int(config_loader.get_config().get("partner", {}).get("wedding_cost", 0) or 0)
        await ctx.send(f"💌 {member.mention} — {ctx.author.mention} ชวนคุณเป็นคู่หู!\n"
                       f"ค่าจัดงานคนละ 🪙 `{cost:,}` ทอง (หักตอนกดตกลง)",
                       view=ProposalView(ctx.author.id, member.id))

    @adventure_room_only()
    @commands.command(name="divorce", aliases=["หย่า"])
    async def divorce_cmd(self, ctx):
        from bot import partner
        _ok, msg = partner.divorce(ctx.author.id)
        await ctx.send(msg)

    # --- 🏪 !market: ตลาดผู้เล่น (C5) ---
    @adventure_room_only()   # P8: เซิร์ฟหลักใช้ได้เฉพาะมิติส่วนตัว
    @commands.command(name="market", aliases=["ตลาด"])
    async def market_board(self, ctx, action: str = None, arg1: str = None, arg2: str = None):
        from bot import market
        from bot.views.menu_view import MarketView

        if action in ("sell", "ขาย"):
            if not arg1 or not arg2:
                return await ctx.send("❓ **วิธีใช้:** `!market sell [เลขไอเทม] [ราคา]`")
            _ok, msg = market.list_item(ctx.author.id, arg1, arg2)
            return await ctx.send(msg)

        if action in ("cancel", "ยกเลิก"):
            if not arg1 or not arg1.lstrip("#").isdigit():
                return await ctx.send("❓ **วิธีใช้:** `!market cancel [เลขรายการ]`")
            _ok, msg = market.cancel_listing(ctx.author.id, int(arg1.lstrip("#")))
            return await ctx.send(msg)

        if action in ("mine", "ของฉัน"):
            rows = market.my_listings(ctx.author.id)
            if not rows:
                return await ctx.send("📭 คุณไม่มีของลงขายอยู่")
            lines = [f"`#{lid}` {market._item_name(item)} — 🪙 `{price:,}` ทอง"
                     for lid, item, price in rows]
            return await ctx.send("🏪 **ของที่คุณลงขายอยู่:**\n" + "\n".join(lines)
                                  + "\n*ยกเลิก: `!market cancel [เลขรายการ]`*")

        if action in ("buy", "ซื้อ"):
            if not arg1 or not arg1.lstrip("#").isdigit():
                return await ctx.send("❓ **วิธีใช้:** `!market buy [เลขรายการ]`")
            _ok, msg = market.buy_listing(ctx.author.id, int(arg1.lstrip("#")))
            return await ctx.send(msg)

        await ctx.send(embed=market.build_market_embed(ctx.author.id),
                       view=MarketView(ctx.author.id))

    # --- 🐾 !pet: สัตว์เลี้ยงที่จับมาได้ + เลือกตัวติดตาม (C4) ---
    @adventure_room_only()   # P8: เซิร์ฟหลักใช้ได้เฉพาะมิติส่วนตัว
    @commands.command(name="pet", aliases=["pets", "สัตว์เลี้ยง"])
    async def pet_board(self, ctx):
        from bot import pets
        from bot.views.menu_view import PetView
        await ctx.send(embed=pets.build_pet_embed(ctx.author.id, ctx.author.display_name),
                       view=PetView(ctx.author.id))

    # --- 🎟️ !season: ซีซั่นพาสรายเดือน (C2) ---
    @adventure_room_only()   # P8: เซิร์ฟหลักใช้ได้เฉพาะมิติส่วนตัว
    @commands.command(name="season", aliases=["pass", "ซีซั่น", "ซีซัน"])
    async def season_pass(self, ctx):
        from bot import season
        from bot.views.menu_view import SeasonView
        await ctx.send(embed=season.build_season_embed(ctx.author.id, ctx.author.display_name),
                       view=SeasonView(ctx.author.id))

    # --- 🎟️ แอดมินเปิดพรีเมียมให้คนที่โอนเงินจริงมาแล้ว (คู่กับ !confirm_payment) ---
    @main_server_only()
    @has_permission("admin")
    @allowed_channel("payment")   # ห้องเดียวกับที่แอดมินกด !confirm_payment
    @commands.command(name="grant_season")
    async def grant_season(self, ctx, member: discord.Member = None):
        if member is None:
            return await ctx.send("❓ **วิธีใช้:** `!grant_season @ผู้เล่น` — เปิดสายพรีเมียมซีซั่นนี้ให้")
        from bot import season
        if season.grant_premium(member.id):
            await ctx.send(f"🎟️ เปิดสายพรีเมียมซีซั่น `{player_model.season_key()}` ให้ {member.mention} แล้ว!")
        else:
            await ctx.send(f"ℹ️ {member.mention} เปิดสายพรีเมียมของซีซั่นนี้ไว้อยู่แล้ว")

    # --- 🏅 !ach: ความสำเร็จ + เลือกตำแหน่งอวด (C8) ---
    @adventure_room_only()   # P8: เซิร์ฟหลักใช้ได้เฉพาะมิติส่วนตัว
    @commands.command(name="ach", aliases=["achievement", "title", "ความสำเร็จ", "ตำแหน่ง"])
    async def achievements_board(self, ctx):
        from bot import achievements
        from bot.views.menu_view import AchievementView
        await ctx.send(embed=achievements.build_achievement_embed(ctx.author.id, ctx.author.display_name),
                       view=AchievementView(ctx.author.id))

    # --- โค้ดคำสั่ง !bag ---
    @adventure_room_only()   # P8: เซิร์ฟหลักใช้ได้เฉพาะมิติส่วนตัว
    @commands.command(name="bag")
    async def check_bag(self, ctx): # 🚨 จุดสำคัญ: เติม self ลงไปตรงนี้ครับ
        user_id = ctx.author.id
        player = player_model.get_player(user_id)

        if not player:
            print(f"ERROR: [Bag] ไม่พบข้อมูลผู้เล่นสำหรับ User ID: {user_id}")
            await ctx.send("❌ ไม่พบข้อมูลตัวละครของคุณ! พิมพ์ `!play` เพื่อสร้างตัวละครก่อนน้า")
            return

        embed = build_bag_embed(ctx.author.display_name, ctx.author.display_avatar.url, player)
        from bot.views.menu_view import BagActionView   # B1: ปุ่มคราฟ/ขายวัสดุ ติดมากับ !bag ด้วย
        await ctx.send(embed=embed, view=BagActionView(ctx.author.id))
    
    # ⏱️ เช็กเวลาออนไลน์ของตัวเอง
    @main_server_only()   # P8: เซิร์ฟหลักเท่านั้น
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
    @main_server_only()   # P8: เซิร์ฟหลักเท่านั้น
    @adventure_room_only()   # P8: เซิร์ฟหลักใช้ได้เฉพาะมิติส่วนตัว
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

    @adventure_room_only()   # P8: เซิร์ฟหลักใช้ได้เฉพาะมิติส่วนตัว
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
    
    @adventure_room_only()   # P8: เซิร์ฟหลักใช้ได้เฉพาะมิติส่วนตัว
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
    @main_server_only()   # P8: เซิร์ฟหลักเท่านั้น
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
        pvp_min_level = int(config_loader.get_balance("pvp.min_level", 20))
        if attacker.get("level", 0) < pvp_min_level or defender.get("level", 0) < pvp_min_level:
            return await ctx.send(f"❌ ระบบ PVP รองรับเฉพาะผู้กล้าเลเวล {pvp_min_level} ขึ้นไปเท่านั้น! (และห้ามรังแกผู้เล่นเลเวลต่ำกว่านี้)")
        
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
            reward_exp = int(config_loader.get_balance("pvp.reward_exp_base", 100)) + (loser.get("level", 1) * int(config_loader.get_balance("pvp.reward_exp_per_level", 1000)))
            reward_gold = int(config_loader.get_balance("pvp.reward_gold_base", 500)) + (loser.get("level", 1) * int(config_loader.get_balance("pvp.reward_gold_per_level", 500)))

            is_lvl_up, new_lvl, new_exp = player_model.add_exp(w_member.id, reward_exp)

            # ⚖️ ล่าค่าหัว (P4): ฝ่ายบุกฆ่าอาชญากร (สติติดลบ) = รับค่าหัว + เหยื่อชดใช้กรรม (สติรีเซ็ต 0)
            bounty = 0
            if loser is defender and defender.get("sanity", 100) < 0:
                bounty = game_modifiers.bounty_for(defender.get("sanity", 100))
                player_model.update_player_field(l_member.id, "sanity", 0)

            new_winner_cash = winner.get("cash", 0) + reward_gold + bounty
            player_model.update_player_field(w_member.id, "cash", new_winner_cash)

            lvl_up_msg = f"\n✨ **Level Up!** คุณเลเวลอัปเป็น {new_lvl}!" if is_lvl_up else ""
            reward_text = f"\n💰 **ได้รับรางวัล:** `{reward_gold}` ทอง | `EXP +{reward_exp}`{lvl_up_msg}"
            if bounty:
                reward_text += (f"\n🎯 **ล่าหัวสำเร็จ!** รับค่าหัว `{bounty:,}` ทอง — "
                                f"{l_member.mention} ชดใช้กรรมแล้ว (สติกลับเป็น 0 หลุดจากกระดานล่าหัว)")
            
            cooldown_seconds = random.randint(int(config_loader.get_balance("pvp.kill_cooldown_min_sec", 300)), int(config_loader.get_balance("pvp.kill_cooldown_max_sec", 600)))
            self.pk_cooldowns[ctx.author.id] = time.time() + cooldown_seconds
            player_model.update_player_field(l_member.id, "current_state", "death")
            death_status_text = f"\n💀 **☠️ สิ้นชีพ!** พลังชีวิตของ {l_member.mention} หมดลงและเข้าสู่สถานะเสียชีวิต!"

        # ==========================================
        # 🧠 6. ระบบสูญเสียสติ (Sanity) ของผู้โจมตี
        # ==========================================
        # ⚖️ P4: เป้าหมายเป็นอาชญากร (สติติดลบ) = ปราบโจรไม่บาป — ไม่เสียสติ ไม่มีเวรกรรม
        if defender.get("sanity", 100) < 0:
            if loser_new_hp <= 0 and loser is defender:
                hunter_sanity = min(100, attacker.get("sanity", 100) + int(config_loader.get_balance("bounty.hunt_sanity_reward", game_modifiers.BOUNTY_HUNT_SANITY_REWARD)))
                player_model.update_player_field(ctx.author.id, "sanity", hunter_sanity)
                sanity_text = f"\n🧠 **จิตใจผ่องใสจากการผดุงยุติธรรม** สติ `+{int(config_loader.get_balance("bounty.hunt_sanity_reward", game_modifiers.BOUNTY_HUNT_SANITY_REWARD))}` (ปัจจุบัน: {hunter_sanity})"
            else:
                sanity_text = "\n🧠 การไล่ล่าอาชญากรไม่ใช่บาป — สติไม่ลดลง"
            karma_text = ""
            new_sanity = 0  # sentinel: การล่าโจรไม่นับเป็นบาป — ข้ามเช็คสติแตกด้านล่างเสมอ (แม้นักล่าเองสติติดลบ)
        else:
            sanity_loss = int(config_loader.get_balance("pvp.sanity_loss_base", 5)) + int(attacker.get("level", 1) * float(config_loader.get_balance("pvp.sanity_loss_per_level", 0.25)))
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
                    jail_mins = int(config_loader.get_balance("pvp.jail_base_min", 10)) + (deficit * int(config_loader.get_balance("pvp.jail_per_deficit_min", 3)))
                    jail_until = time.time() + (jail_mins * 60)
                    
                    player_model.update_player_fields(ctx.author.id, {
                        "current_state": "arrested",
                        "arrest_until": jail_until
                    })
                    karma_text = f"\n\n🚨 **เวรกรรมตามสนอง!** ความคลุ้มคลั่งทำให้ {ctx.author.mention} ถูกจับเข้าคุกเป็นเวลา `{jail_mins}` นาที!"
                    
                elif event_type == "execute":
                    money_penalty = int(config_loader.get_balance("pvp.fine_base", 1000)) + (deficit * int(config_loader.get_balance("pvp.fine_per_deficit", 200)))
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
    @adventure_room_only()   # P8: เซิร์ฟหลักใช้ได้เฉพาะมิติส่วนตัว
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
    @adventure_room_only()   # P8: เซิร์ฟหลักใช้ได้เฉพาะมิติส่วนตัว
    @commands.command(name="craft")
    async def craft_item(self, ctx, item_id: str = None):
        _ok, msg = craft_for(ctx.author.id, item_id)
        await ctx.send(msg)
            
    # สแกนผู้เล่นว่าตีได้หรือไม่
    @allowed_channel("arena") # 🛠️ ใช้ Decorator บล็อกห้อง
    @not_arrested() # 🛠️ บล็อกคนติดคุก
    @main_server_only()   # P8: เซิร์ฟหลักเท่านั้น
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

def sell_all_junk(user_id):
    """🧱 B5: ขายวัสดุ/ของขยะทั้งกระเป๋ารวดเดียว — คืน (จำนวนชิ้น, ทองที่ได้, ข้อความ)
    'ของขยะ' = ไม่มี effect, ไม่ใช่อุปกรณ์สวมใส่ (ของใช้/อาร์ติแฟกต์/เกราะ/อาวุธ ปลอดภัยเสมอ)"""
    player = player_model.get_player(user_id)
    if not player:
        return 0, 0, "❌ ไม่พบข้อมูลตัวละครของคุณ!"
    inv = player_model.load_inventory(player.get("inventory", ""))
    all_items = config_loader.get_all_items()

    keep, sold, gold = [], 0, 0
    for item_id in inv:
        data = all_items.get(item_id, {})
        is_junk = data and not data.get("effect") and not data.get("equip_key") and data.get("type") != "use"
        if is_junk:
            sold += 1
            gold += int(data.get("sell", 0))
        else:
            keep.append(item_id)

    if not sold:
        return 0, 0, "🎒 ไม่มีวัสดุ/ของขายในกระเป๋าเลย (ของใช้กับอุปกรณ์ไม่ถูกขาย)"
    player_model.update_player_fields(user_id, {
        "inventory": json.dumps(keep), "cash": player.get("cash", 0) + gold})
    return sold, gold, f"💰 ขายวัสดุ **{sold}** ชิ้น ได้ **{gold:,}** ทอง (เหลือของในกระเป๋า {len(keep)} ชิ้น)"


def craft_for(user_id, item_id):
    """🔨 B1: ตรรกะคราฟกลาง — ใช้ทั้งคำสั่ง !craft และปุ่มในเมนู คืน (สำเร็จ, ข้อความ)"""
    try:
        if not item_id or not config_loader.get_crafting_recipe(str(item_id)):
            return False, "❌ รหัสไอเทมนี้ไม่มีสูตรคราฟ หรือรหัสไม่ถูกต้อง!"
        item_id = str(item_id)
        player = player_model.get_player(user_id)
        if not player:
            return False, "❌ ไม่พบข้อมูลตัวละครของคุณ!"
        inv_list = player_model.load_inventory(player.get("inventory", []))
        recipe_data = config_loader.get_crafting_recipe(item_id)
        recipe = recipe_data["recipe"]
        fail_rate = recipe_data.get("fail_rate", 0.2)

        # 1. เช็กวัตถุดิบ
        for ing_id, amount in recipe.items():
            if inv_list.count(str(ing_id)) < amount:
                needed_name = config_loader.get_item_config(str(ing_id)).get("name", "Unknown")
                return False, f"❌ วัตถุดิบไม่พอ! คุณขาด `{needed_name}`"

        # 2. เช็กกระเป๋าเต็ม
        capacity = player.get("capacity", 10)
        if capacity != 0 and len(inv_list) >= capacity:
            return False, "⚠️ กระเป๋าของคุณเต็ม!"

        # 3. โอกาสล้มเหลว — เสียวัตถุดิบครึ่งหนึ่ง
        if random.random() < fail_rate:
            for ing_id, amount in recipe.items():
                for _ in range((amount + 1) // 2):
                    if str(ing_id) in inv_list:
                        inv_list.remove(str(ing_id))
            player_model.update_player_field(user_id, "inventory", json.dumps(inv_list))
            return False, f"💥 **ล้มเหลว ({int(fail_rate * 100)}%)!** วัตถุดิบเสียหายไปบางส่วน!"

        # 4. คราฟสำเร็จ
        for ing_id, amount in recipe.items():
            for _ in range(amount):
                inv_list.remove(str(ing_id))
        inv_list.append(item_id)
        player_model.update_player_field(user_id, "inventory", json.dumps(inv_list))
        craft_name = config_loader.get_item_config(item_id).get("name", item_id)
        return True, f"✨ คราฟสำเร็จ! คุณได้รับ `{craft_name}` 1 ชิ้น!"

    except Exception as e:
        print(f"❌ [CRITICAL ERROR] การคราฟพัง! สาเหตุ: {e}")
        traceback.print_exc()
        return False, f"⚠️ ระบบคราฟมีปัญหาทางเทคนิค! (Error: {e})"


def craftable_now(user_id):
    """สูตรที่วัตถุดิบครบพร้อมคราฟตอนนี้ — [(item_id, ชื่อ, ข้อความวัตถุดิบ), ...]"""
    player = player_model.get_player(user_id)
    if not player:
        return []
    inv = player_model.load_inventory(player.get("inventory", []))
    recipes = config_loader.get_config().get("item_catalog", {}).get("crafting_recipes", {})
    out = []
    for item_id, data in recipes.items():
        recipe = (data or {}).get("recipe") or {}
        if not recipe or not all(inv.count(str(i)) >= n for i, n in recipe.items()):
            continue
        mats = " + ".join(f"{config_loader.get_item_config(str(i)).get('name', i)}×{n}"
                          for i, n in recipe.items())
        out.append((item_id, config_loader.get_item_config(item_id).get("name", item_id), mats))
    return out


def drop_item_for(user_id, item_id, amount=1):
    """🗑️ B1: ทิ้งไอเทมออกจากกระเป๋า — ใช้ทั้งคำสั่ง !drop และปุ่มในกระเป๋า"""
    player = player_model.get_player(user_id)
    if not player:
        return False, "❌ ไม่พบข้อมูลตัวละครของคุณ!"
    inv = player_model.load_inventory(player.get("inventory", ""))
    item_id = str(item_id)
    have = inv.count(item_id)
    if not have:
        return False, "❌ คุณไม่มีไอเทมชิ้นนี้ในกระเป๋า!"
    amount = max(1, min(int(amount), have))
    for _ in range(amount):
        inv.remove(item_id)
    player_model.update_player_field(user_id, "inventory", json.dumps(inv))
    name = config_loader.get_item_config(item_id).get("name", item_id)
    return True, f"🗑️ ทิ้ง **{name}** ×{amount} ทิ้งแล้ว (เหลือของในกระเป๋า {len(inv)} ชิ้น)"


# ===== 🏆 อันดับรวม (O6) — 6 คำสั่งเดิมยุบเหลือ !top หน้าเดียว =====

TOP_KINDS = {
    "rich":  ("💰 เศรษฐี", "ทอง", lambda v: f"{v:,} ทอง"),
    "level": ("⭐ เลเวล", "Lv.", lambda v: f"Lv. {v:,}"),
    "text":  ("💬 นักแชท", "ข้อความ", lambda v: f"{v:,} ข้อความ"),
    "time":  ("🎙️ เวลาออนไลน์", "ชั่วโมง", lambda v: f"{int(v) // 3600:,} ชม. {int(v) % 3600 // 60} นาที"),
    "weekly": ("🗓️ นักผจญภัยแห่งสัปดาห์", "แต้ม", lambda v: f"{v:,} แต้ม"),
}
MEDALS = ["🥇", "🥈", "🥉"]


def build_top_embed(kind, viewer_id=None):
    """หน้าอันดับหมวดเดียว + บอกอันดับของคนดูด้วย"""
    title, _unit, fmt = TOP_KINDS.get(kind, TOP_KINDS["rich"])
    rows = player_model.get_leaderboard(kind, 10)
    embed = discord.Embed(title=f"🏆 อันดับ {title} — TOP 10", color=0xf1c40f)
    if not rows:
        embed.description = "*ยังไม่มีข้อมูลผู้เล่น*"
    else:
        lines = []
        for i, (uid, value) in enumerate(rows):
            badge = MEDALS[i] if i < 3 else f"`{i + 1:>2}.`"
            me = " ⬅️ **คุณ**" if uid == viewer_id else ""
            lines.append(f"{badge} <@{uid}> — {fmt(value or 0)}{me}")
        embed.description = "\n".join(lines)
    if viewer_id:
        mine = player_model.get_my_rank(viewer_id, kind)
        if mine:
            rank, value, total = mine
            embed.add_field(name="📍 อันดับของคุณ",
                            value=f"อันดับ **{rank:,}** จาก {total:,} คน · {fmt(value or 0)}", inline=False)
    if kind == "weekly":
        rewards = config_loader.get_weekly_ranking("rewards", []) or []
        if rewards:
            embed.add_field(
                name="🎁 รางวัลตอนปิดสัปดาห์ (เข้าธนาคารอัตโนมัติ)",
                value=" · ".join(f"{m} {int(r.get('gold', 0)):,} ทอง"
                                 for m, r in zip(MEDALS, rewards)),
                inline=False)
        import datetime
        left = 7 - datetime.date.today().weekday()      # จันทร์=0 → เหลือ 7 วัน, อาทิตย์=6 → เหลือ 1
        embed.set_footer(text=f"แต้ม = EXP ที่หาได้ในสัปดาห์นี้ · ปิดอันดับอีก {left} วัน (เช้าวันจันทร์)")
    else:
        embed.set_footer(text="กดปุ่มด้านล่างเพื่อสลับหมวด")
    return embed
