"""P7 กิลด์วอร์: เดิมพัน DB + สุ่มเป้าหมาย + สกอร์ + คืนเดิมพันตอนรีสตาร์ท"""
import random

import bot.models.player_model as pm
from bot.cogs.guild_war import DEFAULT_ENCOUNTERS as ENCOUNTERS, apply_encounter, encounters, roll_encounter


def test_encounter_table():
    assert [e[0] for e in encounters()] == [e[0] for e in ENCOUNTERS]   # ตารางจาก Panel ตรงกับค่าเริ่มต้น
    keys = {e[0] for e in ENCOUNTERS}
    assert keys == {"soldier", "leader", "fort", "castle"}
    assert sum(e[1] for e in ENCOUNTERS) == 100
    rng = random.Random(7)
    seen = {roll_encounter(rng)[0] for _ in range(300)}
    assert seen == keys  # 300 ครั้งต้องเจอครบทุกชนิด


def test_apply_encounter_scoring():
    scores = {1: 0, 2: 0}
    apply_encounter(scores, 1, 2, ("soldier", 60, 1, "me", 0))
    apply_encounter(scores, 1, 2, ("leader", 15, 10, "me", 5))
    assert scores == {1: 11, 2: 0}
    apply_encounter(scores, 1, 2, ("castle", 5, -100, "enemy", 8))
    assert scores == {1: 11, 2: -100}  # แต้มศัตรูติดลบได้


def test_war_stake_db(tmp_path, monkeypatch):
    monkeypatch.setattr(pm, "DB_NAME", str(tmp_path / "t.db"))
    pm.record_war_stake(111, 1, 2, 500)
    assert pm.pop_war_stake(111) == (1, 2, 500)
    assert pm.pop_war_stake(111) is None                     # ดึงแล้วหาย


def test_restart_refund_flow(tmp_path, monkeypatch):
    """ศึกค้าง 2 ศึกตอนรีสตาร์ท → pop_all คืนครบแล้วตารางว่าง"""
    monkeypatch.setattr(pm, "DB_NAME", str(tmp_path / "t.db"))
    g1 = pm.create_guild("A", "🏰", 1, 10, 20)
    g2 = pm.create_guild("B", "🗡️", 2, 11, 21)
    pm.guild_add_treasury(g1, 1000)
    pm.guild_add_treasury(g2, 1000)
    pm.record_war_stake(111, g1, g2, 400)
    for _cid, ga, gb, stake in pm.pop_all_war_stakes():
        pm.guild_add_treasury(ga, stake)
        pm.guild_add_treasury(gb, stake)
    assert pm.get_guild_of(1)["treasury"] == 1400
    assert pm.get_guild_of(2)["treasury"] == 1400
    assert pm.pop_all_war_stakes() == []
