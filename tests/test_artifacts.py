"""ทดสอบ V1: ระบบอาร์ติแฟกต์ช่องเดียว (สถานะถาวร + สวมทับทำลาย + ผลถาวร)"""
import pytest

import bot.models.player_model as player_model
from bot import game_modifiers as gm
from bot.cogs import player_commands as pc
from bot.views import game_views as gv


@pytest.fixture
def game_db(tmp_path, monkeypatch):
    monkeypatch.setattr(player_model, "DB_NAME", str(tmp_path / "game.db"))
    player_model.init_db()
    uid = 999
    player_model.get_player(uid)
    return uid


def _give(uid, item_id):
    inv = player_model.load_inventory(player_model.get_player(uid)["inventory"])
    inv.append(str(item_id))
    player_model.update_player_field(uid, "inventory", inv)


ARTIFACT_ITEMS = {
    "42": {"name": "🧤 ถุงมือกันคลื่น EMP", "type": "use", "effect": "equip_artifact", "effect_value": "art_emp_gauntlet"},
    "43": {"name": "🥾 รองเท้าขนนกวายุ", "type": "use", "effect": "equip_artifact", "effect_value": "art_gale_boots"},
}


def test_artifact_table_structure():
    for key in ("art_emp_gauntlet", "art_gale_boots", "art_sylvan_cloak", "art_fire_ring"):
        cfg = gm.STATUS_EFFECTS[key]
        assert cfg["artifact"] is True and cfg["no_tick"] is True
    # ไม่ tick หมดเอง
    ticked, expired = gm.tick_statuses({"art_fire_ring": 1}, "step")
    assert ticked == {"art_fire_ring": 1} and expired == []
    # แสดงเป็น ∞
    assert "(∞)" in gm.format_status_line({"art_fire_ring": 1})


def test_second_artifact_blocked_when_slots_are_full(game_db, monkeypatch):
    """ช่องเต็มแล้วต้อง 'ใส่ไม่ได้' — ไม่ใช่ทำลายของเก่าทิ้งแบบเดิม (ดีไซน์ใหม่: ระบบช่อง)"""
    uid = game_db
    monkeypatch.setattr(pc.config_loader, "get_item_config", lambda iid: ARTIFACT_ITEMS.get(str(iid)))
    _give(uid, "42")
    ok, _msg = pc.apply_item_effect(uid, "42")
    assert ok and "art_emp_gauntlet" in gm.parse_statuses(player_model.get_player(uid))

    _give(uid, "43")
    ok, msg = pc.apply_item_effect(uid, "43")
    assert not ok and "ช่องอาร์ติแฟกต์เต็ม" in msg
    statuses = gm.parse_statuses(player_model.get_player(uid))
    assert "art_emp_gauntlet" in statuses, "ของเก่าห้ามหาย"
    assert "art_gale_boots" not in statuses
    inv = player_model.load_inventory(player_model.get_player(uid).get("inventory", ""))
    assert "43" in inv, "ใส่ไม่สำเร็จ ไอเทมต้องยังอยู่ในกระเป๋า"


def test_wearing_the_same_artifact_twice_is_refused(game_db, monkeypatch):
    uid = game_db
    monkeypatch.setattr(pc.config_loader, "get_item_config", lambda iid: ARTIFACT_ITEMS.get(str(iid)))
    _give(uid, "42")
    pc.apply_item_effect(uid, "42")
    _give(uid, "42")
    ok, msg = pc.apply_item_effect(uid, "42")
    assert not ok and "อยู่แล้ว" in msg


def test_artifact_survives_cleansing(game_db):
    uid = game_db
    player_model.update_player_field(uid, "status_effects", {"art_fire_ring": 1, "poison": 10})
    # cleanse_all จากงานเลี้ยง/พร — อาร์ติแฟกต์ต้องรอด
    lines, died = gv.execute_special_outcome(uid, {"cleanse_all": True})
    statuses = gm.parse_statuses(player_model.get_player(uid))
    assert "art_fire_ring" in statuses and "poison" not in statuses


