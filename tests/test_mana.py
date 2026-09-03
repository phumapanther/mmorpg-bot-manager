"""💎 มานา = เม็ดคริสตัล (2026-08-14) — จำนวนครั้งที่ "ใช้สกิลแล้วพลาด" ได้ต่อวัน

กติกาที่ต้องคุมไว้: เริ่มวันละ 3 เม็ด · +1 ทุก 20 เลเวล · เพดาน 10 ·
ทอยชนะไม่เสีย · ทอยแพ้เสีย 1 · เม็ดหมดใช้สกิลไม่ได้แต่ตีปกติได้
"""
import pathlib
import random

import pytest

import bot.models.player_model as pm
from bot import adventure_core, config_loader, mana
from tests import conftest


@pytest.fixture
def hero(tmp_path, monkeypatch):
    p = {"user_id": 1, "level": 1, "hp": 1000, "max_hp": 1000, "cash": 0, "bank": 0,
         "inventory": "[]", "weapon": "W", "armor": "A", "weapon_dur": 50, "armor_dur": 100,
         "current_state": "fighting", "last_event": "monster", "continent": "main",
         "race": None, "class_name": "Warrior", "status_effects": "{}", "pet": "",
         "mana": 3, "mana_date": mana._today()}
    monkeypatch.setattr(pm, "DB_NAME", str(tmp_path / "t.db"))
    monkeypatch.setattr(pm, "get_player", lambda uid: dict(p))
    monkeypatch.setattr(pm, "update_player_field", lambda uid, f, v: p.__setitem__(f, v))
    monkeypatch.setattr(pm, "update_player_fields", lambda uid, d: p.update(d))
    monkeypatch.setattr(config_loader, "get_weapon_stats", lambda k: {"atk": 10})
    monkeypatch.setattr(config_loader, "get_armor_stats", lambda k: {"hp": 100, "eva": 20})
    monkeypatch.setattr(config_loader, "get_balance", lambda key, default=None: default)
    return p


def _fight(**over):
    f = {"rank": "Common", "stats": dict(adventure_core.MONSTER_RANKS["Common"]),
         "hp": 10 ** 6, "hp_max": 10 ** 6, "element": "earth", "statuses": {},
         "fight_grace": [], "infused": False, "faction_side": None, "turn": 1, "buffs": {}}
    f.update(over)
    return f


class Roll(random.Random):
    """คุมผลแพ้ชนะเต๋า — เต๋าผู้เล่นกับของมอนทอยคนละช่วงแล้ว (ปรับ 2026-08-14)"""

    def __init__(self, win, seed=0):
        super().__init__(seed)
        self.player_val, self.monster_val = (20, 1) if win else (1, 20)
        self._player_done = False
        self.n100 = 0

    def random(self):
        return 0.0 if self.player_val >= 12 else 0.99

    def randint(self, a, b):
        if (a, b) == (1, 100):
            self.n100 += 1
            return 100 if self.n100 == 1 else 1      # ครั้งแรกคือเช็คมอนหนี อย่าให้หนี
        if not self._player_done:
            self._player_done = True
            return max(a, min(b, self.player_val))
        return max(a, min(b, self.monster_val))


# ── ขั้นบันไดตามเลเวล ────────────────────────────────────────────────────────

@pytest.mark.parametrize("level,expect", [(1, 3), (19, 3), (20, 4), (39, 4), (40, 5),
                                          (60, 6), (80, 7), (100, 8)])
def test_crystals_grow_one_step_every_twenty_levels(level, expect, hero):
    assert mana.max_mana(level) == expect


def test_the_cap_is_respected_even_at_absurd_levels(hero):
    assert mana.max_mana(10_000) == 10, "เพดาน 10 เม็ดต้องกันไว้เสมอ"


def test_panel_can_retune_every_number(hero, monkeypatch):
    monkeypatch.setattr(config_loader, "get_balance",
                        lambda k, d=None: {"mana.base": 5, "mana.per_levels": 10,
                                           "mana.max": 12}.get(k, d))
    assert mana.max_mana(0) == 5 and mana.max_mana(50) == 10 and mana.max_mana(200) == 12


def test_broken_panel_values_never_break_the_game(hero, monkeypatch):
    monkeypatch.setattr(config_loader, "get_balance",
                        lambda k, d=None: {"mana.per_levels": 0, "mana.base": "พัง"}.get(k, d))
    assert mana.max_mana(40) >= 0        # หารศูนย์/ค่าพิมพ์ผิดต้องไม่ระเบิด


# ── เติมข้ามวัน ───────────────────────────────────────────────────────────────

