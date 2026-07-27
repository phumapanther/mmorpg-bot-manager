"""ทดสอบระบบสถานะติดตัว (A2) — ฟังก์ชัน pure ใน game_modifiers (ส่วน view ทดสอบ manual)"""
import random

import pytest

from bot import game_modifiers as gm


def test_status_table_structure():
    assert set(gm.STATUS_EFFECTS) >= {"poison", "numb", "emp", "exp_blessing"}
    for cfg in gm.STATUS_EFFECTS.values():
        assert cfg["label"]
        assert cfg["tick"] in ("step", "fight")
        assert cfg.get("default_turns", 1) > 0


def test_parse_statuses_filters_and_accepts_str_or_dict():
    assert gm.parse_statuses(None) == {}
    assert gm.parse_statuses({}) == {}
    assert gm.parse_statuses({"status_effects": None}) == {}
    assert gm.parse_statuses({"status_effects": "ไม่ใช่ json"}) == {}
    # str JSON, ตัดสถานะไม่รู้จัก + เทิร์น <= 0 ทิ้ง
    raw = '{"poison": 5, "unknown": 3, "emp": 0}'
    assert gm.parse_statuses({"status_effects": raw}) == {"poison": 5}
    # dict ตรงๆ (จาก update_player_field ที่ json.dumps ให้)
    assert gm.parse_statuses({"status_effects": {"numb": 2}}) == {"numb": 2}


def test_apply_status_refresh_keeps_higher():
    s = gm.apply_status({}, "poison")
    assert s == {"poison": gm.STATUS_EFFECTS["poison"]["default_turns"]}
    s = gm.apply_status({"poison": 3}, "poison", turns=10)   # ติดซ้ำค่าใหม่มากกว่า → รีเซ็ต
    assert s["poison"] == 10
    s = gm.apply_status({"poison": 15}, "poison", turns=5)   # ค่าใหม่น้อยกว่า → คงของเดิม
    assert s["poison"] == 15
    assert gm.apply_status({}, "no_such_status") == {}       # สถานะไม่รู้จัก = เมิน


def test_tick_only_matching_type_and_expiry():
    s = {"poison": 2, "emp": 1}
    s, expired = gm.tick_statuses(s, "step")
    assert s == {"poison": 1, "emp": 1} and expired == []    # emp เป็น fight ไม่โดน step tick
    s, expired = gm.tick_statuses(s, "step")
    assert s == {"emp": 1} and expired == ["poison"]         # พิษหมด ถูกลบ
    s, expired = gm.tick_statuses(s, "fight")
    assert s == {} and expired == ["emp"]


def test_cleanse_on_village_and_npc():
    s = {"poison": 10, "numb": 3}
    s, cleansed = gm.cleanse_statuses(s, "village")
    assert cleansed == ["poison"] and s == {"numb": 3}       # ชาไม่มี cleanse_on ไม่หาย
    s2, cleansed2 = gm.cleanse_statuses({"poison": 4}, "npc")
    assert cleansed2 == ["poison"] and s2 == {}


def test_combat_mult_and_flags():
    assert gm.status_combat_mult({}, "player_dmg_mult") == 1.0
    assert gm.status_combat_mult({"numb": 2}, "player_dmg_mult") == 0.5
    assert gm.status_combat_mult({"exp_blessing": 5}, "exp_mult") == 1.5
    assert gm.status_combat_mult({"numb": 2, "exp_blessing": 5}, "exp_mult") == 1.5
    assert gm.has_status_flag({"emp": 1}, "disable_skills") is True
    assert gm.has_status_flag({"poison": 9}, "disable_skills") is False


def test_step_damage_within_range():
    rng = random.Random(5)
    lo, hi = gm.STATUS_EFFECTS["poison"]["step_damage"]
    for _ in range(20):
        total, details = gm.roll_step_damage({"poison": 5}, rng=rng)
        assert lo <= total <= hi
        assert details[0][0] == gm.STATUS_EFFECTS["poison"]["label"]
    assert gm.roll_step_damage({"numb": 2}, rng=rng) == (0, [])  # ชาไม่มีเลือดไหล


