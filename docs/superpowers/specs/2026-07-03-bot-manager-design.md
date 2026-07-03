# MMORPG Bot Manager — Design (v1)

วันที่: 2026-07-03
สถานะ: รอรีวิว

## 1. เป้าหมาย

เปลี่ยนบอท Discord MMORPG เดิม (ที่ค่าต่างๆ hardcode ผูกกับเซิร์ฟเวอร์เดียว) ให้กลายเป็น
**โปรแกรมที่คนอื่นโหลดไปติดตั้งแล้วตั้งค่าเองได้ผ่านหน้าจอบนเครื่อง** โดยไม่ต้องแก้โค้ด

ผู้ใช้ปลายทาง (เจ้าของเซิร์ฟ Discord) ดับเบิลคลิกไฟล์เดียว → เบราว์เซอร์เด้งหน้า Dashboard →
ใส่ token, เลือกเซิร์ฟเวอร์, ตั้งค่าห้อง/สิทธิ์/ยศซื้อขาย, กดรันบอท จบในหน้าจอเดียว

## 2. ขอบเขต

### v1 (สเปกนี้)
- **แผงควบคุม (Control Panel):** ใส่/บันทึก token, เลือก guild, ปุ่ม start/stop/restart บอท, ไฟสถานะ, ดู log สด
- **Channel Routing:** กำหนดว่าห้องไหนใช้ฟีเจอร์ไหน (แทน `allowed_channels` ที่ hardcode)
- **Role → กลุ่มคำสั่ง:** จับ role ของเซิร์ฟเข้ากลุ่มสิทธิ์ (แทน `has_role_or_owner` ที่ hardcode)
- **Auto-trade Roles:** จัดการรายการยศซื้อขายออโต้ + ราคา (แทน `DARK_ROLES`/`LIGHT_ROLES` ที่ hardcode)
- **แพ็กเป็น `.exe`** ไฟล์เดียวด้วย PyInstaller, เปิดแล้ว auto-open browser

### ไม่อยู่ใน v1 (เฟสถัดไป)
- **Skill Buff/Nerf** (`SKILL_CONFIG`) — เป็นการรื้อ balance เกมที่ลึกสุด เลื่อนไปเฟส 2
- Multi-tenant / รองรับหลาย guild พร้อมกันในตัวเดียว — v1 เป็น single-guild ต่อการติดตั้ง
- Live-reload config โดยไม่ restart บอท — v1 ใช้ "แก้แล้ว restart"
- ระบบ auth/login เข้า panel — v1 ผูกกับ localhost เครื่องเดียว ไม่เปิดออกเน็ต

## 3. หลักการออกแบบ

- **โปรเจ็คใหม่แยกจากเดิม:** คัดลอกบอทมา refactor ให้อ่าน config; โปรเจ็คเดิม `discord-mmorpg-bot` ไม่ถูกแตะ
- **แยก 2 process:** panel กับ bot คนละ process คุยกันผ่าน `config.json` ไฟล์เดียว
- **Config เป็น source of truth เดียว:** ทุกค่าที่เคย hardcode ย้ายมาที่ `config.json`; บอทอ่านตอนสตาร์ท, panel เป็นตัวเขียน
- **แก้แล้ว restart:** panel คุมวงจรชีวิตบอทอยู่แล้ว การ apply config = กด restart (ไม่กี่วิ)

## 4. สถาปัตยกรรม

```
┌─────────────────┐   HTTP    ┌──────────────────────┐
│  Browser (UI)   │ ⇄──────── │   Panel (FastAPI)    │
│  localhost:8770 │           │                      │
└─────────────────┘           │  ├ REST /api/config  │──เขียน/อ่าน──► config.json
                              │  ├ REST /api/bot     │                   │
                              │  │   start/stop/log  │──subprocess──┐    │ อ่านตอนสตาร์ท
                              │  └ REST /api/discord │              ▼    ▼
                              │      guilds/channels │        ┌──────────────────┐
                              │      /roles          │        │   Bot (bot/)     │
                              └──────────┬───────────┘        │  main.py + cogs  │
                                         │ ใช้ token           │  อ่าน config_loader│
                                         ▼ ยิง Discord REST     └──────────────────┘
                                  discord.com/api
```

