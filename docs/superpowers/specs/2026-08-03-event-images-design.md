# ภาพพิกเซลอาร์ตประกอบเหตุการณ์สุ่ม — Design

วันที่: 2026-08-03 (แก้ครั้งที่ 2 — ขยายขอบเขตตามผู้ใช้) | สถานะ: รอผู้ใช้รีวิว

## เป้าหมาย

ทุกเหตุการณ์ในเกมมีภาพพิกเซลอาร์ตแนวแฟนตาซีประกอบ ภาพใช้ซ้ำ — เหตุการณ์เดียวกันใช้ภาพเดิมทุกครั้ง
และ **ภาพต่างกันตามบริบท**: ทวีปเดียวกันเจอหมู่บ้าน/NPC/หีบ ฯลฯ หน้าตาแบบทวีปนั้น,
มอนสเตอร์แต่ละตัวมีภาพของตัวเอง, ยานพาหนะแต่ละแบบมีภาพของตัวเอง, มาถึงทวีปไหนเห็นภาพทวีปนั้น

ข้อกำหนดจากผู้ใช้:
- เจนด้วยบริการฟรี Pollinations.ai (ทดสอบแล้วใช้ได้ ภาพแนวพิกเซล/เรโทรตรงโจทย์)
- **ภาพต้องเล็ก** — ผู้เล่นเน็ตช้าโหลดได้ (เป้า ≤ ~100KB/ภาพ; เจน 512×512 แล้ว quantize PNG 256 สี → ~20-60KB)
- มอนสเตอร์: **ภาพต่อมอน 1 ใบ** (~50 ตัว) — ธาตุที่สุ่มได้แสดงด้วย**สีขอบ embed** ตามธาตุ + ข้อความเดิม
  (ตัดทางเลือก มอน×ธาตุ ~350 ภาพทิ้ง — เจนนาน/คัดไม่ไหว/repo บวม)

## ขอบเขตภาพ (~152 ภาพ, รวม ~6MB)

| ชุด | จำนวน | รูปแบบชื่อไฟล์ใน `assets/events/` |
|---|---|---|
| อีเวนต์เดิน × ทวีป (7×9) | 63 | `<continent>_<event>.png` เช่น `frozen_treasure.png` — event: monster(เงาปริศนา), village, treasure, dungeon, npc, trap, calm |
| เรียกบอส | 3 | `mini_summon.png`, `main_summon.png`, `unbeatable_summon.png` |
| Special events รายทวีป | 10 | `<key>.png` (blizzard_ambush, ancestral_feast, volcanic_eruption, poison_thicket, emp_field, ancient_excavation, falling_island, goddess_gamble, black_market_dealer, zombie_parasite) |
| ธีมสัปดาห์ | 13 | `theme_<key>.png` (normal + 12 ธีมพิเศษ) |
| ยานพาหนะเดินทางข้ามทวีป | 4 | `vehicle_<key>.png` (airship, ship, portal, caravan) |
| มาถึงทวีปใหม่ | 9 | `arrival_<continent>.png` (main, demon, frozen, nether, volcanic, sylvan, mechanized, skyward, ocean) |
| มอนสเตอร์รายตัว | ~50 | `monster_<slug>.png` — slug จากชื่ออังกฤษในวงเล็บ เช่น `monster_ice_dragon.png` รวมภาพแรงค์พื้นฐาน 5 ใบ (Common/Mini-Boss/Main-Boss/Secret/Unbeatable) สำหรับมอนที่ไม่มีชื่อเฉพาะ |

## สถาปัตยกรรม

### 1. สคริปต์เจนภาพ — `scripts/gen_event_images.py` (รันมือ, รันซ้ำได้)

- ตาราง `PROMPTS: dict[filename, prompt]` — prompt อังกฤษบรรยายฉากตาม intro/บริบทของเหตุการณ์นั้น
  ผสมบรรยากาศทวีป ลงท้ายสไตล์เดียวกันทุกภาพ: `pixel art, 16-bit retro fantasy game style, vibrant colors`
- เจนผ่าน `https://image.pollinations.ai/prompt/<prompt>?width=512&height=512&nologo=true&seed=<n>`
  (stdlib `urllib`) → quantize PNG 256 สีด้วย Pillow (มีแล้วจาก `qrcode[pil]`)
- **ข้ามไฟล์ที่มีอยู่แล้ว** — ภาพไหนไม่สวย ลบไฟล์แล้วรันใหม่ (เปลี่ยน seed ผ่าน CLI arg) → คัดทีละใบได้
- เจนทีละภาพต่อคิว (บริการฟรี) — ครบชุด ~152 ภาพใช้เวลา ~30-45 นาที

