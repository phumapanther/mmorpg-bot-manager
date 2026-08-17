"""🏃 การเคลื่อนที่ในสนามรบ — เดิน กระโดด ตก จมน้ำ เหยียบกับดัก เปิดหีบ

จุดที่พังแล้วเจ็บที่สุด:
  1. **เชื่อพิกัดที่เบราว์เซอร์ส่งมา** = เปิด devtools แล้วเทเลพอร์ตไปยืนหลังศัตรูได้
  2. ลงเอยยืนอยู่ในกำแพง / ลอยกลางอากาศ — เกมพังโดยไม่มีอะไรฟ้อง
  3. ชนกำแพงถูกนับเป็นจมน้ำ (เคยพลาดมาแล้วจริง ๆ ตอนเขียนครั้งแรก)
"""
import pathlib
import re
import time

import pytest

import bot.models.player_model as pm
from bot.pvp import match, physics as P, terrain as T
from license_server import web_db

UID = 6201
WEB = pathlib.Path("license_server/web_static")
PLAY = (WEB / "play.js").read_text(encoding="utf-8")
HTML = (WEB / "play.html").read_text(encoding="utf-8")
LOOK = {"race": "Human", "cls": "Warrior", "armor": "None", "weapon": ""}


def _flat(top=200):
    g = [[T.AIR] * T.W for _ in range(T.H)]
    for x in range(T.W):
        for y in range(top, T.H - T.WATER):
            g[y][x] = T.ROCK
    return g


# ── ฟิสิกส์ล้วน ──

def test_you_stand_on_the_ground_not_inside_it():
    g = _flat()
    assert P.standable(g, 300, 200)
    assert not P.standable(g, 300, 210), "ยืนจมอยู่ในดินได้"
    assert not P.standable(g, 300, 150), "ยืนลอยกลางอากาศได้"


def test_walking_moves_you_one_pixel_per_step():
    r = P.walk(_flat(), 300, 200, 1, 10)
    assert r["x"] == 310 and len(r["path"]) == 10 and not r["drowned"]


def test_a_wall_stops_you_but_does_not_kill_you():
    """เคยพลาด: ชนกำแพงกับตกน้ำคืนค่าเหมือนกัน ชนกำแพงเลยตายทันที"""
    g = _flat()
    for y in range(150, 200):
        g[y][320] = T.ROCK
    r = P.walk(g, 300, 200, 1, 40)
    assert not r["drowned"], "ชนกำแพงแล้วถูกนับว่าจมน้ำ"
    assert r["x"] < 320, "เดินทะลุกำแพงไปได้"
    assert P.standable(g, r["x"], r["y"])


def test_you_climb_small_steps_but_not_cliffs():
    for rise, should in ((P.CLIMB, True), (P.CLIMB + 6, False)):
        g = [[T.AIR] * T.W for _ in range(T.H)]
        for x in range(T.W):
            top = 200 if x < 300 else 200 - rise
            for y in range(top, T.H - T.WATER):
                g[y][x] = T.ROCK
        r = P.walk(g, 290, 200, 1, 20)
        got = r["x"] > 302
        assert got is should, f"ขั้นสูง {rise}: {'ควรปีนได้' if should else 'ไม่ควรปีนขึ้นไปได้'}"


def test_walking_off_a_cliff_makes_you_fall_and_hurt():
    g = [[T.AIR] * T.W for _ in range(T.H)]
    for x in range(T.W):
        top = 150 if x < 300 else 230
        for y in range(top, T.H - T.WATER):
            g[y][x] = T.ROCK
    r = P.walk(g, 290, 150, 1, 20)
    assert r["y"] == 230 and r["fell"] == 80
    assert P.fall_damage(r["fell"]) > 0, "ตก 80 พิกเซลแล้วไม่เจ็บเลย"
    assert P.fall_damage(P.FALL_HURT_FROM - 1) == 0, "ตกเตี้ย ๆ ระหว่างเดินไม่ควรเสียเลือด"


def test_walking_into_the_sea_drowns_you():
    g = [[T.AIR] * T.W for _ in range(T.H)]
    for x in range(295):
        for y in range(150, 160):
            g[y][x] = T.ROCK
    assert P.walk(g, 290, 150, 1, 20)["drowned"]


