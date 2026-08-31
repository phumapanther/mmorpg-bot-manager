// 🎴 ศึกไพ่รูน — หน้าโต๊ะไพ่
//
// 🔒 กติกาเหล็กเดียวกับสนามรบผลัดเทิร์น: เบราว์เซอร์ส่งไปแค่ "กดอะไร"
//    กฎทั้งหมดตัดสินที่เซิร์ฟเวอร์ · ไพ่ในมือคนอื่นไม่เคยถูกส่งลงมา
//    (uno_table.view คัดออกให้แล้ว ที่นี่จึงวาดหลังไพ่ตามจำนวนที่บอกมาเท่านั้น)
//
// อนิเมชันยกมาจากม็อคอัพที่เจ้าของเกมอนุมัติแล้ว (docs/mockups/card-table.html)
// พลิกไพ่ = ctx.scale(cos) · แจกไพ่ = เส้นโค้ง + easing · นาฬิกา DT เดินตามเวลาจริง

const UNO_CW = 76, UNO_CH = 108;
const UNO_COLOR = {
  fire:  { c: '#d4553a', d: '#8f3021', ico: '🔥' },
  water: { c: '#4a86a8', d: '#2c5670', ico: '💧' },
  wood:  { c: '#5f9455', d: '#3a5f34', ico: '🌿' },
  light: { c: '#e8b04b', d: '#a2742a', ico: '☀️' },
};
const UNO_FACE = { skip: '🛡️', reverse: '🌀', draw2: '⚔️', wild: '🔮', wild4: '🌑' };

let UNO = null;              // สถานะล่าสุดจากเซิร์ฟเวอร์
let UNO_CARDS = [];          // ไพ่ที่กำลังวาดอยู่บนจอ
let UNO_BITS = [];           // อนุภาค
let UNO_LOOP = 0, UNO_DT = 1, UNO_LAST = 0;
let UNO_DRAG = null, UNO_HOVER = null;
let UNO_PICK = null;         // ไพ่ที่รอเลือกสี (ไวลด์)
let UNO_PULSE = 0;           // จังหวะเต้นของขอบเรืองแสง

const unoEase = t => 1 - Math.pow(1 - t, 3);
const unoEaseIO = t => t < .5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2;

function unoClock(now) {
  const gap = UNO_LAST ? now - UNO_LAST : 16.7;
  UNO_LAST = now;
  UNO_DT = Math.max(0.2, Math.min(3, gap * 60 / 1000));   // เท่ากันทุกจอ 60/144 Hz
}

function unoRR(ctx, x, y, w, h, r) {
  ctx.beginPath();
  if (ctx.roundRect) ctx.roundRect(x, y, w, h, r);
  else { ctx.moveTo(x + r, y); ctx.arcTo(x + w, y, x + w, y + h, r);
         ctx.arcTo(x + w, y + h, x, y + h, r); ctx.arcTo(x, y + h, x, y, r);
         ctx.arcTo(x, y, x + w, y, r); ctx.closePath(); }
}

