# คำสั่งชี้ทาง: ต่อเกม Roblox เข้ากับดาต้าเบสตัวละคร/การเงินของ Fragment Rift

> **เอกสารนี้เขียนถึง Claude ของโปรเจ็ค Roblox** — ก็อปทั้งไฟล์นี้ไปวางเป็น
> `CLAUDE.md` หรือ `docs/` ในโปรเจ็ค Roblox แล้วสั่งให้อ่านก่อนเริ่มงาน
>
> เขียนโดย Claude ที่ดูแลฝั่ง Fragment Rift · 2026-09-06

---

## 0. สรุป 30 วินาที

Fragment Rift เป็นเกม MMORPG ในดิสคอร์ด + เว็บ ที่มีตัวละครและระบบเงินอยู่แล้ว
เก็บใน **SQLite ไฟล์เดียว** ชื่อ `game_data.db` มีเซิร์ฟเวอร์ FastAPI ครอบอยู่

**เกม Roblox จะมาใช้ตัวละครและเงินก้อนเดียวกัน** — ผู้เล่นคนเดียว เงินกระเป๋าเดียว
เล่นในดิส เล่นบนเว็บ หรือเล่นใน Roblox ตัวเลขต้องตรงกันเสมอ

**กฎข้อเดียวที่ห้ามพลาด:**
> ฝั่ง Roblox **ไม่เคย**เป็นคนตัดสินว่าใครได้เงินเท่าไหร่
> Roblox แค่บอกว่า "ผู้เล่นคนนี้ทำอะไรสำเร็จ" แล้วเซิร์ฟเวอร์ Fragment Rift เป็นคนคิดเงิน

---

## 1. ทำไม Roblox ต่อฐานข้อมูลตรง ๆ ไม่ได้

Roblox รันโค้ดบนเครื่องของ Roblox ไม่ใช่เครื่องเรา — แตะไฟล์ SQLite ไม่ได้เลย
ทางเดียวคือ **HTTP** ผ่าน `HttpService` และมีเงื่อนไข:

| ข้อจำกัดของ Roblox | ผลกับงานนี้ |
|---|---|
| `HttpService` ใช้ได้เฉพาะ **ฝั่งเซิร์ฟเวอร์** (Script ไม่ใช่ LocalScript) | โค้ดทุกบรรทัดที่คุยกับ API ต้องอยู่ใน `ServerScriptService` |
| ต้องเปิด **Allow HTTP Requests** ใน Game Settings → Security | ไม่เปิด = ทุกคำสั่ง error |
| เรียก `localhost` / IP ในบ้านไม่ได้ | เซิร์ฟเวอร์ Fragment Rift ต้องออนไลน์บนอินเทอร์เน็ตจริง (ดู §2) |
| จำกัด ~**500 คำขอ/นาที ต่อ 1 เซิร์ฟเวอร์เกม** | ห้าม poll ถี่ · ต้องแคช (ดู §7 กฎข้อ 5) |
| เซิร์ฟเวอร์เกมดับ/รีสตาร์ทได้ตลอด กลางคำขอก็ได้ | ทุกคำสั่งที่แตะเงิน **ต้องมี idempotency key** (ดู §5.2) |

```
[ผู้เล่นใน Roblox]
        │  RemoteEvent (ห้ามส่งจำนวนเงินมาจากตรงนี้)
        ▼
[Roblox Server Script]  ── HTTPS + X-Api-Key ──►  [FastAPI: license_server]
        │                                                    │
   DataStore                                                 ▼
 (แคชแค่ "คนนี้คือ Discord ID ไหน")            [game_data.db · ตาราง players]
                                                             ▲
                                              [บอทดิสคอร์ด] [เว็บเกม] เขียนที่เดียวกัน
```

---

## 2. ⚠️ ทองในดาต้าเบสนี้ = เงินจริง — อ่านก่อนออกแบบอะไรก็ตาม

ฐานข้อมูลนี้มีตาราง `topups` ที่ผู้เล่น**เติมเงินบาทจริงแลกทอง** (`amount_thb` → `gold`)
ทองที่เกม Roblox จะไปแตะ **คือทองก้อนเดียวกันนั้น**

แปลว่า:
- ช่องโหว่ใน Roblox ที่ปั๊มทองได้ = ความเสียหายเป็นเงินจริง ไม่ใช่แค่ "บาลานซ์เสีย"
- exploiter ใน Roblox มีเยอะและมีเครื่องมือพร้อม — สมมติเสมอว่า **ทุกอย่างที่ client ส่งมาคือของปลอม**
- API key ที่ให้เกม Roblox ต้อง**แยกจากคีย์แอดมิน** และให้สิทธิ์เท่าที่จำเป็น