def test_artifact_passive_helpers():
    boots = {"art_gale_boots": 1}
    assert gm.status_reroll_vs(boots, "wind") == 40
    assert gm.status_reroll_vs(boots, "fire") == 0
    assert gm.status_fall_damage_mult(boots) == 0.5
    ring = {"art_fire_ring": 1}
    assert gm.status_reflect_vs(ring, "fire") == 0.2
    assert gm.status_reflect_vs(ring, "water") == 0
    cloak = {"art_sylvan_cloak": 1}
    assert gm.has_status_flag(cloak, "block_root") is True
    # เสื้อคลุมหารเลือดไหลพิษเหลือ ~20%
    import random as _r
    total, details = gm.roll_step_damage({"poison": 10, "art_sylvan_cloak": 1}, rng=_r.Random(1))
    assert 1 <= total <= 2
    # ถุงมือกัน EMP ติดไม่เข้า
    s = gm.apply_status({"art_emp_gauntlet": 1}, "emp")
    assert "emp" not in s


def test_v2_artifact_table_and_helpers():
    for key in ("art_frostward_mail", "art_nether_amulet", "art_twin_blade",
                "art_celestial_staff", "art_masquerade_monocle", "art_goddess_dicebag"):
        assert gm.STATUS_EFFECTS[key]["artifact"] is True
    # เกราะน้ำแข็ง: กันชา+เต๋าหลุดมือ
    s = gm.apply_status({"numb": 3, "fumble": 2}, "art_frostward_mail")
    assert "numb" not in s and "fumble" not in s
    assert gm.apply_status(s, "numb") == s
    # สร้อยเนเธอร์: แปลง drain เป็นฮีล 3% MaxHP + กันสาปคี่
    amulet = {"art_nether_amulet": 1}
    assert gm.STATUS_EFFECTS["art_nether_amulet"]["hp_drain_heal"] == 0.03
    assert gm.has_status_flag(amulet, "hp_drain_heal") is True
    assert gm.has_status_flag(amulet, "block_hp_drain") is False
    assert gm.apply_status(amulet, "odd_curse") == amulet
    # ดาบแฝด/คทา: ตัวคูณถาวร
    assert gm.status_combat_mult({"art_twin_blade": 1}, "player_dmg_mult") == 1.15
    assert gm.status_combat_mult({"art_celestial_staff": 1}, "exp_mult") == 1.25
    # แว่นหน้ากาก/ถุงเต๋า
    assert gm.has_status_flag({"art_masquerade_monocle": 1}, "free_inspect") is True
    assert gm.status_roll_bonus({"art_goddess_dicebag": 1}) == 1
    assert gm.status_roll_bonus({}) == 0


def test_v2_drop_sources():
    # แหล่งดรอปครบ 6: น้ำแข็ง/เนเธอร์/จักรกล/พงไพร/ตลาดมืด/โต๊ะพนันเทพี
    frozen_success = gm.CONTINENTS["frozen"]["mods"]["special_events"][0]["success"]
    assert {"id": "46", "qty": 1, "chance": 8} in frozen_success["items"]
    feast = gm.CONTINENTS["nether"]["mods"]["special_events"][0]
    blessing = next(o for o in feast["outcomes"] if o.get("cleanse_all"))
    assert {"id": "47", "qty": 1, "chance": 8} in blessing["items"]
    dig = next(e for e in gm.CONTINENTS["mechanized"]["mods"]["special_events"] if e["key"] == "ancient_excavation")
    assert {"id": "48", "qty": 1, "chance": 8} in dig["success"]["items"]
    thicket = gm.CONTINENTS["sylvan"]["mods"]["special_events"][0]
    assert {"id": "49", "qty": 1, "chance": 8} in thicket["choices"][0]["outcome"]["items"]
    market = next(t for t in gm.WEEKLY_THEMES if t["key"] == "black_market")
    monocle_choice = market["mods"]["special_events"][0]["choices"][2]
    assert {"id": "50", "qty": 1, "chance": 30} in monocle_choice["outcome"]["items"]
    goddess = next(t for t in gm.WEEKLY_THEMES if t["key"] == "goddess_dice")
    gamble = goddess["mods"]["special_events"][0]
    assert gamble["key"] == "goddess_gamble"
    assert {"id": "51", "qty": 1, "chance": 8} in gamble["success"]["items"]


