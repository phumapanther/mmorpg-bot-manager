"""บั๊กเฟส D #2: ตัดเถาวัลย์กลางไฟต์แล้วต้องหนีได้ (สแนปช็อตไฟต์ต้องไม่ขังผู้เล่น)"""
import asyncio
from types import SimpleNamespace

import bot.views.game_views as gv
import bot.game_modifiers as gm


def _fake_interaction():
    calls = {}

    async def send_message(msg=None, **kw):
        calls["send"] = msg

    async def edit_message(**kw):
        calls["edit"] = kw.get("content", "")

    return SimpleNamespace(response=SimpleNamespace(send_message=send_message, edit_message=edit_message),
                           user=SimpleNamespace(id=1, roles=[])), calls


def _fight_view(monkeypatch, db_statuses):
    monkeypatch.setattr(gv.player_model, "get_player",
                        lambda uid: {"hp": 100, "max_hp": 100, "status_effects": db_statuses,
                                     "level": 5, "cash": 0, "continent": "main"})
    monkeypatch.setattr(gv.player_model, "update_player_field", lambda *a, **k: None)
    v = gv.MonsterEventView(user_id=1, member_roles=[], monster_rank="Common", monster_hp=50,
                            fight_statuses={"entangled": 3})   # สแนปช็อตไฟต์: ยังโดนพัน
    v.m_stats["flee_chance"] = 100                              # หนีติดแน่นอนถ้าไม่ถูกบล็อก
    return v


def test_flee_blocked_while_still_entangled(monkeypatch):
    v = _fight_view(monkeypatch, '{"entangled": 3}')            # DB ยังมีเถา
    itx, calls = _fake_interaction()
    asyncio.run(gv.MonsterEventView.flee(v, itx, None))
    assert "รากไม้รัดขาแน่น" in calls["send"]


def test_flee_allowed_after_vine_cutter(monkeypatch):
    v = _fight_view(monkeypatch, "{}")                          # DB ถูกล้างแล้ว (ใช้มีดตัดเถา)
    itx, calls = _fake_interaction()
    asyncio.run(gv.MonsterEventView.flee(v, itx, None))
    assert "send" not in calls or "รากไม้" not in str(calls.get("send"))
    assert "entangled" not in v.statuses                        # สแนปช็อตถูกล้างตาม


def _bare_view(monkeypatch, db_statuses, snapshot, grace=()):
    monkeypatch.setattr(gv.player_model, "get_player",
                        lambda uid: {"status_effects": db_statuses, "hp": 100, "max_hp": 100})
    monkeypatch.setattr(gv.player_model, "update_player_field", lambda *a, **k: None)
    v = gv.MonsterEventView(user_id=1, member_roles=[], monster_rank="Common", monster_hp=50,
                            fight_statuses=dict(snapshot), fight_grace=set(grace))
    return v


def test_resync_drops_cured_statuses(monkeypatch):
    """รักษากลางไฟต์ (ชา/ไฟลวก) → สแนปช็อตต้องหลุดตาม DB"""
    v = _bare_view(monkeypatch, "{}", {"burn": 2, "numb": 1})
    v._resync_statuses(gv.player_model.get_player(1))
    assert v.statuses == {}


def test_resync_keeps_fight_grace(monkeypatch):
    """บัฟที่หมดอายุด้วย tick ต้นไฟต์ (เช่น น้ำมนต์ไฟต์สุดท้าย) ยังคุ้มครองจนจบไฟต์"""
    v = _bare_view(monkeypatch, "{}", {"holy_guard": 1}, grace={"holy_guard"})
    v._resync_statuses(gv.player_model.get_player(1))
    assert "holy_guard" in v.statuses


def test_resync_adds_midfight_buffs(monkeypatch):
    """กดใช้บัฟกลางไฟต์ (ชิป EMP) → มีผลทันทีในไฟต์นี้"""
    v = _bare_view(monkeypatch, '{"emp_shield": 1}', {})
    v._resync_statuses(gv.player_model.get_player(1))
    assert "emp_shield" in v.statuses
