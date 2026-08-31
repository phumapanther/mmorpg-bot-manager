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
// เหรียญอันดับ — ต้องอยู่บนสุดกับค่าคงที่ตัวอื่น
// ⚠️ const ใช้ก่อนบรรทัดที่ประกาศไม่ได้ (temporal dead zone)
//    เคยอยู่กลางไฟล์ แต่โค้ดวาดที่นั่งเรียกก่อน → ReferenceError ทุกเฟรม
//    ลูปวาดตายคาที่ หน้าจอจึงค้างหมด (เจ้าของเกมเจอ 08-29)
const UNO_TROPHY = { 1: '🏆', 2: '🥈', 3: '🥉' };

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
let UNO_SUIT_CARDS = [];     // ไพ่ธาตุ 4 ใบที่ลอยขึ้นให้เลือก
// 🛑 สั่งอะไรไปแล้ว = จบตาเราทันที ไม่รอคำตอบจากเซิร์ฟเวอร์
//    เจ้าของเกมเจอ 08-29: ลงไพ่แล้วยังลงไพ่ต่อได้อีก
//    เพราะระหว่างรอคำตอบ (~หลักร้อย ms) UNO.my_turn ยังเป็น true อยู่
let UNO_SENT = false;        // สั่งไปแล้วรอผลอยู่

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

/** ที่นั่งล้อมวงโต๊ะ — เราอยู่ล่างสุดเสมอ คนอื่นไล่ตามทิศที่เล่น

    วางบนวงรีหนึ่ง เหมือนนั่งล้อมโต๊ะจริง — เราอยู่ที่ 6 นาฬิกา
    คนอื่นไล่ไปตามเข็ม จะได้ตรงกับลำดับเทิร์นจริง
 */
