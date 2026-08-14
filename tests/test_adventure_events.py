"""ตัวตัดสินผลเหตุการณ์กลาง (เว็บเกม เฟส 5.4) — ดิสกับเว็บต้องได้ผลเดียวกัน

เดิมตรรกะพวกนี้ฝังอยู่ในปุ่มของ Discord View ทดสอบไม่ได้เลย
พอย้ายมา adventure_core แล้วต้องมีเทสล็อกไว้ ไม่งั้นแก้ฝั่งหนึ่งแล้วอีกฝั่งเพี้ยนเงียบ ๆ
"""
import pathlib
import random

import pytest

import bot.models.player_model as pm
from bot import adventure_core, config_loader

ITEMS = {"1": {"name": "ยาแดง", "buy": 50}, "2": {"name": "ดาบเทพ", "buy": 999999}}
ARMORS = {"None": {"hp": 0, "eva": 0}, "Plate": {"hp": 500, "eva": 40}}


@pytest.fixture
def world(tmp_path, monkeypatch):
    """ผู้เล่นปลอมหนึ่งคนในหน่วยความจำ — เขียนอะไรลงไปก็อ่านกลับมาเช็คได้"""
    p = {"user_id": 1, "level": 10, "hp": 50, "max_hp": 100, "cash": 100_000, "bank": 0,
         "armor": "Plate", "armor_dur": 100, "inventory": "[]", "capacity": 10,
         "current_state": "village", "last_event": "none", "dungeon_steps": 0,
         "continent": "main", "class_name": "Warrior"}
    monkeypatch.setattr(pm, "DB_NAME", str(tmp_path / "t.db"))
    monkeypatch.setattr(pm, "get_player", lambda uid: dict(p))
    monkeypatch.setattr(pm, "update_player_field", lambda uid, f, v: p.__setitem__(f, v))
    monkeypatch.setattr(pm, "update_player_fields", lambda uid, d: p.update(d))
    monkeypatch.setattr(config_loader, "get_all_items", lambda: ITEMS)
    monkeypatch.setattr(config_loader, "get_armor_stats", lambda k: ARMORS.get(k))
    monkeypatch.setattr(config_loader, "get_balance",
                        lambda key, default=None: {"village.rest_cost": 2000,
                                                   "village.rest_cost_per_level": 0}.get(key, default))
    return p


# ── 🏡 หมู่บ้าน ────────────────────────────────────────────────────────────────

def test_rest_heals_to_max_including_armor_bonus(world):
    r = adventure_core.resolve_village(1, "rest")
    assert world["hp"] == 600, "HP เต็มต้องรวมโบนัสจากเกราะด้วย"
    assert world["cash"] == 98_000 and r["cost"] == 2000
    assert world["current_state"] == "idle", "พักแรมเสร็จต้องปลดสถานะ ไม่งั้นค้างเล่นต่อไม่ได้"


def test_broken_armor_gives_no_hp_bonus(world):
    world["armor_dur"] = 0
    adventure_core.resolve_village(1, "rest")
    assert world["hp"] == 100, "เกราะพังแล้วต้องไม่ได้โบนัส HP"


def test_rest_refused_when_too_poor_keeps_state_and_money(world):
    world["cash"] = 100
    r = adventure_core.resolve_village(1, "rest")
    assert "error" in r and world["cash"] == 100
    assert world["current_state"] == "village", "จ่ายไม่ไหวต้องยังอยู่ในหมู่บ้าน กดใหม่ได้"


def test_rest_cost_scales_with_level(world, monkeypatch):
    monkeypatch.setattr(config_loader, "get_balance",
                        lambda key, default=None: {"village.rest_cost": 2000,
                                                   "village.rest_cost_per_level": 100}.get(key, default))
    assert adventure_core.rest_cost(world) == 2000 + 100 * 10


# ── 📦 หีบสมบัติ ───────────────────────────────────────────────────────────────

def test_mimic_marks_next_event_as_a_guaranteed_trap(world):
    r = adventure_core.resolve_treasure(1, "open", is_rogue=False, rng=random.Random(0))
    if r.get("mimic"):
        assert world["last_event"] == "treasure_trap", "โดนมิมิกแล้วก้าวหน้าต้องเจอกับดักชัวร์"


