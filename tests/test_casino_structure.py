"""โครงสร้างหมวดคาสิโนหลังรื้อ (รื้อโครงสร้าง 2026-09-02)

เป้าหมาย: แบ่งโฟลเดอร์ให้คนดูแล UNO แก้ได้แค่โฟลเดอร์ตัวเอง ไม่กระทบ
คนดูแลแบล็กแจ็ค/สล็อต/ไฮโล — เทสชุดนี้คุมกฎการแบ่งงาน ไม่ใช่คุมตรรกะเกม
(ตรรกะเกมมีเทสของตัวเองอยู่แล้วที่ test_uno_*.py / test_blackjack_core.py / test_casino_core.py)
"""
import ast
import importlib
import pathlib

import pytest

CASINO_ROOT = pathlib.Path(__file__).resolve().parent.parent / "bot" / "games" / "casino"
GAME_FOLDERS = ["uno", "blackjack", "slots", "hilo"]


# ── 1. ทุกเกมมีโฟลเดอร์ของตัวเอง ──

@pytest.mark.parametrize("game", GAME_FOLDERS)
def test_ทุกเกมมีโฟลเดอร์ของตัวเองและ_import_ได้(game):
    folder = CASINO_ROOT / game
    assert folder.is_dir(), f"ไม่พบโฟลเดอร์ bot/games/casino/{game}/"
    mod = importlib.import_module(f"bot.games.casino.{game}")
    assert mod is not None


# ── 2. สะพานเก่ายังใช้ได้ ──

@pytest.mark.parametrize("modpath", [
    "bot.blackjack_core",
    "bot.casino_core",
    "bot.cards.uno_deck",
    "bot.cards.uno_rules",
    "bot.cards.uno_engine",
    "bot.cards.uno_bot",
    "bot.cards.uno_table",
    "bot.cards.uno_room",
])
def test_สะพานเก่ายังใช้ได้(modpath):
    mod = importlib.import_module(modpath)
    assert mod is not None


def test_ชื่อขีดล่างที่มีคนใช้ข้ามไฟล์ต้องอยู่ในสะพานด้วย():
    """import * ไม่ดึงชื่อขึ้นต้นด้วย _ — ต้องดึงมาเพิ่มเองในสะพาน"""
    from bot import blackjack_core
    from bot.cards import uno_room, uno_table
    assert hasattr(blackjack_core, "_view"), "web_api.py:745 เรียก blackjack_core._view"
    assert hasattr(uno_room, "_payout"), "tests/test_uno_money.py เรียก uno_room._payout"
    assert hasattr(uno_room, "_room"), "tests/test_uno_money.py เรียก uno_room._room"
    assert hasattr(uno_table, "_run_bots"), "tests/test_uno_web.py เรียก uno_table._run_bots"


# ── 3. เกมไม่ import ข้ามกัน ──

def _imported_modules(py_file):
    """แตกไฟล์ .py ด้วย ast แล้วคืนชื่อโมดูลที่ import ทั้งหมด (ไม่รันโค้ดจริง)"""
    tree = ast.parse(py_file.read_text(encoding="utf-8"))
    names = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names += [a.name for a in node.names]
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.append(node.module)
    return names


@pytest.mark.parametrize("game", GAME_FOLDERS)
def test_เกมไม่import_ข้ามหมวดเกมอื่นในคาสิโน(game):
    others = [g for g in GAME_FOLDERS if g != game]
    folder = CASINO_ROOT / game
    for py_file in folder.glob("*.py"):
        for name in _imported_modules(py_file):
            for other in others:
                assert f"casino.{other}" not in name, (
                    f"{py_file.name} import ข้ามไปหมวด {other} ("
                    f"{name}) — ห้ามข้ามทีมกัน")


# ── 4. ของกลางอยู่ที่เดียว ──

def test_take_bet_มีนิยามเดียวใน_shared():
    from bot.games.casino import shared
    from bot.games.casino.hilo import core as hilo_core
    from bot.games.casino.slots import core as slots_core
    assert hasattr(shared, "_take_bet")
    assert hilo_core._take_bet is shared._take_bet, "hilo ต้องใช้ตัวเดียวกับ shared ไม่ก๊อปซ้ำ"
    assert slots_core._take_bet is shared._take_bet, "slots ต้องใช้ตัวเดียวกับ shared ไม่ก๊อปซ้ำ"


# ── 5. พฤติกรรมไม่เปลี่ยน — ทางเก่ากับทางใหม่ต้องได้ผลเหมือนกันเป๊ะ ──

def test_ทางเก่ากับทางใหม่ให้ผลเหมือนกันเป๊ะ_hilo_slots():
    from bot import casino_core as old
    from bot.games.casino.hilo import core as new_hilo
    from bot.games.casino.slots import core as new_slots
    assert old.hilo_rig_chance(20000) == new_hilo.hilo_rig_chance(20000)
    assert old.slots_rig_chance(20000) == new_slots.slots_rig_chance(20000)
    assert old.slots_multiplier(["💰"] * 3) == new_slots.slots_multiplier(["💰"] * 3)
    assert old.play_hilo is new_hilo.play_hilo
    assert old.play_slots is new_slots.play_slots


def test_ทางเก่ากับทางใหม่ให้ผลเหมือนกันเป๊ะ_blackjack():
    from bot import blackjack_core as old
    from bot.games.casino.blackjack import core as new_bj
    assert old.rig_chance_for(150_000) == new_bj.rig_chance_for(150_000)
    assert old.start is new_bj.start


def test_ทางเก่ากับทางใหม่ให้ผลเหมือนกันเป๊ะ_uno():
    from bot.cards import uno_deck as old_deck
    from bot.games.casino.uno import deck as new_deck
    assert old_deck.SUITS == new_deck.SUITS
    assert old_deck.new_deck is new_deck.new_deck
