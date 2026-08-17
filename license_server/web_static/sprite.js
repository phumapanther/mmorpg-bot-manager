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

// ══════ 👗 แฟชั่น (2026-08-15) ══════
// แฟชั่น "สวมทับตอนวาด" เท่านั้น — ข้อมูลจริงในฐานข้อมูลไม่ขยับสักตัว
// เกราะเหล็กที่ใส่อยู่ยังเป็นเกราะเหล็ก (ค่าป้องกัน/ความคงทนเท่าเดิม) แค่วาดออกมาเป็นชุดอื่น
// รูปทรงอาวุธยังแยกตามอาชีพเหมือนเดิม แฟชั่นเปลี่ยนแค่ "สีกับความยาว"

const FASHION_OUTFIT = {
  // ✨ สายแสงสว่าง — เกราะขาวมุกขอบทอง ผ้าคลุมทองพลิ้วหลัง
  light_knight: { base:'#f6f1e2', shade:'#c0a874', hi:'#ffffff', helm:2,
                  cape:'#e8bf5c', capeShade:'#b8892c', glow:'#ffe9a8' },
  // 🌑 สายความมืด — ชุดคลุมดำอมม่วง ขอบเรืองม่วง เงาพลิ้ว
  dark_cloak:   { base:'#2f2439', shade:'#171021', hi:'#7b5aa0', helm:1,
                  cape:'#4a2f6b', capeShade:'#241539', glow:'#b06be0' },
};

const FASHION_WEAPON = {
  // เก็บโครงเดียวกับ WEAPON_LOOK — ทรงยังมาจากอาชีพเหมือนเดิม
  light_blade:  { base:'#fff3c4', shade:'#d8a93c', hi:'#ffffff', len:18, glow:1 },
  dark_scythe:  { base:'#4a3560', shade:'#1e1329', hi:'#c07ff0', len:19, glow:1 },
};

// ── ✨ ออร่า (2026-08-15) ──
// เปลวไฟพิกเซล: แอ่งแสงที่พื้น + ลิ้นไฟแตกแฉกลอยขึ้น + วงโคจรรอบตัว
// วาดทุกพิกัดแบบ "ปัดเข้าช่องพิกเซล" (snap) — ไม่งั้นได้เส้นโค้งเนียนที่หลุดสไตล์เกม
const FASHION_AURA = {
  light_halo: { style: 'ring',
                c1: '#b8862a', c2: '#f0c95a', c3: '#fff6d8',  // เข้ม · ตัว · แกนสว่าง
                tongues: 5, height: 15, sway: 2.2 },
  dark_mist:  { style: 'swirl',
                c1: '#4a2170', c2: '#8d47c4', c3: '#dfa8ff',
                tongues: 6, height: 13, sway: 2.8 },
};

/** วาดออร่ารอบตัว — t = เลขเฟรม (ไม่ใส่ = นิ่ง) */
function drawAura(ctx, x, y, s, key, t = 0) {
  const A = FASHION_AURA[key];
  if (!A) return;
  const cx = x + 8 * s, base = y + 21 * s;
  const snap = v => Math.round(v / s) * s;              // บังคับให้ลงช่องพิกเซล
  const px = (gx, gy, w, h, c) => {                     // วาดทีละก้อนพิกเซล
    ctx.fillStyle = c;
    ctx.fillRect(snap(gx), snap(gy), Math.max(s, snap(w)), Math.max(s, snap(h)));
  };

  ctx.save();

  // ① แอ่งแสงที่พื้น — บอกว่าออร่าพุ่งออกมาจากตัว ไม่ใช่ลอยเฉย ๆ
  const pulse = 1 + Math.sin(t / 18) * .12;
  for (let i = 0; i < 3; i++) {
    const w = (11 - i * 3) * s * pulse;
    ctx.globalAlpha = [.32, .5, .7][i];
    px(cx - w / 2, base - i * s, w, s, [A.c1, A.c2, A.c3][i]);
  }

  // ② ลิ้นไฟแตกแฉก — แต่ละแฉกสูงไม่เท่ากันและแกว่งคนละจังหวะ
  for (let i = 0; i < A.tongues; i++) {
    const seed = i * 2.4;
    const spread = (i - (A.tongues - 1) / 2) * 2.6 * s;
    const life = (Math.sin(t / 13 + seed) + 1) / 2;               // 0..1 สูง-ต่ำสลับกัน
    const h = Math.round((A.height * (.55 + life * .45)) );
    for (let r = 0; r < h; r++) {
      const p = r / h;                                            // 0 = โคน, 1 = ปลาย
      const w = Math.max(1, Math.round((1 - p) * 3.2));           // เรียวขึ้นไปหาปลาย
      const sway = Math.sin(t / 11 + seed + p * 2.4) * A.sway * p * s;
      const gy = base - r * s - s;
      ctx.globalAlpha = .28 + (1 - p) * .5;
      px(cx + spread + sway - w * s / 2, gy, w * s, s, A.c1);     // ขอบนอกเข้ม
      if (w > 1) {
        ctx.globalAlpha = .45 + (1 - p) * .45;
        px(cx + spread + sway - (w - 1) * s / 2, gy, (w - 1) * s, s, A.c2);
      }
      if (p < .55) {                                              // แกนสว่างเฉพาะช่วงโคน
        ctx.globalAlpha = .8;
        px(cx + spread + sway - s / 2, gy, s, s, A.c3);
      }
    }
  }

  // ③ วงโคจรรอบตัว — ring = วงแหวนเอียง · swirl = เกลียวหมุน
  const orbit = A.style === 'ring' ? 2 : 3;
  for (let o = 0; o < orbit; o++) {
    const ry = A.style === 'ring' ? 3.2 * s : 5 * s;
    const rx = (9 - o * 1.5) * s;
    const cy = y + (A.style === 'ring' ? 15 - o * 6 : 11) * s;
    const spin = t / (A.style === 'ring' ? 16 : 11) + o * 2.1;
    for (let k = 0; k < 14; k++) {
      const a = spin + (k / 14) * Math.PI * 2;
      const back = Math.sin(a) < 0;                               // ครึ่งหลังจาง = ดูมีมิติ
      ctx.globalAlpha = (back ? .3 : .85) * (1 - k / 26);
      px(cx + Math.cos(a) * rx - s / 2, cy + Math.sin(a) * ry - s / 2,
         s, s, k % 4 === 0 ? A.c3 : A.c2);
    }
  }

  ctx.restore();
  ctx.globalAlpha = 1;
}

