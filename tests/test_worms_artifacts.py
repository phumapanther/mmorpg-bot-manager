"""🏺 อาร์ติแฟกต์เป็นไอเทมโจมตีในสนามรบ

เจ้าของเกมเคาะไว้: ใส่แค่ 8 จาก 11 ชิ้น · หาได้จากหีบในสนามเท่านั้น
**ไม่ดึงจากกระเป๋าในเกมหลัก** เพราะมินิเกมแยกขาดจากเกมปกติ ทุกคนเริ่มมือเปล่าเท่ากัน

จุดที่พังแล้วเจ็บที่สุด:
  1. ใช้ไอเทมที่ไม่มีในมือได้ = ยิงท่าไม้ตายฟรีไม่จำกัด
  2. ใช้แล้วไม่หมด = ยิงซ้ำได้ตลอดเกม
  3. สนามไปแตะกระเป๋าจริงในเกมหลัก (ผิดข้อตกลงหลักของหมวดนี้)
"""
import pathlib
import time

import pytest

import bot.models.player_model as pm
from bot.pvp import match, terrain as T, weapons as W
from license_server import web_db

UID = 6401
WEB = pathlib.Path("license_server/web_static")
PLAY = (WEB / "play.js").read_text(encoding="utf-8")
HTML = (WEB / "play.html").read_text(encoding="utf-8")


@pytest.fixture
def world(tmp_path, monkeypatch):
    monkeypatch.setattr(pm, "DB_NAME", str(tmp_path / "g.db"))
    monkeypatch.setattr(web_db, "DB_PATH", tmp_path / "w.db")
    pm.init_db()
    pm.get_player(UID)
    return None


def arena(cls="Warrior", gap=200, bag=None, top=200):
    """สนามพื้นราบล้วน — ทดสอบไอเทมโดยไม่มีภูมิประเทศมากวน"""
    match.new_practice(UID, {"race": "Human", "cls": cls, "armor": "None", "weapon": ""}, seed=7)
    g = [[T.AIR] * T.W for _ in range(T.H)]
    for x in range(T.W):
        for y in range(top, T.H - T.WATER):
            g[y][x] = T.ROCK
    st = match.load(UID)
    st["terrain"] = T.encode(g)
    st["props"] = []
    st["fighters"][0].update(x=200, y=top, face=1, hp=100, bag=dict(bag or {}),
                             look={**st["fighters"][0]["look"], "cls": cls})
    st["fighters"][1].update(x=200 + gap, y=top, face=1, hp=100)
    match.save(UID, st)
    return st


def _dmg_to_bot(r):
    a = r["attack"]
    hits = (a.get("hits") or []) + ((a.get("blast") or {}).get("hits") or [])
    return sum(h["damage"] for h in hits if h["name"] != "คุณ")


# ── แคตตาล็อก ──

def test_only_eight_artifacts_make_it_into_the_arena():
    """เจ้าของเกมเคาะ: อีก 3 ชิ้นไม่ใส่ในสนาม"""
    assert len(W.ARTIFACTS) == 8, f"มี {len(W.ARTIFACTS)} ชิ้น (ต้องเป็น 8)"


def test_the_names_match_the_main_game_exactly():
    """ชื่อไม่ตรง = ผู้เล่นงงว่ามันคือชิ้นเดียวกับในเกมหลักไหม"""
    from bot import config_loader

    real = {d["name"] for d in config_loader.get_all_items().values()
            if d.get("effect") == "equip_artifact"}
    arena_names = {a["name"] for a in W.ARTIFACTS.values()}
    assert arena_names <= real, f"ชื่อที่ไม่มีในเกมหลัก: {sorted(arena_names - real)}"
    left = {"🎭 แว่นเดี่ยวหน้ากาก", "👝 ถุงเต๋าเทพี", "💠 ปริซึมมานา"}
    assert real - arena_names == left, "รายชื่อที่ไม่ใส่ในสนามไม่ตรงกับที่เคาะไว้"


def test_every_artifact_actually_does_something():
    for key, a in W.ARTIFACTS.items():
        assert a["kind"] in ("lob", "beam", "melee", "self"), f"{key} ไม่รู้จักชนิดนี้"
        if a["kind"] == "self":
            assert a.get("buff") or a.get("heal"), f"{key} ใช้แล้วไม่เกิดอะไรเลย"
        else:
            assert a.get("dmg"), f"{key} เป็นท่าโจมตีแต่ไม่มีดาเมจ"
        assert a["desc"], f"{key} ไม่มีคำอธิบายให้ผู้เล่นอ่าน"


