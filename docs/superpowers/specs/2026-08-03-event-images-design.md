# ภาพพิกเซลอาร์ตประกอบเหตุการณ์สุ่ม — Design

วันที่: 2026-08-03 | สถานะ: ผู้ใช้อนุมัติแนวทางแล้ว (แนวทาง 1: เจนล่วงหน้า)

## เป้าหมาย

ทุกเหตุการณ์สุ่มในเกม (และประกาศธีมสัปดาห์) มีภาพพิกเซลอาร์ตแนวแฟนตาซีประกอบ
เพื่อความสนุก/น่าสนใจ ภาพใช้ซ้ำ — เหตุการณ์เดียวกันใช้ภาพเดิมทุกครั้ง

ข้อกำหนดจากผู้ใช้:
- เจนด้วยบริการฟรี Pollinations.ai (ทดสอบแล้วใช้ได้ ภาพแนวพิกเซล/เรโทรตรงโจทย์)
- **ภาพต้องเล็ก** — ผู้เล่นเน็ตช้าโหลดได้ (เป้า ≤ ~100KB/ภาพ)
- ครอบคลุมทุกอีเวนต์สุ่ม + ประกาศเปลี่ยนธีมสัปดาห์

## ขอบเขตภาพ (33 ภาพ)

| ชุด | คีย์ |
|---|---|
| อีเวนต์เดินหลัก (7) | monster, village, treasure, dungeon, npc, trap, calm |
| เรียกบอส (3) | mini_summon, main_summon, unbeatable_summon |
| Special events รายทวีป (10) | blizzard_ambush, ancestral_feast, volcanic_eruption, poison_thicket, emp_field, ancient_excavation, falling_island, goddess_gamble, black_market_dealer, zombie_parasite |
| ธีมสัปดาห์ (13) | theme_normal, theme_faction_war, theme_palette, theme_royal_convoy, theme_dragon_nesting, theme_solar_eclipse, theme_mana_meteor, theme_absolute_zero, theme_blood_moon, theme_goddess_dice, theme_masquerade, theme_black_market, theme_zombie |

ไฟล์ภาพ: `assets/events/<key>.png` (commit ลง repo, รวม ~1-2MB)

## สถาปัตยกรรม

### 1. สคริปต์เจนภาพ — `scripts/gen_event_images.py` (รันมือครั้งเดียว/รันซ้ำได้)

- ตาราง `PROMPTS: dict[key, prompt]` 33 รายการ — prompt ภาษาอังกฤษบรรยายฉากตาม
  เนื้อเรื่อง/intro ของอีเวนต์นั้น ลงท้ายสไตล์ล็อกเหมือนกันทุกภาพ:
  `pixel art, 16-bit retro fantasy game style, vibrant colors`
- เจนผ่าน `https://image.pollinations.ai/prompt/<prompt>?width=512&height=512&nologo=true&seed=<n>`
  (stdlib `urllib` — ไม่เพิ่ม dependency)
- โหลดแล้วบีบอัด: quantize เป็น PNG 256 สีด้วย Pillow (มีในโปรเจ็คแล้วจาก PromptPay QR)
  → พิกเซลอาร์ตแทบไม่เสียคุณภาพ ขนาดตก ~20-60KB
- **ข้ามไฟล์ที่มีอยู่แล้ว** — ภาพไหนไม่สวย ลบไฟล์ทิ้งแล้วรันใหม่ (เปลี่ยน seed ผ่าน CLI arg ได้)
  ทำให้คัดภาพทีละใบตามสไตล์อนุมัติทีละข้อได้

### 2. Helper เดียว — `bot/utils.py`

```python
def event_image(key):
    """คืน discord.File ของภาพอีเวนต์ หรือ None ถ้าไม่มีไฟล์ (ไม่มีภาพ = ข้อความเดิม ไม่พัง)"""
```

- path มาจาก root โปรเจ็ค `assets/events/<key>.png`
- สร้าง `discord.File` ใหม่ทุกครั้งที่เรียก (discord.py ห้าม reuse File object)

### 3. จุดแนบภาพ

| จุด | ไฟล์ | วิธีแนบ |
|---|---|---|
| อีเวนต์เดิน 7 แบบ + special | `bot/views/game_views.py` `walk_step` ทุก branch | `file=event_image(key)` ใน `followup.send(...)` |
| บอส summon โผล่ (last_event เป็น mini/main/unbeatable_summon แล้วเจอ monster) | branch monster ใน `walk_step` | ใช้ภาพ summon ตามคีย์แทนภาพ monster |
| ประกาศธีมสัปดาห์ | `bot/cogs/weekly_event.py` `build_announce_embed` | แนบไฟล์ + `embed.set_image(url="attachment://...")` |

หมายเหตุ: `discord.py` รับ `file=None` ไม่ได้ในบางเวอร์ชัน — helper ฝั่งเรียกใช้รูปแบบ
`**({"file": f} if (f := event_image(key)) else {})` หรือเทียบเท่า เพื่อไม่ส่ง kwarg เมื่อไม่มีไฟล์

### 4. Fallback / Error handling

- ไฟล์ภาพหาย → `event_image` คืน `None` → ส่งข้อความแบบเดิมไม่มีภาพ (เกมไม่พังแน่นอน)
- สคริปต์เจนล้ม (เน็ต/บริการล่ม) → ไม่กระทบเกม เพราะเจนแยกออฟไลน์จากรันไทม์บอท

### 5. เทส — `tests/test_event_images.py`

- `event_image("ไม่มีจริง")` คืน `None`
- ทุกคีย์ทั้ง 33 มีไฟล์ใน `assets/events/` ครบ (กันลืมเจน/ลืม commit)
- `PROMPTS` ในสคริปต์เจนครอบคลุมคีย์ครบตรงกับที่เกมใช้

## ขั้นตอนดำเนินงาน (ตามสไตล์อนุมัติทีละข้อ)

1. เขียนสคริปต์เจน + เจนครบ 33 ภาพ → โชว์ให้ผู้ใช้คัด
2. ผู้ใช้ชี้ภาพที่ไม่ผ่าน → เจนใหม่เฉพาะใบ (เปลี่ยน seed/prompt) จนพอใจ
3. เขียน helper + เทส
4. ต่อโค้ดจุดแนบภาพทีละไฟล์ (game_views → weekly_event)

## สิ่งที่ตัดออก (YAGNI)

- ภาพแยกตามทวีป/ธีมสำหรับอีเวนต์เดียวกัน (เช่น treasure 9 แบบตามทวีป) — ใช้ภาพกลางพอ เพิ่มทีหลังได้
- เจนภาพสดตอนเกิดอีเวนต์ — ช้า/พึ่งเน็ต ตัดทิ้ง
- ระบบตั้งค่าเปิด-ปิดภาพใน Panel — ยังไม่มีใครขอ
