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

UID = 6403
WEB = pathlib.Path("license_server/web_static")
PLAY = (WEB / "play.js").read_text(encoding="utf-8")
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
    stay = body[body.index("if (!moves.length) {"):body.index("if (!WM_ANIM || WM_ANIM.fi !== bi)")]
    assert "wmPlayBotShots(shots)" in stay,         "บอทยืนยิงอยู่กับที่ (ไม่ได้เดิน) แล้วไม่มีใครเล่นภาพ — หลุมจะไม่ถูกลบบนจอ"
    assert "onEnd: i === moves.length - 1" in body, "บอทเดินยังไม่จบก็ยิงทับเลย"


def test_the_bot_shots_no_longer_guess_the_timing():
    assert "setTimeout" not in _fn("function wmPlayAttack("), \
        "ยังใช้ setTimeout เดาเวลาแทนที่จะรอภาพเล่นจบจริง"
    body = _fn("function wmPlayBotShots(")
    assert "WM_AFTER.push" in body, "ยิงหลายนัดจะทับกันเอง ไม่ได้รอนัดก่อนเล่นจบ"
