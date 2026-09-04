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
  raf: null,
};

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

/** เล่นเหตุการณ์ที่เพิ่งเกิด — แปลงเป็นเลขลอย/สั่นจอ */
function pbPlay(events) {
  for (const e of events || []) {
    if (e.t === 'attack') {
      pbPop(e.to, `-${e.dmg}`, e.crit ? '#ffd34a' : '#ff7a7a', e.crit);
      PB.shake = e.crit ? 10 : 5;
    } else if (e.t === 'aoe') {
      (e.targets || []).forEach((id, i) => pbPop(id, `-${e.dmgs[i]}`, '#ff9a5a'));
      PB.shake = 8;
    } else if (e.t === 'heal') {
      pbPop(e.to, `+${e.amount}`, '#6ee7a0');
    } else if (e.t === 'miss') {
      pbPop(e.to, 'พลาด!', '#9aa4b2');
    } else if (e.t === 'die') {
      pbPop(e.who, '💀', '#ff5252', true);
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
  pbLoop();
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

function pbDraw() {
  const c = PB.ctx;
  if (!c) return;
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
    const pct = u.side === 'party'
      ? Math.max(0, u.hp) / Math.max(1, u.hp_max)
      : (u.hp_pct || 0) / 100;
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
    if (PB.pops.length || PB.shake > 0) {
      PB.raf = requestAnimationFrame(tick);
    } else {
      PB.raf = null;
      pbDraw();
    }
  };
  PB.raf = requestAnimationFrame(tick);
}
