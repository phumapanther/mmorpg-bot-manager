"""ทดสอบแกน game_modifiers — ล็อกกติกา: identity ไม่เปลี่ยนเกม, กติการวมผล, ธีมสัปดาห์ deterministic"""
import datetime

import pytest

from bot import game_modifiers as gm


def test_default_is_identity(monkeypatch):
    monkeypatch.setattr(gm, "WEEKLY_THEMES", [])
    mods = gm.get_active_modifiers({"continent": "main"})
    assert mods["monster_hp_mult"] == 1.0
    assert mods["monster_dmg_mult"] == 1.0
    assert mods["monster_gold_mult"] == 1.0
    assert mods["monster_exp_mult"] == 1.0
    assert mods["event_weight_mult"] == {}
    assert mods["monster_pool"] == {}
    assert mods["theme_texts"] == {}


def test_missing_or_unknown_continent_falls_back_to_main():
    assert gm.get_continent(None) is gm.CONTINENTS["main"]
    assert gm.get_continent({}) is gm.CONTINENTS["main"]
    assert gm.get_continent({"continent": "atlantis?"}) is gm.CONTINENTS["main"]


def test_apply_event_weights_identity_when_no_mult():
    weights = [25, 25, 20, 15, 10, 5]
    out = gm.apply_event_weights(weights, gm_event_list(), gm.DEFAULT_MODS)
    assert out == weights


def gm_event_list():
    return ["monster", "village", "treasure", "dungeon", "npc", "trap"]


def test_merge_rules(monkeypatch):
    monkeypatch.setitem(gm.CONTINENTS, "testland", {
        "label": "test",
        "mods": {
            "monster_hp_mult": 2.0,
            "event_weight_mult": {"monster": 1.5},
            "monster_pool": {"Common": ["Imp"]},
            "theme_texts": {"treasure": "หีบทดสอบ"},
        },
    })
    monkeypatch.setattr(gm, "WEEKLY_THEMES", [{
        "key": "testweek",
        "mods": {
            "monster_hp_mult": 1.5,
            "event_weight_mult": {"monster": 2.0},
            "monster_pool": {"Common": ["Zombie"], "Mini-Boss": ["Zombie Titan"]},
            "theme_texts": {"treasure": "หีบซอมบี้"},
        },
    }])

    mods = gm.get_active_modifiers({"continent": "testland"})
    assert mods["monster_hp_mult"] == pytest.approx(3.0)          # 2.0 × 1.5
    assert mods["event_weight_mult"]["monster"] == pytest.approx(3.0)  # 1.5 × 2.0
    assert mods["monster_pool"]["Common"] == ["Imp", "Zombie"]    # ต่อกันรายแรงค์
    assert mods["monster_pool"]["Mini-Boss"] == ["Zombie Titan"]
    assert mods["theme_texts"]["treasure"] == "หีบซอมบี้"          # ธีมสัปดาห์ทับทวีป
    # ตัวอื่นยังเป็น identity
    assert mods["monster_gold_mult"] == 1.0

    weights = gm.apply_event_weights([10, 20, 30], ["monster", "village", "treasure"], mods)
    assert weights == [pytest.approx(30.0), 20, 30]

    # DEFAULT_MODS ต้องไม่ถูกแก้ไขข้างเคียง
    assert gm.DEFAULT_MODS["monster_hp_mult"] == 1.0
    assert gm.DEFAULT_MODS["monster_pool"] == {}


def test_weekly_theme_deterministic(monkeypatch):
    themes = [{"key": "a"}, {"key": "b"}, {"key": "c"}]
    monkeypatch.setattr(gm, "WEEKLY_THEMES", themes)
    day1 = datetime.date(2026, 7, 20)   # จันทร์
    day2 = datetime.date(2026, 7, 26)   # อาทิตย์ สัปดาห์เดียวกัน
    next_week = datetime.date(2026, 7, 27)
    assert gm.get_weekly_theme(day1) is gm.get_weekly_theme(day2)
    # ข้ามสัปดาห์: เลือกจาก seed ใหม่ (อาจซ้ำได้ แต่ต้อง deterministic ต่อสัปดาห์)
    assert gm.get_weekly_theme(next_week) is gm.get_weekly_theme(next_week)


def test_weekly_theme_none_when_empty(monkeypatch):
    monkeypatch.setattr(gm, "WEEKLY_THEMES", [])
    assert gm.get_weekly_theme() is None


# ===== ธีมจริง 2 ตัวแรก (ข้อ 5) =====