- **Panel → Discord REST:** ใช้ token ยิง `GET /users/@me/guilds`, `/guilds/{id}/channels`, `/guilds/{id}/roles`
  เพื่อดึงรายชื่อจริงมาทำ dropdown (ผู้ใช้ไม่ต้องพิมพ์ ID) — ไม่ต้องรอบอทรัน
- **Panel → Bot:** `subprocess.Popen(["python", "bot/main.py"])`, จับ stdout ส่งเข้า log view, ปุ่ม start/stop/restart
- **Bot → config.json:** โหลดผ่าน `bot/config_loader.py` ตอน import; decorator และ role_shop อ่านจากตรงนี้

## 5. โครงไฟล์โปรเจ็คใหม่

```
mmorpg-bot-manager/
├── config.json                 # source of truth เดียว (panel เขียน, bot อ่าน)
├── config.example.json         # ค่าเริ่มต้น/ตัวอย่างให้ผู้ใช้ใหม่
├── launcher.py                 # entry point: สตาร์ท panel + เปิด browser
├── requirements.txt
├── build.spec                  # PyInstaller (แพ็ก .exe)
│
├── bot/                        # คัดลอก + refactor จากโปรเจ็คเดิม
│   ├── main.py                 # token จาก config, ไม่มี hardcode bypass
│   ├── config_loader.py        # ★ ใหม่: อ่าน/แคช config.json ให้ทั้งบอท
│   ├── utils.py                # allowed_channels / has_permission = config-driven
│   ├── models/player_model.py  # (คงเดิม)
│   ├── controller/             # (คงเดิม)
│   ├── views/                  # (คงเดิม — game_views.py ตัวเดียว)
│   └── cogs/                   # refactor เฉพาะจุดที่อ่าน channel/role/trade
│
└── panel/
    ├── server.py               # FastAPI app + รวม route
    ├── routes_config.py        # GET/PUT /api/config
    ├── routes_bot.py           # POST /api/bot/{start,stop,restart}, GET /api/bot/log (SSE)
    ├── routes_discord.py       # GET /api/discord/guilds|channels|roles
    ├── process_manager.py      # จัดการ subprocess บอท + buffer log
    ├── discord_fetch.py        # httpx ยิง Discord REST
    └── static/                 # หน้าเว็บ (single page + tabs)
        ├── index.html
        ├── app.js
        └── style.css
```

## 6. โครง `config.json`

```json
{
  "bot_token": "",
  "guild_id": null,
  "panel_port": 8770,

  "channels": {
    "bank":        { "label": "ธนาคาร / เศรษฐกิจ", "channel_id": null },
    "arena":       { "label": "ลานประลอง (pvp/att/scan)", "channel_id": null },
    "role_shop":   { "label": "ซื้อยศออโต้", "channel_id": null },
    "profile":     { "label": "เช็คโปรไฟล์", "channel_id": null },
    "adventure":   { "label": "เริ่มเกม/ผจญภัย", "channel_id": null },
    "rent":        { "label": "สัญญาเช่าห้อง", "channel_id": null },
    "police":      { "label": "ห้องแจ้งความ (arrest/fine)", "channel_id": null },
    "casino_hilo": { "label": "Hi-Lo", "channel_id": null },
    "casino_slots":{ "label": "สล็อต", "channel_id": null },
    "casino_bj":   { "label": "Blackjack", "channel_id": null }
  },

  "permission_groups": {
    "admin":  { "label": "แอดมินหลัก (set_cash, spawn, tax...)", "role_ids": [] },
    "police": { "label": "ตำรวจ/อัศวิน (arrest, fine, remove)", "role_ids": [] },
    "priest": { "label": "นักบวช/หมอ (heal, rv)", "role_ids": [] }
  },

  "auto_trade_roles": {
    "dark":  [ { "label": "♆ Maou-sama", "value": "maou", "price": 300000000, "role_id": 0, "emoji": "👑" } ],
    "light": [ { "label": "พระเจ้า", "value": "god", "price": 300000000, "role_id": 0, "emoji": "✨" } ],
    "gacha_price": 10000000,
    "gacha_pool_price": 20000000
  }
}
```

