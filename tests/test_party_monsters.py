"""🎭 มอนหลายตัว + บอสหลายเฟส (เฟส 4)

⚠️ กฎเหล็กของเฟสนี้: **บอสต้องเตือนก่อนออกท่าใหญ่ 1 ตาเสมอ**
   ตายแบบไม่ทันตั้งตัวไม่สนุก — เจ้าของเกมสั่งไว้ในสเปก
   `test_ท่าใหญ่ต้องเตือนก่อนเสมอ` เล่นจริงทั้งสมรภูมิเพื่อพิสูจน์ข้อนี้
"""
import json
import random
import sqlite3

import pytest

from bot.models import player_model
from bot.games.party import engine, journey, monsters, room


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
    # ⚠️ ตรึงให้เจอมอนเสมอ — ตั้งแต่เฟส 10b begin() สุ่มเหตุการณ์ได้หลายแบบ
    #    เทสชุดนี้ตรวจการต่อสู้ จึงต้องล็อกไว้ ไม่งั้นแดงแบบสุ่ม
    #    (เทสของเหตุการณ์อื่นอยู่ที่ test_party_events_roll.py)
    from bot.games.party import encounter as _enc
    monkeypatch.setattr(_enc, "roll_kind", lambda *a, **k: "monster")
    player_model.init_db()
    for uid in range(1, 7):
        player_model.get_player(uid)          # สร้างแถวตัวละครไว้ล่วงหน้า
    yield


# ── เฟสบอส ──

def test_เฟสเปลี่ยนตรงเปอร์เซ็นต์():
    """ขอบเขตต้องเป๊ะ ไม่งั้นบอสคลั่งช้า/เร็วกว่าที่ผู้เล่นคาด"""
    assert monsters.boss_phase(100, 100) == "normal"
    assert monsters.boss_phase(71, 100) == "normal"
    assert monsters.boss_phase(70, 100) == "rage", "แตะ 70% พอดีต้องเข้าคลั่งแล้ว"
    assert monsters.boss_phase(31, 100) == "rage"
    assert monsters.boss_phase(30, 100) == "desperate", "แตะ 30% พอดีต้องสิ้นหวัง"
    assert monsters.boss_phase(0, 100) == "desperate"


def test_เฟสไม่พังเมื่อเลือดสูงสุดเป็นศูนย์():
    """หารศูนย์ = ทั้งสมรภูมิพัง ต้องกันไว้"""
    assert monsters.boss_phase(0, 0) in monsters.PHASES


# ── เตือนก่อนท่าใหญ่ ──

def test_เฟสปกติไม่ออกท่าใหญ่():
    boss = {"hp": 100, "hp_max": 100, "since_big": 99}
    assert monsters.telegraph(boss) is None, "เลือดเต็มยังไม่ควรมีท่าใหญ่"


def test_คลั่งแล้วออกท่าใหญ่ตามรอบ():
    boss = {"hp": 50, "hp_max": 100, "since_big": 0}
    assert monsters.telegraph(boss) is None, "เพิ่งออกไป ยังไม่ถึงรอบ"
    boss["since_big"] = 99
    assert monsters.telegraph(boss), "ถึงรอบแล้วต้องเตือน"


def test_สิ้นหวังออกท่าใหญ่ถี่กว่าคลั่ง():
    assert monsters.BIG_MOVE_EVERY["desperate"] < monsters.BIG_MOVE_EVERY["rage"]


# ── กลุ่มมอน ──

def test_ทุกตัวมี_id_ไม่ซ้ำ():
    """id ซ้ำ = ตีตัวหนึ่งแล้วอีกตัวเลือดลด (renderer ก็วาดทับกัน)"""
    g = monsters.spawn_group(1, 5, random.Random(7))
    ids = [m["id"] for m in g]
    assert len(ids) == len(set(ids))


def test_จำนวนมอนไม่เกิน_5_ตัวเสมอ():
    """⚠️ กฎเดิม "3-5 ตัวเสมอ" ถูกสเปกเสริม 2026-09-04 ทับแล้ว
       ตอนนี้จำนวนขึ้นกับ **รอบการเดินทาง** โดยมีขั้นต่ำตามจำนวนคน
    """
    for size in range(1, 6):
        for rnd in (1, 3, 6, 10, 30):
            g = monsters.spawn_group(1, size, random.Random(size), rnd=rnd)
            assert 1 <= len(g) <= 5, f"ปาร์ตี้ {size} คน รอบ {rnd} เจอ {len(g)} ตัว"


def test_รอบลึกเจอมอนมากกว่ารอบแรก():
    early = journey.monster_count(1, 2)
    late = journey.monster_count(10, 2)
    assert late > early, f"รอบ 10 เจอ {late} ตัว ไม่มากกว่ารอบ 1 ({early})"


