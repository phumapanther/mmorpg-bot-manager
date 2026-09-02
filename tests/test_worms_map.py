"""🪱 แผนที่สนามรบผลัดเทิร์น — เกาะลอยที่ยิงจนพังได้

แผนที่พังแล้วเจ็บที่สุดตรงไหน:
  1. เกิดมาแล้วยืนกลางอากาศ / จมน้ำทันที = เกมจบก่อนเริ่ม
  2. เมล็ดเดียวกันได้คนละแผนที่ = แชร์รหัสแผนที่กับเพื่อนไม่ได้ และเทสย้อนดูไม่ได้
  3. ฝั่ง JS ถอดรหัสได้กริดคนละใบกับฝั่งเซิร์ฟเวอร์ = เห็นพื้นคนละที่กับที่เซิร์ฟเวอร์คิด
     (ข้อนี้เทสจริงด้วยการรัน worms.js ใน node แล้วเทียบลายเซ็นกริด)
"""
import json
import pathlib
import re
import shutil
import subprocess
import time

import pytest

from bot.pvp import terrain as T

WEB = pathlib.Path("license_server/web_static")
WORMS = (WEB / "worms.js").read_text(encoding="utf-8")
PLAY = (WEB / "play.js").read_text(encoding="utf-8")
HTML = (WEB / "play.html").read_text(encoding="utf-8")

SEEDS = [55529632192042, 1, 7, 12345, 999999, 2 ** 40 + 3]


# ── แผนที่เดิมต้องได้เหมือนเดิมเสมอ ──

@pytest.mark.parametrize("seed", SEEDS)
def test_the_same_seed_always_gives_the_same_map(seed):
    assert T.generate(seed)["grid"] == T.generate(seed)["grid"]


def test_different_seeds_give_different_maps():
    grids = {T.encode(T.generate(s)["grid"]) for s in SEEDS}
    assert len(grids) == len(SEEDS), "เมล็ดต่างกันแต่ได้แผนที่ซ้ำ"


@pytest.mark.parametrize("seed", SEEDS)
def test_encoding_survives_a_round_trip(seed):
    g = T.generate(seed)["grid"]
    assert T.decode(T.encode(g)) == g, "บีบแล้วถอดกลับได้ไม่เหมือนเดิม"


def test_the_map_compresses_worth_it():
    """ถ้าบีบแล้วไม่เล็กลง ก็ส่งบิตดิบไปเลยง่ายกว่า — บีบต้องคุ้มจริง"""
    enc = T.encode(T.generate(55529632192042)["grid"])
    assert len(enc) < T.W * T.H / 8, f"บีบได้แค่ {T.W * T.H / len(enc):.0f} เท่า"


def test_the_map_is_big_enough_to_need_a_camera():
    """เจ้าของเกมสั่งให้ใหญ่ขึ้น — ใหญ่กว่าจอจนต้องซูม/เลื่อนดู"""
    assert T.W >= 700 and T.H >= 260, f"แผนที่ {T.W}×{T.H} ยังเล็กเกิน"


def test_making_a_map_is_fast_enough_to_do_on_demand():
    t0 = time.perf_counter()
    for s in SEEDS:
        T.view(s)
    ms = (time.perf_counter() - t0) * 1000 / len(SEEDS)
    assert ms < 250, f"สร้างแผนที่ใบละ {ms:.0f} ms — ช้าเกินจะกดสุ่มรัว ๆ"


# ── รูปร่างแผนที่ ──

@pytest.mark.parametrize("seed", SEEDS)
def test_nothing_is_ever_built_inside_the_water(seed):
    """น้ำก้นจอคือเขตตาย ห้ามมีพื้นให้ยืนอยู่ในนั้น"""
    g = T.generate(seed)["grid"]
    for y in range(T.H - T.WATER, T.H):
        assert not any(g[y]), f"มีพื้นอยู่ใต้เส้นน้ำที่แถว {y}"


@pytest.mark.parametrize("seed", SEEDS)
def test_there_is_enough_land_to_play_on(seed):
    """แผนที่ที่แทบไม่มีพื้น = ยืนไม่ได้ · พื้นเต็มจอ = ไม่มีที่ให้ตก ทั้งคู่ไม่สนุก"""
    g = T.generate(seed)["grid"]
    solid = sum(1 for r in g for v in r if v)
    pct = solid * 100 / (T.W * T.H)
    assert 4 < pct < 45, f"พื้นกินพื้นที่ {pct:.0f}% ของจอ"


