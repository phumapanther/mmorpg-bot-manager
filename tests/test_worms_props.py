"""🏗️ ของบนแผนที่สนามรบ — สิ่งปลูกสร้าง หีบสมบัติ กับดัก

สิ่งที่เจ้าของเกมสั่ง: ต้นไม้ หิน หมู่บ้าน ปราสาทที่เข้าไปแอบได้ แต่ยิงพังได้
หีบสมบัติเปิดสุ่มไอเทม และกับดักที่ทำงานเมื่อเดินไปโดน

**ตัดสินใจที่ทำให้ทุกข้อข้างบนเกิดขึ้นเอง:** สิ่งปลูกสร้างเป็นเนื้อเดียวกับพื้น
กำแพงตัน ข้างในกลวง มีประตู → แอบได้เอง · ยิงพังได้เองด้วย carve() ตัวเดียวกับดิน
ไฟล์นี้จึงคุมว่า "กลวงจริงไหม" กับ "พังจริงไหม" เป็นหลัก

🔒 กับดักต้องไม่รั่วไปให้เบราว์เซอร์ ไม่งั้นเปิด devtools แล้วเดินหลบได้หมด
"""
import json
import pathlib
import random
import re
import time

import pytest

from bot.pvp import physics as P, terrain as T

WEB = pathlib.Path("license_server/web_static")
WORMS = (WEB / "worms.js").read_text(encoding="utf-8")
PLAY = (WEB / "play.js").read_text(encoding="utf-8")
HTML = (WEB / "play.html").read_text(encoding="utf-8")
CSS = (WEB / "play.css").read_text(encoding="utf-8")

SEEDS = [55529632192042, 1, 7, 12345, 999999, 2 ** 40 + 3]
MAT_NAMES = {T.GRASS: "หญ้า", T.DIRT: "ดิน", T.ROCK: "หิน", T.WOOD: "ไม้บ้าน",
             T.BRICK: "อิฐปราสาท", T.TRUNK: "ลำต้น", T.LEAF: "ใบไม้"}


def _mats(grid):
    return {v for row in grid for v in row if v}


# ── 🏗️ สิ่งปลูกสร้าง ──

@pytest.mark.parametrize("seed", SEEDS)
def test_every_map_has_things_to_hide_behind(seed):
    """แผนที่โล่ง ๆ ไม่มีที่กำบัง = ยิงกันตายรอบเดียวจบ ไม่สนุก

    ไม่บังคับว่าต้องมีครบทุกชนิดทุกใบ — ต้นไม้ต้องมีเสมอ ส่วนบ้าน/ปราสาทต้องใช้
    พื้นราบกว้าง บางแผนที่จึงไม่มี ขอแค่มีของกำบังชนิดอื่นทดแทน
    """
    have = _mats(T.generate(seed)["grid"])
    kinds = {T.TRUNK, T.WOOD, T.BRICK, T.ROCK} & have
    assert len(kinds) >= 2,         f"มีของกำบังแค่ {len(kinds)} ชนิด — โล่งเกินไป ยิงกันตายรอบเดียวจบ"


def test_trees_and_villages_show_up_on_most_maps():
    """ทุกอย่างต้องการที่ว่าง แผนที่ที่แน่นจนไม่มีบางอย่างมีได้ แต่ต้องเป็นส่วนน้อย"""
    trees = houses = 0
    for s in range(1, 31):
        have = _mats(T.generate(s)["grid"])
        trees += T.TRUNK in have
        houses += T.WOOD in have
    assert trees >= 25, f"มีต้นไม้แค่ {trees}/30 เมล็ด"
    assert houses >= 20, f"มีหมู่บ้านแค่ {houses}/30 เมล็ด — พื้นราบกว้างหายากเกินไป"


def test_a_castle_shows_up_on_most_maps():
    """ปราสาทต้องการที่ราบกว้าง เมล็ดที่ไม่มีมีได้บ้าง แต่ต้องเป็นส่วนน้อย"""
    n = sum(1 for s in range(1, 41) if T.BRICK in _mats(T.generate(s)["grid"]))
    assert n >= 20, f"มีปราสาทแค่ {n}/40 เมล็ด — ที่ราบกว้าง 84 ช่องหายากเกินไป"


