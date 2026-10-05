"""🌐 ไฟล์คำแปล — ทุกคีย์ในโค้ดต้องแปลครบ 3 ภาษา และคำแปลต้องไม่ทำของพัง

พังแบบเงียบที่กันไว้:
- แก้ข้อความไทยในโค้ดแล้วลืมแปลใหม่ → ต่างชาติเห็นไทยโผล่
- คำแปลทำ {ตัวแปร} หาย → KeyError ตอนรัน (ไพทอน) / ค้าง {gold} บนจอ (JS)
- คำแปลทำแท็กหรือ id หาย → JS เขียนตัวเลขลง #pCash ไม่เจอ
"""
import re

import pytest

from scripts import i18n_extract as X

KEYS, MISUSE = X.collect()
TABLES = {lang: X.load(lang) for lang in X.LANGS}
PH = re.compile(r"\{([A-Za-z_][A-Za-z0-9_]*)\}")
TAGS = re.compile(r"</?[a-zA-Z][^>]*>")


def test_tr_รับข้อความตรง_ๆ_เท่านั้น():
    assert MISUSE == []


@pytest.mark.parametrize("lang", X.LANGS)
def test_ไฟล์คำแปลเป็น_ข้อความ_ต่อ_ข้อความ(lang):
    assert all(isinstance(k, str) and isinstance(v, str) for k, v in TABLES[lang].items())


@pytest.mark.parametrize("lang", X.LANGS)
def test_ทุกคีย์ในโค้ดมีคำแปล(lang):
    missing = sorted(k for k in KEYS if not TABLES[lang].get(k))
    assert not missing, (f"{lang}.json ยังไม่แปล {len(missing)} คีย์ — "
                         f"รัน python scripts/i18n_extract.py --write แล้วเติมคำแปล: {missing[:10]}")


@pytest.mark.parametrize("lang", X.LANGS)
def test_ตัวแปรและแท็กในคำแปลตรงกับต้นฉบับ(lang):
    bad = []
    for k, v in TABLES[lang].items():
        if not v:
            continue
        if sorted(PH.findall(k)) != sorted(PH.findall(v)):
            bad.append(f"ตัวแปรไม่ตรง: {k[:50]!r} → {v[:50]!r}")
        if sorted(TAGS.findall(k)) != sorted(TAGS.findall(v)):
            bad.append(f"แท็ก/แอตทริบิวต์ไม่ตรง (ต้องก๊อปแท็กไปทั้งแท็ก): {k[:50]!r} → {v[:50]!r}")
    assert not bad, "\n".join(bad)
