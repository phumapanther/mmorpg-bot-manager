"""⛶ โหมดขยายเต็มจอ — ใช้ได้ทั้งมือถือและคอม

หัวใจคือคลาส CSS ไม่ใช่ Fullscreen API: iPhone ไม่รองรับ requestFullscreen
กับ element ทั่วไป ถ้าพึ่ง API อย่างเดียว ผู้เล่นบน iPhone จะกดแล้วไม่เกิดอะไรขึ้น
"""
import pathlib
import re

WEB = pathlib.Path("license_server/web_static")
JS = (WEB / "play.js").read_text(encoding="utf-8")
CSS = (WEB / "play.css").read_text(encoding="utf-8")
HTML = (WEB / "play.html").read_text(encoding="utf-8")


def _block():
    return JS[JS.index("const fullBtn = document.getElementById('playFull');"):
              JS.index("// 🔊 ปุ่มเปิด/ปิดเสียง")]


def test_there_is_a_button_for_it():
    assert 'id="playFull"' in HTML, "ไม่มีปุ่มขยายเต็มจอ"
    assert HTML.index('id="playFull"') < HTML.index('id="playLogout"'), \
        "ปุ่มเต็มจอควรอยู่แถวเดียวกับปุ่มเสียง/ออกจากระบบ"


def test_it_does_not_depend_on_the_fullscreen_api():
    """iPhone ไม่มี requestFullscreen สำหรับ element ทั่วไป — คลาส CSS ต้องทำงานเองได้"""
    b = _block()
    assert "classList.toggle('fullscreen', want)" in b, "ไม่ได้ใช้คลาส CSS เป็นตัวหลัก"
    assert "requestFullscreen?.()" in b, "ควรลองขอเต็มจอจริงด้วย (เดสก์ท็อป/แอนดรอยด์)"
    assert "catch" in b, "เบราว์เซอร์ปฏิเสธแล้วต้องไม่พังทั้งหน้า"

    # คลาสต้องถูกสลับ "ก่อน" เรียก API เสมอ — API พังก็ยังเต็มจอ
    assert b.index("classList.toggle") < b.index("requestFullscreen"), \
        "ถ้าเรียก API ก่อนแล้วมันโยน error คลาสจะไม่ถูกใส่ → iPhone กดแล้วไม่เกิดอะไร"


def test_you_can_always_get_back_out():
    b = _block()
    assert "'Escape'" in b, "กด Esc ออกไม่ได้"
    assert "fullscreenchange" in b, "ออกจากเต็มจอด้วยวิธีของเบราว์เซอร์แล้วคลาสจะค้าง"
    assert "exitFullscreen" in b


def test_the_exit_button_never_scrolls_away():
    """เต็มจอแล้วเลื่อนลงไปดูปุ่ม ถ้าปุ่มออกหายไปด้านบน = ติดอยู่ในเต็มจอ"""
    fs = CSS[CSS.index("/* ── ⛶ โหมดเต็มจอ ── */"):]
    assert "body.fullscreen .pbar" in fs and "position: sticky" in fs, \
        "แถบตัวละคร (ที่มีปุ่มออก) ต้องหนึบอยู่บนสุด"


def test_it_hides_the_page_chrome():
    fs = CSS[CSS.index("/* ── ⛶ โหมดเต็มจอ ── */"):]
    for part in ("body.fullscreen .nav-wrap", "body.fullscreen footer"):
        assert part in fs, f"เต็มจอแล้วยังโชว์ {part}"
    assert "position: fixed; inset: 0" in fs, "ตัวเกมไม่ได้กินเต็มจอ"


def test_it_stays_under_the_confirm_dialog():
    """ป็อปอัพยืนยัน (z-index 200) ต้องอยู่เหนือเสมอ ไม่งั้นกดยืนยันไม่ได้ตอนเต็มจอ"""
    fs = CSS[CSS.index("/* ── ⛶ โหมดเต็มจอ ── */"):]
    z = int(re.search(r"body\.fullscreen \.play-shell \{[^}]*z-index: (\d+)", fs, re.S).group(1))
    dialog = int(re.search(r"#confirmWrap \{[^}]*z-index:(\d+)", CSS, re.S).group(1))
    assert z < dialog, f"ตัวเกม (z={z}) บังป็อปอัพยืนยัน (z={dialog})"


def test_the_scene_does_not_push_the_buttons_off_screen():
    """จอคอมกว้าง ๆ ฉากจะสูงมากจนปุ่มแอคชั่นตกจอ — ต้องคุมความสูงไว้"""
    fs = CSS[CSS.index("/* ── ⛶ โหมดเต็มจอ ── */"):]
    caps = [int(v) for v in re.findall(r"max-height: (\d+)vh", fs)]
    assert caps, "ไม่ได้คุมความสูงฉากตอนเต็มจอ"
    assert all(c <= 60 for c in caps), f"ฉากสูงเกินไป เหลือที่ให้ปุ่มน้อย: {caps}vh"
    assert min(caps) < max(caps), "จอมือถือควรคุมความสูงมากกว่าจอคอม"


def test_it_respects_the_phone_notch():
    fs = CSS[CSS.index("/* ── ⛶ โหมดเต็มจอ ── */"):]
    assert "env(safe-area-inset-bottom)" in fs, "ปุ่มล่างสุดจะโดนแถบโฮมของมือถือบัง"
