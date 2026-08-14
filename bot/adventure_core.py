"""ตรรกะการเดินทางกลาง (เว็บเกม เฟส 5.1)

ดึง "การตัดสินใจว่าก้าวนี้เจออะไร" ออกจาก walk_step ของ Discord View
ลำดับความสำคัญยกมาครบทุกข้อ ห้ามสลับลำดับ — ลำดับคือกติกาของเกม

หมายเหตุ: ฟังก์ชันนี้เขียน DB ตรงบางจุด (dungeon_steps/last_event/village_cooldown)
เหมือนของเดิมเป๊ะ เพื่อไม่ให้พฤติกรรมฝั่งดิสเปลี่ยน
"""
import json
import random

import bot.models.player_model as player_model
from bot import config_loader, game_modifiers, robbery

SUMMON_EVENTS = ("mini_summon", "main_summon", "unbeatable_summon")

# น้ำหนักอีเวนต์ตามสถานการณ์ก่อนหน้า (ตั้งทับได้ที่ Panel)
EVENT_WEIGHTS = {
    "village":            [2,   0,        3,      1,       90,       4],
    "dungeon_inside":     [45,  5,        35,     0,       5,        10],
    "monster":            [25,  25,       20,     10,      10,       10],
    "treasure":           [30,  20,       10,     15,      15,       10],
    "npc":                [20,  40,       15,     10,      5,        10],
    "trap":               [35,  15,       15,     10,      10,       15],
    "none":               [30,  20,       20,     10,      10,       10],
}
EVENT_LIST = ["monster", "village", "treasure", "dungeon", "npc", "trap"]


def event_weights(last_evt):
    """น้ำหนักอีเวนต์ของสถานการณ์นั้น — ตั้งได้ที่ Panel (ไม่ตั้ง/ตั้งไม่ครบ = ค่าเดิมในโค้ด)

    รับได้ทั้งรูป dict จาก Panel {"monster": 25, ...} และ list เรียงตาม EVENT_LIST
    """
    if last_evt not in EVENT_WEIGHTS:
        last_evt = "none"
    default = list(EVENT_WEIGHTS[last_evt])
    row = (config_loader.get_balance("events.weights", {}) or {}).get(last_evt)
    try:
        if isinstance(row, dict):
            return [max(0, int(row.get(evt, default[i]))) for i, evt in enumerate(EVENT_LIST)]
        if isinstance(row, list) and len(row) == len(EVENT_LIST):
            return [max(0, int(w)) for w in row]
    except (TypeError, ValueError):
        pass
    return default


def decide_event(user_id, player, statuses, mods, dg_steps, last_evt, cooldown, rng=random):
    """ก้าวนี้เจอเหตุการณ์อะไร — คืน (เหตุการณ์, ข้อมูลอีเวนต์พิเศษ, dungeon_steps ที่เหลือ)

    ลำดับ (ห้ามสลับ):
      1. วาปกลับเมือง        2. สแกนกล่องสมบัติ    3. อยู่ในดันเจี้ยน/ใบเรียกบอส
      4. กับดักหีบ/ชุบชีวิต/วาปเข้าดันเจี้ยน
      5. สุ่มปกติ: กับดักมอน → โจรปล้น → พาหนะ → อีเวนต์พิเศษ → สงบ → ทอยตามน้ำหนัก
    """
    special_event = None

    # [1] วาปกลับเมือง — สำคัญที่สุด รีเซ็ตดันเจี้ยนทิ้ง
    if last_evt == "warp_village":
        player_model.update_player_field(user_id, "dungeon_steps", 0)
        return "village", None, 0

    # [2] สแกนกล่องสมบัติ — อยู่ในดันเจี้ยนได้ ไม่ลบเทิร์น
    if last_evt == "scan_box":
        return "treasure", None, dg_steps

    # [3] อยู่ในดันเจี้ยน หรือใช้ใบเรียกบอส → เจอมอนแน่นอน
    if dg_steps > 0 or last_evt in SUMMON_EVENTS:
        if dg_steps > 0:
            dg_steps = max(0, dg_steps - 1)
            player_model.update_player_field(user_id, "dungeon_steps", dg_steps)
        return "monster", None, dg_steps

    # [4] เหตุการณ์บังคับอื่นๆ
    if last_evt == "treasure_trap":
        return "trap", None, dg_steps
    if last_evt == "revive":
        return "village", None, dg_steps
    if last_evt == "warp_dungeon":
        return "dungeon", None, dg_steps

    # [5] สุ่มปกติ
    forced_event, _trap_key = game_modifiers.status_forced_event(statuses)
    if forced_event:
        return forced_event, None, dg_steps

    rob_event = robbery.roll_robbery(player.get("cash", 0), player.get("bank", 0), statuses, rng)
    if rob_event:
        return rob_event, None, dg_steps

    if game_modifiers.roll_travel_chance(mods):
        return "travel", None, dg_steps

    special_event = game_modifiers.roll_special_event(mods)
    if special_event:
        return "special", special_event, dg_steps

    if game_modifiers.roll_calm_chance():
        return "calm", None, dg_steps

    weights = event_weights(last_evt)
    if cooldown > 0:
        weights[1] = 0                       # คูลดาวน์หมู่บ้าน = ห้ามเจอหมู่บ้านซ้ำ
    weights = game_modifiers.apply_event_weights(weights, EVENT_LIST, mods)
    mult = game_modifiers.status_event_weight_mult(statuses)
    if mult:
        weights = [w * mult.get(evt, 1.0) for w, evt in zip(weights, EVENT_LIST)]
    return rng.choices(EVENT_LIST, weights=weights, k=1)[0], None, dg_steps


