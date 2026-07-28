"""ด่านสุดท้ายก่อนรีสตาร์ทบอท: ทุกไฟล์ต้องคอมไพล์ผ่านและ import ได้

เคยพลาดมาหลายรอบ — syntax error ในไฟล์ที่ไม่มีเทสแตะ (เช่น codex, cogs บางตัว)
รอดเทสทั้งชุดมาได้ แล้วไปตายตอนบอทสตาร์ทจริง ทำให้ผู้เล่นเข้าไม่ได้
"""
import importlib
import pathlib
import py_compile

import pytest

MODULES = sorted(str(p.with_suffix("")).replace("\\", ".").replace("/", ".")
                 for p in pathlib.Path("bot").rglob("*.py") if p.name != "__init__.py")
SOURCES = sorted(p for d in ("bot", "panel") for p in pathlib.Path(d).rglob("*.py"))


def test_found_modules():
    assert len(MODULES) > 30, "หาไฟล์ไม่เจอ — path เพี้ยน เทสนี้จะกลายเป็นเทสหลอก"


@pytest.mark.parametrize("path", SOURCES, ids=str)
def test_compiles(path):
    """คอมไพล์ล้วน ไม่รันโค้ด — จับ syntax error ทุกไฟล์รวมฝั่ง panel"""
    py_compile.compile(str(path), doraise=True, cfile=None)


@pytest.mark.parametrize("module", MODULES)
def test_imports(module):
    """import จริง — จับพวก import วน / ชื่อหาย ที่คอมไพล์ผ่านแต่บอทสตาร์ทไม่ขึ้น"""
    importlib.import_module(module)
