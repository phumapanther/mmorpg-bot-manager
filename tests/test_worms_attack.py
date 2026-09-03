"""⚔️ ระบบโจมตีในสนามรบ — ตีปกติ สกิลคลาส บัฟ แผนที่พัง

จุดที่พังแล้วเจ็บที่สุด:
  1. เบราว์เซอร์ตัดสินเองว่าโดนใคร/เสียเลือดเท่าไหร่ = โกงได้ทันทีด้วย devtools
  2. ใช้สกิลที่คลาสตัวเองไม่มี / ใช้ทั้งที่ยังคูลดาวน์
  3. ยิงแล้วแผนที่พังแต่คนที่ยืนอยู่บนนั้นไม่ร่วง (ลอยกลางอากาศ)
"""
import pathlib
import re
import time

import pytest

import bot.models.player_model as pm
from bot.pvp import match, physics as P, terrain as T, weapons as W
from license_server import web_db
from tests import conftest

NL = chr(10)
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


def _fn(head):
    """ตัดเนื้อฟังก์ชันหนึ่งตัวจาก play.js — ตัดที่ขอบฟังก์ชันจริง ไม่ใช่นับตัวอักษร"""
    a = PLAY.index(head)
    return PLAY[a:PLAY.index(NL + "}" + NL, a)]

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


def test_every_hit_reports_the_health_left_after_it(world):
    """เว็บต้องได้ "เลือดที่เหลือหลังหมัดนี้" มาจากเซิร์ฟเวอร์ ไม่ใช่คิดลบเอง

    เว็บซ่อนผลไว้ก่อนแล้วค่อยเฉลยทีละคนตอนกล้องไปจับ (ห้ามสรุปผลก่อนภาพจะถึง)
    ถ้าไม่ส่งค่านี้มา เว็บจะเหลือทางเลือกแค่สองทางที่ผิดทั้งคู่:
    ลบเลขเอง (ผิดกติกาเหล็ก) หรือใส่ค่าสุดท้าย (รวมหมัดที่บอทยิงสวนกลับมาด้วย)
    """
    arena()
    ok, r = match.attack(UID, "basic")
    hits = r["attack"]["hits"]
    assert hits, "ตีติดแต่ไม่มีรายการคนโดน"
    for h in hits:
        assert "hp" in h, f"หมัดที่โดน {h['name']} ไม่บอกเลือดที่เหลือ"
        assert h["hp"] == r["fighters"][1]["hp"], "เลือดที่บอกไม่ตรงกับสถานะจริง"


