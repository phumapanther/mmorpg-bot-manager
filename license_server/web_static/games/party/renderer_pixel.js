// 🎭 หน้าจอต่อสู้ปาร์ตี้ — ตัววาดแบบยกเครื่อง (เฟส 7)
//
// ⚠️ ไฟล์นี้ "วาดอย่างเดียว" ไม่ตัดสินกติกาเลยแม้แต่บรรทัดเดียว
//    รับ events จากเซิร์ฟเวอร์แล้วแปลเป็นภาพ เหมือน renderer_basic.js ทุกประการ
//    → นี่คือหลักฐานว่าเปลี่ยนกราฟิกได้โดยไม่ต้องแตะ Python สักบรรทัด
//      (สลับได้ด้วยการแก้ <script src> ใน play.html บรรทัดเดียว)
//
// สัญญาที่ต้องทำตาม (เทสคุมที่ tests/party_boot.js — รันกับ renderer ทุกตัว):
//   pbMount(mountId) · pbSetState(battle) · pbPlay(events) · pbDraw() · pbClick(ev)
//   เรียกกลับ onPartyPick(unitId, side, alive) ตอนคลิกตัวละคร
//
// วาดด้วยรูปทรงล้วน ไม่ใช้ไฟล์ภาพเลย — ไม่ต้องโหลดอะไรเพิ่ม ไม่มีภาพแตก

const PX = {
  cv: null, ctx: null,
  state: null,
  units: [],
  pops: [],          // เลขดาเมจลอย
  fx: [],            // ประกายตอนโดนตี
  hp: {},            // เลือดที่ "กำลังวาด" — ไล่ตามเลือดจริงแบบนุ่ม ๆ
  lunge: {},         // ตัวที่กำลังพุ่งเข้าใส่ (id -> ความคืบหน้า 0..1)
  warn: null,        // ป้ายเตือนท่าใหญ่ ค้างจนบอสปล่อยท่า
  duel: null,        // เต๋าที่กำลังทอยแข่ง {from,to,atk,def,hit,t}
  queue: [],         // เหตุการณ์ที่รอเล่น — เล่นทีละอัน ไม่รัวทับกัน
  wait: 0,           // เฟรมที่ต้องรอก่อนเล่นอันถัดไป
  flash: 0,          // จอวาบตอนคริ
  shake: 0,
  t: 0,              // ตัวนับเฟรม ใช้ทำจังหวะหายใจ/กะพริบ
  raf: null,
};

// จังหวะของแต่ละเหตุการณ์ (เฟรม @60fps) — เล่นทีละอันไม่ให้ทับกัน
// เจ้าของเกมสั่ง 2026-09-04: ถึงตาบอท/มอน ให้รอสักพักแล้วค่อยตี จะได้ดูทัน
const EV_FRAMES = {
  contest: 46, attack: 22, aoe: 28, heal: 20, miss: 18,
  die: 24, phase: 28, telegraph: 36, buff: 16,
};
const EV_DEFAULT = 18;

const DUEL_FRAMES = 46;      // กี่เฟรมที่โชว์เต๋า (คลึงอยู่ครึ่งแรก เฉลยครึ่งหลัง)
const DUEL_SPIN = 20;        // คลึงกี่เฟรมก่อนเฉลยแต้ม

const PX_W = 900;
const PX_H = 420;

const PX_ELEM = {
  fire: ['#ff8a5c', '#c2331a'], water: ['#6bb8ff', '#1a4fa8'],
  wood: ['#7ee89a', '#1f8a48'], earth: ['#e0c05a', '#8a6a12'],
  wind: ['#9df0e4', '#249c8c'], light: ['#ffefa8', '#c9a227'],
  dark: ['#c4a2ff', '#5a2fa8'], none: ['#aab4c2', '#4a5464'],
};

