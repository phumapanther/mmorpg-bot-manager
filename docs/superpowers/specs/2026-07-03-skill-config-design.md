# Skill Buff/Nerf Config — Design

วันที่: 2026-07-03
สถานะ: อนุมัติแล้ว (รอเขียนแผนลงมือทำ)

## 1. เป้าหมาย

เฟสแรกของการทำให้ค่าปรับสมดุลเกม (game balance) ตั้งค่าได้ผ่านหน้า Panel แทนการ hardcode
เฟสนี้ครอบคลุมเฉพาะ **สกิล buff/nerf ของคลาส** และ **บัพยศพิเศษที่ผูกกับ role** เท่านั้น
หมวดอื่น (มอนสเตอร์, ดรอป, EXP/เงิน, ราคาไอเทม) เป็นเฟสถัดไป

## 2. บริบทจากการสำรวจโค้ด

- `bot/views/game_views.py` มี `SKILL_CONFIG` (dict, class → skill → ค่าตัวเลข) เป็นตัวจริงที่ใช้งานอยู่ใน `MonsterEventView.process_turn`
- `bot/cogs/world_boss.py` มีระบบอ่านสกิลแยกต่างหาก แต่ **อ่าน key ที่ไม่มีอยู่จริงใน `SKILL_CONFIG`** (`chance`, `burn_damage`, `heal_amount`) — ผลคือสกิลไม่เคยติดในการต่อสู้ World Boss เลยตั้งแต่ต้น (บั๊กที่มีอยู่ก่อนงานนี้)
- บัพยศพิเศษ 3 อย่างมีอยู่จริงในโค้ด (ทีมงาน ×1.2 EXP ห้องเสียง, นักกวี ×1.5 EXP ห้องเสียง, ผู้ส่งสาร ×3 เงินแชท) จับคู่ด้วย**ชื่อยศ**แบบ hardcode ใน `voice_chat_tracker.py`/`player_commands.py`
- คอมเมนต์ใน `profile_embed.py` (`TEAMWORK_CLASSES`) บรรยายถึงบัพอัศวิน/นักบวชที่ไม่เคยถูกเขียนโค้ดจริง และตัวเลขของ 2 บัพที่มีจริงก็ไม่ตรงกับคอมเมนต์ — ยืนยันแล้วว่าคอมเมนต์เก่าไม่ได้อัปเดตตามโค้ด ไม่ใช่บั๊ก

## 3. ขอบเขต

### อยู่ในเฟสนี้
1. สกิล 8 ตัว (Warrior: heavy_strike, shield_bash / Mage: fireball, frostbolt / Rogue: backstab, evasion / Cleric: heal, holy_aura) — ตั้งค่าผ่าน Panel ได้
2. **แก้บั๊ก World Boss** ให้อ่าน schema เดียวกับ `game_views.py` จริง — เพื่อให้ config ที่ตั้งมีผลจริงทั้งสองจุดที่ใช้สกิล
3. บัพยศพิเศษ (ทีมงาน/นักกวี/ผู้ส่งสาร) — แปลงจากจับคู่ด้วยชื่อยศเป็น **role ID** (ตามหลักการทั้งโปรเจ็ค) + ตั้งค่าได้ผ่าน Panel
4. ลบ `TEAMWORK_CLASSES` และคอมเมนต์บรรยายที่เก่า/ไม่ตรงกับโค้ดจริงออก (data cleanup)

### นอกเฟสนี้ (ยืนยันกับผู้ใช้แล้วว่าเลื่อนไปทำทีหลัง)
- ค่าคอมแบทที่อยู่ติดกับ `process_turn` แต่ไม่ใช่ตัวสกิลเอง: ตาราง enrage ต่อระดับอันตรายมอนสเตอร์, % ลดดาเมจเกราะแบบคงที่ (0.2), ค่าเสื่อมอาวุธ/เทิร์น — จัดเป็นเฟส "มอนสเตอร์/คอมแบท" ในอนาคต
- บัพอัศวิน (+2 ลูกเต๋า) และนักบวช (+25% ฮีลตอน HP ต่ำ) — ยืนยันแล้วว่าเป็นคอมเมนต์เก่า ไม่ใช่ฟีเจอร์ที่ต้องสร้าง ไม่ทำในเฟสนี้
- หมวดอื่นทั้งหมด (ราคาร้านค้า/ดรอป, อัตราการเกิดมอนสเตอร์, เรท EXP/เงิน, ระบบไอเทมใช้แบบขยายได้) — เฟสถัดไปแยกกัน