def test_a_jump_is_an_arc_that_lands_on_the_ground():
    r = P.jump(_flat(), 300, 200, 1)
    top = min(p[1] for p in r["path"])
    assert r["x"] > 320, "กระโดดแล้วไม่ไปไหนเลย"
    assert top < 190, "กระโดดแล้วไม่ลอยขึ้นเลย"
    assert P.standable(_flat(), r["x"], r["y"]), "ลงเอยลอยกลางอากาศ"


def test_a_jump_cannot_pass_through_a_wall():
    g = _flat()
    for y in range(160, 200):
        g[y][320] = T.ROCK
    assert P.jump(g, 300, 200, 1)["x"] < 320, "กระโดดทะลุกำแพง"


def test_the_walk_length_is_capped():
    """กันเบราว์เซอร์ขอเดินรวดเดียวข้ามทั้งแผนที่"""
    assert len(P.walk(_flat(), 100, 200, 1, 9999)["path"]) <= P.STEP_MAX


def test_a_character_fits_through_a_door():
    """ประตูเตี้ยกว่าตัว = เดินเข้าปราสาทไม่ได้เลยสักหลัง (เคยเป็นแบบนั้นจริง)"""
    assert T.DOOR_H > T.CH_H, f"ประตูสูง {T.DOOR_H} แต่ตัวสูง {T.CH_H}"
    g = _flat()
    T._building(g, 300, 199, 60, T.CH_H + 20, T.BRICK, door=True)
    r = P.walk(g, 250, 200, 1, P.STEP_MAX)          # STEP_MAX จำกัดต่อคำสั่ง จึงเดินสองรอบ
    r = P.walk(g, r["x"], r["y"], 1, P.STEP_MAX)
    assert r["x"] > 305, f"เดินเข้าปราสาทไม่ได้ ติดอยู่ที่ x={r['x']}"


# ── แมตช์ ──

@pytest.fixture
def world(tmp_path, monkeypatch):
    monkeypatch.setattr(pm, "DB_NAME", str(tmp_path / "g.db"))
    monkeypatch.setattr(web_db, "DB_PATH", tmp_path / "w.db")
    pm.init_db()
    pm.get_player(UID)
    return None


@pytest.mark.parametrize("seed", list(range(1, 21)))
def test_a_new_match_puts_everyone_on_solid_ground(world, seed):
    """กวาดหลายเมล็ด — จุดเกิดที่ตัวจมพื้นเจอแค่บางแผนที่เท่านั้น"""
    st = match.new_practice(UID, LOOK, seed=seed)
    g = T.decode(st["terrain"])
    for f in st["fighters"]:
        assert P.standable(g, f["x"], f["y"]),             f"{f['name']} เกิดที่ ({f['x']},{f['y']}) แล้วยืนไม่ได้"
    assert abs(st["fighters"][0]["x"] - st["fighters"][1]["x"]) >= T.SPAWN_GAP


@pytest.mark.parametrize("seed", [7, 12345, 999, 42])
def test_you_never_end_up_inside_a_wall(world, seed):
    """เดินมั่ว ๆ ยาว ๆ แล้วต้องยืนบนพื้นเสมอ ไม่จมกำแพง ไม่ลอย"""
    match.new_practice(UID, LOOK, seed=seed)
    for i in range(30):
        act = "jump" if i % 5 == 4 else "walk"
        ok, r = match.move(UID, act, 1 if i % 7 < 4 else -1, 5)
        if not ok:
            match.end_turn(UID)
            continue
        f = r["fighters"][r["turn"]]
        if f["dead"]:
            break
        assert P.standable(T.decode(r["terrain"]), f["x"], f["y"]), \
            f"เมล็ด {seed} ก้าวที่ {i}: ลงเอยที่ ({f['x']},{f['y']}) ยืนไม่ได้"


def test_moving_costs_the_turn_budget(world):
    match.new_practice(UID, LOOK, seed=7)
    before = match.load(UID)["moves"]
    match.move(UID, "walk", 1, 5)
    assert match.load(UID)["moves"] < before, "เดินแล้วแรงไม่ลด — เดินได้ไม่จำกัด"


def test_you_cannot_move_forever(world):
    match.new_practice(UID, LOOK, seed=7)
    for _ in range(60):
        ok, _ = match.move(UID, "walk", 1, 5)
        if not ok:
            break
    assert not match.move(UID, "walk", 1, 5)[0], "แรงหมดแล้วยังเดินได้อีก"