const px = {
  /** ตำแหน่งยืนของแต่ละหน่วย — ปาร์ตี้แถวล่าง มอนแถวบน */
  slots() {
    const party = PX.units.filter(u => u.side === 'party');
    const mons = PX.units.filter(u => u.side === 'monster');
    const out = {};
    const row = (arr, y, scale) => arr.forEach((u, i) => {
      out[u.id] = { x: (PX_W / (arr.length + 1)) * (i + 1), y, u, scale };
    });
    row(mons, 150, 1);
    row(party, 330, 1);
    return out;
  },

  /** เลือดที่วาดอยู่ตอนนี้ (ไล่ตามของจริงทีละนิด ไม่กระตุกลงทันที) */
  hpPct(u) {
    const real = u.side === 'party'
      ? Math.max(0, u.hp) / Math.max(1, u.hp_max)
      : Math.max(0, u.hp_pct || 0) / 100;
    if (PX.hp[u.id] === undefined) PX.hp[u.id] = real;
    return { real, shown: PX.hp[u.id] };
  },

  /** มีอะไรกำลังเคลื่อนไหวอยู่ไหม — ไม่มีก็หยุดวาด ไม่เปลืองแบต */
  busy() {
    if (PX.pops.length || PX.fx.length || PX.shake > 0 || PX.flash > 0) return true;
    // ⚠️ กะพริบแค่ช่วงแรกพอ แล้วปล่อยให้ป้ายนิ่ง
    //    ไม่งั้นวนวาดยาวจนกว่าบอสจะปล่อยท่า (นานได้ถึง 60 วิ) เปลืองแบตเปล่า ๆ
    //    (เทสชุดร่วมจับได้ตอนเฟส 7 — renderer_basic นิ่ง แต่ตัวนี้ไม่นิ่ง)
    if (PX.warn && PX.warn.pulse > 0) return true;
    if (PX.duel && PX.duel.t < DUEL_FRAMES) return true;
    if (PX.queue.length || PX.wait > 0) return true;
    if (Object.keys(PX.lunge).length) return true;
    return PX.units.some(u => {
      const h = px.hpPct(u);
      return Math.abs(h.real - h.shown) > 0.003;
    });
  },
};

/** เริ่มหน้าจอ — สร้าง canvas ในจุดเสียบ */
function pbMount(mountId) {
  const box = document.getElementById(mountId || 'partyMount');
  if (!box) return null;
  if (!PX.cv || !box.contains(PX.cv)) {
    box.innerHTML = '';
    PX.cv = document.createElement('canvas');
    PX.cv.width = PX_W;
    PX.cv.height = PX_H;
    box.appendChild(PX.cv);
    PX.ctx = PX.cv.getContext('2d');
    PX.cv.onclick = pbClick;
    // สร้างจอใหม่ = สมรภูมิใหม่ ล้างของค้างจากรอบก่อนให้หมด
    PX.pops = [];
    PX.fx = [];
    PX.hp = {};
    PX.lunge = {};
    PX.warn = null;
    PX.duel = null;
    PX.queue = [];
    PX.wait = 0;
    PX.shake = 0;
    PX.flash = 0;
  }
  return PX.cv;
}

/** อัปเดตสถานะจาก view() ที่เซิร์ฟเวอร์ส่งมา */
function pbSetState(battle) {
  PX.state = battle || null;
  PX.units = (battle && battle.units) || [];
  pxLoop();
}

/** รับเหตุการณ์ที่เพิ่งเกิด — **เข้าคิวไว้** แล้วค่อยเล่นทีละอัน
 *
 * ⚠️ เดิมเล่นรวดเดียวทั้งชุด ตาของมอน 3 ตัวจึงเกิดพร้อมกันในเฟรมเดียว
 *    ดูไม่ทันว่าใครตีใคร (เจ้าของเกมสั่งให้หน่วงตอนถึงตาบอท 2026-09-04)
 */
function pbPlay(events) {
  for (const e of events || []) PX.queue.push(e);
  pxLoop();
}

/** ดึงเหตุการณ์ถัดไปมาเล่นเมื่อถึงจังหวะ — เรียกทุกเฟรม */
function pxStep() {
  if (PX.wait > 0) { PX.wait -= 1; return; }
  const e = PX.queue.shift();
  if (!e) return;
  pxApply([e]);
  PX.wait = EV_FRAMES[e.t] || EV_DEFAULT;
}

