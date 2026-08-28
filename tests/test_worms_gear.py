"""🏹 อาวุธที่เก็บได้ในสนาม + ยาฮีล + การยิงของบนแผนที่ให้พัง

เจ้าของเกมเคาะ (08-28):
  - ธนู/หน้าไม้ เก็บแล้ว **ใช้ได้ตลอด ไม่หมดแบบอาร์ติแฟกต์** แต่มีกระสุน
    หมดแล้วรอรีโหลด · เก็บซ้ำ = กระสุนสะสมเพิ่ม
  - ธนูยิงนัดเดียว · หน้าไม้แยกสามแฉก
  - ยิงตรงยาวก่อนแล้วค่อยตก (ต่างจากลูกไฟที่โค้งตั้งแต่แรก)
  - ยิงโดนเรือเหาะ/หีบ/กับดัก = พัง เรือเหาะระเบิด+ไฟ · หีบไฟ · กับดักระเบิด

จุดที่พังแล้วเจ็บที่สุด:
  1. กระสุนไม่ลด = ยิงรัวทั้งเกม
  2. ระเบิดลูกโซ่วนหาตัวเองไม่จบ (ของพังแล้วยังอยู่ในลิสต์)
  3. เว็บไม่รู้จักของที่พังชั้นใน = หีบหายจากแผนที่แต่ไม่มีภาพอะไรเลย
"""
import pathlib

import pytest

import bot.models.player_model as pm
from bot.pvp import match, physics as P, terrain as T, weapons as W
from license_server import web_db

UID = 7801
LOOK = {"race": "Human", "cls": "Mage", "armor": "None", "weapon": ""}
PLAY = pathlib.Path("license_server/web_static/play.js").read_text(encoding="utf-8")


@pytest.fixture
def world(tmp_path, monkeypatch):
    monkeypatch.setattr(pm, "DB_NAME", str(tmp_path / "g.db"))
    monkeypatch.setattr(web_db, "DB_PATH", tmp_path / "w.db")
    pm.init_db()
    pm.get_player(UID)
    return None


def _flat():
    g = [[T.AIR] * T.W for _ in range(T.H)]
    for x in range(T.W):
        for y in range(200, T.H - T.WATER):
            g[y][x] = T.ROCK
    return g


def _arena(props=None, ammo=None, hp=100):
    match.new_practice(UID, LOOK, seed=7)
    st = match.load(UID)
    st["terrain"] = T.encode(_flat())
    st["props"] = list(props or [])
    st["wind"] = 0
    st["fighters"][0].update(x=150, y=200, face=1, hp=hp, ammo=dict(ammo or {}), cd={})
    st["fighters"][1].update(x=520, y=200, hp=100)
    match.save(UID, st)
    return st


# ── 🏹 วิถีลูกธนู ──

def test_an_arrow_flies_straight_before_it_drops():
    """นี่คือสิ่งที่ทำให้ธนูต่างจากลูกไฟ — ลูกไฟโค้งตั้งแต่เฟรมแรก"""
    g = _flat()
    curve = P.shoot(g, 100, 200, 15, 70, glide=0)
    arrow = P.shoot(g, 100, 200, 15, 70, glide=W.GEAR["bow"]["glide"])
    assert arrow["x"] - 100 > (curve["x"] - 100) * 1.6, \
        f"ธนูไปได้ {arrow['x'] - 100} px · ลูกโค้ง {curve['x'] - 100} px — ไม่ต่างกันพอ"
    early_arrow = arrow["path"][10][1] - arrow["path"][0][1]
    early_curve = curve["path"][10][1] - curve["path"][0][1]
    assert early_arrow < early_curve, "ช่วงต้นวิถีธนูไม่ได้ตรงกว่าลูกโค้ง"


