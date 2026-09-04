// 🎭 หน้าจอต่อสู้ปาร์ตี้ — ตัววาดพื้นฐาน (เฟส 3)
//
// ⚠️ ไฟล์นี้ "วาดอย่างเดียว" ไม่ตัดสินกติกาเลยแม้แต่บรรทัดเดียว
//    อ่าน events ที่เซิร์ฟเวอร์ส่งมาแล้วแปลเป็นภาพ
//    → เปลี่ยนกราฟิก = เขียนไฟล์ใหม่แทนไฟล์นี้ ไม่ต้องแตะ Python
//    (นี่คือเงื่อนไขที่เจ้าของเกมสั่งไว้ 2026-09-03)
//
// สัญญาเหตุการณ์ดูที่ bot/games/party/events.py

const PB = {
  cv: null, ctx: null,
  units: [],          // สถานะล่าสุดจาก view()
  pops: [],           // เลขดาเมจลอย
  shake: 0,           // สั่นจอตอนโดนตี
  warn: null,         // ป้ายเตือนท่าใหญ่ของบอส — ค้างไว้จนบอสปล่อยท่า
  duel: null,         // เต๋าที่กำลังทอยแข่งกัน
  hpT: {},            // เลือดเป้าหมาย — ขยับตาม **เหตุการณ์** ไม่ใช่ตามสถานะ
  queue: [],          // เหตุการณ์ที่รอเล่น — เล่นทีละอัน ไม่รัวทับกัน
  wait: 0,
  raf: null,
};

// จังหวะของแต่ละเหตุการณ์ (เฟรม @60fps) — เล่นทีละอันไม่ให้ทับกัน
// เจ้าของเกมสั่ง 2026-09-04: ถึงตาบอท/มอน ให้รอสักพักแล้วค่อยตี จะได้ดูทัน
const EV_FRAMES = {
  contest: 46, attack: 22, aoe: 28, heal: 20, miss: 18,
  die: 24, phase: 28, telegraph: 36, buff: 16,
};
const EV_DEFAULT = 18;

const PB_COLORS = {
  fire: '#ff6b4a', water: '#4aa3ff', wood: '#5bd67d', earth: '#c9a227',
  wind: '#7fe3d4', light: '#ffe27a', dark: '#a97bff', null: '#9aa4b2',
};

/** เริ่มหน้าจอต่อสู้ — สร้าง canvas ในจุดเสียบ (#partyMount) */
function pbMount(mountId) {
  const box = document.getElementById(mountId || 'partyMount');
  if (!box) return null;
  if (!PB.cv || !box.contains(PB.cv)) {
    box.innerHTML = '';
    PB.cv = document.createElement('canvas');
    PB.cv.width = 900;
    PB.cv.height = 420;
    box.appendChild(PB.cv);
    PB.ctx = PB.cv.getContext('2d');
    PB.cv.onclick = pbClick;
    // สร้างจอใหม่ = สมรภูมิใหม่ ล้างของค้างจากรอบก่อนให้หมด
    // (ป้ายเตือนท่าใหญ่/เลขดาเมจค้างข้ามรอบจะงงมาก)
    PB.pops = [];
    PB.warn = null;
    PB.duel = null;
    PB.queue = [];
    PB.wait = 0;
    PB.hpT = {};
    PB.shake = 0;
  }
  return PB.cv;
}

/** อัปเดตสถานะจาก view() ที่เซิร์ฟเวอร์ส่งมา */
function pbSetState(battle) {
  PB.state = battle || null;
  PB.units = (battle && battle.units) || [];
  pbLoop();
}

/** รับเหตุการณ์ — **เข้าคิวไว้** แล้วค่อยเล่นทีละอัน
 *  เดิมเล่นรวดเดียว ตาของมอนหลายตัวเกิดพร้อมกันจนดูไม่ทัน */
function pbPlay(events) {
  for (const e of events || []) PB.queue.push(e);
  pbLoop();
}

function pbStep() {
  if (PB.wait > 0) { PB.wait -= 1; return; }
  const e = PB.queue.shift();
  if (!e) {
    for (const u of PB.units) PB.hpT[u.id] = pbFrac(u);
    return;
  }
  pbApply([e]);
  PB.wait = EV_FRAMES[e.t] || EV_DEFAULT;
}

