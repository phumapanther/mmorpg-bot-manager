// เอนจินฉากพิกเซล (เว็บเกม เฟส 4)
// ไม่มีกฎเกมในไฟล์นี้ — รับ "ผลที่เกิดขึ้นแล้ว" จากเซิร์ฟเวอร์มาวาดกับเล่นอนิเมชันเท่านั้น
//
// ฉากมีสองชั้น:
//   1. ฉากเดินทาง — วาดด้วยโค้ด เลื่อนแบบ parallax ได้ ใช้ตอนตัวละครกำลังเดิน
//   2. ภาพเหตุการณ์ — พิกเซลอาร์ตจริง 175 ใบใน /assets/events/ ค่อยๆ จางเข้ามาตอนเจอเหตุการณ์
//      ชื่อไฟล์: {ทวีป}_{เหตุการณ์}.png -> ไม่มีก็ลอง {เหตุการณ์}.png -> ไม่มีอีกก็ใช้ฉากวาดเอง

const GROUND_Y = 108;                 // เส้นพื้นในพิกัดภายในของ canvas (320x132)

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
    this.dust = [];
    this.parts = [];
    this.fx = [];
    this.floats = [];
    this.roll = null;
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

  attack() { this.state = 'fight'; this.char.pose = 'atk'; this.heroLunge = 14;
             setTimeout(() => this.char.pose = 'idle', 420); }
  hitFoe() { this.foeShake = 14; this.foeFlash = 5; }

  /** โชว์ผลทอยเต๋าของทั้งสองฝั่ง — ผู้เล่นต้องเห็นว่าชนะ/แพ้เพราะอะไร ห่างกันเท่าไหร่
   *  roll = {player_roll, monster_roll, player_parts, monster_parts} จากเซิร์ฟเวอร์ */
  showRoll(roll) {
    this.roll = { ...roll, t: 0, dur: 150 };
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
    box(10, '🎲 คุณ', pv, !rolling && win);
    box(this.W - 72, '🎲 มอน', mv, !rolling && !win);

    if (!rolling) {
      ctx.textAlign = 'center';
      ctx.font = 'bold 11px system-ui';
      ctx.fillStyle = win ? '#8fd07a' : '#e8776a';
      ctx.strokeStyle = 'rgba(0,0,0,.8)'; ctx.lineWidth = 3;
      const txt = gap === 0 ? 'เสมอ' : (win ? `ชนะ +${gap} แต้ม` : `แพ้ -${gap} แต้ม`);
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
    const c = this.foeFlash > 0 ? col.hi : col.c;
    const x = 258 + (this.foeShake ? Math.random() * 6 - 3 : 0), y = GROUND_Y - 44, s = 3;
    const R = (dx, dy, w, h, cc) => { ctx.fillStyle = cc; ctx.fillRect(x + dx * s, y + dy * s, w * s, h * s); };

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
    } else if (f.k === 'aura') {
      ctx.strokeStyle = `rgba(232,176,75,${1 - p})`; ctx.lineWidth = 2;
      ctx.beginPath(); ctx.ellipse(this.heroX + 20, GROUND_Y - 8, 8 + p * 34, 4 + p * 13, 0, 0, 7); ctx.stroke();
      ctx.beginPath(); ctx.ellipse(this.heroX + 20, GROUND_Y - 26, 6 + p * 26, 3 + p * 10, 0, 0, 7); ctx.stroke();
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
      drawCharacter(ctx, Math.round(this.heroX + this.heroLunge), GROUND_Y - 68 + bob, 3,
                    { ...this.char, pose }, this.heroAlpha);
    }

    this._drawFoe();

    for (let i = this.fx.length - 1; i >= 0; i--) {
      const f = this.fx[i]; f.t++;
      const p = f.t / f.dur;
      if (p >= 1) { this.fx.splice(i, 1); continue; }
      this._drawFx(f, p);
    }

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
