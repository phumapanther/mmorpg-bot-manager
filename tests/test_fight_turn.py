"""ระบบต่อสู้ (เว็บเกม เฟส 5.6) — เทสชุดแรกที่ "สู้จริง" ไม่ใช่แค่อ่านซอร์ส

เดิม process_turn ฝังอยู่ใน Discord View เรียกจากเทสไม่ได้เลย เทสที่มีจึงได้แค่
เช็คว่าซอร์สมีข้อความนั้น ๆ ไหม พอย้ายมา adventure_core.fight_turn แล้วรันได้จริง
"""
import random

import pytest

import bot.models.player_model as pm
from bot import adventure_core, config_loader, game_modifiers

WEAPON = {"atk": 10}
ARMOR = {"hp": 100, "eva": 20}


@pytest.fixture
def hero(tmp_path, monkeypatch):
    p = {"user_id": 1, "level": 20, "hp": 1000, "max_hp": 1000, "cash": 0, "bank": 0,
         "inventory": "[]", "weapon": "W", "armor": "A", "weapon_dur": 50, "armor_dur": 100,
         "current_state": "fighting", "last_event": "monster", "continent": "main",
         "race": None, "class_name": None, "status_effects": "{}", "pet": ""}
    monkeypatch.setattr(pm, "DB_NAME", str(tmp_path / "t.db"))
    monkeypatch.setattr(pm, "get_player", lambda uid: dict(p))
    monkeypatch.setattr(pm, "update_player_field", lambda uid, f, v: p.__setitem__(f, v))
    monkeypatch.setattr(pm, "update_player_fields", lambda uid, d: p.update(d))
    monkeypatch.setattr(config_loader, "get_weapon_stats", lambda k: WEAPON)
    monkeypatch.setattr(config_loader, "get_armor_stats", lambda k: ARMOR)
    return p


def _fight(hp=200, element="earth", rank="Common", **over):
    # ธาตุดินไม่มีเรทหนี — ธาตุไฟ/แสงมี ทำให้เทิร์นจบก่อนถึงจุดที่อยากทดสอบ
    f = {"rank": rank, "stats": dict(adventure_core.MONSTER_RANKS[rank]), "hp": hp,
         "hp_max": hp, "element": element, "statuses": {}, "fight_grace": [],
         "infused": False, "faction_side": None, "turn": 1, "buffs": {}}
    f.update(over)
    return f


class Rigged(random.Random):
    """คุมเต๋าสองฝั่งแยกกัน — ตั้งแต่ 2026-08-14 เต๋าผู้เล่นทอยคนละช่วงกับของมอน
    (ตีปกติ 12-19 / ออกท่า 1-20) จึงดักที่ "การทอยครั้งแรก = ของผู้เล่น" แทนช่วงตัวเลข

    roll=N        ผู้เล่นได้ N มอนได้ 1 (ผู้เล่นชนะ)
    rolls=[a, b]  ผู้เล่นได้ a มอนได้ b
    pct / pcts    ค่าที่จะคืนให้การทอย 1-100 (ครั้งแรกคือเช็คมอนหนี)
    """

    def __init__(self, roll=None, rolls=None, pct=100, pcts=None):
        super().__init__(0)
        if rolls:
            self.player_val = rolls[0]
            self.monster_val = rolls[1] if len(rolls) > 1 else rolls[0]
        else:
            self.player_val = 20 if roll is None else roll
            self.monster_val = 1
        self.pcts = list(pcts) if pcts else None
        self.pct = pct
        self._player_done = False

    def random(self):
        # เต๋าตีปกติ: <90 = ตกช่วงบน, >=90 = ช่วงพลาด — เลือกให้ตรงกับแต้มที่สั่งไว้
        return 0.0 if self.player_val >= 12 else 0.99

    def _next(self, queue, fallback):
        if not queue:
            return fallback
        return queue.pop(0) if len(queue) > 1 else queue[0]

    def randint(self, a, b):
        if (a, b) == (1, 100):
            return self._next(self.pcts, self.pct)
        if not self._player_done:                 # การทอยเต๋าครั้งแรกของเทิร์น = ของผู้เล่น
            self._player_done = True
            return max(a, min(b, self.player_val))
        return max(a, min(b, self.monster_val))   # ที่เหลือคือเต๋ามอน


# ── กติกาพื้นฐานของเทิร์น ─────────────────────────────────────────────────────

