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
const mdSrc = src.slice(src.indexOf('function unoMustDraw'), src.indexOf('function unoOnDeck'));
const mustDraw = new Function('UNO', mdSrc + '\n return unoMustDraw();');
console.log('กองจั่วเรือง:');
check('ไม่มีไพ่ลงได้', mustDraw({playing:1,my_turn:1,playable:[],winner:null}), true);
check('โดนสแตคแล้วสแตคต่อไม่ได้', mustDraw({playing:1,my_turn:1,playable:[],must_answer:1,stack:2,winner:null}), true);
check('มีไพ่ลงได้ = ไม่เรือง', mustDraw({playing:1,my_turn:1,playable:[0],winner:null}), false);
check('จั่วไปแล้ว = ไม่เรือง', mustDraw({playing:1,my_turn:1,playable:[],drew:1,winner:null}), false);
check('ตาคนอื่น = ไม่เรือง', mustDraw({playing:1,my_turn:0,playable:[],winner:null}), false);
process.exit(fail ? 1 : 0);