def test_item_drop_chance_gate(game_db, monkeypatch):
    uid = game_db
    monkeypatch.setattr(gv.config_loader, "get_all_items", lambda: {"42": {"name": "ถุงมือ", "sell": 5000}})
    player_model.update_player_fields(uid, {"capacity": 0, "inventory": "[]"})

    class FakeRng:
        def __init__(self, rolls):
            self.rolls = list(rolls)

        def randint(self, lo, hi):
            return self.rolls.pop(0) if self.rolls else hi

        def choice(self, seq):
            return seq[0]

    # ทอยเกิน chance = ไม่ดรอป
    gv.execute_special_outcome(uid, {"items": [{"id": "42", "qty": 1, "chance": 8}]}, rng=FakeRng([9]))
    assert player_model.load_inventory(player_model.get_player(uid)["inventory"]) == []
    # ทอยเข้า chance = ดรอป
    gv.execute_special_outcome(uid, {"items": [{"id": "42", "qty": 1, "chance": 8}]}, rng=FakeRng([8]))
    assert player_model.load_inventory(player_model.get_player(uid)["inventory"]) == ["42"]


# ── 💠 เจาะรู / 🔧 ถอด (ระบบช่องอาร์ติแฟกต์) ──

SLOT_ITEMS = {
    "67": {"name": "💠 สว่านเจาะรูอาร์ติแฟกต์", "type": "use", "effect": "artifact_slot_up"},
    "68": {"name": "🔧 ชุดถอดอาร์ติแฟกต์", "type": "use", "effect": "artifact_remove"},
}


def _items(monkeypatch):
    table = {**ARTIFACT_ITEMS, **SLOT_ITEMS}
    monkeypatch.setattr(pc.config_loader, "get_item_config", lambda iid: table.get(str(iid)))
    return table


def test_punch_adds_a_slot_and_lets_you_wear_more(game_db, monkeypatch):
    uid = game_db
    _items(monkeypatch)
    _give(uid, "42")
    pc.apply_item_effect(uid, "42")

    _give(uid, "67")
    ok, msg = pc.apply_item_effect(uid, "67")
    assert ok and "1 → **2**" in msg
    assert player_model.get_player(uid)["artifact_slots"] == 2

    _give(uid, "43")
    ok, _msg = pc.apply_item_effect(uid, "43")
    assert ok, "เจาะช่องแล้วต้องใส่ชิ้นที่สองได้"
    statuses = gm.parse_statuses(player_model.get_player(uid))
    assert {"art_emp_gauntlet", "art_gale_boots"} <= set(statuses)


def test_punch_stops_at_the_cap(game_db, monkeypatch):
    uid = game_db
    _items(monkeypatch)
    cap = int(pc.config_loader.get_balance("artifact.max_slots", 5))
    player_model.update_player_field(uid, "artifact_slots", cap)
    _give(uid, "67")
    ok, msg = pc.apply_item_effect(uid, "67")
    assert not ok and f"{cap} ช่อง" in msg
    inv = player_model.load_inventory(player_model.get_player(uid).get("inventory", ""))
    assert "67" in inv, "เจาะไม่ได้ = สว่านต้องไม่หาย"
    assert player_model.get_player(uid)["artifact_slots"] == cap


def test_slots_never_exceed_the_cap_even_if_db_is_weird(monkeypatch):
    cap = int(pc.config_loader.get_balance("artifact.max_slots", 5))
    assert gm.artifact_slots({"artifact_slots": 99}) == cap
    assert gm.artifact_slots({"artifact_slots": 0}) == 1
    assert gm.artifact_slots({}) == 1


