"""🎮 การบังคับในสนามรบ — จบเทิร์นเอง + เล็งด้วยการกดค้าง

เจ้าของเกมสั่งไว้สามข้อ:
  1. จบเทิร์นแล้วตัวห้ามเด้งหรือจมพื้น
  2. แรงเดินหมด = จบเทิร์นให้เลย ไม่ต้องมากดเอง
  3. เลือกสกิล → กดค้างบนแผนที่เพื่อชาร์จ → ปล่อยยิง
     ไม่มีปุ่มปรับองศา ความแรง หรือปุ่มยิงมารกจอ
"""
import pathlib
import re

import pytest

import bot.models.player_model as pm
from bot.pvp import match, physics as P, terrain as T
from license_server import web_db

UID = 6402
WEB = pathlib.Path("license_server/web_static")
PLAY = (WEB / "play.js").read_text(encoding="utf-8")
WORMS = (WEB / "worms.js").read_text(encoding="utf-8")
HTML = (WEB / "play.html").read_text(encoding="utf-8")


@pytest.fixture
def world(tmp_path, monkeypatch):
    monkeypatch.setattr(pm, "DB_NAME", str(tmp_path / "g.db"))
    monkeypatch.setattr(web_db, "DB_PATH", tmp_path / "w.db")
    pm.init_db()
    pm.get_player(UID)
    return None


def fresh(seed=7):
    match.new_practice(UID, {"race": "Human", "cls": "Warrior",
                             "armor": "None", "weapon": ""}, seed=seed)
    return match.load(UID)


# ── 1. ห้ามเด้ง ห้ามจมพื้น ──

def test_nobody_ends_a_turn_stuck_inside_the_ground(world):
    """จบเทิร์นแล้วทุกคนต้องยังยืนบนพื้นได้จริง ไม่ใช่จมลงไป"""
    sunk = []
    for seed in range(1, 13):
        fresh(seed)
        for _ in range(4):
            st = match.load(UID)
            st["turn_started"] = 0
            match.save(UID, st)
            good, r = match.end_turn(UID, auto=True)
            if not good or r["over"]:
                break
            g = T.decode(r["terrain"])
            sunk += [f"เมล็ด {seed}: {f['name']} ({f['x']},{f['y']})"
                     for f in r["fighters"]
                     if not f["dead"] and not P.standable(g, f["x"], f["y"])]
    assert not sunk, "จบเทิร์นแล้วจมพื้น: " + " · ".join(sunk[:4])


def test_the_replay_follows_a_fighter_by_slot_not_by_object():
    """สถานะใหม่มาแทนทั้งก้อน ถ้าจำเป็น object ไว้ ภาพที่เล่นค้างจะไปขยับของที่ไม่มีใครวาด"""
    assert "WM_ST.fighters[WM_ANIM.fi]" in PLAY, "แอนิเมชันยังจำ object นักสู้ไว้แทนลำดับ"
    assert "WM_ANIM.f." not in PLAY, "ยังมีที่เขียนทับ object เก่าอยู่"


def test_a_new_state_throws_away_the_replay_still_playing():
    body = PLAY[PLAY.index("function wmApply("):PLAY.index("function wmMe(")]
    assert "WM_ANIM = null" in body and "WM_QUEUE = []" in body, \
        "สถานะใหม่มาแล้วไม่ล้างภาพเก่า — ตัวจะถูกลากตามเส้นทางของสถานะที่ตายไปแล้ว"


def test_the_bot_is_rewound_before_its_walk_is_replayed():
    """ไม่ย้อน = บอทโผล่ที่หมายทันที แล้วเด้งกลับมาเดินซ้ำให้ดู"""
    body = PLAY[PLAY.index("function wmQueueBot("):]
    body = body[:body.index("\n}")]
    assert "moves[0].path[0][0]" in body, "ไม่ได้ย้อนบอทกลับจุดเริ่มก่อนเล่นภาพ"
    assert "wmQueueBot(d)" in PLAY.split("function wmQueueBot(")[0], \
        "มีฟังก์ชันแต่ไม่มีใครเรียก"


