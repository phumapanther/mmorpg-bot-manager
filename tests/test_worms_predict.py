"""🏃 เบราว์เซอร์เดินเองได้ทันนิ้ว แต่เซิร์ฟเวอร์ยังเป็นคนตัดสิน

เซิร์ฟเวอร์อยู่หลัง Cloudflare tunnel วัดแล้วไปกลับครั้งละ ~300 ms
โมเดลเดิม (กด → ถามเซิร์ฟเวอร์ → รอ → เล่นภาพ) จึงได้ 6 พิกเซล/ครึ่งวินาที
และปล่อยนิ้วแล้วตัวยังเดินต่อ — เอาไม่อยู่เลย

ทางแก้คือให้เบราว์เซอร์ "เดาไว้ก่อน" ด้วยกฎชุดเดียวกัน แล้วเซิร์ฟเวอร์ตามมายืนยัน
(hedgewars ใช้ธงปุ่มที่กดค้างแล้วขยับทุก 8 ms — uGearsHedgehog.pas:920)

จุดที่พังแล้วเจ็บที่สุด:
  1. **กฎสองฝั่งเพี้ยนจากกัน** = ตัวละครกระตุกไปมาตลอดเวลา (rubber-band)
     ไฟล์นี้จึงบังคับให้ผลตรงกันเป๊ะทุกพิกเซล
  2. API เผลอรับพิกัดจากเบราว์เซอร์ = เปิด devtools แล้ววาร์ปได้ทันที
"""
import json
import pathlib
import random
import shutil
import subprocess
import tempfile

import pytest

from bot.pvp import physics as P, terrain as T
from tests import conftest

WEB = pathlib.Path("license_server/web_static")
WALK_JS = (WEB / "walk.js").read_text(encoding="utf-8")
PLAY = conftest.play_js_source()
HTML = (WEB / "play.html").read_text(encoding="utf-8")

RULES = {"ch_h": T.CH_H, "foot_w": P.FOOT_W, "climb": P.CLIMB,
         "step_max": P.STEP_MAX, "water": T.WATER,
         "gravity": P.GRAVITY, "jump_vx": P.JUMP_VX, "jump_vy": P.JUMP_VY,
         "jump_curve": P.JUMP_CURVE, "air_accel": P.AIR_ACCEL,
         "air_max": P.AIR_MAX, "sink": P.SINK_DEPTH}
# (ค่ากระโดดยังส่งไปด้วยเผื่ออนาคต — ฝั่งจอไม่ได้ใช้แล้ว ดูหัวไฟล์ walk.js)


def _run_js(grid, cases, kind="walk"):
    """รัน walk.js ตัวจริงด้วย node แล้วคืนผลของแต่ละเคส"""
    if not shutil.which("node"):
        pytest.skip("เครื่องนี้ไม่มี node")
    with tempfile.TemporaryDirectory() as tmp:
        f = pathlib.Path(tmp) / "job.json"
        f.write_text(json.dumps({"w": T.W, "h": T.H, "rules": RULES, "kind": kind,
                                 "grid": [v for row in grid for v in row],
                                 "cases": cases}), encoding="utf-8")
        out = subprocess.run(["node", "tests/walk_check.js", str(f)],
                             capture_output=True, text=True, encoding="utf-8")
        assert out.returncode == 0, out.stderr
        return json.loads(out.stdout.strip().splitlines()[-1])


@pytest.mark.parametrize("seed", [3, 11, 27, 42])
def test_both_sides_walk_to_exactly_the_same_pixel(seed):
    """กฎเดินมีสองชุด (Python + JS) — ต่างกันแม้พิกเซลเดียวก็เห็นเป็นตัวกระตุก

    กวาดทั้งเดินราบ ปีนขั้น ตกหน้าผา ชนกำแพง และขอบน้ำ ในแผนที่จริง
    """
    rng = random.Random(seed)
    grid = T.generate(seed)["grid"]
    spots = T._open_spots(grid)
    cases = []
    for _ in range(150):
        x, y = rng.choice(spots)
        cases.append([x, y, rng.choice([-1, 1]), rng.randint(1, P.STEP_MAX),
                      rng.random() < .5])

    js = _run_js(grid, cases)
    for c, j in zip(cases, js):
        x, y, d, n, nd = c
        py = P.walk(grid, x, y, d, n, no_drown=nd)
        assert (py["x"], py["y"], py["drowned"]) == (j["x"], j["y"], j["drowned"]), (
            f"เมล็ด {seed}: เริ่ม ({x},{y}) ทิศ {d} {n} ก้าว no_drown={nd} — "
            f"python ไป ({py['x']},{py['y']}) จม={py['drowned']} · "
            f"js ไป ({j['x']},{j['y']}) จม={j['drowned']}")


