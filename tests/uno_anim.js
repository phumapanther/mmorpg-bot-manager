// รันตรรกะอนิเมชันจริงจาก uno.js — เทสข้อความจับบั๊กพวกนี้ไม่ได้
const fs = require('fs');
const src = fs.readFileSync('license_server/web_static/uno.js', 'utf8');
let fail = 0;
const check = (label, got, want) => {
  const ok = JSON.stringify(got) === JSON.stringify(want);
  console.log(`  ${ok ? '✅' : '❌'} ${label}${ok ? '' : ` — ได้ ${JSON.stringify(got)} ควรเป็น ${JSON.stringify(want)}`}`);
  if (!ok) fail++;
};

// ── 1. จั่วไพ่แล้วต้องพลิกหงายจนสุด ──
const i = src.indexOf('      c.t = Math.min(c.dur, c.t + UNO_DT);');
const block = src.slice(i, src.indexOf('      if (c.t >= c.dur)', i));
const unoEase = t => 1 - Math.pow(1 - t, 3);
const unoEaseIO = t => t < .5 ? 4*t*t*t : 1 - Math.pow(-2*t+2,3)/2;
const step = new Function('c', 'UNO_DT', 'unoEase', 'unoEaseIO', block + '\n return c;');

const card = { anim:'arc', t:0, dur:20, x:0, y:0, rot:0, face:0,
               from:{x:0,y:0,rot:0,face:0}, to:{x:100,y:100,rot:.2,face:1} };
for (let n = 0; n < 30; n++) step(card, 1, unoEase, unoEaseIO);
const showFace = Math.cos(card.face * Math.PI) <= 0;
console.log('จั่วไพ่:');
check('พลิกหงายจนสุด (face=1)', Math.round(card.face * 100) / 100, 1);
check('เห็นหน้าไพ่', showFace, true);

// ── 2. ไพ่เลื่อนช่องแล้วต้องไม่เปลี่ยนสี ──
const j = src.indexOf('  const keep = {};');
const layout = src.slice(j, src.indexOf('function unoHit'));
console.log('จับคู่ไพ่เก่า/ใหม่:');
check('จับด้วยหน้าไพ่ ไม่ใช่เลขช่อง', /keep\[`\$\{c\.card\.suit\}:\$\{c\.card\.value\}\}?`\]/.test(layout) || layout.includes('c.card.suit}:${c.card.value'), true);
check('ไม่ได้ใช้ keep[i] แบบเดิม', /const old = keep\[i\]/.test(layout), false);

// ── 3. ที่นั่งล้อมวงโต๊ะ ──
const seatSrc = src.slice(src.indexOf('function unoSeats'), src.indexOf('function unoFan'));
const mk = n => ({ playing:true, turn:0,
  players: Array.from({length:n}, (_,i)=>({ name: i?`🤖 บอท ${i}`:'คุณ', cards:5, you:i===0 })),
  finished: [] });
const seatsFn = new Function('UNO','cv', seatSrc + '\n return unoSeats(cv);');
const cv = { width: 900, height: 500 };
console.log('ที่นั่งล้อมวง:');
for (const n of [2, 3, 4, 6]) {
  const seats = seatsFn(mk(n), cv);
  const inBox = seats.every(s => s.x > 0 && s.x < cv.width && s.y > 0 && s.y < cv.height);
  const spread = new Set(seats.map(s => Math.round(s.x) + ',' + Math.round(s.y))).size;
  check(`${n} คน: ที่นั่ง ${n-1} ตัว (ไม่นับเรา)`, seats.length, n - 1);
  check(`${n} คน: อยู่ในจอทุกตัว`, inBox, true);
  check(`${n} คน: ไม่ทับกัน`, spread, seats.length);
}
// เราต้องไม่มีเหรียญซ้ำ (มีไพ่ในมืออยู่แล้ว)
check('ไม่มีเหรียญของตัวเอง', seatsFn(mk(4), cv).some(s => s.you), false);


