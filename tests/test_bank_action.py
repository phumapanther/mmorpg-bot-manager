"""bank_action: ตรรกะกลาง ฝาก/ถอน/โอน ที่คำสั่งพิมพ์และปุ่มเมนูใช้ร่วมกัน + ค่าธรรมเนียมตามยอด"""
import time

import bot.cogs.player_commands as pc


def _fake_db(monkeypatch, players):
    def get_player(uid):
        return players.get(uid)

    def update(uid, field, value):
        players[uid][field] = value

    monkeypatch.setattr(pc.player_model, "get_player", get_player)
    monkeypatch.setattr(pc.player_model, "update_player_field", update)
    # กันค่า bank.fee_tiers ใน config เครื่องจริงรั่วเข้าเทส — บังคับใช้ขั้น default
    monkeypatch.setattr(pc.config_loader, "get_balance", lambda key, default=None: default)
    return players


def test_bank_fee_tiers(monkeypatch):
    _fake_db(monkeypatch, {})
    assert pc.bank_fee(50_000) == (2_500, 5)            # <1แสน = 5%
    assert pc.bank_fee(100_000) == (10_000, 10)         # 1แสน–1ล้าน = 10%
    assert pc.bank_fee(5_000_000) == (1_000_000, 20)    # 1–10ล้าน = 20%
    assert pc.bank_fee(50_000_000) == (17_500_000, 35)  # 10–100ล้าน = 35%
    assert pc.bank_fee(200_000_000) == (100_000_000, 50)  # ≥100ล้าน = 50%


def test_deposit_and_withdraw_with_fee(monkeypatch):
    p = _fake_db(monkeypatch, {1: {"cash": 100, "bank": 50}})
    ok, msg = pc.bank_action(1, "deposit", 60)       # fee 5% = 3
    assert ok and p[1]["cash"] == 40 and p[1]["bank"] == 107
    assert "ค่าธรรมเนียม" in msg
    ok, _ = pc.bank_action(1, "withdraw", 107)       # fee 5% = 5
    assert ok and p[1]["cash"] == 142 and p[1]["bank"] == 0


def test_insufficient_and_bad_amount(monkeypatch):
    _fake_db(monkeypatch, {1: {"cash": 10, "bank": 5}})
    assert pc.bank_action(1, "deposit", 999)[0] is False
    assert pc.bank_action(1, "withdraw", 999)[0] is False
    assert pc.bank_action(1, "deposit", 0)[0] is False
    assert pc.bank_action(1, "deposit", -5)[0] is False


def test_transfer_rules(monkeypatch):
    p = _fake_db(monkeypatch, {1: {"cash": 0, "bank": 100}, 2: {"cash": 0, "bank": 0}})
    assert pc.bank_action(1, "transfer", 30, target_id=1)[0] is False   # โอนให้ตัวเอง
    assert pc.bank_action(1, "transfer", 30, target_id=99)[0] is False  # ผู้รับไม่มีตัวตน
    ok, _ = pc.bank_action(1, "transfer", 30, target_id=2)              # fee 5% = 1
    assert ok and p[1]["bank"] == 70 and p[2]["bank"] == 29


def test_arrested_blocked(monkeypatch):
    _fake_db(monkeypatch, {1: {"cash": 100, "bank": 100, "current_state": "arrested",
                               "arrest_until": time.time() + 600}})
    assert pc.bank_action(1, "deposit", 10)[0] is False
    assert pc.bank_action(1, "withdraw", 10)[0] is False


def test_unknown_player_and_action(monkeypatch):
    _fake_db(monkeypatch, {})
    assert pc.bank_action(42, "deposit", 10)[0] is False
    _fake_db(monkeypatch, {1: {"cash": 10, "bank": 10}})
    assert pc.bank_action(1, "explode", 10)[0] is False
