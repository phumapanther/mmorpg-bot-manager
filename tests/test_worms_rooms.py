"""🎪 ห้องเล่นหลายคน — ชวนเพื่อนได้สูงสุด 6 คน แบ่งทีม 3v3 หรือ 2-2-2

เจ้าของเกมสั่ง (08-28): "ทำโหมด PVP ที่สามารถชวนผู้เล่นมาเล่นได้สูงสุด 6 คน
โดยสามารถแบ่งทีมได้แบบ 2-2-2 หรือ 3-3 ได้"

จุดที่พังแล้วเจ็บที่สุด:
  1. **ใครก็สั่งแทนคนอื่นได้** — ของเดิมเช็คแค่ "ตัวปัจจุบันเป็นบอทไหม"
     พอมีคนจริงหลายคนในห้อง เช็คแบบนั้นคือใครกดก็ขยับได้หมด
  2. สถานะแยกกันคนละก้อน = เห็นสนามคนละอัน เล่นด้วยกันไม่ได้
  3. เล่นเป็นทีมแล้วนับผู้ชนะแบบ "เหลือคนเดียว" = เพื่อนร่วมทีมสองคนยืนอยู่
     เกมไม่จบทั้งที่อีกฝั่งตายหมดแล้ว
  4. ทางเล่นคนเดียว (ซ้อมกับบอท) ต้องไม่พังตาม
"""
import pathlib
import re

import pytest

import bot.models.player_model as pm
from bot.pvp import match, rooms
from license_server import web_db

LOOK = {"race": "Human", "cls": "Warrior", "armor": "None", "weapon": ""}
HOST = 9001


@pytest.fixture
def world(tmp_path, monkeypatch):
    monkeypatch.setattr(pm, "DB_NAME", str(tmp_path / "g.db"))
    monkeypatch.setattr(web_db, "DB_PATH", tmp_path / "w.db")
    pm.init_db()
    for uid in range(9001, 9010):
        pm.get_player(uid)
    return None


def _room(n=6, plan=None):
    """เปิดห้องแล้วชวนคนมาให้ครบ n — คืนรหัสห้อง"""
    st = rooms.create(HOST, "หัวห้อง", LOOK)
    for i in range(1, n):
        rooms.join(HOST + i, st["room"], f"เพื่อน{i}", LOOK)
    if plan:
        rooms.set_plan(HOST, plan)
    return st["room"]


# ── เปิดห้อง / เข้าห้อง ──

def test_a_room_holds_up_to_six(world):
    code = _room(6)
    assert len(rooms.load(code)["seats"]) == rooms.MAX_SEATS == 6
    ok, r = rooms.join(9007, code, "คนที่เจ็ด", LOOK)
    assert not ok and "เต็ม" in r["error"], "รับคนที่เจ็ดเข้ามาได้"


def test_a_wrong_code_is_refused(world):
    ok, r = rooms.join(9002, "ZZZZZ", "เพื่อน", LOOK)
    assert not ok and "ไม่มีห้อง" in r["error"]


def test_room_codes_are_easy_to_read_out_loud(world):
    """รหัสมี 0/O หรือ 1/I = พิมพ์ตามเพื่อนบอกแล้วเข้าไม่ได้"""
    for _ in range(50):
        code = rooms.new_code()
        assert len(code) == 5, f"รหัส {code} ยาวไม่เท่ากัน"
        assert not (set(code) & set("O0I1")), f"รหัส {code} มีตัวที่อ่านสับสน"


def test_joining_twice_just_puts_you_back(world):
    code = _room(2)
    ok, _ = rooms.join(9002, code, "เพื่อน1", LOOK)
    assert ok
    assert len(rooms.load(code)["seats"]) == 2, "เข้าซ้ำแล้วได้ที่นั่งเพิ่ม"


def test_you_can_only_sit_in_one_room(world):
    first = _room(2)                       # ต้องมีคนเหลือ ไม่งั้นห้องเก่าปิดไปเลย
    second = rooms.create(9005, "อีกห้อง", LOOK)["room"]
    rooms.join(HOST, second, "หัวห้อง", LOOK)
    assert rooms.room_of(HOST) == second, "ย้ายห้องแล้วยังอยู่ห้องเดิม"
    assert not [s for s in rooms.load(first)["seats"] if s["uid"] == str(HOST)], \
        "ย้ายไปแล้วแต่ยังนั่งค้างอยู่ห้องเก่า"


def test_leaving_hands_the_room_over(world):
    code = _room(3)
    rooms.leave(HOST)
    st = rooms.load(code)
    assert st["host"] != str(HOST), "หัวห้องออกแล้วห้องยังไม่มีหัวใหม่"
    assert len(st["seats"]) == 2