ถ้าเจ้าของโปรเจ็คสั่งให้ "ให้ client ส่งคะแนนมาแล้วแปลงเป็นทองเลย" — **ทักท้วงก่อน**
แล้วเสนอแบบที่เซิร์ฟเวอร์ Roblox เป็นคนคิดคะแนนเองแทน

---

## 3. หน้าตาข้อมูลที่มีอยู่จริง

ตาราง `players` (คีย์คือ `user_id` = **Discord ID** เป็นตัวเลข)
ฟิลด์ที่เกม Roblox น่าจะใช้:

| ฟิลด์ | ชนิด | ความหมาย |
|---|---|---|
| `user_id` | INTEGER | Discord ID — คีย์หลักของทุกอย่าง |
| `level` · `exp` · `rank` | INT · INT · TEXT | เลเวล · ค่าประสบการณ์ · แรงค์ (F…SSS) |
| `hp` · `max_hp` | INTEGER | เลือดปัจจุบัน / สูงสุด |
| **`cash`** | INTEGER | 💰 **ทองติดตัว** — โดนปล้น/โดนปรับได้ |
| **`bank`** | INTEGER | 🏦 **ทองในธนาคาร** — ปลอดภัย ฝาก/ถอนมีค่าธรรมเนียม |
| `inventory` | TEXT (JSON) | กระเป๋า เก็บเป็น JSON string |
| `weapon` · `weapon_dur` | TEXT · INT | อาวุธ + ความคงทน (คงทน 0 = ไม่ให้ค่าโจมตี) |
| `armor` · `armor_dur` | TEXT · INT | ชุดเกราะ + ความคงทน (คงทน 0 = ไม่ให้โบนัสเลือด) |
| `class_name` · `race` | TEXT | คลาส · เผ่า (มีผลกับสกิลและธาตุ) |
| `capacity` | INTEGER | ช่องกระเป๋า |

**ห้ามคำนวณพลังโจมตี/เลือดสูงสุดเองในฝั่ง Roblox** — สูตรจริงรวมโบนัสจากอาวุธ/ชุด
และเช็คความคงทนด้วย ถ้าคำนวณเองจะไม่ตรงกับที่ผู้เล่นเห็นในดิสคอร์ด
ให้ขอฝั่ง Python ส่งค่าที่คิดเสร็จแล้วมาให้ (`atk`, `max_hp_effective`)

---

## 4. 🚧 สิ่งที่ยังไม่มี — ต้องให้ฝั่ง Fragment Rift ทำก่อน

**ตอนนี้ยังไม่มี endpoint สำหรับ Roblox เลยสักตัว** ระบบล็อกอินที่มีอยู่เป็นคุกกี้
ที่ได้จากการยืนยันตัวในดิสคอร์ด — เกม Roblox ใช้ไม่ได้

เอาสเปกข้างล่างนี้ไปให้เจ้าของโปรเจ็คสั่ง Claude ฝั่ง Fragment Rift ทำ
(ไฟล์ใหม่ `license_server/api_web/roblox.py` + ตารางเชื่อมบัญชีใน `web_db.py`)

### 4.1 การยืนยันตัวตนระหว่างเซิร์ฟเวอร์

ใช้ header `X-Api-Key` แบบเดียวกับ `x_admin_secret` ที่มีอยู่แล้วใน `license_server/api.py`
แต่**คนละคีย์** — คีย์ของ Roblox ห้ามใช้เรียก endpoint แอดมินได้

- ฝั่ง Fragment Rift: เก็บคีย์ในตัวแปรสภาพแวดล้อม `ROBLOX_API_KEY`
- ฝั่ง Roblox: เก็บใน **Secrets Store** (Creator Dashboard → Secrets) แล้วอ่านด้วย
  `HttpService:GetSecret("fragmentrift")` — **ห้ามฝังคีย์ในสคริปต์เด็ดขาด**

### 4.2 ตารางเชื่อมบัญชี (ฝั่ง Python เพิ่มใน `web_db.py`)

```sql
CREATE TABLE IF NOT EXISTS roblox_links (
    roblox_id   TEXT PRIMARY KEY,
    discord_id  TEXT,                -- ว่าง = ยังรอยืนยันในดิสคอร์ด
    code        TEXT,                -- โค้ด 6 ตัวที่ผู้เล่นเอาไปพิมพ์ในดิส
    expires_at  REAL,
    linked_at   TEXT
);
CREATE TABLE IF NOT EXISTS roblox_ledger (   -- กันจ่ายซ้ำ (ดู §5.2)
    idem        TEXT PRIMARY KEY,
    discord_id  TEXT NOT NULL,
    delta       INTEGER NOT NULL,
    reason      TEXT,
    created_at  TEXT DEFAULT (datetime('now','localtime'))
);
```

