import httpx

from bot import license_client


def _use_configured_server(monkeypatch):
    monkeypatch.setattr(license_client, "LICENSE_SERVER_URL", "http://test-license-server:8790")


def test_get_machine_id_is_deterministic():
    assert license_client.get_machine_id() == license_client.get_machine_id()
    assert len(license_client.get_machine_id()) == 32


def test_check_license_dev_mode_skips_when_url_not_configured(monkeypatch):
    # ถ้า LICENSE_SERVER_URL ยังเป็น placeholder (ยังไม่ได้ตั้งค่าก่อน build) -> ไม่บล็อกบอทระหว่าง dev/ทดสอบเอง
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
