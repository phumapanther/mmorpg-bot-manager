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
          ? `<button class="go" id="partyStart" ${seats.length < 2 ? 'disabled' : ''}>
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
  if (go) go.onclick = () => partyDo('start');
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
