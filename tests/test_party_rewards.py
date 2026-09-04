"""🎭 รางวัล + ดรอป + กันเงินเฟ้อ (เฟส 5)

⚠️ **เทสชุดนี้คือด่านกันเงินเฟ้อ** — ทองงอกแล้วแก้ทีหลังยากมาก
   ต้องไปไล่ลดของผู้เล่นที่ได้ไปแล้ว ซึ่งไม่มีใครยอม
   กฎเหล็ก: ทองรวมที่จ่ายออก ≤ 1.5 เท่าของที่ควรได้ตอนเล่นเดี่ยว
"""
import random
import sqlite3

import pytest

from bot import lobby
from bot.models import player_model
from bot.games.party import engine, rewards, room


@pytest.fixture(autouse=True)
def db(tmp_path, monkeypatch):
    """ฐานข้อมูลใหม่ทุกเทส — **ทั้งห้องและตัวละคร**

    ⚠️ ไม่หนีบ player_model.DB_NAME ด้วย เทสจะไปอ่าน/เขียน game_data.db ของจริง
       ผลคือ (ก) ผลเทสขึ้นกับตัวละครจริงในเครื่อง (ข) เฟส 5 จ่ายทองใส่ DB จริง
    """
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
        player_model.get_player(uid)          # สร้างแถวตัวละครไว้ล่วงหน้า
    yield


class FixedRng:
    """เต๋าที่ออกหน้าเดิมเสมอ — เทสเงินต้องไม่ขึ้นกับดวง"""

    def randint(self, a, b):
        return b

    def choice(self, seq):
        return list(seq)[0]

    def choices(self, seq, weights=None, k=1):
        return [list(seq)[0]] * k

    def random(self):
        return 0.0


def _mons(n, gold_mult=2, rank="Common"):
    return [{"id": f"m{i+1}", "rank": rank,
             "stats": {"gold_mult": gold_mult, "exp_reward": 25}}
            for i in range(n)]


# ── เพดานทอง ──

def test_ทองที่จ่ายไม่เกินเพดาน():
    """⭐ กฎเหล็กข้อเดียวของเฟสนี้"""
    for size in range(1, 6):
        got = rewards.split_gold(1000, size)
        assert sum(got) <= int(1000 * rewards.PARTY_MULT), \
            f"ปาร์ตี้ {size} คนจ่าย {sum(got)} เกินเพดาน 1500"


def test_เพดานคือ_1_จุด_5_เท่าไม่ใช่ค่าอื่น():
    """⭐ ตรึงตัวเลขจริง ไม่ใช่คำนวณจากค่าคงที่

    ⚠️ เทสข้ออื่นในไฟล์นี้คิดคำตอบจาก PARTY_MULT เอง — ใครแก้ค่าคงที่เป็น 3.0
       เทสจะเขียวหมดทั้งที่ทองออกเป็นสองเท่า (ย้อนเทสจับได้ 2026-09-04)
       ข้อนี้จึงต้องเขียนเลขดิบไว้ตรง ๆ เจ้าของเกมเคาะ 1.5 เท่า
    """
    assert rewards.PARTY_MULT == 1.5
    assert sum(rewards.split_gold(1000, 4)) == 1500
    assert rewards.split_gold(1000, 4) == [375, 375, 375, 375]
    assert sum(rewards.split_gold(100, 3)) == 150


def test_หารกันครบไม่มีทองหล่นหาย():
    """เศษต้องแจกจนหมด ไม่ปัดทิ้งและไม่เสกเพิ่ม"""
    for size in range(1, 6):
        for total in (0, 1, 7, 999, 1000):
            got = rewards.split_gold(total, size)
            assert len(got) == size
            assert sum(got) == int(total * rewards.PARTY_MULT)
            assert max(got) - min(got) <= 1, "แบ่งไม่เท่ากันเกิน 1 ทอง"


def test_ไม่มีใครได้ทองติดลบ():
    assert all(g >= 0 for g in rewards.split_gold(-500, 3))