// ── 4. ดูดไพ่เข้ากอง ──
const npSrc = src.slice(src.indexOf('function unoNearPile'), src.indexOf('function unoFrame'));
const nearPile = new Function('unoPilePos', npSrc + '\n return unoNearPile;')(
  cv2 => ({ deck:{x:cv2.width/2-80, y:cv2.height/2-20}, pile:{x:cv2.width/2+80, y:cv2.height/2-20} }));
const CV = { width: 900, height: 500 };
console.log('ดูดไพ่เข้ากอง:');
check('ปล่อยตรงกองพอดี', nearPile({x:530,y:230}, CV), true);
check('ปล่อยเยื้องไป 120px ยังลง', nearPile({x:650,y:230}, CV), true);
check('ลากขึ้นมากลางจอก็ลง', nearPile({x:200,y:200}, CV), true);
check('ยังอยู่ในแถวไพ่ในมือ = ไม่ลง', nearPile({x:450,y:430}, CV), false);
check('ลากลงล่างสุด = ไม่ลง', nearPile({x:450,y:490}, CV), false);

// ── 5. กองจั่วเรืองทั้งสองกรณี ──
// unoMustDraw เรียก unoMyTurn ต่อ — ยกมาทั้งคู่
const busyPre = src.slice(src.indexOf('function unoBusyFx'), src.indexOf('/** ตอนนี้ทำอะไรไม่ได้'));
const mdSrc = busyPre + src.slice(src.indexOf('function unoMyTurn'), src.indexOf('function unoOnDeck'));
const mustDraw = (UNO, UNO_THINK) =>
  new Function('UNO', 'UNO_THINK', 'UNO_SENT', 'UNO_DEALING', 'UNO_CARDS',
    mdSrc + '\n return unoMustDraw();')(UNO, UNO_THINK || null, false, false, []);
console.log('กองจั่วเรือง:');
check('ไม่มีไพ่ลงได้', mustDraw({playing:1,my_turn:1,playable:[],winner:null}), true);
check('โดนสแตคแล้วสแตคต่อไม่ได้', mustDraw({playing:1,my_turn:1,playable:[],must_answer:1,stack:2,winner:null}), true);
check('มีไพ่ลงได้ = ไม่เรือง', mustDraw({playing:1,my_turn:1,playable:[0],winner:null}), false);
check('จั่วไปแล้ว = ไม่เรือง', mustDraw({playing:1,my_turn:1,playable:[],drew:1,winner:null}), false);
check('ตาคนอื่น = ไม่เรือง', mustDraw({playing:1,my_turn:0,playable:[],winner:null}), false);


// ── 6. ตาใครลงไพ่ได้ ──
const mtSrc = busyPre + src.slice(src.indexOf('function unoMyTurn'), src.indexOf('function unoMustDraw'));
const myTurn = (UNO, THINK) =>
  new Function('UNO', 'UNO_THINK', 'UNO_SENT', 'UNO_DEALING', 'UNO_CARDS', mtSrc + '\n return unoMyTurn();')(UNO, THINK, false, false, []);
console.log('ตาใครลงไพ่ได้:');
check('ตาเรา ปกติ', myTurn({playing:1,my_turn:1}, null), true);
check('ตาคนอื่น', myTurn({playing:1,my_turn:0}, null), false);
check('บอทกำลังคิด (สถานะยังเก่า)', myTurn({playing:1,my_turn:1}, {seat:1}), false);
check('เกมจบแล้ว', myTurn({playing:1,my_turn:1,over:true}, null), false);
check('เราออกไปแล้ว', myTurn({playing:1,my_turn:1,my_place:2}, null), false);
check('ยังไม่มีโต๊ะ', myTurn(null, null), false);


// ── 7. ลงไพ่แล้วต้องจบตาทันที ──
const mt2 = busyPre + src.slice(src.indexOf('function unoMyTurn'), src.indexOf('function unoMustDraw'));
const turnWith = (UNO, THINK, SENT) =>
  new Function('UNO','UNO_THINK','UNO_SENT', 'UNO_DEALING', 'UNO_CARDS', mt2 + '\n return unoMyTurn();')(UNO, THINK||null, !!SENT, false, []);
