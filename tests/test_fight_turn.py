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
    """ทอยเต๋าตามที่สั่ง — ใช้บังคับให้ผู้เล่นชนะ/แพ้เต๋าเพื่อทดสอบทีละเส้นทาง

    roll_combat ทอยของผู้เล่นก่อนเสมอ แล้วค่อยทอยของมอนทีละลูก
    ส่ง rolls=[ของผู้เล่น, ของมอน...] เพื่อคุมผลแพ้ชนะได้แม่น ๆ
    """

    def __init__(self, roll=None, rolls=None, pct=100, pcts=None):
        super().__init__(0)
        self.queue = list(rolls) if rolls else None
        self.roll = roll if roll is not None else 20
        # ทุกธาตุมีเรทมอนหนี 10% เป็นค่าตั้งต้น การทอย 1-100 ครั้งแรกของเทิร์นคือเช็คมอนหนีเสมอ
        # เทสที่อยากทดสอบสกิลจึงต้องให้ครั้งแรกสูง (ไม่หนี) แล้วครั้งถัดไปค่อยต่ำ (สกิลติด)
        self.pcts = list(pcts) if pcts else None
        self.pct = pct

    def _next(self, queue, fallback):
        if not queue:
            return fallback
        return queue.pop(0) if len(queue) > 1 else queue[0]

    def randint(self, a, b):
        if (a, b) == (1, 20):
            return self._next(self.queue, self.roll)
        if (a, b) == (1, 100):
            return self._next(self.pcts, self.pct)
        return b


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
