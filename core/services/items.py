"""ไอเทม — ใช้/สวม/ซื้อ/ขาย/ทิ้ง/ขายวัสดุทั้งกระเป๋า

ย้ายมาจาก bot/cogs/player_commands.py ตรง ๆ (ไม่เปลี่ยนพฤติกรรม) เพื่อให้ทั้งคำสั่งดิสคอร์ด
และเว็บ (ร้านค้า/กระเป๋า) เรียกตรรกะเดียวกันได้ โดยเว็บไม่ต้อง import ผ่าน bot/cogs/
"""
import json
import random

import bot.models.player_model as player_model
from bot import config_loader
from bot import game_modifiers

EQUIP_TYPES = ("armor", "weapon", "bag")
MAX_BUY_AT_ONCE = 99      # เพดานต่อการกดหนึ่งครั้ง — กันพิมพ์เลขหลุดจนกระเป๋า/เงินหายรวดเดียว


def usable_kind(item_cfg):
    """ของชิ้นนี้กดใช้ได้ไหม — "equip" (สวมใส่) / "use" (กดใช้) / "" (เก็บ-ขายอย่างเดียว)

    ยึดตามสาขาที่ apply_item_effect() ด้านล่างรับจริง ๆ ห้ามให้ที่อื่นเดาเอง
    (หน้าเว็บเคยเดาว่า "ต้องมี effect + type=use" เลยซ่อนปุ่มสวมอาวุธ/เกราะทิ้งทั้งหมด)
    """
    if not item_cfg:
        return ""
    if item_cfg.get("type") in EQUIP_TYPES:
        return "equip"
    return "use" if item_cfg.get("effect") else ""


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

    # 💎 กรณี: ยามานา — คืนเม็ดคริสตัลที่ใช้ออกท่า (เต็มอยู่แล้วใช้ไม่ได้ กันกินทิ้ง)
    if item_info.get("effect") == "mana":
        from bot import mana as _mana
        amount = int(item_info.get("effect_amount", 1))
        full = _mana.max_mana(player.get("level", 1))
        cur = _mana.get(user_id, player)
        if cur >= full:
            return False, f"❌ เม็ดคริสตัลของคุณเต็มอยู่แล้ว! (`{cur}/{full}`) เก็บ {item_name} ไว้ก่อน"
        left = _mana.restore(user_id, amount, player)
        msg = (f"💠 คุณบดขยี้ **{item_name}** พลังมานาไหลกลับเข้าร่าง! "
               f"(💎 `{cur}` ➔ `{left}/{full}`)")

    # 🧪 กรณี: ใช้ยาฮีล (ตั้งค่าได้ผ่าน effect: "heal" + effect_amount)
    elif item_info.get("effect") == "heal":
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

    # 🏺 กรณี: สวมอาร์ติแฟกต์ — ใส่ได้เท่าจำนวนช่องที่มี (เจาะเพิ่มได้ด้วยสว่าน)
    elif item_info.get("effect") == "equip_artifact":
        art_key = str(item_info.get("effect_value", ""))
        art_cfg = game_modifiers.STATUS_EFFECTS.get(art_key)
        if not art_cfg or not art_cfg.get("artifact"):
            return False, "❌ ไอเทมนี้ตั้งค่าอาร์ติแฟกต์ไว้ไม่ถูกต้อง (แจ้งแอดมินตรวจ config)"
        statuses = game_modifiers.parse_statuses(player)
        worn = game_modifiers.worn_artifacts(statuses)
        if art_key in worn:
            return False, f"❌ คุณสวม **{item_name}** อยู่แล้ว!"
        slots = game_modifiers.artifact_slots(player)
        if len(worn) >= slots:
            names = " ".join(game_modifiers.STATUS_EFFECTS[k]["label"] for k in worn)
            return False, (f"❌ **ช่องอาร์ติแฟกต์เต็มแล้ว** ({len(worn)}/{slots})\n"
                           f"สวมอยู่: {names}\n"
                           "→ เจาะช่องเพิ่มด้วย 💠 สว่านเจาะรูอาร์ติแฟกต์ (ดรอปจากบอสไร้พ่าย)\n"
                           "→ หรือถอดของเก่าออกด้วย 🔧 ชุดถอดอาร์ติแฟกต์ (ซื้อที่ `!shop`)")
        statuses = game_modifiers.apply_status(statuses, art_key)
        player_model.update_player_field(user_id, "status_effects", statuses)
        msg = (f"🏺 คุณสวม **{item_name}** เข้าช่องอาร์ติแฟกต์ — พลังถาวรไหลเวียนทั่วร่าง! "
               f"(ใช้ไป {len(worn) + 1}/{slots} ช่อง)")

    # 💠 กรณี: สว่านเจาะรูอาร์ติแฟกต์ — เพิ่มช่องถาวร (เพดานตั้งใน Panel)
    elif item_info.get("effect") == "artifact_slot_up":
        cap = int(config_loader.get_balance("artifact.max_slots", 5) or 5)
        current = game_modifiers.artifact_slots(player)
        if current >= cap:
            return False, (f"❌ ร่างคุณเจาะได้สูงสุด **{cap} ช่อง** แล้ว เจาะเพิ่มไม่ได้อีก "
                           "(สว่านยังอยู่ในกระเป๋า)")
        player_model.update_player_field(user_id, "artifact_slots", current + 1)
        msg = (f"💠 **เจาะรูอาร์ติแฟกต์สำเร็จ!** ช่องอาร์ติแฟกต์ {current} → **{current + 1}** "
               f"(สูงสุด {cap})")

    elif item_info.get("effect") == "artifact_remove":
        # 🔧 ต้องเปิดเมนูเลือกว่าจะถอดชิ้นไหน — ทำผ่าน !use เท่านั้น (ของถูกหักตอนยืนยัน)
        return False, ("🔧 ไอเทมนี้ใช้ผ่านคำสั่ง `!use` ในห้องแชทเท่านั้น — "
                       "จะมีเมนูให้เลือกว่าจะถอดอาร์ติแฟกต์ชิ้นไหน")

    elif item_info.get("effect") == "wedding_ring":
        # 💍 ไม่ใช่ของกดใช้ — ถูกใช้ไปเองตอนอีกฝ่ายกดตกลงเป็นคู่หู
        return False, (f"💍 **{item_name}** ไม่ต้องกดใช้ — พิมพ์ `!marry @คนที่อยากขอ` "
                       "แล้วแหวนจะถูกสวมให้เองตอนอีกฝ่ายกดตกลง")

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


