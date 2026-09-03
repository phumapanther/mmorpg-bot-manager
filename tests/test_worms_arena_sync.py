"""🧭 พื้นบนจอต้องตรงกับพื้นจริง · บอทยิงต้องเห็น · ของลงสนามกล้องพาไปดู

เจ้าของเกมเจอเอง: "บนจอยังเห็นพื้น แต่เหยียบไม่ได้ ร่วงทะลุ"

ต้นเหตุ: ฝั่งเว็บถอดรหัสพื้นครั้งเดียวตอนเปิดสนาม หลังจากนั้นพื้นเปลี่ยนได้
จาก carve() ที่เราสั่งเองเท่านั้น — และทางกดจบเทิร์นไม่เคยเล่นภาพที่บอทยิงเลย
หลุมที่เซิร์ฟเวอร์เจาะไปแล้วจึงไม่ถูกลบบนจอ กลายเป็นพื้นผีที่เหยียบแล้วร่วง
"""
import pathlib
import time

import pytest

import bot.models.player_model as pm
from bot.pvp import match, physics as P, terrain as T
from license_server import web_db
from tests import conftest

UID = 6403
WEB = pathlib.Path("license_server/web_static")
PLAY = conftest.play_js_source()
WORMS = (WEB / "worms.js").read_text(encoding="utf-8")


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


# ── พื้นที่เซิร์ฟเวอร์เจาะ ต้องส่งถึงเว็บทุกครั้ง ──

def test_the_bot_turn_reports_its_attack(world):
    """เว็บจะลบหลุมตามได้ก็ต่อเมื่อเซิร์ฟเวอร์บอกว่าบอทยิงอะไรไปตรงไหน"""
    seen = 0
    for seed in range(1, 16):
        fresh(seed)
        for _ in range(8):
            st = match.load(UID)
            st["turn_started"] = 0
            match.save(UID, st)
            good, r = match.end_turn(UID, auto=True)
            if not good or r["over"]:
                break
            shots = [m["attack"] for m in (r.get("bot_moves") or []) if m.get("attack")]
            for a in shots:
                seen += 1
                if a.get("blast"):
                    assert "crater" in a["blast"], "ระเบิดแล้วไม่บอกขนาดหลุม เว็บลบตามไม่ได้"
                    assert "x" in a["blast"] and "y" in a["blast"], "ไม่บอกว่าหลุมอยู่ตรงไหน"
    assert seen >= 5, f"เล่น 15 เมล็ดแล้วบอทยิงแค่ {seen} ครั้ง — เทสตั้งฉากผิด"


def test_the_terrain_the_server_sends_matches_its_own_grid(world):
    """สตริงพื้นที่ส่งขึ้นเว็บต้องเป็นผืนเดียวกับที่เซิร์ฟเวอร์ใช้ตัดสิน"""
    fresh()
    st = match.load(UID)
    st["fighters"][0]["look"]["cls"] = "Mage"
    match.save(UID, st)
    r = match.attack(UID, "fire", angle=40, power=70)[1]
    grid = T.decode(r["terrain"])
    for f in r["fighters"]:
        if not f["dead"]:
            assert P.standable(grid, f["x"], f["y"]), \
                f"{f['name']} ยืนบนพื้นที่ไม่มีอยู่ในสตริงที่ส่งไป"


def test_a_hole_the_bot_blows_is_really_gone_in_the_payload(world):
    """เจาะแล้วสตริงพื้นต้องเปลี่ยนจริง ไม่ใช่เปลี่ยนแค่ในหน่วยความจำ"""
    fresh()
    before = match.load(UID)["terrain"]
    st = match.load(UID)
    st["fighters"][0]["look"]["cls"] = "Mage"
    match.save(UID, st)
    r = match.attack(UID, "fire", angle=40, power=70)[1]
    assert r["terrain"] != before, "ยิงระเบิดแล้วสตริงพื้นไม่เปลี่ยนเลย"


# ── ฝั่งเว็บ ──