def test_ending_a_turn_hands_over_and_refills(world):
    match.new_practice(UID, LOOK, seed=7)
    match.move(UID, "walk", 1, 5)
    ok, r = match.end_turn(UID)
    assert ok and r["turn"] == 1, "จบเทิร์นแล้วยังเป็นตาเดิม"
    assert r["moves"] == match.MOVE_BUDGET, "เทิร์นใหม่แรงไม่เต็ม"


def test_you_cannot_move_on_someone_elses_turn(world):
    match.new_practice(UID, LOOK, seed=7)
    match.end_turn(UID)
    ok, r = match.move(UID, "walk", 1, 5)
    assert not ok and "ยังไม่ถึงตา" in r["error"]


def test_moving_without_a_match_is_refused(world):
    match.drop(UID)
    ok, r = match.move(UID, "walk", 1, 5)
    assert not ok and "ยังไม่ได้เริ่ม" in r["error"]


def test_a_made_up_action_does_nothing(world):
    match.new_practice(UID, LOOK, seed=7)
    before = match.load(UID)
    ok, _ = match.move(UID, "เทเลพอร์ต", 1, 5)
    assert not ok
    assert match.load(UID)["fighters"] == before["fighters"], "ท่ามั่วแล้วตัวละครขยับ"


def test_starting_a_new_match_replaces_the_old_one(world):
    a = match.new_practice(UID, LOOK, seed=7)["seed"]
    b = match.new_practice(UID, LOOK, seed=99)["seed"]
    assert a != b and match.load(UID)["seed"] == b


# ── 🕳️ กับดัก · 🎁 หีบ ──

def _put(uid, kind, dx=3):
    """ย้ายผู้เล่นไปยืนข้าง ๆ ของชิ้นหนึ่ง แล้วเดินเข้าไปหา"""
    st = match.load(uid)
    p = next((q for q in st["props"] if q["kind"] == kind), None)
    if not p:
        pytest.skip(f"เมล็ดนี้ไม่มี {kind}")
    st["fighters"][0]["x"], st["fighters"][0]["y"] = p["x"] - dx, p["y"]
    st["turn"], st["moves"] = 0, match.MOVE_BUDGET
    match.save(uid, st)
    return p


def test_stepping_on_a_trap_hurts_and_uses_it_up(world):
    match.new_practice(UID, LOOK, seed=7)
    _put(UID, "trap")
    ok, r = match.move(UID, "walk", 1, 2)
    assert ok and r["sprung"], "เดินทับกับดักแล้วไม่เกิดอะไร"
    assert r["fighters"][0]["hp"] < 100, "เหยียบกับดักแล้วไม่เจ็บ"
    assert not r["sprung"][0] or match.move(UID, "walk", 1, 2)[1]["sprung"] == [], \
        "กับดักเดิมทำงานซ้ำได้"


def test_walking_over_a_chest_opens_it(world):
    match.new_practice(UID, LOOK, seed=7)
    _put(UID, "chest")
    ok, r = match.move(UID, "walk", 1, 3)
    assert ok and r["opened"], "เดินทับหีบแล้วไม่เปิด"
    assert all(p["kind"] != "chest" or abs(p["x"] - r["opened"][0]["x"]) > 1
               for p in r["props"]), "เปิดแล้วหีบยังอยู่"


def test_a_trap_you_have_not_stepped_on_stays_secret(world):
    """ส่งพิกัดกับดักไป = เปิด devtools แล้วเดินหลบได้หมด

    ต้องหาเมล็ดที่มีกับดักจริงก่อน — ไม่งั้นเทสผ่านลม ๆ บนแผนที่ที่ไม่มีกับดักสักอัน
    """
    import json
    seeds = [s for s in range(1, 40)
             if any(p["kind"] == "trap"
                    for p in match.new_practice(UID, LOOK, seed=s)["props"])]
    assert seeds, "ไม่มีเมล็ดไหนมีกับดักเลย — วางกับดักพังหรือเปล่า"
    for seed in seeds[:6]:
        match.new_practice(UID, LOOK, seed=seed)
        v = match.view(UID)
        assert isinstance(v["traps"], int) and v["traps"] > 0
        blob = json.dumps([v["props"], v["fighters"], v["log"]], ensure_ascii=False)
        assert "trap" not in blob, f"เมล็ด {seed}: พิกัดกับดักหลุดไปเบราว์เซอร์"