function unoSeats(cv) {
  if (!UNO || !UNO.playing) return [];
  const players = UNO.players || [];
  const n = players.length;
  const me = players.findIndex(p => p.you);
  const done = {};
  ((UNO.finished) || []).forEach(f => { done[f.name] = f.place; });

  return players.map((p, i) => {
    // นับจากเราไป ๆ เราอยู่ล่างสุด (มุม 90°) ที่เหลือไล่ทวนเข็มขึ้นไป
    const k = ((i - (me < 0 ? 0 : me)) + n) % n;
    const a = Math.PI / 2 + (k / n) * Math.PI * 2;
    return {
      index: i,
      name: p.name,
      cards: p.cards,
      you: !!p.you,
      bot: p.name.startsWith('🤖'),
      place: done[p.name] || 0,
      out: !!done[p.name],
      x: cv.width / 2 + Math.cos(a) * (cv.width * .34),
      y: cv.height / 2 + Math.sin(a) * (cv.height * .33),
    };
  }).filter(s => !s.you);        // เรามีไพ่ในมืออยู่แล้ว ไม่ต้องมีเหรียญซ้ำ
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
  // ⚠️ จำไพ่เก่าด้วย "หน้าไพ่" ไม่ใช่เลขช่อง
  //    เคยพลาด: วางไพ่ไปใบหนึ่ง ไพ่ที่เหลือเลื่อนช่อง ช่องเดิมจึงกลายเป็นไพ่คนละใบ
  //    ไพ่ที่กำลังเล่นอนิเมชันอยู่เลยเปลี่ยนธาตุคาตา (เจ้าของเกมเจอ 08-29)
  const keep = {};
  UNO_CARDS.filter(c => c.slot !== undefined && c.card).forEach(c => {
    const key = `${c.card.suit}:${c.card.value}`;
    if (!keep[key]) keep[key] = [];
    keep[key].push(c);
  });

  // ไพ่ที่กำลังบินเข้ากองอยู่ ปล่อยให้บินจนจบ ไม่งั้นหายกลางอากาศ
  const flying = UNO_CARDS.filter(c => c.flying && c.anim);
  UNO_CARDS = flying;
  // กองทิ้ง
  if (UNO.top) {
    const t = unoPilePos(cv).pile;
    UNO_CARDS.push({ card: UNO.top, x: t.x, y: t.y, rot: 0,
                     face: 1, sc: 1, pile: true });
  }
  // ไพ่ในมือเรา
  hand.forEach((card, i) => {
    const f = unoFan(i, hand.length, W, H);
    const pool = keep[`${card.suit}:${card.value}`];
    const old = pool && pool.length ? pool.shift() : null;   // ใบหน้าเหมือนกันมีหลายใบ หยิบทีละใบ
    const mine = unoMyTurn();
    const can = mine && (UNO.playable || []).includes(i);
    // ยังไม่ถึงตา = หรี่ทั้งมือ (เจ้าของเกมสั่ง 08-29)
    // แต่ยังหยิบจัดตำแหน่งไพ่ได้ — แค่ลงกองไม่ได้
    const dim = !mine || !can;
    const glow = mine && can;               // ✨ ลงได้ = ขอบทองเรืองแสง
    if (old && old.anim) {
      // กำลังบินอยู่ — ปล่อยให้บินต่อ แค่ย้ายปลายทางไปช่องใหม่
      old.to = { ...old.to, x: f.x, y: f.y, rot: f.rot };
      Object.assign(old, { card, dim, glow, slot: i,
                           home: { x: f.x, y: f.y, rot: f.rot } });
      UNO_CARDS.push(old);
    } else {
      UNO_CARDS.push({ card, x: f.x, y: f.y, rot: f.rot, face: 1, sc: 1, slot: i,
                       dim, glow, home: { x: f.x, y: f.y, rot: f.rot } });
    }
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

/** ตอนนี้เราสั่งอะไรได้ไหม — ตัวตัดสินตัวเดียวของทั้งหน้า

    ⚠️ ต้องเช็ค UNO_THINK ด้วย — ระหว่างเล่นภาพตาบอท
       UNO ยังเป็นสถานะเก่าที่ my_turn ยัง true อยู่
       ไม่เช็ค = ลงไพ่ทับตาบอทได้ (เจ้าของเกมเจอ 08-29)
       รวมถึงตอนอนิเมชันจั่วไพ่ของเราเองยังเล่นไม่จบ — ยังนับเป็นตาเราอยู่
 */
function unoMyTurn() {
  if (!UNO || !UNO.playing || !UNO.my_turn) return false;
  if (UNO.over || UNO.my_place) return false;
  if (UNO_THINK) return false;              // บอทกำลังคิด/ลงไพ่อยู่
  if (UNO_SENT) return false;               // สั่งไปแล้ว รอผลอยู่
  if (UNO_DEALING) return false;            // กำลังแจกไพ่
  if (unoBusyFx()) return false;            // ไพ่ยังบินอยู่ รอให้สุดก่อน
  return true;
}

/** ยังมีภาพค้างอยู่ไหม — นับจากอนิเมชันจริง ไม่ใช่การเดาเวลา

    ⚠️ เดิมใช้ setTimeout เดาเอาว่าภาพน่าจะจบแล้ว — วัดจริงแล้วไม่ตรง:
       ไพ่บินเข้ากอง 22 เฟรม = ~367 ms แต่โค้ดรอแค่ 220 ms
       เหลือช่องว่าง ~147 ms ที่ไพ่ยังลอยอยู่แต่เป็นตาเราแล้ว
       (เจ้าของเกมสั่ง 08-29: "ถ้าอนิเมชั่นของแต่ละคนยังไม่จบ ยังไม่ถึงเทิร์นเรา")
       ดูของจริงแทน — ไม่ต้องมาไล่ปรับตัวเลขเวลาให้ตรงกันทุกครั้ง
 */
function unoBusyFx() {
  return UNO_CARDS.some(c => c.anim && c.flying);
}

/** ตอนนี้ทำอะไรไม่ได้นอกจากจั่วไหม — ใช้ตัดสินว่าจะเรืองขอบกองจั่วไหม */
function unoMustDraw() {
  if (!unoMyTurn()) return false;
  if (UNO.drew) return false;             // จั่วไปแล้วรอบนี้
  // ไม่มีไพ่ลงได้สักใบ = ต้องจั่ว
  // โดนสแตคแล้วสแตคต่อไม่ได้ = ต้องยอมจั่ว — เรืองเหมือนกัน
  // (เจ้าของเกมสั่ง 08-29: "ไม่ว่าจะยอมจั่วหรือต้องจั่วเอง")
  return !(UNO.playable || []).length;
}

/** จุดที่กดอยู่โดนกองจั่วไหม */
function unoOnDeck(p, cv) {
  const d = unoPilePos(cv).deck;
  return Math.abs(p.x - d.x) <= UNO_CW / 2 + 8 && Math.abs(p.y - d.y) <= UNO_CH / 2 + 8;
}

/** ลากมาถึงจุดที่ถือว่า "จะวาง" แล้วหรือยัง

    เจ้าของเกมเจอ (08-29): "ลากวางบางทีมันไม่ตรงมันไม่ลงเลย"
    เดิมต้องลากเข้าใกล้กองภายใน 150px — บนมือถือเล็งกว่านั้นมาก
    ตอนนี้เอา "ลากพ้นแถวไพ่ในมือขึ้นมา" เป็นเกณฑ์แทน — ลากขึ้นมาก็คือจะวาง
    แล้วค่อยดูดไปที่กองเอง ไม่ต้องเล็งให้ตรง
 */
function unoNearPile(c, cv) {
  const t = unoPilePos(cv).pile;
  if (Math.hypot(c.x - t.x, c.y - t.y) < 190) return true;   // ใกล้กองอยู่แล้ว
  return c.y < cv.height - 150;                              // หรือแค่ยกพ้นแถวไพ่ในมือขึ้นมา
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
    ctx.fillText(hot ? (UNO.must_answer ? `กดเพื่อยอมจั่ว ${UNO.stack} ใบ` : 'กดเพื่อจั่ว')
                     : `${UNO.deck_left} ใบ`, 0, UNO_CH / 2 + 18);
    ctx.restore();
  }

  // สีที่ใช้อยู่
  if (UNO && UNO.suit && UNO_COLOR[UNO.suit]) {
    ctx.save(); ctx.globalAlpha = .5;
    ctx.fillStyle = UNO_COLOR[UNO.suit].c;
    ctx.beginPath(); ctx.arc(pos.pile.x, pos.pile.y - 90, 15, 0, Math.PI * 2); ctx.fill();
    ctx.restore();
  }

  // 👥 ที่นั่งล้อมวงโต๊ะ — คนถึงตาจะมีออร่าเรืองรอบตัว ทีละคนเท่านั้น
  if (UNO && UNO.playing) {
    unoSeats(cv).forEach(s => {
      const turn = (UNO_THINK ? s.index === UNO_THINK.seat
                              : s.index === UNO.turn) && !UNO.over;
      const thinking = UNO_THINK && s.index === UNO_THINK.seat;
      ctx.save();
      ctx.translate(s.x, s.y);

      // ✨ ออร่าโฟกัส — วงแหวนเรืองที่คนกำลังเล่นเท่านั้น
      if (turn) {
        const r = 30 + Math.sin(UNO_PULSE) * 3;
        const gl = ctx.createRadialGradient(0, 0, 6, 0, 0, r + 22);
        gl.addColorStop(0, 'rgba(232,176,75,.42)');
        gl.addColorStop(1, 'rgba(232,176,75,0)');
        ctx.fillStyle = gl;
        ctx.beginPath(); ctx.arc(0, 0, r + 22, 0, Math.PI * 2); ctx.fill();
        ctx.strokeStyle = '#e8b04b'; ctx.lineWidth = 2.5;
        ctx.shadowColor = '#e8b04b'; ctx.shadowBlur = 14 + Math.sin(UNO_PULSE) * 7;
        ctx.beginPath(); ctx.arc(0, 0, r, 0, Math.PI * 2); ctx.stroke();
        ctx.shadowBlur = 0;
      }

      // เหรียญที่นั่ง — คนที่ออกไปแล้วจางลง
      ctx.globalAlpha = s.out ? .45 : 1;
      ctx.fillStyle = turn ? '#362a20' : '#2a211a';
      ctx.strokeStyle = turn ? '#e8b04b' : '#453528';
      ctx.lineWidth = 2;
      ctx.beginPath(); ctx.arc(0, 0, 26, 0, Math.PI * 2); ctx.fill(); ctx.stroke();

      ctx.textAlign = 'center'; ctx.textBaseline = 'middle';
      ctx.font = '22px system-ui';
      ctx.fillText(s.place ? (UNO_TROPHY[s.place] || '🏅') : (s.bot ? '🤖' : '🧑'), 0, 1);

      ctx.font = '600 12px system-ui';
      ctx.fillStyle = turn ? '#e8b04b' : '#a99274';
      ctx.fillText(s.name.replace('🤖 ', ''), 0, 42);
      ctx.font = '11px Bahnschrift, DIN Alternate, system-ui';
      ctx.fillStyle = s.cards === 1 ? '#d4553a' : '#a99274';
      ctx.fillText(s.place ? `อันดับ ${s.place}` : `${s.cards} ใบ`, 0, 57);
      // 💭 กำลังคิด — จุดไล่กันสามจุด ให้รู้ว่าเกมไม่ได้ค้าง
      if (thinking) {
        ctx.fillStyle = '#e8b04b';
        for (let k = 0; k < 3; k++) {
          const a = .3 + .7 * Math.max(0, Math.sin(UNO_PULSE * 1.6 - k * .7));
          ctx.globalAlpha = a;
          ctx.beginPath(); ctx.arc((k - 1) * 9, -38, 3, 0, Math.PI * 2); ctx.fill();
        }
        ctx.globalAlpha = 1;
      }
      ctx.restore();

      // หลังไพ่ของคู่แข่ง — วาดจากจำนวนที่เซิร์ฟเวอร์บอก ไม่รู้ว่าเป็นไพ่อะไร
      if (!s.you && !s.place) {
        const show = Math.min(s.cards, 7);
        for (let i = 0; i < show; i++) {
          ctx.save();
          ctx.translate(s.x + (i - (show - 1) / 2) * 11, s.y - 44);
          ctx.scale(.3, .3);
          ctx.fillStyle = '#2a211a';
          unoRR(ctx, -UNO_CW / 2, -UNO_CH / 2, UNO_CW, UNO_CH, 9); ctx.fill();
          ctx.strokeStyle = '#e8b04b'; ctx.lineWidth = 4;
          unoRR(ctx, -UNO_CW / 2 + 6, -UNO_CH / 2 + 6, UNO_CW - 12, UNO_CH - 12, 6);
          ctx.stroke();
          ctx.restore();
        }
      }
    });
  }

  UNO_CARDS.forEach(c => {
    if (c.anim) {
      c.t = Math.min(c.dur, c.t + UNO_DT);
      const k = c.t / c.dur, e = c.anim === 'flip' ? unoEaseIO(k) : unoEase(k);
      c.x = c.from.x + (c.to.x - c.from.x) * e;
      c.y = c.from.y + (c.to.y - c.from.y) * e;
      c.rot = c.from.rot + (c.to.rot - c.from.rot) * e;
      // ⚠️ ต้องไล่ค่า face ด้วย — ไม่งั้นจั่วแล้วไพ่ค้างคว่ำตลอด
      if (c.from.face !== undefined && c.to.face !== undefined) {
        c.face = c.from.face + (c.to.face - c.from.face) * e;
      }
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

  unoDrawSuitCards(ctx, W, H);   // ทับโต๊ะ แต่อยู่ใต้แผงประกาศอันดับ
  unoDrawFanfare(ctx, W, H);     // ทับทุกอย่าง — เป็นประกาศชั้นบนสุด
  UNO_LOOP = requestAnimationFrame(unoSafeFrame);
}

/** กันเฟรมเดียวที่พังไม่ให้ลากทั้งเกมค้าง

    บทเรียนจากสนามรบผลัดเทิร์น: error เฟรมเดียวหยุด requestAnimationFrame
    ทั้งจอค้างโดยไม่มีอะไรบอกเลย หาสาเหตุยากมาก
 */
function unoSafeFrame(now) {
  try {
    unoFrame(now);
  } catch (e) {
    console.error('[ศึกไพ่รูน] เฟรมนี้พัง — เล่นต่อเฟรมหน้า', e);
    UNO_LOOP = requestAnimationFrame(unoSafeFrame);
  }
}

// 🤔 เล่นตาบอททีละคน พร้อมหน่วงเวลา "กำลังคิด"
//    เซิร์ฟเวอร์เดินให้จบในคำขอเดียวแล้ว ที่นี่แค่เล่นภาพย้อนหลังให้ดูทัน
//    ไม่งั้นบอท 3 ตัวเล่นรวดเดียวจบ ผู้เล่นไม่ทันเห็นว่าเกิดอะไรขึ้น
const UNO_THINK_MS = 620;      // หน่วงต่อตาบอทหนึ่งคน
const UNO_DRAW_MS = 420;
const UNO_DEAL_MS = 85;        // ห่างกันกี่ ms ต่อการแจกหนึ่งใบ
let UNO_DEALING = false;       // กำลังแจกไพ่อยู่ — กดอะไรไม่ได้       // รอให้ไพ่ที่จั่วบินเข้ามือจนเห็น ก่อนปล่อยเป็นตาบอท
let UNO_THINK = null;          // {seat, t} บอทที่กำลังคิดอยู่
const unoWait = ms => new Promise(r => setTimeout(r, ms));

/** รอจนไพ่ที่กำลังบินลงจนหมด — ไม่เดาเวลา

    มีเพดานกันค้าง — อนิเมชันพังกลางคันต้องไม่ทำให้เกมค้างถาวร
 */
async function unoWaitFx(maxMs = 2500) {
  const until = Date.now() + maxMs;
  while (unoBusyFx() && Date.now() < until) await unoWait(30);
}

/** เล่นภาพตาบอททีละคน — คิดก่อน แล้วไพ่บินเข้ากอง */
async function unoPlayBotMoves(moves) {
  for (const m of (moves || [])) {
    UNO_THINK = { seat: m.seat, t: 0 };
    await unoWait(UNO_THINK_MS);
    UNO_THINK = null;
    if (m.card) {
      unoFlyToPile(m.seat, m.card);
      await unoWaitFx();                // รอจนไพ่ลงกองจริง ก่อนคนถัดไปคิด
    }
    await unoWait(140);                 // เว้นจังหวะสั้น ๆ ให้ตาตามกันไม่ติดกัน
  }
}

/** 🃏 ไพ่บินจากที่นั่งคนนั้นเข้ากองกลาง — เห็นชัดว่าใครลงไพ่ */
function unoFlyToPile(seat, card) {
  const cv = document.getElementById('unoCanvas');
  if (!cv) return;
  const t = unoPilePos(cv).pile;
  const from = unoSeats(cv).find(x => x.index === seat) || { x: cv.width / 2, y: 60 };
  UNO_CARDS.push({
    card, x: from.x, y: from.y, rot: 0, face: 0, sc: 1, flying: true,
    anim: 'arc', t: 0, dur: 22,
    from: { x: from.x, y: from.y, rot: 0, face: 0 },
    to: { x: t.x, y: t.y, rot: (Math.random() - .5) * .3, face: 1 },
  });
  SFX.play('click');
}

/** 🃏 อนิเมชันแจกไพ่ตอนเปิดโต๊ะ — บินออกจากกองไปทีละคน วนรอบโต๊ะ

    เจ้าของเกมสั่ง 08-29: "เริ่มเปิดโต๊ะก็ให้มีอนิเมชั่นแจกไพ่ให้ทุกคน
    จากเด็กที่อยู่บนโต๊ะ"
    แจกทีละรอบเหมือนโต๊ะจริง — คนละใบ วนไปเรื่อย ๆ จนครบ 7 ใบ
 */
async function unoDealAnim() {
  const cv = document.getElementById('unoCanvas');
  if (!cv || !UNO || !UNO.playing) return;
  const d = unoPilePos(cv).deck;
  const seats = unoSeats(cv);
  const hand = UNO.hand || [];
  const spots = [];
  // เราอยู่ล่างสุด — เอาตำแหน่งกลางแถวไพ่เป็นจุดหมาย
  const meSpot = unoFan(Math.floor(hand.length / 2), Math.max(1, hand.length),
                        cv.width, cv.height);
  for (let round = 0; round < Math.min(hand.length, 7); round++) {
    spots.push({ x: meSpot.x, y: meSpot.y, me: true });
    seats.forEach(s => spots.push({ x: s.x, y: s.y - 44, me: false }));
  }

  UNO_DEALING = true;
  for (const spot of spots) {
    UNO_CARDS.push({
      card: null, x: d.x, y: d.y, rot: 0, face: 0, sc: .8, flying: true,
      anim: 'arc', t: 0, dur: 13,
      from: { x: d.x, y: d.y, rot: 0, face: 0 },
      to: { x: spot.x, y: spot.y, rot: (Math.random() - .5) * .4, face: 0 },
    });
    SFX.play('click');
    await unoWait(UNO_DEAL_MS);
  }
  await unoWaitFx();                  // รอใบสุดท้ายบินถึงจริง ก่อนเฉลยไพ่จริง
  UNO_CARDS = UNO_CARDS.filter(c => c.card);   // เก็บไพ่หลอกทิ้ง
  UNO_DEALING = false;
  unoLayout();
  unoPaint();
}

async function unoDo(action, extra) {
  UNO_SENT = true;             // ปิดตาทันที — กดซ้ำระหว่างรอคำตอบไม่ได้
  try {
    const d = await api('POST', '/api/web/uno', { action, ...(extra || {}) });
    const bots = d.bot_moves || [];
    // 📥 จั่วไพ่หรือยอมจั่ว — ให้ไพ่บินเข้ามือเราให้เห็นก่อน แล้วค่อยเป็นตาบอท
    //    เจ้าของเกมสั่ง 08-29: "ถ้ามีดีเลย์ตอนจั่วก็ให้เป็นเทิร์นของคนๆนั้นไปก่อน"
    if ((action === 'draw' || action === 'take') && bots.length) {
      unoApply(d.table);                   // ไพ่ขึ้นมือ + บินออกจากกอง
      await unoWaitFx();                   // รอไพ่บินเข้ามือจนจบจริง
      await unoWait(UNO_DRAW_MS);          // แล้วค้างให้ดูอีกหน่อย
      await unoPlayBotMoves(bots);
      unoApply(d.table);                   // เซ็ตสถานะสุดท้ายอีกที
      return d;
    }
    // เล่นภาพตาบอทก่อน แล้วค่อยเฉลยสถานะใหม่ — ไม่งั้นผลมาก่อนภาพ
    if (action === 'start') {
      unoApply(d.table);
      await unoDealAnim();               // 🃏 แจกไพ่จากกองให้ทุกคนดูก่อน
      if (bots.length) await unoPlayBotMoves(bots);
      unoApply(d.table);
      return d;
    }
    if (bots.length) await unoPlayBotMoves(bots);
    unoApply(d.table);
    return d;
  } catch (e) {
    UNO_SENT = false;          // คำขอพลาด = คืนตาให้ ไม่งั้นค้างกดอะไรไม่ได้เลย
    toast(e.message, true);
    return null;
  }
}

// 🏁 อนิเมชันตอนมีคนเข้าเส้นชัย — อลังตามอันดับตามที่เจ้าของเกมสั่ง
//    ที่ 1 อลังสุด · ที่ 2-3 มีแต่ไม่เด่นเท่า · ที่เหลือไม่มี
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
  if (f.t >= f.dur) {
    UNO_FANFARE = null;
    unoPaintOver();          // อนิเมชันจบแล้วค่อยเฉลยตารางอันดับ
    return;
  }
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
  // เป็นเราเอง = แสดงความยินดี · เป็นคนอื่น = บอกเฉย ๆ ว่าเขาเข้าเส้นชัยแล้ว
  const line = f.you
    ? (big ? '🎉 ยินดีด้วย! คุณได้อันดับ 1' : `🎉 คุณได้อันดับ ${f.place}`)
    : (big ? 'ชนะ! — อันดับ 1' : `อันดับ ${f.place}`);
  ctx.fillText(line, 0, big ? 46 : 32);
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
  UNO_SENT = false;            // สถานะใหม่มาแล้ว เชื่อคำตอบจากเซิร์ฟเวอร์แทน
  unoLayout();
  // ไพ่ในมือเพิ่มขึ้น = เพิ่งจั่วมา ให้มันบินออกจากกองจริง ๆ
  const gained = ((UNO || {}).hand || []).length - before;
  if (gained > 0 && before) unoFlyDraw(gained);
  unoCheckFanfare();
  unoPaint();
  if (!UNO_LOOP) UNO_LOOP = requestAnimationFrame(unoSafeFrame);
}

/** 🔧 เรียกจาก Console เพื่อดูว่าทำไมแผงถึงค้าง — พิมพ์ unoWhy() ใน F12 */
function unoWhy() {
  const box = document.getElementById('unoOver');
  console.log('แผงสรุปซ่อนอยู่ไหม:', box && box.hidden);
  console.log('สถานะล่าสุด:', UNO && {
    playing: UNO.playing, over: UNO.over,
    finished: (UNO.finished || []).length, my_turn: UNO.my_turn,
  });
  console.log('ลูปวาดทำงานอยู่ไหม:', !!UNO_LOOP);
  return { fix: () => { if (box) box.hidden = true; return 'ซ่อนแล้ว'; } };
}

/** สรุปอันดับทั้งโต๊ะตอนจบเกม */
function unoPlaceText() {
  return ((UNO && UNO.finished) || [])
    .map(f => `${f.place}. ${f.name}${f.you ? ' (คุณ)' : ''}`).join(' · ');
}

/** 🏁 ตารางอันดับส่งท้าย — ขึ้นตอนจบเกมจริง พร้อมทางไปต่อ */
function unoPaintOver() {
  const box = document.getElementById('unoOver');
  const tbl = document.getElementById('unoRank');
  if (!box || !tbl) return;
  const done = (UNO && UNO.finished) || [];
  // ⚠️ รออนิเมชันแสดงความยินดีเล่นจบก่อน — ตารางคลุมเต็มจอ ขึ้นเร็วไปจะบังหมด
  //    เจ้าของเกมเจอ 08-29: "ลงไพ่ใบท้ายแล้วไม่มีอะไรขึ้น"
  //    (เล่น 2 คน ลงใบสุดท้าย = จบทันที ตารางขึ้นทับอนิเมชันพอดี)
  const show = !!(UNO && UNO.playing && UNO.over && done.length && !UNO_FANFARE);
  box.hidden = !show;
  if (!show) return;
  // ⚠️ ข้อมูลขาดฟิลด์สักตัวต้องไม่ทำให้ทั้งแผงพัง
  //    เกมที่ค้างใน DB จากก่อนเพิ่มฟิลด์ bot/left จะไม่มีค่าเหล่านี้
  //    ถ้า throw กลางคัน แผงจะโชว์ค้างโดยตารางว่างเปล่า กดอะไรก็ไม่หาย (เจ้าของเกมเจอ 08-29)
  try {
    tbl.innerHTML = done.map(f => {
      const place = f.place || 0;
      const name = String(f.name || 'ผู้เล่น');
      const medal = UNO_TROPHY[place] || `${place}.`;
      const who = `${f.bot ? '🤖' : '🧑'} ${name.replace('🤖 ', '')}`;
      const left = place === 1 ? 'หมดมือ' : `เหลือ ${f.left || 0} แต้ม`;
      return `<tr class="${f.you ? 'you' : ''}"><td>${medal}</td>` +
             `<td>${who}${f.you ? ' (คุณ)' : ''}</td><td>${left}</td></tr>`;
    }).join('');
  } catch (e) {
    console.error('[ศึกไพ่รูน] สร้างตารางอันดับไม่สำเร็จ', e, done);
    box.hidden = true;                  // สร้างไม่ได้ก็อย่าบังจอไว้
  }
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
    ['unoPass', 'unoSayUno'].forEach(id => show(id, false));
    show('unoOver', false);
    return;
  }
  // 🔧 กล่องเลือกสีจะโชว์ก็ต่อเมื่อมีไพ่รอเลือกสีจริง — นอกนั้นซ่อนเสมอ
  //    เคยพลาด: ซ่อนแค่ตอนไม่มีโต๊ะ กดเลือกสีแล้วปุ่มค้างคาหน้าจอตลอด
  const me = (UNO.players || []).find(p => p.you) || { cards: 0 };
  if (hud) hud.textContent = `กองจั่ว ${UNO.deck_left} ใบ · ${UNO.dir > 0 ? '↻' : '↺'}`;
  const over = !!UNO.over;
  const mine = UNO.my_place || 0;
  if (msg) {
    msg.textContent = over
      ? `🏁 จบเกม — ${unoPlaceText()}`
      : mine ? `🏅 คุณเข้าเส้นชัยอันดับ ${mine} — นั่งดูจนจบเกม`
      : UNO.must_answer ? `⚠️ โดน ${UNO.stack} ใบจ่ออยู่ — วางต่อ หรือกดกองไพ่เพื่อยอมจั่ว`
      : UNO.my_turn ? (unoMustDraw() ? '📥 ไม่มีไพ่ลงได้ — กดกองไพ่เพื่อจั่ว'
                        : 'ตาคุณ — ลากไพ่ไปวางที่กองกลาง')
      : 'รอคู่แข่ง...';
  }
  const playing = UNO.my_turn && !over && !mine;      // ทิ้งไพ่หมดแล้วกดอะไรไม่ได้อีก
  // จั่ว/ยอมจั่วย้ายไปกดที่กองไพ่บนโต๊ะแทนแล้ว (เจ้าของเกมสั่ง 08-29)
  show('unoPass', playing && UNO.drew);
  show('unoSayUno', me.cards === 1 && !me.said_uno && !over && !mine);
  if (log) log.innerHTML = (UNO.log || []).map(l =>
    `<div>${l.replace(/</g, '&lt;')}</div>`).join('');
  unoPaintOver();
}

/** ไวลด์ต้องเลือกสีก่อนวาง — โชว์ปุ่มสีแล้วรอกด */
function unoAskSuit(slot) {
  UNO_PICK = slot;
  const cv = document.getElementById('unoCanvas');
  if (!cv) return;
  const y = cv.height / 2 + 30;
  const keys = Object.keys(UNO_COLOR);
  // 🃏 ไพ่ธาตุ 4 ใบลอยขึ้นกลางจอ — ชี้แล้วใบนั้นลอยขึ้น กดแล้วเลือกสีนั้น
  //    แทนปุ่มข้อความด้านล่าง (เจ้าของเกมสั่ง 08-29)
  UNO_SUIT_CARDS = keys.map((k, i) => ({
    suit: k,
    x: cv.width / 2 + (i - (keys.length - 1) / 2) * 96,
    y: y + 40,                       // ลอยขึ้นจากข้างล่าง
    ty: y,
    t: 0,
    hover: false,
  }));
}

/** กดเลือกสีจากไพ่ที่ลอยอยู่ */
function unoPickSuitAt(p) {
  return UNO_SUIT_CARDS.find(c =>
    Math.abs(p.x - c.x) <= UNO_CW / 2 + 6 && Math.abs(p.y - c.y) <= UNO_CH / 2 + 6);
}

/** วาดไพ่เลือกสีที่ลอยอยู่ */
function unoDrawSuitCards(ctx, W, H) {
  if (!UNO_SUIT_CARDS.length) return;
  ctx.save();
  ctx.fillStyle = 'rgba(23,17,13,.72)';       // หรี่ฉากหลังให้ไพ่เด่น
  ctx.fillRect(0, 0, W, H);
  ctx.fillStyle = '#f2e7d8';
  ctx.font = '600 17px system-ui'; ctx.textAlign = 'center';
  ctx.fillText('เลือกธาตุต่อไป', W / 2, UNO_SUIT_CARDS[0].ty - UNO_CH / 2 - 26);
  ctx.restore();

  UNO_SUIT_CARDS.forEach(c => {
    c.t = Math.min(1, c.t + .1 * UNO_DT);
    c.y += (c.ty - (c.hover ? 16 : 0) - c.y) * Math.min(1, .2 * UNO_DT);
    const sc = (c.hover ? 1.12 : 1) * unoEase(c.t);
    const s = UNO_COLOR[c.suit];
    ctx.save();
    ctx.translate(c.x, c.y);
    ctx.scale(sc, sc);
    if (c.hover) {                            // ชี้ค้าง = ขอบเรือง
      ctx.shadowColor = '#e8b04b';
      ctx.shadowBlur = 20 + Math.sin(UNO_PULSE) * 8;
      ctx.strokeStyle = '#e8b04b'; ctx.lineWidth = 3;
      unoRR(ctx, -UNO_CW / 2, -UNO_CH / 2, UNO_CW, UNO_CH, 9);
      ctx.stroke(); ctx.stroke();
      ctx.shadowBlur = 0;
    }
    ctx.shadowColor = 'rgba(0,0,0,.55)'; ctx.shadowBlur = 16; ctx.shadowOffsetY = 7;
    ctx.fillStyle = '#f2e7d8';
    unoRR(ctx, -UNO_CW / 2, -UNO_CH / 2, UNO_CW, UNO_CH, 9); ctx.fill();
    ctx.shadowBlur = 0; ctx.shadowOffsetY = 0;
    const g = ctx.createLinearGradient(0, -UNO_CH / 2, 0, UNO_CH / 2);
    g.addColorStop(0, s.c); g.addColorStop(1, s.d);
    ctx.fillStyle = g;
    unoRR(ctx, -UNO_CW / 2 + 5, -UNO_CH / 2 + 5, UNO_CW - 10, UNO_CH - 10, 6); ctx.fill();
    ctx.fillStyle = 'rgba(255,255,255,.95)';
    ctx.textAlign = 'center'; ctx.textBaseline = 'middle';
    ctx.font = '30px system-ui';
    ctx.fillText(s.ico, 0, -6);
    ctx.font = '600 12px system-ui';
    ctx.fillText((UNO.suits || {})[c.suit] || '', 0, 26);
    ctx.restore();
  });
}

function unoBind() {
  const cv = document.getElementById('unoCanvas');
  if (!cv || cv.dataset.bound) return;
  cv.dataset.bound = '1';

  const down = e => {
    const pt = unoAt(e, cv);
    // 🃏 กำลังเลือกธาตุอยู่ — กินการกดทั้งหมด จนกว่าจะเลือกสีเสร็จ
    if (UNO_SUIT_CARDS.length) {
      const hit = unoPickSuitAt(pt);
      e.preventDefault();
      if (!hit) return;
      SFX.play('click');
      const pick = UNO_PICK;
      UNO_PICK = null;
      UNO_SUIT_CARDS = [];
      unoDo('play', { index: pick, suit: hit.suit });
      return;
    }
    const p = pt;
    // 📥 กดกองจั่วบนโต๊ะ = จั่วเลย ไม่ต้องเลื่อนไปหาปุ่มข้างล่าง
    if (unoOnDeck(p, cv) && unoMyTurn()) {
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
    if (UNO_SUIT_CARDS.length) {          // ชี้ไพ่ธาตุใบไหน ใบนั้นลอยขึ้น
      const hit = unoPickSuitAt(p);
      UNO_SUIT_CARDS.forEach(c => { c.hover = c === hit; });
      return;
    }
    if (!UNO_DRAG) { UNO_HOVER = unoHit(p); return; }
    UNO_DRAG.c.x = p.x + UNO_DRAG.ox;
    UNO_DRAG.c.y = p.y + UNO_DRAG.oy;
    UNO_DRAG.c.rot += (0 - UNO_DRAG.c.rot) * .2;
    e.preventDefault();
  };
  const up = async () => {
    if (!UNO_DRAG) return;
    const c = UNO_DRAG.c; UNO_DRAG = null;
    // ยังไม่ถึงตา = เด้งกลับเสมอ ไม่ส่งคำสั่งไปให้เซิร์ฟเวอร์ปฏิเสธ
    if (!unoMyTurn() || !unoNearPile(c, cv)) {   // ลากไม่ถึง = เด้งกลับ
      c.anim = 'move'; c.t = 0; c.dur = 18;
      c.from = { x: c.x, y: c.y, rot: c.rot }; c.to = { ...c.home };
      return;
    }
    const t = unoPilePos(cv).pile;
    // 🧲 ดูดเข้ากอง — ปล่อยตรงไหนก็ไหลเข้าที่เอง ไม่ต้องเล็งให้ตรง
    c.anim = 'move'; c.t = 0; c.dur = 8;
    c.from = { x: c.x, y: c.y, rot: c.rot };
    c.to = { x: t.x, y: t.y, rot: (Math.random() - .5) * .3 };
    unoBurst(t.x, t.y + 22, '#c8b48e', 16);
    const card = c.card;
    if (card && (card.value === 'wild' || card.value === 'wild4')) {
      UNO_SENT = true;                         // กำลังเลือกสี = ลงใบอื่นซ้อนไม่ได้
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

// 🤖 เลือกจำนวนบอทที่จะนั่งด้วย — มีผลตอนกดเปิดโต๊ะครั้งถัดไป
let UNO_BOTS = 1;
function unoPaintSeats() {
  document.querySelectorAll('[data-bots]').forEach(b =>
    b.classList.toggle('on', +b.dataset.bots === UNO_BOTS));
}
document.querySelectorAll('[data-bots]').forEach(b => {
  b.addEventListener('click', () => {
    UNO_BOTS = +b.dataset.bots;
    SFX.play('click');
    unoPaintSeats();
  });
});
unoPaintSeats();

document.getElementById('unoStart')?.addEventListener('click', async () => {
  SFX.play('click'); unoBind();
  UNO_SEEN_PLACE = 0; UNO_FANFARE = null; UNO_SUIT_CARDS = [];   // โต๊ะใหม่ เริ่มนับอันดับใหม่
  const overBox = document.getElementById('unoOver');
  if (overBox) overBox.hidden = true;
  await unoDo('start', { bots: UNO_BOTS });
});
document.getElementById('unoPass')?.addEventListener('click', () => {
  SFX.play('click'); unoDo('pass');
});
document.getElementById('unoAgain')?.addEventListener('click', async () => {
  SFX.play('click');
  UNO_SEEN_PLACE = 0; UNO_FANFARE = null; UNO_SUIT_CARDS = [];
  // ⚠️ ซ่อนแผงทันที ไม่รอคำตอบจากเซิร์ฟเวอร์
  //    เน็ตช้าหรือคำขอพลาด แผงก็ต้องหาย ไม่งั้นผู้เล่นติดค้างกดอะไรก็ไม่ได้
  //    (เจ้าของเกมเจอ 08-29: กดเล่นอีกรอบแล้วหน้าไม่หาย)
  const box = document.getElementById('unoOver');
  if (box) box.hidden = true;
  await unoDo('start', { bots: UNO_BOTS });
});
document.getElementById('unoLeave')?.addEventListener('click', async () => {
  SFX.play('click');
  const box = document.getElementById('unoOver');
  if (box) box.hidden = true;
  await unoDo('quit');
  showPanel('home');
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
