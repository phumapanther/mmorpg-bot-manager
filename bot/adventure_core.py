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


def commit_event(user_id, chosen_event, last_evt):
    """บันทึกผลของก้าวนี้ — last_event และคูลดาวน์หมู่บ้าน (ยกมาจากของเดิม)

    เจอมอนต่อจากใบเรียกบอส = ไม่ทับ last_event (ต้องคงค่าเรียกบอสไว้ให้ระบบไฟต์อ่าน)
    """
    if not (chosen_event == "monster" and last_evt in SUMMON_EVENTS):
        player_model.update_player_field(user_id, "last_event", chosen_event)
    if chosen_event == "village":
        player_model.update_player_field(user_id, "village_cooldown", 10)
