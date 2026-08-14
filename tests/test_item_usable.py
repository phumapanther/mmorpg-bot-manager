"""⚔️ ของชิ้นไหน "กดใช้ได้" — หน้าเว็บต้องถามที่เดียวกับตัวที่ใช้จริง

บั๊กที่เจอ: หน้าเว็บเดากฎเองว่า "ต้องมี effect และ type=use" อาวุธกับเกราะไม่เข้าเงื่อนไข
ทั้งคู่ เลยไม่มีปุ่มสวมใส่โผล่มาสักที ผู้เล่นซื้ออาวุธมาแล้วใส่ไม่ได้เลยทั้งเกม
"""
import json
import pathlib

import pytest

import bot.models.player_model as player_model
from bot import config_loader
from bot.cogs import player_commands as pc

API = pathlib.Path("license_server/web_api.py").read_text(encoding="utf-8")


@pytest.fixture
def game_db(tmp_path, monkeypatch):
    monkeypatch.setattr(player_model, "DB_NAME", str(tmp_path / "game.db"))
    player_model.init_db()
    uid = 777
    player_model.get_player(uid)
    return uid


def _give(uid, item_id):
    inv = player_model.load_inventory(player_model.get_player(uid)["inventory"])
    inv.append(str(item_id))
    player_model.update_player_field(uid, "inventory", inv)


def test_equipment_counts_as_usable():
    assert pc.usable_kind({"type": "weapon", "equip_key": "Iron_Weapon"}) == "equip"
    assert pc.usable_kind({"type": "armor", "equip_key": "Leather_L"}) == "equip"
    assert pc.usable_kind({"type": "bag", "equip_key": "Large_Bag"}) == "equip"
    assert pc.usable_kind({"type": "use", "effect": "heal"}) == "use"
    assert pc.usable_kind({"type": "junk", "sell": 10}) == ""      # ของขาย ไม่มีปุ่มใช้
    assert pc.usable_kind({"type": "drop"}) == ""                  # ไม่ตั้ง effect = กดไม่ได้จริง
    assert pc.usable_kind({}) == "" and pc.usable_kind(None) == ""


def test_every_equipment_in_the_real_catalog_can_be_worn():
    """ไล่ของจริงทั้งตู้ — ของที่มี equip_key ต้องขึ้นปุ่มสวมใส่ทุกชิ้น ไม่มีตกหล่น"""
    worn = [iid for iid, d in config_loader.get_all_items().items() if d.get("equip_key")]
    assert worn, "ตู้ไอเทมไม่มีอุปกรณ์สวมใส่เลย — config โหลดพลาด"
    for iid in worn:
        d = config_loader.get_all_items()[iid]
        assert pc.usable_kind(d) == "equip", f"ไอเทม {iid} {d.get('name')} สวมไม่ได้"


def test_wearing_a_weapon_from_the_bag_actually_equips_it(game_db):
    """เทสของจริง: หยิบอาวุธเหล็กในกระเป๋ามาใส่ แล้วช่องอาวุธต้องเปลี่ยนจริง"""
    uid = game_db
    iron = next(iid for iid, d in config_loader.get_all_items().items()
                if d.get("equip_key") == "Iron_Weapon")
    _give(uid, iron)

    ok, msg = pc.apply_item_effect(uid, iron)
    assert ok, msg
    p = player_model.get_player(uid)
    assert p["weapon"] == "Iron_Weapon"
    assert p["weapon_dur"] > 0                                    # ความคงทนเต็มหลอดตอนใส่
    assert iron not in player_model.load_inventory(p["inventory"])  # ของถูกใช้ไป


def test_the_web_does_not_invent_its_own_rule():
    """เว็บห้ามคิดกฎ 'ใช้ได้' เอง — ต้องเรียก usable_kind() ตัวเดียวกับที่ใช้จริง"""
    assert 'bool(it.get("effect")) and it.get("type") == "use"' not in API
    assert 'bool(d.get("effect")) and d.get("type") == "use"' not in API
    assert API.count("usable_kind(") >= 3


def test_you_can_buy_something_that_refills_mana():
    """มานาหมดแล้วต้องมีทางเติมด้วยเงิน ไม่ใช่รอวันใหม่อย่างเดียว"""
    shop = {iid: d for iid, d in config_loader.get_all_items().items()
            if d.get("purchasable", True)}
    refill = [d for d in shop.values() if d.get("effect") == "mana"]
    assert refill, "ร้านค้าไม่มีของเติมมานาขายเลย"
    for d in refill:
        assert int(d.get("effect_amount", 0)) >= 1
        assert int(d["buy"]) > int(d["sell"]), "ซื้อถูกกว่าขาย = เครื่องปั๊มเงิน"


def test_the_shipped_config_matches_the_live_one_for_that_item():
    """config.example.json คือแม่แบบที่คนอื่นเอาไปตั้งเซิร์ฟ ต้องมีของเติมมานาขายด้วย"""
    ex = json.loads(pathlib.Path("config.example.json").read_text(encoding="utf-8"))
    items = ex["item_catalog"]["items"]
    assert any(d.get("effect") == "mana" and d.get("purchasable", True)
               for d in items.values()), "แม่แบบ config ไม่มีของเติมมานาขายในร้าน"
