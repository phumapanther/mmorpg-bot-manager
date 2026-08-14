// หน้าเล่นเกม Fragment Rift
// ตัวละคร/กระเป๋า/ธนาคาร/ทองคำแท่ง/คราฟ = ข้อมูลจริง เรียกฟังก์ชันชุดเดียวกับบอทดิส
// ร้านยศ/กาชา/ทอยเต๋า = ยังเป็นโครงหน้า (เฟส 7-8)
// กติกา: ไม่มีกฎเกมในไฟล์นี้ — เซิร์ฟเวอร์คำนวณทุกอย่าง ที่นี่แค่วาดกับถามยืนยัน
renderChrome("/play");
fillDiscordInvite();

// ── สไปรต์ตัวละคร (เฟส 1.2 — เอนจินอยู่ใน sprite.js) ──
let LAST = null;                 // ข้อมูลตัวละครล่าสุดจาก API
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
  if (id === 'bank') fillQuick();
  if (id === 'goldbar') fillBars().catch(e => toast(e.message, true));
  if (id === 'craft') fillCraft();
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

  // % คิดมาจากเซิร์ฟเวอร์ด้วยสูตรเดียวกับที่เกมใช้อัปเลเวลจริง
  document.getElementById('prExp').style.width = (id.exp_pct ?? 0) + '%';
  document.getElementById('prExpIn').textContent = id.max_level
    ? 'เลเวลเต็ม' : fmt(id.exp) + ' / ' + fmt(id.exp_required);
  document.getElementById('prExpTxt').textContent = id.max_level
    ? 'Lv ' + id.level + ' MAX' : 'Lv ' + (id.level ?? '—') + ' · ' + (id.exp_pct ?? 0) + '%';

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
  box.innerHTML = bag.items.map((it, i) => `
    <div class="item${it.usable ? ' use' : ''}">
      ${it.usable ? '<span class="badge">กดใช้ได้</span>' : ''}
      <span class="nm">${esc(it.name)}</span><span class="qty">×${it.count}</span>
      <span class="row-btns">
        ${it.usable ? `<button class="use-btn" data-use="${i}">ใช้</button>` : ''}
        <button class="drop-btn" data-drop="${i}">ทิ้ง</button>
      </span>
    </div>`).join('');
  box.querySelectorAll('[data-use]').forEach(b => b.onclick = () => {
    const it = bag.items[+b.dataset.use];
    useItem(it.id, it.name);
  });
  box.querySelectorAll('[data-drop]').forEach(b => b.onclick = () => {
    const it = bag.items[+b.dataset.drop];
    dropItem(it.id, it.name, it.count, it.sell);
  });
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
    LAST = g;
    paint(g);
  })
  .catch(() => document.getElementById('needLogin').classList.remove('hidden'));


// ══════ เฟส 2: ธุรกรรมจริง — ทุกรายการต้องยืนยันก่อนเสมอ (กันกดผิด) ══════

/** หน้าต่างยืนยัน — คืน true เมื่อกดยืนยัน
 *  lines: [[ป้าย, ค่า, สไตล์('warn'|'good'|'')]] บอกผลลัพธ์ที่จะเกิดขึ้นจริง */
function confirmAction({ title, message, lines, okText }) {
  return new Promise(resolve => {
    const wrap = document.getElementById('confirmWrap');
    document.getElementById('cfTitle').textContent = title;
    document.getElementById('cfMsg').textContent = message || '';
    document.getElementById('cfLines').innerHTML = (lines || [])
      .map(([k, v, cls]) => '<div class="' + (cls || '') + '"><span>' + esc(k) +
                            '</span><b>' + esc(v) + '</b></div>').join('');
    const yes = document.getElementById('cfYes'), no = document.getElementById('cfNo');
    yes.textContent = okText || 'ยืนยัน';
    yes.disabled = false;
    wrap.classList.add('on');
    yes.focus();

    const onKey = e => { if (e.key === 'Escape') done(false); };
    function done(ok) {
      wrap.classList.remove('on');
      yes.onclick = no.onclick = wrap.onclick = null;
      document.removeEventListener('keydown', onKey);
      resolve(ok);
    }
    yes.onclick = () => { yes.disabled = true; done(true); };
    no.onclick = () => done(false);
    wrap.onclick = e => { if (e.target === wrap) done(false); };   // คลิกนอกกล่อง = ยกเลิก
    document.addEventListener('keydown', onKey);
  });
}

