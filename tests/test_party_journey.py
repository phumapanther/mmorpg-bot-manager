"""🧭 รอบการเดินทาง (เฟส 10a)

สเปกเสริม 2026-09-04 · เจ้าของเกมเคาะ: **1 เหตุการณ์ = 1 รอบ**
(หมู่บ้าน/หีบ/NPC ก็นับรอบด้วย ไม่ใช่เฉพาะตอนสู้)

ยิ่งรอบสูง มอนยิ่งแรง ทอง/EXP/ดรอปยิ่งดี · ตายยกทีมกลับไปรอบ 1
"""
import sqlite3

import pytest

from bot.models import player_model
from bot.games.party import journey, room


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
    # ⚠️ ตรึงให้เจอมอนเสมอ — ตั้งแต่เฟส 10b begin() สุ่มเหตุการณ์ได้หลายแบบ
    #    เทสชุดนี้ตรวจการต่อสู้ จึงต้องล็อกไว้ ไม่งั้นแดงแบบสุ่ม
    #    (เทสของเหตุการณ์อื่นอยู่ที่ test_party_events_roll.py)
    from bot.games.party import encounter as _enc
    monkeypatch.setattr(_enc, "roll_kind", lambda *a, **k: "monster")
    player_model.init_db()
    for uid in range(1, 7):
        player_model.get_player(uid)
    yield


def _party(uids=(1, 2)):
    _, st = room.open_party(uids[0], "เอ")
    for u in uids[1:]:
        room.join_party(u, f"P{u}", st["room"])
    return st["room"]


def _heal_all(st):
    for u in st["extra"]["battle"]["units"].values():
        if u["side"] == "party":
            u["hp"] = u["hp_max"]
    for uid in (1, 2):
        p = player_model.get_player(uid)
        player_model.update_player_field(uid, "hp", p["max_hp"])


# ── ตัวนับรอบ ──

def test_เริ่มเดินทางได้รอบที่_1():
    _party()
    room.begin(1)
    assert room.view(1)["round"] == 1


def test_ยังไม่เริ่มก็ยังไม่มีรอบ():
    """อยู่ในล็อบบี้เฉย ๆ ยังไม่ได้ออกเดินทาง"""
    _party()
    assert room.view(1).get("round") in (None, 0)


def test_ไปต่อแล้วรอบเพิ่ม():
    """1 เหตุการณ์ = 1 รอบ (เจ้าของเกมเคาะ 2026-09-04)"""
    _party()
    room.begin(1)
    st = room._room(1)
    st["extra"]["battle"].update(over=True, winner="party")
    _heal_all(st)
    from bot import lobby
    lobby.save(st["room"], st)

    ok, _ = room.again(1)
    assert ok
    assert room.view(1)["round"] == 2


def test_ปาร์ตี้ใหม่เริ่มที่รอบ_1_เสมอ():
    """ห้องว่างหมด = รอบหาย (เจ้าของเกมเคาะข้อ 8)"""
    _party()
    room.begin(1)
    st = room._room(1)
    st["extra"]["round"] = 9
    from bot import lobby
    lobby.save(st["room"], st)
    room.leave_party(1)
    room.leave_party(2)

    _party()
    room.begin(1)
    assert room.view(1)["round"] == 1, "ห้องใหม่ยังจำรอบเก่าอยู่"


def test_เพื่อนเห็นรอบเดียวกัน():
    """รอบเป็นของปาร์ตี้ ไม่ใช่ของใครคนหนึ่ง"""
    _party()
    room.begin(1)
    assert room.view(1)["round"] == room.view(2)["round"]


# ── สูตรไต่ระดับ (ยังไม่มีใครเรียกใช้ในขั้นนี้ แต่ต้องถูกตั้งแต่แรก) ──

def test_รอบ_1_ยังไม่มีตัวคูณ():
    assert journey.monster_mult(1) == 1.0
    assert journey.gold_mult(1) == 1.0


def test_ยิ่งรอบสูงยิ่งแรงยิ่งได้เยอะ():
    for a, b in ((1, 5), (5, 10), (10, 20)):
        assert journey.monster_mult(b) > journey.monster_mult(a)
        assert journey.gold_mult(b) > journey.gold_mult(a)


