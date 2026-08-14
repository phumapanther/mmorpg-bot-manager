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
    inv.append(int(chosen))
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
