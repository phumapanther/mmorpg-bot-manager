"""🎭 ทางเข้าโหมด "ชวนเพื่อนเดินทาง" — ปุ่ม + หน้าโครง

สเปก: docs/superpowers/specs/2026-09-03-party-rpg-design.md
เฟสนี้ทำแค่ทางเข้า (ปุ่ม + หน้าโครง) ยังไม่มีตัวเกม — เปิดไว้ให้ทีมเห็นและช่วยดู

⚠️ เทสชุดนี้คุม "ทางเข้าต้องไม่หาย" ไม่ได้คุมกติกาเกม
   พอทำเฟส 2-3 แล้วค่อยเพิ่มเทสกติกาแยกไฟล์
"""
import pathlib

import pytest

from tests import conftest

WEB = pathlib.Path("license_server/web_static")
HTML = conftest.strip_i18n((WEB / "play.html").read_text(encoding="utf-8"))
CSS = (WEB / "play.css").read_text(encoding="utf-8")


def _adventure_section():
    """ตัดเฉพาะหมวด "ออกผจญภัย" — ใช้หัวข้อถัดไปเป็นขอบ ไม่ผูกกับการจัดรูปแบบ

    (เคยพลาด 09-02: เทสตัดด้วย </div></div> แล้ว IDE จัดรูปแบบใหม่ เทสแดง 12 ข้อ)
    """
    i = HTML.index("<h3>ออกผจญภัย</h3>")
    j = HTML.index("<h3>", i + 10)
    return HTML[i:j]


def test_ปุ่มอยู่ในหมวดออกผจญภัย():
    sec = _adventure_section()
    assert 'data-go="party"' in sec, "ไม่มีปุ่มชวนเพื่อนเดินทางในหมวดออกผจญภัย"
    assert "ชวนเพื่อนเดินทาง" in sec


def test_ปุ่มอยู่ถัดจากเริ่มออกเดินทาง():
    """เจ้าของเกมสั่งตำแหน่งไว้ชัด — อยู่ถัดจาก "เริ่มออกเดินทาง" """
    sec = _adventure_section()
    assert sec.index("เริ่มออกเดินทาง") < sec.index("ชวนเพื่อนเดินทาง"), \
        "ปุ่มต้องอยู่ถัดจาก 'เริ่มออกเดินทาง' ไม่ใช่ก่อนหน้า"


def test_ปุ่มเดิมยังอยู่ครบ():
    """เพิ่มปุ่มใหม่ต้องไม่ไปเบียดของเดิม"""
    sec = _adventure_section()
    for keep in ("เริ่มออกเดินทาง", "ล็อบบี้", "สรุปทุกทวีป"):
        assert keep in sec, f"ปุ่ม '{keep}' หายไปจากหมวดออกผจญภัย"


def test_มีหน้า_v_party():
    assert 'id="v-party"' in HTML, "ไม่มีหน้า v-party — กดปุ่มแล้วจะไปหน้าว่าง"


def test_มีจุดเสียบเกม():
    """#partyMount คือที่ที่ renderer จะมาเสียบ — หัวใจของ 'เปลี่ยนกราฟิกได้ง่าย'"""
    assert 'id="partyMount"' in HTML
    assert ".party-mount" in CSS, "ไม่มี CSS ของจุดเสียบ หน้าจะเพี้ยน"


@pytest.mark.parametrize("kind", ["canvas", "iframe"])
def test_จุดเสียบรองรับทั้ง_canvas_และ_iframe(kind):
    """สเปกข้อ 8: ทีมใช้เอนจินอะไรก็ได้ — inline (canvas) หรือ iframe (เอนจินหนัก)

    ⚠️ ต้องเป็น selector **ลูกหลาน** ไม่ใช่ลูกตรง (>) — เกมส่วนใหญ่ห่อจอไว้ใน
       กล่องอีกชั้น (lobby.js ห่อไว้ใน #partyCanvas) ใช้ > แล้วกฎไม่โดนเลย
       จอกางเต็ม 900px ทะลุกรอบบนมือถือ (เจอตอนเทสด้วยมือ 2026-09-04)
    """
    assert f".party-mount > {kind}" not in CSS, \
        f"ใช้ลูกตรงกับ {kind} — เกมที่ห่อจออีกชั้นจะไม่โดนกฎนี้"
    assert f".party-mount {kind}" in CSS, \
        f"CSS ยังไม่รองรับการเสียบแบบ {kind} — ทีมที่ใช้เอนจินอื่นจะจัดหน้าไม่ได้"


def test_ไม่บอกว่ายังไม่เสร็จแล้ว():
    """ทำครบ 7 เฟสแล้ว ป้าย "กำลังสร้างอยู่" ต้องหายไป

    ⚠️ ป้ายนี้อยู่ใน #partyMount ซึ่ง JS เขียนทับตอนโหลด ผู้เล่นเลยไม่ค่อยเห็น
       แต่มันแวบขึ้นมาก่อน JS ทำงาน และรายการงานในนั้นก็ล้าสมัยไปแล้ว
    """
    i = HTML.index('id="v-party"')
    section = HTML[i:HTML.index("g-panelview", i + 10)]
    for stale in ("กำลังสร้างอยู่", "ยังทำไม่เสร็จ", "party-plan"):
        assert stale not in section, f"ยังมี \"{stale}\" ค้างอยู่"


def test_ใช้ตัวแปรสีที่นิยามจริง():
    """--g-text ไม่มีนิยามในโปรเจ็ค (ของเดิมใช้ผิดอยู่ 3 จุด) ของใหม่ต้องไม่ทำตาม"""
    i = CSS.index("/* ══ 🎭 ชวนเพื่อนเดินทาง")
    block = CSS[i:]
    assert "var(--g-text)" not in block, \
        "บล็อกนี้ใช้ --g-text ที่ไม่มีนิยาม — ใช้ --g-ink แทน"