WALL = (T.WOOD, T.BRICK)
# ใช้ขนาดตัวจริงกับตัวเดินจริงจาก bot/games/pvp/physics.py
# ไม่เขียนโมเดลเดินของตัวเองในเทส ไม่งั้นพอปรับขนาดตัวละครทีเดียวเทสเพี้ยนหมด
HEAD = T.CH_H


def _buildings(g):
    """หาตัวอาคารจริงจากกริด — ก้อนกำแพงไม้/อิฐที่ติดกัน แล้วคืนกรอบสี่เหลี่ยม

    วัดจากของจริงในแผนที่ ไม่ใช่นิยามประมาณ ๆ อย่าง "มีหลังคากับกำแพงข้าง"
    ที่เคยทำให้เทสจับบั๊กไม่ได้เพราะช่องประตูไปทำให้นิยามนั้นเป็นเท็จ
    """
    seen, out = set(), []
    for y0 in range(T.H):
        for x0 in range(T.W):
            if g[y0][x0] not in WALL or (x0, y0) in seen:
                continue
            stack, cells = [(x0, y0)], []
            seen.add((x0, y0))
            while stack:
                x, y = stack.pop()
                cells.append((x, y))
                for dx in (-1, 0, 1):
                    for dy in (-1, 0, 1):
                        nx, ny = x + dx, y + dy
                        if (0 <= nx < T.W and 0 <= ny < T.H and (nx, ny) not in seen
                                and g[ny][nx] in WALL):
                            seen.add((nx, ny))
                            stack.append((nx, ny))
            xs = [c[0] for c in cells]
            ys = [c[1] for c in cells]
            if max(xs) - min(xs) >= 10 and max(ys) - min(ys) >= 8:
                out.append((min(xs), min(ys), max(xs), max(ys)))
    return out


def _inside_spots(g, box):
    """ที่ยืนที่อยู่ "ใต้หลังคา" จริง ๆ

    ต้องเช็คว่ามีกำแพงอยู่เหนือหัว ไม่งั้นที่ยืนบน**หลังคา**ก็ติดมาด้วย
    ซึ่งไม่ใช่การแอบในอาคารเลย (เคยพลาดตรงนี้ เทสเลยฟ้องผิดจุด)
    """
    x0, y0, x1, y1 = box
    out = []
    for x in range(x0 + 3, x1 - 2):
        for y in T.surfaces_at(g, x):
            # ช่องประตูกินกำแพงล่างไป DOOR_H แถว ขอบล่างของกรอบจึงลอยสูงกว่าพื้นห้องจริง
            # เผื่อระยะเท่าความสูงประตู ไม่งั้นพื้นห้องจริงจะถูกตัดทิ้งทั้งหมด
            if y <= y0 + 2 or y > y1 + T.DOOR_H + 4:
                continue                  # บนหลังคาพอดี / ต่ำกว่าตัวบ้านมาก = ไม่ได้อยู่ในบ้าน
            if not P.standable(g, x, y):
                continue                  # ตัวจริงยัดลงตรงนี้ไม่ได้
            # ช่องประตูตัดกำแพงให้สั้นลง กรอบล่างจึงสูงกว่าพื้นห้องจริง
            # เกณฑ์ที่เชื่อได้คือ "มีกำแพงอยู่เหนือหัว" ไม่ใช่ขอบล่างของกรอบ
            if any(T.material(g, x, y - k) in WALL for k in range(HEAD, y - y0 + 1)):
                out.append((x, y))
    return out