function pbApply(events) {
  for (const e of events || []) {
    if (e.t === 'contest') {
      // 🎲 ต้องเห็นเต๋าทั้งสองฝั่งทุกครั้ง (เจ้าของเกมสั่ง 2026-09-04)
      PB.duel = { atk: e.atk, def: e.def, hit: e.hit, evaded: e.evaded, t: 0 };
    } else if (e.t === 'attack') {
      pbPop(e.to, `-${e.dmg}`, e.crit ? '#ffd34a' : '#ff7a7a', e.crit);
      pbRelease([e.to]);
      PB.shake = e.crit ? 10 : 5;
    } else if (e.t === 'aoe') {
      (e.targets || []).forEach((id, i) => pbPop(id, `-${e.dmgs[i]}`, '#ff9a5a'));
      pbRelease(e.targets || []);
      PB.shake = 8;
    } else if (e.t === 'heal') {
      pbPop(e.to, `+${e.amount}`, '#6ee7a0');
      pbRelease([e.to]);
    } else if (e.t === 'miss') {
      pbPop(e.to, 'พลาด!', '#9aa4b2');
    } else if (e.t === 'die') {
      pbPop(e.who, '💀', '#ff5252', true);
      pbRelease([e.who]);
    } else if (e.t === 'telegraph') {
      // ⚠️ ป้ายนี้คือสิ่งเดียวที่ผู้เล่นได้รู้ล่วงหน้า — ต้องค้างข้ามเฟรม
      //    ไม่ใช่วูบเดียวหาย ไม่งั้นเตือนไปก็เท่านั้น
      PB.warn = { who: e.who, move: e.move };
      pbPop(e.who, '⚠️', '#ffd34a', true);
    } else if (e.t === 'phase') {
      pbPop(e.who, e.phase === 'rage' ? '🔥 คลั่ง!' : '💀 สิ้นหวัง!', '#ff4a4a', true);
    }
    // ปล่อยท่าแล้วป้ายเตือนหมดหน้าที่
    if ((e.t === 'aoe' || e.t === 'attack') && PB.warn && e.from === PB.warn.who) {
      PB.warn = null;
    }
  }
}

function pbPop(unitId, text, color, big) {
  PB.pops.push({ id: unitId, text, color, big: !!big, life: 60, dy: 0 });
}

/** ตำแหน่งบนจอของแต่ละหน่วย — ปาร์ตี้อยู่ล่าง มอนอยู่บน */
function pbSlots() {
  const party = PB.units.filter(u => u.side === 'party');
  const mons = PB.units.filter(u => u.side === 'monster');
  const out = {};
  const place = (arr, y) => arr.forEach((u, i) => {
    out[u.id] = { x: (900 / (arr.length + 1)) * (i + 1), y, u };
  });
  place(mons, 130);
  place(party, 330);
  return out;
}

/** เหตุการณ์ที่ยังค้างคิวอยู่กี่อัน — 0 = อนิเมชันเล่นจบแล้ว
 *  หน้าเว็บ/เทสใช้เช็คว่ายังเล่นอยู่ไหม (ส่วนหนึ่งของสัญญา renderer)
 */
function pbPending() {
  return PB.queue.length + (PB.wait > 0 ? 1 : 0);
}

function pbClick(ev) {
  const r = PB.cv.getBoundingClientRect();
  const x = (ev.clientX - r.left) * (PB.cv.width / r.width);
  const y = (ev.clientY - r.top) * (PB.cv.height / r.height);
  const slots = pbSlots();
  for (const [id, s] of Object.entries(slots)) {
    if (Math.abs(x - s.x) < 55 && Math.abs(y - s.y) < 55) {
      // ⚠️ ห้ามตัดคนที่ล้มทิ้งตรงนี้ — ท่าชุบต้องเล็งคนที่ล้มเท่านั้น
      //    renderer ไม่รู้กติกา ส่งต่อให้คนเรียกตัดสิน (เจอบั๊กนี้ตอนเฟส 6)
      if (typeof onPartyPick === 'function') onPartyPick(id, s.u.side, s.u.alive);
      return;
    }
  }
}

