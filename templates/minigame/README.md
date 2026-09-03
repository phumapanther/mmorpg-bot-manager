# 🎯 เทมเพลตมินิเกม — ตัวอย่าง "ทายเลข 1-10 ผลัดกันทาย"

เทมเพลตนี้**รันได้จริงตั้งแต่ก๊อปมา** — ไม่ใช่ไฟล์เปล่าที่มีแต่ `TODO`
ลองรันเทสดูก่อนได้เลย (ดูคำสั่งท้ายไฟล์นี้) แล้วค่อยแก้ทีละไฟล์เป็นเกมของตัวเอง

## โครงไฟล์ (ต้องตรงกับที่นี่เป๊ะ — มีเทสคุมอยู่ที่ `tests/test_template_minigame.py`)

```
templates/minigame/
├── README.md                    ← ไฟล์นี้
├── core/                        → ปลายทาง bot/games/<หมวด>/<ชื่อเกม>/
│   ├── __init__.py
│   ├── rules.py                 กติกาล้วน ๆ ไม่มี I/O ไม่มี DB
│   ├── engine.py                สถานะเกม + ลำดับเทิร์น
│   ├── bot_ai.py                 บอทเล่นแทนคน (ทำก่อนเสมอ — เทสคนเดียวได้)
│   ├── table.py                 โหมดซ้อมกับบอท
│   └── room.py                  โหมดหลายคนบนล็อบบี้กลาง
├── web/
│   ├── game.js                  → ปลายทาง license_server/web_static/<ชื่อเกม>.js
│   └── panel.html.snippet       ชิ้นส่วน HTML ไปแปะใน play.html
├── api/
│   └── routes.py.snippet        → ชิ้นส่วนไปแปะใน web_api.py
└── tests/
    ├── test_rules.py
    ├── test_engine.py
    └── test_room.py
```

ไฟล์ทั้งหมด: `core/__init__.py` · `core/rules.py` · `core/engine.py` ·
`core/bot_ai.py` · `core/table.py` · `core/room.py` · `web/game.js` ·
`web/panel.html.snippet` · `api/routes.py.snippet` · `tests/test_rules.py` ·
`tests/test_engine.py` · `tests/test_room.py`

## เกมตัวอย่างเล่นยังไง

เลขลับ 1-10 สุ่มโดยเซิร์ฟเวอร์ ผู้เล่นผลัดกันทาย — ทายถูก = ชนะทันที
ทายผิดได้แค่คำใบ้ "สูงไป"/"ต่ำไป" แล้วส่งตาให้คนถัดไป (โหมดซ้อมมีบอทช่วยทาย
กลยุทธ์ binary search ให้ดูเป็นตัวอย่าง)

## กฎเหล็กที่เขียนไว้ในเทมเพลต (เอาจากบทเรียนจริงของ UNO/สนามรบผลัดเทิร์น)

1. **เซิร์ฟเวอร์ตัดสินทุกอย่าง** เบราว์เซอร์ส่งแค่ "กดปุ่มไหน"
   (ดู `web/game.js` — ไม่มี logic ตัดสินแพ้ชนะในนั้นเลย มีแต่วาดสิ่งที่เซิร์ฟเวอร์บอกมา)

2. **`view(uid)` เป็นประตูเดียว** ก่อนส่งขึ้นเบราว์เซอร์ — ซ่อนด้วย CSS ไม่นับว่าซ่อน
   เกมนี้ของลับคือ "เลขคำตอบ" (`secret`) — `table.view()`/`room.view()` คัดออก
   จนกว่าเกมจะจบ ต้องมีเทส **2 ชั้น**: ที่ฟังก์ชัน (`tests/test_room.py`) และที่
   คำตอบ HTTP (`tests/test_template_minigame.py` เรียก `api/routes.py.snippet`
   ตรง ๆ) — เกมไพ่รูน (UNO) เคยเกือบหลุดไพ่คนอื่นเพราะเช็คแค่ชั้นเดียว

3. **แตะเงินต้องมีเทส "ทองรวมก่อน = หลัง"** ทุกกรณีรวมคนออกกลางคัน
   และต้องเพิ่ม path ลงกลุ่ม `money` ใน `license_server/rate_limit.py`
   (UNO เคยลืม อยู่กลุ่ม `write` ที่หลวมกว่า)
   ⚠️ เกมตัวอย่างนี้**ไม่แตะเงิน** เพื่อให้เทมเพลตเรียบง่าย — ถ้าเกมของคุณมี
   เดิมพัน ให้ดู `bot/games/casino/uno/room.py` เป็นแบบอย่าง (หักเงินตอนเข้าห้อง
   จ่ายตอนจบเกม คืนเงินตอนยุบห้องก่อนเริ่ม)

4. **เกมห้าม import ข้ามเกม** — มีเทสคุมใน `tests/test_casino_structure.py` /
   `tests/test_pvp_structure.py` เป็นตัวอย่าง (เกมใหม่ของคุณควรมีเทสแบบเดียวกัน
   หลังย้ายเข้าโปรเจ็คจริง)

5. **ทำบอทก่อนโหมดหลายคนเสมอ** — เทสคนเดียวได้ (`core/bot_ai.py` +
   `tests/test_engine.py`) งานเดินเร็วกว่ามาก ค่อยไปทำ `room.py` ทีหลัง

## ⚠️ เรื่อง import ที่ต้องรู้ก่อนแก้ไฟล์ในนี้

- ไฟล์ใน `core/` ใช้ **relative import** กันเอง (`from . import rules as R`)
  เพื่อให้ก๊อปทั้งโฟลเดอร์ไปที่ `bot/games/<หมวด>/<ชื่อเกม>/` แล้ว **ไม่ต้องแก้
  import ภายใน core/ เลย** — relative import ไม่สนใจว่า package ชื่อจริงคืออะไร
- ไฟล์ **นอก** `core/` (เทสใน `tests/`, `api/routes.py.snippet`) ใช้
  **absolute import** ชี้ที่ `templates.minigame.core` — พวกนี้**ต้องแก้**
  เป็น `bot.games.<หมวด>.<ชื่อเกม>` ตอนก๊อปไปใช้จริง (ดูขั้นตอนที่
  `templates/README.md`)
- `core/table.py` import `bot.models.player_model` (DB กลาง) และ `core/room.py`
  import `bot.lobby` (ล็อบบี้กลาง) — สองบรรทัดนี้เป็น path จริงของโปรเจ็ค
  **ไม่ต้องแก้** หลังก๊อป

## รันเทสของเทมเพลตนี้เดี่ยว ๆ

```bash
PYTHONIOENCODING=utf-8 python -m pytest templates/minigame/tests -q
```