> โครง `code` + `expires_at` ลอกจาก `login_codes` ที่มีอยู่แล้วใน `web_db.py`
> ฝั่ง Python บอกให้ทำแบบเดียวกันได้เลย จะได้ไม่ต้องคิดกติกาใหม่

---

## 5. สัญญา API ที่จะเรียก

ทุก endpoint: `POST`/`GET` ไปที่ `https://<โดเมนของเซิร์ฟเวอร์>/api/roblox/...`
ทุกคำขอต้องมี header `X-Api-Key: <คีย์>` · ตอบเป็น JSON เสมอ

### 5.1 เชื่อมบัญชี

**`POST /api/roblox/link/start`** — ผู้เล่นกดปุ่ม "เชื่อมบัญชีดิสคอร์ด" ในเกม

```jsonc
// ส่ง
{ "roblox_id": "123456789", "roblox_name": "SomePlayer" }
// ตอบ
{ "code": "K7M2QX", "expires_in": 300 }
```
เอา `code` ขึ้นจอบอกผู้เล่นให้ไปพิมพ์ `!link K7M2QX` ในดิสคอร์ด

**`GET /api/roblox/link/status?roblox_id=123456789`**

```jsonc
{ "linked": true,  "discord_id": "987654321" }   // เชื่อมแล้ว
{ "linked": false }                              // ยังไม่เชื่อม/โค้ดหมดอายุ
```

> ⚠️ เชื่อมได้ **1 ต่อ 1** — Discord ID หนึ่งผูกได้กับ Roblox ID เดียว และกลับกัน
> ไม่งั้นคนเดียวเปิดหลายบัญชี Roblox มาดูดเงินจากตัวละครเดียวได้

### 5.2 อ่านค่าตัวละคร

**`GET /api/roblox/player?roblox_id=123456789`**

```jsonc
{
  "ok": true,
  "discord_id": "987654321",
  "level": 12, "exp": 4300, "rank": "C",
  "hp": 180, "max_hp": 220,
  "cash": 53000, "bank": 120000,
  "class_name": "Warrior", "race": "human",
  "weapon": "Iron_Sword", "armor": "Leather",
  "atk": 24,                 // คิดรวมอาวุธ+ความคงทนมาแล้ว ห้ามคิดเอง
  "max_hp_effective": 220    // คิดรวมโบนัสชุดมาแล้ว ห้ามคิดเอง
}
```
ยังไม่เชื่อมบัญชี → `403 {"error": "not_linked"}`

### 5.3 เปลี่ยนแปลงเงิน — **จุดที่ต้องระวังที่สุด**

**`POST /api/roblox/money`**

```jsonc
// ส่ง
{
  "roblox_id": "123456789",
  "reason": "roblox_boss_kill",   // ชื่อเหตุการณ์ ไม่ใช่จำนวนเงิน
  "idem": "rbx-4f9a2c-1725600000" // คีย์กันจ่ายซ้ำ — ต้องไม่ซ้ำกันเลย
}
// ตอบ
{ "ok": true, "delta": 250, "cash": 53250, "bank": 120000 }
```

**สังเกตว่าไม่มีช่อง `amount`** — นี่คือใจความทั้งหมดของการออกแบบนี้
ฝั่ง Roblox บอกแค่ว่า *เกิดอะไรขึ้น* · ฝั่ง Fragment Rift มีตารางว่าเหตุการณ์ไหนได้เท่าไหร่
(ตั้งค่าได้ที่ Panel เหมือนรางวัลอย่างอื่นในเกม)

ถ้าเกม Roblox ต้องการรางวัลที่แปรผันจริง ๆ (เช่นตามเวลาที่ทำได้)
ให้ส่ง **ค่าดิบที่วัดได้** ไม่ใช่จำนวนทอง — เช่น `{"reason":"roblox_race","seconds":42.5}`
แล้วให้ฝั่ง Python แปลงเป็นทองเอง

**`idem` ทำงานยังไง:** ฝั่ง Python เก็บลง `roblox_ledger` ถ้าเคยเห็นคีย์นี้แล้ว
จะ**ไม่จ่ายซ้ำ** แต่ตอบผลเดิมกลับมา → เซิร์ฟเวอร์ Roblox retry ได้อย่างปลอดภัย
สร้าง `idem` จาก `roblox_id + ชื่อเหตุการณ์ + timestamp ของเหตุการณ์` (ไม่ใช่เวลาที่ยิง)