def test_a_normal_turn_returns_every_field_the_screen_needs(hero):
    t = adventure_core.fight_turn(1, _fight(), rng=Rigged(roll=20))
    for key in ("outcome", "player_roll", "monster_roll", "player_parts", "monster_parts",
                "damage_to_monster", "damage_to_player", "monster_hp", "player_hp", "fight"):
        assert key in t, f"ผลเทิร์นไม่มี {key} — หน้าจอวาดไม่ได้"
    assert t["outcome"] in ("win", "lose", "continue")


def test_winning_the_dice_damages_the_monster_not_you(hero):
    t = adventure_core.fight_turn(1, _fight(hp=99999), rng=Rigged(roll=20))
    assert t["damage_to_monster"] > 0 and t["damage_to_player"] == 0
    assert t["monster_hp"] < 99999


def test_the_monster_dies_when_its_hp_runs_out(hero):
    t = adventure_core.fight_turn(1, _fight(hp=1), rng=Rigged(roll=20))
    assert t["outcome"] == "win" and t["monster_hp"] == 0


def test_the_turn_counter_advances(hero):
    t = adventure_core.fight_turn(1, _fight(hp=99999), rng=Rigged(roll=20))
    assert t["fight"]["turn"] == 2, "เทิร์นต้องเดิน ไม่งั้นระบบคลั่งไม่ทำงาน"


def test_fight_state_stays_serialisable_across_turns(hero):
    """สู้บนเว็บต้องเซฟสถานะลง DB ทุกเทิร์น — มีอะไรที่ json ไม่รับปนมาไม่ได้"""
    import json
    f = _fight(hp=99999)
    for _ in range(3):
        f = adventure_core.fight_turn(1, f, rng=Rigged(roll=15))["fight"]
        json.dumps(f)


# ── ความเสียหายฝั่งผู้เล่น ────────────────────────────────────────────────────

def test_losing_the_dice_hurts_you_and_wears_the_armor(hero):
    t = adventure_core.fight_turn(1, _fight(hp=99999), rng=Rigged(rolls=[1, 20]))
    assert t["damage_to_player"] > 0 and t["damage_to_monster"] == 0
    assert t["db_updates"]["armor_dur"] < 100, "โดนตีแล้วเกราะต้องสึก"
    assert t["player_hp"] < 1000


def test_you_die_when_your_hp_runs_out(hero):
    hero["hp"] = 1
    t = adventure_core.fight_turn(1, _fight(hp=99999), rng=Rigged(rolls=[1, 20]))
    assert t["outcome"] == "lose" and t["player_hp"] == 0


def test_weapon_wears_faster_when_you_use_a_skill(hero):
    plain = adventure_core.fight_turn(1, _fight(hp=99999), rng=Rigged(roll=20))
    skill = adventure_core.fight_turn(1, _fight(hp=99999), skill_used="skill_heavy_strike",
                                      rng=Rigged(roll=20))
    assert plain["db_updates"]["weapon_dur"] == 49
    assert skill["db_updates"]["weapon_dur"] == 47, "ออกท่าต้องเปลืองอาวุธกว่าตีปกติ"


def test_a_broken_weapon_adds_no_attack_power(hero):
    hero["weapon_dur"] = 0
    broken = adventure_core.fight_turn(1, _fight(hp=99999), rng=Rigged(roll=20))
    hero["weapon_dur"] = 50
    ok = adventure_core.fight_turn(1, _fight(hp=99999), rng=Rigged(roll=20))
    assert broken["damage_to_monster"] < ok["damage_to_monster"]


# ── ธาตุ ──────────────────────────────────────────────────────────────────────

def test_light_monsters_can_bolt_before_the_turn_starts(hero):
    """ธาตุแสงหนีได้ = จบไฟต์ ไม่ได้รางวัล (จุดที่ทำให้มันเป็นของหายาก)"""
    if not game_modifiers.ELEMENTS["light"].get("monster_flee_chance"):
        pytest.skip("ธาตุแสงไม่มีเรทหนีในคอนฟิกนี้")
    t = adventure_core.fight_turn(1, _fight(element="light"), rng=Rigged(pct=1))
    assert t["outcome"] == "monster_fled"


def test_a_monster_trap_pins_even_a_light_monster(hero):
    f = _fight(element="light", statuses={"monster_trap": 1})
    hero["status_effects"] = '{"monster_trap": 1}'
    t = adventure_core.fight_turn(1, f, rng=Rigged(pct=1))
    assert t["outcome"] != "monster_fled", "ติดกับดักแล้วต้องหนีไม่ได้ — จุดขายหลักของกับดัก"


