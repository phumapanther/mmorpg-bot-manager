# Item Catalog & Extensible Item Effects — Design

วันที่: 2026-07-04
สถานะ: อนุมัติแบบตัดสินใจอัตโนมัติ (ผู้ใช้อนุมัติให้ตัดสินใจเองต่อเนื่องระหว่างพักผ่อน — ดูบริบทในบทสนทนา)

## 1. เป้าหมาย

เฟสที่ 2 ของการทำ config ปรับสมดุลเกม ครอบคลุม 2 หมวดที่ผู้ใช้ขอไว้ (รวมกันเพราะแก้ไฟล์ชุดเดียวกัน):
- **ราคาไอเทมในร้านค้า/คราฟต์** (หมวด 2 จากการสำรวจ)
- **รองรับการเพิ่มไอเทมกดใช้/อุปกรณ์ในอนาคตแบบไม่ต้องแก้โค้ด** (หมวด 8)

## 2. บริบทจากการสำรวจโค้ด (ยืนยันด้วยการอ่านโค้ดจริงอีกครั้ง)

`bot/views/profile_embed.py` มี 5 ตารางกลางที่มีโครงสร้างดีอยู่แล้ว: `ITEM_CONFIG` (28 ไอเทม), `ARMOR_STATS` (5), `WEAPON_STATS` (3), `BAG_STATS` (4), `CRAFTING_RECIPES` (11 สูตร)

**บั๊กที่เจอ 2 จุด (ยืนยันแล้ว จะแก้ในเฟสนี้):**
1. `bot/cogs/player_commands.py:398` — ไอเทม heal potion (id "1") ใช้ `heal_amount = 50` hardcode แยกจาก `ITEM_CONFIG` เลย ถ้าแอดมินปรับราคาคาดว่าจะปรับพลังฮีลด้วยไม่ได้
2. `bot/models/player_model.py:30-31` — ผู้เล่นใหม่เริ่มด้วย `"bag": "Medium_Bag"` แต่ `"capacity": 10` ในขณะที่ `BAG_STATS["Medium_Bag"]["capacity"]` จริงคือ `50` — ผู้เล่นใหม่ได้กระเป๋าเล็กทั้งที่ควรได้กระเป๋ากลาง

**ระบบไอเทมใช้ได้ (`use_item`, `bot/cogs/player_commands.py:365-532`) ตอนนี้เป็นแบบ hardcode-per-ID:**
- `type` ที่เป็น `armor`/`weapon`/`bag` **เป็น data-driven อยู่แล้ว** (อ่าน `equip_key` แล้วไป lookup stat dict) — ไม่ต้องแก้
- `type == "use"` ถูก special-case ด้วย literal ID: `if item_id == "1"` (ฮีล), `elif item_id == "2"` (ซ่อม)
- `type == "drop"` ใช้ `drop_map` dict แยกต่างหาก (id → ชื่อ state) บวก special-case แยกสำหรับ id "28" (ชุบชีวิต ต้องเช็คว่าตายจริง)

## 3. ขอบเขต

### อยู่ในเฟสนี้
1. ย้าย `ITEM_CONFIG`/`ARMOR_STATS`/`WEAPON_STATS`/`BAG_STATS`/`CRAFTING_RECIPES` ไป `config.json` ใต้ key `item_catalog`
2. เพิ่ม field `effect`/`effect_amount`/`effect_value` ใน `ITEM_CONFIG` แต่ละไอเทม แทนที่ literal-ID branching ใน `use_item` — ไอเทมใช้ได้ใหม่ในอนาคต (เช่น ยาฮีลสูตร 2, ไอเทม warp แบบใหม่) เพิ่มผ่าน config ได้เลยไม่ต้องแก้โค้ด **ตรงตามที่ผู้ใช้ขอไว้ตั้งแต่ต้น**
3. แก้บั๊กทั้ง 2 จุดข้างต้น
4. Panel: แท็บ "Items" ใหม่ — ตารางแก้ไขได้ 5 ชุด (Items, Armor, Weapon, Bag, Crafting Recipes)

### นอกเฟสนี้
- ราคาไอเทมดรอปเฉพาะ/ตารางดรอป (หมวด 3) — เฟสถัดไป (ใช้ `ITEM_CONFIG["buy"]` ที่ตั้งค่าได้แล้วจากเฟสนี้ในการคำนวณน้ำหนักดรอป แต่ตัวสูตรดรอปเองยังไม่แก้)
- มอนสเตอร์/EXP/เงิน/เปอร์เซ็นต์อื่นๆ — เฟสถัดไป

## 4. โครงสร้าง `effect` ใหม่ใน `ITEM_CONFIG`

แทนที่การเช็ค `item_id` ตรงๆ ด้วยการเช็ค `effect` string:

| effect | ความหมาย | field เสริม |
|---|---|---|
| `heal` | ฟื้น HP ตามจำนวนที่ตั้ง | `effect_amount` (int) |
| `repair` | ซ่อมเกราะ/อาวุธที่สวมใส่เต็ม (คำนวณจาก stat dict อัตโนมัติอยู่แล้ว) | ไม่ต้องมี |
| `revive` | ชุบชีวิต (เช็คว่าตายจริงก่อน) | ไม่ต้องมี |
| `set_state` | เปลี่ยน `last_event` เป็นค่าที่ตั้ง (ทริกเกอร์เหตุการณ์พิเศษ) | `effect_value` (string) |

ไอเทม armor/weapon/bag ไม่ต้องมี `effect` (ระบบเดิม data-driven อยู่แล้วผ่าน `type`+`equip_key`)

