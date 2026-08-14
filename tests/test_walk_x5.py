"""O5: ปุ่ม ⏩ เดินต่อ ×5 — เดินรวดเฉพาะช่วงที่ไม่มีอะไรให้ตัดสินใจ"""
import pathlib

import bot.views.game_views as gv


def test_button_exists():
    labels = [b.label for b in gv.AdventureView(1).children]
    assert any("เดินต่อ" in l for l in labels) and any("เริ่มออกเดินทาง" in l for l in labels)


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
    api = pathlib.Path("license_server/web_api.py").read_text(encoding="utf-8")
    assert "adventure_core.fast_walk_stops_here(event, pre[\"last_evt\"])" in api
    assert "steps: int = 1" in api, "เว็บต้องรับจำนวนก้าวได้"
    play = pathlib.Path("license_server/web_static/play.js").read_text(encoding="utf-8")
    assert "adventure/walk?steps=" in play, "หน้าเว็บไม่ได้ส่งจำนวนก้าวไป"


def test_default_single_step():
    """ปุ่มเดิมต้องยังเดินทีละก้าวเหมือนเดิม (max_steps=1)"""
    src = pathlib.Path("bot/views/game_views.py").read_text(encoding="utf-8")
    # ตรรกะเดินอยู่ในเมธอดธรรมดา (walk_step) ปุ่มทั้งสองเป็นแค่ตัวเรียก — ห้ามเรียกปุ่มเป็นฟังก์ชัน
    assert "async def walk_step(self, interaction: discord.Interaction, button: discord.ui.Button, max_steps=1):" in src
    assert "await self.walk_step(interaction, button, max_steps=5)" in src
    assert "await self.walk_step(interaction, button, max_steps=1)" in src
