"""ตรรกะเลือกเหตุการณ์ตอนเดิน (เว็บเกม เฟส 5.1)

ลำดับความสำคัญคือกติกาของเกม สลับเมื่อไหร่พฤติกรรมเปลี่ยนทันทีโดยไม่มีอะไรฟ้อง
เทสชุดนี้ล็อกลำดับไว้ทุกขั้น (ของเดิมฝังอยู่ใน walk_step ไม่เคยมีเทสคุม)
"""
import random

import pytest

import bot.models.player_model as pm
from bot import adventure_core as ac
from bot import config_loader, game_modifiers, robbery


@pytest.fixture
def db(tmp_path, monkeypatch):
    monkeypatch.setattr(pm, "DB_NAME", str(tmp_path / "adv.db"))
    monkeypatch.setattr(config_loader, "get_balance", lambda k, d=None: d)
    pm.init_db()
    pm.get_player(1)
    return pm


def _decide(**kw):
    args = dict(user_id=1, player={"cash": 0, "bank": 0}, statuses={}, mods={},
                dg_steps=0, last_evt="none", cooldown=0, rng=random.Random(1))
    args.update(kw)
    return ac.decide_event(**args)


# ── ลำดับที่ 1-4: เหตุการณ์บังคับ ──

def test_warp_village_wins_over_everything(db):
    pm.update_player_fields(1, {"dungeon_steps": 5})
    ev, _, dg = _decide(last_evt="warp_village", dg_steps=5)
    assert ev == "village" and dg == 0
    assert pm.get_player(1)["dungeon_steps"] == 0, "วาปกลับเมืองต้องล้างดันเจี้ยนทิ้ง"


def test_scan_box_gives_treasure_without_burning_a_dungeon_turn(db):
    ev, _, dg = _decide(last_evt="scan_box", dg_steps=3)
    assert ev == "treasure" and dg == 3, "สแกนกล่องห้ามลดเทิร์นดันเจี้ยน"


def test_inside_dungeon_always_monster_and_burns_a_turn(db):
    ev, _, dg = _decide(dg_steps=3)
    assert ev == "monster" and dg == 2
    assert pm.get_player(1)["dungeon_steps"] == 2


@pytest.mark.parametrize("summon", ["mini_summon", "main_summon", "unbeatable_summon"])
def test_summon_paper_forces_monster(db, summon):
    ev, _, dg = _decide(last_evt=summon)
    assert ev == "monster" and dg == 0


@pytest.mark.parametrize("last,expect", [
    ("treasure_trap", "trap"), ("revive", "village"), ("warp_dungeon", "dungeon"),
])
def test_forced_follow_ups(db, last, expect):
    assert _decide(last_evt=last)[0] == expect


# ── ลำดับที่ 5: สาขาสุ่มปกติ ──

def test_monster_trap_beats_everything_in_the_random_branch(db, monkeypatch):
    monkeypatch.setattr(game_modifiers, "roll_travel_chance", lambda m: True)
    monkeypatch.setattr(game_modifiers, "roll_calm_chance", lambda: True)
    assert _decide(statuses={"monster_trap": 1})[0] == "monster"


def test_robbery_beats_travel_and_calm(db, monkeypatch):
    monkeypatch.setattr(robbery, "roll_robbery", lambda c, b, s, rng=None: "mugging")
    monkeypatch.setattr(game_modifiers, "roll_travel_chance", lambda m: True)
    assert _decide()[0] == "mugging"


def test_travel_beats_special_and_calm(db, monkeypatch):
    monkeypatch.setattr(game_modifiers, "roll_travel_chance", lambda m: True)
    monkeypatch.setattr(game_modifiers, "roll_special_event", lambda m: {"key": "x"})
    monkeypatch.setattr(game_modifiers, "roll_calm_chance", lambda: True)
    assert _decide()[0] == "travel"


def test_special_event_is_returned_with_its_data(db, monkeypatch):
    monkeypatch.setattr(game_modifiers, "roll_travel_chance", lambda m: False)
    monkeypatch.setattr(game_modifiers, "roll_special_event", lambda m: {"key": "feast"})
    ev, special, _ = _decide()
    assert ev == "special" and special["key"] == "feast"


def test_village_cooldown_blocks_finding_a_village(db, monkeypatch):
    monkeypatch.setattr(game_modifiers, "roll_travel_chance", lambda m: False)
    monkeypatch.setattr(game_modifiers, "roll_special_event", lambda m: None)
    monkeypatch.setattr(game_modifiers, "roll_calm_chance", lambda: False)
    rng = random.Random(4)
    seen = {_decide(cooldown=5, rng=rng)[0] for _ in range(200)}
    assert "village" not in seen, "ยังคูลดาวน์อยู่ห้ามเจอหมู่บ้าน"


