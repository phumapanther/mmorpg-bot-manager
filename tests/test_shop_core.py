"""ตรรกะร้านค้ากลาง (เว็บเกม เฟส 2) — ดึงออกจากปุ่ม Discord แล้วใช้ร่วมกันทั้งดิสและเว็บ

กติกา: พฤติกรรมฝั่งดิสต้องเหมือนเดิมเป๊ะ — ลำดับการตรวจและเงื่อนไขทุกข้อยกมาครบ
"""
import json

import pytest

import bot.models.player_model as pm
from bot import config_loader
from bot.cogs.player_commands import buy_item_for, sell_item_for


@pytest.fixture
def db(tmp_path, monkeypatch):
    monkeypatch.setattr(pm, "DB_NAME", str(tmp_path / "shop.db"))
    pm.init_db()
    pm.get_player(1)
    return pm


def _set(uid=1, **fields):
    pm.update_player_fields(uid, fields)


def test_buy_deducts_cash_and_adds_item(db):
    price = int(config_loader.get_item_config("1")["buy"])
    _set(cash=price + 500, inventory="[]", capacity=10)
    ok, msg = buy_item_for(1, "1")
    p = pm.get_player(1)
    assert ok and p["cash"] == 500
    assert "1" in pm.load_inventory(p["inventory"])
    assert "ยาฮีล" in msg


def test_buy_blocked_when_broke(db):
    _set(cash=0, inventory="[]", capacity=10)
    ok, msg = buy_item_for(1, "1")
    assert not ok and "เงินไม่พอ" in msg
    assert pm.load_inventory(pm.get_player(1)["inventory"]) == []


def test_buy_blocked_when_bag_full(db):
    """ความจุเต็ม = ซื้อไม่ได้ และต้องไม่หักเงิน"""
    price = int(config_loader.get_item_config("1")["buy"])
    _set(cash=price * 5, inventory=json.dumps(["9", "9"]), capacity=2)
    ok, msg = buy_item_for(1, "1")
    assert not ok and "กระเป๋าเต็ม" in msg
    assert pm.get_player(1)["cash"] == price * 5


def test_buy_blocked_for_unpurchasable_item(db):
    """ของที่ purchasable=false (เช่นสว่านเจาะรู/ทองคำแท่ง) ซื้อจากร้านไม่ได้"""
    unbuyable = next(i for i, d in config_loader.get_all_items().items()
                     if d.get("purchasable") is False)
    _set(cash=10**12, inventory="[]", capacity=50)
    ok, msg = buy_item_for(1, unbuyable)
    assert not ok and "ไม่สามารถซื้อ" in msg


def test_buy_unlimited_capacity_zero(db):
    """capacity = 0 คือไม่จำกัด ต้องซื้อได้เรื่อยๆ"""
    price = int(config_loader.get_item_config("1")["buy"])
    _set(cash=price * 3, inventory=json.dumps(["9"] * 50), capacity=0)
    assert buy_item_for(1, "1")[0] is True


def test_sell_adds_cash_and_removes_one(db):
    sell = int(config_loader.get_item_config("1")["sell"])
    _set(cash=0, inventory=json.dumps(["1", "1", "9"]))
    ok, _ = sell_item_for(1, "1")
    p = pm.get_player(1)
    assert ok and p["cash"] == sell
    inv = pm.load_inventory(p["inventory"])
    assert inv.count("1") == 1 and "9" in inv        # ขายทีละชิ้น ของอื่นอยู่ครบ


def test_sell_without_the_item(db):
    _set(cash=0, inventory="[]")
    ok, msg = sell_item_for(1, "1")
    assert not ok and "ไม่มีไอเทมชิ้นนี้" in msg


def test_unknown_item_both_ways(db):
    _set(cash=10**9, inventory="[]", capacity=10)
    assert buy_item_for(1, "ไม่มีจริง")[0] is False
    assert sell_item_for(1, "ไม่มีจริง")[0] is False
