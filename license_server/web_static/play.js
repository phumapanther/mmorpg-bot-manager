// หน้าเล่นเกม Fragment Rift
// ตัวละคร/กระเป๋า/ธนาคาร/ทองคำแท่ง/คราฟ/ร้านค้า/คาสิโน = ข้อมูลจริง เรียกฟังก์ชันชุดเดียวกับบอทดิส
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
  if (id === 'shop') fillShop();
  if (id === 'slots' || id === 'hilo' || id === 'bj') buildChips();
  if (id === 'bj') bjRestore();
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
  // การ์ดของ = ปุ่มเดียวทั้งใบ กดแล้วค่อยเลือกว่าจะใช้หรือทิ้ง
  // (เดิมแปะปุ่มไว้ทุกใบตลอดเวลา ทำให้ล้นการ์ดและกดผิดง่าย)
  box.innerHTML = bag.items.map((it, i) => `
    <button class="item${it.usable ? ' use' : ''}" data-item="${i}">
      ${it.usable ? '<span class="badge">ใช้ได้</span>' : ''}
      <span class="nm">${esc(it.name)}</span><span class="qty">×${it.count}</span>
    </button>`).join('');
  box.querySelectorAll('[data-item]').forEach(b => b.onclick = () =>
    openItemMenu(bag.items[+b.dataset.item]));
}

async function boot() {
  // 1) ล็อกอินผ่านไหม — อันนี้อย่างเดียวที่ตัดสินว่าจะโชว์หน้า "ต้องล็อกอิน"
  try {
    await api("GET", "/api/web/me/session");
  } catch (e) {
    document.getElementById('needLogin').classList.remove('hidden');
    return;
  }

  // 2) ล็อกอินผ่านแล้ว = เปิดเมนูทันที ไม่ต้องรอข้อมูลตัวละคร
  //    (เดิมรวมไว้ก้อนเดียว พอวาดพลาดตรงไหนก็เด้งไปขึ้น "ต้องล็อกอินก่อน" ทั้งที่ล็อกอินแล้ว
  //     เมนูเลยไม่เปิดและหาสาเหตุไม่เจอ)
  document.getElementById('shell').classList.remove('hidden');

  // 3) โหลดข้อมูลตัวละคร — พังก็บอกสาเหตุจริง เมนูยังใช้ได้
  try {
    const g = await api("GET", "/api/web/me/game");
    if (g.new_player) {
      document.getElementById('pName').textContent = 'ยังไม่มีตัวละคร';
      document.getElementById('pSub').innerHTML =
        'พิมพ์ <b>!play</b> ในเซิร์ฟ Discord เพื่อสร้างตัวละครก่อน';
      drawSprite(document.getElementById('pfp'));
      return;
    }
    LAST = g;
    paint(g);
  } catch (e) {
    document.getElementById('pName').textContent = 'โหลดข้อมูลไม่สำเร็จ';
    document.getElementById('pSub').textContent = e.message || String(e);
    console.error('[play] โหลด/วาดข้อมูลตัวละครล้มเหลว:', e);
  }
}
boot();


// ══════ เฟส 2: ธุรกรรมจริง — ทุกรายการต้องยืนยันก่อนเสมอ (กันกดผิด) ══════

/** กล่องโต้ตอบกลาง — ใช้ทั้งเมนูเลือกและหน้ายืนยัน คืนค่า value ของปุ่มที่กด (ปิด = null)
 *  lines:   [[ป้าย, ค่า, สไตล์('warn'|'good'|'')]] บอกผลลัพธ์ที่จะเกิดขึ้นจริง
 *  buttons: [{label, value, cls}] — cls 'yes' = ปุ่มเน้น, 'danger' = ปุ่มทำลาย */