def roll_combat(user_id, player, statuses, element_data, m_stats, player_elements, rng=random):
    """ทอยเต๋าหนึ่งเทิร์น — คืนแต้มผู้เล่น/มอน พร้อม "ที่มาของแต้ม" ไว้โชว์บนจอ

    ลำดับยกมาจาก process_turn เดิมทั้งหมด (ลำดับมีผลกับผลลัพธ์ ห้ามสลับ):
      ทอยพื้นฐาน → ถุงเต๋าเทพี/สถานะถ่วง → passive ลม → สัตว์เลี้ยง
      → เต๋าถ่วงน้ำหนัก → รากพันธนาการ → โบนัสเต๋ามอนจากธาตุ
      → เต๋าหลุดมือ → เต๋าถูกผนึก → โบนัสเต๋ามอนจากสถานะ

    คืน dict: player_roll, monster_roll, player_parts, monster_parts, log, statuses
    (statuses อาจเปลี่ยนเมื่อโคลเวอร์ถูกใช้กันราก)
    """
    dice_n = m_stats.get("dice_count", 1)
    player_roll = rng.randint(1, 20)
    monster_roll = sum(rng.randint(1, 20) for _ in range(dice_n))
    parts = [f"`{player_roll}` พื้นฐาน"]
    mon_parts = [f"`{monster_roll}` พื้นฐาน" + (f" ({dice_n} เต๋า)" if dice_n > 1 else "")]
    log = ""

    # 👝 ถุงเต๋าเทพี / 🍄 สถานะถ่วงเต๋า
    roll_bonus = game_modifiers.status_roll_bonus(statuses)
    if roll_bonus > 0:
        player_roll += roll_bonus
        parts.append(f"👝+{roll_bonus}")
        log += f"👝 **ถุงเต๋าเทพีสั่นกรุ๋งกริ๋ง** เต๋า `+{roll_bonus}` (รวม {player_roll})\n"
    elif roll_bonus < 0:
        player_roll = max(1, player_roll + roll_bonus)     # กดต่ำสุด 1 ไม่ทับกลไกราก (เต๋า=0)
        parts.append(f"🍄{roll_bonus}")
        log += f"🍄 **ร่างกายหนักอึ้ง** เต๋า `{roll_bonus}` (เหลือ {player_roll})\n"

    # 💨 passive ธาตุลมของผู้เล่น
    wind_bonus = game_modifiers.player_passive_sum(player_elements or [], "roll_bonus")
    if wind_bonus:
        player_roll += wind_bonus
        parts.append(f"💨+{wind_bonus}")
        log += f"💨 **สายลมประจำตัวหนุนลูกเต๋า** `+{wind_bonus}` (รวม {player_roll})\n"

    # 🐾 สัตว์เลี้ยงที่ติดตัว
    try:
        from bot import pets as _pets
        pet_bonus = _pets.roll_bonus(player)
        if pet_bonus:
            player_roll += pet_bonus
            parts.append(f"🐾+{pet_bonus}")
            log += (f"🐾 **{_pets.active(player)['name']} ส่งเสียงเชียร์!** "
                    f"เต๋า `+{pet_bonus}` (รวม {player_roll})\n")
    except Exception as e:
        print(f"⚠️ [pets] โบนัสเต๋าพัง: {e}")

    # 🎲 เต๋าถ่วงน้ำหนัก: การันตีแต้มขั้นต่ำ (ก่อนราก/เต๋าหลุดมือ)
    weighted_min = game_modifiers.status_min_roll(statuses)
    if weighted_min and player_roll < weighted_min:
        log += f"🎲 **เต๋าถ่วงน้ำหนักทำงาน!** แต้ม `{player_roll}` ถูกดันขึ้นเป็น `{weighted_min}`\n"
        player_roll = weighted_min
        parts = [f"🎲 ดันขึ้นเป็น `{weighted_min}` (เต๋าถ่วง)"]

    # 🌿 รากพันธนาการ — ล็อกเต๋าผู้เล่นเหลือ 0
    root_chance = element_data.get("root_chance", 0)
    if root_chance and rng.randint(1, 100) <= root_chance:
        if game_modifiers.has_status_flag(statuses, "block_root"):
            consumed = [k for k in statuses
                        if game_modifiers.STATUS_EFFECTS[k].get("block_root")
                        and not game_modifiers.STATUS_EFFECTS[k].get("artifact")]
            if consumed:
                statuses = {k: v for k, v in statuses.items() if k not in consumed}
                fresh = game_modifiers.parse_statuses(player_model.get_player(user_id))
                fresh = {k: v for k, v in fresh.items() if k not in consumed}
                player_model.update_player_field(user_id, "status_effects", fresh)
                log += "🍀 **โคลเวอร์นำโชคเปล่งแสง!** รากไม้เหี่ยวเฉาก่อนแตะตัวคุณ (เครื่องรางสลายไป)\n"
            else:
                log += "🧥 **เสื้อคลุมเปลือกไม้สั่นไหว** — รากไม้จำต้นตระกูลตัวเองได้ ถอยหนีไปเอง!\n"
        else:
            player_roll = 0
            parts = ["🌿 ถูกรากล็อกเหลือ `0`"]
            log += ("🌿 **รากพันธนาการ!** เถาวัลย์พุ่งขึ้นรัดแขนคุณแน่น "
                    "เต๋าโจมตีถูกล็อกเหลือ `0` ในเทิร์นนี้!\n")

    # 💨🌿 โบนัสเต๋ามอนสเตอร์จากธาตุ
    elem_dice = element_data.get("dice_bonus")
    if elem_dice:
        bonus = rng.randint(elem_dice[0], elem_dice[1])
        monster_roll += bonus
        mon_parts.append(f"{element_data['label'].split()[0]}+{bonus}")
        log += f"{element_data['label']}: กระแสธาตุหนุนเต๋ามอนสเตอร์ `+{bonus}` หน่วย!\n"

    # 🤲 เต๋าหลุดมือ
    fumble = game_modifiers.status_fumble_chance(statuses)
    if fumble and rng.randint(1, 100) <= fumble:
        player_roll = 0
        log += "🤲 **เต๋าหลุดมือ!** นิ้วที่แข็งชาทำลูกเต๋าร่วงพื้น — เสียจังหวะโจมตีเทิร์นนี้!\n"

    # 🎲 เต๋าถูกผนึก
    seal_at = game_modifiers.status_seal_threshold(statuses)
    if seal_at and player_roll >= seal_at:
        log += f"🎲 **เต๋าถูกกดทับ!** สถานะบนร่างคุณบีบแต้ม `{player_roll}` ให้เหลือ `1`!\n"
        player_roll = 1

    # 🌱 โบนัสเต๋ามอนสเตอร์จากสถานะ
    status_dice = game_modifiers.status_monster_dice_bonus(statuses)
    if status_dice:
        monster_roll += status_dice
        mon_parts.append(f"🌱+{status_dice}")
        log += f"🌱 ร่างที่ถูกพันธนาการขยับลำบาก — เต๋ามอนสเตอร์ `+{status_dice}` หน่วย!\n"

    return {"player_roll": player_roll, "monster_roll": monster_roll,
            "player_parts": parts, "monster_parts": mon_parts,
            "log": log, "statuses": statuses}


def commit_event(user_id, chosen_event, last_evt):
    """บันทึกผลของก้าวนี้ — last_event และคูลดาวน์หมู่บ้าน (ยกมาจากของเดิม)

    เจอมอนต่อจากใบเรียกบอส = ไม่ทับ last_event (ต้องคงค่าเรียกบอสไว้ให้ระบบไฟต์อ่าน)
    """
    if not (chosen_event == "monster" and last_evt in SUMMON_EVENTS):
        player_model.update_player_field(user_id, "last_event", chosen_event)
    if chosen_event == "village":
        player_model.update_player_field(user_id, "village_cooldown", 10)


