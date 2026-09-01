# ย้ายขึ้นคลาวด์ Oracle Cloud (ฟรีถาวร) — คู่มือทีละขั้น

รันบอท + เว็บเกม 24 ชม. ไม่ต้องเปิดคอมทิ้งไว้ · **ค่าใช้จ่าย 0 บาท**

---

## ⚠️ อ่านก่อน — กันโดนเรียกเก็บเงิน

Oracle ให้ฟรีจริง แต่**ตัดเงินอัตโนมัติถ้าเผลอใช้เกิน** — บัตรที่ผูกไว้ไม่ได้มีไว้เฉยๆ

### ลิมิตของฟรี (Always Free)

| | ได้ฟรี | เกมนี้ใช้จริง |
|---|---|---|
| เครื่อง ARM (Ampere) | 4 OCPU / 24 GB | ~0.3 OCPU / 320 MB |
| ดิสก์ | 200 GB | ~1 GB |
| **เน็ตขาออก** | **10 TB/เดือน** | ~10 GB/เดือน (**0.1%**) |
| IP สาธารณะ | 2 อัน | 1 อัน |

เกมนี้ใช้ทรัพยากรน้อยมาก ไม่มีทางชนลิมิตจากการใช้งานปกติ

### 🔴 จุดที่คนโดนเก็บเงินจริง

**1. เผลอกด "Upgrade to Paid"** ← สาเหตุอันดับ 1
Oracle เด้งป็อบอัปชวนอัปเกรดบ่อยมาก **กดแล้วกดกลับไม่ได้** ของที่เคยฟรีจะเริ่มคิดเงินทันที

**2. สร้างเครื่องผิด shape**
ต้องเป็น `VM.Standard.A1.Flex` เท่านั้น และต้องมีป้ายเขียว **"Always Free-eligible"**
ถ้าไม่มีป้าย = เสียเงิน

**3. ช่วง Free Trial 30 วันแรก**
ตอนสมัครได้เครดิต $300 ใช้ 30 วัน — ช่วงนี้ถ้าเผลอสร้างของที่ไม่ฟรี
มันจะหักเครดิตเงียบๆ พอครบ 30 วันของนั้นจะโดนลบหรือเริ่มคิดเงิน

### ✅ ทำ 3 ข้อนี้ปลอดภัย

1. **ตั้ง Budget Alert** — Billing → Budgets → ตั้ง $1 ให้เมลเตือน เกิน 1 ดอลลาร์รู้ทันที
2. **ห้ามกด "Upgrade to Paid Account"** ไม่ว่าป็อบอัปจะชวนแค่ไหน
3. **เช็ค Billing → Cost Analysis เดือนละครั้ง** ต้องเป็น **$0.00** ตลอด

### 🟡 ความเสี่ยงอีกอย่าง: โดนยึดเครื่องคืน

บัญชีฟรีล้วน ถ้าเครื่อง "ไม่ได้ใช้งาน" — CPU < 20% + เน็ตน้อย + RAM ต่ำ **ติดกัน 7 วัน**
Oracle มีสิทธิ์ยึดคืน (มีเมลเตือนก่อน ไม่ลบทันที)

บอทออนไลน์ตลอดช่วยได้ระดับหนึ่ง แต่ถ้าไม่มีคนเล่นเลยก็มีโอกาสเข้าเกณฑ์
ถ้าโดนยึด ข้อมูลอยู่ครบถ้ามี backup (ดูหัวข้อ backup ข้างล่าง)

---

## ขั้น 3 — สร้างเครื่องบน Oracle Cloud

1. เข้า cloud.oracle.com → เมนู ☰ → **Compute** → **Instances** → **Create instance**
2. ตั้งค่า:
   - **Image**: Ubuntu 24.04 (กด Edit → Change image)
   - **Shape**: กด Change shape → เลือก **Ampere** → `VM.Standard.A1.Flex`
     - OCPU **4** · Memory **24 GB** ← ฟรีทั้งหมด
   - **Region**: Singapore (ping มาไทยดีสุด)
3. **SSH keys** → Save private key ⚠️ **โหลดเก็บไว้ ไม่งั้นเข้าเครื่องไม่ได้ตลอดกาล**
4. กด Create → รอ ~2 นาที → จด **Public IP**

> เจอ "Out of capacity"? = เซิร์ฟเวอร์ฟรีเต็ม ลองใหม่วันหลัง หรือเปลี่ยน region

### เปิดพอร์ต (ลืมข้อนี้ = เข้าเว็บไม่ได้)

