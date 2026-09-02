# 🤖 หมวดบอทดิสคอร์ด — แยก 3 โปรเจ็คย่อยตามหน้าที่

รื้อโครงสร้าง 2026-09-02 — ย้าย `bot/cogs/*.py` (24 ไฟล์) ออกมาแบ่งโฟลเดอร์ตาม
หน้าที่ เพื่อให้แจกงาน 3 ทีมดูแลคนละส่วนได้โดยไม่ชนกัน (บอทยังรันเป็นโปรเซส
เดียวเหมือนเดิม — แค่แยกโค้ดให้ชัดว่าใครดูแลไฟล์ไหน)

```
bot/apps/
├── bot_game/       🟢 คำสั่งผู้เล่นทั่วไป (ทีมเกม) — 14 ไฟล์
├── bot_admin/      🟡 คำสั่งแอดมิน/เจ้าของเซิร์ฟ (ทีมแอดมิน) — 4 ไฟล์
└── bot_worker/     ⚪ งานเบื้องหลัง ไม่มีคำสั่งเลย (ทีมระบบ) — 6 ไฟล์
```

## ใครดูแลไฟล์ไหน

**🟡 bot_admin/** — ทุกคำสั่งล็อกสิทธิ์แอดมิน/เจ้าของเซิร์ฟ
`admin_commands` `world_admin` `owner_announce` `guest_server`

**⚪ bot_worker/** — ไม่มีคำสั่งเลย มีแต่ loop เบื้องหลัง
`db_backup` `role_grant_worker` `lobby_invite` `server_status`
`voice_chat_tracker` `weekly_event`

**🟢 bot_game/** — ที่เหลือทั้งหมด (คำสั่งผู้เล่น)
`player_commands` `game_commands` `casino` `blackjack` `guild` `guild_war`
`pvp_duel` `world_boss` `role_shop` `payment` `web_link` `adventure_zone`
`private_room` `dice_board_cmd`

(`payment` / `web_link` / `guild_war` ดูก้ำกึ่งแต่ตัดสินไว้แล้วว่าเป็น
bot_game — ดูเหตุผลที่ `.superpowers/sdd/2026-09-02-lobby-uno-betting/refactor-cogs-brief.md`)

## กฎการแบ่งงาน

- ไฟล์เก่าที่จุดเดิม (`bot/cogs/*.py`) เหลือไว้เป็น **สะพาน** ให้
  `bot/main.py` (เวอร์ชันเก่า/สคริปต์อื่น) กับเทสที่ยัง import ทางเดิมอยู่ไม่พัง
  — `bot/main.py` เองแก้ให้ `load_extension` ชี้ `bot.apps.*` ตรง ๆ แล้ว
  ไม่ได้พึ่งสะพาน
- โค้ดใหม่ให้ import จากที่ใหม่ในนี้ตรง ๆ **ห้ามดัดโค้ดในนี้ให้อ้อมกลับไปหา
  สะพาน** ที่ `bot/cogs/`
- ทุกไฟล์ (cog) ต้องมี `async def setup(bot)` — ไม่งั้นบอทโหลด extension นี้
  ไม่ขึ้นตอนรันจริง (เทสไม่จับปัญหานี้อัตโนมัติถ้าลืม แต่มี
  `tests/test_apps_structure.py::test_ทุก_cog_มี_setup` คุมไว้แล้ว)

## ⚠️ 2 กับดักที่เจอจริงตอนรื้อ (09-02) — อ่านก่อนแก้ไฟล์ในนี้

**1. `import *` ไม่ดึงชื่อขึ้นต้นด้วย `_` ให้สะพาน**

โค้ดข้ามไฟล์บางจุดเรียกชื่อ `_` ตรง ๆ ผ่านสะพานเก่า เช่น
`bot/apps/bot_game/guild_war.py` เรียก `bot.cogs.guild._is_leader` และ
`tests/test_codex_is_current.py` เรียก `bot.cogs.player_commands._item_effect_desc`
— ถ้าเพิ่มฟังก์ชัน `_` ตัวใหม่ในไฟล์พวกนี้แล้วมีคนเรียกข้ามไฟล์ผ่านสะพาน ต้อง
`from bot.apps.<กลุ่ม>.<ไฟล์> import _ชื่อฟังก์ชัน` เพิ่มเองในสะพานที่
`bot/cogs/<ไฟล์>.py` ไม่งั้นหายเงียบ ๆ (`ImportError`/`AttributeError` ตอนรันเทส)

**2. `monkeypatch`/`mock.patch` แพตช์ตัวแปร global ที่สะพานไม่มีผล**

ฟังก์ชันที่นิยามจริงมองตัวแปร global ของ**โมดูลที่นิยาม** ไม่ใช่ของสะพาน —
แพตช์ที่สะพาน (`bot.cogs.xxx.SOME_CONST`) จะไม่มีผลกับฟังก์ชันที่รันจริง
(ฟังก์ชันยังอ่านค่าเดิมจาก `bot.apps.<กลุ่ม>.xxx.SOME_CONST`)

```python
# ❌ ผิด — แพตช์ที่สะพาน ไม่มีผล
import bot.cogs.world_boss as wb
monkeypatch.setattr(wb, "SKILL_CONFIG", fake_config)

# ✅ ถูก — แพตช์ที่โมดูลจริง
import bot.apps.bot_game.world_boss as wb
monkeypatch.setattr(wb, "SKILL_CONFIG", fake_config)
```

ข้อยกเว้น: ถ้าแพตช์ **โมดูลย่อยที่ใช้ร่วมกัน** (เช่น `config_loader`,
`player_model`, `random`, `os`) ผ่านสะพานได้ตามปกติ เพราะโมดูลนั้นเป็น
singleton เดียวกันไม่ว่าจะเข้าทางสะพานหรือของจริง — ปัญหาเกิดเฉพาะตัวแปร
ธรรมดา (string/dict/number) ที่นิยามตรงในไฟล์ cog เอง

เจอมาแล้ว 2 จุดตอนรื้อ: `tests/test_world_boss.py` (`SKILL_CONFIG`) และ
`tests/test_topup_ingame.py` (`web_link.UPLOAD_DIR`) — แก้ทั้งสองให้ import
จาก `bot.apps.bot_game.*` ตรง ๆ แทนสะพาน
