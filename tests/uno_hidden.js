// 🔍 ทุก element ที่ HTML สั่ง hidden ไว้ ต้องซ่อนได้จริงบนจอ
//
// เจ้าของเกมเจอ 08-29: JS สั่ง hidden สำเร็จแล้ว (เห็น hidden="" ใน DOM จริง ๆ)
// แต่แผงยังโชว์อยู่ กดปุ่มไหนก็ไม่หาย
// ต้นเหตุ: CSS ตั้ง display:grid ซึ่ง "ทับ" กฎ [hidden]{display:none} ของเบราว์เซอร์
// แผงอื่นในไฟล์นี้ (wm-over, foe-bar, ...) มีกฎคู่กันหมด — ของศึกไพ่รูนตกหล่นไป
const fs = require('fs');

const html = fs.readFileSync('license_server/web_static/play.html', 'utf8');
const css = fs.readFileSync('license_server/web_static/play.css', 'utf8');
let fail = 0;
let checked = 0;

// เก็บคลาสของ element ที่ตั้ง hidden ไว้ใน HTML
// เก็บคู่ (คลาส, id) — กันด้วย id ก็นับว่าปลอดภัย (เช่น #wmAim[hidden])
const seen = new Map();
const tags = /<[a-z]+[^>]*\shidden\b[^>]*>/g;
let tag;
while ((tag = tags.exec(html))) {
  const cls = /class="([^"]+)"/.exec(tag[0]);
  const id = /id="([^"]+)"/.exec(tag[0]);
  if (cls) cls[1].split(/\s+/).forEach(c => {
    if (c && !seen.has(c)) seen.set(c, id ? id[1] : '');
  });
}

if (!seen.size) {
  console.log('  ❌ หา element ที่ซ่อนไว้ไม่เจอเลย — เทสนี้ไม่ได้ตรวจอะไร');
  process.exit(1);
}

for (const [cls, id] of [...seen].sort()) {
  // หาบล็อกของคลาสนี้ (ข้ามบล็อกที่มี [ ต่อท้าย เช่น .cls[hidden])
  const block = new RegExp('\\.' + cls + '\\s*\\{([^}]*)\\}').exec(css);
  if (!block) continue;                       // ไม่มีสไตล์ = ใช้ค่าเริ่มต้น ปลอดภัย
  if (!/display\s*:/.test(block[1])) continue; // ไม่ได้ตั้ง display = ปลอดภัย

  checked++;
  if (css.includes('.' + cls + '[hidden]') || (id && css.includes('#' + id + '[hidden]'))) {
    console.log('  ✅ .' + cls);
  } else {
    console.log('  ❌ .' + cls + ' ตั้ง display ไว้ แต่ไม่มีกฎ [hidden] — สั่งซ่อนแล้วไม่หาย');
    fail++;
  }
}

if (!checked) {
  console.log('  ❌ ไม่มีคลาสไหนถูกตรวจเลย — เทสนี้ไม่ได้ตรวจอะไร');
  fail++;
}
process.exit(fail ? 1 : 0);
