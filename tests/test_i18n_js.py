"""🌐 i18n.js ฝั่งเบราว์เซอร์ — รันจริงใน node + ทุกหน้าต้องโหลดก่อน web.js"""
import json
import pathlib
import re
import shutil
import subprocess

import pytest

from bot import i18n
from tests.test_i18n_core import NORMALIZE_CASES

WEB = pathlib.Path("license_server/web_static")


def _node(cases):
    if not shutil.which("node"):
        pytest.skip("เครื่องนี้ไม่มี node")
    return subprocess.run(["node", "tests/i18n_boot.js", json.dumps(cases)],
                          capture_output=True, text=True, encoding="utf-8")


def test_i18n_js_ในกล่อง_vm():
    r = _node([])
    assert r.returncode == 0, r.stdout + r.stderr


def test_normLang_ตรงกับ_normalize_ฝั่งไพทอน():
    codes = [c for c, _want in NORMALIZE_CASES]
    r = _node(codes)
    assert r.returncode == 0, r.stdout + r.stderr
    line = next(ln for ln in r.stdout.splitlines() if ln.startswith("NORM "))
    assert json.loads(line[5:]) == [i18n.normalize(c) for c in codes]


@pytest.mark.parametrize("page", sorted(WEB.glob("*.html")), ids=lambda p: p.name)
def test_ทุกหน้าโหลด_i18n_js_ก่อน_web_js_ทันที(page):
    """web.js เรียก tr() ตั้งแต่โหลด — i18n.js มาทีหลังเมื่อไหร่ ทั้งหน้าพัง ReferenceError"""
    srcs = re.findall(r'<script src="([^"]+)"></script>', page.read_text(encoding="utf-8"))
    assert "/web.js" in srcs, f"{page.name} ไม่ได้โหลด web.js"
    i = srcs.index("/web.js")
    assert i > 0 and srcs[i - 1] == "/i18n.js", \
        f'{page.name}: ต้องมี <script src="/i18n.js"></script> อยู่ก่อน web.js ทันที'


def test_ไฟล์คำแปลเสิร์ฟได้และไม่ค้างแคช(tmp_path, monkeypatch):
    """แคชค้าง = แก้คำแปลแล้วผู้เล่นยังเห็นของเก่า"""
    import license_server.web_db as web_db
    from license_server.api import app
    from starlette.testclient import TestClient

    monkeypatch.setattr(web_db, "DB_PATH", tmp_path / "web.db")
    r = TestClient(app).get("/locales/en.json")
    assert r.status_code == 200
    assert isinstance(r.json(), dict)
    assert "no-cache" in r.headers.get("cache-control", "")