def test_the_last_one_out_closes_the_room(world):
    code = _room(2)
    rooms.leave(HOST)
    rooms.leave(9002)
    assert rooms.load(code) is None, "ไม่มีคนแล้วห้องยังค้างอยู่"


# ── แบ่งทีม ──

def test_both_team_plans_the_owner_asked_for_exist():
    assert "3v3" in rooms.TEAM_PLANS and "2v2v2" in rooms.TEAM_PLANS
    assert rooms.TEAM_PLANS["3v3"]["teams"] == 2
    assert rooms.TEAM_PLANS["3v3"]["size"] == 3
    assert rooms.TEAM_PLANS["2v2v2"]["teams"] == 3
    assert rooms.TEAM_PLANS["2v2v2"]["size"] == 2


def test_choosing_a_plan_spreads_everyone_out(world):
    code = _room(6, "2v2v2")
    teams = [s["team"] for s in rooms.load(code)["seats"]]
    assert sorted(teams) == [0, 0, 1, 1, 2, 2], f"เกลี่ยทีมไม่ลงตัว: {teams}"


def test_only_the_host_picks_the_plan(world):
    _room(3)
    ok, r = rooms.set_plan(9002, "3v3")
    assert not ok and "หัวห้อง" in r["error"]


def test_you_cannot_pile_into_one_team(world):
    code = _room(6, "3v3")
    mine = next(s for s in rooms.load(code)["seats"] if s["uid"] == str(9002))
    full = 1 - mine["team"]
    moved = 0
    for uid in (9002, 9003, 9004, 9005, 9006):
        ok, _ = rooms.set_team(uid, full)
        moved += ok
    got = sum(1 for s in rooms.load(code)["seats"] if s["team"] == full)
    assert got == rooms.TEAM_PLANS["3v3"]["size"], f"ทีมนี้มี {got} คน (ต้องเป็น 3)"


def test_free_for_all_has_no_teams_to_move_between(world):
    _room(3)
    ok, r = rooms.set_team(9002, 1)
    assert not ok and "ตัวใครตัวมัน" in r["error"]


def test_a_plan_that_does_not_fit_cannot_start(world):
    code = _room(5, "3v3")          # 3v3 ต้องมี 6 คนพอดี
    ok, why = rooms.plan_ready(rooms.load(code))
    assert not ok and "6 คน" in why, f"5 คนแต่เริ่ม 3v3 ได้: {why}"


def test_one_person_alone_cannot_start(world):
    code = _room(1)
    ok, why = rooms.plan_ready(rooms.load(code))
    assert not ok and "2 คน" in why


# ── เริ่มเกมจริง ──

def test_starting_builds_one_shared_match(world):
    code = _room(6, "3v3")
    ok, st = match.start_room(HOST)
    assert ok, st
    assert len(st["fighters"]) == 6, "จำนวนนักสู้ไม่ตรงกับคนในห้อง"
    assert not any(f["bot"] for f in st["fighters"]), "ห้องคนจริงแต่มีบอทโผล่มา"
    # ทุกคนต้องเห็นสนามเดียวกัน — เมล็ดกับพื้นเดียวกันเป๊ะ
    seen = {match.view(uid)["seed"] for uid in range(9001, 9007)}
    assert len(seen) == 1, f"เห็นสนามคนละอัน: {seen}"


def test_only_the_host_starts(world):
    _room(6, "3v3")
    ok, r = match.start_room(9003)
    assert not ok and "หัวห้อง" in r["error"]


def test_everyone_spawns_somewhere_they_can_stand(world):
    from bot.pvp import physics as P, terrain as T

    _room(6, "2v2v2")
    ok, st = match.start_room(HOST)
    assert ok
    g = T.decode(st["terrain"])
    for f in st["fighters"]:
        assert P.standable(g, f["x"], f["y"]), f"{f['name']} เกิดในที่ยืนไม่ได้"


# ── 🔒 ใครสั่งได้ตอนไหน ──

def test_you_cannot_move_on_someone_elses_turn(world):
    """ข้อนี้พังแล้วเกมพัง — ใครกดก็ขยับตัวคนอื่นได้หมด"""
    _room(6, "3v3")
    ok, st = match.start_room(HOST)
    assert ok
    now = st["fighters"][st["turn"]]["uid"]
    other = next(f["uid"] for f in st["fighters"] if f["uid"] != now)
    ok2, r = match.move(int(other), "walk", 1, 3)
    assert not ok2 and "ยังไม่ถึงตา" in r["error"], "คนอื่นสั่งเดินแทนได้"
    ok3, _ = match.move(int(now), "walk", 1, 3)
    assert ok3, "เจ้าของตากลับสั่งไม่ได้"


