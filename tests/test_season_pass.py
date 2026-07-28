"""C2: Season Pass รายเดือน — สายฟรี/พรีเมียม, รับรางวัลครั้งเดียว, เปลี่ยนซีซั่นเอง"""
import datetime
import json

import pytest

import bot.models.player_model as pm
from bot import config_loader, season

CFG = {"season_pass": {"enabled": True, "price_gold": 5000000, "tiers": [
    {"points": 100, "free": {"gold": 1000}, "premium": {"gold": 5000}},
    {"points": 500, "free": {"gold": 2000}, "premium": {"gold": 9000}},
]}}


@pytest.fixture
def world(tmp_path, monkeypatch):
    monkeypatch.setattr(pm, "DB_NAME", str(tmp_path / "t.db"))
    monkeypatch.setattr(config_loader, "get_config", lambda: CFG)
    state = {"cash": 6000000, "bank": 0, "inventory": "[]"}
    monkeypatch.setattr(pm, "get_player", lambda uid: dict(state))
    monkeypatch.setattr(pm, "update_player_field", lambda uid, f, v: state.__setitem__(f, v))
    monkeypatch.setattr(pm, "add_exp", lambda uid, exp: None)
    return state


def test_season_key_is_the_month():
    assert pm.season_key(datetime.date(2026, 7, 28)) == "2026-07"
    assert pm.season_key(datetime.date(2026, 8, 1)) == "2026-08"   # เดือนใหม่ = ซีซั่นใหม่เอง


def test_points_reset_between_seasons(world):
    pm.add_season_points(1, 300, season="2026-07")
    assert pm.get_season_points(1, "2026-07") == 300
    assert pm.get_season_points(1, "2026-08") == 0


def test_free_track_only_without_premium(world):
    pm.add_season_points(1, 600)
    msg = season.claim_all(1)
    assert world["bank"] == 1000 + 2000                 # ได้เฉพาะสายฟรีสองขั้น
    assert "พรีเมียม" not in msg

    assert "ยังไม่มีรางวัล" in season.claim_all(1)      # รับซ้ำไม่ได้
    assert world["bank"] == 3000


def test_premium_unlocks_the_second_track(world):
    pm.add_season_points(1, 600)
    season.claim_all(1)                                 # เก็บสายฟรีไปก่อน
    ok, _msg = season.buy_premium(1)
    assert ok and world["cash"] == 6000000 - 5000000

    season.claim_all(1)
    assert world["bank"] == 3000 + 5000 + 9000          # ย้อนเก็บสายพรีเมียมของขั้นที่ปลดไว้แล้วได้


def test_locked_tier_pays_nothing(world):
    pm.add_season_points(1, 99)
    season.claim_all(1)
    assert world["bank"] == 0


def test_buy_requires_enough_cash(world):
    world["cash"] = 10
    ok, msg = season.buy_premium(1)
    assert not ok and "!payment" in msg                 # ชี้ทางไปเติมเงินระบบเดิม
    assert not season.is_premium(1)


def test_admin_grant_is_idempotent(world):
    assert season.grant_premium(1) is True
    assert season.grant_premium(1) is False
    assert season.is_premium(1)


def test_premium_is_per_season(world):
    season.grant_premium(1, season="2026-07")
    assert season.is_premium(1, "2026-07")
    assert not season.is_premium(1, "2026-08")          # ซีซั่นใหม่ต้องซื้อใหม่ = รายได้ต่อเนื่อง


def test_embed_shows_both_tracks(world):
    pm.add_season_points(1, 150)
    embed = season.build_season_embed(1, "T")
    text = "\n".join(f.name + f.value for f in embed.fields)
    assert "🆓" in text and "⭐" in text
    assert "กดรับได้" in text and "ต้องเปิดพรีเมียม" in text and "ยังไม่ถึง" in text


def test_config_tiers_sorted():
    tiers = json.load(open("config.example.json", encoding="utf-8"))["season_pass"]["tiers"]
    pts = [t["points"] for t in tiers]
    assert pts == sorted(pts), "ขั้นต้องเรียงจากน้อยไปมาก (claim_all หยุดที่ขั้นแรกที่ยังไม่ถึง)"


def test_points_come_from_add_exp():
    import pathlib
    src = pathlib.Path("bot/models/player_model.py").read_text(encoding="utf-8")
    add_exp = src[src.index("def add_exp("):src.index("def add_exp(") + 800]
    assert "add_season_points" in add_exp and "add_weekly_points" in add_exp
