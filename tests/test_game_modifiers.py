"""ทดสอบแกน game_modifiers — ล็อกกติกา: identity ไม่เปลี่ยนเกม, กติการวมผล, ธีมสัปดาห์ deterministic"""
import datetime

import pytest

from bot import game_modifiers as gm


def test_default_is_identity(monkeypatch):
    monkeypatch.setattr(gm, "WEEKLY_THEMES", [])
    mods = gm.get_active_modifiers({"continent": "main"})
    assert mods["monster_hp_mult"] == 1.0
    assert mods["monster_dmg_mult"] == 1.0
    assert mods["monster_gold_mult"] == 1.0
    assert mods["monster_exp_mult"] == 1.0
    assert mods["event_weight_mult"] == {}
    assert mods["rank_weight_mult"] == {}
    assert mods["monster_pool"] == {}
    assert mods["theme_texts"] == {}
    assert mods["element_overrides"] == {}


def test_missing_or_unknown_continent_falls_back_to_main():
    assert gm.get_continent(None) is gm.CONTINENTS["main"]
    assert gm.get_continent({}) is gm.CONTINENTS["main"]
    assert gm.get_continent({"continent": "atlantis?"}) is gm.CONTINENTS["main"]


def test_apply_event_weights_identity_when_no_mult():
    weights = [25, 25, 20, 15, 10, 5]
    out = gm.apply_event_weights(weights, gm_event_list(), gm.DEFAULT_MODS)
    assert out == weights


def gm_event_list():
    return ["monster", "village", "treasure", "dungeon", "npc", "trap"]


def test_merge_rules(monkeypatch):
    monkeypatch.setitem(gm.CONTINENTS, "testland", {
        "label": "test",
        "mods": {
            "monster_hp_mult": 2.0,
            "event_weight_mult": {"monster": 1.5},
            "monster_pool": {"Common": ["Imp"]},
            "theme_texts": {"treasure": "หีบทดสอบ"},
        },
    })
    monkeypatch.setattr(gm, "WEEKLY_THEMES", [{
        "key": "testweek",
        "mods": {
            "monster_hp_mult": 1.5,
            "event_weight_mult": {"monster": 2.0},
            "monster_pool": {"Common": ["Zombie"], "Mini-Boss": ["Zombie Titan"]},
            "theme_texts": {"treasure": "หีบซอมบี้"},
        },
    }])

    mods = gm.get_active_modifiers({"continent": "testland"})
    assert mods["monster_hp_mult"] == pytest.approx(3.0)          # 2.0 × 1.5
    assert mods["event_weight_mult"]["monster"] == pytest.approx(3.0)  # 1.5 × 2.0
    assert mods["monster_pool"]["Common"] == ["Imp", "Zombie"]    # ต่อกันรายแรงค์
    assert mods["monster_pool"]["Mini-Boss"] == ["Zombie Titan"]
    assert mods["theme_texts"]["treasure"] == "หีบซอมบี้"          # ธีมสัปดาห์ทับทวีป
    # ตัวอื่นยังเป็น identity
    assert mods["monster_gold_mult"] == 1.0

    weights = gm.apply_event_weights([10, 20, 30], ["monster", "village", "treasure"], mods)
    assert weights == [pytest.approx(30.0), 20, 30]

    # DEFAULT_MODS ต้องไม่ถูกแก้ไขข้างเคียง
    assert gm.DEFAULT_MODS["monster_hp_mult"] == 1.0
    assert gm.DEFAULT_MODS["monster_pool"] == {}


def test_weekly_theme_deterministic(monkeypatch):
    themes = [{"key": "a"}, {"key": "b"}, {"key": "c"}]
    monkeypatch.setattr(gm, "WEEKLY_THEMES", themes)
    day1 = datetime.date(2026, 7, 20)   # จันทร์
    day2 = datetime.date(2026, 7, 26)   # อาทิตย์ สัปดาห์เดียวกัน
    next_week = datetime.date(2026, 7, 27)
    assert gm.get_weekly_theme(day1) is gm.get_weekly_theme(day2)
    # ข้ามสัปดาห์: เลือกจาก seed ใหม่ (อาจซ้ำได้ แต่ต้อง deterministic ต่อสัปดาห์)
    assert gm.get_weekly_theme(next_week) is gm.get_weekly_theme(next_week)


def test_weekly_theme_none_when_empty(monkeypatch):
    monkeypatch.setattr(gm, "WEEKLY_THEMES", [])
    assert gm.get_weekly_theme() is None


# ===== ธีมจริง 2 ตัวแรก (ข้อ 5) =====

VALID_RANKS = {"Common", "Mini-Boss", "Main-Boss", "Secret", "Unbeatable"}