# ── สกิล ──────────────────────────────────────────────────────────────────────

def test_evasion_ends_the_fight_without_rewards(hero):
    hero["class_name"] = "Rogue"
    t = adventure_core.fight_turn(1, _fight(hp=99999), skill_used="skill_evasion",
                                  rng=Rigged(pcts=[100, 1]))
    assert t["outcome"] == "player_fled"
    assert hero["current_state"] == "idle", "หนีสำเร็จต้องปลดสถานะ ไม่งั้นค้าง"


def test_heavy_strike_multiplies_the_damage(hero):
    plain = adventure_core.fight_turn(1, _fight(hp=99999), rng=Rigged(roll=20, pcts=[100, 1]))
    heavy = adventure_core.fight_turn(1, _fight(hp=99999), skill_used="skill_heavy_strike",
                                      rng=Rigged(roll=20, pcts=[100, 1]))
    assert heavy["damage_to_monster"] > plain["damage_to_monster"]


def test_heal_restores_hp_without_passing_max(hero):
    hero["hp"] = 500
    t = adventure_core.fight_turn(1, _fight(hp=99999), skill_used="skill_heal",
                                  rng=Rigged(roll=20))
    assert t["player_hp"] > 500 and t["player_hp"] <= 1000


def test_skills_are_dead_while_emp_jams_you(hero):
    """ชิป EMP ปิดสกิลทั้งไฟต์ — กดมาก็ต้องกลายเป็นโจมตีธรรมดา ไม่ใช่พังทั้งเทิร์น"""
    if "disable_skills" not in str(game_modifiers.STATUS_EFFECTS):
        pytest.skip("คอนฟิกนี้ไม่มีสถานะปิดสกิล")
    t = adventure_core.fight_turn(1, _fight(hp=99999), skill_used="skill_heavy_strike",
                                  rng=Rigged(roll=20))
    assert t["outcome"] in ("win", "lose", "continue")


# ── ความคลั่งตามเทิร์น ────────────────────────────────────────────────────────

def test_bosses_hit_harder_the_longer_you_take(hero):
    early = adventure_core.fight_turn(1, _fight(hp=99999, rank="Main-Boss", turn=1),
                                      rng=Rigged(rolls=[1, 20]))
    late = adventure_core.fight_turn(1, _fight(hp=99999, rank="Main-Boss", turn=12),
                                     rng=Rigged(rolls=[1, 20]))
    assert late["damage_to_player"] > early["damage_to_player"], \
        "ระบบคลั่งต้องกดดันให้จบไฟต์เร็ว ไม่งั้นยืนตียาวได้ฟรี"


def test_missing_player_does_not_crash_the_turn(tmp_path, monkeypatch):
    monkeypatch.setattr(pm, "get_player", lambda uid: None)
    assert adventure_core.fight_turn(1, _fight())["outcome"] == "no_player"


# ── 🏆 รางวัลตอนชนะ (เฟส 5.6c) ────────────────────────────────────────────────

def test_victory_pays_gold_and_exp(hero):
    v = adventure_core.fight_victory(1, _fight(hp=0), rng=random.Random(3))
    assert v["reward"] > 0 and v["exp"] > 0
    assert v["current_exp"] >= 0 and v["level"] >= 1


def test_bigger_monsters_pay_more(hero):
    common = adventure_core.fight_victory(1, _fight(hp=0, rank="Common"), rng=random.Random(1))
    boss = adventure_core.fight_victory(1, _fight(hp=0, rank="Unbeatable"), rng=random.Random(1))
    assert boss["reward"] > common["reward"], "ไร้พ่ายต้องจ่ายหนักกว่ามอนธรรมดา"
    assert boss["exp"] > common["exp"]


def test_enough_exp_levels_you_up(hero):
    from bot.models.player_model import exp_required
    hero["level"] = 1
    hero["exp"] = exp_required(1) - 1          # ขาดอีกแต้มเดียว
    v = adventure_core.fight_victory(1, _fight(hp=0), rng=random.Random(5))
    assert v["level_up"] and v["level"] == 2
    assert hero["hp"] == hero["max_hp"], "เลเวลอัปต้องฟื้นเลือดเต็ม"


def test_rank_promotion_is_reported_not_granted(hero):
    """เว็บให้ยศ discord เองไม่ได้ — core ต้องคืนแรงค์ใหม่ออกมาให้ผู้เรียกจัดการ"""
    hero["level"] = 4
    hero["exp"] = 10 ** 9                       # ดันให้ข้ามหลายเลเวลรวด
    hero["rank"] = "F"
    v = adventure_core.fight_victory(1, _fight(hp=0), rng=random.Random(2))
    if v["promoted_rank"]:
        assert "เลื่อนขั้น" in v["rank_msg"]
    assert "discord" not in str(type(v.get("promoted_rank")))


