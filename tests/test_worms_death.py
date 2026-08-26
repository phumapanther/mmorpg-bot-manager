"""💀 ตายแล้วร่างระเบิด · เจ็บแล้วจบเทิร์น · เรือเหาะเกาะละลำ

เจ้าของเกมสั่ง:
  - ตายแล้วต้องมีเอฟเฟกต์ระเบิดสร้างความเสียหายรอบด้าน
    รอเอฟเฟกต์จบก่อนถึงจะสรุปว่าใครโดนอะไร ใครแพ้ชนะ
  - ตัวละครไหนเจ็บ = จบเทิร์นของคนที่กำลังเล่นทันที
  - เรือเหาะเหลือเกาะละลำเดียว
"""
import pathlib
import time

import pytest

import bot.models.player_model as pm
from bot.pvp import match, physics as P, terrain as T
from license_server import web_db

UID = 6405
WEB = pathlib.Path("license_server/web_static")
PLAY = (WEB / "play.js").read_text(encoding="utf-8")


@pytest.fixture
def world(tmp_path, monkeypatch):
    monkeypatch.setattr(pm, "DB_NAME", str(tmp_path / "g.db"))
    monkeypatch.setattr(web_db, "DB_PATH", tmp_path / "w.db")
    pm.init_db()
    pm.get_player(UID)
    return None


def _fn(head):
    body = PLAY[PLAY.index(head):]
    return body[:body.index(chr(10) + "}")]


def fresh(seed=7):
    match.new_practice(UID, {"race": "Human", "cls": "Warrior",
                             "armor": "None", "weapon": ""}, seed=seed)
    return match.load(UID)


def flat_arena(gap=16, foe_hp=6):
    """พื้นราบล้วน คู่ต่อสู้เลือดน้อยยืนติดตัว — ตีทีเดียวตาย"""
    fresh()
    g = [[T.AIR] * T.W for _ in range(T.H)]
    for x in range(T.W):
        for y in range(200, T.H - T.WATER):
            g[y][x] = T.ROCK
    st = match.load(UID)
    st["terrain"], st["props"] = T.encode(g), []
    st["fighters"][0].update(x=300, y=200, face=1, hp=100)
    st["fighters"][1].update(x=300 + gap, y=200, hp=foe_hp)
    match.save(UID, st)
    return st


# ── ตายแล้วร่างระเบิด ──

def test_a_corpse_explodes(world):
    flat_arena()
    good, r = match.attack(UID, "basic", angle=0)
    assert good
    assert r.get("deaths"), "ตายแล้วร่างไม่ระเบิด"
    d = r["deaths"][0]
    assert d["blast"]["crater"] > 0, "ระเบิดแล้วไม่เจาะพื้น"
    assert any("ระเบิด" in line for line in r["log"]), "ไม่ได้บันทึกว่าร่างระเบิด"


def test_the_corpse_blast_hurts_whoever_is_near(world):
    """เจ้าของเกมสั่ง: สร้างความเสียหายรอบด้าน"""
    flat_arena(gap=16)
    r = match.attack(UID, "basic", angle=0)[1]
    hits = r["deaths"][0]["blast"]["hits"]
    assert any(h["name"] == "คุณ" for h in hits), \
        "ยืนติดร่างตอนมันระเบิดแล้วไม่เจ็บเลย"


def test_someone_far_away_is_untouched(world):
    """กันแรงเกินจนระเบิดทั้งแผนที่"""
    flat_arena(gap=300)
    st = match.load(UID)
    st["fighters"][1]["hp"] = 1
    match.save(UID, st)
    st = match.load(UID)
    grid = T.decode(st["terrain"])
    st["fighters"][1]["dead"] = True
    out = match._death_blasts(st, grid)
    assert out, "ตั้งฉากผิด — ไม่มีร่างระเบิด"
    assert not any(h["name"] == "คุณ" for h in out[0]["blast"]["hits"]), \
        f"อยู่ห่าง 300 px ยังโดนระเบิดจากร่าง (รัศมี {match.DEATH_RADIUS})"


