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


# ⏩ เดินเร็ว: เหตุการณ์ที่ "หยุดขบวน" — นอกจากนี้เดินผ่านไปเลย ไม่ต้องกดอะไร
# แลกกัน: ได้ระยะทางเร็ว แต่ไม่เจอหีบ/NPC/อีเวนต์พิเศษ (เก็บของต้องเดินทีละก้าว)
FAST_WALK_STOPS = ("monster", "dungeon", "mugging", "bank_robbery",
                   "village", "trap", "travel")


# ก้าวที่ "ไอเทมเป็นคนสั่ง" — ต้องหยุดเสมอ ไม่งั้นของที่เพิ่งใช้ไปถูกกินฟรี
# (เช่นสแกนกล่องสมบัติแล้วเดินเร็วผ่านหีบไปเลย = เสียใบสแกนเปล่า)
FAST_WALK_FORCED = ("warp_village", "scan_box", "treasure_trap", "revive", "warp_dungeon")


def fast_walk_stops_here(event, last_evt=None):
    """โหมดเดินเร็วต้องหยุดที่ก้าวนี้ไหม — ตัวเดียวกันทั้งดิสและเว็บ"""
    if last_evt and (last_evt in FAST_WALK_FORCED or last_evt in SUMMON_EVENTS):
        return True
    return event in FAST_WALK_STOPS


def calm_bonus(user_id, player=None):
    """🧘 ก้าวที่ไม่มีอะไรเกิดขึ้น = ได้พักหายใจ คืนเม็ดคริสตัล 1 เม็ด

    คืน (ข้อความเสริม, เม็ดที่เหลือ) — ข้อความว่างแปลว่าเต็มอยู่แล้ว ไม่ได้อะไรเพิ่ม
    """
    from bot import mana as _mana
    player = player or player_model.get_player(user_id) or {}
    amount = int(config_loader.get_balance("mana.calm_gain", 1) or 0)
    full = _mana.max_mana(player.get("level", 1))
    cur = _mana.get(user_id, player)
    if amount <= 0 or cur >= full:
        return "", cur
    left = _mana.restore(user_id, amount, player)
    return (f"💎 พักหายใจริมทาง — เม็ดคริสตัลคืนมา `+{left - cur}` (`{left}/{full}`)", left)


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


def roll_player_die(rng=random, skill_used=None):
    """เต๋าฝั่งผู้เล่น (ปรับ 2026-08-14) — ตีปกติกับออกท่าใช้กติกาคนละแบบ

    โจมตีปกติ = มือที่ชำนาญแล้ว: 90% ตกช่วงบน 12-19 อีก 10% พลาดร่วงลงมา 1-11
                แต่ "ไม่มีทางทอยได้ 20 เอง" — แต้มสูงสุดเป็นของสกิลเท่านั้น
    ใช้สกิล    = เสี่ยงกว่า: ทอยเต็มช่วง 1-20 เฉลี่ยต่ำกว่าตีปกติ แต่แตะ 20 ได้
                (แลกกับดาเมจที่แรงกว่าเสมอ ดูตัวคูณใน fight_turn)

    ทุกตัวเลขตั้งได้ที่ Panel — ตั้งเพี้ยนก็ตกกลับค่าในโค้ด ไม่พังเกม
    """
    if skill_used:
        return rng.randint(1, int(config_loader.get_balance("dice.skill_max", 20)))
    try:
        lo = int(config_loader.get_balance("dice.normal_min", 12))
        hi = int(config_loader.get_balance("dice.normal_max", 19))
        miss_hi = int(config_loader.get_balance("dice.normal_miss_max", 11))
        hit_pct = float(config_loader.get_balance("dice.normal_hit_pct", 90))
    except (TypeError, ValueError):
        lo, hi, miss_hi, hit_pct = 12, 19, 11, 90.0
    if lo > hi:
        lo, hi = hi, lo
    if rng.random() * 100 < hit_pct:
        return rng.randint(lo, hi)
    return rng.randint(1, max(1, min(miss_hi, lo - 1)))


