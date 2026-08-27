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
from bot.pvp import match, physics as P, terrain as T, weapons as W
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
    for i in range(20):
        good, r = match.move(UID, "walk", 1 if i % 2 else -1, 40)   # กลับไปกลับมา
        if not good:                                               # เดินทางเดียวชนขอบเหว
            pytest.fail("เดินไม่ได้: " + r["error"])               # แล้วแรงจะไม่มีวันหมด
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
    for i in range(20):
        good, r = match.move(UID, "walk", 1 if i % 2 else -1, 40)
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
    m = re.search(r"const hold = WM_ANIM\.path\.length <= \d+ \? (\d+) : "
                 r"WM_ANIM\.path\.length <= \d+ \? (\d+) : (\d+);", PLAY)
    assert m, "ไม่ได้หน่วงการเล่นภาพเดินเลย"
    short, mid, long = (int(g) for g in m.groups())
    assert short > 1, "ก้าวสั้นยังเล่นรวดเดียว"
    assert mid > 1, "ท่อนกลาง (การกระเด็น) เล่นรวดเดียว ดูไม่ทัน"
    assert long == 1, "ท่อนยาวก็หน่วงด้วย — ตาบอทจะนานเป็นชาติ"


# ── 5. เดินแล้วขาต้องขยับ พื้นต้องไม่ลื่น ──

def test_a_walking_fighter_uses_a_walking_pose():
    """ยืนท่าเดิมแล้วเลื่อนตัวไป = เห็นเป็นลื่นไถลไปกับพื้น"""
    body = PLAY[PLAY.index("function wmDrawFighter("):]
    body = body[:body.index(chr(10) + "}")]
    assert "'run1'" in body and "'run2'" in body, "เดินแล้วยังใช้ท่ายืนเฉย ๆ"
    assert "beat % 2" in body, "สลับขาไม่ตามก้าวจริง"
    # ต้องนับก้าวได้ทั้งตอนเล่นเส้นทางจากเซิร์ฟเวอร์ และตอนจอเดินเอง
    assert "Math.floor(anim.i)" in body, "ไม่ได้นับก้าวจากเส้นทางที่เซิร์ฟเวอร์ส่งมา"
    assert "WM_PRED.pending + WM_PRED.beat" in body, "เดินเองฝั่งจอแล้วขาไม่ขยับ"


def test_the_camera_only_follows_near_the_edge():
    """ตามทุกเฟรม = ตัวค้างกลางจอ พื้นไหลข้างใต้ เห็นเป็นพื้นลื่น"""
    body = PLAY[PLAY.index("function wmFocus("):]
    body = body[:body.index(chr(10) + "}")]
    assert "force || x < mx" in body, "กล้องยังตามติดทุกเฟรม ไม่ได้เช็คว่าใกล้ขอบจอหรือยัง"
    assert "WM_CAM.center" in body, "ไม่มีทางเลื่อนกล้องกลับมาที่ตัวเลย"


def test_the_camera_follows_whoever_is_moving():
    """ตอนบอทเดิน กล้องเกาะตัวเราอยู่ก็ไม่เห็นว่าบอททำอะไร"""
    assert "wmFocus(af || { x: x, y: y })" in PLAY, "กล้องไม่ตามคนที่กำลังขยับ"


# ── 6. ฟันได้รอบตัว 360° ──

def test_melee_can_be_aimed_in_any_direction(world):
    """เจ้าของเกมทัก: ตีปกติใช้ได้แค่ซ้ายกับขวา"""
    fresh()
    st = match.load(UID)
    me, foe = st["fighters"]
    me.update(x=300, y=180, face=1)
    foe.update(x=300, y=180 - 20)              # ยืนอยู่ "เหนือหัว" เรา
    match.save(UID, st)
    good, r = match.attack(UID, "basic", angle=88)
    assert good, r.get("error")
    assert any(h["name"] != "คุณ" for h in r["attack"]["hits"]), "ฟันขึ้นข้างบนแล้วไม่โดน"


def test_melee_still_misses_what_is_behind_you(world):
    """รอบตัว ไม่ได้แปลว่าฟันทีเดียวโดนทุกคนรอบทิศ"""
    fresh()
    st = match.load(UID)
    me, foe = st["fighters"]
    me.update(x=300, y=180, face=1)
    foe.update(x=300, y=180 + 20)              # อยู่ใต้เท้า แต่เราฟันขึ้น
    match.save(UID, st)
    r = match.attack(UID, "basic", angle=88)[1]
    assert not [h for h in r["attack"]["hits"] if h["name"] != "คุณ"],         "ฟันขึ้นข้างบนแล้วโดนคนที่อยู่ใต้เท้าด้วย"


def test_the_server_tells_the_page_which_way_the_swing_went(world):
    fresh()
    r = match.attack(UID, "basic", angle=30)[1]
    assert r["attack"].get("aim"), "ไม่ได้ส่งทิศที่ฟันกลับไปให้เว็บวาด"


def test_a_plain_tap_swings_straight_ahead(world):
    """ไม่เล็ง = ฟันตรงหน้า ไม่ใช่ฟันขึ้นฟ้า 45° แล้วพลาดคนที่ยืนข้าง ๆ"""
    fresh()
    r = match.attack(UID, "basic")[1]
    ax, ay = r["attack"]["aim"]
    assert abs(ay) < 0.01 and abs(ax) == 1, f"ค่าตั้งต้นฟันไปทาง {ax},{ay}"


def test_the_page_aims_melee_the_same_way_as_a_shot():
    assert "sp.kind === 'melee' ? 0 : 45" in PLAY, "ท่าประชิดไม่ได้เริ่มที่ฟันตรงหน้า"
    body = PLAY[PLAY.index("function wmSwing("):]
    body = body[:body.index(chr(10) + "}")]
    assert "a.aim" in body, "วงเหวี่ยงยังหันตามซ้าย/ขวาแทนทิศที่เล็ง"


# ── 7. บัฟไม่ใช่การโจมตี ──

BUFFS_ONLY = ["evade", "heal", "aura", "feather_boots", "bark_cloak", "ice_scale"]


@pytest.mark.parametrize("key", BUFFS_ONLY)
def test_a_buff_hurts_nobody_and_breaks_nothing(world, key):
    """เจ้าของเกมสั่ง: ของป้องกัน/บัฟ ต้องไม่สร้างความเสียหาย

    เรียก _use_skill ตรง ๆ เพราะ attack() จบเทิร์นให้แล้วบอทตีสวนทันที
    ภูมิประเทศที่พังจากบอทจะกลบผลของบัฟจนวัดไม่ได้
    """
    cls = {"evade": "Rogue", "heal": "Cleric", "aura": "Cleric"}.get(key, "Warrior")
    match.new_practice(UID, {"race": "Human", "cls": cls,
                             "armor": "None", "weapon": ""}, seed=7)
    st = match.load(UID)
    me, foe = st["fighters"]
    me["look"]["cls"] = cls
    foe.update(x=me["x"] + 12, y=me["y"])      # ยืนติดตัวเลย จะได้รู้ว่าโดนลูกหลงไหม
    hp, ground = foe["hp"], st["terrain"]
    grid = T.decode(st["terrain"])

    a = match._use_skill(st, grid, me, key, None, 70)
    assert not a.get("hits"), f"{key} ทำดาเมจใส่คนอื่น"
    assert not a.get("blast"), f"{key} เจาะพื้นเป็นหลุม"
    assert not a.get("path"), f"{key} ยิงอะไรออกไปด้วย"
    assert foe["hp"] == hp, f"{key} ทำให้คู่ต่อสู้เลือดลด"
    assert T.encode(grid) == ground, f"{key} ทำสิ่งแวดล้อมพัง"


@pytest.mark.parametrize("key", BUFFS_ONLY)
def test_a_buff_actually_does_its_own_thing(world, key):
    """ไม่ทำดาเมจ ก็ต้องไม่ใช่กดแล้วไม่เกิดอะไรเลย"""
    cls = {"evade": "Rogue", "heal": "Cleric", "aura": "Cleric"}.get(key, "Warrior")
    match.new_practice(UID, {"race": "Human", "cls": cls,
                             "armor": "None", "weapon": ""}, seed=7)
    st = match.load(UID)
    st["fighters"][0]["look"]["cls"] = cls
    st["fighters"][0]["hp"] = 40
    if key in W.ARTIFACTS:
        st["fighters"][0]["bag"] = {key: 1}
    match.save(UID, st)
    a = match.attack(UID, key)[1]["attack"]
    assert a.get("buff") or a.get("heal"), f"{key} กดแล้วไม่เกิดอะไรเลย"
    assert a.get("from"), f"{key} ไม่บอกตำแหน่งคนใช้ เว็บเล่นเอฟเฟกต์ไม่ได้"


def test_the_page_plays_a_buff_effect_not_an_attack_one():
    body = PLAY[PLAY.index("function wmShowHit("):]
    body = body[:body.index(chr(10) + "}")]
    assert "wmBuffFx(a)" in body, "บัฟไม่มีเอฟเฟกต์ของตัวเอง"
    at = body.index("wmBuffFx(a)")
    assert "return;" in body[at:at + 120], "เล่นเอฟเฟกต์บัฟแล้วยังไหลไปเล่นเอฟเฟกต์โจมตีต่อ"


def test_every_buff_in_the_game_has_its_own_look():
    look = PLAY[PLAY.index("const WM_BUFF_LOOK"):]
    look = look[:look.index("};")]
    for key in W.BUFFS:
        assert f"{key}:" in look, f"บัฟ {key} ไม่มีสีกับชื่อของตัวเองบนจอ"


def test_a_buff_draws_its_own_ring(world):
    """สีกับชื่ออย่างเดียวไม่พอ ต้องมีอะไรให้เห็นบนจอจริง ๆ ตอนกด"""
    body = PLAY[PLAY.index("function wmDrawFx("):]
    body = body[:body.index(chr(10) + "}")]
    assert "WM_AURAS.forEach" in body, "ไม่ได้วาดวงแหวนบัฟเลย"
    assert "ctx.arc(" in body[body.index("WM_AURAS.forEach"):][:400], "วนลูปแล้วแต่ไม่ได้วาดอะไร"
    assert "wmBuffFx" in PLAY and "WM_AURAS.push" in PLAY, "ไม่มีใครใส่วงแหวนเข้าคิว"


def test_buff_text_is_not_damage_coloured():
    assert "p.buff ? '#8ef0b0'" in PLAY, "ตัวหนังสือบัฟยังใช้สีแดงเหมือนตัวเลขดาเมจ"


# ── 8. กระสุนต้องออกจากมือคนยิง ──

