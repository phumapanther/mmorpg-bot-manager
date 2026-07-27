"""!codex ต้องสร้าง embed ได้ครบ 4 หมวด และทุก field ไม่เกินลิมิต Discord 1024"""
import asyncio
from types import SimpleNamespace

from bot.cogs.player_commands import PlayerCommands


def run_codex(topic):
    sent = {}

    async def send(*args, **kwargs):
        sent["embed"] = kwargs.get("embed") or (args[0] if args else None)

    ctx = SimpleNamespace(send=send)
    asyncio.run(PlayerCommands.codex.callback(None, ctx, topic=topic))
    return sent["embed"]


def test_codex_embeds_fit_discord_limits():
    for topic in ("", "ธาตุ", "สถานะ", "ทวีป", "วิธีเล่น", "คำสั่ง", "ไอเทม"):
        embed = run_codex(topic)
        assert embed is not None, topic
        assert len(embed.fields) <= 25
        for f in embed.fields:
            assert len(str(f.value)) <= 1024, f"{topic}: field เกินลิมิต ({len(str(f.value))})"


def test_codex_element_page_covers_all_elements():
    import bot.game_modifiers as gm
    embed = run_codex("ธาตุ")
    names = [f.name for f in embed.fields]
    for data in gm.ELEMENTS.values():
        assert data["label"] in names


def test_codex_menu_button_and_select():
    """ปุ่ม 📖 ในเมนู: select ครบ 6 หัวข้อ และทุก value สร้าง embed ได้จริง"""
    from bot.cogs.player_commands import build_codex_embed
    from bot.views.menu_view import CODEX_TOPICS, CodexView, GameMenuView

    select = CodexView().children[0]
    assert len(select.options) == 6
    for _, value in CODEX_TOPICS:
        embed = build_codex_embed(value)
        assert embed is not None and embed.title
    assert any(getattr(c, "custom_id", "") == "game_menu:codex" for c in GameMenuView().children)