ตัวอย่างค่าเริ่มต้น (ตรงกับพฤติกรรมปัจจุบัน 100%):
```json
"1": {"name": "💉 ยาฮีล", "buy": 300, "sell": 100, "type": "use", "effect": "heal", "effect_amount": 50},
"2": {"name": "🛠️ ใบซ่อมแซม", "buy": 500, "sell": 150, "type": "use", "effect": "repair"},
"22": {"name": "📜ใบวาปเมือง", "buy": 500, "sell": 50, "type": "drop", "purchasable": false, "effect": "set_state", "effect_value": "warp_village"},
"28": {"name": "💌ใบชุบชีวิต", "buy": 5000, "sell": 500, "type": "drop", "purchasable": false, "effect": "revive"}
```
(items 23-27 ได้ `effect: "set_state"` พร้อม `effect_value` ตรงกับ `drop_map` เดิมทุกตัว)

## 5. `CRAFTING_RECIPES` — แก้ไขผ่าน UI แบบง่าย

Recipe แต่ละสูตรคือ `{item_id: qty}` — ให้แก้ผ่านช่องข้อความรูปแบบ `id:qty,id:qty` (เช่น `9:2,12:1`) แทนตัวแก้ไข list ซ้อน list ที่ซับซ้อนเกินจำเป็น (YAGNI — คราฟต์มีแค่ 11 สูตร ไม่คุ้มสร้าง sub-editor ซ้อน)

## 6. Panel UI — แท็บ "Items" ใหม่

5 ตารางแก้ไขได้ (add/delete แถวแบบเดียวกับ Auto-trade/Shop):
1. **Items** — id, name, buy, sell, type (dropdown: use/armor/weapon/bag/junk/drop), purchasable (checkbox), equip_key (dropdown จาก stat ชุดที่ตรงกับ type — โชว์เฉพาะ type armor/weapon/bag), effect (dropdown: -/heal/repair/revive/set_state — โชว์เฉพาะ type use/drop), effect_amount/effect_value (text/number โชว์ตาม effect ที่เลือก)
2. **Armor Stats** — key, name, hp, eva, dur, vis
3. **Weapon Stats** — key, name, atk, dur
4. **Bag Stats** — key, name, capacity
5. **Crafting Recipes** — item_id (dropdown จากตาราง Items), ingredients (text `id:qty,id:qty`), fail_rate

ปุ่มบันทึกเดียวสำหรับทั้งแท็บ (ทั้ง 5 ตารางไปด้วยกัน)

## 7. การแก้โค้ดฝั่งบอท

| ไฟล์ | การเปลี่ยนแปลง |
|---|---|
| `bot/config_loader.py` | เพิ่ม `get_item_config(item_id)`, `get_all_items()`, `get_armor_stats(key)`, `get_weapon_stats(key)`, `get_bag_stats(key)`, `get_crafting_recipe(item_id)` |
| `bot/models/player_model.py` | แก้ `NEW_PLAYER_DEFAULTS["capacity"]` จาก `10` เป็น `50` (ตรงกับ Medium_Bag จริง) |
| `bot/views/profile_embed.py` | `create_profile_embed` อ่าน stat จาก `config_loader` แทน module-level dict; ลบ `ITEM_CONFIG`/`ARMOR_STATS`/`WEAPON_STATS`/`BAG_STATS`/`CRAFTING_RECIPES` ทิ้ง |
| `bot/cogs/player_commands.py` | `use_item`/`craft`/`recipes`/`drop`/`give` อ่านจาก `config_loader` แทน import ตรงจาก `profile_embed`; `use_item`'s "use"/"drop" branch เปลี่ยนจาก literal-ID เช็คเป็นเช็ค `effect` field |
| `bot/cogs/admin_commands.py` | จุดที่ import `ITEM_CONFIG` (validate `!spawn`/`!give`/`!remove`) เปลี่ยนไปใช้ `config_loader.get_item_config`/`get_all_items` |
| `bot/views/game_views.py` | จุดที่ import `ARMOR_STATS`/`WEAPON_STATS`/`ITEM_CONFIG` (คอมแบท, ร้านค้า, ดรอป, กาชา) เปลี่ยนไปใช้ `config_loader` |
| `bot/cogs/pvp_duel.py` | จุดที่ import `ARMOR_STATS`/`WEAPON_STATS` (คำนวณสถิติ PvP) เปลี่ยนไปใช้ `config_loader` |

**ยืนยันด้วย repo-wide grep ก่อนเขียนแผน:** ไฟล์ที่อ้างถึง constant เหล่านี้มีแค่ 5 ไฟล์ (`profile_embed.py`, `game_views.py`, `pvp_duel.py`, `player_commands.py`, `admin_commands.py`) — `world_boss.py` **ไม่ได้**อ้างถึงเลย (import แค่ `SKILL_CONFIG` จาก `game_views.py` ซึ่งจัดการแยกไปแล้วในเฟสสกิล)

## 8. ความเสี่ยง

- ไฟล์ที่แตะเยอะ (5+ ไฟล์อ่าน `ITEM_CONFIG`/stat dicts) — ต้องแก้ทุกจุดพร้อมกันไม่งั้น import พัง เพราะจะลบ constant เดิมออกจาก `profile_embed.py`
- ผู้เล่นเก่าที่มี `capacity: 10` ในฐานข้อมูลอยู่แล้วจะไม่ได้รับผลจากการแก้ default (ค่า default มีผลกับผู้เล่น**ใหม่**เท่านั้น) — ไม่ retroactive ไม่ใช่บั๊กที่ต้องแก้เพิ่ม เป็นพฤติกรรมปกติของ default value
