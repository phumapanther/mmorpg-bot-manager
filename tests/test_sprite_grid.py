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
