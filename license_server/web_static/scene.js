// เอนจินฉากพิกเซล (เว็บเกม เฟส 4)
// ไม่มีกฎเกมในไฟล์นี้ — รับ "ผลที่เกิดขึ้นแล้ว" จากเซิร์ฟเวอร์มาวาดกับเล่นอนิเมชันเท่านั้น
//
// ฉากมีสองชั้น:
//   1. ฉากเดินทาง — วาดด้วยโค้ด เลื่อนแบบ parallax ได้ ใช้ตอนตัวละครกำลังเดิน
//   2. ภาพเหตุการณ์ — พิกเซลอาร์ตจริง 175 ใบใน /assets/events/ ค่อยๆ จางเข้ามาตอนเจอเหตุการณ์
//      ชื่อไฟล์: {ทวีป}_{เหตุการณ์}.png -> ไม่มีก็ลอง {เหตุการณ์}.png -> ไม่มีอีกก็ใช้ฉากวาดเอง

const GROUND_Y = 108;
const FLASH_FRAMES = 9;
const HIT_FRAMES = 16;      // ความยาวจังหวะ "โดนตีแล้วเจ็บ" ของมอน (เฟรม)
// ชนิดกับดักที่วาดได้ — คีย์ตรงกับทวีปในเกม (ทวีปที่ไม่มีในนี้ใช้หนามแหลมกลาง)
const TRAP_FX = { main: 1, demon: 1, frozen: 1, nether: 1, volcanic: 1,
                  sylvan: 1, mechanized: 1, skyward: 1, ocean: 1 };               // จำนวนเฟรมที่มอนแฟลชขาวก่อนแตกเป็นเศษ

/** '#e8563b' -> '232,86,59' (ไว้ทำสีโปร่งใสของวงแหวน) */
function hexRgb(hex) {
  const h = String(hex).replace('#', '');
  return [0, 2, 4].map(i => parseInt(h.slice(i, i + 2), 16) || 0).join(',');
}                 // เส้นพื้นในพิกัดภายในของ canvas (320x132)

// สีประจำทวีป — คีย์ตรงกับ CONTINENTS ในเกม (มีเทสคุมว่าครบทุกทวีป)
const MAPS = {
  main:       { sky:['#2a3a5c','#5b6f94','#c99a6a'], far:'#3c4a68', near:'#2a3448', gnd:['#3a3226','#241f18'], p:'#ffffff44' },
  demon:      { sky:['#1a0c18','#3d1030','#82203c'], far:'#33132c', near:'#220d1e', gnd:['#2a0f22','#180818'], p:'#ff4a6a66' },
  frozen:     { sky:['#1c2c40','#3f6484','#a8ccdd'], far:'#4a6a86', near:'#31485e', gnd:['#c8dbe6','#8fa9ba'], p:'#ffffffaa' },
  nether:     { sky:['#140a0a','#361212','#6e2415'], far:'#2c1010', near:'#1c0a0a', gnd:['#241010','#160808'], p:'#ff8a3a66' },
  volcanic:   { sky:['#241a2e','#4a2838','#a04f30'], far:'#3a2430', near:'#2b1a22', gnd:['#1a1119','#120c11'], p:'#ffb45a88' },
  sylvan:     { sky:['#16241c','#2f4a34','#6f9455'], far:'#28402e', near:'#1c2e21', gnd:['#2a3a24','#18220f'], p:'#a8d07a55' },
  mechanized: { sky:['#1a1a20','#33343e','#6a6a58'], far:'#2c2d36', near:'#1e1f26', gnd:['#2e2e34','#1a1a1e'], p:'#e8b04b55' },
  skyward:    { sky:['#2b3f6e','#6a86c0','#e0c7d8'], far:'#54689a', near:'#3c4a74', gnd:['#8fa0c8','#5f6d94'], p:'#ffffff77' },
  ocean:      { sky:['#0e2430','#1c4a5e','#4d8fa0'], far:'#1a3d4e', near:'#122a38', gnd:['#16404e','#0c2630'], p:'#9fe0ee66' },
};

// มอนสเตอร์: ทรงร่าง + สีตามธาตุ (คีย์ธาตุตรงกับ ELEMENTS ในเกม)
const ELEMENT_COLOR = {
  fire:  { c:'#8f2317', hi:'#e8563b', eye:'#ffd08a' },
  water: { c:'#2f6d84', hi:'#7fd0e0', eye:'#ffffff' },
  earth: { c:'#6b5433', hi:'#a8894f', eye:'#e8b04b' },
  wind:  { c:'#4a7a5c', hi:'#8fd0a0', eye:'#eaffee' },
  wood:  { c:'#3f6b3a', hi:'#7fb35c', eye:'#d8f0a0' },
  light: { c:'#8a7a3a', hi:'#ffe9a0', eye:'#ffffff' },
  dark:  { c:'#3a2a4a', hi:'#8a6ab0', eye:'#e85fb0' },
};
const SHAPES = ['dragon', 'slime', 'humanoid', 'golem'];

// ── โหลดภาพแบบแคช: ลองภาพเฉพาะทวีปก่อน แล้วค่อยภาพกลาง ──
const _imgCache = new Map();

function loadImage(src) {
  if (_imgCache.has(src)) return _imgCache.get(src);
  const p = new Promise(resolve => {
    const im = new Image();
    im.onload = () => resolve(im);
    im.onerror = () => resolve(null);      // ไม่มีไฟล์ = ใช้ฉากวาดเองแทน ไม่ใช่ error
    im.src = src;
  });
  _imgCache.set(src, p);
  return p;
}

async function eventArt(eventKey, continent) {
  if (!eventKey) return null;
  if (continent) {
    const im = await loadImage(`/assets/events/${continent}_${eventKey}.png`);
    if (im) return im;
  }
  return await loadImage(`/assets/events/${eventKey}.png`);
}

