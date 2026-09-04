"""🎲 ทอยเต๋าแข่งกัน (เฟส 8)

เจ้าของเกมสั่ง 2026-09-04: **ทุกการโจมตีต้องทอยเต๋าแข่งกัน**
ผู้โจมตีทอยได้มากกว่าหรือเท่า = โดน · น้อยกว่า = พลาด
ทั้งตอนคนตีมอนและมอนตีคน และต้องเห็นแต้มทั้งสองฝั่งบนจอ

⚠️ กติกานี้ยืมจากเกมหลัก (`adventure_core` บรรทัด `player_roll >= monster_roll`)
   ห้ามตั้งเกณฑ์ใหม่เอง ไม่งั้นสองโหมดตัดสินไม่เหมือนกัน
"""
import random
import sqlite3

import pytest

from bot.models import player_model
from bot.games.party import contest, engine, room


@pytest.fixture(autouse=True)
def db(tmp_path, monkeypatch):
    from license_server import web_db
    path = tmp_path / "web.db"

    def _connect():
        conn = sqlite3.connect(str(path), timeout=5)
        conn.row_factory = sqlite3.Row
        conn.executescript(web_db._SCHEMA)
        return conn

    monkeypatch.setattr(web_db, "connect", _connect)
    monkeypatch.setattr(player_model, "DB_NAME", str(tmp_path / "game.db"))
    player_model.init_db()
    for uid in range(1, 7):
        player_model.get_player(uid)
    yield


def _u(**kw):
    u = {"id": "p1", "side": "party", "hp": 100, "hp_max": 100,
         "level": 1, "atk": 10, "def": 2, "fx": {}, "defending": False,
         "name": "ทดสอบ", "element": None}
    u.update(kw)
    return u


class Dice:
    """เต๋าที่กำหนดผลได้ — เทสกติกาต้องไม่ขึ้นกับดวง"""

    def __init__(self, *vals):
        self.vals = list(vals)

    def randint(self, a, b):
        # ⚠️ ค่าที่เตรียมไว้หมดแล้วคืน "ต่ำสุด" ไม่ใช่สูงสุด
        #    มอนแต่ละแรงค์ทอยไม่เท่ากัน (บอสถึง 5 ลูก) เตรียมไว้ 2 ค่าจึงไม่พอ
        #    คืนค่าสูงสุดทำให้ผลพลิกแบบสุ่ม เทสแดงทั้งที่โค้ดถูก (เจอ 3 รอบแล้ว)
        return self.vals.pop(0) if self.vals else a

    def choice(self, seq):
        return list(seq)[0]

    def random(self):
        return 0.5      # ไม่เข้าช่วง "พลาดร่วง" ของ roll_player_die


# ── กติกาแพ้ชนะ ──

def test_ทอยมากกว่าคือโดน():
    r = contest.roll_off(_u(), _u(id="m1", side="monster"), Dice(15, 9))
    assert r["hit"] is True
    assert r["atk"] == 15 and r["def"] == 9


def test_ทอยน้อยกว่าคือพลาด():
    r = contest.roll_off(_u(), _u(id="m1", side="monster"), Dice(5, 18))
    assert r["hit"] is False


def test_เสมอถือว่าผู้โจมตีชนะ():
    """ยืมเกณฑ์เกมหลักเป๊ะ ๆ — ที่นั่นใช้ player_roll >= monster_roll"""
    r = contest.roll_off(_u(), _u(id="m1", side="monster"), Dice(12, 12))
    assert r["hit"] is True, "เสมอต้องนับว่าโดน เหมือนโหมดเดี่ยว"


def test_เกณฑ์ตรงกับเกมหลัก():
    """ห้ามตั้งเกณฑ์ใหม่ — อ่านซอร์สเกมหลักมายืนยัน"""
    import pathlib
    src = pathlib.Path("bot/adventure_core.py").read_text(encoding="utf-8")
    assert "if player_roll >= monster_roll:" in src, \
        "เกมหลักเปลี่ยนเกณฑ์แล้ว ต้องตามไปแก้ contest.py ด้วย"


# ── สถานะที่มีผลกับเต๋า ──

def test_ติดสถานะช้าแล้วทอยได้น้อยลง():
    slow = _u(fx={"slow": 2})
    hi = contest.roll_off(slow, _u(id="m1", side="monster"), Dice(15, 9))
    normal = contest.roll_off(_u(), _u(id="m1", side="monster"), Dice(15, 9))
    assert hi["atk"] < normal["atk"], "ติดช้าแล้วแต้มต้องลด"


def test_แต้มไม่ต่ำกว่า_1():
    """สถานะซ้อนกันเยอะ ๆ ต้องไม่ทำให้แต้มติดลบ"""
    heavy = _u(fx={"slow": 9})
    r = contest.roll_off(heavy, _u(id="m1", side="monster"), Dice(1, 1))
    assert r["atk"] >= 1 and r["def"] >= 1


