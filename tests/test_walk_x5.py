"""⏩ ปุ่มเดินเร็ว — เดินรวดจนเจอเหตุการณ์ที่ต้องตัดสินใจจริงเท่านั้น

กติกาที่ผู้เล่นสั่ง: เจอได้แค่ มอน · ดันเจี้ยน · โจร · หมู่บ้าน · กับดัก · พาหนะข้ามทวีป
หีบสมบัติ · พักผ่อน (ทางเงียบ) · NPC · อีเวนต์พิเศษ — ห้ามโผล่เด็ดขาด
"""
import pathlib

import pytest

import bot.views.game_views as gv
from tests import conftest


def test_button_exists():
    labels = [b.label for b in gv.AdventureView(1).children]
    assert any("เดินเร็ว" in l for l in labels) and any("เริ่มออกเดินทาง" in l for l in labels)


def test_walk_logic_rules():
    """กติกาที่ต้องคงไว้: วนซ้ำจุดเดียว + ถามกฎกลางว่าหยุดไหม + หยุดเมื่อเลือดต่ำกว่า 30%"""
    src = pathlib.Path("bot/views/game_views.py").read_text(encoding="utf-8")

    # ต้องมีจุดวนซ้ำจุดเดียวเท่านั้น — ไม่งั้นเงื่อนไขหยุดจะกระจายจนไล่ไม่ครบ
    assert src.count("max_steps=max_steps - 1") == 1, "จุดวนเดินเร็วต้องมีที่เดียว"
    loop = src[src.index("adventure_core.fast_walk_stops_here("):]
    assert "max_steps=max_steps - 1" in loop[:600], "ต้องนับก้าวถอยหลัง (กันวนไม่รู้จบ)"
    assert "max_hp" in loop[:600] and "0.3" in loop[:600], "ต้องหยุดเมื่อเลือดต่ำ"

    # ห้ามเขียนรายชื่อเหตุการณ์ที่หยุดไว้ในดิสเอง — ต้องถามกฎกลางที่เว็บใช้ร่วมกัน
    assert "adventure_core.fast_walk_stops_here(chosen_event, last_evt)" in src


def test_the_stop_list_is_exactly_what_the_player_asked_for():
    """เดินเร็วต้องเจอแค่ 6 อย่างนี้ — เพิ่ม/ลดต้องตั้งใจ ไม่ใช่หลุดมาเอง"""
    from bot import adventure_core as ac
    assert set(ac.FAST_WALK_STOPS) == {
        "monster", "dungeon", "mugging", "bank_robbery", "village", "trap", "travel"}
    for skip in ("calm", "treasure", "npc", "special"):
        assert not ac.fast_walk_stops_here(skip), f"{skip} ไม่ควรหยุดขบวนเดินเร็ว"


def test_an_item_summoned_step_always_stops():
    """ใช้ใบสแกนหีบแล้วเดินเร็วผ่านหีบไปเลย = ของหายฟรี ต้องหยุดเสมอ"""
    from bot import adventure_core as ac
    assert ac.fast_walk_stops_here("treasure", "scan_box"), "สแกนหีบแล้วต้องหยุดที่หีบ"
    for evt in ac.SUMMON_EVENTS:
        assert ac.fast_walk_stops_here("monster", evt), f"ใบเรียกบอส {evt} ต้องหยุด"


def test_the_web_uses_the_same_rule():
    api = conftest.web_api_source()
    assert "adventure_core.fast_walk_stops_here(event, pre[\"last_evt\"])" in api
    assert "steps: int = 1" in api, "เว็บต้องรับจำนวนก้าวได้"
    play = pathlib.Path("license_server/web_static/play.js").read_text(encoding="utf-8")
    assert "adventure/walk?steps=" in play, "หน้าเว็บไม่ได้ส่งจำนวนก้าวไป"


def test_default_single_step():
    """ปุ่มเดิมต้องยังเดินทีละก้าวเหมือนเดิม (max_steps=1)"""
    src = pathlib.Path("bot/views/game_views.py").read_text(encoding="utf-8")
    # ตรรกะเดินอยู่ในเมธอดธรรมดา (walk_step) ปุ่มทั้งสองเป็นแค่ตัวเรียก — ห้ามเรียกปุ่มเป็นฟังก์ชัน
    assert "async def walk_step(self, interaction: discord.Interaction, button: discord.ui.Button, max_steps=1):" in src
    assert "max_steps=adventure_core.FAST_WALK_MAX)" in src, "ปุ่มเดินเร็วต้องใช้เพดานกลาง"
    assert "await self.walk_step(interaction, button, max_steps=1)" in src


# ── เดินเร็วต้องเจอ "เฉพาะ 6 อย่างนี้เท่านั้น" ──

