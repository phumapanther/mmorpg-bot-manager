// รันตรรกะ glow จริงจาก uno.js — เทสข้อความอย่างเดียวจับไม่ได้ว่าตรรกะถูกไหม
const fs = require('fs');
const src = fs.readFileSync('license_server/web_static/uno.js', 'utf8');

// ยก unoMyTurn มาด้วย — ตัวตัดสินว่าถึงตาเราหรือยัง
const mtSrc = src.slice(src.indexOf('function unoMyTurn'), src.indexOf('function unoMustDraw'));

const i = src.indexOf('  hand.forEach((card, i) => {');
const body = src.slice(i, src.indexOf('  });', i));
const picked = body.split('\n').filter(l =>
  l.includes('const mine') || l.includes('const can') ||
  l.includes('const dim') || l.includes('const glow')).join('\n');

const decide = (UNO, idx, THINK) =>
  new Function('UNO', 'i', 'UNO_THINK',
    mtSrc + '\n' + picked + '\n return { can, dim, glow };')(UNO, idx, THINK || null);

let fail = 0;
const check = (label, got, want) => {
  if (got !== want) { console.log(`  ❌ ${label}: ได้ ${got} ควรเป็น ${want}`); fail++; }
  else console.log(`  ✅ ${label}`);
};

const mine = { playing: true, my_turn: true, playable: [0, 2] };
console.log('ตาเรา มีไพ่ลงได้ใบ 0 กับ 2:');
check('ใบ 0 เรือง', decide(mine, 0).glow, true);
check('ใบ 1 ไม่เรือง', decide(mine, 1).glow, false);
check('ใบ 2 เรือง', decide(mine, 2).glow, true);
check('ใบ 1 หรี่', decide(mine, 1).dim, true);

const theirs = { playing: true, my_turn: false, playable: [] };
console.log('ตาคนอื่น:');
check('ไม่เรืองสักใบ', decide(theirs, 0).glow, false);
// เจ้าของเกมสั่ง 08-29: ยังไม่ถึงเทิร์นตัวเอง = หรี่ทั้งมือ
check('หรี่ทั้งมือ', decide(theirs, 0).dim, true);

console.log('บอทกำลังคิด (สถานะยังเก่า my_turn=true):');
check('ไม่เรือง', decide(mine, 0, { seat: 1 }).glow, false);
check('หรี่ไว้', decide(mine, 0, { seat: 1 }).dim, true);

process.exit(fail ? 1 : 0);
