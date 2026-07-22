"""ทดสอบแกน game_modifiers — ล็อกกติกา: identity ไม่เปลี่ยนเกม, กติการวมผล, ธีมสัปดาห์ deterministic"""
import datetime

import pytest

from bot import game_modifiers as gm


def test_default_is_identity():
    mods = gm.get_active_modifiers({"continent": "main"})
    assert mods["monster_hp_mult"] == 1.0
    assert mods["monster_gold_mult"] == 1.0
    assert mods["monster_exp_mult"] == 1.0
    assert mods["event_weight_mult"] == {}
    assert mods["monster_pool"] == []
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
            "monster_pool": ["Imp"],
            "theme_texts": {"treasure": "หีบทดสอบ"},
        },
    })
    monkeypatch.setattr(gm, "WEEKLY_THEMES", [{
        "key": "testweek",
        "mods": {
            "monster_hp_mult": 1.5,
            "event_weight_mult": {"monster": 2.0},
            "monster_pool": ["Zombie"],
            "theme_texts": {"treasure": "หีบซอมบี้"},
        },
    }])

    mods = gm.get_active_modifiers({"continent": "testland"})
    assert mods["monster_hp_mult"] == pytest.approx(3.0)          # 2.0 × 1.5
    assert mods["event_weight_mult"]["monster"] == pytest.approx(3.0)  # 1.5 × 2.0
    assert mods["monster_pool"] == ["Imp", "Zombie"]              # ต่อกัน
    assert mods["theme_texts"]["treasure"] == "หีบซอมบี้"          # ธีมสัปดาห์ทับทวีป
    # ตัวอื่นยังเป็น identity
    assert mods["monster_gold_mult"] == 1.0

    weights = gm.apply_event_weights([10, 20, 30], ["monster", "village", "treasure"], mods)
    assert weights == [pytest.approx(30.0), 20, 30]

    # DEFAULT_MODS ต้องไม่ถูกแก้ไขข้างเคียง
    assert gm.DEFAULT_MODS["monster_hp_mult"] == 1.0
    assert gm.DEFAULT_MODS["monster_pool"] == []


def test_weekly_theme_deterministic(monkeypatch):
    themes = [{"key": "a"}, {"key": "b"}, {"key": "c"}]
    monkeypatch.setattr(gm, "WEEKLY_THEMES", themes)
    day1 = datetime.date(2026, 7, 20)   # จันทร์
    day2 = datetime.date(2026, 7, 26)   # อาทิตย์ สัปดาห์เดียวกัน
    next_week = datetime.date(2026, 7, 27)
    assert gm.get_weekly_theme(day1) is gm.get_weekly_theme(day2)
    # ข้ามสัปดาห์: เลือกจาก seed ใหม่ (อาจซ้ำได้ แต่ต้อง deterministic ต่อสัปดาห์)
    assert gm.get_weekly_theme(next_week) is gm.get_weekly_theme(next_week)


def test_weekly_theme_none_when_empty():
    assert gm.get_weekly_theme() is None


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


def test_travel_chance_boundaries():
    class FakeRng:
        def __init__(self, value):
            self.value = value

        def randint(self, lo, hi):
            return self.value

    assert gm.roll_travel_chance(FakeRng(gm.TRAVEL_EVENT_CHANCE)) is True
    assert gm.roll_travel_chance(FakeRng(gm.TRAVEL_EVENT_CHANCE + 1)) is False
