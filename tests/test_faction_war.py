"""P5 สงครามฝ่าย: ฝ่ายจากยศ + ธีม + แต้มสงคราม + แชมเปี้ยนเกิดในไฟต์"""
import random
import sqlite3
from types import SimpleNamespace

import bot.game_modifiers as gm
import bot.models.player_model as pm


def test_resolve_faction():
    assert gm.resolve_player_faction(["、🐉 • มังกร"]) == "human"
    assert gm.resolve_player_faction(["• Lich 🧙🏽‍♂️"]) == "demon"
    assert gm.resolve_player_faction(["Warrior"]) is None
    assert gm.resolve_player_faction([]) is None
    # ถือสองฝ่าย = มนุษย์ก่อน
    assert gm.resolve_player_faction(["、👹 • ยักษ์", "• Ogre 👹"]) == "human"


def test_theme_registered_and_merged():
    theme = gm.get_theme_by_key("faction_war")
    assert theme and theme["mods"]["faction_war"]["chance"] == 25
    mods = gm.get_active_modifiers({"continent": "main"}, theme_override="faction_war") \
        if "theme_override" in gm.get_active_modifiers.__code__.co_varnames else None
    # merge ผ่านตัวจริง: จำลองธีมด้วย THEME_OVERRIDE
    old = gm.THEME_OVERRIDE
    gm.THEME_OVERRIDE = "faction_war"
    try:
        mods = gm.get_active_modifiers({"continent": "main"})
        assert mods.get("faction_war") == {"chance": 25}
    finally:
        gm.THEME_OVERRIDE = old


def test_war_scores(tmp_path, monkeypatch):
    monkeypatch.setattr(pm, "DB_NAME", str(tmp_path / "t.db"))
    assert pm.get_faction_war_scores("2026-W01") == {"human": 0, "demon": 0}
    pm.add_faction_war_point("human", "2026-W01")
    pm.add_faction_war_point("human", "2026-W01")
    scores = pm.add_faction_war_point("demon", "2026-W01")
    assert scores == {"human": 2, "demon": 1}
    # คนละสัปดาห์แยกกัน
    assert pm.get_faction_war_scores("2026-W02") == {"human": 0, "demon": 0}


def test_champion_spawn(monkeypatch):
    import bot.views.game_views as gv
    old = gm.THEME_OVERRIDE
    gm.THEME_OVERRIDE = "faction_war"
    monkeypatch.setattr(gv.random, "randint", lambda a, b: 1)  # ผ่านเช็ค chance เสมอ + ค่าอื่นต่ำสุด
    try:
        roles = [SimpleNamespace(name="、🐉 • มังกร")]  # ฝ่ายมนุษย์
        v = gv.MonsterEventView(user_id=1, member_roles=roles)
        assert v.faction_war_side == "human"
        assert v.element == "dark" and "ขุนศึกฝ่ายปีศาจ" in v.m_stats["name"]
        # ไม่มีฝ่าย = ไม่เจอแชมเปี้ยน
        v2 = gv.MonsterEventView(user_id=1, member_roles=[])
        assert v2.faction_war_side is None
    finally:
        gm.THEME_OVERRIDE = old
