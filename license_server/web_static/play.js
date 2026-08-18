// หน้าเล่นเกม Fragment Rift
// ตัวละคร/กระเป๋า/ธนาคาร/ทองคำแท่ง/คราฟ/ร้านค้า/คาสิโน = ข้อมูลจริง เรียกฟังก์ชันชุดเดียวกับบอทดิส
// ร้านยศ/กาชา/ทอยเต๋า = ยังเป็นโครงหน้า (เฟส 7-8)
// กติกา: ไม่มีกฎเกมในไฟล์นี้ — เซิร์ฟเวอร์คำนวณทุกอย่าง ที่นี่แค่วาดกับถามยืนยัน
renderChrome("/play");

// ▴ ย่อแถบข้อมูลนักผจญภัยด้านบน — บนมือถือมันตัดเป็น 3 แถวจนบังจอเกม
// ย่อแล้วเหลือแค่แถวปุ่ม (เลือด/เงินยังดูได้ที่การ์ดใต้ฉากอยู่แล้ว ไม่ได้หายไปไหน)
const minBtn = document.getElementById('playMin');
if (minBtn) {
  const paint = () => {
    const min = document.body.classList.contains('bar-min');
    minBtn.textContent = min ? '▾' : '▴';
    minBtn.title = min ? 'กางแถบข้อมูล' : 'ย่อแถบข้อมูล';
  };
  minBtn.addEventListener('click', () => {
    document.body.classList.toggle('bar-min');
    localStorage.setItem('barMin', document.body.classList.contains('bar-min') ? '1' : '0');
    paint();
  });
  if (localStorage.getItem('barMin') === '1') document.body.classList.add('bar-min');
  paint();
}

// ⛶ ขยายเต็มจอ — คลาส .fullscreen คือตัวจริงที่ทำให้เต็มจอ (ซ่อนแถบเมนู/ท้ายหน้า)
// ส่วน Fullscreen API ของเบราว์เซอร์เป็นของแถม: เดสก์ท็อป/แอนดรอยด์ได้เต็มจอจริงถึงขอบ
// iPhone ไม่รองรับ requestFullscreen กับ element ทั่วไป — จึงต้องมีคลาสนี้เป็นหลัก
const fullBtn = document.getElementById('playFull');
if (fullBtn) {
  const on = () => document.body.classList.contains('fullscreen');
  const paint = () => { fullBtn.textContent = on() ? '⤢' : '⛶';
                        fullBtn.title = on() ? 'ออกจากเต็มจอ' : 'ขยายเต็มจอ'; };
  const setFull = want => {
    document.body.classList.toggle('fullscreen', want);
    try {
      if (want && !document.fullscreenElement) document.documentElement.requestFullscreen?.();
      if (!want && document.fullscreenElement) document.exitFullscreen?.();
    } catch (e) { /* เบราว์เซอร์ไม่ให้ก็ยังเต็มจอด้วย CSS ได้ */ }
    paint();   // ฉากเป็น canvas 320x132 ที่ CSS ยืดให้เอง ไม่ต้องสั่งวาดใหม่
  };
  fullBtn.addEventListener('click', () => setFull(!on()));
  // กด Esc หรือปัดออกจากเต็มจอของเบราว์เซอร์ — ต้องถอดคลาสตามให้ตรงกัน
  document.addEventListener('fullscreenchange', () => {
    if (!document.fullscreenElement && on()) setFull(false);
  });
  document.addEventListener('keydown', e => { if (e.key === 'Escape' && on()) setFull(false); });
  paint();
}

// 🔊 ปุ่มเปิด/ปิดเสียง — แยกเอฟเฟกต์กับเพลงพื้นหลัง จำค่าที่เลือกไว้ข้ามครั้ง
const sfxBtn = document.getElementById('playSfx');
if (sfxBtn) {
  const paint = () => { sfxBtn.textContent = SFX.enabled ? '🔊' : '🔇';
                        sfxBtn.title = SFX.enabled ? 'ปิดเสียงเอฟเฟกต์' : 'เปิดเสียงเอฟเฟกต์'; };
  paint();
  sfxBtn.addEventListener('click', () => { SFX.toggle(); paint(); });
}
const bgmBtn = document.getElementById('playBgm');
if (bgmBtn) {
  const paint = () => { bgmBtn.textContent = SFX.musicEnabled ? '🎵' : '🔕';
                        bgmBtn.title = SFX.musicEnabled ? 'ปิดเพลงพื้นหลัง' : 'เปิดเพลงพื้นหลัง'; };
  paint();
  bgmBtn.addEventListener('click', () => { SFX.toggleMusic(); paint(); });
}

// เพลงพื้นหลังของแต่ละทวีป — โทนตามบรรยากาศฉาก ไม่ใช่ทวีปละเพลงให้เปลืองเปล่า
const CONT_MOOD = { main: 'field', sylvan: 'field', skyward: 'field',
                    demon: 'dark', nether: 'dark',
                    volcanic: 'forge', mechanized: 'forge',
                    frozen: 'deep', ocean: 'deep' };
let IN_FIGHT = false, SCENE_EVENT = '';

