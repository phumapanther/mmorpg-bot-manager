"""ปุ่ม Stop ของ Panel ต้องปิดบอททุกตัวในโปรเซส

เคสจริง (2026-08-14):
1) บอทแจกไม่ได้โหลด cog server_status พอกด Stop บอทเกมปิดตัวแต่บอทแจกยังรัน
   โปรเซสไม่จบ พาแนลต้องรอ 6 วิแล้วบังคับฆ่า รวม 8 วิ ผู้ใช้คิดว่าปุ่มเสีย
2) ครั้งแรกที่แก้ เอาทะเบียนบอทไปไว้ใน bot/main.py — ใช้ไม่ได้ เพราะบอทรันด้วย
   `python -m bot.main` โมดูลนั้นเป็น __main__ พอ cog สั่ง import bot.main
   Python โหลดไฟล์เดิมขึ้นมาอีกก้อน ทะเบียนจึงเป็นคนละลิสต์และว่างเปล่า
"""
import asyncio
import pathlib

from bot import bot_registry


class FakeBot:
    def __init__(self, name, closed=False):
        self.bot_type = name
        self._closed = closed
        self.closed_calls = 0

    def is_closed(self):
        return self._closed

    async def close(self):
        self.closed_calls += 1
        self._closed = True


def test_close_all_closes_every_running_bot(monkeypatch):
    game, guest = FakeBot("game"), FakeBot("guest")
    monkeypatch.setattr(bot_registry, "ACTIVE_BOTS", [game, guest])
    asyncio.run(bot_registry.close_all())
    assert game.closed_calls == 1 and guest.closed_calls == 1


def test_already_closed_bot_is_skipped(monkeypatch):
    done, alive = FakeBot("game", closed=True), FakeBot("guest")
    monkeypatch.setattr(bot_registry, "ACTIVE_BOTS", [done, alive])
    asyncio.run(bot_registry.close_all())
    assert done.closed_calls == 0 and alive.closed_calls == 1


def test_one_bot_failing_does_not_block_the_others(monkeypatch):
    class Broken(FakeBot):
        async def close(self):
            raise RuntimeError("ปิดไม่ได้")

    broken, ok = Broken("game"), FakeBot("guest")
    monkeypatch.setattr(bot_registry, "ACTIVE_BOTS", [broken, ok])
    asyncio.run(bot_registry.close_all())
    assert ok.closed_calls == 1, "บอทตัวหนึ่งพังต้องไม่ทำให้ตัวอื่นไม่ถูกปิด"


def test_register_is_idempotent(monkeypatch):
    monkeypatch.setattr(bot_registry, "ACTIVE_BOTS", [])
    b = FakeBot("game")
    bot_registry.register(b)
    bot_registry.register(b)
    assert bot_registry.ACTIVE_BOTS == [b]


def test_created_bots_register_themselves(monkeypatch):
    import bot.main as bot_main
    monkeypatch.setattr(bot_registry, "ACTIVE_BOTS", [])
    bot_main.create_bot("game")
    bot_main.create_bot("guest")
    assert [b.bot_type for b in bot_registry.ACTIVE_BOTS] == ["game", "guest"]


def test_registry_lives_outside_the_entrypoint_module():
    """ทะเบียนต้องไม่อยู่ใน bot/main.py — โมดูลนั้นถูกรันเป็น __main__ ทำให้ import ได้คนละก้อน"""
    main_src = pathlib.Path("bot/main.py").read_text(encoding="utf-8")
    assert "ACTIVE_BOTS = []" not in main_src, "ทะเบียนต้องอยู่ใน bot/bot_registry.py"
    assert "bot_registry.register" in main_src

    cog_src = pathlib.Path("bot/cogs/server_status.py").read_text(encoding="utf-8")
    assert "from bot.main import" not in cog_src, "cog ห้าม import bot.main (ได้โมดูลคนละก้อน)"
    assert "bot_registry.close_all" in cog_src
