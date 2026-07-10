# Community Bot Manager — Design (v1)

วันที่: 2026-07-10
สถานะ: รอรีวิว
โปรเจ็คต้นทาง: `mmorpg-bot-manager` (fork แล้วตัดส่วนเกมออก)

## 1. เป้าหมาย

โปรแกรมจัดการบอทคอมมูนิตี้ Discord ครบวงจร — เจ้าของเซิร์ฟดับเบิลคลิก `.exe` →
ตั้งค่าทุกระบบผ่านหน้าเว็บ localhost → กด Start ใช้งานได้ทันที ขายต่อได้ด้วยระบบ license เดิม

ระบบทั้งหมด: ธนาคาร/เศรษฐกิจ, คาสิโน (ไฮโล/สล็อต/แบล็คแจ็ค/หวย), พิมพ์คุยรับเงิน,
รายวัน+leaderboard, เลเวล (แชท+voice) พร้อมแจ้งเตือน/รางวัล, เพลง YouTube, Watch Together,
ร้านยศ (ซื้อขาด+กาชา), ทิคเก็ต+เติมเงิน PromptPay, custom commands, ตั้งค่าคำสั่ง+สิทธิ์,
ต้อนรับสมาชิก+ยศออโต้, giveaway

## 2. การตัดสินใจหลัก (จากการ brainstorm)

| หัวข้อ | ข้อสรุป |
|---|---|
| สถาปัตยกรรม | **Fork ตัด+เติม** จาก mmorpg-bot-manager (ไม่เขียนใหม่ ไม่ทำ plugin framework) |
| ระบบหนัง | ❌ ไม่มีสตรีมหนังโดยบอท (Discord ไม่เปิด API ให้บอทสตรีมวิดีโอ) → ใช้ `!movie` สร้างลิงก์ **Watch Together** แทน |
| แหล่งเพลง | YouTube ผ่าน **yt-dlp standalone exe** + ffmpeg (vendor แยก ไม่ freeze รวม) |
| สกุลเงิน | **สกุลเดียว** ใช้ร่วมทุกระบบ ตั้งชื่อ+อีโมจิได้ใน panel |
| ธนาคาร | เช็คยอด + โอน (มีค่าธรรมเนียม) + ฝาก/ถอนแยกกระเป๋า (cash/bank) |
| Custom commands | ครบ 3 ชั้น: ตั้งค่าคำสั่ง built-in / คำสั่งตอบข้อความ / คำสั่ง action (ให้เงิน/ยศ) |
| เลเวล | XP จากแชท+voice, เลเวลอัพได้เงิน+ยศออโต้, แจ้งเตือนห้องที่กำหนด |
| ทิคเก็ต | ระบบกลาง หลายประเภท (เติมเงิน + ติดต่อทั่วไป) แอดมินสร้างประเภทเองใน panel |
| ระบบเสริม | หวย, รายวัน+leaderboard, ต้อนรับ+ยศออโต้, giveaway |
| ประวัติธุรกรรม | เพิ่มตาราง `transactions` (ledger) — จำเป็นเพราะรับเงินจริง ใช้ตรวจข้อพิพาท |

## 3. สิ่งที่ยกมา / ตัดทิ้ง

**ยกมาแก้น้อย:** panel ทั้งชุด (FastAPI, config.json, process_manager, SSE log, Discord REST
dropdown), license_server + license_client, promptpay.py, การแพ็ก exe (PyInstaller/Nuitka/
installer zip), cogs: casino, blackjack, role_shop, private_room, owner_announce,
voice_chat_tracker (เอาโครงมาทำ voice XP)

**ตัดทิ้ง:** adventure_zone, world_boss, pvp_duel, game_commands, player_commands,
bot_brain/trainer (ML), player_model (แทนด้วย economy ใหม่)

## 4. ธรรมเนียม Feature Module (หัวใจความ "เผื่ออนาคต")

ทุกระบบทำตามกติกา 4 ข้อ:

