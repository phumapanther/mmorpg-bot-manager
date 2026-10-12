"""🌐 ลิงก์เว็บแบบสุ่ม (Cloudflare Quick Tunnel) บนเครื่องที่ไม่มีหน้าต่าง GUI — NAS / คลาวด์

บนเครื่องที่บ้าน keygen_gui คอยจับลิงก์ใหม่แล้วเขียน LICENSE_SERVER_URL.txt ให้
บน NAS ไม่มีหน้าต่าง → license_server/tunnel_url.py ถาม cloudflared เอง แล้วเขียนไฟล์เดียวกัน
บอทอ่านไฟล์นี้ใหม่ทุกครั้งที่แจกลิงก์ (!web / !login) ลิงก์เปลี่ยนเมื่อไหร่ผู้เล่นได้ลิงก์ใหม่ทันที
"""
import pathlib

import pytest

from license_server import tunnel_url

ROOT = pathlib.Path(__file__).resolve().parent.parent


def test_เขียนลิงก์ใหม่ลงไฟล์ที่บอทอ่าน(tmp_path):
    f = tmp_path / "LICENSE_SERVER_URL.txt"
    assert tunnel_url.save_tunnel_url("abc-def-ghi.trycloudflare.com", f) is True
    assert f.read_text(encoding="utf-8").strip() == "https://abc-def-ghi.trycloudflare.com"
    assert tunnel_url.save_tunnel_url("abc-def-ghi.trycloudflare.com", f) is False, "ลิงก์เดิมไม่ต้องเขียนซ้ำ"
    assert tunnel_url.save_tunnel_url("new-link.trycloudflare.com", f) is True
    assert f.read_text(encoding="utf-8").strip() == "https://new-link.trycloudflare.com"


@pytest.mark.parametrize("bad", [
    "", None, "   ",                               # tunnel ยังไม่ขึ้น cloudflared ตอบ hostname ว่าง
    "evil.com",
    "a.trycloudflare.com.evil.com",
    "https://a.trycloudflare.com",                 # cloudflared ตอบแค่ชื่อโฮสต์ ไม่มี https://
    "a.trycloudflare.com/../x",
])
def test_ค่าที่ไม่ใช่ลิงก์_quick_tunnel_ไม่แตะไฟล์(tmp_path, bad):
    f = tmp_path / "LICENSE_SERVER_URL.txt"
    f.write_text("https://old.trycloudflare.com\n", encoding="utf-8")
    assert tunnel_url.save_tunnel_url(bad, f) is False
    assert f.read_text(encoding="utf-8").strip() == "https://old.trycloudflare.com"


def test_ไฟล์ปลายทางคือไฟล์เดียวกับที่บอทอ่าน():
    from bot.apps.bot_game import web_link
    assert pathlib.Path(tunnel_url.url_file()) == pathlib.Path(web_link.URL_FILE)


def test_อ่านคำตอบจาก_cloudflared(monkeypatch, tmp_path):
    """/quicktunnel ของ cloudflared ตอบ {"hostname":"..."} (ซอร์ส cloudflared metrics/metrics.go)"""
    f = tmp_path / "LICENSE_SERVER_URL.txt"
    monkeypatch.setattr(tunnel_url, "_fetch", lambda url: b'{"hostname":"zz-top.trycloudflare.com"}')
    assert tunnel_url.poll_once("http://tunnel:2000/quicktunnel", f) is True
    assert f.read_text(encoding="utf-8").strip() == "https://zz-top.trycloudflare.com"


def test_cloudflared_ยังไม่ตอบ_ไม่พัง(monkeypatch, tmp_path):
    def boom(url):
        raise OSError("connection refused")
    monkeypatch.setattr(tunnel_url, "_fetch", boom)
    assert tunnel_url.poll_once("http://tunnel:2000/quicktunnel", tmp_path / "x.txt") is False
    monkeypatch.setattr(tunnel_url, "_fetch", lambda url: b"not json")
    assert tunnel_url.poll_once("http://tunnel:2000/quicktunnel", tmp_path / "x.txt") is False


def test_serve_เปิดตัวจับลิงก์เมื่อตั้ง_TUNNEL_METRICS_URL():
    src = (ROOT / "license_server" / "serve.py").read_text(encoding="utf-8")
    assert "TUNNEL_METRICS_URL" in src and "watch_tunnel" in src


def test_compose_ของ_NAS_ต่อกันครบและไม่เปิดพอร์ตออกนอก():
    yaml = pytest.importorskip("yaml")
    nas = yaml.safe_load((ROOT / "docker-compose.nas.yml").read_text(encoding="utf-8"))
    game, tunnel = nas["services"]["game"], nas["services"]["tunnel"]
    assert "ports" not in game and "ports" not in tunnel, "NAS แชร์ไฟล์คนอื่นอยู่ — ห้ามเปิดพอร์ต ให้เข้าผ่าน tunnel อย่างเดียว"
    assert game["environment"]["TUNNEL_METRICS_URL"] == "http://tunnel:2000/quicktunnel"
    assert "--metrics 0.0.0.0:2000" in tunnel["command"] and "--url http://game:8790" in tunnel["command"]
    assert game.get("mem_limit"), "ต้องจำกัดแรมไม่ให้แย่ง NAS คนอื่น (cpus ใช้ไม่ได้บนเคอร์เนล Synology บางรุ่น)"
    assert "./data:/app/data" in game["volumes"]
    assert "./config.json:/app/config.json" in game["volumes"], "ต้อง mount config.json ไม่งั้นบอทได้ตั้งค่าว่าง"
    for key in ("GAME_DB_PATH", "WEB_DB_PATH", "LICENSE_DB_PATH", "UPLOAD_DIR", "BACKUP_DIR"):
        assert game["environment"][key].startswith("/app/data/"), f"{key} ต้องอยู่ใน volume ไม่งั้นข้อมูลหายตอน build ใหม่"