def test_ปาร์ตี้ใหญ่ไม่เจอมอนตัวเดียว():
    """⭐ สเปกเปล่า ๆ ว่ารอบ 1-3 เจอ 1-2 ตัว — ปาร์ตี้ 5 คนจะรุมจบในตาเดียว
       อีก 4 คนนั่งดู เจ้าของเกมเคาะให้มีขั้นต่ำครึ่งหนึ่งของจำนวนคน
    """
    assert journey.monster_count(1, 5) >= 2
    assert journey.monster_count(1, 1) >= 1


def test_มอนแรงขึ้นตามรอบจริง():
    """ตัวคูณรอบต้อง **คูณทับ** งบที่คุมตามจำนวนคน ไม่ใช่แทนที่"""
    a = monsters.spawn_group(1, 3, random.Random(4), rnd=1)
    b = monsters.spawn_group(1, 3, random.Random(4), rnd=9)
    assert sum(m["hp_max"] for m in b) > sum(m["hp_max"] for m in a)
    assert sum(m["atk"] for m in b) > sum(m["atk"] for m in a)


def test_งบตามจำนวนคนยังทำงานอยู่ควบคู่กัน():
    """คูณทับ = ของเดิมต้องยังมีผล ไม่ใช่โดนตัวคูณรอบกลบ"""
    small = monsters.spawn_group(1, 2, random.Random(4), rnd=5)
    big = monsters.spawn_group(1, 5, random.Random(4), rnd=5)
    assert sum(m["hp_max"] for m in big) > sum(m["hp_max"] for m in small)


def test_บอสเรดมีบอสหนึ่งตัวกับลูกน้อง_2_ถึง_4():
    g = monsters.spawn_group(1, 3, random.Random(3), boss=True)
    bosses = [m for m in g if m.get("boss")]
    assert len(bosses) == 1, f"บอสเรดต้องมีบอสตัวเดียว ได้ {len(bosses)}"
    assert 2 <= len(g) - 1 <= 4


def test_บอสเรดใช้มอนของเกมหลักไม่ได้สร้างใหม่():
    """เจ้าของเกมสั่ง: ใช้ดาต้าเดิม ไม่งั้นมอนสองโหมดไม่ตรงกัน"""
    from bot import adventure_core
    g = monsters.spawn_group(1, 3, random.Random(3), boss=True)
    for m in g:
        assert m.get("rank") in adventure_core.MONSTER_RANKS
        assert m.get("stats"), "ไม่มี stats = ไม่ได้มาจาก spawn_monster"


def test_บอสแรงกว่าลูกน้อง():
    g = monsters.spawn_group(1, 3, random.Random(11), boss=True)
    boss = [m for m in g if m.get("boss")][0]
    for m in g:
        if not m.get("boss"):
            assert boss["hp_max"] > m["hp_max"] or boss["atk"] > m["atk"]


# ── สมดุล ──

def test_งบคุมความแรงรวมไม่ใช่จำนวนตัว():
    """มอน 3 ตัวกับ 5 ตัวสำหรับปาร์ตี้เท่ากัน ต้องแรงรวมพอ ๆ กัน

    ⚠️ นี่คือหัวใจของสมดุลโหมดนี้ — จำนวนตัวมีไว้ให้ภาพดูเป็นกลุ่ม
       ไม่ใช่ให้ยากขึ้นตามจำนวน (ถ้าลบ _budget ปาร์ตี้ 2 คนชนะ 1/40)
    """
    g3 = [{"hp_max": 100, "hp": 100, "atk": 10} for _ in range(3)]
    g5 = [{"hp_max": 100, "hp": 100, "atk": 10} for _ in range(5)]
    monsters._budget(g3, 2)
    monsters._budget(g5, 2)
    tot = lambda g: sum(m["hp_max"] for m in g)
    assert abs(tot(g3) - tot(g5)) <= 10,         f"3 ตัวรวม {tot(g3)} แต่ 5 ตัวรวม {tot(g5)} — งบบานตามจำนวนตัว"


def test_ปาร์ตี้ใหญ่เจอของหนักกว่าปาร์ตี้เล็ก():
    """ไม่งั้นชวนคนเยอะ ๆ แล้วเกมง่ายจนไม่มีความหมาย"""
    g = [{"hp_max": 100, "hp": 100, "atk": 10} for _ in range(4)]
    monsters._budget(g, 2)
    small = sum(m["hp_max"] for m in g)
    g = [{"hp_max": 100, "hp": 100, "atk": 10} for _ in range(4)]
    monsters._budget(g, 5)
    assert sum(m["hp_max"] for m in g) > small


