"""ทดสอบเอนจินอีเวนต์พิเศษ (A3) — การสุ่ม, การ merge, และตัวจ่ายผลกับ DB จำลอง"""
import random

import pytest

import bot.models.player_model as player_model
from bot import game_modifiers as gm
from bot.views import game_views as gv


class FakeRng:
    def __init__(self, value):
        self.value = value

    def randint(self, lo, hi):
        return self.value


# ===== การสุ่ม / merge =====

def test_roll_special_event_chance_and_order():
    events = [
        {"key": "a", "chance": 0},
        {"key": "b", "chance": 50},
        {"key": "c", "chance": 100},
    ]
    mods = {"special_events": events}
    assert gm.roll_special_event(mods, FakeRng(50))["key"] == "b"   # ตัวแรกที่ทอยติดชนะ (a ไม่มีทางติด)
    assert gm.roll_special_event(mods, FakeRng(100))["key"] == "c"
    assert gm.roll_special_event({"special_events": []}, FakeRng(1)) is None
    assert gm.roll_special_event(gm.DEFAULT_MODS, FakeRng(1)) is None


def test_special_events_merge_concat(monkeypatch):
    monkeypatch.setitem(gm.CONTINENTS, "testland", {
        "label": "t", "mods": {"special_events": [{"key": "a", "chance": 5}]},
    })
    monkeypatch.setattr(gm, "WEEKLY_THEMES", [{
        "key": "w", "mods": {"special_events": [{"key": "b", "chance": 5}]},
    }])
    merged = gm.get_active_modifiers({"continent": "testland"})["special_events"]
    assert [e["key"] for e in merged] == ["a", "b"]


def test_resolve_instant_weighted():
    event = {"template": "instant", "outcomes": [
        {"weight": 1, "text": "x"}, {"weight": 1, "text": "y"},
    ]}
    rng = random.Random(2)
    picks = {gv.resolve_instant_special(event, rng=rng)["text"] for _ in range(50)}
    assert picks == {"x", "y"}
    assert gv.resolve_instant_special({"outcomes": []}) == {}


# ===== ตัวจ่ายผล (ใช้ DB จำลอง) =====

@pytest.fixture
def game_db(tmp_path, monkeypatch):
    monkeypatch.setattr(player_model, "DB_NAME", str(tmp_path / "game.db"))
    player_model.init_db()
    uid = 777
    player_model.get_player(uid)  # auto-create
    return uid


def test_outcome_gold_gain_and_floor(game_db):
    uid = game_db
    start_cash = player_model.get_player(uid)["cash"]
    lines, died = gv.execute_special_outcome(uid, {"gold": 100})
    assert not died and any("100" in l for l in lines)
    assert player_model.get_player(uid)["cash"] == start_cash + 100
    # เสียเงินมากกว่าที่มี → floor 0 ไม่ติดลบ
    gv.execute_special_outcome(uid, {"gold": -999_999_999})
    assert player_model.get_player(uid)["cash"] == 0


def test_outcome_damage_death_and_heal(game_db):
    uid = game_db
    lines, died = gv.execute_special_outcome(uid, {"damage": 40})
    assert not died
    lines, died = gv.execute_special_outcome(uid, {"damage": 9999})
    assert died
    p = player_model.get_player(uid)
    assert p["hp"] == 0 and p["current_state"] == "dead"
    # ฮีลเต็ม
    gv.execute_special_outcome(uid, {"heal": "full"})
    p = player_model.get_player(uid)
    assert p["hp"] == p["max_hp"]


def test_outcome_items_with_overflow_converts_to_gold(game_db, monkeypatch):
    uid = game_db
    monkeypatch.setattr(gv.config_loader, "get_all_items",
                        lambda: {"11": {"name": "💎 เศษอัญมณีหมองหม่น", "sell": 50}})
    player_model.update_player_fields(uid, {"capacity": 3, "inventory": "[]", "cash": 0})
    lines, died = gv.execute_special_outcome(uid, {"items": {"id": "11", "qty": 10}})
    assert not died
    p = player_model.get_player(uid)
    inv = player_model.load_inventory(p["inventory"])
    assert inv == ["11", "11", "11"]                 # ใส่ได้ 3 ตาม capacity
    assert p["cash"] == 7 * 50                       # ส่วนเกิน 7 ชิ้นแปลงเป็นทองราคาขาย
    assert any("กระเป๋าเต็ม" in l for l in lines)


def test_outcome_items_id_pool_random_pick(game_db, monkeypatch):
    uid = game_db
    monkeypatch.setattr(gv.config_loader, "get_all_items",
                        lambda: {str(i): {"name": f"วัสดุ{i}", "sell": 10} for i in range(9, 19)})
    player_model.update_player_fields(uid, {"capacity": 0, "inventory": "[]"})
    pool = [str(i) for i in range(9, 19)]
    lines, died = gv.execute_special_outcome(uid, {"items": {"id_pool": pool, "qty": 1}})
    assert not died
    inv = player_model.load_inventory(player_model.get_player(uid)["inventory"])
    assert len(inv) == 1 and inv[0] in pool


def test_outcome_status_and_force_continent(game_db):
    uid = game_db
    gv.execute_special_outcome(uid, {"apply_status": {"key": "poison", "turns": 5}})
    p = player_model.get_player(uid)
    assert gm.parse_statuses(p) == {"poison": 5}
    # ล้างทั้งหมด + บังคับย้ายทวีป
    lines, died = gv.execute_special_outcome(uid, {"cleanse_all": True, "force_continent": "main"})
    p = player_model.get_player(uid)
    assert gm.parse_statuses(p) == {}
    assert p["continent"] == "main"


def test_fall_guard_saves_from_island_crash(game_db):
    uid = game_db
    player_model.update_player_fields(uid, {"hp": 100, "max_hp": 100})
    gv.execute_special_outcome(uid, {"apply_status": {"key": "featherfall"}})
    # ร่วงจากเกาะ (ดาเมจหนัก + บังคับย้ายทวีป) — ขนนกกดดาเมจเหลือ <=5 และสลายไป
    lines, died = gv.execute_special_outcome(uid, {"damage": [40, 80], "force_continent": "main"})
    p = player_model.get_player(uid)
    assert not died and p["hp"] >= 95
    assert p["continent"] == "main"
    assert "featherfall" not in gm.parse_statuses(p)
    # ดาเมจธรรมดา (ไม่ใช่การร่วง) ไม่กิน fall_guard
    gv.execute_special_outcome(uid, {"apply_status": {"key": "featherfall"}})
    gv.execute_special_outcome(uid, {"damage": 30})
    assert "featherfall" in gm.parse_statuses(player_model.get_player(uid))


def test_outcome_exp_uses_add_exp(game_db):
    uid = game_db
    start_exp = player_model.get_player(uid)["exp"]
    lines, died = gv.execute_special_outcome(uid, {"exp": 25})
    assert any("25" in l for l in lines)
    assert player_model.get_player(uid)["exp"] >= start_exp  # add_exp อาจเลเวลอัพ/รีเซ็ต exp — เช็คแค่ไม่พัง