def test_both_sides_agree_on_the_nasty_edges():
    """ด่านที่เคยพังมาแล้วทั้งนั้น — ขอบน้ำ ขั้นสูงเกินปีน กำแพงตัน เดินลงผา"""
    g = [[T.AIR] * T.W for _ in range(T.H)]
    for x in range(100, 300):                       # เกาะซ้าย
        for y in range(150, T.H - T.WATER):
            g[y][x] = T.ROCK
    for x in range(320, 420):                       # เกาะขวา ต่ำกว่า = เดินลงผา
        for y in range(200, T.H - T.WATER):
            g[y][x] = T.ROCK
    for y in range(150 - P.CLIMB, 150):             # ขั้นเตี้ยพอปีนได้
        for x in range(250, 300):
            g[y][x] = T.ROCK
    for y in range(100, 150):                       # กำแพงสูงเกินปีน
        for x in range(200, 204):
            g[y][x] = T.ROCK
    # 🌿 พุ่มไม้คลุมทางเดิน — ใบไม้ต้องลอดได้ ลำต้นต้องกั้น
    #    (เคยพลาดฝั่งเซิร์ฟเวอร์มาแล้ว: นับใบไม้เป็นกำแพง ต้นไม้ตัดเกาะขาดเป็นท่อน)
    for y in range(150 - T.CH_H, 150):
        for x in range(150, 170):
            g[y][x] = T.LEAF
    for y in range(150 - T.CH_H, 150):
        for x in range(175, 178):
            g[y][x] = T.TRUNK

    cases = []
    for x in (110, 140, 155, 165, 172, 180, 195, 205, 245, 255, 295, 299, 310, 330, 415):
        for d in (-1, 1):
            for nd in (True, False):
                cases.append([x, 150 if x < 300 else 200, d, 30, nd])
    js = _run_js(g, cases)
    for c, j in zip(cases, js):
        x, y, d, n, nd = c
        py = P.walk(g, x, y, d, n, no_drown=nd)
        assert (py["x"], py["y"], py["drowned"]) == (j["x"], j["y"], j["drowned"]), (
            f"เริ่ม ({x},{y}) ทิศ {d} no_drown={nd} — "
            f"python ({py['x']},{py['y']}) · js ({j['x']},{j['y']})")


# ── ค่าคงที่ต้องมาจากเซิร์ฟเวอร์ ไม่ใช่ฝังไว้ในไฟล์ JS ──

def test_the_browser_never_hardcodes_the_rules():
    """ฝังตัวเลขไว้สองที่ = วันหนึ่งแก้ที่เดียวแล้วสองฝั่งเพี้ยนเงียบ ๆ"""
    for num in (str(T.CH_H), str(P.CLIMB), str(P.STEP_MAX), str(T.WATER)):
        body = WALK_JS[WALK_JS.index("const WALK"):]
        assert f"= {num}" not in body, f"ฝังเลข {num} ไว้ในเบราว์เซอร์"
    for key in ("ch_h", "foot_w", "climb", "step_max", "water"):
        assert f"r.{key}" in WALK_JS, f"ไม่ได้ใช้ {key} ที่เซิร์ฟเวอร์ส่งมา"


def test_the_server_sends_the_rules(tmp_path, monkeypatch):
    import bot.models.player_model as pm
    from bot.pvp import match
    from license_server import web_db

    monkeypatch.setattr(pm, "DB_NAME", str(tmp_path / "g.db"))
    monkeypatch.setattr(web_db, "DB_PATH", tmp_path / "w.db")
    pm.init_db()
    pm.get_player(7101)
    st = match.new_practice(7101, {"race": "Human", "cls": "Warrior",
                                   "armor": "None", "weapon": ""}, seed=5)
    got = match.view(7101, st)["rules"]
    assert got == RULES, f"ค่าที่ส่งไปไม่ตรงกับของจริง: {got}"


def test_the_page_loads_the_walk_rules():
    assert '<script src="/walk.js"></script>' in HTML, "หน้าเว็บไม่ได้โหลดกฎการเดิน"

# ── กดแล้วต้องขยับทันที และปล่อยแล้วต้องหยุด ──