### 2. Helper — `bot/utils.py`

```python
def event_image(key, continent=None):
    """คืน discord.File ของภาพอีเวนต์ หรือ None ถ้าไม่มีไฟล์
    continent ระบุ = ลอง <continent>_<key>.png ก่อน ไม่มีค่อย fallback เป็น <key>.png กลาง"""

def monster_image(monster_name, rank):
    """แปลงชื่อมอน → slug จากชื่ออังกฤษในวงเล็บ → discord.File
    ไม่มีไฟล์ → fallback ภาพแรงค์ → ไม่มีอีก → None"""
```

- สร้าง `discord.File` ใหม่ทุกครั้ง (discord.py ห้าม reuse File object)
- ฝั่งเรียกใช้รูปแบบ `**({"file": f} if (f := event_image(...)) else {})` — ไม่มีภาพ = ไม่ส่ง kwarg

### 3. จุดแนบภาพ

| จุด | ที่ | วิธี |
|---|---|---|
| อีเวนต์เดิน 7 แบบ + special | `game_views.py` `walk_step` ทุก branch | `file=event_image(evt, continent)` |
| บอส summon โผล่ (last_event เป็น summon แล้วเจอ monster) | branch monster ใน `walk_step` | ภาพ summon แทนภาพเงาปริศนา |
| มอนสเตอร์ในไฟต์ | embed ไฟต์ (`fight_ui.py`) **เฉพาะเทิร์นแรก** | แนบไฟล์ + `set_thumbnail(attachment://...)` + สีขอบ embed ตามธาตุ (เทิร์นถัดไป edit โดยไม่แนบซ้ำ — กันอัปโหลดถี่ทำช้า) |
| ประกาศธีมสัปดาห์ | `weekly_event.py` `build_announce_embed` | แนบไฟล์ + `embed.set_image` |
| เจอยานพาหนะ | จุดสร้างข้อความ travel encounter (`game_views.py` ~2546) | `vehicle_<key>.png` |
| มาถึงทวีป | embed arrival (`game_views.py` ~2597, `player_commands.py` ~354) | `arrival_<continent>.png` |

### 4. Fallback / Error handling

- ไฟล์หาย → helper คืน `None` → ข้อความแบบเดิมไม่มีภาพ เกมไม่พัง
- ภาพรายทวีปยังไม่ได้เจน/ถูกลบ → fallback ภาพกลางของอีเวนต์นั้น (ถ้ามี)
- สคริปต์เจนแยกจากรันไทม์บอทโดยสิ้นเชิง — บริการล่มไม่กระทบเกม

### 5. เทส — `tests/test_event_images.py`

- helper คืน `None` เมื่อไม่มีไฟล์ / คืน File เมื่อมี
- fallback ทวีป→กลาง และ มอน→แรงค์ ทำงานถูก
- ทุกคีย์ที่เกมใช้ (ทวีป×อีเวนต์, มอนทุกชื่อใน pool, ธีม, ยานพาหนะ) มีไฟล์ภาพครบ
- slug มอนทุกชื่อใน `monster_pool` ทั้งเกมแปลงได้ไม่ชนกัน

## ขั้นตอนดำเนินงาน (อนุมัติทีละข้อ)

1. เขียนสคริปต์เจน + เจนชุดเล็กก่อน (อีเวนต์เดินทวีปหลัก + มอนตัวอย่าง) → โชว์ให้คัดสไตล์
2. สไตล์ผ่านแล้ว → เจนที่เหลือทั้งหมด → โชว์รวมให้คัด ใบไหนไม่ผ่านเจนใหม่
3. เขียน helper + เทส
4. ต่อโค้ดทีละไฟล์: game_views (เดิน/travel) → fight_ui (มอน) → weekly_event (ธีม) → player_commands (arrival)

## สิ่งที่ตัดออก (YAGNI)

- ภาพ มอน×ธาตุ ทุกคู่ (~350 ภาพ) — ใช้สีขอบ embed ตามธาตุแทน ผู้ใช้เลือกแล้ว
- เจนภาพสดตอนเกิดอีเวนต์ — ช้า/พึ่งเน็ต
- ระบบตั้งค่าเปิด-ปิดภาพใน Panel — ยังไม่มีใครขอ
- ภาพอีเวนต์เดินแยกตามธีมสัปดาห์ (เช่น หีบ royal_convoy) — ใช้ภาพทวีปพอ เพิ่มทีหลังได้
