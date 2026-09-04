"""🎭 คิวเทิร์น + คำสั่ง — หัวใจของโหมดปาร์ตี้

⚠️ กติกาเหล็ก: คนที่ไม่ใช่เจ้าของตาปัจจุบันสั่งอะไรไม่ได้
   (UNO เคยพลาดข้อนี้ คนอื่นลงไพ่แทนกันได้ กว่าจะเจอก็หลังเทสจริง)
"""
import random
import sqlite3

import pytest

from bot.models import player_model
from bot.games.party import engine


@pytest.fixture(autouse=True)
def _iso(tmp_path, monkeypatch):
    """⚠️ ต้องหนีบ DB ตัวละครทุกไฟล์ที่สั่ง engine.act ได้

    ตั้งแต่เฟส 9 สกิลไปอ่าน/หัก **เม็ดคริสตัลจากฐานข้อมูลจริง**
    ไม่หนีบ = เทสรันทีไรตัวละครจริงเสียเม็ดทุกที (เจอตอนเทสชุดเต็ม 2026-09-04)
    """
    monkeypatch.setattr(player_model, "DB_NAME", str(tmp_path / "game.db"))
    player_model.init_db()
    for uid in range(1, 7):
        player_model.get_player(uid)
    yield


def _player(uid, name, level=10, cls="Warrior", el="fire"):
    return {"uid": str(uid), "name": name, "level": level,
            "class_name": cls, "element": el,
            "hp": 100, "max_hp": 100, "atk": 12, "def": 3}


def _monster(mid, hp=60, el="wood"):
    return {"id": mid, "name": f"มอน{mid}", "hp": hp, "hp_max": hp,
            "element": el, "atk": 8, "def": 2}


@pytest.fixture
def battle():
    st = {"extra": {}}
    return engine.start_battle(
        st, [_player(1, "เอ"), _player(2, "บี")],
        [_monster("m1"), _monster("m2")], random.Random(42))


def _b(st):
    return st["extra"]["battle"]


def _act_current(st, action="attack", target="m1", seed=1):
    """สั่งแทนคนที่ถึงตาอยู่ตอนนี้ (ถ้าเป็นผู้เล่น)"""
    who = engine.current_actor(st)
    if not who.startswith("p"):
        return None
    return engine.act(st, int(who[1:]), action, target, random.Random(seed))


# ── ความไว + คิวเทิร์น ──

def test_ความไวคำนวณจาก_level_อาชีพ_เต๋า():
    """ผู้เล่นไม่มีช่อง agility — ต้องคำนวณเอา (สเปกข้อ 3)"""
    lo = engine.initiative(_player(1, "เอ", level=1), random.Random(7))
    hi = engine.initiative(_player(2, "บี", level=99), random.Random(7))
    assert hi > lo, "เลเวลสูงกว่าต้องไวกว่าเมื่อเต๋าเท่ากัน"


def test_อาชีพมีผลกับความไว():
    """Rogue ต้องไวกว่า Warrior เมื่อเลเวลกับเต๋าเท่ากัน"""
    w = engine.initiative(_player(1, "เอ", cls="Warrior"), random.Random(7))
    r = engine.initiative(_player(2, "บี", cls="Rogue"), random.Random(7))
    assert r > w


def test_อาชีพที่ไม่รู้จักไม่พัง():
    assert engine.initiative(_player(1, "เอ", cls="ไม่มีอาชีพนี้"), random.Random(1)) > 0


def test_คิวมีทุกคนครบ(battle):
    assert set(_b(battle)["order"]) == {"p1", "p2", "m1", "m2"}


def test_คิวคงที่ทั้งรอบไม่ทอยใหม่(battle):
    """ทอยใหม่ทุกตา = วางแผนไม่ได้ เกมเทิร์นเบสจะไม่สนุก"""
    before = list(_b(battle)["order"])
    for _ in range(3):
        _act_current(battle)
    assert _b(battle)["order"] == before


def test_current_actor_ตรงกับคิว(battle):
    b = _b(battle)
    assert engine.current_actor(battle) == b["order"][b["turn"]]


# ── สิทธิ์การสั่ง (กติกาเหล็ก) ──

def test_คนที่ยังไม่ถึงตาสั่งไม่ได้(battle):
    now = engine.current_actor(battle)
    other = "2" if now == "p1" else "1"
    ok, r = engine.act(battle, int(other), "attack", "m1", random.Random(1))
    assert not ok and "ยังไม่ถึงตา" in r["error"]