def _hold(ping=300, hold_ms=1500, moves=60):
    """จำลองกดค้างเดินด้วยฟังก์ชันของจริง เทียบโมเดลเดิมกับโมเดลใหม่"""
    if not shutil.which("node"):
        pytest.skip("เครื่องนี้ไม่มี node")
    grid = [[T.AIR] * T.W for _ in range(T.H)]
    for x in range(T.W):
        for y in range(200, T.H - T.WATER):
            grid[y][x] = T.ROCK
    job = {"w": T.W, "h": T.H, "grid": [v for row in grid for v in row],
           "rules": RULES, "x": 100, "y": 200, "dir": 1, "moves": moves,
           "ping": ping, "holdMs": hold_ms, "walkTicks": 3, "sendMs": 250,
           "oldSteps": 6, "animMs": 500}
    with tempfile.TemporaryDirectory() as tmp:
        f = pathlib.Path(tmp) / "j.json"
        f.write_text(json.dumps(job), encoding="utf-8")
        out = subprocess.run(["node", "tests/predict_loop.js", str(f)],
                             capture_output=True, text=True, encoding="utf-8")
        assert out.returncode == 0, out.stderr
        return json.loads(out.stdout.strip().splitlines()[-1])


def test_the_character_moves_on_the_very_next_frame():
    """เซิร์ฟเวอร์อยู่หลัง tunnel วัดจริง ~300 ms — รอคำตอบก่อนขยับคือคุมไม่ได้

    โมเดลเดิมขยับครั้งแรกช้ากว่านิ้วเต็ม ๆ หนึ่ง ping
    """
    r = _hold()
    assert r["predicted"]["firstMoveAt"] < 60,         f"กดแล้วกว่าจะขยับใช้เวลา {r['predicted']['firstMoveAt']:.0f} ms"
    assert r["old"]["firstMoveAt"] >= 250, "โมเดลเดิมไม่ได้ช้าอย่างที่วัดไว้ — เทสนี้วัดผิดแล้ว"


def test_letting_go_stops_the_character_where_you_let_go():
    """โมเดลเดิม: ปล่อยนิ้วแล้วก้อนที่ยิงไปยังเดินต่ออีก 6 ก้าว — เล็งจุดยืนไม่ได้เลย"""
    r = _hold()
    assert r["old"]["overshoot"] > 0, "โมเดลเดิมไม่ได้เดินเลยอย่างที่วัดไว้ — เทสนี้วัดผิดแล้ว"
    # โมเดลใหม่หยุดที่ก้าวสุดท้ายที่กดจริง ไม่มีก้อนค้างท่อ
    assert r["predicted"]["x"] == r["predicted"]["serverX"],         "จอกับเซิร์ฟเวอร์ลงเอยคนละที่ = ตัวจะกระตุกตอนคำตอบมาถึง"


def test_the_screen_and_the_server_end_up_on_the_same_pixel():
    """หัวใจของการเดาไว้ก่อน: เดาผิดเมื่อไหร่ผู้เล่นเห็นตัวกระตุกทันที"""
    for ping in (50, 150, 300, 600):
        r = _hold(ping=ping)
        assert r["predicted"]["x"] == r["predicted"]["serverX"],             f"ที่ ping {ping} ms จอไปถึง {r['predicted']['x']} "             f"แต่เซิร์ฟเวอร์ว่า {r['predicted']['serverX']}"


def test_walking_never_spends_more_energy_than_the_turn_has():
    """แรงเดินหมดต้องหยุดเอง ไม่ใช่เดินต่อแล้วให้เซิร์ฟเวอร์ปฏิเสธทีหลัง"""
    r = _hold(hold_ms=6000, moves=12)
    assert r["predicted"]["sent"] <= 12,         f"ส่งไป {r['predicted']['sent']} ก้าว ทั้งที่มีแรงแค่ 12"


# ── ยังโกงไม่ได้ ──

def test_the_api_still_never_takes_a_position():
    """เดาฝั่งจอได้ แต่ห้ามหลุดให้ส่งพิกัดมา — ไม่งั้นเปิด devtools แล้ววาร์ป"""
    api = conftest.web_api_source()
    body = api[api.index("class WormsBody"):api.index('@router.post("/pvp/worms/match")')]
    for leaked in ("x:", "y:", "pos", "hp", "damage"):
        assert leaked not in body, f"API รับ {leaked} จากเบราว์เซอร์"
    assert "steps" in body, "API ไม่รับจำนวนก้าว"


def test_the_screen_always_yields_to_the_server():
    """ทาบแล้วต้องเชื่อเซิร์ฟเวอร์เสมอ ห้ามมีเงื่อนไข 'ถ้าต่างนิดเดียวใช้ของจอ'"""
    body = PLAY[PLAY.index("function wmReconcile("):]
    body = body[:body.index(chr(10) + "}" + chr(10))]
    assert "f.x = spot.x; f.y = spot.y;" in body, "ไม่ได้เอาตำแหน่งของเซิร์ฟเวอร์มาใช้"
    assert "WALK.walk(" in body, "ไม่ได้เดินก้าวที่ค้างอยู่ต่อจากตำแหน่งจริง"


