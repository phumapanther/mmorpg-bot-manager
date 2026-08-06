"""🧈 ทองคำแท่ง: แลกซื้อ/ขายคืนที่ธนาคาร (fee flat) + โจรฉกของแพง top 5 + กันปุ่มขายวัสดุเทขายแท่ง"""
import json
import random

import bot.models.player_model as pm
from bot import config_loader, gold_bars, robbery
from bot.cogs.player_commands import sell_all_junk

_BARS = {
    "72": {"name": "🧈 ทองคำแท่ง 1M", "buy": 1_000_000, "sell": 850_000, "type": "gold_bar", "bar_value": 1_000_000},
    "73": {"name": "🧈 ทองคำแท่ง 10M", "buy": 10_000_000, "sell": 8_500_000, "type": "gold_bar", "bar_value": 10_000_000},
}
_CATALOG = {**_BARS,
            "1": {"name": "💉 ยาฮีล", "buy": 300, "sell": 100, "type": "use", "effect": "heal"},
            "9": {"name": "🦴 เศษกระดูก", "buy": 100, "sell": 10, "type": "junk"}}


def _fake(monkeypatch, players):
    monkeypatch.setattr(pm, "get_player", lambda uid: players.get(uid))

    def update(uid, field, value):
        players[uid][field] = value
    monkeypatch.setattr(pm, "update_player_field", update)
    monkeypatch.setattr(pm, "update_player_fields", lambda uid, fields: players[uid].update(fields))
    monkeypatch.setattr(config_loader, "get_balance", lambda k, d=None: d)
    monkeypatch.setattr(config_loader, "get_all_items", lambda: _CATALOG)
    monkeypatch.setattr(config_loader, "get_item_config", lambda iid: dict(_CATALOG.get(str(iid), {})))
    return players


def test_buy_bar_deducts_bank_with_fee(monkeypatch):
    p = _fake(monkeypatch, {1: {"cash": 0, "bank": 2_000_000, "capacity": 10, "inventory": "[]"}})
    ok, msg = gold_bars.buy_bar(1, "72")     # 1M + 5% = 1,050,000
    assert ok and p[1]["bank"] == 950_000
    assert json.loads(p[1]["inventory"]) == ["72"]
    ok, _ = gold_bars.buy_bar(1, "72")       # เงินไม่พอรอบสอง
    assert not ok


def test_sell_bar_credits_bank_minus_fee(monkeypatch):
    p = _fake(monkeypatch, {1: {"cash": 0, "bank": 0, "capacity": 10, "inventory": '["72"]'}})
    ok, _ = gold_bars.sell_bar(1, "72")      # ได้ 1M - 5% = 950,000
    assert ok and p[1]["bank"] == 950_000 and json.loads(p[1]["inventory"]) == []
    assert gold_bars.sell_bar(1, "72")[0] is False   # ไม่มีแท่งแล้ว


def test_buy_bar_respects_capacity(monkeypatch):
    _fake(monkeypatch, {1: {"cash": 0, "bank": 99_000_000, "capacity": 1, "inventory": '["1"]'}})
    assert gold_bars.buy_bar(1, "72")[0] is False


def test_steal_chance_tiers(monkeypatch):
    _fake(monkeypatch, {})
    assert robbery.steal_chance(500_000) == 0
    assert robbery.steal_chance(1_000_000) == 10
    assert robbery.steal_chance(10_000_000) == 20
    assert robbery.steal_chance(100_000_000) == 30
    assert robbery.steal_chance(1_000_000_000) == 40


def test_roll_item_theft_takes_most_valuable(monkeypatch):
    _fake(monkeypatch, {})
    rng = random.Random(7)
    inv = ["1", "72", "9", "1", "73"]
    hits = []
    for _ in range(300):
        taken = robbery.roll_item_theft(inv, 1_000_000_000, _CATALOG, rng)   # 40%
        assert len(taken) <= 2
        hits.extend(inv[i] for i in taken)
    assert hits, "ที่ 40% ทอย 300 รอบต้องโดนบ้าง"
    # ของแพงสุด (แท่ง 10M) ต้องโดนบ่อยกว่าเศษกระดูก และเศษกระดูกอยู่อันดับ 5 ยังโดนได้
    assert hits.count("73") > 0 and hits.count("73") >= hits.count("9")
    # จนกว่าเกณฑ์ = ไม่โดนเลย
    assert all(not robbery.roll_item_theft(inv, 500_000, _CATALOG, rng) for _ in range(100))


def test_sell_all_junk_keeps_gold_bars(monkeypatch):
    p = _fake(monkeypatch, {1: {"cash": 0, "bank": 0, "capacity": 10,
                                "inventory": json.dumps(["9", "72", "9", "73"])}})
    sold, gold, _msg = sell_all_junk(1)
    assert sold == 2 and gold == 20                       # ขายเฉพาะเศษกระดูก 2 ชิ้น
    assert json.loads(p[1]["inventory"]) == ["72", "73"]  # แท่งทองอยู่ครบ
