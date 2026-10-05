"""🌐 แกนแปลภาษาฝั่ง Python — ข้อความไทยคือคีย์ ภาษาปัจจุบันอยู่ใน contextvar

สเปก: docs/superpowers/specs/2026-10-05-i18n-design.md
"""
import asyncio
import json
import pathlib

import pytest

from bot import i18n

# ใช้ร่วมกับ tests/test_i18n_js.py — normLang() ฝั่ง JS ต้องตอบตรงกันทุกข้อ
NORMALIZE_CASES = [
    (None, "th"), ("", "th"), ("  ", "th"),
    ("th", "th"), ("TH", "th"), ("th-TH", "th"),
    ("en-US", "en"), ("en-GB", "en"),
    ("zh-CN", "zh"), ("zh-TW", "zh"), ("zh_TW", "zh"),
    ("ja", "ja"), ("ja-JP", "ja"),
    ("ko", "en"), ("fr", "en"), ("pt-BR", "en"),
]


@pytest.fixture
def tables(monkeypatch, tmp_path):
    (tmp_path / "en.json").write_text(json.dumps(
        {"ได้รับ {gold} ทอง": "Got {gold} gold", "ว่าง": ""}, ensure_ascii=False), encoding="utf-8")
    monkeypatch.setattr(i18n, "LOCALES_DIR", tmp_path)
    monkeypatch.setattr(i18n, "_tables", {})
    return tmp_path


@pytest.mark.parametrize("code,want", NORMALIZE_CASES)
def test_แปลงรหัสภาษาเหลือ_4_ภาษา(code, want):
    assert i18n.normalize(code) == want


def test_ภาษาไทยคืนข้อความเดิมแล้วเติมตัวแปร(tables):
    assert i18n.current() == "th"
    assert i18n.tr("ได้รับ {gold} ทอง", gold=5) == "ได้รับ 5 ทอง"


def test_แปลตามภาษาปัจจุบัน_ออกจาก_with_แล้วกลับภาษาเดิม(tables):
    with i18n.use_lang("en-US"):
        assert i18n.current() == "en"
        assert i18n.tr("ได้รับ {gold} ทอง", gold=5) == "Got 5 gold"
    assert i18n.current() == "th"


def test_ไม่มีคำแปลหรือคำแปลว่างคืนไทย(tables):
    with i18n.use_lang("ja"):                       # ไม่มี ja.json เลย
        assert i18n.tr("ว่าง") == "ว่าง"
    with i18n.use_lang("en"):
        assert i18n.tr("ว่าง") == "ว่าง"            # มีคีย์แต่ยังไม่ได้แปล
        assert i18n.tr("ไม่มีในไฟล์") == "ไม่มีในไฟล์"


def test_ไม่ส่งตัวแปร_ไม่แตะวงเล็บปีกกา(tables):
    assert i18n.tr("วงเล็บ {ไม่ใช่ตัวแปร}") == "วงเล็บ {ไม่ใช่ตัวแปร}"


def test_โฟลเดอร์คำแปลไม่มี_เช่น_exe_ลูกค้า_ไม่พัง(monkeypatch, tmp_path):
    monkeypatch.setattr(i18n, "LOCALES_DIR", tmp_path / "ไม่มีโฟลเดอร์นี้")
    monkeypatch.setattr(i18n, "_tables", {})
    with i18n.use_lang("en"):
        assert i18n.tr("ทอง") == "ทอง"


def test_ไฟล์คำแปลพัง_ไม่พัง(monkeypatch, tmp_path):
    (tmp_path / "en.json").write_text("{ไม่ใช่ json", encoding="utf-8")
    monkeypatch.setattr(i18n, "LOCALES_DIR", tmp_path)
    monkeypatch.setattr(i18n, "_tables", {})
    with i18n.use_lang("en"):
        assert i18n.tr("ทอง") == "ทอง"


def test_แต่ละ_task_มีภาษาของตัวเอง(tables):
    """คำสั่งบอท 2 คนรันพร้อมกัน ภาษาต้องไม่ปนกัน"""
    async def job(code):
        i18n.set_lang(code)
        await asyncio.sleep(0)
        return i18n.tr("ได้รับ {gold} ทอง", gold=1)

    async def main():
        return await asyncio.gather(job("en"), job("th"))

    assert asyncio.run(main()) == ["Got 1 gold", "ได้รับ 1 ทอง"]
    assert i18n.current() == "th"


def test_ไฟล์คำแปลจริงอยู่ที่เดียวกับที่เว็บเสิร์ฟ():
    assert i18n.LOCALES_DIR == pathlib.Path("license_server/web_static/locales").resolve()
    for lang in ("en", "zh", "ja"):
        table = json.loads((i18n.LOCALES_DIR / f"{lang}.json").read_text(encoding="utf-8"))
        assert isinstance(table, dict)
    assert not (i18n.LOCALES_DIR / "th.json").exists(), "ภาษาไทยคือคีย์เอง ไม่ต้องมีไฟล์"


def test_exe_ทั้งสองแบบพาไฟล์คำแปลไปด้วย():
    """exe ลูกค้าไม่มี license_server/ — ไม่ใส่ไว้ บอทจะตอบไทยล้วนในก้อน 3"""
    assert "license_server/web_static/locales" in pathlib.Path("build.spec").read_text(encoding="utf-8")
    assert "license_server/web_static/locales" in pathlib.Path("build_nuitka.py").read_text(encoding="utf-8")