@pytest.mark.parametrize("seed", SEEDS)
def test_the_islands_actually_float(seed):
    """ต้องมีช่องว่างใต้พื้นจริง ๆ ไม่งั้นเป็นภูเขาตันไม่ใช่เกาะลอยตามที่สั่ง"""
    g = T.generate(seed)["grid"]
    floating = 0
    for x in range(T.W):
        col = [y for y in range(T.H) if g[y][x] and g[y][x] != T.LEAF]
        if col and any(not g[y][x] for y in range(col[0], col[-1])):
            floating += 1
    assert floating > 20, f"มีช่องว่างใต้พื้นแค่ {floating} คอลัมน์ — แผนที่ตันเกินไป"


# ── จุดเกิด ──

@pytest.mark.parametrize("seed", SEEDS)
@pytest.mark.parametrize("n", [2, 4, 8])
def test_everyone_gets_a_spot_on_solid_ground(seed, n):
    g = T.generate(seed)["grid"]
    sp = T.spawns(g, n)
    assert len(sp) == n, f"ขอ {n} จุด ได้ {len(sp)} จุด"
    for x, y in sp:
        assert T.solid(g, x, y), f"จุดเกิด ({x},{y}) ลอยอยู่กลางอากาศ"
        assert not T.solid(g, x, y - 1), f"จุดเกิด ({x},{y}) ฝังอยู่ในพื้น"
        assert y < T.H - T.WATER, "เกิดมาจมน้ำเลย"


def test_two_players_do_not_spawn_on_top_of_each_other():
    """ต้องห่างกันทุกเมล็ด ไม่ใช่ห่างเพราะฟลุก — ลอง 40 เมล็ดกันเทสผ่านด้วยดวง"""
    close = [s for s in range(1, 41)
             if abs(T.spawns(T.generate(s)["grid"], 2)[0][0]
                    - T.spawns(T.generate(s)["grid"], 2)[1][0]) < T.SPAWN_GAP]
    assert not close, f"เมล็ดที่เกิดมาติดกันจนยิงตายทันที: {close}"


@pytest.mark.parametrize("seed", SEEDS)
def test_you_can_actually_walk_where_you_spawn(seed):
    """เกิดบนยอดหินแหลมเดียว = ขยับไปทางไหนก็ร่วง ยังไม่ทันได้เล่น

    ใช้ตัวเดินจริงของเกมตัดสิน ไม่ลอกเงื่อนไขในตัวสร้างมาเขียนซ้ำ
    (เขียนโมเดลเดินของตัวเองแล้วปรับขนาดตัวละครทีเดียวเทสเพี้ยนหมด เคยเจอมาแล้ว)
    """
    from bot.pvp import physics as P

    g = T.generate(seed)["grid"]
    for x, y in T.spawns(g, 4):
        assert P.standable(g, x, y), f"จุดเกิด ({x},{y}) ยืนไม่ได้"
        moved = [d for d in (-1, 1) if P.step(g, x, y, d)[0] != P.BLOCKED]
        assert moved, f"จุดเกิด ({x},{y}) ขยับไม่ได้สักทาง — ติดอยู่ในซอก"


def test_spawns_are_stable_for_a_seed():
    g = T.generate(7)["grid"]
    import random
    assert T.spawns(g, 4, random.Random(1)) == T.spawns(g, 4, random.Random(1))


# ── 💥 ยิงจนพัง ──

def test_a_blast_actually_removes_ground():
    g = T.generate(7)["grid"]
    x, y = T.spawns(g, 1)[0]
    y += 6                                  # ใต้เท้า = พื้นแน่นอน
    gone = T.carve(g, x, y, 10)
    assert gone, "ยิงแล้วพื้นไม่หายสักพิกเซล"
    assert not T.solid(g, x, y), "กลางหลุมยังตัน"
    assert all(not T.solid(g, px, py) for px, py in gone), "บอกว่าหายแต่ยังอยู่"


def test_a_blast_only_eats_a_circle():
    """ระเบิดต้องกินเป็นวงกลม ไม่ใช่ลบทั้งแถว"""
    g = [[T.ROCK] * T.W for _ in range(T.H)]
    T.carve(g, 300, 120, 10)
    assert not T.solid(g, 300, 120) and not T.solid(g, 305, 120)
    assert T.solid(g, 300 + 12, 120), "ระเบิดกินเลยรัศมีไป"
    assert T.solid(g, 300, 120 - 12), "ระเบิดกินเลยรัศมีในแนวตั้ง"