function toast(msg, bad) {
  const t = document.getElementById('toast');
  t.textContent = msg;
  t.classList.toggle('bad', !!bad);
  t.classList.add('on');
  clearTimeout(toast._t);
  toast._t = setTimeout(() => t.classList.remove('on'), 4200);
}

async function reload() {
  const g = await api("GET", "/api/web/me/game");
  if (!g.new_player) { LAST = g; paint(g); }
}

// ── ธนาคาร ──
const BANK_LABEL = { deposit: 'ฝากเงิน', withdraw: 'ถอนเงิน', transfer: 'โอนเงิน' };

document.querySelectorAll('[data-bank]').forEach(btn => btn.addEventListener('click', async () => {
  const action = btn.dataset.bank;
  document.getElementById('bankTargetRow').style.display = action === 'transfer' ? '' : 'none';

  const amount = parseInt(document.getElementById('bankAmt').value, 10);
  const target = document.getElementById('bankTarget').value.trim();
  if (!(amount > 0)) return toast('ใส่จำนวนเงินก่อนนะครับ', true);
  if (action === 'transfer' && !/^\d+$/.test(target))
    return toast('ใส่ไอดี Discord ของผู้รับเป็นตัวเลข แล้วกดโอนอีกครั้ง', true);

  // ถามค่าธรรมเนียมจากเซิร์ฟเวอร์ — ไม่คำนวณเองเพราะจะเพี้ยนจากของจริง
  let fee;
  try { fee = await api("GET", "/api/web/bank/fee?amount=" + amount); }
  catch (e) { return toast(e.message, true); }

  const netLabel = action === 'deposit' ? 'เข้าธนาคารจริง'
                 : action === 'withdraw' ? 'ได้รับจริง' : 'ผู้รับได้จริง';
  const lines = [
    ['จำนวนที่ทำรายการ', fmt(fee.amount) + ' ทอง'],
    ['ค่าธรรมเนียม ' + fee.pct + '%', '-' + fmt(fee.fee) + ' ทอง', 'warn'],
    [netLabel, fmt(fee.net) + ' ทอง', 'good'],
  ];
  if (action === 'transfer') lines.push(['ไอดีผู้รับ', target]);

  const ok = await confirmAction({
    title: '🏦 ยืนยัน' + BANK_LABEL[action],
    message: 'ตรวจตัวเลขให้ดีก่อนนะครับ — ทำรายการแล้วย้อนกลับไม่ได้',
    lines, okText: 'ยืนยัน' + BANK_LABEL[action],
  });
  if (!ok) return;

  try {
    const r = await api("POST", "/api/web/bank", { action: action, amount: amount, target_id: target });
    toast(r.message, !r.ok);
    if (r.ok) { document.getElementById('bankAmt').value = ''; await reload(); }
  } catch (e) { toast(e.message, true); }
}));

// ปุ่มลัดจำนวนเงิน — อิงยอดที่มีจริง
function fillQuick() {
  const box = document.getElementById('bankQuick');
  if (!box || !LAST) return;
  const cash = LAST.money.cash, bank = LAST.money.bank;
  const preset = [10000, 100000, 1000000].filter(v => v <= Math.max(cash, bank));
  box.innerHTML = preset.map(v => '<button data-amt="' + v + '">' + fmt(v) + '</button>').join('')
    + '<button data-amt="' + cash + '">เงินสดทั้งหมด</button>'
    + '<button data-amt="' + bank + '">ในธนาคารทั้งหมด</button>';
  box.querySelectorAll('button').forEach(b => b.onclick = () => {
    document.getElementById('bankAmt').value = b.dataset.amt;
  });
}

