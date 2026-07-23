# Dynamic Continents + World Events — Design (อนาคต)

วันที่: 2026-07-23
สถานะ: **ดีไซน์สำหรับอนาคต — ยังไม่เริ่มทำ** (ตอนเริ่มจริงจะแตกเป็นรายการขออนุมัติทีละข้อตามธรรมเนียม)
ต่อยอดจาก: ระบบ modifier/ทวีป/ธีมสัปดาห์/ธาตุ ที่ทำเสร็จแล้ว (commits 7370016 → a846150)

## 1. ข้อตีความสำคัญ (ยืนยันกับผู้ใช้แล้ว)

- **"Mechanics" ในสเปกต้นทาง = อีเวนต์สุ่มประจำทวีป** ที่มีโอกาสเจอระหว่างเดินทางในทวีปนั้น
  (แบบเดียวกับเจอพาหนะ/หีบ/กับดัก) — ไม่ใช่ระบบ passive ที่ทำงานตลอดเวลา
- สถานะติดตัว: ติดได้**หลายสถานะพร้อมกัน** แต่ละสถานะมี**ตัวนับเทิร์นของตัวเอง** หมด = ลบออก
- เกาะถล่ม (Skyward): อีเวนต์เดียวจบ — ทอยเต๋ากำหนดดาเมจ แล้ว**บังคับกลับทวีปหลักทุกกรณี** (รอดหรือตาย)
- เพชร (Volcanic): **ไอเทม**ใน item_catalog (ใช้เป็นวัตถุดิบคราฟต่อได้) — ไม่ใช่สกุลเงินใหม่
- Crafting: **ใช้ระบบเดิม** — `!recipe`/`!craft`, สูตรใน `config.item_catalog.crafting_recipes`
  (11 สูตร, มี fail_rate, แก้ผ่าน panel แท็บ Items ได้แล้ว) + มอนสเตอร์มีระบบดรอปไอเทมตอนชนะอยู่แล้ว

## 2. ของใหม่ที่ต้องสร้างจริง มีแค่ 3 ชิ้น

### 2.1 ชั้นอีเวนต์พิเศษ (Special Events Layer)
- เพิ่ม `special_events` ใน data ของทวีป **และ** ธีมสัปดาห์ (merge ผ่านระบบ modifier เดิม)
- จุดสุ่ม: `start_adv` ชั้นเดียวกับพาหนะ (8%) / เงียบสงบ (12%) — ทอยตาม `chance` ของแต่ละอีเวนต์
- **View กลาง 1 ตัว** render จาก data — 2 แม่แบบครอบทุกอีเวนต์ในสเปก:
  - `dice_check`: intro → ทอยเต๋าเทียบ `pass_roll` → success/fail (รางวัลเงิน/ไอเทม/ดาเมจ/สถานะ/บังคับย้ายทวีป)
  - `choice`: intro → ปุ่มเลือก 2-3 ทาง → ผลลัพธ์ต่างกัน (รวมแบบ gamble พร/คำสาป)
- ตัวอย่าง data:
```python
"special_events": [
    {"key": "excavation", "chance": 10, "template": "dice_check",
     "intro": "⚙️ คุณพบหีบกลไกโบราณ...", "pass_roll": 12,
     "success": {"gold": (500, 2000), "text": "ไขสำเร็จ!"},
     "fail": {"damage": (10, 30), "text": "กับดักไฟฟ้าช็อต!"}},
]
```
- ผลลัพธ์ที่ template รองรับ: `gold`, `items` (id+จำนวน), `damage`, `heal`, `apply_status`,
  `force_continent`, `exp`

### 2.2 ระบบสถานะติดตัว (Status Effects)
- Field ใหม่ `status_effects` (JSON dict): `{"poison": 20, "emp": 1, "exp_blessing": 10}`
- **Tick:** กด "เริ่มออกเดินทาง" 1 ครั้ง = ทุกสถานะ -1 → เหลือ 0 ลบออกอัตโนมัติ
- นิยามสถานะเป็น data table: label/emoji, ผลต่อเทิร์นเดิน (เช่น เลือดไหล), ผลในไฟต์
  (ปิดสกิล/ลดดาเมจผู้เล่น/บัฟ EXP), เงื่อนไขล้างพิเศษ (`cleanse_on: ["village", "npc"]` สำหรับพิษ)
- แสดงสถานะปัจจุบันในหน้า `!play` (บรรทัดเดียว: ไอคอน+เทิร์นเหลือ)

### 2.3 Hook แจกไอเทมจากอีเวนต์
- ฟังก์ชันกลาง "ให้ไอเทม N ชิ้น" ใช้ร่วมทุกอีเวนต์ (เช็ค capacity กระเป๋า — พฤติกรรมตอนเต็มดูคำถามค้าง ข้อ 6)

