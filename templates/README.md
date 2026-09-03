# 📦 เทมเพลตมินิเกม — สร้างเกมใหม่แล้วเมิร์จกลับเข้าโปรเจ็คนี้

โฟลเดอร์นี้มีเทมเพลตให้ก๊อปไปเป็น "บ้านแยกรายคน" — ทำมินิเกมใหม่ในแบบของ
ตัวเองได้เต็มที่ โดยโครงสร้างไฟล์ยังตรงกับเกมอื่นในโปรเจ็คเสมอ ทำให้เมิร์จ
กลับง่าย และคนอื่นเปิดโค้ดของคุณมาแล้วอ่านออกทันทีเพราะหน้าตาเหมือนเกมที่มีอยู่แล้ว

ตอนนี้มีเทมเพลตเดียว: **`minigame/`** (อ่านคู่มือเฉพาะที่
`templates/minigame/README.md`) — ตัวอย่างที่ทำเสร็จแล้วจริงดูได้ที่
`bot/games/casino/uno/` (เกมไพ่) และ `bot/games/pvp/` (สนามรบผลัดเทิร์น)

## ขั้นตอน: จากเทมเพลตจนเมิร์จกลับ

```bash
# 1. แตก branch ของตัวเอง
git checkout main && git pull
git checkout -b game/<ชื่อเกม>-<ชื่อคุณ>

# 2. ก๊อปเทมเพลตไปเป็นบ้านตัวเอง
cp -r templates/minigame/core bot/games/<หมวด>/<ชื่อเกม>
cp templates/minigame/web/game.js license_server/web_static/<ชื่อเกม>.js
cp -r templates/minigame/tests/* tests/     # เปลี่ยนชื่อไฟล์เป็นของเกมตัวเอง

# ⚠️ หลังก๊อป ต้องแก้ import ในไฟล์เทสที่ tests/ (และใน routes.py.snippet ถ้าเอามาใช้)
#    จาก "from templates.minigame.core import ..." เป็น
#    "from bot.games.<หมวด>.<ชื่อเกม> import ..." — ไฟล์ใน core/ ไม่ต้องแก้
#    (ใช้ relative import กันเองอยู่แล้ว อ่านรายละเอียดที่ templates/minigame/README.md)

# 3. ทำงานในโฟลเดอร์ตัวเองเท่านั้น — ไฟล์ที่แตะได้:
#    bot/games/<หมวด>/<ชื่อเกม>/**     ← บ้านคุณ แก้ได้เต็มที่
#    license_server/web_static/<ชื่อเกม>.js
#    tests/test_<ชื่อเกม>_*.py
#
#    ⚠️ ไฟล์ที่ "ต้องแตะแต่คนอื่นใช้ร่วม" — แก้ให้น้อยที่สุด แจ้งทีมก่อน:
#    license_server/web_api.py      (เพิ่ม endpoint ของเกมตัวเอง — ดู api/routes.py.snippet)
#    license_server/web_static/play.html  (เพิ่มปุ่ม — ดู web/panel.html.snippet)
#    license_server/rate_limit.py   (ถ้าเกมแตะเงิน — เพิ่ม path ลงกลุ่ม "money")

# 4. ก่อนส่ง: เทสต้องผ่านหมด
PYTHONIOENCODING=utf-8 python -m pytest -q

# 5. เมิร์จกลับ
git checkout main && git pull && git merge --no-ff game/<ชื่อเกม>-<ชื่อคุณ>
```

**3 ไฟล์ที่ใช้ร่วมกัน** (`web_api.py` · `play.html` · `rate_limit.py`) คือจุดที่
merge conflict เกิดบ่อยที่สุด — แก้เป็นก้อนเดียวจบในคอมมิตเดียว อย่ากระจายหลายที่
และแจ้งทีมก่อนแตะ กันชนกับคนอื่นที่กำลังเพิ่ม endpoint เกมตัวเองพร้อมกัน

## กฎเหล็ก 5 ข้อ (รายละเอียดเต็มอยู่ที่ `templates/minigame/README.md`)

1. เซิร์ฟเวอร์ตัดสินทุกอย่าง เบราว์เซอร์ส่งแค่ "กดปุ่มไหน"
2. `view(uid)` เป็นประตูเดียวก่อนส่งขึ้นเบราว์เซอร์ — ต้องมีเทส 2 ชั้น (ฟังก์ชัน + HTTP)
3. แตะเงินต้องมีเทส "ทองรวมก่อน = หลัง" + เพิ่ม path ลงกลุ่ม `money` ใน `rate_limit.py`
4. เกมห้าม import ข้ามเกม (มีเทสคุม เช่น `tests/test_casino_structure.py`)
5. ทำบอทก่อนโหมดหลายคนเสมอ — เทสคนเดียวได้ งานเดินเร็วกว่ามาก
