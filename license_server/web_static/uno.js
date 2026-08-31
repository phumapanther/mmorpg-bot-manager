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

/** จุดกลางของสองกอง — กองจั่วซ้าย กองทิ้งขวา เหมือนโต๊ะจริง */
function unoPilePos(cv) {
  return { deck: { x: cv.width / 2 - 80, y: cv.height / 2 - 20 },
           pile: { x: cv.width / 2 + 80, y: cv.height / 2 - 20 } };
}

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
    const t = unoPilePos(cv).pile;
    UNO_CARDS.push({ card: UNO.top, x: t.x, y: t.y, rot: 0,
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

/** ตอนนี้ทำอะไรไม่ได้นอกจากจั่วไหม — ใช้ตัดสินว่าจะเรืองขอบกองจั่วไหม */
function unoMustDraw() {
  if (!UNO || !UNO.playing || !UNO.my_turn) return false;
  if (UNO.winner !== null && UNO.winner !== undefined) return false;
  if (UNO.must_answer) return false;      // โดนสแตค — มีปุ่ม "ยอมจั่ว" แยกต่างหาก
  if (UNO.drew) return false;             // จั่วไปแล้วรอบนี้
  return !(UNO.playable || []).length;    // ไม่มีไพ่ลงได้สักใบ
}

/** จุดที่กดอยู่โดนกองจั่วไหม */
function unoOnDeck(p, cv) {
  const d = unoPilePos(cv).deck;
  return Math.abs(p.x - d.x) <= UNO_CW / 2 + 8 && Math.abs(p.y - d.y) <= UNO_CH / 2 + 8;
}

function unoNearPile(c, cv) {
  const t = unoPilePos(cv).pile;
  return Math.hypot(c.x - t.x, c.y - t.y) < 150;
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

  const pos = unoPilePos(cv);

  // ที่วางกองทิ้ง — เรืองแสงตอนลากเข้ามาใกล้
  const armed = UNO_DRAG && unoNearPile(UNO_DRAG.c, cv);
  ctx.save(); ctx.setLineDash([5, 5]);
  ctx.globalAlpha = armed ? .95 : .30;
  ctx.strokeStyle = armed ? '#e8b04b' : '#a99274';
  ctx.lineWidth = armed ? 2.5 : 1.5;
  const pd = armed ? 5 : 0;
  unoRR(ctx, pos.pile.x - UNO_CW / 2 - pd, pos.pile.y - UNO_CH / 2 - pd,
        UNO_CW + pd * 2, UNO_CH + pd * 2, 9);
  ctx.stroke(); ctx.restore();

  // 🂠 กองจั่วบนโต๊ะ — กดตรงนี้จั่วได้เลย ไม่ต้องหาปุ่มข้างล่าง
  if (UNO && UNO.playing) {
    const hot = unoMustDraw();          // ทำอะไรไม่ได้นอกจากจั่ว = ขอบเหลืองบอก
    ctx.save();
    ctx.translate(pos.deck.x, pos.deck.y);
    if (hot) {                          // เรืองเตือนก่อน แล้วค่อยวาดกองทับ
      ctx.save();
      ctx.shadowColor = '#e8b04b';
      ctx.shadowBlur = 18 + Math.sin(UNO_PULSE) * 9;
      ctx.strokeStyle = '#e8b04b'; ctx.lineWidth = 3;
      unoRR(ctx, -UNO_CW / 2, -UNO_CH / 2, UNO_CW, UNO_CH, 9);
      ctx.stroke(); ctx.stroke();
      ctx.restore();
    }
    // ซ้อนหลายใบให้ดูเป็นกอง — หนาตามจำนวนที่เหลือจริง
    const layers = Math.max(1, Math.min(4, Math.ceil((UNO.deck_left || 0) / 12)));
    for (let k = layers - 1; k >= 0; k--) {
      ctx.save();
      ctx.translate(k * 2, k * -2);
      ctx.fillStyle = '#2a211a';
      ctx.shadowColor = 'rgba(0,0,0,.5)'; ctx.shadowBlur = 10; ctx.shadowOffsetY = 4;
      unoRR(ctx, -UNO_CW / 2, -UNO_CH / 2, UNO_CW, UNO_CH, 9); ctx.fill();
      ctx.shadowBlur = 0; ctx.shadowOffsetY = 0;
      ctx.strokeStyle = '#e8b04b'; ctx.lineWidth = 1.5;
      unoRR(ctx, -UNO_CW / 2 + 6, -UNO_CH / 2 + 6, UNO_CW - 12, UNO_CH - 12, 6);
      ctx.stroke();
      if (k === 0) {
        ctx.fillStyle = '#e8b04b'; ctx.globalAlpha = .82;
        ctx.font = '26px system-ui'; ctx.textAlign = 'center'; ctx.textBaseline = 'middle';
        ctx.fillText('\u{1F702}', 0, 0);
        ctx.globalAlpha = 1;
      }
      ctx.restore();
    }
    ctx.fillStyle = hot ? '#e8b04b' : '#a99274';
    ctx.font = '600 12px Bahnschrift, DIN Alternate, system-ui';
    ctx.textAlign = 'center';
    ctx.fillText(hot ? 'กดเพื่อจั่ว' : `${UNO.deck_left} ใบ`, 0, UNO_CH / 2 + 18);
    ctx.restore();
  }

  // สีที่ใช้อยู่
  if (UNO && UNO.suit && UNO_COLOR[UNO.suit]) {
    ctx.save(); ctx.globalAlpha = .5;
    ctx.fillStyle = UNO_COLOR[UNO.suit].c;
    ctx.beginPath(); ctx.arc(pos.pile.x, pos.pile.y - 90, 15, 0, Math.PI * 2); ctx.fill();
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

  unoDrawFanfare(ctx, W, H);     // ทับทุกอย่าง — เป็นประกาศชั้นบนสุด
  UNO_LOOP = requestAnimationFrame(unoFrame);
}

async function unoDo(action, extra) {
  try {
    const d = await api('POST', '/api/web/uno', { action, ...(extra || {}) });
    unoApply(d.table);
    return d;
  } catch (e) { toast(e.message, true); return null; }
}

// 🏁 อนิเมชันตอนมีคนเข้าเส้นชัย — อลังตามอันดับตามที่เจ้าของเกมสั่ง
//    ที่ 1 อลังสุด · ที่ 2-3 มีแต่ไม่เด่นเท่า · ที่เหลือไม่มี
const UNO_TROPHY = { 1: '🏆', 2: '🥈', 3: '🥉' };
const UNO_PLACE_MS = { 1: 190, 2: 120, 3: 100 };     // ค้างนานแค่ไหน (เฟรมมาตรฐาน)
let UNO_FANFARE = null;     // {name, place, t, dur} กำลังฉลองอยู่
let UNO_SEEN_PLACE = 0;     // ฉลองอันดับไหนไปแล้ว (กันฉลองซ้ำตอนโหลดสถานะซ้ำ)

/** มีใครเพิ่งเข้าเส้นชัยไหม — มีก็เปิดฉากฉลอง */
function unoCheckFanfare() {
  const done = (UNO && UNO.finished) || [];
  if (done.length <= UNO_SEEN_PLACE) return;
  const fresh = done[UNO_SEEN_PLACE];        // คนที่เพิ่งเข้าเส้นชัย
  UNO_SEEN_PLACE = done.length;
  if (fresh.place > 3) return;               // ที่ 4 เป็นต้นไป ไม่มีอนิเมชัน
  UNO_FANFARE = { ...fresh, t: 0, dur: UNO_PLACE_MS[fresh.place] };
  const cv = document.getElementById('unoCanvas');
  if (!cv) return;
  // ที่ 1 สาดกระดาษเต็มจอ · ที่ 2-3 น้อยกว่าตามลำดับ
  const bursts = fresh.place === 1 ? 90 : fresh.place === 2 ? 40 : 24;
  const cols = fresh.place === 1
    ? ['#e8b04b', '#f2e7d8', '#d4553a', '#5f9455', '#4a86a8']
    : ['#e8b04b', '#a99274'];
  for (let k = 0; k < bursts; k++) {
    unoBurst(cv.width * (.2 + Math.random() * .6), cv.height * (.25 + Math.random() * .3),
             cols[k % cols.length], 1);
  }
  SFX.play(fresh.place === 1 ? 'win' : 'click');
}

/** วาดแผงประกาศอันดับ — จางเข้าจางออกเอง ไม่ค้างจอ */
function unoDrawFanfare(ctx, W, H) {
  if (!UNO_FANFARE) return;
  const f = UNO_FANFARE;
  f.t += UNO_DT;
  if (f.t >= f.dur) { UNO_FANFARE = null; return; }
  const k = f.t / f.dur;
  const fade = Math.min(1, k * 6) * Math.min(1, (1 - k) * 6);   // จางเข้า/ออกสั้น ๆ
  const big = f.place === 1;
  ctx.save();
  ctx.globalAlpha = fade * (big ? .82 : .62);
  ctx.fillStyle = '#17110d';
  ctx.fillRect(0, H * (big ? .28 : .34), W, big ? 150 : 96);
  ctx.globalAlpha = fade;
  ctx.textAlign = 'center'; ctx.textBaseline = 'middle';
  const cy = H * (big ? .28 : .34) + (big ? 75 : 48);
  const pop = 1 + Math.sin(Math.min(1, k * 4) * Math.PI / 2) * (big ? .18 : .07);
  ctx.save();
  ctx.translate(W / 2, cy); ctx.scale(pop, pop);
  ctx.font = big ? '54px system-ui' : '34px system-ui';
  ctx.fillText(UNO_TROPHY[f.place] || '🏅', 0, big ? -26 : -16);
  ctx.fillStyle = big ? '#e8b04b' : '#f2e7d8';
  ctx.font = big ? '600 30px Bahnschrift, DIN Alternate, system-ui'
                 : '600 19px Bahnschrift, DIN Alternate, system-ui';
  ctx.fillText(f.name, 0, big ? 18 : 12);
  ctx.fillStyle = '#a99274';
  ctx.font = big ? '600 16px system-ui' : '13px system-ui';
  ctx.fillText(big ? 'ชนะ! — อันดับ 1' : `อันดับ ${f.place}`, 0, big ? 46 : 32);
  ctx.restore();
  ctx.restore();
}

/** 🎴 ไพ่บินจากกองจั่วเข้ามือ — เรียกหลังรู้ว่าจั่วได้กี่ใบ */
function unoFlyDraw(count) {
  const cv = document.getElementById('unoCanvas');
  if (!cv || !count) return;
  const d = unoPilePos(cv).deck;
  const n = (UNO.hand || []).length;
  for (let k = 0; k < count; k++) {
    const i = n - count + k;
    if (i < 0) continue;
    const c = UNO_CARDS.find(x => x.slot === i);
    if (!c) continue;
    c.anim = 'arc'; c.t = 0; c.dur = 20;
    c.from = { x: d.x, y: d.y, rot: 0, face: 0 };
    c.to = { x: c.x, y: c.y, rot: c.rot, face: 1 };
    c.x = d.x; c.y = d.y; c.face = 0;      // เริ่มที่กอง คว่ำหน้าลง
  }
  unoBurst(d.x, d.y, '#e8b04b', 10);
}

function unoApply(table, drew) {
  const before = ((UNO || {}).hand || []).length;
  UNO = table || { playing: false };
  unoLayout();
  // ไพ่ในมือเพิ่มขึ้น = เพิ่งจั่วมา ให้มันบินออกจากกองจริง ๆ
  const gained = ((UNO || {}).hand || []).length - before;
  if (gained > 0 && before) unoFlyDraw(gained);
  unoCheckFanfare();
  unoPaint();
  if (!UNO_LOOP) UNO_LOOP = requestAnimationFrame(unoFrame);
}

/** สรุปอันดับทั้งโต๊ะตอนจบเกม */
function unoPlaceText() {
  return ((UNO && UNO.finished) || [])
    .map(f => `${f.place}. ${f.name}${f.you ? ' (คุณ)' : ''}`).join(' · ');
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
  // 🔧 กล่องเลือกสีจะโชว์ก็ต่อเมื่อมีไพ่รอเลือกสีจริง — นอกนั้นซ่อนเสมอ
  //    เคยพลาด: ซ่อนแค่ตอนไม่มีโต๊ะ กดเลือกสีแล้วปุ่มค้างคาหน้าจอตลอด
  show('unoSuits', UNO_PICK !== null);
  const me = (UNO.players || []).find(p => p.you) || { cards: 0 };
  if (hud) hud.textContent = `กองจั่ว ${UNO.deck_left} ใบ · ${UNO.dir > 0 ? '↻' : '↺'}`;
  const over = !!UNO.over;
  const mine = UNO.my_place || 0;
  if (msg) {
    msg.textContent = over
      ? `🏁 จบเกม — ${unoPlaceText()}`
      : mine ? `🏅 คุณเข้าเส้นชัยอันดับ ${mine} — นั่งดูจนจบเกม`
      : UNO.must_answer ? `⚠️ โดน ${UNO.stack} ใบจ่ออยู่ — วางต่อหรือยอมจั่ว`
      : UNO.my_turn ? 'ตาคุณ — ลากไพ่ไปวางที่กองกลาง' : 'รอคู่แข่ง...';
  }
  const playing = UNO.my_turn && !over && !mine;      // ทิ้งไพ่หมดแล้วกดอะไรไม่ได้อีก
  show('unoDraw', playing && !UNO.must_answer && !UNO.drew);
  show('unoTake', playing && UNO.must_answer);
  show('unoPass', playing && UNO.drew);
  show('unoSayUno', me.cards === 1 && !me.said_uno && !over && !mine);
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
      const pick = UNO_PICK;
      UNO_PICK = null;              // ล้างก่อน — unoPaint จะซ่อนกล่องให้เอง
      box.hidden = true;            // ซ่อนทันทีด้วย ไม่ต้องรอคำตอบจากเซิร์ฟเวอร์
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
    const p = unoAt(e, cv);
    // 📥 กดกองจั่วบนโต๊ะ = จั่วเลย ไม่ต้องเลื่อนไปหาปุ่มข้างล่าง
    if (unoOnDeck(p, cv)) {
      e.preventDefault();
      SFX.play('click');
      if (UNO.must_answer) unoDo('take');     // โดนสแตคอยู่ = ยอมจั่วทั้งกอง
      else if (!UNO.drew) unoDo('draw');
      return;
    }
    const c = unoHit(p);
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
    const t = unoPilePos(cv).pile;
    unoBurst(t.x, t.y + 22, '#c8b48e', 16);
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