def player_dice_count(player):
    """🎲 ผู้เล่นทอยกี่ลูก (2026-08-14) — เดิมทอยลูกเดียวตายตัวทุกคน

    ฐาน 1 ลูก + 1 ลูกทุก 25 เลเวล + ลูกที่ได้จากสัตว์เลี้ยงที่พาไปด้วย
    คืน (รวมทั้งหมด, จากเลเวล, จากสัตว์เลี้ยง) — ตั้งค่าได้ที่ Panel ทุกตัว
    """
    from bot import pets as _pets
    try:
        per = int(config_loader.get_balance("dice.level_per_die", 25))
        cap = int(config_loader.get_balance("dice.max_dice", 8))
    except (TypeError, ValueError):
        per, cap = 25, 8
    lvl_dice = (int(player.get("level", 1) or 1) // per) if per > 0 else 0
    pet_dice = int(_pets.roll_bonus(player) or 0)

    # ชนเพดานแล้วตัด "เต๋าสัตว์เลี้ยง" ก่อนเสมอ — เต๋าที่ปั้นมาเองจากเลเวลต้องไม่โดนกิน
    own = 1 + lvl_dice
    if own >= cap:
        return max(1, cap), lvl_dice, 0
    pet_dice = min(pet_dice, cap - own)
    return own + pet_dice, lvl_dice, pet_dice


def roll_combat(user_id, player, statuses, element_data, m_stats, player_elements,
                rng=random, skill_used=None):
    """ทอยเต๋าหนึ่งเทิร์น — คืนแต้มผู้เล่น/มอน พร้อม "ที่มาของแต้ม" ไว้โชว์บนจอ

    ลำดับยกมาจาก process_turn เดิมทั้งหมด (ลำดับมีผลกับผลลัพธ์ ห้ามสลับ):
      ทอยพื้นฐาน → ถุงเต๋าเทพี/สถานะถ่วง → passive ลม → สัตว์เลี้ยง
      → เต๋าถ่วงน้ำหนัก → รากพันธนาการ → โบนัสเต๋ามอนจากธาตุ
      → เต๋าหลุดมือ → เต๋าถูกผนึก → โบนัสเต๋ามอนจากสถานะ

    คืน dict: player_roll, monster_roll, player_parts, monster_parts, log, statuses
    (statuses อาจเปลี่ยนเมื่อโคลเวอร์ถูกใช้กันราก)
    """
    dice_n = m_stats.get("dice_count", 1)
    my_dice, lvl_dice, pet_dice = player_dice_count(player)
    # เต๋าของตัวเอง (ฐาน + จากเลเวล) ทอยเต็มช่วงปกติ
    # ส่วนเต๋าสัตว์เลี้ยงเป็นลูกเล็ก 1-6 กันแต้มเฟ้อจนล้นเกม (ตั้งได้ที่ Panel)
    own_dice = max(1, my_dice - pet_dice)
    pet_die_max = int(config_loader.get_balance("dice.pet_die_max", 6) or 6)
    player_roll = sum(roll_player_die(rng, skill_used) for _ in range(own_dice))
    pet_points = sum(rng.randint(1, pet_die_max) for _ in range(pet_dice))
    player_roll += pet_points
    monster_roll = sum(rng.randint(1, 20) for _ in range(dice_n))
    parts = [f"`{player_roll - pet_points}` พื้นฐาน"
             + (f" ({own_dice} เต๋า)" if own_dice > 1 else "")
             + ("" if skill_used else " ตีปกติ")]
    mon_parts = [f"`{monster_roll}` พื้นฐาน" + (f" ({dice_n} เต๋า)" if dice_n > 1 else "")]
    log = ""
    if my_dice > 1:
        log += (f"🎲 **คุณทอย {my_dice} ลูกรวมกัน** — ของตัวเอง {own_dice} ลูก"
                + (f" + สัตว์เลี้ยง {pet_dice} ลูก (ลูกละ 1-{pet_die_max})" if pet_dice else "")
                + "\n")

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

    # 🐾 สัตว์เลี้ยง: เพิ่ม "จำนวนลูก" แบบลูกเล็ก 1-6 (ดู player_dice_count)
    if pet_dice:
        parts.append(f"🐾+{pet_points} ({pet_dice} ลูก)")

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

    # 🔮 ปริซึมมานา (อาร์ติแฟกต์): คืนเม็ดคริสตัลทุกก้าวที่เดิน
    regen = max((game_modifiers.STATUS_EFFECTS[k].get("mana_regen_per_step", 0)
                 for k in statuses if k in game_modifiers.STATUS_EFFECTS), default=0)
    if regen:
        from bot import mana as _mana
        before = _mana.get(user_id, player)
        after = _mana.restore(user_id, regen, player)
        if after > before:
            notes.append(f"🔮 ปริซึมมานาเรืองแสง — คืนเม็ดคริสตัล `+{after - before}` "
                         f"({_mana.bar(after, _mana.max_mana(player.get('level', 1)))})")

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
    from bot import mana as _mana
    crystals = _mana.refill(user_id)      # 💎 นอนพักที่เมือง = เม็ดคริสตัลเต็ม
    return {"text": f"💤 คุณนอนพักผ่อนอย่างเต็มอิ่ม ฟื้นฟู HP จนเต็ม! *(จ่าย {cost:,} ทอง)*\n"
                    f"💎 เม็ดคริสตัลเต็มอีกครั้ง — {_mana.bar(crystals, crystals)}",
            "hp": full_hp, "cost": cost, "mana": crystals}


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
        gold = int(rng.randint(50, 150) * float(config_loader.get_balance("reward.gold_mult", 1.0)))
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


def npc_ambush(user_id, rng=random):
    """🎭 มอนปลอมตัวซุ่มตีก่อนที่จะทันระวัง — คืน {text, died, damage, start_fight}

    ตรรกะกลาง: ทั้งปุ่มในดิสและปุ่มบนเว็บเรียกตัวนี้ ห้ามคิดดาเมจกันเอง
    """
    dmg = rng.randint(10, 20)
    player = player_model.get_player(user_id) or {}
    new_hp = max(0, int(player.get("hp", 100) or 0) - dmg)
    if new_hp <= 0:
        player_model.update_player_fields(user_id, {"hp": 0, "current_state": "dead"})
        return {"text": f"🎭 **'NPC' ฉีกคราบออก — มันคือมอนสเตอร์ปลอมตัวมา!** "
                        f"จู่โจมจากระยะประชิด `-{dmg}` HP... คุณหมดสติ!",
                "died": True, "damage": dmg, "start_fight": False}
    player_model.update_player_fields(user_id, {"hp": new_hp, "current_state": "fighting"})
    return {"text": f"🎭 **'NPC' ฉีกคราบออก — มันคือมอนสเตอร์ปลอมตัวมา!**\n"
                    f"💥 โดนจู่โจมเปิดฉาก `-{dmg}` HP (เหลือ {new_hp}) — เข้าสู่การต่อสู้ทั้งแบบนั้น!",
            "died": False, "damage": dmg, "start_fight": True}


def npc_inspect(user_id, disguised, fee):
    """🔍 ตรวจตัวตน NPC — แว่นเดี่ยวหน้ากาก/แว่นส่องสัจจะใช้ฟรี ไม่มีก็จ่ายเงิน

    คืน {ok, text, start_fight} — ok=False คือเงินไม่พอ (ยังไม่ได้ตรวจ ไม่หักอะไร)
    """
    fee = int(fee or 0)
    player = player_model.get_player(user_id) or {}
    inv = player_model.load_inventory(player.get("inventory", "[]"))

    if game_modifiers.has_status_flag(game_modifiers.parse_statuses(player), "free_inspect"):
        note = "🎭 แว่นเดี่ยวหน้ากากของคุณเรืองแสง มองทะลุทุกการอำพราง (ฟรี — พลังถาวร)"
    elif "38" in inv:
        inv.remove("38")
        player_model.update_player_field(user_id, "inventory", inv)
        note = "🔍 คุณยกแว่นส่องสัจจะขึ้นส่องทะลุหน้ากาก... (ไม่เสียเงิน — เลนส์แตกสลายหลังใช้)"
    elif int(player.get("cash", 0) or 0) < fee:
        return {"ok": False, "start_fight": False,
                "text": f"❌ เงินสดไม่พอค่าตรวจสอบ (`{fee:,}` ทอง) — "
                        "หรือหาซื้อ 🔍 แว่นส่องสัจจะติดกระเป๋าไว้"}
    else:
        player_model.update_player_field(user_id, "cash", int(player.get("cash", 0)) - fee)
        note = f"🔍 คุณจ่าย `{fee:,}` ทองให้ผู้เชี่ยวชาญส่องหน้ากาก..."

    if disguised:
        player_model.update_player_field(user_id, "current_state", "fighting")
        return {"ok": True, "start_fight": True,
                "text": f"{note}\n🎭 **จับได้! มันคือมอนสเตอร์ปลอมตัวมา!** "
                        "มันจนมุมก่อนได้ลงมือ — คุณเข้าปะทะแบบไม่เสียเปรียบ!"}
    return {"ok": True, "start_fight": False,
            "text": f"{note}\nผลออกมา: **เป็น NPC ตัวจริง!** คุยต่อได้ตามปกติ 🧓"}


def npc_talk(user_id, rng=random):
    """💬 คุยกับ NPC — สุ่มได้ของขวัญ / โดนยัดขาย / ไม่มีอะไร (ยกมาจากปุ่มในดิสทั้งชุด)"""
    player = player_model.get_player(user_id) or {}
    items = config_loader.get_all_items()
    outcome = rng.choice(["gift", "shop", "nothing"])
    _done(user_id, "npc")

    if outcome == "gift":
        gold = int(rng.randint(30, 70) * float(config_loader.get_balance("reward.gold_mult", 1.0)))
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


def _item_value(items, item_id):
    """มูลค่าที่แท้จริงของไอเทม = **ราคาขาย** ไม่ใช่ราคาซื้อ (แก้ 2026-08-14)

    เดิมตีมูลค่าด้วยราคาซื้อ ซึ่งแพงกว่าราคาขายราว 3-10 เท่า
    แลกประตูวาร์ปมิติ (ซื้อ 40,000 / ขาย 4,000) กับ NPC จึงได้ ~36,000
    ทั้งที่ขายที่ร้านได้แค่ 4,000 — คุ้มกว่าขายร้าน 9 เท่า = ยังพิมพ์เงินได้อยู่

    ของที่ไม่ได้ตั้งราคาขายไว้ ประเมินคร่าว ๆ ที่ 1/3 ของราคาซื้อ (เรทร้านค้าปกติ)
    """
    d = items.get(str(item_id), {}) or {}
    sell = int(d.get("sell", 0) or 0)
    return sell if sell > 0 else int(d.get("buy", 0) or 0) // 3


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

    # 🧓 NPC เร่ร่อนไม่มีปัญญาซื้อของระดับสมบัติ — ขอเฉพาะของที่ราคาไม่เกินเพดาน
    # (กันทั้งการฟอกทองคำแท่งเป็นเงินสด และกันผู้เล่นเผลอแลกของล้ำค่าทิ้ง)
    cap = int(config_loader.get_balance("npc.trade_max_item_value", 200_000))
    if cap > 0:
        inv = [i for i in inv if _item_value(items, i) <= cap]
        if not inv:
            _done(user_id, "npc")
            return None

    requested = rng.sample(inv, rng.randint(1, len(inv)))
    counts = {}
    for i in requested:
        counts[i] = counts.get(i, 0) + 1
    req_text = ", ".join(f"**{items.get(str(i), {}).get('name', '???')}** x{c}" for i, c in counts.items())
    req_value = sum(_item_value(items, i) for i in requested)

    # 💸 เนิฟ 2026-08-14: ของเดิมสุ่ม 0.5-2.0 เท่า = เฉลี่ย 1.25 เท่า
    # ซึ่งแปลว่า "แลกกี่รอบก็กำไร" ถือทองคำแท่งพันล้านแลกทีเดียวได้พันสองร้อยล้าน
    # ตอนนี้เฉลี่ยต่ำกว่า 1 เท่า (เป็นการเสี่ยงดวง ไม่ใช่เครื่องพิมพ์เงิน) + เพดานเงินสดต่อครั้ง
    lo = float(config_loader.get_balance("npc.trade_min_mult", 0.5))
    hi = float(config_loader.get_balance("npc.trade_max_mult", 1.3))
    reward_val = rng.randint(int(req_value * min(lo, hi)), max(1, int(req_value * max(lo, hi))))
    valid = [i for i, d in items.items() if 0 < _item_value(items, i) <= reward_val]
    reward_item = rng.choice(valid) if valid else None
    reward_cash = reward_val - (_item_value(items, reward_item) if reward_item else 0)
    cash_cap = int(config_loader.get_balance("npc.trade_cash_cap", 100_000))
    if cash_cap > 0:
        reward_cash = min(reward_cash, cash_cap)      # กันฟอกของแพงเป็นเงินสดก้อนโต
    reward_cash = max(0, reward_cash)

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


def _resync_statuses(statuses, player, grace=()):
    """ซิงก์สแนปช็อตไฟต์กับ DB สด (บั๊กเฟส D #2-#3):
    - สถานะที่ถูก "รักษากลางไฟต์" (มีดตัดเถา/ครีมว่านเย็น/ชา/สายดิน/เทียน ฯลฯ) หลุดจากไฟต์ทันที
    - บัฟที่ "เพิ่งกดใช้กลางไฟต์" (ชิป EMP/น้ำมนต์/เต๋าถ่วง ฯลฯ) มีผลทันที
    - ยกเว้น grace: สถานะที่หมดอายุด้วย tick ต้นไฟต์ ยังคุ้มครองจนจบไฟต์ตามดีไซน์เดิม
    """
    fresh = game_modifiers.parse_statuses(player)
    grace = set(grace or ())
    synced = {k: v for k, v in statuses.items() if k in fresh or k in grace}
    for k, v in fresh.items():
        synced.setdefault(k, v)
    return synced


def _holy_aura_chance(p_lvl):
    cfg = config_loader.get_skill_config("Cleric", "holy_aura")
    return cfg["chance_base"] + (p_lvl * cfg["chance_lvl_scale"])

# ตารางน้ำหนักเหตุการณ์ย้ายไป bot/adventure_core.py แล้ว (ใช้ร่วมกับเว็บ)
# re-export ไว้ให้โค้ด/เทสเดิมที่อ้างจากไฟล์นี้ยังใช้ได้
from bot.adventure_core import (EVENT_WEIGHTS, EVENT_LIST, event_weights,  # noqa: E402,F401
                                DEFAULT_SPAWN_WEIGHTS, MONSTER_RANKS,
                                spawn_weights_for, _rank_stats,
                                _random_enemy_champion)


def fight_turn(user_id, fight, member_roles=(), skill_used=None, rng=random):
    """คำนวณหนึ่งเทิร์นของการต่อสู้ (เว็บเกม เฟส 5.6) — ยกมาจาก MonsterEventView.process_turn

    ไม่มีอะไรผูกกับ discord เลย ผู้เรียกเอาผลไปวาดเอง (ดิสทำ embed / เว็บส่ง JSON)

    outcome:
      monster_fled  มอนธาตุแสงเผ่นหนี จบไฟต์ ไม่ได้รางวัล
      player_fled   Evasion สำเร็จ หนีออกมาได้
      win           มอนเลือดหมด (ผู้เรียกไปจ่ายรางวัลต่อ)
      lose          ผู้เล่นเลือดหมด
      continue      สู้ต่อเทิร์นหน้า
    """
    from bot import identity as _identity
    player = player_model.get_player(user_id)
    if not player:
        return {"outcome": "no_player", "text": "❌ ไม่พบข้อมูลตัวละครของคุณในระบบ!"}

    mods = game_modifiers.get_active_modifiers(player)
    m_stats = fight["stats"]
    monster_rank = fight["rank"]
    monster_hp = fight["hp"]
    monster_hp_max = fight.get("hp_max", monster_hp)
    element = fight.get("element")
    element_data = game_modifiers.get_element_data(mods, element)
    active_buffs = fight.get("buffs") or {}
    turn_count = fight.get("turn", 1)
    infused = fight.get("infused", False)
    faction_side = fight.get("faction_side")
    role_names = _identity.effective_role_names(member_roles, player)
    player_elements = game_modifiers.resolve_player_elements(role_names)

    # ซิงก์สถานะกับ DB สดก่อนคำนวณ — ไอเทมรักษา/บัฟที่กดใช้ระหว่างรอเทิร์นมีผลทันที
    statuses = _resync_statuses(fight["statuses"], player, fight.get("fight_grace"))

    # 💎 มานา: เม็ดหมดแล้วใช้สกิลไม่ได้ (โจมตีปกติ/หนี ยังทำได้ตามเดิม)
    from bot import mana as _mana
    if skill_used and not _mana.can_use_skill(user_id, player):
        st = _mana.status_line(user_id, player)
        return {"outcome": "no_mana", "fight": fight, "mana": st,
                "text": (f"💎 **เม็ดคริสตัลหมดแล้ววันนี้!** ({st['bar']}) "
                         f"ใช้สกิลไม่ได้จนกว่าจะข้ามวัน — โจมตีปกติหรือหนียังทำได้")}

    p_lvl = player.get("level", 1)

    # ✨ ธาตุแสง: โอกาสมอนสเตอร์เผ่นหนีต้นเทิร์น (แบบ Metal Slime) — จบไฟต์ ไม่ได้รางวัล
    # 🪤 กับดักมอนสเตอร์ล็อกไว้ = หนีไม่ได้เลย (จุดขายหลักของกับดัก — ล่ามอนแสงได้จริง)
    monster_flee = element_data.get("monster_flee_chance", 0)
    if game_modifiers.has_status_flag(statuses, "block_monster_flee"):
        monster_flee = 0
    if monster_flee and rng.randint(1, 100) <= monster_flee:
        player_model.update_player_field(user_id, "current_state", "idle")
        return {"outcome": "monster_fled", "skill_log": "", "combat_log": "",
                "text": f"💨✨ **{m_stats.get('name', 'มอนสเตอร์')} ระเบิดแสงวาบตาแล้วเผ่นหนีหายไป!** "
                        f"คุณคว้าอะไรไม่ทันเลย...",
                "damage_to_monster": 0, "damage_to_player": 0,
                        "player_roll": 0, "monster_roll": 0,
                        "player_parts": [], "monster_parts": [],
                        "damage_line": "", "db_updates": {},
                        "fight": fight, "monster_hp": monster_hp, "player_hp": player.get("hp", 0)}

    # 1. 🛡️ ดึงข้อมูลอุปกรณ์
    w_id = player.get("weapon", "Wooden_Weapon")
    a_id = player.get("armor", "None")
    w_stat = config_loader.get_weapon_stats(w_id) or config_loader.get_weapon_stats("Wooden_Weapon") or {"atk": 1}
    a_stat = config_loader.get_armor_stats(a_id) or config_loader.get_armor_stats("None") or {"hp": 0}
    
    # 2. 🛡️ คำนวณพลังโจมตี (ถ้าความทนทานเป็น 0 พลังโจมตีหาย)
    curr_atk = w_stat.get("atk", 0) if player.get("weapon_dur", 0) > 0 else 0
    
    # ⚡ ไฟฟ้าสถิต: สกิลอาจลัดวงจรก่อนออกท่า (กลายเป็นโจมตีธรรมดา + ช็อกตัวเอง)
    shock_note = ""
    if skill_used:
        shock_failed, shock_dmg = game_modifiers.status_skill_shock(statuses)
        if shock_failed:
            skill_used = None
            player["hp"] = max(0, player.get("hp", 100) - shock_dmg)
            shock_note = f"⚡ **สกิลลัดวงจร!** กระแสไฟฟ้าสถิตช็อกร่างคุณ `-{shock_dmg}` HP (เหลือ {player['hp']}) — ท่ากลายเป็นการโจมตีธรรมดา!\n"

    # 3. 🛠️ กำหนดค่าความทนทานเริ่มต้นเป็น 0 เพื่อป้องกันบั๊ก
    durability_lost_w = 3 if skill_used else 1
    damage_to_armor = 0 
    
    skill_log = ""
    if shock_note:
        skill_log += shock_note
    combat_log = ""
    db_updates = {}
    # เดิมสองตัวนี้ประกาศเฉพาะในสาขาของตัวเอง เพราะ View ใช้ทีละสาขา
    # ตอนนี้ต้องคืนออกไปทั้งคู่ทุกเทิร์น (หน้าจอเว็บวาดทั้งสองฝั่ง) จึงต้องมีค่าตั้งต้น
    damage_to_monster = 0
    damage_to_player = 0
    healed_amount = 0
    damage_line = ""

    enrage_bonus = 0
    # 🌑 ธาตุมืด: เข้าสถานะคลั่งตั้งแต่เทิร์นแรก (ระบบคลั่งปกติเริ่มหลังเทิร์น 3)
    enraged_turns = turn_count if element_data.get("pre_enraged") else turn_count - 3
    if enraged_turns > 0:
        rank_danger = {"Common": 2, "Mini-Boss": 5, "Main-Boss": 10, "Secret": 8, "Unbeatable": 25}
        enrage_bonus = enraged_turns * rank_danger.get(monster_rank, 2)
        skill_log += f"😡 **{m_stats.get('name', 'บอส')} กำลังคลั่ง!** บอสสะสมความโกรธเพิ่มพลังโจมตีเด็ดขาด `+{enrage_bonus}` หน่วยในเทิร์นนี้!\n"

    # 🎲 ทอยเต๋าทั้งเทิร์น — ตรรกะอยู่ใน adventure_core (ใช้ร่วมกับหน้าไฟต์บนเว็บ)
    _roll = roll_combat(
        user_id, player, statuses, element_data,
        m_stats, player_elements, rng, skill_used)
    player_roll = _roll["player_roll"]
    monster_roll = _roll["monster_roll"]
    roll_parts = _roll["player_parts"]      # 🎲 B3: ที่มาของแต้ม ไว้โชว์ในหน้าจอไฟต์
    mon_parts = _roll["monster_parts"]
    statuses = _roll["statuses"]       # โคลเวอร์อาจถูกใช้ไปกันราก
    skill_log += _roll["log"]

    damage_multiplier = 1

    # ─── ⚔️ ระบบคำนวณสกิลช่วงต้นเทิร์น ───
    try:
        if skill_used == "skill_heavy_strike":
            w_cfg = config_loader.get_skill_config("Warrior", "heavy_strike")
            chance = w_cfg["chance_base"] + (p_lvl * w_cfg["chance_lvl_scale"])
            if rng.randint(1, 100) <= chance:
                damage_multiplier = w_cfg["damage_multiplier"]
                # 💥 คริ: เต๋าถึงเกณฑ์ (18+) ตอนใช้สกิล = ตัวคูณพุ่งเป็นระดับคริ (config เก่าไม่มี key = ไม่มีคริ)
                crit_min = w_cfg.get("crit_roll_min")
                if crit_min and player_roll >= crit_min:
                    damage_multiplier = w_cfg.get("crit_multiplier", damage_multiplier)
                    skill_log += f"💥 **Heavy Strike ติดคริติคอล!** เต๋า `{player_roll}` เข้าจังหวะมรณะ ดาเมจ ×{damage_multiplier} เท่า!\n"
                else:
                    skill_log += f"✨ **Heavy Strike สำเร็จ!** การโจมตีในเทิร์นนี้จะแรงขึ้น {damage_multiplier} เท่า!\n"
            else:
                skill_log += "💨 **Heavy Strike ล้มเหลว!** ทอยเต๋าพลาดสมาธิหลุด\n"

        elif skill_used == "skill_evasion":
            r_cfg = config_loader.get_skill_config("Rogue", "evasion")
            chance = r_cfg["chance_base"] + (p_lvl * r_cfg["chance_lvl_scale"])
            if rng.randint(1, 100) <= chance:
                player_model.update_player_field(user_id, "current_state", "idle")
                return {"outcome": "player_fled", "skill_log": skill_log, "combat_log": "",
                        "text": f"💨 **Evasion สำเร็จ!** คุณม้วนตัวหนีออกจากสู้กับ "
                                f"**{m_stats.get('name', 'มอนสเตอร์')}** ได้สำเร็จ!",
                        "damage_to_monster": 0, "damage_to_player": 0,
                        "player_roll": 0, "monster_roll": 0,
                        "player_parts": [], "monster_parts": [],
                        "damage_line": "", "db_updates": {},
                        "fight": fight, "monster_hp": monster_hp, "player_hp": player.get("hp", 0)}
            else:
                skill_log += "⚠️ **Evasion ล้มเหลว!** มอนสเตอร์ดักทางเท้าไว้ได้\n"

        elif skill_used == "skill_heal":
            c_cfg = config_loader.get_skill_config("Cleric", "heal")
            heal_percent = c_cfg["heal_percent_base"] + (p_lvl * c_cfg["heal_lvl_scale"])
            heal_amount = int(player.get("max_hp", 100) * heal_percent)
            
            if monster_rank in ["Main-Boss", "Unbeatable"]:
                stolen_heal = int(heal_amount * 0.3)
                heal_amount -= stolen_heal
                monster_hp = min(m_stats.get("hp_range", [0,100])[1], monster_hp + stolen_heal)
                skill_log += f"💔 **คำสาปบอสทำงาน!** บอสสูบกลืนแสงฮีลของคุณไป `+{stolen_heal}` HP! "
            
            new_hp = min(player.get("max_hp", 100), player.get("hp", 100) + heal_amount)
            healed_amount = max(0, new_hp - player.get("hp", 100))   # ฟื้นจริง (ชนเพดาน MaxHP แล้ว)
            player["hp"] = new_hp
            skill_log += f"✨ **Heal!** พลังชีวิตของคุณฟื้นฟู `+ {heal_amount}` หน่วย (❤️ HP: {new_hp})\n"

        if skill_used == "skill_shield_bash":
            active_buffs["shield_bash"] = config_loader.get_skill_config("Warrior", "shield_bash")["duration"]
        elif skill_used == "skill_fireball":
            active_buffs["fireball"] = config_loader.get_skill_config("Mage", "fireball")["duration"]
        elif skill_used == "skill_frostbolt":
            f_cfg = config_loader.get_skill_config("Mage", "frostbolt")
            active_buffs["frostbolt"] = f_cfg["duration_base"] + int(p_lvl * f_cfg["duration_lvl_scale"])
        elif skill_used == "skill_holy_aura":
            active_buffs["holy_aura"] = 3
        elif skill_used == "skill_backstab":
            r_b_cfg = config_loader.get_skill_config("Rogue", "backstab")
            if rng.randint(1, 100) <= (r_b_cfg["chance_base"] + (p_lvl * r_b_cfg["chance_lvl_scale"])):
                active_buffs["backstab"] = 1
    except KeyError as e:
        print(f"⚠️ [WARNING] ตั้งค่าสกิลขาดหาย: {e}")

    # 🔥 คิดเอฟเฟกต์เผาไหม้ของ Fireball
    if active_buffs.get("fireball", 0) > 0:
        try:
            m_cfg = config_loader.get_skill_config("Mage", "fireball")
            burn_percent = m_cfg["burn_base"] + (p_lvl * m_cfg["burn_lvl_scale"])
            burn_damage = int(m_stats.get("hp_range", [0,100])[1] * burn_percent)
            monster_hp = max(0, monster_hp - burn_damage)
            combat_log += f"🔥 *เอฟเฟกต์เผาไหม้:* บอสโดนไฟบอลเผาเสีย HP `- {burn_damage}` หน่วย (บอสเหลือ HP: {monster_hp})\n"
            active_buffs["fireball"] -= 1
        except Exception as e: pass

    # 🥾 รองเท้าขนนกวายุ: แพ้เต๋าให้มอนธาตุลม → โอกาสขอทอยใหม่หนึ่งครั้ง
    reroll_chance = game_modifiers.status_reroll_vs(statuses, element)
    if reroll_chance and player_roll < monster_roll and rng.randint(1, 100) <= reroll_chance:
        new_roll = rng.randint(1, 20)
        skill_log += f"🥾 **รองเท้าขนนกวายุพัดหวน!** ขอทอยใหม่: `{player_roll}` ➔ `{new_roll}`\n"
        player_roll = new_roll

    # 🎲 กติกาเต๋าประจำวัน (ธีมเต๋าแห่งเทพี)
    goddess_rule = game_modifiers.get_daily_dice_rule() if mods.get("dice_rules") else None

    # ⚔ คุณทอยได้เต๋าชนะบอส
    if player_roll >= monster_roll:
        # 🥶 สถานะลดแรงโจมตีผู้เล่น (เช่น ชา = ×0.5)
        status_dmg_mult = game_modifiers.status_combat_mult(statuses, "player_dmg_mult")
        goddess_mult = game_modifiers.dice_rule_bonus(goddess_rule, player_roll) if goddess_rule else 1.0
        if goddess_mult > 1.0:
            combat_log += f"🎲 **เทพีโปรดปราน!** เต๋าของคุณเข้ากติกาวันนี้ ดาเมจ ×{goddess_mult:g}!\n"
        # ⚔️ ธาตุผู้เล่นได้เปรียบธาตุมอน (dual-race ซ้อนได้เปรียบ = ×2.0 cap)
        elem_adv_mult = game_modifiers.player_attack_element_mult(player_elements, element)
        if elem_adv_mult > 1.0:
            combat_log += f"⚔️✨ **ธาตุประจำตัวของคุณข่มธาตุศัตรู!** ดาเมจ ×{elem_adv_mult:g}\n"
        # 🔥🌑 Passive ธาตุผู้เล่น: โบนัสดาเมจถาวร (ไฟ ×1.15, มืด ×1.25 — ถือหลายธาตุคูณทบกัน)
        passive_dmg_mult = game_modifiers.player_passive_mult(player_elements, "dmg_mult")
        if passive_dmg_mult > 1.0:
            combat_log += f"🩸 **พลังธาตุประจำตัวเสริมคมอาวุธ** ดาเมจ ×{passive_dmg_mult:g}\n"
        # ⚔️ ออกท่าแล้วทอยชนะ ต้องแรงกว่าตีปกติที่แต้มเท่ากันเสมอ (ปรับ 2026-08-14)
        # ใช้กับทุกสกิลรวมสายกันตัว/บัฟ — เพราะกดแล้วทอยชนะก็ยังฟาดโดนมอนอยู่ดี
        # สกิลสายโจมตี (เช่น Heavy Strike) มีตัวคูณของตัวเองซ้อนทับอีกชั้น
        skill_bonus = float(config_loader.get_balance("skill.damage_bonus_mult", 1.3)) if skill_used else 1.0
        if skill_bonus > 1.0:
            combat_log += f"⚔️💫 **พลังจากการออกท่า** ดาเมจ ×{skill_bonus:g}\n"
        damage_to_monster = int((player_roll + curr_atk) * 5 * damage_multiplier * status_dmg_mult * goddess_mult * elem_adv_mult * passive_dmg_mult * skill_bonus)
        # 💥 B3: สรุปสูตรดาเมจให้ผู้เล่นเห็นว่าคูณอะไรมาบ้าง
        _mults = []
        for _label, _v in (("สกิล", damage_multiplier), ("สถานะ", status_dmg_mult), ("เทพี", goddess_mult),
                           ("⚔️ธาตุข่ม", elem_adv_mult), ("ธาตุติดตัว", passive_dmg_mult)):
            if _v != 1:
                _mults.append(f"{_label} ×{_v:g}")
        damage_line = f"**`{damage_to_monster:,}`** ใส่ศัตรู  ·  ({player_roll} เต๋า +{curr_atk} ดาบ) ×5"
        if _mults:
            damage_line += "  ·  " + "  ·  ".join(_mults)

        # 🌗 คำสาปแต้มคี่/คู่: parity ของเต๋าตรงคำสาป = ผลโจมตีบิดเบี้ยว
        curse_key = game_modifiers.status_curse_for_roll(statuses, player_roll)
        if curse_key:
            curse_cfg = game_modifiers.STATUS_EFFECTS[curse_key]
            if curse_cfg.get("curse_parity") == "odd":
                reflect = max(1, round(damage_to_monster * curse_cfg.get("reflect_pct", 0.2)))
                player["hp"] = max(0, player.get("hp", 100) - reflect)
                combat_log += f"🌑 **คำสาปแต้มคี่ทำงาน!** เต๋าออก `{player_roll}` การโจมตีแป้กสนิท แถมแรงสาปสะท้อน `-{reflect}` HP ใส่ตัวคุณ (เหลือ {player['hp']})\n"
            else:
                monster_hp += damage_to_monster
                combat_log += f"🌕 **คำสาปแต้มคู่ทำงาน!** เต๋าออก `{player_roll}` พลังโจมตีทั้งหมดไหลย้อนไป**ฮีลมอนสเตอร์** `+{damage_to_monster}` HP!\n"
            damage_to_monster = 0

        monster_hp = max(0, monster_hp - damage_to_monster)

        # 💧 Passive ธาตุน้ำของผู้เล่น: ดูดเลือดตามดาเมจที่ตีโดนจริง
        ls_pct = game_modifiers.player_passive_sum(player_elements, "lifesteal")
        if ls_pct and damage_to_monster > 0:
            max_hp = player.get("max_hp", 100)
            healed = min(max_hp, player.get("hp", 100) + max(1, round(damage_to_monster * ls_pct))) - player.get("hp", 100)
            if healed > 0:
                player["hp"] += healed
                combat_log += f"💧 **สายธารชีวิตดูดกลืนพลังศัตรู** `+{healed}` HP (เหลือ {player['hp']})\n"

        if status_dmg_mult < 1.0:
            combat_log += "🥶 ร่างกายชาเย็นจนขยับช้า แรงโจมตีอ่อนลงกว่าปกติ!\n"
        combat_log += f"⚔️ คุณทอยได้ **🎲 {player_roll}/บอส({monster_roll})** (+{curr_atk} ดาบ) สร้างความเสียหายใส่บอส `- {damage_to_monster}` หน่วย\n"
    
    # 👾 บอสทอยได้เต๋าชนะ
    else:
        # ตัวคูณดาเมจมอนสเตอร์จากทวีป/ธีมสัปดาห์ × ธาตุ (🔥 ไฟ = ×1.5) × infusion (☄️ ×2)
        elem_dmg_mult = element_data.get("dmg_mult", 1.0)
        infusion_mult = (mods.get("infusion") or {}).get("dmg_mult", 1.0) if infused else 1.0
        goddess_penalty = game_modifiers.dice_rule_penalty(goddess_rule, player_roll) if goddess_rule else 1.0
        if goddess_penalty > 1.0:
            combat_log += "🎲 **เทพีเบือนหน้าหนี...** เต๋าตกโซนโทษ มอนสเตอร์ตีสวนแรงขึ้น!\n"
        # 🛡️ ธาตุผู้เล่นต้านทาน/แพ้ทางธาตุมอนฝั่งรับ
        elem_def_mult = game_modifiers.player_defense_element_mult(player_elements, element)
        if elem_def_mult < 1.0:
            combat_log += "🛡️ **ธาตุประจำตัวของคุณต้านทานพลังโจมตีนี้!**\n"
        elif elem_def_mult > 1.0:
            combat_log += "☯️ **พลังแสง-มืดปะทะกันรุนแรง!** ดาเมจที่ได้รับหนักขึ้น!\n"
        # 🪨🌑 Passive ธาตุผู้เล่นฝั่งรับ: ดินหนังเหนียว ×0.9, มืดเปราะบาง ×1.1
        passive_def_mult = game_modifiers.player_passive_mult(player_elements, "def_mult")
        if passive_def_mult < 1.0:
            combat_log += "🪨 **ผิวศิลาดูดซับแรงกระแทก!**\n"
        elif passive_def_mult > 1.0:
            combat_log += "🌑 **ร่างที่กระหายเลือดเปราะบางต่อการโจมตี!**\n"
        damage_to_player = round((rng.randint(10, 25) + enrage_bonus) * mods.get("monster_dmg_mult", 1.0) * elem_dmg_mult * infusion_mult * goddess_penalty * elem_def_mult * passive_def_mult)
        if elem_dmg_mult > 1.0:
            combat_log += "🔥 **เพลิงธาตุลุกโหม!** การโจมตีของมอนสเตอร์รุนแรงขึ้นกว่าปกติ!\n"
        if infusion_mult > 1.0:
            combat_log += "☄️ **พลังอุกกาบาตปะทุ!** แรงโจมตีทวีคูณอย่างน่ากลัว!\n"
        
        if player.get("armor_dur", 0) > 0:
            damage_to_armor = max(1, int(damage_to_player / 10))
            reduction = int(damage_to_player * 0.2)
            damage_to_player -= reduction
            combat_log += f"🛡️ เกราะรับดาเมจแทนคุณ `- {reduction}` หน่วย!\n"
        
        try:
            if active_buffs.get("frostbolt", 0) > 0:
                f_reduce = config_loader.get_skill_config("Mage", "frostbolt")["damage_reduce"]
                damage_to_player = int(damage_to_player * (1 - f_reduce))
                combat_log += f"❄️ *น้ำแข็งเกาะ:* บอสติดแช่แข็ง พลังโจมตีลดลง {int(f_reduce*100)}%! (โดนดาเมจเบา ๆ `- {damage_to_player}`)\n"

            elif active_buffs.get("holy_aura", 0) > 0 and rng.randint(1, 100) <= _holy_aura_chance(p_lvl):
                damage_to_player = 0
                combat_log += "✨ *Holy Aura ทำงาน:* ร่างกายส่องแสงบล็อคพลังโจมตีของบอสกลายเป็น 0!\n"

            elif active_buffs.get("backstab", 0) > 0:
                damage_to_player = int(damage_to_player * 0.2)
                rogue_reflect = int(player_roll * 5 * config_loader.get_skill_config("Rogue", "backstab")["damage_reflect_mult"])
                monster_hp = max(0, monster_hp - rogue_reflect)
                combat_log += f"🗡️ *Backstab คุมเชิง:* ดาเมจสวนกลับลดลง 80% (โดนแค่ `- {damage_to_player}`) พร้อมวาร์ปตลบหลังแทงบอสสวนกลับหงายหลังฟาด `- {rogue_reflect}` หน่วย! (บอสเหลือ HP: {monster_hp})\n"

            elif active_buffs.get("shield_bash", 0) > 0:
                s_b_cfg = config_loader.get_skill_config("Warrior", "shield_bash")
                reduction = s_b_cfg["reduction_base"] + (p_lvl * s_b_cfg["reduction_lvl_scale"])
                incoming = damage_to_player
                damage_to_player = int(damage_to_player * (1 - min(0.9, reduction)))
                combat_log += f"🛡️ *Shield Bash บล็อก:* ดาเมจลดลงครอบคลุมเกราะ (โดนแค่ `- {damage_to_player}`)\n"
                # 🛡️⚔️ สวนกลับ: สะท้อนดาเมจตามสัดส่วนของแรงปะทะเดิม (config เก่าไม่มี key = ไม่สะท้อน)
                reflect_pct = s_b_cfg.get("reflect_pct", 0)
                if reflect_pct:
                    reflected = max(1, int(incoming * reflect_pct))
                    monster_hp = max(0, monster_hp - reflected)
                    combat_log += f"🛡️⚔️ *โล่กระแทกสวนกลับ!* แรงปะทะสะท้อนใส่ศัตรู `- {reflected}` หน่วย (บอสเหลือ HP: {monster_hp})\n"
        except Exception: pass

        if damage_to_player > 0:
            damage_line = f"😱 ศัตรูสวนกลับ **`{damage_to_player:,}`** ใส่คุณ (เกราะเสื่อม `{damage_to_armor}`)"
            player["hp"] = max(0, player.get("hp", 100) - damage_to_player)
            combat_log += f"⚔️ คุณทอยได้ **🎲 {player_roll}/บอส({monster_roll})** 💥 บอสโจมตีสวน! เสีย HP `- {damage_to_player}` (เกราะเสื่อมสภาพ `- {damage_to_armor}`)\n"

            # 💍 แหวนหินอัคนี: สะท้อนดาเมจกลับใส่มอนธาตุที่ระบุ (ไฟ)
            reflect_pct = game_modifiers.status_reflect_vs(statuses, element)
            if reflect_pct:
                reflected = max(1, round(damage_to_player * reflect_pct))
                monster_hp = max(0, monster_hp - reflected)
                combat_log += f"💍 **แหวนหินอัคนีลุกโชน!** สะท้อนเพลิง `-{reflected}` กลับใส่ศัตรู (บอสเหลือ HP: {monster_hp})\n"
            # 💧 ธาตุน้ำ: ดูดเลือดจากดาเมจสุทธิที่ตีโดนจริง
            lifesteal = element_data.get("lifesteal", 0)
            if lifesteal:
                healed = max(1, round(damage_to_player * lifesteal))
                monster_hp += healed
                combat_log += f"💧 **ดูดเลือด!** มอนสเตอร์สูบพลังชีวิตจากบาดแผลของคุณ ฟื้น HP `+{healed}` (บอสเหลือ HP: {monster_hp})\n"

            # 🧪 มอนเสกสถานะใส่ผู้เล่นตอนตีโดน — จากธาตุ (element_overrides ได้) หรือระดับทวีป/ธีม
            for on_hit in (element_data.get("on_hit_status"), mods.get("on_hit_status")):
                if not on_hit:
                    continue
                if rng.randint(1, 100) > on_hit.get("chance", 100):
                    continue
                status_key = on_hit.get("key")
                status_cfg = game_modifiers.STATUS_EFFECTS.get(status_key)
                if not status_cfg:
                    continue
                if status_key in statuses and not status_cfg.get("stacking"):
                    continue  # สถานะปกติติดซ้ำระหว่างไฟต์ไม่สแปมข้อความ (แบบสะสมสแตกได้เรื่อยๆ)
                fresh = game_modifiers.parse_statuses(player_model.get_player(user_id))
                fresh = game_modifiers.apply_status(fresh, status_key, on_hit.get("turns"))
                player_model.update_player_field(user_id, "status_effects", fresh)
                statuses = game_modifiers.apply_status(statuses, status_key, on_hit.get("turns"))
                if status_cfg.get("stacking"):
                    transform_to = status_cfg.get("transform_to")
                    if status_key in statuses:
                        combat_log += (f"🦠 **เชื้อกลายพันธุ์แทรกซึม!** {status_cfg['label']} "
                                       f"({statuses[status_key]}/{status_cfg.get('transform_at')} สแตก)\n")
                    elif transform_to and transform_to in statuses:
                        frenzy_label = game_modifiers.STATUS_EFFECTS[transform_to]["label"]
                        combat_log += f"🧟 **เชื้อครบสามสแตก — คุณเสียสติ!** ติดสถานะ {frenzy_label}!\n"
                else:
                    combat_log += f"🧪 **พิษสงจากศัตรู!** คุณติดสถานะ {status_cfg['label']}!\n"

    # 💀 Life Drain (ทวีป/ธีม เช่น เนเธอร์): วิญญาณดูดกลืนชีวิตทุกเทิร์นที่สู้
    drain_range = mods.get("combat_hp_drain")
    if drain_range:
        # 📿 สร้อยเนเธอร์: แปลงพลังดูดชีวิตเป็นฮีล % MaxHP (ชนะ block ถ้ามีทั้งคู่)
        heal_pct = max((game_modifiers.STATUS_EFFECTS[k].get("hp_drain_heal", 0) for k in statuses), default=0)
        if heal_pct:
            max_hp = player.get("max_hp", 100)
            heal = max(1, round(max_hp * heal_pct))
            player["hp"] = min(max_hp, player.get("hp", 100) + heal)
            combat_log += f"📿 **สร้อยวิญญาณกลืนพลังดูดชีวิตย้อนกลับ** `+{heal}` HP (เหลือ {player['hp']})\n"
        elif game_modifiers.has_status_flag(statuses, "block_hp_drain"):
            combat_log += "✝️ **น้ำมนต์เปล่งแสงคุ้มครอง** — พลังดูดกลืนชีวิตถูกขับไล่ออกไป!\n"
        else:
            drain = rng.randint(int(drain_range[0]), int(drain_range[1]))
            player["hp"] = max(0, player.get("hp", 100) - drain)
            combat_log += f"🩸 **แดนมรณะดูดกลืนชีวิต** `-{drain}` HP (เหลือ {player['hp']})\n"

    # 🔥 สถานะเผาไหม้: เสียเลือดตาม % MaxHP ทุกเทิร์นที่สู้
    burn_pct = game_modifiers.status_pct_damage(statuses)
    if burn_pct:
        burn_dmg = max(1, round(player.get("max_hp", 100) * burn_pct))
        player["hp"] = max(0, player.get("hp", 100) - burn_dmg)
        combat_log += f"🔥 **แผลแผดเผาลุกลาม** `-{burn_dmg}` HP (เหลือ {player['hp']})\n"

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
    if active_buffs.get("frostbolt", 0) > 0: active_buffs["frostbolt"] -= 1
    if active_buffs.get("holy_aura", 0) > 0: active_buffs["holy_aura"] -= 1
    if active_buffs.get("shield_bash", 0) > 0: active_buffs["shield_bash"] -= 1
    if active_buffs.get("backstab", 0) > 0: active_buffs["backstab"] -= 1

    # 💎 ใช้สกิลแล้ว "ทอยแพ้" เท่านั้นถึงเสียเม็ด — ทอยชนะถือว่าคุ้มค่าท่า ไม่หัก
    mana_spent = 0
    if skill_used and player_roll < monster_roll:
        _mana.spend(user_id, 1, player)
        mana_spent = 1
        skill_log += "💎 **เม็ดคริสตัลแตกไปหนึ่งเม็ด** (ออกท่าแล้วทอยแพ้)\n"

    fight = dict(fight, stats=m_stats, hp=monster_hp, hp_max=monster_hp_max,
                 element=element, statuses=statuses, buffs=active_buffs,
                 turn=turn_count + 1, infused=infused, faction_side=faction_side)
    outcome = "win" if monster_hp <= 0 else ("lose" if player.get("hp", 0) <= 0 else "continue")
    return {"outcome": outcome, "skill_log": skill_log, "combat_log": combat_log,
            "damage_line": damage_line, "db_updates": db_updates,
            "player_roll": player_roll, "monster_roll": monster_roll,
            "player_parts": roll_parts, "monster_parts": mon_parts,
            "damage_to_monster": damage_to_monster, "damage_to_player": damage_to_player,
            "healed": healed_amount,
            "monster_hp": monster_hp, "monster_hp_max": monster_hp_max,
            "player_hp": player.get("hp", 0), "fight": fight, "player": player,
            "mana_spent": mana_spent, "mana": _mana.status_line(user_id)}


def record_element_book(user_id, cont_key, monster_rank, element, db_updates):
    """🧬 สมุดธาตุ: จดช่อง (ทวีป × แรงค์ × ธาตุ) แล้วแจกรางวัลตามลำดับขั้น

    ครบ 7 ธาตุของแรงค์ → ทอง | ครบทุกแรงค์ในทวีป → อาร์ติแฟกต์ประจำทวีป |
    ครบทุกทวีป → สัตว์เลี้ยงระดับสูงสุด — ทุกชั้นรับได้ครั้งเดียวผ่านสมุดจอง claim_once
    คืนข้อความประกาศ (ไม่มีอะไรปลด = สตริงว่าง)
    """
    if not element:
        return ""
    player_model.record_element_kill(user_id, cont_key, monster_rank, element)
    book = player_model.get_element_book(user_id)
    cont_label = game_modifiers.CONTINENTS.get(cont_key, game_modifiers.CONTINENTS["main"])["label"]
    msg = ""

    # ① ครบทุกธาตุของแรงค์นี้ ในทวีปนี้
    if game_modifiers.element_rank_done(book, cont_key, monster_rank) \
            and player_model.claim_once(user_id, f"elem:{cont_key}:{monster_rank}"):
        gold = int((config_loader.get_balance("bestiary.element_rank_rewards", {}) or {})
                   .get(monster_rank, 0))
        db_updates["cash"] = db_updates.get("cash", 0) + gold
        rank_name = _rank_stats(monster_rank).get("name", monster_rank)
        msg += (f"\n🧬 **สมุดธาตุครบชุด!** ล้ม {rank_name} ครบทั้ง 7 ธาตุแห่ง {cont_label} "
                f"— โบนัส `+{gold:,}` ทอง")

    # ② ครบทุกแรงค์ทุกธาตุในทวีปนี้ → อาร์ติแฟกต์ประจำทวีป
    if game_modifiers.element_continent_done(book, cont_key) \
            and player_model.claim_once(user_id, f"elem:cont:{cont_key}"):
        item_id = str((config_loader.get_balance("bestiary.continent_artifacts", {}) or {}).get(cont_key, ""))
        if item_id:
            fresh = player_model.get_player(user_id) or {}
            inv = player_model.load_inventory(db_updates.get("inventory") or fresh.get("inventory", ""))
            inv.append(item_id)
            db_updates["inventory"] = json.dumps(inv)
            art_name = config_loader.get_item_config(item_id).get("name", "อาร์ติแฟกต์")
            msg += (f"\n🏺 **พิชิตสมุดธาตุแห่ง {cont_label} ครบทั้งทวีป!** "
                    f"ได้รับ **{art_name}** เป็นรางวัล!")

    # ③ ครบทุกทวีป → สัตว์เลี้ยงระดับสูงสุด
    if game_modifiers.element_book_complete(book) \
            and player_model.claim_once(user_id, "elem:all"):
        from bot import pets as _pets
        pet_key = str(config_loader.get_balance("bestiary.element_complete_pet", "") or "")
        pet = next((p for p in _pets.all_pets() if p.get("key") == pet_key), None)
        if pet and player_model.claim_once(user_id, f"pet:{pet_key}"):
            msg += (f"\n🐉 **สมุดธาตุสมบูรณ์ทั้ง 9 ทวีป!!** ตำนานที่ไม่มีใครทำได้ — "
                    f"ได้รับสัตว์เลี้ยงขั้นสูงสุด **{pet['name']}**!")
        elif pet:
            msg += f"\n🐉 **สมุดธาตุสมบูรณ์ทั้ง 9 ทวีป!!** (คุณมี {pet['name']} อยู่แล้ว)"
    return msg


def fight_victory(user_id, fight, member_roles=(), rng=random, carry=None):
    """จ่ายรางวัลตอนโค่นมอนสำเร็จ (เว็บเกม เฟส 5.6c) — ยกมาจาก process_turn ทั้งก้อน

    ครอบคลุม: ทอง/EXP (ตัวคูณแรงค์ × ทวีป/ธีม × ธาตุ × passive × สงครามฝ่าย)
    ดรอปไอเทม · สมุดล่ามอน · สัตว์เลี้ยง · เควสรายวัน · ความสำเร็จ · คู่หู
    เลเวลอัป · เลื่อนแรงค์ · ดรอปวาร์ปในดันเจี้ยน · ดรอปของธีม infusion

    ไม่แตะ discord: ยศแรงค์คืนออกไปเป็น promoted_rank ให้ผู้เรียกไปให้เอง

    carry = db_updates ที่ค้างมาจากเทิร์นสุดท้าย (hp/ความทนทาน) — ต้องรวมมาเขียนด้วย
    ไม่งั้นผลของเทิร์นที่ล้มมอน (เช่นฮีลที่เพิ่งกด) หายไปทั้งหมด
    """
    from bot import identity as _identity
    player = player_model.get_player(user_id) or {}
    mods = game_modifiers.get_active_modifiers(player)
    m_stats = fight["stats"]
    monster_rank = fight["rank"]
    monster_hp = fight.get("hp", 0)
    monster_hp_max = fight.get("hp_max", 1)
    element = fight.get("element")
    element_data = game_modifiers.get_element_data(mods, element)
    statuses = dict(fight.get("statuses") or {})
    active_buffs = fight.get("buffs") or {}
    turn_count = fight.get("turn", 1)
    infused = fight.get("infused", False)
    faction_side = fight.get("faction_side")
    player_elements = game_modifiers.resolve_player_elements(
        _identity.effective_role_names(member_roles, player))

    combat_log = ""
    dropped_item_msg = ""
    rank_msg = ""
    battle_end_log = ""
    promoted_rank = None
    in_dungeon = False
    db_updates = dict(carry or {})

    # รางวัล = ฐานสุ่ม × แรงค์ × ทวีป/ธีม × ธาตุ (✨ แสง = ทอง ×3.5)
    elem_gold_mult = element_data.get("gold_mult", 1.0)
    # ✨ Passive ธาตุแสงของผู้เล่น: ทอง+EXP ที่ได้ ×1.1
    passive_reward_mult = game_modifiers.player_passive_mult(player_elements, "reward_mult")
    reward = int(rng.randint(1, 25) * m_stats.get("gold_mult", 1.0) * mods.get("monster_gold_mult", 1.0) * elem_gold_mult * passive_reward_mult)
    status_exp_mult = game_modifiers.status_combat_mult(statuses, "exp_mult")
    gained_exp = int((m_stats.get("exp_reward", 10) + rng.randint(5, 15)) * mods.get("monster_exp_mult", 1.0) * element_data.get("exp_mult", 1.0) * status_exp_mult * passive_reward_mult)
    # ⚔️ โค่นแชมเปี้ยนฝ่ายตรงข้าม (ธีมสงครามฝ่าย): ทอง ×2, EXP ×1.5
    if faction_side:
        reward = int(reward * float(config_loader.get_balance("faction_war.gold_mult", game_modifiers.FACTION_WAR_GOLD_MULT)))
        gained_exp = int(gained_exp * float(config_loader.get_balance("faction_war.exp_mult", game_modifiers.FACTION_WAR_EXP_MULT)))
    if elem_gold_mult > 1.0:
        combat_log += "✨ **พรแห่งแสง!** ร่างมอนสเตอร์สลายเป็นกองทองคำมูลค่าพิเศษ!\n"
    if status_exp_mult > 1.0:
        combat_log += "🌟 **พรบรรพชนหนุนนำ!** ประสบการณ์ที่ได้รับเพิ่มขึ้นเป็นพิเศษ!\n"
    
    # 💠 สว่านเจาะรูอาร์ติแฟกต์ — ดรอปจากบอสไร้พ่ายเท่านั้น เรทสูงมาก
    if monster_rank == "Unbeatable":
        try:
            punch_id = str(config_loader.get_balance("artifact.punch_item", "") or "")
            chance = int(config_loader.get_balance("artifact.punch_drop_chance", 0) or 0)
            if punch_id and rng.randint(1, 100) <= chance:
                fresh_p = player_model.get_player(user_id) or {}
                inv_p = player_model.load_inventory(
                    db_updates.get("inventory") or fresh_p.get("inventory", ""))
                inv_p.append(punch_id)
                db_updates["inventory"] = json.dumps(inv_p)
                pname = config_loader.get_item_config(punch_id).get("name", "สว่านเจาะรู")
                dropped_item_msg += (f"\n💠 **{pname}** ร่วงจากซากไร้พ่าย! "
                                     "— ใช้เพิ่มช่องอาร์ติแฟกต์ได้อีก 1 ช่อง")
        except Exception as e:
            print(f"⚠️ [artifact] ดรอปสว่านพัง: {e}")

    # 🪤 กับดักถูกใช้ไปแล้ว — ปลดออกตอนล้มมอนได้ (หนีออกมาเฉย ๆ กับดักยังอยู่ ใช้ต่อได้)
    if "monster_trap" in statuses:
        statuses.pop("monster_trap", None)
        db_updates["status_effects"] = json.dumps(statuses)
        combat_log += "🪤 **กับดักมอนสเตอร์ถูกใช้ไปแล้ว** — เหยื่อติดกับสมบูรณ์\n"

    # 💞 C7: โบนัสคู่หู — เต็มจำนวนเมื่อคู่เข้ามาเล่นวันเดียวกัน
    try:
        from bot import partner as _partner
        p_mult, p_note = _partner.bonus_for(user_id)
        if p_mult > 1.0:
            reward = int(reward * p_mult)
            gained_exp = int(gained_exp * p_mult)
            combat_log += p_note
    except Exception as e:
        print(f"⚠️ [partner] โบนัสคู่หูพัง: {e}")

    db_updates["cash"] = player.get("cash", 0) + reward
    db_updates["sanity"] = player.get("sanity", 100) + 1
    db_updates["last_event"] = "monster"
    db_updates["current_state"] = "idle"
    
    dropped_item_msg = ""
    try:
        fresh_player = player_model.get_player(user_id)
        raw_inv = fresh_player.get("inventory", "[]")
        
        if isinstance(raw_inv, str):
            try:
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

        m_tier = monster_rank
        dropped_item_id = None

        ITEM_CONFIG = config_loader.get_all_items()
        if m_tier in ["Secret", "Unbeatable"] and rng.randint(1, 100) <= int(config_loader.get_balance("drops.rare_chance", 1)):
            dropped_item_id = rng.choice(["8", "21"])
        elif rng.randint(1, 100) <= int(config_loader.get_balance("drops.normal_chance", 70)):
            if m_tier == "Common":
                drop_pool = ["9", "10", "11", "12", "13", "14", "15", "16", "17", "18"]
            else:
                drop_pool = ["9", "10", "11", "12", "13", "14", "15", "16", "17", "18", 
                             "22", "23", "24", "25", "26", "27", "28", "3", "4", "5", "6", "7"]
            weights = [100000 / ITEM_CONFIG.get(i, {}).get("buy", 100) for i in drop_pool]
            dropped_item_id = rng.choices(drop_pool, weights=weights, k=1)[0]

        if dropped_item_id:
            dropped_item_name = ITEM_CONFIG.get(dropped_item_id, {}).get("name", "ไอเทมปริศนา")
            capacity = fresh_player.get("capacity", 10)
            current_count = len(inv_list)
            
            if capacity == 0 or current_count < capacity:
                inv_list.append(str(dropped_item_id))
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

    # ⚔️ แต้มสงครามฝ่าย (P5): +1 ให้ฝ่ายผู้เล่น + โชว์สกอร์สด — พังต้องไม่ล้มไฟต์
    if faction_side:
        try:
            side = faction_side
            foe = "demon" if side == "human" else "human"
            scores = player_model.add_faction_war_point(side)
            s_lbl = game_modifiers.FACTIONS[side]["label"]
            f_lbl = game_modifiers.FACTIONS[foe]["label"]
            dropped_item_msg += (f"\n⚔️ **เกียรติยศแด่{s_lbl}!** แต้มสงคราม `+1` — "
                                 f"สกอร์สัปดาห์นี้ {s_lbl} `{scores[side]}` : `{scores[foe]}` {f_lbl} (`!war`)")
        except Exception as e:
            print(f"❌ [ERROR] ระบบแต้มสงครามพัง: {e}")

    # 📅 C1: นับเควสรายวัน (ล่ามอน / ล้มบอส)
    try:
        from bot import daily as _daily
        _daily.track(user_id, "kill", 1)
        if monster_rank in ("Mini-Boss", "Main-Boss", "Secret", "Unbeatable"):
            _daily.track(user_id, "boss", 1)
    except Exception as e:
        print(f"⚠️ [daily] นับเควสล่ามอนพัง: {e}")

    # 🏅 C8: ปลดล็อกความสำเร็จทันทีที่ถึงเกณฑ์ (คำนวณจากสมุดล่า/สถิติที่มีอยู่ ไม่มีตัวนับใหม่)
    try:
        from bot import achievements as _ach
        dropped_item_msg += _ach.unlock_message(_ach.check_and_unlock(user_id))
    except Exception as e:
        print(f"⚠️ [ach] เช็คความสำเร็จพัง: {e}")

    # 🐾 C4: ลุ้นจับมอนที่เพิ่งล้มมาเลี้ยง (โอกาสตามแรงค์ — ตัวที่มีแล้วไม่ออกซ้ำ)
    try:
        from bot import pets as _pets
        dropped_item_msg += _pets.tame_message(_pets.try_tame(user_id, monster_rank))
    except Exception as e:
        print(f"⚠️ [pets] จับสัตว์เลี้ยงพัง: {e}")

    # 📕 สมุดสะสมมอน (Bestiary): จดแต้ม + แจกโบนัสครั้งเดียวเมื่อครบชุด — พังต้องไม่ล้มไฟต์
    try:
        cont_key = player.get("continent") or "main"
        player_model.record_bestiary_kill(user_id, cont_key, monster_rank)
        # 🧬 สมุดธาตุ: จดแยกตามธาตุของมอน + แจกรางวัล 3 ชั้น (แรงค์ → ทวีป → ทั้งเล่ม)
        dropped_item_msg += record_element_book(user_id, cont_key, monster_rank, element, db_updates)
        book = player_model.get_bestiary(user_id)
        cont_label = game_modifiers.CONTINENTS.get(cont_key, game_modifiers.CONTINENTS["main"])["label"]
        if monster_rank == "Unbeatable":
            if player_model.claim_bestiary_reward(user_id, f"star:{cont_key}"):
                db_updates["cash"] += int(config_loader.get_balance("bestiary.star_reward", game_modifiers.BESTIARY_REWARD_STAR))
                dropped_item_msg += f"\n⭐ **ดาวไร้พ่ายประดับสมุดล่า!** พิชิตไร้พ่ายแห่ง {cont_label} — โบนัส `+{int(config_loader.get_balance("bestiary.star_reward", game_modifiers.BESTIARY_REWARD_STAR)):,}` ทอง"
        elif game_modifiers.bestiary_continent_done(book, cont_key):
            if player_model.claim_bestiary_reward(user_id, f"continent:{cont_key}"):
                db_updates["cash"] += int(config_loader.get_balance("bestiary.continent_reward", game_modifiers.BESTIARY_REWARD_CONTINENT))
                dropped_item_msg += f"\n📕 **สมุดล่า {cont_label} ครบชุด!** โบนัส `+{int(config_loader.get_balance("bestiary.continent_reward", game_modifiers.BESTIARY_REWARD_CONTINENT)):,}` ทอง (ดูสมุด: `!bestiary`)"
        if game_modifiers.bestiary_complete(book) and player_model.claim_bestiary_reward(user_id, "complete"):
            db_updates["cash"] += int(config_loader.get_balance("bestiary.complete_reward", game_modifiers.BESTIARY_REWARD_COMPLETE))
            if db_updates.get("inventory") is not None:
                final_inv = json.loads(db_updates["inventory"])
            else:
                final_inv = player_model.load_inventory(player.get("inventory", ""))
            final_inv.append(game_modifiers.BESTIARY_COMPLETE_ITEM)  # รางวัลใหญ่ ไม่เช็คความจุ
            db_updates["inventory"] = json.dumps(final_inv)
            dropped_item_msg += f"\n🏆 **สมุดล่าสมบูรณ์ทั้ง 9 ทวีป!** ตำนานนักล่าจารึกชื่อคุณ — `+{int(config_loader.get_balance("bestiary.complete_reward", game_modifiers.BESTIARY_REWARD_COMPLETE)):,}` ทอง + 💊 ยาครอบจักรวาล!"
    except Exception as e:
        print(f"❌ [ERROR] ระบบสมุดล่าพัง: {e}")

    in_dungeon = (player.get("current_state") == "dungeon_choice"
                  or player.get("dungeon_steps", 0) > 0)
    battle_end_log = ("\n⚔️ มอนสเตอร์ในชั้นนี้ถูกกำจัดแล้ว! "
                      "เตรียมตัวเดินทางลึกเข้าไปในดันเจี้ยนขั้นถัดไป...") if in_dungeon else ""

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
        
        player_model.update_player_fields(user_id, db_updates)
        
        # ยศแรงค์ต้องให้ผ่าน discord — คืนออกไปให้ผู้เรียกจัดการ
        # (ดิสให้ยศทันที / เว็บให้ไม่ได้เอง ต้องรอบอทซิงก์ตอนผู้เล่นเข้าเซิร์ฟ)
        if old_rank != new_rank:
            promoted_rank = new_rank
            rank_msg = f"\n🎖️ **สมาคมนักผจญภัยได้เลื่อนขั้นให้คุณเป็น: นักผจญภัยแรงค์ {new_rank}!**"
    except Exception as e:
        print(f"❌ [ERROR] ระบบแรงค์พัง: {e}")

    # ☄️ มอนอาบพลังพิเศษ: ดรอปไอเทมของธีม (เขียนหลัง db_updates เพื่อไม่ชนกัน)
    if infused:
        drop_cfg = (mods.get("infusion") or {}).get("drop_items")
        if drop_cfg:
            try:
                infusion_lines, _ = execute_special_outcome(user_id, {"items": dict(drop_cfg)})
                dropped_item_msg += "\n☄️ **พลังอุกกาบาตตกผลึก!** " + " · ".join(infusion_lines)
            except Exception as e:
                print(f"❌ [ERROR] ดรอปไอเทม infusion พัง: {e}")

    # 🌀 มอนในดันเจี้ยน: มีโอกาสดรอปไอเทมวาร์ปทวีป (แหล่งเดียวในเกม)
    if player.get("current_state") == "dungeon_choice" or player.get("dungeon_steps", 0) > 0:
        try:
            warp_lines, _ = execute_special_outcome(user_id, {"items": [
                {"id": "52", "qty": 1, "chance": 6},   # 🌀 ประตูวาร์ปมิติ (สุ่มทวีป)
                {"id": "53", "qty": 1, "chance": 2},   # 🎫 ตั๋วเรือเหมาลำ (เลือกทวีปเอง — แรร์กว่า)
            ]})
            if warp_lines:
                dropped_item_msg += "\n🌀 **แสงมิติเล็ดลอดจากซากมอนสเตอร์!** " + " · ".join(warp_lines)
        except Exception as e:
            print(f"❌ [ERROR] ดรอปไอเทมวาร์ปพัง: {e}")

    return {"reward": reward, "exp": gained_exp, "level": current_level, "current_exp": current_exp,
            "level_up": is_lv_up, "rank_msg": rank_msg, "promoted_rank": promoted_rank,
            "drops": dropped_item_msg, "battle_end_log": battle_end_log,
            "in_dungeon": in_dungeon, "combat_log": combat_log, "statuses": statuses}


def fight_flee(user_id, fight, rng=random):
    """🏃 กดหนีจากไฟต์ (เว็บเกม เฟส 5.6d) — ยกมาจากปุ่มหนีในดิสทั้งชุด

    รากพันธนาการล็อกไว้ = หนีไม่ได้ (เช็คกับสถานะสด ใช้มีดตัดเถากลางไฟต์แล้วหนีได้ทันที)
    ทอยไม่ผ่านเรทหนีของแรงค์ = โดนสวนกลับ เสีย HP + เกราะสึก

    outcome: blocked | fled | hit | lose
    """
    player = player_model.get_player(user_id) or {}
    statuses = _resync_statuses(fight.get("statuses") or {}, player, fight.get("fight_grace"))

    if game_modifiers.has_status_flag(statuses, "no_flee"):
        turns = next((v for k, v in statuses.items()
                      if game_modifiers.STATUS_EFFECTS[k].get("no_flee")), "?")
        return {"outcome": "blocked", "fight": fight,
                "text": (f"🌱 **รากไม้รัดขาแน่น!** (สถานะพันธนาการเหลือ `{turns}` ก้าว) "
                         f"คุณดิ้นเท่าไหร่ก็หนีไม่หลุด — ใช้ 🗡️ มีดตัดเถาวัลย์/🌿 ยาถอนพิษก่อน")}

    if rng.randint(1, 100) <= fight["stats"]["flee_chance"]:
        player_model.update_player_field(user_id, "current_state", "idle")
        return {"outcome": "fled", "fight": fight,
                "text": "💨 **หนีสำเร็จ!** สลัดหลุดจากมอนสเตอร์สำเร็จ!"}

    damage = rng.randint(15, 30)
    new_hp = max(0, player.get("hp", 0) - damage)
    dur = player.get("armor_dur", 0)
    armor_loss = max(1, damage // 10) if dur > 0 else 0
    updates = {"hp": new_hp, "armor_dur": max(0, dur - armor_loss),
               "current_state": "dead" if new_hp <= 0 else "fighting"}
    player_model.update_player_fields(user_id, updates)

    if new_hp <= 0:
        return {"outcome": "lose", "fight": fight, "player_hp": 0,
                "text": "💥 หนีไม่พ้นและโดนตบตายคาที่!"}

    msg = (f"💥 หนีไม่พ้น! โดนสวนหลังฟาดกระอักเลือด `- {damage}`! "
           f"(เกราะเสียหาย `- {armor_loss}`)")
    if updates["armor_dur"] == 0 and dur > 0:
        msg += "\n🚨 **ชุดเกราะของคุณพังยับเยิน!**"
    return {"outcome": "hit", "text": msg, "player_hp": new_hp, "damage": damage,
            "fight": dict(fight, turn=fight.get("turn", 1) + 1, statuses=statuses)}


def respawn(user_id):
    """💀 ชุบชีวิต — ตรรกะเดียวใช้ทุกเส้นทางตาย ทั้งดิสและเว็บ (เว็บเกม 2026-08-14)

    เดิมฝังอยู่ใน respawn_player ของ Discord ซึ่งสร้าง embed ด้วย เว็บจึงเรียกไม่ได้
    ผลคือตายบนเว็บแล้วไม่มีปุ่มฟื้น ค้างที่สถานะ dead จนต้องไปกด !play ในดิส

    คืน dict ข้อมูลล้วน — ผู้เรียกเอาไปสร้างหน้าจอเอง (None ถ้าไม่มีตัวละคร)
    """
    player = player_model.get_player(user_id)
    if not player:
        return None
    max_hp = player.get("max_hp", 100)
    hp_pct = int(config_loader.get_balance("drops.respawn_hp_percent", 30))
    respawn_hp = max(1, int(max_hp * hp_pct / 100))
    tiers = config_loader.get_balance(
        "death.respawn_fee_tiers",
        [[100, 10000], [90, 5000], [50, 2500], [20, 1000], [10, 500], [0, 0]])
    fee = next((int(f) for lv, f in tiers if player.get("level", 0) >= int(lv)), 0)
    new_cash = player.get("cash", 0) - fee
    lost_steps = player.get("dungeon_steps", 0)

    player_model.update_player_fields(user_id, {
        "hp": respawn_hp, "cash": new_cash,
        "current_state": "village", "last_event": "village", "dungeon_steps": 0})
    clear_pending(user_id)                      # ตายแล้วเหตุการณ์ค้างเก่าต้องไม่หลงเหลือ

    from bot import mana as _mana
    _mana.refill(user_id)                       # 💎 เกิดใหม่ = เม็ดคริสตัลเต็ม

    return {"player": player, "hp": respawn_hp, "max_hp": max_hp, "hp_pct": hp_pct,
            "fee": fee, "cash": new_cash, "lost_steps": lost_steps}