def test_real_themes_structure():
    keys = [t["key"] for t in gm.WEEKLY_THEMES]
    assert "normal" in keys and "palette" in keys and "zombie" in keys and "royal_convoy" in keys
    for theme in gm.WEEKLY_THEMES:
        assert theme["label"] and theme["description"]
        assert set(theme["mods"].get("monster_pool", {})) <= VALID_RANKS


def test_normal_theme_is_identity_and_most_common():
    normal = next(t for t in gm.WEEKLY_THEMES if t["key"] == "normal")
    assert normal["mods"] == {}
    # สัปดาห์สงบสุขได้ mods เท่ากับไม่มีธีมเป๊ะ
    counts = {}
    day = datetime.date(2026, 1, 5)
    # หน้าต่างต้องยาวพอให้สถิติชนะดวงของ seed รายสัปดาห์ (10 ปี)
    for i in range(520):
        theme = gm.get_weekly_theme(day + datetime.timedelta(weeks=i))
        counts[theme["key"]] = counts.get(theme["key"], 0) + 1
    # weight สูงสุดต้องทำให้สัปดาห์ปกติโผล่บ่อยกว่าธีมพิเศษทุกตัว
    for key, count in counts.items():
        if key != "normal":
            assert counts["normal"] > count, f"normal ({counts['normal']}) ต้องมากกว่า {key} ({count})"


def test_zombie_theme_numbers():
    zombie = next(t for t in gm.WEEKLY_THEMES if t["key"] == "zombie")
    mods = zombie["mods"]
    assert mods["event_weight_mult"] == {"monster": 1.4}
    assert mods["monster_hp_mult"] == 1.3
    assert mods["monster_dmg_mult"] == 1.2
    assert mods["monster_gold_mult"] == 2.0
    assert mods["monster_exp_mult"] == 1.5
    assert any("Zombie Titan" in n for n in mods["monster_pool"]["Mini-Boss"])


def test_palette_theme_numbers():
    palette = next(t for t in gm.WEEKLY_THEMES if t["key"] == "palette")
    assert palette["mods"]["monster_gold_mult"] == 1.5
    # มีหลายสีต่อแรงค์ให้สุ่มไม่ซ้ำ
    assert len(palette["mods"]["monster_pool"]["Common"]) >= 3


def test_royal_convoy_theme_numbers():
    convoy = next(t for t in gm.WEEKLY_THEMES if t["key"] == "royal_convoy")
    assert convoy["mods"]["event_weight_mult"] == {"treasure": 1.8}
    assert convoy["mods"]["monster_gold_mult"] == 2.0
    assert "หีบราชสมบัติ" in convoy["mods"]["theme_texts"]["treasure"]


def test_dragon_nesting_theme_numbers():
    dragon = next(t for t in gm.WEEKLY_THEMES if t["key"] == "dragon_nesting")
    mods = dragon["mods"]
    assert mods["event_weight_mult"] == {"monster": 1.2}
    assert mods["monster_dmg_mult"] == 1.2
    assert mods["monster_gold_mult"] == 1.8
    assert all(rank in mods["monster_pool"] for rank in ("Common", "Mini-Boss", "Main-Boss"))


def test_solar_eclipse_theme_numbers(monkeypatch):
    eclipse = next(t for t in gm.WEEKLY_THEMES if t["key"] == "solar_eclipse")
    monkeypatch.setattr(gm, "WEEKLY_THEMES", [eclipse])
    mods = gm.get_active_modifiers({"continent": "main"})
    assert mods["element_weights"] == {"dark": 40}
    assert mods["rank_weight_mult"] == {"Secret": 3.0}
    assert mods["monster_exp_mult"] == 1.3
    dark = gm.get_element_data(mods, "dark")
    assert dark["hp_mult"] == 1.5 and dark["dice_bonus"] == [2, 4]
    assert dark["pre_enraged"] is True     # ของเดิมของธาตุมืดยังอยู่
    # rank_weight_mult ทบกับทวีปได้ราย key
    monkeypatch.setitem(gm.CONTINENTS, "testland", {
        "label": "t", "mods": {"rank_weight_mult": {"Secret": 2.0}},
    })
    merged = gm.get_active_modifiers({"continent": "testland"})
    assert merged["rank_weight_mult"]["Secret"] == pytest.approx(6.0)


def test_mana_meteor_theme_and_catalog():
    meteor = next(t for t in gm.WEEKLY_THEMES if t["key"] == "mana_meteor")
    infusion = meteor["mods"]["infusion"]
    assert infusion["chance"] == 50
    assert infusion["dmg_mult"] == 2.0
    assert infusion["drop_items"] == {"id": "29", "qty": [1, 2]}
    # ไอเทมคริสตัล + สูตรคราฟอาวุธในตำนานต้องอยู่ใน config.example.json
    import json
    catalog = json.load(open("config.example.json", encoding="utf-8"))["item_catalog"]
    assert "มานาคริสตัล" in catalog["items"]["29"]["name"]
    assert catalog["crafting_recipes"]["8"] == {"recipe": {"29": 5}, "fail_rate": 0.25}


