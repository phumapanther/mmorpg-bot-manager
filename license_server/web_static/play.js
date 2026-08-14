// หน้าเล่นเกม Fragment Rift
// ตัวละคร/กระเป๋า/ธนาคาร/ทองคำแท่ง/คราฟ/ร้านค้า/คาสิโน = ข้อมูลจริง เรียกฟังก์ชันชุดเดียวกับบอทดิส
// ร้านยศ/กาชา/ทอยเต๋า = ยังเป็นโครงหน้า (เฟส 7-8)
// กติกา: ไม่มีกฎเกมในไฟล์นี้ — เซิร์ฟเวอร์คำนวณทุกอย่าง ที่นี่แค่วาดกับถามยืนยัน
renderChrome("/play");

// 🔊 ปุ่มเปิด/ปิดเสียง — จำค่าที่เลือกไว้ข้ามครั้ง
const sfxBtn = document.getElementById('playSfx');
if (sfxBtn) {
  const paint = () => { sfxBtn.textContent = SFX.enabled ? '🔊' : '🔇';
                        sfxBtn.title = SFX.enabled ? 'ปิดเสียง' : 'เปิดเสียง'; };
  paint();
  sfxBtn.addEventListener('click', () => { SFX.toggle(); paint(); });
}

// เสียงคลิกทุกปุ่มในหน้าเกม (ครั้งแรกที่คลิกคือจังหวะที่เบราว์เซอร์ยอมให้เปิดเสียง)
document.getElementById('shell')?.addEventListener('click', e => {
  if (e.target.closest('button')) SFX.play('click');
}, true);

// 🚪 ออกจากระบบ — เว็บนี้เก็บ session ไว้ 30 วัน เครื่องสาธารณะต้องมีทางออก
document.getElementById('playLogout')?.addEventListener('click', async () => {
  if (!await confirmAction({ title: '🚪 ออกจากระบบ',
                             message: 'ต้องล็อกอินด้วยโค้ดจากบอทใหม่อีกครั้ง',
                             okText: 'ออกจากระบบ', danger: true })) return;
  try { await api('POST', '/api/web/logout'); } catch (e) { /* ออกอยู่ดี */ }
  location.href = '/login';
});
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
  if (id === 'roleshop') fillRoleShop().catch(e => toast(e.message, true));
  if (id === 'gacha') fillGacha().catch(e => toast(e.message, true));
  if (id === 'rewards') fillBoard();
  if (id === 'pets') fillPets().catch(e => toast(e.message, true));
  if (id === 'daily') fillDaily().catch(e => toast(e.message, true));
  if (id === 'achv') fillAchv().catch(e => toast(e.message, true));
  if (id === 'books') fillBooks().catch(e => toast(e.message, true));
  if (id === 'elembook') fillElemBook().catch(e => toast(e.message, true));
  if (id === 'season') fillSeason().catch(e => toast(e.message, true));
  if (id === 'partner') fillPartner().catch(e => toast(e.message, true));
  if (id === 'slots' || id === 'hilo' || id === 'bj') buildChips();
  if (id === 'bj') bjRestore();
  if (id === 'scene') initScene().catch(e => toast(e.message, true));
  window.scrollTo({ top: document.getElementById('shell').offsetTop - 80, behavior: 'smooth' });
}
document.querySelectorAll('[data-go]').forEach(b => {
  if (b.classList.contains('soon')) return;
  b.addEventListener('click', () => showPanel(b.dataset.go));
});
document.querySelectorAll('[data-back]').forEach(b =>
  b.addEventListener('click', () => showPanel('home')));

// ── ร้านขายยศ + กาชา (เฟส 7) ──
// เว็บแจกยศ Discord เองไม่ได้ — กดซื้อแล้วเซิร์ฟเวอร์โยนเข้าคิวให้บอทมาแจก
// หน้านี้จึงต้องถามสถานะซ้ำจนกว่าบอทจะจัดการเสร็จ แล้วค่อยเฉลยผล
const FACTIONS = [['dark', '🩸 ฝ่ายความมืด'], ['light', '🕊️ ฝ่ายแสงสว่าง']];
let ROLE_FACTION = 'dark';
let GACHA_FACTION = 'dark';
let SHOP_BUSY = false;

/** ถามสถานะตั๋วจนกว่าบอทจะแจกเสร็จ (หรือหมดเวลา) */
async function waitTicket(id, onTick) {
  for (let i = 0; i < 20; i++) {
    await new Promise(r => setTimeout(r, i < 3 ? 700 : 1600));
    const t = await api('GET', '/api/web/roleshop/ticket/' + id);
    if (onTick) onTick(t);
    if (t.status !== 'pending') return t;
  }
  return { status: 'pending', note: 'บอทยังไม่ได้หยิบรายการนี้ — เดี๋ยวจะมอบยศให้เองภายหลัง' };
}

async function fillRoleShop() {
  chipRow(document.getElementById('roleFactions'), FACTIONS, v => {
    ROLE_FACTION = v; fillRoleShop();
  }, ROLE_FACTION);
  const box = document.getElementById('roleList');
  box.innerHTML = '<div class="g-note">กำลังโหลด...</div>';
  try {
    const d = await api('GET', '/api/web/roleshop?faction=' + ROLE_FACTION);
    box.innerHTML = d.roles.map((r, i) => `
      <div class="role-card" style="--rc:${ROLE_FACTION === 'dark' ? '#8f2317' : '#2f6d84'}">
        <div class="rn">${esc(r.emoji || '')} ${esc(r.label)}</div>
        <div class="rp">${fmt(r.price)} ทอง</div>
        <button data-buy="${i}">ซื้อยศนี้</button>
      </div>`).join('');
    box.querySelectorAll('[data-buy]').forEach(btn => {
      const r = d.roles[+btn.dataset.buy];
      btn.onclick = () => buyRole(r);
    });
  } catch (e) {
    box.innerHTML = '<div class="g-note">โหลดร้านไม่สำเร็จ: ' + esc(e.message) + '</div>';
  }
}

