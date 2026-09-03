# 🌐 API เว็บไซต์เกม — แยก controller ตามหมวด

รื้อโครงสร้าง 2026-09-02 (ขั้นที่ 4) — ผ่า `license_server/web_api.py`
(เดิม 2,308 บรรทัด 81 endpoint ไฟล์เดียว) ออกมาเป็น controller แยกไฟล์ตามหมวด
เพื่อให้แจกงานหลายทีมดูแลคนละไฟล์ได้โดยไม่ชนกัน (เว็บยังรันเป็น router
เดียวกันเป๊ะเหมือนเดิม — แค่แยกโค้ดให้ชัดว่าใครดูแลไฟล์ไหน)

```
license_server/api_web/
├── __init__.py     รวม router ย่อยทุกตัวเป็นตัวเดียว (prefix /api/web)
├── deps.py         ตัวช่วยกลาง — sign/verify/require_admin/require_player/
│                   _game_conn/_user_lock/_money_now/player_model_get
├── auth.py         /login/* /logout /admin/logout /me/session
├── player.py       /me/* (18 endpoint — ใหญ่สุด) /friends/* /lobby/invite
├── bank.py         /bank* /goldbar*
├── shop.py         /shop* /market* /craft* /bag/* /item/* /roleshop*
│                   /fashion/gacha*
├── topup.py        /topup* /admin/topups*
├── adventure.py    /adventure/* /board /board/roll
├── admin.py        /admin/cmdlog /admin/ping /admin/login /news* /admin/news*
├── misc.py         /gamedata /continents /codex
└── games/
    ├── uno.py      /uno* /uno/room*
    ├── pvp.py      /pvp/worms/*
    └── casino.py   /casino /blackjack*
```

`license_server/web_api.py` เหลือเป็น **สะพาน**:
`from license_server.api_web import *` + re-export ชื่อที่โค้ด/เทสเก่าเรียก
ผ่าน `web_api.<name>` ตรง ๆ (`sign` `verify` `_finish_special` `_dur_pct` ฯลฯ)

## กฎการแบ่งงาน

- ไฟล์เก่า `license_server/web_api.py` เป็นสะพานให้โค้ด/เทสที่ยัง
  `from license_server import web_api` หรือเรียก `web_api.router`,
  `web_api.sign(...)` ตรง ๆ ไม่พัง — `license_server/api.py` เองใช้
  `web_api.router` ผ่านสะพานได้ตามปกติเพราะเป็น object เดียวกัน
- โค้ดใหม่ให้ import จาก `license_server.api_web.<ไฟล์>` ตรง ๆ **ห้ามดัดโค้ด
  ในนี้ให้อ้อมกลับไปหาสะพาน** ที่ `web_api.py`
- ไฟล์ควบคุมทุกไฟล์ต้องมี `router = APIRouter()` (ไม่ใส่ prefix ของตัวเอง —
  prefix `/api/web` อยู่ที่ `api_web/__init__.py` ตัวเดียว) แล้วต้องถูก
  `include_router` เข้า `api_web/__init__.py` ไม่งั้น endpoint หายไปเงียบ ๆ
  (เว็บ 404 ตอนรันจริง แต่ import ไม่มี error ให้เห็น) — คุมด้วย
  `tests/test_api_structure.py`

## ⚠️ กับดักที่เจอจริงตอนรื้อ (09-02) — อ่านก่อนแก้ไฟล์ในนี้

**1. เทสนับ endpoint แบบเซตกลืนของซ้ำได้ — ต้องเช็คจำนวนจริงด้วย**

`router.include_router()` ที่ซ้อนกัน (controller ย่อย → `api_web.router` →
`app` ใน `api.py`) ทำให้ FastAPI ห่อ route เป็น `_IncludedRouter` ซึ่งไม่มี
`.path`/`.methods` ตรง ๆ ต้องคลี่ผ่าน `.original_router.routes` แล้วต่อ
prefix จาก `.include_context` เอง (ดู `_flatten()` ใน `test_api_structure.py`)

