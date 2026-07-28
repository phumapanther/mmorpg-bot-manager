"""P8-① ชั้นแยกเซิร์ฟหลัก/เซิร์ฟรอง"""
import asyncio
from types import SimpleNamespace

from bot import config_loader, utils


def _ctx(guild_id, sent):
    async def send(msg=None, **kw):
        sent.append(msg)
    return SimpleNamespace(guild=SimpleNamespace(id=guild_id), send=send)


def test_is_main_server_default_true(monkeypatch):
    monkeypatch.setattr(config_loader, "get_main_guild_id", lambda: None)
    assert utils.is_main_server(SimpleNamespace(guild=SimpleNamespace(id=123))) is True


def test_is_main_server_match(monkeypatch):
    monkeypatch.setattr(config_loader, "get_main_guild_id", lambda: 999)
    assert utils.is_main_server(SimpleNamespace(guild=SimpleNamespace(id=999))) is True
    assert utils.is_main_server(SimpleNamespace(guild=SimpleNamespace(id=111))) is False


def test_main_server_only_blocks_with_invite(monkeypatch):
    monkeypatch.setattr(config_loader, "get_main_guild_id", lambda: 999)
    monkeypatch.setattr(config_loader, "get_main_server_invite", lambda: "https://discord.gg/test")
    predicate = utils.main_server_only().predicate
    sent = []
    assert asyncio.run(predicate(_ctx(999, sent))) is True and sent == []
    assert asyncio.run(predicate(_ctx(111, sent))) is False
    assert "เซิร์ฟหลัก" in sent[0] and "discord.gg/test" in sent[0]


def test_config_keys_exist():
    import json
    cfg = json.load(open("config.example.json", encoding="utf-8"))
    assert "guest_bot_token" in cfg and cfg["guest_bot_token"] == ""
    assert "main_guild_id" in cfg and cfg["main_guild_id"] is None
    assert cfg["main_server_invite"].startswith("https://discord.gg/")


def test_locked_cogs_have_main_server_gate():
    """cog ที่ต้องล็อกไว้เซิร์ฟหลัก ต้องมีด่านเช็คจริง (กันเผลอลบตอน refactor)"""
    import pathlib
    must_gate = ["casino", "blackjack", "role_shop", "payment", "pvp_duel", "world_boss",
                 "world_admin", "private_room", "owner_announce", "guild", "guild_war",
                 "admin_commands"]
    for name in must_gate:
        src = pathlib.Path(f"bot/cogs/{name}.py").read_text(encoding="utf-8")
        assert "is_main_server(ctx)" in src, f"{name} ไม่มีด่านเซิร์ฟหลัก!"


def test_adventure_commands_stay_open():
    """คำสั่งเล่นผจญภัยต้องไม่ถูกล็อก (guest ต้องใช้ได้)"""
    import pathlib
    gc = pathlib.Path("bot/cogs/game_commands.py").read_text(encoding="utf-8")
    assert "async def cog_check" not in gc          # ไม่ล็อกทั้ง cog (มี !play/!menu)
    assert "@main_server_only()" in gc              # แต่ล็อก !shop
    adv = pathlib.Path("bot/cogs/adventure_zone.py").read_text(encoding="utf-8")
    assert "is_main_server" not in adv              # !adv เปิดให้เซิร์ฟรอง