def test_a_blast_at_the_edge_does_not_crash():
    g = T.generate(7)["grid"]
    for x, y in ((0, 0), (T.W - 1, T.H - 1), (-5, 50), (T.W + 5, 50)):
        T.carve(g, x, y, 15)          # ไม่ต้องได้ผล แค่ต้องไม่ระเบิดใส่เซิร์ฟเวอร์


def test_the_ground_can_be_blown_away_entirely():
    """ยิงจนเกาะขาดกลาง ต้องเดินข้ามไม่ได้จริง (พื้นหายจริง ไม่ใช่แค่ภาพ)"""
    g = T.generate(12345)["grid"]
    x, y = T.spawns(g, 1)[0]
    for r in range(3):
        T.carve(g, x, y + 4 + r * 8, 14)
    assert T.surface_at(g, x) != y, "ยิงจนพื้นหายแล้วผิวยังอยู่ที่เดิม"


# ── กติกาเหล็ก: เบราว์เซอร์ห้ามสร้างแผนที่เอง ──

def test_the_browser_has_no_map_generator():
    """เบราว์เซอร์สร้างแผนที่เองเมื่อไหร่ = เปิด devtools แล้วยืนกลางอากาศได้ทันที"""
    # ตัดคอมเมนต์ทิ้งก่อน ไม่งั้นคำอธิบายที่พูดถึง Math.random ก็โดนจับด้วย
    code = re.sub(r"/\*.*?\*/|//.*", "", WORMS, flags=re.S)
    for banned in ("function generate", "Math.random"):
        assert banned not in code, f"worms.js มี {banned} — ตัวสร้างแผนที่ต้องอยู่ที่เซิร์ฟเวอร์"
    assert "/api/web/pvp/worms/match" in PLAY, "หน้าเว็บไม่ได้ขอแผนที่จากเซิร์ฟเวอร์"


def test_the_panel_is_wired():
    assert 'data-go="worms"' in HTML and 'id="v-worms"' in HTML
    assert '/worms.js' in HTML, "ไม่ได้โหลด worms.js"
    # เจ้าของเกมสั่ง 09-02: เข้าสนามรบเจอหน้าเลือกโหมดก่อน แล้วค่อยโหลดสนาม
    # (เดิมโหลดทันทีที่เปิดหน้า — เทสข้อนี้เคยผูกกับพฤติกรรมเก่า)
    assert "wmShowGate()" in PLAY, "เปิดหน้าสนามรบแล้วไม่ได้โชว์หน้าเลือกโหมด"
    assert PLAY.count("await fillWorms();") >= 2, "ปุ่มเลือกโหมดต้องโหลดสนามให้ทั้งสองทาง"
    for el in ("wmCanvas", "wmSeed", "wmNew", "wmSame"):
        assert el in PLAY and el in HTML, f"อ้างถึง #{el} แต่ไม่มีในหน้าเว็บ (หรือกลับกัน)"


def _worms_js():
    """ทั้งหมวดสนามรบใน play.js — ตัดตามจุดเริ่มของบล็อก ไม่ใช่นับตัวอักษร"""
    a = PLAY.index("let WM = null, WM_CAM = null, WM_ST = null;")
    return PLAY[a:PLAY.index("let FRIENDS = null;", a)]


def test_the_fighters_are_our_characters_not_worms():
    """เจ้าของเกมสั่งไว้: ลงสนามด้วยตัวละครของเราเอง ไม่ใช่หนอน"""
    fn = _worms_js()
    assert "drawCharacter(" in fn, "ไม่ได้วาดตัวละครจริงลงสนาม"
    assert "f.look" in fn, "ไม่ได้ใช้หน้าตาตัวละครที่เซิร์ฟเวอร์ส่งมา"


def test_every_continent_has_ground_colours():
    """ทวีปที่ไม่มีสีพื้น = สนามรบขึ้นมาเป็นสีเดียวจืด ๆ"""
    from bot.game_data import CONTINENTS
    block = WORMS[WORMS.index("const WORM_GROUND"):]
    block = block[:block.index("\n};")]
    keys = set(re.findall(r"^\s{2}(\w+):", block, re.M))
    assert set(CONTINENTS) <= keys, f"ทวีปที่ยังไม่มีสีพื้น: {sorted(set(CONTINENTS) - keys)}"


def test_the_ground_colours_are_real_hex():
    """เคยพิมพ์ '#5f7near' หลุดไปแล้วครั้งหนึ่ง — สีเพี้ยนแบบนี้ไม่มีอะไรฟ้อง"""
    block = WORMS[WORMS.index("const WORM_GROUND"):]
    block = block[:block.index("\n};")]
    bad = [c for c in re.findall(r"'([^']*)'", block) if not re.fullmatch(r"#[0-9a-fA-F]{6}", c)]
    assert not bad, f"สีที่เขียนผิดรูปแบบ: {bad}"