def test_คนนอกปาร์ตี้สั่งไม่ได้(battle):
    ok, r = engine.act(battle, 999, "attack", "m1", random.Random(1))
    assert not ok


def test_ตายแล้วสั่งไม่ได้แต่ยังอยู่ในสมรภูมิ(battle):
    """สเปกข้อ 5: ตายแล้วนั่งดู รอเพื่อนชุบ — ห้ามลบออกจากห้อง

    ⚠️ ต้องบังคับให้เป็น "ตาของคนที่ตาย" ก่อน ไม่งั้นด่านเช็คลำดับตาจะฟ้องก่อน
       แล้วเทสผ่านทั้งที่ด่านเช็คคนตายถูกถอดออกไปแล้ว (เจอตอนกลับด้านเทส)
    """
    b = _b(battle)
    b["units"]["p1"]["hp"] = 0
    b["turn"] = b["order"].index("p1")     # บังคับให้เป็นตาของคนที่ตาย
    ok, r = engine.act(battle, 1, "attack", "m1", random.Random(1))
    assert not ok, "คนที่ล้มแล้วต้องสั่งอะไรไม่ได้"
    assert "ล้ม" in r["error"], f"ต้องบอกว่าล้มแล้ว ไม่ใช่ {r["error"]!r}"
    assert "p1" in b["units"], "ตายแล้วต้องยังอยู่ในสมรภูมิ (รอชุบ)"


def test_คำสั่งที่ไม่รู้จักไม่ได้(battle):
    """กันคนยิง API ส่งคำสั่งมั่ว"""
    who = engine.current_actor(battle)
    if who.startswith("p"):
        ok, _ = engine.act(battle, int(who[1:]), "ยิงเลเซอร์", "m1", random.Random(1))
        assert not ok


def test_เกมจบแล้วสั่งไม่ได้(battle):
    b = _b(battle)
    b["over"] = True
    who = engine.current_actor(battle)
    if who.startswith("p"):
        ok, _ = engine.act(battle, int(who[1:]), "attack", "m1", random.Random(1))
        assert not ok


# ── การเล็งเป้า ──

def test_ตีเพื่อนไม่ได้(battle):
    who = engine.current_actor(battle)
    if who.startswith("p"):
        ok, _ = engine.act(battle, int(who[1:]), "attack", "p2", random.Random(1))
        assert not ok


def test_เป้าที่ไม่มีอยู่จริงไม่ได้(battle):
    who = engine.current_actor(battle)
    if who.startswith("p"):
        ok, _ = engine.act(battle, int(who[1:]), "attack", "m99", random.Random(1))
        assert not ok


def test_ตีเป้าที่ตายแล้วไม่ได้(battle):
    b = _b(battle)
    b["units"]["m1"]["hp"] = 0
    who = engine.current_actor(battle)
    if who.startswith("p"):
        ok, _ = engine.act(battle, int(who[1:]), "attack", "m1", random.Random(1))
        assert not ok


# ── ผลของการกระทำ ──

def test_สั่งแล้วเลื่อนไปคนถัดไป(battle):
    i0 = _b(battle)["turn"]
    if _act_current(battle):
        assert _b(battle)["turn"] != i0


def test_ทุกการกระทำคืนรายการเหตุการณ์(battle):
    """renderer อ่านรายการนี้ไปวาด — ขาดไม่ได้"""
    r = _act_current(battle, "attack", "m1")
    if r:
        ok, out = r
        assert ok and isinstance(out["events"], list) and out["events"]


def test_โจมตีแล้วเลือดลด(battle):
    b = _b(battle)
    who = engine.current_actor(battle)
    if who.startswith("p"):
        before = b["units"]["m1"]["hp"]
        engine.act(battle, int(who[1:]), "attack", "m1", random.Random(3))
        assert b["units"]["m1"]["hp"] <= before


def test_เลือดไม่ติดลบ(battle):
    b = _b(battle)
    b["units"]["m1"]["hp"] = 1
    who = engine.current_actor(battle)
    if who.startswith("p"):
        engine.act(battle, int(who[1:]), "attack", "m1", random.Random(3))
        assert b["units"]["m1"]["hp"] >= 0