หมายเหตุ: `config.example.json` จะเก็บ `DARK_ROLES`/`LIGHT_ROLES` ชุดเดิมไว้เป็นค่าเริ่มต้น
(ผู้ใช้ใหม่ปรับ role_id ให้ตรงเซิร์ฟตัวเองผ่าน dropdown)

## 7. การ refactor บอท (จุดต่อจุด)

| จุดเดิม (hardcode) | เปลี่ยนเป็น |
|---|---|
| `allowed_channels(["🏦ธนาคารกลาง🏦"])` และอีก ~10 ห้อง | `allowed_channel("bank")` — decorator รับ **feature key** แล้วไปเทียบ `config.channels[key].channel_id` กับ `ctx.channel.id` |
| `has_role_or_owner("คนบ้า")` / `"อัศวิน"` / `"นักบวช"` | `has_permission("admin")` / `"police"` / `"priest"` — เทียบ role ของผู้ใช้กับ `config.permission_groups[group].role_ids` (owner ผ่านเสมอ) |
| `DARK_ROLES` / `LIGHT_ROLES` / ราคา gacha ใน `role_shop.py` | อ่านจาก `config.auto_trade_roles` ผ่าน `config_loader` |
| `main.py` token = `os.getenv("ARTHUR_TOKEN")` + bypass mode | token = `config.bot_token`; รันบอทเกมตัวเดียว (เหมือน bypass ปัจจุบัน) |

**`config_loader.py`** ให้ helper กลาง: `get_config()` (อ่าน+แคช), `get_channel_id(key)`, `get_role_ids(group)`, `get_trade_roles(faction)`.
Decorator ใน `utils.py` เรียก helper พวกนี้ — เปลี่ยน 60 จุดที่ใช้ decorator เป็นแค่เปลี่ยน **argument** จากสตริงห้อง/ยศ เป็น key (mechanical, ทีละ cog).

**ประเด็นสำคัญ — เทียบด้วย ID ไม่ใช่ชื่อ:** เดิมเทียบด้วย "ชื่อห้อง/ชื่อยศ" ซึ่งเปราะ (เปลี่ยนชื่อแล้วพัง)
v1 เก็บเป็น **ID** ทั้งหมด (channel_id, role_id) ที่ dropdown เลือกมา → ทนต่อการเปลี่ยนชื่อ

## 8. Panel — REST API

| Method | Path | หน้าที่ |
|---|---|---|
| GET | `/api/config` | คืน config.json ปัจจุบัน |
| PUT | `/api/config` | validate + เขียนทับ config.json |
| GET | `/api/discord/guilds` | ยิง Discord REST ด้วย token → รายชื่อ guild ที่บอทอยู่ |
| GET | `/api/discord/channels?guild_id=` | รายชื่อ text channel ของ guild |
| GET | `/api/discord/roles?guild_id=` | รายชื่อ role ของ guild |
| POST | `/api/bot/start`·`/stop`·`/restart` | คุม subprocess บอท |
| GET | `/api/bot/status` | running/stopped + PID |
| GET | `/api/bot/log` | สตรีม log สด (Server-Sent Events) |

## 9. Panel — หน้าจอ (single page + tabs)

1. **Setup:** ช่องใส่ token (ปุ่ม "ตรวจสอบ" → ยิง `/api/discord/guilds`), เลือก guild จาก dropdown
2. **Dashboard:** ไฟสถานะ (🟢/🔴), ปุ่ม Start/Stop/Restart, กล่อง log สด (auto-scroll)
3. **Channels:** ตารางฟีเจอร์ ~10 แถว แต่ละแถวมี dropdown เลือกห้องจริงจากเซิร์ฟ
4. **Permissions:** 3 กลุ่ม (admin/police/priest) แต่ละกลุ่มเลือกได้หลาย role (multi-select)
5. **Auto-trade:** 2 ตาราง (dark/light) เพิ่ม/ลบ/แก้ยศ + ราคา + เลือก role จาก dropdown

