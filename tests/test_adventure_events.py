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
    assert 'player.get("current_state") != _WEB_PLAYABLE.get(event)' in API
    assert "adventure_core.clear_pending(uid)" in API
