"""P2 ชุด 1: เลือดไหล + ผ้าพันแผล"""
import json
import random

import bot.game_modifiers as gm


def test_bleed_status():
    b = gm.STATUS_EFFECTS["bleed"]
    assert b["tick"] == "step" and b["default_turns"] == 5
    total, details = gm.roll_step_damage({"bleed": 3}, rng=random.Random(1))
    assert 4 <= total <= 8 and details[0][0] == b["label"]


def test_demon_inflicts_bleed():
    mods = gm.get_active_modifiers({"continent": "demon"})
    assert mods["on_hit_status"] == {"key": "bleed", "chance": 15}


def test_bandage_item_cures_bleed():
    it = json.load(open("config.example.json", encoding="utf-8"))["item_catalog"]["items"]["61"]
    assert it["effect"] == "cure_status" and it["effect_value"] == "bleed"
    assert it["purchasable"] is True and it["buy"] == 800


# ── P2 ชุด 2: เห็ดราซิลวาน ──

def test_spores_stack_then_bloom():
    s = gm.apply_status({}, "spores")
    s = gm.apply_status(s, "spores")
    assert s.get("spores") == 2 and "mushroom_bloom" not in s
    s = gm.apply_status(s, "spores")  # ครบ 3 → เห็ดบาน
    assert "spores" not in s
    assert s.get("mushroom_bloom") == gm.STATUS_EFFECTS["mushroom_bloom"]["default_turns"]


def test_bloom_pct_damage_and_roll_penalty():
    total, details = gm.roll_step_damage({"mushroom_bloom": 6}, rng=random.Random(1), max_hp=200)
    assert total == 10  # 5% ของ 200
    # เสื้อคลุมเปลือกไม้หารเบา: 10 × 0.2 = 2
    total2, _ = gm.roll_step_damage({"mushroom_bloom": 6, "art_sylvan_cloak": 1}, rng=random.Random(1), max_hp=200)
    assert total2 == 2
    assert gm.status_roll_bonus({"mushroom_bloom": 6}) == -1


def test_sylvan_inflicts_spores_and_antidote_cures():
    mods = gm.get_active_modifiers({"continent": "sylvan"})
    assert mods["on_hit_status"] == {"key": "spores", "chance": 20}
    it = json.load(open("config.example.json", encoding="utf-8"))["item_catalog"]["items"]["30"]
    assert "spores" in it["effect_value"]


# ── P2 ชุด 3: ยาสุ่มของแม่มด ──

def _witch_setup(monkeypatch):
    import bot.cogs.player_commands as pc
    players = {1: {"inventory": "62", "status_effects": "{}", "hp": 100, "max_hp": 100}}
    updates = {}
    monkeypatch.setattr(pc.player_model, "get_player", lambda uid: players.get(uid))
    monkeypatch.setattr(pc.player_model, "load_inventory", lambda s: ["62"])
    monkeypatch.setattr(pc.player_model, "update_player_field",
                        lambda uid, field, value: updates.__setitem__(field, value))
    return pc, updates


def test_witch_brew_good_roll(monkeypatch):
    pc, updates = _witch_setup(monkeypatch)
    monkeypatch.setattr(pc.random, "randint", lambda a, b: 1)      # ออกดีเสมอ
    monkeypatch.setattr(pc.random, "choice", lambda seq: seq[0])   # exp_blessing
    ok, msg = pc.apply_item_effect(1, "62")
    assert ok and "exp_blessing" in updates["status_effects"]
    assert "โชคเข้าข้าง" in msg


def test_witch_brew_bad_roll(monkeypatch):
    pc, updates = _witch_setup(monkeypatch)
    monkeypatch.setattr(pc.random, "randint", lambda a, b: 100)    # ออกร้ายเสมอ
    monkeypatch.setattr(pc.random, "choice", lambda seq: seq[0])   # poison
    ok, msg = pc.apply_item_effect(1, "62")
    assert ok and "poison" in updates["status_effects"]
    assert "แม่มดหัวเราะ" in msg


def test_witch_brew_catalog():
    it = json.load(open("config.example.json", encoding="utf-8"))["item_catalog"]["items"]["62"]
    assert it["effect"] == "gamble_status" and it["buy"] == 500 and it["purchasable"] is True
    assert len(it["effect_value"]["good"]) == 5 and len(it["effect_value"]["bad"]) == 5