## 3. ทวีปใหม่ 6 แห่ง (สรุปเป็นภาษาระบบเรา)

| ทวีป | มอนสเตอร์ (monster_pool) | อีเวนต์พิเศษ (template) | อื่นๆ |
|---|---|---|---|
| ⚙️ Mechanized | Steam Puppet, Clockwork Golem, Laser Gear Spider, Ancient Guardian | ขุดหีบกลไก (dice: รางวัล ×2) · สนาม EMP (choice: ฝ่า = ติดสถานะ emp ปิดสกิลไฟต์ถัดไป) | — |
| ☁️ Skyward | Winged Beast, Griffin, Garuda, Sky Gargoyle, Fallen Angel | เกาะถล่ม (dice: ดาเมจเบา→ตาย + **บังคับกลับทวีปหลักทุกกรณี**) | ลมชุก + ลมได้บัฟ (element_overrides) + บัฟ EXP ลม ×1.5-2 |
| 🌲 Sylvan | Savage Forest Elf, Ent, Mutant Carnivorous Plant, Cursed Dryad | พงหนามพิษ (choice: ลุย = ติดสถานะ poison / อ้อม = เสียเงิน-เวลา) | ไม้ root_chance ×2 + ไม้ EXP ×2 (element_overrides); พิษล้างเมื่อ village/npc |
| 🌋 Volcanic | Fire Salamander, Lava Golem, Light Dragon, Ash Phoenix | ภูเขาไฟระเบิด (dice: ผ่าน = 💎 เพชร ×10, พลาด = ดาเมจ) | ไฟ atk +20% (element_overrides); เพิ่มไอเทม "เพชร" ใน item_catalog |
| ❄️ Frozen | Yeti, Snow Wolf, Ice Dragon, Ancient Ice Knight | พายุหิมะซุ่ม (dice: พลาด = เข้าไฟต์แบบเสียเปรียบ) | ambush = `event_weight_mult {"monster": 1.5}` (มีอยู่แล้ว); สถานะ "ชา" ลดดาเมจผู้เล่น 50% ไฟต์ยาว |
| 💀 Nether | Banshee, Lich, Ghoul, Undead King | งานเลี้ยงบรรพชน (choice/gamble: พร = ฟื้น HP เต็ม / สาป = ดาเมจหนัก) | Life Drain: เลือดไหลต่อเทิร์นในไฟต์ (hook ใน process_turn) |

ทุกทวีปต้องเติม: `element_weights`, `travel_flavors/arrival_text`, และอัปเดตปลายทางพาหนะ (ดู 5.2)

## 4. อีเวนต์โลกใหม่ 9 แบบ (แปลงเข้าสถิติที่มีจริง)

ตารางแปลงสถิติที่เกมไม่มี → ที่มี: **Speed/Attack Speed → โบนัสเต๋า** · **Crit → dmg_mult** ·
**Defense → hp_mult** · **Magic Damage → dmg_mult** · **Drop Rate → gold/exp mult + item ผ่านชั้นอีเวนต์พิเศษ**

| อีเวนต์ | ระบบที่ใช้ | หมายเหตุ |
|---|---|---|
| ☄️ Mana Meteor | สุ่ม 50% ตอนเกิดมอน "อาบอุกกาบาต" dmg ×2 + ป้าย; ชนะแล้วอีเวนต์ต่อ = special_event แจก Mana Crystal (ไอเทมคราฟใหม่) | ต้อง hook สุ่มตอนเกิด 1 จุด |
| 🌑 Solar Eclipse | element_overrides {dark: hp×1.5, dice+}; ดันน้ำหนักแรงค์ **Secret** (= "Secret Dungeon" ของเกมเรา) | ต้องมี mod เลื่อนน้ำหนักแรงค์ |
| 🥶 Absolute Zero | สถานะ frostbite (ใช้ระบบสถานะเดียวกับพิษ — เลือดไหล, ล้างเมื่อ village/dungeon/npc + ฟื้น 20%); น้ำ hp×2; `TRAVEL_EVENT_CHANCE` คูณเพิ่ม | ใช้ 3 ระบบที่มี/กำลังสร้าง ครบพอดี |
| 🎭 Masquerade | NPC ปลอม + ปุ่ม Inspect เสียเงิน | **flow ใหม่จริง** — แตกสเปกย่อยตอนทำ |
| 🏴 Black Market | แตะระบบร้านค้า | **แตกสเปกย่อยตอนทำ** |
| 🐉 Dragon Nesting | monster_pool มังกร + dmg/dice bonus + gold_mult; ดรอปอุปกรณ์ = ระบบดรอปเดิม | ง่ายกว่าที่คิดเพราะดรอปมีแล้ว |
| 🌕 Blood Moon | monster_pool หมาป่า + hp×1.5 + dice+; วัสดุคราฟ ×2 (ไอเทม) | ❗"Horde สู้หลายตัว" = โหมดใหม่ — ตัดหรือแตกสเปกย่อย |
| 👑 Royal Convoy | `event_weight_mult {treasure: ×}` + `monster_gold_mult 2.0` + theme_texts | **ทำได้ทันทีวันนี้ (ข้อมูลล้วน)** |
| 🎲 Goddess Dice | EXP/ดรอป ×1.5 ✓; กติกาเต๋าพิเศษ = hook สูตรเต๋า | ❗"รายชั่วโมง" ขัดโครงรายสัปดาห์ → เสนอ "กติกาเปลี่ยนรายวัน" |

