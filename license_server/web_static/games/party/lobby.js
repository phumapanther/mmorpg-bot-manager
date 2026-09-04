// 🎭 ชวนเพื่อนเดินทาง — หน้าล็อบบี้ปาร์ตี้ (เฟส 2)
//
// ⚠️ ไฟล์นี้ทำแค่ "ห้อง" ไม่ใช่ตัวเกม — ตัวเกมกับการวาดภาพอยู่ที่ renderer (เฟส 3)
//    เบราว์เซอร์ส่งแค่ "กดปุ่มไหน" กติกาทั้งหมดตัดสินที่เซิร์ฟเวอร์
//
// สเปก: docs/superpowers/specs/2026-09-03-party-rpg-design.md

let PARTY = null;              // สถานะห้องล่าสุดที่เซิร์ฟเวอร์ส่งมา
let PARTY_POLL = null;         // ตัวจับเวลาถามสถานะซ้ำ

/** ถามสถานะห้องซ้ำ ๆ เพื่อเห็นคนเข้า/ออกแบบสด
 *  on=false ต้องหยุดเสมอตอนออกจากหน้า ไม่งั้นยิงทิ้งไว้ตลอด */
function partyWatch(on) {
  clearInterval(PARTY_POLL);
  PARTY_POLL = null;
  if (!on) return;
  PARTY_POLL = setInterval(async () => {
    try {
      const r = await api('GET', '/api/web/party/room');
      PARTY = r.room;
      partyPaint();
      if (PARTY.phase === 'battle') partyWatch(false);   // เข้าสู้แล้ว เฟส 3 รับช่วงต่อ
    } catch (e) {
      /* เน็ตสะดุดครั้งเดียวไม่ต้องทำอะไร รอบหน้าถามใหม่ */
    }
  }, 2000);
}

/** สั่งงานห้อง — ทุกคำสั่งไปที่เซิร์ฟเวอร์หมด ไม่มีการตัดสินใจฝั่งนี้ */
async function partyDo(action, extra) {
  try {
    const r = await api('POST', '/api/web/party/room', { action, ...(extra || {}) });
    PARTY = r.room;
    partyPaint();
    partyWatch(PARTY.in_room && PARTY.phase !== 'battle');
  } catch (e) {
    toast(e.message, true);
  }
}

/** วาดหน้าล็อบบี้จากสถานะที่เซิร์ฟเวอร์ส่งมา */
function partyPaint() {
  const box = document.getElementById('partyMount');
  if (!box) return;

  // เข้าสู้แล้ว — renderer รับช่วงวาด หน้าล็อบบี้ถอยไป
  if (PARTY && PARTY.in_room && PARTY.battle) {
    partyPaintBattle();
    return;
  }

  if (!PARTY || !PARTY.in_room) {
    box.innerHTML = `
      <div class="party-lobby">
        <p class="party-hint">ชวนเพื่อนสูงสุด 5 คนออกผจญภัยด้วยกัน · ต่อสู้แบบผลัดเทิร์น</p>
        <div class="g-grid">
          <button class="g-tile hot" id="partyCreate">
            <span class="ic">🎪</span>เปิดปาร์ตี้<span class="sub">ได้รหัสไว้ชวนเพื่อน</span>
          </button>
          <button class="g-tile" id="partyJoin">
            <span class="ic">🚪</span>เข้าด้วยรหัส<span class="sub">ใส่รหัสที่เพื่อนส่งมา</span>
          </button>
        </div>
      </div>`;
    document.getElementById('partyCreate').onclick = () => partyDo('create');
    document.getElementById('partyJoin').onclick = () => {
      const code = prompt('ใส่รหัสห้องที่เพื่อนส่งมา');
      if (code && code.trim()) partyDo('join', { code: code.trim() });
    };
    return;
  }

  const seats = PARTY.seats || [];
  const rows = seats.map(s =>
    `<li>${s.host ? '👑' : '🧍'} ${s.name}${s.you ? ' <b>(คุณ)</b>' : ''}</li>`).join('');
  const empty = Math.max(0, (PARTY.max || 5) - seats.length);
  const blanks = '<li class="empty">🪑 ที่ว่าง</li>'.repeat(empty);

  box.innerHTML = `
    <div class="party-lobby">
      <div class="party-code">
        รหัสห้อง <b id="partyCode">${PARTY.code}</b>
        <button class="mini" id="partyCopy">📋 คัดลอก</button>
      </div>
      <ul class="party-seats">${rows}${blanks}</ul>
      <div class="party-btns">
        ${PARTY.host
          ? `<label class="party-raid">
               <input type="checkbox" id="partyBoss"> 👑 ล่าบอส (ยากกว่า รางวัลดีกว่า)
             </label>
             <button class="go" id="partyStart" ${seats.length < 2 ? 'disabled' : ''}>
               ⚔️ เริ่มออกเดินทาง${seats.length < 2 ? ' (รออีกอย่างน้อย 1 คน)' : ''}
             </button>`
          : '<span class="party-hint">รอหัวห้องกดเริ่ม...</span>'}
        <button class="out" id="partyLeave">← ออกจากปาร์ตี้</button>
      </div>
    </div>`;

  document.getElementById('partyCopy').onclick = () => {
    navigator.clipboard?.writeText(PARTY.code);
    toast('คัดลอกรหัสแล้ว — ส่งให้เพื่อนได้เลย');
  };
  document.getElementById('partyLeave').onclick = () => partyDo('leave');
  const go = document.getElementById('partyStart');
  if (go) go.onclick = () => partyDo('start', {
    boss_raid: !!document.getElementById('partyBoss')?.checked,
  });
}

