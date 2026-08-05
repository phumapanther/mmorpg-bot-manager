# เว็บไซต์เกมบน license_server — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** เว็บไซต์เกม (ข่าว/ข้อมูลเกม/ล็อกอิน Discord/โปรไฟล์/เติมเงิน/แอดมิน) โฮสต์บนแอป FastAPI ของ license_server + ปุ่มเปิดเว็บใน keygen GUI และคำสั่ง `!web` ในเกม

**Architecture:** router ใหม่ `license_server/web_api.py` (prefix `/api/web`) + DB ใหม่ `license_server/web.db` + static site `license_server/web_static/` mount ที่ `/` + mount `/assets` ชี้โฟลเดอร์ assets ของโปรเจ็ค · ล็อกอิน = device-code ผ่านบอท (cog ใหม่ `bot/cogs/web_link.py`) · cookie ลงชื่อ HMAC คีย์ = admin secret เดิม

**Tech Stack:** FastAPI + sqlite3 + hmac (stdlib) + qrcode[pil] (มีแล้ว) + HTML/CSS/JS ล้วน — **ห้ามเพิ่ม dependency**

**Spec:** `docs/superpowers/specs/2026-08-05-game-website-design.md`

## Global Constraints

- ธีมเว็บ: พื้นครีม `#f5f1ea` ข้อความ `#2d2a4a` แอคเซนต์ `#d93b2b` การ์ดโค้ง 24px navbar ขาว sticky ฟอนต์ Prompt (Google Fonts + fallback ระบบ) responsive
- `game_data.db` เปิด **read-only** (`file:...?mode=ro&uri=True`) ทุกจุด ยกเว้นอนุมัติเติมเงิน (เขียนจุดเดียว, `busy_timeout=5000`)
- ทุก API เขียนข้อมูลต้องมี cookie HMAC ถูกต้อง ไม่มี = 401 · cookie เป็น HttpOnly SameSite=Lax
- path DB/ไฟล์อ้างจาก `PROJECT_ROOT = Path(__file__).resolve().parent.parent` — ห้ามพึ่ง CWD
- คอมมิตท้ายทุก task · รันเทส `python -m pytest tests/ -q` ก่อนคอมมิตทุกครั้ง

## โครงไฟล์

- Create: `license_server/web_db.py` (schema+ตัวช่วย web.db), `license_server/web_api.py` (router),
  `license_server/web_static/{index,news,game,topup,me,login,admin}.html + style.css + web.js`,
  `bot/cogs/web_link.py`, `tests/test_web_api.py`, `tests/test_web_link_cog.py`
- Modify: `license_server/api.py` (include router + mounts), `license_server/keygen_gui.py` (ปุ่ม 🌐),
  `bot/main.py` (โหลด cog ในบล็อกเซิร์ฟหลัก)

---

### Task 1: web_db + auth + ข่าว CRUD (backend)

**Interfaces (Produces):**
- `web_db.connect() -> sqlite3.Connection` (สร้างตารางถ้ายังไม่มี: news, login_codes, topups ตาม spec)
- `web_api.router` — endpoints:
  - `GET /api/web/news?category=` → `{news: [{id,title,category,created_at,excerpt}]}` (published เท่านั้น, ใหม่→เก่า)
  - `GET /api/web/news/{id}` → แถวเต็ม (รวม body)
  - `POST /api/web/admin/login` body `{secret}` → เทียบ `get_or_create_admin_secret()` → Set-Cookie `web_admin`
  - `POST/PUT/DELETE /api/web/admin/news[/{id}]` — ต้องมี cookie admin
- `web_api.sign(payload: dict) -> str` / `web_api.verify(token) -> dict|None` — HMAC-SHA256 `base64(json).sig`, มี `exp` epoch ตรวจหมดอายุ, คีย์ = admin secret

**Steps:** เขียนเทสก่อน (`tests/test_web_api.py` ใช้ TestClient บน `license_server.api.app` + fixture monkeypatch path web.db → tmp): admin login ผิด→401 ถูก→cookie · CRUD ข่าวต้องมี cookie (ไม่มี→401) · GET news สาธารณะ · verify ปฏิเสธ token แก้ไข/หมดอายุ → รัน fail → implement → รันผ่าน → commit

### Task 2: gamedata API + โครงเว็บ + หน้าแรก + หน้าข้อมูลเกม

