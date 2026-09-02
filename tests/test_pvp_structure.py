"""โครงสร้างหมวด PVP หลังรื้อ (รื้อโครงสร้าง 2026-09-02)

ย้าย bot/pvp/*.py -> bot/games/pvp/*.py ให้เข้าโครงเดียวกับหมวดคาสิโนที่ทำไปแล้ว
เทสชุดนี้คุมกฎการแบ่งงาน ไม่ใช่คุมตรรกะเกม (ตรรกะเกมมีเทสของตัวเองอยู่แล้วที่
test_worms_*.py)
"""
import ast
import importlib
import pathlib

import pytest

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
PVP_NEW = REPO_ROOT / "bot" / "games" / "pvp"
MODULES = ["match", "terrain", "physics", "weapons", "rooms"]

# ฟังก์ชันขึ้นต้นด้วย _ ที่เทส worms เรียกข้ามไฟล์ผ่านสะพาน bot.pvp.{match,terrain,physics}
# (import * ไม่ดึงชื่อพวกนี้ให้ - ต้องดึงมาเพิ่มเองในสะพาน)
MATCH_UNDERSCORE_NAMES = [
    "_bodies", "_bot_aim", "_bot_attack", "_check_over", "_death_blasts",
    "_explode", "_fall_hurt", "_knock_back", "_open_chests", "_ride_ferry",
    "_rise_disaster", "_settle_everyone", "_supply_drop", "_use_skill",
]
TERRAIN_UNDERSCORE_NAMES = ["_building", "_open_spots", "_standable", "_tree"]
PHYSICS_UNDERSCORE_NAMES = ["_blocks"]

# ฟังก์ชันสาธารณะตัวแทนของแต่ละไฟล์ - ใช้เช็คว่าสะพาน "import *" ดึงของจริงมา
# ไม่ใช่แค่ import สำเร็จเฉย ๆ (ไฟล์เปล่าก็ import สำเร็จได้เหมือนกัน)
ANCHOR_NAME = {
    "match": "move",
    "terrain": "generate",
    "physics": "walk",
    "weapons": "spec",
    "rooms": "create",
}


# ── 1. โฟลเดอร์ใหม่มีจริงและ import ได้ ──

@pytest.mark.parametrize("modname", MODULES)
def test_โฟลเดอร์ใหม่มีจริงและ_import_ได้(modname):
    folder = PVP_NEW / f"{modname}.py"
    assert folder.is_file(), f"ไม่พบ bot/games/pvp/{modname}.py"
    mod = importlib.import_module(f"bot.games.pvp.{modname}")
    assert mod is not None


# ── 2. สะพานเก่ายังใช้ได้ และเป็นตัวเดียวกับที่ใหม่ ──

@pytest.mark.parametrize("modname", MODULES)
def test_สะพานเก่ายังใช้ได้และเป็นตัวเดียวกับที่ใหม่(modname):
    old = importlib.import_module(f"bot.pvp.{modname}")
    new = importlib.import_module(f"bot.games.pvp.{modname}")
    assert old is not None
    # เช็คฟังก์ชันตัวแทนก่อน - กันกรณีสะพานว่างเปล่าที่ import สำเร็จ
    # แบบไม่มีเนื้อ (test ด้านล่างที่วน dir() จะไม่จับกรณีนี้เพราะไม่มีอะไรให้เทียบ)
    anchor = ANCHOR_NAME[modname]
    assert hasattr(old, anchor), (
        f"bot.pvp.{modname} ไม่มี {anchor} - สะพานไม่ได้ import * จากของใหม่จริง")
    assert getattr(old, anchor) is getattr(new, anchor), (
        f"bot.pvp.{modname}.{anchor} ไม่ใช่ตัวเดียวกับ bot.games.pvp.{modname}.{anchor}")
    # เทียบตัวแทนของสองโมดูล (ไม่ใช่ตัว module object เอง เพราะสะพานคือคนละ
    # module object กับของใหม่จริง ๆ - แต่ฟังก์ชัน/ค่าที่ import * ดึงมาต้อง
    # เป็นตัวเดียวกันเป๊ะ)
    for name in dir(new):
        if name.startswith("__"):
            continue
        if hasattr(old, name):
            assert getattr(old, name) is getattr(new, name), (
                f"bot.pvp.{modname}.{name} ไม่ใช่ตัวเดียวกับ "
                f"bot.games.pvp.{modname}.{name}")


def test_ชื่อขีดล่างที่มีคนใช้ข้ามไฟล์ต้องอยู่ในสะพานด้วย():
    """import * ไม่ดึงชื่อขึ้นต้นด้วย _ - ต้องดึงมาเพิ่มเองในสะพาน"""
    from bot.pvp import match, physics, terrain
    for name in MATCH_UNDERSCORE_NAMES:
        assert hasattr(match, name), f"tests/test_worms_*.py เรียก match.{name}"
    for name in TERRAIN_UNDERSCORE_NAMES:
        assert hasattr(terrain, name), f"tests/test_worms_*.py เรียก terrain.{name}"
    for name in PHYSICS_UNDERSCORE_NAMES:
        assert hasattr(physics, name), f"tests/test_worms_*.py เรียก physics.{name}"


# ── 3. PVP ห้าม import จาก bot/cogs/ ──

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


def test_pvp_ห้าม_import_จาก_bot_cogs():
    for py_file in PVP_NEW.glob("*.py"):
        for name in _imported_modules(py_file):
            assert "bot.cogs" not in name, (
                f"{py_file.name} import จาก {name} - PVP ห้ามพึ่ง cogs")


# ── 4. PVP ห้าม import จากหมวดคาสิโน และกลับกัน ──

def test_pvp_ห้าม_import_จากหมวดคาสิโน():
    for py_file in PVP_NEW.glob("*.py"):
        for name in _imported_modules(py_file):
            assert "games.casino" not in name, (
                f"{py_file.name} import จาก {name} - คนละทีมกับคาสิโน")


def test_คาสิโน_ห้าม_import_จากหมวด_pvp():
    casino_root = REPO_ROOT / "bot" / "games" / "casino"
    for py_file in casino_root.rglob("*.py"):
        for name in _imported_modules(py_file):
            assert "games.pvp" not in name, (
                f"{py_file.name} import จาก {name} - คนละทีมกับ PVP")


# ── 5. โค้ดใหม่ห้ามอ้อมกลับหาสะพาน ──

def test_โค้ดใหม่ห้ามอ้อมกลับหาสะพาน():
    for py_file in PVP_NEW.glob("*.py"):
        for name in _imported_modules(py_file):
            assert not (name == "bot.pvp" or name.startswith("bot.pvp.")), (
                f"{py_file.name} import จาก {name} - ห้ามอ้อมกลับไปหาสะพานเก่า")