def test_the_walk_budget_comes_from_the_server_every_batch():
    """จอนับแรงเดินเองระหว่างก้าว แต่ทุกก้อนที่ยืนยันต้องเอาของเซิร์ฟเวอร์มาทับ"""
    body = PLAY[PLAY.index("async function wmDo("):]
    body = body[:body.index(chr(10) + "}" + chr(10))]
    assert "WM_ST = { ...d };" in body, "ไม่ได้เอาสถานะจากเซิร์ฟเวอร์มาทับทั้งก้อน"


def test_falling_off_a_ledge_is_animated_not_teleported():
    """เดินตกหน้าผาแล้ววาปลงพื้นทันที = สิ่งที่เจ้าของเกมบ่นมาตลอด"""
    body = PLAY[PLAY.index("function wmWalkTick("):]
    body = body[:body.index(chr(10) + "}" + chr(10))]
    assert "wmChunk(" in body, "ตกหน้าผาแล้วไม่มีภาพร่วง — วาปลงพื้นเลย"

# ── 🔋 แรงเดินสองฝั่งต้องตรงกัน ไม่งั้นค้างทั้งเทิร์น ──

@pytest.mark.parametrize("seed", [3, 11, 27])
def test_both_sides_charge_the_same_energy(seed):
    """เจ้าของเกมเจอ: หมดแรงแล้วไม่จบเทิร์นเอง · ยังไม่หมดแรงแต่ขยับไม่ได้

    ต้นเหตุ: จอหักแรงทุกครั้งที่พยายามก้าว แม้ชนกำแพง แต่เซิร์ฟเวอร์หัก
    max(ก้าวที่เดินได้จริง, 1) "ต่อหนึ่งคำขอ" — กดค้างดันกำแพงแล้วจอคิดว่าแรงหมด
    ทั้งที่เซิร์ฟเวอร์ยังเหลือเยอะ จอเลยหยุดส่งคำสั่ง เซิร์ฟเวอร์ไม่มีทางรู้ว่า
    ต้องจบเทิร์น = กดอะไรไม่ได้เลยทั้งเทิร์น
    """
    rng = random.Random(seed * 17)
    grid = T.generate(seed)["grid"]
    spots = T._open_spots(grid)
    cases = [[*rng.choice(spots), rng.choice([-1, 1]), rng.randint(1, 8), True]
             for _ in range(150)]
    js = _run_js(grid, cases)
    for c, j in zip(cases, js):
        x, y, d, n, _ = c
        py = P.walk(grid, x, y, d, n, no_drown=True)
        server = max(py["steps"], 1)              # กติกาหักแรงของ match.move()
        screen = max(j["steps"], 1)               # กติกาที่ walk.js ต้องทำตาม
        assert server == screen, (
            f"เมล็ด {seed}: เดินจาก ({x},{y}) ทิศ {d} ขอ {n} ก้าว — "
            f"เซิร์ฟเวอร์หัก {server} แต่จอหัก {screen}")


def test_the_screen_charges_once_when_it_hits_a_wall():
    """ดันกำแพงค้างไว้ต้องเสียแรงก้อนละ 1 ไม่ใช่ทุกเฟรมที่พยายามก้าว"""
    body = PLAY[PLAY.index("function wmWalkTick("):]
    body = body[:body.index(chr(10) + "}" + chr(10))]
    assert "if (!WM_PRED.pending) { WM_ST.moves--; WM_PRED.pending++; }" in body,         "ชนกำแพงแล้วยังหักแรงทุกครั้งที่พยายามก้าว"


def test_the_screen_never_decides_the_turn_is_over_by_itself():
    """จอคิดว่าแรงหมดได้ แต่ต้องถามเซิร์ฟเวอร์เสมอ ไม่ใช่เงียบไปเฉย ๆ

    เงียบเมื่อไหร่ = เซิร์ฟเวอร์ไม่รู้ว่าต้องจบเทิร์น ผู้เล่นค้างทั้งเทิร์น
    """
    body = PLAY[PLAY.index("function wmWalkTick("):]
    body = body[:body.index(chr(10) + "}" + chr(10))]
    assert "WM_ST.moves <= 0 && !WM_PRED.pending && !WM_PRED.probed" in body,         "จอคิดว่าแรงหมดแล้วหยุดส่งคำสั่งเลย เซิร์ฟเวอร์ไม่มีทางรู้"


