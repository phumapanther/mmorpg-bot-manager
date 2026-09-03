// 🎭 หน้าจอต่อสู้ปาร์ตี้ต้องวาดได้จริง — ไม่ใช่แค่ไฟล์มีอยู่
//
// เทสข้อความจับไม่ได้ว่าโค้ดรันแล้วพังไหม (เจอมาแล้วตอน !login เงียบ)
// ตัวนี้โหลด JS จริงเข้า vm แล้วสั่งวาดเฟรม + ป้อน events แบบเดียวกับที่เซิร์ฟเวอร์ส่ง
const fs = require('fs');
const vm = require('vm');

let fail = 0;
const ok = (label, cond, why) => {
  if (cond) console.log(`  ✅ ${label}`);
  else { console.log(`  ❌ ${label}${why ? ' — ' + why : ''}`); fail++; }
};

// ── canvas ปลอมที่นับว่าถูกเรียกอะไรบ้าง ──
const calls = [];
function fakeCtx() {
  const rec = name => (...a) => calls.push([name, ...a]);
  return new Proxy({}, {
    get: (_, k) => {
      if (k === 'createLinearGradient') return () => ({ addColorStop() {} });
      if (k === 'measureText') return () => ({ width: 10 });
      if (typeof k === 'string' && k.startsWith('_')) return undefined;
      return rec(k);
    },
    set: () => true,
  });
}

const el = () => ({
  width: 900, height: 420, style: {},
  innerHTML: '', dataset: {}, classList: { add() {}, remove() {}, contains: () => false },
  appendChild() {}, contains: () => true,
  getContext: () => fakeCtx(),
  getBoundingClientRect: () => ({ left: 0, top: 0, width: 900, height: 420 }),
  querySelectorAll: () => [], onclick: null,
});

const box = el();
const sandbox = {
  document: {
    getElementById: () => box,
    createElement: () => el(),
    querySelectorAll: () => [],
  },
  // ⚠️ rAF ของจริงเป็น async — เรียก cb ทันทีแบบ sync จะทำให้
  //    PB.raf ค้างเป็นค่า truthy หลัง recursion จบ แล้ว pbLoop() รอบต่อไปถูกกันออก
  //    (เจอตอนเขียนเทสนี้ — โค้ดไม่ผิด เทสปลอมผิด) จึงต้องเข้าคิวแล้วค่อยระบาย
  requestAnimationFrame: cb => { sandbox.__raf.push(cb); return sandbox.__raf.length; },
  cancelAnimationFrame: () => {},
  __raf: [],
  Math, console, JSON,
};
vm.createContext(sandbox);

/** ระบายคิวเฟรมแบบเบราว์เซอร์จริง — เฟรมถัดไปรันหลังเฟรมนี้จบ */
function drain(max = 200) {
  let n = 0;
  while (sandbox.__raf.length && n < max) {
    const cb = sandbox.__raf.shift();
    cb();
    n += 1;
  }
  return n;
}

// ── โหลด renderer จริง ──
try {
  vm.runInContext(
    fs.readFileSync('license_server/web_static/games/party/renderer_basic.js', 'utf8'),
    sandbox);
  ok('โหลด renderer_basic.js ได้ ไม่มี error ตอนอ่านโค้ด', true);
} catch (e) {
  ok('โหลด renderer_basic.js', false, e.message);
  process.exit(1);
}

for (const fn of ['pbMount', 'pbSetState', 'pbPlay', 'pbDraw']) {
  ok(`มีฟังก์ชัน ${fn}`, typeof sandbox[fn] === 'function');
}

// ── สถานะแบบเดียวกับที่ engine.view() ส่งมาจริง ──
const state = {
  in_battle: true,
  turn_of: 'p1',
  round: 1,
  over: false,
  winner: null,
  order: ['p1', 'm1', 'p2', 'm2'],
  units: [
    { id: 'p1', side: 'party', name: 'เอ', alive: true, defending: false, hp: 80, hp_max: 100, you: true },
    { id: 'm1', side: 'monster', name: 'มอน 1', alive: true, defending: false, hp_pct: 60 },
    { id: 'p2', side: 'party', name: 'บี', alive: true, defending: true, hp: 40, hp_max: 100, you: false },
    { id: 'm2', side: 'monster', name: 'มอน 2', alive: false, defending: false, hp_pct: 0 },
  ],
};

