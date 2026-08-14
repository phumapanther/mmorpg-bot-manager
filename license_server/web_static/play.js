// หน้าเล่นเกม — โครงเมนู (เฟสวางโครง 2026-08-13)
// ⚠️ ยังไม่เชื่อมข้อมูลจริง: ตัวเลข/รายการในนี้เป็นตัวอย่างเพื่อวางเลย์เอาต์
//    ของจริงจะดึงจาก GET /api/web/me/game (เฟส 1.1) แล้วให้เซิร์ฟเวอร์เป็นคนคำนวณทุกอย่าง
renderChrome("/play");
fillDiscordInvite();

// ── สไปรต์ตัวละคร (เฟส 1.2 — เอนจินอยู่ใน sprite.js) ──
let CHAR = { race: null, cls: null, armor: 'None', weapon: null, pose: 'idle' };

function drawSprite(cv, scale) {
  const ctx = cv.getContext('2d');
  ctx.clearRect(0, 0, cv.width, cv.height);
  const s = scale || Math.max(1, Math.floor(cv.width / 18));
  drawCharacter(ctx, (cv.width - 16 * s) / 2, 2, s, CHAR);
}

// ── สลับแผง ──
function showPanel(id) {
  document.querySelectorAll('.g-panelview').forEach(v => v.classList.toggle('on', v.id === 'v-' + id));
  window.scrollTo({ top: document.getElementById('shell').offsetTop - 80, behavior: 'smooth' });
}
document.querySelectorAll('[data-go]').forEach(b => {
  if (b.classList.contains('soon')) return;
  b.addEventListener('click', () => showPanel(b.dataset.go));
});
document.querySelectorAll('[data-back]').forEach(b =>
  b.addEventListener('click', () => showPanel('home')));

// ── ตัวอย่างรายการยศ (เฟส 7 จะดึงจาก auto_trade_roles จริง) ──
const DEMO_ROLES = [
  { n: '♆ Maou-sama ⚓️', p: 300000000, c: '#8f2317' },
  { n: '💀 NECROMANCER', p: 100000000, c: '#5b3a8f' },
  { n: '👹 Giant-King', p: 50000000, c: '#8f5a17' },
  { n: '🕯️ Asmodeus', p: 20000000, c: '#2f6d84' },
];
document.getElementById('roleList').innerHTML = DEMO_ROLES.map(r => `
  <div class="role-card" style="--rc:${r.c}">
    <div class="rn">${esc(r.n)}</div>
    <div class="rp">${r.p.toLocaleString()} ทอง</div>
    <button disabled style="opacity:.5;cursor:not-allowed">ยังเปิดไม่ได้ (เฟส 7)</button>
  </div>`).join('');
document.getElementById('gachaPrice').textContent = '10,000,000 ทอง/ครั้ง';

// ── กระดานทอยเต๋า: วาดช่องตัวอย่าง (เฟส 8 จะสร้างจากธีมสัปดาห์จริง) ──
const TILES = ['🏁','🪙','💉','🌟','🪙','🧭','📦','🪙','🧪','🎁','🪙','🛠️','🌟','🪙','💎','🪙',
               '🧱','🪙','💉','🎁','🪙','🧭','🪙','🏆'];
document.getElementById('board').innerHTML = TILES.map((t, i) => {
  const cls = i === 0 ? 'sq start' : (t === '🏆' || t === '💎' ? 'sq big' : 'sq');
  return `<div class="${cls}">${t}${i === 0 ? '<i class="me"></i>' : ''}</div>`;
}).join('');

document.getElementById('rollBtn').addEventListener('click', () =>
  alert('ยังทอยไม่ได้ครับ — ระบบนี้อยู่ในเฟส 8 ของแผน\nตอนนี้เป็นการวางโครงหน้าเท่านั้น'));
document.getElementById('gachaBtn').addEventListener('click', () =>
  alert('ยังหมุนไม่ได้ครับ — ระบบนี้อยู่ในเฟส 7 ของแผน\nตอนนี้เป็นการวางโครงหน้าเท่านั้น'));

// ── โหลดตัวละครจริง (เฟส 1.1) ──
// ทุกค่าที่ใช้แสดงผลถูกแปลงมาจากฝั่งเซิร์ฟเวอร์แล้ว — ตรงนี้แค่วางลงหน้าจอ
const fmt = n => Number(n || 0).toLocaleString();

// ถ้าค้างอะไรอยู่ในดิส ต้องบอกให้รู้ (กติกาสองแพลตฟอร์ม)
const STATE_NOTE = {
  fighting: '⚔️ กำลังสู้มอนอยู่ในดิส',
  village: '🏡 อยู่ในหมู่บ้าน',
  trap_defense: '⚠️ ติดกับดักอยู่',
  treasure_choice: '📦 ยืนอยู่หน้าหีบสมบัติ',
  npc_choice: '🧓 กำลังคุยกับ NPC',
  dungeon_choice: '🚪 ยืนอยู่ปากดันเจี้ยน',
  arrested: '🚓 ติดคุกอยู่',
};