## 4. โครงสร้าง config เพิ่มเติม (`config.json`)

```json
{
  "skills": {
    "Warrior": {
      "heavy_strike": {"chance_base": 80, "chance_lvl_scale": 1, "damage_multiplier": 2},
      "shield_bash":  {"duration": 3, "reduction_base": 0.50, "reduction_lvl_scale": 0.005}
    },
    "Mage": {
      "fireball":  {"duration": 2, "burn_base": 0.05, "burn_lvl_scale": 0.002},
      "frostbolt": {"duration_base": 1, "duration_lvl_scale": 0.05, "damage_reduce": 0.75}
    },
    "Rogue": {
      "backstab": {"chance_base": 50, "chance_lvl_scale": 0.5, "damage_reflect_mult": 1.5},
      "evasion":  {"chance_base": 100, "chance_lvl_scale": 0.0}
    },
    "Cleric": {
      "heal":      {"heal_percent_base": 0.40, "heal_lvl_scale": 0.01},
      "holy_aura": {"chance_base": 50, "chance_lvl_scale": 1}
    }
  },
  "role_bonuses": [
    {"label": "ทีมงาน (Staff) — โบนัส EXP ห้องเสียง", "role_id": null, "bonus_type": "voice_exp_multiplier", "value": 1.2},
    {"label": "นักกวี (Poet) — โบนัส EXP ห้องเสียง", "role_id": null, "bonus_type": "voice_exp_multiplier", "value": 1.5},
    {"label": "ผู้ส่งสาร (Messenger) — โบนัสเงินแชท", "role_id": null, "bonus_type": "chat_gold_multiplier", "value": 3.0}
  ]
}
```

ค่าเริ่มต้นใน `config.example.json` ใช้ตัวเลขเดิมที่มีอยู่ในโค้ดปัจจุบันทุกตัว (ไม่เปลี่ยนพฤติกรรมเกมตอนอัปเกรด)

**กติกา `role_bonuses`:**
- เป็นลิสต์ เพิ่ม/ลบแถวได้ไม่จำกัดจำนวน
- ถ้าผู้เล่นถือ role ที่ตรงกับหลายแถวพร้อมกัน (เช่นมีทั้งยศทีมงานและนักกวี) ตัวคูณจะ**คูณกันสะสม** ตรงกับพฤติกรรมเดิมของโค้ด
- `bonus_type` มีค่าตายตัว 2 แบบตอนนี้: `voice_exp_multiplier`, `chat_gold_multiplier` — ตรงกับกลไกที่มีอยู่จริงในโค้ด การเพิ่มประเภทบัพใหม่ที่ไม่เคยมีกลไกรองรับต้องแก้โค้ด ไม่ใช่แค่แก้ config (เหมือนหลักการเดียวกับ auto_trade_roles/shop_items)

## 5. การแก้โค้ดฝั่งบอท

| ไฟล์ | การเปลี่ยนแปลง |
|---|---|
| `bot/config_loader.py` | เพิ่ม `get_skill_config(class_name, skill_name) -> dict`, `get_role_bonuses(bonus_type) -> list[{role_id, value}]` |
| `bot/views/game_views.py` | `MonsterEventView.process_turn` เปลี่ยนจากอ่านค่าคงที่โมดูล `SKILL_CONFIG` เป็นเรียก `config_loader.get_skill_config(...)` ตอนประมวลผลเทิร์นจริง (อ่านสดตอนเรียกใช้ ไม่ cache ตอน import — รูปแบบเดียวกับ `role_shop.py`) |
| `bot/cogs/world_boss.py` | **แก้บั๊ก:** `get_random_skill`/`attack` เปลี่ยนไปอ่าน field ชุดเดียวกับที่ `game_views.py` ใช้จริงผ่าน `config_loader.get_skill_config` (`chance_base`+`chance_lvl_scale` แทน `chance`, ใช้ `damage_multiplier`/`burn_base`/`heal_percent_base` ของจริงแทน `burn_damage`/`heal_amount` ที่ไม่เคยมีอยู่) |
| `bot/cogs/voice_chat_tracker.py` | แทนที่ `if "ทีมงาน" in roles` และเช็คชื่อยศนักกวี ด้วยลูปอ่าน `config_loader.get_role_bonuses("voice_exp_multiplier")` เทียบด้วย role ID |
| `bot/cogs/player_commands.py` | แทนที่เช็คชื่อยศผู้ส่งสาร (คำนวณเงินแชท) ด้วย `get_role_bonuses("chat_gold_multiplier")` แบบเดียวกัน |
| `bot/views/profile_embed.py` | ลบ `TEAMWORK_CLASSES` และคอมเมนต์บรรยายที่เก่า/ไม่ตรงโค้ดจริง |

