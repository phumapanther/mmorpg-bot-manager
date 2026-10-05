"""🌐 แปลภาษา — ข้อความไทยคือคีย์ · ภาษาปัจจุบันอยู่ใน contextvar

    from bot.i18n import tr
    await ctx.send(tr("ได้รับ {gold} ทอง", gold=g))

- หาคำแปลไม่เจอ / ไฟล์ไม่มี (exe ลูกค้า) → คืนข้อความไทยเดิม ไม่มีวันพัง
- ชื่อ tr ไม่ใช่ _ เพราะโค้ดเดิมใช้ _ เป็นตัวแปรทิ้งอยู่ 53 จุด (for _ in ...)
- คู่กับ license_server/web_static/i18n.js ฝั่งเบราว์เซอร์ — ไฟล์คำแปลชุดเดียวกัน
สเปก: docs/superpowers/specs/2026-10-05-i18n-design.md
"""
import contextlib
import contextvars
import json
from pathlib import Path

LANGS = ("th", "en", "zh", "ja")
# แบบเดียวกับ bot/event_images.py — อิง __file__ จึงใช้ได้ทั้งรันจากซอร์ส, Docker และ exe
LOCALES_DIR = Path(__file__).resolve().parent.parent / "license_server" / "web_static" / "locales"

_lang = contextvars.ContextVar("lang", default="th")
_tables = {}


def normalize(code):
    """รหัสภาษาดิสคอร์ด/เบราว์เซอร์ → th/en/zh/ja · ว่าง → th · ภาษาอื่น → en

    คู่กับ normLang() ใน web_static/i18n.js — tests/test_i18n_js.py เทียบให้ตรงกันเสมอ
    """
    base = str(code or "").strip().lower().replace("_", "-").split("-")[0]
    if not base:
        return "th"
    return base if base in LANGS else "en"


def current():
    """ภาษาของคำสั่ง/คำขอที่กำลังรันอยู่"""
    return _lang.get()


def set_lang(code):
    """ตั้งภาษาให้คำสั่ง/คำขอนี้ (task ที่สร้างต่อจากนี้ได้ภาษาเดียวกัน — asyncio คัดลอก context ให้)"""
    _lang.set(normalize(code))


@contextlib.contextmanager
def use_lang(code):
    """สลับภาษาชั่วคราว เช่นประกาศลงห้องด้วยภาษาเซิร์ฟเวอร์ — ออกจาก with แล้วกลับภาษาเดิม"""
    token = _lang.set(normalize(code))
    try:
        yield
    finally:
        _lang.reset(token)


def _table(lang):
    # ponytail: โหลดครั้งเดียวต่อโปรเซส — แก้ไฟล์คำแปลแล้วต้องรีสตาร์ทบอท/เว็บ
    if lang not in _tables:
        try:
            _tables[lang] = json.loads((LOCALES_DIR / f"{lang}.json").read_text(encoding="utf-8"))
        except (OSError, ValueError):
            _tables[lang] = {}          # exe ลูกค้าไม่มีโฟลเดอร์นี้ / ไฟล์พัง → ตกเป็นไทย
    return _tables[lang]


def tr(text, **kw):
    """ข้อความไทย → ภาษาปัจจุบัน แล้วเติม {ตัวแปร} · ไม่มีคำแปล = ไทยเดิม"""
    lang = _lang.get()
    s = text if lang == "th" else (_table(lang).get(text) or text)
    return s.format(**kw) if kw else s
