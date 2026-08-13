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

// ── ต้องล็อกอินก่อนถึงเห็นเมนู ──
api("GET", "/api/web/me/session")
  .then(() => {
    document.getElementById('shell').classList.remove('hidden');
    drawSprite(document.getElementById('pfp'));
    // ⚠️ ชั่วคราว: ของจริงเรียก /api/web/me/game (เฟส 1.1)
    document.getElementById('pName').textContent = 'ตัวละครของคุณ';
    document.getElementById('pLv').textContent = 'Lv —';
    document.getElementById('pSub').textContent = 'ยังไม่ได้เชื่อมข้อมูลตัวละคร — มาในเฟส 1';
    document.getElementById('pCash').textContent = '—';
    document.getElementById('pBank').textContent = '—';
  })
  .catch(() => document.getElementById('needLogin').classList.remove('hidden'));
