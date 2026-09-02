"""ทดสอบโครงสร้างชั้น (layering) — ดึงตรรกะกลางออกจาก bot/cogs/ ไปไว้ core/services/

เจตนา: เว็บกับบอทดิสคอร์ดจะแยกทีมดูแล เว็บจึงห้ามพึ่งไฟล์คำสั่งดิสคอร์ดตรง ๆ อีกต่อไป
(ก่อนรื้อ เว็บ import จาก bot/cogs/ 13 จุด — เทสนี้กันคนเผลอเพิ่มกลับมา)
"""
import pathlib
import re

import pytest

ROOT = pathlib.Path(__file__).resolve().parent.parent
CORE_SERVICES = ROOT / "core" / "services"


def _service_files():
    return sorted(p for p in CORE_SERVICES.glob("*.py") if p.name != "__init__.py")


def test_เว็บห้าม_import_จาก_bot_cogs():
    src = (ROOT / "license_server" / "web_api.py").read_text(encoding="utf-8")
    hits = re.findall(r"(?:from|import)\s+bot\.cogs\b", src)
    assert hits == [], f"เว็บยังพึ่งไฟล์คำสั่งดิสคอร์ดอยู่ {len(hits)} จุด"


@pytest.mark.parametrize("path", _service_files(), ids=lambda p: p.name)
def test_core_services_ห้าม_import_discord(path):
    src = path.read_text(encoding="utf-8")
    assert not re.search(r"^\s*(?:import discord\b|from discord\b)", src, re.M), \
        f"{path.name} ห้าม import discord"


@pytest.mark.parametrize("path", _service_files(), ids=lambda p: p.name)
def test_core_services_ห้าม_import_จาก_bot_cogs(path):
    src = path.read_text(encoding="utf-8")
    assert not re.search(r"(?:from|import)\s+bot\.cogs\b", src), \
        f"{path.name} ห้าม import จาก bot/cogs"


def test_สะพานเก่ายังใช้ได้():
    """แก้ไฟล์คำสั่งดิสคอร์ดโดยไม่รู้ตัวว่าไปกระทบเว็บ — ของเดิมต้อง import ผ่านได้เหมือนก่อนรื้อ"""
    from bot.cogs.player_commands import bank_action, bank_fee  # noqa: F401
    from bot.cogs.player_commands import (  # noqa: F401
        usable_kind, apply_item_effect, buy_item_for, sell_item_for,
        drop_item_for, sell_all_junk,
    )
    from bot.cogs.player_commands import craft_for, craftable_now  # noqa: F401
    from bot.cogs.player_commands import build_codex_embed  # noqa: F401
    from bot.cogs.lobby_invite import validate  # noqa: F401


def test_พฤติกรรมเหมือนเดิม_bank():
    """ทางเก่ากับทางใหม่ต้องเป็นฟังก์ชันตัวเดียวกัน (สะพาน = re-export ตรง ๆ ไม่ใช่ก็อปปี้)"""
    from bot.cogs.player_commands import bank_action as old_action, bank_fee as old_fee
    from core.services.bank import bank_action as new_action, bank_fee as new_fee
    assert old_action is new_action
    assert old_fee is new_fee
    assert old_fee(500_000) == new_fee(500_000)


def test_พฤติกรรมเหมือนเดิม_craft():
    from bot.cogs.player_commands import craft_for as old_craft, craftable_now as old_check
    from core.services.crafting import craft_for as new_craft, craftable_now as new_check
    assert old_craft is new_craft
    assert old_check is new_check