def test_หลบได้แล้วพลาดแน่นอนไม่ต้องทอย():
    """💨 Evasion ของ Rogue — กันครั้งถัดไปแน่นอน ไม่ใช่แค่เพิ่มโอกาส"""
    dodger = _u(id="p2", fx={"evade": 1})
    r = contest.roll_off(_u(id="m1", side="monster"), dodger, Dice(20, 1))
    assert r["hit"] is False, "ทอย 20 ก็ต้องไม่โดนคนที่กดหลบไว้"
    assert r.get("evaded") is True


def test_หลบแล้วใช้หมดไปเลย():
    """กันได้ครั้งเดียว ไม่ใช่กันตลอดทั้งสมรภูมิ"""
    dodger = _u(id="p2", fx={"evade": 1})
    contest.roll_off(_u(id="m1", side="monster"), dodger, Dice(20, 1))
    assert not dodger["fx"].get("evade")


# ── เต๋าหลายลูกตามเลเวล ──

def test_เลเวลสูงทอยหลายลูกเหมือนเกมหลัก():
    """เกมหลักให้เต๋าเพิ่มทุก 25 เลเวล — โหมดนี้ต้องเหมือนกัน"""
    low = contest.dice_count(_u(level=1))
    high = contest.dice_count(_u(level=80))
    assert high > low, f"เลเวล 80 ทอย {high} ลูก เท่ากับเลเวล 1 ({low})"


def test_มอนทอยตามแรงค์():
    """dice_count ของแรงค์มาจากเกมหลัก บอสทอยหลายลูกกว่า"""
    common = contest.dice_count(_u(id="m1", side="monster",
                                   stats={"dice_count": 1}))
    boss = contest.dice_count(_u(id="m1", side="monster",
                                 stats={"dice_count": 5}))
    assert boss > common


# ── ในสมรภูมิจริง ──

def _battle(uids=(1, 2)):
    _, st = room.open_party(uids[0], "เอ")
    for u in uids[1:]:
        room.join_party(u, f"P{u}", st["room"])
    room.begin(uids[0])
    st = room._room(uids[0])
    b = st["extra"]["battle"]
    # ⚠️ มอนที่ไวกว่าอาจกวาดปาร์ตี้ร่วงตั้งแต่ยังไม่ทันเริ่ม — เติมเลือด
    #    **และล้างธงจบเกม** ไม่งั้นสั่งอะไรก็เจอ "สมรภูมินี้จบไปแล้ว" แบบสุ่ม ๆ
    b["over"], b["winner"] = False, None
    for u in b["units"].values():
        if u["side"] == "party":
            u["hp"] = u["hp_max"]        # มอนที่ไวกว่าอาจซัดร่วงก่อนเทสเริ่ม
    return st


def test_ทุกการโจมตีส่งเหตุการณ์ทอยแข่ง():
    """⭐ หน้าจอต้องเล่นอนิเมชันเต๋าได้ทุกครั้ง ไม่ใช่บางครั้ง"""
    st = _battle()
    b = st["extra"]["battle"]
    b["turn"] = b["order"].index("p1")
    foes = [u["id"] for u in b["units"].values()
            if u["side"] == "monster" and u["hp"] > 0]
    ok, r = engine.act(st, 1, "attack", foes[0], random.Random(1))
    assert ok, r
    ct = [e for e in r["events"] if e["t"] == "contest"]
    assert ct, "ตีแล้วไม่มีเหตุการณ์ทอยแข่ง หน้าจอเล่นอนิเมชันไม่ได้"
    assert "atk" in ct[0] and "def" in ct[0], "ต้องส่งแต้มทั้งสองฝั่ง"


def test_มอนตีก็ต้องทอยแข่งเหมือนกัน():
    """เจ้าของเกมสั่ง: ไม่ว่ามอนหรือคนเป็นฝ่ายโจมตี ต้องเห็นเต๋าทั้งคู่"""
    st = _battle()
    b = st["extra"]["battle"]
    mon = [u for u in b["units"].values() if u["side"] == "monster"][0]
    b["turn"] = b["order"].index(mon["id"])
    evs = engine.monster_turn(st, random.Random(1))
    ct = [e for e in evs if e["t"] == "contest"]
    assert ct, "มอนตีแล้วไม่มีเหตุการณ์ทอยแข่ง"
    assert ct[0]["from"] == mon["id"]