def _walk_out(g, x, y, box):
    """เดินจากจุดนี้ออกไปพ้นกรอบอาคารได้ไหม — เดินจริงทีละก้าว

    เดินออกได้ = เดินเข้าได้ (ทางเดียวกัน) · กำแพงตันจะทำให้ก้าวต่อไม่ได้จริง ๆ
    ก้าวลงต่ำได้ไม่จำกัด (ตกลงไปเฉย ๆ) แต่ปีนขึ้นได้แค่ CLIMB — เหมือนเกมจริง
    """
    x0, _, x1, _ = box
    for step in (-1, 1):
        cx, cy = x, y
        for _ in range(x1 - x0 + 12):
            how, cx, cy = P.step(g, cx, cy, step)          # ใช้ตัวเดินจริงของเกม
            if how == P.BLOCKED:
                break
            if cx < x0 or cx > x1:                         # พ้นกรอบอาคาร = ออกได้จริง
                return True
            if how == P.DROWNED:
                break
    return False


@pytest.mark.parametrize("seed", list(range(1, 25)))
def test_you_can_actually_stand_inside_a_building(seed):
    """เข้าไปแอบในปราสาทได้ = ต้องมีที่ยืนอยู่ในตัวอาคารจริง ตันทั้งก้อนแปลว่าแอบไม่ได้"""
    g = T.generate(seed)["grid"]
    boxes = _buildings(g)
    if not boxes:
        pytest.skip("เมล็ดนี้ไม่มีสิ่งปลูกสร้าง")
    roomy = [b for b in boxes if len(_inside_spots(g, b)) >= 5]
    assert roomy, f"อาคารทั้ง {len(boxes)} หลังตันหมด ยืนข้างในไม่ได้เลย"


@pytest.mark.parametrize("seed", list(range(1, 25)))
def test_you_can_walk_into_the_building_you_hide_in(seed):
    """มีห้องแต่เดินเข้าไม่ได้ = มองเห็นแต่ใช้ไม่ได้ เท่ากับไม่มี

    กวาดหลายเมล็ด — เคยพลาดมาแล้ว: ประตูข้างเดียวไปเปิดออกหน้าผาพอดี
    บ้านหลังนั้นเข้าไม่ได้ทั้งหลัง และเจอแค่บางเมล็ดเท่านั้น
    """
    g = T.generate(seed)["grid"]
    ok = [b for b in _buildings(g)
          if any(_walk_out(g, *p, b) for p in _inside_spots(g, b))]
    if not _buildings(g):
        pytest.skip("เมล็ดนี้ไม่มีสิ่งปลูกสร้าง")
    assert ok, "มีอาคารแต่เดินเข้าไม่ได้สักหลัง — ไม่มีประตูที่ใช้ได้จริง"


def test_a_lone_building_is_hollow_with_a_way_in():
    """ทดสอบตัวสร้างอาคารตรง ๆ บนพื้นราบ แยกจากความสุ่มของแผนที่"""
    g = [[T.AIR] * T.W for _ in range(T.H)]
    for x in range(T.W):
        for y in range(150, T.H - T.WATER):
            g[y][x] = T.ROCK
    T._building(g, 300, 149, 60, T.CH_H + 20, T.BRICK, door=True)   # ต้องใหญ่พอให้ตัวจริงเข้าไปยืน
    box = _buildings(g)[0]
    inside = _inside_spots(g, box)
    assert len(inside) >= 20, f"ข้างในตัน ยืนได้แค่ {len(inside)} จุด"
    assert any(_walk_out(g, *p, box) for p in inside), "ไม่มีประตูให้เดินเข้า"


def test_shooting_a_castle_wall_breaks_it():
    """กำแพงใช้ carve ตัวเดียวกับพื้นดิน — ยิงพังได้เหมือนกันหมดโดยไม่ต้องเขียนกฎเพิ่ม"""
    g = [[T.AIR] * T.W for _ in range(T.H)]
    T._building(g, 300, 150, 40, 28, T.BRICK, door=False)
    before = sum(1 for r in g for v in r if v == T.BRICK)
    T.carve(g, 280, 135, 9)
    after = sum(1 for r in g for v in r if v == T.BRICK)
    assert after < before, "ยิงกำแพงปราสาทแล้วไม่พัง"


