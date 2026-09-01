// 🔒 ทุกทางที่ส่งคำสั่งไปเซิร์ฟเวอร์ ต้องผ่านด่าน "ถึงตาเราหรือยัง"
//
// เจ้าของเกมเจอ 08-29: "เงื่อนไขกันวางไพ่ในเทิร์นคนอื่นยังมีหลุดอยู่บ้าง
// ใส่ยังไม่คุมครบทุกตำแหน่ง"
// เดิมดักทีละจุด (ลากไพ่ / กดกอง) แต่ปุ่มผ่านกับ UNO! ไม่ได้ดักเลย
// ตอนนี้ย้ายด่านไปไว้ใน unoDo ที่เดียว — ทุกทางลอดผ่านตรงนั้นหมด
const fs = require('fs');
const src = fs.readFileSync('license_server/web_static/uno.js', 'utf8');
let fail = 0;
const check = (label, got, want) => {
  const ok = got === want;
  console.log(`  ${ok ? '✅' : '❌'} ${label}${ok ? '' : ` — ได้ ${got} ควรเป็น ${want}`}`);
  if (!ok) fail++;
};

// ── ทุก call site ต้องยิงผ่าน unoDo ──
const calls = [...src.matchAll(/unoDo\('(\w+)'/g)].map(m => m[1]);
const uniq = [...new Set(calls)].sort();
console.log('คำสั่งที่ส่งได้:', uniq.join(', '));
check('ไม่มีทางลัดยิง api ตรง ๆ',
      (src.match(/api\('POST', '\/api\/web\/uno'/g) || []).length, 1);

// ── ด่านอยู่ใน unoDo และอยู่ก่อนทุกอย่าง ──
const i = src.indexOf('async function unoDo');
const head = src.slice(i, src.indexOf('try {', i));
check('มีด่านใน unoDo', /!unoMyTurn\(\)/.test(head), true);
check('ด่านอยู่ก่อนตั้งธง',
      head.indexOf('unoMyTurn()') < head.indexOf('UNO_SENT = true'), true);

// ── คำสั่งไหนผ่านได้ตลอด ──
const allow = /const UNO_ANYTIME = new Set\(\[([^\]]+)\]\)/.exec(src);
const anytime = allow ? allow[1].match(/'(\w+)'/g).map(s => s.replace(/'/g, '')) : [];
console.log('ผ่านได้ตลอด:', anytime.join(', '));
check('start ผ่านได้ (ยังไม่มีโต๊ะ)', anytime.includes('start'), true);
check('quit ผ่านได้ (ออกได้เสมอ)', anytime.includes('quit'), true);
// คำสั่งที่เปลี่ยนเกมต้องไม่อยู่ในรายการยกเว้น
['play', 'draw', 'take', 'pass', 'uno'].forEach(a =>
  check(`${a} ต้องผ่านด่าน`, anytime.includes(a), false));

// ── ตรรกะด่านจริง ──
const busy = src.slice(src.indexOf('function unoBusyFx'), src.indexOf('/** ตอนนี้ทำอะไรไม่ได้'));
const mt = src.slice(src.indexOf('function unoMyTurn'), src.indexOf('function unoMustDraw'));
const turn = o => new Function('UNO','UNO_THINK','UNO_SENT','UNO_DEALING','UNO_CARDS','UNO_SUIT_CARDS',
  busy + mt + '\n return unoMyTurn();')(
    o.uno === undefined ? {playing:1, my_turn:1} : o.uno,
    o.think || null, !!o.sent, !!o.dealing, o.cards || [], o.suits || []);
console.log('ด่านบล็อกครบไหม:');
check('ตาเรา ว่าง = ผ่าน', turn({}), true);
check('ตาคนอื่น', turn({uno:{playing:1,my_turn:0}}), false);
check('สั่งไปแล้วรอผล', turn({sent:true}), false);
check('บอทกำลังคิด', turn({think:{seat:1}}), false);
check('กำลังแจกไพ่', turn({dealing:true}), false);
check('ไพ่บอทยังบิน', turn({cards:[{anim:'arc', flying:true}]}), false);
check('กำลังเลือกสีไวลด์', turn({suits:[{suit:'fire'}]}), false);
check('เกมจบแล้ว', turn({uno:{playing:1,my_turn:1,over:true}}), false);
check('เราออกไปแล้ว', turn({uno:{playing:1,my_turn:1,my_place:2}}), false);
check('ยังไม่มีโต๊ะ', turn({uno:null}), false);
process.exit(fail ? 1 : 0);