def test_every_buff_an_artifact_grants_actually_exists():
    for key, a in W.ARTIFACTS.items():
        b = a.get("buff")
        assert not b or b in W.BUFFS, f"{key} ให้บัฟ {b} ที่ไม่มีในตาราง"


# ── ต้องมีของถึงจะใช้ได้ ──

def test_you_cannot_use_an_artifact_you_do_not_have(world):
    arena()
    ok, r = match.attack(UID, "flame_ring")
    assert not ok and "ไม่มีไอเทม" in r["error"]


def test_using_an_artifact_consumes_it(world):
    arena(bag={"flame_ring": 1})
    match.attack(UID, "flame_ring", angle=45, power=60)
    assert "flame_ring" not in match.load(UID)["fighters"][0].get("bag", {}), \
        "ใช้แล้วยังอยู่ในกระเป๋า — ยิงซ้ำได้ตลอดเกม"


def test_having_two_leaves_one(world):
    arena(bag={"flame_ring": 2})
    match.attack(UID, "flame_ring", angle=45, power=60)
    assert match.load(UID)["fighters"][0]["bag"]["flame_ring"] == 1


@pytest.mark.parametrize("key", sorted(W.ARTIFACTS))
def test_every_artifact_can_be_used_without_crashing(world, key):
    a = W.ARTIFACTS[key]
    arena(gap=18 if a["kind"] == "melee" else 200, bag={key: 1})
    ok, r = match.attack(UID, key, angle=3 if a["kind"] == "beam" else 42, power=62)
    assert ok, r.get("error")
    assert r["attack"]["name"] == a["name"]


# ── ผลของแต่ละชิ้น ──

def test_the_flame_ring_hits_harder_than_a_plain_fireball(world):
    """ของหายากต้องคุ้มกว่าสกิลประจำคลาส ไม่งั้นเก็บไปทำไม"""
    assert W.ARTIFACTS["flame_ring"]["dmg"] > W.SKILLS["fire"]["dmg"]


def test_the_nether_beads_reach_wider_than_anything_else(world):
    """เจ้าของเกมสั่ง: ใครอยู่ใกล้โดนหมด"""
    others = [s.get("radius", 0) for k, s in W.ALL.items() if k != "nether_beads"]
    assert W.ARTIFACTS["nether_beads"]["radius"] > max(others)


def test_the_twin_blades_swing_more_than_once(world):
    arena(gap=18, bag={"twin_blades": 1})
    once = W.ARTIFACTS["twin_blades"]["dmg"]
    got = _dmg_to_bot(match.attack(UID, "twin_blades")[1])
    assert got > once, f"ฟันรัวแล้วได้ {got} เท่ากับฟันครั้งเดียว ({once})"
    assert W.ARTIFACTS["twin_blades"]["times"] > 1


def test_the_laser_hits_whoever_it_passes_through(world):
    """เคยพลาด: คิดดาเมจแค่ตรงจุดที่ลำแสงชนพื้น ยิงทะลุกลางตัวก็ไม่โดน"""
    arena(gap=200, bag={"divine_staff": 1})
    assert _dmg_to_bot(match.attack(UID, "divine_staff", angle=2, power=70)[1]) > 0, \
        "เลเซอร์พาดผ่านตัวคู่ต่อสู้แต่ไม่โดน"


def test_the_emp_locks_the_target_out_of_skills(world):
    arena(gap=120, bag={"emp_glove": 1})
    r = match.attack(UID, "emp_glove", angle=30, power=50)[1]
    assert "emp" in r["fighters"][1].get("buffs", {}), "ยิง EMP แล้วไม่ติดดีบัฟ"

    st = match.load(UID)
    st["turn"], st["turn_started"] = 1, time.time()
    st["fighters"][1]["bot"] = False        # ให้ลองสั่งโจมตีในฐานะคนโดน EMP
    match.save(UID, st)
    ok, err = match.attack(UID, "basic")
    assert not ok and "EMP" in err["error"], "โดน EMP แล้วยังใช้สกิลได้"


def test_the_feather_boots_cancel_fall_damage(world):
    from bot.pvp import physics as P

    arena(top=150)
    st = match.load(UID)
    st["fighters"][0]["buffs"] = {"feather": 3}
    match.save(UID, st)
    st = match.load(UID)
    before = st["fighters"][0]["hp"]
    hurt = match._fall_hurt(st, st["fighters"][0], 300)
    assert hurt == 0 and st["fighters"][0]["hp"] == before, "ใส่รองเท้าขนนกแล้วยังเจ็บ"
    assert P.fall_damage(300) > 0, "ตก 300 px ปกติต้องเจ็บ"