ระหว่างรื้อเคยคัดลอก `/fashion/gacha` ไปไว้ `shop.py` แล้ว **ลืมลบของเก่า**
ใน `web_api.py` — route เดียวกันลงทะเบียนซ้ำ 2 ครั้ง (83 แทน 81) แต่เทสที่
เทียบด้วย `set(seen) == EXPECTED_ROUTES` มองไม่เห็นบั๊กนี้เลยเพราะเซต
dedupe ของซ้ำทิ้งไปเอง ต้องมีเทสเช็คจำนวนจริงแบบไม่ dedupe ควบคู่ไปด้วย
(`test_ไม่มีrouteลงทะเบียนซ้ำ`)

**2. `monkeypatch`/`mock.patch` แพตช์ผ่านสะพานหรือ `deps.py` ไม่มีผล
ถ้าโมดูลปลายทางทำ `from ... import ชื่อ` ไว้แล้ว**

ทุกไฟล์ควบคุมทำ `from license_server.api_web.deps import require_player, ...`
ตอน import — นั่นคือการ **ผูกชื่อไว้กับ object ฟังก์ชันตอนนั้นเลย** ไม่ใช่การ
มองผ่าน `deps` ทุกครั้งที่เรียก แพตช์ที่ `deps.require_player` หรือที่สะพาน
`web_api.require_player` (แค่ re-export) จะไม่มีผลกับของที่ไฟล์ควบคุมถืออยู่

```python
# ❌ ผิด — แพตช์ที่สะพาน/deps.py ไม่มีผลกับ pvp.py
from license_server import web_api
monkeypatch.setattr(web_api, "require_player", lambda r: {"uid": UID})

# ✅ ถูก — แพตช์ที่โมดูลจริงที่เรียกใช้
from license_server.api_web.games import pvp as web_api_pvp
monkeypatch.setattr(web_api_pvp, "require_player", lambda r: {"uid": UID})
```

เจอมาแล้วที่ `tests/test_worms_controls.py::test_the_quit_action_goes_through_the_api`
— แก้ให้แพตช์ที่ `license_server.api_web.games.pvp` ตรง ๆ

ข้อยกเว้นที่ยังแพตช์ผ่านสะพานได้ปกติ: **ตัวแปรที่ตั้งใจให้เป็นของกลางจริง ๆ**
อย่าง `GAME_DB_PATH` — เพราะฟังก์ชันที่อ่านมันทุกจุด (`_game_conn`) นิยามอยู่
ใน `deps.py` เอง ไม่มีไฟล์ไหน `from deps import GAME_DB_PATH` ไปผูกชื่อทิ้งไว้
แพตช์ที่ `license_server.api_web.deps.GAME_DB_PATH` (หรือที่สะพานเผื่อไว้)
จึงยังมีผลจริง — กติกาคือ **เช็คว่าฟังก์ชันที่รันจริงมองตัวแปร/ฟังก์ชันนั้น
ผ่านโมดูลไหนตอนเรียก ไม่ใช่ผ่านโมดูลที่ import มันเข้ามา**

**3. เทสที่อ่านซอร์สโค้ดตรง ๆ (`pathlib.Path("web_api.py").read_text()`)
ต้องเปลี่ยนไปอ่านรวมทุกไฟล์**

มีเทสหลายสิบตัวที่ค้นข้อความในซอร์ส (เช่น `"def continents_summary(" in API`)
โดยอ่านจาก `web_api.py` ไฟล์เดียว — ย้าย route ออกไปแล้วข้อความยังอยู่ครบ
แต่ไปอยู่คนละไฟล์ ใช้ `tests.conftest.web_api_source()` แทน (รวมซอร์ส
`web_api.py` สะพาน + ทุกไฟล์ใน `api_web/**` เป็นก้อนเดียว) ไม่ใช่อ่าน
`web_api.py` ตรง ๆ