// ── ทองคำแท่ง ──
async function fillBars() {
  const box = document.getElementById('barList');
  if (!box || box.dataset.ready) return;
  const d = await api("GET", "/api/web/goldbar/prices");
  box.dataset.ready = '1';
  box.innerHTML = d.bars.map(b =>
    '<div class="bar-card">' +
      '<div class="bn">' + esc(b.name) + '</div>' +
      '<div class="px"><span>ซื้อ (หักจากธนาคาร)</span><b>' + fmt(b.buy) + '</b></div>' +
      '<div class="px"><span>ขายคืน (เข้าธนาคาร)</span><b>' + fmt(b.sell) + '</b></div>' +
      '<div class="btns"><button data-bar-buy="' + b.id + '">ซื้อ</button>' +
      '<button data-bar-sell="' + b.id + '">ขายคืน</button></div>' +
    '</div>').join('');

  const run = async (id, action) => {
    const b = d.bars.find(x => x.id === id);
    const buying = action === 'buy';
    const ok = await confirmAction({
      title: buying ? '🧈 ยืนยันซื้อทองคำแท่ง' : '🧈 ยืนยันขายคืนทองคำแท่ง',
      message: buying ? 'แท่งทองจะเข้ากระเป๋า และมีโอกาสถูกโจรฉกระหว่างผจญภัย'
                      : 'แท่งทองจะหายจากกระเป๋า เงินเข้าธนาคาร',
      lines: buying
        ? [['ได้รับ', b.name], ['หักจากธนาคาร', fmt(b.buy) + ' ทอง', 'warn'],
           ['มูลค่าหน้าแท่ง', fmt(b.face) + ' ทอง'],
           ['ค่าธรรมเนียม ' + d.fee_pct + '%', '-' + fmt(b.buy - b.face) + ' ทอง', 'warn']]
        : [['ขาย', b.name], ['ได้รับเข้าธนาคาร', fmt(b.sell) + ' ทอง', 'good'],
           ['ค่าธรรมเนียม ' + d.fee_pct + '%', '-' + fmt(b.face - b.sell) + ' ทอง', 'warn']],
      okText: buying ? 'ยืนยันซื้อ' : 'ยืนยันขายคืน',
    });
    if (!ok) return;
    try {
      const r = await api("POST", "/api/web/goldbar", { action: action, item_id: id });
      toast(r.message, !r.ok);
      if (r.ok) await reload();
    } catch (e) { toast(e.message, true); }
  };
  box.querySelectorAll('[data-bar-buy]').forEach(b => b.onclick = () => run(b.dataset.barBuy, 'buy'));
  box.querySelectorAll('[data-bar-sell]').forEach(b => b.onclick = () => run(b.dataset.barSell, 'sell'));
}

// ── ใช้ไอเทมจากกระเป๋า ──
async function useItem(id, name) {
  const ok = await confirmAction({
    title: '🧪 ยืนยันใช้ไอเทม',
    message: 'ไอเทมจะถูกใช้ทันทีและหายจากกระเป๋า 1 ชิ้น',
    lines: [['ไอเทม', name], ['ใช้ไป', '1 ชิ้น', 'warn']],
    okText: 'ยืนยันใช้',
  });
  if (!ok) return;
  try {
    const r = await api("POST", "/api/web/item/use", { item_id: id });
    toast(r.message, !r.ok);
    if (r.ok) await reload();
  } catch (e) { toast(e.message, true); }
}


