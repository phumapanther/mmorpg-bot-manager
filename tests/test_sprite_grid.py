"""สไปรต์ตัวละครบนเว็บ — ตารางพิกเซลต้องตรงเป๊ะ

เขียนด้วยมือทีละแถว นับพลาดช่องเดียว = ตัวละครบิดทั้งตัวและไม่มีอะไรฟ้อง
เทสนี้อ่าน sprite.js ตรงๆ เพื่อกันเคสนั้น
"""
import pathlib
import re

import pytest

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
    js = pathlib.Path("license_server/web_static/play.js").read_text(encoding="utf-8")
    # ทุกแผงที่ปุ่มชี้ไป ต้องมีอยู่จริง ไม่งั้นกดแล้วจอว่าง
    import re as _re
    for target in set(_re.findall(r'data-go="(\w+)"', html)):
        assert f'id="v-{target}"' in html, f'ปุ่ม data-go="{target}" ชี้ไปแผงที่ไม่มีอยู่'
    assert 'drawCharacter' in js


def test_every_money_action_goes_through_confirm():
    """ทุกธุรกรรมเงิน/ใช้ไอเทมต้องเรียก confirmAction ก่อน — กันเผลอต่อปุ่มตรงเข้า API"""
    js = pathlib.Path("license_server/web_static/play.js").read_text(encoding="utf-8")
    for call in ('"/api/web/bank"', '"/api/web/goldbar"',
                 '"/api/web/item/use"', '"/api/web/item/drop"'):
        idx = js.index(call)
        before = js[max(0, idx - 1400):idx]
        assert "confirmAction" in before, f"{call} ถูกเรียกโดยไม่ผ่านหน้ายืนยัน"
    html = pathlib.Path("license_server/web_static/play.html").read_text(encoding="utf-8")
    assert 'id="confirmWrap"' in html and 'id="cfYes"' in html and 'id="toast"' in html