# ── ฝั่ง JS ต้องเห็นพื้นชุดเดียวกับเซิร์ฟเวอร์ ──

def _js_grid_signature(data):
    node = shutil.which("node")
    if not node:
        pytest.skip("ไม่มี node ในเครื่องนี้")
    src = r"""
const DATA = __DATA__;
globalThis.document = { createElement: () => ({ width:0, height:0, getContext: () => ({
  clearRect(){}, fillRect(){}, drawImage(){},
  createImageData:(w,h)=>({width:w,height:h,data:new Uint8ClampedArray(w*h*4)}),
  putImageData(){}, createLinearGradient:()=>({addColorStop(){}}),
  set fillStyle(v){}, set globalAlpha(v){} }) }) };
globalThis.MAPS = {};
__WORMS__
const m = new WormsMap(DATA);
let sig = 0;
for (let i = 0; i < m.w * m.h; i++) if (m.g[i]) sig = (sig * 31 + i) >>> 0;
console.log(sig);
""".replace("__DATA__", json.dumps(data)).replace("__WORMS__", WORMS)
    import tempfile
    f = pathlib.Path(tempfile.mkdtemp()) / "t.mjs"
    f.write_text(src, encoding="utf-8")
    r = subprocess.run([node, str(f)], capture_output=True, text=True, encoding="utf-8")
    assert r.returncode == 0, r.stderr[-1500:]
    return int(r.stdout.strip().splitlines()[-1])


def _py_grid_signature(grid):
    sig = 0
    for y in range(T.H):
        for x in range(T.W):
            if grid[y][x]:
                sig = (sig * 31 + (y * T.W + x)) & 0xFFFFFFFF
    return sig


@pytest.mark.parametrize("seed", [55529632192042, 7])
def test_the_browser_sees_exactly_the_ground_the_server_built(seed):
    """ถอดรหัสคนละแบบ = ผู้เล่นเห็นพื้นคนละที่กับที่เซิร์ฟเวอร์ใช้ตัดสิน"""
    data = T.view(seed, "sylvan", 2)
    assert _js_grid_signature(data) == _py_grid_signature(T.generate(seed)["grid"])


# ── ยิงผ่าน HTTP จริง ──

@pytest.fixture
def web(tmp_path, monkeypatch):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    import bot.models.player_model as pm
    from license_server import web_api

    uid = 6101
    monkeypatch.setattr(pm, "DB_NAME", str(tmp_path / "w.db"))
    pm.init_db()
    pm.get_player(uid)
    monkeypatch.setattr(web_api, "GAME_DB_PATH", tmp_path / "w.db")
    app = FastAPI()
    app.include_router(web_api.router)
    c = TestClient(app)
    c.cookies.set("web_session", web_api.sign({"uid": str(uid), "exp": time.time() + 3600}))
    return c


def test_http_hands_out_a_playable_map(web):
    d = web.get("/api/web/pvp/worms/map?players=2").json()
    assert d["w"] == T.W and d["h"] == T.H and d["seed"] > 0
    assert len(d["spawns"]) == 2
    assert d["continent_label"], "ไม่ได้บอกชื่อทวีป"
    g = T.decode(d["terrain"])
    for s in d["spawns"]:
        assert g[s["y"]][s["x"]] != T.AIR, "จุดเกิดที่ส่งมาไม่ได้อยู่บนพื้น"


def test_http_gives_back_the_same_map_for_a_seed(web):
    a = web.get("/api/web/pvp/worms/map?seed=424242&continent=frozen").json()
    b = web.get("/api/web/pvp/worms/map?seed=424242&continent=frozen").json()
    assert a == b, "รหัสแผนที่เดียวกันแต่ได้คนละแผนที่ — แชร์กับเพื่อนไม่ได้"


def test_http_shrugs_off_junk_input(web):
    d = web.get("/api/web/pvp/worms/map?players=99&continent=ทวีปปลอม").json()
    assert 2 <= len(d["spawns"]) <= 8, "จำนวนคนไม่ถูกจำกัด"
    from bot.game_data import CONTINENTS
    assert d["continent"] in CONTINENTS, "ทวีปมั่วหลุดเข้าไปได้"


def test_a_logged_out_visitor_gets_no_map(web):
    web.cookies.clear()
    assert web.get("/api/web/pvp/worms/map").status_code in (401, 403)
