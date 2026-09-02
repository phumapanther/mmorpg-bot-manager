"""ค่าที่เคยฟิกในโค้ด ต้องตั้งได้จาก Panel และตั้งเพี้ยนก็ต้องไม่ทำเกมพัง"""
import json

import pytest

import bot.models.player_model as pm
import bot.views.game_views as gv
from bot import config_loader, game_modifiers


def _balance(monkeypatch, tree):
    monkeypatch.setattr(config_loader, "get_config", lambda: {"game_balance": tree})


# ── ตารางน้ำหนักอีเวนต์ ──

def test_event_weights_default_matches_code(monkeypatch):
    _balance(monkeypatch, {})
    assert gv.event_weights("none") == gv.EVENT_WEIGHTS["none"]
    assert gv.event_weights("ไม่มีสถานการณ์นี้") == gv.EVENT_WEIGHTS["none"]


def test_event_weights_from_panel(monkeypatch):
    _balance(monkeypatch, {"events": {"weights": {
        "none": {"monster": 99, "village": 1, "treasure": 2, "dungeon": 3, "npc": 4, "trap": 5}}}})
    assert gv.event_weights("none") == [99, 1, 2, 3, 4, 5]     # เรียงตาม EVENT_LIST


def test_event_weights_survive_garbage(monkeypatch):
    for junk in ({"monster": "มาก"}, [1, 2], "ทั้งก้อนพัง", None):
        _balance(monkeypatch, {"events": {"weights": {"none": junk}}})
        assert gv.event_weights("none") == gv.EVENT_WEIGHTS["none"], f"ค่าเพี้ยน {junk!r} ต้องตกกลับค่าเดิม"


def test_config_example_has_every_situation():
    weights = json.load(open("config.example.json", encoding="utf-8"))["game_balance"]["events"]["weights"]
    assert set(weights) == set(gv.EVENT_WEIGHTS), "ตารางใน config ต้องครบทุกสถานการณ์"
    for row in weights.values():
        assert set(row) == set(gv.EVENT_LIST)


# ── สถานะผิดปกติ ──

def test_status_turns_and_damage_from_panel(monkeypatch):
    base = game_modifiers.STATUS_EFFECTS["poison"]
    _balance(monkeypatch, {"status_overrides": {"poison": {"turns": 3, "dmg_min": 50, "dmg_max": 60}}})
    cfg = game_modifiers.status_cfg("poison")
    assert cfg["default_turns"] == 3 and cfg["step_damage"] == (50, 60)
    assert cfg["cleanse_on"] == base["cleanse_on"], "ของที่ไม่ได้ตั้งต้องคงเดิม"

    applied = game_modifiers.apply_status({}, "poison")
    assert applied["poison"] == 3, "จำนวนเทิร์นที่ติดจริงต้องใช้ค่าจาก Panel"


def test_status_override_swaps_reversed_damage(monkeypatch):
    _balance(monkeypatch, {"status_overrides": {"poison": {"dmg_min": 9, "dmg_max": 2}}})
    assert game_modifiers.status_cfg("poison")["step_damage"] == (2, 9)


def test_status_override_garbage_falls_back(monkeypatch):
    _balance(monkeypatch, {"status_overrides": {"poison": {"turns": "เยอะ"}}})
    assert game_modifiers.status_cfg("poison") == game_modifiers.STATUS_EFFECTS["poison"]


def test_config_example_covers_all_statuses():
    ov = json.load(open("config.example.json", encoding="utf-8"))["game_balance"]["status_overrides"]
    real = {k for k, v in game_modifiers.STATUS_EFFECTS.items() if not v.get("artifact")}
    assert set(ov) == real
    for key, row in ov.items():
        assert row["turns"] == game_modifiers.STATUS_EFFECTS[key].get("default_turns", 1)


# ── ค่าที่เหลือ ──

def test_new_player_starters_from_panel(tmp_path, monkeypatch):
    monkeypatch.setattr(pm, "DB_NAME", str(tmp_path / "t.db"))
    pm.init_db()
    _balance(monkeypatch, {"new_player": {"cash": 777, "capacity": 5, "max_hp": 250, "hp": 250}})
    p = pm.get_player(123456)
    assert p["cash"] == 777 and p["capacity"] == 5 and p["max_hp"] == 250


def test_new_player_defaults_when_unset(tmp_path, monkeypatch):
    monkeypatch.setattr(pm, "DB_NAME", str(tmp_path / "t2.db"))
    pm.init_db()
    _balance(monkeypatch, {})
    p = pm.get_player(999)
    assert p["cash"] == pm.NEW_PLAYER_DEFAULTS["cash"]


@pytest.mark.parametrize("path,default", [
    ("duel.rounds", 5), ("duel.bet", 2000), ("village.heal_fee", 300),
    ("casino.slot_weights", None), ("new_player.cash", 20000),
])
def test_every_new_knob_exists_in_config_example(path, default):
    cfg = json.load(open("config.example.json", encoding="utf-8"))["game_balance"]
    node = cfg
    for part in path.split("."):
        assert part in node, f"ขาด game_balance.{path} ใน config.example.json"
        node = node[part]


def test_code_no_longer_hardcodes_them():
    import pathlib
    checks = [("bot/cogs/pvp_duel.py", "max_rounds = 5"),
              ("bot/cogs/pvp_duel.py", 'increment_player_field(winner[\'user\'].id, "cash", 2000)'),
              ("bot/apps/bot_admin/admin_commands.py", "fee = 300"),
              ("bot/views/game_views.py", "current_weights = list(EVENT_WEIGHTS[last_evt])")]
    for f, needle in checks:
        assert needle not in pathlib.Path(f).read_text(encoding="utf-8"), f"{f} ยังฟิก: {needle}"