VALID_RANKS = {"Common", "Mini-Boss", "Main-Boss", "Secret", "Unbeatable"}


def test_real_themes_structure():
    keys = [t["key"] for t in gm.WEEKLY_THEMES]
    assert "palette" in keys and "zombie" in keys
    for theme in gm.WEEKLY_THEMES:
        assert theme["label"] and theme["description"]
        assert set(theme["mods"].get("monster_pool", {})) <= VALID_RANKS


def test_zombie_theme_numbers():
    zombie = next(t for t in gm.WEEKLY_THEMES if t["key"] == "zombie")
    mods = zombie["mods"]
    assert mods["event_weight_mult"] == {"monster": 1.4}
    assert mods["monster_hp_mult"] == 1.3
    assert mods["monster_dmg_mult"] == 1.2
    assert mods["monster_gold_mult"] == 2.0
    assert mods["monster_exp_mult"] == 1.5
    assert any("Zombie Titan" in n for n in mods["monster_pool"]["Mini-Boss"])


def test_palette_theme_numbers():
    palette = next(t for t in gm.WEEKLY_THEMES if t["key"] == "palette")
    assert palette["mods"]["monster_gold_mult"] == 1.5
    # มีหลายสีต่อแรงค์ให้สุ่มไม่ซ้ำ
    assert len(palette["mods"]["monster_pool"]["Common"]) >= 3


def test_demon_plus_zombie_stacking(monkeypatch):
    zombie = next(t for t in gm.WEEKLY_THEMES if t["key"] == "zombie")
    monkeypatch.setattr(gm, "WEEKLY_THEMES", [zombie])  # ธีมเดียว = สัปดาห์ไหนก็ได้ zombie
    mods = gm.get_active_modifiers({"continent": "demon"})
    assert mods["monster_hp_mult"] == pytest.approx(1.95)   # 1.5 × 1.3
    assert mods["monster_dmg_mult"] == pytest.approx(1.56)  # 1.3 × 1.2
    assert mods["monster_gold_mult"] == pytest.approx(4.0)  # 2.0 × 2.0
    assert mods["monster_exp_mult"] == pytest.approx(2.25)  # 1.5 × 1.5
    # ซอมบี้แทรกเข้า pool ควบคู่มอนสเตอร์ทวีป (ไม่แทนที่)
    common = mods["monster_pool"]["Common"]
    assert any("Imp" in n for n in common) and any("Zombie" in n for n in common)


# ===== ระบบธาตุมอนสเตอร์ =====

def test_elements_table_structure():
    assert set(gm.ELEMENTS) == {"fire", "water", "earth", "wind", "wood", "dark", "light"}
    for element in gm.ELEMENTS.values():
        assert element["label"]
    # พารามิเตอร์ตามสเปก
    assert gm.ELEMENTS["fire"]["dmg_mult"] == 1.5
    assert gm.ELEMENTS["water"]["lifesteal"] == 0.35
    assert gm.ELEMENTS["earth"]["hp_mult"] == 2.0
    assert gm.ELEMENTS["wind"]["dice_bonus"] == (2, 4)
    assert gm.ELEMENTS["wood"]["dice_bonus"] == (2, 4)
    assert gm.ELEMENTS["wood"]["root_chance"] == 25
    assert gm.ELEMENTS["dark"]["pre_enraged"] is True
    assert gm.ELEMENTS["light"]["monster_flee_chance"] == 40
    assert gm.ELEMENTS["light"]["gold_mult"] == 3.5


def test_continent_element_weights(monkeypatch):
    monkeypatch.setattr(gm, "WEEKLY_THEMES", [])
    demon = gm.get_active_modifiers({"continent": "demon"})["element_weights"]
    assert demon == {"dark": 35, "fire": 20}
    ocean = gm.get_active_modifiers({"continent": "ocean"})["element_weights"]
    assert ocean == {"water": 35, "wind": 20}
    main = gm.get_active_modifiers({"continent": "main"})["element_weights"]
    assert main == {}


def test_roll_element_valid_and_respects_weights():
    rng = __import__("random").Random(9)
    # เรทว่าง = สุ่มจากทุกธาตุ
    for _ in range(20):
        assert gm.roll_element(gm.DEFAULT_MODS, rng=rng) in gm.ELEMENTS
    # บังคับเรทเหลือธาตุเดียว → ต้องได้ธาตุนั้นเสมอ
    forced = {"element_weights": {k: 0 for k in gm.ELEMENTS} | {"water": 5}}
    for _ in range(20):
        assert gm.roll_element(forced, rng=rng) == "water"