def test_infusion_merge_replace(monkeypatch):
    meteor = next(t for t in gm.WEEKLY_THEMES if t["key"] == "mana_meteor")
    monkeypatch.setattr(gm, "WEEKLY_THEMES", [meteor])
    mods = gm.get_active_modifiers({"continent": "demon"})
    assert mods["infusion"]["chance"] == 50    # ธีมส่งผ่าน merge ครบ
    assert gm.DEFAULT_MODS["infusion"] is None # ค่าตั้งต้นไม่ถูกแตะ


def test_absolute_zero_theme_numbers(monkeypatch):
    zero = next(t for t in gm.WEEKLY_THEMES if t["key"] == "absolute_zero")
    monkeypatch.setattr(gm, "WEEKLY_THEMES", [zero])
    mods = gm.get_active_modifiers({"continent": "main"})
    assert mods["ambient_status"] == "frostbite"
    assert mods["travel_chance_mult"] == 2.0
    assert mods["element_weights"] == {"water": 35}
    assert gm.get_element_data(mods, "water")["hp_mult"] == 2.0
    # สถานะ frostbite ต้องมีในตาราง + ล้างที่แหล่งความอบอุ่นทั้ง 3
    frost = gm.STATUS_EFFECTS["frostbite"]
    assert frost["tick"] == "step" and frost["step_damage"] == (2, 4)
    assert set(frost["cleanse_on"]) == {"village", "npc", "dungeon"}


def test_blood_moon_theme_numbers():
    moon = next(t for t in gm.WEEKLY_THEMES if t["key"] == "blood_moon")
    mods = moon["mods"]
    assert mods["monster_hp_mult"] == 1.5
    assert mods["monster_dmg_mult"] == 1.25
    assert mods["event_weight_mult"] == {"monster": 1.3}
    infusion = mods["infusion"]
    assert infusion["chance"] == 100 and infusion["dmg_mult"] == 1.0
    assert len(infusion["drop_items"]["id_pool"]) == 10


def test_goddess_dice_rules():
    theme = next(t for t in gm.WEEKLY_THEMES if t["key"] == "goddess_dice")
    assert theme["mods"]["dice_rules"] is True
    assert theme["mods"]["monster_exp_mult"] == 1.5
    # กติการายวัน deterministic: วันเดียวกันได้กติกาเดิม
    day = datetime.date(2026, 7, 23)
    assert gm.get_daily_dice_rule(day) is gm.get_daily_dice_rule(day)
    # bonus/penalty logic
    even = next(r for r in gm.DICE_RULES if r["key"] == "even")
    assert gm.dice_rule_bonus(even, 10) == 2.0
    assert gm.dice_rule_bonus(even, 7) == 1.0
    assert gm.dice_rule_bonus(even, 0) == 1.0     # เต๋าโดนล็อก 0 (รากพันธนาการ) ไม่นับเป็นคู่
    odd = next(r for r in gm.DICE_RULES if r["key"] == "odd")
    assert gm.dice_rule_bonus(odd, 7) == 2.0 and gm.dice_rule_bonus(odd, 8) == 1.0
    high = next(r for r in gm.DICE_RULES if r["key"] == "high")
    assert gm.dice_rule_bonus(high, 15) == 2.5 and gm.dice_rule_bonus(high, 14) == 1.0
    gamble = next(r for r in gm.DICE_RULES if r["key"] == "gamble")
    assert gm.dice_rule_bonus(gamble, 16) == 3.0 and gm.dice_rule_bonus(gamble, 15) == 1.0
    assert gm.dice_rule_penalty(gamble, 5) == 1.5 and gm.dice_rule_penalty(gamble, 6) == 1.0
    assert gm.dice_rule_penalty(even, 3) == 1.0   # กติกาอื่นไม่มีโทษ


def test_masquerade_theme_numbers(monkeypatch):
    masq = next(t for t in gm.WEEKLY_THEMES if t["key"] == "masquerade")
    monkeypatch.setattr(gm, "WEEKLY_THEMES", [masq])
    mods = gm.get_active_modifiers({"continent": "main"})
    assert mods["masquerade"] == {"chance": 40, "inspect_fee": 1500}
    assert mods["monster_gold_mult"] == 1.6
    assert mods["monster_exp_mult"] == 1.2
    # ธีมอื่น/สัปดาห์ปกติต้องไม่มี masquerade
    monkeypatch.setattr(gm, "WEEKLY_THEMES", [])
    assert gm.get_active_modifiers({"continent": "main"})["masquerade"] is None