def test_the_bark_cloak_soaks_exactly_one_hit(world):
    arena(gap=18)
    st = match.load(UID)
    st["fighters"][1]["buffs"] = {"bark": 4}
    match.save(UID, st)
    assert _dmg_to_bot(match.attack(UID, "basic")[1]) == 0, "เปลือกไม้ไม่กันเลย"
    assert "bark" not in match.load(UID)["fighters"][1].get("buffs", {}), \
        "กันแล้วบัฟยังอยู่ — กันได้ไม่จำกัด"


def test_the_ice_scale_sends_damage_back(world):
    arena(gap=18)
    st = match.load(UID)
    st["fighters"][1]["buffs"] = {"reflect": 3}
    match.save(UID, st)
    r = match.attack(UID, "basic")[1]
    assert "สะท้อนกลับ" in " ".join(r["log"]), "ใส่เกล็ดน้ำแข็งแล้วไม่สะท้อน"


def test_reflecting_never_loops_forever(world):
    """สองฝ่ายใส่เกล็ดน้ำแข็งพร้อมกันต้องไม่สะท้อนกันไปมาไม่จบ"""
    arena(gap=18)
    st = match.load(UID)
    st["fighters"][0]["buffs"] = {"reflect": 3}
    st["fighters"][1]["buffs"] = {"reflect": 3}
    match.save(UID, st)
    ok, r = match.attack(UID, "basic")      # ถ้าวนไม่จบ จะค้างหรือ RecursionError ตรงนี้
    assert ok and all(f["hp"] >= 0 for f in r["fighters"])


# ── 🎁 หีบเป็นทางเดียวที่จะได้ของ ──

def _seed_with_a_chest():
    """หาเมล็ดที่มีหีบจริง — ข้ามเทสไปเฉย ๆ ไม่ได้ป้องกันอะไรเลย"""
    for seed in range(1, 40):
        match.new_practice(UID, {"race": "Human", "cls": "Warrior",
                                 "armor": "None", "weapon": ""}, seed=seed)
        st = match.load(UID)
        chest = next((p for p in st["props"] if p["kind"] == "chest"), None)
        if chest:
            return seed, chest
    raise AssertionError("ไม่มีเมล็ดไหนมีหีบเลยใน 40 เมล็ด — วางหีบพังหรือเปล่า")


def test_a_chest_gives_an_artifact(world):
    _, chest = _seed_with_a_chest()
    st = match.load(UID)
    st["fighters"][0]["x"], st["fighters"][0]["y"] = chest["x"] - 3, chest["y"]
    st["turn"], st["moves"] = 0, match.MOVE_BUDGET
    match.save(UID, st)
    ok, r = match.move(UID, "walk", 1, 3)
    assert ok and r["opened"], "เดินทับหีบแล้วไม่ได้อะไร"
    assert r["opened"][0].get("item") in W.ARTIFACTS, "หีบไม่ได้ให้อาร์ติแฟกต์"
    assert r["fighters"][0]["bag"], "ได้ของแต่ไม่เข้ากระเป๋า"


def test_a_chest_always_gives_the_same_thing_for_a_seed(world):
    """แผนที่เดิมต้องได้ของเดิม ไม่งั้นรีโหลดรัวเพื่อรีสุ่มของได้"""
    def open_first():
        _, chest = _seed_with_a_chest()
        st = match.load(UID)
        st["fighters"][0]["x"], st["fighters"][0]["y"] = chest["x"], chest["y"]
        match.save(UID, st)
        st = match.load(UID)
        return (match._open_chests(st, st["fighters"][0]) or [{}])[0].get("item")

    assert open_first() == open_first()


def test_you_start_the_match_with_nothing(world):
    """มินิเกมแยกจากเกมหลัก — เข้าสนามมือเปล่าเท่ากันทุกคน"""
    st = arena()
    match.new_practice(UID, {"race": "Human", "cls": "Warrior",
                             "armor": "None", "weapon": ""}, seed=7)
    for f in match.load(UID)["fighters"]:
        assert not f.get("bag"), f"{f['name']} เริ่มเกมมามีของติดตัวแล้ว"


def test_the_arena_never_touches_the_real_inventory():
    """กติกาเหล็กของหมวดนี้ — ห้ามแตะกระเป๋า/เงิน/EXP ของเกมหลัก"""
    src = pathlib.Path("bot/pvp/match.py").read_text(encoding="utf-8")
    for banned in ("player_model", "inventory", "load_inventory", "update_player"):
        assert banned not in src, f"สนามไปแตะ {banned} ของเกมหลัก"