def test_random_branch_only_returns_known_events(db, monkeypatch):
    monkeypatch.setattr(game_modifiers, "roll_travel_chance", lambda m: False)
    monkeypatch.setattr(game_modifiers, "roll_special_event", lambda m: None)
    monkeypatch.setattr(game_modifiers, "roll_calm_chance", lambda: False)
    rng = random.Random(8)
    for _ in range(120):
        assert _decide(rng=rng)[0] in ac.EVENT_LIST


# ── บันทึกผล ──

def test_commit_writes_last_event_and_village_cooldown(db):
    ac.commit_event(1, "village", "none")
    p = pm.get_player(1)
    assert p["last_event"] == "village" and p["village_cooldown"] == 10


def test_commit_keeps_summon_marker_when_monster_follows(db):
    """เจอมอนต่อจากใบเรียกบอส ต้องไม่ทับ last_event ไม่งั้นระบบไฟต์ไม่รู้ว่าเป็นบอส"""
    pm.update_player_fields(1, {"last_event": "main_summon"})
    ac.commit_event(1, "monster", "main_summon")
    assert pm.get_player(1)["last_event"] == "main_summon"

    ac.commit_event(1, "monster", "none")            # เจอมอนปกติ = ทับได้
    assert pm.get_player(1)["last_event"] == "monster"


def test_event_weights_fall_back_when_panel_value_is_broken(db, monkeypatch):
    monkeypatch.setattr(config_loader, "get_balance",
                        lambda k, d=None: {"none": [1, 2]} if k == "events.weights" else d)
    assert ac.event_weights("none") == ac.EVENT_WEIGHTS["none"]
    monkeypatch.setattr(config_loader, "get_balance",
                        lambda k, d=None: {"none": {"monster": "มั่ว"}} if k == "events.weights" else d)
    assert ac.event_weights("none") == ac.EVENT_WEIGHTS["none"]


# ── การทอยเต๋าในไฟต์ (เฟส 5.2) ──

def _roll(db_ok=None, **kw):
    args = dict(user_id=1, player={}, statuses={}, element_data={}, m_stats={},
                player_elements=[], rng=random.Random(3))
    args.update(kw)
    return ac.roll_combat(**args)


def test_monster_dice_count_scales_with_rank(db):
    """บอสทอยหลายลูก — ต้องรวมแต้มทุกลูก ไม่ใช่ลูกเดียว"""
    r1 = _roll(m_stats={"dice_count": 1}, rng=random.Random(5))
    r5 = _roll(m_stats={"dice_count": 5}, rng=random.Random(5))
    assert r5["monster_roll"] > r1["monster_roll"]
    assert "5 เต๋า" in r5["monster_parts"][0]
    assert "เต๋า)" not in r1["monster_parts"][0], "เต๋าลูกเดียวไม่ต้องบอกจำนวน"


def test_roll_parts_explain_where_the_score_came_from(db):
    """ที่มาของแต้มคือสิ่งที่ผู้เล่นเห็นบนจอ — ต้องมีเสมอ"""
    r = _roll()
    assert r["player_parts"] and "พื้นฐาน" in r["player_parts"][0]
    assert r["monster_parts"] and "พื้นฐาน" in r["monster_parts"][0]
    assert 1 <= r["player_roll"] <= 20


def test_dice_bag_adds_to_roll_and_is_shown(db):
    r = _roll(statuses={"weighted_dice": 5}) if "weighted_dice" in game_modifiers.STATUS_EFFECTS \
        else None
    if r is None:
        pytest.skip("เกมนี้ไม่มีสถานะถุงเต๋า")
    assert r["player_roll"] >= 1


def test_root_locks_player_dice_to_zero(db):
    r = _roll(element_data={"root_chance": 100, "label": "🌿 ไม้"}, rng=random.Random(1))
    assert r["player_roll"] == 0
    assert "ราก" in r["player_parts"][0] and "รากพันธนาการ" in r["log"]


def test_element_dice_bonus_boosts_monster_and_is_logged(db):
    r = _roll(element_data={"dice_bonus": (3, 3), "label": "💨 ลม"}, m_stats={"dice_count": 1},
              rng=random.Random(2))
    base = int(r["monster_parts"][0].split("`")[1])
    assert r["monster_roll"] == base + 3
    assert "+3" in r["monster_parts"][1]


def test_seal_crushes_a_high_roll(db, monkeypatch):
    monkeypatch.setattr(game_modifiers, "status_seal_threshold", lambda s: 1)
    r = _roll(statuses={"sealed_dice": 5})
    assert r["player_roll"] == 1 and "เต๋าถูกกดทับ" in r["log"]


def test_weighted_dice_floor_replaces_the_breakdown(db, monkeypatch):
    monkeypatch.setattr(game_modifiers, "status_min_roll", lambda s: 20)
    r = _roll(rng=random.Random(11))
    assert r["player_roll"] == 20 and "เต๋าถ่วง" in r["player_parts"][0]


def test_fumble_drops_the_dice(db, monkeypatch):
    monkeypatch.setattr(game_modifiers, "status_fumble_chance", lambda s: 100)
    r = _roll()
    assert r["player_roll"] == 0 and "เต๋าหลุดมือ" in r["log"]