def test_victory_result_is_serialisable(hero):
    import json
    json.dumps(adventure_core.fight_victory(1, _fight(hp=0), rng=random.Random(9)))


def test_dungeon_kills_say_there_is_more_ahead(hero):
    hero["dungeon_steps"] = 5
    v = adventure_core.fight_victory(1, _fight(hp=0), rng=random.Random(4))
    assert v["in_dungeon"] and "ดันเจี้ยน" in v["battle_end_log"]


def test_a_broken_bestiary_never_eats_your_reward(hero, monkeypatch):
    """สมุดล่าพังต้องไม่ทำให้รางวัลหาย — เดิมอยู่ใน try/except ต้องคงไว้"""
    monkeypatch.setattr(pm, "record_element_kill", lambda *a: 1 / 0)
    v = adventure_core.fight_victory(1, _fight(hp=0), rng=random.Random(6))
    assert v["reward"] > 0 and v["exp"] > 0


# ── 🐛 บั๊กที่เจอจากผู้เล่นจริง (2026-08-14) ─────────────────────────────────

def test_the_killing_turn_does_not_throw_away_its_own_effects(hero):
    """เทิร์นที่ล้มมอนต้องเซฟผลของเทิร์นนั้นด้วย — ฮีลที่เพิ่งกดห้ามหาย

    เดิม db_updates เป็น dict เดียวกันทั้งเทิร์นและก้อนรางวัล พอแยกฟังก์ชันแล้ว
    ก้อนรางวัลสร้าง dict ใหม่ ผลของเทิร์นสุดท้ายจึงหล่นหายทั้งชุด
    """
    saved = {}
    import bot.models.player_model as _pm
    orig = _pm.update_player_fields
    monkey = lambda uid, d: (saved.update(d), orig(uid, d))
    _pm.update_player_fields = monkey
    try:
        v = adventure_core.fight_victory(1, _fight(hp=0), carry={"hp": 777, "weapon_dur": 3},
                                         rng=random.Random(1))
    finally:
        _pm.update_player_fields = orig
    assert saved.get("weapon_dur") == 3, "ความทนทานที่สึกในเทิร์นสุดท้ายต้องถูกเซฟ"
    assert "cash" in saved, "ต้องเขียนรางวัลลง DB ในครั้งเดียวกัน"


def test_heal_amount_is_reported_for_the_screen(hero):
    """ต้องรู้ว่าฮีลไปเท่าไหร่ ถึงจะเด้งเลขให้เห็นบนจอได้"""
    hero["hp"] = 100
    t = adventure_core.fight_turn(1, _fight(hp=99999), skill_used="skill_heal",
                                  rng=Rigged(roll=20, pcts=[100, 1]))
    assert t["healed"] > 0 and t["player_hp"] == 100 + t["healed"]


def test_plain_attack_reports_no_heal(hero):
    t = adventure_core.fight_turn(1, _fight(hp=99999), rng=Rigged(roll=20))
    assert t["healed"] == 0


def test_web_shows_the_last_turn_log_when_you_win():
    """ดิสโชว์ช่อง '📜 เทิร์นสุดท้าย' ในหน้าชนะ เว็บก็ต้องโชว์ ไม่งั้นเหมือนชนะทันทีโดยไม่ตี"""
    import pathlib
    api = pathlib.Path("license_server/web_api.py").read_text(encoding="utf-8")
    assert api.count('out["log"]') >= 2, "หน้าชนะบนเว็บต้องมีล็อกเทิร์นสุดท้าย"
    assert 'carry=t.get("db_updates")' in api, "เว็บต้องส่งผลเทิร์นสุดท้ายไปเซฟด้วย"


# ── 🎯 สกิลครบทั้ง 8 ตัวของ 4 คลาส (ล็อกไว้หลังผู้เล่นทัก 2026-08-14) ─────────

class Lose(Rigged):
    """บังคับให้แพ้เต๋าแน่นอน — ผู้เล่นได้ 1 มอนได้ 20

    การทอย 1-100 ครั้งแรกคือเช็คมอนหนี (ให้ 100 = ไม่หนี) ที่เหลือให้ติดหมด
    เพื่อให้เอฟเฟกต์กันตัวอย่าง Holy Aura ทำงานแน่นอน
    """

    def __init__(self, seed=0):
        super().__init__(rolls=[1, 20], pcts=[100, 1])


