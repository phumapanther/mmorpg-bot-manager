"""ทุก dropdown ต้องผ่านกฎของ Discord — ไม่งั้นส่งไม่ออกทั้งอัน

เคสจริง (2026-08-01): TitleSelect/PetSelect ใส่ตัวเลือก "— ถอดออก —" ด้วย value=""
Python สร้าง object ได้ปกติ เทสก็ผ่าน แต่พอส่งจริง Discord ตอบ 400:
"In data.components.0.components.0.options.0.value: Must be between 1 and 100 in length"
→ ปุ่ม 🏅 ความสำเร็จ กดแล้วไม่ขึ้นอะไรเลย (และปุ่ม 🐾 สัตว์เลี้ยง จะพังเหมือนกัน
   ทันทีที่ผู้เล่นจับสัตว์เลี้ยงตัวแรกได้)
"""
import sqlite3

import pytest

import bot.models.player_model as pm
from bot import achievements, pets
from bot.views import menu_view as mv


def _check(select, where):
    opts = select.options
    assert 1 <= len(opts) <= 25, f"{where}: มี {len(opts)} ตัวเลือก (Discord รับ 1-25)"
    seen = set()
    for i, o in enumerate(opts):
        assert 1 <= len(o.value) <= 100, \
            f"{where} ตัวเลือกที่ {i}: value ยาว {len(o.value)} (ต้อง 1-100) — value={o.value!r}"
        assert 1 <= len(o.label) <= 100, f"{where} ตัวเลือกที่ {i}: label ยาวเกิน 100"
        if o.description is not None:
            assert len(o.description) <= 100, f"{where} ตัวเลือกที่ {i}: description ยาวเกิน 100"
        assert o.value not in seen, f"{where}: value ซ้ำ ({o.value!r})"
        seen.add(o.value)


@pytest.fixture
def player(tmp_path, monkeypatch):
    monkeypatch.setattr(pm, "DB_NAME", str(tmp_path / "t.db"))
    pm.init_db()
    uid = 42
    pm.get_player(uid)
    return uid


def test_title_dropdown_with_unlocked_titles(player, monkeypatch):
    """เคสที่พังจริง — ผู้เล่นที่ปลดตำแหน่งแล้วเท่านั้นถึงจะเห็น dropdown"""
    monkeypatch.setattr(achievements, "unlocked_titles",
                        lambda uid: ["นักล่าฝึกหัด", "ผู้พิชิตทุกทวีป"])
    view = mv.AchievementView(player)
    assert view.children, "ผู้เล่นที่มีตำแหน่งต้องเห็น dropdown"
    _check(view.children[0], "TitleSelect")


def test_pet_dropdown_with_owned_pets(player, monkeypatch):
    monkeypatch.setattr(pets, "owned", lambda uid: {p["key"] for p in pets.all_pets()})
    view = mv.PetView(player)
    assert view.children
    _check(view.children[0], "PetSelect")


def _select_of(view):
    return next(c for c in view.children if hasattr(c, "options"))


def test_codex_and_continent_dropdowns():
    _check(_select_of(mv.CodexView()), "CodexSelect")
    _check(_select_of(mv.ElementBookView()), "ElementBookSelect")


def test_no_dropdown_anywhere_uses_an_empty_value():
    """สแกนซอร์ส — กันเผลอเขียน value=\"\" ใหม่อีก"""
    import pathlib
    for f in pathlib.Path("bot").rglob("*.py"):
        src = f.read_text(encoding="utf-8")
        assert 'value=""' not in src, \
            f"{f} มี SelectOption value=\"\" — Discord ปฏิเสธทั้ง dropdown (ใช้ NONE_CHOICE แทน)"


def test_none_choice_round_trips():
    """เลือก 'ไม่เอาอะไรเลย' ต้องแปลงกลับเป็นค่าว่างก่อนส่งเข้าตรรกะเกม"""
    import pathlib
    src = pathlib.Path("bot/views/menu_view.py").read_text(encoding="utf-8")
    assert src.count('"" if self.values[0] == NONE_CHOICE else self.values[0]') == 2, \
        "ทั้ง TitleSelect และ PetSelect ต้องแปลง sentinel กลับเป็นค่าว่าง"
    assert len(mv.NONE_CHOICE) >= 1
