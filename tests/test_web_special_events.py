"""✨ อีเวนต์พิเศษ + 🎭 NPC ปลอมตัว — เล่นบนเว็บได้เท่ากับในดิส

เดิมเว็บขึ้นว่า "เล่นได้เฉพาะในดิสคอร์ด" สองกรณี: อีเวนต์แบบจ่ายผลทันที (instant)
กับอีเวนต์/NPC ที่ลากเข้าไฟต์ — ตอนนี้เว็บสู้ได้แล้ว จึงต้องเปิดให้ครบ
"""
import pathlib
import re

import pytest

from bot import adventure_core

API = pathlib.Path("license_server/web_api.py").read_text(encoding="utf-8")
PLAY = pathlib.Path("license_server/web_static/play.js").read_text(encoding="utf-8")
VIEWS = pathlib.Path("bot/views/game_views.py").read_text(encoding="utf-8")


class Fake:
    """DB จำลองในหน่วยความจำ — พอสำหรับตรวจว่าใครถูกหักอะไร"""

    def __init__(self, **over):
        self.p = {"user_id": 1, "hp": 100, "max_hp": 100, "cash": 50000, "bank": 0,
                  "inventory": "[]", "capacity": 10, "current_state": "npc_choice",
                  "level": 10, "status_effects": "{}"} | over

    def install(self, monkeypatch):
        import bot.models.player_model as pm
        monkeypatch.setattr(pm, "get_player", lambda uid: dict(self.p))
        monkeypatch.setattr(pm, "update_player_field", lambda uid, f, v: self.p.__setitem__(f, v))
        monkeypatch.setattr(pm, "update_player_fields", lambda uid, d: self.p.update(d))
        return self


# ── ✨ อีเวนต์พิเศษ ──

def test_the_web_no_longer_refuses_special_events():
    assert "อีเวนต์พิเศษแบบนี้ยังเล่นได้เฉพาะในดิสคอร์ด" not in API, \
        "ยังมีข้อความปฏิเสธอีเวนต์พิเศษค้างอยู่"
    assert "สัปดาห์นี้มีธีมปลอมตัว — คุยกับ NPC ได้เฉพาะในดิสคอร์ด" not in API, \
        "ยังกันไม่ให้คุยกับ NPC ในสัปดาห์ธีมปลอมตัว"
    assert "resolve_instant_special(special)" in API, "เว็บยังไม่ได้จ่ายผลอีเวนต์แบบ instant"


def test_a_special_that_starts_a_fight_actually_starts_one(monkeypatch):
    """เดิมอีเวนต์ที่ลากเข้าไฟต์ถูกกันไว้ทั้งอัน — ตอนนี้ต้องเกิดมอนแล้วสู้ต่อได้จริง"""
    from license_server import web_api
    st = Fake().install(monkeypatch)
    spawned = {}
    monkeypatch.setattr(adventure_core, "spawn_monster",
                        lambda uid, roles: spawned.setdefault("f", {
                            "stats": {"name": "เงาปริศนา"}, "rank": "Common", "element": "fire",
                            "hp": 80, "hp_max": 80, "turn": 1}))
    monkeypatch.setattr(adventure_core, "set_pending", lambda uid, e, d: spawned.update(pending=e))
    monkeypatch.setattr(web_api, "_money_now", lambda uid: {"cash": 0, "bank": 0})

    out = {"text": "โดนซุ่มโจมตี!"}
    web_api._finish_special(1, out, {"start_fight": True}, died=False)
    assert out["pending"] == "monster" and out["monster"]["name"] == "เงาปริศนา"
    assert st.p["current_state"] == "fighting", "ไม่ได้ล็อกสถานะเป็นกำลังสู้"
    assert spawned["pending"] == "monster", "ไม่ได้เก็บมอนไว้ให้กดสู้ต่อ"


def test_dying_in_a_special_locks_the_dead_state(monkeypatch):
    from license_server import web_api
    st = Fake().install(monkeypatch)
    cleared = []
    monkeypatch.setattr(adventure_core, "clear_pending", lambda uid: cleared.append(uid))
    out = {"text": "ตายคาที่"}
    web_api._finish_special(1, out, {}, died=True)
    assert out["died"] is True and st.p["current_state"] == "dead"
    assert cleared, "ตายแล้วต้องล้างเหตุการณ์ค้าง ไม่งั้นกดต่อไม่ได้"


def test_a_plain_special_ends_the_event(monkeypatch):
    st = Fake().install(monkeypatch)
    from license_server import web_api
    monkeypatch.setattr(adventure_core, "clear_pending", lambda uid: None)
    out = {"text": "เจอของดี"}
    web_api._finish_special(1, out, {"gold": 100}, died=False)
    assert out.get("pending") is None
    assert st.p["current_state"] == "idle", "จบอีเวนต์แล้วต้องปลดสถานะ ไม่งั้นค้างเล่นต่อไม่ได้"


# ── 🎭 NPC ปลอมตัว (สัปดาห์ธีม Masquerade) ──

