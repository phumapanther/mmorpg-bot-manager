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


def _fs():
    return CSS[CSS.index("/* ── ⛶ โหมดเต็มจอ + ▴ ย่อแถบข้อมูล ── */"):]


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
    fs = _fs()
    assert "body.fullscreen .pbar" in fs and "position: sticky" in fs, \
        "แถบตัวละคร (ที่มีปุ่มออก) ต้องหนึบอยู่บนสุด"


def test_it_hides_the_page_chrome():
    fs = _fs()
    for part in ("body.fullscreen .nav-wrap", "body.fullscreen footer"):
        assert part in fs, f"เต็มจอแล้วยังโชว์ {part}"
    assert "position: fixed; inset: 0" in fs, "ตัวเกมไม่ได้กินเต็มจอ"


def test_it_stays_under_the_confirm_dialog():
    """ป็อปอัพยืนยัน (z-index 200) ต้องอยู่เหนือเสมอ ไม่งั้นกดยืนยันไม่ได้ตอนเต็มจอ"""
    fs = _fs()
    z = int(re.search(r"body\.fullscreen \.play-shell \{[^}]*z-index: (\d+)", fs, re.S).group(1))
    dialog = int(re.search(r"#confirmWrap \{[^}]*z-index:(\d+)", CSS, re.S).group(1))
    assert z < dialog, f"ตัวเกม (z={z}) บังป็อปอัพยืนยัน (z={dialog})"


def test_the_canvas_is_never_told_to_size_itself():
    """canvas มีขนาดจริง 320x132 — สั่ง width:auto เมื่อไหร่มันหดกลับไปเท่านั้นทันที
    (เคยพลาดมาแล้ว: เต็มจอบนคอม 1920px แล้วฉากเหลือ 320px จิ๋วกลางจอ)"""
    rules = re.sub(r"/\*.*?\*/", "", _fs(), flags=re.S)   # ตัดคอมเมนต์ออก ดูแต่กฎจริง
    assert "width: auto" not in rules and "width:auto" not in rules, \
        "สั่ง width:auto ให้ canvas = ฉากหดเหลือ 320px"
    assert "body.fullscreen .stage-wrap { max-width:" in rules, \
        "ต้องคุมความสูงด้วยการจำกัดความกว้างของกรอบแทน"


def test_the_scene_does_not_push_the_buttons_off_screen():
    """จอคอมกว้าง ๆ ฉากจะสูงมากจนปุ่มแอคชั่นตกจอ — ต้องคุมความสูงไว้"""
    fs = _fs()
    caps = [int(v) for v in re.findall(r"calc\((\d+)vh \* 320 / 132\)", fs)]
    assert caps, "ไม่ได้คุมความสูงฉากตอนเต็มจอ"
    assert all(c <= 60 for c in caps), f"ฉากสูงเกินไป เหลือที่ให้ปุ่มน้อย: {caps}vh"


def test_the_scene_actually_gets_bigger_not_smaller():
    """คำนวณจริง: เต็มจอบนคอม 1920x1080 ฉากต้องกว้างกว่าขนาดเดิม 320px หลายเท่า"""
    fs = _fs()
    cap = int(re.search(r"calc\((\d+)vh \* 320 / 132\)", fs).group(1))
    width = min(1920 - 24, cap / 100 * 1080 * 320 / 132)
    assert width > 320 * 3, f"เต็มจอแล้วฉากกว้างแค่ {width:.0f}px — ไม่คุ้มที่จะกดเต็มจอ"


def test_the_player_card_shrinks_too():
    """ฉากใหญ่ขึ้นแต่การ์ดข้อมูลยังเทอะทะ = แย่งที่กันเอง (ปัญหาที่ผู้เล่นเจอ)"""
    fs = _fs()
    assert "body.fullscreen .adv-hud" in fs, "การ์ดข้อมูลนักผจญภัยไม่ได้บีบให้เตี้ยลง"
    assert "body.fullscreen .adv-hud { max-width:" in fs, "การ์ดควรกว้างเท่าฉาก ไม่ใช่เต็มจอ"
    assert "body.fullscreen .g-head { display: none; }" in fs,         "หัวข้อ/คำอธิบายแผงยังกินที่ตอนเต็มจอ"


# ── ▴ ย่อแถบข้อมูลด้านบน ──

def test_the_top_bar_can_be_folded_away():
    """บนมือถือแถบข้อมูลตัดเป็น 3 แถวจนบังจอเกม ต้องย่อเก็บได้"""
    assert 'id="playMin"' in HTML, "ไม่มีปุ่มย่อแถบข้อมูล"
    b = JS[JS.index("const minBtn = document.getElementById('playMin');"):
           JS.index("// ⛶ ขยายเต็มจอ")]
    assert "classList.toggle('bar-min')" in b
    assert "localStorage" in b, "ย่อแล้วเปิดหน้าใหม่ต้องจำได้ ไม่ใช่กางกลับทุกครั้ง"

    fold = CSS[CSS.index("/* ▴ ย่อแถบข้อมูลด้านบน"):]
    for gone in (".pbar .avatar", ".pbar .idbox", ".pbar .money .pill"):
        assert gone in fold, f"ย่อแล้ว {gone} ยังอยู่"


def test_folding_never_hides_the_buttons():
    """ย่อแล้วปุ่มกางกลับต้องยังอยู่ ไม่งั้นกางคืนไม่ได้"""
    fold = CSS[CSS.index("/* ▴ ย่อแถบข้อมูลด้านบน"):CSS.index("@media (max-width: 640px)", CSS.index("/* ▴ ย่อ"))]
    assert "body.bar-min .pbar .money {" in fold, "ต้องเหลือแถวปุ่มไว้"
    assert "body.bar-min .pbar .money { display: none" not in fold


def test_nothing_important_is_lost_when_folded():
    """เลือด/เงินที่ซ่อนไปตอนย่อ ต้องยังดูได้จากการ์ดใต้ฉาก"""
    assert 'id="advHp"' in HTML and 'id="advCash"' in HTML


def test_the_stale_note_is_gone():
    """ป้ายประกาศ 'ทุกเหตุการณ์เล่นบนเว็บได้ครบแล้ว' กินที่เปล่า ๆ — ผู้เล่นสั่งให้ลบ"""
    assert "ทุกเหตุการณ์เล่นบนเว็บได้ครบแล้ว" not in HTML


def test_it_respects_the_phone_notch():
    fs = _fs()
    assert "env(safe-area-inset-bottom)" in fs, "ปุ่มล่างสุดจะโดนแถบโฮมของมือถือบัง"