def test_ตัวเลขตรงกับสเปกเป๊ะ():
    """⭐ ตรึงเลขดิบ ไม่ใช่คำนวณจากค่าคงที่ตัวเดียวกับโค้ด

    (บทเรียนเฟส 5: แก้ค่าคงที่แล้วเทสเขียวหมดทั้งที่ผลเปลี่ยน)
    สเปก: มอน ×(1+(r−1)×0.25) · ทอง ×(1+(r−1)×0.40)
    """
    assert journey.monster_mult(5) == pytest.approx(2.0)
    assert journey.monster_mult(20) == pytest.approx(5.75)
    assert journey.gold_mult(5) == pytest.approx(2.6)
    assert journey.gold_mult(20) == pytest.approx(8.6)


def test_ดรอปหายากมีเพดาน_0_85():
    """ตัวเดียวในสเปกที่มีเพดาน — ทองไม่มี (เจ้าของเกมเคาะแล้ว)"""
    assert journey.rare_drop_chance(0.5, 999) == pytest.approx(0.85)
    assert journey.rare_drop_chance(0.05, 1) == pytest.approx(0.05)


def test_ทองไม่มีเพดาน():
    """เจ้าของเกมเคาะ 2026-09-04 ว่าไม่มีเพดาน — ใครจะใส่ต้องถามก่อน"""
    assert journey.gold_mult(200) > journey.gold_mult(100) > journey.gold_mult(50)


# ── ห้ามคนใหม่เข้าระหว่างเดินทาง (แต่คนเดิมกลับได้) ──

def test_คนใหม่เข้าไม่ได้ระหว่างเดินทาง():
    """เจ้าของเกมเคาะข้อ 7 — รอบเป็นของปาร์ตี้ คนมาทีหลังจะได้ของฟรี"""
    code = _party()
    room.begin(1)
    ok, r = room.join_party(9, "คนใหม่", code)
    assert not ok
    assert "เดินทาง" in r["error"], f"ข้อความไม่บอกเหตุผล: {r}"


def test_ข้อความบอกด้วยว่าเดินมาถึงรอบไหน():
    """คนที่ถูกปฏิเสธควรรู้ว่าต้องรอนานแค่ไหน"""
    code = _party()
    room.begin(1)
    st = room._room(1)
    st["extra"]["round"] = 7
    from bot import lobby
    lobby.save(st["room"], st)
    ok, r = room.join_party(9, "คนใหม่", code)
    assert not ok and "7" in r["error"]


def test_คนเดิมเน็ตหลุดแล้วกลับเข้ามาได้():
    """⭐ ห้ามทับฟีเจอร์เฟส 6 — คนที่มีที่นั่งอยู่แล้วกลับได้เสมอ"""
    code = _party()
    room.begin(1)
    ok, got = room.join_party(2, "บี", code)
    assert ok, f"คนเดิมกลับเข้ามาไม่ได้: {got}"
    assert room.view(2)["in_room"]


def test_ปาร์ตี้เต็มคนเดิมก็ยังกลับได้ระหว่างเดินทาง():
    """เต็ม 5 คนแล้วออกเดินทาง คนที่หลุดต้องกลับได้ ไม่ใช่โดนกันสองชั้น"""
    code = _party(uids=(1, 2, 3, 4, 5))
    room.begin(1)
    ok, _ = room.join_party(4, "P4", code)
    assert ok, "ปาร์ตี้เต็มแล้วคนเดิมกลับไม่ได้"


def test_ยังไม่ออกเดินทางใครเข้าก็ได้():
    """กันไว้แน่นเกินไปจนชวนเพื่อนไม่ได้ก็ไม่ไหว"""
    code = _party()
    ok, _ = room.join_party(9, "คนใหม่", code)
    assert ok


# ── กฎการตาย (สเปกข้อ 1) ──

def _units(*hps):
    return [{"id": f"p{i+1}", "uid": str(i + 1), "side": "party",
             "hp": h, "hp_max": 200} for i, h in enumerate(hps)]


def test_ยังมีคนรอดคนที่ล้มฟื้นมา_1_เปอร์เซ็นต์():
    us = _units(0, 150)
    ending, revived = journey.close_out(us)
    assert ending == "survive"
    assert revived == [("p1", 2)], "ต้องบอกด้วยว่าใครฟื้นเท่าไหร่ (เอาไปทำอนิเมชัน)"
    assert us[0]["hp"] == 2, "200 × 1% = 2"
    assert us[1]["hp"] == 150, "คนที่ยังไม่ล้มห้ามโดนแตะ"


