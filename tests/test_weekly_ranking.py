"""C3: อันดับรายสัปดาห์ + รางวัลท็อป 3"""
import datetime
import json

import pytest

import bot.cogs.weekly_event as we
import bot.models.player_model as pm
from bot import config_loader


@pytest.fixture
def db(tmp_path, monkeypatch):
    monkeypatch.setattr(pm, "DB_NAME", str(tmp_path / "t.db"))
    return tmp_path


def test_points_accumulate_per_week(db):
    pm.add_weekly_points(1, 300, week="2026-W10")
    pm.add_weekly_points(1, 200, week="2026-W10")
    pm.add_weekly_points(1, 999, week="2026-W11")      # สัปดาห์อื่นต้องแยกกอง
    pm.add_weekly_points(2, 400, week="2026-W10")

    assert pm.get_weekly_top(10, "2026-W10") == [(1, 500), (2, 400)]
    assert pm.get_weekly_top(10, "2026-W11") == [(1, 999)]


def test_negative_points_ignored(db):
    pm.add_weekly_points(1, -50, week="2026-W10")      # EXP ติดลบต้องไม่ทำแต้มเพี้ยน
    assert pm.get_weekly_top(10, "2026-W10") == []


def test_my_rank(db):
    for uid, pts in [(1, 900), (2, 500), (3, 100)]:
        pm.add_weekly_points(uid, pts, week=pm.week_key())
    rank, pts, total = pm.get_my_weekly_rank(2)
    assert (rank, pts, total) == (2, 500, 3)
    assert pm.get_my_weekly_rank(99)[0] == 4           # ยังไม่มีแต้ม = ต่อท้าย


def test_week_key_matches_the_cog():
    """คีย์สัปดาห์ต้องเป็นสตริงเดียวกันทั้งสองฝั่ง ไม่งั้นจ่ายรางวัลผิดสัปดาห์"""
    day = datetime.date(2026, 7, 28)
    assert pm.week_key(day) == we.current_week_key(day)
    assert we.previous_week_key(day) == pm.week_key(day - datetime.timedelta(days=7))


def test_add_exp_feeds_the_board(db, monkeypatch):
    """แต้มต้องมาจาก add_exp จุดเดียว — ล่ามอน/บอส/เควส เข้าอันดับหมดโดยไม่ต้อง hook เพิ่ม"""
    monkeypatch.setattr(pm, "get_player", lambda uid: {"exp": 0, "level": 1, "max_hp": 100})
    monkeypatch.setattr(pm, "update_player_fields", lambda *a, **k: None)
    monkeypatch.setattr(pm, "update_player_field", lambda *a, **k: None)
    pm.add_exp(7, 250)
    assert pm.get_weekly_top(10) == [(7, 250)]


def test_payout_top3_into_bank(db, monkeypatch):
    for uid, pts in [(1, 5000), (2, 3000), (3, 1000), (4, 50)]:
        pm.add_weekly_points(uid, pts, week="2026-W10")

    banked, exp_given = {}, []
    monkeypatch.setattr(pm, "get_player", lambda uid: {"bank": 1000, "cash": 0})
    monkeypatch.setattr(pm, "update_player_field",
                        lambda uid, field, val: banked.__setitem__((uid, field), val))
    monkeypatch.setattr(pm, "add_exp", lambda uid, exp: exp_given.append((uid, exp)))
    monkeypatch.setattr(config_loader, "get_config", lambda: {"weekly_ranking": {
        "enabled": True, "min_points": 100,
        "rewards": [{"gold": 300000, "exp": 5000}, {"gold": 150000, "exp": 2500},
                    {"gold": 75000, "exp": 1000}]}})

    paid = we.pay_weekly_ranking("2026-W10")

    assert [p[0] for p in paid] == [1, 2, 3]                  # อันดับ 4 ไม่ได้รางวัล
    assert banked[(1, "bank")] == 1000 + 300000               # เข้าธนาคาร ไม่ใช่เงินสด (ตายแล้วไม่หาย)
    assert banked[(3, "bank")] == 1000 + 75000
    assert exp_given == [(1, 5000), (2, 2500), (3, 1000)]


def test_payout_respects_min_points(db, monkeypatch):
    pm.add_weekly_points(1, 20, week="2026-W10")
    monkeypatch.setattr(config_loader, "get_config", lambda: {"weekly_ranking": {
        "enabled": True, "min_points": 100, "rewards": [{"gold": 1, "exp": 0}]}})
    assert we.pay_weekly_ranking("2026-W10") == []


def test_config_has_weekly_section():
    cfg = json.load(open("config.example.json", encoding="utf-8"))["weekly_ranking"]
    assert len(cfg["rewards"]) == 3 and cfg["rewards"][0]["gold"] > cfg["rewards"][2]["gold"]


def test_board_wired_into_existing_top():
    """หมวดใหม่ต้องเสียบกับระบบ !top เดิม ไม่ใช่สร้างคำสั่งใหม่"""
    from bot.cogs.player_commands import TOP_KINDS
    from bot.views.menu_view import TopBoardView
    assert "weekly" in TOP_KINDS
    assert ("🗓️ สัปดาห์นี้", "weekly") in TopBoardView.KINDS
    assert len(TopBoardView(1).children) == 5