def test_a_tree_can_be_shot_down_too():
    g = [[T.AIR] * T.W for _ in range(T.H)]
    for y in range(150, 160):
        g[y][300] = T.ROCK
    T._tree(random.Random(3), g, 300, 150)
    before = sum(1 for r in g for v in r if v in (T.TRUNK, T.LEAF))
    assert before > 0
    T.carve(g, 300, 140, 12)
    assert sum(1 for r in g for v in r if v in (T.TRUNK, T.LEAF)) < before, "ยิงต้นไม้แล้วไม่พัง"


def test_leaves_are_not_a_floor():
    """เดินบนพุ่มไม้ไม่ได้ — ไม่งั้นยืนลอยบนยอดต้นไม้"""
    g = [[T.AIR] * T.W for _ in range(T.H)]
    for y in range(40, 50):
        g[y][100] = T.LEAF
    for y in range(120, 130):
        g[y][100] = T.ROCK
    assert T.surface_at(g, 100) == 120, "ใบไม้ถูกนับเป็นพื้นให้ยืน"


def test_the_ground_is_skinned_before_anything_is_planted():
    src = pathlib.Path("bot/games/pvp/terrain.py").read_text(encoding="utf-8")
    body = src[src.index("def generate("):]
    assert body.index("_skin(g)") < body.index("_decorate(rng, g)"), \
        "ปลูกของก่อนทาผิวดิน — หลังคาบ้านจะกลายเป็นหญ้า"


@pytest.mark.parametrize("seed", SEEDS)
def test_roofs_never_turn_into_grass(seed):
    """เช็คผลจริง ไม่ใช่แค่ลำดับบรรทัด"""
    g = T.generate(seed)["grid"]
    for y in range(1, T.H):
        row, above = g[y], g[y - 1]
        for x in range(T.W):
            if row[x] in (T.WOOD, T.BRICK):
                assert above[x] != T.GRASS, f"มีหญ้างอกบนหลังคาที่ ({x},{y})"


# ── 🎁 หีบสมบัติ + 🕳️ กับดัก ──

@pytest.mark.parametrize("seed", SEEDS)
def test_chests_and_traps_land_on_walkable_ground(seed):
    g = T.generate(seed)["grid"]
    props = T.place_props(g, random.Random(seed))
    assert props, "ไม่มีหีบหรือกับดักเลยสักอัน"
    for p in props:
        assert p["kind"] in T.PROPS
        assert T.solid(g, p["x"], p["y"]), f"{p['kind']} ลอยกลางอากาศ"
        assert T._standable(g, p["x"], p["y"]), f"{p['kind']} ไปอยู่บนยอดแหลม เดินไปไม่ถึง"


def test_both_chests_and_traps_show_up_across_maps():
    kinds = set()
    for seed in range(1, 25):
        kinds |= {p["kind"] for p in T.place_props(T.generate(seed)["grid"], random.Random(seed))}
    assert kinds == set(T.PROPS), f"ของบางชนิดไม่เคยโผล่เลย: {set(T.PROPS) - kinds}"


def test_props_do_not_pile_up_in_one_spot():
    xs = sorted(p["x"] for p in T.place_props(T.generate(7)["grid"], random.Random(7)))
    assert all(b - a >= 22 for a, b in zip(xs, xs[1:])), "ของกองอยู่ที่เดียวกัน"


def test_nobody_spawns_standing_on_a_trap():
    for seed in range(1, 21):
        g = T.generate(seed)["grid"]
        rng = random.Random(seed)
        props = T.place_props(g, rng)
        for x, _ in T.spawns(g, 4, rng, avoid=props):
            assert all(abs(x - p["x"]) >= 10 for p in props), \
                f"เมล็ด {seed}: เกิดมาทับกับดัก/หีบพอดี"


# ── 🔒 กับดักต้องไม่รั่วไปให้เบราว์เซอร์ ──