def test_remover_opens_a_menu_instead_of_burning_itself(game_db, monkeypatch):
    uid = game_db
    _items(monkeypatch)
    _give(uid, "68")
    ok, msg = pc.apply_item_effect(uid, "68")
    assert not ok and "`!use`" in msg
    inv = player_model.load_inventory(player_model.get_player(uid).get("inventory", ""))
    assert "68" in inv, "ชุดถอดต้องไม่ถูกใช้จนกว่าจะเลือกชิ้น"


def test_remove_returns_the_artifact_to_the_bag(game_db, monkeypatch):
    """ถอดแล้วของต้องกลับเข้ากระเป๋า ไม่ใช่หายไปเฉย ๆ (ของราคาแพง)"""
    import asyncio
    from types import SimpleNamespace

    import bot.views.game_views as gv2
    uid = game_db
    _items(monkeypatch)
    _give(uid, "42")
    pc.apply_item_effect(uid, "42")
    _give(uid, "68")

    monkeypatch.setattr(gv2.config_loader, "get_all_items",
                        lambda: {**ARTIFACT_ITEMS, **SLOT_ITEMS})
    monkeypatch.setattr(gv2.config_loader, "get_item_config",
                        lambda iid: {**ARTIFACT_ITEMS, **SLOT_ITEMS}.get(str(iid), {}))

    view = gv2.ArtifactRemoveView(uid, "68", ["art_emp_gauntlet"])
    select = view.children[0]
    select._values = ["art_emp_gauntlet"]
    monkeypatch.setattr(type(select), "values", property(lambda s: ["art_emp_gauntlet"]))

    sent = {}

    class Resp:
        async def edit_message(self, **kw):
            sent.update(kw)

    asyncio.run(select.callback(SimpleNamespace(response=Resp(), user=SimpleNamespace(id=uid))))

    player = player_model.get_player(uid)
    assert "art_emp_gauntlet" not in gm.parse_statuses(player), "ต้องถอดออกจริง"
    inv = player_model.load_inventory(player.get("inventory", ""))
    assert "42" in inv, "อาร์ติแฟกต์ต้องกลับเข้ากระเป๋า"
    assert "68" not in inv, "ชุดถอดถูกใช้ไปแล้ว"
    assert "ถอด" in sent.get("content", "")


def test_punch_drops_only_from_unbeatable():
    import pathlib
    src = pathlib.Path("bot/adventure_core.py").read_text(encoding="utf-8")
    block = src[src.index("# 💠 สว่านเจาะรูอาร์ติแฟกต์"):]
    guard = block[:block.index("try:")]
    assert 'monster_rank == "Unbeatable"' in guard, "ต้องดรอปจากไร้พ่ายเท่านั้น"
    assert "artifact.punch_drop_chance" in block


def test_item_catalog_setup():
    import json
    cfg = json.load(open("config.example.json", encoding="utf-8"))
    items = cfg["item_catalog"]["items"]
    art = cfg["game_balance"]["artifact"]
    assert art["max_slots"] == 5
    assert art["punch_drop_chance"] >= 80, "ผู้ใช้ขอเรทสูงมาก แทบได้ทุกครั้งที่ชนะ"

    punch = items[str(art["punch_item"])]
    assert punch["purchasable"] is False, "สว่านต้องดรอปอย่างเดียว ห้ามมีขาย"
    assert punch["effect"] == "artifact_slot_up"

    remover = next(i for i in items.values() if i.get("effect") == "artifact_remove")
    assert remover["purchasable"] is True and remover["buy"] >= 1000000, "ชุดถอดซื้อได้และแพง"

    recipes = cfg["item_catalog"]["crafting_recipes"]
    assert str(art["punch_item"]) not in recipes, "สว่านห้ามคราฟได้ (ต้องล่าไร้พ่ายเท่านั้น)"