def test_a_new_day_refills_to_full(hero):
    hero.update(level=40, mana=0, mana_date="2020-01-01")
    assert mana.get(1) == 5, "ข้ามวันแล้วต้องเต็มตามเลเวลปัจจุบัน"
    assert hero["mana_date"] == mana._today()


def test_same_day_keeps_what_is_left(hero):
    hero.update(mana=1, mana_date=mana._today())
    assert mana.get(1) == 1


def test_levelling_up_raises_the_cap_immediately(hero):
    hero.update(level=19, mana=3, mana_date=mana._today())
    assert mana.get(1) == 3
    hero["level"] = 20
    assert mana.max_mana(hero["level"]) == 4, "อัปเลเวลแล้วเพดานต้องขยับทันที"


def test_stale_value_above_the_cap_is_clamped(hero):
    hero.update(level=1, mana=99, mana_date=mana._today())
    assert mana.get(1) == 3, "ค่าค้างเกินเพดานต้องถูกตัดลง"


# ── กติกาเสียเม็ด ─────────────────────────────────────────────────────────────

def test_winning_the_roll_with_a_skill_costs_nothing(hero):
    t = adventure_core.fight_turn(1, _fight(), skill_used="skill_heavy_strike", rng=Roll(win=True))
    assert t["mana_spent"] == 0 and hero["mana"] == 3, "ทอยชนะต้องไม่เสียเม็ด"


def test_losing_the_roll_with_a_skill_costs_one_crystal(hero):
    t = adventure_core.fight_turn(1, _fight(), skill_used="skill_heavy_strike", rng=Roll(win=False))
    assert t["mana_spent"] == 1 and hero["mana"] == 2
    assert "เม็ดคริสตัลแตก" in t["skill_log"]


def test_a_plain_attack_never_costs_mana(hero):
    for win in (True, False):
        hero["mana"] = 3
        t = adventure_core.fight_turn(1, _fight(), rng=Roll(win=win))
        assert t["mana_spent"] == 0 and hero["mana"] == 3


def test_running_dry_blocks_skills_but_not_the_rest(hero):
    hero["mana"] = 0
    blocked = adventure_core.fight_turn(1, _fight(), skill_used="skill_heavy_strike",
                                        rng=Roll(win=False))
    assert blocked["outcome"] == "no_mana" and "หมด" in blocked["text"]
    assert hero["hp"] == 1000, "ถูกบล็อกแล้วต้องไม่กินเทิร์น ไม่เสียเลือด"

    ok = adventure_core.fight_turn(1, _fight(), rng=Roll(win=True))
    assert ok["outcome"] == "continue", "เม็ดหมดก็ยังตีปกติได้"


def test_you_can_never_go_below_zero(hero):
    hero["mana"] = 1
    for _ in range(3):
        adventure_core.fight_turn(1, _fight(), skill_used="skill_heavy_strike", rng=Roll(win=False))
    assert hero["mana"] == 0


def test_restore_never_overflows(hero):
    hero["mana"] = 2
    assert mana.restore(1, 99) == 3


# ── หน้าจอทั้งสองแพลตฟอร์ม ────────────────────────────────────────────────────

def test_the_bar_shows_used_and_unused_crystals():
    assert mana.bar(2, 5) == "💎💎🖤🖤🖤"
    assert mana.bar(0, 3) == "🖤🖤🖤"
    assert "12" in mana.bar(4, 12), "เกิน 10 เม็ดสลับเป็นตัวเลขไม่ให้ล้นบรรทัด"


def test_both_platforms_show_and_gate_on_mana():
    gv = pathlib.Path("bot/views/game_views.py").read_text(encoding="utf-8")
    ui = pathlib.Path("bot/views/fight_ui.py").read_text(encoding="utf-8")
    api = conftest.web_api_source()
    js = pathlib.Path("license_server/web_static/play.js").read_text(encoding="utf-8")
    assert "disabled=crystals <= 0" in gv, "ดิสต้องดับปุ่มสกิลเมื่อเม็ดหมด"
    assert "_mana_bar(player)" in ui, "หน้าไฟต์ในดิสต้องโชว์เม็ด"
    assert '"no_player", "no_mana"' in api, "เว็บต้องกันใช้สกิลตอนเม็ดหมด"
    assert "MANA_LEFT <= 0" in js, "เว็บต้องดับปุ่มสกิลเมื่อเม็ดหมด"