def test_you_cannot_attack_on_someone_elses_turn(world):
    _room(6, "3v3")
    ok, st = match.start_room(HOST)
    now = st["fighters"][st["turn"]]["uid"]
    other = next(f["uid"] for f in st["fighters"] if f["uid"] != now)
    ok2, r = match.attack(int(other), "basic")
    assert not ok2 and "ยังไม่ถึงตา" in r["error"], "คนอื่นสั่งโจมตีแทนได้"


def test_the_page_is_told_whose_turn_it_is(world):
    _room(6, "3v3")
    ok, st = match.start_room(HOST)
    now = int(st["fighters"][st["turn"]]["uid"])
    assert match.view(now)["my_turn"] is True
    other = next(int(f["uid"]) for f in st["fighters"] if int(f["uid"]) != now)
    assert match.view(other)["my_turn"] is False
    assert match.view(other)["me"] != match.view(now)["me"], "ทุกคนคิดว่าตัวเองคือคนเดียวกัน"


def test_what_one_player_does_everyone_else_sees(world):
    """หัวใจของการเล่นด้วยกัน — สถานะต้องมีก้อนเดียว

    เขียนลงแถวส่วนตัวเมื่อไหร่ คนอื่นจะยังเห็นสนามค้างอยู่ที่เดิมตลอดกาล
    """
    _room(6, "3v3")
    ok, st = match.start_room(HOST)
    assert ok
    now = int(st["fighters"][st["turn"]]["uid"])
    other = next(int(f["uid"]) for f in st["fighters"] if int(f["uid"]) != now)
    before = match.view(other)["fighters"][st["turn"]]["x"]

    ok2, _ = match.move(now, "walk", 1, 5)
    assert ok2
    after = match.view(other)["fighters"][st["turn"]]["x"]
    assert after != before,         f"คนหนึ่งเดินไปแล้ว แต่อีกคนยังเห็นอยู่ที่เดิม (x={before})"


def test_ending_a_turn_hands_over_to_the_next_player(world):
    """ไม่มีบอทในห้องคนจริง — จบเทิร์นแล้วต้องไปที่คนถัดไป ไม่ใช่วนกลับมาที่เดิม"""
    _room(6, "2v2v2")
    ok, st = match.start_room(HOST)
    assert ok
    first = st["turn"]
    ok2, r = match.end_turn(int(st["fighters"][first]["uid"]))
    assert ok2
    assert r["turn"] != first, "จบเทิร์นแล้วยังเป็นตาคนเดิม"
    assert not r["fighters"][r["turn"]]["bot"], "ห้องคนจริงแต่ส่งตาให้บอท"


# ── 🏁 แพ้ชนะแบบทีม ──

def test_a_team_wins_when_the_other_side_is_gone(world):
    """เหลือเพื่อนร่วมทีมสองคนก็ต้องจบแล้ว ไม่ใช่รอให้เหลือคนเดียว"""
    _room(6, "3v3")
    ok, st = match.start_room(HOST)
    for f in st["fighters"]:
        if f["team"] == 1:
            f["dead"], f["hp"] = True, 0
    match._check_over(st)
    assert st["over"], "อีกฝั่งตายหมดแล้วเกมยังไม่จบ"
    assert st["winner"] == rooms.TEAM_NAME[0], f"ผู้ชนะเพี้ยน: {st['winner']}"


def test_a_team_game_is_not_over_while_both_sides_stand(world):
    _room(6, "3v3")
    ok, st = match.start_room(HOST)
    st["fighters"][0]["dead"] = True
    match._check_over(st)
    assert not st["over"], "ตายคนเดียวแล้วจบเกมทั้งที่ทีมยังเหลือคน"


def test_free_for_all_still_ends_with_one_survivor(world):
    _room(3)                       # ตัวใครตัวมัน
    ok, st = match.start_room(HOST)
    assert ok
    for f in st["fighters"][1:]:
        f["dead"] = True
    match._check_over(st)
    assert st["over"] and st["winner"] == st["fighters"][0]["name"]


# ── ทางเล่นคนเดียวต้องไม่พัง ──

