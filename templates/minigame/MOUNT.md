# สัญญาการเสียบเกมเข้าหน้าเว็บ

เจ้าของเกมให้อิสระเรื่องเอนจิน (2026-09-03) — **ทีมใช้อะไรก็ได้**
ขอแค่ **กดปุ่มเข้าจากหน้าเว็บเดียวกันได้** และไม่ไปกวนเกมของทีมอื่น

---

## 2 แบบ เลือกตามเอนจินที่ใช้

### 1. `inline` — Canvas 2D (แนะนำถ้าไม่มีเหตุผลต้องใช้อย่างอื่น)

เกมเดิมทุกเกมใช้แบบนี้ (สนามรบ · ศึกไพ่รูน) เบา เร็ว ใช้ตัวช่วยกลางร่วมกับหน้าอื่นได้

```html
<div id="myGameMount" class="party-mount"></div>
```
```js
// renderer สร้าง canvas ยัดเข้าไปเอง
const cv = document.createElement('canvas');
document.getElementById('myGameMount').appendChild(cv);
```

### 2. `iframe` — เอนจินหนัก (Phaser · Pygbag · อะไรก็ได้)

เกมโหลดในกล่องแยก — **เอนจินชนกันไม่ได้** เพราะคนละ JS context

```js
// ⚠️ ใส่ iframe "ตอนกดปุ่มเข้าเกม" เท่านั้น อย่าใส่ไว้ตั้งแต่โหลดหน้า
function openMyGame() {
  const mount = document.getElementById('myGameMount');
  if (mount.querySelector('iframe')) return;          // ใส่ซ้ำไม่ได้
  mount.innerHTML = '<iframe src="/games/mygame/index.html"></iframe>';
}
```

**ทำไมต้องรอกดปุ่มค่อยใส่**: วัดแล้ว Pygbag ต้องโหลด runtime **12 MB**
จาก CDN ภายนอก (`pygame-web.github.io`) — ใส่ไว้ตั้งแต่แรก **คนที่ไม่เล่นเกมนี้ก็โดนโหลดด้วย**
และถ้า CDN ล่ม หน้าเว็บทั้งหน้าจะค้าง

---

## CSS ของจุดเสียบต้องรองรับทั้งสองแบบ

ดูตัวอย่างที่ `.party-mount` ใน `license_server/web_static/play.css`:

```css
.party-mount { min-height: 320px; display: flex; align-items: center; justify-content: center; }
.party-mount canvas,
.party-mount iframe { width: 100%; max-width: 900px; height: auto; border: 0; border-radius: 12px; display: block; }

⚠️ ใช้ selector **ลูกหลาน** ไม่ใช่ลูกตรง (`>`) — เกมส่วนใหญ่ห่อจอไว้ในกล่องอีกชั้น
   ใช้ `>` แล้วกฎไม่โดน จอกางเต็มความกว้างจริงจนทะลุกรอบบนมือถือ
   (ชวนเพื่อนเดินทางเจอบั๊กนี้จริงตอนเทสด้วยมือ 2026-09-04)
```

---

## กฎที่ทุกแบบต้องทำตาม

1. **เซิร์ฟเวอร์ตัดสินทุกอย่าง** — เบราว์เซอร์ส่งแค่ "กดปุ่มไหน"
   ห้ามคำนวณดาเมจ/เงิน/ผลแพ้ชนะในฝั่งเบราว์เซอร์เด็ดขาด
2. **`view(uid)` เป็นประตูเดียว** ก่อนส่งข้อมูลขึ้นเบราว์เซอร์
   **ซ่อนด้วย CSS ไม่นับว่าซ่อน** — กด F12 ก็เห็นหมด
3. **แตะเงินต้องเพิ่ม path ลงกลุ่ม `money`** ใน `license_server/rate_limit.py`
   (ศึกไพ่รูนเคยลืม อยู่กลุ่ม `write` ที่หลวมกว่า — ตอนนี้มีเทสคุมแล้ว)
4. **เกมห้าม import ข้ามเกม** — มีเทสคุมที่ `tests/test_casino_structure.py`
5. **แกนเกม (Python) ห้ามรู้จักชื่อไฟล์ renderer** — ไม่งั้นเปลี่ยนกราฟิกไม่ได้

---

## แยกภาพออกจากกติกา (ทำให้เปลี่ยนกราฟิกได้ง่าย)

**เซิร์ฟเวอร์ส่ง "เหตุการณ์" ไม่ส่งภาพ**:

```json
{"t": "attack", "from": "p1", "to": "m2", "dmg": 120, "element": "fire", "crit": true}
{"t": "dice",   "who": "p1", "rolls": [17, 4], "total": 21}
```

renderer อ่านรายการนี้แล้วตีความเป็นภาพเอง
→ **เปลี่ยนกราฟิก = เขียน renderer ใหม่ ไม่ต้องแตะ Python เลย**
→ ทีมกราฟิกกับทีมกติกาทำงานคู่ขนานได้ ไม่ชนกัน

ตัวอย่างจริงดูที่ `bot/games/party/events.py`
