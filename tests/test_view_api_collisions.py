"""กันบอทล่มทั้งตัว: คลาส View/Item ห้ามตั้งชื่อทับเมธอดภายในของ discord.py

เคสจริง (2026-07-30): SeasonView ตั้งเมธอดชื่อ `_refresh(self, interaction, msg)`
ซึ่งไปทับ `View._refresh(self, components)` ของ discord.py — พอมีใครแก้ข้อความที่มี
ปุ่มอยู่ discord.py เรียก _refresh ด้วยอาร์กิวเมนต์ของตัวเอง → TypeError หลุดขึ้นไปถึง
gateway → asyncio.run พังทั้งโปรเซส บอททั้งตัวออฟไลน์ (เทสเดิมจับไม่ได้เลยสักตัว)
"""
import importlib
import inspect
import pathlib

import discord
import pytest

RESERVED = {n for n in dir(discord.ui.View) + dir(discord.ui.Item)
            if n.startswith("_") and not n.startswith("__")}

MODULES = sorted(str(p.with_suffix("")).replace("\\", ".").replace("/", ".")
                 for p in pathlib.Path("bot").rglob("*.py") if p.name != "__init__.py")


def _ui_classes():
    for name in MODULES:
        mod = importlib.import_module(name)
        for cls_name, obj in vars(mod).items():
            if (inspect.isclass(obj) and obj.__module__ == mod.__name__
                    and issubclass(obj, (discord.ui.View, discord.ui.Item))):
                yield f"{name}.{cls_name}", obj


def test_reserved_list_is_not_empty():
    assert "_refresh" in RESERVED and len(RESERVED) > 5


@pytest.mark.parametrize("path,cls", list(_ui_classes()), ids=lambda v: v if isinstance(v, str) else "")
def test_no_class_shadows_discord_internals(path, cls):
    clashes = sorted(set(vars(cls)) & RESERVED)
    assert not clashes, (
        f"{path} ตั้งชื่อทับของ discord.py: {clashes} — "
        "เปลี่ยนชื่อเป็นชื่อธรรมดา (ไม่ขึ้นต้นด้วย _) ไม่งั้นบอทล่มทั้งตัว")