def test_the_page_can_reload_the_whole_ground():
    assert "reload(terrain) {" in WORMS, "ไม่มีทางโหลดพื้นใหม่ทั้งผืน"
    assert "decodeTerrain(terrain, this.w, this.h)" in WORMS, "โหลดใหม่แต่ไม่ได้ถอดรหัส"


def test_the_page_compares_its_ground_with_the_server_every_frame():
    body = _fn("function wmTick(")
    assert "WM_ST.terrain !== WM_GROUND" in body, "ไม่ได้เทียบพื้นบนจอกับของเซิร์ฟเวอร์"
    assert "WM.reload(WM_ST.terrain)" in body, "เทียบแล้วไม่ได้โหลดใหม่"


def test_the_reload_waits_for_the_animation():
    """โหลดทับตอนภาพยังเล่นอยู่ = หลุมโผล่ก่อนกระสุนจะบินถึง"""
    body = _fn("function wmTick(")
    at = body.index("WM_ST.terrain !== WM_GROUND")
    assert "!wmBusyFx()" in body[max(0, at - 200):at], "ไม่ได้รอให้ภาพเล่นจบก่อนโหลดพื้นใหม่"


def test_a_new_match_remembers_the_ground_it_started_with():
    body = PLAY[PLAY.index("function wmApply("):PLAY.index("function wmMe(")]
    assert "WM_GROUND = d.terrain;" in body, \
        "เปิดสนามใหม่แล้วไม่ได้จำพื้นตั้งต้น — จะโหลดซ้ำทุกเฟรม"


def test_both_ways_into_the_bot_turn_replay_its_shots():
    body = _fn("function wmQueueBot(")
    stay = body[body.index("if (!moves.length) {"):body.index("// เดินเป็นขั้นหนึ่ง")]
    assert "wmPlayBotShots(shots)" in stay, "บอทยืนยิงอยู่กับที่แล้วไม่มีใครเล่นภาพ"
    assert "wmStep(() => {" in body, "ตาบอทไม่ได้เข้าคิวขั้นตอน"
    assert body.index("wmStep(() => {") < body.index("wmPlayBotShots(shots);", body.index("// เดินเป็นขั้นหนึ่ง")), "บอทเดินยังไม่จบก็ยิงทับเลย"


def test_the_bot_shots_no_longer_guess_the_timing():
    assert "setTimeout" not in _fn("function wmPlayAttack("), \
        "ยังใช้ setTimeout เดาเวลาแทนที่จะรอภาพเล่นจบจริง"
    body = _fn("function wmPlayBotShots(")
    assert "wmStep(() => wmShowHit(a, true), wmFxIdle)" in body, "ยิงหลายนัดจะทับกันเอง ไม่ได้เข้าคิวทีละนัด"


# ── 👥 เทิร์นของคนอื่นต้องมีภาพให้ดู (เจ้าของเกมเจอ 08-29) ──
#
# "เทิร์นของคนอื่น เวลาคนอื่นขยับหรือทำอะไร มันไม่เห็นการกระทำ
#  และไม่มีอนิเมชั่นการกระทำด้วย"
#
# ต้นเหตุ: เกมมีทางเล่นภาพ 2 ทาง และไม่มีทางไหนครอบคลุมผู้เล่นคนอื่นเลย
#   เราเดินเอง -> wmDo() ต่อคิวภาพเอง
#   บอทเดิน   -> wmQueueBot(d) จากคำตอบตอนเราจบเทิร์น
#   เพื่อนเดิน -> wmPeekTurn() -> fillWorms() -> wmApply() = ได้แค่พิกัดใหม่ ตัววาป
# view() ไม่เคยส่งข้อมูลการเคลื่อนไหว และสถานะก็ไม่ได้เก็บไว้ด้วยซ้ำ


def test_the_state_remembers_what_just_happened(world):
    """เซิร์ฟเวอร์ต้องจำ "เทิร์นล่าสุดเกิดอะไร" ไม่ใช่จำแค่ว่าใครอยู่ตรงไหน"""
    st = match.new_practice(UID, {}, seed=5)
    before = st.get("turn_seq", 0)
    match.move(UID, "walk", 1, steps=3)
    st = match.load(UID)
    assert st.get("last_turn"), "ไม่ได้เก็บว่าเทิร์นล่าสุดเกิดอะไร คนอื่นจึงไม่มีภาพให้ดู"
    assert st["turn_seq"] > before, "ไม่มีเลขลำดับ เบราว์เซอร์แยกไม่ออกว่าอันไหนดูไปแล้ว"


