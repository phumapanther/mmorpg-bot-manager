"""⚔️ ระบบโจมตีในสนามรบ — ตีปกติ สกิลคลาส บัฟ แผนที่พัง

จุดที่พังแล้วเจ็บที่สุด:
  1. เบราว์เซอร์ตัดสินเองว่าโดนใคร/เสียเลือดเท่าไหร่ = โกงได้ทันทีด้วย devtools
  2. ใช้สกิลที่คลาสตัวเองไม่มี / ใช้ทั้งที่ยังคูลดาวน์
  3. ยิงแล้วแผนที่พังแต่คนที่ยืนอยู่บนนั้นไม่ร่วง (ลอยกลางอากาศ)
"""
import pathlib
import time

import pytest

import bot.models.player_model as pm
from bot.pvp import match, physics as P, terrain as T, weapons as W
from license_server import web_db

UID = 6301
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


def arena(cls="Warrior", gap=18, top=200):
    """สนามพื้นราบล้วน — ทดสอบสกิลโดยไม่มีภูมิประเทศมากวน"""
    match.new_practice(UID, {"race": "Human", "cls": cls, "armor": "None", "weapon": ""}, seed=7)
    g = [[T.AIR] * T.W for _ in range(T.H)]
    for x in range(T.W):
        for y in range(top, T.H - T.WATER):
            g[y][x] = T.ROCK
    st = match.load(UID)
    st["terrain"] = T.encode(g)
    st["props"] = []
    st["fighters"][0].update(x=200, y=top, face=1, hp=100,
                             look={**st["fighters"][0]["look"], "cls": cls})
    st["fighters"][1].update(x=200 + gap, y=top, face=1, hp=100)
    match.save(UID, st)
    return st


def _retake_turn():
    """ให้ถึงตาเราอีกครั้งโดยไม่ต้องรอบอท (ใช้ทดสอบกติกาต่อเนื่อง)"""
    st = match.load(UID)
    st["turn"], st["turn_started"] = 0, time.time()
    match.save(UID, st)


# ── สกิลตรงกับเกมหลัก ──

def test_the_skill_list_matches_the_main_game():
    from bot.views.profile_embed import CLASS_SKILLS

    for cls in ("Warrior", "Mage", "Rogue", "Cleric"):
        names = [W.SKILLS[k]["name"] for k in W.kit_for(cls) if k != "basic"]
        assert names == CLASS_SKILLS[cls], f"สกิล {cls} ไม่ตรงกับเกมหลัก"


def test_everyone_gets_a_basic_attack():
    for cls in ("Warrior", "Mage", "Rogue", "Cleric", "ไม่มีคลาส"):
        assert "basic" in W.kit_for(cls), f"{cls} ไม่มีตีปกติ"


def test_cleric_has_no_attack_skill_and_that_is_fine():
    """เจ้าของเกมเคาะไว้: มีฮีลก็คุ้มแล้ว ไม่ต้องเพิ่มสกิลโจมตีให้"""
    kinds = {W.SKILLS[k]["kind"] for k in W.kit_for("Cleric") if k != "basic"}
    assert kinds == {"self"}, "Cleric ไม่ควรมีสกิลโจมตี"
    assert any(W.SKILLS[k].get("heal") for k in W.kit_for("Cleric")), "Cleric ต้องมีฮีล"


# ── ลงมือโจมตี ──

def test_a_basic_attack_takes_health(world):
    arena()
    ok, r = match.attack(UID, "basic")
    assert ok and r["fighters"][1]["hp"] < 100, "ตีแล้วไม่เสียเลือด"


def test_you_cannot_hit_someone_out_of_reach(world):
    arena(gap=200)
    ok, r = match.attack(UID, "basic")
    assert ok and r["fighters"][1]["hp"] == 100, "ฟันโดนทั้งที่อยู่ไกลลิบ"


def test_you_cannot_hit_someone_behind_you(world):
    """ฟันโดนคนข้างหลังได้ = ไม่ต้องหันหน้าก็ได้ ทิศทางไร้ความหมาย"""
    st = arena(gap=18)
    st["fighters"][0]["face"] = -1
    match.save(UID, st)
    ok, r = match.attack(UID, "basic")
    assert ok and r["fighters"][1]["hp"] == 100, "ฟันโดนคนที่อยู่ข้างหลัง"