def test_s2_status_table_and_helpers():
    # โครงสถานะใหม่ 4 ตัว
    assert gm.STATUS_EFFECTS["sealed_dice"]["seal_high_roll"] == 15
    assert gm.STATUS_EFFECTS["fumble"]["fumble_chance"] == 30
    assert gm.STATUS_EFFECTS["burn"]["combat_pct_damage"] == 0.05
    assert gm.STATUS_EFFECTS["burn"]["tick"] == "fight"
    assert gm.STATUS_EFFECTS["entangled"]["no_flee"] is True
    assert gm.STATUS_EFFECTS["entangled"]["monster_dice_bonus"] == 2
    # helpers
    assert gm.status_seal_threshold({}) is None
    assert gm.status_seal_threshold({"sealed_dice": 3}) == 15
    assert gm.status_fumble_chance({"fumble": 2}) == 30
    assert gm.status_fumble_chance({"poison": 5}) == 0
    assert gm.status_pct_damage({"burn": 2}) == 0.05
    assert gm.status_monster_dice_bonus({"entangled": 1}) == 2
    assert gm.has_status_flag({"entangled": 1}, "no_flee") is True


def test_s2_on_hit_bindings():
    # ธาตุลม/ไฟ/ไม้ ตีติดสถานะตามสเปก
    assert gm.ELEMENTS["wind"]["on_hit_status"] == {"key": "sealed_dice", "chance": 15}
    assert gm.ELEMENTS["fire"]["on_hit_status"] == {"key": "burn", "chance": 15}
    assert gm.ELEMENTS["wood"]["on_hit_status"] == {"key": "entangled", "chance": 15}
    # ทวีปน้ำแข็ง: มอนตีติดเต๋าหลุดมือ
    assert gm.CONTINENTS["frozen"]["mods"]["on_hit_status"] == {"key": "fumble", "chance": 12}
    # ทุก on_hit ต้องชี้สถานะที่มีจริง
    for elem in gm.ELEMENTS.values():
        if "on_hit_status" in elem:
            assert elem["on_hit_status"]["key"] in gm.STATUS_EFFECTS


def test_s3_curses_and_shock():
    # ตารางสถานะ
    assert gm.STATUS_EFFECTS["odd_curse"]["curse_parity"] == "odd"
    assert gm.STATUS_EFFECTS["even_curse"]["curse_parity"] == "even"
    assert gm.STATUS_EFFECTS["shock"]["skill_fail_chance"] == 50
    # curse_for_roll: parity ตรงเท่านั้นที่ทำงาน, เต๋า 0 ไม่นับเป็นคู่
    assert gm.status_curse_for_roll({"odd_curse": 5}, 7) == "odd_curse"
    assert gm.status_curse_for_roll({"odd_curse": 5}, 8) is None
    assert gm.status_curse_for_roll({"even_curse": 5}, 8) == "even_curse"
    assert gm.status_curse_for_roll({"even_curse": 5}, 0) is None
    assert gm.status_curse_for_roll({}, 7) is None
    # shock: deterministic ด้วย FakeRng
    class FakeRng:
        def __init__(self, rolls):
            self.rolls = list(rolls)

        def randint(self, lo, hi):
            return self.rolls.pop(0)

    failed, dmg = gm.status_skill_shock({"shock": 2}, rng=FakeRng([50, 9]))
    assert failed and dmg == 9
    failed, dmg = gm.status_skill_shock({"shock": 2}, rng=FakeRng([51]))
    assert not failed and dmg == 0
    assert gm.status_skill_shock({"poison": 5}) == (False, 0)


def test_s3_on_hit_bindings():
    assert gm.CONTINENTS["nether"]["mods"]["on_hit_status"] == {"key": "odd_curse", "chance": 12}
    assert gm.CONTINENTS["mechanized"]["mods"]["on_hit_status"] == {"key": "shock", "chance": 12}
    goddess = next(t for t in gm.WEEKLY_THEMES if t["key"] == "goddess_dice")
    assert goddess["mods"]["on_hit_status"] == {"key": "even_curse", "chance": 12}


