"""🌊 ภัยพิบัติหลังครบ 10 รอบ — บีบให้ทุกคนตายอย่างเท่าเทียมกัน

เจ้าของเกมสั่ง (08-28): "หลังผ่านไป 10 รอบ จะเกิดภัยพิบัติตามแต่ละประเภทของแมพ
ที่จะค่อย ๆ บังคับให้ทุกคนตายอย่างเท่าเทียมกัน · แมพน้ำกับทวีปหลักน้ำค่อย ๆ สูงขึ้น
ลาวาก็เหมือนกัน แมพป่าก็บ่อพิษขึ้นมาเรื่อย ๆ · เพื่อเพิ่มโอกาสหนี เรือเหาะจะส่งขึ้นไป
ที่สูงกว่าปัจจุบันเสมอ และเกิดบ่อยขึ้น"

จุดที่พังแล้วเจ็บที่สุด:
  1. ภัยขึ้นตั้งแต่รอบแรก = เกมจบก่อนได้เล่น
  2. เส้นตายขึ้นแต่พื้นไม่หาย = ยืนลอยอยู่บนน้ำได้สบาย ภัยไม่บีบใคร
  3. ตายไม่เท่ากัน — คนที่ยืนต่ำตายก่อนก็ถูก แต่ต้องเป็นเพราะ "ยืนต่ำ" ไม่ใช่สุ่ม
  4. เรือเหาะพาลงที่ต่ำกว่าเดิม = ทางหนีกลายเป็นทางตาย
"""
import pathlib

import pytest

import bot.models.player_model as pm
from bot.pvp import match, terrain as T, weapons as W
from license_server import web_db
from tests import conftest

UID = 8101
LOOK = {"race": "Human", "cls": "Warrior", "armor": "None", "weapon": ""}
PLAY = conftest.play_js_source()
WORMS = pathlib.Path("license_server/web_static/worms.js").read_text(encoding="utf-8")


@pytest.fixture
def world(tmp_path, monkeypatch):
    monkeypatch.setattr(pm, "DB_NAME", str(tmp_path / "g.db"))
    monkeypatch.setattr(web_db, "DB_PATH", tmp_path / "w.db")
    pm.init_db()
    pm.get_player(UID)
    return None


def _solid(st):
    return sum(1 for row in T.decode(st["terrain"]) for v in row if v)


# ── เริ่มตอนไหน ──

def test_nothing_happens_before_the_tenth_round(world):
    """ภัยมาเร็วไป = ยังไม่ทันได้เล่นก็จบ"""
    st = match.new_practice(UID, LOOK, seed=11)
    for r in range(1, match.DISASTER_ROUND + 1):
        st["round"] = r
        assert match._rise_disaster(st) is None, f"รอบ {r} ภัยพิบัติมาแล้ว (ต้องรอถึงรอบ 10)"
        assert not st.get("flood"), "ยังไม่ถึงรอบแต่ระดับภัยขึ้นแล้ว"


def test_it_starts_right_after_the_tenth_round(world):
    # เลขนี้ต้องยึดไว้ — ตั้งไกลเกินไปคือภัยไม่มีวันมา เกมยืดไม่จบเหมือนเดิม
    assert 5 <= match.DISASTER_ROUND <= 15,         f"ภัยมาตอนรอบ {match.DISASTER_ROUND} — เร็ว/ช้าเกินกว่าที่เจ้าของเกมเคาะ (10)"
    st = match.new_practice(UID, LOOK, seed=11)
    st["round"] = match.DISASTER_ROUND + 1
    hit = match._rise_disaster(st)
    assert hit and hit["first"], "ครบรอบแล้วภัยยังไม่เริ่ม"
    assert st["flood"] == match.FLOOD_STEP


# ── ไต่ขึ้นแล้วกลืนจริง ──

def test_the_line_climbs_and_eats_the_ground(world):
    """เส้นตายขึ้นแต่พื้นไม่หาย = ยืนลอยอยู่ได้สบาย ภัยไม่บีบใครเลย"""
    st = match.new_practice(UID, LOOK, seed=11)
    st["round"] = match.DISASTER_ROUND + 1
    lines, ground = [], [_solid(st)]
    for _ in range(4):
        hit = match._rise_disaster(st)
        lines.append(hit["line"])
        ground.append(_solid(st))
        st["round"] += 1
    assert lines == sorted(lines, reverse=True), f"เส้นตายไม่ได้ไต่ขึ้น: {lines}"
    assert ground == sorted(ground, reverse=True), f"พื้นไม่ได้หายไป: {ground}"
    assert ground[0] - ground[-1] > 1000, "พื้นหายน้อยเกินกว่าจะบีบใครได้"