def test_walking_into_a_disguised_npc_hurts_you(monkeypatch):
    st = Fake(hp=100).install(monkeypatch)
    r = adventure_core.npc_ambush(1, rng=type("R", (), {"randint": staticmethod(lambda a, b: 15)})())
    assert r["damage"] == 15 and r["died"] is False and r["start_fight"] is True
    assert st.p["hp"] == 85 and st.p["current_state"] == "fighting"


def test_a_disguised_npc_can_finish_you_off(monkeypatch):
    st = Fake(hp=5).install(monkeypatch)
    r = adventure_core.npc_ambush(1, rng=type("R", (), {"randint": staticmethod(lambda a, b: 15)})())
    assert r["died"] is True and st.p["hp"] == 0 and st.p["current_state"] == "dead"


def test_inspecting_costs_gold_and_catches_the_fake(monkeypatch):
    st = Fake(cash=50000).install(monkeypatch)
    r = adventure_core.npc_inspect(1, disguised=True, fee=1500)
    assert r["ok"] and r["start_fight"] and st.p["cash"] == 48500
    assert st.p["current_state"] == "fighting"


def test_inspecting_a_real_npc_leaves_you_free_to_talk(monkeypatch):
    st = Fake(cash=50000).install(monkeypatch)
    r = adventure_core.npc_inspect(1, disguised=False, fee=1500)
    assert r["ok"] and not r["start_fight"] and st.p["cash"] == 48500
    assert st.p["current_state"] == "npc_choice", "ตรวจแล้วเป็นตัวจริง ต้องคุยต่อได้"


def test_the_lens_is_used_instead_of_gold(monkeypatch):
    """มีแว่นส่องสัจจะ (id 38) ต้องใช้แว่นก่อน ไม่ใช่หักเงินทั้งที่พกแว่นอยู่"""
    st = Fake(cash=50000, inventory='["38"]').install(monkeypatch)
    r = adventure_core.npc_inspect(1, disguised=False, fee=1500)
    assert r["ok"] and st.p["cash"] == 50000, "พกแว่นแล้วยังโดนหักเงิน"
    assert "38" not in st.p["inventory"], "ใช้แว่นแล้วแว่นต้องหายไป"


def test_no_money_no_inspection_and_nothing_is_taken(monkeypatch):
    st = Fake(cash=100).install(monkeypatch)
    r = adventure_core.npc_inspect(1, disguised=True, fee=1500)
    assert not r["ok"] and st.p["cash"] == 100
    assert st.p["current_state"] == "npc_choice", "เงินไม่พอต้องไม่ถูกลากเข้าไฟต์"


def test_the_answer_never_reaches_the_browser():
    """เปิด devtools ดูแล้วต้องไม่รู้ว่าตัวไหนปลอม — ไม่งั้นระบบนี้ไร้ความหมาย"""
    state = API[API.index("def adventure_state("):]
    assert '"disguised" in data' in state[:1400], "ไม่ได้กรองคำเฉลยออกจาก /adventure/state"
    assert '"masquerade": True, "inspect_fee"' in state[:1400]
    assert "disguised" not in PLAY, "หน้าเว็บไม่ควรรู้จักคำว่า disguised เลย"


def test_discord_and_web_share_the_masquerade_rules():
    """ห้ามเขียนดาเมจ/ค่าตรวจซ้ำสองที่ — ดิสต้องเรียกฟังก์ชันกลางเหมือนเว็บ"""
    assert "adventure_core.npc_ambush(" in VIEWS
    assert "adventure_core.npc_inspect(" in VIEWS
    assert "npc_ambush(" in API and "npc_inspect(" in API
    body = VIEWS[VIEWS.index("async def _masquerade_ambush"):]
    assert "random.randint(10, 20)" not in body[:600], "ดิสยังคิดดาเมจซุ่มตีเอง"


def test_the_inspect_button_shows_up_on_the_web():
    block = re.search(r"npc: g => \[(.*?)\],\n", PLAY, re.S)
    assert block, "หาปุ่มของเหตุการณ์ NPC ไม่เจอ"
    assert "'inspect'" in block.group(1), "ไม่มีปุ่มตรวจสอบตัวตนบนเว็บ"
    assert "masquerade" in block.group(1), "ปุ่มตรวจต้องขึ้นเฉพาะสัปดาห์ธีมปลอมตัว"


# ── 💥 มอนโดนตีแล้วต้องขยับ ──

def test_a_hit_monster_reacts_visibly():
    scene = pathlib.Path("license_server/web_static/scene.js").read_text(encoding="utf-8")
    hit = scene[scene.index("hitFoe()"):scene.index("hitFoe()") + 260]
    for part in ("foeHit", "foeSpark", "foeFlash"):
        assert part in hit, f"โดนตีแล้วไม่มี {part} — ยังนิ่งเกินไป"
    draw = scene[scene.index("_drawFoe()"):scene.index("_drawFx(")]
    assert "sx" in draw and "sy" in draw, "ไม่มีการยุบตัวตอนโดนอัด"
    assert "GROUND_Y - 44) + 14 * (s - sy)" in draw, "ยุบแล้วตัวลอยหลุดพื้น"