def test_รอบแรกต้องชนะได้สบาย():
    """รอบ 1 เจอมอน 1-2 ตัว — ตั้งใจให้ง่าย เป็นการเริ่มต้นที่ไม่ทรมาน

    ⚠️ เทสเดิมตรึงว่า "ห้ามชนะเกิน 11/12" ซึ่งใช้ไม่ได้แล้วหลังเฟส 10a
       เพราะรอบ 1 ควรง่าย ย้ายเงื่อนไข "ต้องไม่ง่ายเกิน" ไปวัดที่รอบลึกแทน
    """
    wins = 0
    for seed in range(12):
        st = _battle(uids=(1, 2, 3))
        _play(st, random.Random(seed))
        wins += st["extra"]["battle"]["winner"] == "party"
    assert wins >= 8, f"รอบแรกชนะแค่ {wins}/12 — เริ่มต้นยากเกินไป"


def test_รอบลึกต้องไม่ชนะทุกกระดาน():
    """⭐ ยิ่งเดินไกลยิ่งเสี่ยง — ถ้ารอบ 12 ยังชนะรวดคือตัวคูณรอบไม่ทำงาน"""
    from bot import lobby
    wins = 0
    for seed in range(12):
        st = _battle(uids=(1, 2, 3))
        st["extra"]["round"] = 12
        st["extra"].pop("battle", None)
        room._spawn_battle(st)
        for u in st["extra"]["battle"]["units"].values():
            if u["side"] == "party":
                u["hp"] = u["hp_max"]
        lobby.save(st["room"], st)
        _play(st, random.Random(seed))
        wins += st["extra"]["battle"]["winner"] == "party"
        for uid in (1, 2, 3):
            room.leave_party(uid)
    assert wins < 12, f"รอบ 12 ยังชนะ {wins}/12 — ความยากไม่ไต่ระดับจริง"


# ── ในสมรภูมิจริง ──

def _battle(uids=(1, 2), boss_raid=False):
    _, st = room.open_party(uids[0], "เอ")
    for u in uids[1:]:
        room.join_party(u, f"P{u}", st["room"])
    room.begin(uids[0], boss_raid=boss_raid)
    return room._room(uids[0])


def _play(st, rng, limit=400):
    """เล่นจนจบ — คืน events ทั้งหมดที่เกิดขึ้น"""
    evs = []
    for _ in range(limit):
        b = st["extra"]["battle"]
        if b["over"]:
            break
        who = engine.current_actor(st)
        if b["units"][who]["side"] == "monster":
            evs += room._run_monsters(st, rng)
            continue
        foes = [u["id"] for u in b["units"].values()
                if u["side"] == "monster" and u["hp"] > 0]
        if not foes:
            break
        # เก็บลูกน้องก่อน (m1 คือบอส) — เล่นแบบคนจริงและบอสจะได้อยู่ถึงเฟสคลั่ง
        ok, r = engine.act(st, int(who[1:]), "attack", foes[-1], rng)
        assert ok, r
        evs += r["events"]
        evs += room._run_monsters(st, rng)
    return evs


def test_ท่าใหญ่ต้องเตือนก่อนเสมอ():
    """⭐ กฎเหล็ก — เล่นจริงหลายสมรภูมิแล้วไล่ดูทุกท่าใหญ่ของมอน

    เทสหน่วยพิสูจน์ข้อนี้ไม่ได้ ต้องดูลำดับเหตุการณ์จริง
    """
    seen = 0
    for seed in range(25):
        st = _battle(boss_raid=True)
        # ⚠️ ตั้งให้บอสพร้อมออกท่าตั้งแต่ต้น แล้วค่อยเล่นจริง
        #    ปล่อยตามธรรมชาติแล้วสมรภูมิจบใน 3-6 รอบ บอสแทบไม่ทันเข้าเฟสคลั่ง
        #    เจอ 1 ครั้งใน 25 กระดาน = เทสไม่ได้พิสูจน์อะไร (ตัวกัน seen จับได้)
        boss = st["extra"]["battle"]["units"]["m1"]
        boss["hp"] = max(1, int(boss["hp_max"] * 0.5))     # เข้าเฟสคลั่ง
        boss["since_big"] = 99                              # ถึงรอบออกท่าพอดี
        evs = _play(st, random.Random(seed))
        warned = set()
        for e in evs:
            if e["t"] == "telegraph":
                warned.add(e["who"])
            elif e["t"] == "aoe" and e["from"].startswith("m"):
                seen += 1
                assert e["from"] in warned, \
                    f"มอน {e['from']} ออกท่าใหญ่โดยไม่เตือนก่อน (seed {seed})"
                warned.discard(e["from"])
    assert seen >= 3, f"เล่น 25 สมรภูมิเจอท่าใหญ่แค่ {seen} ครั้ง — เทสไม่ได้พิสูจน์อะไร"