def test_s4_zombie_parasite_stacking():
    # ติดครั้งแรก = 1 สแตก, ติดซ้ำ = สะสม (ไม่ใช่ refresh)
    s = gm.apply_status({}, "zombie_parasite")
    assert s == {"zombie_parasite": 1}
    s = gm.apply_status(s, "zombie_parasite")
    assert s == {"zombie_parasite": 2}
    # ครบ 3 → แปลงร่างเป็นคลั่งซอมบี้ (เชื้อหาย คลั่งโผล่พร้อมเทิร์นเต็ม)
    s = gm.apply_status(s, "zombie_parasite")
    assert "zombie_parasite" not in s
    assert s["zombie_frenzy"] == gm.STATUS_EFFECTS["zombie_frenzy"]["default_turns"]
    # คลั่ง = เต๋าทุกลูกโดนผนึกเหลือ 1
    assert gm.status_seal_threshold(s) == 2
    # เชื้อไม่ tick ลดเอง แต่คลั่ง tick ตามก้าวปกติ
    ticked, expired = gm.tick_statuses({"zombie_parasite": 2}, "step")
    assert ticked == {"zombie_parasite": 2} and expired == []
    ticked, expired = gm.tick_statuses({"zombie_frenzy": 1}, "step")
    assert ticked == {} and expired == ["zombie_frenzy"]
    # บรรทัดสถานะแสดงเป็นสแตก
    assert "(2/3 สแตก)" in gm.format_status_line({"zombie_parasite": 2})


def test_s4_zombie_theme_bindings():
    zombie = next(t for t in gm.WEEKLY_THEMES if t["key"] == "zombie")
    assert zombie["mods"]["on_hit_status"] == {"key": "zombie_parasite", "chance": 25}
    infusion = zombie["mods"]["infusion"]
    assert infusion["drop_items"] == {"id": "31", "qty": 1}   # พาหะดรอปเสบียงแก้


def test_t1_immunity_mechanics():
    # อบอุ่น: ล้างหนาวตอนติด + กันหนาวติดใหม่
    s = gm.apply_status({"frostbite": 999}, "warm")
    assert "frostbite" not in s and s["warm"] == 10
    s = gm.apply_status(s, "frostbite")
    assert "frostbite" not in s                      # โดน block
    # เกราะกันคลื่น: ล้าง EMP + กัน EMP
    s = gm.apply_status({"emp": 1}, "emp_shield")
    assert "emp" not in s and "emp_shield" in s
    assert gm.apply_status(s, "emp") == s
    # น้ำมนต์: ธง block_hp_drain / ขนนก: ธง fall_guard
    assert gm.has_status_flag({"holy_guard": 3}, "block_hp_drain") is True
    assert gm.has_status_flag({"featherfall": 30}, "fall_guard") is True


def test_t2_dice_and_event_items():
    # เต๋าถ่วงน้ำหนัก: ขั้นต่ำ 14 + ใช้แล้วล้างตราผนึก
    s = gm.apply_status({"sealed_dice": 4}, "weighted_dice")
    assert "sealed_dice" not in s and "weighted_dice" in s
    assert gm.status_min_roll(s) == 14
    assert gm.status_min_roll({}) == 0
    # โคลเวอร์: ธง block_root
    assert gm.has_status_flag({"clover": 1}, "block_root") is True
    # เข็มทิศ: ตัวคูณน้ำหนักหีบ ×2
    assert gm.status_event_weight_mult({"convoy_compass": 20}) == {"treasure": 2.0}
    assert gm.status_event_weight_mult({"poison": 5}) == {}
    # คมอัคนี: บัฟดาเมจทบกับยาโด๊ปได้
    assert gm.status_combat_mult({"obsidian_edge": 1, "illegal_buff": 5}, "player_dmg_mult") == pytest.approx(1.2 * 1.3)


def test_t2_drop_sources():
    # ภูเขาไฟระเบิดแจกอัญมณี + หินอัคนี + แหวนแรร์ (V1)
    eruption = gm.CONTINENTS["volcanic"]["mods"]["special_events"][0]
    assert eruption["success"]["items"] == [{"id": "11", "qty": 10}, {"id": "40", "qty": 1},
                                            {"id": "45", "qty": 1, "chance": 8}]
    # ธีมจานสี: พาหะสีดรอปผงสีรุ้ง
    palette = next(t for t in gm.WEEKLY_THEMES if t["key"] == "palette")
    assert palette["mods"]["infusion"]["drop_items"] == {"id": "41", "qty": 1}


def test_format_status_line_units():
    line = gm.format_status_line({"poison": 12, "emp": 1})
    assert "☠️ พิษป่า (เหลือ 12 ก้าว)" in line
    assert "⚡ โดน EMP (เหลือ 1 ไฟต์)" in line