async function buyRole(r) {
  if (SHOP_BUSY) return;
  if (!await confirmAction({
        title: r.label, message: 'ซื้อยศนี้ด้วยทองในเกม',
        lines: [['ราคา', fmt(r.price) + ' ทอง'],
                ['ผู้มอบยศ', 'บอทในเซิร์ฟ Discord'],
                ['ถ้ามอบไม่สำเร็จ', 'คืนเงินอัตโนมัติ']],
        okText: 'ซื้อเลย' })) return;

  SHOP_BUSY = true;
  try {
    const res = await api('POST', '/api/web/roleshop',
                          { faction: ROLE_FACTION, action: 'buy', value: r.value });
    toast('กำลังมอบยศ ' + r.label + '...');
    boot();
    const t = await waitTicket(res.ticket);
    const msg = { done: '🎉 ได้รับยศ ' + r.label + ' แล้ว!',
                  refunded: '↩️ มอบยศไม่สำเร็จ — ' + (t.note || 'คืนเงินแล้ว'),
                  duplicate: '❌ คุณมียศนี้อยู่แล้ว' }[t.status] || t.note || 'รอบอทมอบยศ';
    toast(msg, t.status !== 'done');
    boot();
  } catch (e) {
    toast(e.message, true);
  } finally { SHOP_BUSY = false; }
}

async function fillGacha() {
  chipRow(document.getElementById('gachaFactions'), FACTIONS, v => {
    GACHA_FACTION = v; fillGacha();
  }, GACHA_FACTION);
  try {
    const d = await api('GET', '/api/web/roleshop?faction=' + GACHA_FACTION);
    document.getElementById('gachaPrice').textContent =
      fmt(d.gacha.price) + ' ทอง/ครั้ง · ในตู้มี ' + d.gacha.pool_size + ' ยศ';
    document.getElementById('gachaBtn').onclick = () => spinGacha(d.gacha.price);
  } catch (e) {
    document.getElementById('gachaPrice').textContent = 'โหลดไม่สำเร็จ';
  }
}

async function spinGacha(price) {
  if (SHOP_BUSY) return;
  if (!await confirmAction({
        title: '🎰 หมุนกาชาสุ่มยศ', message: 'จ่ายค่าหมุนหนึ่งครั้ง',
        lines: [['ค่าหมุน', fmt(price) + ' ทอง'],
                ['ได้ของซ้ำ', 'ไม่คืนเงิน (จ่ายค่าหมุน ไม่ใช่ค่ายศ)']],
        okText: 'หมุนเลย', danger: true })) return;

  const machine = document.getElementById('gachaMachine');
  const card = document.getElementById('gachaCard');
  const won = document.getElementById('gachaWon');
  const state = document.getElementById('gachaState');

  SHOP_BUSY = true;
  card.hidden = true;
  card.className = 'gacha-card';
  machine.classList.add('spin');
  try {
    const res = await api('POST', '/api/web/roleshop',
                          { faction: GACHA_FACTION, action: 'gacha' });
    await new Promise(r => setTimeout(r, 1500));      // ให้ลูกแก้วหมุนเห็น ๆ ก่อนเฉลย
    machine.classList.remove('spin');
    machine.classList.add('pop');
    setTimeout(() => machine.classList.remove('pop'), 500);

    won.textContent = res.label;
    state.textContent = 'กำลังมอบยศในดิสคอร์ด...';
    card.hidden = false;
    boot();

    const t = await waitTicket(res.ticket);
    if (t.status === 'done') {
      state.textContent = '🎉 แจ็คพอตแตก! ยศถูกมอบให้ในดิสคอร์ดแล้ว';
    } else if (t.status === 'duplicate') {
      card.className = 'gacha-card dup';
      state.textContent = '💀 เกลือ! คุณมียศนี้อยู่แล้ว';
    } else if (t.status === 'refunded') {
      card.className = 'gacha-card fail';
      state.textContent = '↩️ ' + (t.note || 'มอบยศไม่สำเร็จ — คืนเงินแล้ว');
    } else {
      state.textContent = '⏳ ' + (t.note || 'รอบอทมอบยศ');
    }
    boot();
  } catch (e) {
    machine.classList.remove('spin');
    toast(e.message, true);
  } finally { SHOP_BUSY = false; }
}

// ── กระดานทอยเต๋ารับของรายวัน (เฟส 8) ──
// กระดาน/รางวัล/โควตา มาจากเซิร์ฟเวอร์ทั้งหมด ที่นี่แค่วาดกับเล่นอนิเมชัน
let BOARD = null;
let BOARD_BUSY = false;

function paintBoard(st) {
  BOARD = st;
  document.getElementById('rollsLeft').textContent = st.rolls_left;
  document.getElementById('boardTheme').textContent = 'ธีมสัปดาห์นี้: ' + st.theme_label;
  document.getElementById('board').innerHTML = st.board.map((t, i) => {
    const cls = i === 0 ? 'sq start' : (t.kind === 'gold' && (t.amount || [0])[1] > 250 ? 'sq big' : 'sq');
    return `<div class="${cls}" data-i="${i}" title="${esc(t.label)}">${t.icon}` +
           (i === st.pos ? '<i class="me"></i>' : '') + '</div>';
  }).join('');
  const btn = document.getElementById('rollBtn');
  btn.disabled = st.rolls_left <= 0;
  btn.title = st.rolls_left <= 0 ? 'วันนี้ทอยครบโควตาแล้ว — พรุ่งนี้มาใหม่' : '';
}

async function fillBoard() {
  try {
    paintBoard(await api('GET', '/api/web/board'));
  } catch (e) {
    document.getElementById('boardTheme').textContent = 'โหลดกระดานไม่สำเร็จ: ' + e.message;
  }
}

/** เดินหมากทีละช่องให้เห็น ๆ ไม่ใช่วาร์ปไปเลย */
async function hopTo(from, steps, size) {
  const squares = document.getElementById('board').children;
  squares[from].querySelector('.me')?.remove();
  let cur = from;
  for (let n = 0; n < steps; n++) {
    cur = (cur + 1) % size;
    squares[cur].classList.add('hop');
    const me = document.createElement('i');
    me.className = 'me';
    squares[cur].appendChild(me);
    await new Promise(r => setTimeout(r, 190));
    squares[cur].classList.remove('hop');
    if (n < steps - 1) squares[cur].querySelector('.me')?.remove();
  }
  squares[cur].classList.add('landed');
  return cur;
}

