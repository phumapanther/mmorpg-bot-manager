"""C7: คู่หู — ผูกคู่สองทาง, หักเงินทั้งคู่พร้อมกัน, โบนัสเต็มเมื่อคู่เล่นวันเดียวกัน"""
import json
import sqlite3

import pytest

import bot.models.player_model as pm
from bot import config_loader, partner

CFG = {"partner": {"wedding_cost": 500000, "divorce_cost": 1000000,
                   "solo_bonus_percent": 5, "together_bonus_percent": 15}}


@pytest.fixture
def db(tmp_path, monkeypatch):
    path = str(tmp_path / "t.db")
    monkeypatch.setattr(pm, "DB_NAME", path)
    monkeypatch.setattr(config_loader, "get_config", lambda: CFG)
    conn = sqlite3.connect(path)
    conn.execute("CREATE TABLE players (user_id INTEGER PRIMARY KEY, cash INTEGER)")
    conn.executemany("INSERT INTO players VALUES (?, ?)", [(1, 900000), (2, 900000), (3, 900000)])
    conn.commit()
    conn.close()
    monkeypatch.setattr(pm, "get_player", lambda uid: _row(path, uid))
    return path


def _row(path, uid):
    conn = sqlite3.connect(path)
    row = conn.execute("SELECT cash FROM players WHERE user_id = ?", (uid,)).fetchone()
    conn.close()
    return {"cash": row[0]} if row else None


def test_marriage_is_two_way_and_charges_both(db):
    ok, msg = partner.marry(1, 2)
    assert ok and "คู่หู" in msg
    assert partner.partner_of(1)[0] == 2
    assert partner.partner_of(2)[0] == 1
    assert _row(db, 1)["cash"] == 400000 and _row(db, 2)["cash"] == 400000


def test_cannot_marry_yourself_or_someone_taken(db):
    assert partner.marry(1, 1)[0] is False
    partner.marry(1, 2)
    ok, msg = partner.marry(3, 2)
    assert not ok and "อีกฝ่ายมีคู่" in msg
    assert partner.partner_of(3) is None
    assert _row(db, 3)["cash"] == 900000, "แต่งไม่สำเร็จห้ามหักเงิน"


def test_broke_partner_blocks_the_wedding(db):
    conn = sqlite3.connect(db)
    conn.execute("UPDATE players SET cash = 10 WHERE user_id = 2")
    conn.commit()
    conn.close()
    ok, msg = partner.marry(1, 2)
    assert not ok and "ไม่พอ" in msg
    assert partner.partner_of(1) is None
    assert _row(db, 1)["cash"] == 900000, "ห้ามหักฝ่ายที่จ่ายไหวไปข้างเดียว"


def test_divorce_clears_both_sides(db):
    partner.marry(1, 2)                       # เหลือคนละ 400,000
    conn = sqlite3.connect(db)
    conn.execute("UPDATE players SET cash = 2000000 WHERE user_id = 1")   # หาเงินมาจ่ายค่าหย่า
    conn.commit()
    conn.close()

    ok, _msg = partner.divorce(1)
    assert ok
    assert partner.partner_of(1) is None and partner.partner_of(2) is None
    assert _row(db, 1)["cash"] == 1000000, "คนขอหย่าจ่ายค่าดำเนินการ"
    assert _row(db, 2)["cash"] == 400000, "อีกฝ่ายไม่ต้องจ่ายค่าหย่า"


def test_divorce_needs_the_fee(db):
    partner.marry(1, 2)                       # เหลือคนละ 400,000 < ค่าหย่า 1,000,000
    ok, msg = partner.divorce(1)
    assert not ok and "ไม่พอ" in msg
    assert partner.partner_of(1)[0] == 2, "หย่าไม่สำเร็จต้องยังเป็นคู่กันอยู่"


def test_bonus_scales_with_partner_activity(db, monkeypatch):
    assert partner.bonus_for(1) == (1.0, "")           # ยังไม่มีคู่

    partner.marry(1, 2)
    monkeypatch.setattr(pm, "get_daily_progress", lambda uid: {})
    mult, note = partner.bonus_for(1)
    assert mult == 1.05 and "ชวนคู่มาเล่น" in note      # คู่ยังไม่เล่นวันนี้

    monkeypatch.setattr(pm, "get_daily_progress", lambda uid: {"kill": (3, False)})
    mult, note = partner.bonus_for(1)
    assert mult == 1.15 and "ออกล่าวันเดียวกัน" in note


def test_activity_check_never_breaks_the_fight(db, monkeypatch):
    partner.marry(1, 2)
    monkeypatch.setattr(pm, "get_daily_progress", lambda uid: 1 / 0)
    assert partner.played_today(2) is False            # อ่านไม่ได้ = ถือว่าไม่ได้เล่น ไม่ใช่ระเบิด


def test_embed_nudges_toward_the_partner(db, monkeypatch):
    embed = partner.build_partner_embed(1, "T")
    assert "ยังไม่มีคู่" in embed.description

    partner.marry(1, 2)
    monkeypatch.setattr(pm, "get_daily_progress", lambda uid: {})
    embed = partner.build_partner_embed(1, "T")
    text = embed.description + " ".join(f.value for f in embed.fields)
    assert "<@2>" in text and "ชวนมาเล่น" in text


def test_wired_into_fight_rewards():
    import pathlib
    src = pathlib.Path("bot/views/game_views.py").read_text(encoding="utf-8")
    assert "_partner.bonus_for(self.user_id)" in src
    assert "reward = int(reward * p_mult)" in src and "gained_exp = int(gained_exp * p_mult)" in src


def test_config_present():
    cfg = json.load(open("config.example.json", encoding="utf-8"))["partner"]
    assert cfg["together_bonus_percent"] > cfg["solo_bonus_percent"], \
        "โบนัสตอนคู่เล่นด้วยต้องมากกว่า ไม่งั้นไม่มีเหตุผลให้ชวนกันมาเล่น"