def test_practice_against_the_bot_still_works(world):
    st = match.new_practice(9009, LOOK, seed=7)
    assert len(st["fighters"]) == 2 and st["fighters"][1]["bot"]
    assert st["fighters"][0]["uid"] == "9009", "ผู้เล่นในโหมดซ้อมไม่มีเจ้าของ"
    ok, _ = match.move(9009, "walk", 1, 3)
    assert ok, "โหมดซ้อมสั่งเดินไม่ได้แล้ว"
    assert not match.load(9009).get("room"), "โหมดซ้อมไปผูกกับห้อง"


def test_sitting_in_a_room_hides_your_practice_match(world):
    """อยู่ห้องแล้วต้องเห็นสนามของห้อง ไม่ใช่สนามซ้อมเก่าของตัวเอง"""
    match.new_practice(HOST, LOOK, seed=7)
    _room(2)
    assert match.load(HOST) is None, "อยู่ห้องแต่ยังโหลดสนามซ้อมเก่ามา"
    ok, _ = match.start_room(HOST)
    assert ok
    assert match.load(HOST)["room"], "เริ่มห้องแล้วยังไม่ได้สนามของห้อง"


def test_leaving_the_room_gives_you_your_own_game_back(world):
    match.new_practice(HOST, LOOK, seed=7)
    _room(2)
    rooms.leave(HOST)
    st = match.load(HOST)
    assert st and not st.get("room"), "ออกจากห้องแล้วกลับไปเล่นคนเดียวไม่ได้"

# ── ฝั่งเว็บ ──

def test_the_lobby_button_is_separate_from_practice():
    """เจ้าของเกมสั่ง: ทำปุ่มแยกออกมาจากซ้อมกับบอท"""
    html = pathlib.Path("license_server/web_static/play.html").read_text(encoding="utf-8")
    assert 'id="wmRoomOpen"' in html, "ไม่มีปุ่มชวนเพื่อน"
    assert 'id="wmRoomJoin"' in html, "ไม่มีปุ่มเข้าห้องด้วยรหัส"
    # ต้องอยู่คนละแถวกับปุ่มซ้อมกับบอท ไม่ใช่ยัดรวมกันจนแยกไม่ออก
    open_at, new_at = html.index('id="wmRoomOpen"'), html.index('id="wmNew"')
    between = html[min(open_at, new_at):max(open_at, new_at)]
    assert 'class="g-grid wm-buttons"' in between, "ปุ่มชวนเพื่อนอยู่แถวเดียวกับปุ่มซ้อม"
    assert "ซ้อมกับบอท" in html, "ปุ่มซ้อมกับบอทหายไป"


def test_the_page_locks_input_when_it_is_not_your_turn():
    """เซิร์ฟเวอร์ปฏิเสธอยู่แล้ว แต่ต้องล็อกฝั่งจอด้วย ไม่งั้นตัวเดินไปแล้วเด้งกลับ"""
    play = pathlib.Path("license_server/web_static/play.js").read_text(encoding="utf-8")
    body = play[play.index("function wmWaiting("):]
    body = body[:body.index(chr(10) + "}" + chr(10))]
    assert "WM_ST.my_turn === false" in body, "ไม่ใช่ตาเราแต่ยังกดได้"


def test_the_page_keeps_checking_while_others_play():
    """ไม่มีตัวนี้ = นั่งมองจอนิ่ง ๆ ไม่มีวันรู้ว่าถึงตาตัวเองแล้ว"""
    play = pathlib.Path("license_server/web_static/play.js").read_text(encoding="utf-8")
    body = play[play.index("function wmPeekTurn("):]
    body = body[:body.index(chr(10) + "}" + chr(10))]
    assert "fillWorms()" in body, "ไม่ได้ถามสถานะซ้ำเลย"
    assert "WM_ST.my_turn" in body, "ถามซ้ำแม้ตอนเป็นตาตัวเอง = ยิงคำสั่งฟรีทั้งเทิร์น"
    assert "wmPeekTurn();" in play, "เขียนไว้แต่ไม่มีใครเรียก"


def test_the_lobby_polls_so_you_see_friends_arrive():
    play = pathlib.Path("license_server/web_static/play.js").read_text(encoding="utf-8")
    assert "function wmRoomWatch(" in play, "เพื่อนเข้าห้องแล้วเราไม่เห็น"
    body = play[play.index("function wmRoomWatch("):]
    body = body[:body.index(chr(10) + "}" + chr(10))]
    assert "setInterval" in body and "clearInterval" in body,         "ตั้งตัวจับเวลาแล้วไม่มีทางหยุด = ถามซ้ำตลอดกาลแม้ออกจากห้องแล้ว"

