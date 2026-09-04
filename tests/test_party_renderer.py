"""🎭 ทิศทางการพึ่งพาของโหมดปาร์ตี้ (เฟส 7)

⭐ เฟสนี้พิสูจน์ว่าออกแบบเฟส 1 ถูก: **เปลี่ยนกราฟิกได้โดยไม่แตะ Python เลย**
   ถ้าเทสในไฟล์นี้แดง แปลว่าโครงสร้างเริ่มพันกัน ต้องแก้ที่โครงสร้าง
   ไม่ใช่แก้เทสให้ผ่าน
"""
import io as _io
import pathlib
import re
import tokenize

import pytest

CORE = sorted(pathlib.Path("bot/games/party").glob("*.py"))
WEB = pathlib.Path("license_server/web_static")
RENDERERS = sorted((WEB / "games/party").glob("renderer_*.js"))
HTML = (WEB / "play.html").read_text(encoding="utf-8")


def _src(p):
    return p.read_text(encoding="utf-8")


def _code(p):
    """ซอร์สที่ตัด **คอมเมนต์กับ docstring** ออกแล้ว

    ⚠️ จำเป็นจริง ๆ ไม่ใช่ทำให้เทสผ่านง่ายขึ้น: ไฟล์พวกนี้เขียนอธิบายกฎไว้
       ในคอมเมนต์ตรง ๆ (เช่น "ห้าม import discord") เทสที่อ่านซอร์สดิบ
       จะไปจับคำในคำอธิบายของตัวเอง แล้วแดงทั้งที่โค้ดถูกต้อง
    """
    out, prev = [], tokenize.INDENT
    for tok in tokenize.generate_tokens(_io.StringIO(_src(p)).readline):
        if tok.type == tokenize.COMMENT:
            continue
        # สตริงที่ยืนเป็นคำสั่งเดี่ยว ๆ = docstring
        if tok.type == tokenize.STRING and prev in (
                tokenize.NEWLINE, tokenize.NL, tokenize.INDENT,
                tokenize.DEDENT, tokenize.ENCODING):
            prev = tok.type
            continue
        if tok.type not in (tokenize.NL, tokenize.NEWLINE):
            out.append(tok.string)
        prev = tok.type
    return chr(10).join(out)


# ── แกนต้องไม่รู้จักโลกภายนอก ──

@pytest.mark.parametrize("f", CORE, ids=lambda f: f.name)
def test_แกนปาร์ตี้ห้ามรู้จัก_discord(f):
    """แกนต้องใช้ได้ทั้งจากบอทและจากเว็บ — ผูก discord แล้วเว็บเรียกไม่ได้"""
    assert "discord" not in _code(f), f"{f.name} ไม่ควรรู้จัก discord"


@pytest.mark.parametrize("f", CORE, ids=lambda f: f.name)
def test_แกนปาร์ตี้ห้ามพึ่งชั้นแอป(f):
    """bot.apps / license_server เป็นชั้นบน แกนห้ามเรียกย้อนขึ้นไป"""
    for bad in ("bot.apps", "license_server", "fastapi"):
        assert bad not in _code(f), f"{f.name} พึ่ง {bad} — แกนต้องอยู่ล่างสุด"


@pytest.mark.parametrize("f", CORE, ids=lambda f: f.name)
def test_แกนปาร์ตี้ห้ามรู้จักการวาดภาพ(f):
    """แกนบอกแค่ "เกิดอะไรขึ้น" ไม่บอกว่า "วาดยังไง" """
    for bad in ("canvas", "getcontext", "#ff", "rgba(", "fillrect"):
        assert bad not in _code(f).lower(),             f"{f.name} มี {bad} ในโค้ด — นั่นเป็นเรื่องของ renderer"


# ── เปลี่ยนกราฟิกโดยไม่แตะ Python ──

def test_ไม่มีโค้ด_python_อ้างชื่อไฟล์_renderer():
    """⭐ หัวใจของเฟสนี้ — Python รู้จักชื่อไฟล์เมื่อไหร่ ก็สลับไม่ได้อีก

    (ยกเว้นเทส เพราะเทสมีหน้าที่ตรวจว่าหน้าเว็บโหลดถูกไฟล์)
    """
    for f in pathlib.Path(".").glob("[!.]*/**/*.py"):
        if "test" in f.parts[0] or f.name.startswith("test_"):
            continue
        assert "renderer_" not in _src(f),             f"{f} อ้างชื่อไฟล์ renderer — เปลี่ยนกราฟิกจะต้องมาแก้ Python ด้วย"


def test_หน้าเว็บโหลด_renderer_ตัวเดียว():
    """โหลดสองตัวพร้อมกัน = ตัวหลังทับฟังก์ชันตัวแรก งงกันทั้งคู่"""
    loaded = re.findall(r"/games/party/(renderer_[a-z_]+\.js)", HTML)
    assert len(loaded) == 1, f"play.html โหลด renderer {len(loaded)} ตัว: {loaded}"
    assert (WEB / "games/party" / loaded[0]).exists()


def test_renderer_ทุกตัวมีสัญญาครบ():
    """ไฟล์ไหนขาดฟังก์ชันไหน เอาไปเสียบแทนกันไม่ได้"""
    assert len(RENDERERS) >= 2, "ต้องมีอย่างน้อย 2 ตัวถึงจะพิสูจน์ว่าสลับได้จริง"
    for f in RENDERERS:
        src = _src(f)
        for fn in ("pbMount", "pbSetState", "pbPlay", "pbDraw", "pbClick"):
            assert f"function {fn}(" in src, f"{f.name} ไม่มี {fn}()"
        assert "onPartyPick" in src, f"{f.name} ไม่เรียกกลับตอนคลิกเป้า"


@pytest.mark.parametrize("f", RENDERERS, ids=lambda f: f.name)
def test_renderer_ห้ามตัดสินกติกา(f):
    """เบราว์เซอร์ส่งแค่ "กดปุ่มไหน" — คำนวณเองเมื่อไหร่ก็โกงได้"""
    src = _src(f)
    for bad in ("rollDice", "calcDamage", "element_multiplier", "PARTY_MULT"):
        assert bad not in src, f"{f.name} มี {bad} — กติกาตัดสินที่เซิร์ฟเวอร์"


@pytest.mark.parametrize("f", RENDERERS, ids=lambda f: f.name)
def test_renderer_ห้ามยิง_api_เอง(f):
    """renderer วาดอย่างเดียว การคุยกับเซิร์ฟเวอร์เป็นหน้าที่ของ lobby.js"""
    for bad in ("fetch(", "XMLHttpRequest", "/api/web"):
        assert bad not in _src(f), f"{f.name} คุยกับเซิร์ฟเวอร์เอง"