function openDialog({ title, message, lines, buttons }) {
  return new Promise(resolve => {
    const wrap = document.getElementById('confirmWrap');
    document.getElementById('cfTitle').textContent = title;
    document.getElementById('cfMsg').textContent = message || '';
    document.getElementById('cfLines').innerHTML = (lines || [])
      .map(([k, v, cls]) => '<div class="' + (cls || '') + '"><span>' + esc(k) +
                            '</span><b>' + esc(v) + '</b></div>').join('');
    document.getElementById('cfLines').style.display = (lines || []).length ? '' : 'none';

    const box = document.getElementById('cfBtns');
    box.innerHTML = '';
    wrap.classList.add('on');

    const onKey = e => { if (e.key === 'Escape') done(null); };
    function done(v) {
      wrap.classList.remove('on');
      wrap.onclick = null;
      document.removeEventListener('keydown', onKey);
      resolve(v);
    }
    (buttons || []).forEach((b, i) => {
      const el = document.createElement('button');
      el.textContent = b.label;
      if (b.cls) el.className = b.cls;
      el.onclick = () => { box.querySelectorAll('button').forEach(x => x.disabled = true); done(b.value); };
      box.appendChild(el);
      if (i === (buttons.length - 1)) el.focus();
    });
    wrap.onclick = e => { if (e.target === wrap) done(null); };   // คลิกนอกกล่อง = ปิด
    document.addEventListener('keydown', onKey);
  });
}

