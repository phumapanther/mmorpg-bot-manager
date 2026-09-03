"""🏃 ปุ่มหนี — ต้องเห็นเต๋าที่ทอย และหนีซ้ำต้องมีโอกาสรอดมากขึ้น

อาการที่ผู้เล่นเจอ:
1. กดหนีแล้วไม่เห็นผลทอยเต๋าเลย ทั้งที่ระบบทอยจริง — ไม่รู้ว่าเฉียดหรือห่าง
2. มอนเรทหนีต่ำ (บอสไร้พ่าย 5%) กดหนีรัวก็ยังโอกาสเท่าเดิมทุกครั้ง
   เสียเลือดฟรีไปเรื่อย ๆ โดยไม่มีทางออก
"""
import pytest

import bot.models.player_model as pm
from bot import adventure_core as ac
from tests import conftest

UID = 7001


class Rng:
    """ทอยตามที่กำหนดไว้ล่วงหน้า — คุมผลได้เป๊ะ"""

    def __init__(self, *vals):
        self.vals = list(vals)

    def randint(self, a, b):
        return self.vals.pop(0) if self.vals else a


def _fight(rank="Main-Boss", flee=30, tries=0):
    return {"rank": rank, "stats": {"name": "มอนทดสอบ", "flee_chance": flee},
            "hp": 100, "hp_max": 100, "turn": 1, "statuses": {}, "flee_tries": tries}


@pytest.fixture
def world(tmp_path, monkeypatch):
    monkeypatch.setattr(pm, "DB_NAME", str(tmp_path / "f.db"))
    pm.init_db()
    pm.get_player(UID)
    pm.update_player_fields(UID, {"hp": 500, "max_hp": 500, "armor_dur": 50,
                                  "current_state": "fighting"})


# ── 1. ต้องเห็นเต๋า ──

def test_a_successful_escape_reports_the_roll(world):
    r = ac.fight_flee(UID, _fight(flee=30), rng=Rng(20))
    assert r["outcome"] == "fled"
    assert r["roll"] == 20, "หนีสำเร็จแต่ไม่บอกว่าทอยได้เท่าไหร่"
    assert r["need"] == 30, "ไม่บอกว่าต้องทอยไม่เกินเท่าไหร่"


def test_a_failed_escape_reports_the_roll_too(world):
    r = ac.fight_flee(UID, _fight(flee=30), rng=Rng(80, 20))
    assert r["outcome"] == "hit"
    assert r["roll"] == 80 and r["need"] == 30, "หนีไม่พ้นก็ต้องเห็นเต๋าว่าห่างแค่ไหน"


def test_dying_while_fleeing_still_reports_the_roll(world):
    pm.update_player_field(UID, "hp", 5)
    r = ac.fight_flee(UID, _fight(flee=30), rng=Rng(90, 30))
    assert r["outcome"] == "lose" and r["roll"] == 90


def test_being_rooted_has_no_roll_to_show(world, monkeypatch):
    """โดนรากล็อกไว้ = หนีไม่ได้เลย ไม่ได้ทอยด้วยซ้ำ ต้องไม่แกล้งโชว์เต๋า"""
    from bot import game_modifiers as gm
    monkeypatch.setattr(gm, "has_status_flag", lambda s, f: f == "no_flee")
    monkeypatch.setattr(gm, "STATUS_EFFECTS", {"root": {"no_flee": True}})
    r = ac.fight_flee(UID, dict(_fight(), statuses={"root": 3}), rng=Rng(1))
    assert r["outcome"] == "blocked" and "roll" not in r


def test_the_web_hands_the_roll_to_the_dice_box():
    import pathlib
    api = conftest.web_api_source()
    block = api[api.index('if action == "flee":'):api.index('skill = action if')]
    assert '"roll"' in block, "เว็บไม่ได้ส่งผลทอยหนีไปให้กล่องเต๋า"
    assert "player_parts" in block, "รูปแบบไม่ตรงกับที่ showRoll ต้องการ"


# ── 2. หนีซ้ำต้องง่ายขึ้น ──

def test_each_failed_attempt_makes_the_next_one_easier(world):
    """ทอย 40 แพ้เรท 30 ในครั้งแรก แต่ครั้งที่สอง (เรท 45) ต้องรอด"""
    first = ac.fight_flee(UID, _fight(flee=30), rng=Rng(40, 20))
    assert first["outcome"] == "hit"
    assert first["fight"]["flee_tries"] == 1, "ไม่ได้นับครั้งที่หนีพลาด"

    second = ac.fight_flee(UID, first["fight"], rng=Rng(40))
    assert second["outcome"] == "fled", "หนีครั้งที่สองด้วยเต๋าเท่าเดิมยังไม่รอด"
    assert second["need"] > 30, "โอกาสหนีไม่ได้เพิ่มขึ้นเลย"


def test_the_bonus_climbs_with_every_try(world):
    step = int(ac.FLEE_BONUS_PER_TRY)
    for tries in range(4):
        r = ac.fight_flee(UID, _fight(flee=30, tries=tries), rng=Rng(100, 20))
        assert r["need"] == 30 + step * tries, f"ครั้งที่ {tries+1} โบนัสไม่ตรง"


def test_escaping_is_never_guaranteed(world):
    """ต่อให้กดหนีเป็นร้อยครั้งก็ต้องมีโอกาสพลาด ไม่งั้นบอสไร้พ่ายไร้ความหมาย"""
    r = ac.fight_flee(UID, _fight(flee=85, tries=999), rng=Rng(100, 20))
    assert r["need"] <= ac.FLEE_MAX_CHANCE < 100
    assert r["outcome"] == "hit", "ทอยได้ 100 ต้องไม่มีทางหนีรอด"


def test_a_new_monster_starts_the_counter_over(world):
    """หนีจากตัวนี้ไม่สำเร็จ ไม่ควรทำให้หนีตัวถัดไปง่ายขึ้น"""
    r = ac.fight_flee(UID, _fight(flee=30, tries=5), rng=Rng(100, 20))
    assert r["fight"]["flee_tries"] == 6
    fresh = ac.spawn_monster(UID, ())
    assert fresh.get("flee_tries", 0) == 0, "มอนตัวใหม่ติดโบนัสหนีมาด้วย"


def test_the_counter_survives_a_round_trip_through_the_web(world):
    """เว็บเก็บไฟต์ลง adventure_pending — ตัวนับต้องรอดข้ามคำขอ"""
    r = ac.fight_flee(UID, _fight(flee=30), rng=Rng(100, 20))
    ac.set_pending(UID, "monster", r["fight"])
    _evt, data = ac.get_pending(UID)
    assert data["flee_tries"] == 1, "ตัวนับหายตอนเก็บลงฐานข้อมูล"