def test_anyone_below_the_line_is_taken(world):
    st = match.new_practice(UID, LOOK, seed=11)
    st["round"] = match.DISASTER_ROUND + 1
    low = st["fighters"][0]
    low["x"], low["y"] = 300, T.H - T.WATER - 2      # ยืนต่ำติดผิวน้ำ
    st["fighters"][1]["y"] = 60                       # อีกคนอยู่สูง
    match._rise_disaster(st)
    assert low["dead"], "ยืนใต้เส้นตายแล้วยังไม่ตาย"
    assert not st["fighters"][1]["dead"], "คนที่อยู่สูงก็โดนไปด้วย"
    # ต้องตายเพราะ "ภัยกลืน" ตรง ๆ ไม่ใช่บังเอิญพื้นหายแล้วร่วงลงน้ำทีหลัง
    # (ปล่อยให้ร่วงเอาเองมีช่องคว้าขอบรอด — ภัยพิบัติต้องไม่มีข้อยกเว้น)
    took = [l for l in st["log"] if "กลืน" in l and low["name"] in l]
    assert took, f"ไม่มีบันทึกว่าภัยกลืนเขาไป: {st['log'][-3:]}"


def test_it_eventually_takes_everyone(world):
    """"บังคับให้ทุกคนตาย" — ปล่อยไว้นานพอต้องไม่มีใครรอด"""
    st = match.new_practice(UID, LOOK, seed=11)
    st["round"] = match.DISASTER_ROUND + 1
    for _ in range(T.H // match.FLOOD_STEP + 2):
        match._rise_disaster(st)
        st["round"] += 1
        if all(f["dead"] for f in st["fighters"]):
            return
    pytest.fail("ภัยไต่ขึ้นจนสุดแผนที่แล้วยังมีคนรอด")


def test_props_below_the_line_go_under_too(world):
    st = match.new_practice(UID, LOOK, seed=11)
    st["round"] = match.DISASTER_ROUND + 1
    st["props"] = [{"kind": "chest", "x": 100, "y": T.H - T.WATER - 1},
                   {"kind": "ferry", "x": 200, "y": 50}]
    match._rise_disaster(st)
    kinds = [p["kind"] for p in st["props"]]
    assert kinds == ["ferry"], f"ของใต้เส้นตายยังลอยอยู่: {kinds}"


# ── แต่ละทวีปเจอภัยคนละแบบ ──

def test_every_continent_has_a_disaster(world):
    from bot.game_data import CONTINENTS

    for cont in CONTINENTS:
        st = {"continent": cont}
        kind = match.disaster_kind(st)
        assert kind in match.DISASTER_NAME, f"ทวีป {cont} ไม่มีภัยพิบัติที่รู้จัก"


def test_water_lava_and_poison_all_exist():
    """เจ้าของเกมยกตัวอย่างมาสามแบบ ต้องมีครบ"""
    assert set(match.DISASTER.values()) >= {"water", "lava", "poison"}
    assert match.DISASTER["ocean"] == "water" and match.DISASTER["main"] == "water"
    assert match.DISASTER["volcanic"] == "lava"
    assert match.DISASTER["sylvan"] == "poison"


# ── 🎈 ทางหนี ──

def test_the_ferry_always_sends_you_higher_once_the_flood_starts(world):
    """เรือเหาะพาลงที่ต่ำกว่าเดิม = ทางหนีกลายเป็นทางตาย"""
    g = [[T.AIR] * T.W for _ in range(T.H)]
    for x in range(100, 160):                       # เกาะที่ยืนอยู่
        for y in range(200, T.H - T.WATER):
            g[y][x] = T.ROCK
    for x in range(250, 600):                       # เกาะต่ำกว่า และกว้างกว่ามาก
        for y in range(232, T.H - T.WATER):         # (สุ่มมั่วจะเลือกอันนี้แทบทุกครั้ง)
            g[y][x] = T.ROCK
    for x in range(640, 680):                       # เกาะสูง เล็กนิดเดียว
        for y in range(120, T.H - T.WATER):
            g[y][x] = T.ROCK
    st = match.new_practice(UID, LOOK, seed=11)
    st["terrain"] = T.encode(g)
    st["flood"] = match.FLOOD_STEP
    st["props"] = [{"kind": "ferry", "x": 130, "y": 200}]
    f = st["fighters"][0]
    f["x"], f["y"] = 130, 200
    ride = match._ride_ferry(st, T.decode(st["terrain"]), f)
    assert ride, "ขึ้นเรือไม่ได้"
    assert ride["y"] < 200, f"เรือพาไปที่ y={ride['y']} ซึ่งไม่ได้สูงกว่าเดิม (200)"


def test_ferries_drop_more_often_during_the_disaster(world):
    st = match.new_practice(UID, LOOK, seed=11)
    st["props"] = []
    st["flood"] = match.FLOOD_STEP
    st["round"] = match.DISASTER_ROUND + 2
    drops = match._supply_drop(st)
    ferries = sum(1 for d in drops if d["kind"] == "ferry")
    assert ferries >= 2, f"ภัยมาแล้วแต่เรือเหาะลงแค่ {ferries} ลำ"


def test_normal_rounds_still_drop_traps(world):
    """ก่อนภัยมา ของที่ลงต้องเหมือนเดิม — ไม่ใช่เปลี่ยนกติกาทั้งเกม"""
    st = match.new_practice(UID, LOOK, seed=11)
    st["props"] = []
    st["round"] = 2
    kinds = {d["kind"] for d in match._supply_drop(st)}
    assert "trap" in kinds, f"รอบปกติไม่มีกับดักลงแล้ว: {kinds}"


# ── 🏹 อาวุธหาง่ายที่สุด ──

def test_weapons_are_the_easiest_thing_to_find():
    """เจ้าของเกมสั่ง: ทำให้ธนู/หน้าไม้ มีให้เก็บง่ายที่สุด"""
    share = sum(1 for k in W.CHEST_LOOT if k in W.GEAR) / len(W.CHEST_LOOT)
    assert share >= 0.4, f"โอกาสได้อาวุธแค่ {share:.0%} — ยังไม่ใช่ของที่เจอง่ายที่สุด"
    per_gear = len(W.CHEST_LOOT) * share / len(W.GEAR)
    per_other = len(W.CHEST_LOOT) * (1 - share) / (len(W.ARTIFACTS) or 1)
    assert per_gear > per_other, "อาวุธแต่ละชิ้นยังเจอยากกว่าอาร์ติแฟกต์แต่ละชิ้น"


# ── ส่งขึ้นเว็บ ──

def test_the_page_is_told_how_high_it_is(world):
    st = match.new_practice(UID, LOOK, seed=11)
    st["round"] = match.DISASTER_ROUND + 1
    match._rise_disaster(st)
    match.save(UID, st)
    v = match.view(UID)
    assert v["flood"] == match.FLOOD_STEP, "ไม่ได้บอกเว็บว่าภัยขึ้นมาเท่าไหร่"
    assert v["flood_line"] == match.flood_line(st), "เส้นตายที่บอกไม่ตรง"
    assert v["disaster"] in match.DISASTER_NAME, "ไม่ได้บอกว่าเป็นภัยแบบไหน"


def test_the_page_counts_down_to_the_disaster(world):
    st = match.new_practice(UID, LOOK, seed=11)
    st["round"] = 4
    match.save(UID, st)
    assert match.view(UID)["disaster_in"] == match.DISASTER_ROUND - 3, \
        "ไม่ได้บอกว่าเหลืออีกกี่รอบภัยจะมา"


def test_the_page_draws_the_rising_surface():
    assert "WORM_FLOOD" in WORMS, "ไม่มีสีของภัยแต่ละแบบ"
    for kind in ("water", "lava", "poison"):
        assert kind + ":" in WORMS.replace("'", "").replace('"', ""), \
            f"ไม่มีสีของภัยแบบ {kind}"
    draw = WORMS[WORMS.index("// น้ำ/ลาวา/บ่อพิษ"):]
    draw = draw[:draw.index("globalAlpha = 1;")]
    line = [l for l in draw.splitlines() if "const wy =" in l]
    assert line and "this.flood" in line[0],         f"เส้นผิวภัยไม่ได้บวกระดับที่ไต่ขึ้นมา: {line}"
    assert "WORM_FLOOD[this.disaster]" in draw, "วาดสีเดียวทุกภัย"
    assert "WM.flood = d.flood" in PLAY, "เว็บไม่ได้อัปเดตระดับภัยจากเซิร์ฟเวอร์"
    assert "function wmWarnDisaster(" in PLAY, "ภัยมาแล้วไม่เตือนผู้เล่น"