def test_rogue_never_hits_a_mimic(world):
    for seed in range(40):
        r = adventure_core.resolve_treasure(1, "open", is_rogue=True, rng=random.Random(seed))
        assert not r.get("mimic"), "Rogue ต้องกันมิมิกได้ 100%"


def test_full_bag_shows_the_item_but_does_not_keep_it(world):
    world["inventory"] = "[1,1,1,1,1,1,1,1,1,1]"      # เต็มพอดี 10/10

    class OnlyItem(random.Random):
        def random(self): return 0.9                    # ไม่โดนมิมิก
        def choices(self, seq, weights=None, k=1): return ["item"] if seq[0] == "gold" else [seq[0]]

    r = adventure_core.resolve_treasure(1, "open", rng=OnlyItem())
    assert r.get("bag_full") and world["inventory"] == "[1,1,1,1,1,1,1,1,1,1]"


def test_walking_past_the_chest_changes_nothing_but_state(world):
    adventure_core.resolve_treasure(1, "ignore")
    assert world["cash"] == 100_000 and world["current_state"] == "idle"


# ── 💀 ดันเจี้ยน / ⚠️ กับดัก ────────────────────────────────────────────────────

def test_entering_a_dungeon_queues_ten_forced_fights(world):
    adventure_core.resolve_dungeon(1, "enter")
    assert world["dungeon_steps"] == 10 and world["last_event"] == "dungeon_inside"


def test_declining_a_dungeon_leaves_no_forced_fights(world):
    adventure_core.resolve_dungeon(1, "leave")
    assert world["dungeon_steps"] == 0 and world["last_event"] == "dungeon"


def test_rogue_always_dodges_the_trap(world):
    for seed in range(20):
        world.update(hp=50, armor_dur=100)
        r = adventure_core.resolve_trap(1, is_rogue=True, rng=random.Random(seed))
        assert r["dodged"] and world["hp"] == 50


def test_failed_dodge_costs_hp_and_wears_the_armor(world):
    class AlwaysFail(random.Random):
        def randint(self, a, b): return b               # ทอยสูงสุด = หลบไม่พ้น (eva 40)

    r = adventure_core.resolve_trap(1, is_rogue=False, rng=AlwaysFail())
    assert not r["dodged"] and world["hp"] == 50 - r["damage"]
    assert world["armor_dur"] < 100, "โดนกับดักแล้วเกราะต้องสึก"
    assert world["current_state"] == "idle"


def test_trap_dodge_uses_armor_evasion(world):
    class Roll(random.Random):
        def randint(self, a, b): return 40              # เท่ากับ eva พอดี = รอด

    assert adventure_core.resolve_trap(1, rng=Roll())["dodged"]


# ── 🧭 เดินทางข้ามทวีป ─────────────────────────────────────────────────────────

def test_boarding_without_the_fare_does_not_move_you(world):
    world["cash"] = 10
    r = adventure_core.resolve_travel(1, {"vehicle": "cart", "label": "เกวียน", "fare": 5000}, "board")
    assert "continent" not in r and world["continent"] == "main" and world["cash"] == 10
    assert world["current_state"] == "idle", "ยานออกไปแล้วต้องไม่ค้างสถานะ"


def test_declining_travel_costs_nothing(world):
    adventure_core.resolve_travel(1, {"vehicle": "cart", "label": "เกวียน", "fare": 5000}, "decline")
    assert world["cash"] == 100_000 and world["current_state"] == "idle"


def test_fare_comes_from_the_server_not_the_browser(world):
    """ค่าโดยสารต้องอ่านจาก encounter ที่เซิร์ฟเวอร์เก็บไว้ ไม่ใช่ค่าที่เบราว์เซอร์ส่งมา"""
    api = pathlib.Path("license_server/web_api.py").read_text(encoding="utf-8")
    assert "resolve_travel(uid, data, body.action)" in api, "ต้องใช้ encounter จาก adventure_pending"
    assert "body.fare" not in api and "body.encounter" not in api


# ── 🗂️ เหตุการณ์ค้าง ──────────────────────────────────────────────────────────

def test_pending_event_survives_a_page_refresh(tmp_path, monkeypatch):
    monkeypatch.setattr(pm, "DB_NAME", str(tmp_path / "t.db"))
    adventure_core.set_pending(7, "travel", {"vehicle": "ship", "fare": 1234})
    assert adventure_core.get_pending(7) == ("travel", {"vehicle": "ship", "fare": 1234})
    adventure_core.clear_pending(7)
    assert adventure_core.get_pending(7) == (None, {})