def test_the_menu_tile_says_what_the_mode_actually_is():
    """เจ้าของเกมสั่ง: ปุ่มหน้าเข้าเกมต้องเป็น "สนามรบผลัดเทิร์น"

    เดิมเขียนว่า "ซ้อมกับบอท" ซึ่งตอนนี้ไม่จริงแล้ว — โหมดนี้ชวนเพื่อนได้ 6 คน
    ชื่อปุ่มบอกแค่ครึ่งเดียวของสิ่งที่กดเข้าไปเจอ
    """
    html = pathlib.Path("license_server/web_static/play.html").read_text(encoding="utf-8")
    tile = html[html.index('data-go="worms"'):]
    tile = tile[:tile.index("</button>")]
    # ⚠️ ต้องดู "ชื่อปุ่ม" คือข้อความก่อน <span class="sub"> ไม่ใช่ค้นทั้งปุ่ม
    #    ของเดิมมีคำว่าสนามรบผลัดเทิร์นอยู่ในบรรทัดคำอธิบายอยู่แล้ว ค้นรวม ๆ เลยผ่านทุกที
    # ใช้ regex แทน index() ตรง ๆ — IDE จัดรูปแบบใหม่แยก ">" ของ <span class="sub"
    #    ไปคนละบรรทัดได้ (</span\n  >), ยอมให้มีช่องว่าง/ขึ้นบรรทัดใหม่ก่อน ">"
    m = re.search(r'</span>(.*?)<span class="sub"\s*>', tile, re.S)
    assert m, f"หาโครงสร้าง <span class=\"sub\"> ไม่เจอ: {tile!r}"
    label = m.group(1)
    assert label.strip() == "สนามรบผลัดเทิร์น", f"ชื่อปุ่มคือ {label.strip()!r}"
    sub = tile[m.end():]
    assert "ชวนเพื่อน" in sub, f"คำอธิบายไม่ได้บอกว่าชวนเพื่อนได้: {sub!r}"


# ── ค้างในห้องแล้วซ้อมกับบอทไม่ได้ (เจ้าของเกมเจอ 08-28) ──

def test_opening_a_room_does_not_block_practice(world):
    """เปิดห้องทิ้งไว้แล้วกดซ้อมกับบอท ต้องได้เล่นจริง ไม่ใช่ค้างหน้าเริ่มเกม

    บั๊กที่เจอ: เปิดห้องแล้วไม่ได้ปิด → match.load() เห็นว่ายังอยู่ในห้องที่ยัง
    ไม่เริ่ม เลยคืน None ทิ้งแมตช์ซ้อมที่เพิ่งสร้างไปเฉย ๆ
    view() จึงตอบ active=False → เว็บขึ้นหน้า "เริ่มเกม" ทับ กดอะไรก็ไม่ไป
    """
    rooms.create(HOST, "หัวห้อง", LOOK)
    match.new_practice(HOST, LOOK, seed=7)
    assert match.view(HOST)["active"] is True


def test_practice_gives_you_a_bot_to_fight(world):
    """ซ้อมกับบอทต้องมีบอทให้ตีจริง — ไม่ใช่ยืนคนเดียวในสนาม"""
    rooms.create(HOST, "หัวห้อง", LOOK)
    match.new_practice(HOST, LOOK, seed=7)
    v = match.view(HOST)
    assert sum(1 for f in v["fighters"] if f.get("bot")) >= 1


def test_practice_leaves_the_room_behind(world):
    """กดซ้อมกับบอท = ลุกจากห้องเดิม ไม่ค้างที่นั่งไว้ให้คนอื่นรอเก้อ"""
    code = rooms.create(HOST, "หัวห้อง", LOOK)["room"]
    match.new_practice(HOST, LOOK, seed=7)
    assert rooms.room_of(HOST) is None
    assert rooms.load(code) is None          # คนเดียวในห้อง = ห้องปิดไปด้วย


def test_every_action_works_after_opening_a_room(world):
    """กระโดด/ยอมแพ้/จบเทิร์น ต้องใช้ได้หลังเคยเปิดห้องทิ้งไว้

    ทั้งสามเดินผ่าน match.load() ตัวเดียวกัน — พอ load() คืน None
    ทุกปุ่มจึงตายพร้อมกันหมด ไม่ใช่บั๊กแยกกันสามตัว
    """
    rooms.create(HOST, "หัวห้อง", LOOK)
    match.new_practice(HOST, LOOK, seed=7)
    for act in (lambda: match.move(HOST, "jump", 1),
                lambda: match.end_turn(HOST),
                lambda: match.surrender(HOST)):
        ok, r = act()
        assert r.get("error") != "ยังไม่ได้เริ่มแมตช์", r
