"""ทดสอบระบบสถานะติดตัว (A2) — ฟังก์ชัน pure ใน game_modifiers (ส่วน view ทดสอบ manual)"""
import random

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


def test_format_status_line_units():
    line = gm.format_status_line({"poison": 12, "emp": 1})
    assert "☠️ พิษป่า (เหลือ 12 ก้าว)" in line
    assert "⚡ โดน EMP (เหลือ 1 ไฟต์)" in line
