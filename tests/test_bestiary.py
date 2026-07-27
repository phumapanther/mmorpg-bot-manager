"""P3 Bestiary: ชั้น DB (tmp) + helper ครบชุด + embed"""
import asyncio
from types import SimpleNamespace

import bot.game_modifiers as gm
import bot.models.player_model as pm


def _tmp_db(tmp_path, monkeypatch):
    monkeypatch.setattr(pm, "DB_NAME", str(tmp_path / "test.db"))


def test_record_and_get(tmp_path, monkeypatch):
    _tmp_db(tmp_path, monkeypatch)
    pm.record_bestiary_kill(1, "demon", "Common")
    pm.record_bestiary_kill(1, "demon", "Common")
    pm.record_bestiary_kill(1, "main", "Secret")
    book = pm.get_bestiary(1)
    assert book[("demon", "Common")] == 2 and book[("main", "Secret")] == 1
    assert pm.get_bestiary(2) == {}


def test_claim_reward_once(tmp_path, monkeypatch):
    _tmp_db(tmp_path, monkeypatch)
    assert pm.claim_bestiary_reward(1, "continent:demon") is True
    assert pm.claim_bestiary_reward(1, "continent:demon") is False   # ซ้ำไม่ได้
    assert pm.claim_bestiary_reward(2, "continent:demon") is True    # คนละคนแยกกัน


def test_continent_done_and_complete():
    book = {("demon", r): 1 for r in gm.BESTIARY_RANKS}
    assert gm.bestiary_continent_done(book, "demon") is True
    assert gm.bestiary_continent_done(book, "main") is False
    # ไร้พ่ายไม่จำเป็นต่อความครบ
    assert "Unbeatable" not in gm.BESTIARY_RANKS
    full = {(c, r): 1 for c in gm.CONTINENTS for r in gm.BESTIARY_RANKS}
    assert gm.bestiary_complete(full) is True
    full.pop(("ocean", "Secret"))
    assert gm.bestiary_complete(full) is False


def test_bestiary_embed(tmp_path, monkeypatch):
    _tmp_db(tmp_path, monkeypatch)
    from bot.cogs.player_commands import PlayerCommands
    pm.record_bestiary_kill(1, "demon", "Common")
    pm.record_bestiary_kill(1, "demon", "Unbeatable")
    sent = {}

    async def send(*a, **kw):
        sent["e"] = kw.get("embed") or a[0]

    ctx = SimpleNamespace(send=send, author=SimpleNamespace(
        id=1, display_name="T", display_avatar=SimpleNamespace(url="https://x/a.png")))
    asyncio.run(PlayerCommands.bestiary.callback(None, ctx))
    embed = sent["e"]
    assert len(embed.fields) == 10  # 9 ทวีป + สรุป
    demon_field = [f for f in embed.fields if "ปีศาจ" in f.name][0]
    assert "✅" in demon_field.value and "⭐" in demon_field.value
    assert "1/36" in embed.fields[-1].value and "1/9" in embed.fields[-1].value


def test_bestiary_menu_button():
    from bot.views.menu_view import GameMenuView
    assert any(getattr(c, "custom_id", "") == "game_menu:bestiary" for c in GameMenuView().children)
