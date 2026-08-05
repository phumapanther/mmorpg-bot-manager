# Panel จัดการระบบภาพอีเวนต์ — Design

วันที่: 2026-08-05 | สถานะ: ผู้ใช้อนุมัติแล้ว | ต่อยอดจาก `2026-08-03-event-images-design.md`

## เป้าหมาย

1. เปิด/ปิดระบบภาพอีเวนต์ทั้งเกมได้จาก Panel
2. อัพโหลดภาพแทนรายใบได้จาก Panel (แก้ภาพที่ไม่สวย/ใส่ภาพของตัวเอง)

## ดีไซน์

### สวิตช์เปิด/ปิด
- config section ใหม่ `event_images: {"enabled": true}` — **ไม่มี key = เปิด** (config เก่าไม่พัง)
- เช็คที่ `bot/event_images.py::_file()` จุดเดียว → ปิดแล้วทุก helper คืน `None` ทุกจุดในเกมหยุดแนบภาพเอง
- มีผลหลังรีสตาร์ทบอท (config ถูกแคช — ขั้นตอนเดียวกับค่าอื่นใน Panel)

### แท็บใหม่ 🖼️ ภาพอีเวนต์ (`data-tab="images"`)
- บนสุด: checkbox `event_images.enabled` + ปุ่มบันทึก (เซฟผ่าน `PUT /api/config` เดิม) + ช่องค้นหากรองชื่อ
- ตารางภาพจากโฟลเดอร์จริง `assets/events/*.png`: thumbnail (lazy load) / ชื่อคีย์ / ขนาด KB / ปุ่ม 📤 อัพโหลดแทน
- อัพโหลด: รับ png/jpg/webp → **ย่อ 512×512 + quantize 256 สีอัตโนมัติ** (คุมไฟล์เล็กตามโจทย์เน็ตช้า)
  → ทับไฟล์เดิม — เห็นผลในเกมทันทีไม่ต้องรีสตาร์ท (บอทเปิดไฟล์ใหม่ทุกครั้งที่ใช้)

### API ใหม่ — `panel/routes_images.py`
| Method | Path | ทำอะไร |
|---|---|---|
| GET | `/api/event-images` | รายชื่อ `[{key, size}]` จากโฟลเดอร์จริง |
| GET | `/api/event-images/{key}` | ตัวไฟล์ PNG (ให้ตาราง preview) |
| POST | `/api/event-images/{key}` | อัพโหลดแทน — **body เป็น raw bytes** (ไม่ใช้ multipart → ไม่ต้องเพิ่ม dependency `python-multipart`) |

- คีย์ validate ด้วย regex `^[a-z0-9_]+$` — กัน path traversal เด็ดขาด
- ไฟล์อัพโหลดเกิน 10MB / เปิดเป็นภาพไม่ได้ → 400 พร้อมข้อความไทย
- อัพโหลดคีย์ที่ยังไม่มีไฟล์ได้ (กรณีผู้ใช้ลบภาพทิ้งแล้วอยากใส่ใหม่)

### เทส
- ปิดสวิตช์ → `event_image`/`monster_image`/`item_use_image` คืน `None` แม้ไฟล์มีจริง
- API: list เจอไฟล์ / upload ย่อเป็น 512×512 จริง / คีย์เพี้ยน (`../` ฯลฯ) โดนปฏิเสธ / ไฟล์ขยะโดน 400
- ผ่าน guard เดิม: `test_every_config_section_is_reachable_from_panel` (สตริง `event_images` ต้องอยู่ใน app.js)

## ตัดออก (YAGNI)
ปุ่มลบภาพ · สั่งเจนใหม่จาก Panel · เปิด/ปิดรายหมวด · แสดงภาพที่คีย์ควรมีแต่ไฟล์หาย