/** ตัดชื่อให้สั้นแบบ **นับอักขระจริง** ไม่ใช่นับหน่วย UTF-16
 *  slice() ธรรมดาผ่ากลางอิโมจิได้ (อิโมจิ 1 ตัว = 2 หน่วย) แล้วขึ้น � บนจอ */
function pbShortName(name) {
  const c = [...String(name || '')];
  return c.length > 14 ? c.slice(0, 14).join('') : c.join('');
}

/** สัดส่วนเลือดตามสถานะล่าสุดจากเซิร์ฟเวอร์ */
function pbFrac(u) {
  return u.side === 'party'
    ? Math.max(0, u.hp) / Math.max(1, u.hp_max)
    : Math.max(0, u.hp_pct || 0) / 100;
}

/** ปล่อยให้แถบเลือดของหน่วยพวกนี้ไล่ตามสถานะล่าสุด */
function pbRelease(ids) {
  for (const u of PB.units) {
    if (ids.includes(u.id)) PB.hpT[u.id] = pbFrac(u);
  }
}

/** สัดส่วนเลือดที่ "กำลังวาด" ของหน่วยนี้ (0-1)
 *
 * ⚠️ เส้นทางวาดต้องเรียกฟังก์ชันนี้ **ตัวเดียว** ห้ามคำนวณเองซ้ำ
 *    ไม่งั้นเทสอ่านค่าจากที่หนึ่งแต่จอวาดอีกค่าหนึ่ง จับบั๊กไม่ได้
 */
function pbHpShown(id) {
  const u = (PB.units || []).find(x => x.id === id);
  if (!u) return null;
  if (PB.hpT[id] === undefined) PB.hpT[id] = pbFrac(u);
  return PB.hpT[id];
}