def test_ล้มยกทีมแล้วยังตายอยู่ไม่ฟื้นทันที():
    """⭐ เจ้าของเกมสั่ง 2026-09-04: "เวลาตายก็ตายสิ"

    ฟื้นทันทีตอนจบสมรภูมิ = จอเห็นเลือดเด้งกลับ ผู้เล่นไม่รู้สึกว่าแพ้จริง
    เลือดกลับมาตอนกด "เริ่มออกเดินทางใหม่" เท่านั้น
    """
    us = _units(0, 0)
    ending, revived = journey.close_out(us)
    assert ending == "wipe"
    assert revived == [], "ล้มยกทีมแล้วห้ามฟื้นทันที"
    assert all(u["hp"] == 0 for u in us), "ต้องยังตายอยู่ให้จอแสดงได้"


def test_ฟื้นครึ่งเลือดตอนกดเริ่มใหม่():
    us = _units(0, 0)
    journey.close_out(us)
    journey.respawn_party(us)
    assert all(u["hp"] == 100 for u in us), "200 × 50% = 100"
    assert all(u["hp"] == 100 for u in us), "200 × 50% = 100"


def test_ฟื้นแล้วต้องไม่เป็นศูนย์():
    """เลือดสูงสุดน้อยมาก 1% ปัดลงเป็น 0 แล้วฟื้นไม่ขึ้น ล้มค้างตลอดกาล

    ⚠️ ต้องมีคนรอดอย่างน้อย 1 ไม่งั้นเข้าทาง "ล้มยกทีม" (ฟื้น 50%) แทน
       แล้วเทสจะไม่เคยแตะโค้ดฟื้น 1% เลย (ย้อนเทสจับได้ 2026-09-04)
    """
    us = [{"id": "p1", "side": "party", "hp": 0, "hp_max": 10},
          {"id": "p2", "side": "party", "hp": 50, "hp_max": 100}]
    assert journey.close_out(us)[0] == "survive"
    assert us[0]["hp"] >= 1, "1% ของ 10 ปัดเป็น 0 — ต้องยกขึ้นเป็น 1"


def test_ปาร์ตี้ว่างไม่นับว่าล้มยกทีม():
    assert journey.close_out([]) == ("survive", [])


# ── โทษตอนตายยกทีม ──

def test_เสียเงินสด_10_เปอร์เซ็นต์():
    got = journey.wipe_penalty({"level": 30, "cash": 5000, "exp": 99999,
                                "max_hp": 220})
    assert got["gold_lost"] == 500 and got["cash"] == 4500


def test_ธนาคารไม่โดนแตะ():
    """⭐ ฝากเงินก่อนออกเดินทาง = การเล่นที่ฉลาด (เข้ากับระบบธนาคารที่มีอยู่)"""
    got = journey.wipe_penalty({"level": 10, "cash": 100, "bank": 999999,
                                "exp": 99999, "max_hp": 200})
    assert "bank" not in got, "โทษไปแตะเงินในธนาคาร"
    assert got["gold_lost"] == 10


def test_เสีย_EXP_แล้วตกเลเวลได้():
    got = journey.wipe_penalty({"level": 20, "cash": 0, "exp": 0, "max_hp": 200})
    assert got["exp_lost"] > 0
    assert got["level"] == 19 and got["level_lost"] == 1


def test_ตกเลเวลแล้วเลือดสูงสุดลดตามเกมหลัก():
    """เกมหลักให้ +20 ต่อเลเวล ตกเลเวลก็ต้องลดเท่ากัน"""
    got = journey.wipe_penalty({"level": 20, "cash": 0, "exp": 0, "max_hp": 200})
    assert got["max_hp"] == 180


def test_เลเวล_1_ตกไม่ได้():
    got = journey.wipe_penalty({"level": 1, "cash": 0, "exp": 0, "max_hp": 100})
    assert got["level"] == 1 and got["exp"] == 0 and got["max_hp"] == 100


def test_EXP_เยอะพอไม่ตกเลเวล():
    got = journey.wipe_penalty({"level": 20, "cash": 0, "exp": 999999,
                                "max_hp": 200})
    assert got["level"] == 20 and got["level_lost"] == 0


