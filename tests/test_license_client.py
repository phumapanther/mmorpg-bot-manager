import httpx

from bot import license_client


def _use_configured_server(monkeypatch):
    # ⚠️ ระบบไลเซนส์ **ปิดสวิตช์ไว้** (เจ้าของเกมไม่ขายแล้ว 2026-09-24) — เทสชุดนี้
    #    เปิดกลับเพื่อคุมว่าโค้ดเช็คคีย์ยังทำงานถูกอยู่ วันที่กลับมาขายจะได้ใช้ได้เลย
    monkeypatch.setattr(license_client, "LICENSE_REQUIRED", True)
    monkeypatch.setattr(license_client, "LICENSE_SERVER_URL", "http://test-license-server:8790")


def test_get_machine_id_is_deterministic():
    assert license_client.get_machine_id() == license_client.get_machine_id()
    assert len(license_client.get_machine_id()) == 32


def test_check_license_dev_mode_skips_when_url_not_configured(monkeypatch):
    # ถ้า LICENSE_SERVER_URL ยังเป็น placeholder (ยังไม่ได้ตั้งค่าก่อน build) -> ไม่บล็อกบอทระหว่าง dev/ทดสอบเอง
    monkeypatch.setattr(license_client, "LICENSE_REQUIRED", True)
    monkeypatch.setattr(license_client, "LICENSE_SERVER_URL", "http://YOUR-LICENSE-SERVER-ADDRESS:8790")
    ok, msg = license_client.check_license("", "token")
    assert ok is True


def test_check_license_no_key(monkeypatch):
    _use_configured_server(monkeypatch)
    ok, msg = license_client.check_license("", "token")
    assert ok is False
    assert "License Key" in msg


def test_check_license_success(monkeypatch):
    _use_configured_server(monkeypatch)

    def fake_post(url, json, timeout=None):
        return httpx.Response(200, json={"ok": True}, request=httpx.Request("POST", url))
    monkeypatch.setattr(license_client.httpx, "post", fake_post)
    ok, msg = license_client.check_license("ABCD-1234", "token")
    assert ok is True


def test_check_license_used_elsewhere(monkeypatch):
    _use_configured_server(monkeypatch)

    def fake_post(url, json, timeout=None):
        return httpx.Response(403, json={"detail": "already_used_elsewhere"}, request=httpx.Request("POST", url))
    monkeypatch.setattr(license_client.httpx, "post", fake_post)
    ok, msg = license_client.check_license("ABCD-1234", "token")
    assert ok is False
    assert "เครื่องอื่น" in msg


def test_check_license_invalid_key(monkeypatch):
    _use_configured_server(monkeypatch)

    def fake_post(url, json, timeout=None):
        return httpx.Response(404, json={"detail": "invalid_key"}, request=httpx.Request("POST", url))
    monkeypatch.setattr(license_client.httpx, "post", fake_post)
    ok, msg = license_client.check_license("BOGUS", "token")
    assert ok is False
    assert "ไม่ถูกต้อง" in msg


def test_check_license_server_unreachable(monkeypatch):
    _use_configured_server(monkeypatch)
    monkeypatch.setattr(license_client.os.path, "isdir", lambda p: False)   # เครื่องลูกค้า — ไม่มี fallback

    def fake_post(url, json, timeout=None):
        raise httpx.ConnectError("refused", request=httpx.Request("POST", url))
    monkeypatch.setattr(license_client.httpx, "post", fake_post)
    ok, msg = license_client.check_license("ABCD-1234", "token")
    assert ok is False
    assert "License Server" in msg


def test_check_license_falls_back_to_localhost_on_owner_machine(monkeypatch):
    """เครื่องเจ้าของเกม (มีโฟลเดอร์ license_server): tunnel ตาย → เช็คผ่าน localhost ต่ออัตโนมัติ"""
    _use_configured_server(monkeypatch)
    calls = []

    def fake_post(url, json, timeout=None):
        calls.append(url)
        if "localhost" not in url:
            raise httpx.ConnectError("dead tunnel", request=httpx.Request("POST", url))
        return httpx.Response(200, json={"ok": True}, request=httpx.Request("POST", url))
    monkeypatch.setattr(license_client.httpx, "post", fake_post)
    ok, _msg = license_client.check_license("ABCD-1234", "token")
    assert ok is True                                       # ผ่านด้วย localhost
    assert any("localhost:8790" in u for u in calls)
    assert calls[0].startswith("http://test-license-server")  # ลอง URL หลักก่อนเสมอ


# ── สวิตช์ปิดระบบไลเซนส์ (2026-09-24) ──
#
# เจ้าของเกมเลิกขาย รันใช้เองเครื่องเดียว — บอทต้องสตาร์ทได้โดยไม่ต้องมีคีย์
# และไม่ต้องเปิดโปรแกรม License Server ทิ้งไว้

def test_ปิดสวิตช์แล้วสตาร์ทได้โดยไม่ต้องมีคีย์():
    """⭐ ค่าจริงในไฟล์ต้องปิดอยู่ — ไม่ใช่แค่ปิดได้ตอน monkeypatch"""
    assert license_client.LICENSE_REQUIRED is False, "สวิตช์ไลเซนส์ยังเปิดอยู่"
    ok, msg = license_client.check_license("", "")
    assert ok is True, msg


def test_ปิดสวิตช์แล้วไม่ยิง_http_เลยสักครั้ง(monkeypatch):
    """⭐ ใจความทั้งหมด — ยังยิงอยู่ = ยังต้องเปิด License Server ทิ้งไว้เหมือนเดิม

    ถ้าดักทีหลังด่านอื่น (เช่น หลังเช็คว่ามีคีย์ไหม) บอทจะยังสตาร์ทไม่ได้
    ต้องคืนค่าออกไปตั้งแต่บรรทัดแรกของฟังก์ชัน
    """
    monkeypatch.setattr(license_client, "LICENSE_SERVER_URL", "http://test-license-server:8790")

    def boom(*a, **k):
        raise AssertionError("ยังยิง HTTP ทั้งที่ปิดสวิตช์แล้ว")
    monkeypatch.setattr(license_client.httpx, "post", boom)

    for key in ("", "คีย์มั่ว", "ABCD-1234"):
        ok, _ = license_client.check_license(key, "token")
        assert ok is True, f"คีย์ {key!r} ยังถูกบล็อก"


def test_เปิดสวิตช์กลับแล้วเช็คคีย์เหมือนเดิม(monkeypatch):
    """⭐ กันถอดเกิน — โค้ดเช็คคีย์ต้องยังอยู่ครบ กลับมาขายได้ทันที"""
    _use_configured_server(monkeypatch)
    ok, msg = license_client.check_license("", "token")
    assert ok is False and "License Key" in msg
