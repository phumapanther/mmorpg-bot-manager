"""🎭 แกนปาร์ตี้ต้องเป็นแกนจริง ๆ — ไม่รู้จัก Discord ไม่รู้จักเว็บ ไม่รู้จักการวาดภาพ

นี่คือเทสที่ทำให้ "เปลี่ยนกราฟิกได้ง่าย" เป็นจริง ไม่ใช่แค่ตั้งใจไว้เฉย ๆ
ถ้าใครเผลอ import discord หรือเรียกเข้า bot/apps/ เทสนี้แดงทันที
"""
import pathlib

import pytest

CORE = pathlib.Path("bot/games/party")
PY_FILES = sorted(CORE.glob("*.py"))


def test_มีไฟล์แกนอยู่จริง():
    assert PY_FILES, "ไม่เจอไฟล์ใน bot/games/party เลย"


@pytest.mark.parametrize("f", PY_FILES, ids=lambda f: f.name)
def test_แกนห้าม_import_discord(f):
    """แกนต้องใช้ได้ทั้งจากบอทและจากเว็บ — เว็บไม่ได้ติดตั้ง discord ก็ต้องรันได้"""
    for line in f.read_text(encoding="utf-8").splitlines():
        t = line.strip()
        assert not (t.startswith("import discord") or t.startswith("from discord")), \
            f"{f.name} import discord — แกนต้องไม่รู้จัก Discord"


@pytest.mark.parametrize("f", PY_FILES, ids=lambda f: f.name)
def test_แกนห้าม_import_จากชั้นตัวบอท(f):
    """bot/apps/ คือชั้นคำสั่งดิสคอร์ด ไม่ใช่แกนเกม — ทิศลูกศรต้องชี้เข้าแกนทางเดียว"""
    src = f.read_text(encoding="utf-8")
    for line in src.splitlines():
        t = line.strip()
        if t.startswith("#"):
            continue
        assert "bot.apps" not in t, f"{f.name} เรียกเข้า bot/apps/ — ผิดทิศ"


@pytest.mark.parametrize("f", PY_FILES, ids=lambda f: f.name)
def test_แกนห้ามรู้จักฝั่งเว็บ(f):
    """แกนห้าม import fastapi — ถ้าต้องใช้ แปลว่าโค้ดนั้นควรอยู่ที่ api_web/"""
    for line in f.read_text(encoding="utf-8").splitlines():
        t = line.strip()
        assert not t.startswith(("import fastapi", "from fastapi")), \
            f"{f.name} import fastapi — ย้ายไป license_server/api_web/ แทน"


def test_แกนโหลดได้โดยไม่มี_discord():
    """พิสูจน์ของจริง ไม่ใช่แค่ดูข้อความในไฟล์ — บล็อก discord แล้วต้องยัง import ได้"""
    import subprocess
    import sys
    code = (
        "import sys\n"
        "class Block:\n"
        "    def find_module(self, name, path=None):\n"
        "        if name == 'discord' or name.startswith('discord.'): return self\n"
        "    def load_module(self, name): raise ImportError('discord ถูกบล็อก')\n"
        "sys.meta_path.insert(0, Block())\n"
        "from bot.games.party import rules, events\n"
        "print('OK')\n"
    )
    r = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True)
    assert "OK" in r.stdout, f"แกนโหลดไม่ได้ถ้าไม่มี discord:\n{r.stderr[-400:]}"


def test_ไม่มีชื่อไฟล์_renderer_ในโค้ด_python():
    """เปลี่ยน renderer ต้องไม่ต้องแตะ Python — ถ้า Python รู้จักชื่อไฟล์ภาพ แปลว่าผูกกันแล้ว"""
    for f in PY_FILES:
        src = f.read_text(encoding="utf-8")
        code = "\n".join(l for l in src.splitlines() if not l.strip().startswith("#"))
        assert "renderer_" not in code, \
            f"{f.name} อ้างชื่อไฟล์ renderer — แกนต้องไม่รู้ว่าใครวาด"


def test_มีสัญญาเสียบเกมให้ทีมอ่าน():
    """ทีมที่จะทำเกมใหม่ต้องรู้ว่าเสียบเกมเข้าหน้าเว็บยังไง"""
    p = pathlib.Path("templates/minigame/MOUNT.md")
    assert p.is_file(), "ไม่มี templates/minigame/MOUNT.md"
    doc = p.read_text(encoding="utf-8")
    for kw in ("inline", "iframe"):
        assert kw in doc, f"MOUNT.md ไม่ได้อธิบายแบบ {kw}"


def test_ไฟล์เทสที่สั่งแกนได้ต้องหนีบฐานข้อมูลตัวละคร():
    """🔴 ตั้งแต่เฟส 9 สกิลไปอ่าน/หัก "เม็ดคริสตัล" จากฐานข้อมูลจริง

    ไฟล์เทสที่เรียก engine.act / room.begin แล้วไม่หนีบ player_model.DB_NAME
    จะไปเขียนทับข้อมูลตัวละครจริงทุกครั้งที่รันเทส
    (test_party_engine.py พลาดข้อนี้จริง เจอตอนเทสชุดเต็ม 2026-09-04)

    เทสนี้เงียบตอนนี้ แต่จะแดงทันทีที่มีคนเพิ่มไฟล์เทสใหม่โดยลืมหนีบ
    """
    import pathlib
    touches = ("engine.act(", "engine.strike(", "engine.monster_turn(",
               "room.begin(", "room.act(", "room.settle(", "skills.use(")
    bad = []
    for f in sorted(pathlib.Path("tests").glob("test_party_*.py")):
        src = f.read_text(encoding="utf-8")
        if not any(t in src for t in touches):
            continue
        if 'player_model, "DB_NAME"' not in src:
            bad.append(f.name)
    assert not bad, f"ไฟล์พวกนี้สั่งแกนได้แต่ไม่หนีบ DB ตัวละคร: {bad}"