def test_trap_positions_never_reach_the_browser():
    """ส่งพิกัดกับดักไป = เปิด devtools แล้วเดินหลบได้หมด กับดักไร้ความหมายทันที"""
    v = T.view(7, "main", 2)
    assert isinstance(v["traps"], int), "traps ต้องเป็นแค่จำนวน ไม่ใช่รายการพิกัด"
    assert all(p["kind"] != "trap" for p in v["props"]), "พิกัดกับดักหลุดไปกับ props"
    assert "trap" not in json.dumps(v["props"]), "ยังมีคำว่า trap ในข้อมูลที่ส่งออก"


def test_chests_are_visible_because_they_are_meant_to_be():
    seen = [T.view(s, "main", 2) for s in range(1, 12)]
    assert any(p["kind"] == "chest" for v in seen for p in v["props"]), "ไม่มีหีบให้เห็นเลย"


def test_the_browser_draws_every_prop_kind():
    fn = WORMS[WORMS.index("  _prop("):]
    fn = fn[:fn.index("\n  }")]
    assert all(k in fn for k in ("'chest'", "'trap'", "'ferry'")), "เบราว์เซอร์ไม่ได้วาดของครบทุกชนิด"


# ── 🎥 กล้อง: ซูม/เลื่อน/ไปดูคนอื่น ──

def test_the_camera_exists_and_is_wired():
    """แผนที่ใหญ่กว่าจอ ถ้าไม่มีกล้องก็มองไม่เห็นครึ่งสนาม"""
    assert "class WormsCam" in WORMS
    for m in ("zoomAt", "pan", "center", "fit", "attach"):
        assert m + "(" in WORMS, f"กล้องไม่มี {m}"
    for el in ("wmIn", "wmOut", "wmFit", "wmZoom", "wmWho"):
        assert el in HTML and el in PLAY, f"ปุ่มกล้อง #{el} ยังไม่ได้ต่อสาย"


def test_you_can_jump_to_look_at_another_player():
    assert "WM_CAM.center(f.x, f.y - 10)" in PLAY, "กดชื่อคนแล้วกล้องไม่ตามไป"
    assert "data-look=" in PLAY, "ไม่มีปุ่มเลือกคนที่จะไปดู"


def test_pinch_and_wheel_both_zoom():
    assert "touchmove" in WORMS and "wheel" in WORMS, "ซูมได้ทางเดียว มือถือหรือคอมจะเสียไปข้าง"
    assert "touch-action: none" in CSS, \
        "ลากบนมือถือจะกลายเป็นเลื่อนหน้าเว็บแทนการเลื่อนแผนที่"


def test_zoom_stays_on_whole_pixels():
    """ซูมเป็นทศนิยม = พิกเซลอาร์ตเบลอทันที"""
    fn = WORMS[WORMS.index("  zoomAt("):]
    fn = fn[:fn.index("\n  }")]
    assert "Math.round" in fn, "ซูมไม่ได้ปัดเป็นจำนวนเต็ม"


def test_the_camera_never_scrolls_off_the_map():
    assert "clamp()" in WORMS, "ไม่มีการจำกัดขอบกล้อง — ลากไปจนเห็นแต่ท้องฟ้าได้"
    for m in ("pan(", "center(", "fit()"):
        fn = WORMS[WORMS.index("  " + m):]
        fn = fn[:fn.index("\n  }")]
        assert "clamp()" in fn, f"{m} ไม่ได้จำกัดขอบ"


# ── วัสดุสองฝั่งต้องตรงกัน ──

def test_the_material_numbers_match_the_server():
    """เลขวัสดุคนละชุด = บ้านกลายเป็นก้อนหิน ใบไม้กลายเป็นดิน"""
    line = re.search(r"const AIR = 0[^;]*;", WORMS).group(0)
    got = dict(re.findall(r"(\w+) = (\d+)", line))
    for name in ("AIR", "GRASS", "DIRT", "ROCK", "WOOD", "BRICK", "TRUNK", "LEAF"):
        assert int(got[name]) == getattr(T, name), f"เลขวัสดุ {name} ไม่ตรงกับเซิร์ฟเวอร์"