def test_a_jump_with_no_energy_says_so(): 
    """กดกระโดดแล้วเงียบ = ผู้เล่นนึกว่าปุ่มเสีย (เจ้าของเกมเจอ: โดนตีแล้วกระโดดไม่ได้)"""
    body = PLAY[PLAY.index("function wmJumpFire("):]
    body = body[:body.index(chr(10) + "}" + chr(10))]
    assert "toast(" in body, "แรงไม่พอกระโดดแล้วไม่บอกอะไรเลย"


# ── ⏱️ นาฬิกาฝั่งเซิร์ฟเวอร์ต้องหยุดตอนผู้เล่นนั่งดูภาพ ──

def _match(tmp_path, monkeypatch, uid=7301):
    import bot.models.player_model as pm
    from bot.pvp import match
    from license_server import web_db

    monkeypatch.setattr(pm, "DB_NAME", str(tmp_path / "g.db"))
    monkeypatch.setattr(web_db, "DB_PATH", tmp_path / "w.db")
    pm.init_db()
    pm.get_player(uid)
    match.new_practice(uid, {"race": "Human", "cls": "Warrior",
                             "armor": "None", "weapon": ""}, seed=7)
    return match, uid


def test_time_spent_watching_the_bot_is_not_charged_to_your_turn(tmp_path, monkeypatch):
    """เจ้าของเกมเจอ: ขึ้นหมดเวลาทั้งที่บนจอยังเหลือเวลา

    ฝั่งเว็บหยุดนาฬิกาบนจอตอนเล่นภาพ (ตามที่สั่งไว้) แต่ฝั่งเซิร์ฟเวอร์ยังเดินอยู่
    ตาบอทเดิน + ของลงสนาม + ร่างระเบิด กินเวลาได้หลายสิบวินาที
    """
    import time

    match, uid = _match(tmp_path, monkeypatch)
    st = match.load(uid)
    st["turn_started"] = time.time() - 20
    st["anim_sent_at"] = time.time() - 20        # นั่งดูภาพมา 20 วิ
    match.save(uid, st)
    assert match.time_left(match.load(uid)) >= match.TURN_SECONDS - 1,         "เวลาที่นั่งดูภาพถูกหักจากเทิร์นของผู้เล่น"


def test_the_grace_has_a_ceiling(tmp_path, monkeypatch):
    """เปิดจอทิ้งไว้เฉย ๆ ห้ามได้เวลาฟรีไม่จำกัด ทั้งห้องจะค้าง"""
    import time

    match, uid = _match(tmp_path, monkeypatch)
    st = match.load(uid)
    st["turn_started"] = time.time() - 3600
    st["anim_sent_at"] = time.time() - 3600
    match.save(uid, st)
    assert match.time_left(match.load(uid)) == 0,         f"ทิ้งไว้ชั่วโมงหนึ่งแล้วยังไม่หมดเวลา (เพดาน {match.ANIM_GRACE} วิ)"


def test_acting_gives_the_watched_time_back(tmp_path, monkeypatch):
    """สั่งอะไรมา = ดูภาพจบแล้ว ต้องคืนเวลาที่นั่งดูให้เขาถาวร ไม่ใช่คืนชั่วคราว"""
    import time

    match, uid = _match(tmp_path, monkeypatch)
    st = match.load(uid)
    st["turn_started"] = time.time() - 15
    st["anim_sent_at"] = time.time() - 15
    match.save(uid, st)
    ok, _ = match.move(uid, "walk", 1, 1)
    assert ok
    st = match.load(uid)
    assert st["anim_sent_at"] == 0, "สั่งไปแล้วยังค้างสถานะนั่งดูภาพอยู่"
    assert match.time_left(st) >= match.TURN_SECONDS - 2, "คืนเวลาที่นั่งดูไม่ครบ"


def test_a_new_turn_starts_the_clock_clean(tmp_path, monkeypatch):
    """เปลี่ยนตาแล้วต้องล้างสถานะนั่งดูภาพ ไม่งั้นตาถัดไปได้เวลาฟรีติดมาด้วย"""
    import time

    match, uid = _match(tmp_path, monkeypatch)
    st = match.load(uid)
    st["anim_sent_at"] = time.time() - 25
    match.save(uid, st)
    match.end_turn(uid)
    assert match.load(uid)["anim_sent_at"] in (0, None) or         match.load(uid).get("anim_sent_at", 0) >= time.time() - 1,         "ตาใหม่แล้วยังถือสถานะนั่งดูภาพของตาเก่า"


