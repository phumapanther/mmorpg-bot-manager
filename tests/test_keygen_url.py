"""ลิงก์ tunnel ต้องอยู่คงเดิม เปลี่ยนก็ต่อเมื่อกดปุ่ม "ขอลิงก์ใหม่" เอง (เจ้าของเกมสั่ง 09-01)

⚠️ Cloudflare quick tunnel ขอชื่อเดิมไม่ได้ (มีแต่ --url ไม่มี --name) ที่ทำได้คือ
   ไม่เอาลิงก์ใหม่ไปทับไฟล์ LICENSE_SERVER_URL.txt ที่ลูกค้าใช้ build
"""
import pytest

tk = pytest.importorskip("tkinter")
from license_server import keygen_gui


class _Var:
    def __init__(self): self.v = ""
    def set(self, v): self.v = v
    def get(self): return self.v


class _App:
    """ตัวปลอมพอให้ _got_tunnel_url ทำงาน — ไม่ต้องเปิดหน้าต่างจริง"""
    def __init__(self):
        self.want_new_url = False
        self.live_url = ""
        self.tunnel_var = _Var()
        self.url_status_var = _Var()
        self.saved = []

    _got_tunnel_url = keygen_gui.KeygenApp._got_tunnel_url

    def _save_url_file(self, url):
        self.saved.append(url)
        return "บันทึกแล้ว"


def _app(monkeypatch, tmp_path, saved_url):
    f = tmp_path / "LICENSE_SERVER_URL.txt"
    if saved_url is not None:
        f.write_text(saved_url, encoding="utf-8")
    monkeypatch.setattr(keygen_gui, "URL_FILE", str(f))
    a = _App()
    a._saved_url = lambda: keygen_gui.KeygenApp._saved_url(a)
    return a


OLD = "https://resorts-person-strikes-handling.trycloudflare.com"
NEW = "https://brand-new-random-words.trycloudflare.com"


def test_เปิดโปรแกรมใหม่ไม่ทับลิงก์เดิม(monkeypatch, tmp_path):
    a = _app(monkeypatch, tmp_path, OLD)
    a._got_tunnel_url(NEW)
    assert a.saved == [], "ห้ามเขียนทับ LICENSE_SERVER_URL.txt เอง"
    assert a.tunnel_var.get() == OLD, "ต้องโชว์ลิงก์เดิมที่ลูกค้าถืออยู่"
    assert a.live_url == NEW, "แต่ยังต้องจำลิงก์จริงของ tunnel รอบนี้ไว้"


def test_กดขอลิงก์ใหม่แล้วทับ(monkeypatch, tmp_path):
    a = _app(monkeypatch, tmp_path, OLD)
    a.want_new_url = True
    a._got_tunnel_url(NEW)
    assert a.saved == [NEW]
    assert a.tunnel_var.get() == NEW
    assert a.want_new_url is False, "ต้องรีเซ็ต ไม่งั้นรอบหน้าทับซ้ำ"


def test_ยังไม่เคยมีไฟล์ก็บันทึกเลย(monkeypatch, tmp_path):
    a = _app(monkeypatch, tmp_path, None)
    a._got_tunnel_url(NEW)
    assert a.saved == [NEW]


@pytest.mark.parametrize("junk", ["", "   ", "ยังไม่ได้ตั้งค่า", "http://localhost:8000"])
def test_ไฟล์เสียก็บันทึกทับได้(monkeypatch, tmp_path, junk):
    a = _app(monkeypatch, tmp_path, junk)
    a._got_tunnel_url(NEW)
    assert a.saved == [NEW], f"ค่าที่ใช้ไม่ได้ ({junk!r}) ต้องถูกทับ"


def test_ปุ่มขอลิงก์ใหม่มีเมธอดจริง():
    # เคยพลาด: ใส่ปุ่มแล้วลืมเขียนเมธอด กดแล้วโปรแกรมพัง
    for name in ("renew_tunnel", "_stop_tunnel", "_saved_url", "_got_tunnel_url"):
        assert callable(getattr(keygen_gui.KeygenApp, name, None)), name
