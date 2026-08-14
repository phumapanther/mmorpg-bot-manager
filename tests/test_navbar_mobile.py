"""📱 แถบเมนูบนสุด — จอมือถือต้องพับเก็บได้ ไม่ให้กินครึ่งจอ

ผู้เล่นเจอว่าเมนู (หน้าแรก/ข่าวสาร/ข้อมูลเกม/เล่นเกม/เติมเกม/โปรไฟล์) กางเต็มจอ
บังหน้าเกมจนเล่นไม่ถนัด
"""
import pathlib
import re

WEB = pathlib.Path("license_server/web_static")
JS = (WEB / "web.js").read_text(encoding="utf-8")
CSS = (WEB / "style.css").read_text(encoding="utf-8")


def _mobile_block():
    """เนื้อใน @media (max-width: 640px)"""
    i = CSS.index("@media (max-width: 640px)")
    depth, j = 0, CSS.index("{", i)
    for k in range(j, len(CSS)):
        if CSS[k] == "{":
            depth += 1
        elif CSS[k] == "}":
            depth -= 1
            if depth == 0:
                return CSS[j:k]
    raise AssertionError("อ่านบล็อกมือถือไม่จบ")


def test_the_menu_can_fold_away():
    """ใช้ <details> ของเบราว์เซอร์ — เปิดปิดเองได้ กดคีย์บอร์ดได้ ไม่ต้องเขียน JS เอง"""
    assert '<details class="nav">' in JS, "แถบเมนูยังพับไม่ได้"
    assert '<summary class="navbar-toggle">' in JS, "ไม่มีหัวข้อให้กดพับ/กาง"
    assert 'class="burger"' in JS, "ไม่มีปุ่มขีดสามขีดให้กด"


def test_it_starts_folded_on_phones_and_open_on_desktop():
    block = JS[JS.index('<details class="nav">'):JS.index("async function fillDiscordInvite")]
    assert "matchMedia" in block and "max-width: 640px" in block
    assert "bar.open = wide()" in block, "ต้องกางบนจอกว้าง และพับบนจอแคบตั้งแต่แรก"


def test_resizing_never_slams_an_open_menu_shut():
    """บนมือถือ คีย์บอร์ดเด้งขึ้นก็นับเป็น resize — ห้ามหุบเมนูที่ผู้ใช้เพิ่งกางกลางคัน"""
    block = JS[JS.index('const bar = nav.querySelector'):JS.index("async function fillDiscordInvite")]
    hit = re.search(r'addEventListener\("resize",\s*\(\)\s*=>\s*\{([^}]*)\}', block)
    assert hit, "ไม่ได้ดักการเปลี่ยนขนาดจอ"
    assert "if (wide()) bar.open = true" in hit.group(1), "resize แล้วต้องสั่งได้แค่ 'กาง'"
    assert "= false" not in hit.group(1), "resize แล้วไปสั่งหุบเมนู ผู้ใช้จะงง"


def test_the_toggle_is_hidden_on_desktop():
    """จอกว้างไม่ต้องมีปุ่มพับให้เกะกะ — เมนูกางอยู่แล้ว"""
    head = CSS[:CSS.index("@media")]
    assert ".nav .burger { display: none; }" in head, "จอกว้างยังโชว์ปุ่มขีดสามขีด"
    assert ".nav > summary { display: contents; }" in head, "โลโก้ต้องอยู่แถวเดียวกับเมนูเหมือนเดิม"


def test_the_phone_menu_is_a_real_column_with_a_tappable_button():
    m = _mobile_block()
    assert ".nav .burger" in m and "display: grid" in m, "จอแคบต้องโชว์ปุ่มขีดสามขีด"
    assert "flex-direction: column" in m, "เมนูบนมือถือควรเรียงลงเป็นแถว ไม่ใช่ตัดบรรทัดมั่ว"
    for size in re.findall(r"\.nav a\.nav-link \{ padding: (\d+)px", m):
        assert int(size) >= 10, "ปุ่มเล็กเกินไปสำหรับนิ้ว"


def test_it_says_it_is_open_by_turning_into_an_x():
    m = _mobile_block()
    assert ".nav[open] .burger" in m, "กางแล้วไม่มีอะไรบอกว่ากดอีกทีเพื่อปิด"
    assert "rotate(45deg)" in m and "rotate(-45deg)" in m, "ขีดสามขีดไม่ได้กลายเป็นกากบาท"


def test_no_extra_javascript_was_written_for_the_toggle():
    """เปิด/ปิดเป็นงานของ <details> อยู่แล้ว — ห้ามเขียนตัวสลับเอง"""
    block = JS[JS.index('<details class="nav">'):JS.index("async function fillDiscordInvite")]
    for hand_rolled in ("classList.toggle", 'addEventListener("click"', "onclick"):
        assert hand_rolled not in block, f"เขียนตัวสลับเองทั้งที่เบราว์เซอร์ทำให้แล้ว: {hand_rolled}"