def test_the_clock_pauses_only_when_there_is_something_to_watch(tmp_path, monkeypatch):
    """ไม่มีภาพให้ดูก็ต้องนับเวลาตามปกติ ไม่งั้นเทิร์นไม่มีวันหมด"""
    import time

    match, uid = _match(tmp_path, monkeypatch)
    st = match.load(uid)
    st["turn_started"] = time.time() - 20
    st["anim_sent_at"] = 0
    match.save(uid, st)
    left = match.time_left(match.load(uid))
    assert left <= match.TURN_SECONDS - 19, f"ไม่มีภาพให้ดูแต่นาฬิกาไม่เดิน (เหลือ {left})"

def test_falling_does_not_eat_your_whole_turn():
    """เดินตกผาเคยเสียแรงตามจำนวนพิกเซลที่ร่วง — ตก 74 px = เสียแรง 82 จากที่มี 60

    ก้าวพลาดหนึ่งก้าวจบเทิร์นทันที และฝั่งจอเดาตามไม่ได้เลยเพราะไม่รู้ว่าจะร่วงกี่พิกเซล
    (ในเกมแนวนี้การตกไม่ใช่ "ออกแรงเดิน" อยู่แล้ว — เจ็บจากการตกคิดแยกต่างหาก)
    """
    g = [[T.AIR] * T.W for _ in range(T.H)]
    for x in range(100, 300):
        for y in range(120, T.H - T.WATER):
            g[y][x] = T.ROCK
    for x in range(300, 500):                    # เกาะขวาต่ำกว่า 80 px
        for y in range(200, T.H - T.WATER):
            g[y][x] = T.ROCK
    r = P.walk(g, 295, 120, 1, 8, no_drown=True)
    assert r["y"] == 200, "ไม่ได้ตกลงไปเกาะล่างจริง"
    assert len(r["path"]) > 60, "เทสนี้ต้องเป็นเคสที่ร่วงยาว ๆ ถึงจะวัดอะไรได้"
    assert r["steps"] <= 8, f"ก้าวได้จริง {r['steps']} ก้าว แต่ขอไปแค่ 8"
    assert max(r["steps"], 1) < 20,         f"ตกผาแล้วคิดแรง {r['steps']} — ยังคิดตามพิกเซลที่ร่วงอยู่"

def test_a_real_walk_off_a_cliff_barely_costs_energy(tmp_path, monkeypatch):
    """ไล่ผ่าน match.move() ของจริง ไม่ใช่คิดสูตรเองแล้วเทียบกับสูตรตัวเอง

    ⚠️ ต้องใช้หน้าผาที่ "ตกแล้วไม่เจ็บ" (ต่ำกว่า FALL_HURT_FROM) — ตกแล้วเจ็บเมื่อไหร่
       เซิร์ฟเวอร์จบเทิร์นให้ทันทีแล้วรีเซ็ตแรงเต็ม วัดค่าที่หักไปไม่ได้เลย
    """
    match, uid = _match(tmp_path, monkeypatch, uid=7401)
    drop = P.FALL_HURT_FROM - 5
    g = [[T.AIR] * T.W for _ in range(T.H)]
    for x in range(100, 300):
        for y in range(120, T.H - T.WATER):
            g[y][x] = T.ROCK
    for x in range(300, 500):
        for y in range(120 + drop, T.H - T.WATER):
            g[y][x] = T.ROCK
    st = match.load(uid)
    st["terrain"] = T.encode(g)
    st["props"] = []
    st["fighters"][0].update(x=295, y=120, face=1, hp=100)
    st["fighters"][1].update(x=450, y=120 + drop)
    match.save(uid, st)

    before = match.load(uid)["moves"]
    ok, r = match.move(uid, "walk", 1, 8)
    assert ok, r.get("error")
    assert not r.get("auto_ended"), "ตกแล้วเจ็บจนจบเทิร์น — วัดแรงที่หักไม่ได้ ปรับความสูงหน้าผา"
    assert r["fighters"][0]["y"] == 120 + drop, "ไม่ได้ตกลงเกาะล่างจริง"
    assert len(r["move"]["path"]) > 30, "เคสนี้ต้องมีพิกเซลร่วงเยอะ ๆ ถึงจะวัดอะไรได้"
    spent = before - r["moves"]
    assert spent <= 8, (
        f"เดินตกผา 8 ก้าวแล้วเสียแรง {spent} (พิกเซลที่ร่วง {len(r['move']['path'])}) "
        "— ยังคิดแรงตามพิกเซลที่ร่วงอยู่")