def test_ตัวเลขโทษตรงกับที่เคาะ():
    """⭐ ตรึงเลขดิบ — เงินสด 10% · EXP 20% (เจ้าของเกมเคาะข้อ 4)"""
    assert journey.DEFAULTS["wipe_gold_pct"] == 0.10
    assert journey.DEFAULTS["wipe_exp_pct"] == 0.20
    assert journey.DEFAULTS["revive_pct"] == 0.01
    assert journey.DEFAULTS["respawn_pct"] == 0.50


# ── ในห้องจริง ──

def test_ล้มยกทีมแล้วรอบกลับไป_1():
    _party()
    room.begin(1)
    st = room._room(1)
    st["extra"]["round"] = 12
    b = st["extra"]["battle"]
    for u in b["units"].values():
        if u["side"] == "party":
            u["hp"] = 0
    b.update(over=True, winner="monster")
    room.settle(st)
    assert st["extra"]["round"] == 1
    assert st["extra"]["wiped"] is True


def test_ล้มยกทีมหักโทษจริงในฐานข้อมูล():
    player_model.update_player_fields(1, {"cash": 5000, "level": 20, "exp": 99999})
    _party()
    room.begin(1)
    st = room._room(1)
    b = st["extra"]["battle"]
    for u in b["units"].values():
        if u["side"] == "party":
            u["hp"] = 0
    b.update(over=True, winner="monster")
    room.settle(st)
    assert int(player_model.get_player(1)["cash"]) == 4500


def test_หักโทษครั้งเดียวไม่ใช่ทุกครั้งที่_poll():
    """⭐ บั๊กแบบเดียวกับจ่ายรางวัลซ้ำ — poll ทุก 2 วิ หักซ้ำก็หมดตัว"""
    player_model.update_player_fields(1, {"cash": 5000, "level": 20, "exp": 99999})
    _party()
    room.begin(1)
    st = room._room(1)
    b = st["extra"]["battle"]
    for u in b["units"].values():
        if u["side"] == "party":
            u["hp"] = 0
    b.update(over=True, winner="monster")
    for _ in range(5):
        room.settle(st)
        room.view(1)
    assert int(player_model.get_player(1)["cash"]) == 4500, "หักโทษซ้ำ"


def test_ชนะไม่โดนโทษ():
    player_model.update_player_fields(1, {"cash": 5000})
    _party()
    room.begin(1)
    st = room._room(1)
    b = st["extra"]["battle"]
    for u in b["units"].values():
        u["hp"] = u["hp_max"] if u["side"] == "party" else 0
    b.update(over=True, winner="party")
    room.settle(st)
    assert int(player_model.get_player(1)["cash"]) >= 5000
    assert not st["extra"].get("wiped")


def test_เริ่มออกเดินทางใหม่ได้หลังล้มยกทีม():
    _party()
    room.begin(1)
    st = room._room(1)
    st["extra"]["round"] = 8
    b = st["extra"]["battle"]
    for u in b["units"].values():
        if u["side"] == "party":
            u["hp"] = 0
    b.update(over=True, winner="monster")
    room.settle(st)
    from bot import lobby
    lobby.save(st["room"], st)

    ok, _ = room.restart(1)
    assert ok
    got = room.view(1)
    assert got["round"] == 1 and not got.get("wiped")
    assert got["battle"]["in_battle"]


def test_คนที่ไม่ใช่หัวห้องเริ่มใหม่ไม่ได้():
    _party()
    room.begin(1)
    st = room._room(1)
    st["extra"]["wiped"] = True
    from bot import lobby
    lobby.save(st["room"], st)
    ok, r = room.restart(2)
    assert not ok and "หัวห้อง" in r["error"]