def test_black_market_theme_numbers(monkeypatch):
    market = next(t for t in gm.WEEKLY_THEMES if t["key"] == "black_market")
    monkeypatch.setattr(gm, "WEEKLY_THEMES", [market])
    mods = gm.get_active_modifiers({"continent": "frozen"})
    assert mods["monster_gold_mult"] == pytest.approx(1.6 * 1.4)  # ทบกับทวีป
    # อีเวนต์พ่อค้าต่อท้ายอีเวนต์ของทวีป (frozen มีพายุหิมะอยู่แล้ว)
    keys = [e["key"] for e in mods["special_events"]]
    assert keys == ["blizzard_ambush", "black_market_dealer"]
    dealer = mods["special_events"][1]
    assert dealer["template"] == "choice" and dealer["chance"] == 14
    assert dealer["choices"][0]["outcome"]["apply_status"]["key"] == "illegal_buff"
    # สถานะบัฟตัวแรก: ดาเมจผู้เล่น ×1.3 และทบกับ "ชา" ได้
    assert gm.status_combat_mult({"illegal_buff": 5}, "player_dmg_mult") == 1.3
    assert gm.status_combat_mult({"illegal_buff": 5, "numb": 2}, "player_dmg_mult") == pytest.approx(0.65)


def test_theme_pool_weights_final():
    # ธีมพิเศษทุกตัว weight 1 (ไม่ระบุ = 1), สงบสุข = 11 → ครึ่งหนึ่งของสัปดาห์
    specials = [t for t in gm.WEEKLY_THEMES if t["key"] != "normal"]
    assert len(specials) == 12  # +faction_war (P5)
    assert all(t.get("weight", 1) == 1 for t in specials)
    normal = next(t for t in gm.WEEKLY_THEMES if t["key"] == "normal")
    assert normal["weight"] == len(specials)


def test_stacking_ceilings_locked(monkeypatch):
    """ล็อกเพดานตัวคูณทบสูงสุดที่เป็นไปได้ทั้งเกม — เพิ่มทวีป/ธีม/ธาตุแล้วเกินนี้ = ตั้งใจต้องมาแก้เลขนี้"""
    max_gold = max_dmg = max_hp = 1.0
    for theme in gm.WEEKLY_THEMES:
        monkeypatch.setattr(gm, "WEEKLY_THEMES", [theme])
        for continent_key in gm.CONTINENTS:
            mods = gm.get_active_modifiers({"continent": continent_key})
            infusion_dmg = (mods.get("infusion") or {}).get("dmg_mult", 1.0)
            for element_key in gm.ELEMENTS:
                elem = gm.get_element_data(mods, element_key)
                max_gold = max(max_gold, mods["monster_gold_mult"] * elem.get("gold_mult", 1.0))
                max_dmg = max(max_dmg, mods["monster_dmg_mult"] * elem.get("dmg_mult", 1.0) * infusion_dmg)
                max_hp = max(max_hp, mods["monster_hp_mult"] * elem.get("hp_mult", 1.0))
    assert max_gold == pytest.approx(14.0)   # demon x2.0 × convoy x2.0 × แสง x3.5
    assert max_dmg == pytest.approx(4.14)    # volcanic x1.15 × ไฟ override x1.8 × meteor infusion x2.0
    assert max_hp == pytest.approx(4.5)      # demon x1.5 × blood moon x1.5 × ดิน x2.0


def test_demon_plus_zombie_stacking(monkeypatch):
    zombie = next(t for t in gm.WEEKLY_THEMES if t["key"] == "zombie")
    monkeypatch.setattr(gm, "WEEKLY_THEMES", [zombie])  # ธีมเดียว = สัปดาห์ไหนก็ได้ zombie
    mods = gm.get_active_modifiers({"continent": "demon"})
    assert mods["monster_hp_mult"] == pytest.approx(1.95)   # 1.5 × 1.3
    assert mods["monster_dmg_mult"] == pytest.approx(1.56)  # 1.3 × 1.2
    assert mods["monster_gold_mult"] == pytest.approx(4.0)  # 2.0 × 2.0
    assert mods["monster_exp_mult"] == pytest.approx(2.25)  # 1.5 × 1.5
    # ซอมบี้แทรกเข้า pool ควบคู่มอนสเตอร์ทวีป (ไม่แทนที่)
    common = mods["monster_pool"]["Common"]
    assert any("Imp" in n for n in common) and any("Zombie" in n for n in common)


# ===== ระบบธาตุมอนสเตอร์ =====

def test_elements_table_structure():
    assert set(gm.ELEMENTS) == {"fire", "water", "earth", "wind", "wood", "dark", "light"}
    for element in gm.ELEMENTS.values():
        assert element["label"]
    # พารามิเตอร์ตามสเปก
    assert gm.ELEMENTS["fire"]["dmg_mult"] == 1.5
    assert gm.ELEMENTS["water"]["lifesteal"] == 0.35
    assert gm.ELEMENTS["earth"]["hp_mult"] == 2.0
    assert gm.ELEMENTS["wind"]["dice_bonus"] == (2, 4)
    assert gm.ELEMENTS["wood"]["dice_bonus"] == (2, 4)
    assert gm.ELEMENTS["wood"]["root_chance"] == 25
    assert gm.ELEMENTS["dark"]["pre_enraged"] is True
    assert gm.ELEMENTS["light"]["monster_flee_chance"] == 40
    assert gm.ELEMENTS["light"]["gold_mult"] == 3.5