# ── 🤖 บอทใช้ของเป็น ──

def test_the_bot_uses_artifacts_it_finds(world):
    match.new_practice(UID, {"race": "Human", "cls": "Warrior",
                             "armor": "None", "weapon": ""}, seed=7)
    st = match.load(UID)
    st["fighters"][1]["bag"] = {"flame_ring": 3}
    match.save(UID, st)
    used = False
    for _ in range(10):
        st = match.load(UID)
        st["turn_started"] = 0
        match.save(UID, st)
        ok, r = match.end_turn(UID, auto=True)
        if not ok or r["over"]:
            break
        if any((m.get("attack") or {}).get("skill") == "flame_ring" for m in r["bot_moves"]):
            used = True
            break
    assert used, "บอทมีอาร์ติแฟกต์แต่ไม่เคยหยิบมาใช้"
    assert match.load(UID)["fighters"][1]["bag"].get("flame_ring", 0) < 3, \
        "บอทใช้แล้วของไม่ลด"


def test_an_emp_stops_the_bot_too(world):
    arena()
    st = match.load(UID)
    st["fighters"][1]["buffs"] = {"emp": 3}
    st["turn_started"] = 0
    match.save(UID, st)
    ok, r = match.end_turn(UID, auto=True)
    assert ok and not any(m.get("attack") for m in r["bot_moves"]), \
        "บอทโดน EMP แล้วยังโจมตีได้"


# ── หน้าเว็บ ──

def test_the_item_panel_is_wired():
    assert 'id="wmItems"' in HTML and "wmPaintItems" in PLAY
    assert "WM_ST.items" in PLAY, "หน้าเว็บไม่ได้อ่านรายการไอเทมจากเซิร์ฟเวอร์"


def test_the_server_sends_the_bag_to_the_page(world):
    arena(bag={"flame_ring": 2})
    items = match.view(UID)["items"]
    assert items and items[0]["key"] == "flame_ring" and items[0]["count"] == 2
    assert items[0]["aim"] is True, "ไม่ได้บอกว่าชิ้นนี้ต้องเล็ง"


def test_you_can_aim_downhill():
    """เลเซอร์ใช้ได้จริงแค่มุมเกือบราบ และบางทีต้องยิงลงจากหน้าผา"""
    import re

    m = re.search(r"Math\.max\((-?\d+), Math\.min\((-?\d+), 45", PLAY)
    assert m, "หาช่วงองศาที่ยอมให้เล็งไม่เจอ"
    assert int(m.group(1)) <= 0, "เล็งลงต่ำกว่าแนวราบไม่ได้"


# ── ทุกท่าประชิดต้องทำพื้นแตก ──

MELEE = ["basic", "bash", "heavy", "stab", "twin_blades"]


def real_arena(key, seed=7, adjacent=True):
    """แผนที่จริง ไม่ใช่พื้นราบสังเคราะห์ — ของจริงมีเนิน กำแพง ต้นไม้ระดับอกให้ฟันโดน

    วางคู่ต่อสู้ประชิดตัวด้วย เพราะกรณีอันตรายคือฟันคนที่ยืนบนหิ้งบาง ๆ ข้างเรา
    """
    cls = "Rogue" if key == "stab" else "Warrior"
    match.new_practice(UID, {"race": "Human", "cls": cls,
                             "armor": "None", "weapon": ""}, seed=seed)
    st = match.load(UID)
    me, foe = st["fighters"]
    if key in W.ARTIFACTS:
        me["bag"] = {key: 1}
    me["look"]["cls"] = cls
    if adjacent:
        g = T.decode(st["terrain"])
        for dx in (14, -14, 16, -16, 12, -12):
            y = T.surface_at(g, me["x"] + dx)
            if y is not None:
                foe["x"], foe["y"] = me["x"] + dx, y
                me["face"] = 1 if dx > 0 else -1
                break
    match.save(UID, st)
    return st


def _solid(st):
    return sum(1 for row in T.decode(st["terrain"]) for m in row if m != T.AIR)


@pytest.mark.parametrize("key", MELEE)
def test_every_melee_move_chews_up_the_ground(world, key):
    """เจ้าของเกมทัก: ตีปกติแล้วสิ่งแวดล้อมไม่พังเลย"""
    before = _solid(real_arena(key))
    good, r = match.attack(UID, key)
    assert good, r.get("error")
    assert _solid(match.load(UID)) < before, f"{key} ฟันแล้วพื้นไม่แหว่งเลย"
    assert r["attack"].get("blast"), "ไม่ได้ส่งหลุมกลับไปให้เว็บวาด"


