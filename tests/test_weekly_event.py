"""ทดสอบ helper ของ cog ประกาศธีมรายสัปดาห์ (ส่วน loop/Discord ทดสอบ manual)"""
import datetime

import bot.models.player_model as player_model
from bot.cogs import weekly_event as we


def test_state_roundtrip_and_overwrite(tmp_path, monkeypatch):
    monkeypatch.setattr(player_model, "DB_NAME", str(tmp_path / "state.db"))
    assert we.get_state("announced_week") is None
    we.set_state("announced_week", "2026-W30")
    assert we.get_state("announced_week") == "2026-W30"
    we.set_state("announced_week", "2026-W31")
    assert we.get_state("announced_week") == "2026-W31"


def test_current_week_key_changes_on_monday():
    monday = datetime.date(2026, 7, 27)      # วันจันทร์
    sunday_before = monday - datetime.timedelta(days=1)
    same_week_later = monday + datetime.timedelta(days=6)
    assert we.current_week_key(sunday_before) != we.current_week_key(monday)
    assert we.current_week_key(monday) == we.current_week_key(same_week_later)


def test_week_key_same_seed_as_theme_picker(monkeypatch):
    """key ที่จดกันประกาศซ้ำ กับ seed ที่ใช้เลือกธีม ต้องอิงสัปดาห์เดียวกัน"""
    from bot import game_modifiers as gm
    themes = [{"key": "a"}, {"key": "b"}]
    monkeypatch.setattr(gm, "WEEKLY_THEMES", themes)
    day = datetime.date(2026, 7, 27)
    same_week = day + datetime.timedelta(days=3)
    assert we.current_week_key(day) == we.current_week_key(same_week)
    assert gm.get_weekly_theme(day) is gm.get_weekly_theme(same_week)


def test_build_announce_embed():
    theme = {"key": "x", "label": "ทดสอบ", "description": "คำอธิบายธีม"}
    embed = we.build_announce_embed(theme)
    assert "ทดสอบ" in embed.title
    assert embed.description == "คำอธิบายธีม"