1. **1 ระบบ = 1 cog** ใน `bot/cogs/` — ไม่ยุ่งข้ามระบบ ยกเว้นผ่าน `economy`
2. **1 section ใน config.json** มี `"enabled": true/false` เสมอ — ปิดแล้ว `main.py` ไม่โหลด cog นั้นเลย
3. **เงินทุกบาทผ่าน `bot/models/economy.py` ที่เดียว** — ห้าม cog แตะ DB เงินตรง
4. **1 แท็บ panel ต่อระบบ** (หรือรวมกลุ่มใกล้เคียง) + ปุ่มบันทึก + เตือน restart

เพิ่มระบบใหม่ = สร้าง cog + เพิ่ม config section + เพิ่มแท็บ — ไม่แตะของเดิม
ถ้าอนาคตแท็บเยอะจนเขียนมือไม่ไหว ค่อยยกระดับเป็น schema-driven UI ได้โดยไม่รื้อโครง

## 5. Data Layer

`bot/models/db.py` — SQLite ไฟล์เดียว `data.db`, WAL mode, timeout กัน lock,
สร้างตารางอัตโนมัติตอนสตาร์ท, **backup อัตโนมัติวันละครั้ง เก็บ 7 ชุดล่าสุด**

`bot/models/economy.py` — ที่เดียวที่แตะตารางเงิน:
- `get_wallet(user_id)` → `{cash, bank}`
- `adjust(user_id, amount, type, note)` — atomic, เช็คยอดก่อนหักใน transaction เดียวกัน
  ยอดไม่พอ = raise, ไม่มีทางติดลบ; เขียน `transactions` ทุกครั้ง
- `transfer(from_id, to_id, amount)` — หักค่าธรรมเนียม % ตาม config
- `deposit(user_id, amount)` / `withdraw(user_id, amount)` — ย้าย cash⇄bank

ตาราง:

```
wallets        user_id PK | cash | bank
transactions   id | user_id | amount | balance_after | type | note | created_at
levels         user_id PK | xp | level | last_chat_xp_at
daily_claims   user_id PK | last_claim_date | streak
tickets        id | user_id | channel_id | type | status | amount | created_at
lottery_rounds id | draw_at | status | winning_number | prize_pool
lottery_tickets id | round_id | user_id | number
giveaways      id | prize_type | prize_value | ends_at | channel_id | message_id | winners_count | status
giveaway_entries giveaway_id | user_id
```

Custom commands / ตั้งค่าคำสั่ง / กลุ่มสิทธิ์ เก็บใน `config.json` (เป็น "การตั้งค่า" ไม่ใช่ "ข้อมูล")

**กติกาเงิน:** cash = ใช้จ่าย/เดิมพันได้, bank = ฝากปลอดภัย ใช้ไม่ได้จนกว่าถอน;
คาสิโน/หวย/ร้านยศ หักจาก cash เท่านั้น

## 6. สเปกรายระบบ

### 6.1 💰 economy cog
- `!bal` (cash+bank), `!transfer @user amount` (ค่าธรรมเนียม % ตั้งได้), `!deposit`/`!withdraw`
- แอดมิน: `!addcash` `!removecash` `!setcash` `!balof @user`
- **พิมพ์คุยรับเงิน:** on_message → เงินสุ่ม min–max + cooldown ต่อคน + allow/deny list ห้อง
- **รายวัน:** `!daily` ฐาน + โบนัส streak (ตั้งได้ทั้งคู่) — ขาดวัน streak รีเซ็ต
- **Leaderboard:** `!top` (รวย = cash+bank) / `!top level`

### 6.2 🎰 casino cogs (เดิม rewire) + lottery cog (ใหม่)
- Hi-Lo, สล็อต, Blackjack: เปลี่ยน player_model → economy; ตั้ง enabled + min/max bet รายเกม
- **หวย:** `!lotto ซื้อ <เลข>` (จำนวนหลัก 2-3 ตั้งได้, ราคาต่อใบตั้งได้) →
  ออกรางวัลอัตโนมัติตามเวลา (cron ใน cog, เช่น ทุกวัน 20:00) หรือแอดมินสั่ง `!lotto ออก` →
  รางวัล = fixed หรือ % ยอดขาย (ตั้งได้) แบ่งเท่ากันถ้าถูกหลายคน → ประกาศห้องที่กำหนด →
  รอบใหม่เปิดอัตโนมัติ