def test_every_continent_lists_all_seven_materials():
    from bot.game_data import CONTINENTS
    block = WORMS[WORMS.index("const WORM_GROUND"):]
    block = block[:block.index("\n};")]
    rows = dict(re.findall(r"^\s{2}(\w+):\s*\[(.*)\],", block, re.M))
    assert set(CONTINENTS) <= set(rows), f"ทวีปที่ยังไม่มีสี: {sorted(set(CONTINENTS) - set(rows))}"
    for name, line in rows.items():
        cols = re.findall(r"'([^']*)'", line)
        assert len(cols) == 7, f"ทวีป {name} มี {len(cols)} สี (ต้องครบ 7 วัสดุ)"
        bad = [c for c in cols if not re.fullmatch(r"#[0-9a-fA-F]{6}", c)]
        assert not bad, f"ทวีป {name} มีสีที่เขียนผิดรูปแบบ: {bad}"


# ── ยิงผ่าน HTTP จริง ──

@pytest.fixture
def web(tmp_path, monkeypatch):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    import bot.models.player_model as pm
    from license_server import web_api

    uid = 6102
    monkeypatch.setattr(pm, "DB_NAME", str(tmp_path / "w.db"))
    pm.init_db()
    pm.get_player(uid)
    monkeypatch.setattr(web_api, "GAME_DB_PATH", tmp_path / "w.db")
    app = FastAPI()
    app.include_router(web_api.router)
    c = TestClient(app)
    c.cookies.set("web_session", web_api.sign({"uid": str(uid), "exp": time.time() + 3600}))
    return c


def test_http_never_leaks_trap_positions(web):
    d = web.get("/api/web/pvp/worms/map?seed=7").json()
    assert isinstance(d["traps"], int)
    assert "trap" not in json.dumps(d["props"], ensure_ascii=False)


def test_http_sends_chests_and_a_trap_count(web):
    d = web.get("/api/web/pvp/worms/map?seed=7").json()
    assert "props" in d and "traps" in d
    g = T.decode(d["terrain"])
    for p in d["props"]:
        assert g[p["y"]][p["x"]] != T.AIR, "หีบที่ส่งมาลอยกลางอากาศ"


@pytest.mark.parametrize("seed", list(range(1, 13)))
def test_a_building_never_digs_a_pit_through_the_ground(seed):
    """ห้องต้องกลวงเฉพาะเหนือพื้น — เจาะทะลุลงไปคือได้หลุมไม่มีก้น ตกลงไปแล้วออกไม่ได้"""
    g = T.generate(seed)["grid"]
    for x0, y0, x1, y1 in _buildings(g):
        for x in range(x0 + 2, x1 - 1):
            floors = [y for y in T.surfaces_at(g, x) if y > y0 + HEAD]
            if len(floors) < 2:
                continue
            # ชั้นล่างสุดต้องเป็นดิน/หินธรรมชาติ ไม่ใช่ช่องว่างที่เจาะทะลุลงไป
            deep = floors[-1]
            assert T.material(g, x, deep) in (T.GRASS, T.DIRT, T.ROCK, T.WOOD, T.BRICK),                 f"เมล็ด {seed}: ใต้บ้านที่ x={x} ไม่มีพื้นรองรับ"


@pytest.mark.parametrize("seed", list(range(1, 13)))
def test_no_tree_grows_through_a_wall(seed):
    """ต้นไม้งอกทะลุปราสาทคือภาพที่ดูออกทันทีว่าพัง และบังประตูจนเข้าไม่ได้"""
    g = T.generate(seed)["grid"]
    for x0, y0, x1, y1 in _buildings(g):
        bad = [(x, y) for x in range(x0 + 1, x1)
               for y in range(y0 + 1, y1 + 1)
               if g[y][x] in (T.TRUNK, T.LEAF)]
        assert not bad, f"เมล็ด {seed}: มีต้นไม้อยู่ในตัวอาคาร {len(bad)} จุด เช่น {bad[:3]}"
