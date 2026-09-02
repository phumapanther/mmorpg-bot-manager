"""โครงสร้างแยก 3 โปรเจ็คย่อยของบอทดิสคอร์ดหลังรื้อ (รื้อโครงสร้าง 2026-09-02)

bot/cogs/*.py (24 ไฟล์) ถูกย้ายไป bot/apps/{bot_game,bot_admin,bot_worker}/ ตามหน้าที่
เพื่อแจกงานให้ทีมเกม/ทีมแอดมิน/ทีมระบบดูแลคนละส่วนได้โดยไม่ชนกัน
เทสชุดนี้คุมกฎการแบ่งงาน ไม่ใช่คุมตรรกะเกม (ตรรกะเกมมีเทสของตัวเองอยู่แล้ว)
"""
import importlib
import pathlib
import re

import pytest

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
APPS_ROOT = REPO_ROOT / "bot" / "apps"

BOT_ADMIN = ["admin_commands", "world_admin", "owner_announce", "guest_server"]
BOT_WORKER = ["db_backup", "role_grant_worker", "lobby_invite", "server_status",
              "voice_chat_tracker", "weekly_event"]
BOT_GAME = ["player_commands", "game_commands", "casino", "blackjack", "guild",
            "guild_war", "pvp_duel", "world_boss", "role_shop", "payment",
            "web_link", "adventure_zone", "private_room", "dice_board_cmd"]

GROUP_OF = {}
for _n in BOT_ADMIN:
    GROUP_OF[_n] = "bot_admin"
for _n in BOT_WORKER:
    GROUP_OF[_n] = "bot_worker"
for _n in BOT_GAME:
    GROUP_OF[_n] = "bot_game"

ALL_COGS = BOT_ADMIN + BOT_WORKER + BOT_GAME


# ── 1. ทุก cog ที่ย้ายแล้ว import ได้จากที่ใหม่ ──

@pytest.mark.parametrize("name", ALL_COGS)
def test_cog_ย้ายไปที่ใหม่แล้ว_import_ได้(name):
    group = GROUP_OF[name]
    path = APPS_ROOT / group / f"{name}.py"
    assert path.is_file(), f"ไม่พบ bot/apps/{group}/{name}.py"
    mod = importlib.import_module(f"bot.apps.{group}.{name}")
    assert mod is not None


# ── 2. สะพานเก่ายังใช้ได้ และเป็นตัวเดียวกับที่ใหม่ ──

@pytest.mark.parametrize("name", ALL_COGS)
def test_สะพานเก่ายังใช้ได้และเป็นตัวเดียวกับที่ใหม่(name):
    group = GROUP_OF[name]
    old = importlib.import_module(f"bot.cogs.{name}")
    new = importlib.import_module(f"bot.apps.{group}.{name}")
    assert hasattr(old, "setup"), (
        f"bot.cogs.{name} ไม่มี setup — สะพานไม่ได้ import * จากของใหม่จริง")
    assert old.setup is new.setup, f"bot.cogs.{name}.setup ไม่ใช่ตัวเดียวกับของใหม่"
    for attr in dir(new):
        if attr.startswith("__"):
            continue
        if hasattr(old, attr):
            assert getattr(old, attr) is getattr(new, attr), (
                f"bot.cogs.{name}.{attr} ไม่ใช่ตัวเดียวกับ bot.apps.{group}.{name}.{attr}")


# ── 3. ทุก cog มี setup() — กันบอทโหลด cog ไม่ขึ้นแบบเทสไม่จับ ──

def test_ทุก_cog_มี_setup():
    checked = 0
    for group in ("bot_game", "bot_admin", "bot_worker"):
        folder = APPS_ROOT / group
        for py_file in sorted(folder.glob("*.py")):
            if py_file.name == "__init__.py":
                continue
            src = py_file.read_text(encoding="utf-8")
            assert re.search(r"^async def setup\(", src, re.M), (
                f"{py_file.relative_to(REPO_ROOT)} ไม่มี async def setup(bot) — โหลดเป็น cog ไม่ได้")
            checked += 1
    assert checked == len(ALL_COGS), f"เช็คได้ {checked} ไฟล์ แต่ควรมี {len(ALL_COGS)}"


# ── 4. bot/main.py ชี้ path ที่มีอยู่จริง (สำคัญที่สุด — พิมพ์ผิดแล้วบอทตายเงียบ) ──

def _load_extension_paths():
    main_src = (REPO_ROOT / "bot" / "main.py").read_text(encoding="utf-8")
    return re.findall(r'load_extension\(\s*["\']([\w.]+)["\']', main_src)


def test_main_py_load_extension_import_ได้จริงทุกตัว():
    paths = _load_extension_paths()
    assert paths, "หา load_extension ใน bot/main.py ไม่เจอเลย — เทสอาจต้องแก้ regex"
    for modpath in paths:
        importlib.import_module(modpath)  # จะ raise ImportError ถ้าพิมพ์ path ผิด


def test_main_py_ชี้ที่ใหม่ตรงๆ_ไม่พึ่งสะพาน():
    """ตามข้อกำหนด: main.py ต้องแก้ให้ชี้ bot.apps.* ตรง ๆ ไม่ใช่พึ่งสะพาน bot.cogs.*"""
    for modpath in _load_extension_paths():
        assert not modpath.startswith("bot.cogs."), (
            f"{modpath} ยังชี้สะพานเก่าอยู่ — แก้ bot/main.py ให้ชี้ bot.apps ตรง ๆ")


@pytest.mark.parametrize("name", ALL_COGS)
def test_ทุก_cog_ถูกโหลดจาก_main_py(name):
    """กันลืมย้ายบางไฟล์ตกหล่นไม่มีใครโหลดเลย"""
    paths = _load_extension_paths()
    group = GROUP_OF[name]
    assert f"bot.apps.{group}.{name}" in paths, (
        f"bot/main.py ไม่ได้ load_extension bot.apps.{group}.{name}")


# ── 5. bot_worker ห้ามมีคำสั่งเลย (ไม่มีคำสั่ง = งานเบื้องหลังล้วน ๆ) ──

@pytest.mark.parametrize("name", BOT_WORKER)
def test_bot_worker_ห้ามมีคำสั่ง(name):
    src = (APPS_ROOT / "bot_worker" / f"{name}.py").read_text(encoding="utf-8")
    assert "@commands.command" not in src, (
        f"{name}.py มีคำสั่ง — จัดกลุ่มผิด (ควรอยู่ bot_game หรือ bot_admin)")


# ── 6. bot_admin ทุกไฟล์ต้องมีด่านล็อกสิทธิ์แอดมิน/เจ้าของเซิร์ฟ ──

_ADMIN_GATE_PATTERNS = (
    "has_permission", "commands.has_permissions", "is_owner",
    "ctx.author.id ==", "ctx.author.id !=",
)


@pytest.mark.parametrize("name", BOT_ADMIN)
def test_bot_admin_ทุกไฟล์ต้องล็อกสิทธิ์(name):
    src = (APPS_ROOT / "bot_admin" / f"{name}.py").read_text(encoding="utf-8")
    assert any(pat in src for pat in _ADMIN_GATE_PATTERNS), (
        f"{name}.py ไม่พบด่านล็อกสิทธิ์แอดมิน/เจ้าของเซิร์ฟเลย — จัดกลุ่มผิดหรือลืมล็อกสิทธิ์")