def _taken(hero, skill, seeds=range(12)):
    """ดาเมจเฉลี่ยที่ผู้เล่นรับในเทิร์นที่กดสกิลนั้น"""
    vals = []
    for s in seeds:
        hero.update(hp=5000, max_hp=5000, weapon_dur=500, armor_dur=500)
        t = adventure_core.fight_turn(1, _fight(hp=10 ** 6), skill_used=skill, rng=Lose(s))
        if t["outcome"] in ("continue", "lose"):
            vals.append(t["damage_to_player"])
    return sum(vals) / max(1, len(vals))


@pytest.mark.parametrize("skill", ["skill_heavy_strike", "skill_shield_bash", "skill_fireball",
                                   "skill_frostbolt", "skill_backstab", "skill_evasion",
                                   "skill_heal", "skill_holy_aura"])
def test_every_class_skill_is_recognised(hero, skill):
    """กดสกิลแล้วต้องมีอะไรเกิดขึ้น — ไม่ใช่กลายเป็นตีธรรมดาเงียบ ๆ"""
    hero["class_name"] = "Cleric"
    t = adventure_core.fight_turn(1, _fight(hp=10 ** 6), skill_used=skill,
                                  rng=Rigged(roll=20, pcts=[100, 1]))
    if t["outcome"] == "player_fled":
        return                                        # Evasion จบไฟต์ ถือว่าออกฤทธิ์แล้ว
    fired = (t["skill_log"] or t["combat_log"] or t["healed"]
             or t["fight"]["buffs"])                  # ข้อความ / ฮีล / บัฟค้าง อย่างใดอย่างหนึ่ง
    assert fired, f"{skill} กดแล้วไม่มีผลอะไรเลย"


@pytest.mark.parametrize("skill,buff", [("skill_shield_bash", "shield_bash"),
                                        ("skill_fireball", "fireball"),
                                        ("skill_frostbolt", "frostbolt"),
                                        ("skill_holy_aura", "holy_aura")])
def test_buff_skills_survive_the_trip_through_the_database(hero, skill, buff):
    """บัฟต้องรอดจากการเซฟลง DB เป็น JSON ไม่งั้นสู้บนเว็บแล้วบัฟหายทุกเทิร์น"""
    import json
    t = adventure_core.fight_turn(1, _fight(hp=10 ** 6), skill_used=skill,
                                  rng=Rigged(roll=20, pcts=[100, 1]))
    saved = json.loads(json.dumps(t["fight"]))
    assert saved["buffs"].get(buff, 0) > 0, f"{buff} ไม่ค้างข้ามเทิร์น"


@pytest.mark.parametrize("skill", ["skill_shield_bash", "skill_frostbolt", "skill_holy_aura",
                                   "skill_backstab"])
def test_defensive_skills_actually_cut_the_damage(hero, skill):
    """สกิลกันดาเมจต้องลดของจริง ไม่ใช่แค่ขึ้นข้อความ"""
    hero["class_name"] = "Warrior"
    base = _taken(hero, None)
    with_skill = _taken(hero, skill)
    assert base > 0, "ตั้งเทสผิด — ไม่โดนตีเลย"
    assert with_skill < base * 0.9, f"{skill} ไม่ได้ลดดาเมจจริง ({with_skill:.1f} vs {base:.1f})"


def test_fireball_keeps_burning_after_the_turn_you_cast_it(hero):
    hero["class_name"] = "Mage"
    t = adventure_core.fight_turn(1, _fight(hp=10 ** 6), skill_used="skill_fireball",
                                  rng=Rigged(roll=20, pcts=[100, 1]))
    nxt = adventure_core.fight_turn(1, t["fight"], rng=Rigged(roll=20, pcts=[100, 1]))
    assert "เผาไหม้" in nxt["combat_log"], "ไฟบอลต้องเผาต่อในเทิร์นถัดไปตามค่า duration"


def test_heal_never_overflows_max_hp(hero):
    """ล็อกไว้: ข้อความบอกจำนวนที่ตั้งใจฮีล แต่ healed คือที่ได้จริงหลังชนเพดาน"""
    hero["hp"] = hero["max_hp"] - 1                   # ขาดอีกแต้มเดียวก็เต็ม
    t = adventure_core.fight_turn(1, _fight(hp=10 ** 6), skill_used="skill_heal",
                                  rng=Rigged(roll=20, pcts=[100, 1]))
    assert t["player_hp"] == hero["max_hp"] and t["healed"] == 1