def test_backstab_hits_harder_from_behind(world):
    arena("Rogue", gap=18)
    st = match.load(UID)
    st["fighters"][1]["face"] = 1
    match.save(UID, st)
    behind = 100 - match.attack(UID, "stab")[1]["fighters"][1]["hp"]

    arena("Rogue", gap=18)
    st = match.load(UID)
    st["fighters"][1]["face"] = -1
    match.save(UID, st)
    facing = 100 - match.attack(UID, "stab")[1]["fighters"][1]["hp"]
    assert behind > facing, f"ลอบแทงจากหลัง {behind} ไม่แรงกว่าจากหน้า {facing}"


def test_shield_bash_knocks_the_target_away(world):
    arena("Warrior", gap=18)
    before = match.load(UID)["fighters"][1]["x"]
    a = match.attack(UID, "bash")[1]["attack"]
    assert a.get("knock"), "ไม่มีการกระเด็นเลย"
    assert a["knock"][-1][0] > before, "กระเด็นผิดทาง"


def test_a_fireball_blows_a_hole_in_the_ground(world):
    arena("Mage", gap=200)
    before = sum(1 for row in T.decode(match.load(UID)["terrain"]) for v in row if v)
    ok, r = match.attack(UID, "fire", angle=45, power=60)
    assert ok and r["attack"].get("blast"), "ยิงแล้วไม่ระเบิด"
    after = sum(1 for row in T.decode(r["terrain"]) for v in row if v)
    assert after < before, "ระเบิดแล้วพื้นไม่หาย"


def test_a_blast_hurts_more_the_closer_you_are():
    assert P.blast_damage(0, 30, 40) > P.blast_damage(20, 30, 40) > 0
    assert P.blast_damage(31, 30, 40) == 0, "อยู่นอกรัศมีแต่ยังเจ็บ"


def test_the_ground_giving_way_makes_you_fall(world):
    """ยิงพื้นใต้เท้าแล้วต้องร่วง ไม่ใช่ยืนลอยอยู่กลางอากาศ"""
    arena("Mage", gap=60, top=150)
    ok, r = match.attack(UID, "fire", angle=20, power=42)
    g = T.decode(r["terrain"])
    for f in r["fighters"]:
        if not f["dead"]:
            assert P.standable(g, f["x"], f["y"]), f"{f['name']} ลอยอยู่กลางอากาศหลังระเบิด"


def test_healing_restores_health_but_not_over_the_cap(world):
    arena("Cleric")
    st = match.load(UID)
    st["fighters"][0]["hp"] = 50
    match.save(UID, st)
    a = match.attack(UID, "heal")[1]["attack"]
    assert a["heal"] > 0 and a["heal"] <= W.SKILLS["heal"]["heal"]

    # เลือดเต็มอยู่แล้วต้องฟื้นได้ 0 — ดูจากค่าที่ฮีลจริง ไม่ใช่เลือดตอนจบ
    # (จบเทิร์นแล้วบอทตีสวนทันที เลือดตอนจบจึงไม่ใช่ผลของการฮีลอย่างเดียว)
    arena("Cleric")
    assert match.attack(UID, "heal")[1]["attack"]["heal"] == 0, "ฮีลทะลุเลือดเต็ม"


# ── บัฟ ──

def test_evasion_dodges_the_next_hit(world):
    arena("Rogue")
    st = match.load(UID)
    st["fighters"][1]["buffs"] = {"evade": 3}
    match.save(UID, st)
    ok, r = match.attack(UID, "basic")
    assert r["fighters"][1]["hp"] == 100, "มีบัฟหลบแล้วยังโดนเต็ม ๆ"
    assert "หลบพ้น" in " ".join(r["log"])


def test_evasion_is_used_up_after_one_dodge(world):
    arena("Rogue")
    st = match.load(UID)
    st["fighters"][1]["buffs"] = {"evade": 3}
    match.save(UID, st)
    match.attack(UID, "basic")
    assert "evade" not in match.load(UID)["fighters"][1].get("buffs", {}), \
        "หลบแล้วบัฟยังอยู่ — หลบได้ไม่จำกัด"


def test_holy_aura_halves_damage(world):
    arena("Warrior")
    plain = 100 - match.attack(UID, "basic")[1]["fighters"][1]["hp"]

    arena("Warrior")
    st = match.load(UID)
    st["fighters"][1]["buffs"] = {"aura": 3}
    match.save(UID, st)
    warded = 100 - match.attack(UID, "basic")[1]["fighters"][1]["hp"]
    assert warded < plain, f"มีออร่าแล้วยังเจ็บเท่าเดิม ({warded} เทียบ {plain})"