def test_other_players_get_the_movement_path(world):
    """view() ต้องส่งเส้นทางเดินมาด้วย ไม่งั้นวาดได้แค่จุดปลายทาง = ตัววาป"""
    match.new_practice(UID, {}, seed=5)
    match.move(UID, "walk", 1, steps=3)
    v = match.view(UID)
    lt = v.get("last_turn") or {}
    assert lt.get("moves"), "ไม่ส่งการเคลื่อนไหวมาเลย"
    assert (lt["moves"][0].get("path") or []), "ส่งมาแต่ไม่มีเส้นทาง วาดเป็นอนิเมชันไม่ได้"


def test_the_replay_number_lets_the_browser_skip_what_it_saw(world):
    """เลขลำดับต้องนิ่งเมื่อไม่มีใครทำอะไร ไม่งั้นโพลทีก็เล่นภาพซ้ำที"""
    match.new_practice(UID, {}, seed=5)
    match.move(UID, "walk", 1, steps=3)
    a = match.view(UID)["turn_seq"]
    b = match.view(UID)["turn_seq"]
    assert a == b, "ถามเฉย ๆ ไม่ได้ทำอะไร เลขไม่ควรขยับ"
    # ...แต่พอมีคนทำอะไรจริง เลขต้องเดินหน้า
    # เลขค้างที่เดิม = เบราว์เซอร์เล่นภาพแรกครั้งเดียวแล้วตาบอดตลอดกาล
    match.move(UID, "walk", 1, steps=2)
    assert match.view(UID)["turn_seq"] > b, "เดินอีกรอบแต่เลขไม่ขยับ — คนอื่นจะตาบอดตั้งแต่เทิร์นที่สอง"


def test_the_browser_plays_what_it_has_not_seen_yet():
    """ฝั่งเบราว์เซอร์ต้องเล่นภาพเทิร์นที่ยังไม่เคยดู แทนที่จะล้างคิวทิ้งอย่างเดียว"""
    body = _fn("function wmApply(")
    assert "wmQueueOther" in body, "wmApply ไม่เคยเรียกตัวเล่นภาพของคนอื่นเลย"
    seen = _fn("function wmQueueOther(")
    # เลขลำดับมาใน last_turn.seq — ต้องเทียบกับของที่ดูไปแล้วก่อนเล่น
    assert "WM_SEEN_TURN" in seen, "ไม่ได้จำว่าดูถึงเทิร์นไหนแล้ว"
    assert "seq <= WM_SEEN_TURN" in seen.replace("lt.", ""),         "ไม่ได้ข้ามเทิร์นที่ดูไปแล้ว จะเล่นซ้ำทุกครั้งที่โพล"
    assert "WM_QUEUE.push" in seen, "ไม่ได้ต่อคิวภาพเดินของคนอื่น"


def test_practice_never_plays_the_bot_twice():
    """ซ้อมกับบอทมี wmQueueBot() เล่นภาพอยู่แล้ว

    wmEndTurn เรียก wmApply(d) แล้วตามด้วย wmQueueBot(d)
    ถ้า wmApply ต่อคิวให้ด้วย บอทจะเดินสองรอบกลางแมตช์
    """
    body = _fn("function wmApply(")
    line = [l for l in body.split(chr(10)) if "wmQueueOther(d)" in l]
    assert line, "wmApply ไม่เรียกตัวเล่นภาพของคนอื่น"
    assert "d.room" in line[0],         "ไม่ได้จำกัดเฉพาะห้องหลายคน — ซ้อมกับบอทจะเห็นบอทเดินสองรอบ"
    assert "wmSeenTurn" in _fn("function wmQueueBot("),         "wmQueueBot ไม่จดว่าเล่นไปแล้ว โพลรอบถัดไปจะเล่นซ้ำ"