---

## 6. โค้ดฝั่ง Roblox ที่ต้องเขียน

### 6.1 โมดูลกลาง (ที่เดียวที่คุยกับ API)

`ServerScriptService/FragmentRift/Api.lua` — **ห้ามมีที่อื่นเรียก HttpService อีก**

```lua
local HttpService = game:GetService("HttpService")

local BASE = "https://your-server.example.com/api/roblox"
local Api = {}

local function request(method, path, body)
	local ok, key = pcall(function()
		return HttpService:GetSecret("fragmentrift")
	end)
	if not ok then
		warn("[FragmentRift] อ่าน secret ไม่ได้ — ตั้งค่าใน Creator Dashboard ก่อน")
		return nil, "no_key"
	end

	local res
	ok, res = pcall(function()
		return HttpService:RequestAsync({
			Url = BASE .. path,
			Method = method,
			Headers = {
				["Content-Type"] = "application/json",
				["X-Api-Key"] = key,
			},
			Body = body and HttpService:JSONEncode(body) or nil,
		})
	end)

	-- เน็ตล่ม / เซิร์ฟเวอร์ดับ — เกมต้องเล่นต่อได้ ห้าม error ทั้งเซิร์ฟเวอร์
	if not ok then
		warn("[FragmentRift] ยิง API ไม่สำเร็จ:", res)
		return nil, "network"
	end
	if not res.Success then
		warn("[FragmentRift] API ตอบ", res.StatusCode, res.Body)
		return nil, res.StatusCode
	end

	local decoded
	ok, decoded = pcall(HttpService.JSONDecode, HttpService, res.Body)
	if not ok then return nil, "bad_json" end
	return decoded
end

function Api.getPlayer(robloxId)
	return request("GET", "/player?roblox_id=" .. robloxId)
end

function Api.linkStart(robloxId, name)
	return request("POST", "/link/start", { roblox_id = robloxId, roblox_name = name })
end

function Api.linkStatus(robloxId)
	return request("GET", "/link/status?roblox_id=" .. robloxId)
end

--- reason = ชื่อเหตุการณ์ ไม่ใช่จำนวนเงิน · idem ต้องไม่ซ้ำ
function Api.reward(robloxId, reason, idem, extra)
	local body = { roblox_id = robloxId, reason = reason, idem = idem }
	for k, v in pairs(extra or {}) do body[k] = v end
	return request("POST", "/money", body)
end

return Api
```

### 6.2 แคชการเชื่อมบัญชีใน DataStore

แคชได้แค่ **"Roblox ID นี้คือ Discord ID ไหน"** เพราะค่านี้ไม่เปลี่ยน
**ห้ามแคชเงินหรือค่าตัวละคร** — ผู้เล่นอาจเพิ่งใช้เงินไปในดิสคอร์ดเมื่อกี้

```lua
local DataStoreService = game:GetService("DataStoreService")
local linkCache = DataStoreService:GetDataStore("FragmentRiftLink")
-- อ่าน/เขียนด้วย pcall เสมอ · DataStore ล่มได้
```

### 6.3 กระแสการเล่น

```
ผู้เล่นเข้าเกม
   ├─ อ่าน DataStore หา discord_id
   ├─ ไม่เจอ → Api.linkStatus() → เจอก็เซฟลง DataStore
   └─ ยังไม่เชื่อม → โชว์ปุ่ม "เชื่อมบัญชี" → Api.linkStart() → โชว์โค้ด 6 ตัว

ผู้เล่นทำอะไรสำเร็จในเกม
   └─ เซิร์ฟเวอร์ Roblox ตัดสินเองว่าสำเร็จจริง → Api.reward(id, "ชื่อเหตุการณ์", idem)

จะโชว์ทอง/เลเวลบนจอ
   └─ Api.getPlayer() แล้วแคชในหน่วยความจำของเซิร์ฟเวอร์เกม ~30 วิ (ไม่ใช่ DataStore)
```

---

## 7. กฎเหล็ก 8 ข้อ