function paint(g) {
  const id = g.identity, v = g.vitals, m = g.money;
  document.getElementById('pName').textContent = id.title || 'นักผจญภัย';
  document.getElementById('pLv').textContent = 'Lv ' + (id.level ?? '—');
  const bits = [id.race, id.class_name, id.continent_label].filter(Boolean);
  const note = STATE_NOTE[v.state];
  document.getElementById('pSub').innerHTML =
    esc(bits.join(' · ')) + (note ? ' <span style="color:var(--g-gold)">· ' + esc(note) + '</span>' : '');
  document.getElementById('pCash').textContent = fmt(m.cash);
  document.getElementById('pBank').textContent = fmt(m.bank);

  // ตัวละครประกอบจากของที่สวมจริง — เผ่า/คลาส/เกราะ/อาวุธ มาจาก DB ทั้งหมด
  CHAR = { race: id.race, cls: id.class_name,
           armor: g.gear.armor.key, weapon: g.gear.weapon.key, pose: 'idle' };
  drawSprite(document.getElementById('pfp'));
  paintProfile(g);
  paintBag(g.bag);
}

// ── โปรไฟล์ (เฟส 1.3) ──
function paintProfile(g) {
  const id = g.identity, v = g.vitals, gear = g.gear;
  document.getElementById('prName').textContent = id.title || 'นักผจญภัย';
  document.getElementById('prRace').textContent =
    [id.race, id.class_name].filter(Boolean).join(' · ') || 'ยังไม่มีเผ่า/คลาส';

  const hp = v.hp ?? 0, mx = v.max_hp || 1, pct = Math.max(0, Math.min(100, hp / mx * 100));
  document.getElementById('prHp').style.width = pct + '%';
  document.getElementById('prHpIn').textContent = fmt(hp) + ' / ' + fmt(mx);
  document.getElementById('prHpTxt').textContent = Math.round(pct) + '%';

  // เกมนับ EXP สะสมรวม ไม่ได้รีเซ็ตต่อเลเวล — โชว์ยอดสะสมตรงๆ ไม่ปั้นสูตรเอง
  document.getElementById('prExp').style.width = '100%';
  document.getElementById('prExpIn').textContent = fmt(id.exp) + ' EXP';
  document.getElementById('prExpTxt').textContent = 'Lv ' + (id.level ?? '—');

  document.getElementById('prRank').textContent = id.rank || '—';
  document.getElementById('prSan').textContent = fmt(v.sanity);
  document.getElementById('prCont').textContent = id.continent_label || '—';
  document.getElementById('prArt').textContent = (gear.artifact_slots ?? 1) + ' ช่อง';

  const durBar = d => d == null ? '' :
    `<div class="dur${d < 30 ? ' low' : ''}"><i style="width:${Math.max(0, Math.min(100, d))}%"></i></div>`;
  document.getElementById('prGear').innerHTML = `
    <div class="slot-card"><div class="ic">🛡️</div><div style="min-width:0">
      <div class="t">เกราะ</div><div class="v">${esc(gear.armor.name)}</div>${durBar(gear.armor.dur)}</div></div>
    <div class="slot-card"><div class="ic">⚔️</div><div style="min-width:0">
      <div class="t">อาวุธ</div><div class="v">${esc(gear.weapon.name)}</div>${durBar(gear.weapon.dur)}</div></div>`;

  const bf = document.getElementById('prBuffs');
  document.getElementById('prBuffCard').style.display = g.buffs.length ? '' : 'none';
  bf.innerHTML = g.buffs.map(b =>
    `<span>${esc(b.label)} ${b.no_tick ? '<b>ค้างไว้</b>' : `<b>${b.turns}</b> ${esc(b.unit)}`}</span>`).join('');

  const big = document.getElementById('bigChar');
  const ctx = big.getContext('2d');
  ctx.clearRect(0, 0, big.width, big.height);
  drawCharacter(ctx, (big.width - 16 * 8) / 2, 4, 8, CHAR);   // ตัวใหญ่ ×8
}

// ── กระเป๋า (เฟส 1.3) ──
function paintBag(bag) {
  const cap = bag.capacity || 0, used = bag.used || 0;
  document.getElementById('bagCap').style.width =
    (cap ? Math.min(100, used / cap * 100) : 0) + '%';
  document.getElementById('bagCapTxt').textContent = cap ? `${used} / ${cap}` : `${used} (ไม่จำกัด)`;
  const box = document.getElementById('bagItems');
  if (!bag.items.length) {
    box.innerHTML = '<div class="empty-bag">กระเป๋าว่างเปล่า — ออกผจญภัยเก็บของก่อนนะ</div>';
    return;
  }
  box.innerHTML = bag.items.map(it => `
    <div class="item${it.usable ? ' use' : ''}">
      ${it.usable ? '<span class="badge">กดใช้ได้</span>' : ''}
      <span class="nm">${esc(it.name)}</span><span class="qty">×${it.count}</span>
    </div>`).join('');
}

api("GET", "/api/web/me/session")
  .then(() => api("GET", "/api/web/me/game"))
  .then(g => {
    document.getElementById('shell').classList.remove('hidden');
    if (g.new_player) {
      document.getElementById('pName').textContent = 'ยังไม่มีตัวละคร';
      document.getElementById('pSub').innerHTML =
        'พิมพ์ <b>!play</b> ในเซิร์ฟ Discord เพื่อสร้างตัวละครก่อน';
      drawSprite(document.getElementById('pfp'));
      return;
    }
    paint(g);
  })
  .catch(() => document.getElementById('needLogin').classList.remove('hidden'));