def test_continent_element_weights(monkeypatch):
    monkeypatch.setattr(gm, "WEEKLY_THEMES", [])
    demon = gm.get_active_modifiers({"continent": "demon"})["element_weights"]
    assert demon == {"dark": 35, "fire": 20}
    ocean = gm.get_active_modifiers({"continent": "ocean"})["element_weights"]
    assert ocean == {"water": 35, "wind": 20}
    main = gm.get_active_modifiers({"continent": "main"})["element_weights"]
    assert main == {}


def test_roll_element_valid_and_respects_weights():
    rng = __import__("random").Random(9)
    # เรทว่าง = สุ่มจากทุกธาตุ
    for _ in range(20):
        assert gm.roll_element(gm.DEFAULT_MODS, rng=rng) in gm.ELEMENTS
    # บังคับเรทเหลือธาตุเดียว → ต้องได้ธาตุนั้นเสมอ
    forced = {"element_weights": {k: 0 for k in gm.ELEMENTS} | {"water": 5}}
    for _ in range(20):
        assert gm.roll_element(forced, rng=rng) == "water"


def test_get_element_data_with_overrides():
    # ไม่มี override = ค่ามาตรฐานเป๊ะ (ยกเว้นเรทหนีที่ Panel เติมให้ทุกธาตุ)
    assert gm.get_element_data(gm.DEFAULT_MODS, "wood") == {
        **gm.ELEMENTS["wood"], "monster_flee_chance": gm.element_flee_chance("wood")}
    # override ทับเฉพาะพารามิเตอร์ที่ระบุ พารามิเตอร์อื่นของธาตุเดิมอยู่ครบ
    mods = {"element_overrides": {"wood": {"root_chance": 50, "exp_mult": 2.0}}}
    wood = gm.get_element_data(mods, "wood")
    assert wood["root_chance"] == 50
    assert wood["exp_mult"] == 2.0
    assert wood["dice_bonus"] == (2, 4)          # ของเดิมไม่หาย
    assert gm.ELEMENTS["wood"]["root_chance"] == 25  # ตารางกลางไม่ถูกแก้
    # ธาตุอื่นไม่กระทบ
    assert gm.get_element_data(mods, "fire") == {
        **gm.ELEMENTS["fire"], "monster_flee_chance": gm.element_flee_chance("fire")}
    # ธาตุไม่รู้จัก/None = ว่าง
    assert gm.get_element_data(mods, None) == {}
    assert gm.get_element_data(mods, "void?") == {}


def test_element_overrides_merge_nested(monkeypatch):
    monkeypatch.setitem(gm.CONTINENTS, "testland", {
        "label": "test",
        "mods": {"element_overrides": {"wood": {"root_chance": 50}}},
    })
    monkeypatch.setattr(gm, "WEEKLY_THEMES", [{
        "key": "t",
        "mods": {"element_overrides": {"wood": {"exp_mult": 2.0}, "fire": {"dmg_mult": 2.0}}},
    }])
    mods = gm.get_active_modifiers({"continent": "testland"})
    # รวมรายพารามิเตอร์ ไม่ล้างกัน: wood ได้ทั้งของทวีปและธีม
    assert mods["element_overrides"]["wood"] == {"root_chance": 50, "exp_mult": 2.0}
    assert mods["element_overrides"]["fire"] == {"dmg_mult": 2.0}


def test_element_weights_merge_theme_over_continent(monkeypatch):
    monkeypatch.setattr(gm, "WEEKLY_THEMES", [{
        "key": "t", "mods": {"element_weights": {"dark": 50}},
    }])
    merged = gm.get_active_modifiers({"continent": "demon"})["element_weights"]
    assert merged == {"dark": 50, "fire": 20}  # ธีมทับทวีปราย key


# ===== ระบบเดินทางข้ามทวีป (ข้อ 2) =====

def test_travel_encounter_fare_within_cash():
    rng = __import__("random").Random(42)
    for cash in (0, 1, 50_000):
        enc = gm.roll_travel_encounter(cash, rng=rng)
        assert enc["vehicle"] in gm.VEHICLES
        assert enc["label"] == gm.VEHICLES[enc["vehicle"]]["label"]
        assert 0 <= enc["fare"] <= cash


def test_roll_destination_never_returns_current():
    rng = __import__("random").Random(7)
    for vehicle in gm.VEHICLES:
        for current in gm.CONTINENTS:
            for _ in range(30):
                assert gm.roll_destination(vehicle, current, rng=rng) != current