function spritePalette(race, cls, armor, outfit) {
  const R = RACE_LOOK[race] || RACE_FALLBACK;
  const C = CLASS_LOOK[cls] || CLASS_FALLBACK;
  // 👗 ใส่แฟชั่นอยู่ = ใช้สีของชุดแฟชั่นแทน (ค่าเกราะจริงไม่เกี่ยวกับตรงนี้เลย)
  const A = FASHION_OUTFIT[outfit] || ARMOR_LOOK[armor] || ARMOR_FALLBACK;
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
  // 👗 แฟชั่นสวมทับตอนวาดเท่านั้น — ของจริงที่ใส่อยู่ไม่ขยับ
  const f = cfg.fashion || {};
  const A = FASHION_OUTFIT[f.outfit] || ARMOR_LOOK[cfg.armor] || ARMOR_FALLBACK;
  const C = CLASS_LOOK[cls] || CLASS_FALLBACK;
  const W = FASHION_WEAPON[f.weapon] || WEAPON_LOOK[cfg.weapon];
  const pal = spritePalette(race, cls, cfg.armor, f.outfit);
  const grid = POSES[cfg.pose] || POSES.idle;

  if (f.aura) drawAura(ctx, x, y, s, f.aura, cfg.frame || 0);   // ออร่าอยู่หลังตัว

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
  if (A.cape) {                                   // 👘 ผ้าคลุมของชุดแฟชั่น พลิ้วอยู่ข้างหลัง
    ctx.save(); ctx.globalAlpha = .9;
    ctx.fillStyle = A.capeShade;
    ctx.fillRect(x + 2 * s, y + 11 * s, 2 * s, 9 * s);
    ctx.fillRect(x + 12 * s, y + 11 * s, 2 * s, 9 * s);
    ctx.fillStyle = A.cape;
    ctx.fillRect(x + 2 * s, y + 11 * s, s, 8 * s);
    ctx.fillRect(x + 12 * s, y + 11 * s, s, 8 * s);
    ctx.fillRect(x + 3 * s, y + 11 * s, 10 * s, s);   // สาบบ่า
    ctx.restore();
  }
  if (A.helm) blitGrid(ctx, HELMS[A.helm], x, y, s, pal);
  if (C.hat) blitGrid(ctx, HATS[C.hat], x, y, s, pal);

  if (!W) return;
  drawWeapon(ctx, x, y, s, W, cls, cfg.pose);
}


// ── ทรงอาวุธรายคลาส (2026-08-14) ──
// ระดับอาวุธ (ไม้/เหล็ก/ตำนาน) คุมสีกับความยาว · คลาสคุม "ทรง"
// ไม่มีคลาส/คลาสแปลกปลอม = ดาบมาตรฐาน
const CLASS_WEAPON = {
  Warrior: 'sword',   // ดาบใบกว้าง มีการ์ดขวาง
  Mage:    'staff',   // คทาหัวคริสตัลเรืองแสง
  Rogue:   'dagger',  // กริชสั้นคู่
  Cleric:  'mace',    // ไม้เท้าหัวกลมมีรัศมี
};