### 6.3 📈 leveling cog
- XP แชท: ต่อข้อความ + cooldown (default 60s); XP voice: ต่อนาที (โครง voice_chat_tracker เดิม
  — ไม่นับคน mute/อยู่คนเดียว, เงื่อนไขตั้งได้)
- สูตร: `xp_needed(level) = base × level^factor` (default เทียบ MEE6)
- เลเวลอัพ → ประกาศห้องที่กำหนด (template `{user}` `{level}`) + เงินรางวัล (ต่อเลเวล ตั้งได้)
  + ยศตาม mapping เลเวล→role_id (โหมดสะสม/แทนที่ เลือกได้)
- `!rank` ดูเลเวล/XP ตัวเอง

### 6.4 🎵 music cog (+ Watch Together)
- `!play <ชื่อ/URL>` → ค้น YouTube ผ่าน yt-dlp → ต่อคิว; `!skip` `!stop` `!pause` `!resume`
  `!queue` `!np` `!vol`
- **yt-dlp เป็น standalone exe ใน `vendor/`** เรียกผ่าน subprocess (ไม่ freeze เข้า exe หลัก)
  + `vendor/ffmpeg.exe` → panel มีปุ่ม "อัปเดต yt-dlp" (รัน `yt-dlp -U`) —
  YouTube เปลี่ยนโครงเมื่อไหร่ ลูกค้ากดปุ่มเดียวหาย ไม่ต้องรอ build ใหม่
- ต้องเพิ่ม dep: PyNaCl (voice)
- `!movie <ลิงก์ YouTube>` → สร้าง invite ของ voice channel ที่ผู้ใช้อยู่ พร้อม
  `target_application_id` = Watch Together → ดูพร้อมกันตาม ToS

### 6.5 👑 role_shop cog (เดิม rewire)
- ซื้อขาด: รายการยศ+ราคา (panel), กาชา: pool + ราคาต่อครั้ง (ของเดิมทั้งคู่ เปลี่ยนแค่ระบบเงิน)

### 6.6 🎫 tickets cog (ใหม่)
- Panel กำหนดประเภททิคเก็ต: ชื่อ, อีโมจิ, ชนิด (`topup`/`general`), ยศ staff, category
- บอทโพสต์แผงปุ่มในห้องที่กำหนด (คำสั่ง `!ticketpanel` หรือปุ่มใน panel) →
  สมาชิกกด → สร้าง text channel ส่วนตัว (เห็นเฉพาะผู้เปิด+staff) — จำกัด 1 ทิคเก็ตเปิดค้าง/คน/ประเภท
- **topup:** modal ถามจำนวนบาท → QR PromptPay (promptpay.py เดิม) + แสดงเรทแปลง
  บาท→เงินเซิร์ฟ (ตั้งได้) → ลูกค้าส่งสลิป → staff กด "ยืนยัน" →
  credit ผ่าน economy + บันทึก transaction (type=`topup`) + transcript ลงไฟล์ + ปิดห้อง
  — **ปุ่มยืนยัน idempotent:** เช็คสถานะใน DB ก่อน credit กัน staff กดซ้ำ/พร้อมกัน
- **general:** เปิดห้อง + ping staff + ปุ่มปิดทิคเก็ต (staff หรือผู้เปิด)

### 6.7 ⌨️ commands cog (ใหม่) — 3 ชั้น
1. **ตั้งค่า built-in:** ทุกคำสั่งมีรายการใน panel — เปลี่ยนชื่อ/alias, เปิด/ปิด, จำกัดห้อง,
   จำกัดกลุ่มสิทธิ์ → ทำเป็น **global check ตัวเดียว** อ่าน config ตอนรันคำสั่ง;
   alias/ชื่อใหม่ apply ตอนบอทสตาร์ท