def test_a_normal_shot_is_unchanged():
    """glide ค่าตั้งต้นต้องเป็น 0 ไม่งั้นลูกไฟทุกลูกในเกมเปลี่ยนวิถีเงียบ ๆ"""
    g = _flat()
    assert P.shoot(g, 100, 200, 45, 70)["path"] == \
        P.shoot(g, 100, 200, 45, 70, glide=0)["path"]


# ── 🎒 เก็บแล้วใช้ได้ตลอด แต่มีกระสุน ──

def test_a_weapon_from_a_chest_gives_ammo_not_a_one_use_item(world):
    st = _arena(props=[{"kind": "chest", "x": 150, "y": 200}])
    f = st["fighters"][0]
    got = match._open_chests(st, f)
    assert got, "เดินทับหีบแล้วไม่ได้อะไร"
    key = got[0]["item"]
    if key not in W.GEAR:
        assert f["bag"].get(key) == 1, "อาร์ติแฟกต์ไม่เข้ากระเป๋า"
        return
    assert f["ammo"][key] == W.GEAR[key]["ammo"], "เก็บอาวุธแล้วไม่ได้กระสุน"
    assert key not in f.get("bag", {}), "อาวุธไปโผล่ในกระเป๋าของใช้ครั้งเดียว"


def test_firing_spends_ammo_and_the_weapon_stays(world):
    _arena(ammo={"bow": 2})
    ok, r = match.attack(UID, "bow", angle=15, power=80)
    assert ok, r.get("error")
    f = match.load(UID)["fighters"][0]
    assert f["ammo"]["bow"] == 1, "ยิงแล้วกระสุนไม่ลด"
    assert "bow" in f["ammo"], "ยิงแล้วอาวุธหายไปเลย — ต้องใช้ได้ตลอด"


def test_running_out_of_ammo_starts_a_reload(world):
    _arena(ammo={"bow": 1})
    ok, _ = match.attack(UID, "bow", angle=15, power=80)
    assert ok
    f = match.load(UID)["fighters"][0]
    assert f["ammo"]["bow"] == 0 and f["cd"]["bow"] > 0, "กระสุนหมดแล้วไม่เข้าคูลดาวน์รีโหลด"
    ok, r = match.attack(UID, "bow", angle=15, power=80)
    assert not ok and "กระสุน" in r["error"], "กระสุนหมดแล้วยังยิงได้อีก"


def test_the_reload_refills_the_magazine(world):
    _arena(ammo={"bow": 1})
    match.attack(UID, "bow", angle=15, power=80)
    for _ in range(W.GEAR["bow"]["reload"] + 4):
        st = match.load(UID)
        if st["over"]:
            pytest.skip("แมตช์จบก่อนรีโหลดครบ")
        st["turn_started"] = 0
        match.save(UID, st)
        match.end_turn(UID, auto=True)
        if match.load(UID)["fighters"][0]["ammo"]["bow"] > 0:
            break
    assert match.load(UID)["fighters"][0]["ammo"]["bow"] == W.GEAR["bow"]["ammo"], \
        "รีโหลดครบแล้วกระสุนไม่เต็ม"


def test_you_cannot_use_a_weapon_you_never_picked_up(world):
    _arena()
    ok, r = match.attack(UID, "bow", angle=15, power=80)
    assert not ok and "ยังไม่มีอาวุธ" in r["error"]


# ── 🎯 หน้าไม้ยิงสามแฉก ──