def test_a_blast_reports_the_health_left_too(world):
    """ระเบิดก็ต้องบอกเหมือนกัน — ไม่งั้นเว็บเฉลยเลือดคนที่โดนลูกหลงไม่ได้"""
    st = arena("Mage", gap=20)
    grid = T.decode(st["terrain"])
    t = st["fighters"][1]
    r = match._explode(st, grid, t["x"], t["y"] - T.CH_H // 2, 30, 20, 0, "เทส")
    assert r["hits"], "ระเบิดกลางตัวแล้วไม่โดนใครเลย"
    for h in r["hits"]:
        assert "hp" in h, f"แรงระเบิดที่โดน {h['name']} ไม่บอกเลือดที่เหลือ"
        f = next(x for x in st["fighters"] if x["name"] == h["name"])
        assert h["hp"] == f["hp"], "เลือดที่บอกไม่ตรงกับสถานะจริงตอนนั้น"
        assert h["hp"] < 100, "โดนระเบิดแล้วเลือดยังเต็ม"


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
    assert a.get("knocks"), "ไม่มีการกระเด็นเลย"
    kb = a["knocks"][0]
    assert kb["path"][-1][0] > before, "กระเด็นผิดทาง"
    assert kb["name"], "ไม่ได้บอกว่าใครกระเด็น เว็บเล่นภาพให้ผิดคนได้"


def test_every_hit_knocks_the_target_back(world):
    """เจ้าของเกมสั่ง: ทุกครั้งที่โดนโจมตีต้องมีการกระเด็น ไม่ใช่แค่ท่ากระแทก"""
    for skill in ("basic", "heavy"):
        arena("Warrior", gap=16)
        a = match.attack(UID, skill, angle=0)[1]["attack"]
        assert a.get("knocks"), f"{skill} ตีโดนแล้วคู่ต่อสู้ยืนนิ่งเฉย"


def test_a_heavier_hit_throws_you_further(world):
    """แรงกระเด็นต้องตามดาเมจ ไม่ใช่ทุกท่าผลักเท่ากันหมด"""
    arena("Warrior", gap=16)
    light = match.attack(UID, "basic", angle=0)[1]["attack"]["knocks"][0]
    arena("Warrior", gap=16)
    heavy = match.attack(UID, "heavy", angle=0)[1]["attack"]["knocks"][0]
    assert len(heavy["path"]) > len(light["path"]), \
        f"ตีหนัก ({len(heavy['path'])}) ผลักไม่ไกลกว่าตีปกติ ({len(light['path'])})"


def test_a_fireball_blows_a_hole_in_the_ground(world):
    arena("Mage", gap=200)
    before = sum(1 for row in T.decode(match.load(UID)["terrain"]) for v in row if v)
    ok, r = match.attack(UID, "fire", angle=45, power=60)
    assert ok and r["attack"].get("blast"), "ยิงแล้วไม่ระเบิด"
    after = sum(1 for row in T.decode(r["terrain"]) for v in row if v)
    assert after < before, "ระเบิดแล้วพื้นไม่หาย"


def _first_solid_between(grid, a, b):
    """เดินเส้นตรงระหว่างสองจุดของเส้นวิถี — เจอพื้นตันตรงไหนก่อน

    เขียนแยกจากของจริงในเกมโดยตั้งใจ (คนละวิธีเดิน) จะได้เป็นการตรวจอิสระ
    ไม่ใช่เอาสูตรเดียวกันมาเทียบตัวเองแล้วผ่านทุกที
    """
    x0, y0 = a
    x1, y1 = b
    n = max(abs(x1 - x0), abs(y1 - y0))
    for i in range(1, n):
        x = x0 + (x1 - x0) * i // n
        y = y0 + (y1 - y0) * i // n
        if 0 <= x < T.W and 0 <= y < T.H and P._blocks(grid, x, y):
            return x, y
    return None


def test_a_shot_cannot_slip_through_a_thin_wall():
    """กระสุนวิ่ง 8-9 px/เฟรม ถ้าเช็คแค่ปลายก้าวก็ข้ามกำแพงบางไปเฉย ๆ

    hedgewars กันด้วยการบังคับความเร็วไม่เกิน 2 px/เฟรม
    (uGearsHandlersMess.pas:400) เราเช็คถี่ขึ้นแทน จะได้ไม่ต้องแตะจังหวะเกม
    """
    for thick in (1, 2, 3, 5):
        for power in (30, 50, 70, 90, 100):
            g = [[T.AIR] * T.W for _ in range(T.H)]
            for x in range(150, 150 + thick):
                for y in range(60, 240):
                    g[y][x] = T.ROCK
            r = P.shoot(g, 100, 200, 10, power)
            assert r["hit"], f"กำแพงหนา {thick} px แรง {power} — กระสุนทะลุไปเฉย ๆ"
            assert r["x"] <= 150 + thick,                 f"ระเบิดเลยกำแพงไปที่ x={r['x']} (กำแพงอยู่ 150-{150 + thick})"


def test_shots_blow_up_where_they_actually_touch_the_ground():
    """กวาดแผนที่จริง — จุดระเบิดต้องตรงกับพิกเซลแรกที่วิถีแตะพื้น

    วัดก่อนแก้: 720 นัด มี 270 นัด (37%) ที่ระเบิดคลาดจากจุดที่แตะพื้นเกิน 2 px
    ในนั้นคลาดเกิน 30 px ไป 26 นัด และทะลุหายไม่ระเบิดเลย 18 นัด
    รัศมีระเบิดมีแค่ 26-30 px คลาดขนาดนั้นคือเปลี่ยนว่าใครโดนใครรอด
    """
    import math
    import random

    rng = random.Random(0)
    shots = bad = 0
    worst = 0
    for seed in range(1, 9):
        grid = T.generate(seed)["grid"]
        spots = T._open_spots(grid)
        for _ in range(40):
            x, y = rng.choice(spots)
            ang = rng.choice([15, 25, 35, 45, 55, 70])
            if rng.random() < .5:
                ang = 180 - ang
            r = P.shoot(grid, x, y, ang, rng.choice([30, 50, 70, 85, 100]))
            shots += 1
            path = r["path"]
            sx, sy = path[0]
            for i in range(len(path) - 1):
                c = _first_solid_between(grid, path[i], path[i + 1])
                if not c or math.hypot(c[0] - sx, c[1] - sy) <= P.ARM_DIST:
                    continue
                off = math.hypot(r["x"] - c[0], r["y"] - c[1]) if r["hit"] else 999
                if off > 2:                      # เกินนี้ไม่ใช่แค่ปัดเศษแล้ว
                    bad += 1
                    worst = max(worst, off)
                break
    assert bad * 100 / shots < 3,         f"ยิง {shots} นัด ระเบิดผิดที่ {bad} นัด ({bad * 100 / shots:.0f}%) คลาดสุด {worst:.0f} px"


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
    """เว็บ "แสดง" เลือดได้ แต่ห้าม "คิด" เลือดเอง

    เดิมแบนคำว่า `hp =` ไปเลย ซึ่งกว้างเกินจริง — เว็บต้องเขียนค่าลง f.hp
    เพื่อเฉลยผลทีละคนตอนภาพเล่นถึง (ห้ามสรุปผลก่อนอนิเมชั่นจบ)
    ที่ต้องกันจริง ๆ คือการ "คำนวณ" เอง จึงแบนเลขคณิตกับ hp และการสุ่ม
    แล้วบังคับต่อว่าทุกค่าที่เขียนลง hp ต้องมาจากก้อนข้อมูลของเซิร์ฟเวอร์
    """
    a = PLAY.index("async function wmAttack(")
    block = PLAY[a:PLAY.index("let WM_SHOT", a)]
    for banned in ("hp -", "hp +", "hp *", "hp /", "damage =", "Math.random"):
        assert banned not in block, f"หน้าเว็บคิดผลการโจมตีเอง: {banned}"
    # เขียนลง hp ได้ แต่ฝั่งขวาต้องเป็นค่าที่เซิร์ฟเวอร์ส่งมาเท่านั้น
    okay = ("hp = hp", "hp = h.hp", "hp = o.hp", "hp = v.hp", "hp = f.hp")
    for m in re.finditer(r"hp = .+", block):
        assert m.group(0).startswith(okay), f"เว็บเสกเลือดขึ้นมาเอง: {m.group(0)}"
    assert "action: 'attack'" in block, "ไม่ได้ส่งคำสั่งโจมตีไปเซิร์ฟเวอร์"


def test_the_api_only_takes_a_skill_and_an_aim():
    api = conftest.web_api_source()
    body = api[api.index("class WormsBody"):api.index('@router.post("/pvp/worms/match")')]
    for leaked in ("damage", "hp", "target"):
        assert leaked not in body, f"API รับ {leaked} จากเบราว์เซอร์ — โกงได้ทันที"
    for need in ("skill", "angle", "power"):
        assert need in body, f"API ไม่รับ {need}"


def test_the_skill_panel_is_wired():
    for el in ("wmSkills", "wmItems", "wmAim"):
        assert el in HTML and el in PLAY, f"อ้างถึง #{el} แต่ไม่มีในหน้าเว็บ (หรือกลับกัน)"
    assert "s.kind === 'self'" in PLAY, "ไม่ได้แยกบัฟใส่ตัวเอง (กดใช้ได้เลย) ออกจากท่าที่ต้องเล็ง"


def test_no_aim_buttons_clutter_the_screen():
    """เจ้าของเกมสั่ง: ไม่ควรมีปุ่มปรับองศา ความแรง หรือปุ่มยิงมารกจอ"""
    for gone in ("wmAngle", "wmPower", "wmFire", "data-dir=", "WM_DIR"):
        assert gone not in HTML and gone not in PLAY, f"ยังมี {gone} ค้างอยู่"


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
    from license_server.api_web import deps as _api_web_deps

    monkeypatch.setattr(_api_web_deps, "GAME_DB_PATH", tmp_path / "g.db")

    monkeypatch.setattr(web_api, "GAME_DB_PATH", tmp_path / "g.db")  # เผื่อโค้ดเก่าอ่านผ่าน web_api
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


# ── 🎯 ต้องเห็นว่าตีตรงไหน โดนอะไร เสียหายเท่าไหร่ ──

def test_a_hit_reports_where_it_landed(world):
    """ไม่บอกพิกัด = เบราว์เซอร์เด้งตัวเลขดาเมจตรงไหนไม่ได้"""
    arena()
    hits = match.attack(UID, "basic")[1]["attack"]["hits"]
    assert hits and all("x" in h and "y" in h for h in hits), "ไม่ได้บอกว่าโดนตรงไหน"
    assert all("damage" in h for h in hits)


def test_a_dodge_is_reported_too(world):
    """หลบได้แต่ไม่บอก = ผู้เล่นเห็นแค่ไม่มีอะไรเกิดขึ้น"""
    arena("Rogue")
    st = match.load(UID)
    st["fighters"][1]["buffs"] = {"evade": 3}
    match.save(UID, st)
    hits = match.attack(UID, "basic")[1]["attack"]["hits"]
    assert hits and hits[0]["dodged"] is True, "หลบแล้วไม่บอกว่าหลบ"


def test_a_melee_swing_reports_its_arc(world):
    """ต้องรู้จุดเริ่ม ทิศ และระยะ ถึงจะวาดวงเหวี่ยงได้"""
    arena()
    a = match.attack(UID, "basic")[1]["attack"]
    for k in ("from", "face", "reach"):
        assert k in a, f"สกิลประชิดไม่ได้บอก {k}"


def test_a_blast_reports_its_centre_and_size(world):
    arena("Mage", gap=200)
    b = match.attack(UID, "fire", angle=45, power=60)[1]["attack"].get("blast")
    assert b and {"x", "y", "crater", "hits"} <= set(b), "ระเบิดไม่ได้บอกจุด/ขนาด"


def test_the_bot_attack_comes_back_so_it_can_be_shown(world):
    """เลือดลดโดยไม่เห็นอะไรเลย = ผู้เล่นนึกว่าตีตัวเอง (เจ้าของเกมรายงานมาจริง)"""
    match.new_practice(UID, {"race": "Human", "cls": "Warrior",
                             "armor": "None", "weapon": ""}, seed=7)
    seen = False
    for _ in range(14):
        st = match.load(UID)
        st["turn_started"] = 0
        match.save(UID, st)
        ok, r = match.end_turn(UID, auto=True)
        if not ok or r["over"]:
            break
        for m in r["bot_moves"]:
            if m.get("attack"):
                seen = True
                assert m["attack"].get("name"), "ไม่ได้บอกว่าบอทใช้สกิลอะไร"
    assert seen, "บอทโจมตีแต่ไม่ได้ส่งรายละเอียดกลับมาให้แสดงผล"


def test_the_page_shows_damage_numbers_and_flashes():
    for need in ("wmPop", "WM_FLASH", "wmSwing", "wmBoom", "wmDrawAim", "wmDrawTrail"):
        assert need in PLAY, f"ไม่มีเอฟเฟกต์ {need}"
    fn = _fn("function wmShowHit(")
    assert "wmPlayVictims(a," in fn, "ไม่ได้ไล่สรุปผลคนที่โดนทีละคน"
    one = _fn("function wmSettleVictim(")
    assert "WM_POPS.push" in one, "ไม่ได้เด้งตัวเลขดาเมจ"
    assert "wmFocus(f, true)" in one, "ไม่ได้จับกล้องไปที่คนที่กำลังสรุปผล"
    assert "wmSwing(a)" in fn, "ไม่ได้วาดวงเหวี่ยงตอนฟัน"


def test_a_projectile_leaves_a_dotted_trail():
    """เจ้าของเกมสั่ง: ต้องเห็นว่ากระสุนโค้งไปถึงตรงนั้นได้ยังไง"""
    assert "function wmDrawTrail" in PLAY, "ไม่มีเส้นประวิถี"
    fx = _fn("function wmDrawFx(")
    assert "wmDrawTrail(ctx, seen" in fx, "ไม่ได้ลากเส้นตามทางที่บินผ่านมาแล้ว"
    assert "WM_TRAIL = { path:" in fx, "ไม่ได้เก็บวิถีไว้ให้ดูต่อหลังระเบิด"
    assert "if (WM_TRAIL)" in fx, "เก็บวิถีไว้แต่ไม่ได้วาด"


def test_melee_gets_a_swing_not_a_trail():
    """ประชิดไม่มีวิถี — แสดงแค่วงเหวี่ยงตรงจุดที่ฟันถึง"""
    fn = _fn("function wmShowHit(")
    assert "if (a.path && a.path.length)" in fn, "ไม่ได้แยกสกิลมีวิถีออกจากประชิด"
    # ตัดเอาเฉพาะ "ในบล็อกของสกิลมีวิถี" ไม่ใช่นับตัวอักษรเอา
    # (นับตัวอักษรแล้วพอเพิ่มโค้ดในบล็อกนิดเดียวเทสก็แดงทั้งที่พฤติกรรมเหมือนเดิม)
    tail = fn[fn.index("if (a.path && a.path.length)"):]
    block = tail[:tail.index(chr(10) + "  }")]
    assert "return;" in block, "สกิลมีวิถีต้องรอบินให้จบก่อน ไม่ใช่แสดงผลทันที"
    assert "wmPlayVictims" not in block, "ยังสรุปผลทันทีทั้งที่กระสุนยังไม่ถึงเป้า"


def test_the_crater_appears_only_when_the_shot_lands():
    """เดิมเจาะหลุมทันทีที่ได้ผลกลับมา พื้นหายก่อนกระสุนบินถึงด้วยซ้ำ"""
    # การเจาะพื้นต้องอยู่ใน wmLand() ที่ถูกเรียกตอนกระสุนถึงเป้าเท่านั้น
    # ไม่ใช่ที่ wmShowHit() ซึ่งทำงานทันทีที่ได้ผลกลับมาจากเซิร์ฟเวอร์
    assert "WM.carve" not in _fn("function wmShowHit("),         "เจาะหลุมตั้งแต่ยังไม่ได้ยิง"
    assert "wmLand(shot.blast)" in _fn("function wmDrawFx("), \
        "กระสุนถึงเป้าแล้วไม่ได้เจาะพื้น"


def test_the_impact_throws_debris():
    """สกิลปะทะแล้วต้องเห็นว่าทำลายสิ่งแวดล้อมจริง"""
    fn = _fn("function wmLand(")
    assert "WM.carve" in fn and "wmBoom" in fn and "WM_BITS.push" in fn, \
        "ปะทะแล้วไม่ครบทั้งเจาะพื้น ระเบิด และสะเก็ด"


def test_the_bot_turn_is_animated_too():
    """ใช้ตัวเล่นเอฟเฟกต์ตัวเดียวกันทั้งของเราและของบอท จะได้ไม่ลืมอันใดอันหนึ่ง"""
    assert "wmShowHit(a, true)" in _fn("function wmPlayBotShots("), \
        "ไม่ได้เล่นเอฟเฟกต์การโจมตีของบอท"
    assert "wmPlayBotShots(shots)" in _fn("function wmQueueBot("), \
        "เขียนตัวเล่นภาพบอทไว้แต่ไม่มีใครเรียก"


# ── 🔥 ยิงแล้วต้องไม่ระเบิดใส่ตัวเอง ──

def test_a_shot_never_explodes_in_your_own_face(world):
    """วัดจากแผนที่จริง: ก่อนแก้มี 8/24 นัดที่ระเบิดในรัศมีตัวเอง เพราะยืนติดบ้าน/ก้อนหิน"""
    close = 0
    for seed in range(1, 25):
        match.new_practice(UID, {"race": "Human", "cls": "Mage",
                                 "armor": "None", "weapon": ""}, seed=seed)
        st = match.load(UID)
        g = T.decode(st["terrain"])
        me = st["fighters"][0]
        r = P.shoot(g, me["x"], me["y"], 45, 70)
        if r["hit"] and abs(r["x"] - me["x"]) < W.SKILLS["fire"]["radius"]:
            close += 1
    assert close == 0, f"{close}/24 นัดระเบิดในรัศมีตัวเอง"


def test_the_arming_distance_covers_the_biggest_blast():
    """ระยะปลอดภัยต้องกว้างกว่ารัศมีระเบิดที่แรงที่สุด ไม่งั้นยังโดนตัวเองอยู่ดี"""
    biggest = max(s.get("radius", 0) for s in W.SKILLS.values())
    assert P.ARM_DIST > biggest, f"ระยะปลอดภัย {P.ARM_DIST} ไม่พ้นรัศมี {biggest}"


def test_shots_pass_through_leaves(world):
    """ลูกไฟทะลุพุ่มไม้ได้ ไม่งั้นต้นไม้ต้นเดียวกันหมดทั้งสนาม"""
    g = [[T.AIR] * T.W for _ in range(T.H)]
    for x in range(T.W):
        for y in range(200, T.H - T.WATER):
            g[y][x] = T.ROCK
    for y in range(150, 190):
        for x in range(250, 270):
            g[y][x] = T.LEAF
    r = P.shoot(g, 200, 200, 20, 70)
    assert r["x"] > 280, f"กระสุนไปได้แค่ x={r['x']} — ติดพุ่มใบไม้"


def test_shots_still_stop_at_a_trunk(world):
    g = [[T.AIR] * T.W for _ in range(T.H)]
    for x in range(T.W):
        for y in range(200, T.H - T.WATER):
            g[y][x] = T.ROCK
    for y in range(150, 200):
        for x in range(258, 262):
            g[y][x] = T.TRUNK
    r = P.shoot(g, 200, 200, 20, 70)
    assert r["hit"] and r["x"] < 270, "ยิงทะลุลำต้นไปได้"


# ── 🧭 เลือกทิศยิงเองได้ ──

def test_you_can_aim_the_other_way(world):
    """เดิมยิงตามทิศที่เดินล่าสุดอย่างเดียว ศัตรูอยู่ข้างหลังก็ยิงไม่ได้เลย"""
    st = arena(gap=18)
    st["fighters"][1]["x"] = st["fighters"][0]["x"] - 18
    st["fighters"][0]["face"] = 1
    match.save(UID, st)
    ok, r = match.attack(UID, "basic", direction=-1)
    assert ok and r["attack"]["hits"], "สั่งหันซ้ายแล้วยังฟันไม่โดน"
    assert r["attack"]["face"] == -1


def test_the_direction_comes_from_which_side_you_press():
    """ไม่มีปุ่มเลือกทิศแล้ว — กดฝั่งไหนของตัวเองก็ยิงไปทางนั้น"""
    assert "WM_CAM.mx(p.x) >= wmMe().x ? 1 : -1" in PLAY, "ไม่ได้อ่านทิศจากฝั่งที่กด"
    assert "dir: dir" in PLAY, "ไม่ได้ส่งทิศไปกับคำสั่งโจมตี"