def test_roll_destination_fallback_for_new_continent(monkeypatch):
    # ทวีปใหม่ที่พาหนะไม่รู้จัก ต้องโผล่เป็นปลายทางเองด้วย weight มาตรฐาน
    monkeypatch.setitem(gm.CONTINENTS, "frozen_test", {"label": "❄️ test", "mods": {}})
    rng = __import__("random").Random(11)
    seen = {gm.roll_destination("caravan", "main", rng=rng) for _ in range(300)}
    assert "frozen_test" in seen
    # ทวีปเดิมยังโผล่ครบ (เรทเดิมไม่ถูกลบ)
    assert {"demon", "ocean"} <= seen


def test_roll_destination_respects_zero_weight():
    # ระบุ weight 0 = พาหนะนั้นห้ามไปทวีปนั้นเด็ดขาด (ทวีปอื่นที่ไม่ระบุยังได้ fallback ตามปกติ)
    rng = __import__("random").Random(1)
    original = gm.VEHICLES["ship"]["dest_weights"]
    gm.VEHICLES["ship"]["dest_weights"] = {"main": 0, "demon": 0, "ocean": 100}
    try:
        results = {gm.roll_destination("ship", "main", rng=rng) for _ in range(60)}
        assert "demon" not in results          # โดนแบนด้วย weight 0
        assert "ocean" in results              # เรทหลักยังมา
    finally:
        gm.VEHICLES["ship"]["dest_weights"] = original


# ===== ผลทวีปต่อเกมเพลย์ (ข้อ 3) =====

def test_demon_continent_mods_match_approved_numbers(monkeypatch):
    monkeypatch.setattr(gm, "WEEKLY_THEMES", [])
    mods = gm.get_active_modifiers({"continent": "demon"})
    assert mods["event_weight_mult"] == {"monster": 1.5, "trap": 1.3, "village": 0.5}
    assert mods["monster_hp_mult"] == 1.5
    assert mods["monster_dmg_mult"] == 1.3
    assert mods["monster_gold_mult"] == 2.0
    assert mods["monster_exp_mult"] == 1.5
    assert "Imp" in mods["monster_pool"]["Common"][0]
    assert "Dark Curse" in mods["theme_texts"]["treasure"]
    assert "Demon Rift" in mods["theme_texts"]["trap"]


def test_ocean_continent_mods_match_approved_numbers(monkeypatch):
    monkeypatch.setattr(gm, "WEEKLY_THEMES", [])
    mods = gm.get_active_modifiers({"continent": "ocean"})
    assert mods["event_weight_mult"] == {"treasure": 1.6, "trap": 1.2}
    assert mods["monster_hp_mult"] == 1.2
    assert mods["monster_dmg_mult"] == 1.0
    assert mods["monster_gold_mult"] == 1.5
    assert mods["monster_exp_mult"] == 1.0
    assert "Ghost Pirate" in mods["monster_pool"]["Common"][0]
    assert "Tropical Storm" in mods["theme_texts"]["trap"]
    assert "Treasure Island" in mods["theme_texts"]["treasure"]


def test_frozen_continent_numbers(monkeypatch):
    monkeypatch.setattr(gm, "WEEKLY_THEMES", [])
    mods = gm.get_active_modifiers({"continent": "frozen"})
    assert mods["event_weight_mult"] == {"monster": 1.5}
    assert mods["monster_hp_mult"] == 1.2
    assert mods["monster_gold_mult"] == 1.6
    assert mods["monster_exp_mult"] == 1.3
    assert mods["element_weights"] == {"water": 30, "wind": 20}
    assert "Yeti" in mods["monster_pool"]["Common"][0]
    assert "Ice Dragon" in mods["monster_pool"]["Main-Boss"][0]
    events = mods["special_events"]
    assert len(events) == 1 and events[0]["key"] == "blizzard_ambush"
    ambush = events[0]
    assert ambush["template"] == "dice_check" and ambush["chance"] == 12
    assert ambush["fail"]["start_fight"] is True
    assert ambush["fail"]["apply_status"]["key"] == "numb"
    # ทวีปใหม่ต้องโผล่เป็นปลายทางพาหนะอัตโนมัติ (fallback จาก A1)
    rng = __import__("random").Random(21)
    seen = {gm.roll_destination("caravan", "main", rng=rng) for _ in range(300)}
    assert "frozen" in seen