def test_the_crossbow_fires_three_bolts_at_once(world):
    _arena(ammo={"crossbow": 3})
    ok, r = match.attack(UID, "crossbow", angle=15, power=80)
    assert ok, r.get("error")
    volley = r["attack"]["volley"]
    assert len(volley) == W.GEAR["crossbow"]["shots"] == 3, "ไม่ได้ยิงสามแฉก"
    # ⚠️ ต้องเทียบ "ช่วงต้นวิถี" ไม่ใช่จุดตก — ลูกแรกเจาะพื้นเป็นหลุมไว้แล้ว
    #    ลูกหลังบินลอดหลุมไปตกคนละที่อยู่ดี ถึงจะยิงมุมเดียวกันเป๊ะ
    early = {tuple(v["path"][6]) for v in volley}
    assert len(early) == 3, f"ออกจากปากธนูทางเดียวกันหมด ({early}) — ไม่ได้แยกแฉก"
    ends = {tuple(v["path"][-1]) for v in volley}
    assert len(ends) == 3, f"สามลูกไปตกที่เดียวกัน ({ends})"
    assert match.load(UID)["fighters"][0]["ammo"]["crossbow"] == 2, \
        "ยิงสามลูกต้องเสียกระสุนนัดเดียว"


def test_weapons_and_potions_really_come_out_of_chests():
    """หาไม่เจอในหีบ = ของที่ทำมาไม่มีวันได้ใช้"""
    assert set(W.GEAR) <= set(W.CHEST_LOOT),         f"อาวุธที่หีบออกได้: {sorted(set(W.CHEST_LOOT) & set(W.GEAR))}"
    for key in ("herb_potion", "great_potion"):
        assert key in W.ARTIFACTS and W.ARTIFACTS[key].get("heal"), f"ไม่มียาฮีล {key}"
        assert key in W.CHEST_LOOT, f"ยาฮีล {key} ไม่เคยออกจากหีบ"
    gear_share = sum(1 for k in W.CHEST_LOOT if k in W.GEAR) / len(W.CHEST_LOOT)
    assert 0.02 < gear_share < 0.35,         f"โอกาสได้อาวุธ {gear_share:.0%} — อาวุธใช้ได้ตลอด ควรหายากกว่าของใช้ครั้งเดียว"


def test_the_bow_fires_only_one(world):
    _arena(ammo={"bow": 3})
    ok, r = match.attack(UID, "bow", angle=15, power=80)
    assert ok
    assert not r["attack"].get("volley"), "ธนูไม่ควรยิงแยกแฉก"


# ── 💥 ยิงของบนแผนที่ให้พัง ──

def test_shooting_a_ferry_blows_it_up_and_sets_a_fire(world):
    st = _arena(props=[{"kind": "ferry", "x": 300, "y": 200}])
    grid = T.decode(st["terrain"])
    broke = match._explode(st, grid, 300, 194, 26, 40, 26, "เทส")["broke"]
    assert [b["kind"] for b in broke] == ["ferry"], f"เรือเหาะไม่พัง: {broke}"
    assert broke[0]["blast"], "เรือเหาะพังแล้วไม่ระเบิด"
    assert broke[0]["fire"] > 0, "เรือเหาะพังแล้วไม่ติดไฟ"
    assert not st["props"], "พังแล้วยังอยู่บนแผนที่"


def test_shooting_a_chest_sets_a_fire_without_an_explosion(world):
    st = _arena(props=[{"kind": "chest", "x": 300, "y": 200}])
    grid = T.decode(st["terrain"])
    broke = match._explode(st, grid, 300, 194, 20, 30, 14, "เทส")["broke"]
    assert [b["kind"] for b in broke] == ["chest"]
    assert not broke[0]["blast"], "หีบไม้ไม่ควรระเบิด"
    assert broke[0]["fire"] > 0, "หีบพังแล้วไม่ติดไฟ"


def test_shooting_a_trap_sets_it_off(world):
    st = _arena(props=[{"kind": "trap", "x": 300, "y": 200}])
    grid = T.decode(st["terrain"])
    broke = match._explode(st, grid, 300, 194, 20, 30, 14, "เทส")["broke"]
    assert [b["kind"] for b in broke] == ["trap"]
    assert broke[0]["blast"], "กับดักโดนยิงแล้วไม่ลั่น"