def buy_item_for(user_id, item_id, count=1):
    """🛒 ซื้อไอเทมจากร้าน — ตรรกะกลาง ใช้ทั้งปุ่มร้านค้าในดิสและหน้าร้านบนเว็บ

    คืน (สำเร็จ, ข้อความ) — ลำดับการตรวจเหมือนเดิมทุกข้อ: มีของ → ซื้อได้ → เงินพอ → กระเป๋าพอ
    ซื้อหลายชิ้นเป็นแบบ "ได้ทั้งกองหรือไม่ได้เลย" ไม่มีสภาพซื้อได้ครึ่งกองแล้วเงินหาย
    """
    item_id = str(item_id)
    item = config_loader.get_item_config(item_id)
    if not item:
        return False, "❌ ไอเทมนี้ไม่มีอยู่ในระบบ!"
    if not item.get("purchasable", True):
        return False, "❌ ไอเทมนี้ไม่สามารถซื้อจากร้านค้าได้!"

    player = player_model.get_player(user_id)
    if not player:
        return False, "❌ ไม่พบข้อมูลตัวละครของคุณ!"

    try:
        count = max(1, min(int(count), MAX_BUY_AT_ONCE))
    except (TypeError, ValueError):
        return False, "❌ จำนวนต้องเป็นตัวเลข"

    price = int(item.get("buy", 0))
    total = price * count
    if player.get("cash", 0) < total:
        return False, (f"❌ เงินไม่พอ! ซื้อ {count} ชิ้นต้องใช้ `{total:,}` ทอง "
                       f"(คุณมี `{player.get('cash', 0):,}` ทอง)")

    inv = player_model.load_inventory(player.get("inventory", ""))
    capacity = int(player.get("capacity", 10) or 0)
    if capacity != 0 and len(inv) + count > capacity:
        room = max(0, capacity - len(inv))
        if room == 0:
            return False, f"❌ กระเป๋าเต็มแล้ว! ({len(inv)}/{capacity}) จัดการของก่อนซื้อเพิ่ม"
        return False, (f"❌ กระเป๋าไม่พอ! เหลือที่ว่าง {room} ช่อง "
                       f"แต่จะซื้อ {count} ชิ้น ({len(inv)}/{capacity})")

    # ซื้อทีเดียวทั้งกอง — ผ่านทุกด่านแล้วค่อยหักเงิน ไม่มีสภาพซื้อได้ครึ่งกอง
    inv.extend([item_id] * count)
    player_model.update_player_fields(user_id, {
        "cash": player["cash"] - total, "inventory": json.dumps(inv)})
    many = f" ×{count}" if count > 1 else ""
    return True, f"✅ ซื้อ **{item.get('name', item_id)}**{many} เข้ากระเป๋าเรียบร้อย! (-{total:,} ทอง)"


def sell_item_for(user_id, item_id):
    """📦 ขายไอเทมทีละชิ้นให้ร้าน — ตรรกะกลาง ใช้ทั้งดิสและเว็บ"""
    item_id = str(item_id)
    item = config_loader.get_item_config(item_id)
    if not item:
        return False, "❌ ไอเทมนี้ไม่มีอยู่ในระบบ!"

    player = player_model.get_player(user_id)
    if not player:
        return False, "❌ ไม่พบข้อมูลตัวละครของคุณ!"

    inv = player_model.load_inventory(player.get("inventory", ""))
    if item_id not in inv:
        return False, "❌ คุณไม่มีไอเทมชิ้นนี้ให้ขายแล้ว!"

    price = int(item.get("sell", 0))
    inv.remove(item_id)
    player_model.update_player_fields(user_id, {
        "cash": player.get("cash", 0) + price, "inventory": json.dumps(inv)})
    return True, f"✅ ขาย **{item.get('name', item_id)}** แล้ว! ได้เงินมา `{price:,}` ทอง"


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
        # ทองคำแท่ง (bar_value) ไม่ใช่ขยะ — กันปุ่มขายวัสดุเทขายแท่ง 1000M ทิ้งรวดเดียว
        is_junk = (data and not data.get("effect") and not data.get("equip_key")
                   and data.get("type") != "use" and not data.get("bar_value"))
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