def test_เล่น_100_รอบทองไม่งอกเกิน():
    """⭐ กันเงินเฟ้อ — เทียบกับ 'ต่างคนต่างไปสู้มอนคนละตัว'

    ใช้เต๋าออกหน้าเดิมเพื่อให้ผลเป๊ะ ไม่ใช่ผ่านเพราะดวงดี
    """
    rng = FixedRng()
    for size in (2, 3, 5):
        paid = solo = 0
        for _ in range(100):
            mons = _mons(size + 1)                       # มอน 3-6 ตัว
            gold, _ = rewards.encounter_value(mons, size, rng)
            paid += sum(rewards.split_gold(gold, size))
            solo += size * rewards.monster_gold(mons[0], rng)
        assert paid == int(solo * rewards.PARTY_MULT), \
            f"ปาร์ตี้ {size} คนจ่าย {paid} แต่เพดานคือ {int(solo * rewards.PARTY_MULT)}"


def test_ทองคิดตามจำนวนคนไม่ใช่จำนวนมอน():
    """⚠️ หัวใจกันเงินเฟ้อ — มอน 5 ตัวเลือดรวมเท่ามอน 2 ตัว (monsters._budget)
       ถ้าคิดทองตามจำนวนตัวจะจ่าย 5 ตัวเต็ม = พิมพ์เงินฟรี
    """
    rng = FixedRng()
    few, _ = rewards.encounter_value(_mons(3), 2, rng)
    many, _ = rewards.encounter_value(_mons(5), 2, rng)
    assert few == many, f"มอน 3 ตัวให้ {few} แต่ 5 ตัวให้ {many} — งอกตามจำนวนตัว"


def test_ปาร์ตี้ใหญ่ได้ทองรวมมากกว่าแต่ต่อหัวเท่ากัน():
    rng = FixedRng()
    g2, _ = rewards.encounter_value(_mons(4), 2, rng)
    g5, _ = rewards.encounter_value(_mons(4), 5, rng)
    assert g5 > g2
    assert rewards.split_gold(g2, 2)[0] == rewards.split_gold(g5, 5)[0], \
        "ต่อหัวต้องเท่ากัน ไม่งั้นชวนคนเยอะ ๆ แล้วรวยกว่า"


# ── ดรอปไอเทม ──

def test_ดรอปได้คนเดียว():
    """สเปกข้อ 7: สุ่มว่าใครได้ แล้วกิฟกันเองด้วย !give"""
    rng = random.Random(4)
    got = [rewards.roll_drop(_mons(3), ["1", "2", "3"], rng) for _ in range(60)]
    for d in got:
        if d:
            assert d["uid"] in ("1", "2", "3")
            assert isinstance(d.get("item"), str) and d["item"]
    assert any(got), "ดรอป 60 ครั้งไม่ได้อะไรเลย — เรทพังหรือเทสไม่ได้พิสูจน์อะไร"


def test_ดรอปกระจายไม่ใช่คนเดิมตลอด():
    rng = random.Random(9)
    who = {d["uid"] for d in
           (rewards.roll_drop(_mons(3), ["1", "2", "3"], rng) for _ in range(80))
           if d}
    assert len(who) >= 2, f"ดรอปตกที่ {who} ตลอด — ไม่ได้สุ่มจริง"


def test_ปาร์ตี้ว่างไม่ดรอป():
    assert rewards.roll_drop(_mons(3), [], random.Random(1)) is None


def test_ดรอปครั้งเดียวต่อสมรภูมิไม่ใช่ต่อมอน():
    """มอน 5 ตัวไม่ได้แปลว่าได้ของ 5 ชิ้น — ของจะล้นเกม"""
    d = rewards.roll_drop(_mons(5), ["1", "2"], FixedRng())
    assert d is None or isinstance(d, dict), "ต้องคืนชิ้นเดียวหรือไม่ได้เลย"


# ── จ่ายจริงในสมรภูมิ ──