def test_element_weights_merge_theme_over_continent(monkeypatch):
    monkeypatch.setattr(gm, "WEEKLY_THEMES", [{
        "key": "t", "mods": {"element_weights": {"dark": 50}},
    }])
    merged = gm.get_active_modifiers({"continent": "demon"})["element_weights"]
    assert merged == {"dark": 50, "fire": 20}  # ธีมทับทวีปราย key


# ===== ระบบเดินทางข้ามทวีป (ข้อ 2) =====

def test_travel_encounter_fare_within_cash():
    rng = __import__("random").Random(42)
    for cash in (0, 1, 50_000):
        enc = gm.roll_travel_encounter(cash, rng=rng)
        assert enc["vehicle"] in gm.VEHICLES
        assert enc["label"] == gm.VEHICLES[enc["vehicle"]]["label"]
        assert 0 <= enc["fare"] <= cash


def test_roll_destination_never_returns_current():
    rng = __import__("random").Random(7)
    for vehicle in gm.VEHICLES:
        for current in gm.CONTINENTS:
            for _ in range(30):
                assert gm.roll_destination(vehicle, current, rng=rng) != current


def test_roll_destination_respects_zero_weight():
    # เรือข้ามสมุทรตั้ง demon=5 — ถ้า set เป็น 0 ต้องไม่สุ่มไป demon เลย
    rng = __import__("random").Random(1)
    original = gm.VEHICLES["ship"]["dest_weights"]
    gm.VEHICLES["ship"]["dest_weights"] = {"main": 0, "demon": 0, "ocean": 100}
    try:
        for _ in range(30):
            assert gm.roll_destination("ship", "main", rng=rng) == "ocean"
    finally:
        gm.VEHICLES["ship"]["dest_weights"] = original


# ===== ผลทวีปต่อเกมเพลย์ (ข้อ 3) =====

def test_demon_continent_mods_match_approved_numbers(monkeypatch):
    monkeypatch.setattr(gm, "WEEKLY_THEMES", [])
    mods = gm.get_active_modifiers({"continent": "demon"})
    assert mods["event_weight_mult"] == {"monster": 1.5, "trap": 1.3, "village": 0.5}
    assert mods["monster_hp_mult"] == 1.5
    assert mods["monster_dmg_mult"] == 1.3
    assert mods["monster_gold_mult"] == 2.0
    assert mods["monster_exp_mult"] == 1.5
    assert "Imp" in mods["monster_pool"]["Common"][0]
    assert "Dark Curse" in mods["theme_texts"]["treasure"]
    assert "Demon Rift" in mods["theme_texts"]["trap"]


def test_ocean_continent_mods_match_approved_numbers(monkeypatch):
    monkeypatch.setattr(gm, "WEEKLY_THEMES", [])
    mods = gm.get_active_modifiers({"continent": "ocean"})
    assert mods["event_weight_mult"] == {"treasure": 1.6, "trap": 1.2}
    assert mods["monster_hp_mult"] == 1.2
    assert mods["monster_dmg_mult"] == 1.0
    assert mods["monster_gold_mult"] == 1.5
    assert mods["monster_exp_mult"] == 1.0
    assert "Ghost Pirate" in mods["monster_pool"]["Common"][0]
    assert "Tropical Storm" in mods["theme_texts"]["trap"]
    assert "Treasure Island" in mods["theme_texts"]["treasure"]


def test_pick_monster_name_themed_and_fallback(monkeypatch):
    monkeypatch.setattr(gm, "WEEKLY_THEMES", [])
    demon_mods = gm.get_active_modifiers({"continent": "demon"})
    assert "Imp" in gm.pick_monster_name(demon_mods, "Common")
    assert "Demon Lord" in gm.pick_monster_name(demon_mods, "Main-Boss")
    # แรงค์ที่ไม่มีธีม + ทวีปหลัก = None (ใช้ชื่อเดิม)
    assert gm.pick_monster_name(demon_mods, "Unbeatable") is None
    assert gm.pick_monster_name(gm.get_active_modifiers({"continent": "main"}), "Common") is None


def test_travel_chance_boundaries():
    class FakeRng:
        def __init__(self, value):
            self.value = value

        def randint(self, lo, hi):
            return self.value

    assert gm.roll_travel_chance(FakeRng(gm.TRAVEL_EVENT_CHANCE)) is True
    assert gm.roll_travel_chance(FakeRng(gm.TRAVEL_EVENT_CHANCE + 1)) is False