# ── 🔒 กติกาข้อ 1: ตรรกะเดียว สองแพลตฟอร์ม ────────────────────────────────────

GV = pathlib.Path("bot/views/game_views.py").read_text(encoding="utf-8")
API = pathlib.Path("license_server/web_api.py").read_text(encoding="utf-8")


@pytest.mark.parametrize("fn", ["resolve_village", "resolve_treasure", "resolve_dungeon",
                                "resolve_trap", "resolve_travel"])
def test_discord_and_web_call_the_same_resolver(fn):
    assert f"adventure_core.{fn}(" in GV, f"ปุ่มในดิสยังไม่ได้เรียก {fn}"
    assert f"adventure_core.{fn}(" in API, f"เว็บยังไม่ได้เรียก {fn}"


def test_the_web_never_locks_a_state_it_cannot_unlock():
    """กันบั๊กร้ายแรงที่สุดของเฟสนี้ — ล็อกสถานะที่เว็บเล่นต่อไม่ได้ = ค้างถาวรทั้งสองแพลตฟอร์ม

    (เกมไม่มีคำสั่งปลดสถานะค้าง จึงต้องกันตั้งแต่ต้นทาง)
    """
    import re
    playable = set(re.search(r"_WEB_PLAYABLE = \{(.*?)\n\}", API, re.S).group(1).split('"')[1::4])
    handled = set(re.findall(r'elif event == "(\w+)":', API))
    assert playable <= handled | {"village"}, f"ล็อกสถานะแต่ไม่มีทางปลด: {playable - handled}"
    assert "playable\"] = False" in API, "เหตุการณ์ที่เว็บเล่นไม่ได้ต้องไม่ล็อกสถานะ"


def test_walk_counts_the_daily_quest_on_both_platforms():
    core = pathlib.Path("bot/adventure_core.py").read_text(encoding="utf-8")
    assert '_daily.track(user_id, "walk", 1)' in core
    assert "adventure_core.step_prelude(" in GV and "adventure_core.step_prelude(" in API


def test_act_cannot_be_replayed_after_the_event_is_over():
    """กดปุ่มซ้ำหลังเหตุการณ์จบแล้ว = เปิดหีบ/พักแรมซ้ำได้ฟรี — ต้องกันด้วยการเช็คสถานะ"""
    assert 'if player.get("current_state") != expected:' in API
    assert "adventure_core.clear_pending(uid)" in API


# ── 🧓 NPC ────────────────────────────────────────────────────────────────────

def test_npc_gift_adds_gold(world):
    class Gift(random.Random):
        def choice(self, seq): return "gift"
        def randint(self, a, b): return 50

    r = adventure_core.npc_talk(1, rng=Gift())
    assert world["cash"] == 100_050 and r["gold"] == 50
    assert world["current_state"] == "idle" and world["last_event"] == "npc"


def test_npc_pedlar_does_not_sell_when_the_bag_is_full(world):
    world["inventory"] = "[1,1,1,1,1,1,1,1,1,1]"

    class Shop(random.Random):
        def choice(self, seq): return "shop"
        def choices(self, seq, weights=None, k=1): return [seq[0]]
        def randint(self, a, b): return b

    adventure_core.npc_talk(1, rng=Shop())
    assert world["cash"] == 100_000, "กระเป๋าเต็มต้องไม่หักเงิน"
    assert world["inventory"] == "[1,1,1,1,1,1,1,1,1,1]"


def test_npc_pedlar_does_not_sell_what_you_cannot_afford(world):
    world["cash"] = 5

    class Shop(random.Random):
        def choice(self, seq): return "shop"
        def choices(self, seq, weights=None, k=1): return ["2"]     # ดาบเทพ ราคาแพง
        def randint(self, a, b): return b

    adventure_core.npc_talk(1, rng=Shop())
    assert world["cash"] == 5 and world["inventory"] == "[]"


