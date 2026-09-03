"""สไปรต์ตัวละครบนเว็บ — ตารางพิกเซลต้องตรงเป๊ะ

เขียนด้วยมือทีละแถว นับพลาดช่องเดียว = ตัวละครบิดทั้งตัวและไม่มีอะไรฟ้อง
เทสนี้อ่าน sprite.js ตรงๆ เพื่อกันเคสนั้น
"""
import pathlib
import re

import pytest
from tests import conftest

SRC = pathlib.Path("license_server/web_static/sprite.js").read_text(encoding="utf-8")
WIDTH = 16
ROWS = 22


def _grids(block_name):
    """ดึงตารางพิกเซลของบล็อกที่ระบุ → {ชื่อท่า: [แถว...]}"""
    m = re.search(block_name + r"\s*=\s*\{(.*?)\n\};", SRC, re.S)
    assert m, f"หาบล็อก {block_name} ใน sprite.js ไม่เจอ"
    out = {}
    for pose, body in re.findall(r"(\w+):\s*\[(.*?)\]", m.group(1), re.S):
        rows = re.findall(r"'([^']*)'", body)
        if rows:
            out[pose] = rows
    return out


def test_sprite_js_exists():
    assert "function drawCharacter" in SRC


@pytest.mark.parametrize("pose", ["idle", "run1", "run2", "atk"])
def test_pose_grid_is_rectangular(pose):
    grids = _grids("const POSES")
    assert pose in grids, f"ไม่มีท่า {pose}"
    rows = grids[pose]
    assert len(rows) == ROWS, f"ท่า {pose} มี {len(rows)} แถว (ต้องเป็น {ROWS})"
    bad = [(i, len(r)) for i, r in enumerate(rows) if len(r) != WIDTH]
    assert not bad, f"ท่า {pose} แถวเหล่านี้กว้างไม่ถูก (ต้อง {WIDTH}): {bad}"


def test_overlay_grids_match_width():
    """หมวกคลาส/หมวกเกราะวาดทับสไปรต์ ต้องกว้างเท่ากันไม่งั้นเหลื่อม"""
    for block in ("const HATS", "const HELMS"):
        for name, rows in _grids(block).items():
            bad = [(i, len(r)) for i, r in enumerate(rows) if len(r) != WIDTH]
            assert not bad, f"{block} {name} แถวกว้างไม่ถูก: {bad}"


def test_every_symbol_has_a_colour():
    """ทุกตัวอักษรที่ใช้ในตารางต้องมีสีในพาเลตต์ ไม่งั้นวาดออกมาเป็นรูโหว่"""
    palette = re.search(r"return \{(.*?)\n  \};", SRC, re.S).group(1)
    palette = re.sub(r"//.*", "", palette)          # ตัดคอมเมนต์ กันคำในนั้นถูกนับเป็นคีย์
    known = set(re.findall(r"\b(\w):", palette))    # หลายคีย์ต่อบรรทัดก็ต้องเจอครบ
    used = set()
    for block in ("const POSES", "const HATS", "const HELMS"):
        for rows in _grids(block).values():
            for r in rows:
                used |= set(r)
    unknown = used - known - {"."}
    assert not unknown, f"ตัวอักษรที่ไม่มีสีในพาเลตต์: {sorted(unknown)}"


def test_play_page_wires_sprite_engine():
    """หน้า /play ต้องโหลด sprite.js และมีแผงโปรไฟล์/กระเป๋าครบ"""
    html = pathlib.Path("license_server/web_static/play.html").read_text(encoding="utf-8")
    assert '/sprite.js' in html, "play.html ไม่ได้โหลด sprite.js"
    for pid in ('v-profile', 'v-bag', 'v-roleshop', 'v-gacha', 'v-rewards'):
        assert f'id="{pid}"' in html, f"ไม่มีแผง {pid}"
    js = conftest.play_js_source()
    # ทุกแผงที่ปุ่มชี้ไป ต้องมีอยู่จริง ไม่งั้นกดแล้วจอว่าง
    import re as _re
    for target in set(_re.findall(r'data-go="(\w+)"', html)):
        assert f'id="v-{target}"' in html, f'ปุ่ม data-go="{target}" ชี้ไปแผงที่ไม่มีอยู่'
    assert 'drawCharacter' in js


def test_every_money_action_goes_through_confirm():
    """ทุกธุรกรรมเงิน/ใช้ไอเทมต้องเรียก confirmAction ก่อน — กันเผลอต่อปุ่มตรงเข้า API"""
    js = conftest.play_js_source()
    for call in ('"/api/web/bank"', '"/api/web/goldbar"',
                 '"/api/web/item/use"', '"/api/web/item/drop"', '"/api/web/shop"'):
        idx = js.index(call)
        before = js[max(0, idx - 1400):idx]
        assert "confirmAction" in before, f"{call} ถูกเรียกโดยไม่ผ่านหน้ายืนยัน"
    html = pathlib.Path("license_server/web_static/play.html").read_text(encoding="utf-8")
    assert 'id="confirmWrap"' in html and 'id="cfBtns"' in html and 'id="toast"' in html


def test_bag_items_open_a_menu_instead_of_inline_buttons():
    """ของในกระเป๋าต้องกดที่ใบแล้วเด้งเมนู ไม่ใช่แปะปุ่มใช้/ทิ้งไว้ตลอด (ปุ่มล้นการ์ด)"""
    js = conftest.play_js_source()
    assert "openItemMenu" in js
    assert "use-btn" not in js and "drop-btn" not in js, "ยังมีปุ่มติดการ์ดค้างอยู่"
    css = pathlib.Path("license_server/web_static/play.css").read_text(encoding="utf-8")
    assert ".use-btn" not in css and ".drop-btn" not in css, "CSS ปุ่มเก่ายังไม่ถูกลบ"