def test_a_bot_turn_response_pauses_the_clock(tmp_path, monkeypatch):
    """ตอบพร้อมภาพให้ดูแล้วต้องหยุดนาฬิกา ไม่งั้นคืนเวลาไม่ได้เพราะไม่รู้ว่าเริ่มดูตอนไหน"""
    match, uid = _match(tmp_path, monkeypatch, uid=7402)
    st = match.load(uid)
    st["turn_started"] = 0                  # บังคับให้หมดเวลาแล้วจะได้สลับตาจริง
    match.save(uid, st)
    ok, r = match.end_turn(uid, auto=True)
    assert ok
    st = match.load(uid)
    played = (r.get("bot_moves") or []) or st.get("drops")
    if not played:
        pytest.skip("ตานี้บอทไม่ได้ทำอะไรและไม่มีของลง")
    assert st.get("anim_sent_at"),         "ส่งภาพไปให้ดูแล้วแต่ไม่ได้หยุดนาฬิกา — เดี๋ยวขึ้นหมดเวลาทั้งที่ยังดูภาพอยู่"

# ── 🦘 กระโดดต้องลอยจริง ไม่ใช่วาปไปจุดลงพื้น ──

# ── 🌊 หมัดหนักผลักคนตกทะเลได้ ──

def test_a_solid_hit_can_shove_someone_into_the_sea(tmp_path, monkeypatch):
    """เจ้าของเกมสั่ง: การโจมตีต้องผลักคนอื่นกระเด็นตกน้ำได้"""
    match, uid = _match(tmp_path, monkeypatch, uid=7601)
    g = [[T.AIR] * T.W for _ in range(T.H)]
    for x in range(200, 260):                    # เกาะแคบ ๆ ยืนใกล้ขอบ
        for y in range(200, T.H - T.WATER):
            g[y][x] = T.ROCK
    st = match.load(uid)
    st["terrain"] = T.encode(g)
    st["props"] = []
    st["fighters"][0].update(x=230, y=200, face=1, hp=100)
    st["fighters"][1].update(x=252, y=200, face=-1, hp=100)
    match.save(uid, st)
    grid = T.decode(st["terrain"])
    kb = match._knock_back(st, grid, st["fighters"][1], 230, 40)
    assert st["fighters"][1]["dead"], "ต่อยเต็มแรงชิดขอบเกาะแล้วยังไม่ตกน้ำ"


def test_a_light_graze_does_not_shove_you_into_the_sea(tmp_path, monkeypatch):
    """หมัดเบา ๆ ต้องหยุดตรงขอบ — ไม่งั้นกลับไปเป็น "อยู่ ๆ ก็ตกรอบแพ้เอง"

    วัดแล้ว: เปิดให้ทุกหมัดผลักตกน้ำ ผู้เล่นยืนเฉย ๆ 40 เมล็ดจมน้ำ 19 ครั้ง
    (10 ครั้งก่อนรอบ 6) · จำกัดเป็น dmg>=25 เหลือ 8 ครั้ง (เร็วแค่ 2)
    """
    match, uid = _match(tmp_path, monkeypatch, uid=7602)
    g = [[T.AIR] * T.W for _ in range(T.H)]
    for x in range(200, 260):
        for y in range(200, T.H - T.WATER):
            g[y][x] = T.ROCK
    st = match.load(uid)
    st["terrain"] = T.encode(g)
    st["props"] = []
    st["fighters"][0].update(x=230, y=200, face=1, hp=100)
    st["fighters"][1].update(x=252, y=200, face=-1, hp=100)
    match.save(uid, st)
    grid = T.decode(st["terrain"])
    match._knock_back(st, grid, st["fighters"][1], 230, match.KNOCK_DROWN_DMG - 1)
    assert not st["fighters"][1]["dead"],         f"หมัดเบา ({match.KNOCK_DROWN_DMG - 1}) ก็ผลักตกน้ำตายได้ — แรงเกินไป"


# ── ✨ เอฟเฟกต์ที่เจ้าของเกมขอ ──

