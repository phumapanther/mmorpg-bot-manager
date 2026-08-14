"""ตรรกะการเดินทางกลาง (เว็บเกม เฟส 5.1)

ดึง "การตัดสินใจว่าก้าวนี้เจออะไร" ออกจาก walk_step ของ Discord View
ลำดับความสำคัญยกมาครบทุกข้อ ห้ามสลับลำดับ — ลำดับคือกติกาของเกม

หมายเหตุ: ฟังก์ชันนี้เขียน DB ตรงบางจุด (dungeon_steps/last_event/village_cooldown)
เหมือนของเดิมเป๊ะ เพื่อไม่ให้พฤติกรรมฝั่งดิสเปลี่ยน
"""
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