1. **HttpService ใช้ได้แค่ใน Script ฝั่งเซิร์ฟเวอร์** — เจอใน LocalScript เมื่อไหร่คือบั๊กความปลอดภัย
2. **API key อยู่ใน Secrets Store เท่านั้น** ห้ามฝังในสคริปต์ ห้ามใส่ใน ModuleScript ที่ client เห็น
3. **RemoteEvent จาก client ไม่เคยพก "จำนวนเงิน"** — พกได้แค่ "ฉันกดปุ่มนี้" แล้วเซิร์ฟเวอร์ตรวจเอง
4. **ทุกคำสั่งที่แตะเงินต้องมี `idem`** — เซิร์ฟเวอร์เกม Roblox ดับกลางคันได้ตลอด
5. **อย่า poll ถี่** — ลิมิต ~500 คำขอ/นาที/เซิร์ฟเวอร์ · แคชค่าตัวละครในหน่วยความจำ ~30 วิ
   เซิร์ฟเวอร์ 30 คนที่ poll ทุก 5 วิ = 360 คำขอ/นาที ชนลิมิตแล้ว
6. **ห้ามแคชเงินลง DataStore แล้วเขียนกลับ** — บอทดิสคอร์ดกับเว็บเขียนตารางเดียวกันอยู่
   เขียนทับ = เงินผู้เล่นหาย · อ่านผ่านอย่างเดียว เขียนผ่าน `/money` เท่านั้น
7. **API ล่มแล้วเกมต้องเล่นต่อได้** — `pcall` ทุกจุด · ล้มเหลวก็แค่ไม่ได้รางวัลรอบนั้น
   ห้ามให้ผู้เล่นค้างหน้าโหลดเพราะเซิร์ฟเวอร์ Fragment Rift ไม่ตอบ
8. **ห้ามคำนวณกติกาของเกมหลักซ้ำ** (พลังโจมตี · ราคาของ · รางวัล)
   ค่าพวกนี้ปรับได้จาก Panel — คำนวณเองเมื่อไหร่ สองเกมจะไม่ตรงกันทันทีที่มีคนปรับ

---

## 8. เช็กลิสต์ก่อนเปิดจริง

**ฝั่ง Fragment Rift (บอกเจ้าของโปรเจ็คให้สั่งทำ)**
- [ ] เซิร์ฟเวอร์ออนไลน์บนโดเมนสาธารณะ + HTTPS (ดู `docs/cloud-deploy.md` ในโปรเจ็คนั้น)
- [ ] `license_server/api_web/roblox.py` + ตาราง `roblox_links` / `roblox_ledger`
- [ ] คีย์ `ROBLOX_API_KEY` แยกจากคีย์แอดมิน
- [ ] คำสั่ง `!link <โค้ด>` ในบอทดิสคอร์ด
- [ ] ตารางรางวัลรายเหตุการณ์ของ Roblox ตั้งได้ที่ Panel
- [ ] เขียนเงินต้องผ่าน `_user_lock(uid)` — มี 3 ฝ่ายเขียนตารางเดียวกัน

**ฝั่ง Roblox**
- [ ] เปิด Allow HTTP Requests ใน Game Settings → Security
- [ ] ใส่คีย์ใน Creator Dashboard → Secrets ชื่อ `fragmentrift`
- [ ] `Api.lua` เป็นที่เดียวที่เรียก HttpService (grep ยืนยัน)
- [ ] ไม่มี `HttpService` ใน LocalScript สักตัว (grep ยืนยัน)
- [ ] ทดสอบ: ปิดเซิร์ฟเวอร์ Fragment Rift แล้วเข้าเกม Roblox — ต้องเล่นได้ไม่ค้าง
- [ ] ทดสอบ: ยิง `/money` ด้วย `idem` เดิม 5 ครั้ง — ทองต้องเพิ่มครั้งเดียว
- [ ] ทดสอบ: ใช้เงินในดิสคอร์ด แล้วดูใน Roblox — ตัวเลขต้องตรงกันภายใน 30 วิ

---

## 9. คำถามที่ต้องถามเจ้าของโปรเจ็คก่อนลงมือ

1. **เกม Roblox เป็นเกมอะไร** — ทำอะไรถึงจะได้ทอง? (ต้องรู้ก่อนถึงตั้งตารางรางวัลได้)
2. **ให้ใช้ทองได้ไหม หรือได้อย่างเดียว** — ถ้าใช้ได้ ต้องมี endpoint หักเงินด้วย
   และต้องคิดเรื่อง "จ่ายแล้วเกมค้าง ของไม่ได้" (ต้องมีระบบคืนเงิน)
3. **เลเวล/EXP ใช้ร่วมกันด้วยไหม หรือแค่ทอง** — ถ้าใช้ร่วม ต้องคุยเรื่องสมดุล
   เพราะสูตร EXP ของเกมหลักปรับตามรอบการเดินทาง
4. **ผู้เล่นที่ยังไม่เชื่อมบัญชี เล่นเกม Roblox ได้ไหม** — ได้แต่ไม่ได้รางวัล / หรือเล่นไม่ได้เลย
