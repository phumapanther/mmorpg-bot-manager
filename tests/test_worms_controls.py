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


# ── 5. เดินแล้วขาต้องขยับ พื้นต้องไม่ลื่น ──

def test_a_walking_fighter_uses_a_walking_pose():
    """ยืนท่าเดิมแล้วเลื่อนตัวไป = เห็นเป็นลื่นไถลไปกับพื้น"""
    body = PLAY[PLAY.index("function wmDrawFighter("):]
    body = body[:body.index(chr(10) + "}")]
    assert "'run1'" in body and "'run2'" in body, "เดินแล้วยังใช้ท่ายืนเฉย ๆ"
    assert "WM_ANIM.i % 2" in body, "สลับขาไม่ตามก้าวจริง"


def test_the_camera_only_follows_near_the_edge():
    """ตามทุกเฟรม = ตัวค้างกลางจอ พื้นไหลข้างใต้ เห็นเป็นพื้นลื่น"""
    body = PLAY[PLAY.index("function wmFocus("):]
    body = body[:body.index(chr(10) + "}")]
    assert "force || x < mx" in body, "กล้องยังตามติดทุกเฟรม ไม่ได้เช็คว่าใกล้ขอบจอหรือยัง"
    assert "WM_CAM.center" in body, "ไม่มีทางเลื่อนกล้องกลับมาที่ตัวเลย"


def test_the_camera_follows_whoever_is_moving():
    """ตอนบอทเดิน กล้องเกาะตัวเราอยู่ก็ไม่เห็นว่าบอททำอะไร"""
    assert "wmFocus(af)" in PLAY, "กล้องไม่ตามคนที่กำลังขยับ"


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
    assert "WM_ST.turn !== WM_TURN_SHOWN" in body, "เปลี่ยนตาแล้วกล้องไม่ตามไปหาคนที่ถึงตา"
    assert "wmFocus(wmMe(), true)" in body, "ตามแบบไม่บังคับ — ถ้าตัวอยู่กลางจอพอดีก็ไม่ขยับ"
    assert "!WM_ANIM &&" in body, "ตัดกล้องทั้งที่ภาพเดินยังเล่นค้างอยู่"


def test_a_new_match_forgets_which_turn_was_focused():
    body = PLAY[PLAY.index("function wmApply("):PLAY.index("function wmMe(")]
    assert "WM_TURN_SHOWN = -1;" in body,         "เปิดสนามใหม่แล้วยังจำตาเก่า กล้องเลยไม่ยอมจัดให้"


# ── 10. จบเกมแล้วสรุปผล ──

def _finish(cls="Warrior"):
    """ตีจนจบเกมจริง ๆ แล้วคืนสถานะสุดท้าย"""
    fresh()
    for _ in range(60):
        good, r = match.attack(UID, "basic")
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
    assert "d.standings" in rows, "ตารางอันดับว่างเปล่า ไม่ได้วนของจริงมาวาด"
    for col in ("r.rank", "r.name", "r.dealt", "r.kills", "r.hp"):
        assert col in rows, f"ตารางไม่มีช่อง {col}"
    assert "wmAgain" in body and "wmQuit" in body, "ไม่มีให้เลือกว่าจะเล่นต่อหรือจบ"
    assert "wmNewMatch(0)" in body, "ปุ่มเล่นอีกรอบไม่ได้เปิดสนามใหม่"
    assert 'wmOver' in HTML, "ไม่มีที่วางแผงสรุปในหน้าเว็บ"


def test_the_scoreboard_only_shows_when_the_match_is_over():
    body = PLAY[PLAY.index("function wmPaintOver("):]
    body = body[:body.index(chr(10) + "}")]
    assert "box.hidden = !d || !d.over" in body, "แผงสรุปโผล่ตั้งแต่ยังเล่นอยู่"
    assert "wmPaintOver()" in PLAY.split("function wmPaintOver(")[0] or         PLAY.count("wmPaintOver()") >= 1, "เขียนแล้วไม่มีใครเรียก"