def test_a_shot_starts_at_the_shooter_not_out_in_thin_air(world):
    """เจ้าของเกมทัก: ผลการยิงไม่ค่อยตรงจากจุดที่คนยิงอยู่

    เดิมเก็บจุดแรกหลังกระสุนบินไปแล้วหนึ่งก้าว ตอนชาร์จเต็มก้าวหนึ่งยาว 9 px
    บวกระยะแขนอีก 7 = เห็นกระสุนโผล่ห่างตัวไป 16 px เหมือนยิงจากที่ว่าง
    """
    import math

    worst = 0
    for power in (10, 40, 70, 100):
        for ang in (-40, 0, 45, 80):
            fresh()
            st = match.load(UID)
            st["fighters"][0]["look"]["cls"] = "Mage"
            match.save(UID, st)
            me = st["fighters"][0]
            a = match.attack(UID, "fire", angle=ang, power=power)[1]["attack"]
            x0, y0 = a["path"][0]
            worst = max(worst, math.hypot(x0 - me["x"], y0 - (me["y"] - T.CH_H // 2)))
    arm = T.CH_W // 2 + 3
    assert worst <= arm + 1.5, f"จุดแรกของวิถีห่างตัวถึง {worst:.1f} px (ระยะแขนคือ {arm})"


def test_a_laser_starts_at_the_shooter_too(world):
    import math

    fresh()
    st = match.load(UID)
    st["fighters"][0]["bag"] = {"divine_staff": 1}
    match.save(UID, st)
    me = st["fighters"][0]
    a = match.attack(UID, "divine_staff", angle=2, power=70)[1]["attack"]
    x0, y0 = a["path"][0]
    gap = math.hypot(x0 - me["x"], y0 - (me["y"] - T.CH_H // 2))
    assert gap == 0, f"ลำแสงเริ่มห่างตัว {gap:.1f} px — จุดแรกต้องเป็นอกคนยิงเป๊ะ"


def test_the_trail_the_page_draws_is_the_one_the_server_sent():
    """เว็บต้องวาดตามเส้นที่ได้มา ไม่ใช่คำนวณวิถีเอง กติกาอยู่ที่เซิร์ฟเวอร์"""
    assert "WM_SHOT = { path: a.path" in PLAY, "เว็บไม่ได้ใช้เส้นวิถีที่เซิร์ฟเวอร์ส่งมา"


# ── 9. ถึงตาใครก็เลื่อนกล้องไปหาคนนั้น ──

def test_the_camera_jumps_to_whoever_the_turn_belongs_to():
    body = PLAY[PLAY.index("function wmStartLoop("):]
    body = body[:body.index("/** วาดนักสู้")]
    assert "turnKey !== WM_TURN_SHOWN" in body, "เปลี่ยนตาแล้วกล้องไม่ตามไปหาคนที่ถึงตา"
    assert "wmFocus(wmMe(), true)" in body, "ตามแบบไม่บังคับ — ถ้าตัวอยู่กลางจอพอดีก็ไม่ขยับ"
    assert "!wmBusyFx() &&" in body, "ตัดกล้องทั้งที่ภาพเดินยังเล่นค้างอยู่"


def test_a_new_match_forgets_which_turn_was_focused():
    body = PLAY[PLAY.index("function wmApply("):PLAY.index("function wmMe(")]
    assert "WM_TURN_SHOWN = '';" in body, "เปิดสนามใหม่แล้วยังจำตาเก่า กล้องเลยไม่ยอมจัดให้"


# ── 10. จบเกมแล้วสรุปผล ──

def _finish(cls="Warrior"):
    """ตีจนจบเกมจริง ๆ แล้วคืนสถานะสุดท้าย

    ต้องลากคู่ต่อสู้กลับมาชิดทุกครั้ง เพราะตอนนี้ทุกหมัดผลักให้กระเด็น
    ปล่อยไว้เฉย ๆ หมัดที่สองก็ไปไม่ถึงแล้ว
    """
    fresh()
    for _ in range(60):
        st = match.load(UID)
        if st["over"]:
            return match.view(UID, st)
        me, foe = st["fighters"]
        # ยืนไกลกว่ารัศมีระเบิดของร่าง (36) แต่ยังอยู่ในระยะฟัน (52)
        # ไม่งั้นฆ่าบอทแล้วร่างมันระเบิดใส่เราตายตามไปด้วย = ไม่มีผู้รอด
        foe.update(x=me["x"] + 45, y=me["y"])
        match.save(UID, st)
        good, r = match.attack(UID, "basic", angle=0)
        if not good or r["over"]:
            return r
    raise AssertionError("ตี 60 ครั้งแล้วเกมยังไม่จบ")


def test_the_match_reports_a_scoreboard_when_it_ends(world):
    r = _finish()
    assert r["over"] and r["standings"], "จบเกมแล้วไม่มีตารางสรุป"
    assert len(r["standings"]) == len(r["fighters"])
    assert [x["rank"] for x in r["standings"]] == [1, 2], "อันดับไม่เรียง"


def test_the_scoreboard_counts_who_dealt_what(world):
    r = _finish()
    assert sum(x["dealt"] for x in r["standings"]) > 0, "ตีกันทั้งเกมแต่ดาเมจรวมเป็นศูนย์"
    for x in r["standings"]:
        assert x["dealt"] >= 0 and "kills" in x and "hp" in x


def test_the_survivor_ranks_first(world):
    r = _finish()
    top = r["standings"][0]
    assert not top["dead"], "คนที่ตกรอบได้อันดับหนึ่ง"
    assert top["name"] == r["winner"], "อันดับหนึ่งไม่ใช่ผู้ชนะ"


def test_damage_you_did_to_yourself_is_not_counted(world):
    """ระเบิดโดนตัวเองไม่ควรนับเป็นผลงาน"""
    fresh()
    st = match.load(UID)
    st["fighters"][0]["look"]["cls"] = "Mage"
    st["fighters"][1].update(x=st["fighters"][0]["x"] + 400)   # ยิงไปไม่ถึงแน่ ๆ
    match.save(UID, st)
    match.attack(UID, "fire", angle=80, power=12)              # ยิงขึ้นฟ้าตกใส่ตัวเอง
    me = match.load(UID)["fighters"][0]
    assert me["dealt"] == 0, f"ระเบิดใส่ตัวเองแล้วนับเป็นดาเมจ {me['dealt']}"


def test_the_page_shows_the_scoreboard_and_both_choices():
    body = PLAY[PLAY.index("function wmPaintOver("):]
    body = body[:body.index(chr(10) + "}")]
    rows = body[body.index("<table>"):body.index("</table>")]
    assert "rows.map(r" in rows, "ตารางอันดับว่างเปล่า ไม่ได้วนของจริงมาวาด"
    assert "d.standings" in body, "ไม่ได้ดึงตารางอันดับจากเซิร์ฟเวอร์"
    for col in ("r.rank", "r.name", "r.dealt", "r.kills", "r.hp"):
        assert col in rows, f"ตารางไม่มีช่อง {col}"
    assert "wmAgain" in body and "wmQuit" in body, "ไม่มีให้เลือกว่าจะเล่นต่อหรือจบ"
    assert "wmNewMatch(0)" in body, "ปุ่มเล่นอีกรอบไม่ได้เปิดสนามใหม่"
    assert 'wmOver' in HTML, "ไม่มีที่วางแผงสรุปในหน้าเว็บ"


def test_the_scoreboard_only_shows_when_the_match_is_over():
    body = PLAY[PLAY.index("function wmPaintOver("):]
    body = body[:body.index(chr(10) + "}")]
    assert "box.hidden = !idle && !d.over" in body, "แผงสรุปโผล่ตั้งแต่ยังเล่นอยู่"
    assert "wmPaintOver()" in PLAY.split("function wmPaintOver(")[0] or         PLAY.count("wmPaintOver()") >= 1, "เขียนแล้วไม่มีใครเรียก"


# ── 11. หน้าเริ่มเกม + ปุ่มจบเกมที่จบจริง ──

def test_quitting_really_clears_the_match(world):
    """กดจบเกมแล้วกลับเข้ามาต้องไม่เจอกระดานสรุปเดิมค้างอยู่"""
    fresh()
    assert match.view(UID)["active"], "เพิ่งเปิดสนามแต่ยังไม่ active"
    match.drop(UID)
    assert not match.view(UID)["active"], "ทิ้งแมตช์แล้วยังโผล่มาอีก"


def test_the_quit_action_goes_through_the_api(world, monkeypatch):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from license_server import web_api

    app = FastAPI()
    app.include_router(web_api.router)
    client = TestClient(app)
    monkeypatch.setattr(web_api, "require_player", lambda r: {"uid": UID})

    fresh()
    r = client.post("/api/web/pvp/worms/match", json={"action": "quit"})
    assert r.status_code == 200, r.text
    assert r.json()["active"] is False, "สั่งจบเกมแล้ว API ยังบอกว่ายังเล่นอยู่"


def test_the_page_asks_the_server_to_quit_not_just_walk_away():
    body = PLAY[PLAY.index("function wmPaintOver("):]
    body = body[:body.index(chr(10) + "}")]
    assert "action: 'quit'" in body, "ปุ่มจบเกมแค่เด้งออกเมนู ไม่ได้บอกเซิร์ฟเวอร์ให้จบ"


def test_there_is_a_start_screen_before_the_match():
    """เจ้าของเกมสั่ง: ต้องมีหน้าก่อนเริ่มเกมสำหรับกดเริ่ม"""
    body = PLAY[PLAY.index("function wmPaintOver("):]
    body = body[:body.index(chr(10) + "}")]
    assert "const idle = !d || !d.active;" in body, "ไม่ได้แยกสถานะ 'ยังไม่เริ่ม' ออกมา"
    assert "if (idle) {" in body, "แยกสถานะไว้แต่ไม่ได้ใช้ — หน้าเริ่มเกมไม่มีวันโผล่"
    start = body[body.index("if (idle) {"):body.index("return;", body.index("if (idle) {"))]
    assert "เริ่มเกม" in start and "wmStart" in start, "หน้าก่อนเริ่มไม่มีปุ่มเริ่มเกม"
    assert "wmNewMatch(0)" in start, "กดเริ่มเกมแล้วไม่ได้เปิดสนามใหม่"


def test_the_start_screen_is_painted_even_with_no_match():
    """wmPaintSkills ไปไม่ถึงตอนยังไม่มีแมตช์ ต้องวาดจาก wmApply โดยตรง"""
    body = PLAY[PLAY.index("function wmApply("):PLAY.index("function wmMe(")]
    at = body.index("wmPaintOver()")
    assert at < body.index("if (!d.active)"), "วาดแผงหลังจากออกจากฟังก์ชันไปแล้ว"


# ── 12. โฟกัสคนที่ถึงตาให้ได้จริง ──

def test_the_focus_key_includes_the_round(world):
    """ซ้อมกับบอท: จบเทิร์นแล้วบอทเดินจบในคำขอเดียว d.turn จึงกลับมาเป็น 0 เท่าเดิม
    เทียบแค่ turn กล้องเลยไม่มีวันขยับ"""
    fresh()
    before = match.view(UID)
    match.end_turn(UID)
    after = match.view(UID)
    assert after["turn"] == before["turn"], "สมมติฐานเปลี่ยน — ตากลับมาที่เดิมไม่ใช่แล้ว"
    assert after["round"] != before["round"], "รอบไม่เดิน แล้วจะใช้อะไรรู้ว่าเปลี่ยนตา"
    assert "WM_ST.round + ':' + WM_ST.turn" in PLAY, "กุญแจโฟกัสไม่ได้นับรอบด้วย"


# ── 13. สถิติต้องอ่านออก ──

def test_the_results_panel_is_not_crushed_by_the_stage_line_height():
    """.wm-stage ตั้ง line-height: 0 ไว้ให้ canvas — ตัวหนังสือในแผงเลยทับกันจนอ่านไม่ออก"""
    css = (WEB / "play.css").read_text(encoding="utf-8")
    block = css[css.index(".wm-over {"):css.index(".wm-over[hidden]")]
    assert "line-height" in block, "ไม่ได้คืนระยะบรรทัดให้แผงสรุป"


def test_the_table_shows_rank_and_damage_side_by_side():
    body = PLAY[PLAY.index("function wmPaintOver("):]
    body = body[:body.index(chr(10) + "}")]
    head = body[body.index("<tr><th>"):body.index("</tr>")]
    assert "อันดับ" in head and "ความเสียหาย" in head, "หัวตารางไม่ได้บอกว่าคอลัมน์ไหนคืออะไร"
    rows = body[body.index("${rows.map"):body.index(".join('')")]
    for col in ("r.rank", "r.name", "r.dealt", "r.kills", "r.hp"):
        assert col in rows, f"ตารางไม่มีช่อง {col}"
    assert "class=\"dmg\"" in rows, "ไม่มีแท่งเทียบความเสียหายให้เห็นว่าใครมากกว่า"


def test_you_can_tell_which_row_is_you():
    body = PLAY[PLAY.index("function wmPaintOver("):]
    body = body[:body.index(chr(10) + "}")]
    assert "(คุณ)" in body, "ดูไม่ออกว่าแถวไหนคือเรา"


# ── 14. เดินแล้วห้ามตกทะเลเอง ──

def test_walking_never_marches_you_into_the_sea(world):
    """เจ้าของเทสวัดแล้ว: เดินอย่างเดียว 20 เมล็ด ตายไป 12 เพราะเดินตกขอบเกาะ

    step() ปล่อยให้ก้าวลงลึกเท่าไหร่ก็ได้ กดค้างเดินจึงเดินตรงลงทะเลไปเฉย ๆ
    """
    dead = []
    for seed in range(1, 21):
        fresh(seed)
        st = match.load(UID)
        g = T.decode(st["terrain"])
        x, y = st["fighters"][0]["x"], st["fighters"][0]["y"]
        for _ in range(120):
            r = P.walk(g, x, y, 1, 6, no_drown=True)
            if r["drowned"]:
                dead.append(seed)
                break
            if not r["path"]:
                break
            x, y = r["x"], r["y"]
    assert not dead, f"เดินอย่างเดียวแล้วตกทะเลในเมล็ด {dead}"


def test_a_walk_stops_at_the_edge_of_the_water(world):
    """เจ้าของเกมสั่ง: เดินลงจากผาได้ — ห้ามเฉพาะเดินลงทะเลเท่านั้น

    เดิมห้ามก้าวลงลึกเกิน 24 px ด้วย ผู้เล่นเลยเดินลงผาไม่ได้เลย
    เหมือนมีกำแพงล่องหนกั้นอยู่ตรงขอบ
    """
    # ① ผาสูง 70 px แต่ข้างล่างมีพื้น — ต้องเดินลงได้
    g = [[T.AIR] * T.W for _ in range(T.H)]
    for x in range(100, 200):
        for y in range(120, 190):
            g[y][x] = T.ROCK
    for x in range(200, 400):
        for y in range(190, 240):
            g[y][x] = T.ROCK
    down = P.walk(g, 190, 120, 1, 40, no_drown=True)
    assert down["x"] > 205, f"เดินลงผาไม่ได้ ติดอยู่ที่ x={down['x']}"
    assert down["y"] == 190, f"ลงผาแล้วไม่ได้อยู่บนพื้นข้างล่าง (y={down['y']})"
    assert down["fell"] >= 60, "ตกลงมาแล้วแต่ไม่นับว่าตก — จะไม่เจ็บจากการตก"
    assert not down["drowned"]

    # ② ขอบเกาะที่ข้างล่างเป็นน้ำ — ต้องหยุดตรงขอบ
    sea = [[T.AIR] * T.W for _ in range(T.H)]
    for x in range(100, 200):
        for y in range(120, 190):
            sea[y][x] = T.ROCK
    edge = P.walk(sea, 190, 120, 1, 40, no_drown=True)
    assert not edge["drowned"], "เดินลงทะเลเอง"
    assert edge["y"] == 120, f"หลุดขอบไปแล้ว (y={edge['y']})"

    # ③ ไม่ใส่ธง (แรงกระแทก) ยังผลักตกทะเลได้ตามเดิม
    blown = P.walk(sea, 190, 120, 1, 40)
    assert blown["drowned"], "แรงกระแทกผลักใครตกทะเลไม่ได้เลย"


def test_a_small_step_down_is_still_fine():
    """ห้ามเข้มจนเดินลงเนินเตี้ย ๆ ไม่ได้"""
    g = [[T.AIR] * T.W for _ in range(T.H)]
    for x in range(100, 200):
        for y in range(120, 220):
            g[y][x] = T.ROCK
    for x in range(200, 300):                    # ต่ำลงแค่ 10 px
        for y in range(130, 220):
            g[y][x] = T.ROCK
    r = P.walk(g, 190, 120, 1, 30, no_drown=True)
    assert r["x"] >= 215, f"ลงเนินเตี้ยแค่ 10 px ก็ยังไม่ยอมเดินผ่าน (หยุดที่ x={r['x']})"
    assert r["y"] == 130, f"ลงเนินแล้วไม่ได้อยู่บนพื้นชั้นล่าง (y={r['y']})"


def test_the_player_walk_always_blocks_walking_into_the_sea():
    body = pathlib.Path("bot/pvp/match.py").read_text(encoding="utf-8")
    assert "no_drown=True" in body, "move() ไม่ได้ห้ามเดินลงทะเล"
    assert body.count("no_drown=True") >= 2, "แรงกระแทกหรือการเดินอย่างใดอย่างหนึ่งยังไม่ได้ห้าม"


# ── 15. ตก/กระเด็น ต้องมีภาพให้เห็น ──

def test_falling_looks_different_from_walking():
    body = PLAY[PLAY.index("function wmDrawFighter("):]
    body = body[:body.index(chr(10) + "}")]
    assert "anim.air" in body, "ตกกับเดินวาดเหมือนกันหมด"
    assert "ctx.rotate(" in body, "ลอยกลางอากาศแล้วตัวยังตั้งตรงเป๊ะเหมือนยืน"


def test_the_replay_knows_when_a_fighter_is_airborne():
    body = PLAY[PLAY.index("function wmStartLoop("):PLAY.index("/** วาดนักสู้")]
    assert "WM_ANIM.dy = pb[1] - pa[1];" in body, "ไม่ได้ดูว่ากำลังขึ้นหรือลง"
    assert "WM_ANIM.air =" in body, "ไม่ได้จำว่าลอยอยู่หรือยืนอยู่"


def test_landing_kicks_up_dust():
    body = PLAY[PLAY.index("function wmStartLoop("):PLAY.index("/** วาดนักสู้")]
    assert "wmDust(" in body, "ตกถึงพื้นแล้วเงียบสนิท ไม่มีอะไรบอกว่ากระแทกพื้น"
    assert "WM_ANIM.air && WM_ANIM.dy <= 0" in body, "ฝุ่นไม่ได้ผูกกับจังหวะแตะพื้น"


def test_being_knocked_back_is_replayed_on_the_right_fighter(world):
    kn = _fn("function wmPlayKnocks(")
    assert "f.name === k.name" in kn, "จับคู่คนกับเส้นทางกระเด็นไม่ถูก"
    assert "wmChunk(fi, k.path, null)" in kn, "ไม่ได้เล่นภาพกระเด็น"
    assert "(a.blast || {}).knocks" in _fn("function wmPlayVictims("), \
        "โดนระเบิดผลักแล้วไม่เห็นตัวปลิว"


def test_the_clock_is_frozen_while_the_bot_replay_plays():
    """หมดเวลาระหว่างนั่งดูบอทเดิน = ขอจบเทิร์นไปตัดภาพบอทกลางคัน
    แล้วเทิร์นเราก็โผล่มาโดยไม่ได้ดูว่าบอททำอะไร"""
    body = PLAY[PLAY.index("function wmTick("):]
    body = body[:body.index(chr(10) + "}")]
    assert "if (wmBusyFx()) WM_DEADLINE" in body,         "นาฬิกายังเดินตอนภาพตาบอทเล่นค้างอยู่"


# ── 17. ปุ่มยอมแพ้ ──

def test_surrendering_blows_yourself_up_and_ends_it(world):
    fresh()
    good, r = match.surrender(UID)
    assert good, r.get("error")
    assert r["over"], "ยอมแพ้แล้วเกมยังไม่จบ"
    assert r["fighters"][0]["dead"], "ยอมแพ้แล้วยังไม่ตาย"
    assert r["surrender"]["blast"]["crater"] > 0, "ไม่มีระเบิดให้เห็น"
    assert any("ยอมแพ้" in line for line in r["log"]), "ไม่ได้บันทึกว่ายอมแพ้"


def test_surrendering_does_not_hurt_the_opponent(world):
    fresh()
    st = match.load(UID)
    st["fighters"][1].update(x=st["fighters"][0]["x"] + 10, y=st["fighters"][0]["y"])
    match.save(UID, st)
    r = match.surrender(UID)[1]
    assert r["fighters"][1]["hp"] == 100, "ระเบิดยอมแพ้ไปโดนคู่ต่อสู้ด้วย"


def test_you_cannot_surrender_twice(world):
    fresh()
    match.surrender(UID)
    good, r = match.surrender(UID)
    assert not good and "จบ" in r["error"]


def test_the_page_has_a_surrender_button():
    assert 'id="wmGiveUp"' in HTML, "ไม่มีปุ่มยอมแพ้บนหน้าเว็บ"
    body = PLAY[PLAY.index("async function wmGiveUp("):]
    body = body[:body.index(chr(10) + "}")]
    assert "action: 'surrender'" in body, "ปุ่มยอมแพ้ไม่ได้บอกเซิร์ฟเวอร์"
    assert "if (!confirm(" in body, "กดพลาดทีเดียวจบเกมเลย ต้องถามก่อน"
    at = body.index("if (!confirm(")
    assert "return;" in body[at:at + 140], "ถามแล้วแต่ตอบไม่ก็ยังยอมแพ้อยู่ดี"
    assert "wmLand(s.blast)" in body, "ยอมแพ้แล้วไม่มีอนิเมชันระเบิดตัวเอง"


# ── 18. ตกลงน้ำต้องเห็นว่าตกและจม ──

def _cliff(ledge_x=200):
    g = [[T.AIR] * T.W for _ in range(T.H)]
    for x in range(100, ledge_x):
        for y in range(120, 130):
            g[y][x] = T.ROCK
    return g


def test_falling_off_the_edge_shows_the_whole_fall(world):
    """เจ้าของเกมทัก: ยังไม่แตะน้ำเลยก็ตายแล้ว

    เดิมเก็บแค่จุดปลาย ตัวเลยวาร์ปจากขอบผาไปโผล่ที่ผิวน้ำทีเดียว
    """
    r = P.walk(_cliff(), 190, 120, 1, 40)
    ys = [pt[1] for pt in r["path"]]
    assert r["drowned"], "เดินตกขอบแล้วไม่ได้ตกน้ำ — เทสตั้งฉากผิด"
    gap = max(ys[i + 1] - ys[i] for i in range(len(ys) - 1))
    assert gap <= 2, f"ร่วงทีละ {gap} px = วาร์ป ไม่ใช่ตก"
    assert len(ys) > 60, f"เส้นทางมีแค่ {len(ys)} จุด สั้นเกินกว่าจะเห็นว่าตก"


def test_the_body_keeps_sinking_below_the_surface(world):
    """ต้องมีอนิเมชันจมน้ำ ไม่ใช่หยุดที่ผิวน้ำแล้วหายวับ"""
    water = T.H - T.WATER
    for r in (P.walk(_cliff(), 190, 120, 1, 40), P.jump(_cliff(), 198, 120, 1)):
        assert r["drowned"]
        deepest = max(pt[1] for pt in r["path"])
        assert deepest > water, f"เส้นทางลึกสุดแค่ {deepest} ผิวน้ำอยู่ {water} — ไม่ได้จมเลย"
        assert deepest - water >= 10, f"จมแค่ {deepest - water} px แป๊บเดียวก็หาย"
        assert r["y"] == water, "ตำแหน่งจริงต้องอยู่ที่ผิวน้ำ จุดจมมีไว้เล่นภาพเท่านั้น"


def test_jumping_into_the_sea_arcs_first(world):
    """กระโดดออกไปต้องเห็นวิถีโค้งก่อน ไม่ใช่ตายทันทีที่พ้นขอบ"""
    r = P.jump(_cliff(), 198, 120, 1)
    ys = [pt[1] for pt in r["path"]]
    assert min(ys) < 120, "กระโดดแล้วไม่ได้ลอยขึ้นเลย"
    assert len(ys) > 25, f"วิถีมีแค่ {len(ys)} เฟรม สั้นเกินกว่าจะเห็น"


def test_a_drowned_fighter_is_still_drawn_while_sinking():
    body = PLAY[PLAY.index("function wmStartLoop("):PLAY.index("/** วาดนักสู้")]
    assert "if (!f.dead || moving || WM_DYING[i])" in body,         "ตายปุ๊บหยุดวาดปั๊บ — ภาพจมน้ำที่เซิร์ฟเวอร์ส่งมาไม่มีใครได้เห็น"


def test_hitting_the_water_makes_a_splash():
    body = PLAY[PLAY.index("function wmStartLoop("):PLAY.index("/** วาดนักสู้")]
    assert "wmSplash(" in body, "แตะผิวน้ำแล้วเงียบสนิท"
    assert "af.y < wl && y >= wl" in body, "ไม่ได้ผูกน้ำกระจายกับจังหวะข้ามผิวน้ำ"
    assert "function wmSplash(" in PLAY, "เรียกแต่ไม่มีฟังก์ชัน"


def test_the_body_fades_as_it_sinks():
    body = PLAY[PLAY.index("function wmDrawFighter("):]
    body = body[:body.index(chr(10) + "}")]
    assert "const deep = f.y - (WM.h - WM.water);" in body, "ไม่ได้ดูว่าจมลึกแค่ไหน"
    assert "1 - deep / 18" in body, "จมแล้วไม่จาง — ค้างอยู่ใต้น้ำเฉย ๆ"


# ── 19. กดเดิน/กระโดดรัว ๆ แล้วห้ามวาป ──

def test_a_second_walk_does_not_warp_the_fighter_backwards():
    """กดค้างเดินยิงคำสั่งถี่กว่าภาพเล่นจบ ท่อนใหม่จะเริ่มจากตำแหน่งของเซิร์ฟเวอร์
    ซึ่งอยู่ข้างหน้าตำแหน่งที่กำลังวาดอยู่ — ย้อนผิดจุดคือวาปย้อนหลังแล้ววาปกลับ"""
    body = PLAY[PLAY.index("async function wmDo("):PLAY.index("async function wmEndTurn(")]
    assert "WM_ANIM.path[WM_ANIM.path.length - 1]" in body,         "ยังย้อนไปที่ตำแหน่งกลางแอนิเมชันแทนปลายทางของท่อนก่อน"
    assert "WM_ANIM.fi === mine" in body, "ไม่ได้เช็คว่าท่อนที่ค้างอยู่เป็นของคนเดียวกัน"
    assert "const from = tail ?" in body, "ไม่ได้ใช้ปลายทางของท่อนก่อนเป็นจุดเริ่ม"


# ── 20. อย่าเฉลยผลก่อนภาพจะเล่นจบ ──

def test_the_result_waits_for_the_animation_to_finish():
    """เจ้าของเกมทัก: ขึ้น "คุณแพ้" ก่อนตัวจะร่วงลงน้ำเสียอีก

    เซิร์ฟเวอร์รู้ผลตั้งแต่วินาทีที่สั่ง แต่ผู้เล่นยังไม่เห็นตัวเองตกด้วยซ้ำ
    """
    body = PLAY[PLAY.index("function wmPaintOver("):]
    body = body[:body.index(chr(10) + "}")]
    assert "if (!idle && wmBusyFx()) { box.hidden = true;" in body, \
        "ยังขึ้นแผงสรุปทับทันทีที่เซิร์ฟเวอร์บอกว่าจบ"


def test_busy_covers_every_kind_of_animation():
    body = PLAY[PLAY.index("function wmBusyFx("):]
    body = body[:body.index(chr(10) + "}")]
    for fx, why in [("WM_ANIM", "ตัวกำลังเดิน/ร่วง"), ("WM_QUEUE.length", "ยังมีท่อนรอเล่น"),
                    ("WM_SHOT", "กระสุนกำลังบิน"), ("WM_BOOMS.length", "ระเบิดยังไม่จาง")]:
        assert fx in body, f"ไม่ได้นับ {fx} ({why}) ว่าเป็นภาพที่ยังเล่นค้างอยู่"


def test_the_result_does_appear_once_nothing_is_animating():
    body = PLAY[PLAY.index("function wmTick("):]
    body = body[:body.index(chr(10) + "}")]
    assert "WM_ST.over && !WM_OVER_SHOWN && !wmBusyFx()" in body,         "รอแล้วไม่มีใครมาเปิดแผงให้ — จบเกมแล้วจอค้างเปล่า ๆ"


def test_the_result_is_painted_once_not_every_frame():
    assert "WM_OVER_SHOWN = !idle;" in PLAY, "ไม่ได้จำว่าขึ้นไปแล้ว จะวาดใหม่ทุกเฟรม"
    body = PLAY[PLAY.index("function wmApply("):PLAY.index("function wmMe(")]
    assert "if (!d || !d.over) WM_OVER_SHOWN = false;" in body,         "เริ่มสนามใหม่แล้วยังจำว่าเคยขึ้นผลไปแล้ว รอบหน้าจะไม่ขึ้นอีกเลย"


# ── 21. กระเด็นให้จบก่อน แล้วค่อยสรุปดาเมจ/ตาย ──

def test_every_hit_reports_a_knockback_path(world):
    """เจ้าของเกมสั่ง: ทุกครั้งที่โดนโจมตีต้องมีการกระเด็นและมีอนิเมชัน"""
    for skill in ("basic", "heavy"):
        fresh()
        st = match.load(UID)
        me, foe = st["fighters"]
        foe.update(x=me["x"] + 16, y=me["y"])
        match.save(UID, st)
        a = match.attack(UID, skill, angle=0)[1]["attack"]
        assert a.get("knocks"), f"{skill} โดนแล้วไม่กระเด็น"
        assert a["knocks"][0]["path"], "กระเด็นแต่ไม่มีเส้นทางให้เล่นภาพ"
        assert a["knocks"][0]["name"], "ไม่บอกว่าใครกระเด็น"


def test_a_blast_pushes_people_away_from_the_centre(world):
    """ระเบิดต้องผลักออกจากจุดระเบิด — เรียก _explode ตรง ๆ จะได้ไม่ต้องลุ้นว่ายิงโดนไหม"""
    fresh()
    g = [[T.AIR] * T.W for _ in range(T.H)]
    for x in range(T.W):
        for y in range(200, T.H - T.WATER):
            g[y][x] = T.ROCK
    st = match.load(UID)
    st["terrain"], st["props"] = T.encode(g), []
    me, foe = st["fighters"]
    me.update(x=300, y=200)
    foe.update(x=330, y=200)
    match.save(UID, st)

    st = match.load(UID)
    g = T.decode(st["terrain"])
    blast = match._explode(st, g, 300, 190, 60, 40, 0, "ทดสอบ", by=st["fighters"][0])
    assert blast["hits"], "ระเบิดติดตัวแล้วไม่โดนใครเลย — ฉากทดสอบเพี้ยน"
    assert blast["knocks"], "โดนระเบิดแล้วยืนนิ่งเฉย ไม่กระเด็นเลย"
    assert st["fighters"][1]["x"] > 330, "ระเบิดผลักเข้าหาจุดระเบิดแทนที่จะผลักออก"


def test_the_page_waits_for_the_knockback_before_showing_damage():
    """เจ้าของเกมสั่ง: กระเด็นให้จบก่อน แล้วค่อยสรุปว่าโดนเท่าไหร่ ตายหรือยัง"""
    vic = _fn("function wmPlayVictims(")
    assert vic.index("wmPlayKnocks(knocks)") < vic.index("wmSettleVictim(v)"),         "ยังไม่ได้ให้กระเด็นก่อนแล้วค่อยสรุปผล"
    assert "if (flying) wmStep(() => {}, wmFxIdle);" in vic,         "ไม่ได้รอให้ทุกคนตกถึงพื้นก่อนเริ่มสรุปผล"
    one = _fn("function wmSettleVictim(")
    assert "WM_POPS.push" in one and "wmDie(fi, f)" in one, "สรุปผลไม่ครบทั้งเลขดาเมจและภาพตาย"
    assert "wmStep(() => wmSettleVictim(v), wmFxIdle)" in _fn("function wmPlayVictims("), \
        "คนที่โดนแต่ละคนไม่ได้เป็นขั้นแยกกัน — จะเล่นทับกัน"


def test_deferred_work_actually_runs_when_the_replay_drains():
    body = PLAY[PLAY.index("function wmStartLoop("):PLAY.index("/** วาดนักสู้")]
    assert "while (WM_AFTER.length) WM_AFTER.shift()();" in body,         "เข้าคิวไว้แล้วไม่มีใครมาสะสาง — เลขดาเมจจะไม่ขึ้นเลย"


def test_a_death_is_announced_once_not_every_frame():
    body = PLAY[PLAY.index("function wmCallDeaths("):]
    body = body[:body.index(chr(10) + "}")]
    assert "if (f.dead && !WM_DEAD_SEEN[f.name]) {" in body, "ประกาศตายซ้ำทุกเฟรม"
    assert "WM_DEAD_SEEN[f.name] = true;" in body, "ไม่ได้ทำเครื่องหมายว่าประกาศไปแล้ว"
    assert "wmDie(i, f)" in body, "ไม่ได้เล่นภาพตาย"


def test_dying_has_its_own_animation():
    body = PLAY[PLAY.index("function wmDie("):]
    body = body[:body.index(chr(10) + "}")]
    assert "WM_DYING[i] =" in body, "ไม่ได้กันเวลาไว้ให้ภาพตายเล่น"
    assert "WM_BITS.push" in body and "WM_POPS.push" in body,         "ตายแล้วหายเงียบ ไม่มีสะเก็ดไม่มีป้ายบอกว่าใครตาย"


def test_the_body_stays_on_screen_through_the_death_animation():
    body = PLAY[PLAY.index("function wmStartLoop("):PLAY.index("/** วาดนักสู้")]
    assert "|| WM_DYING[i]" in body, "ภาพตายเล่นอยู่แต่ตัวหายไปแล้ว"


def test_the_result_panel_waits_for_the_death_animation_too():
    body = PLAY[PLAY.index("function wmBusyFx("):]
    body = body[:body.index(chr(10) + "}")]
    assert "WM_AFTER.length" in body, "ยังมีงานค้างแต่ขึ้นแผงสรุปแล้ว"
    assert "Object.keys(WM_DYING).length" in body, "ภาพตายยังเล่นอยู่แต่ขึ้นแผงสรุปแล้ว"


def test_damage_numbers_pop_where_the_target_landed():
    """เด้งเลขจากตำแหน่งสด ๆ ของตัวนักสู้ ไม่ใช่จุดที่ยืนตอนโดน (กระเด็นไปไกลแล้ว)"""
    one = _fn("function wmSettleVictim(")
    assert "const f = WM_ST.fighters[fi];" in one, "ไม่ได้อ่านตำแหน่งสดตอนสรุปผล"
    assert "wmFocus(f, true)" in one, "ไม่ได้จับกล้องไปที่คนที่กำลังสรุปผลของเขา"
    assert "x: f.x, y: f.y - 26" in one, "เลขดาเมจเด้งที่จุดเดิมตอนโดน"


def test_a_new_match_forgets_who_died():
    body = PLAY[PLAY.index("function wmApply("):PLAY.index("function wmMe(")]
    assert "WM_DEAD_SEEN" in body, "สนามใหม่ยังจำคนตายรอบก่อน ภาพตายจะไม่เล่นอีกเลย"


# ── 21.5 ห้ามเฉลยผลก่อนภาพจะเล่นถึง ──

def _reveal_flow():
    """รันฟังก์ชันซ่อน/เฉลยของจริงด้วย node แล้วคืนผลแต่ละขั้น

    อ่านซอร์สอย่างเดียวจับไม่ได้ว่าเลือด "โผล่ค่าใหม่ตั้งแต่กระสุนยังไม่ถึง"
    ต้องรันจริงถึงจะเห็นว่าค่าบนจอเป็นเท่าไหร่ในแต่ละจังหวะ
    """
    import json
    import shutil
    import subprocess

    if not shutil.which("node"):
        pytest.skip("เครื่องนี้ไม่มี node")
    r = subprocess.run(["node", "tests/reveal_flow.js"],
                       capture_output=True, text=True, encoding="utf-8")
    assert r.returncode == 0, r.stderr
    return {d["step"]: d for d in map(json.loads, r.stdout.strip().splitlines())}


def test_the_screen_keeps_the_old_hp_until_the_animation_gets_there():
    """เจ้าของเกมสั่ง: "ห้ามสรุปผลลัพธ์ก่อน เด็ดขาด"

    อาการที่เจอ: ยิงไม่โดนแต่เลือดตัวเองลดตั้งแต่กระสุนยังไม่ทันบินถึง
    เพราะเซิร์ฟเวอร์ตอบผลทั้งก้อนมาแล้วเว็บเอาไปแสดงทันที
    """
    r = _reveal_flow()
    me, bot = r["hidden"]["f"]
    assert me["hp"] == 100, "เลือดเราลดตั้งแต่ภาพยังไม่เล่นถึง"
    assert bot["hp"] == 30 and not bot["dead"], "คู่ต่อสู้ตายก่อนเห็นภาพโดน"
    assert bot["x"] == 90, "คู่ต่อสู้วาปไปจุดที่กระเด็นไปแล้วตั้งแต่ยังไม่โดน"


def test_each_victim_is_revealed_when_the_camera_reaches_him():
    """เฉลยทีละคนตอนกล้องไปจับ — และตัดเท่าที่โชว์ ไม่ใช่กระโดดไปค่าสุดท้าย

    ค่าสุดท้ายรวมหมัดที่ยังไม่ได้เล่นภาพด้วย (บอทยิงสวนมาในคำตอบเดียวกัน)
    ตัดทีเดียวคือเลือดหายมากกว่าตัวเลขที่เด้งขึ้นมา
    """
    body = PLAY[PLAY.index("function wmSettleVictim("):]
    body = body[:body.index(chr(10) + "}" + chr(10))]
    assert body.index("wmRevealOne(") < body.index("WM_POPS.push"),         "ไม่ได้เฉลยเลือดตอนกล้องไปจับคนที่โดน — เลขดาเมจเด้งแต่หลอดเลือดไม่ขยับ"

    r = _reveal_flow()
    me, bot = r["one"]["f"]
    assert bot["hp"] == 0 and bot["dead"], "ถึงคิวเขาแล้วยังไม่ตัดเลือด"
    assert me["hp"] == 75, ("ตัดเลือดไม่เท่าตัวเลขที่เด้ง — เลือดเหลือ "
                            f"{me['hp']} ทั้งที่เพิ่งโชว์ -25 จาก 100")


def test_many_hits_on_one_person_become_one_reveal(world):
    """ดาบคู่ฟันรัวสี่ครั้ง = สี่รายการของคนเดียว ต้องยุบเหลือรายการเดียว

    และต้องพก "เลือดหลังหมัดสุดท้าย" ที่เซิร์ฟเวอร์บอกมาไปด้วย
    ไม่งั้นตอนเฉลยจะไม่มีเลขให้ใส่ เลือดค้างค่าเก่าจนจบภาพ
    """
    v = _reveal_flow()["victims"]["v"]
    assert len(v) == 1, f"ยุบไม่ครบ เหลือ {len(v)} รายการ"
    assert v[0]["dmg"] == 30, "รวมดาเมจทุกหมัดไม่ครบ"
    assert v[0]["hp"] == 70, "ไม่ได้พกเลือดที่เซิร์ฟเวอร์บอกมา — เฉลยไม่ได้"


def test_everything_matches_the_server_once_the_show_is_over():
    """ซ่อนได้ แต่ห้ามซ่อนค้าง — ภาพจบแล้วค่าบนจอต้องตรงกับเซิร์ฟเวอร์เป๊ะ"""
    r = _reveal_flow()
    me, bot = r["all"]["f"]
    assert me["hp"] == 60 and bot["hp"] == 0 and bot["dead"]
    assert bot["x"] == 140, "ตำแหน่งสุดท้ายไม่ตรงกับเซิร์ฟเวอร์ = เดินต่อแล้วเพี้ยน"
    assert r["all"]["left"] is None, "เฉลยแล้วยังค้างของซ่อนไว้อีก"


def test_the_new_state_is_applied_before_the_visuals_are_queued():
    """wmApply ล้างคิวภาพทิ้งทุกครั้ง — ต่อคิวก่อนเรียกมันคือต่อทิ้ง

    เคยพลาดจริง: ท่าประชิดต่อคิวภาพไว้ใน wmShowHit แล้ว wmApply ล้างทิ้งทั้งชุด
    เห็นแต่คู่ต่อสู้วาปไปจุดใหม่ ไม่มีทั้งการกระเด็นและตัวเลขดาเมจ
    """
    body = PLAY[PLAY.index("function wmPlayAttack("):]
    body = body[:body.index(chr(10) + "}" + chr(10))]
    assert body.index("wmApply(d)") < body.index("wmShowHit("),         "เรียก wmShowHit ก่อน wmApply — ภาพที่ต่อคิวไว้จะถูกล้างทิ้ง"
    assert body.index("wmHideOutcome(") < body.index("wmShowHit("),         "ยังไม่ทันซ่อนผล ภาพก็เริ่มเล่นแล้ว"
    assert "wmStep(() => {}, wmFxIdle, () => wmQueueBot(d))" in body,         "ต่อคิวตาบอททันที — บอทจะเดินแข่งกับกระสุนของเราที่ยังบินอยู่"


def test_the_bot_turn_is_queued_behind_what_the_step_it_waited_for_spawned():
    """wmStep ต้องรับงาน "ตอนขั้นนี้เสร็จ" ได้

    กระสุนถึงเป้าแล้วค่อยต่อคิวสรุปผลทีละคน ถ้าต่อคิวตาบอทไว้ตั้งแต่แรก
    คิวจะเป็น [บอท, สรุปผล] = บอทเดินก่อนตัวเลขดาเมจจะขึ้นด้วยซ้ำ
    """
    assert "function wmStep(run, done, then)" in PLAY
    assert "if (fin) fin();" in PLAY, "ขั้นเสร็จแล้วไม่ได้เรียกงานที่ฝากไว้"


def test_hidden_values_are_never_left_hidden():
    """กันซ่อนค้าง — ภาพจบเมื่อไหร่ต้องเฉลยเอง ไม่ต้องรอใครสั่ง"""
    assert "if (WM_HIDDEN && !wmBusyFx()) wmRevealAll();" in PLAY,         "ไม่มีใครเฉลยของที่ซ่อนไว้ เลือดบนจอจะค้างค่าเก่าตลอดกาล"
    assert "WM_HIDDEN = null;                // ค่าที่ซ่อนไว้ก็เป็นของก้อนเก่า" in PLAY,         "สถานะใหม่มาแล้วยังถือค่าซ่อนของก้อนเก่าไว้"


# ── 21.6 ห้ามเห็นผลของบอทก่อนบอทจะขยับ ──

def test_the_bot_stays_put_until_its_walk_actually_plays():
    """เจ้าของเกมทัก: บางทีเห็นผลการเดินของบอทก่อนบอทจะเดินจริง

    ต้นเหตุ: wmQueueBot ย้อนบอทกลับจุดเริ่ม "ตอนขั้นนั้นเริ่มทำงาน" ซึ่งช้ากว่า
    ตอนรับคำตอบอย่างน้อย 1 วินาที (WM_GAP_BEFORE) ระหว่างนั้นจอวาดบอทที่ปลายทางไปแล้ว
    """
    import json
    import shutil
    import subprocess

    if not shutil.which("node"):
        pytest.skip("เครื่องนี้ไม่มี node")
    r = subprocess.run(["node", "tests/bot_reveal.js"],
                       capture_output=True, text=True, encoding="utf-8")
    assert r.returncode == 0, r.stderr
    out = json.loads(r.stdout.strip().splitlines()[-1])

    bot = next(f for f in out["duringGap"] if f["name"] == "บอท")
    assert (bot["x"], bot["y"]) == (300, 200),         f"ช่วงรอภาพเริ่ม บอทไปยืนที่ ({bot['x']},{bot['y']}) แล้ว — เฉลยก่อนเดิน"
    me = next(f for f in out["duringGap"] if f["name"] == "คุณ")
    assert me["hp"] == 90, "เลือดเราลดตั้งแต่ยังไม่เห็นบอทตี"

    done = next(f for f in out["after"] if f["name"] == "บอท")
    assert (done["x"], done["y"]) == (420, 188), "เล่นภาพจบแล้วบอทไม่ไปที่ที่ควรอยู่"


def test_every_state_swap_hides_the_outcome_first():
    """ทุกทางที่รับสถานะใหม่ทั้งก้อนต้องซ่อนผลไว้ก่อน ไม่ใช่แค่ทางจบเทิร์น

    เดิม wmDo ไม่ซ่อน — พอเดินจนแรงหมด (auto_ended) บอทเดินต่อในคำตอบเดียวกัน
    ผู้เล่นจึงเห็นบอทยืนอยู่ปลายทางค้างเป็นวินาทีก่อนมันจะเด้งกลับไปเดิน
    """
    for fn in ("async function wmDo(", "async function wmEndTurn(",
               "function wmPlayAttack("):
        body = PLAY[PLAY.index(fn):]
        body = body[:body.index(chr(10) + "}" + chr(10))]
        assert "wmSnapshot()" in body and "wmHideOutcome(" in body,             f"{fn} รับสถานะใหม่มาแล้วโชว์ทันที ไม่ได้ซ่อนรอภาพ"
        # ทับสถานะเก่าได้สองทาง: เขียน WM_ST ตรง ๆ หรือผ่าน wmApply()
        swap = min(i for i in (body.find("WM_ST = "), body.find("wmApply(")) if i >= 0)
        assert body.index("wmSnapshot()") < swap,             f"{fn} จำค่าเก่าหลังจากทับไปแล้ว — จำได้แต่ของใหม่"
        assert swap < body.index("wmHideOutcome("),             f"{fn} ซ่อนผลก่อนที่สถานะใหม่จะมาถึง = ซ่อนของเก่าทับของเก่า"


def test_reconciled_position_is_not_overwritten_by_the_late_reveal():
    """ตัวเราทาบตำแหน่งเสร็จแล้วคือของจริง ห้ามให้การเฉลยรวมทีหลังมาทับ

    ไม่งั้นเดินอยู่ดี ๆ ตัวจะเด้งถอยไปจุดที่เซิร์ฟเวอร์ตอบก่อนหน้า
    """
    body = PLAY[PLAY.index("function wmReconcile("):]
    body = body[:body.index(chr(10) + "}" + chr(10))]
    assert "delete WM_HIDDEN[f.name]" in body,         "ทาบเสร็จแล้วยังค้างอยู่ในรายการที่รอเฉลย — เดี๋ยวโดนทับ"


# ── 22. แผงสรุปผลต้องแสดงชื่อกับดาเมจจริง ──

def _render_over(payload):
    """เรนเดอร์แผงสรุปผลจริง ๆ ด้วย node แล้วคืน HTML ที่ได้

    เทสที่ไล่ดูแต่ซอร์สจับไม่ได้ว่า "ขึ้นว่าแพ้ทั้งที่ชนะ" หรือ "ตารางว่างเปล่า"
    ต้องรันฟังก์ชันจริงกับข้อมูลจริงถึงจะเห็น
    """
    import json
    import shutil
    import subprocess
    import tempfile

    if not shutil.which("node"):
        pytest.skip("เครื่องนี้ไม่มี node")
    with tempfile.TemporaryDirectory() as tmp:
        f = pathlib.Path(tmp) / "state.json"
        f.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        r = subprocess.run(["node", "tests/render_over.js", str(f)],
                           capture_output=True, text=True, encoding="utf-8")
        assert r.returncode == 0, r.stderr
        return r.stdout


def _finished(world_seed=7):
    """เล่นจนจบจริง แล้วคืนสถานะสุดท้ายแบบที่เว็บได้รับ"""
    fresh(world_seed)
    st = match.load(UID)
    st["fighters"][1].update(hp=8, x=st["fighters"][0]["x"] + 16, y=st["fighters"][0]["y"])
    match.save(UID, st)
    return match.attack(UID, "basic", angle=0)[1]


def test_winning_says_you_won(world):
    """เจ้าของเกมทัก: ฆ่าบอทได้ก็ยังขึ้นว่าคุณแพ้"""
    d = _finished()
    assert not d["fighters"][0]["dead"] and d["over"], "ฉากทดสอบเพี้ยน — ไม่ได้ชนะจริง"
    html = _render_over(d)
    assert "คุณชนะ" in html, "ชนะแล้วยังขึ้นว่าแพ้:" + chr(10) + html


def test_the_table_really_lists_names_and_damage(world):
    """เจ้าของเกมทัก: อันดับไม่แสดงชื่อผู้เล่นหรือบอทและคะแนนความเสียหายเลย"""
    d = _finished()
    html = _render_over(d)
    for f in d["fighters"]:
        assert f["name"] in html, f"ตารางไม่มีชื่อ {f['name']}"
    dealt = max(f.get("dealt", 0) for f in d["fighters"])
    assert dealt > 0, "ฉากทดสอบเพี้ยน — ไม่มีใครทำดาเมจเลย"
    assert f">{dealt}" in html, f"ตารางไม่มีตัวเลขความเสียหาย {dealt}"
    assert "ความเสียหาย" in html, "ไม่มีหัวคอลัมน์ความเสียหาย"


def test_the_panel_survives_a_payload_without_standings(world):
    """standings หายไปด้วยเหตุใดก็ตาม ต้องไม่กลายเป็น 'คุณแพ้' + ตารางว่าง"""
    d = _finished()
    d.pop("standings", None)
    html = _render_over(d)
    assert "คุณชนะ" in html, "ไม่มี standings แล้วตัดสินว่าแพ้ทันที"
    assert d["fighters"][1]["name"] in html, "ไม่มี standings แล้วตารางว่างเปล่า"


def test_the_verdict_comes_from_the_fighters_not_the_table(world):
    """standings เป็นแค่ตารางสรุป ความจริงว่าใครรอดอยู่ที่ตัวนักสู้

    ถ้าไปตัดสินจากตาราง พอตารางเพี้ยนหรือหายไปก็ประกาศผลผิดทันที
    """
    d = _finished()
    for row in d["standings"]:                  # ตารางบอกว่าตายหมดทุกคน
        row["dead"] = True
    html = _render_over(d)
    assert "คุณชนะ" in html, "เชื่อตารางมากกว่าตัวนักสู้ — ตารางเพี้ยนแล้วประกาศผลผิด"


def test_losing_still_says_you_lost(world):
    """กันแก้เกินจนขึ้นว่าชนะตลอด"""
    d = _finished()
    d["fighters"][0]["dead"] = True
    d["standings"][0]["dead"] = True
    html = _render_over(d)
    assert "คุณแพ้" in html, "ตายแล้วยังขึ้นว่าชนะ"


# ── 23. ระยะประชิดไกลขึ้นเท่าตัว + กระโดดชนกำแพง ──

def test_melee_reach_was_doubled():
    """เจ้าของเกมสั่ง: เพิ่มระยะการโจมตีปกติและสกิลออกเท่าตัว"""
    was = {"basic": 26, "bash": 30, "heavy": 26, "stab": 24, "twin_blades": 30}
    for key, before in was.items():
        assert W.ALL[key]["reach"] == before * 2,             f"{key} ระยะ {W.ALL[key]['reach']} ไม่ใช่สองเท่าของ {before}"


def test_the_bot_still_walks_close_enough_to_swing():
    """ระยะฟันไกลขึ้นแล้วบอทต้องยังเข้าถึงตัวได้ ไม่ใช่ยืนห่างแล้วฟันลม"""
    shortest = min(a["reach"] for a in W.ALL.values() if a.get("kind") == "melee")
    assert match.BOT_REACH < shortest,         f"บอทหยุดที่ {match.BOT_REACH} แต่ท่าสั้นสุดฟันได้ {shortest}"


def test_you_can_hit_from_twice_as_far(world):
    fresh()
    st = match.load(UID)
    me, foe = st["fighters"]
    foe.update(x=me["x"] + 40, y=me["y"])       # ไกลกว่าระยะเดิม (26) แต่ในระยะใหม่ (52)
    me["face"] = 1
    match.save(UID, st)
    a = match.attack(UID, "basic", angle=0)[1]["attack"]
    assert [h for h in a["hits"] if h["name"] != "คุณ"], "ห่าง 40 px ยังฟันไม่ถึง"


def test_a_jump_into_a_wall_reports_where_it_hit():
    g = [[T.AIR] * T.W for _ in range(T.H)]
    for x in range(T.W):
        for y in range(200, T.H - T.WATER):
            g[y][x] = T.ROCK
    for x in range(214, 224):
        for y in range(150, 200):
            g[y][x] = T.BRICK
    hit = P.jump(g, 210, 200, 1)
    assert hit["bump"], "กระโดดชนกำแพงแล้วไม่บอกว่าชนตรงไหน"
    assert 205 < hit["bump"][0] < 230, f"จุดชนอยู่ที่ {hit['bump']} ซึ่งไม่ใช่ตรงกำแพง"
    clear = P.jump(g, 100, 200, 1)
    assert clear["bump"] is None, "กระโดดโล่ง ๆ ก็ยังบอกว่าชน"


def test_the_page_plays_a_bump_when_you_hit_a_wall():
    assert "if (d.move && d.move.bump) wmBump(" in PLAY,         "เซิร์ฟเวอร์บอกว่าชนแล้วเว็บไม่เล่นภาพ"
    body = PLAY[PLAY.index("function wmBump("):]
    body = body[:body.index(chr(10) + "}")]
    assert "WM_BITS.push" in body and "wmDust(" in body, "ชนกำแพงแล้วเงียบสนิท"


# ── 24. ห้ามกดอะไรจนกว่าจะถึงตาเรา ──

def _fn(head):
    body = PLAY[PLAY.index(head):]
    return body[:body.index(chr(10) + "}")]


def test_waiting_covers_the_bot_replay_not_just_the_turn_number():
    """ซ้อมกับบอท: เซิร์ฟเวอร์เดินตาบอทจบในคำขอเดียว d.turn จึงกลับมาเป็นเราทันที
    เช็คแค่ wmMe().bot เลยไม่มีวันเป็นจริง — กดสั่งได้ทั้งที่บอทยังเดินอยู่บนจอ"""
    body = _fn("function wmWaiting(")
    assert "WM_ANIM && isBot(WM_ANIM.fi)" in body, "ไม่ได้ดูว่าภาพที่เล่นอยู่เป็นของบอท"
    assert "WM_QUEUE.some(q => isBot(q.fi))" in body, "ไม่ได้ดูท่อนที่รอเล่นของบอท"
    assert "wmMe().bot" in body, "ตาบอทจริง ๆ ก็ต้องล็อกด้วย"
    assert "WM_ST.over" in body, "จบเกมแล้วยังกดได้"


def test_your_own_walk_does_not_lock_you_out():
    """ล็อกเหมารวมทุกแอนิเมชัน = กดค้างเดินไม่ได้เลย เพราะภาพเดินของเราเองก็ค้างอยู่"""
    body = _fn("function wmWaiting(")
    assert "isBot(" in body, "ล็อกโดยไม่ดูว่าเป็นภาพของใคร — เดินเองก็จะโดนล็อก"
    assert "WM_ANIM ||" not in body, "ล็อกทุกแอนิเมชันรวมของตัวเองด้วย"


def test_every_way_in_is_guarded():
    """ปุ่มถูกปิดแล้วก็จริง แต่คีย์บอร์ดกับการแตะจอยังเข้ามาได้"""
    for head, why in [("async function wmDo(", "เดิน/กระโดด"),
                      ("async function wmAttack(", "โจมตี"),
                      ("async function wmGiveUp(", "ยอมแพ้"),
                      ("function wmHoldStart(", "กดค้างเดิน")]:
        assert "wmWaiting()" in _fn(head), f"{why} ยังสั่งได้ตอนไม่ถึงตา"
    down = PLAY[PLAY.index("  const down = e => {"):]
    assert "wmWaiting()" in down[:down.index(chr(10) + "  };")], "เล็งได้ตอนไม่ถึงตา"


def test_the_buttons_are_actually_disabled_while_waiting():
    body = _fn("function wmSyncLock(")
    assert "b.disabled = wait" in body, "ไม่ได้ปิดปุ่มบนแผงบังคับ"
    assert "wmGiveUp" in body, "ปุ่มยอมแพ้ยังกดได้ตอนบอทเดิน"
    assert "classList.toggle('wm-wait', wait)" in body, "ไม่มีสัญญาณให้เห็นว่ากดไม่ได้"
    assert "wmHoldStop()" in body, "กดค้างอยู่แล้วถึงตาบอท มือยังค้างสั่งต่อ"


def test_the_lock_is_rechecked_every_frame():
    """เรียกแค่ตอนสถานะเปลี่ยนไม่พอ — ตาบอทเริ่มหลัง wmApply ไปแล้วหนึ่งจังหวะ"""
    body = _fn("function wmTick(")
    assert "wmSyncLock();" in body, "ไม่ได้เช็คสถานะล็อกทุกเฟรม"


def test_the_lock_only_touches_the_dom_when_it_changes():
    body = _fn("function wmSyncLock(")
    assert "if (wait === WM_LOCK_SHOWN) return;" in body,         "แตะ DOM ทุกเฟรม 60 ครั้งต่อวินาที"


def test_the_skill_panel_uses_the_same_lock():
    assert "const locked = wmWaiting();" in PLAY, "แผงสกิลใช้เงื่อนไขคนละชุดกับปุ่มอื่น"


def test_the_hud_names_whoever_is_acting_right_now():
    """d.turn บอกว่าเป็นตาเราแล้ว ทั้งที่จอยังเล่นภาพบอทเดินอยู่"""
    body = _fn("function wmPaintHud(")
    assert "WM_ANIM && d.fighters[WM_ANIM.fi]" in body, "บอกชื่อจาก d.turn ซึ่งสวนกับภาพบนจอ"
    assert "รอก่อน" in body, "ไม่ได้บอกผู้เล่นว่าต้องรอ"


def test_the_camera_snaps_to_the_bot_when_its_turn_starts():
    body = _fn("function wmQueueBot(")
    assert "wmFocus(WM_ST.fighters[bi], true)" in body,         "ตาบอทเริ่มแล้วกล้องยังค้างอยู่ที่เรา ไม่เห็นว่าบอททำอะไร"


# ── 25. ยิงแล้วกล้องต้องเกาะลูกกระสุน ──

def test_the_camera_follows_the_shell_in_flight():
    """เจ้าของเกมสั่ง: ยิงแล้วให้โฟกัสลูกกระสุนจนกว่าจะกระทบเป้า"""
    body = PLAY[PLAY.index("  if (WM_SHOT) {"):]
    body = body[:body.index(chr(10) + "  }")]
    assert "wmFocus({ x: p[0], y: p[1] })" in body, "ยิงแล้วกล้องไม่ตามลูกกระสุน"


def test_the_camera_is_not_yanked_back_while_the_shell_flies():
    """ยิงแล้วเทิร์นเปลี่ยนทันที ถ้าไม่กัน กล้องจะดีดกลับมาที่ตัวเราตั้งแต่กระสุนยังไม่ถึง"""
    body = PLAY[PLAY.index("function wmStartLoop("):PLAY.index("/** วาดนักสู้")]
    assert "!wmBusyFx() && turnKey !== WM_TURN_SHOWN" in body,         "กระสุนยังบินอยู่แต่กล้องดีดกลับไปหาคนที่ถึงตาแล้ว"


def test_a_melee_swing_shows_where_the_blow_lands():
    body = PLAY[PLAY.index("function wmSwing("):]
    body = body[:body.index(chr(10) + "}")]
    assert "wmFocus({" in body, "ฟันไกล ๆ แล้วไม่เห็นว่าหมัดลงตรงไหน"
    assert "a.aim" in body, "จุดที่มองไม่ได้อิงทิศที่ฟันจริง"


# ── 26. โดนหลายคน = ไล่โฟกัสทีละคน สรุปดาเมจทีละคน ──

def test_each_victim_gets_its_own_turn_on_camera():
    """เจ้าของเกมสั่ง: โดนหลายตัวให้กล้องโฟกัสทีละตัว แล้วคำนวณดาเมจทีละคน"""
    vic = _fn("function wmPlayVictims(")
    assert "order.forEach(v => wmStep(" in vic, "คนที่โดนแต่ละคนไม่ได้เป็นขั้นแยกกัน"
    assert "wmFxIdle" in vic, "ไม่ได้รอให้ขั้นก่อนหน้าเล่นจบก่อนไปคนถัดไป"
    one = _fn("function wmSettleVictim(")
    for hold in ("wmHoldOn(fi, 46, null)", "wmHoldOn(fi, 78, null)"):
        assert hold in one, f"ไม่ได้ค้างกล้องให้ทันดู ({hold})"


def test_several_hits_on_one_person_are_summed_into_one_number():
    """ดาบคู่แฝดฟันรัวสี่ครั้ง — ต้องขึ้นเลขรวมครั้งเดียว ไม่ใช่เด้งสี่ป้ายทับกัน"""
    vic = _fn("function wmPlayVictims(")
    assert "order.find(x => x.name === h.name)" in vic, "ไม่ได้ยุบหมัดหลายครั้งของคนเดียวกัน"
    assert "v.dmg += h.damage" in vic, "ไม่ได้รวมดาเมจ"


def test_the_death_animation_plays_at_that_persons_turn_on_camera():
    tail = _fn("function wmSettleVictim(")
    assert "wmDie(fi, f)" in tail, "ตายแล้วไม่เล่นภาพตายตอนกล้องจับอยู่ที่เขา"
    assert "WM_DEAD_SEEN[f.name]" in tail, "ประกาศตายซ้ำได้"
    assert tail.index("wmDie(fi, f)") < tail.index("wmHoldOn(fi, 78"),         "เล่นภาพตายหลังจากค้างกล้องไปแล้ว ผู้เล่นไม่ทันเห็น"


def test_a_chunk_can_carry_work_to_run_when_it_ends():
    """กลไกที่ทำให้ร้อยลำดับได้ — ท่อนจบแล้วทำงานต่อท้าย แล้วค่อยไปท่อนถัดไป"""
    body = PLAY[PLAY.index("function wmStartLoop("):PLAY.index("/** วาดนักสู้")]
    assert "const done = WM_ANIM.onEnd;" in body, "ท่อนไม่มีงานต่อท้าย"
    assert "if (done) done();" in body, "มีงานต่อท้ายแต่ไม่ได้เรียก"
    assert body.index("if (done) done();") < body.index("WM_ANIM = WM_QUEUE.shift() || null;", body.index("const done")),         "ไปท่อนถัดไปก่อนทำงานต่อท้าย — งานที่ต่อคิวเพิ่มจะถูกข้าม"


def test_the_camera_holds_on_the_impact_point_first():
    """พอกระทบให้โฟกัสจุดกระทบก่อน แล้วค่อยไล่ดูคนที่โดน"""
    body = PLAY[PLAY.index("    if (WM_SHOT.i >= WM_SHOT.path.length) {"):]
    body = body[:body.index(chr(10) + "    }")]
    assert "wmFocus({ x: p[0], y: p[1] }, true)" in body, "กระสุนถึงเป้าแล้วกล้องไม่ค้างที่จุดกระทบ"
    assert body.index("wmLand(shot.blast)") < body.index("wmPlayVictims("),         "ไล่ดูคนที่โดนก่อนที่ระเบิดจะขึ้น"


def test_the_shot_carries_the_whole_attack_for_the_victim_pass():
    body = _fn("function wmShowHit(")
    assert "atk: a" in body, "กระสุนไม่ได้พกผลทั้งก้อนไป ตอนกระทบเลยไม่รู้ว่าใครกระเด็นบ้าง"


def test_nobody_hit_means_no_queue():
    vic = _fn("function wmPlayVictims(")
    assert "if (!order.length) { if (done) done(); return false; }" in vic,         "ยิงพลาดไม่โดนใครก็ยังค้างคิวรอ"


# ── 27. ห้าม "อยู่ ๆ ก็ตกรอบ" จากพื้นหายใต้เท้า ──

def test_you_do_not_lose_early_by_standing_still(world):
    """เจ้าของเกมทัก: อยู่ ๆ ฉันก็ตกรอบ แพ้เอง

    ของเดิมที่พัง: ผู้เล่นยืนเฉย ๆ 40 เมล็ด จบเกมด้วยการตกน้ำ 27 ครั้ง
    ภายในราว 5 รอบ เพราะบอทยิงทะลุเกาะแล้ว _settle_everyone ปล่อยให้ร่วงลงทะเลทันที

    ⚠️ ที่วัดต้องเป็น "ตกน้ำเร็ว" ไม่ใช่ "ตกน้ำกี่ครั้ง" — เกาะโดนถล่มมาสิบกว่ารอบ
       แล้วพังจนไม่เหลือที่ยืนเป็นเรื่องปกติของเกมแนวนี้ ไม่ใช่บั๊ก
       (วัด 40 เมล็ด: ตกน้ำ 5 ครั้ง ที่รอบ 8/13/14/16/22 · เกมทั่วไปจบที่รอบ 9)
       เกณฑ์เดิมนับหัวอย่างเดียวบน 25 เมล็ด แคบเกินกว่าความผันผวนปกติ
    """
    drown = []
    for seed in range(1, 41):
        fresh(seed)
        for _ in range(30):
            st = match.load(UID)
            st["turn_started"] = 0
            match.save(UID, st)
            good, r = match.end_turn(UID, auto=True)
            if not good:
                break
            if r["fighters"][0]["dead"] or r["over"]:
                if "ตกน้ำ" in " ".join(r["log"][-8:]):
                    drown.append(r["round"])
                break
    early = [d for d in drown if d < 6]
    assert not early, f"ยังไม่ทันทำอะไรก็ตกน้ำแล้ว ที่รอบ {early} — เกาะไม่น่าพังเร็วขนาดนั้น"
    assert len(drown) <= 8, f"ยืนเฉย ๆ แล้วตกน้ำ {len(drown)}/40 เมล็ด (รอบ {drown}) เยอะเกินไป"


def test_the_ground_giving_way_lets_you_grab_a_ledge(world):
    """พื้นใต้เท้าหายแล้วต้องคว้าขอบใกล้ ๆ ก่อน ไม่ใช่ร่วงลงทะเลทันที"""
    fresh()
    g = [[T.AIR] * T.W for _ in range(T.H)]
    for x in range(300, 360):                       # แผ่นดินเล็ก ๆ ลอยเหนือน้ำ
        for y in range(200, 214):
            g[y][x] = T.ROCK
    st = match.load(UID)
    st["terrain"], st["props"] = T.encode(g), []
    st["fighters"][0].update(x=310, y=200)
    st["fighters"][1].update(x=350, y=200)
    match.save(UID, st)

    st = match.load(UID)
    grid = T.decode(st["terrain"])
    for y in range(200, 214):                       # เจาะพื้นใต้เท้าคนแรกให้หายเกลี้ยง
        for x in range(304, 318):
            grid[y][x] = T.AIR
    st["terrain"] = T.encode(grid)
    match._settle_everyone(st, grid)
    me = st["fighters"][0]
    assert not me["dead"], "พื้นหายแล้วร่วงลงทะเลตายทันที ทั้งที่มีขอบให้เกาะข้าง ๆ"
    assert P.standable(grid, me["x"], me["y"]), "รอดแต่ลอยอยู่กลางอากาศ"
    assert any("คว้าขอบ" in line for line in st["log"]), "ไม่ได้บอกผู้เล่นว่าเกิดอะไรขึ้น"


def test_with_nothing_to_grab_you_still_drown(world):
    """กันแก้เกินจนตกน้ำไม่ได้อีกเลย"""
    fresh()
    g = [[T.AIR] * T.W for _ in range(T.H)]
    for x in range(600, 660):            # มีแผ่นดินอยู่ แต่ไกลเกินกว่าจะคว้าถึง
        for y in range(200, 214):
            g[y][x] = T.ROCK
    st = match.load(UID)
    st["terrain"], st["props"] = T.encode(g), []
    st["fighters"][0].update(x=300, y=200)
    match.save(UID, st)
    st = match.load(UID)
    match._settle_everyone(st, T.decode(st["terrain"]))
    assert st["fighters"][0]["dead"], "ไม่มีอะไรให้เกาะเลยก็ยังไม่ตกน้ำ"


def test_the_islands_are_thick_enough_to_take_a_fireball(world):
    """เกาะบางกว่าหลุมไฟ = ยิงนัดเดียวทะลุ คนที่ยืนอยู่ร่วงทันที"""
    import statistics

    th = []
    for seed in range(1, 16):
        fresh(seed)
        st = match.load(UID)
        g = T.decode(st["terrain"])
        for f in st["fighters"]:
            n = 0
            for gy in range(f["y"], T.H - T.WATER):
                if not T.solid(g, f["x"], gy):
                    break
                n += 1
            th.append(n)
    assert statistics.median(th) >= 20,         f"พื้นใต้จุดเกิดหนากลาง ๆ แค่ {statistics.median(th):.0f} px"


# ── 28. เล่นภาพช้าลงให้ตามทัน ──

def test_the_shell_moves_a_fraction_of_a_step_per_frame():
    """เจ้าของเกมสั่ง: กระสุนต้องช้าและลื่น กล้องจะได้ตามทัน

    จุดในเส้นวิถีห่างกันได้ถึง 9 px ตอนชาร์จเต็ม เดินทีละจุดจึงยังกระตุก
    """
    import re as _re

    body = PLAY[PLAY.index("  if (WM_SHOT) {"):]
    body = body[:body.index(chr(10) + "  }")]
    assert "WM_SHOT.i + WM_SHOT_STEP" in body, "ยังเดินทีละจุดเต็ม ๆ"
    assert "k < 3 && WM_SHOT.i" not in body, "ยังข้ามทีละ 3 จุดอยู่"
    m = _re.search(r"WM_SHOT_STEP = ([\d.]+)", PLAY)
    assert m, "ไม่ได้ตั้งความเร็วกระสุน"
    assert float(m.group(1)) <= 0.5, f"เดินทีละ {m.group(1)} จุด เร็วเกินกว่ากล้องจะตามทัน"


def test_the_shell_position_is_smoothed_between_path_points():
    body = PLAY[PLAY.index("  if (WM_SHOT) {"):]
    body = body[:body.index(chr(10) + "  }")]
    assert "const mix = WM_SHOT.i - at;" in body, "ไม่ได้เกลี่ยตำแหน่งระหว่างจุด"
    assert "pa[0] + (pb[0] - pa[0]) * mix" in body, "ตำแหน่งที่วาดยังกระโดดทีละจุด"


def test_the_effects_linger_long_enough_to_read():
    import re as _re

    for pat, least, what in [(r"WM_BOOMS\.filter\(b => b\.t < (\d+)\)", 24, "ลูกไฟระเบิด"),
                             (r"WM_POPS\.filter\(p => p\.t < (\d+)\)", 60, "เลขดาเมจ"),
                             (r"WM_DYING\[i\] = (\d+);", 45, "ภาพตาย")]:
        m = _re.search(pat, PLAY)
        assert m, f"หาอายุของ{what}ไม่เจอ"
        assert int(m.group(1)) >= least, f"{what} อยู่แค่ {m.group(1)} เฟรม ดูไม่ทัน"


def test_the_fade_matches_the_lifetime():
    """จางเร็วกว่าที่อยู่จริง = หายไปก่อนถึงเวลา · ช้ากว่า = ดับวับตอนจบ"""
    import re as _re

    for life, fade, what in [(r"WM_BOOMS\.filter\(b => b\.t < (\d+)\)", r"\(b\.t \+= WM_DT\) / (\d+), r =", "ลูกไฟ"),
                             (r"WM_POPS\.filter\(p => p\.t < (\d+)\)", r"const k = \(p\.t \+= WM_DT\) / (\d+);", "เลขดาเมจ"),
                             (r"WM_BITS\.filter\(b => b\.t < (\d+)\)", r"\(1 - b\.t / (\d+)\)", "สะเก็ด")]:
        a, b = _re.search(life, PLAY), _re.search(fade, PLAY)
        assert a and b, f"หาอายุ/การจางของ{what}ไม่เจอ"
        assert a.group(1) == b.group(1),             f"{what} อยู่ {a.group(1)} เฟรม แต่จางตาม {b.group(1)} เฟรม"


def test_deferred_work_drains_even_with_nothing_animating():
    """เจ้าของเกมทัก: พอถึงตาของฉัน ฉันขยับไม่ได้ ทำอะไรไม่ได้

    ยิงพลาดไม่โดนใคร = งานถูกเข้าคิวทั้งที่ไม่มีภาพเล่นอยู่
    เดิมสะสางเฉพาะจังหวะที่ภาพเพิ่งเล่นจบ คิวเลยค้างตลอดกาล
    wmWaiting() ค้างเป็น true = ปุ่มทุกปุ่มถูกล็อกไปทั้งเกม
    """
    body = _fn("function wmTick(")
    assert "if (!WM_ANIM && WM_AFTER.length) {" in body,         "ไม่มีใครสะสางคิวงานตอนไม่มีภาพเล่นอยู่ — ล็อกค้างทั้งเกม"
    assert "while (WM_AFTER.length) WM_AFTER.shift()();" in body, "เช็คแล้วแต่ไม่ได้สะสาง"


# ── 29. ครบรอบแล้วเติมของ + เรือเหาะข้ามเกาะ ──

def _round_up(seed=7, rounds=6):
    """เล่นให้ครบหลายรอบแล้วคืนสถานะ"""
    fresh(seed)
    for _ in range(rounds * 2):
        st = match.load(UID)
        st["turn_started"] = 0
        match.save(UID, st)
        good, r = match.end_turn(UID, auto=True)
        if not good or r["over"]:
            break
    return match.load(UID)


def test_new_things_drop_in_as_rounds_go_by(world):
    """เจ้าของเกมสั่ง: ครบ 1 รอบ (ทุกคนเล่นครบ) ให้สปอนของใหม่"""
    fresh()
    before = len(match.load(UID)["props"])
    st = _round_up(rounds=6)
    assert st["round"] > 1, "เล่นไม่ครบรอบ — เทสตั้งฉากผิด"
    assert len(st["props"]) > before, f"ผ่านไป {st['round']} รอบแล้วของบนแผนที่ยังเท่าเดิม"
    assert any("ของใหม่" in line for line in st["log"]), "ไม่ได้บอกผู้เล่นว่ามีของลงสนาม"


def test_the_field_does_not_fill_up_forever(world):
    st = _round_up(rounds=14)
    assert match.DROP_MAX <= 20, f"เพดาน {match.DROP_MAX} ไม่ได้จำกัดอะไรเลย"
    assert len(st["props"]) <= match.DROP_MAX,         f"ของล้นสนาม {len(st['props'])} ชิ้น (เพดาน {match.DROP_MAX})"


def test_a_ferry_shows_up_to_cross_islands(world):
    """แผนที่เป็นเกาะลอย เดินข้ามแทบไม่ได้ — ต้องมีพาหนะให้"""
    assert "ferry" in T.PROPS, "ไม่มีเรือเหาะในรายการของบนแผนที่"
    seen = 0
    for seed in range(1, 9):
        st = _round_up(seed, rounds=5)
        seen += sum(1 for p in st["props"] if p["kind"] == "ferry")
    assert seen >= 4, f"เล่น 8 เมล็ดแล้วเจอเรือเหาะแค่ {seen} ลำ"


def test_riding_the_ferry_takes_you_somewhere_you_could_not_walk(world):
    """วาร์ปไปจุดที่เดินถึงอยู่แล้วก็ไม่ได้แก้ปัญหาข้ามเกาะ"""
    for seed in range(1, 12):
        st = _round_up(seed, rounds=5)
        fer = next((p for p in st["props"] if p["kind"] == "ferry"), None)
        if not fer:
            continue
        g = T.decode(st["terrain"])
        me = st["fighters"][0]
        me["dead"] = False
        start = (fer["x"], fer["y"])
        me["x"], me["y"] = start
        reach = P.walk_group(g, start)
        got = match._ride_ferry(st, g, me)
        if not got:
            continue                      # เมล็ดนี้ไม่มีเกาะอื่นให้ไป
        assert (me["x"], me["y"]) not in reach,             "เรือเหาะพาไปจุดที่เดินถึงอยู่แล้ว ไม่ได้ข้ามเกาะจริง"
        assert P.standable(g, me["x"], me["y"]), "ลงเรือแล้วลอยอยู่กลางอากาศ"
        assert not any(p["kind"] == "ferry" and p["x"] == start[0] for p in st["props"]),             "ขึ้นแล้วเรือยังอยู่ที่เดิม — ใช้ซ้ำได้ไม่จำกัด"
        assert any("เรือเหาะ" in line for line in st["log"])
        return
    pytest.skip("ไม่เจอเรือเหาะในเมล็ดที่ลอง")


def test_supply_drops_show_where_traps_are(world):
    """กติกาเหล็กกลับด้าน (08-27) — กับดักต้องหลุดไปให้เบราว์เซอร์วาด

    เดิมห้ามส่ง แต่เจ้าของเกมเคาะว่าเหยียบโดนของที่มองไม่เห็นคือโดนโกง
    ต้องเห็นแล้วกระโดดข้ามได้
    """
    st = _round_up(rounds=6)
    view = match.view(UID, st)
    traps = [p for p in view["props"] if p["kind"] == "trap"]
    assert traps, "ไม่ได้ส่งกับดักไปให้เบราว์เซอร์เลย วาดหลบไม่ได้"
    for t in traps:
        assert "x" in t and "y" in t, "ส่งกับดักไปแต่ไม่บอกตำแหน่ง"
    assert view["traps"] == len(traps), "จำนวนกับดักที่บอกไม่ตรงกับที่ส่งไป"

def test_the_page_draws_the_ferry_and_the_ride():
    worms = (WEB / "worms.js").read_text(encoding="utf-8")
    assert "p.kind === 'ferry'" in worms, "เรือเหาะไม่ถูกวาดบนแผนที่"
    assert "d.ferry" in PLAY, "ขึ้นเรือแล้วเว็บไม่รู้เรื่อง"
    body = PLAY[PLAY.index("async function wmDo("):PLAY.index("async function wmEndTurn(")]
    assert "wmFocus(WM_ST.fighters[mine], true)" in body, "ข้ามเกาะแล้วกล้องไม่ตามไป"


# ── 32. โดนตีกระเด็นทันที แต่ยังไม่คิดค่าเสียหาย ──

def test_the_knockback_starts_the_moment_the_hit_lands():
    """เจ้าของเกมสั่ง: เวลาโดนตีให้กระเด็นเลย แต่อย่าเพิ่งคิดค่าเสียหาย"""
    vic = _fn("function wmPlayVictims(")
    assert "const flying = wmPlayKnocks(knocks);" in vic, "ไม่ได้ปล่อยให้กระเด็นทันที"
    assert vic.index("wmPlayKnocks(knocks)") < vic.index("wmSettleVictim(v)"),         "คิดค่าเสียหายก่อนกระเด็น"


def test_the_knockback_is_not_queued_behind_a_gap():
    """กระเด็นต้องเริ่มตอนหมัดลง ไม่ใช่รอคิวเว้นจังหวะ 1 วิก่อน"""
    vic = _fn("function wmPlayVictims(")
    at = vic.index("const flying = wmPlayKnocks(knocks);")
    assert "wmStep(" not in vic[:at], "การกระเด็นถูกเอาไปต่อคิวข้างหลังขั้นอื่น"
    kn = _fn("function wmPlayKnocks(")
    assert "wmChunk(fi, k.path, null)" in kn, "ไม่ได้เล่นภาพกระเด็นเลย"
    assert "wmStep(" not in kn, "การกระเด็นยังต้องรอคิวขั้นตอนอยู่"


def test_everyone_hit_flies_at_once():
    """โดนระเบิดพร้อมกันหลายคนก็ต้องปลิวพร้อมกัน ไม่ใช่ปลิวทีละคน"""
    kn = _fn("function wmPlayKnocks(")
    assert "(knocks || []).forEach" in kn, "ไม่ได้ปล่อยกระเด็นทุกคนที่โดน"


def test_the_damage_waits_until_everyone_has_landed():
    vic = _fn("function wmPlayVictims(")
    assert "if (flying) wmStep(() => {}, wmFxIdle);" in vic,         "ไม่ได้รอให้ทุกคนตกถึงพื้นก่อนเริ่มคิดค่าเสียหาย"
    at = vic.index("if (flying) wmStep(() => {}, wmFxIdle);")
    assert vic.index("wmSettleVictim(v)") > at, "คิดค่าเสียหายตั้งแต่ยังปลิวอยู่กลางอากาศ"


def test_settling_no_longer_replays_the_knockback():
    """แยกกันแล้ว — ขั้นสรุปผลต้องไม่เล่นภาพกระเด็นซ้ำอีกรอบ"""
    one = _fn("function wmSettleVictim(")
    assert "wmChunk(" not in one, "ขั้นสรุปผลยังเล่นภาพกระเด็นซ้ำ"
    assert "WM_POPS.push" in one, "ขั้นสรุปผลไม่ได้เด้งเลขดาเมจ"


def test_hiding_the_result_panel_lets_it_come_back():
    """เจ้าของเกมเจอ: กดยอมแพ้ ตัวระเบิด สถานะขึ้น "จบแล้ว" แต่ผลแพ้ชนะไม่ขึ้น

    wmApply เรียก wmPaintOver ก่อนที่ระเบิดจะถูกต่อคิว ตอนนั้นยังว่าง
    แผงเลยโชว์แล้วติดธง "โชว์แล้ว" · พอระเบิดมาถึง แผงถูกซ่อน
    แล้วธงกันโชว์ซ้ำทำให้ไม่มีวันกลับมาโชว์อีก
    """
    body = _fn("function wmPaintOver(")
    assert "box.hidden = true; WM_OVER_SHOWN = false; return;" in body,         "ซ่อนแผงเพราะยังมีภาพเล่นอยู่ แต่ไม่ได้ล้างธง — แผงจะไม่กลับมาอีกเลย"


def test_the_result_panel_still_paints_only_once_when_it_shows():
    """กันแก้เกินจนวาดใหม่ทุกเฟรม"""
    body = _fn("function wmPaintOver(")
    assert "WM_OVER_SHOWN = !idle;" in body, "โชว์แล้วไม่ได้ติดธง จะวาดซ้ำทุกเฟรม"
    assert body.index("WM_OVER_SHOWN = false; return;") < body.index("WM_OVER_SHOWN = !idle;"),         "ลำดับสลับกัน — ธงจะถูกล้างหลังติด"
