// 🎯 ทายเลข 1-10 — หน้าเกม (ไปเป็น license_server/web_static/<ชื่อเกม>.js)
//
// 🔒 กติกาเหล็ก: เบราว์เซอร์ส่งไปแค่ "กดปุ่มไหน" กฎทั้งหมดตัดสินที่เซิร์ฟเวอร์
//    เลขลับไม่เคยถูกส่งลงมาก่อนเกมจบ (table.view()/room.view() คัดออกให้แล้ว)
//    ไฟล์นี้แค่ "วาดสิ่งที่เซิร์ฟเวอร์บอกมา" ไม่ตัดสินอะไรเอง
//
// ตัวอย่างจริงที่ใหญ่กว่านี้มาก (มีอนิเมชัน canvas): license_server/web_static/uno.js

let GN_MODE = null;   // "bot" | "room" | null

async function gnPost(path, body) {
  const res = await fetch(`/api/web/${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body || {}),
  });
  const data = await res.json();
  if (!res.ok) throw new Error(data.detail || "เกิดข้อผิดพลาด");
  return data;
}

function gnLog(el, lines) {
  if (!el) return;
  el.innerHTML = (lines || []).map((l) => `<div>${l}</div>`).join("");
  el.scrollTop = el.scrollHeight;
}

// ── โหมดซ้อมกับบอท ──

function gnRenderTable(table) {
  const status = document.getElementById("gnStatus");
  const pad = document.getElementById("gnNumberPad");
  if (!table || !table.playing) {
    if (status) status.textContent = "กดเริ่มเกมเพื่อทายเลข 1-10";
    return;
  }
  if (status) {
    status.textContent = table.over
      ? `จบเกม! เลขลับคือ ${table.secret} — ${table.winner === 0 ? "🎉 คุณชนะ!" : "🤖 บอทชนะ"}`
      : table.my_turn
        ? "ตาคุณ — เลือกเลข 1-10"
        : "รอตาคู่แข่ง...";
  }
  if (pad) {
    pad.querySelectorAll("button[data-n]").forEach((btn) => {
      btn.disabled = !table.my_turn || table.over;
    });
  }
  gnLog(document.getElementById("gnLog"), table.log);
}

async function gnStart() {
  const data = await gnPost("guessnum", { action: "start", bots: 1 });
  gnRenderTable(data.table);
}

async function gnGuess(n) {
  const data = await gnPost("guessnum", { action: "guess", number: n });
  gnRenderTable(data.table);
}

// ── โหมดชวนเพื่อน ──

function gnRenderRoom(room) {
  const el = document.getElementById("gnRoomStatus");
  if (!el) return;
  if (!room || !room.in_room) {
    el.textContent = "";
    return;
  }
  const names = (room.seats || []).map((s) => s.name).join(", ");
  el.textContent = room.over
    ? `จบเกม! เลขลับคือ ${room.secret}`
    : `ห้อง ${room.code} — ${names}${room.my_turn ? " (ตาคุณ!)" : ""}`;
}

async function gnRoomOpen() {
  const data = await gnPost("guessnum/room", { action: "create" });
  gnRenderRoom(data);
}

async function gnRoomJoin(code) {
  const data = await gnPost("guessnum/room", { action: "join", code });
  gnRenderRoom(data);
}

// ── ปุ่มต่าง ๆ (ผูกเมื่อ DOM พร้อม) ──

document.addEventListener("DOMContentLoaded", () => {
  const start = document.getElementById("gnStart");
  if (start) start.addEventListener("click", gnStart);

  const pad = document.getElementById("gnNumberPad");
  if (pad) {
    pad.querySelectorAll("button[data-n]").forEach((btn) => {
      btn.addEventListener("click", () => gnGuess(Number(btn.dataset.n)));
    });
  }

  const roomOpen = document.getElementById("gnRoomOpen");
  if (roomOpen) roomOpen.addEventListener("click", gnRoomOpen);

  const roomJoin = document.getElementById("gnRoomJoin");
  if (roomJoin) {
    roomJoin.addEventListener("click", () => {
      const code = document.getElementById("gnJoinInput").value;
      gnRoomJoin(code);
    });
  }
});
