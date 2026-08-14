"""เรทเกิดมอนตามเลเวล — ย้ายจากโค้ดเข้า Panel + แท็บ Items ต้องไม่ล้าง effect ทิ้ง"""
import json
import pathlib

import pytest

import bot.views.game_views as gv
from bot import config_loader

RANKS = ["Common", "Mini-Boss", "Main-Boss", "Secret", "Unbeatable"]


def _cfg(monkeypatch, tree):
    monkeypatch.setattr(config_loader, "get_config", lambda: {"game_balance": tree})


def test_defaults_match_the_old_hardcoded_table(monkeypatch):
    _cfg(monkeypatch, {})
    assert gv.spawn_weights_for(100, RANKS) == [10, 30, 20, 25, 15]
    assert gv.spawn_weights_for(50, RANKS) == [50, 20, 20, 8, 2]
    assert gv.spawn_weights_for(5, RANKS) == [95, 2, 1, 1, 1]


def test_picks_the_highest_tier_not_over_the_level(monkeypatch):
    _cfg(monkeypatch, {})
    assert gv.spawn_weights_for(99, RANKS) == gv.DEFAULT_SPAWN_WEIGHTS[90]
    assert gv.spawn_weights_for(49, RANKS) == gv.DEFAULT_SPAWN_WEIGHTS[20]
    assert gv.spawn_weights_for(0, RANKS) == gv.DEFAULT_SPAWN_WEIGHTS[0]


def test_panel_values_win(monkeypatch):
    _cfg(monkeypatch, {"spawn_weights": {
        "0": {"Common": 1, "Mini-Boss": 2, "Main-Boss": 3, "Secret": 4, "Unbeatable": 90}}})
    assert gv.spawn_weights_for(60, RANKS) == [1, 2, 3, 4, 90], "ตั้งช่วงเดียวต้องใช้กับทุกเลเวล"


@pytest.mark.parametrize("junk", [
    {"0": {"Common": "เยอะ"}},
    {"0": {"Common": 0, "Mini-Boss": 0, "Main-Boss": 0, "Secret": 0, "Unbeatable": 0}},
    {"0": []},
    {"ไม่ใช่เลข": {"Common": 5}},
    "พังทั้งก้อน",
])
def test_bad_config_never_breaks_the_roll(monkeypatch, junk):
    """น้ำหนักรวมเป็น 0 หรือค่าเพี้ยน = random.choices จะพังทั้งเกม ต้องตกกลับค่าเดิม"""
    _cfg(monkeypatch, {"spawn_weights": junk})
    w = gv.spawn_weights_for(60, RANKS)
    assert len(w) == len(RANKS) and sum(w) > 0


def test_config_example_has_every_tier():
    cfg = json.load(open("config.example.json", encoding="utf-8"))["game_balance"]["spawn_weights"]
    assert {int(k) for k in cfg} == set(gv.DEFAULT_SPAWN_WEIGHTS)
    for lv, row in cfg.items():
        assert set(row) == set(RANKS), f"ช่วงเลเวล {lv} มีแรงค์ไม่ครบ"
        assert row == dict(zip(RANKS, gv.DEFAULT_SPAWN_WEIGHTS[int(lv)]))


def test_no_hardcoded_tier_left_in_the_fight():
    # การเกิดมอนย้ายไป adventure_core แล้ว (เว็บเกม เฟส 5.6) — เจอมอนบนเว็บต้องใช้เรทเดียวกัน
    src = pathlib.Path("bot/adventure_core.py").read_text(encoding="utf-8")
    assert "spawn_weights = [50, 20, 20, 8, 2]" not in src
    assert 'spawn_weights_for(player.get("level", 0), rank_keys)' in src


def test_panel_table_wired():
    app = pathlib.Path("panel/static/app.js").read_text(encoding="utf-8")
    html = pathlib.Path("panel/static/index.html").read_text(encoding="utf-8")
    assert 'id="balSpawnTable"' in html
    assert "renderSpawnTable" in app and 'data-spawn' in app
    assert "renderSpawnTable();" in app, "ต้องถูกเรียกตอน render แท็บ Balance"


# ── บั๊กที่เจอระหว่างตรวจ: แท็บ Items ล้าง effect ทิ้ง ──

def test_items_tab_knows_every_effect_the_game_uses():
    """เดิมดรอปดาวน์มี effect แค่ 5 แบบ — กดบันทึกทีเดียวไอเทม 38 ชิ้นเลิกทำงาน"""
    app = pathlib.Path("panel/static/app.js").read_text(encoding="utf-8")
    block = app[app.index("const ITEM_EFFECTS = ["):app.index("function renderItemsCatalog")]
    items = json.load(open("config.example.json", encoding="utf-8"))["item_catalog"]["items"]
    used = {v.get("effect") for v in items.values() if v.get("effect")}
    missing = [e for e in used if f'value: "{e}"' not in block]
    assert not missing, f"แท็บ Items ไม่รู้จัก effect เหล่านี้ กดบันทึกแล้วจะโดนล้าง: {missing}"


def test_unknown_effect_is_preserved_not_wiped():
    app = pathlib.Path("panel/static/app.js").read_text(encoding="utf-8")
    assert "ITEM_EFFECTS.some(e => e.value === item.effect)" in app, \
        "effect ที่แอดมินเพิ่มเองต้องถูกเก็บไว้เป็นตัวเลือก ไม่ใช่หายตอนบันทึก"