class Scene {
  constructor(canvas) {
    this.cv = canvas;
    this.ctx = canvas.getContext('2d');
    this.W = canvas.width;
    this.H = canvas.height;

    this.map = 'main';
    this.state = 'idle';            // idle | walk | fight
    this.char = { race: null, cls: null, armor: 'None', weapon: null, pose: 'idle' };
    this.foe = null;                // {shape, element, name}
    this.backdrop = null;           // ภาพเหตุการณ์จริง
    this.backdropAlpha = 0;

    this.scroll = 0;
    this.frame = 0;
    this.heroX = 46;
    this.heroLunge = 0;
    this.heroAlpha = 1;
    this.foeShake = 0;
    this.foeFlash = 0;
    this.foeHit = 0;                 // แรงกระแทกตอนโดนตี — เด้งถอยแล้วสปริงกลับที่
    this.foeSpark = 0;               // ประกายไฟตรงจุดปะทะ
    this.dust = [];
    this.parts = [];
    this.fx = [];
    this.floats = [];
    this.roll = null;
    this.death = null;
    this.heroShake = 0;
    this.heroFall = 0;
    this.pet = null;
    this.flee = null;
    this.ko = null;
    for (let i = 0; i < 26; i++) {
      this.parts.push({ x: Math.random() * this.W, y: Math.random() * GROUND_Y,
                        s: .1 + Math.random() * .35, r: Math.random() * 1.6 + .6 });
    }
    this._tick = this._tick.bind(this);
    requestAnimationFrame(this._tick);
  }

  setCharacter(cfg) { this.char = { ...this.char, ...cfg }; }
  setMap(key) { if (MAPS[key]) this.map = key; }

  walk() { this.state = 'walk'; this.clearBackdrop(); }
  idle() { this.state = 'idle'; }

  clearBackdrop() { this.backdrop = null; this.backdropAlpha = 0; }

  /** โชว์ภาพเหตุการณ์จริง (จางเข้า) — ไม่มีไฟล์ก็อยู่กับฉากวาดเองต่อ */
  async showEvent(eventKey) {
    const im = await eventArt(eventKey, this.map);
    this.backdrop = im;               // null ได้ = ไม่มีภาพ
    this.backdropAlpha = 0;
    this.state = 'idle';
  }

  setFoe(foe) { this.foe = foe; this.state = 'fight'; }
  clearFoe() { this.foe = null; }

  /** เอฟเฟกต์สกิล — key ตรงกับสกิลของแต่ละคลาสในเกม */
  playSkill(key) {
    const dur = { fire:46, frost:46, heavy:26, bash:30, stab:26, evade:34, heal:40, aura:38 }[key];
    if (!dur) return;
    if (key === 'evade') { this.heroAlpha = .35; setTimeout(() => this.heroAlpha = 1, 500); }
    if (key === 'stab') { this.heroAlpha = 0; setTimeout(() => this.heroAlpha = 1, 260); }
    this.fx.push({ k: key, t: 0, dur });
  }

  /** 💥 มอนตาย — แฟลชขาว แล้วแตกเป็นเศษพิกเซลกระเด็นตกพื้น พร้อมวงแหวนพลังกับดวงวิญญาณลอยขึ้น
   *  (ผลแพ้ชนะตัดสินที่เซิร์ฟเวอร์ไปแล้ว ตรงนี้แค่เล่นภาพให้เห็นว่ามันล้ม ไม่ใช่หายไปเฉย ๆ) */
  killFoe() {
    if (!this.foe || this.death) return;
    const col = ELEMENT_COLOR[this.foe.element] || ELEMENT_COLOR.fire;
    const bx = 258, by = GROUND_Y - 44, cell = 3, span = 14 * cell;
    const bits = [];
    for (let i = 0; i < 56; i++) {
      const a = Math.random() * Math.PI * 2, sp = .5 + Math.random() * 2.6;
      bits.push({ x: bx + Math.random() * span, y: by + Math.random() * span,
                  vx: Math.cos(a) * sp, vy: Math.sin(a) * sp - 1.5,
                  sz: 2 + Math.floor(Math.random() * 3),
                  c: [col.c, col.c, col.hi, col.eye, '#ffffff'][Math.floor(Math.random() * 5)] });
    }
    const souls = [];
    for (let i = 0; i < 5; i++) {
      souls.push({ x: bx + 6 + Math.random() * (span - 12), y: by + span * .6,
                   sw: Math.random() * 6.28, sp: .5 + Math.random() * .5 });
    }
    this.death = { t: 0, dur: 86, col, x: bx + span / 2, y: by + span / 2, bits, souls };
    this.foeShake = FLASH_FRAMES;
    this.foeFlash = FLASH_FRAMES;
  }

  _drawDeath() {
    const d = this.death;
    if (!d) return;
    d.t++;
    if (d.t === FLASH_FRAMES) this.foe = null;        // แฟลชจบ ร่างหายไป เหลือแต่เศษ
    if (d.t > d.dur) { this.death = null; return; }
    if (d.t < FLASH_FRAMES) return;

    const ctx = this.ctx;
    const k = (d.t - FLASH_FRAMES) / (d.dur - FLASH_FRAMES);

    // วงแหวนพลังกระจายออกตอนแตก
    if (k < .5) {
      const kk = k / .5;
      ctx.strokeStyle = `rgba(255,230,168,${(1 - kk) * .85})`;
      ctx.lineWidth = Math.max(1, 3 - kk * 2);
      ctx.beginPath(); ctx.arc(d.x, d.y, 5 + kk * 58, 0, 7); ctx.stroke();
      ctx.strokeStyle = `rgba(${hexRgb(d.col.hi)},${(1 - kk) * .6})`;
      ctx.beginPath(); ctx.arc(d.x, d.y, 3 + kk * 34, 0, 7); ctx.stroke();
    }

    // เศษร่างกระเด็น ตกพื้นแล้วเด้งเบา ๆ
    ctx.globalAlpha = Math.max(0, 1 - k * 1.1);
    for (const b of d.bits) {
      b.x += b.vx; b.y += b.vy; b.vy += .17; b.vx *= .985;
      if (b.y > GROUND_Y - b.sz) { b.y = GROUND_Y - b.sz; b.vy *= -.4; b.vx *= .72; }
      ctx.fillStyle = b.c;
      ctx.fillRect(Math.round(b.x), Math.round(b.y), b.sz, b.sz);
    }

    // ดวงวิญญาณลอยขึ้นช้า ๆ ส่ายไปมา
    for (const sl of d.souls) {
      sl.y -= sl.sp; sl.sw += .18;
      ctx.fillStyle = `rgba(255,255,255,${Math.max(0, .85 - k)})`;
      ctx.fillRect(Math.round(sl.x + Math.sin(sl.sw) * 4), Math.round(sl.y), 2, 2);
    }
    ctx.globalAlpha = 1;
  }