/** เลือกเพลงให้ตรงกับสิ่งที่อยู่ตรงหน้า — สู้อยู่ = เพลงต่อสู้ แวะหมู่บ้าน = เพลงเมือง ไม่งั้นตามทวีป */
function sceneMusic() {
  if (IN_FIGHT) return SFX.music('battle');
  if (SCENE_EVENT === 'village') return SFX.music('town');
  SFX.music(CONT_MOOD[(LAST && LAST.identity.continent) || 'main'] || 'field');
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
document.getElementById('frAdd')?.addEventListener('click', addFriend);
document.getElementById('wmNew')?.addEventListener('click', () => wmNewMatch(0));
document.getElementById('wmSame')?.addEventListener('click', () => {
  const seed = prompt('วางรหัสแผนที่ที่อยากเปิด', document.getElementById('wmSeed').textContent);
  if (seed && /^\d+$/.test(seed.trim())) wmNewMatch(seed.trim());
});
document.getElementById('wmFire')?.addEventListener('click', () => WM_SKILL && wmAttack(WM_SKILL));
['wmAngle', 'wmPower'].forEach(id => document.getElementById(id)?.addEventListener('input', e => {
  document.getElementById(id === 'wmAngle' ? 'wmAngVal' : 'wmPowVal').textContent =
    e.target.value + (id === 'wmAngle' ? '°' : '');
}));
document.getElementById('wmIn')?.addEventListener('click', () => wmZoom(1));
document.getElementById('wmOut')?.addEventListener('click', () => wmZoom(-1));
document.getElementById('wmFit')?.addEventListener('click', () => {
  WM_CAM?.fit(); document.getElementById('wmZoom').textContent = '×' + WM_CAM.z; });

// ปุ่มบนจอ (มือถือ) — กดค้างเดินต่อเนื่อง
const WM_ACT = { left: ['walk', -1], right: ['walk', 1], jumpL: ['jump', -1], jumpR: ['jump', 1] };
document.querySelectorAll('[data-wm]').forEach(b => {
  const a = WM_ACT[b.dataset.wm];
  // ต้องห่อด้วยลูกศร ไม่งั้น MouseEvent จะถูกส่งไปเป็นชื่อคำสั่ง เซิร์ฟเวอร์ปฏิเสธทุกครั้ง
  if (!a) { b.addEventListener('click', () => wmEndTurn()); return; }
  b.addEventListener('pointerdown', e => { e.preventDefault(); wmHoldStart(a[0], a[1]); });
  ['pointerup', 'pointerleave', 'pointercancel'].forEach(ev =>
    b.addEventListener(ev, wmHoldStop));
});

// คีย์บอร์ด (คอม) — ทำงานเฉพาะตอนอยู่หน้าสนามรบ
const WM_KEY = { ArrowLeft: ['walk', -1], ArrowRight: ['walk', 1],
                 ArrowUp: ['jump', 1], ' ': ['jump', 1] };
document.addEventListener('keydown', e => {
  if (!document.getElementById('v-worms')?.classList.contains('on')) return;
  if (e.repeat) return;
  if (e.key === 'Enter') return void wmEndTurn();
  const a = WM_KEY[e.key];
  if (!a) return;
  e.preventDefault();
  wmHoldStart(a[0], e.key === 'ArrowUp' || e.key === ' '
              ? (WM_ST && wmMe().face < 0 ? -1 : 1) : a[1]);
});
document.addEventListener('keyup', wmHoldStop);
document.getElementById('wmSame')?.addEventListener('click', async () => {
  const seed = prompt('วางรหัสแผนที่ที่อยากเปิด', document.getElementById('wmSeed').textContent);
  if (seed && /^\d+$/.test(seed.trim())) wormsReroll(seed.trim());
});
document.getElementById('frInput')?.addEventListener('keydown',
  e => { if (e.key === 'Enter') addFriend(); });

// ── สไปรต์ตัวละคร (เฟส 1.2 — เอนจินอยู่ใน sprite.js) ──
let LAST = null;                 // ข้อมูลตัวละครล่าสุดจาก API
let CHAR = { race: null, cls: null, armor: 'None', weapon: null, pose: 'idle' };

// ✨ ออร่าต้องขยับ "ทุกที่ที่มีตัวละคร" ไม่ใช่แค่ในฉากผจญภัย
// ฉากผจญภัยวาดใหม่ทุกเฟรมอยู่แล้ว แต่รูปโปรไฟล์/หัวการ์ดวาดครั้งเดียว ออร่าเลยค้างเป็นภาพนิ่ง
// ตรงนี้เก็บรายชื่อจอพวกนั้นไว้ แล้ววาดซ้ำให้ — เฉพาะตอนที่ใส่ออร่าอยู่ (ไม่ใส่ = ไม่กินแบตเปล่า)
const AURA_CANVASES = [];
let auraLoop = 0;

function auraRepaint(cv, draw) {
  if (!cv) return;
  if (!AURA_CANVASES.some(a => a.cv === cv)) AURA_CANVASES.push({ cv, draw });
  draw();
  if (auraLoop) return;
  const tick = () => {
    if (!((CHAR.fashion || {}).aura)) { auraLoop = 0; return; }   // ถอดออร่าแล้วหยุดลูป
    AURA_CANVASES.forEach(a => { try { a.draw(); } catch (e) { /* จอหาย ไม่ต้องพัง */ } });
    auraLoop = requestAnimationFrame(tick);
  };
  auraLoop = requestAnimationFrame(tick);
}

function drawSprite(cv, scale) {
  auraRepaint(cv, () => {
    const ctx = cv.getContext('2d');
    ctx.clearRect(0, 0, cv.width, cv.height);
    const s = scale || Math.max(1, Math.floor(cv.width / 18));
    drawCharacter(ctx, (cv.width - 16 * s) / 2, 2, s, CHAR);
  });
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
  if (id === 'atlas') fillAtlas().catch(e => toast(e.message, true));
  if (id === 'fashion') fillFashion().catch(e => toast(e.message, true));
  if (id === 'fgacha') fillFashionGacha().catch(e => toast(e.message, true));
  if (id === 'friends') fillFriends().catch(e => toast(e.message, true));
  if (id === 'worms') fillWorms().catch(e => toast(e.message, true));
  if (id === 'market') fillMarket().catch(e => toast(e.message, true));
  if (id === 'season') fillSeason().catch(e => toast(e.message, true));
  if (id === 'partner') fillPartner().catch(e => toast(e.message, true));
  if (id === 'slots' || id === 'hilo' || id === 'bj') buildChips();
  if (id === 'bj') bjRestore();
  if (id === 'scene') initScene().catch(e => toast(e.message, true));

  // เพลงคลอเฉพาะหน้าที่มีบรรยากาศ — หน้าอื่นเงียบ ไม่ต้องมีเสียงตอนนั่งอ่านตาราง
  if (id === 'scene') sceneMusic();
  else if (id === 'slots' || id === 'hilo' || id === 'bj') SFX.music('casino');
  else SFX.music(null);
  window.scrollTo({ top: document.getElementById('shell').offsetTop - 80, behavior: 'smooth' });
}
document.querySelectorAll('[data-go]').forEach(b => {
  if (b.classList.contains('soon')) return;
  b.addEventListener('click', () => showPanel(b.dataset.go));
});
document.querySelectorAll('[data-back]').forEach(b =>
  b.addEventListener('click', () => showPanel('home')));
document.querySelectorAll('[data-friends-back]').forEach(b =>
  b.addEventListener('click', () => showPanel('friends')));

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

/** 🔌 ยศต้องให้บอทเป็นคนแจก บอทดับเมื่อไหร่ก็ซื้อไม่ได้ — บอกไว้ก่อนกด */
function botOfflineBanner(online) {
  return online ? '' : `<div class="g-note bot-off">🔌 <b>บอทดิสคอร์ดออฟไลน์อยู่</b> —
    ยศต้องให้บอทเป็นคนมอบ ตอนนี้จึงซื้อไม่ได้ กลับมาลองใหม่เมื่อบอทออนไลน์</div>`;
}

async function fillRoleShop() {
  chipRow(document.getElementById('roleFactions'), FACTIONS, v => {
    ROLE_FACTION = v; fillRoleShop();
  }, ROLE_FACTION);
  const box = document.getElementById('roleList');
  box.innerHTML = '<div class="g-note">กำลังโหลด...</div>';
  try {
    const d = await api('GET', '/api/web/roleshop?faction=' + ROLE_FACTION);
    box.innerHTML = botOfflineBanner(d.bot_online) + d.roles.map((r, i) => `
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
    SFX.play('buy');                      // จ่ายเงินแล้ว — ที่เหลือรอบอทในดิสมอบยศ
    toast('กำลังมอบยศ ' + r.label + '...');
    boot();
    const t = await waitTicket(res.ticket);
    const msg = { done: '🎉 ได้รับยศ ' + r.label + ' แล้ว!',
                  refunded: '↩️ มอบยศไม่สำเร็จ — ' + (t.note || 'คืนเงินแล้ว'),
                  duplicate: '❌ คุณมียศนี้อยู่แล้ว' }[t.status] || t.note || 'รอบอทมอบยศ';
    SFX.play(t.status === 'done' ? 'reward' : 'error');   // รอนานแล้วต้องรู้ผลโดยไม่ต้องจ้องจอ
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
    document.getElementById('gachaOffline').innerHTML = botOfflineBanner(d.bot_online);
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
  SFX.play('gacha');                        // ลูกแก้วกลิ้งคลอไปตลอดจังหวะหมุน
  try {
    const res = await api('POST', '/api/web/roleshop',
                          { faction: GACHA_FACTION, action: 'gacha' });
    await new Promise(r => setTimeout(r, 1500));      // ให้ลูกแก้วหมุนเห็น ๆ ก่อนเฉลย
    machine.classList.remove('spin');
    machine.classList.add('pop');
    SFX.play('reward');
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
      SFX.play('error');                    // เกลือ — เสียงต้องไม่เหมือนตอนแจ็คพอตแตก
      state.textContent = '💀 เกลือ! คุณมียศนี้อยู่แล้ว';
    } else if (t.status === 'refunded') {
      card.className = 'gacha-card fail';
      SFX.play('error');
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
    SFX.play('reward');
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
  const spTile = document.getElementById('tileSeasonSub');
  if (spTile) {                                    // ป้ายบนปุ่มซีซั่นพาส — มีของค้างรับไหม
    const n = (g.season && g.season.claimable) || 0;
    spTile.textContent = n ? `🎁 ${n} ช่องรอรับ` : 'รางวัล + สายพรีเมียม';
  }

  // ตัวละครประกอบจากของที่สวมจริง — เผ่า/คลาส/เกราะ/อาวุธ มาจาก DB ทั้งหมด
  CHAR = { race: id.race, cls: id.class_name,
           armor: g.gear.armor.key, weapon: g.gear.weapon.key, pose: 'idle',
           fashion: g.fashion || {} };   // 👗 แฟชั่นสวมทับตอนวาด ของจริงไม่ขยับ
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
  const dur = (o, icon) => {
    if (!o || o.dur == null) return '';
    const pct = o.dur_pct ?? 0;
    return `<span title="${esc(o.name || '')} ${fmt(o.dur)}/${fmt(o.dur_max)}">` +
      `${icon} <b class="${pct < 30 ? 'low' : ''}">${pct}%</b>` +
      (pct <= 0 ? ' <b class="low">พัง</b>' : '') + '</span>';
  };
  document.getElementById('advGear').innerHTML =
    dur(g.gear.weapon, '⚔️') + dur(g.gear.armor, '🛡️');

  // 🧬 สถานะติดตัว — จะได้รู้ว่าทำไมทอยได้ 0 ไม่ต้องเดาว่าบัคไหม
  document.getElementById('advBuffs').innerHTML = (g.buffs || []).map(b =>
    `<span class="${BAD_STATUS.test(b.label) ? 'bad' : ''}" title="${esc(b.label)}">${esc(b.label)}` +
    (b.no_tick ? '' : ` <b>${b.turns}</b>${esc(b.unit || '')}`) + '</span>').join('');

  const face = document.getElementById('advFace');
  auraRepaint(face, () => {
    const ctx = face.getContext('2d');
    ctx.clearRect(0, 0, face.width, face.height);
    drawCharacter(ctx, (face.width - 16 * 3) / 2, -6, 3, CHAR);   // ครึ่งตัวบนพอดีกรอบ
  });
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

  // 🎲 สรุปเต๋า — ตอบคำถามที่ถามบ่อยว่าทอยได้สูงสุดเท่าไหร่ เพราะอะไร
  // ค่าทุกตัวมีค่าสำรอง: เซิร์ฟเวอร์เวอร์ชันเก่ายังไม่ส่ง dice มา ต้องไม่ขึ้น undefined ให้ผู้เล่นเห็น
  const dc = g.dice || {};
  const num = (v, dflt) => (Number.isFinite(+v) ? +v : dflt);
  const own = num(dc.own_dice, 1), petN = num(dc.pet_dice, 0);
  const lo = num(dc.normal_min, 8), hi = num(dc.normal_max, 18);
  const skMax = num(dc.skill_max, 20), petMax = num(dc.pet_die_max, 6);
  const flat = num(dc.bonus_total, 0), per = num(dc.level_per_die, 25);
  const total = num(dc.dice_count, own + petN);
  const capN = num(dc.normal_cap, own * hi + petN * petMax + flat);
  const capS = num(dc.skill_cap, own * skMax + petN * petMax + flat);

  document.getElementById('prDice').textContent =
    `${total} ลูก` + (petN ? `  (ตัวเอง ${own} + สัตว์เลี้ยง ${petN})` : '');

  const line = [];
  line.push(`🧍 <b>ของตัวเอง ${own}</b> ลูก  <small>(ฐาน 1 + จากเลเวล ${num(dc.level_dice, 0)})</small>`);
  line.push(petN
    ? `🐾 <b>สัตว์เลี้ยง +${petN}</b> ลูก — ${esc(dc.pet_name || 'ที่พาไปด้วย')} <small>(ลูกละ 1-${petMax})</small>`
    : `🐾 <span style="color:#a99274">ยังไม่ได้พาสัตว์เลี้ยงไปด้วย — พาไปจะได้เต๋าเพิ่มอีก</span>`);
  line.push(`⚔️ ตีปกติ ลูกละ <b>${lo}-${hi}</b>` + (flat ? ` + โบนัส <b>${flat}</b>` : '') +
            ` → สูงสุด <b class="cap">${capN}</b>`);
  line.push(`✨ ใช้สกิล ลูกละ <b>1-${skMax}</b>` + (flat ? ` + โบนัส <b>${flat}</b>` : '') +
            ` → สูงสุด <b class="cap">${capS}</b>`);
  line.push(`📈 ได้เต๋าเพิ่ม 1 ลูกทุก <b>${per}</b> เลเวล` +
            (Number.isFinite(+dc.next_die_at) ? ` · ลูกถัดไปที่ <b>Lv ${dc.next_die_at}</b>` : ''));
  if ((dc.bonus || []).length)
    line.push(dc.bonus.map(b => `${esc(b.from)} <b>+${b.value}</b>`).join(' · '));
  document.getElementById('prDiceDetail').innerHTML = line.join('<br>');

  const durBar = o => {
    if (!o || o.dur == null) return '';
    const pct = o.dur_pct ?? 0;
    return `<div class="dur${pct < 30 ? ' low' : ''}"><i style="width:${pct}%"></i></div>` +
      `<span class="dur-pct${pct < 30 ? ' low' : ''}">ความทนทาน ${pct}% ` +
      `<small>(${fmt(o.dur)}/${fmt(o.dur_max)})</small>` +
      (pct <= 0 ? ' — พังแล้ว! ไม่ได้โบนัส' : pct < 30 ? ' — ใกล้พัง' : '') + '</span>';
  };
  document.getElementById('prGear').innerHTML = `
    <div class="slot-card"><div class="ic">🛡️</div><div style="min-width:0">
      <div class="t">เกราะ</div><div class="v">${esc(gear.armor.name)}</div>${durBar(gear.armor)}</div></div>
    <div class="slot-card"><div class="ic">⚔️</div><div style="min-width:0">
      <div class="t">อาวุธ</div><div class="v">${esc(gear.weapon.name)}</div>${durBar(gear.weapon)}</div></div>`;

  const bf = document.getElementById('prBuffs');
  document.getElementById('prBuffCard').style.display = g.buffs.length ? '' : 'none';
  bf.innerHTML = g.buffs.map(b =>
    `<span>${esc(b.label)} ${b.no_tick ? '<b>ค้างไว้</b>' : `<b>${b.turns}</b> ${esc(b.unit)}`}</span>`).join('');

  const big = document.getElementById('bigChar');
  auraRepaint(big, () => {
    const ctx = big.getContext('2d');
    ctx.clearRect(0, 0, big.width, big.height);
    drawCharacter(ctx, (big.width - 16 * 8) / 2, 4, 8, CHAR);   // ตัวใหญ่ ×8
  });
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
      ${it.usable ? `<span class="badge">${it.kind === 'equip' ? 'สวมได้' : 'ใช้ได้'}</span>` : ''}
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

/** ถามตัวเลขหนึ่งค่า — คืนจำนวนเต็มบวก หรือ null เมื่อยกเลิก/กรอกไม่ถูก
 *  max: ใส่แล้วจะมีปุ่มลัด (×1 ×5 ×10 สูงสุด) และตัดค่าที่เกินให้เอง
 *  (เช็คค่าจริงอีกรอบที่เซิร์ฟเวอร์เสมอ ตรงนี้แค่กันพิมพ์ผิดให้ผู้เล่น) */
function askNumber({ title, message, lines, placeholder, okText, max, value }) {
  return new Promise(resolve => {
    const box = document.getElementById('cfLines');
    openDialog({
      title, message, lines,
      buttons: [{ label: 'ยกเลิก', value: null },
                { label: okText || 'ตกลง', value: true, cls: 'yes' }],
    }).then(v => {
      const raw = (box.querySelector('input') || {}).value;
      box.querySelector('.ask-row')?.remove();
      let n = Math.floor(Number(String(raw || '').replace(/[, ]/g, '')));
      if (max) n = Math.min(n, max);
      resolve(v === true && Number.isFinite(n) && n > 0 ? n : null);
    });

    const row = document.createElement('div');
    row.className = 'ask-row';
    const picks = max ? [1, 5, 10, 50, max].filter((n, i, a) =>
      n >= 1 && n <= max && a.indexOf(n) === i) : [];
    row.innerHTML =
      (picks.length > 1 ? `<div class="ask-chips">${picks.map(n =>
        `<button type="button" data-n="${n}">${n === max ? 'สูงสุด ' + fmt(n) : '×' + n}</button>`
      ).join('')}</div>` : '') +
      `<input type="number" inputmode="numeric" min="1" step="1"${max ? ` max="${max}"` : ''}
         ${value ? `value="${value}"` : ''} placeholder="${esc(placeholder || '')}">`;
    box.appendChild(row);
    box.style.display = '';

    const input = row.querySelector('input');
    row.querySelectorAll('[data-n]').forEach(b => b.onclick = () => {
      input.value = b.dataset.n; input.focus(); input.select();
    });
    input.focus();
    input.select();
    input.onkeydown = e => {                       // กด Enter = ตกลง ไม่ต้องเอื้อมไปกดปุ่ม
      if (e.key === 'Enter') document.querySelector('#cfBtns button.yes')?.click();
    };
  });
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
    if (r.ok !== false) SFX.play('bank');
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
      if (r.ok !== false) SFX.play('gold');
      toast(r.message, !r.ok);
      if (r.ok) await reload();
    } catch (e) { toast(e.message, true); }
  };
  box.querySelectorAll('[data-bar-buy]').forEach(b => b.onclick = () => run(b.dataset.barBuy, 'buy'));
  box.querySelectorAll('[data-bar-sell]').forEach(b => b.onclick = () => run(b.dataset.barSell, 'sell'));
}

// ── ใช้ไอเทมจากกระเป๋า ──
async function useItem(id, name, kind) {
  const eq = kind === 'equip';
  const ok = await confirmAction({
    // สวมใส่ = ของชิ้นเก่าหายไปเลย ไม่ได้คืนกระเป๋า ต้องเตือนให้ชัดกว่ากดใช้ยา
    title: eq ? '⚔️ ยืนยันสวมใส่' : '🧪 ยืนยันใช้ไอเทม',
    message: eq ? 'ของที่ใส่อยู่เดิมจะหายไปเลย เอากลับไม่ได้ — และชิ้นนี้จะหายจากกระเป๋า'
                : 'ไอเทมจะถูกใช้ทันทีและหายจากกระเป๋า 1 ชิ้น',
    lines: [['ไอเทม', name], [eq ? 'สวมใส่' : 'ใช้ไป', '1 ชิ้น', 'warn']],
    okText: eq ? 'ยืนยันสวมใส่' : 'ยืนยันใช้',
  });
  if (!ok) return;
  try {
    const r = await api("POST", "/api/web/item/use", { item_id: id });
    toast(r.message, !r.ok);
    if (r.ok) { SFX.play(eq ? 'equip' : 'use'); await reload(); }
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
  SFX.play('slot');
  await wait(700);
  for (let i = 0; i < 3; i++) {
    await wait(430);
    reels[i].classList.remove('spin');
    reels[i].querySelector('span').textContent = res.reels[i];
    SFX.play('reel');                       // ก๊อก...ก๊อก...ก๊อก ทีละวง ให้ลุ้นทีละอัน
    if (i === 2) clearInterval(flick);
  }
  if (res.winnings) reels.forEach(r => r.classList.add('hit'));
  SFX.play(res.winnings ? 'win' : 'lose');
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
  SFX.play('dice');
  await wait(620);
  clearInterval(flick);
  res.dice.forEach((v, i) => dice[i].textContent = v);
  SFX.play('reel');
  await wait(150);
  SFX.play(res.winnings ? 'win' : 'lose');
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
  // 🎭 สัปดาห์ธีมปลอมตัว: มีปุ่มตรวจตัวตนเพิ่มมา — เข้าไปคุยดื้อ ๆ กับตัวปลอมจะโดนซุ่มตี
  npc: g => [...((g.encounter && g.encounter.masquerade)
                 ? [['inspect', `🔍 ตรวจสอบตัวตน (${fmt(g.encounter.inspect_fee)} ทอง)`, 'danger',
                     'จ่ายค่าตรวจ (มีแว่นส่องสัจจะใช้ฟรี) — ถ้าเป็นของปลอมจะได้เปรียบตอนเข้าปะทะ']]
                 : []),
             ['talk', '💬 เข้าไปพูดคุย', 'hot'],
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

// เหตุการณ์ -> เสียงตอนเจอ (เหตุการณ์ 'travel' ใช้เสียงตามพาหนะ ดูใน advWalk)
// ฟังแล้วต้องรู้เลยว่าเจออะไร ไม่ต้องรออ่านข้อความ
const EVENT_SFX = { calm: 'calm', village: 'village', treasure: 'treasure', trap: 'trap',
                    dungeon: 'dungeon', monster: 'foe', npc: 'npc', special: 'special',
                    bank_robbery: 'danger', mugging: 'danger' };

// เหตุการณ์ -> คีย์ภาพในโฟลเดอร์ assets/events (ชื่อเดียวกับที่ดิสใช้)
const ADV_ART = { calm: 'calm', fastwalk: 'calm', village: 'village', treasure: 'treasure', trap: 'trap',
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
  btn.onclick = () => advWalk(1);
  box.appendChild(btn);

  // ⏩ เดินเร็ว — ข้ามช่วงที่ไม่มีอะไรให้ตัดสินใจ แลกกับการไม่เจอหีบ/NPC/อีเวนต์พิเศษ
  const fast = document.createElement('button');
  fast.className = 'g-tile casino-go';
  fast.innerHTML = '<span class="ic">⏩</span>เดินเร็ว ×5';
  fast.title = 'เดินรวดจนเจอ มอน · ดันเจี้ยน · โจร · หมู่บ้าน · กับดัก · พาหนะข้ามทวีป\n'
             + '(ระหว่างทางจะไม่แวะหีบสมบัติ NPC หรืออีเวนต์พิเศษ)';
  fast.onclick = () => advWalk(5);
  box.appendChild(fast);
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
    SFX.play('revive');                               // 🏥 ลุกกลับมาแล้ว
    SCENE.clearFoe(); SCENE.clearRoll();
    document.getElementById('foeBar').hidden = true;
    SCENE.setMap((LAST && LAST.identity.continent) || 'main');
    SCENE.showEvent('village');
    IN_FIGHT = false; SCENE_EVENT = 'village'; sceneMusic();
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

async function advWalk(steps) {
  if (ADV_BUSY) return;
  ADV_BUSY = true;
  const fast = steps > 1;
  const tag = document.getElementById('sceneTag');
  SFX.walking(true);                    // 👣 ฝีเท้าดังไปเรื่อย ๆ จนกว่าจะถึงจุดหมาย
  SCENE.clearFoe(); SCENE.clearRoll(); SCENE.walk(fast);   // ⏩ เดินเร็ว = ฉากเร่งสปีด
  document.getElementById('foeBar').hidden = true;
  tag.textContent = fast ? 'กำลังเดินเร็ว...' : 'กำลังเดินทาง...';
  document.getElementById('advActions').innerHTML = '';
  document.getElementById('advText').textContent = fast
    ? '⏩ คุณเร่งฝีเท้า มุ่งหน้าไปข้างหน้าโดยไม่แวะข้างทาง...'
    : '✨ คุณเริ่มก้าวเท้าออกเดินทางตรวจตราเส้นทาง...';

  try {
    const g = await api('POST', '/api/web/adventure/walk?steps=' + (fast ? 5 : 1));
    await new Promise(r => setTimeout(r, fast ? 1400 : 900));   // เดินเร็วให้เห็นระยะทางนานกว่า
    SFX.walking(false);                               // ถึงที่แล้ว หยุดเดิน
    SCENE.setMap(g.continent || 'main');
    const art = g.event === 'travel' ? 'vehicle_' + g.encounter.vehicle : ADV_ART[g.event];
    if (art) SCENE.showEvent(art); else SCENE.idle();
    tag.textContent = ADV_LABEL[g.event] || g.event;
    // ล้มกลางทางจากพิษ/สถานะ หรือโดนอีเวนต์พิเศษเล่นจนหมดสติ
    if (g.event === 'death' || g.died) {
      SCENE.killHero();
      SFX.play('lose');
      IN_FIGHT = false; SCENE_EVENT = ''; sceneMusic();
      advPaint({ text: g.text, notes: g.notes });
      advRespawnButton(document.getElementById('advActions'));
      boot();
      return;
    }
    SFX.play(g.event === 'travel' ? 'veh_' + g.encounter.vehicle : EVENT_SFX[g.event]);
    if (g.item || g.got_item) SFX.play('item');
    paintFoe(g.monster);
    IN_FIGHT = !!g.monster; SCENE_EVENT = g.event; sceneMusic();
    if (g.money != null) boot();      // เงิน/เลือดเปลี่ยน วาดหัวการ์ดใหม่
    if (g.fast && g.walked > 1) g.text = `⏩ **เดินเร็วมา ${g.walked} ก้าว**\n${g.text || ''}`;
    advPaint(g);
  } catch (e) {
    SCENE.idle();
    toast(e.message, true);
    advIdleButton(document.getElementById('advActions'));
  } finally { ADV_BUSY = false; SFX.walking(false); }   // ทางออกสุดท้าย — เน็ตหลุดก็ต้องหยุดเดิน
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
    if (action === 'open') SFX.play('chest');   // ฝาหีบเอี๊ยด — เล่นตอนกด ไม่ต้องรอเซิร์ฟเวอร์เฉลย
    if (action === 'rest') SFX.play('rest');    // 🛏️ พักแรมที่หมู่บ้าน

    const r = await api('POST', '/api/web/adventure/act', { action: action });

    if (r.fx) {                                        // กับดักลั่นก่อน แล้วค่อยเฉลยเต๋า
      SCENE.playTrap(r.fx.kind, r.fx.hit);
      SFX.play('trap');
      await new Promise(res => setTimeout(res, 420));
    }
    if (r.roll) {
      SCENE.showRoll(r.roll);
      await new Promise(res => setTimeout(res, 750));      // ให้เห็นเต๋าเฉลยก่อนตัวเลขเด้ง
    }
    // อีเวนต์พิเศษ/กับดักเล่นจนหมดสติ — ต้องมีปุ่มฟื้นคืนชีพ ไม่ใช่ค้างอยู่เฉย ๆ
    if (r.died) {
      SFX.play('lose');
      IN_FIGHT = false; sceneMusic();
      SCENE.killHero();
      await new Promise(res => setTimeout(res, 900));
      advPaint({ text: r.text });
      advRespawnButton(document.getElementById('advActions'));
      boot();
      return;
    }
    if (r.damage_to_monster) {                          // มอนกินดาเมจ — เข้าแรงเสียงหนักกว่า
      SCENE.hitFoe(); SCENE.float('-' + fmt(r.damage_to_monster), '', 72);
      const foeMax = (r.monster && r.monster.hp_max) || 0;
      SFX.play(foeMax && r.damage_to_monster >= foeMax / 4 ? 'foecrit' : 'foehit');
    }
    if (r.damage_to_player) SFX.play('hurt');
    // หนีแล้วไม่รอด — โดนสวนกลับ ต้องมีเสียงเตือนให้รู้ตัวว่ายังไม่จบ
    if (action === 'flee' && r.outcome === 'continue') SFX.play('caught');
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
      IN_FIGHT = false; sceneMusic();
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
    if (r.item || r.got_item) SFX.play('item');
    if (r.monster !== undefined) paintFoe(r.pending === 'monster' ? r.monster : null);
    if (r.damage) { SCENE.hitFoe(); SCENE.float('-' + r.damage, '', 40); SFX.play('foehit'); }
    if (r.gold) { SCENE.float('+' + r.gold, 'gold', 50); SFX.play('coin'); }
    if (r.continent) { SCENE.setMap(r.continent); SCENE.showEvent('village'); SCENE_EVENT = 'village'; }
    IN_FIGHT = r.pending === 'monster';
    sceneMusic();                                       // จบยกแล้วเพลงต้องกลับมาตรงกับฉาก
    // ยังมีขั้นต่อ (ข้อเสนอเควส / คุย NPC ต่อหลังตรวจตัวตน) ก็โชว์ปุ่มต่อ
    advPaint({ text: r.text, pending: r.pending, encounter: r.encounter });
    boot();                                           // เลือด/เงิน/กระเป๋าเปลี่ยน โหลดใหม่
  } catch (e) {
    toast(e.message, true);
  } finally { ADV_BUSY = false; }
}

const ADV_LABEL = { calm: 'เส้นทางเงียบสงบ', village: 'หมู่บ้านอุ่นใจ', treasure: 'หีบสมบัติ',
                    trap: 'กับดัก', dungeon: 'ปากดันเจี้ยน', monster: 'เงาปริศนา',
                    bank_robbery: 'โจรปล้นธนาคาร', mugging: 'โดนดักปล้น', npc: 'นักเดินทาง',
                    travel: 'พาหนะข้ามทวีป', special: 'เหตุการณ์พิเศษ', death: 'หมดสติ',
                    // ⏩ ไม่ใช่ "เหตุการณ์" — คือผลของการเดินเร็วแล้วยังไม่เจออะไร
                    fastwalk: 'เดินเร็ว' };

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
    IN_FIGHT = st.pending === 'monster';                  // เพลงต้องตรงกับสิ่งที่ค้างอยู่จริง
    SCENE_EVENT = st.pending || '';
    sceneMusic();
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
    SFX.play('card');                                  // เสียงไพ่ทุกครั้งที่โต๊ะขยับ
    bjPaint(r.game);
    if (r.game.over) SFX.play(r.game.net > 0 ? 'win' : r.game.net < 0 ? 'bust' : 'reel');
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
        (it.usable ? '<span class="badge">' + (it.kind === 'equip' ? 'สวมได้' : 'ใช้ได้') + '</span>' : '') +
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
  let count = 1;

  if (buying) {
    // ซื้อทีละหลายชิ้น — เลือกจำนวนก่อน (เงิน/ที่ว่างในกระเป๋าถูกตรวจซ้ำที่เซิร์ฟเวอร์เสมอ)
    const bag = LAST ? LAST.bag : null;
    const room = bag && bag.capacity ? Math.max(0, bag.capacity - bag.used) : 99;
    const most = Math.max(1, Math.min(99, room, price > 0 ? Math.floor(cash / price) : 99));
    count = await askNumber({
      title: '🏪 ซื้อ ' + it.name,
      message: `ซื้อได้สูงสุด ${fmt(most)} ชิ้น (จำกัดด้วยเงินสดและที่ว่างในกระเป๋า)`,
      lines: [['ราคา', fmt(price) + ' ทอง/ชิ้น'],
              ['เงินสด', fmt(cash) + ' ทอง'],
              ['ที่ว่างในกระเป๋า', (bag && bag.capacity ? fmt(room) + ' ช่อง' : 'ไม่จำกัด')]],
      max: most, value: 1, okText: 'ซื้อ',
    });
    if (!count) return;
  } else {
    const ok = await confirmAction({
      title: '📦 ยืนยันขายไอเทม',
      message: 'ขายครั้งละ 1 ชิ้น ได้เป็นเงินสด',
      lines: [['ไอเทม', it.name], ['ขายได้', fmt(price) + ' ทอง', 'good'],
              ['มีอยู่', it.count + ' ชิ้น'],
              ['เงินสดหลังขาย', fmt(cash + price) + ' ทอง']],
      okText: 'ยืนยันขาย', danger: true,
    });
    if (!ok) return;
  }

  try {
    const r = await api("POST", "/api/web/shop", { action: action, item_id: it.id, count: count });
    if (r.ok) SFX.play(action === 'buy' ? 'buy' : 'coin');
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
      SFX.play(res.ok ? 'craft' : 'error');    // คราฟพลาดเสียงต้องต่างกัน ไม่ต้องอ่านข้อความก็รู้
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
    if (r.ok) { SFX.play('sellall'); await reload(); }
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
  const kind = it.kind || (it.usable ? 'use' : '');   // เซิร์ฟเวอร์เก่ายังไม่ส่ง kind มา
  const lines = [['มีอยู่', it.count + ' ชิ้น']];
  if (it.sell > 0) lines.push(['ขายได้', fmt(it.sell) + ' ทอง/ชิ้น']);
  lines.push(['ประเภท', kind === 'equip' ? 'อุปกรณ์สวมใส่'
                      : kind ? 'ของใช้ได้' : 'เก็บ/ขายอย่างเดียว']);

  const buttons = [{ label: 'ปิด', value: null }];
  if (kind) buttons.push({ label: kind === 'equip' ? '⚔️ สวมใส่' : '🧪 ใช้', value: 'use', cls: 'yes' });
  buttons.push({ label: '🗑️ ทิ้ง', value: 'drop', cls: 'danger' });

  const choice = await openDialog({ title: it.name, message: 'เลือกสิ่งที่ต้องการทำ', lines, buttons });
  if (choice === 'use') await useItem(it.id, it.name, kind);
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
        SFX.play('pet');
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
    try { toast((await api('POST', '/api/web/me/daily/claim')).message);
          SFX.play('reward'); fillDaily(); boot(); }
    catch (e) { toast(e.message, true); }
  };
}

// ── 🏅 ความสำเร็จ ──
async function fillAchv() {
  const d = await api('GET', '/api/web/me/achievements');
  const chips = [['', '— ไม่สวมฉายา —'], ...d.titles.map(t => [t, t])];
  chipRow(document.getElementById('titleChips'), chips, async v => {
    try { toast((await api('POST', '/api/web/me/title', { title: v })).message);
          SFX.play('reward'); boot(); }
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

// ── 🛒 ตลาดผู้เล่น ──
// เงินกับของขยับที่ market.py ทั้งหมด (transaction เดียว) — ที่นี่แค่ถามยืนยันแล้วส่งคำสั่ง
let MK_TAB = 'buy';
let MK = null;

async function fillMarket() {
  const box = document.getElementById('marketList');
  box.innerHTML = '<div class="g-note">กำลังโหลด...</div>';
  try { MK = await api('GET', '/api/web/market'); }
  catch (e) { box.innerHTML = '<div class="g-note">โหลดไม่สำเร็จ: ' + esc(e.message) + '</div>'; return; }

  document.getElementById('marketHead').innerHTML = MK.enabled
    ? `<div class="rolls-left">🏪 แผงที่เปิดขายอยู่ <b>${MK.listings.length}</b> ·
         ของคุณ <b>${MK.mine.length}</b>/${MK.max_listings} แผง</div>
       <small style="color:var(--g-dim)">ราคา ${fmt(MK.min_price)}–${fmt(MK.max_price)} ทอง${
         MK.tax_percent ? ` · ค่าธรรมเนียมตลาด ${MK.tax_percent}% หักจากคนขาย` : ''}
         · เงินที่ขายได้เข้าธนาคาร ไม่ใช่เงินสด</small>`
    : '<div class="rolls-left">🚫 ตอนนี้ปิดตลาดผู้เล่นอยู่</div>';

  document.querySelectorAll('[data-mk]').forEach(b =>
    b.setAttribute('aria-pressed', String(b.dataset.mk === MK_TAB)));

  if (MK_TAB === 'buy') return paintMarketBuy(box);
  if (MK_TAB === 'mine') return paintMarketMine(box);
  paintMarketSell(box);
}

function paintMarketBuy(box) {
  const others = MK.listings;
  if (!others.length) {
    box.innerHTML = '<div class="empty-bag">ยังไม่มีใครลงขายอะไรเลย — ลงขายเป็นคนแรกได้ที่แท็บ 🏷️</div>';
    return;
  }
  box.innerHTML = others.map((l, i) => `
    <div class="bar-card">
      <div class="bn">${esc(l.name)}${l.mine ? ' <span class="badge">แผงของคุณ</span>' : ''}</div>
      <div class="px"><span>ราคา</span><b>${fmt(l.price)} ทอง</b></div>
      <div class="btns"><button data-mk-buy="${i}"${l.mine ? ' disabled' : ''}>${
        l.mine ? 'ซื้อของตัวเองไม่ได้' : 'ซื้อเลย'}</button></div>
    </div>`).join('');
  box.querySelectorAll('[data-mk-buy]').forEach(b => b.onclick = () =>
    marketBuy(others[+b.dataset.mkBuy]));
}

function paintMarketMine(box) {
  if (!MK.mine.length) {
    box.innerHTML = '<div class="empty-bag">คุณยังไม่ได้ฝากขายอะไรไว้</div>';
    return;
  }
  box.innerHTML = MK.mine.map((l, i) => `
    <div class="bar-card">
      <div class="bn">${esc(l.name)}</div>
      <div class="px"><span>ตั้งราคาไว้</span><b>${fmt(l.price)} ทอง</b></div>
      <div class="btns"><button data-mk-cancel="${i}">↩️ ยกเลิก เอาของคืน</button></div>
    </div>`).join('');
  box.querySelectorAll('[data-mk-cancel]').forEach(b => b.onclick = () =>
    marketCancel(MK.mine[+b.dataset.mkCancel]));
}

function paintMarketSell(box) {
  if (!MK.bag.length) {
    box.innerHTML = '<div class="empty-bag">กระเป๋าว่างเปล่า — ออกผจญภัยเก็บของก่อนนะ</div>';
    return;
  }
  if (MK.mine.length >= MK.max_listings) {
    box.innerHTML = `<div class="g-note">แผงเต็มแล้ว (${MK.mine.length}/${MK.max_listings}) —
      ปิดแผงเก่าที่แท็บ 📦 ก่อนถึงจะลงขายเพิ่มได้</div>`;
    return;
  }
  box.innerHTML = MK.bag.map((it, i) => `
    <div class="bar-card">
      <div class="bn">${esc(it.name)} <span class="qty">×${it.count}</span></div>
      <div class="px"><span>ขายร้านได้</span><b>${fmt(it.sell)} ทอง/ชิ้น</b></div>
      <div class="btns"><button data-mk-sell="${i}">🏷️ ตั้งราคาลงขาย</button></div>
    </div>`).join('');
  box.querySelectorAll('[data-mk-sell]').forEach(b => b.onclick = () =>
    marketSell(MK.bag[+b.dataset.mkSell]));
}

async function marketBuy(l) {
  const ok = await confirmAction({
    title: '🛒 ยืนยันซื้อจากตลาด',
    message: 'จ่ายจากเงินสดในกระเป๋า — ของเข้ากระเป๋าทันที',
    lines: [['ไอเทม', l.name], ['ราคา', fmt(l.price) + ' ทอง', 'warn']],
    okText: 'ซื้อเลย',
  });
  if (!ok) return;
  try {
    const r = await api('POST', '/api/web/market', { action: 'buy', listing_id: l.id });
    SFX.play('buy'); toast(r.message); await reload(); await fillMarket();
  } catch (e) { SFX.play('error'); toast(e.message, true); }
}

async function marketCancel(l) {
  const ok = await confirmAction({
    title: '↩️ ยกเลิกแผงขาย',
    message: 'ของจะกลับเข้ากระเป๋าทันที (กระเป๋าต้องมีที่ว่าง)',
    lines: [['ไอเทม', l.name], ['ราคาที่ตั้งไว้', fmt(l.price) + ' ทอง']],
    okText: 'ยกเลิกแผง',
  });
  if (!ok) return;
  try {
    const r = await api('POST', '/api/web/market', { action: 'cancel', listing_id: l.id });
    toast(r.message); await reload(); await fillMarket();
  } catch (e) { SFX.play('error'); toast(e.message, true); }
}

async function marketSell(it) {
  const price = await askNumber({
    title: '🏷️ ตั้งราคาขาย',
    message: `ลงขาย ${it.name} 1 ชิ้น — ของจะออกจากกระเป๋าทันทีจนกว่าจะขายได้หรือยกเลิก`,
    lines: [['ขายให้ร้านได้', fmt(it.sell) + ' ทอง/ชิ้น'],
            ['ช่วงราคาที่ตั้งได้', fmt(MK.min_price) + ' – ' + fmt(MK.max_price) + ' ทอง'],
            ...(MK.tax_percent ? [['ค่าธรรมเนียมตลาด', MK.tax_percent + '% หักจากคุณ', 'warn']] : [])],
    placeholder: 'ราคาที่ต้องการ',
    okText: 'ลงขาย',
  });
  if (!price) return;
  try {
    const r = await api('POST', '/api/web/market',
                        { action: 'list', item_id: it.id, price: price });
    SFX.play('coin'); toast(r.message); await reload(); await fillMarket();
  } catch (e) { SFX.play('error'); toast(e.message, true); }
}

document.querySelectorAll('[data-mk]').forEach(t => t.onclick = () => {
  MK_TAB = t.dataset.mk; fillMarket();
});

// ── 👗 ตู้เสื้อผ้า ──
// แฟชั่นเปลี่ยนแค่การแสดงผล เซิร์ฟเวอร์เป็นคนตัดสินว่ามีของจริงไหม ที่นี่แค่วาดกับส่งคำสั่ง
let FASH = null;
let FASH_TRY = null;        // ชุดที่กำลัง "ลองใส่ดู" (ยังไม่ได้ใส่จริง)
let FASH_FRAME = 0;

const FASH_SLOT = { outfit: '👘 ชุด', weapon: '⚔️ อาวุธ', aura: '✨ ออร่า' };

async function fillFashion() {
  const box = document.getElementById('fashList');
  box.innerHTML = '<div class="g-note">กำลังโหลด...</div>';
  try { FASH = await api('GET', '/api/web/me/fashion'); }
  catch (e) { box.innerHTML = '<div class="g-note">โหลดไม่สำเร็จ: ' + esc(e.message) + '</div>'; return; }
  FASH_TRY = null;
  paintFashion();
  fashPreview();
}

function paintFashion() {
  const worn = FASH.worn || {};
  const html = FASH.slots.map(slot => {
    const mine = FASH.items.filter(i => i.slot === slot);
    return `<div class="fash-sec">
      <div class="fash-head"><b>${FASH_SLOT[slot] || slot}</b>
        ${worn[slot] ? `<button class="fash-off" data-off="${slot}">✕ ถอด</button>` : ''}</div>
      <div class="fash-row">${mine.map((i, n) => `
        <button class="fash-card${i.worn ? ' on' : ''}${i.owned ? '' : ' locked'}"
                data-key="${esc(i.key)}" style="--fc:${FASH.themes[i.theme].color}">
          ${i.worn ? '<span class="fash-tag">ใส่อยู่</span>' : ''}
          ${i.owned ? '' : '<span class="fash-tag lock">🔒 ยังไม่มี</span>'}
          <b>${esc(i.name)}</b>
          <small>${esc(i.desc)}</small>
        </button>`).join('')}</div>
    </div>`;
  }).join('');
  document.getElementById('fashList').innerHTML = html;

  document.getElementById('fashList').querySelectorAll('[data-key]').forEach(b =>
    b.onclick = () => fashTry(b.dataset.key));
  document.getElementById('fashList').querySelectorAll('[data-off]').forEach(b =>
    b.onclick = () => fashOff(b.dataset.off));
}

/** แตะที่ชุด = ลองใส่ดูก่อน (ยังไม่บันทึก) · แตะซ้ำที่ชุดเดิม = ใส่จริง */
function fashTry(key) {
  const item = FASH.items.find(i => i.key === key);
  if (!item) return;
  if (FASH_TRY === key) return fashWear(key);
  FASH_TRY = key;
  SFX.play('click');
  document.getElementById('fashHint').innerHTML = item.owned
    ? `กำลังลอง <b>${esc(item.name)}</b> — แตะอีกครั้งเพื่อใส่จริง`
    : `กำลังลอง <b>${esc(item.name)}</b> — 🔒 ยังไม่มีชิ้นนี้ (ได้จากกาชาแฟชั่น)`;
  fashPreview();
}

/** ตัวอย่างบนหุ่น — ใช้ตัววาดตัวเดียวกับในเกม เห็นแบบไหนคือได้แบบนั้น */
function fashPreview() {
  const cv = document.getElementById('fashChar');
  if (!cv || !FASH) return;
  const look = { ...(FASH.worn || {}) };
  if (FASH_TRY) {
    const it = FASH.items.find(i => i.key === FASH_TRY);
    if (it) look[it.slot] = FASH_TRY;
  }
  const ctx = cv.getContext('2d');
  const s = Math.max(1, Math.floor(cv.width / 18));
  const draw = () => {
    ctx.clearRect(0, 0, cv.width, cv.height);
    drawCharacter(ctx, (cv.width - 16 * s) / 2, 6, s,
                  { ...CHAR, fashion: look, frame: FASH_FRAME++ });
    if (document.getElementById('v-fashion').classList.contains('on'))
      requestAnimationFrame(draw);          // ออร่าต้องขยับ ไม่งั้นดูไม่ออกว่าเป็นเอฟเฟกต์
  };
  draw();
}

async function fashWear(key) {
  try {
    const r = await api('POST', '/api/web/me/fashion', { action: 'wear', key: key });
    SFX.play('equip'); toast(r.message);
    FASH.worn = r.worn; FASH_TRY = null;
    FASH.items.forEach(i => i.worn = r.worn[i.slot] === i.key);
    paintFashion(); fashPreview();
    await reload();
  } catch (e) { toast(e.message, true); }
}

async function fashOff(slot) {
  try {
    const r = await api('POST', '/api/web/me/fashion', { action: 'off', slot: slot });
    toast(r.message);
    FASH.worn = r.worn; FASH_TRY = null;
    FASH.items.forEach(i => i.worn = r.worn[i.slot] === i.key);
    paintFashion(); fashPreview();
    await reload();
  } catch (e) { toast(e.message, true); }
}

// ── 🪱 สนามรบผลัดเทิร์น ──
// แผนที่มาจากเซิร์ฟเวอร์ทั้งใบ ที่นี่แค่วาด + คุมกล้อง (ซูม/เลื่อน/กระโดดไปดูคนอื่น)
let WM = null, WM_CAM = null, WM_ST = null;
let wmLoop = 0, wmHold = 0, wmBusy = false;
let WM_DEADLINE = 0;       // เวลาหมดเทิร์น (เทียบจาก time_left ที่เซิร์ฟเวอร์ส่งมา)
let WM_ANIM = null;        // เส้นทางที่เซิร์ฟเวอร์ส่งมา กำลังเล่นภาพอยู่

// ก้าวต่อการยิงคำสั่งหนึ่งครั้ง — ยิงก้อนใหญ่ห่าง ๆ ดีกว่าก้อนเล็กถี่ ๆ
// 36 ก้าวเล่นภาพที่ 60fps = 600ms พอดีกับช่วงยิง ภาพจึงเดินต่อเนื่องไม่สะดุด
// ตกเหลือ 1.7 ครั้ง/วินาที (แรงเดินมีแค่ 60/เทิร์นอยู่แล้ว สองคำสั่งก็หมดเทิร์น)
const WM_WALK_STEPS = 36;
const WM_HOLD_MS = 600;
let WM_BACKOFF = 0;        // โดน 429 แล้วหยุดยิงชั่วคราว กันวนยิงซ้ำจนแย่ลงกว่าเดิม

async function fillWorms() {
  try { wmApply(await api('GET', '/api/web/pvp/worms/match')); }
  catch (e) { toast(e.message, true); }
}

async function wmNewMatch(seed) {
  try {
    wmApply(await api('POST', '/api/web/pvp/worms/match', { action: 'new', seed: seed || 0 }));
    SFX.music('battle');       // เพลงคลอสนามรบ (battle เป็นเพลง ไม่ใช่เสียงเอฟเฟกต์)
  } catch (e) { toast(e.message, true); }
}

/** รับสถานะจากเซิร์ฟเวอร์มาแสดง — พื้นสร้างใหม่เฉพาะตอนแมตช์เปลี่ยน */
function wmApply(d) {
  const fresh = !WM || !WM_ST || WM_ST.seed !== d.seed;
  WM_ST = d;
  document.getElementById('v-worms').classList.toggle('wm-idle', !d.active);
  if (!d.active) { cancelAnimationFrame(wmLoop); wmLoop = 0; return; }

  WM_DEADLINE = performance.now() + (d.time_left || 0) * 1000;
  if (fresh) {
    WM = new WormsMap(d);
    WM_CAM = new WormsCam(document.getElementById('wmCanvas'), WM);
    WM_CAM.attach(null);
    WM_CAM.z = 3;
    wmFocus();
    wmStartLoop();
  } else {
    WM.props = d.props; WM.repaint();
  }
  wmPaintHud();
}

function wmMe() { return WM_ST.fighters[WM_ST.turn]; }

function wmFocus() {
  const f = wmMe();
  if (WM_CAM && f) WM_CAM.center(f.x, f.y - 10);
}

function wmStartLoop() {
  const cv = document.getElementById('wmCanvas'), ctx = cv.getContext('2d');
  cancelAnimationFrame(wmLoop);
  let t = 0;
  const tick = () => {
    if (!document.getElementById('v-worms').classList.contains('on')) { wmLoop = 0; return; }
    // เล่นภาพเส้นทางที่เซิร์ฟเวอร์ส่งมาทีละเฟรม (ตำแหน่งจริงเซิร์ฟเวอร์ตัดสินไปแล้ว)
    if (WM_ANIM && WM_ANIM.i < WM_ANIM.path.length) {
      const [x, y] = WM_ANIM.path[WM_ANIM.i++];
      WM_ANIM.f.x = x; WM_ANIM.f.y = y;
      if (WM_ANIM.i % 3 === 0) SFX.play('walk');
      wmFocus();
    } else if (WM_ANIM) {
      WM_ANIM = WM_QUEUE.shift() || null;      // ท่อนถัดไปของบอท (ถ้ามี)
      if (!WM_ANIM) wmPaintHud();
    }
    wmTick();

    WM.draw(ctx, WM_CAM, t++);
    WM_ST.fighters.forEach((f, i) => { if (!f.dead) wmDrawFighter(ctx, f, i === WM_ST.turn, t); });
    wmDrawFx(ctx);
    wmLoop = requestAnimationFrame(tick);
  };
  tick();
}

/** วาดนักสู้ตามกล้อง — ซูมออกสุดตัวจะเล็กมาก จึงมีแถบเลือดกับลูกศรชี้ตาปัจจุบัน */
function wmDrawFighter(ctx, f, active, t) {
  const z = WM_CAM.z, x = WM_CAM.sx(f.x), y = WM_CAM.sy(f.y);
  if (x < -60 || x > WM_CAM.vw + 60) return;
  const look = { ...(f.look || {}), pose: 'idle', flip: f.face < 0 };
  if (z >= 2) drawCharacter(ctx, x - 8 * z, y - 21 * z, z, look);
  else { ctx.fillStyle = f.bot ? '#ff9d84' : '#8fd0a0'; ctx.fillRect(x - 3, y - 10, 6, 10); }

  const bw = Math.max(16, 14 * z / 2), by = y - 22 * z - 8;
  ctx.fillStyle = '#00000099'; ctx.fillRect(x - bw / 2 - 1, by - 1, bw + 2, 5);
  ctx.fillStyle = f.bot ? '#ff6a4a' : '#6fd07a';
  ctx.fillRect(x - bw / 2, by, bw * Math.max(0, f.hp) / f.max_hp, 3);
  if (active) {                                  // ลูกศรกระพริบชี้คนที่ถึงตา
    ctx.fillStyle = '#ffd66b';
    const bob = Math.round(Math.sin(t / 9) * 2);
    for (let i = 0; i < 5; i++) ctx.fillRect(x - 4 + i, by - 12 + bob + i, 9 - i * 2, 1);
  }
}

let WM_QUEUE = [];         // ท่อนเดินที่รอเล่นภาพ (บอทเดินหลายท่อนต่อกัน)
let wmTimingOut = false, wmNextTimeout = 0;

/** นับถอยหลังบนจอ + พอหมดเวลาก็ขอจบเทิร์น (เซิร์ฟเวอร์เช็คเวลาเองอีกชั้น) */
function wmTick() {
  const el = document.getElementById('wmClock');
  if (!el || !WM_ST || !WM_ST.active) return;
  const left = WM_ST.over ? 0 : Math.max(0, Math.ceil((WM_DEADLINE - performance.now()) / 1000));
  el.textContent = '⏱️ ' + String(Math.floor(left / 60)) + ':' + String(left % 60).padStart(2, '0');
  el.classList.toggle('low', left <= 10 && !WM_ST.over);
  // ⚠️ ขอจบเทิร์นแล้วพลาด (เน็ตหลุด/โดนจำกัดอัตรา) ห้ามวนยิงใหม่ทุกเฟรม
  //    ไม่งั้นกลายเป็นยิง 60 ครั้งต่อวินาที ซึ่งยิ่งทำให้โดนจำกัดหนักกว่าเดิม
  const now = performance.now();
  if (left <= 0 && !WM_ST.over && !wmTimingOut && now >= WM_BACKOFF && now >= wmNextTimeout) {
    wmTimingOut = true;
    wmNextTimeout = now + 4000;
    wmHoldStop();
    wmEndTurn('timeout').finally(() => { wmTimingOut = false; });
  }
}

function wmPaintHud() {
  const d = WM_ST;
  if (!d || !d.active) return;
  document.getElementById('wmSeed').textContent = d.seed;
  document.getElementById('wmWhere').innerHTML =
    '🗺️ ' + esc(d.continent_label) + ' · 🎁 ' + d.props.length + ' หีบ · 🕳️ ' +
    d.traps + ' กับดัก (ซ่อนอยู่)';
  document.getElementById('wmTurn').innerHTML = d.over
    ? '🏁 <b>จบแล้ว</b> — ' + (d.winner ? esc(d.winner) + ' ชนะ!' : 'เสมอ')
    : 'รอบ ' + d.round + ' · ตาของ <b>' + esc(wmMe().name) + '</b>';
  const pct = Math.round(d.moves * 100 / d.move_budget);
  document.getElementById('wmMoves').style.width = pct + '%';
  document.getElementById('wmMovesTxt').textContent = d.moves + '/' + d.move_budget;
  document.getElementById('wmWho').innerHTML = d.fighters.map((f, i) =>
    `<button data-look="${i}" class="${f.dead ? 'dead' : ''}${i === d.turn ? ' now' : ''}">
       ${esc(f.name)} ${f.dead ? '☠️' : f.hp + '❤️'}</button>`).join('');
  document.getElementById('wmWho').querySelectorAll('[data-look]').forEach(b =>
    b.onclick = () => { const f = d.fighters[+b.dataset.look];
                        WM_CAM.center(f.x, f.y - 10); SFX.play('click'); });
  document.getElementById('wmLog').innerHTML = (d.log || []).map(l => '<div>' + esc(l) + '</div>').join('');
  document.querySelectorAll('[data-wm]').forEach(b => b.disabled = d.over || !!wmMe().bot);
  wmPaintSkills();
}

let WM_SKILL = null;       // สกิลที่เลือกไว้ (ที่ต้องเล็งจะรอกดยิงอีกที)

function wmPaintSkills() {
  const box = document.getElementById('wmSkills');
  const d = WM_ST;
  if (!box || !d || !d.active) return;
  const locked = d.over || wmMe().bot;
  box.innerHTML = (d.skills || []).map(s => `
    <button data-skill="${esc(s.key)}" ${locked || s.ready_in ? 'disabled' : ''}
            class="${WM_SKILL === s.key ? 'on' : ''}">
      ${s.ready_in ? `<span class="cd">⏳${s.ready_in}</span>` : ''}
      ${esc(s.name)}<small>${esc(s.desc)}</small></button>`).join('');
  box.querySelectorAll('[data-skill]').forEach(b =>
    b.onclick = () => wmPickSkill(b.dataset.skill));
  wmShowAim();
}

/** เลือกสกิล — แบบที่ต้องเล็งจะโชว์แถบมุม/แรงก่อน ที่เหลือใช้ทันที */
function wmPickSkill(key) {
  const s = (WM_ST.skills || []).find(x => x.key === key);
  if (!s) return;
  SFX.play('click');
  if (!s.aim) { WM_SKILL = null; wmAttack(key); return; }
  WM_SKILL = WM_SKILL === key ? null : key;
  wmPaintSkills();
}

function wmShowAim() {
  const el = document.getElementById('wmAim');
  if (el) el.hidden = !WM_SKILL;
}

async function wmAttack(key) {
  if (wmBusy || performance.now() < WM_BACKOFF) return;
  wmBusy = true;
  try {
    const d = await api('POST', '/api/web/pvp/worms/match', {
      action: 'attack', skill: key,
      angle: +document.getElementById('wmAngle').value,
      power: +document.getElementById('wmPower').value,
    });
    WM_SKILL = null;
    wmPlayAttack(d);
  } catch (e) { if (!wmBackoff(e)) toast(e.message, true); }
  finally { wmBusy = false; }
}

/** เล่นภาพผลการโจมตี แล้วต่อด้วยตาบอท (ผลทั้งหมดเซิร์ฟเวอร์ตัดสินไปแล้ว) */
function wmPlayAttack(d) {
  const a = d.attack || {};
  SFX.play(a.kind === 'self' ? 'use' : a.kind === 'lob' ? 'skill' : 'hit');
  if (a.path && a.path.length) WM_SHOT = { path: a.path, i: 0 };
  if (a.blast) { WM.carve(a.blast.x, a.blast.y, a.blast.crater || 6); wmBoom(a.blast); }
  const hits = (a.hits || []).concat((a.blast || {}).hits || []);
  if (hits.length) { SFX.play('foehit'); toast(hits.map(h => `${h.name} -${h.damage}`).join(' · '), true); }
  if (a.heal) toast(`✨ ฟื้นเลือด +${a.heal}`);
  wmApply(d);
  const bot = WM_ST.fighters.find(f => f.bot);
  WM_QUEUE = (d.bot_moves || []).filter(m => (m.path || []).length)
                                .map(m => ({ f: bot, path: m.path, i: 0 }));
  (d.bot_moves || []).forEach(m => { if (m.attack && m.attack.blast) {
    WM.carve(m.attack.blast.x, m.attack.blast.y, m.attack.blast.crater || 6); } });
  if (WM_QUEUE.length) WM_ANIM = WM_QUEUE.shift();
}

let WM_SHOT = null, WM_BOOMS = [];

function wmBoom(b) { WM_BOOMS.push({ x: b.x, y: b.y, r: (b.crater || 8) * 1.6, t: 0 }); }

/** วาดกระสุนที่กำลังบิน + ลูกไฟระเบิด */
function wmDrawFx(ctx) {
  if (WM_SHOT) {
    for (let k = 0; k < 3 && WM_SHOT.i < WM_SHOT.path.length; k++) WM_SHOT.i++;
    const p = WM_SHOT.path[Math.min(WM_SHOT.i, WM_SHOT.path.length - 1)];
    ctx.fillStyle = '#ffd66b';
    ctx.fillRect(WM_CAM.sx(p[0]) - 2, WM_CAM.sy(p[1]) - 2, 4, 4);
    if (WM_SHOT.i >= WM_SHOT.path.length) WM_SHOT = null;
  }
  WM_BOOMS = WM_BOOMS.filter(b => b.t < 14);
  WM_BOOMS.forEach(b => {
    const k = b.t++ / 14, r = b.r * (0.4 + k) * WM_CAM.z;
    ctx.globalAlpha = 1 - k;
    ctx.fillStyle = k < .4 ? '#fff6d8' : k < .7 ? '#ffb45a' : '#8f2317';
    ctx.beginPath(); ctx.arc(WM_CAM.sx(b.x), WM_CAM.sy(b.y), r, 0, 6.29); ctx.fill();
    ctx.globalAlpha = 1;
  });
}

/** ส่งคำสั่งไปเซิร์ฟเวอร์ แล้วเอาเส้นทางที่ได้มาเล่นภาพ */
/** โดนจำกัดอัตราแล้วหยุดยิงชั่วคราว — ยิงต่อมีแต่ทำให้รอนานขึ้น */
function wmBackoff(e) {
  if (e.status !== 429) return false;
  const wait = Math.max(2, e.retryAfter || 3);
  WM_BACKOFF = performance.now() + wait * 1000;
  wmHoldStop();
  return true;
}

async function wmDo(action, dir) {
  if (wmBusy || !WM_ST || !WM_ST.active || WM_ST.over) return;
  if (performance.now() < WM_BACKOFF) return;
  wmBusy = true;
  try {
    const d = await api('POST', '/api/web/pvp/worms/match',
                        { action: action, dir: dir, steps: WM_WALK_STEPS });
    const before = WM_ST.fighters[WM_ST.turn];
    WM_ST = { ...d };
    const f = WM_ST.fighters[WM_ST.turn];
    if (d.move && d.move.path.length) {
      f.x = before.x; f.y = before.y;
      WM_ANIM = { f: f, path: d.move.path, i: 0 };
      if (action === 'jump') SFX.play('skill');
    }
    (d.sprung || []).forEach(() => { SFX.play('trap'); toast('🕳️ เหยียบกับดัก!', true); });
    (d.opened || []).forEach(() => { SFX.play('chest'); toast('🎁 เปิดหีบสมบัติ!'); });
    if (d.move && d.move.drowned) SFX.play('lose');
    WM.props = d.props; WM.repaint();
    wmPaintHud();
  } catch (e) { if (!wmBackoff(e)) toast(e.message, true); }
  finally { wmBusy = false; }
}

async function wmEndTurn(how) {
  try {
    const d = await api('POST', '/api/web/pvp/worms/match', { action: how || 'end' });
    wmApply(d);
    // บอทเดินไปแล้วฝั่งเซิร์ฟเวอร์ ที่นี่แค่เล่นภาพตามเส้นทางที่ได้มาทีละท่อน
    const bot = WM_ST.fighters.find(f => f.bot);
    WM_QUEUE = (d.bot_moves || []).filter(m => m.path.length)
                                  .map(m => ({ f: bot, path: m.path, i: 0 }));
    if (WM_QUEUE.length && bot) {
      const first = d.bot_moves.find(m => m.path.length);
      bot.x = first.path[0][0]; bot.y = first.path[0][1];
      WM_ANIM = WM_QUEUE.shift();
    }
    SFX.play('click');
  } catch (e) { if (!wmBackoff(e)) toast(e.message, true); }
}

/** กดค้าง = เดินต่อเนื่อง (ยิงเป็นก้อนละ 5 ก้าว ไม่ใช่ยิงทุกก้าว) */
function wmHoldStart(action, dir) {
  wmDo(action, dir);
  if (action !== 'walk') return;
  clearInterval(wmHold);
  wmHold = setInterval(() => wmDo('walk', dir), WM_HOLD_MS);
}
function wmHoldStop() { clearInterval(wmHold); wmHold = 0; }

function wmZoom(dz) {
  if (!WM_CAM) return;
  WM_CAM.zoomAt(dz, WM_CAM.mx(WM_CAM.vw / 2), WM_CAM.my(WM_CAM.vh / 2));
  document.getElementById('wmZoom').textContent = '×' + WM_CAM.z;
}

// ── 👥 เพื่อน ──
// เพิ่มด้วยไอดี Discord ที่คัดลอกมาวาง — เซิร์ฟเวอร์เป็นคนตัดสินว่าไอดีนั้นมีในเกมไหม
// โปรไฟล์ที่ดูได้มีแต่ของสาธารณะ (ทอง/กระเป๋าไม่ส่งมาตั้งแต่ฝั่งเซิร์ฟเวอร์แล้ว)
let FRIENDS = null;

async function fillFriends() {
  const box = document.getElementById('frList');
  box.innerHTML = '<div class="g-note">กำลังโหลด...</div>';
  try { FRIENDS = await api('GET', '/api/web/me/friends'); }
  catch (e) { box.innerHTML = '<div class="g-note">โหลดไม่สำเร็จ: ' + esc(e.message) + '</div>'; return; }
  document.getElementById('frMyId').textContent = FRIENDS.my_id;
  paintFriends();
}

function paintFriends() {
  const box = document.getElementById('frList');
  box.innerHTML = !FRIENDS.friends.length
    ? `<div class="g-note">ยังไม่มีเพื่อนสักคน — คัดลอกไอดี Discord ของเพื่อนมาวางข้างบนได้เลย</div>`
    : `<div class="fash-head"><b>รายชื่อเพื่อน</b>
         <span class="g-note" style="margin:0">${FRIENDS.count}/${FRIENDS.max} คน</span></div>
       <div class="fr-row">${FRIENDS.friends.map(f => `
         <div class="fr-card">
           <canvas class="fr-pic" data-pic="${esc(f.id)}" width="56" height="76"></canvas>
           <div class="fr-info">
             <b>${esc(f.name)}</b>
             <small>Lv ${f.level} · ${esc(f.race || '—')} ${esc(f.class_name || '')}
               ${f.guild ? '· 🏰 ' + esc(f.guild) : ''}${f.married ? ' · 💍' : ''}</small>
             <small class="fr-id">${esc(f.id)}</small>
           </div>
           <div class="fr-btns">
             <button data-see="${esc(f.id)}">👁️ โปรไฟล์</button>
             <button data-del="${esc(f.id)}">✕ ลบ</button>
           </div>
         </div>`).join('')}</div>`;

  box.querySelectorAll('[data-pic]').forEach(cv => {
    const f = FRIENDS.friends.find(x => x.id === cv.dataset.pic);
    if (f) drawFriend(cv, f);
  });
  box.querySelectorAll('[data-see]').forEach(b => b.onclick = () => seeFriend(b.dataset.see));
  box.querySelectorAll('[data-del]').forEach(b => b.onclick = () => delFriend(b.dataset.del));
}

/** วาดตัวละครเพื่อนด้วยตัววาดตัวเดียวกับในเกม — เห็นแฟชั่นที่เขาใส่จริง */
function drawFriend(cv, f, scale) {
  const ctx = cv.getContext('2d');
  const s = scale || Math.max(1, Math.floor(cv.width / 18));
  const cfg = { race: f.race, cls: f.class_name, armor: f.armor || 'None',
                weapon: f.weapon, pose: 'idle', fashion: f.fashion || {} };
  const draw = () => {
    ctx.clearRect(0, 0, cv.width, cv.height);
    drawCharacter(ctx, (cv.width - 16 * s) / 2, 2, s, cfg);
  };
  draw();
  // ออร่าของเพื่อนก็ต้องขยับ แต่ลูปกลางดูที่ออร่า "ของเรา" จึงหมุนเองแยกที่นี่
  if ((f.fashion || {}).aura) {
    const tick = () => { if (!cv.isConnected) return; draw(); requestAnimationFrame(tick); };
    requestAnimationFrame(tick);
  }
}

async function addFriend() {
  const el = document.getElementById('frInput');
  const id = el.value.trim();
  if (!id) return toast('วางไอดี Discord ของเพื่อนก่อน', true);
  try {
    const r = await api('POST', '/api/web/me/friends', { action: 'add', id: id });
    SFX.play('reward'); toast(r.message);
    el.value = ''; FRIENDS = r; paintFriends();
  } catch (e) { toast(e.message, true); SFX.play('error'); }
}

async function delFriend(id) {
  const f = FRIENDS.friends.find(x => x.id === id);
  if (!await confirmAction({ title: '👋 ลบเพื่อน',
                             message: 'ลบ ' + (f ? f.name : id) + ' ออกจากรายชื่อ',
                             okText: 'ลบเลย', danger: true })) return;
  try {
    const r = await api('POST', '/api/web/me/friends', { action: 'remove', id: id });
    toast(r.message); FRIENDS = r; paintFriends();
  } catch (e) { toast(e.message, true); }
}

async function seeFriend(id) {
  const box = document.getElementById('frCard');
  box.innerHTML = '<div class="g-note">กำลังโหลด...</div>';
  showPanel('friendcard');
  let f;
  try { f = await api('GET', '/api/web/friends/' + encodeURIComponent(id) + '/profile'); }
  catch (e) { box.innerHTML = '<div class="g-note">' + esc(e.message) + '</div>'; return; }
  box.innerHTML = `<div class="g-head"><h2>${esc(f.name)}</h2>
      <p>Lv ${f.level} · ${esc(f.race || '—')} ${esc(f.class_name || '')}</p></div>
    <div class="g-card fash-wrap">
      <div class="fash-preview"><canvas id="frBig" width="160" height="220"></canvas></div>
      <div>${[['ไอดี Discord', f.id], ['เลเวล', 'Lv ' + f.level],
              ['เผ่า', f.race || '—'], ['คลาส', f.class_name || '—'],
              ['ตำแหน่ง', f.title || '—'], ['ทวีปที่อยู่', f.continent_label],
              ['สัตว์เลี้ยง', f.pet || 'ไม่มี'], ['กิลด์', f.guild || 'ไม่มี'],
              ['สถานะ', f.married ? '💍 แต่งงานแล้ว' : 'โสด'],
              ['พลังชีวิต', f.hp + ' / ' + f.max_hp]]
             .map(([k, v]) => `<div class="fr-line"><span>${esc(k)}</span><b>${esc(String(v))}</b></div>`)
             .join('')}</div>
    </div>
    <p class="g-note">โปรไฟล์เพื่อนโชว์เฉพาะข้อมูลสาธารณะ — ทอง ธนาคาร และของในกระเป๋าไม่เปิดให้ดู</p>`;
  drawFriend(document.getElementById('frBig'), f, 9);
}

// ── 🎁 กาชาแฟชั่น ──
// เรทกับผลการสุ่มตัดสินที่เซิร์ฟเวอร์ทั้งหมด ที่นี่แค่กดปุ่มแล้วเล่นภาพผลที่ได้มา
let FG = null;

const FG_KIND = {                     // ผลที่ได้ → ป้ายกับสีการ์ด
  featured: { tag: '✨ ของหน้าตู้!', cls: 'feat' },
  fashion:  { tag: '👗 แฟชั่นใหม่!', cls: 'fash' },
  dup:      { tag: '💎 ได้ซ้ำ → อัญมณี', cls: 'dup' },
  artifact: { tag: '🏺 อาร์ติแฟกต์', cls: 'arti' },
  junk:     { tag: '🧂 ของธรรมดา', cls: '' },
  sold:     { tag: '🎒 กระเป๋าเต็ม → ขายเป็นทอง', cls: '' },
  bonus:    { tag: '💎 โบนัสการันตี', cls: 'dup' },
};

async function fillFashionGacha() {
  const box = document.getElementById('fgTiers');
  box.innerHTML = '<div class="g-note">กำลังโหลด...</div>';
  try { FG = await api('GET', '/api/web/fashion/gacha'); }
  catch (e) { box.innerHTML = '<div class="g-note">โหลดไม่สำเร็จ: ' + esc(e.message) + '</div>'; return; }
  document.getElementById('fgResult').innerHTML = '';
  paintGacha();
}

function paintGacha() {
  const f = FG.featured;
  document.getElementById('fgFeatName').innerHTML =
    esc(f.name) + (f.owned ? ' <span class="fg-have">มีแล้ว</span>' : '');
  document.getElementById('fgFeatDesc').textContent = f.desc;
  document.getElementById('fgGems').textContent = FG.gems;
  document.getElementById('fgGemNote').textContent =
    `อัญมณีการันตี — ครบ ${FG.gems_per_exchange} เม็ดแลกแฟชั่นได้ 1 ชิ้น ` +
    `(มีแล้ว ${FG.owned_count}/${FG.total} ชิ้น)`;
  fgFeatPreview();

  // ปุ่มที่จ่ายไม่ไหวยัง "กดได้" อยู่ — หรี่ให้เห็นว่าเงินไม่พอ แล้วปล่อยให้เซิร์ฟเวอร์
  // เป็นคนบอกว่าขาดเท่าไหร่ (disabled เฉย ๆ = กดแล้วเงียบ ผู้เล่นไม่รู้ว่าทำไมไม่เกิดอะไร)
  document.getElementById('fgTiers').innerHTML = FG.tiers.map(t => {
    const rate = (t.odds.fashion + t.odds.featured).toFixed(1);
    const short = t.price - FG.cash;
    return `<button class="g-tile${t.key === 'ten' ? ' hot' : ''}${short > 0 ? ' poor' : ''}"
              data-tier="${esc(t.key)}">
      <span class="ic">${t.name.slice(0, 2)}</span>${esc(t.name.slice(2).trim())}
      <span class="sub">${fmt(t.price)} ทอง · ลุ้นแฟชั่น ${rate}%${
        t.free_gems ? ` · 💎 ×${t.free_gems} แน่นอน` : ''}${
        short > 0 ? `<br>💰 ขาดอีก ${fmt(short)} ทอง` : ''}</span></button>`;
  }).join('');
  document.getElementById('fgTiers').querySelectorAll('[data-tier]').forEach(b =>
    b.onclick = () => fgPull(b.dataset.tier));

  const can = FG.gems >= FG.gems_per_exchange;
  document.getElementById('fgExchange').innerHTML = !FG.exchangeable.length
    ? '<div class="g-note">🎉 เก็บครบทุกชิ้นแล้ว — อัญมณีเก็บไว้รอตู้ชุดต่อไปได้เลย</div>'
    : `<div class="fash-head"><b>💎 แลกด้วยอัญมณี</b>
         <span class="g-note" style="margin:0">${can ? 'เลือกได้เลย' :
           `ยังขาดอีก ${FG.gems_per_exchange - FG.gems} เม็ด`}</span></div>
       <div class="fash-row">${FG.exchangeable.map(i => `
         <button class="fash-card${can ? '' : ' locked'}" data-buy="${esc(i.key)}"
                 style="--fc:${FG.featured.key === i.key ? '#ffd66b' : '#7f8aa8'}">
           <b>${esc(i.name)}</b><small>${esc(i.desc)}</small></button>`).join('')}</div>`;
  document.getElementById('fgExchange').querySelectorAll('[data-buy]').forEach(b =>
    b.onclick = () => fgExchange(b.dataset.buy));
}

/** หุ่นโชว์ของหน้าตู้ — ใช้ตัววาดตัวเดียวกับในเกม เห็นแบบไหนคือได้แบบนั้น */
function fgFeatPreview() {
  const cv = document.getElementById('fgFeat');
  if (!cv || !FG) return;
  const ctx = cv.getContext('2d');
  const s = Math.max(1, Math.floor(cv.width / 18));
  const look = { [FG.featured.slot]: FG.featured.key };
  auraRepaint(cv, () => {
    ctx.clearRect(0, 0, cv.width, cv.height);
    drawCharacter(ctx, (cv.width - 16 * s) / 2, 4, s, { ...CHAR, fashion: look });
  });
}

async function fgPull(tier) {
  const box = document.getElementById('fgResult');
  box.innerHTML = '<div class="g-note">🎰 กำลังหมุน...</div>';
  SFX.play('gacha');
  let r;
  try { r = await api('POST', '/api/web/fashion/gacha', { action: 'pull', tier: tier }); }
  catch (e) { box.innerHTML = ''; toast(e.message, true); SFX.play('error'); return; }

  const best = r.pulls.some(p => p.kind === 'featured') ? 'reward'
             : r.pulls.some(p => p.kind === 'fashion') ? 'win'
             : r.pulls.some(p => p.kind === 'artifact') ? 'treasure' : 'item';
  SFX.play(best);

  // โหลดตู้ใหม่ก่อน (ทองลด อัญมณีเพิ่ม มีของเพิ่ม) แล้วค่อยวางการ์ดผล
  // ไม่งั้น fillGacha จะล้างการ์ดที่เพิ่งโชว์ทิ้ง
  try { FG = await api('GET', '/api/web/fashion/gacha'); paintGacha(); } catch (e) { }
  box.innerHTML = `<div class="fg-cards">${r.pulls.map((p, n) => {
    const k = FG_KIND[p.kind] || FG_KIND.junk;
    return `<div class="fg-card ${k.cls}" style="animation-delay:${n * 70}ms">
      <span class="fg-ktag">${k.tag}</span><b>${esc(p.name)}</b>
      ${p.gold ? `<small>+${fmt(p.gold)} ทอง</small>` : ''}</div>`;
  }).join('')}</div>`;
  box.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
  await reload();
}

async function fgExchange(key) {
  try {
    const r = await api('POST', '/api/web/fashion/gacha', { action: 'exchange', key: key });
    SFX.play('reward'); toast(r.message);
    FG = r; paintGacha();
    await reload();
  } catch (e) { toast(e.message, true); }
}

// ── 🗺️ สรุปทุกทวีป ──
// ตัวเลขทุกตัวมาจาก game_data ชุดเดียวกับที่ใช้ตอนเดินจริง ที่นี่แค่จัดหน้า
async function fillAtlas() {
  const box = document.getElementById('atlasList');
  box.innerHTML = '<div class="g-note">กำลังโหลด...</div>';
  let d;
  try { d = await api('GET', '/api/web/continents'); }
  catch (e) { box.innerHTML = '<div class="g-note">โหลดไม่สำเร็จ: ' + esc(e.message) + '</div>'; return; }

  const x = n => (n === 1 ? '' : `<b>×${n}</b>`);
  box.innerHTML = d.continents.map(c => `
    <div class="atlas${c.here ? ' here' : ''}">
      <div class="at-head">
        <span class="at-name">${esc(c.label)}</span>
        ${c.here ? '<span class="at-tag">📍 อยู่ที่นี่</span>' : ''}
        ${c.killed ? `<span class="at-killed">⚔️ ล้มไปแล้ว ${fmt(c.killed)} ตัว</span>`
                   : '<span class="at-killed off">ยังไม่เคยไป</span>'}
      </div>
      <div class="at-rows">
        <div class="at-row"><span>ธาตุชุกชุม</span><b>${c.elements.length
          ? c.elements.map(e => esc(e.label)).join(' · ') : 'สมดุลทุกธาตุ'}</b></div>
        ${c.status ? `<div class="at-row warn"><span>สถานะประจำถิ่น</span>
          <b>${esc(c.status.label)} <small>โดนตี ${c.status.chance}%</small></b></div>` : ''}
        <div class="at-row"><span>มอนแรงกว่า / รางวัลดีกว่า</span>
          <b>❤️ ${x(c.mult.hp) || '—'} 🪙 ${x(c.mult.gold) || '—'} 🔷 ${x(c.mult.exp) || '—'}</b></div>
        ${c.monsters.map(m => `<div class="at-row"><span>${esc(m.rank)}</span>
          <b class="at-mon">${m.names.map(esc).join(' · ')}</b></div>`).join('')}
        ${c.specials.map(s => `<div class="at-row hot"><span>อีเวนต์พิเศษ ${s.chance}%</span>
          <b>${esc(s.intro)}…</b></div>`).join('')}
      </div>
    </div>`).join('');
}

// ── 🎟️ ซีซั่นพาส + ⭐ สายพรีเมียม (แผงเดียวจบ) ──
// สถานะแต่ละช่อง (รับแล้ว/ยังไม่ถึง/ต้องเปิดพรีเมียม/กดรับได้) เซิร์ฟเวอร์เป็นคนตัดสิน
// ที่นี่แค่แปลงเป็นป้ายสี — จะได้ตรงกับที่ดิสโชว์เป๊ะ ๆ
const SP_STATUS = {
  claimed:      ['✅ รับแล้ว', 'ok'],
  ready:        ['🎁 กดรับได้!', 'hot'],
  locked:       ['🔒 ยังไม่ถึง', 'off'],
  need_premium: ['🔐 ต้องเปิดพรีเมียม', 'prem'],
};

async function fillSeason() {
  const d = await api('GET', '/api/web/me/season');
  const nx = d.next;

  // หัวแผง: ปลดไปกี่ขั้นแล้ว + อีกกี่แต้มถึงขั้นถัดไป (เห็นความคืบหน้าในบรรทัดเดียว)
  const pct = nx ? Math.max(0, Math.min(100, d.points / Math.max(1, nx.points) * 100)) : 100;
  document.getElementById('seasonHead').innerHTML = `
    <div class="sp-line"><span class="sp-badge ${d.premium ? 'prem' : ''}">${
      d.premium ? '⭐ สายพรีเมียม' : '🆓 สายฟรี'}</span>
      <span class="sp-season">ซีซั่น ${esc(d.season)}</span></div>
    <div class="rolls-left">🎟️ แต้มสะสม <b>${fmt(d.points)}</b> ·
      ปลดแล้ว <b>${d.tiers_done}</b>/${d.tiers_total} ขั้น</div>
    <div class="prog${nx ? '' : ' done'}"><i style="width:${pct}%"></i></div>
    <small style="color:var(--g-dim)">${nx
      ? `อีก ${fmt(nx.need_more)} แต้ม ถึงขั้น ${nx.index + 1} (${fmt(nx.points)} แต้ม)`
      : '🏆 ปลดครบทุกขั้นแล้ว!'}</small>`;

  // รายขั้น: การ์ดใบเดียวเห็นทั้งสายฟรีและสายพรีเมียม พร้อมชื่อของที่จะได้
  document.getElementById('seasonList').innerHTML = d.tiers.map(t => `
    <div class="sp-tier${t.reached ? ' hit' : ''}">
      <div class="sp-th"><b>ขั้น ${t.index + 1}</b>
        <span>${t.reached ? '✅ ปลดแล้ว' : '🔒 ' + fmt(t.points) + ' แต้ม'}</span></div>
      ${t.tracks.map(k => {
        const [label, cls] = SP_STATUS[k.status] || ['—', 'off'];
        return `<div class="sp-row ${cls}">
          <span class="sp-tr">${k.track === 'free' ? '🆓' : '⭐'}</span>
          <span class="sp-rw">${esc(k.text)}</span>
          <span class="sp-st">${label}</span></div>`;
      }).join('') || '<div class="sp-row off"><span class="sp-rw">— ไม่มีรางวัลขั้นนี้ —</span></div>'}
    </div>`).join('');

  // ปุ่มรับรางวัล: บอกจำนวนช่องที่กดได้ตรงปุ่ม ไม่ต้องไล่หาเองว่ามีอะไรค้างไหม
  const claim = document.getElementById('seasonClaim');
  document.getElementById('seasonClaimSub').textContent =
    d.claimable ? d.claimable + ' ช่องรอรับ' : 'ยังไม่มีให้รับ';
  claim.disabled = !d.claimable;
  claim.onclick = async () => {
    try { toast((await api('POST', '/api/web/me/season/claim')).message);
          SFX.play('reward'); fillSeason(); boot(); }
    catch (e) { toast(e.message, true); }
  };
  // ป้ายบนปุ่มเมนูหลัก — เห็นตั้งแต่ยังไม่เข้ามาว่ามีของค้างรับ
  const tile = document.getElementById('tileSeasonSub');
  if (tile) tile.textContent = d.claimable ? `🎁 ${d.claimable} ช่องรอรับ` : 'รางวัล + สายพรีเมียม';
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
    try { toast((await api('POST', '/api/web/me/season/premium')).message);
          SFX.play('reward'); fillSeason(); boot(); }
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
