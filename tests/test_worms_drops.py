"""📦 ครบรอบแล้วของลงสนาม · เรือเหาะข้ามเกาะ · กล้องพาไปดูของทีละชิ้น

เจ้าของเกมทัก: แผนที่เป็นเกาะลอย เดินข้ามเกาะแทบเป็นไปไม่ได้
เกมเลยกลายเป็นยืนยิงข้ามน้ำอย่างเดียว จึงต้องมีของลงสนามทุกครบรอบ
และกล้องต้องพาไปดูของที่เพิ่งลงทีละชิ้นก่อนเริ่มตาคนแรก
"""
import pathlib
import time

import pytest

import bot.models.player_model as pm
from bot.pvp import match, physics as P, terrain as T
from license_server import web_db
from tests import conftest

UID = 6404
WEB = pathlib.Path("license_server/web_static")
PLAY = conftest.play_js_source()
WORMS = (WEB / "worms.js").read_text(encoding="utf-8")


@pytest.fixture
def world(tmp_path, monkeypatch):
    monkeypatch.setattr(pm, "DB_NAME", str(tmp_path / "g.db"))
    monkeypatch.setattr(web_db, "DB_PATH", tmp_path / "w.db")
    pm.init_db()
    pm.get_player(UID)
    return None


def _fn(head):
    body = PLAY[body_at(head):]
    return body[:body.index(chr(10) + "}")]


def body_at(head):
    assert head in PLAY, f"หาไม่เจอใน play.js: {head}"
    return PLAY.index(head)


def _round_up(seed=7, rounds=6):
    """เล่นให้ครบหลายรอบแล้วคืนสถานะสุดท้าย"""
    match.new_practice(UID, {"race": "Human", "cls": "Warrior",
                             "armor": "None", "weapon": ""}, seed=seed)
    for _ in range(rounds * 2):
        st = match.load(UID)
        st["turn_started"] = 0
        match.save(UID, st)
        good, r = match.end_turn(UID, auto=True)
        if not good or r["over"]:
            break
    return match.load(UID)


# ── ของลงสนามทุกครบรอบ ──

def test_new_things_drop_in_as_rounds_go_by(world):
    match.new_practice(UID, {"race": "Human", "cls": "Warrior",
                             "armor": "None", "weapon": ""}, seed=7)
    before = len(match.load(UID)["props"])
    st = _round_up(rounds=6)
    assert st["round"] > 1, "เล่นไม่ครบรอบ — เทสตั้งฉากผิด"
    assert len(st["props"]) > before, f"ผ่านไป {st['round']} รอบแล้วของบนแผนที่ยังเท่าเดิม"
    assert any("ของใหม่" in line for line in st["log"]), "ไม่ได้บอกผู้เล่นว่ามีของลงสนาม"


def test_the_server_tells_the_page_what_dropped(world):
    """เว็บจะพากล้องไปดูของใหม่ได้ ก็ต่อเมื่อรู้ว่าอะไรลงตรงไหน"""
    # ⚠️ ต้องดูทุกรอบระหว่างเล่น ไม่ใช่ดูแค่สถานะสุดท้าย — รายการถูกล้างทุกต้นรอบ
    #    รอบสุดท้ายอาจไม่มีของลงพอดี (เคยพังตอนบอทเล็งเก่งขึ้นแล้วจบเกมเร็วกว่าเดิม)
    for seed in (11, 7, 3, 19):
        match.new_practice(UID, {"race": "Human", "cls": "Warrior",
                                 "armor": "None", "weapon": ""}, seed=seed)
        for _ in range(10):
            st = match.load(UID)
            st["turn_started"] = 0
            match.save(UID, st)
            good, r = match.end_turn(UID, auto=True)
            if not good or r["over"]:
                break
            view = match.view(UID)
            assert "drops" in view, "ไม่ได้บอกเว็บว่าอะไรลงสนามบ้าง"
            if view["drops"]:
                for x in view["drops"]:
                    assert {"kind", "x", "y"} <= set(x), f"ของที่ลงบอกไม่ครบ: {x}"
                return
    pytest.fail("เล่นครบรอบหลายเมล็ดแล้วไม่มีของลงสนามเลยสักชิ้น")


