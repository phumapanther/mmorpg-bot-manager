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


def test_allowed_channel_skips_on_secondary_server(monkeypatch):
    """P8: เซิร์ฟรองใช้ห้องของตัวเอง — ด่านห้องจาก config (ของเซิร์ฟหลัก) ต้องไม่บล็อก"""
    import asyncio
    from bot import utils
    monkeypatch.setattr(config_loader, "get_main_guild_id", lambda: 999)
    monkeypatch.setattr(config_loader, "get_channel_id", lambda key: 12345)  # ห้องเซิร์ฟหลัก
    predicate = utils.allowed_channel("adventure").predicate

    async def _noop(*a, **k):
        return SimpleNamespace(delete=lambda: None)

    secondary = SimpleNamespace(guild=SimpleNamespace(id=111), channel=SimpleNamespace(id=777),
                                send=_noop, message=SimpleNamespace(delete=_noop))
    assert asyncio.run(predicate(secondary)) is True      # เซิร์ฟรอง = ผ่าน (ด่านรายเซิร์ฟคุมแทน)

    main_wrong_room = SimpleNamespace(guild=SimpleNamespace(id=999), channel=SimpleNamespace(id=777),
                                      send=_noop, message=SimpleNamespace(delete=_noop))
    assert asyncio.run(predicate(main_wrong_room)) is False   # เซิร์ฟหลักยังบังคับห้องตามเดิม


def test_play_room_rule_only_on_main_server():
    """!play ในเซิร์ฟรองไม่ต้องเปิดมิติส่วนตัวก่อน"""
    import pathlib
    src = pathlib.Path("bot/apps/bot_game/game_commands.py").read_text(encoding="utf-8")
    assert "if is_main_server(ctx) and required_room_part not in current_room_name:" in src


def test_portal_button_only_on_guest(monkeypatch):
    """ปุ่ม 🌏 ไปต่างโลก โผล่เฉพาะเซิร์ฟรอง และลิงก์ตรงกับ config"""
    import discord
    from bot.views.menu_view import CodexView
    monkeypatch.setattr(config_loader, "get_main_server_invite", lambda: "https://discord.gg/test")

    assert not [c for c in CodexView(show_portal=False).children if isinstance(c, discord.ui.Button)]
    btns = [c for c in CodexView(show_portal=True).children if isinstance(c, discord.ui.Button)]
    assert len(btns) == 1 and btns[0].url == "https://discord.gg/test"
    assert "ไปต่างโลก" in btns[0].label

    # ไม่ได้ตั้งลิงก์ = ไม่โผล่ปุ่ม (ไม่ให้ปุ่มตายค้าง)
    monkeypatch.setattr(config_loader, "get_main_server_invite", lambda: "")
    assert not [c for c in CodexView(show_portal=True).children if isinstance(c, discord.ui.Button)]
