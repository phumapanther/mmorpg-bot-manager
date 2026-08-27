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

WEB = pathlib.Path("license_server/web_static")
WALK_JS = (WEB / "walk.js").read_text(encoding="utf-8")
PLAY = (WEB / "play.js").read_text(encoding="utf-8")
HTML = (WEB / "play.html").read_text(encoding="utf-8")

RULES = {"ch_h": T.CH_H, "foot_w": P.FOOT_W, "climb": P.CLIMB,
         "step_max": P.STEP_MAX, "water": T.WATER,
         "gravity": P.GRAVITY, "jump_vx": P.JUMP_VX, "jump_vy": P.JUMP_VY,
         "jump_curve": P.JUMP_CURVE, "air_accel": P.AIR_ACCEL,
         "air_max": P.AIR_MAX, "sink": P.SINK_DEPTH}


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


@pytest.mark.parametrize("seed", [3, 11, 27])
def test_both_sides_jump_along_exactly_the_same_arc(seed):
    """วิถีกระโดดตัดสินตั้งแต่วินาทีที่ปล่อยปุ่ม จอจึงคำนวณเองได้ทันที

    แต่ต้องตรงกับเซิร์ฟเวอร์ "ทุกเฟรม" ไม่ใช่แค่จุดตก — ไม่งั้นเห็นตัวสลับวิถีกลางอากาศ
    """
    rng = random.Random(seed * 31)
    grid = T.generate(seed)["grid"]
    spots = T._open_spots(grid)
    cases = []
    for _ in range(120):
        x, y = rng.choice(spots)
        cases.append([x, y, rng.choice([-1, 1]), round(rng.random(), 3),
                      rng.choice([-1.0, 0.0, 1.0, round(rng.uniform(-1, 1), 3)])])

    js = _run_js(grid, cases, kind="jump")
    for c, j in zip(cases, js):
        x, y, d, pw, ln = c
        py = P.jump(grid, x, y, d, power=pw, lean=ln)
        assert (py["x"], py["y"], py["drowned"]) == (j["x"], j["y"], j["drowned"]), (
            f"เมล็ด {seed}: กระโดดจาก ({x},{y}) ทิศ {d} แรง {pw} เอน {ln} — "
            f"python ลง ({py['x']},{py['y']}) · js ลง ({j['x']},{j['y']})")
        assert len(py["path"]) == len(j["path"]), (
            f"วิถียาวไม่เท่ากัน (python {len(py['path'])} · js {len(j['path'])}) "
            "= ลอยคนละจังหวะ เห็นเป็นตัวกระตุกกลางอากาศ")
        assert py["path"] == [list(pt) for pt in j["path"]], "วิถีไม่ตรงกันทุกเฟรม"


def test_the_jump_leaves_the_ground_without_waiting_for_the_server():
    """ปล่อยปุ่มแล้วต้องลอยเลย ไม่ใช่รอ ~300 ms ให้เซิร์ฟเวอร์ตอบก่อน"""
    body = PLAY[PLAY.index("function wmJumpFire("):]
    body = body[:body.index(chr(10) + "}" + chr(10))]
    assert body.index("WM_ANIM = {") < body.index("wmBusy"),         "ยิงคำสั่งไปเซิร์ฟเวอร์ก่อนแล้วค่อยเริ่มภาพ = รอเน็ตเหมือนเดิม"
    assert "WALK.jump(" in body, "ไม่ได้คำนวณวิถีเอง"


def test_a_jump_is_never_lost_when_the_line_is_busy():
    """ปล่อยกระโดดตอนก้อนเดินยังไม่กลับ — ถ้าคำสั่งหาย เซิร์ฟเวอร์จะไม่รู้เรื่องเลย
    จอกระโดดไปแล้วแต่เซิร์ฟเวอร์ยังคิดว่ายืนอยู่ที่เดิม = เพี้ยนยาว
    """
    body = PLAY[PLAY.index("function wmJumpFire("):]
    body = body[:body.index(chr(10) + "}" + chr(10))]
    assert "WM_JUMP_SEND = send" in body, "สายไม่ว่างแล้วทิ้งคำสั่งกระโดดไปเฉย ๆ"
    tick = PLAY[PLAY.index("function wmWalkTick("):]
    tick = tick[:tick.index(chr(10) + "}" + chr(10))]
    assert "WM_JUMP_SEND" in tick, "ไม่มีใครส่งคำสั่งกระโดดที่ค้างไว้"


def test_a_late_walk_batch_cannot_drag_you_out_of_the_air():
    """ก้อนเดินที่ส่งไปก่อนกระโดดจะกลับมาตอนกำลังลอยอยู่ — ห้ามลากตัวกลับลงพื้น"""
    body = PLAY[PLAY.index("async function wmDo("):]
    body = body[:body.index(chr(10) + "}" + chr(10))]
    assert "if (!WM_JUMP_END) wmReconcile(" in body,         "ก้อนเดินที่มาทีหลังยังทาบตำแหน่งได้ทั้งที่กำลังลอยอยู่"


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
    api = pathlib.Path("license_server/web_api.py").read_text(encoding="utf-8")
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