async function rollBoard() {
  if (BOARD_BUSY || !BOARD) return;
  BOARD_BUSY = true;
  const dice = document.getElementById('diceRoller');
  const result = document.getElementById('boardResult');
  const btn = document.getElementById('rollBtn');
  btn.disabled = true;
  result.hidden = true;
  document.querySelectorAll('.board .sq.landed').forEach(s => s.classList.remove('landed'));

  dice.classList.remove('landed');
  dice.classList.add('rolling');
  SFX.play('dice');
  const tumble = setInterval(() => {
    dice.textContent = ['⚀','⚁','⚂','⚃','⚄','⚅'][Math.floor(Math.random() * 6)];
  }, 90);

  try {
    const r = await api('POST', '/api/web/board/roll');
    await new Promise(res => setTimeout(res, 900));      // ให้เต๋ากลิ้งเห็น ๆ ก่อนเฉลย
    clearInterval(tumble);
    dice.classList.remove('rolling');
    dice.textContent = ['⚀','⚁','⚂','⚃','⚄','⚅'][r.steps - 1];
    dice.classList.add('landed');

    await hopTo(r.from, r.steps, BOARD.size);
    result.innerHTML = mdLite(`ตกช่อง **${r.tile.icon} ${r.tile.label}**\n${r.text}`);
    result.hidden = false;
    document.getElementById('rollsLeft').textContent = r.rolls_left;
    BOARD.pos = r.to;
    BOARD.rolls_left = r.rolls_left;
    boot();
  } catch (e) {
    clearInterval(tumble);
    dice.classList.remove('rolling');
    dice.textContent = '🎲';
    toast(e.message, true);
  } finally {
    BOARD_BUSY = false;
    btn.disabled = (BOARD.rolls_left ?? 0) <= 0;
  }
}

document.getElementById('rollBtn').addEventListener('click', rollBoard);

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
  if (SCENE) SCENE.setPet(v.pet || '');     // 🐾 พาไปด้วยไหม เซิร์ฟเวอร์เป็นคนบอก
  paintProfile(g);
  paintAdvHud(g);
  paintBag(g.bag);
}

/** หัวสถานะบนหน้าผจญภัย — ต้องเห็นเลือด/EXP/เงินตลอดเวลาที่กำลังเล่น
 *  ค่าทุกตัวมาจากชุดเดียวกับโปรไฟล์ ไม่คำนวณอะไรเองที่นี่ */
