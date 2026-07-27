"""P4 ล่าค่าหัว: สูตรค่าหัว + คิวรีอาชญากร + กระดาน"""
import asyncio
import sqlite3
from types import SimpleNamespace

import bot.game_modifiers as gm
import bot.models.player_model as pm


def test_bounty_formula():
    assert gm.bounty_for(100) == 0 and gm.bounty_for(0) == 0     # สติปกติ = ไม่มีหัว
    assert gm.bounty_for(-1) == 12_000                            # 10k + 1×2k
    assert gm.bounty_for(-10) == 30_000
    assert gm.bounty_for(-999) == gm.BOUNTY_CAP                   # ชนเพดาน 100k


def test_get_outlaws_sorted(tmp_path, monkeypatch):
    monkeypatch.setattr(pm, "DB_NAME", str(tmp_path / "t.db"))
    conn = sqlite3.connect(pm.DB_NAME)
    conn.execute("CREATE TABLE players (user_id INTEGER PRIMARY KEY, sanity INTEGER)")
    conn.executemany("INSERT INTO players VALUES (?, ?)", [(1, 100), (2, -5), (3, -20), (4, 0)])
    conn.commit()
    conn.close()
    assert pm.get_outlaws() == [(3, -20), (2, -5)]  # เรียงคลั่งสุดก่อน, สติ 0 ไม่ติดกระดาน


def test_bounty_board_embed(monkeypatch):
    import bot.cogs.player_commands as pc
    monkeypatch.setattr(pc.player_model, "get_outlaws", lambda: [(3, -20), (2, -5)])
    sent = {}

    async def send(*a, **kw):
        sent["e"] = kw.get("embed") or a[0]

    asyncio.run(pc.PlayerCommands.bounty_board.callback(None, SimpleNamespace(send=send)))
    v = sent["e"].fields[0].value
    assert "<@3>" in v and "50,000" in v   # -20 → 10k+40k
    assert "<@2>" in v and "20,000" in v   # -5 → 10k+10k

    monkeypatch.setattr(pc.player_model, "get_outlaws", lambda: [])
    asyncio.run(pc.PlayerCommands.bounty_board.callback(None, SimpleNamespace(send=send)))
    assert "สงบสุข" in sent["e"].description