def test_a_corpse_only_explodes_once(world):
    flat_arena()
    match.attack(UID, "basic", angle=0)
    st = match.load(UID)
    again = match._death_blasts(st, T.decode(st["terrain"]))
    assert not again, "ร่างเดิมระเบิดซ้ำได้เรื่อย ๆ"


def test_a_chain_reaction_resolves(world):
    """ระเบิดของร่างหนึ่งฆ่าอีกคน คนนั้นก็ต้องระเบิดต่อ — และต้องจบ ไม่วนไม่รู้จบ"""
    flat_arena(gap=16)
    st = match.load(UID)
    st["fighters"][0]["hp"] = 3          # เราเลือดน้อย ระเบิดจากร่างบอทจะฆ่าเราต่อ
    st["fighters"][1]["dead"] = True
    match.save(UID, st)
    st = match.load(UID)
    out = match._death_blasts(st, T.decode(st["terrain"]))
    assert len(out) >= 2, f"ลูกโซ่ไม่ทำงาน (ระเบิดแค่ {len(out)} ร่าง)"
    assert all(f.get("boomed") for f in st["fighters"] if f["dead"]), "มีร่างที่ยังไม่ระเบิด"


def test_the_match_ends_only_after_the_blast_is_resolved(world):
    """ระเบิดจากร่างอาจฆ่าคนสุดท้าย — ต้องเช็คจบเกมหลังระเบิด ไม่ใช่ก่อน"""
    body = PLAY  # ฝั่งเซิร์ฟเวอร์เช็คในลำดับที่ถูก
    src = pathlib.Path("bot/pvp/match.py").read_text(encoding="utf-8")
    at = src.index("deaths = _death_blasts(st, grid)")
    assert "_check_over(st)" in src[at:at + 200], "ระเบิดร่างแล้วไม่ได้เช็คว่าเกมจบหรือยัง"


# ── เจ็บแล้วจบเทิร์น ──

def test_getting_hurt_ends_your_turn(world):
    """เจ้าของเกมสั่ง: ตัวเองตกจากที่สูงแล้วเจ็บ ก็จบเทิร์น"""
    fresh()
    g = [[T.AIR] * T.W for _ in range(T.H)]
    for x in range(300, 340):
        for y in range(120, 130):
            g[y][x] = T.ROCK
    for x in range(340, 520):
        for y in range(200, 220):
            g[y][x] = T.ROCK
    st = match.load(UID)
    st["terrain"], st["props"] = T.encode(g), []
    st["fighters"][0].update(x=335, y=120, hp=100)
    st["fighters"][1].update(x=500, y=200)
    match.save(UID, st)

    good, r = match.move(UID, "jump", 1, 1)
    assert good, r.get("error")
    assert r["fighters"][0]["hp"] < 100, "ตกจากที่สูง 80 px แล้วไม่เจ็บ — เทสตั้งฉากผิด"
    assert r.get("auto_ended"), "เจ็บแล้วเทิร์นยังไม่จบ"


def test_walking_without_getting_hurt_keeps_your_turn(world):
    """กันแก้เกินจนเดินนิดเดียวก็จบเทิร์น"""
    flat_arena(gap=300)
    good, r = match.move(UID, "walk", 1, 6)
    assert good and not r.get("auto_ended"), "เดินบนพื้นราบไม่เจ็บเลยแต่จบเทิร์นให้"


def test_the_turn_ends_when_a_trap_hurts_you(world):
    fresh()
    st = match.load(UID)
    me = st["fighters"][0]
    st["props"] = [{"kind": "trap", "x": me["x"] + 3, "y": me["y"]}]
    match.save(UID, st)
    good, r = match.move(UID, "walk", 1, 5)
    assert good, r.get("error")
    if not r.get("sprung"):
        pytest.skip("ก้าวนี้ไม่โดนกับดัก")
    assert r.get("auto_ended"), "เหยียบกับดักเจ็บแล้วเทิร์นยังไม่จบ"


# ── เรือเหาะเกาะละลำ ──

