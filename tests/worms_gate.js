// 🚪 หน้าเลือกโหมดสนามรบต้องไม่มีจอเกมโผล่มาด้วย
// เจ้าของเกมเจอ 09-03: กดเข้าสนามรบแล้วเห็นทั้งปุ่มเลือกโหมด "และ" จอเกม/ปุ่มซูม พร้อมกัน
// สาเหตุ: wmShowGate() ซ่อนแค่ปุ่ม ไม่ได้ซ่อน .wm-stage (ไม่มี id ให้จับ)
const fs = require('fs');

const html = fs.readFileSync('license_server/web_static/play.html', 'utf8');
const js = fs.readFileSync('license_server/web_static/games/worms_ui.js', 'utf8');

let fail = 0;
const check = (label, ok, why) => {
  if (ok) { console.log(`  ✅ ${label}`); }
  else { console.log(`  ❌ ${label}${why ? ' — ' + why : ''}`); fail++; }
};

// ── โครง HTML ──
check('มีกล่อง #wmGameArea ห่อจอเกมไว้', html.includes('id="wmGameArea"'),
      'ไม่มีกล่องให้ซ่อน จอเกมจะโผล่คาหน้าเลือกโหมด');

const i = html.indexOf('id="wmGameArea"');
const close = html.indexOf('id="wmBotButtons"');
const inside = i >= 0 && close > i ? html.slice(i, close) : '';
for (const el of ['wmCanvas', 'wm-zoom', 'wm-hud', 'wmSkills', 'wmItems', 'wmLog']) {
  check(`${el} อยู่ในกล่องที่ซ่อนได้`, inside.includes(el),
        'อยู่นอกกล่อง จะโผล่ตอนอยู่หน้าเลือกโหมด');
}

check('กล่องเริ่มต้นเป็น hidden', /id="wmGameArea"\s+hidden/.test(html),
      'เปิดหน้ามาจอเกมโชว์ทันทีก่อนเลือกโหมด');

// ── ตรรกะ JS ──
check('wmShowGate ซ่อนจอเกม', /function wmShowGate[\s\S]*?wmGameArea\(false\)[\s\S]*?\n\}/.test(js),
      'กลับมาหน้าเลือกโหมดแล้วจอเกมยังค้าง');
check('มีฟังก์ชัน wmGameArea', js.includes('function wmGameArea'));

const botBtn = js.slice(js.indexOf("getElementById('wmModeBot')"), js.indexOf("getElementById('wmModeFriend')"));
check('กดซ้อมกับบอทแล้วโชว์จอเกม', botBtn.includes('wmGameArea(true)'),
      'เลือกโหมดแล้วจอไม่ขึ้น เล่นไม่ได้');

const frBtn = js.slice(js.indexOf("getElementById('wmModeFriend')"));
check('กดเล่นกับเพื่อนแล้วโชว์จอเกม', frBtn.slice(0, 400).includes('wmGameArea(true)'));

// ── จำลอง DOM จริง: ซ่อนแล้วโชว์ ──
const box = { hidden: false };
const fake = { getElementById: (id) => (id === 'wmGameArea' ? box : { hidden: false, classList: { add() {}, remove() {} } }) };
const run = new Function('document', 'wmRoomWatch', js.slice(js.indexOf('function wmShowGate'), js.indexOf('function wmGameArea')) +
  js.slice(js.indexOf('function wmGameArea'), js.indexOf('\n}', js.indexOf('function wmGameArea')) + 2) +
  '\n wmShowGate(); return document.getElementById("wmGameArea").hidden;');
check('เรียก wmShowGate() แล้วกล่องถูกซ่อนจริง', run(fake, () => {}) === true,
      'ตรรกะซ่อนไม่ทำงานจริง');

console.log(fail ? `\n  ${fail} ข้อไม่ผ่าน` : '\n  ผ่านหมด');
process.exit(fail ? 1 : 0);