def test_both_paths_into_the_bot_turn_use_the_same_replay():
    """เดิมจบเทิร์นย้อนจุดเริ่ม แต่ยิงเสร็จไม่ย้อน — ทางเดียวเด้ง อีกทางไม่เด้ง"""
    assert PLAY.count("wmQueueBot(d)") >= 3, "ยังมีทางที่ต่อคิวบอทเองแยกจากทางอื่น"


# ── 2. แรงเดินหมดแล้วจบเทิร์นเอง ──

def test_walking_until_the_energy_runs_out_ends_the_turn(world):
    fresh()
    for _ in range(8):
        good, r = match.move(UID, "walk", 1, 40)
        if not good:
            pytest.fail("เดินไม่ได้: " + r["error"])
        if r.get("auto_ended"):
            assert r["moves"] == match.MOVE_BUDGET, "จบเทิร์นแล้วแต่แรงไม่รีเซ็ต"
            return
        assert r["moves"] > 0, "แรงหมดแล้วแต่ยังไม่จบเทิร์นให้"
    pytest.fail("เดินจนสุดแรงแล้วก็ยังไม่จบเทิร์นเอง")


def test_a_turn_with_energy_left_does_not_end_itself(world):
    fresh()
    good, r = match.move(UID, "walk", 1, 6)
    assert good and not r.get("auto_ended"), "เดินนิดเดียวก็จบเทิร์นให้ซะแล้ว"


def test_the_auto_ended_turn_still_reports_the_walk_that_caused_it(world):
    """ไม่งั้นเว็บได้แต่ผลลัพธ์ ไม่รู้ว่าเดินไปทางไหน เลยเล่นภาพไม่ได้"""
    fresh()
    r = None
    for _ in range(8):
        good, r = match.move(UID, "walk", 1, 40)
        if good and r.get("auto_ended"):
            break
    assert r.get("auto_ended") and r.get("move", {}).get("path"), \
        "จบเทิร์นเองแล้วแต่ไม่ส่งเส้นทางเดินกลับมา"


def test_the_page_replays_that_walk_for_the_slot_that_moved():
    """เซิร์ฟเวอร์สลับตาไปแล้ว ถ้าใช้ตาปัจจุบัน = เอาบอทไปเดินตามรอยเรา"""
    body = PLAY[PLAY.index("async function wmDo("):PLAY.index("async function wmEndTurn(")]
    assert "const mine = WM_ST.turn;" in body, "ไม่ได้จำว่าตาใครตอนสั่งเดิน"
    assert "WM_ANIM = { fi: mine" in body, "เล่นภาพเดินให้ผิดคน"
    assert "d.auto_ended" in body, "จบเทิร์นเองแล้วเว็บไม่เล่นภาพตาบอทต่อ"


# ── 3. เล็งด้วยการกดค้าง ──

def test_holding_longer_charges_stronger():
    m = re.search(r"WM_AIM\.pow = Math\.min\(100, 10 \+ .*?WM_CHARGE_MS", PLAY)
    assert m, "ไม่มีการชาร์จตามเวลาที่กดค้าง"
    assert re.search(r"WM_CHARGE_MS = (\d+)", PLAY), "ไม่ได้ตั้งว่ากี่มิลลิวินาทีถึงเต็ม"


def test_the_charge_bar_shows_on_screen():
    body = PLAY[PLAY.index("function wmDrawAim("):]
    body = body[:body.index("\n}")]
    assert "bw * pw / 100" in body, "ชาร์จแล้วไม่มีแถบให้เห็นบนจอ"
    assert "setLineDash" in body, "ไม่มีเส้นเล็งบอกทิศ"


def test_moving_up_and_down_while_holding_changes_the_angle():
    assert "WM_AIM.y0 - at(e).y" in PLAY, "เลื่อนขึ้นลงแล้วองศาไม่เปลี่ยน"