/** หน้ายืนยัน — คืน true เมื่อกดยืนยัน */
async function confirmAction({ title, message, lines, okText, danger }) {
  const v = await openDialog({
    title, message, lines,
    buttons: [{ label: 'ยกเลิก', value: null },
              { label: okText || 'ยืนยัน', value: true, cls: danger ? 'danger' : 'yes' }],
  });
  return v === true;
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


// ══════ คาสิโน (เฟส 3.3) ══════
// ผลออกที่เซิร์ฟเวอร์ทั้งหมด (รวมระบบเจ้ามือตุกติก) — ตรงนี้แค่เล่นอนิเมชันตามผลที่ได้มา
const BETS = [1000, 10000, 100000, 1000000];
const CASINO_BET = { slots: 10000, hilo: 10000 };
const SLOT_FACES = ['🍒', '🍇', '🍊', '💎', '🔔', '💰'];

function buildChips() {
  document.querySelectorAll('[data-chips]').forEach(box => {
    const game = box.dataset.chips;
    box.innerHTML = BETS.map(v =>
      '<button data-bet="' + v + '" aria-pressed="' + (v === CASINO_BET[game]) + '">' +
      fmt(v) + '</button>').join('');
    box.querySelectorAll('button').forEach(b => b.onclick = () => {
      CASINO_BET[game] = +b.dataset.bet;
      box.querySelectorAll('button').forEach(x =>
        x.setAttribute('aria-pressed', String(x === b)));
    });
  });
}

async function casinoPlay(game, choice) {
  const bet = CASINO_BET[game];
  if (LAST && LAST.money.cash < bet) return toast('เงินสดไม่พอเดิมพันจำนวนนี้', true);
  const btns = document.querySelectorAll('.casino-go');
  btns.forEach(b => b.disabled = true);
  try {
    const r = await api("POST", "/api/web/casino", { game: game, bet: bet, choice: choice || "" });
    if (!r.ok) { toast(r.result.message, true); return; }
    if (game === 'slots') await animateSlots(r.result);
    else await animateHilo(r.result);
    if (LAST) LAST.money = r.money;
    document.getElementById('pCash').textContent = fmt(r.money.cash);
    document.getElementById('pBank').textContent = fmt(r.money.bank);
  } catch (e) {
    toast(e.message, true);
  } finally {
    btns.forEach(b => b.disabled = false);
  }
}

const wait = ms => new Promise(r => setTimeout(r, ms));

async function animateSlots(res) {
  const msg = document.getElementById('slotMsg');
  const reels = [0, 1, 2].map(i => document.getElementById('sr' + i));
  msg.className = 'casino-result';
  msg.textContent = 'กำลังหมุน...';
  reels.forEach(r => { r.classList.remove('hit'); r.classList.add('spin'); });

  // หมุนหลอกตาให้ลุ้น แล้วหยุดทีละวงจากซ้ายไปขวา
  const flick = setInterval(() => reels.forEach(r => {
    r.querySelector('span').textContent = SLOT_FACES[Math.floor(Math.random() * 6)];
  }), 90);
  await wait(700);
  for (let i = 0; i < 3; i++) {
    await wait(430);
    reels[i].classList.remove('spin');
    reels[i].querySelector('span').textContent = res.reels[i];
    if (i === 2) clearInterval(flick);
  }
  if (res.winnings) reels.forEach(r => r.classList.add('hit'));
  msg.className = 'casino-result ' + (res.winnings ? 'win' : 'lose');
  msg.textContent = res.message.replace(/`/g, '');
}

async function animateHilo(res) {
  const msg = document.getElementById('hiloMsg');
  const dice = [0, 1, 2].map(i => document.getElementById('d' + i));
  msg.className = 'casino-result';
  msg.textContent = 'กำลังทอย...';
  dice.forEach(d => { d.classList.remove('roll'); void d.offsetWidth; d.classList.add('roll'); });

  const flick = setInterval(() => dice.forEach(d =>
    d.textContent = 1 + Math.floor(Math.random() * 6)), 70);
  await wait(620);
  clearInterval(flick);
  res.dice.forEach((v, i) => dice[i].textContent = v);
  await wait(150);
  msg.className = 'casino-result ' + (res.winnings ? 'win' : 'lose');
  msg.textContent = 'รวม ' + res.total + ' — ' + res.message.replace(/`/g, '');
}

const spinBtn = document.getElementById('spinBtn');
if (spinBtn) spinBtn.onclick = () => casinoPlay('slots');
document.querySelectorAll('[data-hilo]').forEach(b =>
  b.onclick = () => casinoPlay('hilo', b.dataset.hilo));

// ══════ แบล็กแจ็ค 24 (เฟส 3.4) ══════
CASINO_BET.bj = 10000;

function bjCards(box, cards) {
  box.innerHTML = cards.map(c => c[0] === '?'
    ? '<div class="card-f back">?</div>'
    : '<div class="card-f">' + esc(c[0]) + '</div>').join('');
}

function bjPaint(g) {
  bjCards(document.getElementById('bjMe'), g.player);
  bjCards(document.getElementById('bjBot'), g.bot);
  document.getElementById('bjMyScore').textContent = g.player_score + ' แต้ม';
  document.getElementById('bjBotScore').textContent =
    g.bot_score == null ? '' : g.bot_score + ' แต้ม';

  const playing = !g.over;
  document.getElementById('bjBetRow').classList.toggle('hidden', playing);
  document.getElementById('bjPlayRow').classList.toggle('hidden', !playing);

  const msg = document.getElementById('bjMsg');
  if (g.over) {
    msg.className = 'casino-result ' + (g.net > 0 ? 'win' : g.net < 0 ? 'lose' : '');
    msg.textContent = (g.message || '').replace(/`/g, '') +
                      (g.bot_log && g.bot_log.length ? ' · ' + g.bot_log.join(' ') : '');
  } else {
    msg.className = 'casino-result';
    msg.textContent = 'เดิมพัน ' + fmt(g.bet) + ' ทอง — จั่วเพิ่มหรือพอแค่นี้?';
  }
}

async function bjAct(action) {
  const btns = document.querySelectorAll('#bjBetRow .casino-go, #bjPlayRow .casino-go');
  btns.forEach(b => b.disabled = true);
  try {
    const body = { action: action };
    if (action === 'start') body.bet = CASINO_BET.bj;
    const r = await api("POST", "/api/web/blackjack", body);
    if (!r.ok) { toast(r.game.message, true); return; }
    bjPaint(r.game);
    if (LAST) LAST.money = r.money;
    document.getElementById('pCash').textContent = fmt(r.money.cash);
    document.getElementById('pBank').textContent = fmt(r.money.bank);
  } catch (e) {
    toast(e.message, true);
  } finally {
    btns.forEach(b => b.disabled = false);
  }
}

/** เปิดหน้ามา ถ้ามีโต๊ะค้างอยู่ (เช่นเปิดไว้ในดิส) ให้เล่นต่อได้เลย */
async function bjRestore() {
  try {
    const d = await api("GET", "/api/web/blackjack");
    if (d.playing) {
      bjPaint(d.game);
      toast('เจอโต๊ะที่ค้างอยู่ — เล่นต่อได้เลย');
    }
  } catch (e) { /* ยังไม่เคยเล่น = ไม่มีอะไรต้องทำ */ }
}

document.getElementById('bjStart').onclick = () => bjAct('start');
document.getElementById('bjHit').onclick = () => bjAct('hit');
document.getElementById('bjStand').onclick = () => bjAct('stand');

// ── ร้านค้าไอเทม ──
let SHOP_MODE = 'buy';

async function fillShop() {
  const box = document.getElementById('shopList');
  if (!box) return;
  box.innerHTML = '<div class="empty-bag">กำลังโหลด...</div>';

  if (SHOP_MODE === 'buy') {
    let d;
    try { d = await api("GET", "/api/web/shop/items"); }
    catch (e) { return toast(e.message, true); }
    const cash = LAST ? LAST.money.cash : 0;
    box.innerHTML = d.items.map((it, i) =>
      '<button class="item' + (it.buy > cash ? ' poor' : '') + '" data-shop-buy="' + i + '">' +
        (it.usable ? '<span class="badge">ใช้ได้</span>' : '') +
        '<span class="nm">' + esc(it.name) + '</span>' +
        '<span class="qty">' + fmt(it.buy) + '</span>' +
      '</button>').join('');
    box.querySelectorAll('[data-shop-buy]').forEach(b => b.onclick = () =>
      shopAction('buy', d.items[+b.dataset.shopBuy]));
    return;
  }

  // แท็บขาย — ใช้ของในกระเป๋าจากข้อมูลตัวละครที่โหลดไว้แล้ว
  const items = (LAST && LAST.bag.items) ? LAST.bag.items.filter(i => i.sell > 0) : [];
  if (!items.length) {
    box.innerHTML = '<div class="empty-bag">ไม่มีของที่ขายได้ในกระเป๋า</div>';
    return;
  }
  box.innerHTML = items.map((it, i) =>
    '<button class="item" data-shop-sell="' + i + '">' +
      '<span class="nm">' + esc(it.name) + ' ×' + it.count + '</span>' +
      '<span class="qty">' + fmt(it.sell) + '</span>' +
    '</button>').join('');
  box.querySelectorAll('[data-shop-sell]').forEach(b => b.onclick = () =>
    shopAction('sell', items[+b.dataset.shopSell]));
}

async function shopAction(action, it) {
  const buying = action === 'buy';
  const price = buying ? it.buy : it.sell;
  const cash = LAST ? LAST.money.cash : 0;
  const lines = [['ไอเทม', it.name],
                 [buying ? 'ราคาซื้อ' : 'ขายได้', fmt(price) + ' ทอง', buying ? 'warn' : 'good'],
                 ['เงินสดหลังทำรายการ', fmt(buying ? cash - price : cash + price) + ' ทอง']];
  if (!buying) lines.push(['มีอยู่', it.count + ' ชิ้น']);

  const ok = await confirmAction({
    title: buying ? '🏪 ยืนยันซื้อไอเทม' : '📦 ยืนยันขายไอเทม',
    message: buying ? 'ซื้อครั้งละ 1 ชิ้น หักจากเงินสด' : 'ขายครั้งละ 1 ชิ้น ได้เป็นเงินสด',
    lines, okText: buying ? 'ยืนยันซื้อ' : 'ยืนยันขาย', danger: !buying,
  });
  if (!ok) return;
  try {
    const r = await api("POST", "/api/web/shop", { action: action, item_id: it.id });
    toast(r.message, !r.ok);
    if (r.ok) { await reload(); await fillShop(); }
  } catch (e) { toast(e.message, true); }
}

document.querySelectorAll('[data-shop]').forEach(t => t.onclick = () => {
  SHOP_MODE = t.dataset.shop;
  document.querySelectorAll('[data-shop]').forEach(x =>
    x.setAttribute('aria-pressed', String(x === t)));
  fillShop();
});

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


/** เมนูของชิ้นเดียว — กดที่ของแล้วเลือกว่าจะใช้หรือทิ้ง */
async function openItemMenu(it) {
  const lines = [['มีอยู่', it.count + ' ชิ้น']];
  if (it.sell > 0) lines.push(['ขายได้', fmt(it.sell) + ' ทอง/ชิ้น']);
  lines.push(['ประเภท', it.usable ? 'ของใช้ได้' : 'เก็บ/ขายอย่างเดียว']);

  const buttons = [{ label: 'ปิด', value: null }];
  if (it.usable) buttons.push({ label: '🧪 ใช้', value: 'use', cls: 'yes' });
  buttons.push({ label: '🗑️ ทิ้ง', value: 'drop', cls: 'danger' });

  const choice = await openDialog({ title: it.name, message: 'เลือกสิ่งที่ต้องการทำ', lines, buttons });
  if (choice === 'use') await useItem(it.id, it.name);
  if (choice === 'drop') await dropItem(it.id, it.name, it.count, it.sell);
}