- `GET /api/web/gamedata` → `{continents: [{key,label,arrival_text,monsters:[{name,rank}]}], elements: [{key,label,desc}], themes: [{key,label,description}], invite: <config main_server_invite>}` — จาก `bot.game_data` + `bot.game_modifiers.ELEMENTS` + config.json(fallback example)
- `license_server/api.py`: `include_router(web_api.router)` + `mount("/assets", StaticFiles(assets dir))` + `mount("/", StaticFiles(web_static, html=True))` **หลัง router ทั้งหมด**
- `style.css`: design tokens ตาม Global Constraints + navbar/footer/การ์ด/ปุ่ม/hero ใช้ร่วมทุกหน้า
- `index.html`: navbar (โลโก้ · หน้าแรก · ข่าวสาร · ข้อมูลเกม · เติมเกม · โปรไฟล์) / hero (ชื่อเกม + คำโปรย + ปุ่ม "เข้าเล่นใน Discord"=invite + "อ่านข่าว") พื้นหลังภาพ `/assets/events/arrival_main.png` แบบ pixelated / แถวข่าวล่าสุด 3 ใบ (fetch) / การ์ดจุดเด่น 4 ใบ (ผจญภัย 9 ทวีป=arrival_*, บอส=unbeatable_summon, กิลด์วอร์=theme_faction_war, ตลาด=theme_black_market) / footer (ติดต่อ·เมนู·Discord)
- `game.html`: 3 ส่วนจาก gamedata — ทวีป (การ์ดภาพ arrival + มอนในทวีป) · ธาตุ 7 · ธีมสัปดาห์ (ภาพ theme_*)
- `web.js`: ตัวช่วยร่วม `api()`, `esc()`, mini-markdown (`# ## **b** *i* - list [ลิงก์](url) ![รูป](url) \n`), navbar active, แสดงสถานะล็อกอิน
- เทส: gamedata ครบ 9 ทวีป 7 ธาตุ 13 ธีม · GET `/` ได้ 200 html · commit

### Task 3: หน้าข่าว + หน้าแอดมิน

- `news.html`: แถบกรองหมวด (ทั้งหมด/📢/🛠️/🎪) + ลิสต์การ์ด → คลิกอ่านเต็ม (`?id=` render markdown)
- `admin.html`: ฟอร์ม secret → เข้าแล้วเห็น ตารางข่าว (เพิ่ม/แก้/ลบ — textarea markdown + ปุ่มดูตัวอย่าง) และคิวเติมเงิน (Task 6 เติม tbody ทีหลัง — วางโครง section ไว้เลย)
- commit

### Task 4: ล็อกอิน Discord (device-code) + cog บอท

- API: `POST /api/web/login/code` → `{code}` (A-Z0-9 6 ตัว, หมดอายุ 5 นาที) · `GET /api/web/login/status?code=` → `{status: waiting|ok}` — ok = แถวถูก bot เติม discord_id แล้ว → Set-Cookie `web_session` (sign {uid, exp:+30วัน}) + mark used · โค้ดผิด format/หมดอายุ/ใช้แล้ว → 400
- `GET /api/web/me/session` → `{discord_id}` หรือ 401 (ให้ navbar โชว์สถานะ)
- `bot/cogs/web_link.py`: อยู่ได้เฉพาะ `license_server/` มีจริง (ไม่มี = setup() print ข้ามเงียบ) + `main_server_only()`
  - `!weblogin <โค้ด>`: validate regex → UPDATE login_codes SET discord_id WHERE code=? AND discord_id IS NULL AND expires_at>now → ตอบสำเร็จ/โค้ดหมดอายุ · ลบข้อความผู้ใช้ (privacy best-effort)
  - `!web`: อ่าน `LICENSE_SERVER_URL.txt` → embed ลิงก์เว็บ (ไฟล์ไม่มี/ว่าง → บอกยังไม่เปิดเว็บ)
- `bot/main.py`: โหลด `bot.cogs.web_link` เฉพาะบล็อกเซิร์ฟหลัก
- `login.html`: ปุ่มขอโค้ด → โชว์โค้ดใหญ่ + ปุ่มคัดลอกคำสั่ง + poll สถานะ → สำเร็จ redirect `/me`
- เทส (`test_web_link_cog.py` + เพิ่มใน test_web_api): flow เต็ม (ขอโค้ด → จำลอง bot เขียน discord_id ตรงลง web.db → status ได้ cookie) · โค้ดหมดอายุ/ซ้ำ → 400 · cog: โค้ดถูก/ผิด/หมดอายุ (เรียก logic function ตรง ไม่ต้องรัน discord จริง) · commit

