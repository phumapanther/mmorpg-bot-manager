"""C1: เควสรายวัน + Login Streak"""
import sqlite3

import bot.daily as daily
import bot.models.player_model as pm
from bot import config_loader


def _db(tmp_path, monkeypatch):
    monkeypatch.setattr(pm, "DB_NAME", str(tmp_path / "t.db"))


def test_progress_and_claim(tmp_path, monkeypatch):
    _db(tmp_path, monkeypatch)
    assert pm.add_daily_progress(1, "kill", 3) == 3
    assert pm.add_daily_progress(1, "kill", 2) == 5          # สะสมต่อ
    assert pm.get_daily_progress(1)["kill"] == (5, False)
    assert pm.claim_daily(1, "kill") is True
    assert pm.claim_daily(1, "kill") is False                # รับซ้ำไม่ได้
    assert pm.get_daily_progress(1)["kill"][1] is True


def test_progress_separate_per_day(tmp_path, monkeypatch):
    _db(tmp_path, monkeypatch)
    pm.add_daily_progress(1, "kill", 5, day="2026-07-27")
    assert pm.get_daily_progress(1, day="2026-07-28") == {}   # วันใหม่เริ่มนับใหม่


def test_login_streak(tmp_path, monkeypatch):
    _db(tmp_path, monkeypatch)
    assert pm.touch_login_streak(1, "2026-07-01") == (1, 1, True)
    assert pm.touch_login_streak(1, "2026-07-01") == (1, 1, False)   # วันเดิมไม่นับซ้ำ
    assert pm.touch_login_streak(1, "2026-07-02") == (2, 2, True)    # ต่อเนื่อง
    assert pm.touch_login_streak(1, "2026-07-05") == (1, 2, True)    # ขาดวัน → เริ่มใหม่ แต่ best คงเดิม


def test_claim_all_pays_only_completed(tmp_path, monkeypatch):
    _db(tmp_path, monkeypatch)
    saved = {}
    monkeypatch.setattr(pm, "get_player", lambda uid: {"cash": 1000, "inventory": ""})
    monkeypatch.setattr(pm, "update_player_field", lambda uid, f, v: saved.__setitem__(f, v))
    monkeypatch.setattr(pm, "add_exp", lambda uid, e: (False, 1, 0))
    monkeypatch.setattr(config_loader, "get_daily_quests",
                        lambda: [{"key": "kill", "label": "ล่ามอน", "target": 5, "gold": 500, "exp": 10},
                                 {"key": "walk", "label": "เดินทาง", "target": 10, "gold": 300, "exp": 5}])
    monkeypatch.setattr(config_loader, "get_daily_cfg", lambda k, d=None: {} if k == "all_clear_bonus" else d)

    pm.add_daily_progress(1, "kill", 5)      # ครบ
    pm.add_daily_progress(1, "walk", 2)      # ยังไม่ครบ
    msg = daily.claim_all(1)
    assert "ล่ามอน" in msg and "เดินทาง" not in msg
    assert saved["cash"] == 1500              # ได้เฉพาะเควสที่ครบ
    assert "ยังไม่มีภารกิจ" in daily.claim_all(1)   # รับซ้ำไม่ได้


def test_track_ignores_unknown_quest(tmp_path, monkeypatch):
    _db(tmp_path, monkeypatch)
    monkeypatch.setattr(config_loader, "get_daily_quests", lambda: [{"key": "kill", "target": 1}])
    daily.track(1, "ไม่มีเควสนี้", 5)
    assert pm.get_daily_progress(1) == {}
    daily.track(1, "kill", 1)
    assert pm.get_daily_progress(1)["kill"][0] == 1


def test_hooks_wired():
    """ต้องมี hook นับเควสจริงในเกม ไม่ใช่แค่มีระบบ"""
    import pathlib
    gv = pathlib.Path("bot/views/game_views.py").read_text(encoding="utf-8")
    pc = pathlib.Path("bot/cogs/player_commands.py").read_text(encoding="utf-8")
    assert '_daily.track(self.user_id, "kill"' in gv and '"boss"' in gv
    # นับก้าวเดินย้ายไป adventure_core แล้ว (เว็บเกม เฟส 5.4) — เดินบนเว็บก็ต้องนับเควสด้วย
    core = pathlib.Path("bot/adventure_core.py").read_text(encoding="utf-8")
    assert '_daily.track(user_id, "walk"' in core
    assert '_daily.track(user_id, "item"' in pc