def test_จอเห็นเลือดที่ฟื้นแล้วไม่ใช่ศูนย์():
    """⭐ view() ต้อง settle ก่อนถ่ายภาพ ไม่งั้นจอเห็นเลือด 0 ทั้งที่ฟื้นไปแล้ว

    (เจ้าของเกมเห็น "0/480" บนจอตอนเทสด้วยมือ 2026-09-04)
    """
    _party()
    room.begin(1)
    st = room._room(1)
    b = st["extra"]["battle"]
    b["units"]["p1"]["hp"] = 0                 # ล้ม แต่เพื่อนยังรอด
    b["units"]["p2"]["hp"] = b["units"]["p2"]["hp_max"]
    for u in b["units"].values():
        if u["side"] == "monster":
            u["hp"] = 0
    b.update(over=True, winner="party")
    from bot import lobby
    lobby.save(st["room"], st)

    me = [u for u in room.view(1)["battle"]["units"] if u["id"] == "p1"][0]
    assert me["hp"] >= 1, "จอยังเห็นเลือด 0 ทั้งที่ควรฟื้นมาแล้ว"
    assert me["alive"] is True


def test_จอยังเห็นว่าตายหลังล้มยกทีม():
    """⭐ ตายก็ต้องเห็นว่าตาย — จอจะได้ขึ้นป้ายแพ้ทับ"""
    _party()
    room.begin(1)
    st = room._room(1)
    b = st["extra"]["battle"]
    for u in b["units"].values():
        if u["side"] == "party":
            u["hp"] = 0
    b.update(over=True, winner="monster")
    from bot import lobby
    lobby.save(st["room"], st)

    got = room.view(1)
    assert got["wiped"] is True
    for u in got["battle"]["units"]:
        if u["side"] == "party":
            assert u["hp"] == 0, f"{u['id']} เลือดเด้งกลับตอนแพ้ ({u['hp']})"
            assert u["alive"] is False


def test_กดเริ่มใหม่แล้วค่อยฟื้นครึ่งเลือด():
    _party()
    room.begin(1)
    st = room._room(1)
    st["extra"]["round"] = 8
    b = st["extra"]["battle"]
    for u in b["units"].values():
        if u["side"] == "party":
            u["hp"] = 0
    b.update(over=True, winner="monster")
    room.settle(st)
    from bot import lobby
    lobby.save(st["room"], st)

    ok, _ = room.restart(1)
    assert ok

    # ⚠️ วัดที่ **ฐานข้อมูล** ไม่ใช่หน่วยในสนาม — พอสมรภูมิใหม่เปิด มอนที่ไวกว่า
    #    ได้เดินทันที อาจซัดจาก 50 ลงมาชน "คุ้มกันรอบแรก" ที่ 1 ก่อนเทสจะอ่านค่า
    #    (ฉบับแรกแดงแบบสุ่มเพราะเหตุนี้ ไม่ใช่เพราะโค้ดผิด — 2026-09-04)
    for who in (1, 2):
        pl = player_model.get_player(who)
        want = journey.respawn_hp(room.gear_stats(pl)[1])
        assert int(pl["hp"]) == want, f"uid {who} ควรฟื้น {want} ได้ {pl['hp']}"

    got = room.view(1)
    assert got["round"] == 1 and not got.get("wiped")
    assert got["battle"]["in_battle"]


# ── ตารางอันดับดาเมจ (เจ้าของเกมสั่ง 2026-09-04) ──

def _hit(st, uid, dmg):
    """ตั้งดาเมจสะสมของคนนี้ตรง ๆ (ใช้เทสตรรกะตาราง ไม่ได้เทสตัวนับ)"""
    b = st["extra"]["battle"]
    b["units"][f"p{uid}"]["dmg_done"] = \
        int(b["units"][f"p{uid}"].get("dmg_done") or 0) + dmg


def test_ตีจริงแล้วดาเมจถูกนับ():
    """⭐ เทสอื่นตั้ง dmg_done เอง ไม่เคยแตะโค้ดที่นับจริงใน engine.strike

    ย้อนเทสถอดตัวนับออกแล้วเทสยังเขียวหมด (2026-09-04)
    """
    import random as _r
    from bot.games.party import engine
    _party()
    room.begin(1)
    b = room._room(1)["extra"]["battle"]
    me = b["units"]["p1"]
    tgt = [u for u in b["units"].values() if u["side"] == "monster"][0]
    tgt["hp"] = tgt["hp_max"] = 99999
    me["dmg_done"] = 0

    for seed in range(15):
        engine.strike(me, tgt, "attack", _r.Random(seed))
    assert int(me.get("dmg_done") or 0) > 0, "ตีจริงแล้วดาเมจไม่ถูกนับ"


