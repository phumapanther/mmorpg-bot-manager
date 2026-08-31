// 🔍 โหลด uno.js จริงในสภาพแวดล้อมจำลอง แล้ววาดหนึ่งเฟรม
// จับบั๊กที่เทสอ่านข้อความไม่มีทางเห็น เช่น const ถูกใช้ก่อนประกาศ (temporal dead zone)
// ซึ่งทำให้ลูปวาดพังทั้งลูป หน้าจอค้างหมด (เจ้าของเกมเจอ 08-29)
const fs = require('fs');
const vm = require('vm');

const src = fs.readFileSync('license_server/web_static/uno.js', 'utf8');
let fail = 0;
const el = () => ({ hidden: false, innerHTML: '', textContent: '', dataset: {},
                    classList: { toggle() {}, contains: () => false },
                    addEventListener() {}, getBoundingClientRect: () => ({ left:0, top:0, width:900, height:500 }),
                    querySelectorAll: () => [], onclick: null });

const ctx2d = new Proxy({}, { get: (t, k) => {
  if (k === 'canvas') return { width: 900, height: 500 };
  if (k === 'createLinearGradient' || k === 'createRadialGradient')
    return () => ({ addColorStop() {} });
  if (k === 'measureText') return () => ({ width: 10 });
  return () => {};
} });

const canvas = { ...el(), width: 900, height: 500, getContext: () => ctx2d };
let frames = 0, lastErr = null;

const sandbox = {
  console,
  document: { getElementById: id => (id === 'unoCanvas' ? canvas : el()),
              querySelectorAll: () => [] },
  addEventListener() {}, setTimeout, clearTimeout,
  requestAnimationFrame(fn) { if (++frames < 3) { try { fn(frames * 16.7); } catch (e) { lastErr = e; } } return 1; },
  _frames: () => frames,
  cancelAnimationFrame() {},
  performance: { now: () => 0 },
  SFX: { play() {}, music() {} },
  toast() {}, api: async () => ({ table: { playing: false } }),
  showPanel() {}, Math, JSON, Object, Array, String, Number, Promise, Date,
};
sandbox.window = sandbox;

try {
  vm.createContext(sandbox);
  vm.runInContext(src, sandbox);
  console.log('  ✅ โหลดไฟล์ได้ ไม่มี error ตอนอ่านโค้ด');
} catch (e) {
  console.log('  ❌ โหลดไฟล์ไม่ผ่าน:', e.message); process.exit(1);
}

// วาดหนึ่งเฟรมด้วยสถานะเกมจริง — ต้องไม่พัง
const table = {
  playing: true, over: false, my_turn: true, turn: 0, dir: 1, deck_left: 40,
  hand: [{ suit: 'fire', value: 5 }], playable: [0], top: { suit: 'fire', value: 2 },
  suit: 'fire', suits: { fire: '🔥 เพลิง' }, stack: 0, must_answer: false, drew: false,
  players: [{ name: 'คุณ', cards: 1, you: true }, { name: '🤖 บอท 1', cards: 5 }],
  winner: null, finished: [], my_place: 0, score: 0, log: [],
};
try {
  sandbox.unoApply(table);
  if (lastErr) throw lastErr;
  if (!frames) throw new Error('ลูปวาดไม่เคยทำงานเลย');
  console.log('  ✅ วาดเฟรมแรกได้ ไม่มี error (วาดไป ' + frames + ' เฟรม)');
} catch (e) {
  console.log('  ❌ วาดเฟรมแล้วพัง:', e.message); fail++;
}

// จบเกมแล้วต้องวาดต่อได้ (ตอนขึ้นตารางอันดับ)
try {
  lastErr = null;
  sandbox.unoApply({ ...table, over: true, my_turn: false,
    finished: [{ name: 'คุณ', place: 1, you: true, bot: false, left: 0 },
               { name: '🤖 บอท 1', place: 2, you: false, bot: true, left: 25 }] });
  if (lastErr) throw lastErr;
  console.log('  ✅ ตอนจบเกมวาดได้ ไม่มี error');
} catch (e) {
  console.log('  ❌ ตอนจบเกมพัง:', e.message); fail++;
}


// 🔁 กดเล่นอีกรอบ: จบเกม -> เปิดโต๊ะใหม่ -> ตารางอันดับต้องหาย
// (เจ้าของเกมเจอ 08-29: "คลิกเล่นอีกรอบหน้ามันไม่หาย")
const overBox = { hidden: false };
sandbox.document.getElementById = id =>
  id === 'unoCanvas' ? canvas : id === 'unoOver' ? overBox : el();
try {
  lastErr = null;
  sandbox.unoApply({ ...table, over: true, my_turn: false,
    finished: [{ name: 'คุณ', place: 1, you: true, bot: false, left: 0 },
               { name: '🤖 บอท 1', place: 2, you: false, bot: true, left: 25 }] });
  if (overBox.hidden) throw new Error('จบเกมแล้วตารางไม่ขึ้น');
  sandbox.unoApply(table);                      // เปิดโต๊ะใหม่
  if (lastErr) throw lastErr;
  if (!overBox.hidden) throw new Error('เปิดโต๊ะใหม่แล้วตารางอันดับยังค้างอยู่');
  console.log('  ✅ เล่นอีกรอบแล้วตารางอันดับหายจริง');
} catch (e) {
  console.log('  ❌ ' + e.message); fail++;
}
process.exit(fail ? 1 : 0);
