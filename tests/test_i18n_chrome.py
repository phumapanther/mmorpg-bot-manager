"""🌐 แถบเมนู/ท้ายเว็บ (web.js) — ทุกหน้าใช้ร่วมกัน ต้องแปลครบ + มีปุ่มเลือกภาษา"""
import pathlib

from scripts import i18n_extract as X

WEB = pathlib.Path("license_server/web_static")
JS = (WEB / "web.js").read_text(encoding="utf-8")
CSS = (WEB / "style.css").read_text(encoding="utf-8")


def test_web_js_ไม่มีข้อความไทยที่ยังไม่ห่อ_tr():
    assert X.bare_thai_js(JS, "web.js") == []


def test_แถบเมนูมีปุ่มเลือกภาษาครบทุกภาษา():
    block = JS[JS.index("async function renderChrome"):JS.index("async function fillDiscordInvite")]
    assert 'class="lang-pick"' in block
    assert "I18N_LANGS.map" in block and "I18N_NAMES[" in block, "ตัวเลือกต้องสร้างจากรายการภาษากลาง"
    assert "=== I18N_LANG" in block, "ภาษาที่ใช้อยู่ต้องถูกเลือกไว้"
    assert "setLang(" in block


def test_ปุ่มเลือกภาษาไม่ยืดเต็มความกว้างแบบ_select_ในฟอร์ม():
    assert ".nav select.lang-pick" in CSS


def test_จีนกับญี่ปุ่นมีฟอนต์ของตัวเอง():
    """Prompt ไม่มีอักษร CJK — คันจิกับอักษรจีนหน้าตาต่างกัน ต้องแยกฟอนต์"""
    assert "html:lang(zh)" in CSS and "html:lang(ja)" in CSS


def test_มีอภิธานศัพท์ให้คนแปลใช้ร่วมกัน():
    g = pathlib.Path("docs/i18n-glossary.md").read_text(encoding="utf-8")
    for term in ("ทอง", "ทวีป", "ธาตุ", "เติมเกม"):
        assert f"| {term} |" in g