def test_a_chain_reaction_ends_and_reports_every_piece(world):
    """ระเบิดลูกโซ่ต้องจบ และของที่พังชั้นในต้องถูกแบนออกมาให้เว็บเห็นด้วย"""
    st = _arena(props=[{"kind": "ferry", "x": 300, "y": 200},
                       {"kind": "chest", "x": 320, "y": 200},
                       {"kind": "trap", "x": 285, "y": 200}])
    grid = T.decode(st["terrain"])
    broke = match._explode(st, grid, 300, 194, 26, 40, 26, "เทส")["broke"]
    assert {b["kind"] for b in broke} == {"ferry", "chest", "trap"}, \
        f"ลูกโซ่ไม่ครบ: {[b['kind'] for b in broke]}"
    assert not st["props"], "ยังมีของค้างบนแผนที่"
    for b in broke:
        assert "broke" not in (b.get("blast") or {}), "ยังซ้อนกันอยู่ ไม่ได้แบนออกมา"


def test_a_used_ferry_is_gone_for_good(world):
    """เจ้าของเกมสั่ง: เรือเหาะที่ใช้แล้วต้องหายไปเลย"""
    # ต้องมีสองเกาะจริง ๆ ไม่งั้นเรือไม่มีที่ให้ไป แล้วมันจะเก็บเรือไว้ (ตั้งใจ)
    g = [[T.AIR] * T.W for _ in range(T.H)]
    for x in list(range(100, 250)) + list(range(400, 550)):
        for y in range(200, T.H - T.WATER):
            g[y][x] = T.ROCK
    st = _arena(props=[{"kind": "ferry", "x": 150, "y": 200}])
    st["terrain"] = T.encode(g)
    match.save(UID, st)
    grid = T.decode(st["terrain"])
    ride = match._ride_ferry(st, grid, st["fighters"][0])
    assert ride, "เดินทับเรือเหาะแล้วไม่ได้ข้ามเกาะ"
    assert not [p for p in st["props"] if p["kind"] == "ferry"], \
        "ใช้แล้วเรือเหาะยังอยู่บนแผนที่"


# ── 🧪 ยาฮีล ──

@pytest.mark.parametrize("key", ["herb_potion", "great_potion"])
def test_potions_exist_and_actually_heal(world, key):
    assert W.ARTIFACTS.get(key, {}).get("heal"), f"ไม่มียาฮีล {key}"
    st = _arena(hp=40)
    st["fighters"][0]["bag"] = {key: 1}
    match.save(UID, st)
    ok, r = match.attack(UID, key)
    assert ok, r.get("error")
    assert r["fighters"][0]["hp"] > 40, "กินยาแล้วเลือดไม่ขึ้น"


# ── ฝั่งเว็บ ──

def test_the_page_plays_the_fire_and_the_broken_things():
    assert "function wmFlames(" in PLAY, "ไม่มีเอฟเฟกต์ไฟ"
    assert "function wmBreakProps(" in PLAY, "ไม่มีภาพของที่โดนยิงพัง"
    assert "wmBreakProps((shot.blast || {}).broke)" in PLAY, "ยิงโดนแล้วไม่เล่นภาพของที่พัง"
    idle = PLAY[PLAY.index("function wmFxIdle("):]
    idle = idle[:idle.index(chr(10) + "}" + chr(10))]
    assert "WM_FIRES" in idle, "ไฟยังลุกอยู่แต่ระบบถือว่าว่างแล้ว"


def test_the_page_flies_every_bolt_of_a_volley():
    assert "a.volley" in PLAY, "เว็บไม่รู้จักการยิงแยกแฉก"
    shot = PLAY[PLAY.index("  if (WM_SHOT) {"):]
    shot = shot[:shot.index("  // เส้นประค้างไว้อีกครู่")]
    assert "WM_SHOT.extra" in shot, "ลูกที่แยกออกไปไม่ได้ถูกวาด"
    assert "if (e.blast) wmLand(e.blast)" in shot, "ลูกที่แยกออกไปไม่ระเบิด"