2. **คำสั่งตอบข้อความ:** panel CRUD — trigger, ตอบ text/embed/รูป(URL), จำกัดห้อง/สิทธิ์, cooldown
3. **คำสั่ง action:** panel CRUD — ให้เงิน (fix หรือสุ่มช่วง + cooldown ต่อคน) หรือให้ยศ
- ลงทะเบียน dynamic ตอนสตาร์ทจาก config; ชื่อชนกับ built-in → custom แพ้ + เตือนใน panel

### 6.8 🛡️ permissions (ยกระดับจากเดิม)
- เดิม 3 กลุ่ม hardcode → **สร้างกลุ่มได้ไม่จำกัด** ใน panel (ชื่อ + role_ids)
- ทุกระบบอ้างชื่อกลุ่ม (คำสั่ง built-in, custom commands, ทิคเก็ต staff)
- Owner ผ่านเสมอ; decorator `has_permission(group)` ของเดิมใช้ต่อ แค่กลุ่มมาจาก config

### 6.9 👋 welcome cog (ใหม่)
- on_member_join → ข้อความ/embed ต้อนรับ (template `{user}` `{server}` `{count}`)
  ในห้องที่กำหนด + แจกยศแรกเข้าอัตโนมัติ (หลายยศได้)

### 6.10 🎉 giveaway cog (ใหม่)
- แอดมินสร้าง (คำสั่งหรือ panel): รางวัล (เงิน/ยศ/ข้อความ), ระยะเวลา, จำนวนผู้ชนะ
- บอทโพสต์ embed + ปุ่มเข้าร่วม → ครบเวลาสุ่มผู้ชนะ ประกาศ + แจกอัตโนมัติ (เงินผ่าน economy,
  ยศผ่าน add_roles)
- เก็บ `ends_at` ใน DB → บอทดับแล้วสตาร์ทใหม่ เช็คของเลยเวลา ออกผลย้อนหลังทันที (หวยก็ใช้กติกานี้)

### 6.11 คงเดิม
- private_room, owner_announce — ยกมาทั้งดุ้น เพิ่มแค่ `enabled` flag

## 7. Panel — 10 แท็บ

| แท็บ | เนื้อหา |
|---|---|
| Setup | token, license key, เลือก guild (เดิม) |
| Dashboard | start/stop/restart, สถานะ, log สด (เดิม) |
| เศรษฐกิจ | สกุลเงิน (ชื่อ+อีโมจิ), พิมพ์คุยรับเงิน, daily, ค่าธรรมเนียมโอน, ประวัติธุรกรรม (ค้นตาม user) |
| เลเวล | อัตรา XP แชท/voice, สูตร, ห้องประกาศ+template, รางวัล (เงิน/ยศ mapping) |
| คาสิโน | เปิด/ปิด + min/max รายเกม, หวย (ราคา/หลัก/เวลาออก/รางวัล/ห้องประกาศ) |
| เพลง | ห้องที่ใช้ได้, volume default, ปุ่มอัปเดต yt-dlp |
| ร้านยศ | ตารางซื้อขาด + กาชา pool (เดิม) |
| ทิคเก็ต | ประเภททิคเก็ต CRUD, ห้องแผงปุ่ม, เรทเติมเงิน, บัญชี PromptPay |
| คำสั่ง & สิทธิ์ | กลุ่มสิทธิ์ CRUD, ตั้งค่า built-in, custom commands CRUD |
| กิจกรรม | welcome + ยศแรกเข้า, giveaway |

REST เพิ่มจากเดิม: `GET /api/transactions?user_id=`, `POST /api/ytdlp/update`,
`GET /api/commands` (รายชื่อ built-in ทั้งหมดให้แท็บคำสั่ง)

## 8. โครงไฟล์