def test_drowning_ends_the_match(world):
    st = match.new_practice(UID, LOOK, seed=7)
    st["fighters"][1]["dead"] = True          # บอทตกรอบไปแล้ว
    match.save(UID, st)
    match.end_turn(UID)
    assert match.load(UID)["over"], "เหลือคนเดียวแล้วแมตช์ยังไม่จบ"


# ── กติกาเหล็ก: เบราว์เซอร์ไม่ตัดสินตำแหน่ง ──

def test_the_browser_never_computes_a_position():
    """เบราว์เซอร์คิดตำแหน่งเอง = เดินทะลุกำแพงได้ทันทีด้วย devtools"""
    a = PLAY.index("let WM = null, WM_CAM = null, WM_ST = null;")
    block = PLAY[a:PLAY.index("// ── 👥 เพื่อน ──", a)]
    for banned in ("standable", "GRAVITY", "solid(", "+= 1;"):
        assert banned not in block, f"หน้าเว็บคำนวณการเคลื่อนที่เอง: {banned}"
    assert "d.move.path" in block, "ไม่ได้เล่นภาพจากเส้นทางที่เซิร์ฟเวอร์ส่งมา"
    assert "/api/web/pvp/worms/match" in block


def test_the_server_ignores_any_position_sent_by_the_browser():
    api = pathlib.Path("license_server/web_api.py").read_text(encoding="utf-8")
    body = api[api.index("class WormsBody"):api.index("@router.post(\"/pvp/worms/match\")")]
    for leaked in ("x:", "y:", "hp:"):
        assert leaked not in body, f"API รับ {leaked} จากเบราว์เซอร์ — เทเลพอร์ตได้"


def test_the_controls_are_wired():
    for el in ("wmCanvas", "wmTurn", "wmMoves", "wmLog", "wmWho", "wmNew"):
        assert el in HTML and el in PLAY, f"อ้างถึง #{el} แต่ไม่มีในหน้าเว็บ (หรือกลับกัน)"
    assert 'data-wm="left"' in HTML and 'data-wm="right"' in HTML, "ไม่มีปุ่มเดิน"
    assert 'data-wm="jumpL"' in HTML and 'data-wm="jumpR"' in HTML, "ไม่มีปุ่มกระโดด"
    assert "ArrowLeft" in PLAY and "ArrowRight" in PLAY, "เล่นด้วยคีย์บอร์ดไม่ได้"
    assert "pointerdown" in PLAY, "กดค้างเดินต่อเนื่องบนมือถือไม่ได้"


def test_holding_a_button_batches_steps():
    """ยิงคำสั่งทุก 1 ก้าว = ถล่มเซิร์ฟเวอร์ตอนกดค้าง"""
    assert re.search(r"WM_WALK_STEPS\s*=\s*([2-9]|\d\d)", PLAY), "เดินทีละก้าวเดียวต่อคำสั่ง"
    assert "setInterval" in PLAY and "clearInterval" in PLAY, "กดค้างแล้วไม่หยุดเอง"


# ── ยิงผ่าน HTTP จริง ──

@pytest.fixture
def web(tmp_path, monkeypatch):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from license_server import web_api

    monkeypatch.setattr(pm, "DB_NAME", str(tmp_path / "g.db"))
    monkeypatch.setattr(web_db, "DB_PATH", tmp_path / "w.db")
    pm.init_db()
    pm.get_player(UID)
    monkeypatch.setattr(web_api, "GAME_DB_PATH", tmp_path / "g.db")
    app = FastAPI()
    app.include_router(web_api.router)
    c = TestClient(app)
    c.cookies.set("web_session", web_api.sign({"uid": str(UID), "exp": time.time() + 3600}))
    return c


def test_the_whole_loop_works_over_http(web):
    assert web.get("/api/web/pvp/worms/match").json()["active"] is False

    d = web.post("/api/web/pvp/worms/match", json={"action": "new", "seed": 7}).json()
    assert d["active"] and len(d["fighters"]) == 2 and d["turn"] == 0

    r = web.post("/api/web/pvp/worms/match", json={"action": "walk", "dir": 1, "steps": 5})
    assert r.status_code == 200, r.text
    assert r.json()["moves"] < d["moves"], "เดินแล้วแรงไม่ลด"

    assert web.post("/api/web/pvp/worms/match", json={"action": "end"}).json()["turn"] == 1
    assert web.get("/api/web/pvp/worms/match").json()["turn"] == 1


