# โครงสร้างโปรเจ็ค — ใครดูแลอะไร

รื้อโครงสร้าง 2026-09-02 · 6 ขั้น · เทสชุดเต็ม 3,079 ผ่าน 0 แดง

**อ่านไฟล์นี้ก่อนเริ่มงานทุกครั้ง** — บอกว่าโค้ดแต่ละส่วนอยู่ไหน แก้ได้แค่ไหน
และตรงไหนที่แก้แล้วกระทบทีมอื่น

---

## แผนที่ 5 โปรเจ็ค

```
core/                    🔵 แกนกลาง — ไม่รู้จัก Discord หรือเว็บเลย
└── services/               ตรรกะที่ทั้งดิสและเว็บใช้ร่วมกัน
                            bank · items · crafting · codex · lobby_invite

bot/
├── lobby.py             🔵 ล็อบบี้กลาง — ห้องเล่นหลายคนที่ทุกเกมใช้ร่วมได้
├── models/              🔵 ข้อมูลผู้เล่น (M ใน MVC)
├── games/               🔵 กติกาเกม — ไม่รู้จัก Discord หรือเว็บ
│   ├── casino/
│   │   ├── shared.py       ของกลางหมวดคาสิโน (_take_bet)
│   │   ├── uno/            🎴 คนดูแล UNO
│   │   ├── blackjack/      🃏 คนดูแลแบล็กแจ็ค
│   │   ├── slots/          🎰 คนดูแลสล็อต
│   │   └── hilo/           🎲 คนดูแลไฮโล
│   └── pvp/             ⚔️ ทีม PVP (สนามรบผลัดเทิร์น)
└── apps/                🎮 ตัวบอท Discord (C ใน MVC)
    ├── bot_game/           🟢 คำสั่งผู้เล่น 14 ไฟล์ (ทีมเกม)
    ├── bot_admin/          🟡 คำสั่งแอดมิน 4 ไฟล์ (ทีมแอดมิน)
    └── bot_worker/         ⚪ งานเบื้องหลัง 6 ไฟล์ ไม่มีคำสั่ง (ทีมระบบ)

license_server/
├── api_web/             🟠 API เว็บ (C ใน MVC) — ทีมเว็บ
│   ├── deps.py             ตัวช่วยกลาง (require_player · require_admin · sign · verify)
│   ├── auth · player · bank · shop · topup · adventure · admin · misc
│   └── games/              uno · pvp · casino
└── web_static/          🔴 หน้าเว็บ (V ใน MVC) — ทีมเกมบนเว็บ
    ├── play.js             เมนู · นำทาง · ตัวช่วยกลาง
    ├── games/worms_ui.js   หน้าจอสนามรบ
    └── uno.js              หน้าจอศึกไพ่รูน

panel/                   ⚫ หน้าตั้งค่าบอท (โปรเจ็คแยก)
templates/minigame/      📦 เทมเพลตให้ทีมทำเกมใหม่
```

---

## 🔑 กฎเหล็กข้อเดียว: ลูกศรชี้เข้าแกนกลางทางเดียว

| | |
|---|---|
| ✅ `bot/apps/` → `core/` `bot/games/` | บอทเรียกแกนกลางได้ |
| ✅ `license_server/api_web/` → `core/` `bot/games/` | เว็บเรียกแกนกลางได้ |
| ❌ `license_server/` → `bot/apps/` | **เว็บห้ามเรียกเข้าบอท** (มีเทสคุม) |
| ❌ `core/` → `bot/apps/` หรือ `license_server/` | แกนกลางห้ามรู้จักใคร |
| ❌ เกมหนึ่ง → เกมอื่น | UNO ห้าม import แบล็กแจ็ค (มีเทสคุม) |

**ดิสกับเว็บคุยกันผ่านคิวในฐานข้อมูล** ไม่ import ข้ามกัน
(ดู `role_grant_queue` · `lobby_invite_queue` ใน `license_server/web_db.py`)

**พิสูจน์แล้วว่าแยกได้จริง**: บล็อก `discord` ไม่ให้โหลด → `core/services/` ยังทำงานครบ
= เว็บรันได้โดยไม่ต้องติดตั้ง discord.py

---

## ใครแก้อะไรได้บ้าง

| ทีม | แก้ได้เต็มที่ | แก้แล้วกระทบใคร |
|---|---|---|
| UNO | `bot/games/casino/uno/` · `web_static/uno.js` · `api_web/games/uno.py` | ไม่กระทบใคร |
| แบล็กแจ็ค/สล็อต/ไฮโล | `bot/games/casino/<เกม>/` | ไม่กระทบใคร |
| PVP | `bot/games/pvp/` · `web_static/games/worms_ui.js` · `api_web/games/pvp.py` | ไม่กระทบใคร |
| บอทเกม | `bot/apps/bot_game/` | ไม่กระทบใคร |
| แอดมิน | `bot/apps/bot_admin/` | ไม่กระทบใคร |
| เว็บ | `api_web/` (ยกเว้น `deps.py`) | ไม่กระทบใคร |

