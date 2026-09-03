# license_server/api_web/__init__.py
"""รวม router ย่อยทุกตัวของ API เว็บไซต์เกม (prefix /api/web) เป็นตัวเดียว

ระหว่างรื้อโครงสร้าง (09-02 ขั้นที่ 4): license_server/web_api.py ยังถือ route ส่วนใหญ่อยู่
และลงทะเบียนเข้า router ตัวนี้โดยตรง (import เข้ามาจากที่นี่ ไม่ได้สร้างเอง)
ย้ายทีละหมวดออกมาเป็นไฟล์ในนี้แล้วค่อย include_router เพิ่มทีหลัง

⚠️ router ต้องเป็นตัวเดียวกันหมด — license_server/api.py ทำ
   app.include_router(web_api.router) อยู่ตัวเดียว ถ้าไฟล์ไหนสร้าง APIRouter() ของตัวเอง
   แล้วไม่ include เข้าที่นี่ endpoint จะหายไปเงียบ ๆ (เว็บ 404 ตอนรันจริง แต่เทสไม่จับ)
"""
from fastapi import APIRouter

router = APIRouter(prefix="/api/web")

# ย้ายเข้ามาทีละหมวด (ดูลำดับ commit ใน .superpowers/sdd/2026-09-02-lobby-uno-betting/
# refactor-api-web-brief.md) — include_router ทุกตัวที่ย้ายเสร็จแล้วตรงนี้