function pxApply(events) {
  for (const e of events || []) {
    if (e.t === 'contest') {
      // 🎲 เจ้าของเกมสั่ง: ต้องเห็นเต๋าทั้งสองฝั่งทุกครั้ง ไม่ว่าใครเป็นฝ่ายตี
      PX.duel = { from: e.from, to: e.to, atk: e.atk, def: e.def,
                  hit: e.hit, evaded: e.evaded, t: 0 };
    } else if (e.t === 'attack') {
      pxLunge(e.from);
      pxPop(e.to, `-${e.dmg}`, e.crit ? '#ffd34a' : '#ff8080', e.crit);
      pxBurst(e.to, e.element, e.crit ? 22 : 12);
      PX.shake = e.crit ? 12 : 6;
      if (e.crit) PX.flash = 1;
    } else if (e.t === 'aoe') {
      pxLunge(e.from);
      (e.targets || []).forEach((id, i) => {
        pxPop(id, `-${e.dmgs[i]}`, '#ff9a5a');
        pxBurst(id, e.element, 10);
      });
      PX.shake = 10;
    } else if (e.t === 'heal') {
      pxPop(e.to, `+${e.amount}`, '#6ee7a0');
      pxBurst(e.to, 'wood', 10);
    } else if (e.t === 'miss') {
      pxPop(e.to, 'พลาด!', '#9aa4b2');
    } else if (e.t === 'die') {
      pxPop(e.who, '💀', '#ff5252', true);
      pxBurst(e.who, 'dark', 18);
    } else if (e.t === 'phase') {
      pxPop(e.who, e.phase === 'rage' ? '🔥 คลั่ง!' : '💀 สิ้นหวัง!', '#ff4a4a', true);
      PX.flash = 1;
    } else if (e.t === 'telegraph') {
      // ป้ายนี้คือสิ่งเดียวที่ผู้เล่นได้รู้ล่วงหน้า ต้องค้างข้ามเฟรม
      PX.warn = { who: e.who, move: e.move, pulse: 90 };
      pxPop(e.who, '⚠️', '#ffd34a', true);
    }
    if ((e.t === 'aoe' || e.t === 'attack') && PX.warn && e.from === PX.warn.who) {
      PX.warn = null;                                // ปล่อยท่าแล้วป้ายหมดหน้าที่
    }
  }
}

function pxPop(id, text, color, big) {
  PX.pops.push({ id, text, color, big: !!big, life: 64, age: 0 });
}

function pxLunge(id) {
  if (id) PX.lunge[id] = 0;
}

/** ประกายตอนโดนตี — สีตามธาตุของท่า */
function pxBurst(id, element, n) {
  const col = (PX_ELEM[element] || PX_ELEM.none)[0];
  for (let i = 0; i < n; i++) {
    const a = (Math.PI * 2 * i) / n;
    PX.fx.push({
      id, col, life: 26,
      dx: Math.cos(a) * (1.6 + (i % 3)), dy: Math.sin(a) * (1.6 + (i % 3)) - 1,
      x: 0, y: 0,
    });
  }
}

/** เหตุการณ์ที่ยังค้างคิวอยู่กี่อัน — 0 = อนิเมชันเล่นจบแล้ว
 *  หน้าเว็บ/เทสใช้เช็คว่ายังเล่นอยู่ไหม (ส่วนหนึ่งของสัญญา renderer)
 */
function pbPending() {
  return PX.queue.length + (PX.wait > 0 ? 1 : 0);
}

function pbClick(ev) {
  if (!PX.cv) return;
  const r = PX.cv.getBoundingClientRect();
  const x = (ev.clientX - r.left) * (PX_W / (r.width || PX_W));
  const y = (ev.clientY - r.top) * (PX_H / (r.height || PX_H));
  for (const [id, s] of Object.entries(px.slots())) {
    if (Math.abs(x - s.x) < 58 && Math.abs(y - s.y) < 62) {
      // ⚠️ ห้ามตัดคนที่ล้มทิ้งตรงนี้ — ท่าชุบเล็งคนที่ล้มเท่านั้น
      //    renderer ไม่รู้กติกา ส่งต่อให้คนเรียกตัดสิน
      if (typeof onPartyPick === 'function') onPartyPick(id, s.u.side, s.u.alive);
      return;
    }
  }
}

/** ตัดชื่อให้สั้นแบบ **นับอักขระจริง** ไม่ใช่นับหน่วย UTF-16
 *  slice() ธรรมดาผ่ากลางอิโมจิได้ (อิโมจิ 1 ตัว = 2 หน่วย) แล้วขึ้น � บนจอ
 *  ชื่อมอนตามธีมทวีปมีอิโมจิเยอะ จึงมีโอกาสโดนจริง */
function pbShortName(name) {
  const c = [...String(name || '')];
  return c.length > 14 ? c.slice(0, 14).join('') : c.join('');
}

// ── การวาด ──

