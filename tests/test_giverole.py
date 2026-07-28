"""!giverole — แจกไอเทมให้เฉพาะคนที่ถือยศนั้น (ใช้ตอนมีกิจกรรมแล้วแจกยศผู้เข้าร่วม)"""
import asyncio
import json
import sqlite3
from types import SimpleNamespace

import pytest

import bot.models.player_model as pm
from bot.cogs.admin_commands import AdminCommands


@pytest.fixture
def world(tmp_path, monkeypatch):
    path = str(tmp_path / "t.db")
    monkeypatch.setattr(pm, "DB_NAME", path)
    conn = sqlite3.connect(path)
    conn.execute("CREATE TABLE players (user_id INTEGER PRIMARY KEY, inventory TEXT)")
    conn.executemany("INSERT INTO players VALUES (?, ?)",
                     [(1, json.dumps(["30"])), (2, json.dumps([]))])   # ผู้เล่น 3 ยังไม่เคยเล่น
    conn.commit()
    conn.close()
    return path


def _member(uid, name, bot=False):
    return SimpleNamespace(id=uid, display_name=name, bot=bot, mention=f"<@{uid}>")


class _Ctx:
    def __init__(self):
        self.sent = []

    async def send(self, msg):
        self.sent.append(msg)


def _inv(path, uid):
    conn = sqlite3.connect(path)
    raw = conn.execute("SELECT inventory FROM players WHERE user_id = ?", (uid,)).fetchone()[0]
    conn.close()
    return json.loads(raw)


async def _run(ctx, role, item_id, amount=1):
    cog = AdminCommands.__new__(AdminCommands)
    await AdminCommands.give_item_to_role.callback(cog, ctx, role, item_id, amount)


def test_gives_only_to_role_holders(world):
    role = SimpleNamespace(name="แฟนเดย์", mention="@แฟนเดย์",
                           members=[_member(1, "A"), _member(3, "ยังไม่เคยเล่น"), _member(9, "บอท", bot=True)])
    ctx = _Ctx()
    asyncio.run(_run(ctx, role, "65"))

    assert _inv(world, 1) == ["30", "65"], "คนที่มียศต้องได้แหวน ของเดิมไม่หาย"
    assert _inv(world, 2) == [], "คนที่ไม่มียศต้องไม่ได้อะไร"
    assert "สำเร็จ `1` คน" in ctx.sent[-1]
    assert "ยังไม่เคยเริ่มเล่น" in ctx.sent[-1] and "ยังไม่เคยเล่น" in ctx.sent[-1]


def test_amount_and_bad_input(world):
    role = SimpleNamespace(name="แฟนเดย์", mention="@x", members=[_member(1, "A"), _member(2, "B")])

    ctx = _Ctx()
    asyncio.run(_run(ctx, role, "65", 3))
    assert _inv(world, 1).count("65") == 3 and _inv(world, 2).count("65") == 3

    ctx = _Ctx()
    asyncio.run(_run(ctx, role, "ไม่มีไอเทมนี้"))
    assert "ไม่พบไอเทม" in ctx.sent[-1]

    ctx = _Ctx()
    asyncio.run(_run(ctx, role, "65", 0))
    assert "มากกว่า 0" in ctx.sent[-1]

    ctx = _Ctx()
    asyncio.run(_run(ctx, None, None))
    assert "วิธีใช้" in ctx.sent[-1]


def test_empty_role_says_so(world):
    ctx = _Ctx()
    asyncio.run(_run(ctx, SimpleNamespace(name="ว่าง", mention="@ว่าง", members=[]), "65"))
    assert "ไม่มีใครถือยศ" in ctx.sent[-1]


def test_command_is_admin_only():
    import pathlib
    src = pathlib.Path("bot/cogs/admin_commands.py").read_text(encoding="utf-8")
    block = src[src.index('name="giverole"') - 400:src.index('name="giverole"') + 400]
    assert 'has_permission("admin")' in block and "administrator=True" in block
