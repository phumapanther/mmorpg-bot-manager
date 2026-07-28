"""C8: ความสำเร็จ + ตำแหน่งอวด — คำนวณจากสถิติที่เกมเก็บอยู่แล้ว ไม่มีตัวนับใหม่"""
import json

import pytest

import bot.models.player_model as pm
from bot import achievements, config_loader

DEFS = [
    {"key": "kills_50", "stat": "kills", "target": 50, "label": "🗡️ ฝึกหัด", "gold": 30000, "title": "นักล่าฝึกหัด"},
    {"key": "boss_10", "stat": "boss_kills", "target": 10, "label": "👑 นักล่าบอส", "gold": 150000, "title": "นักล่าบอส"},
    {"key": "rich_1b", "stat": "wealth", "target": 1000000000, "label": "💎 พันล้าน", "gold": 5000000, "title": "มหาเศรษฐี"},
]


@pytest.fixture
def world(tmp_path, monkeypatch):
    monkeypatch.setattr(pm, "DB_NAME", str(tmp_path / "t.db"))
    monkeypatch.setattr(config_loader, "get_config", lambda: {"achievements": DEFS})
    state = {"bank": 0, "cash": 5000, "level": 9, "total_text": 0, "total_online_time": 0, "title": ""}
    monkeypatch.setattr(pm, "get_player", lambda uid: dict(state))
    monkeypatch.setattr(pm, "update_player_field",
                        lambda uid, f, v: state.__setitem__(f, v))
    return state


def test_stats_come_from_existing_tables(world):
    pm.record_bestiary_kill(1, "main", "Common")
    pm.record_bestiary_kill(1, "main", "Common")
    pm.record_bestiary_kill(1, "abyss", "Main-Boss")
    stats = achievements.player_stats(1)
    assert stats["kills"] == 3 and stats["boss_kills"] == 1 and stats["continents"] == 2


def test_unlock_pays_once_only(world):
    for _ in range(50):
        pm.record_bestiary_kill(1, "main", "Common")

    first = achievements.check_and_unlock(1)
    assert [a["key"] for a in first] == ["kills_50"]
    assert world["bank"] == 30000                      # รางวัลเข้าธนาคาร ไม่ใช่เงินสด

    assert achievements.check_and_unlock(1) == []      # เรียกซ้ำต้องไม่จ่ายซ้ำ
    assert world["bank"] == 30000


def test_no_rewrites_once_unlocked(world, monkeypatch):
    """คนที่ปลดครบแล้วฆ่ามอนอีก ต้องไม่สั่งเขียน DB ซ้ำเลย
    (เคยยิง claim_once ทุกอันทุกครั้ง = 13 write transaction ต่อการฆ่ามอน 1 ตัว)"""
    world["bank"] = 2000000000
    for _ in range(60):
        pm.record_bestiary_kill(1, "main", "Common")
    achievements.check_and_unlock(1)                 # ปลดรอบแรก

    calls = []
    real = pm.claim_once
    monkeypatch.setattr(pm, "claim_once", lambda u, k: calls.append(k) or real(u, k))
    for _ in range(5):
        achievements.check_and_unlock(1)
    assert calls == [], f"เขียนซ้ำเปล่า ๆ {len(calls)} ครั้ง"


def test_locked_when_below_target(world):
    for _ in range(9):
        pm.record_bestiary_kill(1, "main", "Main-Boss")   # บอส 9 ตัว ยังไม่ถึง 10
    assert [a["key"] for a in achievements.check_and_unlock(1)] == []


def test_retroactive_for_old_players(world):
    """คนที่รวยอยู่ก่อนมีฟีเจอร์นี้ ต้องได้ทันทีที่เปิดหน้าแรก ไม่ต้องเริ่มนับใหม่"""
    world["bank"] = 2000000000
    assert "rich_1b" in [a["key"] for a in achievements.check_and_unlock(1)]


def test_title_must_be_unlocked_first(world):
    ok, msg = achievements.set_title(1, "มหาเศรษฐี")
    assert not ok and "ยังไม่ได้ปลดล็อก" in msg
    assert world["title"] == ""

    world["bank"] = 1000000000
    achievements.check_and_unlock(1)
    ok, _msg = achievements.set_title(1, "มหาเศรษฐี")
    assert ok and world["title"] == "มหาเศรษฐี"

    ok, _msg = achievements.set_title(1, "")           # ถอดออกได้เสมอ
    assert ok and world["title"] == ""


def test_unlock_message_mentions_reward(world):
    msg = achievements.unlock_message(DEFS[:1])
    assert "🗡️ ฝึกหัด" in msg and "30,000" in msg and "นักล่าฝึกหัด" in msg
    assert achievements.unlock_message([]) == ""


def test_profile_shows_title():
    from types import SimpleNamespace

    from bot.views.profile_embed import create_profile_embed
    member = SimpleNamespace(display_name="T", roles=[],
                             display_avatar=SimpleNamespace(url="https://x/a.png"))
    embed = create_profile_embed(member, {"level": 5, "title": "ผู้พิชิตทุกทวีป"})
    assert "ผู้พิชิตทุกทวีป" in (embed.description or "")


def test_config_and_wiring():
    cfg = json.load(open("config.example.json", encoding="utf-8"))
    keys = [a["key"] for a in cfg["achievements"]]
    assert len(keys) == len(set(keys)), "คีย์ซ้ำ = ปลดล็อกเพี้ยน"
    stats = achievements.player_stats.__doc__ and set(a["stat"] for a in cfg["achievements"])
    assert stats <= {"kills", "boss_kills", "continents", "level", "wealth", "streak", "text", "online_hours"}
    assert "title" in pm.NEW_PLAYER_DEFAULTS

    import pathlib
    src = pathlib.Path("bot/views/game_views.py").read_text(encoding="utf-8")
    assert "check_and_unlock" in src, "ต้องเช็คความสำเร็จตอนล้มมอน ไม่ใช่แค่ตอนเปิดหน้า"

    from bot.views.menu_view import GameMenuView
    assert any("ความสำเร็จ" in (b.label or "") for b in GameMenuView().children)
