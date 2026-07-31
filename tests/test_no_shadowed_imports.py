"""กัน UnboundLocalError: import ซ้อนในฟังก์ชันที่บังชื่อซึ่ง import ไว้ระดับไฟล์แล้ว

เคสจริง (2026-07-30): game_views.py มี `import json` ระดับไฟล์อยู่แล้ว แต่ข้างใน
process_turn มี `import json` ซ้ำอีก — Python ถือว่า json เป็น "ตัวแปรท้องถิ่น"
ตลอดทั้งฟังก์ชัน โค้ดบรรทัดก่อนหน้าที่เรียก json.dumps จึงพังด้วย
"cannot access local variable 'json' where it is not associated with a value"
ผู้เล่นเจอตอนใช้กับดักแล้วชนะไฟต์ → ไฟต์ล่มกลางคัน
"""
import ast
import pathlib

import pytest

FILES = sorted(pathlib.Path("bot").rglob("*.py")) + sorted(pathlib.Path("panel").rglob("*.py"))


def _module_level_names(tree):
    names = set()
    for node in tree.body:                       # เฉพาะระดับบนสุดของไฟล์
        if isinstance(node, ast.Import):
            names |= {(a.asname or a.name.split(".")[0]) for a in node.names}
        elif isinstance(node, ast.ImportFrom):
            names |= {(a.asname or a.name) for a in node.names}
    return names


def _nested_imports(tree):
    """(ชื่อที่ถูก bind, บรรทัด, ชื่อฟังก์ชัน) ของ import ที่อยู่ในฟังก์ชัน"""
    out = []
    for func in ast.walk(tree):
        if not isinstance(func, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        for node in ast.walk(func):
            if isinstance(node, ast.Import):
                for a in node.names:
                    out.append(((a.asname or a.name.split(".")[0]), node.lineno, func.name))
            elif isinstance(node, ast.ImportFrom):
                for a in node.names:
                    out.append(((a.asname or a.name), node.lineno, func.name))
    return out


@pytest.mark.parametrize("path", FILES, ids=str)
def test_no_nested_import_shadows_a_module_level_one(path):
    tree = ast.parse(path.read_text(encoding="utf-8"))
    top = _module_level_names(tree)
    clashes = [(n, ln, fn) for n, ln, fn in _nested_imports(tree) if n in top]
    assert not clashes, "\n".join(
        f"{path}:{ln} ใน {fn}() — `import {n}` ซ้ำกับที่ import ไว้บนสุดของไฟล์แล้ว "
        f"ทำให้ {n} กลายเป็นตัวแปรท้องถิ่นทั้งฟังก์ชัน (ลบบรรทัดนี้ทิ้ง)"
        for n, ln, fn in clashes)