function unoDrawCard(ctx, c) {
  const flat = Math.abs(Math.cos(c.face * Math.PI));
  const showFace = Math.cos(c.face * Math.PI) <= 0;
  ctx.save();
  ctx.translate(c.x + (c.jx || 0), c.y + (c.jy || 0) - (c.lift || 0) * 20);
  ctx.rotate(c.rot);
  ctx.scale(Math.max(.02, flat) * (c.sc || 1), c.sc || 1);
  // ✨ ไพ่ที่ลงได้ = ขอบทองเรืองแสง เต้นช้า ๆ ให้สังเกตง่ายโดยไม่รบกวนสายตา
  //    วาดก่อนตัวไพ่ เพราะเงาเรืองต้องอยู่ "ใต้" ใบไพ่ ไม่ใช่ทับหน้าไพ่
  if (c.glow) {
    ctx.save();
    ctx.shadowColor = '#e8b04b';
    ctx.shadowBlur = 16 + Math.sin(UNO_PULSE) * 8;
    ctx.strokeStyle = '#e8b04b';
    ctx.lineWidth = 3;
    unoRR(ctx, -UNO_CW / 2, -UNO_CH / 2, UNO_CW, UNO_CH, 9);
    ctx.stroke(); ctx.stroke();       // ซ้ำสองครั้งให้แสงเข้มพอเห็นชัด
    ctx.restore();
  }
  ctx.shadowColor = 'rgba(0,0,0,.5)'; ctx.shadowBlur = 14; ctx.shadowOffsetY = 6;
  ctx.fillStyle = showFace ? '#f2e7d8' : '#2a211a';
  unoRR(ctx, -UNO_CW / 2, -UNO_CH / 2, UNO_CW, UNO_CH, 9); ctx.fill();
  ctx.shadowBlur = 0; ctx.shadowOffsetY = 0;

  if (showFace && c.card) {
    const s = UNO_COLOR[c.card.suit] || { c: '#6b5b8a', d: '#3d3352', ico: '🔮' };
    const g = ctx.createLinearGradient(0, -UNO_CH / 2, 0, UNO_CH / 2);
    g.addColorStop(0, s.c); g.addColorStop(1, s.d);
    ctx.fillStyle = g;
    unoRR(ctx, -UNO_CW / 2 + 5, -UNO_CH / 2 + 5, UNO_CW - 10, UNO_CH - 10, 6); ctx.fill();
    if (c.dim) { ctx.fillStyle = 'rgba(23,17,13,.55)';
                 unoRR(ctx, -UNO_CW / 2 + 5, -UNO_CH / 2 + 5, UNO_CW - 10, UNO_CH - 10, 6);
                 ctx.fill(); }
    ctx.fillStyle = 'rgba(255,255,255,.94)';
    ctx.textAlign = 'center'; ctx.textBaseline = 'middle';
    const v = c.card.value;
    if (typeof v === 'number') {
      ctx.font = '600 30px Bahnschrift, DIN Alternate, system-ui';
      ctx.fillText(v, 0, 2);
    } else {
      ctx.font = '27px system-ui';
      ctx.fillText(UNO_FACE[v] || '?', 0, 2);
    }
    ctx.font = '14px system-ui';
    ctx.fillText(s.ico, 0, UNO_CH / 2 - 18);
    ctx.textAlign = 'left';
    ctx.fillText(s.ico, -UNO_CW / 2 + 8, -UNO_CH / 2 + 16);
  } else if (!showFace) {
    ctx.strokeStyle = '#e8b04b'; ctx.lineWidth = 1.5;
    unoRR(ctx, -UNO_CW / 2 + 6, -UNO_CH / 2 + 6, UNO_CW - 12, UNO_CH - 12, 6); ctx.stroke();
    ctx.fillStyle = '#e8b04b'; ctx.globalAlpha = .82;
    ctx.font = '26px system-ui'; ctx.textAlign = 'center'; ctx.textBaseline = 'middle';
    ctx.fillText('\u{1F702}', 0, 0);
    ctx.globalAlpha = 1;
  }
  ctx.restore();
}

function unoFan(i, n, W, H) {
  const spread = Math.min(.15, 1.0 / Math.max(1, n)), a = (i - (n - 1) / 2) * spread;
  return { x: W / 2 + Math.sin(a) * 260, y: H - 96 + (1 - Math.cos(a)) * 240, rot: a };
}

function unoBurst(x, y, col, n) {
  for (let i = 0; i < n; i++) {
    const a = Math.random() * Math.PI * 2, sp = 1.4 + Math.random() * 3.4;
    UNO_BITS.push({ x, y, vx: Math.cos(a) * sp, vy: Math.sin(a) * sp - 1,
                    life: 1, col, r: 1.6 + Math.random() * 2.4 });
  }
}

/** สร้างไพ่บนจอจากสถานะที่เซิร์ฟเวอร์ส่งมา */
function unoLayout() {
  const cv = document.getElementById('unoCanvas');
  if (!cv || !UNO || !UNO.playing) { UNO_CARDS = []; return; }
  const W = cv.width, H = cv.height;
  const hand = UNO.hand || [];
  const keep = {};
  UNO_CARDS.filter(c => c.slot !== undefined).forEach(c => { keep[c.slot] = c; });

  UNO_CARDS = [];
  // กองทิ้ง
  if (UNO.top) {
    UNO_CARDS.push({ card: UNO.top, x: W / 2 + 80, y: H / 2 - 20, rot: 0,
                     face: 1, sc: 1, pile: true });
  }
  // ไพ่ในมือเรา
  hand.forEach((card, i) => {
    const f = unoFan(i, hand.length, W, H);
    const old = keep[i];
    const can = (UNO.playable || []).includes(i);
    const dim = UNO.my_turn && !can;
    const glow = UNO.my_turn && can;        // ✨ ลงได้ = ขอบทองเรืองแสง
    UNO_CARDS.push(old && old.anim
      ? Object.assign(old, { card, dim, glow, slot: i })
      : { card, x: f.x, y: f.y, rot: f.rot, face: 1, sc: 1, slot: i, dim, glow,
          home: { x: f.x, y: f.y, rot: f.rot } });
  });
}

