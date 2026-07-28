"""ปุ่มพังเงียบ: interaction เดียวตอบได้ครั้งเดียว — ×5 เคยตายเพราะวนซ้ำแล้วตอบซ้ำ"""
import asyncio
from types import SimpleNamespace

import pytest

import bot.views.game_views as gv
from bot import game_modifiers


class FakeResponse:
    """เลียนแบบ discord: ตอบซ้ำ = InteractionResponded เหมือนของจริง"""
    def __init__(self):
        self.done = False
        self.edits = 0

    def is_done(self):
        return self.done

    async def edit_message(self, **kwargs):
        if self.done:
            raise RuntimeError("InteractionResponded: interaction นี้ตอบไปแล้ว")
        self.done = True
        self.edits += 1

    async def send_message(self, *a, **k):
        if self.done:
            raise RuntimeError("InteractionResponded: interaction นี้ตอบไปแล้ว")
        self.done = True


def _fake_interaction():
    sent = []

    async def _send(*a, **k):
        sent.append(k.get("content", ""))
        return SimpleNamespace(id=1, edit=lambda **kw: None)

    itx = SimpleNamespace(
        response=FakeResponse(),
        followup=SimpleNamespace(send=_send),
        user=SimpleNamespace(id=1, roles=[], display_name="T"),
        message=SimpleNamespace(id=1),
        guild=None)
    return itx, sent


@pytest.fixture
def calm_world(monkeypatch):
    """บังคับให้ทุกก้าวเป็นอีเวนต์สงบ + ผู้เล่นเลือดเต็ม"""
    player = {"user_id": 1, "current_state": "idle", "hp": 100, "max_hp": 100, "level": 5,
              "cash": 100, "inventory": "", "status_effects": "{}", "dungeon_steps": 0,
              "village_cooldown": 0, "last_event": "none", "continent": "main"}
    monkeypatch.setattr(gv.player_model, "get_player", lambda uid: dict(player))
    monkeypatch.setattr(gv.player_model, "update_player_field", lambda *a, **k: None)
    monkeypatch.setattr(game_modifiers, "roll_travel_chance", lambda mods: False)
    monkeypatch.setattr(game_modifiers, "roll_special_event", lambda mods: None)
    monkeypatch.setattr(game_modifiers, "roll_calm_chance", lambda: True)
    return player


def test_walk_x5_survives_five_steps(calm_world):
    """กดเดินรวด ×5 ต้องจบสวย — ไม่ตอบ interaction ซ้ำจนหลุด on_error"""
    view = gv.AdventureView(author_id=1)
    itx, sent = _fake_interaction()

    x5 = next(b for b in view.children if b.label and "×5" in b.label)
    asyncio.run(x5.callback(itx))          # เรียกผ่าน children เหมือน discord จริง

    assert itx.response.edits == 1, "ตอบ interaction ได้ครั้งเดียวเท่านั้น"
    assert len(sent) == 1, "เดินรวดต้องสรุปเป็นข้อความเดียวตอนจบ"
    assert "เดินรวด 5 ก้าว" in sent[0]


def test_browsing_views_have_room_to_read():
    """หน้าเดินดู (หมู่บ้าน/ร้านค้า) ต้องไม่หมดอายุใน 60 วิ จนกดปุ่มไม่ติด"""
    assert gv.VillageEventView(1).timeout >= 300
    assert gv.ShopEventView(1).timeout >= 300


def test_no_view_calls_its_own_button_as_function():
    """discord.py setattr ทับชื่อเมธอดที่ครอบ @button ด้วยอ็อบเจ็กต์ Button
    → self.ชื่อปุ่ม(...) จะพัง 'Button' object is not callable ทุกครั้ง (บั๊กปุ่ม ×5 เดิม)"""
    import ast, pathlib
    bad = []
    for f in sorted(pathlib.Path("bot").rglob("*.py")):
        for cls in [n for n in ast.walk(ast.parse(f.read_text(encoding="utf-8")))
                    if isinstance(n, ast.ClassDef)]:
            btns = {m.name for m in cls.body
                    if isinstance(m, (ast.FunctionDef, ast.AsyncFunctionDef))
                    and any("button" in ast.unparse(d) or "select" in ast.unparse(d)
                            for d in m.decorator_list)}
            for call in [n for n in ast.walk(cls) if isinstance(n, ast.Call)]:
                fn = call.func
                if (isinstance(fn, ast.Attribute) and isinstance(fn.value, ast.Name)
                        and fn.value.id == "self" and fn.attr in btns):
                    bad.append(f"{f}:{call.lineno} {cls.name}.{fn.attr}()")
    assert not bad, "ต้องแยกตรรกะเป็นเมธอดธรรมดาแล้วให้ปุ่มเรียกแทน:\n" + "\n".join(bad)


def test_action_views_report_errors(monkeypatch):
    """ปุ่มพังต้องบอกผู้เล่น ไม่ใช่เงียบหาย"""
    view = gv.VillageEventView(1)
    itx, _sent = _fake_interaction()
    replies = []
    itx.response.send_message = lambda msg, **k: replies.append(msg) or _noop()

    async def _noop():
        return None

    asyncio.run(view.on_error(itx, ValueError("พังทดสอบ"), SimpleNamespace(label="🏦 ธนาคาร")))
    assert replies and "ธนาคาร" in replies[0]