def _win(uids=(1, 2)):
    """เล่นจนปาร์ตี้ชนะ — คืนห้อง (ข้ามกระดานที่แพ้)"""
    for seed in range(60):
        _, st = room.open_party(uids[0], "เอ")
        for u in uids[1:]:
            room.join_party(u, f"P{u}", st["room"])
        room.begin(uids[0])
        st = room._room(uids[0])
        rng = random.Random(seed)
        for _ in range(400):
            b = st["extra"]["battle"]
            if b["over"]:
                break
            who = engine.current_actor(st)
            if b["units"][who]["side"] == "monster":
                room._run_monsters(st, rng)
                continue
            foes = [u["id"] for u in b["units"].values()
                    if u["side"] == "monster" and u["hp"] > 0]
            if not foes:
                break
            engine.act(st, int(who[1:]), "attack", foes[0], rng)
            room._run_monsters(st, rng)
        # ⚠️ ต้องเขียนกลับ ไม่งั้น room.act/room.view โหลดสถานะเก่าจาก DB
        lobby.save(st["room"], st)
        if st["extra"]["battle"]["winner"] == "party":
            room.settle(st)
            return st
        for u in uids:
            room.leave_party(u)
    pytest.skip("สุ่ม 60 กระดานแล้วปาร์ตี้ไม่ชนะเลย")


def _cash(uid):
    from bot.models import player_model
    return int((player_model.get_player(uid) or {}).get("cash") or 0)


def test_ชนะแล้วได้ทองจริง():
    before = {u: _cash(u) for u in (1, 2)}
    st = _win()
    assert st["extra"]["battle"]["winner"] == "party"
    assert any(_cash(u) > before[u] for u in (1, 2)), "ชนะแล้วไม่ได้ทองเลย"


def test_จ่ายรางวัลครั้งเดียวเท่านั้น():
    """⭐ บั๊กเงินคลาสสิก — poll ซ้ำหรือกดซ้ำแล้วได้ทองซ้ำ

    (ล็อบบี้ UNO เคยมีบั๊กทำนองนี้: ทองหายไป 2000 ตอนคนสุดท้ายออก)
    """
    st = _win()
    after = {u: _cash(u) for u in (1, 2)}
    for _ in range(5):
        room.view(1)
        room.act(1, "attack", "m1")            # กดซ้ำหลังจบ ต้องไม่จ่ายอีก
        room.settle(st)
    assert {u: _cash(u) for u in (1, 2)} == after, "จ่ายรางวัลซ้ำ = พิมพ์เงิน"


def test_แพ้แล้วไม่ได้อะไร():
    _, st = room.open_party(1, "เอ")
    room.join_party(2, "บี", st["room"])
    room.begin(1)
    st = room._room(1)
    st["extra"]["battle"].update(over=True, winner="monster")
    before = {u: _cash(u) for u in (1, 2)}
    room.settle(st)
    assert {u: _cash(u) for u in (1, 2)} == before


def test_หนีแล้วไม่ได้อะไร():
    """กด 🏃 หนีแล้วยังได้ทอง = ฟาร์มด้วยการเปิดห้องแล้วหนีรัว ๆ"""
    _, st = room.open_party(1, "เอ")
    room.join_party(2, "บี", st["room"])
    room.begin(1)
    st = room._room(1)
    st["extra"]["battle"].update(over=True, winner="flee")
    before = {u: _cash(u) for u in (1, 2)}
    room.settle(st)
    assert {u: _cash(u) for u in (1, 2)} == before


def test_view_บอกรางวัลให้หน้าเว็บโชว์():
    st = _win()
    got = room.view(1)
    assert got["battle"]["over"]
    assert "reward" in got, "หน้าเว็บไม่รู้ว่าได้อะไรไปบ้าง"
    assert "gold" in got["reward"]


# ── ประตูเงิน ──

def test_เส้นทางปาร์ตี้อยู่กลุ่ม_money():
    """⚠️ UNO เคยลืมข้อนี้ อยู่กลุ่ม write ที่หลวมกว่า
       เฟส 5 เริ่มจ่ายเงินจริงแล้ว ต้องย้ายกลุ่ม
    """
    from license_server import rate_limit
    assert rate_limit.group_for("/api/web/party/room", "POST") == "money"