function unoHit(p) {
  for (let i = UNO_CARDS.length - 1; i >= 0; i--) {
    const c = UNO_CARDS[i];
    if (c.slot === undefined) continue;
    const dx = p.x - c.x, dy = p.y - c.y;
    const co = Math.cos(-c.rot), si = Math.sin(-c.rot);
    if (Math.abs(dx * co - dy * si) <= UNO_CW / 2 &&
        Math.abs(dx * si + dy * co) <= UNO_CH / 2) return c;
  }
  return null;
}

function unoAt(e, cv) {
  const r = cv.getBoundingClientRect(), t = e.touches ? e.touches[0] : e;
  return { x: (t.clientX - r.left) * cv.width / r.width,
           y: (t.clientY - r.top) * cv.height / r.height };
}

function unoNearPile(c, cv) {
  return Math.hypot(c.x - (cv.width / 2 + 80), c.y - (cv.height / 2 - 20)) < 150;
}

function unoFrame(now) {
  const cv = document.getElementById('unoCanvas');
  if (!cv) { UNO_LOOP = 0; return; }
  const ctx = cv.getContext('2d'), W = cv.width, H = cv.height;
  unoClock(now);
  UNO_PULSE += 0.07 * UNO_DT;      // เดินตามเวลาจริง จอเร็วจอช้าเต้นเท่ากัน
  ctx.fillStyle = '#1f1813'; ctx.fillRect(0, 0, W, H);

  // โต๊ะ
  const tg = ctx.createRadialGradient(W / 2, H / 2, 30, W / 2, H / 2, 430);
  tg.addColorStop(0, '#3c2f22'); tg.addColorStop(1, '#241b14');
  ctx.fillStyle = tg;
  ctx.beginPath(); ctx.ellipse(W / 2, H / 2, 400, 215, 0, 0, Math.PI * 2); ctx.fill();
  ctx.strokeStyle = '#453528'; ctx.lineWidth = 2; ctx.stroke();

  // ที่วางกอง — เรืองแสงตอนลากเข้ามาใกล้
  const armed = UNO_DRAG && unoNearPile(UNO_DRAG.c, cv);
  ctx.save(); ctx.setLineDash([5, 5]);
  ctx.globalAlpha = armed ? .95 : .30;
  ctx.strokeStyle = armed ? '#e8b04b' : '#a99274';
  ctx.lineWidth = armed ? 2.5 : 1.5;
  const pd = armed ? 5 : 0;
  unoRR(ctx, W / 2 + 80 - UNO_CW / 2 - pd, H / 2 - 20 - UNO_CH / 2 - pd,
        UNO_CW + pd * 2, UNO_CH + pd * 2, 9);
  ctx.stroke(); ctx.restore();

  // สีที่ใช้อยู่
  if (UNO && UNO.suit && UNO_COLOR[UNO.suit]) {
    ctx.save(); ctx.globalAlpha = .5;
    ctx.fillStyle = UNO_COLOR[UNO.suit].c;
    ctx.beginPath(); ctx.arc(W / 2 + 80, H / 2 - 110, 15, 0, Math.PI * 2); ctx.fill();
    ctx.restore();
  }

  // คู่แข่ง — วาดหลังไพ่ตามจำนวนที่เซิร์ฟเวอร์บอก (ไม่รู้ว่าเป็นไพ่อะไร)
  if (UNO && UNO.playing) {
    const foes = (UNO.players || []).filter(p => !p.you);
    foes.forEach((p, k) => {
      const x = W / 2 + (k - (foes.length - 1) / 2) * 220, y = 76;
      ctx.save();
      ctx.fillStyle = UNO.turn === (UNO.players || []).indexOf(p) ? '#e8b04b' : '#a99274';
      ctx.font = '600 14px system-ui'; ctx.textAlign = 'center';
      ctx.fillText(`${p.name} · ${p.cards} ใบ`, x, y - 42);
      for (let i = 0; i < Math.min(p.cards, 8); i++) {
        ctx.save();
        ctx.translate(x + (i - Math.min(p.cards, 8) / 2) * 15, y);
        ctx.scale(.42, .42);
        ctx.fillStyle = '#2a211a';
        unoRR(ctx, -UNO_CW / 2, -UNO_CH / 2, UNO_CW, UNO_CH, 9); ctx.fill();
        ctx.strokeStyle = '#e8b04b'; ctx.lineWidth = 3;
        unoRR(ctx, -UNO_CW / 2 + 6, -UNO_CH / 2 + 6, UNO_CW - 12, UNO_CH - 12, 6);
        ctx.stroke();
        ctx.restore();
      }
      ctx.restore();
    });
  }

  UNO_CARDS.forEach(c => {
    if (c.anim) {
      c.t = Math.min(c.dur, c.t + UNO_DT);
      const k = c.t / c.dur, e = c.anim === 'flip' ? unoEaseIO(k) : unoEase(k);
      c.x = c.from.x + (c.to.x - c.from.x) * e;
      c.y = c.from.y + (c.to.y - c.from.y) * e;
      c.rot = c.from.rot + (c.to.rot - c.from.rot) * e;
      if (c.anim === 'arc') c.y -= Math.sin(k * Math.PI) * 60;
      if (c.t >= c.dur) c.anim = null;
    }
    const want = (UNO_DRAG && UNO_DRAG.c === c) ? 1 : (!UNO_DRAG && UNO_HOVER === c ? .45 : 0);
    c.lift = (c.lift || 0) + (want - (c.lift || 0)) * Math.min(1, .22 * UNO_DT);
    unoDrawCard(ctx, c);
  });

  UNO_BITS = UNO_BITS.filter(b => {
    b.x += b.vx * UNO_DT; b.y += b.vy * UNO_DT; b.vy += .13 * UNO_DT;
    b.life -= .022 * UNO_DT;
    if (b.life <= 0) return false;
    ctx.globalAlpha = Math.max(0, b.life); ctx.fillStyle = b.col;
    ctx.beginPath(); ctx.arc(b.x, b.y, b.r, 0, Math.PI * 2); ctx.fill();
    ctx.globalAlpha = 1;
    return true;
  });

  UNO_LOOP = requestAnimationFrame(unoFrame);
}