**ในหน้า Oracle**: Instance → Subnet → Security List → Add Ingress Rules
- Source `0.0.0.0/0` · TCP · **80**
- Source `0.0.0.0/0` · TCP · **443**

**ในเครื่อง** (Oracle มี firewall ซ้อนอีกชั้น):
```bash
sudo iptables -I INPUT 1 -p tcp --dport 80 -j ACCEPT
sudo iptables -I INPUT 1 -p tcp --dport 443 -j ACCEPT
sudo netfilter-persistent save
```

---

## ขั้น 4 — โดเมนฟรี + ลง Docker

### DuckDNS (ฟรีตลอด)
1. เข้า duckdns.org → ล็อกอินด้วย Google
2. ตั้งชื่อ เช่น `fragmentrift` → กด add domain
3. ช่อง **current ip** ใส่ Public IP ของเครื่อง → กด update
4. ได้ลิงก์: `fragmentrift.duckdns.org`

### ต่อเข้าเครื่อง + ลง Docker
```bash
ssh -i คีย์ที่โหลดมา ubuntu@PUBLIC_IP

curl -fsSL https://get.docker.com | sudo sh
sudo usermod -aG docker ubuntu
exit          # ออกแล้วเข้าใหม่ ให้สิทธิ์มีผล
```

---

## ขั้น 5 — เอาโปรเจ็คขึ้น + เปิดจริง

```bash
ssh -i คีย์ ubuntu@PUBLIC_IP
git clone <URL repo ของคุณ> game && cd game

cp .env.example .env
nano .env        # ใส่ค่าจริง (ดูข้างล่าง) → Ctrl+O, Enter, Ctrl+X
```

**ค่าใน `.env`:**
| ช่อง | ใส่อะไร |
|---|---|
| `DISCORD_BOT_TOKEN` | โทเค็นบอท (ก๊อปจาก `config.json` เดิม) |
| `ADMIN_SECRET` | รหัสเข้าหลังบ้าน — **ตั้งใหม่ให้ยาว** |
| `DOMAIN` | `fragmentrift.duckdns.org` |

**ย้ายข้อมูลผู้เล่นขึ้นไป** (รันบนเครื่อง Windows ของคุณ):
```bash
scp -i คีย์ game_data.db ubuntu@PUBLIC_IP:~/game/data/
```

**เปิดระบบ:**
```bash
mkdir -p data
docker compose up -d --build     # ครั้งแรกนาน ~5 นาที
docker compose logs -f           # ดู log (Ctrl+C ออก ระบบยังรันต่อ)
```

เปิด `https://fragmentrift.duckdns.org` ได้เลย — HTTPS ออกให้อัตโนมัติ

---

## backup อัตโนมัติ ⚠️ ต้องทำ

ข้อมูลผู้เล่นอยู่บนคลาวด์แล้ว เครื่องพังทีเดียวหายหมด

```bash
mkdir -p ~/backups
crontab -e
```
ใส่บรรทัดนี้ (backup ทุกวันตี 3 เก็บ 14 วัน):
```
0 3 * * * cd ~/game && sqlite3 data/game_data.db ".backup ~/backups/game-$(date +\%Y\%m\%d).db" && find ~/backups -name "game-*.db" -mtime +14 -delete
```

โหลด backup ลงเครื่องตัวเอง:
```bash
scp -i คีย์ ubuntu@PUBLIC_IP:~/backups/*.db ./
```

---

## คำสั่งที่ใช้บ่อย

| อยากทำ | คำสั่ง |
|---|---|
| ดู log สด | `docker compose logs -f` |
| รีสตาร์ท | `docker compose restart` |
| อัปเดตโค้ดใหม่ | `git pull && docker compose up -d --build` |
| ปิดบอทชั่วคราว | แก้ `.env` เป็น `RUN_BOT=0` แล้ว `docker compose up -d` |
| เช็คสถานะ | `docker compose ps` |

## เจอปัญหา

| อาการ | แก้ |
|---|---|
| เข้าเว็บไม่ได้ | ลืมเปิดพอร์ต 80/443 (ทั้ง 2 ที่ในขั้น 3) |
| HTTPS ไม่ขึ้น | DuckDNS ยังชี้ IP ไม่ถูก — เช็คที่ duckdns.org |
| บอทไม่ออนไลน์ | `docker compose logs game` ดู error โทเค็น |
| ข้อมูลหาย | ลืม `GAME_DB_PATH` ชี้เข้า `/app/data` — เช็ค `docker compose config` |