  /** ⚠️ กับดักทำงาน — หน้าตาต่างกันตามทวีป (เซิร์ฟเวอร์เป็นคนบอกว่าทวีปไหน)
   *  hit=false คือหลบพ้น จะวาดเงาตัวละครหลบแทนการโดนเต็ม ๆ */
  playTrap(kind, hit) {
    this.fx.push({ k: 'trap', kind: TRAP_FX[kind] ? kind : 'main', hit: hit !== false,
                   t: 0, dur: 54 });
    if (hit !== false) { this.heroLunge = -8; this.heroShake = 12; }
  }

  /** 💨 มอนเผ่นหนี — วาบแสงขาวแล้วพุ่งออกขวาจอ ทิ้งประกายไว้เป็นทาง
   *  ต่างจากตาย: ไม่มีเศษร่างตกพื้น เพราะมันไม่ได้ล้ม */
  fleeFoe() {
    if (!this.foe || this.flee) return;
    const col = ELEMENT_COLOR[this.foe.element] || ELEMENT_COLOR.fire;
    this.flee = { t: 0, dur: 46, col, trail: [] };
    this.foeFlash = 6;
  }

  _drawFlee() {
    const f = this.flee;
    if (!f) return;
    f.t++;
    if (f.t > f.dur) { this.flee = null; this.foe = null; return; }
    const ctx = this.ctx;
    const k = f.t / f.dur;
    const x = 258 + k * k * 140;                       // เร่งความเร็วออกขวาจอ

    if (f.t < 7) {                                     // วาบแสงก่อนพุ่ง
      ctx.fillStyle = `rgba(255,255,255,${.5 - f.t * .07})`;
      ctx.fillRect(248, GROUND_Y - 52, 60, 52);
      return;
    }
    this.foe = null;                                   // ร่างจริงหายแล้ว เหลือแต่แสง

    f.trail.push({ x, y: GROUND_Y - 26 + Math.sin(f.t * .6) * 5 });
    if (f.trail.length > 12) f.trail.shift();
    f.trail.forEach((t, i) => {
      const a = (i / f.trail.length) * (1 - k);
      ctx.fillStyle = `rgba(255,255,255,${a})`;
      ctx.fillRect(Math.round(t.x), Math.round(t.y), 6 - i * .3, 4);
      ctx.fillStyle = `rgba(${hexRgb(f.col.hi)},${a * .8})`;
      ctx.fillRect(Math.round(t.x), Math.round(t.y + 4), 4, 2);
    });
    for (let i = 0; i < 3; i++) {                      // ประกายที่หลุดร่วง
      ctx.fillStyle = `rgba(255,240,190,${(1 - k) * .8})`;
      ctx.fillRect(Math.round(x - 14 - i * 9), GROUND_Y - 34 + i * 7 + (f.t % 5), 2, 2);
    }
  }

  /** 💀 ผู้เล่นหมดสติ — จอมืดลง ตัวละครทรุดลงกับพื้น วิญญาณลอยขึ้น */
  killHero() {
    if (this.ko) return;
    this.ko = { t: 0, dur: 110, souls: [] };
    for (let i = 0; i < 4; i++) {
      this.ko.souls.push({ x: this.heroX + 12 + Math.random() * 20, y: GROUND_Y - 20,
                           sw: Math.random() * 6.28, sp: .35 + Math.random() * .45 });
    }
    this.heroShake = 14;
  }

  _drawKo() {
    const d = this.ko;
    if (!d) return;
    d.t++;
    if (d.t > d.dur) { this.ko = null; this.heroFall = 0; this.heroAlpha = 1; return; }
    const ctx = this.ctx;
    const k = d.t / d.dur;

    this.heroFall = Math.min(22, d.t * 1.1);           // ทรุดลงกับพื้น
    this.heroAlpha = Math.max(.25, 1 - k * .8);

    if (d.t < 8) {                                     // วาบแดงตอนโดนหมัดสุดท้าย
      ctx.fillStyle = `rgba(200,40,30,${.45 - d.t * .05})`;
      ctx.fillRect(0, 0, this.W, this.H);
    }

    // ขอบจอมืดเข้ม (vignette) ค่อย ๆ บีบเข้ามา
    const dark = Math.min(.62, k * 1.3);
    const g = ctx.createRadialGradient(this.heroX + 20, GROUND_Y - 24, 10,
                                       this.heroX + 20, GROUND_Y - 24, this.W * .8);
    g.addColorStop(0, `rgba(20,0,0,${dark * .25})`);
    g.addColorStop(1, `rgba(8,0,0,${dark})`);
    ctx.fillStyle = g;
    ctx.fillRect(0, 0, this.W, this.H);

    for (const sl of d.souls) {                        // วิญญาณลอยขึ้น
      sl.y -= sl.sp; sl.sw += .16;
      ctx.fillStyle = `rgba(230,220,255,${Math.max(0, .8 - k)})`;
      ctx.fillRect(Math.round(sl.x + Math.sin(sl.sw) * 5), Math.round(sl.y), 2, 3);
    }

    if (k > .3) {                                      // ป้าย K.O.
      ctx.textAlign = 'center';
      ctx.font = 'bold 22px system-ui';
      ctx.strokeStyle = 'rgba(0,0,0,.85)'; ctx.lineWidth = 4;
      ctx.fillStyle = `rgba(232,119,106,${Math.min(1, (k - .3) * 4)})`;
      ctx.strokeText('K.O.', this.W / 2, this.H / 2 + 4);
      ctx.fillText('K.O.', this.W / 2, this.H / 2 + 4);
    }
  }