function paintAdvHud(g) {
  const id = g.identity, v = g.vitals;
  document.getElementById('advName').textContent = id.title || 'นักผจญภัย';
  document.getElementById('advLv').textContent = 'Lv ' + (id.level ?? '—');
  document.getElementById('advCash').textContent = fmt(g.money.cash);

  // 💎 เม็ดคริสตัล — แถบมาจากเซิร์ฟเวอร์แล้ว ที่นี่แค่วางลงจอ
  const mn = document.getElementById('advMana');
  mn.textContent = (v.mana_bar || '') + ' ' + (v.mana ?? 0) + '/' + (v.mana_max ?? 0);
  mn.classList.toggle('empty', (v.mana ?? 0) <= 0);
  MANA_LEFT = v.mana ?? 0;

  const hp = v.hp ?? 0, mx = v.max_hp || 1;
  const pct = Math.max(0, Math.min(100, hp / mx * 100));
  const hpBar = document.getElementById('advHp');
  hpBar.style.width = pct + '%';
  hpBar.classList.toggle('low', pct < 30);          // เลือดต่ำ = แถบเตือน
  document.getElementById('advHpTxt').textContent = fmt(hp) + ' / ' + fmt(mx);

  document.getElementById('advExp').style.width = (id.exp_pct ?? 0) + '%';
  document.getElementById('advExpTxt').textContent =
    id.max_level ? 'เลเวลเต็ม' : (id.exp_pct ?? 0) + '%';

  // 🛡️ ความทนทานอุปกรณ์ — เดิมต้องออกไปดูหน้าโปรไฟล์ ไม่รู้ว่าเกราะกำลังจะพัง
  const dur = (o, icon) => o.dur == null ? '' :
    `<span title="${esc(o.name || '')}">${icon} <b class="${o.dur <= 0 ? 'low' : o.dur < 30 ? 'low' : ''}">${o.dur}%</b>` +
    (o.dur <= 0 ? ' <b class="low">พัง</b>' : '') + '</span>';
  document.getElementById('advGear').innerHTML =
    dur(g.gear.weapon, '⚔️') + dur(g.gear.armor, '🛡️');

  // 🧬 สถานะติดตัว — จะได้รู้ว่าทำไมทอยได้ 0 ไม่ต้องเดาว่าบัคไหม
  document.getElementById('advBuffs').innerHTML = (g.buffs || []).map(b =>
    `<span class="${BAD_STATUS.test(b.label) ? 'bad' : ''}" title="${esc(b.label)}">${esc(b.label)}` +
    (b.no_tick ? '' : ` <b>${b.turns}</b>${esc(b.unit || '')}`) + '</span>').join('');

  const face = document.getElementById('advFace');
  const ctx = face.getContext('2d');
  ctx.clearRect(0, 0, face.width, face.height);
  drawCharacter(ctx, (face.width - 16 * 3) / 2, -6, 3, CHAR);   // ครึ่งตัวบนพอดีกรอบ
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

  // 🎲 สรุปเต๋า — ตอบคำถามที่ถามบ่อยว่าทำไมไม่เคยทอยเกิน 20
  const dc = g.dice || {};
  document.getElementById('prDice').textContent =
    `${dc.dice_count ?? 1} ลูก` + (dc.bonus_total ? `  (+${dc.bonus_total})` : '');
  document.getElementById('prDiceDetail').innerHTML =
    `⚔️ ตีปกติ ทอย <b>${dc.normal_min}-${dc.normal_max}</b>` +
    (dc.bonus_total ? ` + โบนัส <b>${dc.bonus_total}</b>` : '') +
    ` → สูงสุด <b class="cap">${dc.normal_cap}</b><br>` +
    `✨ ใช้สกิล ทอย <b>1-${dc.skill_max}</b>` +
    (dc.bonus_total ? ` + โบนัส <b>${dc.bonus_total}</b>` : '') +
    ` → สูงสุด <b class="cap">${dc.skill_cap}</b>` +
    ((dc.bonus || []).length
      ? '<br>' + dc.bonus.map(b => `${esc(b.from)} <b>+${b.value}</b>`).join(' · ')
      : '<br><span style="color:#a99274">ยังไม่มีโบนัสเต๋า — พาสัตว์เลี้ยงไปด้วยจะได้เพิ่ม</span>');

  const durBar = d => d == null ? '' :
    `<div class="dur${d < 30 ? ' low' : ''}"><i style="width:${Math.max(0, Math.min(100, d))}%"></i></div>` +
    `<span class="dur-pct${d < 30 ? ' low' : ''}">ความทนทาน ${d}%` +
    (d <= 0 ? ' — พังแล้ว! ไม่ได้โบนัส' : d < 30 ? ' — ใกล้พัง' : '') + '</span>';
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
  if (bad) SFX.play('error');
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

// ══════ ฉากผจญภัย (เฟส 4 — เอนจินฉาก) ══════
let SCENE = null;

const SCENE_MAPS = [
  ['main', '🏰 หลัก'], ['volcanic', '🌋 ภูเขาไฟ'], ['frozen', '❄️ น้ำแข็ง'],
  ['demon', '😈 ปีศาจ'], ['nether', '💀 เนเธอร์'], ['sylvan', '🌲 พงไพร'],
  ['mechanized', '⚙️ จักรกล'], ['skyward', '☁️ นภา'], ['ocean', '🌊 มหาสมุทร'],
];
const SCENE_EVENTS = [
  ['village', '🏡 หมู่บ้าน'], ['treasure', '📦 หีบสมบัติ'], ['npc', '🧓 NPC'],
  ['trap', '⚠️ กับดัก'], ['dungeon', '🚪 ดันเจี้ยน'], ['monster', '👹 มอนสเตอร์'],
  ['calm', '🍃 เงียบสงบ'],
];
// สกิลของแต่ละคลาส — ต้องตรงกับ CLASS_SKILLS ในเกม (มีเทสคุม)
const CLASS_SKILL_FX = {
  Warrior: [['bash', '🛡️ Shield Bash'], ['heavy', '⚔️ Heavy Strike']],
  Mage:    [['fire', '🔥 Fireball'], ['frost', '❄️ Frostbolt']],
  Rogue:   [['stab', '🗡️ Backstab'], ['evade', '💨 Evasion']],
  Cleric:  [['heal', '✨ Heal'], ['aura', '🛡️ Holy Aura']],
};
// ปุ่มสกิลบนเว็บส่งชื่อนี้ไปให้เซิร์ฟเวอร์ — ต้องตรงกับที่ fight_turn เช็ค ไม่งั้นกดแล้วเงียบ
const SKILL_ID = { bash: 'skill_shield_bash', heavy: 'skill_heavy_strike',
                   fire: 'skill_fireball', frost: 'skill_frostbolt',
                   stab: 'skill_backstab', evade: 'skill_evasion',
                   heal: 'skill_heal', aura: 'skill_holy_aura' };
const FOE_SHAPES = ['dragon', 'slime', 'humanoid', 'golem'];
const FOE_ELEMENTS = ['fire', 'water', 'earth', 'wind', 'wood', 'light', 'dark'];

function chipRow(box, items, onPick, initial) {
  box.innerHTML = items.map(([v, label], i) =>
    '<button data-v="' + v + '" aria-pressed="' + (v === initial) + '">' + label + '</button>').join('');
  box.querySelectorAll('button').forEach(b => b.onclick = () => {
    box.querySelectorAll('button').forEach(x => x.setAttribute('aria-pressed', String(x === b)));
    onPick(b.dataset.v);
  });
}

// ── ผจญภัยจริง (เฟส 5.4) ──
// ปุ่มทุกปุ่มยกมาจากเกมในดิสเป๊ะ ๆ ผลลัพธ์คำนวณที่เซิร์ฟเวอร์ทั้งหมด
// ที่นี่แค่ส่ง action แล้วเอาข้อความ+ฉากที่ได้กลับมาวาด

// เหตุการณ์ -> ปุ่มที่ต้องขึ้น [action, ป้าย, สไตล์, ข้อความยืนยัน(ถ้ามี)]
/** จอแคบกว่า 480px — ใช้ชื่อปุ่มแบบสั้นไม่ให้ตัดเป็นสามบรรทัด */
const NARROW = () => window.matchMedia('(max-width: 480px)').matches;

const ADV_ACTIONS = {
  village: g => [['rest', NARROW() ? '🛏️ พักแรม' : '🛏️ พักแรม (ฟื้น HP เต็ม)', 'hot',
                  'จ่ายค่าห้องนอนเพื่อฟื้น HP จนเต็ม'],
                 ['leave', NARROW() ? '🚶 ไปต่อ' : '🚶 ออกเดินทางต่อ', '']],
  treasure: () => [['open', NARROW() ? '📦 เปิดหีบ' : '📦 เปิดกล่องสมบัติ', 'hot',
                    'หีบอาจเป็นมิมิกกับดักได้ (Rogue กันได้ 100%)'],
                   ['ignore', NARROW() ? '❌ เดินผ่าน' : '❌ เมินเฉยและเดินผ่าน', '']],
  dungeon: () => [['enter', NARROW() ? '🚪 บุกเข้า' : '🚪 บุกเข้าดันเจี้ยน', 'hot',
                   'เข้าไปแล้วต้องสู้มอนต่อเนื่อง 10 ตา'],
                  ['leave', '🏃 ไม่เข้าดีกว่า', '']],
  trap: () => [['dodge', NARROW() ? '🎲 หลบ' : '🎲 ทอยเต๋าหลบกับดัก', 'hot']],
  travel: g => [['board', `🧳 ขึ้นยาน (จ่าย ${fmt(g.encounter.fare)} ทอง)`, 'hot',
                 `จ่ายค่าโดยสาร ${fmt(g.encounter.fare)} ทอง — ปลายทางรู้ตอนไปถึงเท่านั้น`],
                ['decline', '🙅 ไม่ไป เดินทางต่อ', '']],
  mugging: g => [['fight', '⚔️ สู้', 'hot', `โอกาสชนะ ${g.win_pct}% — แพ้โดนกวาดเงินติดตัวหมด`],
                 ['flee', '🏃 หนี (-50% เงินติดตัว)', '', 'โยนถุงทองครึ่งหนึ่งสกัดโจรแล้ววิ่ง']],
  npc: () => [['talk', '💬 เข้าไปพูดคุย', 'hot'],
              ['quest', '📜 ฟังข้อเสนอเควส', ''],
              ['ignore', '🤫 เมินใส่', '']],
  npc_quest: () => [['accept', '✅ แลกเปลี่ยน', 'hot', 'ของในกระเป๋าตามข้อเสนอจะถูกนำไปแลกทันที'],
                    ['decline', '❌ ปฏิเสธ', '']],
  // ไฟต์: โจมตีปกติ + สกิลของคลาสตัวเอง + หนี (ยกมาจากปุ่มในดิสทั้งชุด)
  monster: () => [['attack', NARROW() ? '⚔️ สู้ต่อ' : '⚔️ สู้ต่อ (ทอยเต๋าปกติ)', 'hot'],
                  ...(CLASS_SKILL_FX[(LAST && LAST.identity.class_name)] || [])
                      .filter(([fx]) => SKILL_ID[fx])
                      .map(([fx, label]) => [SKILL_ID[fx], label, '']),
                  ['flee', '🏃 หนี', '', 'หนีไม่สำเร็จจะโดนสวนกลับเสียเลือด']],
  // อีเวนต์พิเศษ: แบบทอยเต๋าได้ปุ่มเดียว แบบเลือกทางได้ปุ่มตามจำนวนตัวเลือกของอีเวนต์นั้น
  special: g => (g.choices && g.choices.length)
    ? g.choices.map((label, i) => [String(i), esc(label), i === 0 ? 'hot' : ''])
    : [['roll', '🎲 ทอยเต๋าวัดดวง', 'hot']],
};

// เหตุการณ์ -> คีย์ภาพในโฟลเดอร์ assets/events (ชื่อเดียวกับที่ดิสใช้)
const ADV_ART = { calm: 'calm', village: 'village', treasure: 'treasure', trap: 'trap',
                  dungeon: 'dungeon', monster: 'monster', bank_robbery: 'bank_robbery',
                  mugging: 'mugging', npc: 'npc', special: 'special', travel: 'travel' };

let ADV_BUSY = false;
// สถานะที่เป็นโทษ — ขึ้นสีแดงให้เห็นชัดว่ากำลังโดนอะไรอยู่
const BAD_STATUS = /พิษ|เลือดไหล|ชา|แผลแผดเผา|หนาว|ผนึก|หลุดมือ|พันธนาการ|ราก|คำสาป|เห็ด|ซอมบี้|EMP|หนัก/;
let MANA_LEFT = 0;      // เม็ดคริสตัลที่เหลือ — ใช้ตัดสินว่าปุ่มสกิลกดได้ไหม

function advPaint(g) {
  document.getElementById('advText').innerHTML = mdLite(g.text || '');
  document.getElementById('advNotes').innerHTML =
    (g.notes || []).map(n => '<span>' + esc(n) + '</span>').join('');
  document.getElementById('advLog').scrollTop = 0;   // ข้อความใหม่เริ่มอ่านจากบรรทัดบนสุดเสมอ

  const box = document.getElementById('advActions');
  const build = ADV_ACTIONS[g.pending];
  if (!build) { advIdleButton(box); return; }

  box.innerHTML = '';
  build(g).forEach(([action, label, cls, confirmMsg]) => {
    const btn = document.createElement('button');
    btn.className = 'g-tile casino-go' + (cls ? ' ' + cls : '');
    btn.innerHTML = label;
    if (action.startsWith('skill_') && MANA_LEFT <= 0) {   // 💎 เม็ดหมด = ออกท่าไม่ได้
      btn.disabled = true;
      btn.title = 'เม็ดคริสตัลหมดแล้ววันนี้ — โจมตีปกติหรือหนีได้';
    } else {
      btn.onclick = () => advAct(action, label, confirmMsg);
    }
    box.appendChild(btn);
  });
}

function paintFoe(m) {
  const bar = document.getElementById('foeBar');
  if (!m) {
    bar.hidden = true;
    if (!SCENE.death) SCENE.clearFoe();     // กำลังเล่นฉากตายอยู่ อย่าเพิ่งลบร่างทิ้ง
    return;
  }
  bar.hidden = false;
  document.getElementById('foeName').textContent = m.name;
  document.getElementById('foeRank').textContent = m.rank || '';
  const pct = Math.max(0, Math.min(100, m.hp / Math.max(1, m.hp_max) * 100));
  document.getElementById('foeHp').style.width = pct + '%';
  document.getElementById('foeHpTxt').textContent = fmt(m.hp) + ' / ' + fmt(m.hp_max)
                                                    + '  ·  เทิร์น ' + (m.turn || 1);
  SCENE.setFoe({ shape: FOE_SHAPES[(m.name || '').length % FOE_SHAPES.length],
                 element: m.element || 'fire' });
}


function advIdleButton(box) {
  box.innerHTML = '';
  const btn = document.createElement('button');
  btn.className = 'g-tile hot casino-go';
  btn.innerHTML = '<span class="ic">🧭</span>ออกเดินทาง';
  btn.onclick = advWalk;
  box.appendChild(btn);
}


/** 🏥 หมดสติแล้ว — เหลือทางเดียวคือฟื้นกลับหมู่บ้าน (เดิมเว็บไม่มีปุ่มนี้ ผู้เล่นค้างถาวร) */
function advRespawnButton(box) {
  box.innerHTML = '';
  const btn = document.createElement('button');
  btn.className = 'g-tile hot casino-go';
  btn.innerHTML = '<span class="ic">🏥</span>ฟื้นคืนชีพ กลับหมู่บ้าน';
  btn.onclick = advRespawn;
  box.appendChild(btn);
}


async function advRespawn() {
  if (ADV_BUSY) return;
  if (!await confirmAction({
        title: '🏥 ฟื้นคืนชีพ',
        message: 'หมอผีประจำหมู่บ้านจะดึงวิญญาณคุณกลับมา — มีค่าทำพิธีตามเลเวล',
        lines: [['กลับไปที่', 'หมู่บ้าน'],
                ['ความคืบหน้าดันเจี้ยน', 'หายทั้งหมด']],
        okText: 'ยอมรับบทลงโทษ' })) return;

  ADV_BUSY = true;
  try {
    const r = await api('POST', '/api/web/adventure/respawn');
    SCENE.clearFoe(); SCENE.clearRoll();
    document.getElementById('foeBar').hidden = true;
    SCENE.setMap((LAST && LAST.identity.continent) || 'main');
    SCENE.showEvent('village');
    document.getElementById('sceneTag').textContent = ADV_LABEL.village;
    advPaint({ text: r.text, pending: r.pending });   // เปิดเมนูหมู่บ้านต่อทันที (พักแรม/เดินทาง)
    boot();
  } catch (e) {
    toast(e.message, true);
  } finally { ADV_BUSY = false; }
}

/** ตัวหนา **x** และโค้ด `x` จากข้อความเกม — ไม่ใช่ markdown เต็ม แค่สองอย่างที่เกมใช้ */
function mdLite(t) {
  return esc(t).replace(/\*\*(.+?)\*\*/g, '<b>$1</b>').replace(/`(.+?)`/g, '<code>$1</code>')
               .replace(/\n/g, '<br>');
}

async function advWalk() {
  if (ADV_BUSY) return;
  ADV_BUSY = true;
  const tag = document.getElementById('sceneTag');
  SFX.play('walk');
  SCENE.clearFoe(); SCENE.clearRoll(); SCENE.walk();
  document.getElementById('foeBar').hidden = true;
  tag.textContent = 'กำลังเดินทาง...';
  document.getElementById('advActions').innerHTML = '';
  document.getElementById('advText').textContent = '✨ คุณเริ่มก้าวเท้าออกเดินทางตรวจตราเส้นทาง...';

  try {
    const g = await api('POST', '/api/web/adventure/walk');
    await new Promise(r => setTimeout(r, 900));       // ให้เห็นอนิเมชันเดินก่อนเฉลย
    SCENE.setMap(g.continent || 'main');
    const art = g.event === 'travel' ? 'vehicle_' + g.encounter.vehicle : ADV_ART[g.event];
    if (art) SCENE.showEvent(art); else SCENE.idle();
    tag.textContent = ADV_LABEL[g.event] || g.event;
    if (g.event === 'death') {                          // ล้มกลางทางจากพิษ/สถานะ
      SCENE.killHero();
      advPaint({ text: g.text, notes: g.notes });
      advRespawnButton(document.getElementById('advActions'));
      boot();
      return;
    }
    paintFoe(g.monster);
    if (g.money != null) boot();      // เงิน/เลือดเปลี่ยน วาดหัวการ์ดใหม่
    advPaint(g);
  } catch (e) {
    SCENE.idle();
    toast(e.message, true);
    advIdleButton(document.getElementById('advActions'));
  } finally { ADV_BUSY = false; }
}

async function advAct(action, label, confirmMsg) {
  if (ADV_BUSY) return;
  if (confirmMsg && !await confirmAction({
        title: label.replace(/<[^>]+>/g, ''), message: confirmMsg,
        okText: 'ยืนยัน', danger: action === 'fight' })) return;

  ADV_BUSY = true;
  try {
    if (action === 'attack' || action.startsWith('skill_')) {
      SCENE.attack();
      SCENE.petAttack();                     // 🐾 สัตว์เลี้ยงพุ่งเข้าช่วยด้วย
      SFX.play(action.startsWith('skill_') ? 'skill' : 'hit');
    }
    if (action.startsWith('skill_')) SCENE.playSkill(action.slice(6));

    const r = await api('POST', '/api/web/adventure/act', { action: action });

    if (r.fx) {                                        // กับดักลั่นก่อน แล้วค่อยเฉลยเต๋า
      SCENE.playTrap(r.fx.kind, r.fx.hit);
      await new Promise(res => setTimeout(res, 420));
    }
    if (r.roll) {
      SCENE.showRoll(r.roll);
      await new Promise(res => setTimeout(res, 750));      // ให้เห็นเต๋าเฉลยก่อนตัวเลขเด้ง
    }
    if (r.damage_to_monster) { SCENE.hitFoe(); SCENE.float('-' + fmt(r.damage_to_monster), '', 72); }
    if (r.damage_to_player) SFX.play('hurt');
    if (r.outcome === 'win') {
      SFX.play('win');
      SCENE.killFoe();                                  // 💥 แตกเป็นเศษ ไม่ใช่หายวับ
      await new Promise(res => setTimeout(res, 620));   // ให้ดูฉากตายก่อนขึ้นสรุปรางวัล
    } else if (r.outcome === 'monster_fled') {
      SFX.play('flee');
      SCENE.fleeFoe();                                  // 💨 วาบแสงแล้วพุ่งออกจอ
      await new Promise(res => setTimeout(res, 520));
    } else if (r.outcome === 'lose') {
      SFX.play('lose');
      SCENE.killHero();                                 // 💀 ทรุดลง จอมืด ขึ้น K.O.
      await new Promise(res => setTimeout(res, 900));
      advPaint({ text: r.text });
      advRespawnButton(document.getElementById('advActions'));
      boot();
      return;                                           // ตายแล้วเหลือทางเดียว: ฟื้น
    }
    if (r.damage_to_player) SCENE.float('-' + fmt(r.damage_to_player), 'miss', 30);
    if (r.healed) SCENE.float('+' + fmt(r.healed) + ' HP', 'heal', 30);
    if (r.mana) { MANA_LEFT = r.mana.mana; if (r.mana_spent) SCENE.float('💎 -1', 'miss', 46); }
    if (r.reward) { SCENE.float('+' + fmt(r.reward.gold) + ' ทอง', 'gold', 50);
                    SFX.play(r.reward.level_up ? 'levelup' : 'coin'); }
    if (r.monster !== undefined) paintFoe(r.pending === 'monster' ? r.monster : null);
    if (r.damage) { SCENE.hitFoe(); SCENE.float('-' + r.damage, '', 40); }
    if (r.gold) { SCENE.float('+' + r.gold, 'gold', 50); SFX.play('coin'); }
    if (r.continent) { SCENE.setMap(r.continent); SCENE.showEvent('village'); }
    advPaint({ text: r.text, pending: r.pending });   // ยังมีขั้นต่อ (เช่นข้อเสนอเควส) ก็โชว์ปุ่มต่อ
    boot();                                           // เลือด/เงิน/กระเป๋าเปลี่ยน โหลดใหม่
  } catch (e) {
    toast(e.message, true);
  } finally { ADV_BUSY = false; }
}

const ADV_LABEL = { calm: 'เส้นทางเงียบสงบ', village: 'หมู่บ้านอุ่นใจ', treasure: 'หีบสมบัติ',
                    trap: 'กับดัก', dungeon: 'ปากดันเจี้ยน', monster: 'เงาปริศนา',
                    bank_robbery: 'โจรปล้นธนาคาร', mugging: 'โดนดักปล้น', npc: 'นักเดินทาง',
                    travel: 'พาหนะข้ามทวีป', special: 'เหตุการณ์พิเศษ', death: 'หมดสติ' };

async function initScene() {
  if (!SCENE) {
    SCENE = new Scene(document.getElementById('scene'));
    SCENE.setCharacter(CHAR);
    SCENE.setPet((LAST && LAST.vitals.pet) || '');
    SCENE.setMap((LAST && LAST.identity.continent) || 'main');
  }
  document.getElementById('sceneTag').textContent =
    (LAST && LAST.identity.continent_label) || '—';

  // ค้างเหตุการณ์ไหนอยู่ก็กลับมาเล่นต่อจุดเดิม (รีเฟรชหน้าแล้วต้องไม่ตัน)
  try {
    const st = await api('GET', '/api/web/adventure/state');
    if (st.pending === 'monster') {                       // กลับมาสู้ต่อจากที่ค้างไว้
      SCENE.showEvent('monster');
      document.getElementById('sceneTag').textContent = ADV_LABEL.monster;
      paintFoe({ name: st.data.stats.name, rank: st.data.rank, element: st.data.element,
                 hp: st.data.hp, hp_max: st.data.hp_max, turn: st.data.turn });
      advPaint({ pending: 'monster', text: 'คุณยังสู้อยู่กับศัตรูตัวนี้ — เลือกแอคชั่นต่อได้เลย' });
      return;
    }
    if (st.pending) {
      SCENE.showEvent(ADV_ART[st.pending] || st.pending);
      document.getElementById('sceneTag').textContent = ADV_LABEL[st.pending] || st.pending;
      advPaint({ pending: st.pending, encounter: st.data, win_pct: st.data.win_pct,
                 choices: (st.data.choices || []).map(c => c.label),
                 text: st.data.text || st.data.intro || 'คุณค้างอยู่ที่เหตุการณ์นี้ — เลือกต่อได้เลย' });
      return;
    }
    if (st.state === 'dead') {
      SCENE.killHero();
      document.getElementById('advText').textContent =
        '💀 คุณหมดสติอยู่ — ต้องฟื้นคืนชีพก่อนถึงจะออกเดินทางต่อได้';
      advRespawnButton(document.getElementById('advActions'));
      return;
    }
    if (st.state && st.state !== 'idle' && st.state !== 'village') {
      document.getElementById('advText').textContent =
        '⚠️ ตัวละครของคุณติดเหตุการณ์อยู่ในดิสคอร์ด — เล่นให้จบที่นั่นก่อนถึงจะเดินทางบนเว็บได้';
      document.getElementById('advActions').innerHTML = '';
      return;
    }
  } catch (e) { /* ยังไม่มีตัวละคร/ยังไม่ล็อกอิน — ปุ่มเดินทางจะฟ้องเองตอนกด */ }

  advIdleButton(document.getElementById('advActions'));
}

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


// ══════ เมนูสะสม/รางวัล ที่ยกมาจากดิส ══════
// ทุกหน้าอ่านจาก API ที่เรียกโมดูลเดียวกับคำสั่งในดิส — ที่นี่แค่วาด

const bar10 = (cur, target) => {
  const n = Math.max(0, Math.min(10, Math.round(cur / Math.max(1, target) * 10)));
  return '█'.repeat(n) + '░'.repeat(10 - n);
};

// ── 🐾 สัตว์เลี้ยง ──
async function fillPets() {
  const box = document.getElementById('petList');
  box.innerHTML = '<div class="g-note">กำลังโหลด...</div>';
  const d = await api('GET', '/api/web/me/pets');
  box.innerHTML = d.pets.map((p, i) => `
    <div class="role-card${p.active ? ' owned' : ''}" style="--rc:${p.owned ? '#6fa860' : '#4a4038'}">
      <div class="rn">${esc(p.name)}</div>
      <div class="rp">${p.owned ? '🎲 หนุนเต๋า +' + p.dice : '🔒 ยังไม่ได้จับ (' + esc(p.from_rank) + ')'}</div>
      ${p.owned ? `<button data-pet="${i}">${p.active ? 'ปล่อยออก' : 'พาไปด้วย'}</button>` : ''}
    </div>`).join('');
  box.querySelectorAll('[data-pet]').forEach(btn => {
    const p = d.pets[+btn.dataset.pet];
    btn.onclick = async () => {
      try {
        const r = await api('POST', '/api/web/me/pets', { key: p.active ? '' : p.key });
        toast(r.message); fillPets(); boot();
      } catch (e) { toast(e.message, true); }
    };
  });
}

// ── 📅 ภารกิจวันนี้ ──
async function fillDaily() {
  const d = await api('GET', '/api/web/me/daily');
  document.getElementById('dailyStreak').textContent =
    `🔥 ล็อกอินต่อเนื่อง ${d.streak} วัน (สถิติสูงสุด ${d.best} วัน) · รีเซ็ตเที่ยงคืน`;
  document.getElementById('dailyList').innerHTML = d.quests.map(q => {
    const pct = Math.min(100, q.cur / Math.max(1, q.target) * 100);
    return `<div class="kv"><span style="flex:1">${esc(q.label)}
      <div class="prog${q.claimed ? ' done' : ''}"><i style="width:${pct}%"></i></div>
      <small style="color:var(--g-dim)">${q.cur}/${q.target} · ${Math.round(pct)}%</small></span>
      <b>${q.claimed ? '✅ รับแล้ว' : q.ready ? '🎁 รับได้!' : fmt(q.gold) + ' ทอง'}</b></div>`;
  }).join('');
  const btn = document.getElementById('dailyClaim');
  btn.disabled = !d.claimable;
  btn.onclick = async () => {
    try { toast((await api('POST', '/api/web/me/daily/claim')).message); fillDaily(); boot(); }
    catch (e) { toast(e.message, true); }
  };
}

// ── 🏅 ความสำเร็จ ──
async function fillAchv() {
  const d = await api('GET', '/api/web/me/achievements');
  const chips = [['', '— ไม่สวมฉายา —'], ...d.titles.map(t => [t, t])];
  chipRow(document.getElementById('titleChips'), chips, async v => {
    try { toast((await api('POST', '/api/web/me/title', { title: v })).message); boot(); }
    catch (e) { toast(e.message, true); fillAchv(); }
  }, d.title || '');
  document.getElementById('achvList').innerHTML = d.achievements.map(a => {
    const pct = Math.min(100, a.cur / Math.max(1, a.target) * 100);
    return `<div class="kv"><span style="flex:1">${a.done ? '✅' : '⬜'} ${esc(a.label)} — ${esc(a.desc)}
      <div class="prog${a.done ? ' done' : ''}"><i style="width:${pct}%"></i></div>
      <small style="color:var(--g-dim)">${fmt(a.cur)}/${fmt(a.target)} · ${pct.toFixed(pct < 10 ? 1 : 0)}%</small></span>
      <b>${a.done ? 'สำเร็จ' : fmt(a.gold) + ' ทอง'}</b></div>`;
  }).join('');
}

// ── 📕 สมุดมอน (ล้มอะไรไปแล้วบ้าง) ──
async function fillBooks() {
  const d = await api('GET', '/api/web/me/books');
  const touched = d.continents.filter(c => c.ranks.some(r => r.kills > 0)).length;
  document.getElementById('bookSummary').innerHTML =
    `⚔️ ล้มมอนสะสม <b>${fmt(d.total_kills)}</b> ตัว · เคยล่ามาแล้ว <b>${touched}/${d.continents.length}</b> ทวีป`;
  document.getElementById('bookList').innerHTML = d.continents.map(c => {
    const sum = c.ranks.reduce((n, r) => n + r.kills, 0);
    return `<div class="g-card" style="margin-bottom:10px">
      <h3 style="margin-bottom:6px">${esc(c.label)}
        <small style="color:var(--g-dim);font-weight:400">· รวม ${fmt(sum)} ตัว</small></h3>
      ${c.ranks.map(r => `<div class="bk-row">
        <span class="bk-rank">${esc(r.rank)}</span>
        <span class="bk-kills ${r.kills ? '' : 'zero'}">${r.kills ? '⚔️ ' + fmt(r.kills) + ' ตัว' : 'ยังไม่เคยล้ม'}</span>
        <span class="bk-mon">${r.monsters.length ? esc(r.monsters.join(' · ')) : ''}</span>
      </div>`).join('')}
    </div>`;
  }).join('');
}

// ── 🧬 สมุดธาตุ (ตารางธาตุ ครบ 7 ต่อแรงค์) ──
async function fillElemBook() {
  const d = await api('GET', '/api/web/me/books');
  document.getElementById('elemSummary').innerHTML =
    `🧬 ครบทั้ง 7 ธาตุแล้ว <b>${d.elements_done}/${d.elements_total}</b> ช่อง · ` +
    (d.complete ? '🏆 <b>สมุดสมบูรณ์ทั้ง 9 ทวีป!</b>'
                : 'ครบทุกทวีปได้สัตว์เลี้ยงขั้นสูงสุด');
  document.getElementById('elemList').innerHTML = d.continents.map(c => `
    <div class="g-card" style="margin-bottom:10px">
      <h3 style="margin-bottom:6px">${esc(c.label)}
        ${c.done ? '<span class="bk-done">🏺 ครบทั้งทวีป</span>' : ''}</h3>
      ${c.ranks.map(r => `<div class="bk-row">
        <span class="bk-rank">${esc(r.rank)} ${r.rank_done ? '✅' : ''}</span>
        <span class="el-grid">${r.elements.map(e =>
          `<i class="el-dot ${e.got ? 'got' : ''}" title="${esc(e.label)}${e.got ? ' — ล้มแล้ว ' + e.got : ' — ยังไม่เคยล้ม'}"
           >${esc(e.label.split(' ')[0])}</i>`).join('')}</span>
      </div>`).join('')}
    </div>`).join('');
}

// ── 🎟️ ซีซั่นพาส + ⭐ สายพรีเมียม ──
async function fillSeason() {
  const d = await api('GET', '/api/web/me/season');
  document.getElementById('seasonHead').innerHTML =
    `🎟️ แต้มซีซั่นนี้ <b>${fmt(d.points)}</b> · สาย${d.premium ? '<b>พรีเมียม ⭐</b>' : 'ฟรี'}`;
  document.getElementById('seasonList').innerHTML = d.tiers.map(t => {
    const rw = o => [o.gold ? fmt(o.gold) + ' ทอง' : '', o.exp ? fmt(o.exp) + ' EXP' : '',
                     o.item ? 'ไอเทม' : ''].filter(Boolean).join(' + ') || '—';
    return `<div class="kv"><span>${t.reached ? '✅' : '🔒'} ${fmt(t.points)} แต้ม</span>
      <b>ฟรี: ${rw(t.free)}${d.premium ? ' · ⭐ ' + rw(t.premium) : ''}</b></div>`;
  }).join('');
  document.getElementById('seasonClaim').onclick = async () => {
    try { toast((await api('POST', '/api/web/me/season/claim')).message); fillSeason(); boot(); }
    catch (e) { toast(e.message, true); }
  };
  // ราคาต้องอยู่บนปุ่มตั้งแต่ยังไม่กด — ไม่ใช่ไปเห็นตอนป็อปอัพเด้ง
  const buy = document.getElementById('seasonBuy');
  buy.innerHTML = d.premium
    ? '<span class="ic">⭐</span>เปิดสายพรีเมียมแล้ว'
    : `<span class="ic">⭐</span>ซื้อสายพรีเมียม<span class="sub">${fmt(d.premium_price)} ทอง</span>`;
  buy.disabled = d.premium || !d.enabled;
  if (!d.enabled) buy.title = 'ตอนนี้ยังไม่เปิดซีซั่นพาส';
  buy.onclick = async () => {
    if (!await confirmAction({ title: '⭐ ซื้อสายพรีเมียม',
                               message: 'ปลดรางวัลสายพรีเมียมของซีซั่นนี้ทั้งหมด',
                               lines: [['ราคา', fmt(d.premium_price) + ' ทอง']],
                               okText: 'ซื้อเลย' })) return;
    try { toast((await api('POST', '/api/web/me/season/premium')).message); fillSeason(); boot(); }
    catch (e) { toast(e.message, true); }
  };
}

// ── 💍 คู่หู ──
async function fillPartner() {
  const d = await api('GET', '/api/web/me/partner');
  document.getElementById('partnerCard').innerHTML = d.partner_id
    ? `<div class="kv"><span>คู่หูปัจจุบัน</span><b>&lt;@${esc(d.partner_id)}&gt;</b></div>
       <div class="kv"><span>โบนัสตอนนี้</span><b>×${d.bonus_mult}</b></div>
       <div class="kv"><span>วันนี้เล่นด้วยกันแล้ว</span><b>${d.played_today ? '✅ ได้โบนัส' : '⏳ ยังไม่ได้'}</b></div>
       ${d.note ? `<p class="g-note">${esc(d.note)}</p>` : ''}`
    : `<div class="kv"><span>สถานะ</span><b>ยังไม่มีคู่</b></div>
       <div class="kv"><span>${esc(d.ring.name)}</span>
         <b>${d.ring.has ? '✅ มีแหวนแล้ว' : fmt(d.ring.price) + ' ทอง'}</b></div>` +
      (d.history.length ? `<div class="kv"><span>เคยแต่งมาแล้ว</span><b>${d.history.length} ครั้ง</b></div>` : '');
}