def test_quest_offer_does_not_touch_the_bag_until_you_accept(world):
    world["inventory"] = '["1","2"]'
    offer = adventure_core.npc_quest_offer(1, rng=random.Random(3))
    assert offer and offer["requested"]
    assert world["inventory"] == '["1","2"]', "แค่ยื่นข้อเสนอต้องยังไม่หักของ"
    assert world["current_state"] == "village", "ยังไม่ตกลง ต้องยังค้างอยู่ที่ NPC"


def test_empty_bag_gets_no_quest_offer(world):
    assert adventure_core.npc_quest_offer(1) is None
    assert world["current_state"] == "idle"


def test_accepting_a_quest_swaps_items_for_the_reward(world):
    world["inventory"] = '["1","2"]'
    r = adventure_core.npc_quest_settle(1, {"requested": ["1"], "reward_item": "2",
                                            "reward_cash": 500}, True)
    assert "สำเร็จ" in r["text"] and world["cash"] == 100_500
    assert sorted(pm.load_inventory(world["inventory"])) == ["2", "2"]


def test_quest_fails_if_the_items_are_gone(world):
    """กันโกง: เอาของไปทิ้ง/ขายระหว่างกำลังคิด แล้วค่อยกดตกลง"""
    world["inventory"] = "[]"
    r = adventure_core.npc_quest_settle(1, {"requested": ["1"], "reward_item": None,
                                            "reward_cash": 9999}, True)
    assert "ไม่ครบ" in r["text"] and world["cash"] == 100_000


def test_declining_a_quest_keeps_everything(world):
    world["inventory"] = '["1"]'
    adventure_core.npc_quest_settle(1, {"requested": ["1"], "reward_cash": 500}, False)
    assert world["inventory"] == '["1"]' and world["cash"] == 100_000


# ── ✨ อีเวนต์พิเศษ ────────────────────────────────────────────────────────────

def test_events_that_start_a_fight_are_detected():
    """เว็บยังสู้ไม่ได้ ต้องคัดอีเวนต์ที่ลากเข้าไฟต์ออกก่อนตั้งแต่ตอนเจอ"""
    assert adventure_core.special_leads_to_fight({"success": {"start_fight": True}})
    assert adventure_core.special_leads_to_fight({"choices": [{"outcome": {"start_fight": 1}}]})
    assert adventure_core.special_leads_to_fight({"outcomes": [{"gold": 5}, {"start_fight": 1}]})
    assert not adventure_core.special_leads_to_fight({"choices": [{"outcome": {"gold": 100}}]})


def test_dice_check_uses_the_pass_roll():
    ev = {"template": "dice_check", "pass_roll": 15,
          "success": {"gold": 1}, "fail": {"gold": 0}}

    class Roll(random.Random):
        def randint(self, a, b): return 15

    out, prefix = adventure_core.special_pick_outcome(ev, None, rng=Roll())
    assert out == {"gold": 1} and "สำเร็จ" in prefix


def test_choice_event_picks_the_button_you_pressed():
    ev = {"template": "choice", "choices": [{"outcome": {"a": 1}}, {"outcome": {"b": 2}}]}
    assert adventure_core.special_pick_outcome(ev, "1")[0] == {"b": 2}
    assert adventure_core.special_pick_outcome(ev, "ค่าเพี้ยน")[0] == {"a": 1}, "ค่าพังต้องไม่ทำ 500"


# ── ⏳ หมดอายุเหตุการณ์ค้าง ───────────────────────────────────────────────────

def test_stale_mugging_auto_flees_like_the_discord_timeout(tmp_path, monkeypatch):
    """!play ไม่ได้ปลดสถานะ mugging ให้ — ถ้าไม่หมดอายุเอง ผู้เล่นที่ปิดเว็บจะค้างถาวร"""
    import sqlite3
    monkeypatch.setattr(pm, "DB_NAME", str(tmp_path / "t.db"))
    state = {"cash": 1000, "bank": 0, "inventory": "[]", "current_state": "mugging"}
    monkeypatch.setattr(pm, "get_player", lambda uid: dict(state))
    monkeypatch.setattr(pm, "update_player_field", lambda uid, f, v: state.__setitem__(f, v))
    monkeypatch.setattr(config_loader, "get_all_items", lambda: ITEMS)

    adventure_core.set_pending(5, "mugging", {})
    assert adventure_core.expire_pending(5) == "", "เพิ่งเจอ ยังไม่ควรหมดอายุ"

    with sqlite3.connect(pm.DB_NAME) as conn:                 # ย้อนเวลาให้เกิน timeout
        conn.execute("UPDATE adventure_pending SET updated_at=0 WHERE user_id=5")
    note = adventure_core.expire_pending(5)
    assert "โจรฉกถุงทอง" in note
    assert state["cash"] == 500 and state["current_state"] == "idle"
    assert adventure_core.get_pending(5) == (None, {})