def step_prelude(user_id, player, player_elements=()):
    """งานต้นก้าวก่อนสุ่มเหตุการณ์ — ใช้ร่วมกันทั้ง Discord และเว็บ (เว็บเกม เฟส 5.4)

    ทำตามลำดับเดิมเป๊ะ: นับเควสรายวัน > ลดคูลดาวน์หมู่บ้าน > ติดสถานะประจำธีม
    > เลือดไหล/พิษกัดกิน + tick สถานะ > passive ธาตุไม้ฟื้น HP

    คืน dict — ผู้เรียกเอา notes ไปแสดงเอง (ดิสส่ง followup, เว็บส่ง JSON)
    dead=True คือหมดสติกลางทาง ผู้เรียกต้องพาไปหน้าฟื้นคืนชีพ
    """
    try:
        from bot import daily as _daily
        _daily.track(user_id, "walk", 1)
    except Exception as e:
        print(f"⚠️ [daily] นับเควสเดินทางพัง: {e}")

    cooldown = player.get("village_cooldown", 0)
    if cooldown > 0:
        cooldown -= 1
        player_model.update_player_field(user_id, "village_cooldown", cooldown)

    mods = game_modifiers.get_active_modifiers(player)
    statuses = game_modifiers.parse_statuses(player)
    notes = []

    # 🌨️ สถานะแวดล้อมของธีม (เช่น frostbite ช่วง Absolute Zero): ยังไม่ติด = ติดทันที
    ambient = mods.get("ambient_status")
    if ambient and ambient in game_modifiers.STATUS_EFFECTS and ambient not in statuses:
        statuses = game_modifiers.apply_status(statuses, ambient)
        if ambient in statuses:      # ติดจริงเท่านั้น (สถานะภูมิคุ้มกันเช่น "อบอุ่น" อาจกันไว้)
            notes.append(f"🌨️ {game_modifiers.STATUS_EFFECTS[ambient]['label']} แทรกซึมเข้าร่างคุณ! "
                         f"(หาความอบอุ่นจากหมู่บ้าน/NPC/ดันเจี้ยนเพื่อคลายหนาว)")

    if statuses:
        step_dmg, dmg_details = game_modifiers.roll_step_damage(
            statuses, max_hp=player.get("max_hp", 100))
        statuses, expired = game_modifiers.tick_statuses(statuses, "step")
        player_model.update_player_field(user_id, "status_effects", statuses)

        if step_dmg:
            new_hp = max(0, player.get("hp", 100) - step_dmg)
            player_model.update_player_field(user_id, "hp", new_hp)
            player["hp"] = new_hp
            detail = " ".join(f"{label} `-{dmg}`" for label, dmg in dmg_details)
            notes.append(f"🩸 สถานะกัดกินร่างกาย: {detail} (HP เหลือ `{new_hp}`)")
            if new_hp <= 0:
                player_model.update_player_fields(user_id, {"current_state": "dead", "hp": 0})
                return {"notes": notes, "dead": True, "player": player, "statuses": statuses,
                        "mods": mods, "dg_steps": player.get("dungeon_steps", 0),
                        "last_evt": player.get("last_event", "none"), "cooldown": cooldown}

        for key in expired:
            notes.append(f"⏳ {game_modifiers.STATUS_EFFECTS[key]['label']} หมดฤทธิ์แล้ว")

    # 🌿 Passive ธาตุไม้ (สังเคราะห์แสง): ฟื้น % MaxHP ทุกก้าว — เงียบ ๆ เห็นผลที่ตัวเลข HP
    regen_pct = game_modifiers.player_passive_sum(player_elements, "step_regen")
    if regen_pct:
        max_hp = player.get("max_hp", 100)
        if 0 < player.get("hp", 100) < max_hp:
            player["hp"] = min(max_hp, player.get("hp", 100) + max(1, round(max_hp * regen_pct)))
            player_model.update_player_field(user_id, "hp", player["hp"])

    return {"notes": notes, "dead": False, "player": player, "statuses": statuses, "mods": mods,
            "dg_steps": player.get("dungeon_steps", 0),
            "last_evt": player.get("last_event", "none"), "cooldown": cooldown}


# ─────────────────────────────────────────────────────────────────────────────
# ตัวตัดสินผลของแต่ละเหตุการณ์ (เว็บเกม เฟส 5.4)
# ทุกตัวคืน dict {"text": ข้อความผลลัพธ์, ...ข้อมูลดิบ} — ผู้เรียกเอาไปแสดงเอง
# เขียน DB จบในตัว รวมถึงปลดสถานะกลับ idle เสมอ ผู้เล่นจะได้ไม่ค้าง
# ─────────────────────────────────────────────────────────────────────────────

def _done(user_id, last_event):
    player_model.update_player_fields(user_id, {"current_state": "idle", "last_event": last_event})


def rest_cost(player):
    """ค่าพักแรมในหมู่บ้าน — ตั้งได้ที่ Panel และคิดเพิ่มตามเลเวลได้"""
    return (int(config_loader.get_balance("village.rest_cost", 2000))
            + int(config_loader.get_balance("village.rest_cost_per_level", 0)) * player.get("level", 1))


def resolve_village(user_id, action):
    """🏡 หมู่บ้าน — rest (พักแรมฟื้น HP เต็ม) | leave (เดินต่อ)

    เกราะที่ความคงทนหมดจะไม่ให้โบนัส HP — ฟื้นได้แค่ max_hp เปล่า
    """
    player = player_model.get_player(user_id) or {}
    if action != "rest":
        _done(user_id, "village")
        return {"text": "🚶 คุณก้าวเท้าเดินออกจากหมู่บ้านมุ่งสู่เส้นทางหลัก...", "hp": player.get("hp", 0)}

    cost = rest_cost(player)
    if player.get("cash", 0) < cost:
        return {"error": f"❌ เงินสดไม่พอจ่ายค่าห้องนอน (ต้องมี `{cost:,}` ทอง)!"}

    armor = config_loader.get_armor_stats(player.get("armor", "None")) or config_loader.get_armor_stats("None")
    hp_bonus = armor.get("hp", 0) if player.get("armor_dur", 0) > 0 else 0
    full_hp = player["max_hp"] + hp_bonus

    player_model.update_player_fields(user_id, {"cash": player["cash"] - cost, "hp": full_hp,
                                                "current_state": "idle", "last_event": "village"})
    return {"text": f"💤 คุณนอนพักผ่อนอย่างเต็มอิ่ม ฟื้นฟู HP จนเต็ม! *(จ่าย {cost:,} ทอง)*",
            "hp": full_hp, "cost": cost}


def resolve_treasure(user_id, action, is_rogue=False, rng=random):
    """📦 หีบสมบัติ — open (25% เป็นมิมิก, Rogue กันได้ 100%) | ignore

    เปิดได้จริง: เงิน 80% / ไอเทม 20% (ของแพงออกยากตามราคาซื้อ)
    """
    if action != "open":
        _done(user_id, "treasure")
        return {"text": "👀 คุณเลือกที่จะละสายตาจากกล่องและเดินผ่านไปเนิบๆ"}

    player = player_model.get_player(user_id) or {}
    if rng.random() < 0.25 and not is_rogue:
        _done(user_id, "treasure_trap")
        return {"text": "💥 **มันคือหีบกับดักมิมิก (Mimic)!** กลไกกับดักทำงานครอบงำคุณ! "
                        "(ครั้งหน้าคุณจะเจอกับดักชัวร์ๆ 100%)", "mimic": True}

    _done(user_id, "treasure")
    if rng.choices(["gold", "item"], weights=[80, 20], k=1)[0] == "gold":
        gold = rng.randint(50, 150)
        player_model.update_player_field(user_id, "cash", player["cash"] + gold)
        return {"text": f"🎉 โชคดีมาก! ด้านในเป็นหีบสมบัติแท้ คุณได้รับเงินสกุลกลาง `{gold}` ทอง!",
                "gold": gold}

    items = config_loader.get_all_items()
    ids = list(items.keys())
    chosen = rng.choices(ids, weights=[1.0 / max(items[i]["buy"], 1) for i in ids], k=1)[0]
    name = items[chosen]["name"]

    inv = player_model.load_inventory(player.get("inventory", ""))
    cap = player.get("capacity", 10)
    if cap and len(inv) >= cap:
        return {"text": f"🎉 แจ็คพอต!! คุณเปิดหีบได้ **{name}**!\n"
                        f"⚠️ **แต่กระเป๋าของคุณเต็ม ({len(inv)}/{cap}) เลยเก็บไม่ได้!**",
                "item": name, "bag_full": True}
    inv.append(str(chosen))
    player_model.update_player_field(user_id, "inventory", json.dumps(inv))
    return {"text": f"🎉 แจ็คพอต!! หีบมี **{name}** ซ่อนอยู่!\n✅ คุณเก็บไอเทมล้ำค่าชิ้นนี้เข้ากระเป๋าไปได้ฟรีๆ!",
            "item": name}