def test_a_drop_list_shows_a_trap(world):
    """กติกาเหล็กกลับด้าน (08-27) — กับดักที่เพิ่งลงต้องบอกตำแหน่งด้วย

    ต้องเก็บของที่ลงระหว่างเล่นทุกครั้ง ไม่ใช่ดูแค่สถานะสุดท้าย
    เพราะรายการถูกล้างทุกต้นรอบ รอบสุดท้ายอาจไม่มีของลงพอดี
    """
    found = traps = 0
    for seed in range(1, 12):
        match.new_practice(UID, {"race": "Human", "cls": "Warrior",
                                 "armor": "None", "weapon": ""}, seed=seed)
        for _ in range(10):
            st = match.load(UID)
            st["turn_started"] = 0
            match.save(UID, st)
            good, r = match.end_turn(UID, auto=True)
            if not good or r["over"]:
                break
            drops = r.get("drops") or []
            found += len(drops)
            for x in drops:
                assert "x" in x and "y" in x, "ของที่ลงไม่บอกตำแหน่ง วาดไม่ได้"
                traps += x["kind"] == "trap"
    assert found >= 4, f"เจอของที่ลงแค่ {found} ชิ้น น้อยเกินกว่าจะเชื่อผล"
    assert traps, "ลงของมาตั้งเยอะแต่ไม่มีกับดักสักอันในรายการ"

def test_the_field_does_not_fill_up_forever(world):
    st = _round_up(rounds=14)
    assert match.DROP_MAX <= 20, f"เพดาน {match.DROP_MAX} ไม่ได้จำกัดอะไรเลย"
    assert len(st["props"]) <= match.DROP_MAX, \
        f"ของล้นสนาม {len(st['props'])} ชิ้น (เพดาน {match.DROP_MAX})"


def test_things_never_land_close_enough_to_hide_each_other(world):
    """ของสองชิ้นวางชิดกันเกินไป = ชิ้นหลังวาดทับชิ้นแรกจนหายไปเลย

    วัดแล้วตอนเพดานระยะห่างเป็น 10 px: เรือเหาะโดนหีบทับ 31 ครั้งจาก 223 รอบ
    ผู้เล่นเห็นเป็น "บางทีประตูวาปก็ไม่โชว์" แล้วข้ามเกาะไม่ได้ทั้งรอบ
    รูปของกว้างสุด 11 px จึงต้องห่างกันอย่างน้อยเท่านั้น
    """
    WIDE, TALL = 11, 16               # ขนาดรูปของที่กว้าง/สูงที่สุด (เรือเหาะ)
    # เมล็ดพวกนี้คัดมาจากการกวาด 20 เมล็ด — เป็นเมล็ดที่วางทับกันจริงตอนเพดานเป็น 10 px
    for seed in (14, 16, 17, 3):
        st = _round_up(seed=seed, rounds=8)
        props = st["props"]
        for i, a in enumerate(props):
            for b in props[i + 1:]:
                assert not (abs(a["x"] - b["x"]) < WIDE and abs(a["y"] - b["y"]) < TALL),                     (f"เมล็ด {seed}: {a['kind']} ที่ ({a['x']},{a['y']}) กับ "
                     f"{b['kind']} ที่ ({b['x']},{b['y']}) วางทับกันจนบังกันเอง")


# ── เรือเหาะข้ามเกาะ ──

def test_a_ferry_shows_up_to_cross_islands(world):
    assert "ferry" in T.PROPS, "ไม่มีเรือเหาะในรายการของบนแผนที่"
    seen = 0
    for seed in range(1, 9):
        st = _round_up(seed, rounds=5)
        seen += sum(1 for p in st["props"] if p["kind"] == "ferry")
    assert seen >= 4, f"เล่น 8 เมล็ดแล้วเจอเรือเหาะแค่ {seen} ลำ"