def test_stale_village_just_unlocks(tmp_path, monkeypatch):
    import sqlite3
    monkeypatch.setattr(pm, "DB_NAME", str(tmp_path / "t.db"))
    state = {"current_state": "village"}
    monkeypatch.setattr(pm, "update_player_field", lambda uid, f, v: state.__setitem__(f, v))
    adventure_core.set_pending(6, "village", {})
    with sqlite3.connect(pm.DB_NAME) as conn:
        conn.execute("UPDATE adventure_pending SET updated_at=0 WHERE user_id=6")
    assert "หมดอายุ" in adventure_core.expire_pending(6)
    assert state["current_state"] == "idle"


def test_walk_and_state_both_expire_stale_events():
    assert API.count("adventure_core.expire_pending(uid)") >= 2, \
        "ทั้ง /walk และ /state ต้องหมดอายุให้ ไม่งั้นรีเฟรชแล้วยังค้าง"


def test_npc_quest_offer_is_kept_server_side():
    """ข้อเสนอต้องเก็บฝั่งเซิร์ฟเวอร์ ไม่งั้นเบราว์เซอร์แต่งของรางวัลเองได้"""
    assert 'set_pending(uid, "npc_quest", offer)' in API
    assert "npc_quest_settle(uid, data," in API


# ── 👹 การเกิดมอนสเตอร์ (เฟส 5.6) ─────────────────────────────────────────────

def _spawn_world(tmp_path, monkeypatch, **over):
    p = {"user_id": 1, "level": 50, "hp": 500, "max_hp": 500, "cash": 0, "bank": 0,
         "inventory": "[]", "current_state": "fighting", "last_event": "none",
         "continent": "main", "race": None, "class_name": None, "status_effects": "{}"}
    p.update(over)
    monkeypatch.setattr(pm, "DB_NAME", str(tmp_path / "t.db"))
    monkeypatch.setattr(pm, "get_player", lambda uid: dict(p))
    monkeypatch.setattr(pm, "update_player_field", lambda uid, f, v: p.__setitem__(f, v))
    monkeypatch.setattr(pm, "update_player_fields", lambda uid, d: p.update(d))
    return p


def test_summon_scroll_locks_the_boss_rank(tmp_path, monkeypatch):
    """ใบเรียกบอสต้องล็อกแรงค์ 100% ไม่ใช่แค่เพิ่มโอกาส — ผู้เล่นจ่ายเงินซื้อมา"""
    for evt, rank in [("mini_summon", "Mini-Boss"), ("main_summon", "Main-Boss"),
                      ("unbeatable_summon", "Unbeatable")]:
        p = _spawn_world(tmp_path, monkeypatch, last_event=evt)
        m = adventure_core.spawn_monster(1, rng=random.Random(7))
        assert m["rank"] == rank, f"{evt} ต้องได้ {rank} ไม่ใช่ {m['rank']}"
        assert p["last_event"] == "monster", "ใบเรียกต้องถูกใช้ไป ไม่งั้นเรียกซ้ำได้ฟรี"


def test_spawned_monster_is_fully_serialisable(tmp_path, monkeypatch):
    """สถานะไฟต์ต้องเซฟลง DB ได้ ไม่งั้นรีเฟรชหน้าเว็บแล้วไฟต์หาย"""
    import json as _json
    _spawn_world(tmp_path, monkeypatch)
    m = adventure_core.spawn_monster(1, rng=random.Random(1))
    _json.dumps(m)                                   # พังตรงนี้ = มีอ็อบเจ็กต์ที่เซฟไม่ได้ปนมา
    assert m["hp"] > 0 and m["hp_max"] == m["hp"]
    assert m["turn"] == 1 and m["buffs"] == {}


def test_monster_name_carries_its_element_badge(tmp_path, monkeypatch):
    _spawn_world(tmp_path, monkeypatch)
    m = adventure_core.spawn_monster(1, rng=random.Random(2))
    assert " · " in m["stats"]["name"], "ชื่อมอนต้องมีป้ายธาตุนำหน้า ผู้เล่นต้องเห็นธาตุทุกครั้ง"