/** เปิดหน้าปาร์ตี้ — เรียกจาก showPanel('party') */
async function fillParty() {
  try {
    const r = await api('GET', '/api/web/party/room');
    PARTY = r.room;
  } catch (e) {
    PARTY = null;
  }
  partyPaint();
  partyWatch(PARTY && PARTY.in_room && PARTY.phase !== 'battle');
}


// ── หน้าจอสมรภูมิ (เฟส 3) ──

let PARTY_PICK = null;      // ท่าที่เลือกไว้ รอเลือกเป้า

/** ผู้เล่นคลิกเลือกเป้าบน canvas — renderer เรียกกลับมาที่นี่ */
function onPartyPick(unitId, side) {
  if (!PARTY_PICK) return;
  partyAct(PARTY_PICK, unitId);
}

/** สั่งท่าไปที่เซิร์ฟเวอร์ — กติกาทั้งหมดตัดสินที่นั่น */
async function partyAct(action, target) {
  PARTY_PICK = null;
  try {
    const r = await api('POST', '/api/web/party/room',
                        { action, target: target || '' });
    PARTY = r.room;
    if (PARTY.battle) pbSetState(PARTY.battle);
    pbPlay(r.events || []);
    partyPaintBar();
    if (PARTY.battle && PARTY.battle.over) partyWatch(false);
  } catch (e) {
    toast(e.message, true);
    partyPaintBar();
  }
}

function partyPaintBattle() {
  const box = document.getElementById('partyMount');
  if (!box) return;
  if (!document.getElementById('partyBar')) {
    box.innerHTML = '<div id="partyCanvas"></div><div id="partyBar" class="party-bar"></div>';
  }
  pbMount('partyCanvas');
  pbSetState(PARTY.battle);
  partyPaintBar();
}

/** สรุปรางวัล — ตัวเลขทั้งหมดมาจากเซิร์ฟเวอร์ ห้ามคำนวณเองแม้แต่นิดเดียว */
function partyRewardHtml() {
  const r = PARTY && PARTY.reward;
  if (!r) return '';
  const me = (PARTY.battle.units || []).find(u => u.you);
  const mine = me ? (r.gold || {})[String(me.id).slice(1)] : null;
  const drop = r.drop;
  return `
    <div class="party-reward">
      ${mine != null ? `<span>💰 คุณได้ <b>${mine.toLocaleString()}</b> ทอง</span>` : ''}
      ${r.exp ? `<span>⭐ +${r.exp} EXP</span>` : ''}
      ${drop ? `<span>${drop.full_bag
          ? `🎒 กระเป๋าเต็ม! <b>${drop.name}</b> หลุดมือไป`
          : `📦 <b>${drop.name}</b> ตกเป็นของ ${partyNameOf(drop.uid)}`}</span>` : ''}
    </div>`;
}

/** ชื่อคนในปาร์ตี้จาก uid — ใช้โชว์ว่าไอเทมตกที่ใคร */
function partyNameOf(uid) {
  const u = (PARTY.battle.units || []).find(x => x.id === 'p' + uid);
  return u ? (u.you ? 'คุณ' : u.name) : 'เพื่อนร่วมทาง';
}

/** แถบคำสั่ง — โชว์ปุ่มเฉพาะตอนถึงตาเรา */
function partyPaintBar() {
  const bar = document.getElementById('partyBar');
  const b = PARTY && PARTY.battle;
  if (!bar || !b) return;

  if (b.over) {
    const win = b.winner === 'party';
    bar.innerHTML = `
      <div class="party-result ${win ? 'win' : 'lose'}">
        <b>${win ? '🏆 ปาร์ตี้ชนะ!' : b.winner === 'flee' ? '🏃 หนีออกมาได้' : '💀 ปาร์ตี้แพ้'}</b>
        ${partyRewardHtml()}
        <button class="out" id="partyOut">← ออกจากปาร์ตี้</button>
      </div>`;
    document.getElementById('partyOut').onclick = () => partyDo('leave');
    return;
  }

  const me = (b.units || []).find(u => u.you);
  const mine = me && b.turn_of === me.id;

  if (!mine) {
    const who = (b.units || []).find(u => u.id === b.turn_of);
    bar.innerHTML = `<div class="party-wait">⏳ รอ ${who ? who.name : '...'} เลือกคำสั่ง</div>`;
    return;
  }

  if (PARTY_PICK) {
    bar.innerHTML = `
      <div class="party-wait">🎯 คลิกเลือกเป้าหมายบนจอ
        <button class="mini" id="partyCancel">ยกเลิก</button>
      </div>`;
    document.getElementById('partyCancel').onclick = () => {
      PARTY_PICK = null;
      partyPaintBar();
    };
    return;
  }

  bar.innerHTML = `
    <button class="pb" data-a="attack">⚔️ โจมตี</button>
    <button class="pb" data-a="skill">✨ สกิล</button>
    <button class="pb" data-a="aoe">💥 กวาด</button>
    <button class="pb" data-a="heal">💚 ฮีล</button>
    <button class="pb" data-a="defend">🛡️ ป้องกัน</button>
    <button class="pb" data-a="flee">🏃 หนี</button>`;
  bar.querySelectorAll('.pb').forEach(btn => {
    btn.onclick = () => {
      const a = btn.dataset.a;
      // ท่าที่ไม่ต้องเล็ง สั่งได้เลย · ท่าที่ต้องเล็งรอคลิกเป้าบนจอ
      if (a === 'defend' || a === 'flee' || a === 'aoe') {
        partyAct(a, '');
      } else {
        PARTY_PICK = a;
        partyPaintBar();
      }
    };
  });
}
