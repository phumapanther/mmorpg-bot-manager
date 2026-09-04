// 🎭 ชวนเพื่อนเดินทาง — หน้าล็อบบี้ปาร์ตี้ (เฟส 2)
//
// ⚠️ ไฟล์นี้ทำแค่ "ห้อง" ไม่ใช่ตัวเกม — ตัวเกมกับการวาดภาพอยู่ที่ renderer (เฟส 3)
//    เบราว์เซอร์ส่งแค่ "กดปุ่มไหน" กติกาทั้งหมดตัดสินที่เซิร์ฟเวอร์
//
// สเปก: docs/superpowers/specs/2026-09-03-party-rpg-design.md

let PARTY = null;              // สถานะห้องล่าสุดที่เซิร์ฟเวอร์ส่งมา
let PARTY_POLL = null;         // ตัวจับเวลาถามสถานะซ้ำ
let PARTY_SEQ = 0;             // เหตุการณ์ล่าสุดที่เล่นอนิเมชันไปแล้ว (กันเล่นซ้ำ)
let PARTY_BID = null;          // รหัสสมรภูมิที่กำลังดูอยู่ — เปลี่ยน = ขึ้นรอบใหม่

/** ถามสถานะห้องซ้ำ ๆ — ทั้งตอนรอคนเข้าห้อง **และตอนสู้อยู่**
 *
 * ⚠️ เคยหยุด poll ตอนเข้าสู้ ("เดี๋ยวเฟส 3 รับช่วงต่อ") แล้วลืมทำต่อ ผลคือ
 *    1. คนที่รออยู่เห็นจอค้าง เพื่อนกดอะไรก็ไม่รู้
 *    2. นาฬิกาฝั่งเซิร์ฟเวอร์ไม่เดิน (เดินตอน view เท่านั้น) หมดเวลาก็ไม่มีใครปลด
 *    เจอตอนเทสด้วยมือ 2026-09-04 — ตาค้างตลอดกาล
 *
 * on=false ต้องหยุดเสมอตอนออกจากหน้า ไม่งั้นยิงทิ้งไว้ตลอด */
