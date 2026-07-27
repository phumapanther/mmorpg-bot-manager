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