ทุกแท็บมีปุ่ม **"บันทึก"** (PUT /api/config) และเตือน "ต้อง restart บอทเพื่อให้มีผล"

## 10. การจัดการข้อผิดพลาด

- **Token ผิด:** `/api/discord/guilds` คืน 401 → UI แสดง "token ไม่ถูกต้อง"
- **บอทยังไม่ได้อยู่ในเซิร์ฟ:** guild list ว่าง → UI แนะนำลิงก์เชิญบอท
- **บอท crash:** process_manager ตรวจจับ exit code → ไฟสถานะเป็นแดง + โชว์ log ท้ายสุด
- **Port ชนกัน:** launcher จับ error แล้วลองพอร์ตถัดไป / แจ้งผู้ใช้
- **config.json เสีย:** โหลดไม่ได้ → fallback เป็น config.example.json + เตือน
- **Config ไม่ครบตอนรันบอท:** บอทเช็คตอนสตาร์ท ถ้า token ว่าง/guild ว่าง → log บอกชัดว่าให้ไปตั้งใน panel ก่อน

## 11. การทดสอบ

- **config_loader:** unit test — อ่าน config, คืน channel_id/role_ids/trade_roles ถูก, fallback เมื่อ key หาย
- **decorator (has_permission/allowed_channel):** test ด้วย ctx จำลอง — role ตรง/ไม่ตรง, owner ผ่านเสมอ, channel ตรง/ผิด
- **process_manager:** test start→status=running→stop→status=stopped
- **discord_fetch:** mock httpx — parse guild/channel/role list
- **End-to-end แบบ manual:** ตั้งค่าครบใน panel → กด start → บอทออนไลน์ → คำสั่งเข้าห้องถูก/สิทธิ์ถูก (เหมือนที่เพิ่งทดสอบโปรเจ็คเดิม)

## 12. การแพ็ก (.exe)

- `launcher.py` = entry: สตาร์ท FastAPI (uvicorn) บน thread → `webbrowser.open("http://localhost:8770")`
- PyInstaller `--onefile` รวม Python + deps + `panel/static` + `bot/` เข้าไฟล์เดียว
- `config.json` อยู่ข้างไฟล์ exe (แก้ได้/backup ได้) — ถ้าไม่มีให้ copy จาก example ตอนเปิดครั้งแรก
- บอทที่ถูก spawn: ตอนแพ็กเป็น exe จะเรียกตัวเองด้วย flag (`launcher.py --run-bot`) แทน `python bot/main.py`
  เพื่อไม่ต้องพึ่ง Python ที่เครื่องผู้ใช้

## 13. ความเสี่ยง / จุดต้องระวัง

- **สำเนาโค้ดบอทแยกจากเดิม** → แก้บั๊กอนาคตต้องทำ 2 ที่ (ผู้ใช้ยอมรับแล้ว)
- **spawn subprocess ในโหมด .exe** เป็นจุดเทคนิคที่ต้องทดสอบจริง (PyInstaller + Popen ตัวเอง)
- **Discord REST rate limit** ตอนดึง channel/role — แคชผลไว้ ไม่ยิงซ้ำถี่
- **Emoji/ภาษาไทยใน log** — บังคับ `PYTHONIOENCODING=utf-8` ตอน spawn (เจอปัญหานี้แล้วในโปรเจ็คเดิม)

## 14. เฟสถัดไป (นอกสเปกนี้)
- Skill Buff/Nerf editor (แก้ `SKILL_CONFIG`)
- ตั้งค่าค่าคงที่เกมอื่น (ราคา shop, EXP curve, ค่าเริ่มต้นผู้เล่น)
- Live-reload config โดยไม่ restart
