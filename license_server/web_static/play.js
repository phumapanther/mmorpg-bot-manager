// หน้าเล่นเกม — โครงเมนู (เฟสวางโครง 2026-08-13)
// ⚠️ ยังไม่เชื่อมข้อมูลจริง: ตัวเลข/รายการในนี้เป็นตัวอย่างเพื่อวางเลย์เอาต์
//    ของจริงจะดึงจาก GET /api/web/me/game (เฟส 1.1) แล้วให้เซิร์ฟเวอร์เป็นคนคำนวณทุกอย่าง
renderChrome("/play");
fillDiscordInvite();

// ── สไปรต์ตัวละครแบบย่อ (ตัวเต็มมาเฟส 1.2) ──
const SPRITE = [
  '....111111....','...1ssssss1...','...1ssssss1...','...1sessse1...','...1ssssss1...',
  '....1ssss1....','...1AAAAAA1...','..1AAAAAAAA1..','..1AAAAAAAA1..','..1aAAAAAAa1..',
  '..1AAAAAAAA1..','...1AAAAAA1...','...1PP11PP1...','...1PP..PP1...','..1PPP..PPP1..'];
const SPAL = { '1':'#241812','s':'#f2c9a0','e':'#241812','A':'#d93b2b','a':'#8f2317','P':'#3d2b1c' };

function drawSprite(cv) {
  const ctx = cv.getContext('2d'), s = 3;
  ctx.clearRect(0, 0, cv.width, cv.height);
  SPRITE.forEach((row, r) => [...row].forEach((ch, c) => {
    const col = SPAL[ch];
    if (col) { ctx.fillStyle = col; ctx.fillRect(c * s, 8 + r * s, s, s); }
  }));
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

  // สีชุดบนสไปรต์เปลี่ยนตามเกราะที่สวมจริง (ตัวเต็มมาเฟส 1.2)
  const tint = { Steel_H: ['#d5dce4', '#8b949e'], Steel_L: ['#b9c2cc', '#79838d'],
                 Leather_H: ['#8a5c30', '#573a1e'], Leather_L: ['#a4703c', '#6d4823'] };
  const t = tint[g.gear.armor.key];
  if (t) { SPAL.A = t[0]; SPAL.a = t[1]; }
  drawSprite(document.getElementById('pfp'));
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