def test_the_ferry_never_drops_you_somewhere_you_could_already_walk(world):
    """วาร์ปไปจุดที่เดินถึงอยู่แล้วไม่ได้แก้ปัญหาข้ามเกาะ — ตรวจทุกลำที่เจอ"""
    checked = 0
    for seed in range(1, 16):
        st = _round_up(seed, rounds=5)
        g = T.decode(st["terrain"])
        for fer in [p for p in st["props"] if p["kind"] == "ferry"]:
            me = st["fighters"][0]
            me["dead"] = False
            me["x"], me["y"] = fer["x"], fer["y"]
            reach = P.walk_group(g, (fer["x"], fer["y"]))
            got = match._ride_ferry(st, g, me)
            if not got:
                continue
            checked += 1
            assert (me["x"], me["y"]) not in reach, \
                f"เมล็ด {seed}: เรือเหาะพาไปจุดที่เดินถึงอยู่แล้ว"
            assert P.standable(g, me["x"], me["y"]), "ลงเรือแล้วลอยอยู่กลางอากาศ"
    assert checked >= 5, f"ตรวจได้แค่ {checked} ลำ น้อยเกินกว่าจะเชื่อผล"


def test_the_ferry_is_used_up(world):
    for seed in range(1, 16):
        st = _round_up(seed, rounds=5)
        fer = next((p for p in st["props"] if p["kind"] == "ferry"), None)
        if not fer:
            continue
        g = T.decode(st["terrain"])
        me = st["fighters"][0]
        me["dead"] = False
        me["x"], me["y"] = fer["x"], fer["y"]
        if not match._ride_ferry(st, g, me):
            continue
        assert not any(p["kind"] == "ferry" and p["x"] == fer["x"] for p in st["props"]), \
            "ขึ้นแล้วเรือยังอยู่ที่เดิม — ใช้ซ้ำได้ไม่จำกัด"
        assert any("เรือเหาะ" in line for line in st["log"])
        return
    pytest.skip("ไม่เจอเรือเหาะในเมล็ดที่ลอง")


def test_walking_onto_a_ferry_through_the_real_move_call(world):
    """เรียก _ride_ferry ตรง ๆ ไม่พอ — ต้องพิสูจน์ว่า move() เรียกให้จริง"""
    tried = 0
    for seed in range(1, 26):
        st = _round_up(seed, rounds=5)
        fer = next((p for p in st["props"] if p["kind"] == "ferry"), None)
        if not fer:
            continue
        tried += 1
        st["turn"], st["turn_started"] = 0, time.time()
        st["moves"], st["over"] = match.MOVE_BUDGET, False
        st["fighters"][0].update(x=fer["x"], y=fer["y"], dead=False)
        match.save(UID, st)
        good, r = match.move(UID, "walk", 1, 1)
        if not good:
            continue
        assert r.get("ferry"),             "ยืนทับเรือแล้วเดินหนึ่งก้าว แต่ move() ไม่ได้พาขึ้นเรือให้เลย"
        assert r["ferry"].get("x") is not None, "ขึ้นเรือแล้วไม่บอกจุดลง"
        assert r["ferry"].get("from"), "ไม่บอกว่าขึ้นจากตรงไหน เว็บเล่นภาพไม่ได้"
        return
    pytest.fail(f"ลอง {tried} เมล็ดที่มีเรือแล้วไม่มีสักครั้งที่เดินขึ้นเรือได้")


# ── กล้องพาไปดูของที่เพิ่งลง ──

def test_the_tour_is_started_when_drops_arrive():
    body = PLAY[body_at("function wmApply("):body_at("function wmMe(")]
    assert "d.drops" in body, "ได้รายการของใหม่มาแล้วไม่ทำอะไรเลย"
    assert "d.round !== WM_TOUR_ROUND" in body, "พาไปดูของรอบเดิมซ้ำทุกครั้งที่สถานะอัปเดต"
    assert "wmStartTour(d.drops)" in body, "ไม่ได้เริ่มทัวร์"


def test_you_cannot_act_during_the_tour():
    for fn, why in [("function wmBusyFx(", "แผงสรุปผล"), ("function wmWaiting(", "ปุ่มบังคับ")]:
        assert "wmStepsBusy()" in _fn(fn), f"{why} ไม่ได้นับช่วงที่มีขั้นตอนค้างอยู่"


def test_the_spawn_effect_is_slow_enough_to_follow():
    """เจ้าของเกมสั่ง: รอจอเลื่อนไปถึงของก่อน แล้วค้างสัก 3 วินาที ค่อยไปชิ้นถัดไป"""
    import re

    m = re.search(r"WM_TOUR_HOLD = (\d+)", PLAY)
    assert m, "ไม่ได้ตั้งว่าค้างที่ของแต่ละชิ้นกี่เฟรม"
    assert int(m.group(1)) >= 170, \
        f"ค้างแค่ {m.group(1)} เฟรม (~{int(m.group(1)) / 60:.1f} วิ) ไม่ถึง 3 วินาที"
    assert "WM_CAM.arrived()" in _fn("function wmStartTour("), \
        "เริ่มนับเวลาตั้งแต่ยังเลื่อนไม่ถึง"