def test_ท่าใหญ่โดนทุกคนที่ยังไม่ล้ม():
    st = _battle(uids=(1, 2, 3), boss_raid=True)
    b = st["extra"]["battle"]
    boss = b["units"]["m1"]
    boss.update(hp=1, since_big=99)
    alive = [u["id"] for u in b["units"].values()
             if u["side"] == "party" and u["hp"] > 0]

    b["turn"] = b["order"].index(boss["id"])
    engine.monster_turn(st, random.Random(1))          # ตาเตือน
    b["turn"] = b["order"].index(boss["id"])
    evs = engine.monster_turn(st, random.Random(1))    # ตาปล่อยท่า
    hit = [e for e in evs if e["t"] == "aoe"]
    assert hit, "เตือนแล้วแต่ไม่ปล่อยท่า"
    assert set(hit[0]["targets"]) == set(alive), "ท่าใหญ่ต้องโดนทุกคน"


def test_ตาเตือนยังไม่ทำดาเมจ():
    """เตือนแล้วตีเลยในตาเดียว = เตือนไปก็เท่านั้น"""
    st = _battle(boss_raid=True)
    b = st["extra"]["battle"]
    boss = b["units"]["m1"]
    boss.update(hp=1, since_big=99)
    b["turn"] = b["order"].index(boss["id"])
    before = {u["id"]: u["hp"] for u in b["units"].values()}

    evs = engine.monster_turn(st, random.Random(1))
    assert any(e["t"] == "telegraph" for e in evs)
    for u in b["units"].values():
        assert u["hp"] == before[u["id"]], f"{u['id']} เสียเลือดในตาเตือน"


def test_บอสเปลี่ยนเฟสแล้วบอกผู้เล่น():
    st = _battle(boss_raid=True)
    b = st["extra"]["battle"]
    boss = b["units"]["m1"]
    boss.update(hp=max(1, boss["hp_max"] // 2))
    b["turn"] = b["order"].index(boss["id"])
    evs = engine.monster_turn(st, random.Random(1))
    assert any(e["t"] == "phase" and e["phase"] == "rage" for e in evs)


def test_มอนที่ล้มแล้วไม่ได้เทิร์น():
    st = _battle(uids=(1, 2, 3))
    evs = _play(st, random.Random(2))
    dead = set()
    for e in evs:
        if e["t"] == "die":
            dead.add(e["who"])
        elif e["t"] == "turn_start":
            assert e["who"] not in dead, f"{e['who']} ล้มแล้วยังได้เทิร์น"


def test_view_ไม่บอกท่าถัดไปของบอส():
    """🔒 หลุดออกไป = ผู้เล่นกันท่าได้เป๊ะ ความตื่นเต้นหาย"""
    st = _battle(boss_raid=True)
    b = st["extra"]["battle"]
    for u in b["units"].values():
        if u["side"] == "monster":
            u.update(charging=True, since_big=99)
    blob = json.dumps(engine.view(st, 1), ensure_ascii=False)
    for leak in ("charging", "since_big"):
        assert leak not in blob, f"view() ปล่อย {leak} หลุดขึ้นเบราว์เซอร์"


def test_สมรภูมิจริงเกิดมอนตามกติกาจำนวน():
    """เชื่อมกันจริงไหม — spawn_group ต้องถูกเรียกพร้อมรอบ"""
    st = _battle()
    mons = [u for u in st["extra"]["battle"]["units"].values()
            if u["side"] == "monster"]
    want = journey.monster_count(1, 2)
    assert len(mons) == want, f"รอบ 1 ปาร์ตี้ 2 คน ควรเจอ {want} ตัว ได้ {len(mons)}"


def test_แรงค์บอสสุ่มตามเลเวลปาร์ตี้():
    """⭐ วัดจริง 2026-09-04: บังคับ Mini-Boss ทุกเลเวล ทำให้เลเวล 60 ชนะ 30/30

    ตารางน้ำหนักของเกมหลักให้เลเวลสูงมีสิทธิ์เจอแรงค์สูงกว่ามาก
    """
    order = list(monsters.adventure_core.MONSTER_RANKS)
    low = [monsters.boss_rank_for(1, random.Random(s)) for s in range(60)]
    high = [monsters.boss_rank_for(100, random.Random(s)) for s in range(60)]
    avg = lambda xs: sum(order.index(x) for x in xs) / len(xs)
    assert avg(high) > avg(low), \
        f"เลเวล 100 เจอแรงค์เฉลี่ย {avg(high):.1f} ไม่สูงกว่าเลเวล 1 ({avg(low):.1f})"


def test_แรงค์บอสเป็นแรงค์บอสจริงเสมอ():
    for lv in (1, 10, 50, 100):
        for s in range(20):
            assert monsters.boss_rank_for(lv, random.Random(s)) in monsters.BOSS_RANKS