function pxBackdrop(c) {
  const sky = c.createLinearGradient(0, 0, 0, PX_H);
  sky.addColorStop(0, '#161a2a');
  sky.addColorStop(0.55, '#101422');
  sky.addColorStop(1, '#0a0d15');
  c.fillStyle = sky;
  c.fillRect(-30, -30, PX_W + 60, PX_H + 60);

  // ลานยืนสองชั้น ให้รู้สึกมีระยะใกล้-ไกล
  for (const [cy, rx, ry, fill] of [[168, 330, 44, 'rgba(90,110,160,.10)'],
                                    [352, 390, 52, 'rgba(120,140,190,.13)']]) {
    c.beginPath();
    c.ellipse(PX_W / 2, cy, rx, ry, 0, 0, Math.PI * 2);
    c.fillStyle = fill;
    c.fill();
  }
}

/** แถบลำดับคิว — ผู้เล่นวางแผนได้ว่าอีกกี่ตาถึงตัวเอง */
function pxQueue(c) {
  const order = (PX.state && PX.state.order) || [];
  if (!order.length) return;
  const by = {};
  PX.units.forEach(u => { by[u.id] = u; });
  let x = 12;
  for (const id of order.slice(0, 8)) {
    const u = by[id];
    if (!u) continue;
    const on = PX.state && PX.state.turn_of === id;
    const col = (PX_ELEM[u.element] || PX_ELEM.none)[0];
    c.globalAlpha = u.alive ? 1 : 0.3;
    c.fillStyle = on ? '#ffd34a' : 'rgba(255,255,255,.10)';
    c.beginPath();
    c.roundRect(x, 8, 26, 26, 7);
    c.fill();
    c.fillStyle = on ? '#1a1a1a' : col;
    c.font = 'bold 12px system-ui, sans-serif';
    c.textAlign = 'center';
    c.fillText(u.side === 'party' ? '🧍' : '👾', x + 13, 26);
    c.globalAlpha = 1;
    x += 32;
  }
}

function pxUnit(c, s, id) {
  const u = s.u;
  const [c1, c2] = PX_ELEM[u.element] || PX_ELEM.none;
  const boss = !!u.boss;
  const w = boss ? 44 : 30;
  const h = boss ? 94 : 72;

  // หายใจขึ้นลงเบา ๆ — ตัวที่ถึงตาหายใจแรงกว่า
  const turn = PX.state && PX.state.turn_of === id;
  const bob = u.alive ? Math.sin(PX.t / (turn ? 9 : 16)) * (turn ? 3.5 : 1.6) : 0;
  const lung = PX.lunge[id] || 0;
  const dir = u.side === 'party' ? -1 : 1;
  const ox = Math.sin(lung * Math.PI) * 26 * dir;
  const y = s.y + bob;

  // เงาใต้เท้า
  c.globalAlpha = u.alive ? 0.42 : 0.15;
  c.fillStyle = '#000';
  c.beginPath();
  c.ellipse(s.x + ox, s.y + h / 2 + 6, w * 0.9, 9, 0, 0, Math.PI * 2);
  c.fill();
  c.globalAlpha = 1;

  // วงไฟใต้เท้าคนที่ถึงตา
  if (turn && u.alive) {
    const pulse = 0.5 + Math.sin(PX.t / 7) * 0.22;
    c.beginPath();
    c.ellipse(s.x + ox, s.y + h / 2 + 6, w * 1.15, 13, 0, 0, Math.PI * 2);
    c.fillStyle = `rgba(255,211,74,${0.16 + pulse * 0.16})`;
    c.fill();
  }

  c.globalAlpha = u.alive ? 1 : 0.28;

  // ลำตัว (ไล่สีตามธาตุ)
  const g = c.createLinearGradient(0, y - h / 2, 0, y + h / 2);
  g.addColorStop(0, c1);
  g.addColorStop(1, c2);
  c.fillStyle = g;
  c.beginPath();
  c.roundRect(s.x + ox - w / 2, y - h / 2 + 16, w, h - 16, [14, 14, 9, 9]);
  c.fill();

  // หัว
  c.beginPath();
  c.arc(s.x + ox, y - h / 2 + 10, boss ? 17 : 13, 0, Math.PI * 2);
  c.fillStyle = c1;
  c.fill();

  // ขอบเรืองแสงตอนถึงตา
  if (turn && u.alive) {
    c.strokeStyle = 'rgba(255,211,74,.85)';
    c.lineWidth = 2;
    c.beginPath();
    c.roundRect(s.x + ox - w / 2 - 3, y - h / 2 + 13, w + 6, h - 10, 15);
    c.stroke();
  }

  if (boss) {
    c.font = '20px system-ui';
    c.textAlign = 'center';
    c.fillText('👑', s.x + ox, y - h / 2 - 10);
  }
  if (u.defending) {
    c.font = '17px system-ui';
    c.textAlign = 'center';
    c.fillText('🛡️', s.x + ox + w / 2 + 6, y);
  }
  c.globalAlpha = 1;

  // ชื่อ
  c.fillStyle = u.alive ? '#e9edf5' : '#6b7280';
  c.font = '13px system-ui, sans-serif';
  c.textAlign = 'center';
  c.fillText(pbShortName(u.name), s.x, s.y + h / 2 + 26);

  pxHpBar(c, s, u, w, h);
}

