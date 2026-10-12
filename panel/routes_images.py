# panel/routes_images.py
"""API จัดการภาพอีเวนต์ — list / preview / อัพโหลดแทนรายใบ (spec: 2026-08-05-panel-event-images)

อัพโหลดรับ body เป็น raw bytes ตรงๆ (ไม่ใช้ multipart — ไม่ต้องพึ่ง python-multipart)
ทุกภาพถูกย่อ 512×512 + quantize 256 สีอัตโนมัติ ให้ไฟล์เล็กพอสำหรับผู้เล่นเน็ตช้า
"""
import io
import re

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse

from bot import event_images

router = APIRouter()

_KEY_RE = re.compile(r"^[a-z0-9_]+$")
_MAX_UPLOAD = 10 * 1024 * 1024  # 10MB


def _safe_path(key):
    if not _KEY_RE.match(key or ""):
        raise HTTPException(400, "ชื่อภาพไม่ถูกต้อง (ใช้ได้เฉพาะ a-z 0-9 _)")
    return event_images.ASSETS_DIR / f"{key}.png"


@router.get("/api/event-images")
def list_images():
    d = event_images.ASSETS_DIR
    rows = ([{"key": p.stem, "size": p.stat().st_size} for p in sorted(d.glob("*.png"))]
            if d.is_dir() else [])
    return {"images": rows}


@router.get("/api/event-images/{key}")
def get_image(key: str):
    p = _safe_path(key)
    if not p.is_file():
        raise HTTPException(404, "ไม่มีไฟล์ภาพนี้")
    return FileResponse(str(p), media_type="image/png")


@router.post("/api/event-images/{key}")
async def upload_image(key: str, request: Request):
    from PIL import Image
    p = _safe_path(key)
    # กันรูประเบิดพิกเซลทำ container OOM: เช็ค Content-Length ก่อนอ่าน body + จำกัดจำนวนพิกเซล
    clen = request.headers.get("content-length")
    if clen and clen.isdigit() and int(clen) > _MAX_UPLOAD:
        raise HTTPException(400, "ไฟล์ใหญ่เกิน 10MB")
    Image.MAX_IMAGE_PIXELS = 25_000_000
    data = await request.body()
    if len(data) > _MAX_UPLOAD:
        raise HTTPException(400, "ไฟล์ใหญ่เกิน 10MB")
    try:
        img = Image.open(io.BytesIO(data))
        img.load()
    except Exception:
        raise HTTPException(400, "ไฟล์นี้เปิดเป็นรูปภาพไม่ได้ หรือใหญ่ผิดปกติ (รองรับ png/jpg/webp)")
    img = img.convert("RGB").resize((512, 512), Image.LANCZOS).quantize(colors=256)
    p.parent.mkdir(parents=True, exist_ok=True)
    img.save(p, format="PNG", optimize=True)
    return {"ok": True, "size": p.stat().st_size}