def test_one_ferry_per_island(world):
    dupes = []
    for seed in range(1, 11):
        fresh(seed)
        for _ in range(14):
            st = match.load(UID)
            st["turn_started"] = 0
            match.save(UID, st)
            good, r = match.end_turn(UID, auto=True)
            if not good or r["over"]:
                break
        st = match.load(UID)
        g = T.decode(st["terrain"])
        isles = []
        for f in [p for p in st["props"] if p["kind"] == "ferry"]:
            if any((f["x"], f["y"]) in grp for grp in isles):
                dupes.append(f"เมล็ด {seed} ที่ x={f['x']}")
            isles.append(P.walk_group(g, (f["x"], f["y"])))
    assert not dupes, "เกาะเดียวมีเรือหลายลำ: " + " · ".join(dupes[:4])


# ── ฝั่งเว็บ ──

def test_the_page_plays_each_corpse_blast_in_turn():
    body = _fn("function wmPlayDeaths(")
    assert "wmFocus({ x: d.x, y: d.y }, true)" in body, "ไม่ได้พากล้องไปดูร่างที่ระเบิด"
    assert "wmLand(d.blast)" in body, "ไม่ได้เจาะพื้น/เล่นลูกไฟ"
    assert "wmHoldAt(d.x, d.y, WM_DEATH_HOLD" in body, "ไม่ได้ค้างดูระเบิดก่อนไปต่อ"
    assert "wmPlayVictims(d.blast, null)" in body, "ไม่ได้ไล่ดูคนที่โดนลูกหลง"
    assert "wmStep(" in body, "ร่างระเบิดไม่ได้เข้าคิวขั้นตอน — จะไปทับขั้นอื่น"


def test_the_result_waits_for_the_corpse_blast():
    """สรุปผลต้องอยู่ท้ายสุด หลังเหยื่อและร่างระเบิดเล่นจบหมดแล้ว"""
    body = _fn("function wmShowHit(")
    assert "wmPlayVictims(a, () => wmPlayDeaths(boom, () => WM_AFTER.push(wmCallDeaths)))" in body, \
        "ลำดับผิด — ต้องเป็น เหยื่อ → ร่างระเบิด → สรุปผล"


def test_a_hold_can_watch_a_spot_with_nobody_there():
    body = _fn("function wmHoldAt(")
    assert "wmChunk(-1," in body, "ค้างกล้องที่จุดว่าง ๆ ไม่ได้"
    loop = PLAY[PLAY.index("function wmStartLoop("):PLAY.index("/** วาดนักสู้")]
    assert "wmFocus(af || { x: x, y: y })" in loop, \
        "ท่อนที่ไม่มีตัวใครจะดึงกล้องกลับไปหาคนที่ถึงตาแทน"


def test_walking_deaths_are_played_too():
    body = PLAY[PLAY.index("async function wmDo("):PLAY.index("async function wmEndTurn(")]
    assert "wmPlayDeaths(d.deaths" in body, "ตกตาย/เหยียบกับดักตาย ร่างไม่ระเบิดบนจอ"


# ── 🦘 กระโดดคุมได้: ชาร์จแรง + เอนตัวกลางอากาศ ──

def test_a_charged_jump_goes_further_than_a_tap():
    """เจ้าของเกมอยากให้คุมตัวละครได้สมูทกว่านี้ — เริ่มจากคุมระยะกระโดดเองได้"""
    g = [[T.AIR] * T.W for _ in range(T.H)]
    for x in range(T.W):
        for y in range(200, T.H - T.WATER):
            g[y][x] = T.ROCK
    weak = P.jump(g, 300, 200, 1, 0.35, 0)
    full = P.jump(g, 300, 200, 1, 1.0, 0)
    assert full["x"] - 300 > (weak["x"] - 300) * 1.5,         f"ชาร์จเต็มไป {full['x'] - 300} px แต่แตะเบา ๆ ไป {weak['x'] - 300} px — ต่างกันน้อยไป"
    hi = lambda r: 200 - min(p[1] for p in r["path"])
    assert hi(full) > hi(weak), "ชาร์จเต็มแล้วไม่ได้สูงกว่า"


