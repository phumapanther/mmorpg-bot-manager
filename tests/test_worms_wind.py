"""🌬️ ลมในสนามรบ — สุ่มใหม่ทุกเทิร์น เป่ากระสุนวิถีโค้งให้เบน

ยืมกติกามาจาก hedgewars (temp_refs/hedgewars/hedgewars/uTeams.pas:416)
  cWindSpeed := rndSign(GetRandomf * 2 * cMaxWindSpeed)   ← สุ่มใหม่ทุกตา
  Gear^.dX := Gear^.dX + cWindSpeed                       ← บวกเข้าทุกเฟรม

จุดที่พังแล้วเจ็บที่สุด:
  1. ลมแรงเกินจนเล็งยังไงก็ไม่โดน = เกมกลายเป็นเสี่ยงดวง
  2. บอทไม่รู้เรื่องลม ยิงพลาดทุกนัด ผู้เล่นชนะฟรี
  3. ส่งค่าฟิสิกส์จริงไปเบราว์เซอร์ = อ่านค่าแล้วคำนวณจุดตกเป๊ะ ๆ ได้
"""
import pathlib

import pytest

import bot.models.player_model as pm
from bot.pvp import match, physics as P, terrain as T
from license_server import web_db
from tests import conftest

UID = 6601
LOOK = {"race": "Human", "cls": "Mage", "armor": "None", "weapon": ""}
PLAY = conftest.play_js_source()
HTML = pathlib.Path("license_server/web_static/play.html").read_text(encoding="utf-8")


@pytest.fixture
def world(tmp_path, monkeypatch):
    monkeypatch.setattr(pm, "DB_NAME", str(tmp_path / "g.db"))
    monkeypatch.setattr(web_db, "DB_PATH", tmp_path / "w.db")
    pm.init_db()
    pm.get_player(UID)
    return None


def _flat(top=200):
    g = [[T.AIR] * T.W for _ in range(T.H)]
    for x in range(T.W):
        for y in range(top, T.H - T.WATER):
            g[y][x] = T.ROCK
    return g


# ── ฟิสิกส์ ──

def test_wind_pushes_the_shot_the_way_it_blows():
    g = _flat()
    calm = P.shoot(g, 100, 200, 45, 70)["x"]
    tail = P.shoot(g, 100, 200, 45, 70, wind=P.WIND_MAX)["x"]
    head = P.shoot(g, 100, 200, 45, 70, wind=-P.WIND_MAX)["x"]
    assert tail > calm > head, f"ลมไม่มีผลเลย (ตาม {tail} · นิ่ง {calm} · สวน {head})"


def test_the_longer_it_flies_the_more_the_wind_bends_it():
    """ลมสะสมทุกเฟรม ลูกที่ลอยนานกว่าจึงต้องเบนมากกว่า ไม่ใช่เบนเท่ากันหมด"""
    g = _flat()
    short = abs(P.shoot(g, 100, 200, 45, 40, wind=P.WIND_MAX)["x"]
                - P.shoot(g, 100, 200, 45, 40)["x"])
    long_ = abs(P.shoot(g, 100, 200, 45, 90, wind=P.WIND_MAX)["x"]
                - P.shoot(g, 100, 200, 45, 90)["x"])
    assert long_ > short * 2, f"ยิงไกล ({long_}) ไม่ได้โดนลมมากกว่ายิงใกล้ ({short})"


def test_the_wind_is_strong_enough_to_matter_but_not_a_dice_roll():
    """แรงพอให้ต้องเล็งชดเชย แต่ไม่แรงจนเล็งยังไงก็ไม่โดน

    ตัวละครกว้าง 12 px — ลมเต็มแรงต้องเบนเกินตัวคน ไม่งั้นไม่มีใครสนใจ
    แต่ถ้าเบนเกินครึ่งแผนที่ก็เล็งไม่ได้แล้ว กลายเป็นเสี่ยงดวงล้วน
    """
    g = _flat()
    bend = abs(P.shoot(g, 100, 200, 45, 70, wind=P.WIND_MAX)["x"]
               - P.shoot(g, 100, 200, 45, 70)["x"])
    assert bend > T.CH_W * 2, f"ลมเต็มแรงเบนแค่ {bend} px — เบากว่าตัวคนสองเท่า ไม่มีผลจริง"
    assert bend < T.W // 6, f"ลมเต็มแรงเบน {bend} px จากแผนที่กว้าง {T.W} — เล็งไม่ได้แล้ว"