def _web(tmp_path, monkeypatch):
    """เปิดเว็บ API บน DB เปล่า พร้อมตัวละครหนึ่งตัว"""
    import time
    import bot.models.player_model as pm
    monkeypatch.setattr(pm, "DB_NAME", str(tmp_path / "w.db"))
    pm.init_db()
    uid = 4242
    pm.get_player(uid)
    pm.update_player_fields(uid, {"current_state": "idle", "hp": 9000, "max_hp": 9000,
                                  "cash": 1000, "bank": 0, "dungeon_steps": 0,
                                  "last_event": "none"})
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from license_server import web_api
    from license_server.api_web import deps as _api_web_deps

    monkeypatch.setattr(_api_web_deps, "GAME_DB_PATH", pathlib.Path(pm.DB_NAME))

    monkeypatch.setattr(web_api, "GAME_DB_PATH", pathlib.Path(pm.DB_NAME))  # เผื่อโค้ดเก่าอ่านผ่าน web_api
    app = FastAPI()
    app.include_router(web_api.router)
    c = TestClient(app)
    c.cookies.set("web_session", web_api.sign({"uid": str(uid), "exp": time.time() + 3600}))
    return c, uid


FORBIDDEN = ("calm", "treasure", "npc", "special")


@pytest.mark.parametrize("banned", FORBIDDEN)
def test_fast_walk_never_surfaces_a_forbidden_event(tmp_path, monkeypatch, banned):
    """ต่อให้ทุกก้าวสุ่มได้เหตุการณ์ต้องห้าม เดินเร็วต้องไม่เอามาโชว์เด็ดขาด
    (เคสนี้คือตอนหมดเพดานกันวน — เดิมจะเผลอโชว์ก้าวสุดท้ายออกมา)"""
    from bot import adventure_core
    monkeypatch.setattr(adventure_core, "decide_event",
                        lambda *a, **k: (banned, {"template": "instant", "outcomes": []}, 0))
    c, uid = _web(tmp_path, monkeypatch)
    g = c.post("/api/web/adventure/walk?steps=5").json()
    assert g["event"] == "fastwalk", f"เดินเร็วไปโผล่ {g['event']} ซึ่งต้องไม่เจอ"
    assert g["walked"] == adventure_core.FAST_WALK_MAX, "ต้องเดินจนครบเพดานก่อนถึงยอมจบ"
    assert g["pending"] is None, "จบแบบไม่เจออะไร ต้องไม่ล็อกสถานะไว้"

    import bot.models.player_model as pm
    assert pm.get_player(uid)["current_state"] == "idle", "สถานะค้าง = กดเดินต่อไม่ได้"


@pytest.mark.parametrize("stop", ["monster", "dungeon", "mugging", "bank_robbery",
                                  "village", "trap", "travel"])
def test_fast_walk_stops_on_each_of_the_six(tmp_path, monkeypatch, stop):
    """ทั้ง 6 อย่างที่ผู้เล่นสั่งไว้ ต้องหยุดขบวนได้จริงทุกตัว"""
    from bot import adventure_core
    monkeypatch.setattr(adventure_core, "decide_event", lambda *a, **k: (stop, None, 0))
    c, _uid = _web(tmp_path, monkeypatch)
    g = c.post("/api/web/adventure/walk?steps=5").json()
    assert g["event"] == stop and g["walked"] == 1, f"{stop} ต้องหยุดตั้งแต่ก้าวแรก"


def test_normal_walk_still_shows_everything(tmp_path, monkeypatch):
    """เดินทีละก้าวต้องไม่โดนกรอง — หีบ/NPC/อีเวนต์พิเศษยังเจอได้ตามปกติ"""
    from bot import adventure_core
    monkeypatch.setattr(adventure_core, "decide_event", lambda *a, **k: ("treasure", None, 0))
    c, _uid = _web(tmp_path, monkeypatch)
    g = c.post("/api/web/adventure/walk").json()
    assert g["event"] == "treasure" and g["pending"] == "treasure"


# ── เอฟเฟกต์เร่งสปีด ──

def test_the_scene_speeds_up_and_says_so():
    scene = pathlib.Path("license_server/web_static/scene.js").read_text(encoding="utf-8")
    assert "walk(fast)" in scene, "ฉากไม่รู้ว่ากำลังเดินเร็วอยู่"
    fx = scene[scene.index("_drawSpeed()"):scene.index("_drawFx(f, p)")]
    assert "เดินเร็ว" in fx, "ไม่มีป้ายบอกว่ากำลังเดินเร็ว"
    assert "this.frame" in fx, "เส้นความเร็วไม่ขยับ (วาดค้างที่เดิม)"
    assert "this.fast ? 7.5 : 2.2" in scene, "ความเร็วฉากไม่ต่างจากเดินปกติ"

    play = pathlib.Path("license_server/web_static/play.js").read_text(encoding="utf-8")
    assert "SCENE.walk(fast)" in play, "หน้าเว็บไม่ได้บอกฉากว่าเดินเร็วอยู่"
    assert "fastwalk" in play, "ไม่ได้รองรับผลลัพธ์ 'เดินเร็วแล้วยังไม่เจออะไร'"