### ⚠️ ไฟล์ที่ใช้ร่วมกัน — แก้ต้องแจ้งทีม

| ไฟล์ | ใครใช้ |
|---|---|
| `core/services/*` | ทุกทีม |
| `bot/models/player_model.py` | ทุกทีม |
| `bot/lobby.py` | ทุกเกมที่มีโหมดหลายคน |
| `license_server/api_web/deps.py` | ทุก endpoint |
| `license_server/web_static/play.js` | ทุกหน้าจอ |
| `license_server/web_static/play.html` | ทุกหน้าจอ |
| `license_server/rate_limit.py` | ทุกเกมที่แตะเงิน |

---

## 🧪 เทสที่คุมโครงสร้างไว้ (แก้ผิดแล้วแดงทันที)

| ไฟล์ | คุมอะไร |
|---|---|
| `tests/test_layering.py` | เว็บห้าม import จาก `bot/apps/` · `core/services/` ห้าม import discord |
| `tests/test_casino_structure.py` | เกมคาสิโนห้าม import ข้ามกัน |
| `tests/test_pvp_structure.py` | PVP ห้าม import คาสิโน และกลับกัน |
| `tests/test_apps_structure.py` | ทุก cog มี `setup()` · path ใน `main.py` ถูกต้อง |
| `tests/test_api_structure.py` | route ครบ 81 · สะพาน `web_api` re-export ครบ |
| `tests/test_web_split.py` | ฟังก์ชัน JS ครบ · ไม่มี `import`/`export` |
| `tests/test_rate_limit.py` | ทางที่แตะเงินต้องอยู่กลุ่ม `money` |

---

## 🌉 เรื่อง "สะพาน" ที่ต้องรู้

รื้อโครงสร้างใช้วิธี **ย้ายไฟล์ + ทิ้งสะพาน** — ไฟล์เดิม re-export จากที่ใหม่
เพื่อให้โค้ดเก่าไม่ต้องแก้ทีเดียวหลายสิบจุด

**สะพานที่ยังอยู่**: `bot/cards/*` · `bot/pvp/*` · `bot/cogs/*`
`bot/blackjack_core.py` · `bot/casino_core.py` · `license_server/web_api.py`

**โค้ดใหม่ให้ import จากที่ใหม่ตรง ๆ** อย่าเรียกผ่านสะพาน

### กับดัก 4 ข้อที่เจอจริงตอนรื้อ (อ่านก่อนย้ายโค้ด)

1. **`import *` ไม่ดึงชื่อขึ้นต้นด้วย `_`** — สะพานต้อง import เพิ่มเอง
   (PVP มี 14 ตัว · `web_api` เคยลืม `UPLOAD_DIR` จนเทสแดง 3 ข้อ)
2. **`monkeypatch.setattr()` ต้องชี้โมดูลที่นิยามจริง ไม่ใช่สะพาน**
   ```python
   # ❌ ผิด          monkeypatch.setattr(cc, "roll_hilo", ...)
   # ✅ ถูก          monkeypatch.setattr(hilo_core, "roll_hilo", ...)
   ```
3. **เทสที่อ่านซอร์สโค้ดตรง ๆ** (`Path("...").read_text()`) — ย้ายแล้วสะพานไม่มีเนื้อโค้ดให้หา
   ใช้ helper กลางแทน: `conftest.web_api_source()` · `conftest.play_js_source()`
4. **ห้ามดัดโค้ดให้อ้อมกลับหาสะพาน** — เกิด import วนกลับ ถ้าเทสพัง**แก้ที่เทส**

---

## เพิ่มมินิเกมใหม่

ดู `templates/README.md` — มีเทมเพลตที่รันได้จริงให้ก๊อปไปต่อยอด
พร้อมขั้นตอน "บ้านแยกรายคน" ตั้งแต่แตก branch จนเมิร์จกลับ

**กฎ 5 ข้อที่เกมใหม่ต้องทำตาม**:
1. เซิร์ฟเวอร์ตัดสินทุกอย่าง เบราว์เซอร์ส่งแค่ "กดปุ่มไหน"
2. `view(uid)` เป็นประตูเดียวก่อนส่งขึ้นเบราว์เซอร์ (ซ่อนด้วย CSS ไม่นับว่าซ่อน)
3. แตะเงินต้องมีเทส "ทองรวมก่อน = หลัง" + เพิ่ม path ลงกลุ่ม `money` ใน `rate_limit.py`
4. เกมห้าม import ข้ามเกม
5. ทำบอทก่อนโหมดหลายคนเสมอ (เทสคนเดียวได้ งานเดินเร็วกว่า)