  attack() { this.state = 'fight'; this.char.pose = 'atk'; this.heroLunge = 14;
             setTimeout(() => this.char.pose = 'idle', 420); }
  /** โดนตีแต่ยังไม่ตาย — ต้องเห็นว่า "เจ็บ" ไม่ใช่แค่หลอดเลือดลด
   *  กระเด็นถอย + ตัวยุบ + ประกายไฟ + วาบขาว แล้วค่อยสปริงกลับที่เดิม */
  hitFoe() { this.foeHit = HIT_FRAMES; this.foeSpark = 10; this.foeShake = 8; this.foeFlash = 5; }

  /** โชว์ผลทอยเต๋าของทั้งสองฝั่ง — ผู้เล่นต้องเห็นว่าชนะ/แพ้เพราะอะไร ห่างกันเท่าไหร่
   *  roll = {player_roll, monster_roll, player_parts, monster_parts} จากเซิร์ฟเวอร์ */
  showRoll(roll) {
    // ต้องเป็นก้อนข้อมูลเต๋าสองฝั่งเท่านั้น (เคยมีเลขทอยเดี่ยวหลุดเข้ามาจนขึ้น undefined/NaN)
    if (!roll || typeof roll !== 'object'
        || !Number.isFinite(+roll.player_roll) || !Number.isFinite(+roll.monster_roll)) return;
    this.roll = { ...roll, player_roll: +roll.player_roll, monster_roll: +roll.monster_roll,
                  t: 0, dur: 150 };
  }
  clearRoll() { this.roll = null; }

