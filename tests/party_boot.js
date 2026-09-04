// 🎭 หน้าจอต่อสู้ปาร์ตี้ต้องวาดได้จริง — ไม่ใช่แค่ไฟล์มีอยู่
//
// เทสข้อความจับไม่ได้ว่าโค้ดรันแล้วพังไหม (เจอมาแล้วตอน !login เงียบ)
// ตัวนี้โหลด JS จริงเข้า vm แล้วสั่งวาดเฟรม + ป้อน events แบบเดียวกับที่เซิร์ฟเวอร์ส่ง
//
// ⚠️ รันชุดเดียวกันนี้กับ **renderer ทุกตัว** — นี่คือสิ่งที่ทำให้ "เปลี่ยนกราฟิกง่าย"
//    เป็นจริง ไม่ใช่แค่คำพูด: ไฟล์ไหนผ่านชุดนี้ก็เอาไปเสียบแทนกันได้ทันที
//    เพิ่ม renderer ใหม่ = เติมชื่อไฟล์ในลิสต์ RENDERERS ข้างล่าง
const fs = require('fs');
const vm = require('vm');

const RENDERERS = [
  'license_server/web_static/games/party/renderer_basic.js',
  'license_server/web_static/games/party/renderer_pixel.js',
];

let fail = 0;
let ok = () => {};

for (const FILE of RENDERERS) {
  const name = FILE.split('/').pop();
  console.log(`
▶ ${name}`);
  runSuite(FILE);
}

