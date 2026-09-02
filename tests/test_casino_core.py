"""ตรรกะคาสิโนกลาง — สูตรตุกติกและเรทจ่ายต้องตรงกับของเดิมในดิสเป๊ะ"""
import random

import pytest

import bot.models.player_model as pm
from bot import casino_core as cc
from bot import config_loader


@pytest.fixture
def db(tmp_path, monkeypatch):
    monkeypatch.setattr(pm, "DB_NAME", str(tmp_path / "c.db"))
    monkeypatch.setattr(config_loader, "get_balance", lambda k, d=None: d)
    pm.init_db()
    pm.get_player(1)
    return pm


# ── สูตรตุกติก (ยกมาจากโค้ดเดิม) ──

@pytest.mark.parametrize("bet,expect", [
    (0, 0.0), (10000, 0.15), (20000, 0.30), (100000, 0.85), (10**9, 0.85),
])
def test_hilo_rig_chance(bet, expect):
    assert cc.hilo_rig_chance(bet) == pytest.approx(expect)


@pytest.mark.parametrize("bet,expect", [
    (10000, 0.15), (60000, 0.90), (10**9, 0.90),
])
def test_slots_rig_chance_cap_is_higher(bet, expect):
    assert cc.slots_rig_chance(bet) == pytest.approx(expect)


# ── เรทจ่าย ──

def test_slots_multiplier_table():
    assert cc.slots_multiplier(["💰"] * 3) == 15
    assert cc.slots_multiplier(["💎"] * 3) == 10
    assert cc.slots_multiplier(["🔔"] * 3) == 7
    assert cc.slots_multiplier(["🍒"] * 3) == 5
    assert cc.slots_multiplier(["🍒", "🍒", "💰"]) == 1.5
    assert cc.slots_multiplier(["🍒", "🍇", "💰"]) == 0


def test_hilo_pays_2x_and_11hilo_pays_7x(db):
    pm.update_player_fields(1, {"cash": 1000})
    ok, out = cc.play_hilo(1, "high", 100, rng=random.Random(1))
    assert ok
    # เงินสุทธิต้องตรงกับผลที่คืนมาเสมอ
    assert pm.get_player(1)["cash"] == 1000 + out["net"]
    assert out["winnings"] in (0, 200)


def test_hilo_11hilo_multiplier(db, monkeypatch):
    pm.update_player_fields(1, {"cash": 10000})
    # แพตช์ที่โมดูลจริง ไม่ใช่ที่สะพาน bot.casino_core
    # (Python มอง global ของไฟล์ที่ฟังก์ชันถูกนิยาม แพตช์ที่สะพานจะไม่มีผล)
    from bot.games.casino.hilo import core as hilo_core
    monkeypatch.setattr(hilo_core, "roll_hilo", lambda c, b, rng=None: {
        "dice": [5, 3, 3], "total": 11, "result": "11hilo", "rigged": False, "won": True})
    ok, out = cc.play_hilo(1, "11hilo", 100)
    assert ok and out["winnings"] == 700 and out["net"] == 600
    assert pm.get_player(1)["cash"] == 10600


# ── กติกาการหักเงิน ──

def test_cannot_bet_more_than_you_have(db):
    pm.update_player_fields(1, {"cash": 50})
    ok, out = cc.play_hilo(1, "high", 100)
    assert not ok and "ไม่พอ" in out["message"]
    assert pm.get_player(1)["cash"] == 50, "แพ้ตอนตรวจแล้วห้ามหักเงิน"


def test_bet_must_be_positive(db):
    pm.update_player_fields(1, {"cash": 500})
    assert cc.play_hilo(1, "high", 0)[0] is False
    assert cc.play_slots(1, -5)[0] is False
    assert pm.get_player(1)["cash"] == 500


def test_bad_choice_rejected_without_charging(db):
    pm.update_player_fields(1, {"cash": 500})
    ok, _ = cc.play_hilo(1, "กลาง", 100)
    assert not ok and pm.get_player(1)["cash"] == 500


# ── ระบบตุกติกทำงานจริง ──

def test_rigging_pushes_wins_down(db):
    """เดิมพันสูง (ตุกติก 85%) ต้องชนะน้อยกว่าเดิมพันต่ำอย่างเห็นได้ชัด"""
    rng = random.Random(7)
    low = sum(cc.roll_hilo("high", 100, rng)["won"] for _ in range(600))
    high = sum(cc.roll_hilo("high", 10**6, rng)["won"] for _ in range(600))
    assert high < low / 3, f"ตุกติกไม่ทำงาน (เดิมพันต่ำชนะ {low}, สูงชนะ {high})"


def test_slot_rigging_pushes_matches_down(db):
    rng = random.Random(11)
    low = sum(cc.slots_multiplier(cc.spin_slots(100, rng)["reels"]) > 0 for _ in range(600))
    high = sum(cc.slots_multiplier(cc.spin_slots(10**6, rng)["reels"]) > 0 for _ in range(600))
    assert high < low / 3


def test_slot_weights_fall_back_when_panel_value_is_broken(db, monkeypatch):
    monkeypatch.setattr(config_loader, "get_balance", lambda k, d=None: [1, 2, 3])   # ไม่ครบ 6
    assert cc.slot_weights() == cc.DEFAULT_SLOT_WEIGHTS
    monkeypatch.setattr(config_loader, "get_balance", lambda k, d=None: "มั่ว")
    assert cc.slot_weights() == cc.DEFAULT_SLOT_WEIGHTS