def test_being_slowed_halves_your_move_budget(world):
    arena("Warrior")
    st = match.load(UID)
    st["fighters"][0]["buffs"] = {"slow": 5}
    st["turn_started"] = 0
    match.save(UID, st)
    match.end_turn(UID, auto=True)
    assert match.load(UID)["moves"] <= match.MOVE_BUDGET // 2, "ติดแช่แข็งแล้วแรงเดินไม่ลด"


def test_buffs_expire_on_their_own(world):
    """บัฟถาวร = ใช้ทีเดียวติดตลอดเกม"""
    arena("Cleric")
    match.attack(UID, "aura")
    for _ in range(12):
        if "aura" not in match.load(UID)["fighters"][0].get("buffs", {}):
            break
        st = match.load(UID)
        st["turn_started"] = 0
        match.save(UID, st)
        if not match.end_turn(UID, auto=True)[0]:
            break
    assert "aura" not in match.load(UID)["fighters"][0].get("buffs", {}), "บัฟไม่หมดอายุ"


# ── กติกาการใช้ ──

def test_you_cannot_use_another_class_skill(world):
    arena("Warrior")
    ok, r = match.attack(UID, "fire")
    assert not ok and "ใช้สกิลนี้ไม่ได้" in r["error"]


def test_a_made_up_skill_is_refused(world):
    arena("Warrior")
    assert not match.attack(UID, "ท่าไม้ตายลับ")[0]


def test_a_skill_on_cooldown_is_refused(world):
    arena("Warrior")
    assert match.attack(UID, "heavy")[0]
    _retake_turn()
    ok, r = match.attack(UID, "heavy")
    assert not ok and "คูลดาวน์" in r["error"]


def test_the_basic_attack_never_goes_on_cooldown(world):
    assert W.SKILLS["basic"]["cooldown"] == 0
    arena("Warrior")
    for _ in range(3):
        assert match.attack(UID, "basic")[0], "ตีปกติติดคูลดาวน์"
        _retake_turn()


def test_attacking_ends_your_turn(world):
    """ไม่งั้นยิงรัวทั้งเทิร์นจนอีกฝ่ายไม่มีโอกาสได้เล่น"""
    arena("Warrior")
    before = match.load(UID)["round"]
    ok, r = match.attack(UID, "basic")
    assert ok and r["round"] > before, "โจมตีแล้วเทิร์นไม่จบ"


def test_you_cannot_attack_when_time_is_up(world):
    arena("Warrior")
    st = match.load(UID)
    st["turn_started"] = time.time() - match.TURN_SECONDS - 1
    match.save(UID, st)
    ok, r = match.attack(UID, "basic")
    assert not ok and "หมดเวลา" in r["error"]


def test_you_cannot_attack_on_the_bots_turn(world):
    st = arena("Warrior")
    st["turn"] = 1
    match.save(UID, st)
    ok, r = match.attack(UID, "basic")
    assert not ok and "ยังไม่ถึงตา" in r["error"]


# ── 🤖 บอทโจมตีเป็น ──

@pytest.mark.parametrize("cls", ["Warrior", "Mage", "Rogue", "Cleric"])
def test_the_bot_uses_its_skills(world, cls):
    match.new_practice(UID, {"race": "Human", "cls": "Warrior",
                             "armor": "None", "weapon": ""}, seed=7)
    st = match.load(UID)
    st["fighters"][1]["look"]["cls"] = cls
    match.save(UID, st)
    used = 0
    for _ in range(14):
        st = match.load(UID)
        st["turn_started"] = 0
        match.save(UID, st)
        ok, r = match.end_turn(UID, auto=True)
        if not ok or r["over"]:
            break
        used += sum(1 for m in r["bot_moves"] if m.get("attack"))
    assert used, f"บอทคลาส {cls} ไม่ใช้สกิลเลยสักครั้ง"