try {
  sandbox.pbMount('partyMount');
  sandbox.pbSetState(state);
  drain();
  ok('รับสถานะแล้ววาดได้', calls.length > 0, 'ไม่มีการวาดอะไรเลย');
} catch (e) {
  ok('รับสถานะแล้ววาด', false, e.message);
}

// ── ป้อนเหตุการณ์ทุกชนิดที่ events.py ส่งได้ ──
const before = calls.length;
try {
  sandbox.pbPlay([
    { t: 'turn_start', who: 'p1' },
    { t: 'dice', who: 'p1', rolls: [17, 4], total: 21 },
    { t: 'attack', from: 'p1', to: 'm1', dmg: 120, element: 'fire', crit: true },
    { t: 'aoe', from: 'p2', targets: ['m1', 'm2'], dmgs: [40, 35], element: 'water' },
    { t: 'heal', from: 'p2', to: 'p1', amount: 30 },
    { t: 'miss', from: 'm1', to: 'p1' },
    { t: 'die', who: 'm2' },
    { t: 'phase', who: 'm1', phase: 'rage' },
  ]);
  drain();
  ok('เล่นเหตุการณ์ครบ 8 ชนิดได้ ไม่มี error', true);
  ok('เหตุการณ์ทำให้เกิดการวาดเพิ่ม', calls.length > before);
} catch (e) {
  ok('เล่นเหตุการณ์', false, e.message);
}

// ── เลขลอยต้องอยู่ข้ามเฟรม ──
// ⚠️ ต้องใช้ 'heal' ล้วน ๆ เพราะ attack สั่งสั่นจอด้วย แล้วจอที่ยังสั่นอยู่
//    ก็ต่อเฟรมให้เอง — เทสจะผ่านทั้งที่เลขลอยตายตั้งแต่เฟรมแรก
//    (เจอตอนย้อนเทส: แก้ life เหลือ 1 เฟรมแล้วเทสยังเขียว)
try {
  const n = drain();
  ok('เฟรมนิ่งแล้วก่อนวัด', n === 0, `ยังค้าง ${n} เฟรม`);
  sandbox.pbPlay([{ t: 'heal', from: 'p2', to: 'p1', amount: 30 }]);
  ok('เลขลอยอยู่หลายเฟรม (อนิเมชันจริง ไม่ใช่วาดครั้งเดียว)', drain() > 1);
} catch (e) {
  ok('เลขลอยข้ามเฟรม', false, e.message);
}

// ── เหตุการณ์ที่ไม่รู้จักต้องไม่ทำให้พัง ──
try {
  sandbox.pbPlay([{ t: 'ยังไม่มีชนิดนี้', who: 'p1' }]);
  drain();
  ok('เหตุการณ์แปลก ๆ ไม่ทำให้จอพัง', true);
} catch (e) {
  ok('เหตุการณ์แปลก ๆ', false, e.message);
}

// ── สถานะว่าง / มอนตายหมด ──
try {
  sandbox.pbSetState(null);
  sandbox.pbSetState({ units: [], turn_of: null, over: true, winner: 'party' });
  drain();
  ok('สถานะว่างกับจบเกมไม่พัง', true);
} catch (e) {
  ok('สถานะว่าง', false, e.message);
}

// ── ห้ามคำนวณกติกาเอง ──
const src = fs.readFileSync('license_server/web_static/games/party/renderer_basic.js', 'utf8');
for (const bad of ['rollDice', 'calcDamage', 'element_multiplier']) {
  ok(`ไม่คำนวณกติกาเอง (${bad})`, !src.includes(bad),
     'renderer ต้องวาดอย่างเดียว กติกาอยู่ที่เซิร์ฟเวอร์');
}

console.log(fail ? `\n  ${fail} ข้อไม่ผ่าน` : '\n  ผ่านหมด');
process.exit(fail ? 1 : 0);