function pxHpBar(c, s, u, w, h) {
  const bw = Math.max(64, w * 2);
  const bx = s.x - bw / 2;
  const by = s.y - h / 2 - 12;
  const { real, shown } = px.hpPct(u);

  c.fillStyle = 'rgba(0,0,0,.55)';
  c.beginPath();
  c.roundRect(bx, by, bw, 8, 4);
  c.fill();

  // แถบสีจาง = เลือดที่กำลังไหลลง (เห็นชัดว่าเพิ่งโดนไปเท่าไหร่)
  if (shown > real) {
    c.fillStyle = 'rgba(255,90,90,.55)';
    c.beginPath();
    c.roundRect(bx, by, bw * shown, 8, 4);
    c.fill();
  }
  c.fillStyle = real > 0.5 ? '#5bd67d' : real > 0.2 ? '#ffd34a' : '#ff5252';
  c.beginPath();
  c.roundRect(bx, by, bw * Math.max(0, Math.min(1, real)), 8, 4);
  c.fill();

  // ผู้เล่นเห็นตัวเลข มอนเห็นแค่แถบ (เซิร์ฟเวอร์ไม่ส่ง hp จริงของมอนมาให้)
  if (u.side === 'party') {
    c.fillStyle = '#9aa4b2';
    c.font = '11px system-ui, sans-serif';
    c.textAlign = 'center';
    c.fillText(`${u.hp}/${u.hp_max}`, s.x, by - 4);
  }
}

/** ลูกเต๋าหนึ่งลูก — คลึงอยู่ก็สุ่มเลขไปเรื่อย ๆ พอเฉลยค่อยหยุดที่แต้มจริง */
function pxDie(c, x, y, value, spinning, win) {
  const n = spinning ? 1 + Math.floor(Math.random() * 20) : value;
  c.fillStyle = win ? '#ffd34a' : 'rgba(255,255,255,.13)';
  c.beginPath();
  c.roundRect(x - 26, y - 26, 52, 52, 12);
  c.fill();
  c.strokeStyle = win ? '#fff3c4' : 'rgba(255,255,255,.28)';
  c.lineWidth = 2;
  c.stroke();
  c.fillStyle = win ? '#1a1a1a' : '#e9edf5';
  c.font = 'bold 24px system-ui, sans-serif';
  c.textAlign = 'center';
  c.textBaseline = 'middle';
  c.fillText(String(n), x, y + 1);
  c.textBaseline = 'alphabetic';
}

/** จอทอยเต๋าแข่ง — ฝั่งซ้ายคนตี ฝั่งขวาคนโดน แล้วเฉลยว่าใครชนะ */
function pxDuel(c) {
  const d = PX.duel;
  if (!d) return;
  d.t += 1;
  if (d.t > DUEL_FRAMES) { PX.duel = null; return; }

  const spin = d.t < DUEL_SPIN;
  const fade = d.t > DUEL_FRAMES - 8 ? (DUEL_FRAMES - d.t) / 8 : 1;
  const cy = 210;
  c.globalAlpha = fade;

  c.fillStyle = 'rgba(8,10,16,.72)';
  c.beginPath();
  c.roundRect(PX_W / 2 - 150, cy - 46, 300, 92, 16);
  c.fill();

  if (d.evaded) {
    c.fillStyle = '#9df0e4';
    c.font = 'bold 22px system-ui, sans-serif';
    c.textAlign = 'center';
    c.fillText('💨 หลบได้!', PX_W / 2, cy + 8);
    c.globalAlpha = 1;
    return;
  }

  pxDie(c, PX_W / 2 - 72, cy, d.atk, spin, !spin && d.hit);
  pxDie(c, PX_W / 2 + 72, cy, d.def, spin, !spin && !d.hit);

  c.fillStyle = '#9aa4b2';
  c.font = 'bold 18px system-ui, sans-serif';
  c.textAlign = 'center';
  c.fillText('VS', PX_W / 2, cy + 7);

  if (!spin) {
    c.fillStyle = d.hit ? '#ffd34a' : '#9aa4b2';
    c.font = 'bold 15px system-ui, sans-serif';
    c.fillText(d.hit ? '⚔️ โจมตีเข้า!' : '🛡️ ป้องกันไว้ได้', PX_W / 2, cy + 40);
  }
  c.globalAlpha = 1;
}