def test_the_bot_can_actually_hurt_you(world):
    """บอทที่ทำอะไรเราไม่ได้เลย = ซ้อมไม่มีความหมาย"""
    hurt = 0
    for cls in ("Warrior", "Mage", "Rogue"):
        match.new_practice(UID, {"race": "Human", "cls": "Warrior",
                                 "armor": "None", "weapon": ""}, seed=7)
        st = match.load(UID)
        st["fighters"][1]["look"]["cls"] = cls
        match.save(UID, st)
        for _ in range(14):
            st = match.load(UID)
            st["turn_started"] = 0
            match.save(UID, st)
            ok, r = match.end_turn(UID, auto=True)
            if not ok or r["over"]:
                break
        hurt += 100 - match.load(UID)["fighters"][0]["hp"]
    assert hurt > 0, "บอททั้งสามคลาสทำเลือดเราไม่ได้เลยสักหยด"


# ── กติกาเหล็ก: เบราว์เซอร์ไม่ตัดสินผล ──

def test_the_browser_never_decides_damage():
    a = PLAY.index("async function wmAttack(")
    block = PLAY[a:PLAY.index("let WM_SHOT", a)]
    for banned in ("hp -", "hp =", "damage =", "Math.random"):
        assert banned not in block, f"หน้าเว็บคิดผลการโจมตีเอง: {banned}"
    assert "action: 'attack'" in block, "ไม่ได้ส่งคำสั่งโจมตีไปเซิร์ฟเวอร์"


def test_the_api_only_takes_a_skill_and_an_aim():
    api = pathlib.Path("license_server/web_api.py").read_text(encoding="utf-8")
    body = api[api.index("class WormsBody"):api.index('@router.post("/pvp/worms/match")')]
    for leaked in ("damage", "hp", "target"):
        assert leaked not in body, f"API รับ {leaked} จากเบราว์เซอร์ — โกงได้ทันที"
    for need in ("skill", "angle", "power"):
        assert need in body, f"API ไม่รับ {need}"


def test_the_skill_panel_is_wired():
    for el in ("wmSkills", "wmAim", "wmAngle", "wmPower", "wmFire"):
        assert el in HTML and el in PLAY, f"อ้างถึง #{el} แต่ไม่มีในหน้าเว็บ (หรือกลับกัน)"
    assert "s.aim" in PLAY, "ไม่ได้แยกสกิลที่ต้องเล็งออกจากสกิลที่กดใช้ได้เลย"


def test_the_server_tells_the_page_which_skills_are_ready(world):
    arena("Mage")
    v = match.view(UID)
    assert {s["key"] for s in v["skills"]} == set(W.kit_for("Mage")), \
        "รายการสกิลที่ส่งไปไม่ตรงกับคลาส"
    assert any(s["aim"] for s in v["skills"]), "ไม่ได้บอกว่าสกิลไหนต้องเล็ง"
    match.attack(UID, "fire", angle=45, power=60)
    _retake_turn()
    fire = next(s for s in match.view(UID)["skills"] if s["key"] == "fire")
    assert fire["ready_in"] > 0, "ใช้ไปแล้วแต่ยังบอกว่าพร้อมใช้"


# ── ยิงผ่าน HTTP จริง ──

@pytest.fixture
def web(tmp_path, monkeypatch):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from license_server import web_api

    monkeypatch.setattr(pm, "DB_NAME", str(tmp_path / "g.db"))
    monkeypatch.setattr(web_db, "DB_PATH", tmp_path / "w.db")
    pm.init_db()
    pm.get_player(UID)
    monkeypatch.setattr(web_api, "GAME_DB_PATH", tmp_path / "g.db")
    app = FastAPI()
    app.include_router(web_api.router)
    c = TestClient(app)
    c.cookies.set("web_session", web_api.sign({"uid": str(UID), "exp": time.time() + 3600}))
    return c


def test_attacking_over_http(web):
    web.post("/api/web/pvp/worms/match", json={"action": "new", "seed": 7})
    r = web.post("/api/web/pvp/worms/match",
                 json={"action": "attack", "skill": "basic", "angle": 45, "power": 70})
    assert r.status_code == 200, r.text
    d = r.json()
    assert "attack" in d and d["round"] == 2, "โจมตีแล้วเทิร์นไม่จบ"
    assert "skills" in d and d["time_left"] > 0


def test_http_refuses_a_skill_you_do_not_have(web):
    web.post("/api/web/pvp/worms/match", json={"action": "new", "seed": 7})
    st = match.load(UID)
    st["fighters"][0]["look"]["cls"] = "Warrior"
    match.save(UID, st)
    r = web.post("/api/web/pvp/worms/match", json={"action": "attack", "skill": "fire"})
    assert r.status_code == 400