def test_the_drop_has_a_spawn_effect():
    body = _fn("function wmStartTour(")
    assert "WM_POPS.push" in body, "ไม่มีป้ายบอกว่าของอะไรลงมา"
    assert "WM_SPAWNS.push" in body, "ไม่มีเอฟเฟกต์ตอนของลงจอ"
    assert "wmDust(" in _fn("function wmDrawSpawns("), "ของแตะพื้นแล้วไม่มีฝุ่น"


def test_the_page_draws_the_ferry():
    assert "p.kind === 'ferry'" in WORMS, "เรือเหาะไม่ถูกวาดบนแผนที่"


def test_riding_the_ferry_is_shown():
    assert "d.ferry" in PLAY, "ขึ้นเรือแล้วเว็บไม่รู้เรื่อง"
    body = PLAY[body_at("function wmRideFerry("):]
    body = body[:body.index(chr(10) + "}" + chr(10))]
    assert "wmFocus({ x: ferry.x, y: ferry.y }, true)" in body, "ข้ามเกาะแล้วกล้องไม่ตามไป"
    assert body.count("wmStep(") >= 3, "วาร์ปยังเกิดรวดเดียว ไม่ได้แบ่งเป็นจังหวะ"

def test_a_dropped_thing_stays_invisible_until_the_camera_gets_there():
    """เจ้าของเกมทัก: ของโผล่ขึ้นมาก่อนที่กล้องจะโฟกัสไปพร้อมเอฟเฟกต์สปอนซ้ำ

    ต้นเหตุ: wmApply ใส่ props ทั้งชุดลงแผนที่ทันทีที่คำตอบมาถึง
    ทัวร์กล้องเลยไปเล่นเอฟเฟกต์ "ของตกลงมา" ทับของที่เห็นอยู่แล้ว
    """
    import json
    import shutil
    import subprocess

    if not shutil.which("node"):
        pytest.skip("เครื่องนี้ไม่มี node")
    r = subprocess.run(["node", "tests/drop_reveal.js"],
                       capture_output=True, text=True, encoding="utf-8")
    assert r.returncode == 0, r.stderr
    out = json.loads(r.stdout.strip().splitlines()[-1])

    assert out["beforeTour"] == ["chest"],         f"ทัวร์ยังไม่เริ่มแต่ของใหม่โผล่แล้ว: {out['beforeTour']}"
    # ของโผล่ทีละชิ้นตามลำดับที่กล้องไปถึง ไม่ใช่โผล่พร้อมกันหมด
    assert out["afterEachStep"][-1] == "chest,ferry,chest,trap",         f"ทัวร์จบแล้วของไม่ครบ: {out['afterEachStep'][-1]}"
    assert out["afterEachStep"][0] == "chest", "ขั้นเลื่อนกล้องไม่ควรทำให้ของโผล่"
    assert out["stillHidden"] == 0, "ทัวร์จบแล้วยังมีของค้างไม่ถูกปล่อย"


def test_clearing_the_queue_never_leaves_a_thing_invisible_forever():
    """คิวถูกล้างกลางทัวร์ (เปิดหน้าใหม่/แมตช์ใหม่) = ไม่มีใครมาปล่อยของที่ซ่อนไว้"""
    body = PLAY[PLAY.index("function wmApply("):]
    body = body[:body.index(chr(10) + "}" + chr(10))]
    assert body.index("WM_TOUR_HIDE = []") < body.index("wmStartTour("),         "ล้างรายการของที่ซ่อนไว้หลังเริ่มทัวร์ใหม่ = ล้างของรอบใหม่ทิ้ง"
    assert "wmStepsClear();" in body and         body.index("wmStepsClear();") < body.index("WM_TOUR_HIDE = []"),         "ล้างคิวแล้วไม่ได้ล้างรายการของที่ซ่อนไว้ตาม — ของจะหายถาวร"