console.log('ลงไพ่แล้วจบตาทันที:');
const t = {playing:1, my_turn:1};
check('ก่อนลง = ลงได้', turnWith(t, null, false), true);
check('สั่งไปแล้วรอผล = ลงไม่ได้', turnWith(t, null, true), false);
check('บอทกำลังเล่น = ลงไม่ได้', turnWith(t, {seat:1}, false), false);


// ── 8. ไพ่ยังบินอยู่ = ยังไม่ถึงตาเรา ──
const busySrc = src.slice(src.indexOf('function unoBusyFx'), src.indexOf('/** ตอนนี้ทำอะไรไม่ได้'));
const busy = cards => new Function('UNO_CARDS', busySrc + '\n return unoBusyFx();')(cards);
console.log('ไพ่ยังบินอยู่ไหม:');
check('ไม่มีไพ่บิน', busy([{anim:null}]), false);
check('บอทลงไพ่ กำลังบิน', busy([{anim:'arc', flying:true}]), true);
check('บินจบแล้ว', busy([{anim:null, flying:true}]), false);
check('ไพ่ในมือขยับ ไม่นับ', busy([{anim:'move', slot:0}]), false);

// ตาเราต้องยังไม่เปิดระหว่างไพ่บอทบินอยู่
const mt3 = src.slice(src.indexOf('function unoMyTurn'), src.indexOf('function unoMustDraw'));
const turnFx = (cards) => new Function('UNO','UNO_THINK','UNO_SENT','UNO_DEALING','UNO_CARDS',
  busySrc + mt3 + '\n return unoMyTurn();')({playing:1,my_turn:1}, null, false, false, cards);
check('ไพ่บอทยังบิน = ยังไม่ถึงตาเรา', turnFx([{anim:'arc', flying:true}]), false);
check('บินจบแล้ว = ถึงตาเรา', turnFx([{anim:null, flying:true}]), true);


// ── 9. ลงไพ่แล้วล็อกมือทันที ──
const downSrc = src.slice(src.indexOf('    const c = unoHit(p);') - 400,
                          src.indexOf('  const move = e =>'));
console.log('ล็อกมือหลังลงไพ่:');
check('ดักก่อนจับไพ่ (ไม่ใช่แค่ dim)', /if \(UNO_SENT \|\| UNO_DEALING \|\| UNO_THINK\) return;/.test(downSrc), true);
const iSent = downSrc.indexOf('UNO_SENT');
const iHit = downSrc.indexOf('unoHit(p)');
check('เช็คก่อนหาไพ่ที่จับ', iSent >= 0 && iSent < iHit, true);


// ── 10. ไพ่ที่เพิ่งทิ้งต้องหายจากมือทันที ──
// (เจ้าของเกมเจอ 08-29: ทิ้งไพ่ 3 ไปแล้ว ไพ่ 3 ยังอยู่บนมือจนบอทเล่นจบ)
const goneSrc = src.slice(src.indexOf('  const gone = {};'),
                          src.indexOf('    const f = unoFan'));
const countShown = (hand, flying) => {
  let n = 0;
  new Function('hand', 'flying', 'tick', goneSrc + '  tick(); });')(
    hand, flying, () => n++);
  return n;
};
const C = (v) => ({ suit: 'fire', value: v });
const inAir = (v) => [{ card: C(v), toPile: true, anim: 'move', flying: true }];
console.log('ไพ่ที่เพิ่งทิ้ง:');
check('มือ 5 ใบ ทิ้งใบ 3 -> เหลือ 4', countShown([C(1),C(2),C(3),C(4),C(5)], inAir(3)), 4);
check('ไพ่ซ้ำ 2 ใบ ทิ้งไป 1 -> เหลือ 1', countShown([C(3),C(3)], inAir(3)), 1);
check('ไม่มีไพ่บิน -> ครบทุกใบ', countShown([C(1),C(2)], []), 2);
check('ไพ่บินแต่ไม่ได้ไปกอง -> ไม่ซ่อน',
      countShown([C(1)], [{card:C(1), anim:'move', flying:true}]), 1);