```
community-bot-manager/
├── config.json / config.example.json
├── launcher.py, build.spec, build_nuitka.py, make_installer_zip.py   # เดิม
├── vendor/                        # ffmpeg.exe, yt-dlp.exe
├── bot/
│   ├── main.py                    # โหลดเฉพาะ cog ที่ enabled
│   ├── config_loader.py           # เดิม + get_feature(key), is_enabled(key)
│   ├── utils.py                   # allowed_channel, has_permission (generalized)
│   ├── promptpay.py, license_client.py    # เดิม
│   ├── models/db.py               # SQLite + WAL + สร้างตาราง + backup รายวัน
│   ├── models/economy.py          # ★ ที่เดียวที่แตะเงิน
│   └── cogs/                      # economy, casino, blackjack, lottery, leveling,
│                                  # music, role_shop, tickets, commands, welcome,
│                                  # giveaway, private_room, owner_announce
├── panel/                         # เดิม + แท็บ/route ใหม่
└── license_server/                # เดิม ไม่แตะ
```

## 9. การจัดการข้อผิดพลาด

- **เงิน:** เช็คยอด+หักใน SQLite transaction เดียว — ไม่มีติดลบ, ไม่มี race (คาสิโนพร้อมแชทรับเงิน)
- **ยืนยันเติมเงินซ้ำ:** สถานะ ticket ใน DB เป็นตัวตัดสิน — credit ได้ครั้งเดียว
- **เพลง:** yt-dlp ล้มเหลว → แจ้งแชท + ชี้ไปปุ่มอัปเดต; โดนเตะจาก voice → เคลียร์คิว
- **หวย/giveaway ค้างตอนบอทดับ:** สตาร์ทแล้วเช็ค `ends_at`/`draw_at` ที่เลยเวลา → ออกผลย้อนหลัง
- **DB:** WAL + timeout; backup รายวัน 7 ชุด (เงินจริงอยู่ในไฟล์นี้)
- **Token/config เดิม:** พฤติกรรมเดิมทั้งหมด (401 → แจ้ง, config เสีย → fallback example)

## 10. การทดสอบ (pytest ตามแนวเดิม)

economy (adjust/transfer/atomic/ยอดไม่พอ/ledger ถูกเขียน), สูตรเลเวล+level-up detection,
หวย (จับคู่เลข/แบ่งรางวัล), daily streak (ต่อเนื่อง/ขาด), custom command matcher +
built-in gate, config_loader ส่วนใหม่, idempotent ticket confirm —
UI/voice/เพลง ทดสอบ manual

## 11. ลำดับการสร้าง (แต่ละเฟสจบแล้วใช้งานได้จริง)

1. **Fork + ตัดเกม + economy core** — db/economy/ledger + คาสิโน rewire + พิมพ์คุยรับเงิน +
   daily + top + แท็บเศรษฐกิจ/คาสิโน → *บอทเศรษฐกิจ+คาสิโนขายได้แล้ว*
2. **เลเวล + ร้านยศ + welcome** — engagement ครบวงจร
3. **ทิคเก็ต + เติมเงิน PromptPay** — เริ่มรับเงินจริง
4. **คำสั่ง & สิทธิ์** — custom commands 3 ชั้น + กลุ่มสิทธิ์ไม่จำกัด
5. **เพลง + Watch Together** — deps หนักสุด (ffmpeg/yt-dlp/PyNaCl) แยกไว้ท้าย
6. **หวย + giveaway** — ระบบกิจกรรม

## 12. ความเสี่ยง

- **yt-dlp พังตาม YouTube** → ปุ่มอัปเดตใน panel (ออกแบบไว้แล้ว)
- **ขนาด exe +~100MB** จาก vendor (ffmpeg/yt-dlp) — ยอมรับ, เป็นไฟล์แยกไม่ freeze รวม
- **รับเงินจริง** → ledger + idempotent confirm + backup รายวัน
- **โค้ด infra 2 ชุด** (โปรเจ็คเดิม/ใหม่) — บั๊ก infra ต้องแก้ 2 ที่ (ยอมรับตั้งแต่โปรเจ็คแรก)