function pxWarnBanner(c) {
  if (!PX.warn) return;
  if (PX.warn.pulse > 0) PX.warn.pulse -= 1;
  const pulse = PX.warn.pulse > 0 ? 0.62 + Math.sin(PX.t / 5) * 0.22 : 0.78;
  c.fillStyle = `rgba(200,30,30,${pulse})`;
  c.fillRect(0, 0, PX_W, 38);
  c.fillStyle = '#fff';
  c.font = 'bold 16px system-ui, sans-serif';
  c.textAlign = 'center';
  c.fillText(`⚠️ กำลังร่ายท่าใหญ่: ${PX.warn.move} — ตาหน้าโดนทั้งปาร์ตี้!`,
             PX_W / 2, 25);
}

function pbDraw() {
  const c = PX.ctx;
  if (!c) return;
  PX.t += 1;
  pxStep();

  const sx = PX.shake ? (Math.random() - 0.5) * PX.shake : 0;
  const sy = PX.shake ? (Math.random() - 0.5) * PX.shake : 0;
  if (PX.shake > 0) PX.shake = Math.max(0, PX.shake - 0.7);

  c.save();
  c.translate(sx, sy);
  pxBackdrop(c);

  const slots = px.slots();

  // ไล่เลือดที่วาดให้ตามเลือดจริงทีละนิด
  for (const u of PX.units) {
    const { real } = px.hpPct(u);
    PX.hp[u.id] += (real - PX.hp[u.id]) * 0.12;
    if (Math.abs(real - PX.hp[u.id]) <= 0.003) PX.hp[u.id] = real;
  }
  // เดินอนิเมชันพุ่งเข้าใส่
  for (const id of Object.keys(PX.lunge)) {
    PX.lunge[id] += 0.09;
    if (PX.lunge[id] >= 1) delete PX.lunge[id];
  }

  for (const [id, s] of Object.entries(slots)) pxUnit(c, s, id);

  // ประกาย
  for (const f of PX.fx) {
    const s = slots[f.id];
    f.life -= 1;
    if (!s) continue;
    f.x += f.dx;
    f.y += f.dy;
    f.dy += 0.22;
    c.globalAlpha = Math.max(0, f.life / 26);
    c.fillStyle = f.col;
    c.beginPath();
    c.arc(s.x + f.x, s.y + f.y, 2.6, 0, Math.PI * 2);
    c.fill();
  }
  c.globalAlpha = 1;
  PX.fx = PX.fx.filter(f => f.life > 0);

  // เลขดาเมจลอย — พุ่งขึ้นแล้วค่อย ๆ ตกกลับ
  for (const p of PX.pops) {
    const s = slots[p.id];
    p.age += 1;
    p.life -= 1;
    if (!s) continue;
    const k = p.age / 64;
    const rise = Math.sin(Math.min(1, k * 1.6) * Math.PI * 0.5) * 52;
    const pop = p.age < 6 ? 1 + (6 - p.age) * 0.09 : 1;
    c.globalAlpha = Math.max(0, p.life / 64);
    c.fillStyle = p.color;
    c.font = `bold ${Math.round((p.big ? 27 : 20) * pop)}px system-ui, sans-serif`;
    c.textAlign = 'center';
    c.fillText(p.text, s.x, s.y - 56 - rise);
  }
  c.globalAlpha = 1;
  PX.pops = PX.pops.filter(p => p.life > 0);

  pxQueue(c);
  pxDuel(c);
  pxWarnBanner(c);

  // จอวาบตอนคริ
  if (PX.flash > 0) {
    c.fillStyle = `rgba(255,255,255,${PX.flash * 0.22})`;
    c.fillRect(-30, -30, PX_W + 60, PX_H + 60);
    PX.flash = Math.max(0, PX.flash - 0.12);
  }

  c.restore();
}

function pxLoop() {
  if (PX.raf) return;
  const tick = () => {
    pbDraw();
    if (px.busy()) {
      PX.raf = requestAnimationFrame(tick);
    } else {
      PX.raf = null;
      pbDraw();                     // เฟรมนิ่งสุดท้าย
    }
  };
  PX.raf = requestAnimationFrame(tick);
}
