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