function partyWatch(on) {
  clearInterval(PARTY_POLL);
  PARTY_POLL = null;
  if (!on) {
    clearTimeout(PARTY_ANIM);      // ออกจากห้องแล้วห้ามมีตัวจับเวลาค้าง
    PARTY_ANIM = null;
    return;
  }
  PARTY_POLL = setInterval(async () => {
    try {
      const r = await api('GET', '/api/web/party/room');
      PARTY = r.room;
      partyPaint();
      partyPlayNew();                                  // เห็นอนิเมชันของเพื่อนด้วย
      // ⚠️ จบสมรภูมิแล้ว **ห้ามหยุด** — หัวห้องกด "ออกเดินทางต่อ" ได้ตลอด
      //    เพื่อนที่หยุดถามไปแล้วจะค้างอยู่หน้าสรุปผลตลอดกาล
      //    (เจ้าของเกมเจอตอนเทสด้วยมือ 2026-09-04) หยุดเมื่อออกจากห้องเท่านั้น
      if (!PARTY.in_room) partyWatch(false);
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
    partyWatch(PARTY.in_room);
  } catch (e) {
    toast(e.message, true);
  }
}

/** เล่นอนิเมชันเหตุการณ์ที่เพิ่งเกิด — เฉพาะที่ยังไม่เคยเล่น
 *  seq เป็นตัวกันเล่นซ้ำ: คนที่กดเองเล่นไปแล้วตอนได้คำตอบจาก POST */
function partyPlayNew() {
  const b = PARTY && PARTY.battle;
  if (!b || !b.seq) return;
  const before = typeof pbPending === 'function' ? pbPending() : 0;
  // ⚠️ ใช้รหัสสมรภูมิ ไม่ใช่ "เลขถอยหลัง" — รอบเก่าจบที่ seq 1 รอบใหม่ก็เริ่มที่ 1
  //    เหมือนกัน ตัวจับแบบถอยหลังจะไม่ทำงาน แล้วจอนิ่งสนิททั้งรอบ
  if (b.bid && b.bid !== PARTY_BID) {
    PARTY_BID = b.bid;
    PARTY_SEQ = 0;
    const cv = document.getElementById('partyCanvas');
    if (cv) cv.innerHTML = '';        // ล้างจอเก่า pbMount จะสร้างใหม่พร้อมล้างสถานะ
    pbMount('partyCanvas');
    pbSetState(b);
  }
  if (b.seq > PARTY_SEQ) {
    PARTY_SEQ = b.seq;
    pbPlay(b.recent || []);
  }
  // ⚠️ ต้องวาดแถบคำสั่ง **ใหม่หลังเข้าคิวแล้ว**
  //    รอบ poll เรียก partyPaint() ก่อน partyPlayNew() เสมอ ตอนวาดปุ่มจึงยังเห็น
  //    คิวว่าง (pbPending() = 0) แล้วเปิดปุ่มทันทีทั้งที่อนิเมชันกำลังจะเริ่ม
  //    (เจ้าของเกมเจอ: เพื่อนตีปุ๊บ อีกคนกดได้เลยทั้งที่เป็นตามอน 2026-09-04)
  if (typeof pbPending === 'function' && pbPending() !== before) partyPaintBar();
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
               <input type="checkbox" id="partyBoss"> 👑 ล่าบอส
               <span class="party-warn">ยากมาก — แนะนำเลเวล 20 ขึ้นไป</span>
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
  partyWatch(PARTY && PARTY.in_room);
}


// ── หน้าจอสมรภูมิ (เฟส 3) ──

let PARTY_PICK = null;      // ท่าที่เลือกไว้ รอเลือกเป้า
let PARTY_ANIM = null;      // ตัวจับเวลารออนิเมชันจบ (มีได้ตัวเดียว)

/** ผู้เล่นคลิกเลือกเป้าบน canvas — renderer เรียกกลับมาที่นี่ */
function onPartyPick(unitId, side, alive) {
  if (!PARTY_PICK) return;
  // กันคลิกผิดตั้งแต่หน้าจอ (เซิร์ฟเวอร์ยังตัดสินซ้ำอยู่ดี):
  // ชุบเล็งได้เฉพาะคนที่ล้ม · ท่าอื่นเล็งได้เฉพาะคนที่ยังอยู่
  // ชุบเล็งได้เฉพาะคนล้ม · ✨ Heal เล็งได้ทั้งคนที่ยืนและคนที่ล้ม · ท่าอื่นเฉพาะคนที่ยืน
  if (alive !== undefined && PARTY_PICK !== 'heal') {
    if (PARTY_PICK === 'revive' ? alive : !alive) {
      toast(PARTY_PICK === 'revive'
        ? 'ชุบได้เฉพาะเพื่อนที่ล้มแล้ว' : 'คนนี้ล้มไปแล้ว', true);
      return;
    }
  }
  partyAct(PARTY_PICK, unitId);
}

/** สั่งท่าไปที่เซิร์ฟเวอร์ — กติกาทั้งหมดตัดสินที่นั่น */
async function partyAct(action, target) {
  PARTY_PICK = null;
  try {
    const r = await api('POST', '/api/web/party/room',
                        { action, target: target || '' });
    PARTY = r.room;
    if (PARTY.battle) {
      pbSetState(PARTY.battle);
      PARTY_SEQ = PARTY.battle.seq || PARTY_SEQ;   // เล่นเองแล้ว poll ไม่ต้องเล่นซ้ำ
    }
    pbPlay(r.events || []);
    partyPaintBar();
    partyWatch(PARTY.in_room);        // จบแล้วก็ยังต้องคอยฟังว่าหัวห้องพาไปต่อไหม
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

/** สรุปโทษตอนล้มยกทีม — บอกให้ชัดว่าเสียอะไรไป ไม่ใช่เงินหายเงียบ ๆ */
function partyPenaltyHtml() {
  const p = PARTY && PARTY.penalty;
  const rnd = '<span>🧭 การเดินทางเริ่มใหม่ที่รอบ 1</span>';
  if (!p) return `<div class="party-reward">${rnd}</div>`;
  return `
    <div class="party-reward">
      ${p.gold ? `<span>💸 เสีย <b>${p.gold.toLocaleString()}</b> ทอง</span>` : ''}
      ${p.exp ? `<span>📉 เสีย <b>${p.exp.toLocaleString()}</b> EXP</span>` : ''}
      ${p.level ? `<span>⬇️ เลเวลลด <b>${p.level}</b></span>` : ''}
      ${rnd}
    </div>`;
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

  // ⏳ อนิเมชันยังเล่นไม่จบ — ห้ามโชว์ผลแพ้ชนะ ห้ามเปิดปุ่มให้กด
  //
  // เซิร์ฟเวอร์สรุปผลทั้งตาเสร็จตั้งแต่ก่อนอนิเมชันเริ่มเล่น ถ้าวาดตามสถานะทันที
  // ผู้เล่นจะเห็น "ปาร์ตี้ชนะ!" ตั้งแต่เลือดมอนยังไม่ทันลด และกดปุ่มได้ทั้งที่
  // ตายังเป็นของมอนอยู่ (เจ้าของเกมเจอตอนเทสด้วยมือ 2026-09-04)
  clearTimeout(PARTY_ANIM);
  PARTY_ANIM = null;
  if (typeof pbPending === 'function' && pbPending() > 0) {
    bar.innerHTML = '<div class="party-wait">⚔️ กำลังต่อสู้...</div>';
    PARTY_ANIM = setTimeout(partyPaintBar, 120);   // เช็คใหม่จนกว่าจะนิ่ง
    return;
  }

  if (b.over) {
    const win = b.winner === 'party';
    // 💀 ล้มยกทีม = จบการเดินทางรอบนี้ ต้องเริ่มใหม่จากรอบ 1 ไม่ใช่ไปต่อ
    const wiped = !!PARTY.wiped;
    const head = wiped ? '💀 ปาร์ตี้ล้มยกทีม!'
      : win ? '🏆 ปาร์ตี้ชนะ!'
      : b.winner === 'flee' ? '🏃 หนีออกมาได้' : '💀 ปาร์ตี้แพ้';
    bar.innerHTML = `
      <div class="party-result ${win ? 'win' : 'lose'}">
        <b>${head}</b>
        ${wiped ? partyPenaltyHtml() : partyRewardHtml()}
        <div class="party-btns">
          ${PARTY.host
            ? (wiped
                ? '<button class="go" id="partyRestart">🧭 เริ่มออกเดินทางใหม่</button>'
                : '<button class="go" id="partyAgain">🧭 ออกเดินทางต่อ</button>')
            : `<span class="party-hint">รอหัวห้อง${wiped ? 'เริ่มออกเดินทางใหม่' : 'พาออกเดินทางต่อ'}...</span>`}
          <button class="out" id="partyOut">← ออกจากปาร์ตี้</button>
        </div>
      </div>`;
    document.getElementById('partyOut').onclick = () => partyDo('leave');
    const again = document.getElementById('partyAgain');
    if (again) again.onclick = () => partyDo('again');
    const restart = document.getElementById('partyRestart');
    if (restart) restart.onclick = () => partyDo('restart');
    return;
  }

  const me = (b.units || []).find(u => u.you);
  const mine = me && b.turn_of === me.id;

  if (!mine) {
    const who = (b.units || []).find(u => u.id === b.turn_of);
    bar.innerHTML = `<div class="party-wait">⏳ รอ ${who ? who.name : '...'} เลือกคำสั่ง
      <span class="party-clock">
        ${PARTY.round ? `🧭 รอบที่ ${PARTY.round}` : ''}
        ${b.turn_left != null ? ` · ${b.turn_left} วิ` : ''}
      </span>
    </div>`;
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

  // ⚠️ ปุ่มสกิลสร้างจาก me.skills ที่เซิร์ฟเวอร์ส่งมา **ห้ามฝังรายชื่อท่าไว้ที่นี่**
  //    คลาสต่างกันปุ่มต่างกัน (เจ้าของเกมสั่ง 2026-09-04) ฝังไว้เมื่อไหร่
  //    เพิ่มคลาสใหม่หรือปรับท่าที่เกมหลักแล้วหน้าเว็บจะไม่ตามไปด้วย
  const fallen = (b.units || []).some(u => u.side === 'party' && !u.alive);
  const kit = (me.skills || []).map(sk => {
    const cool = sk.cd > 0;
    const noMana = (me.mana || 0) <= 0;
    const why = cool ? `รออีก ${sk.cd} ตา` : noMana ? 'เม็ดคริสตัลหมด' : sk.desc;
    return `<button class="pb" data-a="${sk.key}" data-t="${sk.target}"
              ${cool || noMana ? 'disabled' : ''} title="${why}">
              ${sk.name}${cool ? ` (${sk.cd})` : ''}
            </button>`;
  }).join('');

  bar.innerHTML = `
    <button class="pb" data-a="attack" data-t="single">⚔️ โจมตี</button>
    ${kit}
    ${me.can_revive && fallen
      ? '<button class="pb" data-a="revive" data-t="fallen">💗 ชุบ</button>' : ''}
    <button class="pb" data-a="flee" data-t="self">🏃 หนี</button>
    <span class="party-clock">
      ${PARTY.round ? `🧭 รอบที่ ${PARTY.round} · ` : ''}
      ${me.mana_max ? `💎 ${me.mana}/${me.mana_max}` : ''}
      ${b.turn_left != null ? ` · ⏱️ ${b.turn_left} วิ` : ''}
    </span>`;
  bar.querySelectorAll('.pb').forEach(btn => {
    btn.onclick = () => {
      const a = btn.dataset.a;
      // ⚠️ ดูจาก data-t ที่เซิร์ฟเวอร์บอกมา ไม่ใช่เช็คชื่อท่าทีละตัว
      //    ฝังชื่อท่าไว้แล้วเพิ่มท่าใหม่ทีไรก็ต้องมาแก้ที่นี่ทุกที
      if (['self', 'all', 'party'].includes(btn.dataset.t)) {
        partyAct(a, '');
      } else {
        PARTY_PICK = a;
        partyPaintBar();
      }
    };
  });
}