def test_leaning_changes_where_you_land():
    """แทน 'บังคับซ้ายขวากลางอากาศ' ที่ทำไม่ได้เพราะลอยอยู่แค่ครึ่งวินาที"""
    g = [[T.AIR] * T.W for _ in range(T.H)]
    for x in range(T.W):
        for y in range(200, T.H - T.WATER):
            g[y][x] = T.ROCK
    with_ = P.jump(g, 300, 200, 1, 1.0, 1)
    none = P.jump(g, 300, 200, 1, 1.0, 0)
    against = P.jump(g, 300, 200, 1, 1.0, -1)
    assert with_["x"] > none["x"] > against["x"],         f"เอนตัวไม่มีผล: เอนตาม {with_['x']} · ไม่เอน {none['x']} · เอนสวน {against['x']}"
    assert with_["x"] - against["x"] >= 40,         f"เอนแล้วต่างกันแค่ {with_['x'] - against['x']} px — คุมแทบไม่ได้"


def test_the_jump_arc_is_long_enough_to_read():
    g = [[T.AIR] * T.W for _ in range(T.H)]
    for x in range(T.W):
        for y in range(200, T.H - T.WATER):
            g[y][x] = T.ROCK
    frames = len(P.jump(g, 300, 200, 1, 1.0, 0)["path"])
    assert frames >= 18, f"วิถีมีแค่ {frames} จุด สั้นเกินกว่าจะเป็นกระโดดจริง"
    # ฝั่งเว็บเล่นภาพช้ากว่าเวลาฟิสิกส์ — ค้างจุดละหลายเฟรมแล้วเกลี่ยตำแหน่งระหว่างจุด
    # เวลาฟิสิกส์ 0.38 วิ จึงกลายเป็นภาพที่ดูได้สบายราวหนึ่งวินาที
    import re

    hold = int(re.search(r"path\.length <= \d+ \? \d+ : "
                         r"WM_ANIM\.path\.length <= \d+ \? (\d+)", PLAY).group(1))
    played = frames * hold / 60
    assert played >= 0.8, f"เล่นภาพกระโดดจบใน {played:.2f} วิ เร็วเกินกว่าจะดูออก"
    assert "JUMP_GRAVITY" not in pathlib.Path("bot/pvp/physics.py").read_text(encoding="utf-8"),         "ยังมีแรงโน้มถ่วงแยกสำหรับการกระโดด — แรงโน้มถ่วงควรมีค่าเดียว"


def test_the_jump_values_are_clamped(world):
    """เบราว์เซอร์ส่งค่าเกินมาต้องไม่กระโดดข้ามแผนที่"""
    g = [[T.AIR] * T.W for _ in range(T.H)]
    for x in range(T.W):
        for y in range(200, T.H - T.WATER):
            g[y][x] = T.ROCK
    wild = P.jump(g, 300, 200, 1, 99, 99)
    sane = P.jump(g, 300, 200, 1, 1.0, 1)
    assert wild["x"] == sane["x"], "ส่งค่าเกินมาแล้วกระโดดไกลกว่าเพดาน"


def test_move_passes_the_jump_settings_through(world):
    fresh()
    st = match.load(UID)
    g = [[T.AIR] * T.W for _ in range(T.H)]
    for x in range(T.W):
        for y in range(200, T.H - T.WATER):
            g[y][x] = T.ROCK
    st["terrain"], st["props"] = T.encode(g), []
    st["fighters"][0].update(x=300, y=200)
    st["fighters"][1].update(x=650, y=200)
    match.save(UID, st)
    weak = match.move(UID, "jump", 1, 1, 0.35, 0)[1]["move"]["x"]

    st = match.load(UID)
    st["fighters"][0].update(x=300, y=200)
    st["turn"], st["turn_started"] = 0, time.time()
    st["moves"] = match.MOVE_BUDGET
    match.save(UID, st)
    full = match.move(UID, "jump", 1, 1, 1.0, 1)[1]["move"]["x"]
    assert full > weak, f"move() ไม่ได้ส่งค่ากระโดดต่อ (เบา {weak} · เต็ม+เอน {full})"