ธีมใหม่ทั้งหมด **เพิ่มเข้า pool เดิม** (ไม่แทนที่ palette/zombie/สงบสุข) — ตั้ง weight รายธีม,
สัปดาห์สงบสุขควรคง weight สูงสุดต่อไป

## 5. คำแนะนำเชิงสถาปัตยกรรม (ทำก่อนเติมข้อมูล)

1. **`element_overrides` mod ตัวเดียว** — hook จุดเกิดมอน merge เข้า element_data:
   `{"wood": {"root_chance": 50, "exp_mult": 2}}` → ครอบกลไกธาตุเฉพาะถิ่นของ 4+ ทวีป และ 3+ อีเวนต์โลก **ROI สูงสุด ทำข้อแรก**
2. **`roll_destination` fallback** — ทวีปที่ไม่อยู่ใน `dest_weights` ของพาหนะ ให้ weight มาตรฐานอัตโนมัติ
   → เพิ่มทวีปใหม่ไม่ต้องไล่แก้พาหนะทุกคัน (แก้ครั้งเดียว)
3. **อย่าเปิด 6 ทวีปรวด** — แนะนำเฟสละ 2-3 ทวีป (ผู้เล่นไม่กระจายบางเกิน)
4. **ตารางทบตัวคูณสูงสุด** — ปัจจุบัน demon+zombie+แสง = ทอง ×14; ทุกเฟสใหม่ต้องคำนวณ worst-case
   + เขียน test ล็อกตัวเลขแบบที่ทำมา (test_demon_plus_zombie_stacking)
5. **mod เลื่อนน้ำหนักแรงค์** (`rank_weight_mult`) — Eclipse ใช้ดัน Secret; อนาคตธีมอื่นใช้ได้
6. **แท็บ panel เริ่มคุ้มแล้ว** — ข้อมูลจะโตเป็น 9 ทวีป/12 ธีม ควรกลับมาพิจารณาหลังเฟสนี้

## 6. คำตอบจากผู้ใช้ (ยืนยันแล้ว 2026-07-23)

1. **กระเป๋าเต็มตอนได้ไอเทมรางวัล:** แปลงเป็นทองตามราคาขาย + แจ้งผู้เล่น
2. **สถานะแบบ "ต่อไฟต์":** มี tick 2 แบบ — นับก้าวเดิน (step) และนับไฟต์ (fight)
3. **พายุหิมะ "เสียเปรียบ":** โดนดาเมจเปิดฉากก่อนเทิร์นแรก
4. **งานเลี้ยงบรรพชน:** เจอแล้ว**สุ่มทันที ไม่มีสิทธิ์ปฏิเสธ** — pool ฝั่งพร: ฮีล, ล้างสถานะทั้งหมด, สุ่มล้างบางสถานะ (ฝั่งสาป: ดาเมจหนัก/ติดสถานะร้าย)
5. **Goddess Dice:** กติกาเปลี่ยน**รายวัน**
6. **เพชร:** ✅ ตัดสินใจแล้ว — **ใช้ "💎 เศษอัญมณีหมองหม่น" (id 11) เดิมเป็นรางวัล** (ไม่สร้างไอเทมใหม่)
7. **ทวีป:** ✅ ทำครบทั้ง 6 — เรียงจากง่ายไปยาก (Frozen → Nether → Volcanic → Sylvan → Mechanized → Skyward)
8. **น้ำหนักธีมใหม่ 9 ตัว:** ✅ ธีมพิเศษทุกตัว weight เท่ากันหมด, ธีมสงบสุข weight สูงสุด (เจอบ่อยสุด)

## 7. ขั้นตอนการทำจริง (อนุมัติทีละขั้นตามธรรมเนียม — เริ่ม 2026-07-23)

