# tests/test_panel_images_api.py
"""API จัดการภาพอีเวนต์ใน Panel — list / preview / อัพโหลดแทนรายใบ"""
import io

import pytest
from PIL import Image
from starlette.testclient import TestClient

import bot.event_images as ei
from panel.server import app

client = TestClient(app)


def _png_bytes(size=(64, 64), color=(200, 30, 30), fmt="PNG"):
    buf = io.BytesIO()
    Image.new("RGB", size, color).save(buf, fmt)
    return buf.getvalue()


@pytest.fixture
def assets(tmp_path, monkeypatch):
    monkeypatch.setattr(ei, "ASSETS_DIR", tmp_path)
    (tmp_path / "main_village.png").write_bytes(_png_bytes())
    return tmp_path


def test_list_images(assets):
    r = client.get("/api/event-images")
    assert r.status_code == 200
    rows = r.json()["images"]
    assert any(row["key"] == "main_village" and row["size"] > 0 for row in rows)


def test_get_image_file(assets):
    r = client.get("/api/event-images/main_village")
    assert r.status_code == 200
    assert r.headers["content-type"] == "image/png"
    assert client.get("/api/event-images/no_such_key").status_code == 404


def test_bad_keys_rejected(assets):
    for bad in ("..%2Fsecret", "a.b", "UPPER", "th%E0%B8%B2%E0%B8%A2"):
        r = client.post(f"/api/event-images/{bad}", content=_png_bytes())
        # 405 = path หลุด normalize ไปเส้นทางที่ไม่มี POST — ไม่ถึง handler ไม่แตะไฟล์ = ปฏิเสธเหมือนกัน
        assert r.status_code in (400, 404, 405), bad


def test_upload_replaces_and_shrinks(assets):
    big = _png_bytes(size=(1024, 700), color=(0, 120, 255), fmt="JPEG")
    r = client.post("/api/event-images/main_village", content=big)
    assert r.status_code == 200 and r.json()["ok"]
    img = Image.open(assets / "main_village.png")
    assert img.size == (512, 512) and img.format == "PNG"
    assert (assets / "main_village.png").stat().st_size < 200_000
    # อัพโหลดคีย์ที่ยังไม่มีไฟล์ได้ (เคยลบภาพทิ้งแล้วใส่ใหม่)
    assert client.post("/api/event-images/new_key", content=big).status_code == 200
    assert (assets / "new_key.png").is_file()


def test_upload_garbage_rejected(assets):
    r = client.post("/api/event-images/main_village", content=b"not an image at all")
    assert r.status_code == 400
    r2 = client.post("/api/event-images/main_village", content=b"x" * (11 * 1024 * 1024))
    assert r2.status_code == 400