def test_nether_continent_numbers(monkeypatch):
    monkeypatch.setattr(gm, "WEEKLY_THEMES", [])
    mods = gm.get_active_modifiers({"continent": "nether"})
    assert mods["monster_hp_mult"] == 1.3
    assert mods["monster_dmg_mult"] == 1.2
    assert mods["monster_gold_mult"] == 1.8
    assert mods["monster_exp_mult"] == 1.4
    assert mods["element_weights"] == {"dark": 30, "water": 15}
    assert mods["combat_hp_drain"] == [2, 5]        # Life Drain ต้องรอดผ่าน merge
    assert "Banshee" in mods["monster_pool"]["Common"][0]
    assert "Undead King" in mods["monster_pool"]["Main-Boss"][0]
    feast = mods["special_events"][0]
    assert feast["key"] == "ancestral_feast" and feast["template"] == "instant"
    outcomes = feast["outcomes"]
    assert len(outcomes) == 6
    # พร 3 / สาป 3 น้ำหนักเท่ากัน = 50/50
    blessings = [o for o in outcomes if "heal" in o or "cleanse_all" in o or "cleanse_random" in o]
    curses = [o for o in outcomes if "damage" in o or "apply_status" in o
              or (isinstance(o.get("gold"), list) and o["gold"][1] < 0)]
    assert len(blessings) == 3 and len(curses) == 3


def test_volcanic_continent_numbers(monkeypatch):
    monkeypatch.setattr(gm, "WEEKLY_THEMES", [])
    mods = gm.get_active_modifiers({"continent": "volcanic"})
    assert mods["monster_hp_mult"] == 1.25
    assert mods["monster_dmg_mult"] == 1.15
    assert mods["monster_gold_mult"] == 1.7
    assert mods["monster_exp_mult"] == 1.35
    assert mods["element_weights"] == {"fire": 35, "earth": 15}
    # Searing Heat: ไฟที่นี่ตีแรง 1.8 (override จาก 1.5 มาตรฐาน) — ธาตุอื่นไม่กระทบ
    assert gm.get_element_data(mods, "fire")["dmg_mult"] == 1.8
    assert gm.get_element_data(mods, "water") == {
        **gm.ELEMENTS["water"], "monster_flee_chance": gm.element_flee_chance("water")}
    eruption = mods["special_events"][0]
    assert eruption["key"] == "volcanic_eruption" and eruption["pass_roll"] == 12
    assert eruption["success"]["items"][:2] == [{"id": "11", "qty": 10}, {"id": "40", "qty": 1}]  # อัญมณี + หินอัคนี (T2; แหวนแรร์เช็คที่ test_t2_drop_sources)
    assert "Fire Salamander" in mods["monster_pool"]["Common"][0]
    assert "Light Dragon" in mods["monster_pool"]["Main-Boss"][0]


def test_sylvan_continent_numbers(monkeypatch):
    monkeypatch.setattr(gm, "WEEKLY_THEMES", [])
    mods = gm.get_active_modifiers({"continent": "sylvan"})
    assert mods["monster_hp_mult"] == 1.2
    assert mods["monster_dmg_mult"] == 1.1
    assert mods["monster_gold_mult"] == 1.5
    assert mods["monster_exp_mult"] == 1.5
    assert mods["element_weights"] == {"wood": 35, "earth": 15}
    # Ferocious Flora: ไม้ root 50 + exp x2 (ธาตุอื่นไม่กระทบ)
    wood = gm.get_element_data(mods, "wood")
    assert wood["root_chance"] == 50 and wood["exp_mult"] == 2.0
    assert wood["dice_bonus"] == (2, 4)
    thicket = mods["special_events"][0]
    assert thicket["key"] == "poison_thicket" and thicket["template"] == "choice"
    assert thicket["choices"][0]["outcome"]["apply_status"]["key"] == "poison"
    assert thicket["choices"][1]["outcome"]["gold"] == [-3000, -800]
    assert "Ent" in mods["monster_pool"]["Mini-Boss"][0]
    assert "Cursed Dryad" in mods["monster_pool"]["Main-Boss"][0]


def test_mechanized_continent_numbers(monkeypatch):
    monkeypatch.setattr(gm, "WEEKLY_THEMES", [])
    mods = gm.get_active_modifiers({"continent": "mechanized"})
    assert mods["monster_hp_mult"] == 1.3
    assert mods["monster_gold_mult"] == 1.9
    assert mods["element_weights"] == {"earth": 25, "fire": 20, "wind": 15}
    events = {e["key"]: e for e in mods["special_events"]}
    assert set(events) == {"emp_field", "ancient_excavation"}
    emp = events["emp_field"]
    assert emp["template"] == "choice"
    assert emp["choices"][0]["outcome"]["apply_status"]["key"] == "emp"
    dig = events["ancient_excavation"]
    assert dig["template"] == "dice_check" and dig["pass_roll"] == 12
    assert "Steam Puppet" in mods["monster_pool"]["Common"][0]
    assert "Ancient Guardian" in mods["monster_pool"]["Main-Boss"][0]