## 6. Panel UI — แท็บ "Skills" ใหม่

- การ์ดสกิล 8 ใบ จัดกลุ่มตามคลาส (Warrior/Mage/Rogue/Cleric หัวข้อคั่น) — แต่ละ field มี label ภาษาไทยเฉพาะของมัน (ไม่ใช่ raw key-value หรือ JSON ดิบ) ตามตัวอย่างที่อนุมัติ:
  ```
  [Warrior] เจาะเกราะสุดพลัง (heavy_strike)
    โอกาสติดสกิลพื้นฐาน (%):     [ 80 ]
    โอกาสเพิ่มต่อเลเวล (%):      [ 1  ]
    ตัวคูณดาเมจ:                [ 2  ]
  ```
- ใต้การ์ดสกิลเป็นส่วน "โบนัสยศพิเศษ" — ตารางเพิ่ม/ลบแถวได้แบบเดียวกับ Auto-trade/Shop: ชื่อ (text), dropdown เลือกยศ (reuse pattern ซ่อนยศที่เลือกไปแล้วในแถวอื่น ที่มีอยู่แล้วในแท็บ Auto-trade/Shop), dropdown ประเภทบัพ (2 ตัวเลือก), ช่องตัวเลขค่าตัวคูณ
- ปุ่ม "บันทึก" เดียวสำหรับทั้งแท็บ (skills + role_bonuses ไปด้วยกัน)

## 7. การทดสอบ

- `config_loader`: unit test `get_skill_config`/`get_role_bonuses` — กรณี key ไม่มี, กรณีมีหลายแถว `role_bonuses` ชนิดเดียวกัน
- **World Boss fix**: ต้องมี test พิสูจน์ว่าเปลี่ยนแปลงจริง — เช่น mock ให้ `chance_base`/`chance_lvl_scale` การันตีว่าติดสกิล แล้วเช็คว่า effect (ดาเมจ/heal/burn) ถูกคำนวณจาก field ที่ถูกต้องจริง ไม่ใช่ key เดิมที่ไม่มีอยู่
- `voice_chat_tracker`/`player_commands`: test ว่าสมาชิกที่มี role_id ตรง config ได้ตัวคูณ, ที่ไม่มีไม่ได้, และกรณีมีหลาย role พร้อมกันตัวคูณคูณกันสะสม
- ทดสอบ UI จริงในเบราว์เซอร์ (คลิกแก้ค่า, กดบันทึก, เช็คว่าเซฟถูก) เป็น manual step ให้ผู้ใช้ทำหลังโค้ดเสร็จ — ทำอัตโนมัติไม่ได้

## 8. ความเสี่ยง / จุดต้องระวัง

- การแก้บั๊ก World Boss เปลี่ยนพฤติกรรมเกมจริง (สกิลจะเริ่มติดในบอสที่ไม่เคยติดมาก่อน) — เป็นการเปลี่ยนแปลงที่ตั้งใจตามที่ผู้ใช้ยืนยันแล้ว ไม่ใช่ผลข้างเคียงที่ไม่คาดคิด
- การแปลงบัพยศจากชื่อเป็น ID หมายความว่า **ต้องตั้งค่า role ID ผ่าน Panel ก่อน** บัพถึงจะทำงาน (ค่าเริ่มต้น `role_id: null`) — ถ้าไม่ตั้งค่า บัพจะไม่ทำงานเงียบๆ (ผู้ดูแลต้องรู้ว่าต้องไปตั้งใน Panel หลังอัปเกรด)