// ── 🗡️ ตารางพิกเซลอาวุธ (2026-08-15) ──
// เดิมวาดด้วยสี่เหลี่ยมทีละชิ้น ทำรายละเอียดไม่ได้ ตอนนี้เป็นตารางพิกเซลจริงเหมือนตัวละคร
// ทรงมาจากอาชีพ · สีมาจากระดับอาวุธหรือแฟชั่น
//   o=เส้นขอบ  1=เงาใบมีด 2=ตัวใบมีด 3=สันไฮไลต์  x=ปีกกระบัง  G=อัญมณี
//   h=ด้ามเข้ม H=ด้ามอ่อน
// ทุกแถวยาว 11 เท่ากันหมด · ใบมีดอยู่ช่อง 3-7
const WEAPON_W = 11;
const WEAPON_ART = {
  sword: [
    '.....o.....',
    '....o3o....',
    '....o3o....',
    '...o123o...',
    '...o123o...',
    '...o123o...',
    '...o123o...',
    '...o123o...',
    '...o123o...',
    '...o123o...',
    '...o123o...',
    '...o123o...',
    '...o123o...',
    'oxxo123oxxo',
    'oxGo123oGxo',
    '.oxo123oxo.',
    '..oo1H3oo..',
    '....ohHo...',
    '....ohHo...',
    '....ohHo...',
    '...oGGGo...',
    '....ooo....',
  ],
  staff: [
    '....ooo....',
    '...oxGxo...',
    '..oxG3Gxo..',
    '.oxG333Gxo.',
    '..oxG3Gxo..',
    '...oxGxo...',
    '....oxo....',
    '....o3o....',
    '....o2o....',
    '....o2o....',
    '....o2o....',
    '....o2o....',
    '...oxGxo...',
    '....o2o....',
    '....o2o....',
    '....o2o....',
    '....o2o....',
    '....o2o....',
    '....oho....',
    '....ohHo...',
    '...oGGGo...',
    '....ooo....',
  ],
  dagger: [
    '...........',
    '...........',
    '...........',
    '...........',
    '.....o.....',
    '....o3o....',
    '...o123o...',
    '...o123o...',
    '...o123o...',
    '...o123o...',
    '...o123o...',
    '...o123o...',
    '.oxo123oxo.',
    'oxGo123oGxo',
    '.oxo123oxo.',
    '..oo1H3oo..',
    '....ohHo...',
    '....ohHo...',
    '...oGGGo...',
    '....ooo....',
    '...........',
    '...........',
  ],
  mace: [
    '...oooo....',
    '..oxG3Gxo..',
    '.oxG333Gxo.',
    '.oxG313Gxo.',
    '.oxG333Gxo.',
    '..oxG3Gxo..',
    '...oxxxo...',
    '....o3o....',
    '....o2o....',
    '....o2o....',
    '....o2o....',
    '....o2o....',
    '....o2o....',
    '....o2o....',
    '....o2o....',
    '....o2o....',
    '....o2o....',
    '....oho....',
    '....ohHo...',
    '....ohHo...',
    '...oGGGo...',
    '....ooo....',
  ],
};

/** ตารางสีอาวุธ — ของที่ไม่ได้ตั้งสีอัญมณี/ปีกไว้ ให้อนุมานจากสีหลัก */
function weaponPalette(W) {
  return {
    o: '#1c1418',
    1: W.shade, 2: W.base, 3: W.hi,
    x: W.trim || W.shade,
    G: W.gem || W.hi,
    h: '#3a2a1c', H: '#5c4227',
  };
}

function drawWeapon(ctx, x, y, s, W, cls, pose) {
  const shape = CLASS_WEAPON[cls] || 'sword';
  const grid = WEAPON_ART[shape] || WEAPON_ART.sword;
  const lean = pose === 'atk' ? -2 * s : 0;
  // ⚠️ ขนาดพิกเซลต้องเท่าตัวละครเสมอ (gs = s) — ย่อ/ขยายอาวุธคนละสเกลแล้วพิกเซลจะเบลอ
  //    ระดับอาวุธต่างกันที่ "สี + เรืองแสง + อัญมณี" ไม่ใช่ที่ขนาด
  const gs = s;
  const gx = x + 8 * s + lean, gy = y - s;        // ด้ามพอดีมือขวา ปลายพ้นหัวขึ้นไป

  if (W.glow) {                                   // อาวุธเรืองแสง — เรืองรอบใบมีด
    ctx.save(); ctx.globalAlpha = .22; ctx.fillStyle = W.hi;
    ctx.fillRect(gx + 2 * gs, gy, 7 * gs, 17 * gs);
    ctx.restore();
  }
  blitGrid(ctx, grid, gx, gy, gs, weaponPalette(W));
}