### Task 5: โปรไฟล์ /me

- `GET /api/web/me/profile` (ต้อง web_session): เปิด `PROJECT_ROOT/game_data.db` mode=ro → SELECT จาก players WHERE user_id → `{level, exp, cash, bank, continent(+label จาก CONTINENTS), pet, title, hp, max_hp}` + จำนวน achievement/bestiary (นับจากตารางถ้ามี — ไม่มีตาราง→0) + `topups` 10 รายการล่าสุดของตัวเอง · ไม่พบผู้เล่น → `{new_player: true}`
- `me.html`: การ์ดโปรไฟล์ (แถบ HP/EXP สไตล์เกม) + กระเป๋าเงิน + ประวัติเติมเงิน + ปุ่มไป /topup
- เทส: ไม่ล็อกอิน 401 · ล็อกอินแล้วเห็นค่าตรงกับ DB จำลอง (สร้าง game_data.db ชั่วคราวใน tmp + monkeypatch path) · commit

### Task 6: เติมเงินผ่านเว็บ

- `POST /api/web/topup` (ต้องล็อกอิน) body `{amount_thb}` → ตรวจ 0 < amount, min/max จาก config payment → gold = amount × exchange_rate → INSERT topups(pending) → `{id, gold, qr}` โดย qr = base64 PNG จาก `bot.promptpay.build_qr_png(promptpay_id, amount)` (ไม่ตั้ง promptpay id ใน config → 400 "ยังไม่เปิดรับเติมเงิน")
- `GET /api/web/admin/topups?status=pending` (admin) · `POST /api/web/admin/topups/{id}/approve|reject` body `{note}`:
  - approve ใน transaction เดียว: `UPDATE topups SET status='approved',decided_at,decided_by WHERE id=? AND status='pending'` — **rowcount==0 → 409 (กันอนุมัติซ้ำ)** → สำเร็จค่อย `UPDATE players SET bank=bank+? WHERE user_id=?` บน game_data.db (เขียนจุดเดียว, busy_timeout)
- `topup.html`: ยังไม่ล็อกอิน → อธิบายวิธี + ปุ่มไปล็อกอิน · ล็อกอินแล้ว → ฟอร์มจำนวน → โชว์ QR + เลขรายการ + สถานะ
- `admin.html`: เติม tbody คิวเติมเงิน + ปุ่มอนุมัติ/ปฏิเสธ
- เทส: สร้าง→pending+QR · approve→bank เพิ่มถูกคนถูกจำนวน · **approve ซ้ำ→409 bank ไม่เพิ่มซ้ำ** · reject→bank เท่าเดิม · ติดลบ/เกิน max→400 · ไม่ล็อกอิน→401 · commit

### Task 7: ปุ่ม GUI + ปิดงาน

- `keygen_gui.py`: ปุ่ม "🌐 เปิดเว็บไซต์" ใน btn_row (~บรรทัด 85) → `webbrowser.open(self.tunnel_var.get() or f"http://localhost:{PORT}")`
- เพิ่มหัวข้อเว็บใน `docs/live-test-checklist.md` (เปิดเว็บจาก GUI/!web · ล็อกอิน · เติมเงิน+อนุมัติ · แก้ข่าว)
- รันเทสทั้งโปรเจ็ค → เขียวหมด → commit ปิดงาน + อัปเดต memory

## Self-Review Notes

- Spec ครบ: หน้า 7 หน้า ✓(T2,3,4,5,6) ล็อกอิน ✓(T4) เติมเงิน+audit ✓(T6) ปุ่ม 2 ที่ ✓(T4 !web, T7 GUI)
- จุดเสี่ยงที่ต้องดูของจริงตอนทำ: import bot.game_data ใน license_server (discord ไม่ถูก import — game_data ไม่ import discord ✓ แต่ game_modifiers import game_data เฉยๆ ✓) · ELEMENTS อยู่ game_modifiers (import discord? — game_modifiers ไม่ import discord ✓)
- Windows sqlite ข้ามโปรเซส (บอทเขียน login_codes ขณะ web อ่าน) — ใช้ busy_timeout ทั้งสองฝั่ง