def test_ตายแล้วมีเหตุการณ์_die(battle):
    b = _b(battle)
    b["units"]["m1"]["hp"] = 1
    who = engine.current_actor(battle)
    if who.startswith("p"):
        ok, out = engine.act(battle, int(who[1:]), "attack", "m1", random.Random(3))
        if ok and b["units"]["m1"]["hp"] == 0:
            assert any(e["t"] == "die" for e in out["events"])


def test_ท่าป้องกันเป็นสกิลของคลาสไม่ใช่ปุ่มกลาง(battle):
    """เจ้าของเกมสั่ง 2026-09-04: ถอดปุ่ม "ป้องกัน" กลางออก
    นักรบใช้ 🛡️ Shield Bash ซึ่งเกมหลักนิยามว่าเป็นท่าลดดาเมจอยู่แล้ว"""
    from bot.games.party import skills
    assert "defend" not in engine.ACTIONS
    b = _b(battle)
    who = engine.current_actor(battle)
    if not who.startswith("p"):
        pytest.skip("ตามอน")
    b["units"][who]["class_name"] = "Warrior"
    b["units"][who]["hp"] = b["units"][who]["hp_max"]
    ok, r = engine.act(battle, int(who[1:]), "shield_bash", "m1", random.Random(1))
    assert ok, r
    assert int(b["units"][who]["fx"].get("ward") or 0) > 0


def test_ข้ามคนที่ตายแล้วในคิว(battle):
    """คนตายไม่ได้เทิร์น ไม่งั้นเกมค้างรอคนที่สั่งไม่ได้"""
    b = _b(battle)
    for u in b["units"].values():
        pass
    nxt = engine.current_actor(battle)
    b["units"][nxt]["hp"] = 0 if nxt.startswith("m") else b["units"][nxt]["hp"]
    # เดินคิวไปเรื่อย ๆ ต้องไม่หยุดที่คนตาย
    for _ in range(8):
        cur = engine.current_actor(battle)
        if b["units"][cur]["hp"] <= 0:
            pytest.fail(f"คิวหยุดที่ {cur} ซึ่งตายแล้ว")
        if cur.startswith("p"):
            engine.act(battle, int(cur[1:]), "defend", None, random.Random(1))
        else:
            engine.monster_turn(battle, random.Random(1))
        if b.get("over"):
            break


# ── จบเกม ──

def test_มอนตายหมดแล้วชนะ(battle):
    b = _b(battle)
    for mid in ("m1", "m2"):
        b["units"][mid]["hp"] = 0
    engine.check_over(battle)
    assert b["over"] is True and b["winner"] == "party"


def test_ปาร์ตี้ตายหมดแล้วแพ้(battle):
    b = _b(battle)
    for pid in ("p1", "p2"):
        b["units"][pid]["hp"] = 0
    engine.check_over(battle)
    assert b["over"] is True and b["winner"] == "monster"


def test_ยังมีคนรอดไม่จบเกม(battle):
    b = _b(battle)
    b["units"]["p1"]["hp"] = 0
    engine.check_over(battle)
    assert not b.get("over")


# ── ประตูเดียว: ห้ามส่งค่าลับของมอน ──

def test_view_ไม่บอก_hp_จริงของมอน(battle):
    """สเปก: ห้ามส่งค่าลับของมอน — ผู้เล่นควรเห็นแค่แถบเลือดคร่าว ๆ"""
    v = engine.view(battle, 1)
    for u in v["units"]:
        if u["side"] == "monster":
            assert "hp" not in u, "ส่ง HP จริงของมอนลงไป — ผู้เล่นคำนวณได้เป๊ะเกินไป"
            assert "hp_pct" in u, "ต้องบอกเป็นเปอร์เซ็นต์แทน"


def test_view_บอก_hp_จริงของผู้เล่น(battle):
    """เลือดตัวเองกับเพื่อนต้องเห็นชัด ไม่งั้นตัดสินใจฮีลไม่ได้"""
    v = engine.view(battle, 1)
    mine = [u for u in v["units"] if u["id"] == "p1"][0]
    assert "hp" in mine and "hp_max" in mine


def test_view_บอกว่าถึงตาใคร(battle):
    v = engine.view(battle, 1)
    assert v["turn_of"] == engine.current_actor(battle)
    assert isinstance(v["order"], list)