def test_no_wind_shoots_exactly_like_before():
    """ค่าตั้งต้นต้องเป็นลมนิ่ง ไม่งั้นทุกที่ที่เรียก shoot() โดยไม่ส่งลมจะเพี้ยนเงียบ ๆ"""
    g = _flat()
    assert P.shoot(g, 100, 200, 45, 70)["path"] == P.shoot(g, 100, 200, 45, 70, wind=0)["path"]


# ── ในแมตช์ ──

def test_a_new_match_already_has_wind(world):
    st = match.new_practice(UID, LOOK, seed=7)
    assert "wind" in st, "ตาแรกยังไม่มีลม ต้องรอเปลี่ยนตาก่อนถึงจะมี"
    assert abs(st["wind"]) <= P.WIND_MAX, f"ลมแรงเกินเพดาน: {st['wind']}"


def test_the_wind_changes_every_turn(world):
    """ลมคงที่ทั้งแมตช์ = เล็งครั้งเดียวแล้วยิงซ้ำที่เดิมได้ตลอดเกม"""
    match.new_practice(UID, LOOK, seed=3)
    seen = {match.load(UID)["wind"]}
    for _ in range(8):
        st = match.load(UID)
        st["turn_started"] = 0
        match.save(UID, st)
        ok, r = match.end_turn(UID, auto=True)
        if not ok or r["over"]:
            break
        seen.add(match.load(UID)["wind"])
    assert len(seen) >= 3, f"เล่นไปหลายเทิร์นแล้วลมมีแค่ {len(seen)} ค่า"


def test_the_same_seed_always_gets_the_same_wind(world):
    """สุ่มจากเมล็ด ไม่ใช่สุ่มลอย ๆ — ไม่งั้นเทสไล่ผลไม่ได้และรีเพลย์ไม่ตรง"""
    a = match.new_practice(UID, LOOK, seed=42)["wind"]
    b = match.new_practice(UID, LOOK, seed=42)["wind"]
    assert a == b, f"เมล็ดเดียวกันได้ลมคนละค่า ({a} · {b})"


def test_the_wind_actually_reaches_the_shot(world):
    """ต่อสายครบไหม — ยิงมุมแรงเดียวกันในลมคนละทิศต้องตกคนละที่"""
    spots = []
    for wind in (P.WIND_MAX, -P.WIND_MAX):
        match.new_practice(UID, LOOK, seed=11)
        st = match.load(UID)
        st["terrain"] = T.encode(_flat())
        st["fighters"][0].update(x=120, y=200, face=1)
        st["fighters"][1].update(x=520, y=200, face=-1)
        st["wind"] = wind
        match.save(UID, st)
        ok, r = match.attack(UID, "fire", angle=45, power=80)
        assert ok, r.get("error")
        spots.append(r["attack"]["path"][-1][0])
    assert spots[0] > spots[1] + T.CH_W, \
        f"ยิงเหมือนกันในลมคนละทิศแล้วตกที่เดียวกัน ({spots}) — ลมไม่ได้ต่อถึงกระสุน"