def test_overlay_ui_does_not_depend_on_scoped_tokens():
    """ป็อปอัพ/แถบแจ้งผลอยู่นอก .play-shell — ถ้าใช้ตัวแปรที่ประกาศในนั้นจะกลายเป็นโปร่งใส

    เคสจริง: กล่องยืนยันพื้นหลังใสจนอ่านไม่ออก เพราะ --g-panel ประกาศไว้ที่ .play-shell
    """
    css = re.sub(r"/\*.*?\*/", "", pathlib.Path("license_server/web_static/play.css")
                 .read_text(encoding="utf-8"), flags=re.S)      # ตัดคอมเมนต์ก่อน กัน regex หลง
    root = re.search(r":root\s*\{(.*?)\}", css, re.S)
    assert root and "--g-panel:" in root.group(1), "ตัวแปรสีต้องประกาศในบล็อก :root"

    # กล่องลอยต้องกำหนดพื้นหลังเป็นสีตรง ไม่พึ่งตัวแปร
    for sel in (r"\.confirm-box", r"#toast"):
        block = re.search(sel + r"\s*\{(.*?)\}", css, re.S)
        assert block, f"หา {sel} ไม่เจอ"
        bg = re.search(r"background:\s*([^;]+);", block.group(1))
        assert bg and "var(" not in bg.group(1), f"{sel} ใช้ตัวแปรกับพื้นหลัง เสี่ยงกลายเป็นใส"


# ── 🗡️ ตารางพิกเซลอาวุธ (2026-08-15) ──
# เดิมอาวุธวาดด้วยสี่เหลี่ยมทีละชิ้น ทำรายละเอียดไม่ได้ ตอนนี้เป็นตารางเหมือนตัวละคร
WEAPON_WIDTH = 11


def test_every_weapon_grid_is_rectangular():
    """นับพลาดช่องเดียว = อาวุธบิดทั้งอัน และไม่มีอะไรฟ้อง"""
    grids = _grids("const WEAPON_ART")
    assert grids, "ไม่เจอตารางอาวุธ"
    for name, rows in grids.items():
        assert len(rows) == ROWS, f"อาวุธ {name} มี {len(rows)} แถว (ต้อง {ROWS})"
        for i, row in enumerate(rows):
            assert len(row) == WEAPON_WIDTH, \
                f"อาวุธ {name} แถว {i} ยาว {len(row)} (ต้อง {WEAPON_WIDTH})"


def test_every_class_has_a_weapon_shape():
    """คลาสไหนไม่มีทรง = ถืออาวุธผิดแบบ"""
    shapes = set(_grids("const WEAPON_ART"))
    used = set(re.findall(r"^\s+\w+:\s*'(\w+)',", SRC[SRC.index("const CLASS_WEAPON"):], re.M))
    assert used, "อ่านตาราง CLASS_WEAPON ไม่ออก"
    assert used <= shapes, f"คลาสชี้ไปทรงที่ไม่มี: {sorted(used - shapes)}"
    assert "sword" in shapes, "ต้องมีดาบเป็นทรงสำรองเสมอ"


def test_the_blade_stays_in_its_lane():
    """ใบมีดต้องอยู่ช่อง 3-7 ทุกทรง — ไม่งั้นด้ามไม่ตรงมือตอนวาดทับตัวละคร"""
    for name, rows in _grids("const WEAPON_ART").items():
        for i, row in enumerate(rows):
            for c, ch in enumerate(row):
                if ch in "123":
                    assert 3 <= c <= 7, f"อาวุธ {name} แถว {i}: ใบมีดหลุดไปช่อง {c}"


def test_weapon_grids_only_use_known_symbols():
    ok = set(".o123xGhH")
    for name, rows in _grids("const WEAPON_ART").items():
        bad = {ch for row in rows for ch in row} - ok
        assert not bad, f"อาวุธ {name} ใช้สัญลักษณ์ที่ไม่มีในตารางสี: {sorted(bad)}"


def test_the_weapon_palette_covers_every_symbol():
    """สัญลักษณ์ที่ใช้ในตารางต้องมีสีรองรับครบ ไม่งั้นพิกเซลนั้นหายไปเงียบ ๆ"""
    pal = SRC[SRC.index("function weaponPalette"):]
    pal = pal[:pal.index("\n}")]
    used = {ch for rows in _grids("const WEAPON_ART").values()
            for row in rows for ch in row} - {"."}
    for ch in used:
        assert re.search(rf"[\s{{]{ch}:", pal), f"ตารางสีอาวุธไม่มีสีของ '{ch}'"


def test_weapons_are_drawn_at_the_same_pixel_size_as_the_character():
    """ย่อ/ขยายอาวุธคนละสเกลกับตัวละคร แล้วพิกเซลจะเบลอไม่เข้าพวก"""
    fn = SRC[SRC.index("function drawWeapon("):]
    fn = fn[:fn.index("\n}")]
    assert "const gs = s;" in fn, "อาวุธถูกย่อ/ขยายคนละสเกลกับตัวละคร"


def test_fashion_weapons_reuse_the_same_shapes():
    """แฟชั่นเปลี่ยนแค่สี ทรงยังมาจากอาชีพเหมือนเดิม (ผู้เล่นสั่งไว้)"""
    fn = SRC[SRC.index("function drawWeapon("):]
    fn = fn[:fn.index("\n}")]
    assert "CLASS_WEAPON[cls]" in fn, "ทรงอาวุธไม่ได้มาจากอาชีพแล้ว"