def test_low_level_players_mostly_meet_common_monsters(tmp_path, monkeypatch):
    _spawn_world(tmp_path, monkeypatch, level=1)
    ranks = [adventure_core.spawn_monster(1, rng=random.Random(s))["rank"] for s in range(60)]
    assert ranks.count("Common") > 45, f"เลเวล 1 ต้องเจอ Common เป็นหลัก ได้ {ranks.count('Common')}/60"


def test_discord_and_web_spawn_the_same_way():
    assert "adventure_core.spawn_monster(" in GV, "ดิสยังไม่ได้เรียกตัวเกิดมอนกลาง"


# ── 💸 เนิฟเศรษฐกิจ (2026-08-14) — ปิดเครื่องพิมพ์เงินจากเควส NPC ────────────

def test_trading_with_the_npc_is_a_gamble_not_a_money_printer(world, monkeypatch):
    """ของเดิมสุ่ม 0.5-2.0 เท่า = เฉลี่ย 1.25 เท่า แลกกี่รอบก็กำไร ถือทองคำแท่งพันล้าน
    แลกทีเดียวได้พันสองร้อยล้าน ตอนนี้เฉลี่ยต้องต่ำกว่าทุนเสมอ"""
    monkeypatch.setattr(config_loader, "get_all_items",
                        lambda: {"1": {"name": "ของกลาง", "buy": 5000}})
    total_in = total_out = 0
    for seed in range(200):
        world.update(inventory='["1"]', cash=0, current_state="npc_choice")
        offer = adventure_core.npc_quest_offer(1, rng=random.Random(seed))
        if not offer:
            continue
        adventure_core.npc_quest_settle(1, offer, True)
        kept = pm.load_inventory(world["inventory"])
        total_in += 5000
        total_out += world["cash"] + sum(5000 for i in kept if str(i) == "1")
    assert total_in and total_out < total_in, \
        f"แลกแล้วได้คืนเฉลี่ย {total_out / total_in:.2f} เท่า — เกิน 1 เท่าคือพิมพ์เงินได้ไม่จำกัด"


def test_the_npc_never_asks_for_your_treasures(world, monkeypatch):
    """กันฟอกทองคำแท่งเป็นเงินสด + กันผู้เล่นเผลอแลกของล้ำค่าทิ้ง"""
    monkeypatch.setattr(config_loader, "get_all_items",
                        lambda: {"9": {"name": "ทองคำแท่ง", "buy": 1_000_000_000}})
    world.update(inventory='["9"]', current_state="npc_choice")
    assert adventure_core.npc_quest_offer(1) is None
    assert world["current_state"] == "idle", "ไม่มีอะไรให้แลกก็ต้องปลดสถานะ ไม่ค้าง"


def test_reward_gold_knob_scales_every_source(world, monkeypatch):
    """ปุ่มเดียวปรับทองที่ได้ทั้งเกมจาก Panel — ไม่ต้องแก้โค้ดทีละจุด"""
    monkeypatch.setattr(config_loader, "get_balance",
                        lambda k, d=None: 0.0 if k == "reward.gold_mult" else d)
    world["cash"] = 0

    class Gold(random.Random):
        def random(self): return 0.9
        def choices(self, seq, weights=None, k=1): return [seq[0]]

    adventure_core.resolve_treasure(1, "open", rng=Gold())
    assert world["cash"] == 0, "ตั้งตัวคูณเป็น 0 แล้วต้องไม่ได้ทองเลย"


# ── 💀 ตายแล้วต้องฟื้นได้บนเว็บ (บั๊กจากผู้เล่นจริง 2026-08-14) ───────────────

def test_respawn_puts_you_back_in_the_village_alive(world, monkeypatch):
    monkeypatch.setattr(config_loader, "get_balance",
                        lambda k, d=None: {"drops.respawn_hp_percent": 30,
                                           "death.respawn_fee_tiers": [[0, 500]]}.get(k, d))
    world.update(hp=0, max_hp=260, level=9, cash=10_000, current_state="dead", dungeon_steps=4)
    r = adventure_core.respawn(1)
    assert r["hp"] == 78 and r["fee"] == 500
    assert world["current_state"] == "village" and world["hp"] == 78
    assert world["dungeon_steps"] == 0 and world["cash"] == 9_500