function runSuite(FILE) {
  /** จำนวนเหตุการณ์ที่ยังค้างคิวใน renderer ตัวที่กำลังเทส */
  const PB_len = () => sandbox.pbPending();
  ok = (label, cond, why) => {
    if (cond) console.log(`  ✅ ${label}`);
    else { console.log(`  ❌ ${label}${why ? ' — ' + why : ''}`); fail++; }
  };
  // ── canvas ปลอมที่นับว่าถูกเรียกอะไรบ้าง ──
  const calls = [];
  function fakeCtx() {
    const rec = name => (...a) => calls.push([name, ...a]);
    return new Proxy({}, {
      get: (_, k) => {
        if (typeof k === 'string' && k.startsWith('create') && k.endsWith('Gradient'))
        return () => ({ addColorStop() {} });
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
    Math, console, JSON, Date,
  };
  vm.createContext(sandbox);

  /** ระบายคิวเฟรมแบบเบราว์เซอร์จริง — เฟรมถัดไปรันหลังเฟรมนี้จบ */
  function drain(max = 900) {
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
    vm.runInContext(fs.readFileSync(FILE, 'utf8'), sandbox);
    ok('โหลดได้ ไม่มี error ตอนอ่านโค้ด', true);
  } catch (e) {
    ok('โหลดไฟล์', false, e.message);
    return;
  }

  for (const fn of ['pbMount', 'pbSetState', 'pbPlay', 'pbDraw', 'pbPending',
                    'pbHpShown']) {
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
      { t: 'telegraph', who: 'm1', move: '🔥 คลื่นเพลิงคลั่ง', targets: ['p1', 'p2'] },
    ]);
    drain();
    ok('เล่นเหตุการณ์ครบทุกชนิดได้ ไม่มี error', true);
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

  // ── ป้ายเตือนต้องค้างจนกว่าบอสจะปล่อยท่า ──
  // เตือนแล้วป้ายหายทันที = เตือนไปก็เท่านั้น ผู้เล่นไม่ทันอ่าน
  try {
    drain();
    sandbox.pbPlay([{ t: 'telegraph', who: 'm1', move: 'ท่าใหญ่', targets: ['p1'] }]);
    drain();
    const shown = calls.filter(c => c[0] === 'fillText' &&
                               String(c[1]).includes('ท่าใหญ่')).length;
    ok('ป้ายเตือนขึ้นบนจอ', shown > 0);

    const n0 = calls.length;
    sandbox.pbSetState(state);          // poll รอบถัดไป ป้ายต้องยังอยู่
    drain();
    ok('ป้ายเตือนค้างข้ามการอัปเดตสถานะ',
       calls.slice(n0).some(c => c[0] === 'fillText' && String(c[1]).includes('ท่าใหญ่')));

    const n1 = calls.length;
    sandbox.pbPlay([{ t: 'aoe', from: 'm1', targets: ['p1'], dmgs: [50], element: null }]);
    drain();
    ok('ปล่อยท่าแล้วป้ายหาย',
       !calls.slice(n1).some(c => c[0] === 'fillText' && String(c[1]).includes('ท่าใหญ่')));
  } catch (e) {
    ok('ป้ายเตือนท่าใหญ่', false, e.message);
  }

  // ── คนที่ล้มแล้วต้องยังคลิกได้ (ท่าชุบเล็งคนล้มเท่านั้น) ──
  try {
    sandbox.pbSetState(state);
    drain();
    const picked = [];
    sandbox.onPartyPick = (id, side, alive) => picked.push([id, side, alive]);
    // m2 ในสถานะทดสอบคือตัวที่ alive:false — มอน 2 ตัว จึงอยู่ที่ x = 900/3*2
    sandbox.pbClick({ clientX: 600, clientY: 130 });
    ok('คลิกตัวที่ล้มแล้วได้ (ไม่งั้นชุบไม่ได้เลย)', picked.length > 0);
    ok('บอกด้วยว่าตัวนั้นล้มหรือยัง', picked.length > 0 && picked[0][2] === false);
  } catch (e) {
    ok('คลิกตัวที่ล้ม', false, e.message);
  }

  // ── เริ่มสมรภูมิใหม่ต้องล้างของค้าง ──
try {
  sandbox.pbPlay([{ t: 'telegraph', who: 'm1', move: 'ท่าค้าง', targets: ['p1'] }]);
  drain();
  box.innerHTML = '';
  box.contains = () => false;          // ทำเหมือนจอถูกล้างทิ้งแล้ว
  sandbox.pbMount('partyMount');
  box.contains = () => true;
  sandbox.pbSetState(state);
  const n = calls.length;
  drain();
  ok('สร้างจอใหม่แล้วป้ายเตือนรอบเก่าหายไป',
     !calls.slice(n).some(c => c[0] === 'fillText' && String(c[1]).includes('ท่าค้าง')));
} catch (e) {
  ok('ล้างของค้างตอนสร้างจอใหม่', false, e.message);
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

    // ── ⭐ แถบเลือดต้องลด "หลัง" อนิเมชันโดนตี ไม่ใช่ก่อน ──
  // เจ้าของเกมเจอตอนเทสด้วยมือ 2026-09-04: เลือดลดตั้งแต่ยังไม่ทันทอยเต๋า
  // เพราะ pbSetState เอาสถานะใหม่ (เลือดลดแล้ว) ไปตั้งเป้าทันที
  // ที่ถูกคือแถบเลือดต้องขยับตาม "เหตุการณ์" ไม่ใช่ตามสถานะ
  try {
    drain();
    const full = JSON.parse(JSON.stringify(state));
    sandbox.pbSetState(full);
    drain();
    const before = sandbox.pbHpShown('p1');

    // เซิร์ฟเวอร์ส่งสถานะที่เลือดลดแล้วมาพร้อมเหตุการณ์ (เหมือนของจริง)
    const hurtState = JSON.parse(JSON.stringify(state));
    hurtState.units.find(u => u.id === 'p1').hp = 10;
    sandbox.pbPlay([
      { t: 'contest', from: 'm1', to: 'p1', atk: 18, def: 6, hit: true, evaded: false },
      { t: 'attack', from: 'm1', to: 'p1', dmg: 70, element: null, crit: false },
    ]);
    sandbox.pbSetState(hurtState);

    for (let i = 0; i < 12; i++) drain(1);      // ยังอยู่ช่วงทอยเต๋า
    const mid = sandbox.pbHpShown('p1');
    ok('เลือดยังไม่ลดตอนกำลังทอยเต๋า',
       Math.abs(mid - before) < 0.02, `ก่อน ${before} ระหว่างทอย ${mid}`);

    drain();                                     // ปล่อยจนอนิเมชันจบ
    const after = sandbox.pbHpShown('p1');
    ok('พออนิเมชันโดนตีเล่นแล้วเลือดถึงลด', after < before - 0.2,
       `ก่อน ${before} หลัง ${after}`);
  } catch (e) {
    ok('ลำดับแถบเลือดกับอนิเมชัน', false, e.message);
  }

  // ── เหตุการณ์ต้องเล่นทีละอัน ไม่รัวทับกัน ──
  // เจ้าของเกมสั่ง 2026-09-04: ถึงตาบอท/มอนให้รอสักพักแล้วค่อยตี จะได้ดูทัน
  try {
    drain();
    const many = [
      { t: 'attack', from: 'm1', to: 'p1', dmg: 10, element: null, crit: false },
      { t: 'attack', from: 'm2', to: 'p2', dmg: 11, element: null, crit: false },
      { t: 'attack', from: 'm1', to: 'p1', dmg: 12, element: null, crit: false },
    ];
    sandbox.pbPlay(many);
    const one = drain(1);
    ok('เฟรมแรกเล่นแค่เหตุการณ์เดียว ไม่รัวหมดชุด', PB_len() === 3,
       `เหลือในคิว ${PB_len()}`);
    const all = drain();
    ok('เล่นครบทั้งคิวในที่สุด', PB_len() === 0);
    ok('ใช้เวลาหลายเฟรมกว่าจะครบ (มีจังหวะหน่วง)', all > 40, `ใช้ ${all} เฟรม`);
  } catch (e) {
    ok('เล่นเหตุการณ์ทีละอัน', false, e.message);
  }

  // ── ทอยเต๋าแข่งต้องเห็นแต้มทั้งสองฝั่ง ──
  // เจ้าของเกมสั่ง 2026-09-04: ไม่ว่ามอนหรือคนเป็นฝ่ายตี ต้องเห็นเต๋าทั้งคู่
  //
  // ⚠️ ต้องดู **เฟรมเดียวหลังเต๋าหยุดคลึง** ไม่ใช่รวมทุกเฟรม
  //    ตอนคลึงเต๋าวาดเลขสุ่ม 1-20 ทุกเฟรม เลขที่อยากเช็คจึงโผล่มาเองได้
  //    (ย้อนเทสจับได้: ลบเต๋าฝั่งผู้ป้องกันทิ้งแล้วเทสยังเขียว)
  try {
    drain();
    sandbox.pbPlay([{ t: 'contest', from: 'm1', to: 'p1',
                      atk: 18, def: 6, hit: true, evaded: false }]);
    let spun = 0;
    for (let i = 0; i < 30; i++) spun += drain(1);
    ok('ทอยเต๋าเล่นหลายเฟรม (มีอนิเมชันคลึงเต๋า)', spun > 5, `ได้ ${spun} เฟรม`);

    const n0 = calls.length;
    drain(1);                                  // เฟรมเดียว ตอนเฉลยแต้มแล้ว
    const one = calls.slice(n0)
      .filter(x => x[0] === 'fillText').map(x => String(x[1]));
    ok('โชว์แต้มฝั่งผู้โจมตี', one.includes('18'), one.join(' '));
    ok('โชว์แต้มฝั่งผู้ป้องกัน', one.includes('6'), one.join(' '));
    ok('บอกผลว่าใครชนะ',
       one.some(t => t.includes('โจมตีเข้า') || t.includes('ป้องกันไว้')));

    drain();
    const n1 = calls.length;
    sandbox.pbPlay([{ t: 'contest', from: 'm1', to: 'p1',
                      atk: 0, def: 0, hit: false, evaded: true }]);
    drain(1);
    ok('หลบได้ขึ้นข้อความหลบ ไม่ใช่โชว์เต๋า 0-0',
       calls.slice(n1).some(x => x[0] === 'fillText' && String(x[1]).includes('หลบได้')));
    drain();
  } catch (e) {
    ok('ทอยเต๋าแข่ง', false, e.message);
  }

  // ── ตัดชื่อยาวห้ามผ่ากลางอิโมจิ ──
  // slice() ธรรมดานับหน่วย UTF-16 อิโมจิ 1 ตัว = 2 หน่วย ตัดคาไว้แล้วจอขึ้น �
  // (เจ้าของเกมเห็นตัว � ในชื่อมอนตอนเทสด้วยมือ 2026-09-04)
  try {
    const long = 'ธาตุดินโบราณก\u{1F5FF}ยักษ์หินแห่งขุนเขา';
    const out = sandbox.pbShortName(long);
    ok('ตัดชื่อยาวไม่ผ่ากลางอิโมจิ', !/[\uD800-\uDBFF]$/.test(out),
       JSON.stringify(out));
    ok('ชื่อสั้นไม่ถูกตัด', sandbox.pbShortName('เอ') === 'เอ');
  } catch (e) {
    ok('ตัดชื่อยาว', false, e.message);
  }

// ── ห้ามคำนวณกติกาเอง ──
  const src = fs.readFileSync(FILE, 'utf8');
  for (const bad of ['rollDice', 'calcDamage', 'element_multiplier']) {
    ok(`ไม่คำนวณกติกาเอง (${bad})`, !src.includes(bad),
       'renderer ต้องวาดอย่างเดียว กติกาอยู่ที่เซิร์ฟเวอร์');
  }

}

console.log(fail ? `\n  ${fail} ข้อไม่ผ่าน` : '\n  ผ่านหมด');
process.exit(fail ? 1 : 0);