ทุกขั้น: เสนอดีไซน์+ตัวเลข → ผู้ใช้อนุมัติ → ทำ → test → commit แยก

**เฟส A — โครงสร้างกลาง (3 ขั้น)**
- A1. Hook รากฐาน: `element_overrides` mod (บัฟ/ปรับธาตุเฉพาะถิ่น) + `roll_destination` fallback (ทวีปที่ไม่อยู่ในตารางพาหนะได้ weight มาตรฐานอัตโนมัติ)
- A2. ระบบสถานะติดตัว: field `status_effects` multi-status, tick 2 แบบ (step/fight), cleanse_on, ผลต่อเทิร์นเดิน+ในไฟต์ (เลือดไหล/ปิดสกิล/ลดดาเมจผู้เล่น/บัฟ EXP), แสดงใน !play
- A3. เอนจินอีเวนต์พิเศษ: `special_events` ใน mods, View กลาง 3 แม่แบบ (dice_check / choice / instant), ตัวจ่ายผล (gold/items/damage/heal/apply_status/force_continent/exp) + helper แจกไอเทม (กระเป๋าเต็ม→แปลงทองราคาขาย+แจ้ง)

**เฟส B — ทวีปใหม่ 6 (ง่าย→ยาก, 1 ขั้น = 1 ทวีปครบชุด: มอน+เรทธาตุ+element_overrides+อีเวนต์พิเศษ+arrival/travel text+test)**
- B1. ❄️ Frozen — มอนหิมะ, ambush ×1.5, สถานะ "ชา" (ไฟต์ยาวลดดาเมจผู้เล่น 50%), อีเวนต์พายุหิมะซุ่ม (dice: พลาด = ดาเมจเปิดฉากแล้วเข้าไฟต์)
- B2. 💀 Nether — มอนอันเดด, Life Drain (เลือดไหลต่อเทิร์นไฟต์ — mod `combat_hp_drain`), งานเลี้ยงบรรพชน (instant: สุ่มพร[ฮีล/ล้างสถานะหมด/ล้างสุ่ม] หรือสาป)
- B3. 🌋 Volcanic — มอนไฟ, ไฟ atk+20% (override), ภูเขาไฟระเบิด (dice: ผ่าน = เศษอัญมณี id 11 ×10, พลาด = ดาเมจ)
- B4. 🌲 Sylvan — มอนป่า, ไม้ root ×2 + EXP ×2 (override), พงหนามพิษ (choice: ลุย = ติดพิษ[ล้างเมื่อ village/npc] / อ้อม = เสียเงิน)
- B5. ⚙️ Mechanized — มอนจักรกล, ขุดหีบกลไก (dice: รางวัล ×2), สนาม EMP (choice: ฝ่า = สถานะ emp ปิดสกิลไฟต์ถัดไป [fight-tick])
- B6. ☁️ Skyward — มอนปีก, ลมบัฟ (override) + EXP ลม ×1.5-2, เกาะถล่ม (dice: ดาเมจเบา→ตาย + บังคับกลับทวีปหลักทุกกรณี)

**เฟส C — อีเวนต์โลกใหม่ 9 (ง่าย→ยาก)**
- C1. 👑 Royal Convoy (ข้อมูลล้วน: treasure×, gold×2, texts)
- C2. 🐉 Dragon Nesting (pool มังกร + dmg/dice + gold)
- C3. 🌑 Solar Eclipse (มืด hp×1.5+dice / hook `rank_weight_mult` ดันแรงค์ Secret)
- C4. ☄️ Mana Meteor (50% "อาบอุกกาบาต" dmg×2 + ไอเทม Mana Crystal + สูตรคราฟ + อีเวนต์เก็บคริสตัลหลังชนะ)
- C5. 🥶 Absolute Zero (สถานะ frostbite + น้ำ hp×2 + travel chance ×)
- C6. 🌕 Blood Moon (pool หมาป่า + hp/dice + วัสดุคราฟ ×2)
- C7. 🎲 Goddess Dice (กติกาเต๋าเปลี่ยนรายวัน + EXP/ทอง ×1.5)
- C8. 🎭 Masquerade (mini-design ตอนถึงขั้น: NPC ปลอม + ปุ่ม Inspect)
- C9. 🏴 Black Market (mini-design ตอนถึงขั้น: แตะระบบร้าน)
- C10. ตั้ง weight รวม: ธีมพิเศษทั้ง 11 ตัว = 1 เท่ากัน, สงบสุขสูงสุด (เสนอเลขตอนถึงขั้น) + test ทบตัวคูณ worst-case

**เฟส D — ปิดท้าย:** ตаราง stacking สูงสุด + full test + ชวนผู้ใช้เทสบอทจริงใน Discord ก่อน build แจกลูกค้า