def test_ตีพลาดไม่นับดาเมจ():
    """พลาดคือไม่โดน จะไปนับดาเมจไม่ได้"""
    from bot.games.party import engine
    from tests.test_party_contest import Dice
    _party()
    room.begin(1)
    b = room._room(1)["extra"]["battle"]
    me = b["units"]["p1"]
    tgt = [u for u in b["units"].values() if u["side"] == "monster"][0]
    tgt["stats"] = {"dice_count": 1}
    me["dmg_done"] = 0
    engine.strike(me, tgt, "attack", Dice(1, 20))     # คนทอย 1 มอนทอย 20
    assert int(me.get("dmg_done") or 0) == 0


def test_เก็บดาเมจรายคนเข้าตาราง():
    _party()
    room.begin(1)
    st = room._room(1)
    _hit(st, 1, 500)
    _hit(st, 2, 1200)
    b = st["extra"]["battle"]
    for u in b["units"].values():
        u["hp"] = u["hp_max"] if u["side"] == "party" else 0
    b.update(over=True, winner="party")
    room.settle(st)

    rows = room._score_board(st)
    assert [r["dmg"] for r in rows] == [1200, 500], f"ไม่ได้เรียงอันดับ: {rows}"


def test_ดาเมจสะสมข้ามรอบ():
    """ตารางโชว์ตอนจบการเดินทาง ต้องนับตั้งแต่รอบ 1 ไม่ใช่แค่รอบสุดท้าย"""
    from bot import lobby
    _party()
    room.begin(1)
    st = room._room(1)
    _hit(st, 1, 300)
    b = st["extra"]["battle"]
    for u in b["units"].values():
        u["hp"] = u["hp_max"] if u["side"] == "party" else 0
    b.update(over=True, winner="party")
    room.settle(st)
    lobby.save(st["room"], st)

    room.again(1)
    st = room._room(1)
    _hit(st, 1, 200)
    b = st["extra"]["battle"]
    for u in b["units"].values():
        u["hp"] = u["hp_max"] if u["side"] == "party" else 0
    b.update(over=True, winner="party")
    room.settle(st)

    assert room._score_board(st)[0]["dmg"] == 500, "ดาเมจไม่สะสมข้ามรอบ"


def test_นับดาเมจซ้ำไม่ได้():
    """⭐ บั๊กตระกูลเดียวกับจ่ายรางวัลซ้ำ

    ⚠️ ต้องเรียก _bank_score ซ้ำ ๆ ตรง ๆ — เรียกผ่าน view() ไม่ได้ตรวจอะไร
       เพราะธง paid กันไว้อีกชั้นอยู่แล้ว (ย้อนเทสจับได้ 2026-09-04)
    """
    _party()
    room.begin(1)
    st = room._room(1)
    b = st["extra"]["battle"]
    _hit(st, 1, 400)
    for _ in range(5):
        room._bank_score(st, b)
    assert room._score_board(st)[0]["dmg"] == 400, "นับดาเมจซ้ำ"


def test_เริ่มการเดินทางใหม่ล้างตาราง():
    from bot import lobby
    _party()
    room.begin(1)
    st = room._room(1)
    _hit(st, 1, 999)
    b = st["extra"]["battle"]
    for u in b["units"].values():
        u["hp"] = u["hp_max"] if u["side"] == "party" else 0
    b.update(over=True, winner="party")
    room.settle(st)
    lobby.save(st["room"], st)
    room.leave_party(1)
    room.leave_party(2)

    _party()
    room.begin(1)
    assert room._score_board(room._room(1)) == [], "การเดินทางใหม่ยังจำสกอร์เก่า"


def test_จอได้รับรอบกับตารางไปวาด():
    """renderer รับแค่ก้อน battle — รอบกับตารางต้องอยู่ในนั้น"""
    _party()
    room.begin(1)
    st = room._room(1)
    _hit(st, 1, 250)
    b = st["extra"]["battle"]
    for u in b["units"].values():
        u["hp"] = u["hp_max"] if u["side"] == "party" else 0
    b.update(over=True, winner="party")
    from bot import lobby
    lobby.save(st["room"], st)

    got = room.view(1)["battle"]
    assert got["round"] == 1
    assert got["score"] and got["score"][0]["dmg"] == 250
    assert got["score"][0]["name"]