def test_heal_reports_zero_when_already_full(hero):
    hero["hp"] = hero["max_hp"]
    t = adventure_core.fight_turn(1, _fight(hp=10 ** 6), skill_used="skill_heal",
                                  rng=Rigged(roll=20, pcts=[100, 1]))
    assert t["healed"] == 0, "เลือดเต็มอยู่แล้วต้องไม่เด้งเลขฮีลหลอกตา"


# ── 🎲 กติกาเต๋าใหม่ (2026-08-14) ─────────────────────────────────────────────

def test_a_plain_attack_can_never_roll_the_maximum():
    """แต้มสูงสุดเป็นของสกิลเท่านั้น — ตีปกติต้องไม่มีทางแตะ 20 เอง"""
    rolls = [adventure_core.roll_player_die(random.Random(s)) for s in range(4000)]
    assert max(rolls) < 20, f"ตีปกติทอยได้ {max(rolls)} ทั้งที่ห้ามแตะ 20"
    assert min(rolls) <= 11, "ต้องมีจังหวะพลาดร่วงลงมาบ้าง ไม่ใช่การันตีช่วงบนตลอด"


def test_a_skill_can_reach_the_maximum():
    rolls = [adventure_core.roll_player_die(random.Random(s), "skill_heavy_strike")
             for s in range(4000)]
    assert max(rolls) == 20, "ออกท่าต้องมีลุ้นแตะ 20"


def test_a_plain_attack_rolls_higher_on_average_than_a_skill():
    """ตีปกติ = มือที่ชำนาญ แต้มนิ่งกว่า · สกิล = เสี่ยงกว่าแต่ดาเมจแรงกว่า"""
    plain = [adventure_core.roll_player_die(random.Random(s)) for s in range(6000)]
    skill = [adventure_core.roll_player_die(random.Random(s), "skill_fireball")
             for s in range(6000)]
    assert sum(plain) / len(plain) > sum(skill) / len(skill) + 2


def test_about_ninety_percent_of_plain_attacks_land_in_the_top_band():
    hits = sum(1 for s in range(6000) if adventure_core.roll_player_die(random.Random(s)) >= 12)
    assert 85 <= hits / 6000 * 100 <= 95, f"ตกช่วงบน {hits / 60:.0f}% — ตั้งใจไว้ราว 90%"


def test_panel_can_retune_the_dice(monkeypatch):
    monkeypatch.setattr(config_loader, "get_balance",
                        lambda k, d=None: {"dice.normal_min": 5, "dice.normal_max": 6,
                                           "dice.normal_hit_pct": 100}.get(k, d))
    rolls = {adventure_core.roll_player_die(random.Random(s)) for s in range(300)}
    assert rolls <= {5, 6}


def test_broken_dice_config_never_breaks_the_fight(monkeypatch):
    monkeypatch.setattr(config_loader, "get_balance",
                        lambda k, d=None: {"dice.normal_min": "พัง", "dice.normal_max": None}.get(k, d))
    assert 1 <= adventure_core.roll_player_die(random.Random(0)) <= 20


@pytest.mark.parametrize("skill", ["skill_heavy_strike", "skill_shield_bash", "skill_fireball",
                                   "skill_frostbolt", "skill_backstab", "skill_heal",
                                   "skill_holy_aura"])
def test_any_skill_out_damages_a_plain_attack_at_the_same_roll(hero, skill):
    """กติกาที่ผู้เล่นขอ: ออกท่าแล้วทอยชนะ ต้องแรงกว่าตีปกติที่แต้มเท่ากันเสมอ
    รวมสกิลสายกันตัว/บัฟ เพราะกดแล้วทอยชนะก็ยังฟาดโดนมอนอยู่ดี"""
    plain = adventure_core.fight_turn(1, _fight(hp=10 ** 7), rng=Rigged(roll=15, pcts=[100, 1]))
    withs = adventure_core.fight_turn(1, _fight(hp=10 ** 7), skill_used=skill,
                                      rng=Rigged(roll=15, pcts=[100, 1]))
    assert plain["damage_to_monster"] > 0, "ตั้งเทสผิด — ตีปกติไม่โดน"
    assert withs["damage_to_monster"] > plain["damage_to_monster"], \
        f"{skill} ตีได้ {withs['damage_to_monster']} ไม่มากกว่าตีปกติ {plain['damage_to_monster']}"