// ── 11. ไพ่ที่เราทิ้งเองต้องไม่บล็อกตาเรา ──
// (เจ้าของเกมเจอ 08-29: เล่น 2 คน วางไพ่ข้ามตา บอทถูกข้าม กลับมาเป็นตาเรา
//  แต่จอค้าง "รอคู่แข่ง..." เพราะไพ่ที่เราเพิ่งทิ้งยังบินอยู่)
const busy2 = src.slice(src.indexOf('function unoBusyFx'), src.indexOf('/** ตอนนี้ทำอะไรไม่ได้'));
const isBusy = cards => new Function('UNO_CARDS', busy2 + '\n return unoBusyFx();')(cards);
console.log('ไพ่ของใครบล็อกตาเรา:');
check('ไพ่บอทบินอยู่ = บล็อก', isBusy([{anim:'arc', flying:true}]), true);
check('ไพ่ที่เราทิ้งเอง = ไม่บล็อก', isBusy([{anim:'move', flying:true, mine:true}]), false);
check('ไพ่แจกตอนเปิดโต๊ะ = บล็อก', isBusy([{anim:'arc', flying:true}]), true);
check('ทั้งของเราและของบอท = บล็อก',
      isBusy([{anim:'move', flying:true, mine:true}, {anim:'arc', flying:true}]), true);


// ── 12. ไพ่ที่บินจบแล้วต้องยังนับว่าออกจากมือ ──
// (เจ้าของเกมเจอ 08-29: ไวลด์ประตูนิรันดร์ เลือกสีเสร็จแล้วไพ่ยังอยู่บนมือ
//  เพราะ dur=8 บินจบก่อนเราจะกดเลือกสี -> c.anim=null -> หลุดจากรายการ flying)
const flySrc = src.slice(src.indexOf('  const flying = UNO_CARDS.filter'),
                         src.indexOf('  UNO_CARDS = flying.slice();'));
const flyList = cards => new Function('UNO_CARDS', flySrc + '\n return flying;')(cards);
console.log('ไพ่ที่ถือว่าออกจากมือแล้ว:');
check('กำลังบิน', flyList([{flying:true, anim:'move', toPile:true}]).length, 1);
check('บินจบแล้วแต่ยังค้างบนกอง', flyList([{flying:true, anim:null, toPile:true}]).length, 1);
check('ไพ่ในมือธรรมดา ไม่นับ', flyList([{anim:'move'}]).length, 0);

// ── 13. ไพ่ที่เราวางต้องเป็นใบบนสุด และต้องไม่ถูกนับซ้ำ ──
// (เจ้าของเกมเจอ 08-29: มีประตูนิรันดร์ 2 ใบ วางไป 1 แต่หายจากมือ 2 ใบ
//  เพราะ UNO_CARDS = flying แล้ว push(onPile) ทับ = ตัวเดียวกันอยู่สองที่)
const pileSrc = src.slice(src.indexOf('  const flying = UNO_CARDS.filter'),
                          src.indexOf('  // ไพ่ในมือเรา'));
const layoutPile = (cards, serverTop) =>
  new Function('UNO_CARDS', 'UNO', 'unoPilePos', 'cv', 'UNO_DEALING',
    pileSrc + '\n return UNO_CARDS;')(
      cards, { top: serverTop }, () => ({ pile: { x: 0, y: 0 } }), {}, false);

console.log('ไพ่บนสุดของกอง:');
const wild4 = { suit: null, value: 'wild4' };
const played = { card: wild4, flying: true, toPile: true, onPile: true, anim: null };
const out = layoutPile([played], { suit: 'water', value: 1 });
check('วางแล้ว -> เห็นไพ่ที่เราวาง', out[out.length - 1].card.value, 'wild4');
check('ไม่ถูกนับซ้ำ', out.filter(c => c.card && c.card.value === 'wild4').length, 1);
const clean = layoutPile([], { suit: 'water', value: 1 });
check('ยังไม่วาง -> เห็นไพ่จากเซิร์ฟเวอร์', clean[clean.length - 1].card.value, 1);

process.exit(fail ? 1 : 0);
