"""เปิดลิงก์ด้วย Edge — เจอ Edge ต้องใช้ Edge, ไม่เจอต้องตกกลับเบราว์เซอร์เริ่มต้น (ห้ามพัง)"""
import webbrowser

from bot import open_browser


def test_uses_edge_when_installed(monkeypatch):
    monkeypatch.setattr(open_browser, "_edge", lambda: r"C:\fake\msedge.exe")
    opened = []
    monkeypatch.setattr(webbrowser, "get", lambda cmd: type("B", (), {"open": lambda _s, u: opened.append((cmd, u))})())
    assert open_browser.open_url("http://localhost:8770") is True
    assert opened and "msedge.exe" in opened[0][0] and opened[0][1] == "http://localhost:8770"


def test_falls_back_when_no_edge(monkeypatch):
    monkeypatch.setattr(open_browser, "_edge", lambda: None)
    opened = []
    monkeypatch.setattr(webbrowser, "open", lambda u: opened.append(u))
    assert open_browser.open_url("http://localhost:8790") is False
    assert opened == ["http://localhost:8790"]


def test_falls_back_when_edge_errors(monkeypatch):
    """Edge มีไฟล์แต่เปิดไม่ขึ้น — ต้องไม่โยน error ใส่ผู้ใช้"""
    monkeypatch.setattr(open_browser, "_edge", lambda: r"C:\fake\msedge.exe")

    def boom(_cmd):
        raise webbrowser.Error("no browser")
    monkeypatch.setattr(webbrowser, "get", boom)
    opened = []
    monkeypatch.setattr(webbrowser, "open", lambda u: opened.append(u))
    assert open_browser.open_url("http://x") is False and opened == ["http://x"]
