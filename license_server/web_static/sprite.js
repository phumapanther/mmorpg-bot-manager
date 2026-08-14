// เอนจินสไปรต์ตัวละคร (เว็บเกม เฟส 1.2)
// ตัวละครประกอบจากชั้น: เงาใต้เท้า → ร่าง(เผ่า) → ชุด(เกราะ) → ผม/หมวก(คลาส) → อาวุธ
//
// เทคนิคให้ดูมีมิติ ไม่แบน:
//   • ทุกวัสดุมี 3 โทน — ฐาน(A) เงา(a) ไฮไลต์(Z) วางไฮไลต์บนซ้าย เงาล่างขวา
//   • เส้นขอบใช้สีเข้มอมม่วง ไม่ใช่ดำสนิท (ดำสนิททำให้ภาพแข็ง)
//   • มีเงาวงรีใต้เท้า ตัวละครเลยดูยืนบนพื้นจริง
//   • ตามีตาขาว+ม่านตา ไม่ใช่จุดดำจุดเดียว
//
// ตาราง 16 ช่องกว้าง × 22 สูง — ทุกแถวต้องยาว 16 เท่ากันหมด (มีเทสคุมใน test_sprite_grid.py)
const SP_W = 16;

const POSES = {
  idle: [
    '......oooo......',
    '....ooRRRRoo....',
    '...oRRrrrrRRo...',
    '..oRrrrrrrrrRo..',
    '..oRrssssssrRo..',
    '..oRssssssssRo..',
    '..oRsessssesSo..',
    '..oRssssssssSo..',
    '...oRsssssssSo..',
    '....oRsssssSo...',
    '.....oooSoo.....',
    '...oAAAAAAAAo...',
    '..oAZAAAAAAZAo..',
    '..oAAATTTTAAAo..',
    '..oAAATTTTAAAo..',
    '..oaAAAAAAAAao..',
    '...oAAAAAAAAo...',
    '...oPPPooPPPo...',
    '...oPPPooPPPo...',
    '...oPPPooPPPo...',
    '...obbboobbbo...',
    '..obbbb..bbbbo..',
  ],
  run1: [
    '......oooo......',
    '....ooRRRRoo....',
    '...oRRrrrrRRo...',
    '..oRrrrrrrrrRo..',
    '..oRrssssssrRo..',
    '..oRssssssssRo..',
    '..oRsessssesSo..',
    '..oRssssssssSo..',
    '...oRsssssssSo..',
    '....oRsssssSo...',
    '.....oooSoo.....',
    '...oAAAAAAAAo...',
    '..oAZAAAAAAZAo..',
    '..oAAATTTTAAAo..',
    '..oAAATTTTAAAo..',
    '..oaAAAAAAAAao..',
    '...oAAAAAAAAo...',
    '...oPPPooPPPo...',
    '..oPPPo..oPPPo..',
    '.oPPPo....oPPo..',
    '.obbo......obo..',
    '................',
  ],
  run2: [
    '......oooo......',
    '....ooRRRRoo....',
    '...oRRrrrrRRo...',
    '..oRrrrrrrrrRo..',
    '..oRrssssssrRo..',
    '..oRssssssssRo..',
    '..oRsessssesSo..',
    '..oRssssssssSo..',
    '...oRsssssssSo..',
    '....oRsssssSo...',
    '.....oooSoo.....',
    '...oAAAAAAAAo...',
    '..oAZAAAAAAZAo..',
    '..oAAATTTTAAAo..',
    '..oAAATTTTAAAo..',
    '..oaAAAAAAAAao..',
    '...oAAAAAAAAo...',
    '...oPPPooPPPo...',
    '...oPPPooPPPo...',
    '..oPPPo..oPPo...',
    '..obbo....obo...',
    '................',
  ],
  atk: [
    '.......oooo.....',
    '.....ooRRRRoo...',
    '....oRRrrrrRRo..',
    '...oRrrrrrrrrRo.',
    '...oRrssssssrRo.',
    '...oRssssssssRo.',
    '...oRsessssesSo.',
    '...oRssssssssSo.',
    '....oRsssssssSo.',
    '.....oRsssssSo..',
    '......oooSoo....',
    '..oAAAAAAAAAo...',
    '.oAZAAAAAAAZAo..',
    '.oAAAATTTTAAAo..',
    '.oAAAATTTTAAAo..',
    '.oaAAAAAAAAAao..',
    '..oAAAAAAAAAo...',
    '..oPPPooPPPo....',
    '.oPPPo..oPPPo...',
    'oPPPo.....oPPo..',
    'obbo.......obo..',
    '................',
  ],
};

