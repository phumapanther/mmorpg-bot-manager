// 🔍 โหลดสคริปต์ฝั่งสนามรบจริงตามลำดับใน play.html แล้ววาดหลายเฟรม
//
// เก็บเส้นฐานไว้ก่อนผ่า play.js (09-02 ขั้นที่ 5) — จับ ReferenceError ที่เทสอ่านข้อความ
// มองไม่เห็น เช่น ย้ายฟังก์ชัน wm* ไปไฟล์ใหม่แล้วลืมย้ายตัวแปร global คู่กัน
// (แบบเดียวกับที่ uno_boot.js เคยจับปัญหา const ถูกใช้ก่อนประกาศมาแล้ว)
//
// เทสนี้ทำงานได้ทั้งก่อน/หลังผ่าไฟล์ — playSource() รวม games/worms_ui.js ให้อัตโนมัติ
// ถ้ามีไฟล์นั้นแล้ว (ดู tests/_js_source.js)
const fs = require('fs');
const path = require('path');
const vm = require('vm');
const { WEB, playSource } = require('./_js_source');

const read = f => fs.readFileSync(f, 'utf8');
// ลำดับ <script> จริงใน play.html (บรรทัด 1444-1451 ก่อนผ่า)
const HEAD = ['web.js', 'sfx.js', 'worms.js', 'walk.js', 'sprite.js', 'scene.js']
  .map(f => read(path.join(WEB, f))).join('\n');
const TAIL = read(path.join(WEB, 'uno.js'));
const MID = playSource();   // play.js (+ games/worms_ui.js + shop_ui.js ถ้ามีไฟล์แล้ว)

let fail = 0;
const errors = [];

const el = () => ({
  hidden: false, innerHTML: '', textContent: '', dataset: {}, style: {}, onclick: null,
  classList: { toggle() {}, contains: () => false, add() {}, remove() {} },
  addEventListener() {}, removeEventListener() {},
  getBoundingClientRect: () => ({ left: 0, top: 0, width: 900, height: 400 }),
  querySelectorAll: () => [],
});

const ctx2d = new Proxy({}, {
  get: (t, k) => {
    if (k === 'canvas') return { width: 900, height: 400 };
    if (k === 'createLinearGradient' || k === 'createRadialGradient')
      return () => ({ addColorStop() {} });
    if (k === 'measureText') return () => ({ width: 10 });
    if (k === 'createImageData') return (w, h) => ({ width: w, height: h, data: new Uint8ClampedArray(w * h * 4) });
    if (k === 'getImageData') return () => ({ data: new Uint8ClampedArray(4) });
    return () => {};
  },
  set: () => true,
});
const makeCanvas = (w, h) => ({ ...el(), width: w, height: h, getContext: () => ctx2d });

const wmCanvas = makeCanvas(900, 400);
const wormsPanel = el();
wormsPanel.classList = { toggle() {}, add() {}, remove() {}, contains: cls => cls === 'on' };
const boxes = { wmCanvas, 'v-worms': wormsPanel };
const getEl = id => boxes[id] || (boxes[id] = el());

let frames = 0;

const store = {};
const localStorage = {
  getItem: k => (k in store ? store[k] : null),
  setItem: (k, v) => { store[k] = String(v); },
  removeItem: k => { delete store[k]; },
};

const sandbox = {
  console: { ...console, error: (...a) => errors.push(a.map(String).join(' ')) },
  document: {
    getElementById: getEl,
    querySelectorAll: () => [],
    addEventListener() {}, removeEventListener() {},
    createElement: () => makeCanvas(1, 1),
    body: el(),
  },
  localStorage,
  addEventListener() {}, removeEventListener() {},
  setTimeout, clearTimeout, setInterval, clearInterval,
  requestAnimationFrame(fn) {
    if (++frames <= 5) { try { fn(frames * 16.7); } catch (e) { errors.push('rAF throw: ' + e.message); } }
    return frames;
  },
  cancelAnimationFrame() {},
  performance: { now: () => frames * 16.7 },
  SFX: { play() {}, music() {}, resume() {} },
  api: async () => ({}), prompt: () => null, confirm: () => false,
  location: { href: '' },
  Math, JSON, Object, Array, String, Number, Promise, Date, Uint8Array, Uint8ClampedArray,
};
sandbox.window = sandbox;
sandbox.__wmCanvas = wmCanvas;

try {
  vm.createContext(sandbox);
  vm.runInContext(HEAD + '\n' + MID + '\n' + TAIL, sandbox);
  console.log('  ✅ โหลดสคริปต์ตามลำดับ play.html ได้ครบ ไม่มี error ตอนอ่านโค้ด');
} catch (e) {
  console.log('  ❌ โหลดไฟล์ไม่ผ่าน:', e.message);
  process.exit(1);
}

// ── ฟังก์ชันหลักของสนามรบต้องยังอยู่ครบหลังโหลด (function ประกาศ top-level ติด context เสมอ)
//    ⚠️ class (WormsMap/WormsCam) ไม่ติด context แบบ function — ทดสอบด้วยการ new จริงด้านล่างแทน ──
const mustHave = ['wmStartLoop', 'wmTick', 'wmMe', 'wmNewMatch', 'wmEndTurn', 'wmDrawFighter',
                  'wmShowGate', 'wmHoldStart', 'wmHoldStop', 'fillWorms'];
for (const name of mustHave) {
  if (typeof sandbox[name] !== 'function') { console.log('  ❌ หายไปหลังโหลด:', name); fail++; }
}
if (!fail) console.log('  ✅ ฟังก์ชัน/คลาสหลักของสนามรบยังอยู่ครบ (' + mustHave.length + ' ตัว)');

// ── ตั้งแมตช์จำลอง แล้ววาดจริงหลายเฟรมด้วยลูปของจริง (wmStartLoop) ──
const LOOK = "{ race: 'Human', cls: 'Warrior', armor: 'None', weapon: 'Iron_Weapon', pose: 'idle' }";
try {
  vm.runInContext(`
    WM = new WormsMap({ w: 200, h: 100, water: 10, terrain: '0:200;'.repeat(100),
                         seed: 1, continent: 'main', props: [] });
    WM_CAM = new WormsCam(__wmCanvas, WM);
    document.getElementById('v-worms').classList.add('on');
    WM_ST = { round: 1, turn: 0, terrain: '0:200;'.repeat(100), over: false, active: true,
      fighters: [
        { name: 'คุณ', x: 20, y: 10, hp: 100, max_hp: 100, face: 1, dead: false, bot: false, look: ${LOOK} },
        { name: 'บอท', x: 150, y: 10, hp: 100, max_hp: 100, face: -1, dead: false, bot: true, look: ${LOOK} },
      ] };
    WM_TIME_LEFT = 60;
    WM_DEADLINE = performance.now() + 60000;
    wmStartLoop();
  `, sandbox);
} catch (e) {
  console.log('  ❌ ตั้งแมตช์จำลอง/เริ่มลูปวาดพัง:', e.message);
  process.exit(1);
}

if (frames < 3) { console.log('  ❌ ลูปวาดไม่เคยทำงานเลย (วาดไป ' + frames + ' เฟรม)'); fail++; }
else if (errors.length) {
  console.log('  ❌ วาดแล้วพัง ' + errors.length + ' เฟรม (ลูปกลืน error ไว้เอง แต่เทสจับได้):');
  errors.slice(0, 5).forEach(e => console.log('     ' + e));
  fail++;
} else {
  console.log('  ✅ วาดเฟรมจริงได้ ' + frames + ' เฟรม ไม่มี error');
}

process.exit(fail ? 1 : 0);