def test_the_page_charges_the_jump():
    body = _fn("function wmHoldStart(")
    assert "WM_JUMP = { dir: dir, t0: performance.now() };" in body, "กดปุ่มกระโดดแล้วไม่ชาร์จ"
    assert "if (WM_JUMP) return;" in body, "ชาร์จกระโดดอยู่แล้วลูกศรยังสั่งเดิน"
    stop = _fn("function wmHoldStop(")
    assert "jump_power: wmJumpPower(), lean: wmLean()" in stop, "ปล่อยแล้วไม่ได้ส่งแรง/การเอน"
    assert "if (what === 'walk') return;" in stop,         "ปล่อยลูกศรระหว่างชาร์จแล้วกระโดดออกไปก่อนเวลา"


def test_the_page_shows_the_jump_charge():
    body = _fn("function wmDrawAim(")
    assert "wmJumpPower()" in body, "ชาร์จกระโดดแล้วไม่มีแถบให้เห็น"
    assert "wmLean()" in body, "ไม่มีอะไรบอกว่าจะเอนไปทางไหน"


def test_releasing_one_key_does_not_release_everything():
    """ปล่อยลูกศรระหว่างชาร์จ = แค่เลิกเอน ไม่ใช่กระโดดทันที"""
    assert "wmHoldStop(a[0])" in PLAY, "คีย์บอร์ดยังปล่อยหมดทุกปุ่มพร้อมกัน"
    assert "() => wmHoldStop(a[0])" in PLAY, "ปุ่มบนจอยังปล่อยหมดทุกปุ่มพร้อมกัน"


def test_a_tap_is_a_hop_not_a_leap():
    """เจ้าของเกมทัก: กระโดดจึ๊กหนึ่งยังไกลไป

    เดิมแรงชาร์จเป็นสัดส่วนตรง แตะ 60 ms ก็ได้แรง 0.13 แล้ว = ไป 9 px
    ตอนนี้ใส่โค้ง (ยกกำลัง) แรงช่วงต้นจึงขึ้นช้ากว่าเวลาที่กด
    """
    g = [[T.AIR] * T.W for _ in range(T.H)]
    for x in range(T.W):
        for y in range(200, T.H - T.WATER):
            g[y][x] = T.ROCK
    tap = P.jump(g, 300, 200, 1, min(1.0, 0.02 + 60 / 620), 0)
    assert tap["x"] - 300 <= 4, f"แตะจึ๊กเดียวยังไป {tap['x'] - 300} px (ตัวกว้าง 9 px)"
    assert P.JUMP_CURVE > 1, "ไม่ได้ใส่โค้งให้แรงช่วงต้นขึ้นช้า"


def test_a_full_charge_is_about_your_own_height():
    """สมจริง: กระโดดสุดแรง ≈ สูงเท่าตัวเอง ไม่ใช่ลอยข้ามบ้าน"""
    g = [[T.AIR] * T.W for _ in range(T.H)]
    for x in range(T.W):
        for y in range(200, T.H - T.WATER):
            g[y][x] = T.ROCK
    full = P.jump(g, 300, 200, 1, 1.0, 0)
    high = 200 - min(q[1] for q in full["path"])
    assert T.CH_H * 0.7 <= high <= T.CH_H * 1.3,         f"กระโดดสุดแรงสูง {high} px แต่ตัวสูง {T.CH_H} px — ไม่สมส่วน"


def test_gravity_is_the_same_going_up_and_coming_down():
    """แรงโน้มถ่วงมีค่าเดียวในโลกนี้ — เคยแยกให้ตอนกระโดดเบากว่าเพื่อความลอย"""
    src = pathlib.Path("bot/pvp/physics.py").read_text(encoding="utf-8")
    jump = src[src.index("def jump("):src.index("def blast_damage(")]
    assert "vy += GRAVITY" in jump, "ลูปกระโดดไม่ได้ใช้แรงโน้มถ่วงตัวเดียวกับตอนร่วง"
    assert "JUMP_GRAVITY" not in src, "ยังมีแรงโน้มถ่วงแยกสำหรับการกระโดดอยู่"