def test_http_rejects_moving_out_of_turn(web):
    web.post("/api/web/pvp/worms/match", json={"action": "new", "seed": 7})
    web.post("/api/web/pvp/worms/match", json={"action": "end"})
    assert web.post("/api/web/pvp/worms/match",
                    json={"action": "walk", "dir": 1}).status_code == 400


def test_a_logged_out_visitor_cannot_play(web):
    web.cookies.clear()
    assert web.get("/api/web/pvp/worms/match").status_code in (401, 403)
    assert web.post("/api/web/pvp/worms/match",
                    json={"action": "new"}).status_code in (401, 403)


def test_two_players_have_separate_matches(web, tmp_path):
    from license_server import web_api
    other = 6202
    pm.get_player(other)
    web.post("/api/web/pvp/worms/match", json={"action": "new", "seed": 7})
    web.cookies.set("web_session", web_api.sign({"uid": str(other), "exp": time.time() + 3600}))
    assert web.get("/api/web/pvp/worms/match").json()["active"] is False, "เห็นแมตช์ของคนอื่น"


# ── 🚦 กดค้างเดินต้องไม่ชนเพดานจำกัดอัตรา ──

def test_holding_walk_never_hits_the_rate_limit():
    """บั๊กที่ผู้เล่นเจอ: กดเดิน/กระโดดแล้วขึ้น "ยิงคำสั่งถี่เกินไป — รออีก 32 วินาที"

    ปุ่มเดินยิง 5 ครั้ง/วิ แต่เส้นทางนี้ตกกลุ่ม write (30 ครั้ง/นาที) เลยหมดโควตาใน 6 วินาที
    """
    from license_server import rate_limit as R

    R.reset()
    assert R.group_for("/api/web/pvp/worms/match", "POST") == "arena", \
        "สนามรบยังถูกจัดอยู่กลุ่มเดียวกับการเดินทางในเกมหลัก"
    hold = _hold_interval_ms() / 1000
    n = int(70 / hold)                       # กดค้างเดินยาว ๆ กว่าหนึ่งนาที
    blocked = [i for i in range(n)
               if not R.check("u", "/api/web/pvp/worms/match", "POST", now=i * hold)[0]]
    assert not blocked, f"กดค้างเดินแล้วโดนบล็อก {len(blocked)} ครั้ง"


def test_the_arena_still_has_a_ceiling():
    """ปล่อยกว้างได้ แต่ต้องยังกันยิงถล่มจนเซิร์ฟล่ม"""
    from license_server import rate_limit as R

    R.reset()
    blocked = [i for i in range(600)
               if not R.check("u", "/api/web/pvp/worms/match", "POST", now=i * 0.02)[0]]
    assert blocked, "ยิงรัว 50 ครั้ง/วินาที แล้วไม่โดนบล็อกเลย — ไม่มีเพดาน"
    R.reset()


def test_opening_the_arena_did_not_loosen_the_money_routes():
    """กันเผลอปล่อยเส้นทางที่แตะเงินไปด้วย"""
    from license_server import rate_limit as R

    assert R.group_for("/api/web/roleshop", "POST") == "money"
    assert R.LIMITS["money"][0] <= 20 and R.LIMITS["write"][0] <= 60


def _hold_interval_ms():
    m = re.search(r"const WM_HOLD_MS = (\d+)", PLAY)
    assert m, "หาอัตราการยิงตอนกดค้างใน play.js ไม่เจอ"
    return int(m.group(1))


def test_the_client_batches_enough_steps_to_look_smooth():
    """ยิงห่างขึ้นแต่ก้อนเล็กเท่าเดิม = ตัวละครเดินกระตุก

    ภาพเล่นก้าวละเฟรม (~60fps) ก้อนหนึ่งจึงต้องยาวพอกินเวลาจนถึงคำสั่งถัดไป
    """
    steps = int(re.search(r"const WM_WALK_STEPS = (\d+)", PLAY).group(1))
    ms = _hold_interval_ms()
    assert steps * 1000 / 60 >= ms * 0.85, \
        f"{steps} ก้าวเล่นได้ {steps * 1000 / 60:.0f}ms แต่ยิงทุก {ms}ms — ภาพจะขาดช่วง"
    assert steps <= P.STEP_MAX, "ขอเกินเพดานที่เซิร์ฟเวอร์ยอมให้ต่อคำสั่ง"