def test_the_bot_aims_with_the_wind_it_is_flying_in(world):
    """บอทเล็งด้วยการลองยิงจริง ถ้าไม่ส่งลมให้มันก็เล็งด้วยโลกที่ไม่มีลม พลาดทุกนัด"""
    g = _flat()
    me = {"x": 120, "y": 200}
    target = {"x": 420, "y": 200}
    calm = match._bot_aim(g, me, target, 0)
    windy = match._bot_aim(g, me, target, P.WIND_MAX)
    assert calm and windy, "บอทเล็งไม่ออกเลยทั้งสองแบบ"
    assert (calm[1], calm[2]) != (windy[1], windy[2]), \
        f"ลมเต็มแรงแล้วบอทยังเล็งมุม/แรงเดิม {calm[1:3]} — ไม่ได้ชดเชยลม"

    # และมุมที่มันเลือกตอนมีลม ต้องแม่นกว่าการเล็งแบบไม่สนลมจริง ๆ
    aim = lambda a: a if target["x"] > me["x"] else 180 - a
    naive = P.shoot(g, me["x"], me["y"], aim(calm[1]), calm[2], wind=P.WIND_MAX)
    smart = P.shoot(g, me["x"], me["y"], aim(windy[1]), windy[2], wind=P.WIND_MAX)
    assert abs(smart["x"] - target["x"]) < abs(naive["x"] - target["x"]), \
        "บอทที่ 'ชดเชยลม' ยิงพลาดกว่าบอทที่ไม่สนลม"


def test_the_bot_really_shoots_with_the_wind_it_is_in(world):
    """ต่อสายถึงบอทจริงไหม — เรียกผ่านตาบอทเต็ม ๆ ไม่ใช่เรียก _bot_aim ตรง ๆ

    ถ้าลืมส่งลมตรงจุดที่บอทเรียกใช้ บอทจะเล็งด้วยโลกไร้ลมแล้วยิงพลาดทุกนัด
    ผู้เล่นชนะฟรีโดยไม่ต้องทำอะไร
    """
    for wind in (P.WIND_MAX, -P.WIND_MAX):
        match.new_practice(UID, LOOK, seed=9)
        st = match.load(UID)
        st["terrain"] = T.encode(_flat())
        st["wind"] = wind
        me, bot = st["fighters"]
        me.update(x=140, y=200, face=1)
        bot.update(x=520, y=200, face=-1, cd={}, buffs={}, bag={},
                   look={**bot["look"], "cls": "Mage"})
        grid = T.decode(st["terrain"])

        r = match._bot_attack(st, grid, bot, me)
        assert r and r.get("path"), "บอทไม่ได้ยิงอะไรเลย"
        miss = abs(r["path"][-1][0] - 140)
        # วัดแล้วที่เมล็ด 9 ช่วงห่าง 380: รู้ลมพลาด 11-15 px · ไม่รู้ลมพลาด 28-31 px
        assert miss < 20, f"ลม {wind:+} บอทพลาดไป {miss} px — เหมือนเล็งด้วยโลกไร้ลม"


# ── กติกาเหล็ก: เว็บได้แค่ตัวเลขไว้วาด ──

def test_the_browser_never_sees_the_real_wind_number(world):
    """ส่งค่าฟิสิกส์จริงไป = เปิด devtools แล้วคำนวณจุดตกเป๊ะ ๆ ได้ทุกนัด"""
    st = match.new_practice(UID, LOOK, seed=5)
    v = match.view(UID, st)
    assert v["wind"] == int(v["wind"]), "ส่งลมเป็นทศนิยม = ค่าฟิสิกส์ดิบ ๆ"
    assert -100 <= v["wind"] <= 100, f"ค่าลมที่ส่งไปนอกช่วง -100..100: {v['wind']}"
    assert v["wind"] != st["wind"], "ส่งค่าฟิสิกส์จริงไปให้เบราว์เซอร์ตรง ๆ"


def test_calm_and_full_wind_map_to_the_ends_of_the_bar(world):
    st = match.new_practice(UID, LOOK, seed=5)
    for wind, want in ((0, 0), (P.WIND_MAX, 100), (-P.WIND_MAX, -100)):
        st["wind"] = wind
        assert match.wind_bar(st) == want, f"ลม {wind} ควรเป็นแถบ {want}"


def test_the_page_draws_the_wind_bar():
    assert 'id="wmWind"' in HTML, "ไม่มีแถบลมบนจอ ผู้เล่นเล็งชดเชยไม่ได้"
    assert "function wmPaintWind(" in PLAY, "ไม่มีตัววาดแถบลม"
    assert "wmPaintWind(d.wind" in PLAY, "วาดแถบลมไว้แต่ไม่มีใครเรียก"