def test_ทอยแพ้แล้วไม่เสียเลือด():
    """พลาดคือพลาด ไม่ใช่โดนน้อยลง

    ⚠️ สร้างหน่วยเองแทนดึงจากสมรภูมิจริง — มอนแต่ละแรงค์ทอยไม่เท่ากัน
       เต๋าปลอมที่เตรียมไว้ 2 ค่าเลยไม่พอ แล้วเทสแดงแบบสุ่ม (เจอตอนเฟส 8)
    """
    me = _u(atk=20)
    tgt = _u(id="m1", side="monster", hp=200, hp_max=200)
    evs = engine.strike(me, tgt, "attack", Dice(3, 20))   # คนทอย 3 มอนทอย 20
    assert tgt["hp"] == 200, "ทอยแพ้แล้วยังเสียเลือด"
    assert any(e["t"] == "miss" for e in evs)
    ct = [e for e in evs if e["t"] == "contest"][0]
    assert ct["hit"] is False and ct["atk"] == 3 and ct["def"] == 20


def test_ทอยชนะแล้วเสียเลือดจริง():
    me = _u(atk=20)
    tgt = _u(id="m1", side="monster", hp=200, hp_max=200)
    evs = engine.strike(me, tgt, "attack", Dice(19, 2))
    assert tgt["hp"] < 200, "ทอยชนะแล้วไม่เสียเลือด"
    assert any(e["t"] == "attack" for e in evs)
    assert [e for e in evs if e["t"] == "contest"][0]["hit"] is True


def test_ทอยชนะแต่โดนออร่ากันไว้ก็เจ็บน้อยลง():
    """🛡️ Holy Aura ของ Cleric ลดดาเมจครึ่ง แต่ยังนับว่าโดน"""
    me = _u(id="m1", side="monster", atk=30)
    plain = _u(id="p2", hp=500, hp_max=500)
    warded = _u(id="p3", hp=500, hp_max=500, fx={"aura": 3})
    engine.strike(me, plain, "attack", Dice(19, 2))
    engine.strike(me, warded, "attack", Dice(19, 2))
    assert 500 - warded["hp"] < 500 - plain["hp"], "ออร่าไม่ได้ลดดาเมจเลย"


def test_เหตุการณ์ทอยแข่งอยู่ในสัญญา():
    from bot.games.party import events
    assert "contest" in events.EVENT_TYPES


# ── คุ้มกันรอบแรก ──

def test_รอบแรกปาร์ตี้ไม่ล้ม():
    """⭐ มอนที่ไวกว่าทุกคนเคยกวาดปาร์ตี้ร่วงก่อนใครทันกดอะไรเลย

    (เจ้าของเกมสั่งให้กันไว้ 2026-09-04)
    """
    st = _battle()
    b = st["extra"]["battle"]
    assert b["round"] == 1
    me = _u(id="m9", side="monster", atk=99999)
    for u in b["units"].values():
        if u["side"] == "party":
            engine.strike(me, u, "attack", Dice(20, 1))
            assert u["hp"] >= 1, f"{u['id']} ล้มตั้งแต่รอบแรก"


def test_มอนล้มได้ตั้งแต่รอบแรก():
    """คุ้มกันเฉพาะปาร์ตี้ ไม่ใช่ทำให้ฆ่ามอนไม่ได้"""
    st = _battle()
    b = st["extra"]["battle"]
    tgt = [u for u in b["units"].values() if u["side"] == "monster"][0]
    engine.strike(b["units"]["p1"], tgt, "attack", Dice(19, 1))
    tgt["hp"] = 1
    engine.hurt(tgt, 99999)
    assert tgt["hp"] == 0, "มอนต้องล้มได้ปกติ"


def test_พ้นรอบแรกแล้วล้มได้ตามปกติ():
    """คุ้มกันตลอดกาลก็คือเกมไม่มีความเสี่ยง"""
    st = _battle()
    b = st["extra"]["battle"]
    b["round"] = 1
    n = len(b["order"])
    for _ in range(n * 2):              # เดินให้ครบรอบ
        engine._advance(st)
    assert b["round"] > 1
    p1 = b["units"]["p1"]
    assert not p1.get("grace"), "พ้นรอบแรกแล้วยังคุ้มกันอยู่"
    engine.hurt(p1, 99999)
    assert p1["hp"] == 0


def test_เลือดลดต้องผ่าน_hurt_ที่เดียว():
    """มีช่องไหนหักเลือดตรง ๆ = ช่องนั้นข้ามการคุ้มกันรอบแรกไปได้"""
    import pathlib
    for f in ("engine.py", "skills.py"):
        src = pathlib.Path(f"bot/games/party/{f}").read_text(encoding="utf-8")
        code = chr(10).join(ln.split("#")[0] for ln in src.splitlines())
        assert '"hp"] = max(0,' not in code, \
            f"{f} หักเลือดตรง ๆ ต้องเรียก engine.hurt() แทน"
