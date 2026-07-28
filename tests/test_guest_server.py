"""P8-③ บอทแจก: ห้องผจญภัยรายเซิร์ฟ + ด่านห้อง"""
import asyncio
from types import SimpleNamespace

import bot.models.player_model as pm
from bot import config_loader


def _db(tmp_path, monkeypatch):
    monkeypatch.setattr(pm, "DB_NAME", str(tmp_path / "t.db"))


def test_adv_channels_crud(tmp_path, monkeypatch):
    _db(tmp_path, monkeypatch)
    assert pm.get_adv_channels(1) == []
    assert pm.add_adv_channel(1, 100) is True
    assert pm.add_adv_channel(1, 100) is False        # ซ้ำ
    assert pm.add_adv_channel(1, 200) is True         # หลายห้องได้
    assert sorted(pm.get_adv_channels(1)) == [100, 200]
    assert pm.get_adv_channels(2) == []                # แยกรายเซิร์ฟ
    assert pm.remove_adv_channel(1, 100) is True
    assert pm.get_adv_channels(1) == [200]


def _gate_ctx(guild_id, channel_id, sent, command=None):
    async def send(msg=None, **kw):
        sent.append(msg)
    return SimpleNamespace(guild=SimpleNamespace(id=guild_id),
                           channel=SimpleNamespace(id=channel_id),
                           command=SimpleNamespace(name=command) if command else None,
                           send=send)


def test_channel_gate(tmp_path, monkeypatch):
    _db(tmp_path, monkeypatch)
    import bot.cogs.guest_server as gs
    monkeypatch.setattr(config_loader, "get_main_guild_id", lambda: 999)
    cog = gs.GuestServer.__new__(gs.GuestServer)
    sent = []

    # ยังไม่ตั้งห้อง → บล็อก + แนะนำวิธีตั้ง
    assert asyncio.run(cog.channel_gate(_gate_ctx(1, 100, sent))) is False
    assert "set_adv_channel" in sent[0]

    pm.add_adv_channel(1, 100)
    assert asyncio.run(cog.channel_gate(_gate_ctx(1, 100, sent))) is True    # ห้องถูก
    assert asyncio.run(cog.channel_gate(_gate_ctx(1, 555, sent))) is False   # ผิดห้อง
    # คำสั่งตั้งค่าใช้ได้ทุกห้อง
    assert asyncio.run(cog.channel_gate(_gate_ctx(1, 555, sent, command="set_adv_channel"))) is True
    # เซิร์ฟหลักไม่ถูกด่านนี้จำกัด
    assert asyncio.run(cog.channel_gate(_gate_ctx(999, 777, sent))) is True