def test_skyward_continent_numbers(monkeypatch):
    monkeypatch.setattr(gm, "WEEKLY_THEMES", [])
    mods = gm.get_active_modifiers({"continent": "skyward"})
    assert mods["monster_hp_mult"] == 1.25
    assert mods["monster_exp_mult"] == 1.4
    assert mods["element_weights"] == {"wind": 35, "light": 15}
    wind = gm.get_element_data(mods, "wind")
    assert wind["dice_bonus"] == [3, 6] and wind["exp_mult"] == 1.75
    island = mods["special_events"][0]
    assert island["key"] == "falling_island"
    # เกาะถล่ม: บังคับกลับทวีปหลักทุกกรณี (รอดหรือตาย)
    assert island["success"]["force_continent"] == "main"
    assert island["fail"]["force_continent"] == "main"
    assert island["fail"]["damage"] == [40, 80]
    assert "Fallen Angel" in mods["monster_pool"]["Main-Boss"][0]


def test_all_six_new_continents_registered():
    assert set(gm.CONTINENTS) == {"main", "demon", "ocean", "frozen", "nether",
                                  "volcanic", "sylvan", "mechanized", "skyward"}
    for key, continent in gm.CONTINENTS.items():
        assert continent["label"] and continent["arrival_text"]


def test_pick_monster_name_themed_and_fallback(monkeypatch):
    monkeypatch.setattr(gm, "WEEKLY_THEMES", [])
    demon_mods = gm.get_active_modifiers({"continent": "demon"})
    assert "Imp" in gm.pick_monster_name(demon_mods, "Common")
    assert "Demon Lord" in gm.pick_monster_name(demon_mods, "Main-Boss")
    # แรงค์ที่ไม่มีธีม + ทวีปหลัก = None (ใช้ชื่อเดิม)
    assert gm.pick_monster_name(demon_mods, "Unbeatable") is None
    assert gm.pick_monster_name(gm.get_active_modifiers({"continent": "main"}), "Common") is None


def test_travel_chance_boundaries():
    class FakeRng:
        def __init__(self, value):
            self.value = value

        def randint(self, lo, hi):
            return self.value

    assert gm.roll_travel_chance(rng=FakeRng(gm.TRAVEL_EVENT_CHANCE)) is True
    assert gm.roll_travel_chance(rng=FakeRng(gm.TRAVEL_EVENT_CHANCE + 1)) is False
    # travel_chance_mult คูณโอกาส (Absolute Zero = ×2)
    doubled = {"travel_chance_mult": 2.0}
    assert gm.roll_travel_chance(doubled, rng=FakeRng(gm.TRAVEL_EVENT_CHANCE * 2)) is True
    assert gm.roll_travel_chance(doubled, rng=FakeRng(gm.TRAVEL_EVENT_CHANCE * 2 + 1)) is False


def test_calm_event_chance_and_texts():
    class FakeRng:
        def __init__(self, value):
            self.value = value

        def randint(self, lo, hi):
            return self.value

    assert gm.roll_calm_chance(FakeRng(gm.CALM_EVENT_CHANCE)) is True
    assert gm.roll_calm_chance(FakeRng(gm.CALM_EVENT_CHANCE + 1)) is False
    rng = __import__("random").Random(3)
    for _ in range(10):
        assert gm.pick_calm_text(rng) in gm.CALM_TEXTS


def test_player_element_passives():
    """Passive ธาตุผู้เล่น: ทุกธาตุต้องมี player dict + desc, helper คูณ/บวกถูกต้อง"""
    for key, data in gm.ELEMENTS.items():
        assert data.get("player", {}).get("desc"), f"{key} ไม่มี player passive/desc"
    # คูณทบ: คนแคระ (ดิน+ไฟ) / มืดเดี่ยว / ไม่มีธาตุ
    assert gm.player_passive_mult(["fire", "dark"], "dmg_mult") == 1.15 * 1.25
    assert round(gm.player_passive_mult(["earth", "dark"], "def_mult"), 4) == round(0.9 * 1.1, 4)
    assert gm.player_passive_mult([], "dmg_mult") == 1.0
    assert gm.player_passive_mult(["water"], "dmg_mult") == 1.0
    # ผลรวม: ลมเต๋า+1, น้ำดูดเลือด 15%, ไม้ฟื้น 2%, แสงรางวัล ×1.1
    assert gm.player_passive_sum(["wind"], "roll_bonus") == 1
    assert gm.player_passive_sum(["water"], "lifesteal") == 0.15
    assert gm.player_passive_sum(["wood"], "step_regen") == 0.02
    assert gm.player_passive_mult(["light"], "reward_mult") == 1.1
    # มนุษย์ (แสง+ลม): ได้ทั้งสอง passive อิสระต่อกัน
    human = gm.resolve_player_elements(["มนุษย์"])
    assert gm.player_passive_sum(human, "roll_bonus") == 1
    assert gm.player_passive_mult(human, "reward_mult") == 1.1