@pytest.mark.parametrize("key", MELEE)
def test_a_melee_crater_never_cuts_the_ground_from_under_anyone(world, key):
    """เจาะระดับอก ไม่ใช่ระดับเท้า — ไม่งั้นฟันทีเดียวคู่ต่อสู้ร่วงทะเลตายทุกครั้ง"""
    from bot.pvp import physics as P

    for seed in range(1, 16):
        real_arena(key, seed=seed)
        match.attack(UID, key)
        st = match.load(UID)
        g = T.decode(st["terrain"])
        for f in st["fighters"]:
            assert f["dead"] or P.standable(g, f["x"], f["y"]),                 f"{key} เมล็ด {seed}: {f['name']} ลอยกลางอากาศ"
        assert not any("จมน้ำ" in line for line in st["log"]),             f"{key} เมล็ด {seed}: เจาะพื้นจนมีคนตกทะเล"


def ledge(key, thick=7, top=200):
    """หิ้งบาง ๆ เหนือน้ำ — จุดที่ "เจาะพื้นใต้เท้า" อันตรายจริง

    บนแผนที่จริงเกาะหนาเป็นสิบพิกเซล เจาะระดับไหนก็ไม่มีใครร่วง
    เทสความปลอดภัยจึงต้องมาวัดกันตรงนี้ ไม่ใช่หวังว่าเมล็ดสุ่มจะบังเอิญบาง
    """
    cls = "Rogue" if key == "stab" else "Warrior"
    match.new_practice(UID, {"race": "Human", "cls": cls,
                             "armor": "None", "weapon": ""}, seed=7)
    g = [[T.AIR] * T.W for _ in range(T.H)]
    for x in range(100, 320):
        for y in range(top, top + thick):
            g[y][x] = T.ROCK
    st = match.load(UID)
    st["terrain"], st["props"] = T.encode(g), []
    me, foe = st["fighters"]
    me.update(x=150, y=top, face=1, bag={key: 1} if key in W.ARTIFACTS else {})
    me["look"]["cls"] = cls
    foe.update(x=166, y=top)
    match.save(UID, st)
    return st


@pytest.mark.parametrize("key", ["basic", "bash", "stab", "twin_blades"])
def test_a_light_hit_never_drops_anyone_through_a_thin_ledge(world, key):
    """ท่าเบาต้องกัดพื้นแค่ผิว ๆ — ไม่ใช่เจาะทะลุหิ้งจนคู่ต่อสู้ร่วงทะเลตายฟรี"""
    ledge(key)
    match.attack(UID, key)
    st = match.load(UID)
    assert not any("จมน้ำ" in line for line in st["log"]),         f"{key} เจาะหิ้งขาดจนมีคนร่วงทะเล"
    assert all(f["hp"] > 0 for f in st["fighters"]), f"{key} ฆ่าคนด้วยการเจาะพื้น"


def test_a_light_hit_still_scuffs_that_ledge(world):
    """กัดพื้นแค่ผิว ๆ ก็ต้องเห็นว่ากัด ไม่ใช่ไม่โดนอะไรเลย"""
    before = sum(1 for row in T.decode(ledge("basic")["terrain"]) for m in row if m != T.AIR)
    match.attack(UID, "basic")
    after = sum(1 for row in T.decode(match.load(UID)["terrain"]) for m in row if m != T.AIR)
    assert after < before, "ต่อยลานราบแล้วพื้นไม่แหว่งเลย — อาการที่เจ้าของเกมทักมา"


def test_a_punch_dents_less_than_a_heavy_swing(world):
    """ตีปกติต้องทำพื้นแตกน้อยกว่าท่าหนัก ไม่งั้นจะมีท่าหนักไว้ทำไม"""
    assert W.SKILLS["basic"]["crater"] < W.SKILLS["heavy"]["crater"]


@pytest.mark.parametrize("key", MELEE)
def test_no_melee_move_is_left_without_a_crater(key):
    """เดิมมีแค่ Heavy Strike ที่ทำพื้นแตก อันอื่นฟันแล้วสิ่งแวดล้อมนิ่งสนิท"""
    assert W.ALL[key].get("crater"), f"{key} ฟันแล้วไม่ทำอะไรกับสิ่งแวดล้อมเลย"