async function unoDo(action, extra) {
  try {
    const d = await api('POST', '/api/web/uno', { action, ...(extra || {}) });
    unoApply(d.table);
    return d;
  } catch (e) { toast(e.message, true); return null; }
}

function unoApply(table) {
  UNO = table || { playing: false };
  unoLayout();
  unoPaint();
  if (!UNO_LOOP) UNO_LOOP = requestAnimationFrame(unoFrame);
}

function unoPaint() {
  const msg = document.getElementById('unoMsg');
  const hud = document.getElementById('unoHud');
  const log = document.getElementById('unoLog');
  const show = (id, on) => { const el = document.getElementById(id); if (el) el.hidden = !on; };
  if (!UNO || !UNO.playing) {
    if (msg) msg.textContent = 'กดเปิดโต๊ะเพื่อเริ่มเล่น';
    if (hud) hud.textContent = '';
    if (log) log.innerHTML = '';
    ['unoDraw', 'unoTake', 'unoPass', 'unoSayUno'].forEach(id => show(id, false));
    show('unoSuits', false);
    return;
  }
  const me = (UNO.players || []).find(p => p.you) || { cards: 0 };
  if (hud) hud.textContent = `กองจั่ว ${UNO.deck_left} ใบ · ${UNO.dir > 0 ? '↻' : '↺'}`;
  if (msg) {
    msg.textContent = UNO.winner !== null && UNO.winner !== undefined
      ? `🎉 ${UNO.winner_name} ชนะ! (แต้ม ${UNO.score})`
      : UNO.must_answer ? `⚠️ โดน ${UNO.stack} ใบจ่ออยู่ — วางต่อหรือยอมจั่ว`
      : UNO.my_turn ? 'ตาคุณ — ลากไพ่ไปวางที่กองกลาง' : 'รอคู่แข่ง...';
  }
  const over = UNO.winner !== null && UNO.winner !== undefined;
  show('unoDraw', UNO.my_turn && !over && !UNO.must_answer && !UNO.drew);
  show('unoTake', UNO.my_turn && !over && UNO.must_answer);
  show('unoPass', UNO.my_turn && !over && UNO.drew);
  show('unoSayUno', me.cards === 1 && !me.said_uno && !over);
  if (log) log.innerHTML = (UNO.log || []).map(l =>
    `<div>${l.replace(/</g, '&lt;')}</div>`).join('');
}