  _drawRoll() {
    const r = this.roll;
    if (!r) return;
    r.t++;
    if (r.t > r.dur) { this.roll = null; return; }

    const ctx = this.ctx;
    const rolling = r.t < 24;                       // ช่วงแรกให้เลขวิ่งก่อนเฉลย
    const pv = rolling ? 1 + Math.floor(Math.random() * 20) : r.player_roll;
    const mv = rolling ? 1 + Math.floor(Math.random() * 20) : r.monster_roll;
    const win = r.player_roll > r.monster_roll;
    const gap = Math.abs(r.player_roll - r.monster_roll);

    const box = (x, label, val, hot) => {
      ctx.fillStyle = 'rgba(12,8,6,.82)';
      ctx.fillRect(x, 6, 62, 30);
      ctx.strokeStyle = hot ? '#e8b04b' : '#5c4733';
      ctx.lineWidth = hot ? 2 : 1;
      ctx.strokeRect(x + .5, 6.5, 61, 29);
      ctx.textAlign = 'center';
      ctx.font = '8px system-ui';
      ctx.fillStyle = '#a99274';
      ctx.fillText(label, x + 31, 16);
      ctx.font = 'bold 15px system-ui';
      ctx.fillStyle = hot ? '#ffe6a8' : '#f2e7d8';
      ctx.fillText(String(val), x + 31, 31);
    };
    const [lLabel, rLabel] = r.labels || ['🎲 คุณ', '🎲 มอน'];
    const hotLeft = r.win === undefined ? win : !!r.win;
    box(10, lLabel, pv, !rolling && hotLeft);
    box(this.W - 72, rLabel, mv, !rolling && !hotLeft);

    if (!rolling) {
      ctx.textAlign = 'center';
      ctx.font = 'bold 11px system-ui';
      ctx.fillStyle = hotLeft ? '#8fd07a' : '#e8776a';
      ctx.strokeStyle = 'rgba(0,0,0,.8)'; ctx.lineWidth = 3;
      const txt = r.verdict || (gap === 0 ? 'เสมอ'
                                : (win ? `ชนะ +${gap} แต้ม` : `แพ้ -${gap} แต้ม`));
      ctx.strokeText(txt, this.W / 2, 22);
      ctx.fillText(txt, this.W / 2, 22);

      // ที่มาของแต้ม (โบนัสต่างๆ) บรรทัดเล็กใต้กล่อง
      ctx.font = '8px system-ui';
      ctx.fillStyle = '#a99274';
      const strip = s => String(s).replace(/`/g, '');
      if (r.player_parts) ctx.fillText(strip(r.player_parts.join(' ')), 41, 45);
      if (r.monster_parts) ctx.fillText(strip(r.monster_parts.join(' ')), this.W - 41, 45);
    }
  }

  /** เลขลอย (ดาเมจ/ฮีล/ทอง) — คืนค่าเป็นพิกัดภายใน canvas */
  float(text, kind, xPct) {
    this.floats.push({ text, kind: kind || '', x: (xPct ?? 60) / 100 * this.W,
                       y: GROUND_Y - 40, life: 55 });
  }

  // ── การวาด ──

  _hills(off, amp, base, col) {
    const ctx = this.ctx;
    ctx.fillStyle = col;
    for (let x = 0; x < this.W; x += 2) {
      const h = base + Math.sin((x + off) * .028) * amp + Math.sin((x + off) * .011) * amp * .7;
      ctx.fillRect(x, h, 2, GROUND_Y - h + 8);
    }
  }

  _drawScenery() {
    const ctx = this.ctx, M = MAPS[this.map] || MAPS.main;
    const g = ctx.createLinearGradient(0, 0, 0, GROUND_Y);
    g.addColorStop(0, M.sky[0]); g.addColorStop(.5, M.sky[1]); g.addColorStop(1, M.sky[2]);
    ctx.fillStyle = g; ctx.fillRect(0, 0, this.W, GROUND_Y);

    ctx.fillStyle = M.sky[2];
    ctx.globalAlpha = .55;
    ctx.beginPath(); ctx.arc(240, 66, 24, 0, 7); ctx.fill();
    ctx.globalAlpha = 1;

    this._hills(this.scroll * .18, 13, 60, M.far);
    this._hills(this.scroll * .45, 9, 80, M.near);

    this.parts.forEach(e => {
      e.x -= e.s * 1.6; e.y -= e.s * .5;
      if (e.x < -2 || e.y < -2) { e.x = this.W + 2; e.y = 20 + Math.random() * (GROUND_Y - 20); }
      ctx.fillStyle = M.p;
      ctx.fillRect(Math.round(e.x), Math.round(e.y), Math.ceil(e.r), Math.ceil(e.r));
    });

    ctx.fillStyle = M.gnd[0]; ctx.fillRect(0, GROUND_Y, this.W, this.H - GROUND_Y);
    ctx.fillStyle = M.gnd[1];
    for (let x = -(this.scroll % 16); x < this.W; x += 16) ctx.fillRect(x, GROUND_Y + 6, 9, 2);
    ctx.fillStyle = M.near; ctx.fillRect(0, GROUND_Y, this.W, 2);
  }

  _drawFoe() {
    if (!this.foe) return;
    const ctx = this.ctx;
    const col = ELEMENT_COLOR[this.foe.element] || ELEMENT_COLOR.fire;
    const dying = this.death && this.death.t < FLASH_FRAMES;
    const c = dying ? '#ffffff' : (this.foeFlash > 0 ? col.hi : col.c);
    const s = 3;
    // k: 1 ตอนเพิ่งโดน → 0 ตอนกลับที่เดิม · kb: กระเด็นถอยแล้วแกว่งกลับแบบสปริง
    const k = this.foeHit > 0 ? this.foeHit / HIT_FRAMES : 0;
    const kb = k ? Math.cos((1 - k) * 9) * 13 * k : 0;
    const sx = s * (1 + .20 * k), sy = s * (1 - .24 * k);      // โดนอัดจนตัวยุบแบน
    const x = 258 + kb + (this.foeShake ? Math.random() * 4 - 2 : 0);
    const y = (GROUND_Y - 44) + 14 * (s - sy);                 // ยุบจากหัวลง เท้ายังติดพื้น
    const R = (dx, dy, w, h, cc) => { ctx.fillStyle = cc; ctx.fillRect(x + dx * sx, y + dy * sy, w * sx, h * sy); };

    switch (this.foe.shape) {
      case 'slime':
        R(2,5,10,7,c); R(1,7,12,5,c); R(3,4,8,2,c);
        R(3,6,2,2,col.eye); R(9,6,2,2,col.eye);
        R(4,7,1,1,'#241812'); R(10,7,1,1,'#241812'); R(2,4,3,1,col.hi); break;
      case 'humanoid':
        R(4,1,6,4,c); R(5,2,1,1,col.eye); R(8,2,1,1,col.eye);
        R(3,5,8,6,c); R(2,6,1,4,c); R(11,6,1,4,c);
        R(4,11,2,3,c); R(8,11,2,3,c); R(12,3,1,9,col.hi); break;
      case 'golem':
        R(3,2,8,5,c); R(4,3,2,2,col.eye); R(8,3,2,2,col.eye);
        R(2,7,10,6,c); R(0,8,2,4,col.hi); R(12,8,2,4,col.hi);
        R(4,13,2,1,c); R(8,13,2,1,c); R(5,9,4,2,col.hi); break;
      default:                                   // dragon
        R(1,1,2,3,c); R(11,1,2,3,c);
        R(2,4,10,8,c); R(1,6,12,5,c);
        R(0,7,2,2,col.hi); R(12,7,2,2,col.hi);
        R(3,6,2,2,col.eye); R(9,6,2,2,col.eye);
        R(4,10,6,1,'#241812'); R(4,12,2,2,c); R(8,12,2,2,c);
    }
    // ประกายไฟกระจายออกจากจุดปะทะ — บอกว่า "โดนตรงนี้" ไม่ใช่แค่ตัวสั่น
    if (this.foeSpark > 0 && !dying) {
      const p = 1 - this.foeSpark / 10;
      ctx.fillStyle = p < .5 ? '#fff4d0' : col.hi;
      for (let i = 0; i < 6; i++) {
        const a = i * (Math.PI / 3) + .4;
        const d = 7 + p * 22;
        ctx.fillRect(x + 7 * sx + Math.cos(a) * d, y + 7 * sy + Math.sin(a) * d,
                     3 - p * 2, 3 - p * 2);
      }
      this.foeSpark--;
    }
    if (this.foeHit) this.foeHit--;
    if (this.foeShake) this.foeShake--;
    if (this.foeFlash) this.foeFlash--;
  }

  _drawFx(f, p) {
    const ctx = this.ctx;
    const hx = this.heroX + 40, hy = GROUND_Y - 30, tx = 268, ty = GROUND_Y - 28;
    if (f.k === 'fire' || f.k === 'frost') {
      const warm = f.k === 'fire';
      const x = hx + (tx - hx) * Math.min(1, p * 1.4);
      const y = hy - Math.sin(Math.min(1, p * 1.4) * Math.PI) * 16;
      if (p < .72) {
        for (let i = 0; i < 5; i++) {
          ctx.fillStyle = warm ? (i % 2 ? '#ffb648' : '#e8563b') : (i % 2 ? '#9fe0ee' : '#4a8fa8');
          ctx.fillRect(Math.round(x - i * 3), Math.round(y + Math.sin(f.t * .5 + i) * 2), 4 - i * .5, 4 - i * .5);
        }
      } else {
        const k = (p - .72) / .28;
        ctx.strokeStyle = warm ? `rgba(255,150,60,${1 - k})` : `rgba(159,224,238,${1 - k})`;
        ctx.lineWidth = 3; ctx.beginPath(); ctx.arc(tx, ty, k * 26, 0, 7); ctx.stroke();
      }
    } else if (f.k === 'heavy') {
      ctx.strokeStyle = `rgba(255,224,168,${1 - p})`; ctx.lineWidth = 5;
      ctx.beginPath(); ctx.arc(hx + 8, hy, 18 + p * 22, -1.4, .7); ctx.stroke();
    } else if (f.k === 'bash') {
      ctx.fillStyle = `rgba(217,59,43,${(1 - p) * .5})`;
      ctx.fillRect(hx, hy - 18, (tx - hx) * p, 26);
      ctx.strokeStyle = `rgba(255,255,255,${1 - p})`; ctx.lineWidth = 2;
      ctx.strokeRect(hx + (tx - hx) * p - 6, hy - 14, 12, 20);
    } else if (f.k === 'stab') {
      ctx.strokeStyle = `rgba(180,255,180,${1 - p})`; ctx.lineWidth = 2;
      for (let i = 0; i < 3; i++) {
        ctx.beginPath(); ctx.moveTo(tx - 14, ty - 16 + i * 10);
        ctx.lineTo(tx + 14, ty - 6 + i * 10); ctx.stroke();
      }
    } else if (f.k === 'evade') {
      ctx.fillStyle = `rgba(160,220,180,${(1 - p) * .4})`;
      for (let i = 1; i <= 3; i++) ctx.fillRect(this.heroX - i * 9, GROUND_Y - 52, 12, 50);
    } else if (f.k === 'heal') {
      for (let i = 0; i < 7; i++) {
        const yy = GROUND_Y - 6 - ((p * 46 + i * 7) % 50);
        ctx.fillStyle = `rgba(111,168,96,${1 - p})`;
        ctx.fillRect(this.heroX + 4 + (i * 5) % 26, Math.round(yy), 3, 3);
      }
    } else if (f.k === 'trap') {
      this._drawTrap(f, p);
    } else if (f.k === 'aura') {
      ctx.strokeStyle = `rgba(232,176,75,${1 - p})`; ctx.lineWidth = 2;
      ctx.beginPath(); ctx.ellipse(this.heroX + 20, GROUND_Y - 8, 8 + p * 34, 4 + p * 13, 0, 0, 7); ctx.stroke();
      ctx.beginPath(); ctx.ellipse(this.heroX + 20, GROUND_Y - 26, 6 + p * 26, 3 + p * 10, 0, 0, 7); ctx.stroke();
    }
  }

  /** กับดัก 9 แบบ — พิกัดอ้างอิงตัวละคร (hx, GROUND_Y) ทุกอัน */
  _drawTrap(f, p) {
    const ctx = this.ctx;
    const cx = this.heroX + 22, g = GROUND_Y;
    const fade = 1 - p;
    const jag = (x, y0, y1, w, col, n) => {          // เส้นหยัก ๆ ใช้ทำสายฟ้า/รอยแยก
      ctx.strokeStyle = col; ctx.lineWidth = w; ctx.beginPath(); ctx.moveTo(x, y0);
      for (let i = 1; i <= n; i++) {
        ctx.lineTo(x + (Math.random() - .5) * 14, y0 + (y1 - y0) * (i / n));
      }
      ctx.stroke();
    };

    switch (f.kind) {
      case 'demon':                                  // 🌋 รอยแยกปีศาจ — เปลวไฟพุ่งจากพื้น
        ctx.fillStyle = `rgba(20,4,8,${fade})`;
        ctx.fillRect(cx - 20, g - 3, 40, 5);
        for (let i = 0; i < 9; i++) {
          const h = (1 - Math.abs(i - 4) / 5) * 34 * Math.sin(p * Math.PI);
          ctx.fillStyle = i % 2 ? `rgba(255,120,40,${fade})` : `rgba(200,30,40,${fade})`;
          ctx.fillRect(cx - 18 + i * 4, g - h, 3, h);
        }
        break;
      case 'frozen':                                 // 🕳️ น้ำแข็งแตก — เศษน้ำแข็งกระเด็น
        ctx.strokeStyle = `rgba(200,235,255,${fade})`; ctx.lineWidth = 1;
        for (let i = 0; i < 5; i++) {
          ctx.beginPath(); ctx.moveTo(cx, g);
          ctx.lineTo(cx - 22 + i * 11, g - 12 - (i % 2) * 6); ctx.stroke();
        }
        for (let i = 0; i < 8; i++) {
          const a = (i / 8) * 6.28;
          ctx.fillStyle = `rgba(230,248,255,${fade})`;
          ctx.fillRect(cx + Math.cos(a) * p * 34, g - 8 - Math.sin(a) * p * 26, 3, 3);
        }
        break;
      case 'nether':                                 // 🕸️ วิญญาณอาฆาต — ดวงม่วงวนรอบตัว
        for (let i = 0; i < 6; i++) {
          const a = p * 7 + i * 1.05;
          ctx.fillStyle = `rgba(180,110,220,${fade})`;
          ctx.fillRect(cx + Math.cos(a) * 22, g - 30 + Math.sin(a) * 14, 4, 4);
        }
        ctx.strokeStyle = `rgba(140,80,190,${fade * .7})`; ctx.lineWidth = 1;
        ctx.beginPath(); ctx.ellipse(cx, g - 28, 24, 15, 0, 0, 7); ctx.stroke();
        break;
      case 'volcanic':                               // 🌋 ไอพิษพุ่งขึ้น
        for (let i = 0; i < 7; i++) {
          const yy = g - ((p * 60 + i * 9) % 62);
          ctx.fillStyle = `rgba(190,160,90,${fade * .8})`;
          ctx.fillRect(cx - 16 + i * 5, Math.round(yy), 4, 5);
        }
        break;
      case 'sylvan':                                 // 🌿 รากไม้รัดขา
        ctx.strokeStyle = `rgba(90,160,70,${fade})`; ctx.lineWidth = 3;
        for (let i = 0; i < 4; i++) {
          ctx.beginPath(); ctx.moveTo(cx - 18 + i * 12, g);
          ctx.quadraticCurveTo(cx - 8 + i * 8, g - 22 * p, cx + (i % 2 ? 10 : -10), g - 34 * p);
          ctx.stroke();
        }
        break;
      case 'mechanized':                             // ⚡ สายฟ้าฟาดลงมา
        if (p < .55) {
          jag(cx, 0, g - 4, 3, `rgba(255,240,150,${fade})`, 7);
          jag(cx, 0, g - 4, 1, `rgba(255,255,255,${fade})`, 7);
          ctx.fillStyle = `rgba(255,255,200,${(1 - p / .55) * .28})`;
          ctx.fillRect(0, 0, this.W, this.H);
        }
        break;
      case 'skyward':                                // 🌪️ ลมหมุนดูดร่าง
        ctx.strokeStyle = `rgba(220,230,255,${fade})`; ctx.lineWidth = 2;
        for (let i = 0; i < 4; i++) {
          const r = 6 + i * 8, yy = g - 6 - i * 12;
          ctx.beginPath();
          ctx.ellipse(cx, yy, r, r * .34, p * 4 + i, 0, 5); ctx.stroke();
        }
        break;
      case 'ocean':                                  // 🌀 พายุฝนสาดเฉียง
        ctx.strokeStyle = `rgba(160,210,240,${fade})`; ctx.lineWidth = 1;
        for (let i = 0; i < 16; i++) {
          const x = ((i * 23 + p * 160) % (this.W + 40)) - 20;
          const y = ((i * 17 + p * 220) % this.H);
          ctx.beginPath(); ctx.moveTo(x, y); ctx.lineTo(x - 5, y + 9); ctx.stroke();
        }
        break;
      default:                                       // ⚠️ หนามแหลมดีดขึ้นจากพื้น
        for (let i = 0; i < 6; i++) {
          const h = 20 * Math.sin(Math.min(1, p * 2.2) * Math.PI) + 4;
          const x = cx - 20 + i * 8;
          ctx.fillStyle = `rgba(190,190,200,${fade})`;
          ctx.beginPath(); ctx.moveTo(x, g); ctx.lineTo(x + 4, g - h);
          ctx.lineTo(x + 8, g); ctx.closePath(); ctx.fill();
        }
    }

    if (!f.hit && p > .25) {                         // หลบพ้น — เงาซ้อนแบบหลบตัว
      ctx.fillStyle = `rgba(180,220,200,${fade * .45})`;
      ctx.fillRect(this.heroX - 14, GROUND_Y - 52, 12, 50);
    }
  }

  _tick() {
    const ctx = this.ctx;
    ctx.clearRect(0, 0, this.W, this.H);
    this._drawScenery();

    // ภาพเหตุการณ์จริงจางทับฉากวาดเอง
    if (this.backdrop) {
      this.backdropAlpha = Math.min(1, this.backdropAlpha + .06);
      ctx.globalAlpha = this.backdropAlpha;
      ctx.drawImage(this.backdrop, 0, 0, this.W, this.H);
      ctx.globalAlpha = 1;
    }

    // ฝุ่นใต้เท้าตอนวิ่ง
    for (let i = this.dust.length - 1; i >= 0; i--) {
      const d = this.dust[i]; d.x -= 1.6; d.life--;
      if (d.life <= 0) { this.dust.splice(i, 1); continue; }
      ctx.fillStyle = `rgba(200,180,150,${d.life / 22})`;
      ctx.fillRect(Math.round(d.x), Math.round(d.y), 2, 2);
    }

    const running = this.state === 'walk';
    const pose = this.char.pose === 'atk' ? 'atk'
               : running ? (Math.floor(this.frame / 6) % 2 ? 'run1' : 'run2') : 'idle';
    const bob = running && Math.floor(this.frame / 6) % 2 ? -2 : 0;
    if (typeof drawCharacter === 'function') {
      const shake = this.heroShake ? (this.heroShake--, Math.random() * 5 - 2.5) : 0;
      drawCharacter(ctx, Math.round(this.heroX + this.heroLunge + shake),
                    GROUND_Y - 68 + bob + this.heroFall, 3,
                    { ...this.char, pose }, this.heroAlpha);
    }

    this._drawPet();
    this._drawFoe();
    this._drawDeath();
    this._drawFlee();

    for (let i = this.fx.length - 1; i >= 0; i--) {
      const f = this.fx[i]; f.t++;
      const p = f.t / f.dur;
      if (p >= 1) { this.fx.splice(i, 1); continue; }
      this._drawFx(f, p);
    }

    this._drawKo();
    this._drawRoll();

    // เลขลอย
    for (let i = this.floats.length - 1; i >= 0; i--) {
      const fl = this.floats[i]; fl.life--; fl.y -= 0.9;
      if (fl.life <= 0) { this.floats.splice(i, 1); continue; }
      const a = Math.min(1, fl.life / 22);
      ctx.globalAlpha = a;
      ctx.font = 'bold ' + (fl.kind === 'crit' ? 22 : 16) + 'px system-ui';
      ctx.textAlign = 'center';
      ctx.fillStyle = fl.kind === 'heal' ? '#8fd07a'
                    : fl.kind === 'miss' ? '#b0a08c'
                    : fl.kind === 'crit' ? '#ffe6a8' : '#e8b04b';
      ctx.strokeStyle = 'rgba(0,0,0,.75)'; ctx.lineWidth = 3;
      ctx.strokeText(fl.text, fl.x, fl.y);
      ctx.fillText(fl.text, fl.x, fl.y);
      ctx.globalAlpha = 1;
    }

    if (running) {
      this.scroll += 2.2;
      if (this.frame % 5 === 0) this.dust.push({ x: this.heroX + 6, y: GROUND_Y - 3, life: 22 });
    }
    if (this.heroLunge > 0) this.heroLunge -= 2;
    this.frame++;
    requestAnimationFrame(this._tick);
  }
}


// ── 🐾 สัตว์เลี้ยงที่พาไปด้วย (2026-08-14) ──
// วาดด้วยโค้ดเหมือนมอน — ไม่ต้องมีไฟล์ภาพ เพิ่มสัตว์เลี้ยงใหม่แล้ววาดได้ทันที
// คีย์ตรงกับ pets.list ในคอนฟิก (มีเทสคุมว่าครบทุกตัว)
const PET_LOOK = {
  slime:      { body: '#5fa85c', hi: '#9fe08a', eye: '#ffffff', shape: 'blob' },
  batling:    { body: '#6a4a7a', hi: '#a88fc0', eye: '#ffd08a', shape: 'wing' },
  wolfpup:    { body: '#7a6a58', hi: '#b0a08a', eye: '#ffd08a', shape: 'beast' },
  imp:        { body: '#a8452f', hi: '#e8776a', eye: '#ffe6a8', shape: 'horn' },
  griffin:    { body: '#b08a3a', hi: '#ffe6a8', eye: '#ffffff', shape: 'wing' },
  golemite:   { body: '#6b6b6b', hi: '#a0a0a0', eye: '#8fd0e0', shape: 'block' },
  phantom:    { body: '#4a3a5c', hi: '#9f8fc0', eye: '#e85fb0', shape: 'ghost' },
  dragonling: { body: '#8f2317', hi: '#e8563b', eye: '#ffd08a', shape: 'horn' },
};

Scene.prototype.setPet = function (key) {
  this.pet = PET_LOOK[key] ? { key, bob: 0, lunge: 0 } : null;
};

/** 🐾 สัตว์เลี้ยงออกท่าตามเจ้าของ */
Scene.prototype.petAttack = function () {
  if (this.pet) this.pet.lunge = 12;
};

Scene.prototype._drawPet = function () {
  if (!this.pet) return;
  const look = PET_LOOK[this.pet.key];
  const ctx = this.ctx;
  const running = this.state === 'walk';

  // เดินตามหลังเจ้าของ ห่างประมาณหนึ่งตัว — ตอนวิ่งจะกระโดดตามจังหวะ
  this.pet.bob = running && Math.floor(this.frame / 5) % 2 ? -3 : 0;
  if (this.pet.lunge > 0) this.pet.lunge -= 1.6;
  const x = Math.round(this.heroX - 22 + this.pet.lunge * 2.2);
  const y = GROUND_Y - 16 + this.pet.bob;
  const s = 2;
  const R = (dx, dy, w, h, c) => { ctx.fillStyle = c; ctx.fillRect(x + dx * s, y + dy * s, w * s, h * s); };

  ctx.globalAlpha = look.shape === 'ghost' ? .72 : 1;      // เงาลึกลับโปร่งแสง
  switch (look.shape) {
    case 'wing':
      R(0, 1, 2, 3, look.hi); R(6, 1, 2, 3, look.hi);       // ปีกสองข้าง
      R(2, 2, 4, 4, look.body); R(3, 3, 1, 1, look.eye); R(5, 3, 1, 1, look.eye); break;
    case 'beast':
      R(1, 2, 6, 4, look.body); R(6, 1, 2, 2, look.body);   // หัวยื่นหน้า
      R(7, 2, 1, 1, look.eye); R(1, 0, 1, 2, look.hi); R(0, 5, 1, 2, look.body);
      R(2, 6, 1, 1, look.body); R(6, 6, 1, 1, look.body); break;
    case 'horn':
      R(2, 0, 1, 2, look.hi); R(5, 0, 1, 2, look.hi);       // เขาสองข้าง
      R(1, 2, 6, 5, look.body); R(2, 3, 1, 1, look.eye); R(5, 3, 1, 1, look.eye);
      R(0, 3, 1, 2, look.hi); R(7, 3, 1, 2, look.hi); break;
    case 'block':
      R(1, 1, 6, 6, look.body); R(2, 2, 2, 2, look.eye);
      R(0, 3, 1, 3, look.hi); R(7, 3, 1, 3, look.hi); break;
    case 'ghost':
      R(2, 0, 4, 6, look.body); R(1, 2, 6, 4, look.body);
      R(2, 6, 1, 1, look.body); R(4, 6, 1, 1, look.body);   // ชายผ้าหยัก
      R(2, 2, 1, 1, look.eye); R(5, 2, 1, 1, look.eye); break;
    default:                                                // blob
      R(1, 3, 6, 4, look.body); R(2, 2, 4, 2, look.body);
      R(2, 4, 1, 1, look.eye); R(5, 4, 1, 1, look.eye);
      R(2, 2, 2, 1, look.hi);
  }
  ctx.globalAlpha = 1;

  if (this.pet.lunge > 6) {                                 // ประกายตอนออกท่า
    ctx.fillStyle = `rgba(255,230,168,${this.pet.lunge / 14})`;
    ctx.fillRect(x + 18, y + 4, 5, 2);
    ctx.fillRect(x + 24, y + 2, 3, 2);
  }
};
