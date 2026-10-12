# รันบน Synology NAS (เบื้องหลัง 24 ชม. · ไม่กระทบ User คนอื่น)

รันบอท + เว็บเกมเป็น container บน NAS — **ไม่มีหน้าต่าง/เทอร์มินัลโผล่, ไม่ต้องรีบูต NAS, ไม่เปิดพอร์ต**
ลิงก์เว็บใช้ Cloudflare Quick Tunnel (สุ่ม ฟรี · เปลี่ยนทุกครั้งที่รีสตาร์ต)

> ทดสอบกับ DS720+ · DSM 7.2 · RAM 2 GB — container กินจริง ~90 MB (ล็อกเพดาน 512 MB)

---

## 0. กันไม่ให้ User คนอื่นเห็น/แตะ — อ่านก่อน

- **Container Manager เป็นแอปเฉพาะแอดมิน** — User ที่ไม่ได้อยู่กลุ่ม `administrators` เปิดไม่ได้ มองไม่เห็น container
- **เก็บไฟล์โปรเจกต์ในโฟลเดอร์เฉพาะแอดมิน** — สร้าง Shared Folder ใหม่ชื่อ `docker` (หรือใช้ของเดิม) แล้ว
  Control Panel → Shared Folder → เลือก `docker` → Edit → **Permissions** → เอาสิทธิ์ของ User/กลุ่มอื่นออกให้หมด เหลือเฉพาะคุณ
- **อยากให้ไฟล์อ่านไม่ออกแม้แต่แอดมินคนอื่น** — ตอนสร้าง Shared Folder ติ๊ก **Encrypt this shared folder** ตั้ง key เอง
  (ไฟล์ตอน unmount จะเป็นขยะอ่านไม่ออก · แต่ตอน container รันต้อง mount ไว้)
- ⚠️ **ซ่อน container จากแอดมินคนอื่นไม่ได้** — ใครอยู่กลุ่ม administrators ก็เห็นใน Container Manager
  ทางเดียวที่ซ่อนได้คือย้ายเขาออกจากกลุ่ม administrators

---

## 1. เตรียมไฟล์ (ทำบนเครื่อง Windows ของคุณ)

จากโฟลเดอร์โปรเจกต์ บีบไฟล์ที่ต้องขึ้น NAS (ไม่เอา .git, data, ของ build):

```powershell
# ใน PowerShell ที่โฟลเดอร์โปรเจกต์
git archive --format=zip -o "$env:USERPROFILE\Downloads\fragmentrift.zip" HEAD
```

> ใช้ `git archive` เพื่อได้โค้ดสะอาดตาม git — ไม่ติด `config.json`, `.env`, `*.db`, backups ขึ้นไป

---

## 2. ลง Container Manager + วางไฟล์

1. DSM → **Package Center** → ค้น **Container Manager** → Install
2. **File Station** → ในโฟลเดอร์ `docker` สร้างโฟลเดอร์ `fragmentrift`
3. อัปโหลด `fragmentrift.zip` เข้าไป → คลิกขวา → **Extract here**
4. เข้าไปในโฟลเดอร์ `fragmentrift` ให้เห็น `Dockerfile`, `docker-compose.nas.yml` อยู่ชั้นนอกสุด

---

## 3. สร้างไฟล์ค่าลับ `.env`

File Station → เข้าโฟลเดอร์ `fragmentrift` → Create → **Create file** ชื่อ `.env` → แก้ไข ใส่:

```
DISCORD_BOT_TOKEN=<โทเค็นบอท — ก๊อปจาก config.json เดิม ช่อง bot_token>
ADMIN_SECRET=<รหัสหลังบ้าน ยาว ≥24 ตัว — ดูวิธีสร้างข้างล่าง>
RUN_BOT=1
```

**สร้าง ADMIN_SECRET** (ต้อง ≥24 ตัว ไม่งั้นระบบไม่ยอมเปิด) — รันในเครื่องไหนก็ได้:
```powershell
python -c "import secrets; print(secrets.token_hex(24))"
```
คัดลอกค่าที่ได้มาใส่ · **ถ้ามี `DISCORD_GUEST_TOKEN` / `LICENSE_KEY` เดิมใน config.json ใส่เพิ่มได้**

