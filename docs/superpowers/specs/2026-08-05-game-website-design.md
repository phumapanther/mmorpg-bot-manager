# เว็บไซต์เกม (โฮสต์บน license_server) — Design

วันที่: 2026-08-05 | สถานะ: ผู้ใช้อนุมัติสถาปัตยกรรม + ให้ตัวอย่างดีไซน์ (WIX Tripo Games style)

## เป้าหมาย

เว็บไซต์นำเสนอเกมสำหรับผู้เล่น: ข่าวสาร/แพทช์ · ข้อมูลเกม · เติมเกม · โปรไฟล์ผู้เล่น
โฮสต์บน FastAPI ตัวเดียวกับ license_server (ลิงก์ cloudflared tunnel เดียวกัน) + ปุ่มเปิดเว็บ 2 ที่

## สไตล์ (ตามตัวอย่างที่ผู้ใช้ส่ง — WIX Tripo Games)

- **ธีมสว่าง**: พื้นครีม `#f5f1ea` · ข้อความน้ำเงินเข้ม `#2d2a4a` · แอคเซนต์แดงส้ม `#d93b2b` (ปุ่ม/ป้าย)
- navbar ขาวลอย sticky มุมโค้ง · hero ตัวหนังสือใหญ่หนา + คำโปรย + ปุ่ม CTA
- การ์ดมุมโค้งใหญ่ (~24px) เงานุ่ม รูปเต็มการ์ด — **ใช้ภาพพิกเซลอาร์ต 175 ใบจาก assets/events เป็นวิชวลหลัก**
- footer หลายคอลัมน์: ติดต่อ · เมนู · โซเชียล (ลิงก์ Discord จาก config `main_server_invite`)
- ฟอนต์ไทย Google Fonts (Prompt) + fallback ฟอนต์ระบบ · responsive มือถือ
- HTML/CSS/JS ล้วน ไม่มี framework (สไตล์เดียวกับ Panel) — **ห้ามเพิ่ม dependency ใหม่ทั้งโปรเจ็ค**

## โครงหน้า

| หน้า | เนื้อหา |
|---|---|
| `/` | hero นำเสนอเกม + ข่าวล่าสุด 3 ชิ้น + การ์ดจุดเด่นเกม (ทวีป/บอส/กิลด์/ตลาด) + CTA เข้า Discord |
| `/news` + `/news/{id}` | รายการข่าว (หมวด: 📢 ข่าว / 🛠️ แพทช์ / 🎪 อีเวนต์) + หน้าอ่านเต็ม |
| `/game` | ข้อมูลเกมเจนจาก `bot/game_data.py` จริง: 9 ทวีป (ภาพ arrival + มอนประจำทวีป) · 7 ธาตุ · 12 ธีมสัปดาห์ — อัพเดทเกมแล้วเว็บตรงเสมอ |
| `/topup` | วิธีเติมเกม + (ล็อกอินแล้ว) เติมจริง: ใส่จำนวนบาท → QR PromptPay → รอแอดมินอนุมัติ |
| `/me` | โปรไฟล์: เลเวล/EXP เงินสด/ธนาคาร ทวีป สัตว์เลี้ยง ตำแหน่ง + ประวัติเติมเงินตัวเอง |
| `/login` | ล็อกอินด้วยไอดี Discord แบบ device-code (ดูด้านล่าง) |
| `/admin` | หลังบ้าน: เขียน/แก้/ลบข่าว + คิวอนุมัติเติมเงิน — ล็อกอินด้วย admin secret เดิม |

## สถาปัตยกรรม

- ไฟล์เว็บ: `license_server/web_static/` (index.html, news.html, game.html, topup.html, me.html, login.html, admin.html, style.css, web.js) — mount `/` แบบ html=True บนแอป `license_server/api.py` เดิม (route API มาก่อน static เหมือน panel/server.py)
- ภาพเกม: mount `/assets` → โฟลเดอร์ `assets/` ของโปรเจ็ค (ภาพพิกเซลใช้ซ้ำบนเว็บ)
- API เว็บ: `license_server/web_api.py` (router ใหม่ prefix `/api/web`) + DB: `license_server/web.db` (แยกจาก licenses.db)
- ข้อมูลเกม: `/api/web/gamedata` อ่านจาก `bot.game_data` + `config.example.json` (import ตรง — repo เดียวกัน)
- ข่าว: ตาราง `news(id, title, category, body, created_at, updated_at, published)` — body เป็น
  markdown อย่างง่าย เรนเดอร์ฝั่ง JS (mini renderer เขียนเอง ~40 บรรทัด: หัวข้อ/ตัวหนา/ลิสต์/ลิงก์/รูป)

### ล็อกอิน Discord แบบ device-code (ไม่ต้องมีโดเมน — OAuth จริงทำไม่ได้เพราะ tunnel URL เปลี่ยนทุกรีสตาร์ท)

