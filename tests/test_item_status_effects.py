"""ทดสอบ S1: item effects แก้/เสกสถานะ + เสบียงฉุกเฉิน (ผ่าน apply_item_effect กับ DB จำลอง)"""
import pytest

import bot.models.player_model as player_model
from bot import game_modifiers as gm
from bot.cogs import player_commands as pc


@pytest.fixture
def game_db(tmp_path, monkeypatch):
    monkeypatch.setattr(player_model, "DB_NAME", str(tmp_path / "game.db"))
    player_model.init_db()
    uid = 555
    player_model.get_player(uid)
    return uid


def _give(uid, item_id):
    inv = player_model.load_inventory(player_model.get_player(uid)["inventory"])
    inv.append(str(item_id))
    player_model.update_player_field(uid, "inventory", inv)


def _mock_catalog(monkeypatch, items):
    monkeypatch.setattr(pc.config_loader, "get_item_config", lambda iid: items.get(str(iid)))


def test_cure_status_item(game_db, monkeypatch):
    uid = game_db
    _mock_catalog(monkeypatch, {"30": {"name": "🌿 ยาถอนพิษพงไพร", "type": "use",
                                        "effect": "cure_status", "effect_value": "poison"}})
    _give(uid, "30")
    player_model.update_player_field(uid, "status_effects", {"poison": 12, "numb": 3})

    ok, msg = pc.apply_item_effect(uid, "30")
    assert ok and "พิษป่า" in msg
    p = player_model.get_player(uid)
    assert gm.parse_statuses(p) == {"numb": 3}          # แก้เฉพาะพิษ ตัวอื่นอยู่ครบ
    assert "30" not in player_model.load_inventory(p["inventory"])  # ไอเทมถูกใช้ทิ้ง

    # ไม่มีสถานะเป้าหมาย = ใช้ไม่ได้ ไอเทมไม่หาย
    _give(uid, "30")
    ok, msg = pc.apply_item_effect(uid, "30")
    assert not ok
    assert "30" in player_model.load_inventory(player_model.get_player(uid)["inventory"])


def test_apply_status_item(game_db, monkeypatch):
    uid = game_db
    _mock_catalog(monkeypatch, {"40": {"name": "ยาโด๊ปทดสอบ", "type": "use",
                                        "effect": "apply_status", "effect_value": "exp_blessing",
                                        "effect_amount": 25}})
    _give(uid, "40")
    ok, msg = pc.apply_item_effect(uid, "40")
    assert ok
    assert gm.parse_statuses(player_model.get_player(uid)) == {"exp_blessing": 25}


def test_emergency_ration(game_db, monkeypatch):
    uid = game_db
    _mock_catalog(monkeypatch, {"31": {"name": "🥫 กล่องเสบียงฉุกเฉิน", "type": "use",
                                        "effect": "emergency_ration"}})
    _give(uid, "31")
    player_model.update_player_fields(uid, {"hp": 10, "max_hp": 100})
    ok, msg = pc.apply_item_effect(uid, "31")
    assert ok and "60/100" in msg      # 10 + 50% ของ 100


def test_random_continent_warp_item(game_db, monkeypatch):
    uid = game_db
    _mock_catalog(monkeypatch, {"52": {"name": "🌀 ประตูวาร์ปมิติ", "type": "use", "effect": "random_continent"}})
    # ติดสู้อยู่ = ใช้ไม่ได้ ไอเทมไม่หาย
    _give(uid, "52")
    player_model.update_player_fields(uid, {"current_state": "fighting", "continent": "main"})
    ok, msg = pc.apply_item_effect(uid, "52")
    assert not ok and "52" in player_model.load_inventory(player_model.get_player(uid)["inventory"])
    # สถานะปกติ = วาร์ปสำเร็จ ไปทวีปอื่น (ไม่ซ้ำ main) + ไอเทมถูกใช้
    player_model.update_player_fields(uid, {"current_state": "idle", "dungeon_steps": 0})
    ok, msg = pc.apply_item_effect(uid, "52")
    p = player_model.get_player(uid)
    assert ok
    assert p["continent"] != "main" and p["continent"] in gm.CONTINENTS
    assert p["last_event"] == "none"
    assert "52" not in player_model.load_inventory(p["inventory"])


def test_choose_continent_ticket_not_consumed_via_apply(game_db, monkeypatch):
    uid = game_db
    _mock_catalog(monkeypatch, {"53": {"name": "🎫 ตั๋วเรือเหมาลำ", "type": "use", "effect": "choose_continent"}})
    _give(uid, "53")
    ok, msg = pc.apply_item_effect(uid, "53")
    # ใช้ผ่าน apply ตรงๆ (เช่นปุ่มเมนู) = ปฏิเสธพร้อมคำแนะนำ และตั๋วไม่หาย
    assert not ok and "!use" in msg
    assert "53" in player_model.load_inventory(player_model.get_player(uid)["inventory"])


def test_warp_items_in_catalog():
    import json
    items = json.load(open("config.example.json", encoding="utf-8"))["item_catalog"]["items"]
    assert items["52"]["effect"] == "random_continent" and items["52"]["purchasable"] is False
    assert items["53"]["effect"] == "choose_continent" and items["53"]["purchasable"] is False
    assert "เรือเหมาลำ" in items["53"]["name"]


def test_on_hit_status_merge_and_default(monkeypatch):
    # ระดับทวีป/ธีมผ่าน mods (replace) + ระดับธาตุผ่าน element_overrides
    assert gm.DEFAULT_MODS["on_hit_status"] is None
    monkeypatch.setitem(gm.CONTINENTS, "testland", {
        "label": "t",
        "mods": {
            "on_hit_status": {"key": "numb", "chance": 30},
            "element_overrides": {"fire": {"on_hit_status": {"key": "poison", "chance": 25}}},
        },
    })
    monkeypatch.setattr(gm, "WEEKLY_THEMES", [])
    mods = gm.get_active_modifiers({"continent": "testland"})
    assert mods["on_hit_status"] == {"key": "numb", "chance": 30}
    assert gm.get_element_data(mods, "fire")["on_hit_status"] == {"key": "poison", "chance": 25}
    assert "on_hit_status" not in gm.get_element_data(mods, "water")