def test_releasing_is_what_fires():
    body = PLAY[PLAY.index("const up = () => {"):]
    body = body[:body.index("\n  };")]
    assert "wmAttack(WM_SKILL" in body, "ปล่อยแล้วไม่ยิง"
    assert "WM_AIM = null" in body and "WM_CAM.locked = false" in body, \
        "ปล่อยแล้วไม่เลิกเล็ง — กล้องจะลากไม่ได้ตลอดกาล"


def test_the_charged_power_is_what_gets_sent(world):
    """ชาร์จแล้วต้องยิงไกลกว่าจริง ไม่ใช่แค่แถบสวย"""
    def shoot(power):
        fresh()                                  # พื้นราบล้วน จะได้วัดวิถีล้วน ๆ ไม่มีเนินมาบัง
        g = [[T.AIR] * T.W for _ in range(T.H)]
        for x in range(T.W):
            for y in range(200, T.H - T.WATER):
                g[y][x] = T.ROCK
        st = match.load(UID)
        st["terrain"], st["props"] = T.encode(g), []
        st["fighters"][0].update(x=120, y=200, face=1,
                                 look={**st["fighters"][0]["look"], "cls": "Mage"})
        st["fighters"][1].update(x=600, y=200)
        match.save(UID, st)
        a = match.attack(UID, "fire", angle=45, power=power)[1]["attack"]
        return abs(a["path"][-1][0] - a["path"][0][0])

    far, near = shoot(100), shoot(20)
    assert far > near, f"ชาร์จเต็มไปได้ {far} px แต่ชาร์จนิดเดียวไปได้ {near} px"


def test_dragging_the_map_while_aiming_does_not_move_the_camera():
    body = WORMS[WORMS.index("  attach(onChange) {"):]
    body = body[:body.index("\n  }")]
    assert body.count("this.locked") >= 2, "ตอนเล็งยังลากกล้องได้ — องศาจะเพี้ยนไปด้วย"


def test_only_self_buffs_skip_the_aiming_step():
    body = PLAY[PLAY.index("function wmPickSkill("):]
    body = body[:body.index("\n}")]
    assert "s.kind === 'self'" in body, "ยังใช้ธง aim เดิมที่ปล่อยให้ท่าประชิดยิงทันทีโดยไม่เลือกทิศ"


def test_the_page_explains_how_to_aim():
    body = PLAY[PLAY.index("function wmShowAim("):]
    body = body[:body.index("\n}")]
    assert "กดค้าง" in body and "ปล่อย" in body, "ไม่ได้บอกผู้เล่นว่าต้องกดค้างแล้วปล่อย"


# ── 4. เดินเตาะแตะ ไม่ใช่วืดไปทีเดียว ──

def _num(name):
    m = re.search(rf"{name} = (\d+)", PLAY)
    assert m, f"หา {name} ไม่เจอ"
    return int(m.group(1))


def test_one_press_is_a_small_shuffle_not_a_sprint():
    """กดทีเดียวไม่ควรกินแรงทั้งเทิร์น — เดิมกดสองทีก็หมดแรงแล้ว"""
    steps = _num("WM_WALK_STEPS")
    presses = match.MOVE_BUDGET / steps
    assert presses >= 8, (f"กดทีเดียวเดิน {steps} ก้าว = ทั้งเทิร์นกดได้แค่ {presses:.0f} ที "
                          "แรงหมดเร็วเกินจะขยับให้ตรงจุด")


def test_a_short_walk_is_played_out_step_by_step():
    """ก้าวสั้นต้องค้างจุดละหลายเฟรม ไม่งั้นเดิน 6 ก้าวจบใน 0.1 วิ เห็นเป็นวาร์ป"""
    m = re.search(r"const hold = WM_ANIM\.path\.length <= \d+ \? (\d+) : (\d+);", PLAY)
    assert m, "ไม่ได้หน่วงการเล่นภาพเดินเลย"
    assert int(m.group(1)) > 1, "ก้าวสั้นยังเล่นรวดเดียว"
    assert int(m.group(2)) == 1, "ท่อนยาวก็หน่วงด้วย — ตาบอทจะนานเป็นชาติ"