/** ไวลด์ต้องเลือกสีก่อนวาง — โชว์ปุ่มสีแล้วรอกด */
function unoAskSuit(slot) {
  UNO_PICK = slot;
  const box = document.getElementById('unoSuits');
  if (!box) return;
  box.hidden = false;
  box.innerHTML = Object.entries(UNO.suits || {}).map(([k, label]) =>
    `<button data-suit="${k}">${label}</button>`).join('');
  box.querySelectorAll('[data-suit]').forEach(b => {
    b.onclick = async () => {
      box.hidden = true;
      const pick = UNO_PICK; UNO_PICK = null;
      await unoDo('play', { index: pick, suit: b.dataset.suit });
    };
  });
}

function unoBind() {
  const cv = document.getElementById('unoCanvas');
  if (!cv || cv.dataset.bound) return;
  cv.dataset.bound = '1';

  const down = e => {
    if (!UNO || !UNO.my_turn) return;
    const c = unoHit(unoAt(e, cv));
    if (!c || c.dim) return;
    UNO_DRAG = { c, ox: c.x - unoAt(e, cv).x, oy: c.y - unoAt(e, cv).y };
    e.preventDefault();
  };
  const move = e => {
    const p = unoAt(e, cv);
    if (!UNO_DRAG) { UNO_HOVER = unoHit(p); return; }
    UNO_DRAG.c.x = p.x + UNO_DRAG.ox;
    UNO_DRAG.c.y = p.y + UNO_DRAG.oy;
    UNO_DRAG.c.rot += (0 - UNO_DRAG.c.rot) * .2;
    e.preventDefault();
  };
  const up = async () => {
    if (!UNO_DRAG) return;
    const c = UNO_DRAG.c; UNO_DRAG = null;
    if (!unoNearPile(c, cv)) {                 // ลากไม่ถึง = เด้งกลับ
      c.anim = 'move'; c.t = 0; c.dur = 18;
      c.from = { x: c.x, y: c.y, rot: c.rot }; c.to = { ...c.home };
      return;
    }
    unoBurst(cv.width / 2 + 80, cv.height / 2 + 2, '#c8b48e', 16);
    const card = c.card;
    if (card && (card.value === 'wild' || card.value === 'wild4')) {
      unoAskSuit(c.slot);                      // ไวลด์ต้องเลือกสีก่อน
      return;
    }
    await unoDo('play', { index: c.slot });
  };
  cv.addEventListener('mousedown', down);
  cv.addEventListener('mousemove', move);
  addEventListener('mouseup', up);
  cv.addEventListener('touchstart', down, { passive: false });
  cv.addEventListener('touchmove', move, { passive: false });
  addEventListener('touchend', up);
}

document.getElementById('unoStart')?.addEventListener('click', async () => {
  SFX.play('click'); unoBind(); await unoDo('start', { bots: 1 });
});
document.getElementById('unoDraw')?.addEventListener('click', () => {
  SFX.play('click'); unoDo('draw');
});
document.getElementById('unoTake')?.addEventListener('click', () => {
  SFX.play('click'); unoDo('take');
});
document.getElementById('unoPass')?.addEventListener('click', () => {
  SFX.play('click'); unoDo('pass');
});
document.getElementById('unoSayUno')?.addEventListener('click', () => {
  SFX.play('click'); unoDo('uno');
});

// ❓ คู่มือไพ่ — เปิดค้างไว้ก็เล่นต่อได้ ไม่บังคับให้ปิดก่อน
function unoHelp(on) {
  const box = document.getElementById('unoHelp');
  if (box) box.hidden = !on;
}
document.getElementById('unoHelpBtn')?.addEventListener('click', () => {
  SFX.play('click'); unoHelp(true);
});
document.getElementById('unoHelpClose')?.addEventListener('click', () => {
  SFX.play('click'); unoHelp(false);
});
// กด Esc ก็ปิดได้ — คนที่ชินคีย์บอร์ดจะหาปุ่มกากบาทไม่เจอ
addEventListener('keydown', e => {
  if (e.key === 'Escape') unoHelp(false);
});

/** เปิดหน้ามาเจอโต๊ะที่ค้างไว้ */
async function fillUno() {
  unoBind();
  try { unoApply((await api('GET', '/api/web/uno')).table); }
  catch (e) { /* ยังไม่ได้ล็อกอินหรือเน็ตสะดุด — ไม่ต้องรบกวน */ }
}
