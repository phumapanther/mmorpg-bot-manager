"""P1-③ บัฟวอริเออร์: ค่า config ใหม่ + ไฟล์ config โหลดได้ปกติหลังแก้"""
import json


def test_warrior_skill_config_values():
    for f in ("config.example.json",):
        skills = json.load(open(f, encoding="utf-8"))["skills"]["Warrior"]
        hs, sb = skills["heavy_strike"], skills["shield_bash"]
        # Heavy Strike พื้นฐานคงเดิม (ผู้ใช้ไม่เอาข้อ 1) + คริใหม่
        assert hs["damage_multiplier"] == 2 and hs["chance_base"] == 80
        assert hs["crit_roll_min"] == 18 and hs["crit_multiplier"] == 3
        # Shield Bash หนาขึ้น + สะท้อน
        assert sb["duration"] == 4 and sb["reduction_base"] == 0.6
        assert sb["reflect_pct"] == 0.2


def test_config_json_still_valid():
    cfg = json.load(open("config.json", encoding="utf-8"))
    assert cfg["skills"]["Warrior"]["shield_bash"]["reflect_pct"] == 0.2
    assert "item_catalog" in cfg  # โครงสร้างส่วนอื่นไม่หาย
