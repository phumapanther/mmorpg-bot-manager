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


def test_cure_status_multi_key(game_db, monkeypatch):
    """ยาถอนพิษเวอร์ชันใหม่: effect_value เป็นลิสต์ ล้างได้ทั้งพิษและพันธนาการ"""
    _mock_catalog(monkeypatch, {"30": {"name": "🌿 ยาถอนพิษพงไพร", "type": "use",
                                        "effect": "cure_status", "effect_value": ["poison", "entangled"]}})
    uid = game_db
    # ติดพันธนาการอย่างเดียว → ล้างได้
    player_model.update_player_field(uid, "status_effects", {"entangled": 3})
    _give(uid, "30")
    ok, msg = pc.apply_item_effect(uid, "30")
    assert ok and "entangled" not in gm.parse_statuses(player_model.get_player(uid))
    # ติดทั้งคู่ → ล้างทั้งคู่ในขวดเดียว (สถานะอื่นไม่โดน)
    player_model.update_player_field(uid, "status_effects", {"poison": 10, "entangled": 2, "numb": 4})
    _give(uid, "30")
    ok, msg = pc.apply_item_effect(uid, "30")
    st = gm.parse_statuses(player_model.get_player(uid))
    assert ok and st == {"numb": 4}


def test_vine_cutter_in_catalog():
    import json
    items = json.load(open("config.example.json", encoding="utf-8"))["item_catalog"]["items"]
    assert items["54"]["effect"] == "cure_status" and items["54"]["effect_value"] == "entangled"
    assert items["54"]["purchasable"] is True
    assert items["30"]["effect_value"] == ["poison", "entangled", "spores"]  # P2 ชุด 2: ล้างสปอร์ได้ด้วย


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


def test_dye_profile_item(game_db, monkeypatch):
    uid = game_db
    _mock_catalog(monkeypatch, {"41": {"name": "🎨 ผงสีรุ้ง", "type": "use", "effect": "dye_profile"}})
    _give(uid, "41")
    # ใช้ผ่าน apply ตรงๆ (เมนูปุ่ม) = ปฏิเสธพร้อมคำแนะนำ และผงไม่หาย
    ok, msg = pc.apply_item_effect(uid, "41")
    assert not ok and "!use" in msg
    assert "41" in player_model.load_inventory(player_model.get_player(uid)["inventory"])
    # field สีโปรไฟล์มีใน schema (default 0 = ยังไม่ย้อม)
    assert player_model.get_player(uid).get("profile_color") == 0
    # ตารางสีครบ 8 และค่าใช้งานได้
    from bot.views.game_views import DYE_COLORS
    assert len(DYE_COLORS) == 8
    for label, color in DYE_COLORS:
        assert color == "rainbow" or (isinstance(color, int) and 0 <= color <= 0xFFFFFF)


def test_bag_embed_uses_profile_color():
    inventory = ["1"]
    player = {"inventory": inventory, "cash": 100, "capacity": 10, "profile_color": 0xE74C3C}
    embed = pc.build_bag_embed("Tester", "https://example.com/a.png", player)
    assert embed.color.value == 0xE74C3C
    # ไม่เคยย้อม = สีฟ้าเดิม
    embed = pc.build_bag_embed("Tester", "https://example.com/a.png", {"inventory": [], "cash": 0, "capacity": 10})
    assert embed.color.value == 0x3498DB


def test_warp_items_in_catalog():
    import json
    items = json.load(open("config.example.json", encoding="utf-8"))["item_catalog"]["items"]
    assert items["52"]["effect"] == "random_continent" and items["52"]["purchasable"] is False
    assert items["53"]["effect"] == "choose_continent" and items["53"]["purchasable"] is False
    assert "เรือเหมาลำ" in items["53"]["name"]


def test_bag_embed_survives_huge_inventory():
    """กระเป๋า 200+ ชิ้น ต้องไม่ทะลุลิมิต Discord (field 1024 / embed รวม 6000)"""
    inventory = [str(i) for i in range(1, 54)] * 4   # ทุกไอเทม ×4 แบบเคสจริง
    player = {"inventory": inventory, "cash": 999999, "capacity": 0}
    embed = pc.build_bag_embed("Tester", "https://example.com/a.png", player)
    assert embed.fields, "ต้องมี field อย่างน้อย 1"
    for field in embed.fields:
        assert len(field.value) <= 1024, f"field ยาวเกิน: {len(field.value)}"
    total = len(embed.title or "") + len(embed.description or "") + sum(
        len(f.name) + len(f.value) for f in embed.fields)
    assert total <= 6000, f"embed รวมยาวเกิน: {total}"
    # B5: จัดกลุ่มตามประเภทแล้ว — ของใช้มาก่อน และเรียงตามเลขไอเทมในกลุ่ม
    assert "ของใช้" in embed.fields[0].name
    assert embed.fields[0].value.startswith("`1` ")


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


def test_all_cure_items_reference_real_statuses():
    """ทุกไอเทม cure_status ต้องชี้ key ที่มีจริงใน STATUS_EFFECTS (กัน typo ใน config)"""
    import json
    items = json.load(open("config.example.json", encoding="utf-8"))["item_catalog"]["items"]
    for iid, it in items.items():
        if it.get("effect") != "cure_status":
            continue
        val = it.get("effect_value", "all")
        keys = val if isinstance(val, list) else [val]
        for k in keys:
            assert k == "all" or k in gm.STATUS_EFFECTS, f"item {iid} อ้างสถานะไม่มีจริง: {k}"


def test_new_cure_items_56_to_60():
    import json
    items = json.load(open("config.example.json", encoding="utf-8"))["item_catalog"]["items"]
    assert items["57"]["effect_value"] == ["numb", "fumble"]
    assert items["59"]["effect_value"] == ["odd_curse", "even_curse"]
    panacea = set(items["60"]["effect_value"])
    negatives = {"poison", "numb", "emp", "frostbite", "sealed_dice", "fumble", "burn",
                 "entangled", "odd_curse", "even_curse", "shock", "zombie_parasite", "zombie_frenzy"}
    assert panacea == negatives
    # ยาครอบจักรวาลต้องไม่แตะบัฟดี/อาร์ติแฟกต์
    assert not any(gm.STATUS_EFFECTS[k].get("artifact") for k in panacea)