// เผ่าพันธุ์: สีผิว + สีผม + ลักษณะเด่นบนหัว (คีย์ตรงกับ GAME_RACES/MONSTER_RACES ในเกม)
const RACE_LOOK = {
  'มนุษย์':        { skin:'#f4c9a2', dark:'#c58f66', hair:'#3a2418', hairDark:'#241309', feat:null },
  '• Dragon 🐉':   { skin:'#79b268', dark:'#47764a', hair:'#2f5c38', hairDark:'#1c3a24', feat:'horns' },
  '• Unicon 🦄':   { skin:'#f8dcef', dark:'#cb9dc2', hair:'#e8b0d8', hairDark:'#a86f9c', feat:'horn' },
  '•  Slime 🪼⋆':  { skin:'#6cb4cc', dark:'#3d7f9c', hair:'#8fd6e8', hairDark:'#4d93ad', feat:'blob' },
  '• Ogre 👹':     { skin:'#dd7264', dark:'#a2453a', hair:'#3d1a16', hairDark:'#260e0b', feat:'horns' },
  '• Orc 🧌':      { skin:'#8bab63', dark:'#57713c', hair:'#2b2118', hairDark:'#18110c', feat:'tusks' },
  '• Goblins🧝':   { skin:'#a9c46d', dark:'#708a46', hair:'#4a3a1c', hairDark:'#2c2210', feat:'ears' },
  '• Lich 🧙🏽‍♂️':   { skin:'#c2b0de', dark:'#8272a6', hair:'#6a5490', hairDark:'#3f3059', feat:'horns' },
  '•  Skeleton 🦴':{ skin:'#eee9db', dark:'#aaa391', hair:'#d8d2c0', hairDark:'#9a9484', feat:null },
  '•  Zombie🧟':   { skin:'#9bb389', dark:'#647a55', hair:'#3d3a22', hairDark:'#242212', feat:'ears' },
};
const RACE_FALLBACK = RACE_LOOK['มนุษย์'];

// คลาส: สีลายอกเสื้อ + เครื่องสวมหัว
const CLASS_LOOK = {
  Warrior: { trim:'#d93b2b', hat:'plume' },
  Mage:    { trim:'#5b8fa8', hat:'wizard' },
  Rogue:   { trim:'#4f7a4a', hat:'hood' },
  Cleric:  { trim:'#e8b04b', hat:'halo' },
};
const CLASS_FALLBACK = { trim:'#8a6a4a', hat:null };

// เกราะ: 3 โทนต่อระดับ (ฐาน/เงา/ไฮไลต์) + หมวก
const ARMOR_LOOK = {
  None:      { base:'#c4453a', shade:'#8a2b23', hi:'#e8776a', helm:0 },
  Leather_L: { base:'#a8763f', shade:'#6f4a22', hi:'#c99a63', helm:0 },
  Leather_H: { base:'#8d6033', shade:'#573a1c', hi:'#b0834c', helm:1 },
  Steel_L:   { base:'#b6c0cc', shade:'#79838f', hi:'#e2e9f2', helm:1 },
  Steel_H:   { base:'#d2dae4', shade:'#8a939e', hi:'#f4f8fc', helm:2 },
};
const ARMOR_FALLBACK = ARMOR_LOOK.None;

// อาวุธ: ความยาว + 3 โทน + ออร่า
const WEAPON_LOOK = {
  Wooden_Weapon: { base:'#9a6a38', shade:'#5c3d1c', hi:'#c39560', len:9,  glow:0 },
  Iron_Weapon:   { base:'#c6cfd9', shade:'#7c8691', hi:'#f0f5fa', len:13, glow:0 },
  Legen_Weapon:  { base:'#efba54', shade:'#a87a1c', hi:'#fff0bd', len:17, glow:1 },
};

// หมวก/ผมพิเศษตามคลาส (วาดทับแถว 0-3)
const HATS = {
  plume:  ['.......TT.......', '.....ooTToo.....', '....oTTTTTTo....', '...oTTTTTTTTo...'],
  wizard: ['.......TT.......', '......oTTo......', '.....oTTTTo.....', '...oTTTTTTTTo...'],
  hood:   ['......oooo......', '....ooTTTToo....', '...oTTTTTTTTo...', '..oTTTssssTTo...'.slice(0,16)],
  halo:   ['...oTTTTTTTTo...', '................', '................', '................'],
};
const HELMS = {
  1: ['................', '................', '...oAAAAAAAAo...', '...oAZZZZZZAo...'],
  2: ['................', '...oAAAAAAAAo...', '..oAZAAAAAAZAo..', '..oAAsssssAAo...'.slice(0,16)],
};