def test_warping_and_opening_a_chest_have_their_own_effects():
    for fn, what in (("function wmWarpFx(", "วาร์ป"), ("function wmChestFx(", "เปิดหีบ")):
        assert fn in PLAY, f"ไม่มีเอฟเฟกต์{what}"
    ferry = PLAY[PLAY.index("function wmRideFerry("):]
    ferry = ferry[:ferry.index(chr(10) + "}" + chr(10))]
    assert ferry.count("wmWarpFx(") >= 2,         "เอฟเฟกต์วาร์ปต้องมีทั้งจุดที่หายไปและจุดที่โผล่ออกมา"
    chest = PLAY[PLAY.index("function wmOpenChest("):]
    chest = chest[:chest.index(chr(10) + "}" + chr(10))]
    assert "wmChestFx(" in chest, "เปิดหีบแล้วไม่มีเอฟเฟกต์"
    # และต้องมีใครเรียกทั้งสองตัวจริง ๆ ไม่ใช่เขียนไว้เฉย ๆ
    do = PLAY[PLAY.index("async function wmDo("):]
    do = do[:do.index(chr(10) + "}" + chr(10))]
    assert "wmRideFerry(" in do and "wmOpenChest(" in do, "เขียนไว้แต่ไม่มีใครเรียก"


def test_the_pauses_between_steps_got_shorter():
    """เจ้าของเกมสั่ง: ลดดีเลย์จาก 2 วิเป็น 1 วิ และ 1 วิเป็น 0.5 วิ"""
    import re as _re

    before = int(_re.search("const WM_GAP_BEFORE = " + chr(40) + "?P<n>[0-9]+" + chr(41), PLAY).group("n"))
    after = int(_re.search("const WM_GAP_AFTER = " + chr(40) + "?P<n>[0-9]+" + chr(41), PLAY).group(1))
    assert before == 30, f"เว้นก่อนเริ่ม {before} เฟรม (ต้องเป็น 30 = 0.5 วิ)"
    assert after == 60, f"เว้นหลังเสร็จ {after} เฟรม (ต้องเป็น 60 = 1 วิ)"

# ── 🦘 การลอยค้างต้องล้างได้เสมอ ไม่งั้นเกมค้างถาวร ──

# ── 🦘 กระโดดกลับไปให้เซิร์ฟเวอร์เป็นคนคิด (ถอยระบบลอยฝั่งจอออก 08-27) ──

def test_the_jump_asks_the_server_and_plays_what_it_sends_back():
    """เคยให้จอลอยเองเพื่อตัดดีเลย์ ~300 ms — ฟิสิกส์ตรงเป๊ะแต่ "สภาพการลอย"
    ที่ต้องถือไว้ฝั่งจอกลายเป็นสถานะค้างได้หลายทาง พอค้างแล้วล็อกทั้งเกม
    เจ้าของเกมเจอของจริง: กระโดดแล้วภาพค้าง · ยอมแพ้ไม่ทำงาน · เปิดแมตช์ใหม่จอเพี้ยน
    """
    body = PLAY[PLAY.index("function wmJumpFire("):]
    body = body[:body.index(chr(10) + "}" + chr(10))]
    assert "wmDo('jump'" in body, "ไม่ได้ขอกระโดดจากเซิร์ฟเวอร์"
    assert "jump_power" in body and "lean" in body, "ไม่ได้ส่งแรง/การเอนไปให้คิด"
    assert "predicted" not in body, "ยังส่งแบบ 'เดาไว้ก่อน' อยู่"


def test_no_client_side_flight_state_exists_at_all():
    """สถานะที่ค้างได้ = บัคที่ล็อกเกมได้ — ถอดออกแล้วต้องไม่เหลือร่องรอย"""
    for ghost in ("WM_FLY", "wmFlyTick", "wmSettleJump", "wmLandJump", "WM_JUMP_SEND"):
        assert ghost not in PLAY, f"ยังเหลือ {ghost} ในหน้าเว็บ"
    for ghost in ("jumpStart", "jumpStep", "function jump("):
        assert ghost not in WALK_JS, f"ยังเหลือ {ghost} ใน walk.js"


def test_one_bad_frame_cannot_kill_the_whole_game():
    """error เฟรมเดียวเคยฆ่าลูปวาดทั้งอัน = ภาพค้าง กดอะไรไม่ได้ ปุ่มยอมแพ้ก็ตาย
    ผู้เล่นเห็นเป็น "พังหมดทุกอย่าง" ทั้งที่ต้นเหตุคือบัคเล็ก ๆ จุดเดียว
    """
    body = PLAY[PLAY.index("function wmStartLoop("):]
    body = body[:body.index(chr(10) + "}" + chr(10))]
    assert "try {" in body and "catch (e)" in body, "ลูปวาดไม่มีตาข่ายรับ error"
    assert "requestAnimationFrame(tick)" in body[body.index("catch (e)"):],         "จับ error ได้แล้วแต่ไม่ต่อเฟรมถัดไป = ค้างอยู่ดี"
    assert "console.error" in body, "กลืน error เงียบ ๆ = ไล่บัคไม่ได้"