def resolve_dungeon(user_id, action):
    """💀 ปากดันเจี้ยน — enter (สู้ต่อเนื่อง 10 ตา) | leave"""
    if action == "enter":
        player_model.update_player_fields(user_id, {"current_state": "idle", "last_event": "dungeon_inside",
                                                    "dungeon_steps": 10})
        return {"text": "💀 คุณก้าวเท้าเข้าสู่ประตูดันเจี้ยนสุดมืดมิด! มีไอชั่วร้ายแผ่ออกมา... "
                        "ต่อจากนี้คุณต้องสู้กับมอนสเตอร์ต่อเนื่อง 10 ตา!", "steps": 10}
    _done(user_id, "dungeon")
    return {"text": "🏃 ปลอดภัยไว้ก่อน คุณตัดสินใจเดินหันหลังกลับช้าๆ"}


def resolve_trap(user_id, is_rogue=False, rng=random):
    """⚠️ กับดัก — ทอยหลบด้วยค่าหลบของเกราะ (Rogue รอด 100%) พลาดเสีย HP + เกราะสึก"""
    player = player_model.get_player(user_id) or {}
    _done(user_id, "trap")
    if is_rogue:
        return {"text": "💨 **พรสวรรค์คลาส Rogue ทำงาน!** คุณกระโดดม้วนตัวหลบกลไกกับดักพ้นได้อย่างงดงาม 100%!",
                "dodged": True, "hp": player.get("hp", 0)}

    armor = config_loader.get_armor_stats(player.get("armor", "None")) or config_loader.get_armor_stats("None")
    eva = armor.get("eva", 0)
    roll = rng.randint(1, 100)
    if roll <= eva:
        return {"text": f"🎉 รอดหวุดหวิด! (เต๋าสุ่ม {roll} vs อัตราเกราะ {eva}%) คุณก้าวขาหลบใบมีดกับดักพ้นสำเร็จ!",
                "dodged": True, "roll": roll, "eva": eva, "hp": player.get("hp", 0)}

    dmg = rng.randint(15, 35)
    new_hp = max(0, player["hp"] - dmg)
    dur = player.get("armor_dur", 0)
    player_model.update_player_fields(user_id, {
        "hp": new_hp, "armor_dur": max(0, dur - max(1, dmg // 10)) if dur > 0 else 0})
    return {"text": f"💥 พลาดท่ากระแทกกับดัก! โดนหนามแทงเสีย HP `- {dmg}` หน่วย! (เลือดคงเหลือ: {new_hp})",
            "dodged": False, "roll": roll, "eva": eva, "damage": dmg, "hp": new_hp}


def resolve_travel(user_id, encounter, action):
    """🧭 พาหนะข้ามทวีป — board (จ่ายค่าโดยสาร วัดดวงปลายทาง) | decline

    encounter ต้องมาจากฝั่งเซิร์ฟเวอร์ (เก็บไว้ตอนเจอ) ห้ามรับค่าโดยสารจากเบราว์เซอร์
    """
    player = player_model.get_player(user_id) or {}
    fare = int(encounter.get("fare", 0))
    label = encounter.get("label", "ยานพาหนะ")

    if action != "board":
        player_model.update_player_field(user_id, "current_state", "idle")
        return {"text": f"🙅 คุณโบกมือปฏิเสธ {label} แล้วออกเดินทางต่อ..."}

    if player.get("cash", 0) < fare:
        player_model.update_player_field(user_id, "current_state", "idle")
        return {"text": f"💸 เงินสดของคุณไม่พอค่าโดยสาร (`{fare:,}` ทอง) — {label} จากไปต่อหน้าต่อตา..."}

    dest = game_modifiers.roll_destination(encounter["vehicle"], player.get("continent") or "main")
    info = game_modifiers.CONTINENTS[dest]
    player_model.update_player_fields(user_id, {"cash": player.get("cash", 0) - fare, "continent": dest,
                                                "current_state": "idle", "last_event": "none"})
    return {"text": f"{label} ➜ {info['label']}\n{info['arrival_text']}\n\n💰 จ่ายค่าโดยสาร `{fare:,}` ทอง",
            "continent": dest, "fare": fare}


# ─────────────────────────────────────────────────────────────────────────────
# เหตุการณ์ค้าง (เว็บเกม เฟส 5.4)
# เว็บไม่มี "ข้อความที่มีปุ่ม" แบบดิส จึงต้องจำไว้ใน DB ว่าผู้เล่นค้างอยู่ที่อะไร
# ไม่งั้นรีเฟรชหน้าแล้ว current_state ค้างจนเล่นไม่ได้ทั้งสองแพลตฟอร์ม
# ─────────────────────────────────────────────────────────────────────────────

def _pending_table(conn):
    conn.execute("CREATE TABLE IF NOT EXISTS adventure_pending "
                 "(user_id INTEGER PRIMARY KEY, event TEXT, data TEXT, updated_at REAL)")


def set_pending(user_id, event, data=None):
    import sqlite3
    import time
    with sqlite3.connect(player_model.DB_NAME, timeout=10) as conn:
        _pending_table(conn)
        conn.execute("INSERT OR REPLACE INTO adventure_pending VALUES (?,?,?,?)",
                     (int(user_id), event, json.dumps(data or {}), time.time()))


def get_pending(user_id):
    """คืน (event, data) ของเหตุการณ์ที่ค้างอยู่ — (None, {}) ถ้าไม่มี"""
    import sqlite3
    with sqlite3.connect(player_model.DB_NAME, timeout=10) as conn:
        _pending_table(conn)
        row = conn.execute("SELECT event, data FROM adventure_pending WHERE user_id=?",
                           (int(user_id),)).fetchone()
    return (row[0], json.loads(row[1])) if row else (None, {})


def clear_pending(user_id):
    import sqlite3
    with sqlite3.connect(player_model.DB_NAME, timeout=10) as conn:
        _pending_table(conn)
        conn.execute("DELETE FROM adventure_pending WHERE user_id=?", (int(user_id),))


# หน้าต่างเหตุการณ์ในดิสมี timeout ของมันเอง เว็บไม่มี จึงต้องหมดอายุเองให้เหมือนกัน
# (ค่าตรงกับ timeout ของ View แต่ละตัวใน game_views.py)
PENDING_TIMEOUT = {"village": 600}
PENDING_TIMEOUT_DEFAULT = 60


def expire_pending(user_id):
    """หมดเวลาเหตุการณ์ที่ค้างไว้นานเกิน — ทำเหมือน on_timeout ของ View ในดิสเป๊ะ

    สำคัญกับสถานะ "mugging" เป็นพิเศษ เพราะ !play ไม่ได้ปลดสถานะนี้ให้
    ถ้าไม่หมดอายุเอง ผู้เล่นที่ปิดเว็บกลางคันจะค้างถาวร

    คืนข้อความบอกผลถ้าหมดอายุจริง ('' = ยังไม่หมด/ไม่มีอะไรค้าง)
    """
    import sqlite3
    import time
    event, data = get_pending(user_id)
    if not event:
        return ""
    with sqlite3.connect(player_model.DB_NAME, timeout=10) as conn:
        _pending_table(conn)
        row = conn.execute("SELECT updated_at FROM adventure_pending WHERE user_id=?",
                           (int(user_id),)).fetchone()
    age = time.time() - float(row[0] if row else 0)
    if age < PENDING_TIMEOUT.get(event, PENDING_TIMEOUT_DEFAULT):
        return ""

    clear_pending(user_id)
    if event == "mugging":
        # ยืนตัวแข็งตัดสินใจไม่ทัน = นับเป็นหนี (ตรงกับ MuggingEventView.on_timeout)
        m = robbery.resolve_mugging(user_id, "flee")
        return (f"⏳ คุณยืนตัวแข็งตัดสินใจไม่ทัน... โจรฉกถุงทองไป `{m['lost']:,}` ทอง! "
                f"(เหลือ `{m['cash']:,}`){m['theft']}")
    player_model.update_player_field(user_id, "current_state", "idle")
    if event == "travel":
        return f"⏳ {data.get('label', 'ยานพาหนะ')} ออกเดินทางไปแล้วโดยไม่มีคุณ..."
    return "⏰ **หน้าต่างเหตุการณ์ก่อนหน้าหมดอายุแล้ว** — เดินทางต่อได้เลย"


# ─────────────────────────────────────────────────────────────────────────────
# 🧓 เควส NPC (เว็บเกม เฟส 5.5)
# ─────────────────────────────────────────────────────────────────────────────

def npc_disguise(player, rng=random):
    """🎭 สัปดาห์ธีม Masquerade: NPC ตัวนี้เป็นมอนปลอมตัวไหม — ตัดสินตอนเจอ ผู้เล่นไม่รู้

    คืน (cfg ของธีม, ปลอมตัวจริงไหม) — cfg เป็น None แปลว่าสัปดาห์นี้ไม่มีธีมนี้
    """
    cfg = game_modifiers.get_active_modifiers(player).get("masquerade")
    return cfg, bool(cfg and rng.randint(1, 100) <= cfg.get("chance", 0))


def npc_talk(user_id, rng=random):
    """💬 คุยกับ NPC — สุ่มได้ของขวัญ / โดนยัดขาย / ไม่มีอะไร (ยกมาจากปุ่มในดิสทั้งชุด)"""
    player = player_model.get_player(user_id) or {}
    items = config_loader.get_all_items()
    outcome = rng.choice(["gift", "shop", "nothing"])
    _done(user_id, "npc")

    if outcome == "gift":
        gold = rng.randint(30, 70)
        player_model.update_player_field(user_id, "cash", player["cash"] + gold)
        return {"text": f"🧓 NPC ถูกชะตาในตัวคุณ! เขาใจดีมอบเศษเงินทุนกลางจำนวน `{gold}` ทองให้ฟรี!",
                "gold": gold}

    if outcome == "nothing":
        return {"text": "💤 NPC แค่บ่นพึมพำเรื่องฟ้าฝนชวนคุยแก้เหงาเฉยๆ ไม่มีอะไรเกิดขึ้น"}

    ids = list(items.keys())
    chosen = rng.choices(ids, weights=[1.0 / max(items[i]["buy"], 1) for i in ids], k=1)[0]
    item = items[chosen]
    price = rng.randint(0, item["buy"] * 2)
    inv = player_model.load_inventory(player.get("inventory", "[]"))
    cap = player.get("capacity", 10)

    if player["cash"] < price:
        return {"text": f"🧓 NPC พ่อค้าเร่เสนอขาย **{item['name']}** ให้คุณในราคา `{price:,}` ทอง!\n"
                        f"❌ **แต่เงินในกระเป๋าของคุณไม่พอ!** NPC จึงเดินจากไป..."}
    if cap and len(inv) >= cap:
        return {"text": f"🧓 NPC พ่อค้าเร่เสนอขาย **{item['name']}** ในราคา `{price:,}` ทอง!\n"
                        f"⚠️ **แต่กระเป๋าของคุณเต็ม!** NPC จึงเดินจากไป..."}

    inv.append(str(chosen))
    player_model.update_player_fields(user_id, {"cash": player["cash"] - price,
                                                "inventory": json.dumps(inv)})
    price_text = f"`{price:,}` ทอง" if price > 0 else "**ฟรี!!**"
    return {"text": f"🧓 NPC พ่อค้าเร่เสนอขาย **{item['name']}** ในราคา {price_text}!\n"
                    f"✅ **คุณมีเงินและที่ว่างพอ จึงจ่ายเงินและรับของมาโดยอัตโนมัติ**",
            "spent": price, "item": item["name"]}


def npc_quest_offer(user_id, rng=random):
    """📜 สร้างข้อเสนอแลกของ — ไม่แตะกระเป๋า แค่คำนวณข้อเสนอ (ตกลงแล้วค่อยหัก)

    คืน None ถ้ากระเป๋าว่าง (NPC ไม่มีอะไรให้ขอ)
    """
    player = player_model.get_player(user_id) or {}
    inv = player_model.load_inventory(player.get("inventory", "[]"))
    if not inv:
        _done(user_id, "npc")
        return None

    items = config_loader.get_all_items()
    requested = rng.sample(inv, rng.randint(1, len(inv)))
    counts = {}
    for i in requested:
        counts[i] = counts.get(i, 0) + 1
    req_text = ", ".join(f"**{items.get(str(i), {}).get('name', '???')}** x{c}" for i, c in counts.items())
    req_value = sum(items.get(str(i), {}).get("buy", 0) for i in requested)

    reward_val = rng.randint(int(req_value * 0.5), int(req_value * 2))
    valid = [i for i, d in items.items() if 0 < d.get("buy", 0) <= reward_val]
    reward_item = rng.choice(valid) if valid else None
    reward_cash = reward_val - (items[reward_item]["buy"] if reward_item else 0)

    reward_text = (f"**{items[reward_item]['name']}** และเงิน `{reward_cash:,}` ทอง"
                   if reward_item else f"`{reward_cash:,}` ทอง")
    return {"requested": requested, "reward_item": reward_item, "reward_cash": reward_cash,
            "text": (f"🧓 **NPC พ่อค้าลึกลับยื่นข้อเสนอสุดเร้าใจ!**\n\n"
                     f"👇 **เขาต้องการ:**\n{req_text} (ประเมินมูลค่า: `{req_value:,}` ทอง)\n\n"
                     f"🎁 **สิ่งที่จะนำมาแลกเปลี่ยน:**\n{reward_text} (มูลค่ารวม: `{reward_val:,}` ทอง)\n\n"
                     f"คุณจะรับข้อเสนอนี้หรือไม่?")}


def npc_quest_settle(user_id, offer, accept):
    """✅ ตกลง/ปฏิเสธข้อเสนอ — เช็คของครบอีกรอบก่อนแลก (กันแอบเอาของไปเก็บระหว่างคิด)"""
    if not accept:
        _done(user_id, "npc")
        return {"text": "🙅‍♂️ คุณส่ายหัวปฏิเสธ NPC จึงเก็บของแล้วเดินจากไป"}

    player = player_model.get_player(user_id) or {}
    inv = player_model.load_inventory(player.get("inventory", "[]"))
    left = list(inv)
    for item in offer.get("requested", []):
        if item in left:
            left.remove(item)
        else:
            _done(user_id, "npc")
            return {"text": "❌ ไอเทมในกระเป๋าของคุณไม่ครบตามที่ตกลงไว้! NPC โกรธและเดินหนีไป"}

    if offer.get("reward_item"):
        left.append(str(offer["reward_item"]))
    player_model.update_player_fields(user_id, {
        "inventory": json.dumps(left), "cash": player.get("cash", 0) + offer.get("reward_cash", 0),
        "current_state": "idle", "last_event": "npc"})
    return {"text": "🤝 **แลกเปลี่ยนสำเร็จ!** คุณได้รับของรางวัลและ NPC เดินจากไปอย่างมีความสุข",
            "gold": offer.get("reward_cash", 0)}


# ─────────────────────────────────────────────────────────────────────────────
# ✨ อีเวนต์พิเศษ (เว็บเกม เฟส 5.5)
# ตัวจ่ายผล (execute_special_outcome) อยู่ใน game_views อยู่แล้ว ตรงนี้แค่เลือก outcome
# ─────────────────────────────────────────────────────────────────────────────

def special_leads_to_fight(event):
    """อีเวนต์นี้มีทางออกที่ลากเข้าไฟต์ไหม — เว็บยังสู้ไม่ได้จึงต้องรู้ล่วงหน้า (เฟส 5.6 จะเลิกใช้)"""
    pools = [event.get("success"), event.get("fail")]
    pools += [c.get("outcome") for c in event.get("choices") or []]
    pools += list(event.get("outcomes") or [])
    return any((o or {}).get("start_fight") for o in pools)


def special_pick_outcome(event, action, rng=random):
    """เลือก outcome ตามแบบของอีเวนต์ — คืน (outcome, ข้อความนำหน้า)

    dice_check: ทอย d20 เทียบ pass_roll | choice: เลือกตามปุ่มที่กด
    """
    if event.get("template") == "dice_check":
        roll = rng.randint(1, 20)
        need = int(event.get("pass_roll", 10))
        ok = roll >= need
        return (event.get("success" if ok else "fail", {}),
                f"🎲 คุณทอยได้ `{roll}` (ต้องการ `{need}`) — {'✅ สำเร็จ!' if ok else '❌ พลาด!'}")

    choices = event.get("choices") or []
    try:
        pick = choices[int(action)]
    except (ValueError, TypeError, IndexError):
        pick = choices[0] if choices else {}
    return pick.get("outcome", {}), None


def _roll_amount(value, rng=None):
    """ค่าคงที่ หรือช่วง [lo, hi] → เลขจริง"""
    if isinstance(value, (list, tuple)):
        return (rng or random).randint(int(value[0]), int(value[1]))
    return int(value)


# ── อีเวนต์พิเศษ: ตัวจ่ายผล (ย้ายมาจาก game_views เฟส 5.5 — ไม่มีอะไรผูกกับ discord) ──

def execute_special_outcome(user_id, outcome, rng=None):
    """จ่ายผลอีเวนต์พิเศษ (ดู outcome format ใน game_modifiers) — คืน (บรรทัดข้อความ, died)"""
    rng = rng or random
    player = player_model.get_player(user_id)
    lines = []
    updates = {}
    died = False
    statuses = game_modifiers.parse_statuses(player)
    status_changed = False

    if outcome.get("text"):
        lines.append(outcome["text"])

    if "gold" in outcome:
        amount = _roll_amount(outcome["gold"], rng)
        new_cash = max(0, player.get("cash", 0) + amount)
        updates["cash"] = new_cash
        word = "ได้รับ" if amount >= 0 else "เสีย"
        lines.append(f"💰 {word}เงิน `{abs(amount):,}` ทอง (คงเหลือ `{new_cash:,}`)")

    if "items" in outcome:
        item_entries = outcome["items"] if isinstance(outcome["items"], list) else [outcome["items"]]
        inv = player_model.load_inventory(player.get("inventory", "[]"))
        cash_base = updates.get("cash", player.get("cash", 0))
        catalog = config_loader.get_all_items()
        capacity = player.get("capacity", 10)
        for entry in item_entries:
            # โอกาสดรอปรายชิ้น (ไม่ระบุ = ได้แน่นอน) — ใช้กับของแรร์เช่นอาร์ติแฟกต์
            if "chance" in entry and rng.randint(1, 100) > entry["chance"]:
                continue
            # id เดี่ยว หรือสุ่มจาก id_pool (เช่น ดรอปวัสดุคราฟสุ่มชนิด)
            item_id = str(rng.choice(entry["id_pool"])) if "id_pool" in entry else str(entry["id"])
            qty = _roll_amount(entry.get("qty", 1), rng)
            item_cfg = catalog.get(item_id, {})
            name = item_cfg.get("name", f"ไอเทม #{item_id}")
            added = 0
            while added < qty and (capacity == 0 or len(inv) < capacity):
                inv.append(item_id)
                added += 1
            overflow = qty - added
            if added:
                lines.append(f"🎁 ได้รับ `{name}` ×{added}")
            if overflow:
                # กระเป๋าเต็ม → แปลงส่วนเกินเป็นทองตามราคาขาย (ตามที่ตกลง)
                gold = overflow * int(item_cfg.get("sell", 0))
                cash_base += gold
                lines.append(f"⚠️ กระเป๋าเต็ม! `{name}` ×{overflow} ถูกแปลงเป็นเงิน `{gold:,}` ทองแทน")
        updates["inventory"] = inv
        updates["cash"] = cash_base

    if "heal" in outcome:
        max_hp = player.get("max_hp", 100)
        if outcome["heal"] == "full":
            new_hp = max_hp
        else:
            new_hp = min(max_hp, player.get("hp", 100) + _roll_amount(outcome["heal"], rng))
        updates["hp"] = new_hp
        lines.append(f"💖 ฟื้นฟูพลังชีวิต → `{new_hp}/{max_hp}`")

    if "damage" in outcome:
        dmg = _roll_amount(outcome["damage"], rng)
        # 🥾 รองเท้าวายุ: ดาเมจการร่วง/ถูกดีดข้ามทวีปลดตามตัวคูณถาวร
        if "force_continent" in outcome:
            fall_mult = game_modifiers.status_fall_damage_mult(statuses)
            if fall_mult < 1.0:
                dmg = max(1, round(dmg * fall_mult))
                lines.append("🥾 **รองเท้าขนนกวายุพยุงร่าง** — แรงกระแทกเบาลงมาก!")
        # 🪶 ขนนก: การร่วง/ถูกดีดข้ามทวีปเหลือดาเมจขั้นต่ำ รอดเสมอ (ใช้แล้วหมดไป)
        if "force_continent" in outcome and game_modifiers.has_status_flag(statuses, "fall_guard"):
            dmg = min(dmg, 5)
            statuses = {k: v for k, v in statuses.items()
                        if not game_modifiers.STATUS_EFFECTS[k].get("fall_guard")}
            status_changed = True
            lines.append("🪶 **ม้วนคาถาขนนกทำงาน!** ร่างคุณลอยละลิ่วลงพื้นอย่างแผ่วเบา (ขนนกสลายไป)")
        base_hp = updates.get("hp", player.get("hp", 100))
        new_hp = max(0, base_hp - dmg)
        updates["hp"] = new_hp
        lines.append(f"💥 บาดเจ็บ `-{dmg}` HP (เหลือ `{new_hp}`)")
        if new_hp <= 0:
            died = True
            updates["current_state"] = "dead"
            lines.append("💀 **คุณหมดสติจากเหตุการณ์นี้!**")

    if "apply_status" in outcome:
        entries = outcome["apply_status"] if isinstance(outcome["apply_status"], list) else [outcome["apply_status"]]
        for entry in entries:
            statuses = game_modifiers.apply_status(statuses, entry["key"], entry.get("turns"))
            label = game_modifiers.STATUS_EFFECTS.get(entry["key"], {}).get("label", entry["key"])
            lines.append(f"🧬 ติดสถานะ {label}!")
        status_changed = True
    cleansable = [k for k in statuses if not game_modifiers.STATUS_EFFECTS[k].get("artifact")]
    if outcome.get("cleanse_all") and cleansable:
        names = " ".join(game_modifiers.STATUS_EFFECTS[k]["label"] for k in cleansable)
        lines.append(f"✨ สถานะทั้งหมดถูกชำระล้าง: {names}")
        statuses = {k: v for k, v in statuses.items() if k not in cleansable}
        status_changed = True
    if outcome.get("cleanse_random") and cleansable:
        removed = rng.choice(cleansable)
        statuses = {k: v for k, v in statuses.items() if k != removed}
        lines.append(f"✨ {game_modifiers.STATUS_EFFECTS[removed]['label']} ถูกชำระล้างออกไป")
        status_changed = True
    if status_changed:
        updates["status_effects"] = statuses

    if "force_continent" in outcome:
        dest = outcome["force_continent"]
        if dest in game_modifiers.CONTINENTS:
            updates["continent"] = dest
            updates["last_event"] = "none"
            lines.append(f"🗺️ คุณถูกส่งตัวไปยัง {game_modifiers.CONTINENTS[dest]['label']}!")

    if not died:
        updates.setdefault("current_state", "idle")
    if updates:
        player_model.update_player_fields(user_id, updates)

    if "exp" in outcome and not died:
        exp_gain = _roll_amount(outcome["exp"], rng)
        player_model.add_exp(user_id, exp_gain)
        lines.append(f"✨ ได้รับ EXP `{exp_gain}`")

    return lines, died


def resolve_instant_special(event, rng=None):
    """เลือก outcome จาก pool ถ่วงน้ำหนักของอีเวนต์แบบ instant"""
    rng = rng or random
    outcomes = event.get("outcomes", [])
    if not outcomes:
        return {}
    weights = [o.get("weight", 1) for o in outcomes]
    return rng.choices(outcomes, weights=weights, k=1)[0]


# ── การเกิดมอนสเตอร์: ข้อมูลแรงค์/เรทเกิด (ย้ายมาจาก game_views เฟส 5.6) ──

# เรทเกิดมอนรายแรงค์ตามช่วงเลเวล (ค่าเดิมในโค้ด — ใช้เมื่อ Panel ไม่ได้ตั้ง)
DEFAULT_SPAWN_WEIGHTS = {
    100: [10, 30, 20, 25, 15],
    90:  [30, 20, 20, 20, 10],
    50:  [50, 20, 20, 8, 2],
    20:  [70, 20, 5, 3, 2],
    10:  [80, 10, 5, 3, 2],
    0:   [95, 2, 1, 1, 1],
}


def spawn_weights_for(player_level, rank_keys):
    """น้ำหนักสุ่มแรงค์มอนตามเลเวลผู้เล่น — ตั้งได้ที่ Panel (ตั้งไม่ครบ/เพี้ยน = ค่าเดิม)

    คอนฟิกเป็น {"ช่วงเลเวลขั้นต่ำ": {"Common": 50, ...}} — เลือกช่วงที่สูงสุดที่ไม่เกินเลเวล
    """
    table = config_loader.get_balance("spawn_weights", {}) or {}
    if not isinstance(table, dict):
        table = {}                 # คอนฟิกพังทั้งก้อน (สตริง/ลิสต์) = ใช้ตารางเดิม
    tiers = {}
    for key, row in table.items():
        try:
            tiers[int(key)] = row
        except (TypeError, ValueError):
            continue
    if not tiers:
        tiers = DEFAULT_SPAWN_WEIGHTS
    threshold = max((lv for lv in tiers if player_level >= lv), default=0)
    row = tiers.get(threshold, DEFAULT_SPAWN_WEIGHTS[0])
    try:
        if isinstance(row, dict):
            weights = [max(0, int(row.get(rank, 0))) for rank in rank_keys]
        else:
            weights = [max(0, int(w)) for w in row]
        if len(weights) == len(rank_keys) and sum(weights) > 0:
            return weights
    except (TypeError, ValueError):
        pass
    # ค่าใน Panel ใช้ไม่ได้ = ตกกลับตารางเดิม ห้ามปล่อยให้น้ำหนักเป็นศูนย์ทั้งแถว (random.choices จะพัง)
    fallback = max((lv for lv in DEFAULT_SPAWN_WEIGHTS if player_level >= lv), default=0)
    return list(DEFAULT_SPAWN_WEIGHTS[fallback])


# โครงสร้างข้อมูลระดับความโหดของมอนสเตอร์
MONSTER_RANKS = {
    "Common":      {"name": "🟢 มอนสเตอร์ทั่วไป (Common)",      "dice_count": 1, "hp_range": (40, 100),   "flee_chance": 85,  "gold_mult": 2,   "exp_reward": 25},
    "Mini-Boss":   {"name": "🟡 มินิบอส (Mini-Boss)",          "dice_count": 2, "hp_range": (100, 500),  "flee_chance": 60,  "gold_mult": 5,  "exp_reward": 50},
    "Main-Boss":   {"name": "🔴 บอสหลัก (Main-Boss)",          "dice_count": 3, "hp_range": (500, 1000), "flee_chance": 30,  "gold_mult": 10,  "exp_reward": 250},
    "Secret":      {"name": "🟣 มอนสเตอร์ลับ (Secret)",          "dice_count": 2, "hp_range": (100, 1000), "flee_chance": 50,  "gold_mult": 15,  "exp_reward": 250},
    "Unbeatable":  {"name": "💀 ไร้พ่าย (Unbeatable)",         "dice_count": 5, "hp_range": (1000, 2000), "flee_chance": 5,   "gold_mult": 1000, "exp_reward": 1000}
}



def _rank_stats(rank_key):
    """สเปกมอนสเตอร์รายแรงค์ — ค่าในโค้ดเป็นพื้นฐาน ทับด้วยค่าจาก Panel (monster_ranks)"""
    stats = dict(MONSTER_RANKS[rank_key])
    override = config_loader.get_monster_rank(rank_key)
    if override:
        for key in ("dice_count", "flee_chance", "gold_mult", "exp_reward"):
            if key in override:
                stats[key] = override[key]
        if "hp_min" in override and "hp_max" in override:
            stats["hp_range"] = (int(override["hp_min"]), int(override["hp_max"]))
    return stats


def _random_enemy_champion(member_roles, enemy_faction):
    """สุ่มชื่อผู้เล่นจริงฝ่ายตรงข้ามจากเซิร์ฟมาเป็นแชมเปี้ยน — หาไม่ได้ (ไม่มีคนถือยศ/intent ปิด) = ชื่อกลาง"""
    try:
        guild = member_roles[0].guild
        keywords = game_modifiers.DEMON_RACES if enemy_faction == "demon" else game_modifiers.HUMAN_RACES
        candidates = [m.display_name for m in guild.members
                      if not m.bot and any(k in r.name for r in m.roles for k in keywords)]
        if candidates:
            return random.choice(candidates)
    except Exception:
        pass
    return random.choice(["นักรบนิรนาม", "อัศวินไร้นาม", "เงามรณะปริศนา"])


def spawn_monster(user_id, member_roles=(), rng=random):
    """เกิดมอนสเตอร์หนึ่งตัว (เว็บเกม เฟส 5.6) — ยกมาจาก MonsterEventView.__init__ ทั้งชุด

    ลำดับมีผลกับผลลัพธ์ ห้ามสลับ:
      แรงค์ (ใบเรียกบอสล็อก 100%) > HP ฐาน > ตัวคูณ HP ทวีป/ธีม > ชื่อธีม
      > ธาตุ (ยาพลิกธาตุมาก่อนสุ่ม) > ตัวคูณ HP ธาตุดิน > แชมเปี้ยนสงครามฝ่าย > Infusion
      > tick สถานะแบบต่อไฟต์

    คืน dict ที่เซฟลง DB ได้ตรง ๆ (ไม่มีอ็อบเจ็กต์ discord) เพื่อให้เว็บสู้ข้ามรีเฟรชได้
    """
    from bot import identity as _identity
    player = player_model.get_player(user_id) or {}
    mods = game_modifiers.get_active_modifiers(player)
    statuses = game_modifiers.parse_statuses(player)      # สแนปช็อตของไฟต์นี้ ไม่เปลี่ยนกลางคัน
    rank_keys = list(MONSTER_RANKS.keys())
    last_evt = player.get("last_event", "none")

    # ใบเรียกบอสล็อกแรงค์ 100% — ตัวคูณจากทวีป/ธีมไม่มีผลกับของที่ถูกล็อก
    summon = {"mini_summon": [0, 100, 0, 0, 0], "main_summon": [0, 0, 100, 0, 0],
              "unbeatable_summon": [0, 0, 0, 0, 100]}.get(last_evt)
    if summon:
        weights = summon
        player_model.update_player_field(user_id, "last_event", "monster")
    else:
        weights = spawn_weights_for(player.get("level", 0), rank_keys)
        rank_mult = mods.get("rank_weight_mult") or {}
        if rank_mult:
            weights = [w * rank_mult.get(r, 1.0) for w, r in zip(weights, rank_keys)]

    rank = rng.choices(rank_keys, weights=weights, k=1)[0]
    stats = _rank_stats(rank)
    hp = rng.randint(stats["hp_range"][0], stats["hp_range"][1])
    hp = max(1, round(hp * mods["monster_hp_mult"]))       # ตัวคูณทวีป/ธีม (ครั้งเดียวตอนเกิด)

    themed = game_modifiers.pick_monster_name(mods, rank)
    if themed:
        stats["name"] = themed

    # 🧪 ยาพลิกธาตุบังคับให้เกิดเป็นธาตุที่เผ่าผู้เล่นข่ม — ไม่มีก็สุ่มตามเรทของทวีป/ธีม
    role_names = _identity.effective_role_names(member_roles, player)
    element = game_modifiers.forced_weak_element(
        statuses, game_modifiers.resolve_player_elements(role_names))
    if element is None:
        element = game_modifiers.roll_element(mods)
    edata = game_modifiers.get_element_data(mods, element)
    hp = max(1, round(hp * edata.get("hp_mult", 1.0)))     # 🪨 ธาตุดิน: เลือดหนา
    stats["name"] = f"{edata['label']} · {stats['name']}"

    # ⚔️ ธีมสงครามฝ่าย: มีลุ้นเจอแชมเปี้ยนฝ่ายตรงข้ามแทนมอนปกติ (เฉพาะคนมีฝ่าย)
    faction_side = None
    fw = mods.get("faction_war")
    if fw:
        mine = game_modifiers.resolve_player_faction(role_names)
        if mine and rng.randint(1, 100) <= fw.get("chance", 25):
            enemy = "demon" if mine == "human" else "human"
            fdata = game_modifiers.FACTIONS[enemy]
            element = fdata["element"]                     # ธาตุประจำฝ่ายทับธาตุที่สุ่มไว้
            edata = game_modifiers.get_element_data(mods, element)
            champ = _random_enemy_champion(member_roles, enemy)
            stats["name"] = f"{edata['label']} · ⚔️ {champ} {fdata['champion_title']}"
            faction_side = mine

    # ☄️ Infusion: ตีแรงขึ้นแต่ดรอปของดีขึ้น
    inf = mods.get("infusion")
    infused = bool(inf and rng.randint(1, 100) <= inf.get("chance", 0))
    if infused:
        stats["name"] = f"{inf.get('badge', '☄️')} {stats['name']}"

    # tick สถานะแบบ "ต่อไฟต์" — ที่หมดอายุตรงนี้ยังคุ้มครองจนจบไฟต์ (fight_grace)
    remaining, expired = game_modifiers.tick_statuses(statuses, "fight")
    if remaining != statuses:
        player_model.update_player_field(user_id, "status_effects", remaining)

    return {"rank": rank, "stats": stats, "hp": hp, "hp_max": hp, "element": element,
            "statuses": statuses, "fight_grace": list(expired), "infused": infused,
            "faction_side": faction_side, "turn": 1, "buffs": {}}
