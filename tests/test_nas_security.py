"""🔒 ความปลอดภัยตอนเปิดสู่เน็ตผ่าน tunnel สาธารณะ (NAS/คลาวด์)

รวมช่องโหว่ที่ตัวตรวจเจอก่อนขึ้น NAS 10-12:
- สลิปโอนเงินของคนอื่นเปิดดูได้ (IDOR) · ช่อง mint คีย์ไลเซนส์โผล่ลิงก์สาธารณะ
- รหัสแอดมินอ่อน (เซ็นคุกกี้ทุกใบ) · ลองรหัสแอดมินรัว ๆ ได้
"""
import importlib
import os

import pytest


# ── สลิปเปิดได้เฉพาะเจ้าของ/แอดมินจริง (IDOR) ───────────────────────────────

def test_ผู้เล่นเอาคุกกี้ตัวเองมาใส่ช่องแอดมินเปิดสลิปคนอื่นไม่ได้():
    """คุกกี้ผู้เล่นเซ็นด้วยกุญแจเดียวกับแอดมิน — ต้องเช็ค role==admin ไม่ใช่แค่ลายเซ็นถูก"""
    src = __import__("pathlib").Path("license_server/api_web/topup.py").read_text(encoding="utf-8")
    fn = src[src.index("def get_slip"):src.index("def get_slip") + 700]
    assert '.get("role") == "admin"' in fn, "get_slip ต้องเช็ค role==admin ของคุกกี้ web_admin"
    assert "if not verify(request.cookies.get(\"web_admin\"" not in fn, "ห้ามเช็คแค่ลายเซ็นถูก"


# ── ช่องแจกคีย์ไลเซนส์ปิดได้เมื่อ LICENSE_API=0 ─────────────────────────────

@pytest.fixture
def _clean_env(monkeypatch):
    monkeypatch.setenv("ADMIN_SECRET", "x" * 32)   # กัน create_app อ่านรหัสจริงของเครื่อง
    yield monkeypatch


def _make_client(monkeypatch, tmp_path, license_api):
    import license_server.web_db as web_db
    if license_api is None:
        monkeypatch.delenv("LICENSE_API", raising=False)
    else:
        monkeypatch.setenv("LICENSE_API", license_api)
    monkeypatch.setattr(web_db, "DB_PATH", tmp_path / "web.db")
    import license_server.api as api
    importlib.reload(api)
    from starlette.testclient import TestClient
    return TestClient(api.create_app()), api


def test_LICENSE_API_0_ปิดช่อง_mint_และ_redeem(_clean_env, tmp_path):
    c, api = _make_client(_clean_env, tmp_path, "0")
    try:
        # route ถูกถอด → ไม่มีทางได้ 200 (mint สำเร็จ) หรือ 401 (route ยังเช็ครหัส) · เหลือ 404/405 จาก static mount
        g = c.post("/generate", headers={"x-admin-secret": "x" * 32})
        assert g.status_code in (404, 405) and "key" not in g.text
        assert c.get("/keys", headers={"x-admin-secret": "x" * 32}).status_code in (404, 405)
        assert c.post("/redeem", json={"key": "A", "machine_id": "m"}).status_code in (404, 405)
    finally:
        importlib.reload(api)


def test_ค่าเริ่มต้นยังเปิดช่องไลเซนส์ไว้_เครื่องผู้ขายใช้ได้(_clean_env, tmp_path):
    c, api = _make_client(_clean_env, tmp_path, None)
    try:
        # ไม่ใส่รหัส = 401 (ไม่ใช่ 404) แปลว่า route ยังอยู่
        assert c.get("/keys").status_code == 401
    finally:
        importlib.reload(api)


# ── ลองรหัสแอดมินรัว ๆ โดนจำกัด ────────────────────────────────────────────

def test_ล็อกอินแอดมินมีลิมิตกันสแปมแต่เจ้าของพิมพ์ผิดได้():
    from license_server import rate_limit
    assert rate_limit.group_for("/api/web/admin/login", "POST") == "adminlogin"
    limit, window = rate_limit.LIMITS["adminlogin"]
    assert limit <= 30 and window >= 300, "ต้องมีเพดาน (กันบอทยิงรัว) แต่ไม่แน่นจนเจ้าของพิมพ์ผิดแล้วโดนล็อก"


def test_จำกัดอัตรานับจาก_ip_จริงหลัง_tunnel():
    """หลัง tunnel ทุกคำขอมาจาก ip เดียว + สลับคุกกี้ได้ → ต้อง key ด้วย cf-connecting-ip"""
    src = __import__("pathlib").Path("license_server/api.py").read_text(encoding="utf-8")
    seg = src[src.index("_rate_limit"):src.index("_rate_limit") + 500]
    assert "cf-connecting-ip" in seg, "rate limit ต้อง key จาก cf-connecting-ip ก่อนคุกกี้"


# ── รหัสแอดมินอ่อนไม่ให้สตาร์ท ──────────────────────────────────────────────

@pytest.mark.parametrize("secret,ok", [
    ("", False),
    ("ตั้งรหัสยาวๆสำหรับเข้าหลังบ้าน", False),   # placeholder ใน .env.example
    ("short", False),
    ("a1b2c3d4e5f6g7h8i9j0", False),             # 20 ตัว ยังสั้นไป
    ("a1b2c3d4e5f6g7h8i9j0k1l2", True),          # 24 ตัว
    ("0123456789abcdef0123456789abcdef", True),
])
def test_รหัสแอดมินอ่อนไม่ให้เปิดระบบ(monkeypatch, secret, ok):
    from license_server import serve
    monkeypatch.setenv("ADMIN_SECRET", secret)
    if ok:
        serve._check_admin_secret()                 # ผ่าน ไม่ exit
    else:
        with pytest.raises(SystemExit):
            serve._check_admin_secret()
