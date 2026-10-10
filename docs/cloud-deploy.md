# ย้ายขึ้นคลาวด์ Oracle Cloud (ฟรีถาวร) — คู่มือทีละขั้น

รันบอท + เว็บเกม 24 ชม. ไม่ต้องเปิดคอมทิ้งไว้ · **ค่าใช้จ่าย 0 บาท**

---

## ⚠️ อ่านก่อน — กันโดนเรียกเก็บเงิน

> **อัปเดต 2026-10-10:** Oracle **ลดโควตาเครื่อง ARM ฟรีลงครึ่งหนึ่ง** เมื่อ 15 มิ.ย. 2026 (เงียบ ๆ ไม่ประกาศ)
> จาก 4 OCPU / 24 GB เหลือ **2 OCPU / 12 GB** — คู่มือฉบับเก่าที่บอก 4/24 **ใช้ไม่ได้แล้ว**
> ที่มา: [Always Free Resources (docs.oracle.com)](https://docs.oracle.com/en-us/iaas/Content/FreeTier/freetier_topic-Always_Free_Resources.htm)
> · [InfoQ](https://infoq.com/news/2026/07/oracle-cloud-free-tier-limits/) · [Linuxiac](https://linuxiac.com/oracle-quietly-cuts-free-tier-ampere-a1-resources-in-half/)
> Oracle เปลี่ยนเงื่อนไขได้โดยไม่บอก → ก่อนสร้างเครื่องให้เปิดลิงก์แรกเช็คตัวเลขอีกรอบเสมอ

### กฎข้อเดียวที่ทำให้ไม่โดนเก็บเงิน: **อยู่บัญชี Free Tier ห้ามอัปเกรด**

| บัญชี | ใช้เกินโควตาฟรีแล้วเกิดอะไร |
|---|---|
| **Free Tier (ไม่อัปเกรด)** ✅ | ใช้เกินไม่ได้ — ของที่เกินถูกหยุด/สร้างไม่ได้ **ไม่มีบิล** |
| Pay As You Go (อัปเกรดแล้ว) ❌ | ของ Always Free ยังฟรี แต่**ส่วนที่เกินโดนคิดเงินเข้าบัตร** |

ตอนลด 4/24 → 2/12 บัญชีฟรีล้วนแค่โดนปิดเครื่อง ส่วนบัญชีที่อัปเกรดแล้วมีความเสี่ยงโดนคิดเงินส่วนเกิน
— Oracle เด้งป็อบอัปชวนอัปเกรดบ่อย **อย่ากด** · ช่วงทดลอง 30 วันแรกมีเครดิต $300
ถ้าเผลอสร้างของไม่ฟรีจะกินเครดิต (ไม่ใช่บัตร) พอหมดช่วงทดลองของพวกนั้นจะถูกหยุด/ลบ

### ลิมิตของฟรี (Always Free) — ตัวเลข ณ 2026-10

| | ได้ฟรี | เกมนี้ใช้จริง |
|---|---|---|
| เครื่อง ARM (`VM.Standard.A1.Flex`) | **2 OCPU / 12 GB รวมทุกเครื่อง** (1-2 เครื่อง) | ~0.3 OCPU / 320 MB |
| ดิสก์ (boot + block รวม) | 200 GB · backup ได้ 5 ชุด | ~1 GB (boot volume ค่าเริ่มต้น 50 GB) |
| **เน็ตขาออก** | **10 TB/เดือน** | ~10 GB/เดือน (**0.1%**) |

ทุกอย่างต้องสร้างใน **home region** (เลือกตอนสมัคร เปลี่ยนทีหลังไม่ได้) — Oracle ไม่มี region ในไทย → เลือก **Singapore**

### 🔴 ห้ามทำ

1. **กด "Upgrade to Paid / Pay As You Go"** — ไม่ว่าป็อบอัปจะชวนแค่ไหน
2. **สร้างเครื่องที่ไม่มีป้ายเขียว "Always Free-eligible"** หรือรวมทุกเครื่องเกิน 2 OCPU / 12 GB
3. **เพิ่ม Block Volume / เปิด Backup Policy อัตโนมัติ / Reserved IP / Load Balancer เพิ่ม** — เกมนี้ไม่ต้องใช้สักอย่าง
   (IP สาธารณะแบบ ephemeral ที่ติดมากับเครื่องพอแล้ว · backup ใช้ cron ในเครื่องตามหัวข้อข้างล่าง)

### ✅ ทำ 3 ข้อนี้ทุกครั้ง

1. **ตั้ง Budget Alert** — Billing → Budgets → ตั้ง $1 ให้เมลเตือน เกิน 1 ดอลลาร์รู้ทันที
2. **ตอนสร้างเครื่องดูป้าย "Always Free-eligible"** ทั้ง shape และ image
3. **เช็ค Billing → Cost Analysis เดือนละครั้ง** ต้องเป็น **$0.00** ตลอด

### 🟡 ความเสี่ยงอีกอย่าง: โดนยึดเครื่องคืนเพราะ "ว่าง"

Oracle ถือว่าเครื่องว่างถ้า **ทั้ง 3 ข้อจริงพร้อมกัน ติดกัน 7 วัน**:
CPU (p95) < 20% · เน็ต < 20% · **RAM < 20%** (เฉพาะเครื่อง ARM)

เกมนี้ CPU กับเน็ตต่ำแน่ ๆ → **กันด้วย RAM**: ตั้งเครื่องแค่ **2 GB**
(ระบบ + Docker + เกม ≈ 700 MB = ~35% ไม่เข้าเกณฑ์) · ถ้าตั้ง 12 GB เต็ม จะใช้แค่ ~6% → เข้าเกณฑ์ว่าง
ถ้าโดนยึด ข้อมูลอยู่ครบถ้ามี backup (ดูหัวข้อ backup ข้างล่าง)

---

## ขั้น 3 — สร้างเครื่องบน Oracle Cloud

1. เข้า cloud.oracle.com → เมนู ☰ → **Compute** → **Instances** → **Create instance**
2. ตั้งค่า:
   - **Image**: Ubuntu 24.04 (กด Edit → Change image)
   - **Shape**: กด Change shape → เลือก **Ampere** → `VM.Standard.A1.Flex` (ต้องมีป้าย Always Free-eligible)
     - OCPU **1** · Memory **2 GB** ← อยู่ในโควตาฟรี และ RAM ไม่ต่ำจนโดนยึดเครื่อง (ดูหัวข้อบน)
     - ❌ **ห้ามตั้ง 4 OCPU / 24 GB** ตามคู่มือเก่า — เกินโควตาฟรีแล้ว
   - **Boot volume**: ใช้ค่าเริ่มต้น 50 GB ไม่ต้องแก้
   - **Region**: Singapore (ต้องเป็น home region ที่เลือกตอนสมัคร)
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

# RAM 2 GB — เพิ่ม swap 2 GB กันตอน build ครั้งแรกแรมไม่พอ (ฟรี ใช้ดิสก์เครื่องเอง)
sudo fallocate -l 2G /swapfile && sudo chmod 600 /swapfile
sudo mkswap /swapfile && sudo swapon /swapfile
echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab
exit          # ออกแล้วเข้าใหม่ ให้สิทธิ์มีผล
```

---

## ขั้น 5 — เอาโปรเจ็คขึ้น + เปิดจริง

```bash
ssh -i คีย์ ubuntu@PUBLIC_IP
# งานล่าสุดอยู่สาขา feat/party-rpg (ยังไม่เข้า main) — repo เป็น private ต้องใช้ GitHub token แทนรหัสผ่าน
git clone -b feat/party-rpg https://github.com/phumapanther/mmorpg-bot-manager.git game && cd game

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