// ── คราฟของ ──
async function fillCraft() {
  const box = document.getElementById('craftList');
  if (!box) return;
  let d;
  try { d = await api("GET", "/api/web/craft/list"); }
  catch (e) { return toast(e.message, true); }

  if (!d.recipes.length) {
    box.innerHTML = '<div class="empty-bag">ยังไม่มีสูตรไหนที่วัตถุดิบครบ — ' +
                    'ออกผจญภัยเก็บวัสดุเพิ่มก่อนนะ</div>';
    return;
  }
  box.innerHTML = d.recipes.map(r =>
    '<div class="bar-card">' +
      '<div class="bn">' + esc(r.name) + '</div>' +
      '<div class="px"><span>ใช้วัตถุดิบ</span></div>' +
      '<div style="font-size:12.5px;color:var(--g-muted)">' + esc(r.materials) + '</div>' +
      '<div class="btns"><button data-craft="' + esc(r.id) + '">คราฟ</button></div>' +
    '</div>').join('');

  box.querySelectorAll('[data-craft]').forEach(btn => btn.onclick = async () => {
    const r = d.recipes.find(x => String(x.id) === btn.dataset.craft);
    const ok = await confirmAction({
      title: '🔨 ยืนยันคราฟของ',
      message: 'คราฟมีโอกาสล้มเหลว — ล้มเหลวแล้ววัตถุดิบหายไปเลย ไม่ได้ของ',
      lines: [['จะได้', r.name], ['ใช้วัตถุดิบ', r.materials, 'warn']],
      okText: 'ยืนยันคราฟ',
    });
    if (!ok) return;
    try {
      const res = await api("POST", "/api/web/craft", { item_id: r.id });
      toast(res.message, !res.ok);
      await reload();
      await fillCraft();                      // วัตถุดิบเปลี่ยน รายการสูตรก็เปลี่ยน
    } catch (e) { toast(e.message, true); }
  });
}

// ── เทขายวัสดุทั้งกระเป๋า ──
const junkTile = document.getElementById('tileJunk');
if (junkTile) junkTile.addEventListener('click', async () => {
  let pre;
  try { pre = await api("GET", "/api/web/bag/junk-preview"); }
  catch (e) { return toast(e.message, true); }
  if (!pre.count) return toast('ไม่มีวัสดุ/ของขยะให้ขายในกระเป๋า', true);

  const lines = pre.items.slice(0, 6)
    .map(i => [i.name + ' ×' + i.count, fmt(i.each * i.count) + ' ทอง']);
  if (pre.items.length > 6) lines.push(['และอีก ' + (pre.items.length - 6) + ' ชนิด', '...']);
  lines.push(['รวมได้รับ', fmt(pre.gold) + ' ทอง', 'good']);

  const ok = await confirmAction({
    title: '🧱 ยืนยันขายวัสดุทั้งหมด',
    message: 'ขาย ' + pre.count + ' ชิ้น — ของกดใช้ได้ อุปกรณ์สวมใส่ และทองคำแท่ง จะไม่ถูกขาย',
    lines, okText: 'ยืนยันขายทั้งหมด',
  });
  if (!ok) return;
  try {
    const r = await api("POST", "/api/web/bag/sell-junk");
    toast(r.message, !r.ok);
    if (r.ok) await reload();
  } catch (e) { toast(e.message, true); }
});

/** ทิ้งไอเทม — เตือนแรงกว่าใช้ เพราะของหายถาวรและไม่ได้เงินคืน */
async function dropItem(id, name, count, sell) {
  const lines = [['ไอเทม', name], ['มีอยู่', count + ' ชิ้น'], ['ทิ้ง', '1 ชิ้น', 'warn']];
  if (sell > 0) lines.push(['ถ้าเอาไปขายจะได้', fmt(sell) + ' ทอง/ชิ้น', 'good']);
  const ok = await confirmAction({
    title: '🗑️ ยืนยันทิ้งไอเทม',
    message: 'ของจะหายถาวรและไม่ได้เงินคืน — กู้กลับไม่ได้',
    lines, okText: 'ยืนยันทิ้ง',
  });
  if (!ok) return;
  try {
    const r = await api("POST", "/api/web/item/drop", { item_id: id, amount: 1 });
    toast(r.message, !r.ok);
    if (r.ok) await reload();
  } catch (e) { toast(e.message, true); }
}