> ตั้งสิทธิ์ไฟล์: คลิกขวา `.env` → Properties → Permission → เหลือเฉพาะเจ้าของอ่าน/เขียน

---

## 4. ย้ายข้อมูลผู้เล่นขึ้นไป (ถ้ามีของเดิม)

⚠️ **ปิดบอทที่รันบนเครื่องคุณก่อน** — ไม่งั้นบอท 2 ตัวใช้โทเค็นเดียวกัน ข้อมูลผู้เล่นจะแตกเป็น 2 ชุด

1. ใน `fragmentrift` สร้างโฟลเดอร์ `data`
2. อัปโหลด `game_data.db` เดิมเข้า `data/`
3. (ถ้ามี) `license_server/web.db`, `license_server/licenses.db`, โฟลเดอร์ `web_uploads` → เข้า `data/` เช่นกัน

> ฐานข้อมูลทั้งหมดอยู่ใน `data/` ซึ่ง mount เป็น volume — **build ใหม่กี่ครั้งข้อมูลไม่หาย**

---

## 5. เปิดระบบ

Container Manager → **Project** → **Create**
- **Project name:** `fragmentrift`
- **Path:** เลือกโฟลเดอร์ `docker/fragmentrift`
- **Source:** เลือก **Use existing docker-compose.yml** → ชี้ไป `docker-compose.nas.yml`
- กด **Next** → **Build** (ครั้งแรกนาน ~5 นาที)

เสร็จแล้วแท็บ **Container** จะเห็น `fragmentrift-game-1` กับ `fragmentrift-tunnel-1` เป็น **Running**

---

## 6. เอาลิงก์เว็บไปใช้

ลิงก์สุ่มของ Cloudflare อยู่ใน log — Container Manager → `fragmentrift-game-1` → **Log** → หาบรรทัด:
```
🌐 ลิงก์เว็บใหม่: https://xxxx-xxxx.trycloudflare.com
```
บอทจะหยิบลิงก์นี้ไปตอบ `!web` / `!login` ให้เอง · **ลิงก์เปลี่ยนทุกครั้งที่รีสตาร์ต tunnel** บอทตามให้อัตโนมัติภายใน 30 วิ

> อยากได้ลิงก์ถาวร (ไม่เปลี่ยน) ต้องมีโดเมน + named tunnel — บอกได้ ผมทำให้

---

## 7. ตรวจว่าใช้ได้

- [ ] บอทขึ้นออนไลน์ใน Discord
- [ ] พิมพ์ `!web` ในดิส → ได้ลิงก์ → เปิดเว็บได้
- [ ] `!login` → กดปุ่ม → เข้าโปรไฟล์ได้ (ยืนยันว่าบอทกับเว็บใช้ web.db ไฟล์เดียวกัน)
- [ ] หน้า `/admin` เข้าด้วย ADMIN_SECRET ได้

---

## คำสั่งที่ใช้บ่อย (Container Manager)

| อยากทำ | ทำยังไง |
|---|---|
| ดู log สด | Container → game → Log |
| รีสตาร์ท | Project → fragmentrift → Action → Restart |
| อัปเดตโค้ดใหม่ | อัปโหลดไฟล์ทับ → Project → Build ใหม่ (ข้อมูลใน data/ ไม่หาย) |
| ปิดชั่วคราว | Project → Action → Stop |

## เจอปัญหา

| อาการ | แก้ |
|---|---|
| container ไม่ขึ้น ดับทันที | Log ขึ้น `❌ ADMIN_SECRET ยังไม่ปลอดภัย` = รหัสใน .env สั้นกว่า 24 ตัว |
| บอทไม่ออนไลน์ | Log ขึ้น error โทเค็น — เช็ก `DISCORD_BOT_TOKEN` ใน .env |
| `!web` เงียบ/ลิงก์ว่าง | รอ 30 วิให้ tunnel ขึ้น · เช็ก log ตู้ `fragmentrift-tunnel-1` ว่าขึ้นลิงก์ `trycloudflare.com` แล้ว |
| ข้อมูลผู้เล่นหายหลัง build | ลืมวาง `game_data.db` ใน `data/` ก่อน build — ดูข้อ 4 |
