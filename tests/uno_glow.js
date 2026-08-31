// รันตรรกะ glow จริงจาก uno.js — เทสข้อความอย่างเดียวจับไม่ได้ว่าตรรกะถูกไหม
const fs = require('fs');
const src = fs.readFileSync('license_server/web_static/uno.js', 'utf8');
const i = src.indexOf('  hand.forEach((card, i) => {');
const body = src.slice(i, src.indexOf('  });', i));

// ดึงบรรทัดที่ตัดสิน can/dim/glow ออกมารันจริง
const decide = new Function('UNO', 'i', `
  const can = (UNO.playable || []).includes(i);
  ${body.split('\n').filter(l => l.includes('const dim') || l.includes('const glow')).join('\n')}
  return { can, dim, glow };
`);

let fail = 0;
const check = (label, got, want) => {
  if (got !== want) { console.log(`  ❌ ${label}: ได้ ${got} ควรเป็น ${want}`); fail++; }
  else console.log(`  ✅ ${label}`);
};
const mine = { my_turn: true, playable: [0, 2] };
console.log('ตาเรา มีไพ่ลงได้ใบ 0 กับ 2:');
check('ใบ 0 เรือง', decide(mine, 0).glow, true);
check('ใบ 1 ไม่เรือง', decide(mine, 1).glow, false);
check('ใบ 2 เรือง', decide(mine, 2).glow, true);
check('ใบ 1 หรี่', decide(mine, 1).dim, true);
const theirs = { my_turn: false, playable: [] };
console.log('ตาคนอื่น:');
check('ไม่เรืองสักใบ', decide(theirs, 0).glow, false);
check('ไม่หรี่สักใบ', decide(theirs, 0).dim, false);
process.exit(fail ? 1 : 0);
