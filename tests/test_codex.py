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
    for topic in ("", "ธาตุ", "สถานะ", "ทวีป", "วิธีเล่น", "คำสั่ง", "ไอเทม", "กิลด์"):
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
    """ปุ่ม 📖 ในเมนู: select มีครบทุกหัวข้อ และทุก value สร้าง embed ได้จริง"""
    from bot.cogs.player_commands import build_codex_embed
    from bot.views.menu_view import CODEX_TOPICS, CodexView, GameMenuView

    select = CodexView().children[0]
    assert len(select.options) == len(CODEX_TOPICS)
    assert len(select.options) <= 25, "ลิมิตตัวเลือกของ Discord Select"
    for _, value in CODEX_TOPICS:
        embed = build_codex_embed(value)
        assert embed is not None and embed.title
    assert any(getattr(c, "custom_id", "") == "game_menu:codex" for c in GameMenuView().children)


# ── คู่มือหน้าใหม่ของกลุ่ม C ──

def test_new_codex_pages_exist_and_fit_discord():
    from bot.cogs.player_commands import build_codex_embed
    for topic in ("รางวัล", "สะสม", "สังคม"):
        embed = build_codex_embed(topic)
        assert embed.fields, f"หน้า {topic} ว่างเปล่า"
        assert len(embed) <= 6000
        for f in embed.fields:
            assert len(str(f.value)) <= 1024, f"หน้า {topic} ช่อง {f.name} ยาวเกินลิมิต"


def test_codex_menu_lists_every_topic():
    """เมนูดรอปดาวน์กับหน้าสารบัญต้องมีหัวข้อครบเท่ากัน — เพิ่มหน้าแล้วลืมใส่เมนู = ไม่มีใครเจอ"""
    from bot.cogs.player_commands import build_codex_embed
    from bot.views.menu_view import CODEX_TOPICS
    index = build_codex_embed("").description
    for _label, value in CODEX_TOPICS:
        assert f"`!codex {value}`" in index, f"สารบัญไม่มีหัวข้อ {value}"
        assert build_codex_embed(value).fields, f"เลือก {value} จากเมนูแล้วได้หน้าว่าง"


def test_new_systems_are_documented():
    """ระบบใหม่ทุกอันต้องมีที่อธิบายในคู่มือ ไม่งั้นผู้เล่นไม่รู้ว่ามีอยู่"""
    from bot.cogs.player_commands import build_codex_embed
    pages = " ".join(build_codex_embed(t).description + " ".join(f.name + f.value for f in build_codex_embed(t).fields)
                     for t in ("คำสั่ง", "รางวัล", "สะสม", "สังคม"))
    for cmd in ("!daily", "!season", "!top", "!ach", "!pet", "!market", "!marry"):
        assert cmd in pages, f"คู่มือไม่ได้พูดถึง {cmd}"


def test_patchnote_blocks_fit_discord():
    import pathlib, re
    txt = pathlib.Path("docs/patchnote-2026-07-28.md").read_text(encoding="utf-8")
    blocks = re.findall(r"```\n(.*?)```", txt, re.S)
    assert len(blocks) >= 5, "แพตช์โน้ตต้องแบ่งเป็นบล็อกให้ก็อปไปโพสต์ได้"
    for i, b in enumerate(blocks, 1):
        assert len(b) <= 2000, f"บล็อกที่ {i} ยาว {len(b)} ตัวอักษร เกินลิมิตดิสคอร์ด"