def test_reading_game_state_never_writes_to_the_database():
    """/me/game เปิด DB แบบ mode=ro — ห้ามให้มานาไปเขียนตอนอ่าน ไม่งั้น 500 ทั้งหน้า"""
    api = conftest.web_api_source()
    view = api[api.index("def _mana_view("):api.index('@router.get("/me/game")')]
    assert "update_player" not in view and "mana.get(" not in view


def test_new_players_start_with_crystals():
    assert pm.NEW_PLAYER_DEFAULTS.get("mana") == 3
    assert "mana_date" in pm.NEW_PLAYER_DEFAULTS, "ต้องมีคอลัมน์วันที่ ไม่งั้นเติมข้ามวันไม่ได้"


# ── 🔄 จุดที่คืนเม็ดคริสตัล (2026-08-14) ──────────────────────────────────────

def test_resting_at_the_village_refills_you(hero, monkeypatch):
    monkeypatch.setattr(config_loader, "get_balance",
                        lambda k, d=None: {"village.rest_cost": 0}.get(k, d))
    monkeypatch.setattr(config_loader, "get_armor_stats", lambda k: {"hp": 0, "eva": 0})
    hero.update(level=40, mana=0, cash=99999, current_state="village")
    r = adventure_core.resolve_village(1, "rest")
    assert hero["mana"] == 5 and "เม็ดคริสตัลเต็ม" in r["text"]


def test_levelling_up_refills_you(hero):
    hero.update(level=1, exp=0, mana=0)
    pm.add_exp(1, 10 ** 9)
    assert hero["mana"] == mana.max_mana(hero["level"]), "เลเวลอัพต้องได้เม็ดเต็มตามเพดานใหม่"


def test_respawning_refills_you():
    """ตายแล้วเกิดใหม่ = ตั้งหลักใหม่ ต้องได้เม็ดเต็ม
    (ตรรกะย้ายไป adventure_core.respawn แล้ว เพราะเว็บก็ต้องฟื้นได้)"""
    src = pathlib.Path("bot/adventure_core.py").read_text(encoding="utf-8")
    block = src[src.index("def respawn(user_id):"):]
    assert "_mana.refill(user_id)" in block


def test_the_mana_potion_gives_a_crystal_back(hero, monkeypatch):
    """ยามานาต้องคืนเม็ด และห้ามกินทิ้งตอนเต็มอยู่แล้ว"""
    from bot.cogs.player_commands import apply_item_effect
    monkeypatch.setattr(config_loader, "get_item_config",
                        lambda i: {"name": "💠 ยามานา", "type": "use",
                                   "effect": "mana", "effect_amount": 1})
    hero.update(mana=1, inventory='["29"]')
    ok, msg = apply_item_effect(1, "29")
    assert ok and hero["mana"] == 2 and "มานา" in msg

    hero.update(mana=3, inventory='["29"]')
    ok, msg = apply_item_effect(1, "29")
    assert not ok and "เต็ม" in msg and hero["mana"] == 3


def test_the_mana_prism_gives_a_crystal_every_step(hero, monkeypatch):
    from bot import game_modifiers
    assert game_modifiers.STATUS_EFFECTS["art_mana_prism"]["mana_regen_per_step"] == 1
    hero.update(mana=0, status_effects='{"art_mana_prism": 1}', hp=500, max_hp=500)
    pre = adventure_core.step_prelude(1, dict(hero))
    assert hero["mana"] == 1, "เดินหนึ่งก้าวต้องได้เม็ดคืนหนึ่งเม็ด"
    assert any("ปริซึมมานา" in n for n in pre["notes"]), "ต้องบอกผู้เล่นด้วยว่าได้คืน"


def test_the_prism_never_overflows_the_cap(hero):
    hero.update(level=1, mana=3, status_effects='{"art_mana_prism": 1}', hp=500, max_hp=500)
    adventure_core.step_prelude(1, dict(hero))
    assert hero["mana"] == 3, "เต็มอยู่แล้วต้องไม่ล้นเพดาน"


def test_panel_and_codex_both_know_the_mana_effect():
    """ไอเทม effect ใหม่ต้องบอกผลได้ในคู่มือ และแท็บ Panel ต้องรู้จัก
    ไม่งั้นกดบันทึกที่ Panel ทีเดียว effect โดนล้างเงียบ ๆ"""
    # _item_effect_desc ย้ายไป core/services/codex.py แล้ว (ก้อนรื้อ core/services) — เช็คที่ไฟล์ใหม่
    codex_svc = pathlib.Path("core/services/codex.py").read_text(encoding="utf-8")
    app = pathlib.Path("panel/static/app.js").read_text(encoding="utf-8")
    assert 'if eff == "mana":' in codex_svc
    assert '{ value: "mana"' in app