def test_respawn_clears_any_stuck_event(world, tmp_path, monkeypatch):
    """ตายทั้งที่มีเหตุการณ์ค้าง — ถ้าไม่ล้าง ฟื้นแล้วก็ยังเดินไม่ได้อยู่ดี"""
    monkeypatch.setattr(pm, "DB_NAME", str(tmp_path / "t.db"))
    monkeypatch.setattr(config_loader, "get_balance", lambda k, d=None: d)
    adventure_core.set_pending(1, "monster", {"hp": 5})
    world.update(hp=0, current_state="dead")
    adventure_core.respawn(1)
    assert adventure_core.get_pending(1) == (None, {})


def test_the_web_has_a_way_out_of_death():
    """เดิมตายบนเว็บแล้วค้างถาวร ต้องไปกด !play ในดิสถึงจะฟื้นได้"""
    api = pathlib.Path("license_server/web_api.py").read_text(encoding="utf-8")
    js = pathlib.Path("license_server/web_static/play.js").read_text(encoding="utf-8")
    assert '@router.post("/adventure/respawn")' in api
    assert "advRespawnButton(" in js and "ฟื้นคืนชีพ กลับหมู่บ้าน" in js
    assert "st.state === 'dead'" in js, "เปิดหน้ามาแล้วตายค้างอยู่ ก็ต้องเจอปุ่มฟื้น"


def test_you_cannot_farm_respawns_while_alive():
    api = pathlib.Path("license_server/web_api.py").read_text(encoding="utf-8")
    block = api[api.index("def adventure_respawn("):]
    assert 'player.get("current_state") != "dead"' in block


def test_a_stale_lock_state_is_cleared_but_a_real_event_is_not():
    """สถานะค้างที่ไม่มีเหตุการณ์รออยู่จริง = ของเก่าตกค้าง ปลดได้
    แต่ถ้ามีเหตุการณ์ค้างจริง ห้ามปลด ไม่งั้นรีเฟรชหนีกับดักได้"""
    api = pathlib.Path("license_server/web_api.py").read_text(encoding="utf-8")
    assert "_STALE_STATES" in api
    guard = api[api.index("if _p.get(\"current_state\") in _STALE_STATES"):]
    assert "not adventure_core.get_pending(uid)[0]" in guard[:160]


def test_the_npc_values_items_at_their_sell_price_not_their_shop_price(world, monkeypatch):
    """บั๊กจากผู้เล่นจริง: แลกประตูวาร์ปมิติ (ซื้อ 40,000 / ขาย 4,000) ได้ 40,000
    เพราะตีมูลค่าด้วยราคาซื้อ = คุ้มกว่าขายที่ร้าน 9 เท่า ยังพิมพ์เงินได้อยู่"""
    monkeypatch.setattr(config_loader, "get_all_items",
                        lambda: {"52": {"name": "ประตูวาร์ปมิติ", "buy": 40_000, "sell": 4_000}})
    assert adventure_core._item_value(config_loader.get_all_items(), "52") == 4_000

    total = 0
    rounds = 0
    for seed in range(200):
        world.update(inventory='["52"]', cash=0, current_state="npc_choice")
        offer = adventure_core.npc_quest_offer(1, rng=random.Random(seed))
        if not offer:
            continue
        adventure_core.npc_quest_settle(1, offer, True)
        kept = pm.load_inventory(world["inventory"])
        total += world["cash"] + sum(4_000 for i in kept if str(i) == "52")
        rounds += 1
    avg = total / max(1, rounds)
    assert avg < 4_000, f"แลกแล้วได้เฉลี่ย {avg:,.0f} — เกินราคาขาย 4,000 คือยังพิมพ์เงินได้"


def test_items_without_a_sell_price_are_still_valued_sanely(world, monkeypatch):
    """ของที่แอดมินลืมตั้งราคาขาย ต้องไม่ถูกตีเป็น 0 (แลกฟรีไม่จำกัด)"""
    items = {"9": {"name": "ของลืมตั้งราคาขาย", "buy": 9_000}}
    assert adventure_core._item_value(items, "9") == 3_000
    assert adventure_core._item_value(items, "ไม่มีไอเทมนี้") == 0