function pbDraw() {
  const c = PB.ctx;
  if (!c) return;
  pbStep();
  const sx = PB.shake ? (Math.random() - 0.5) * PB.shake : 0;
  const sy = PB.shake ? (Math.random() - 0.5) * PB.shake : 0;
  if (PB.shake > 0) PB.shake -= 0.6;

  c.save();
  c.translate(sx, sy);

  // พื้นหลัง
  const g = c.createLinearGradient(0, 0, 0, 420);
  g.addColorStop(0, '#141824');
  g.addColorStop(1, '#0c0f16');
  c.fillStyle = g;
  c.fillRect(-20, -20, 940, 460);

  const slots = pbSlots();
  const turnOf = PB.state && PB.state.turn_of;

  for (const [id, s] of Object.entries(slots)) {
    const u = s.u;
    const col = PB_COLORS[u.element] || PB_COLORS.null;

    // วงไฟใต้เท้าคนที่ถึงตา
    if (id === turnOf) {
      c.beginPath();
      c.ellipse(s.x, s.y + 46, 46, 13, 0, 0, Math.PI * 2);
      c.fillStyle = 'rgba(255,211,74,.28)';
      c.fill();
    }

    // ตัวละคร (กล่องสีธาตุ — เฟส 7 จะเปลี่ยนเป็นสไปรต์)
    // บอสตัวใหญ่กว่า ผู้เล่นจะได้รู้ทันทีว่าตัวไหนต้องระวัง
    const w = u.boss ? 48 : 34;
    c.globalAlpha = u.alive ? 1 : 0.3;
    c.fillStyle = col;
    c.beginPath();
    c.roundRect(s.x - w, s.y - 40, w * 2, 80, 12);
    c.fill();
    if (u.boss) {
      c.globalAlpha = 1;
      c.font = '18px system-ui';
      c.textAlign = 'center';
      c.fillText('👑', s.x, s.y - 46);
    }

    // ชื่อ
    c.globalAlpha = 1;
    c.fillStyle = u.alive ? '#e9edf5' : '#6b7280';
    c.font = '13px system-ui, sans-serif';
    c.textAlign = 'center';
    c.fillText(pbShortName(u.name), s.x, s.y + 60);

    // แถบเลือด — ผู้เล่นเห็นตัวเลข มอนเห็นแค่แถบ (เซิร์ฟเวอร์ไม่ส่ง hp จริงของมอน)
    // ⚠️ ใช้เป้าหมายที่เหตุการณ์ตั้งไว้ ไม่ใช่สถานะดิบ ไม่งั้นเลือดลดก่อนทอยเต๋า
    const pct = pbHpShown(u.id);
    c.fillStyle = '#2a2f3d';
    c.fillRect(s.x - w, s.y - 54, w * 2, 7);
    c.fillStyle = pct > 0.5 ? '#5bd67d' : pct > 0.2 ? '#ffd34a' : '#ff5252';
    c.fillRect(s.x - w, s.y - 54, w * 2 * pct, 7);

    if (u.side === 'party') {
      c.fillStyle = '#9aa4b2';
      c.font = '11px system-ui, sans-serif';
      c.fillText(`${u.hp}/${u.hp_max}`, s.x, s.y - 58);
    }
    if (u.defending) {
      c.font = '16px system-ui';
      c.fillText('🛡️', s.x + 30, s.y - 40);
    }
  }

  // จอทอยเต๋าแข่ง
  if (PB.duel) {
    const d = PB.duel;
    d.t += 1;
    if (d.t > 42) {
      PB.duel = null;
    } else {
      const spin = d.t < 18;
      c.fillStyle = 'rgba(8,10,16,.72)';
      c.fillRect(300, 170, 300, 80);
      c.textAlign = 'center';
      if (d.evaded) {
        c.fillStyle = '#9df0e4';
        c.font = 'bold 20px system-ui, sans-serif';
        c.fillText('💨 หลบได้!', 450, 215);
      } else {
        const a = spin ? 1 + Math.floor(Math.random() * 20) : d.atk;
        const b = spin ? 1 + Math.floor(Math.random() * 20) : d.def;
        c.font = 'bold 26px system-ui, sans-serif';
        c.fillStyle = !spin && d.hit ? '#ffd34a' : '#e9edf5';
        c.fillText(String(a), 380, 212);
        c.fillStyle = !spin && !d.hit ? '#ffd34a' : '#e9edf5';
        c.fillText(String(b), 520, 212);
        c.fillStyle = '#9aa4b2';
        c.font = 'bold 15px system-ui, sans-serif';
        c.fillText('VS', 450, 210);
        if (!spin) {
          c.font = '13px system-ui, sans-serif';
          c.fillText(d.hit ? '⚔️ โจมตีเข้า!' : '🛡️ ป้องกันไว้ได้', 450, 238);
        }
      }
    }
  }

  // ป้ายเตือนท่าใหญ่ — ค้างจนกว่าบอสจะปล่อยท่า
  if (PB.warn) {
    c.fillStyle = 'rgba(220,38,38,.85)';
    c.fillRect(0, 0, 900, 34);
    c.fillStyle = '#fff';
    c.font = 'bold 16px system-ui, sans-serif';
    c.textAlign = 'center';
    c.fillText(`⚠️ กำลังร่ายท่าใหญ่: ${PB.warn.move} — ตาหน้าโดนทั้งปาร์ตี้!`, 450, 23);
  }

  // เลขดาเมจลอย
  for (const p of PB.pops) {
    const s = slots[p.id];
    if (!s) continue;
    p.dy += 0.7;
    p.life -= 1;
    c.globalAlpha = Math.max(0, p.life / 60);
    c.fillStyle = p.color;
    c.font = `bold ${p.big ? 26 : 19}px system-ui, sans-serif`;
    c.textAlign = 'center';
    c.fillText(p.text, s.x, s.y - 60 - p.dy);
  }
  c.globalAlpha = 1;
  PB.pops = PB.pops.filter(p => p.life > 0);

  c.restore();
}

function pbLoop() {
  if (PB.raf) return;
  const tick = () => {
    pbDraw();
    if (PB.pops.length || PB.shake > 0 || PB.queue.length || PB.wait > 0
        || (PB.duel && PB.duel.t < 42)) {
      PB.raf = requestAnimationFrame(tick);
    } else {
      PB.raf = null;
      pbDraw();
    }
  };
  PB.raf = requestAnimationFrame(tick);
}