1. หน้า `/login` กดปุ่ม → `POST /api/web/login/code` ได้โค้ด 6 ตัว (A-Z0-9, อายุ 5 นาที, ใช้ครั้งเดียว) → โชว์คำสั่ง `!weblogin <โค้ด>` พร้อมปุ่มคัดลอก
2. ผู้เล่นพิมพ์คำสั่งในดิสคอร์ด → cog ใหม่ `bot/cogs/web_link.py` เขียน `discord_id` ลงแถวโค้ดใน `web.db` (เครื่องเดียวกัน — SQLite ข้ามโปรเซสได้)
3. หน้าเว็บ poll `GET /api/web/login/status?code=..` → ได้ session cookie ลงชื่อ **HMAC** (คีย์ = admin secret, payload = discord_id + วันหมดอายุ 30 วัน — stateless ไม่มีตาราง session)
- ตาราง `login_codes(code, discord_id NULL, created_at, expires_at, used INTEGER)`
- cog ทำงานเฉพาะเครื่องที่มี `license_server/web.db` (เครื่องลูกค้า exe ไม่มีโฟลเดอร์นี้ = cog เงียบ) + เซิร์ฟหลักเท่านั้น

### โปรไฟล์ / เช็คเงิน

- อ่าน `game_data.db` ที่ root โปรเจ็ค แบบ **read-only** (`file:...?mode=ro`) — ไม่มีทางเขียนทับข้อมูลเกม
- โชว์: level, exp, cash, bank, continent(label), pet, title, achievements/bestiary นับรวม

### เติมเงินผ่านเว็บ

- `POST /api/web/topup` (ต้องล็อกอิน): จำนวนบาท → ตรวจ min/max จาก config `payment` → เจน QR PromptPay (reuse `bot/promptpay.py` + `qrcode[pil]` เดิม เบอร์จาก config) → แถว `topups(id, discord_id, amount_thb, gold, status='pending', created_at, decided_at, decided_by, note)` — gold = บาท × `payment.exchange_rate`
- แอดมินเห็นคิวใน `/admin` → อนุมัติ = UPDATE status + **เพิ่ม gold เข้า `players.bank`** ใน transaction สั้น (`busy_timeout=5000` กันชนกับบอท — ชื่อคอลัมน์ตรวจจาก player_model ตอนทำแผน) / ปฏิเสธ = บันทึกเหตุผล
- ทุกรายการคือ audit log ในตัว (ใครอนุมัติ เมื่อไหร่) — ไม่มีการเพิ่มเงินอัตโนมัติโดยไม่ผ่านแอดมิน

### ปุ่มเปิดเว็บ 2 ที่

- keygen GUI: ปุ่ม "🌐 เปิดเว็บไซต์" — เปิดเบราว์เซอร์ด้วยลิงก์ tunnel ปัจจุบัน (ไม่มี tunnel → localhost:8790)
- ในเกม: คำสั่ง `!web` (cog เดียวกับ weblogin) ส่ง embed ลิงก์เว็บ — อ่านจาก `LICENSE_SERVER_URL.txt`

## ความปลอดภัย

- admin: `POST /api/web/admin/login` ด้วย admin secret เดิม → cookie ลงชื่อ HMAC (สิทธิ์ role=admin)
- cookie ทุกใบ: HMAC-SHA256 + วันหมดอายุ, `HttpOnly`, `SameSite=Lax`
- game_data.db เปิด read-only ทุกจุด ยกเว้นอนุมัติเติมเงิน (เขียนจุดเดียว)
- ตรวจ input: จำนวนเงิน > 0 และอยู่ใน min/max, โค้ดล็อกอิน regex `^[A-Z0-9]{6}$`
- API ที่แก้ข้อมูลทั้งหมดต้องมี cookie ถูกต้อง — ไม่มี = 401

## เทส

- ข่าว: CRUD ผ่าน API (admin เท่านั้น) · คนไม่ล็อกอินอ่านได้อย่างเดียว
- ล็อกอิน: โค้ดถูก→ได้ cookie · โค้ดหมดอายุ/ใช้ซ้ำ/ผิด format → ปฏิเสธ · cookie ปลอม/แก้ไข → 401
- เติมเงิน: สร้างรายการ→pending · อนุมัติ→ทองเข้า bank ถูกคน **ครั้งเดียว** (กดอนุมัติซ้ำไม่เพิ่มซ้ำ) · ปฏิเสธ→ทองไม่เข้า · เกิน max/ติดลบ → 400
- โปรไฟล์: ไม่ล็อกอิน → 401 · ล็อกอินแล้วเห็นข้อมูลตรง DB
- gamedata API ครบ 9 ทวีป 7 ธาตุ

## สิ่งที่ตัดออก (YAGNI)

- OAuth จริง (รอมีโดเมน/named tunnel — โครง cookie เดิมใช้ต่อได้)
- อัพโหลดรูปประกอบข่าว (ใช้ URL ภาพ /assets ที่มีอยู่) · คอมเมนต์/ไลค์ · หลายภาษา
- แจ้งเตือนอัตโนมัติเข้า Discord เมื่อมีข่าวใหม่ (เพิ่มทีหลังได้)
- ระบบ role อื่นนอกจาก player/admin
