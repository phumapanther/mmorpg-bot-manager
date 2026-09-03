"""📐 คู่มือโครงสร้างต้องตรงกับของจริงเสมอ

docs/ARCHITECTURE.md คือสิ่งแรกที่คนใหม่ในทีมอ่าน — ถ้าเขียนถึงโฟลเดอร์/ไฟล์/เทส
ที่ไม่มีอยู่จริง คนอ่านจะหลงทาง เทสชุดนี้จับตอนโครงสร้างเปลี่ยนแล้วลืมแก้คู่มือ
"""
import pathlib
import re

import pytest

DOC = pathlib.Path("docs/ARCHITECTURE.md")


@pytest.fixture(scope="module")
def doc():
    assert DOC.is_file(), "ไม่มี docs/ARCHITECTURE.md"
    return DOC.read_text(encoding="utf-8")


# โฟลเดอร์หลักที่คู่มือวาดไว้ในแผนที่ — หายไปเมื่อไหร่คู่มือใช้ไม่ได้ทันที
FOLDERS = [
    "core/services",
    "bot/games/casino/uno", "bot/games/casino/blackjack",
    "bot/games/casino/slots", "bot/games/casino/hilo",
    "bot/games/pvp",
    "bot/apps/bot_game", "bot/apps/bot_admin", "bot/apps/bot_worker",
    "license_server/api_web", "license_server/api_web/games",
    "license_server/web_static/games",
    "templates/minigame",
]


@pytest.mark.parametrize("folder", FOLDERS)
def test_โฟลเดอร์ในคู่มือมีอยู่จริง(folder):
    assert pathlib.Path(folder).is_dir(), f"คู่มือพูดถึง {folder} แต่ไม่มีในโปรเจ็ค"


# ไฟล์ที่คู่มือชี้ให้ไปดู
FILES = [
    "bot/lobby.py",
    "bot/games/casino/shared.py",
    "license_server/api_web/deps.py",
    "license_server/rate_limit.py",
    "license_server/web_static/play.js",
    "license_server/web_static/games/worms_ui.js",
    "templates/README.md",
]


@pytest.mark.parametrize("path", FILES)
def test_ไฟล์ในคู่มือมีอยู่จริง(path):
    assert pathlib.Path(path).is_file(), f"คู่มือพูดถึง {path} แต่ไม่มีในโปรเจ็ค"


# ตารางเทสคุมโครงสร้างในคู่มือ — ลบเทสทิ้งแล้วคู่มือจะโกหก
STRUCTURE_TESTS = [
    "test_layering", "test_casino_structure", "test_pvp_structure",
    "test_apps_structure", "test_api_structure", "test_web_split",
    "test_rate_limit",
]


@pytest.mark.parametrize("name", STRUCTURE_TESTS)
def test_เทสคุมโครงสร้างที่คู่มืออ้างยังอยู่(name):
    assert pathlib.Path(f"tests/{name}.py").is_file(), \
        f"คู่มือบอกว่า {name}.py คุมโครงสร้างอยู่ แต่ไฟล์หายไปแล้ว"


def test_helper_อ่านซอร์สรวมยังอยู่():
    """คู่มือสอนให้ใช้ helper พวกนี้แทนการอ่านไฟล์ตรง ๆ"""
    conf = pathlib.Path("tests/conftest.py").read_text(encoding="utf-8")
    for fn in ("web_api_source", "play_js_source"):
        assert f"def {fn}" in conf, f"คู่มืออ้าง conftest.{fn}() แต่ไม่มีแล้ว"


def test_จำนวนไฟล์_cog_ตรงกับที่คู่มือบอก(doc):
    """คู่มือระบุจำนวนไฟล์ในแต่ละโปรเจ็คบอท — ย้ายไฟล์แล้วต้องอัปเดตตัวเลข"""
    for folder in ("bot_game", "bot_admin", "bot_worker"):
        real = len([f for f in pathlib.Path(f"bot/apps/{folder}").glob("*.py")
                    if f.name != "__init__.py"])
        m = re.search(rf"{folder}/\s+\S+\s+\S*\s*(\d+) ไฟล์", doc)
        assert m, f"คู่มือไม่ได้บอกจำนวนไฟล์ของ {folder}"
        assert int(m.group(1)) == real, \
            f"คู่มือบอก {folder} มี {m.group(1)} ไฟล์ แต่จริง ๆ มี {real}"


def test_README_หลักชี้มาที่คู่มือ():
    """คนใหม่เข้ามาต้องหาคู่มือเจอจากหน้าแรก"""
    readme = pathlib.Path("README.md").read_text(encoding="utf-8")
    assert "docs/ARCHITECTURE.md" in readme, "README หลักไม่ได้ลิงก์มาที่คู่มือโครงสร้าง"
    assert "templates/README.md" in readme, "README หลักไม่ได้ลิงก์ไปที่เทมเพลตมินิเกม"