function spritePalette(race, cls, armor) {
  const R = RACE_LOOK[race] || RACE_FALLBACK;
  const C = CLASS_LOOK[cls] || CLASS_FALLBACK;
  const A = ARMOR_LOOK[armor] || ARMOR_FALLBACK;
  return {
    o: '#1c1418',                        // เส้นขอบอมม่วง นุ่มกว่าดำสนิท
    s: R.skin, S: R.dark, e: '#2a1a1e',  // ผิว/เงาผิว/ม่านตา
    r: R.hair, R: R.hairDark,            // ผม/เงาผม
    A: A.base, a: A.shade, Z: A.hi,      // เกราะ 3 โทน
    T: C.trim,                           // ลายอกตามคลาส
    P: '#3f2d1e', b: '#2a1d13',          // กางเกง/รองเท้า
  };
}

function blitGrid(ctx, grid, x, y, s, pal) {
  for (let r = 0; r < grid.length; r++) {
    const row = grid[r];
    for (let c = 0; c < row.length; c++) {
      const col = pal[row[c]];
      if (!col) continue;
      ctx.fillStyle = col;
      ctx.fillRect(x + c * s, y + r * s, s, s);
    }
  }
}

/** วาดตัวละครครบชุด — cfg: {race, cls, armor, weapon, pose} */
function drawCharacter(ctx, x, y, s, cfg) {
  const race = cfg.race, cls = cfg.cls;
  const R = RACE_LOOK[race] || RACE_FALLBACK;
  const A = ARMOR_LOOK[cfg.armor] || ARMOR_FALLBACK;
  const C = CLASS_LOOK[cls] || CLASS_FALLBACK;
  const W = WEAPON_LOOK[cfg.weapon];
  const pal = spritePalette(race, cls, cfg.armor);
  const grid = POSES[cfg.pose] || POSES.idle;

  // เงาใต้เท้า — ทำให้ดูยืนบนพื้นจริง ไม่ลอย
  ctx.save();
  ctx.globalAlpha = .3;
  ctx.fillStyle = '#000';
  ctx.beginPath();
  ctx.ellipse(x + 8 * s, y + 22 * s, 6 * s, 1.8 * s, 0, 0, 7);
  ctx.fill();
  ctx.restore();

  // ลักษณะเฉพาะเผ่า (วาดก่อน = อยู่หลังหัว)
  ctx.fillStyle = R.dark;
  if (R.feat === 'horns') { ctx.fillRect(x + 3 * s, y, 2 * s, 3 * s);
                            ctx.fillRect(x + 11 * s, y, 2 * s, 3 * s); }
  if (R.feat === 'horn')  { ctx.fillRect(x + 7 * s, y - 3 * s, 2 * s, 4 * s); }
  if (R.feat === 'ears')  { ctx.fillRect(x + 1 * s, y + 5 * s, 2 * s, 2 * s);
                            ctx.fillRect(x + 13 * s, y + 5 * s, 2 * s, 2 * s); }
  if (R.feat === 'blob')  { ctx.globalAlpha = .55; ctx.fillStyle = R.skin;
                            ctx.fillRect(x + 2 * s, y + 17 * s, 12 * s, 5 * s);
                            ctx.globalAlpha = 1; }

  blitGrid(ctx, grid, x, y, s, pal);

  if (R.feat === 'tusks') {                       // เขี้ยวออร์ค ทับปาก
    ctx.fillStyle = '#f4efe2';
    ctx.fillRect(x + 5 * s, y + 8 * s, s, 2 * s);
    ctx.fillRect(x + 10 * s, y + 8 * s, s, 2 * s);
  }
  if (A.helm) blitGrid(ctx, HELMS[A.helm], x, y, s, pal);
  if (C.hat) blitGrid(ctx, HATS[C.hat], x, y, s, pal);

  if (!W) return;
  // อาวุธ: ด้าม → การ์ด → ใบมีด 3 โทน (ขอบเข้ม ตัวใบ ไฮไลต์เส้นเดียว) → ปลายวาว
  const hx = x + 14 * s, hy = y + 16 * s, lean = cfg.pose === 'atk' ? -2 * s : 0;
  if (W.glow) {
    ctx.save(); ctx.globalAlpha = .3; ctx.fillStyle = W.hi;
    ctx.fillRect(hx - s + lean, hy - (W.len + 2) * s, 4 * s, (W.len + 4) * s);
    ctx.restore();
  }
  ctx.fillStyle = '#3a2a1c'; ctx.fillRect(hx + lean, hy - 2 * s, 2 * s, 4 * s);      // ด้าม
  ctx.fillStyle = W.shade;  ctx.fillRect(hx - s + lean, hy - 3 * s, 4 * s, s);       // การ์ด
  ctx.fillStyle = W.shade;  ctx.fillRect(hx + lean, hy - W.len * s, 2 * s, (W.len - 3) * s);
  ctx.fillStyle = W.base;   ctx.fillRect(hx + lean, hy - W.len * s, s, (W.len - 3) * s);
  ctx.fillStyle = W.hi;     ctx.fillRect(hx + lean, hy - W.len * s, s, 2 * s);       // ปลายวาว
}
