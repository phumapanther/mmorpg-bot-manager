// 🔬 จำลองการกดค้างเดินจริง ๆ ด้วยฟังก์ชันของจริงจาก walk.js
//    เทียบสองโมเดล: แบบเดิม (ถามเซิร์ฟเวอร์ก่อนแล้วค่อยขยับ) กับแบบใหม่ (เดาไว้ก่อน)
//    ใช้พิสูจน์เรื่องเดียว: "กดแล้วตัวขยับเมื่อไหร่" และ "ปล่อยแล้วหยุดตรงไหน"
const fs = require('fs'), vm = require('vm');
const CR = String.fromCharCode(13), NL = String.fromCharCode(10);
const src = fs.readFileSync('license_server/web_static/walk.js', 'utf8')
              .split(CR + NL).join(NL);
const ctx = { console, Math };
vm.createContext(ctx);
vm.runInContext(src + NL + 'globalThis.WALK = WALK;', ctx);

const job = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'));
const flat = job.grid;
const map = { w: job.w, h: job.h, at: (x, y) => flat[y * job.w + x] };
const R = job.rules;
const PING = job.ping, HOLD = job.holdMs, HZ = 60;
const WALK_TICKS = job.walkTicks, SEND_MS = job.sendMs;

/** โมเดลใหม่: จอเดินเอง ส่งไปให้ยืนยันเป็นระยะ */
function predicted(x0, y0, dir) {
  let x = x0, y = y0, moves = job.moves, tick = 0, pending = 0, lastSend = 0;
  let firstMoveAt = null, inFlight = null, serverX = x0, serverY = y0, sentTotal = 0;
  const done = [];
  for (let ms = 0; ms <= HOLD + PING * 3; ms += 1000 / HZ) {
    const held = ms < HOLD;
    // คำตอบจากเซิร์ฟเวอร์กลับมาถึงหรือยัง
    if (inFlight && ms >= inFlight.at + PING) {
      const w = ctx.WALK.walk(map, R, inFlight.fromX, inFlight.fromY, dir, inFlight.n, true);
      serverX = w.x; serverY = w.y;
      inFlight = null;
    }
    if (held && moves > 0) {
      tick += 1;
      while (tick >= WALK_TICKS && moves > 0) {
        tick -= WALK_TICKS;
        const s = ctx.WALK.step(map, R, x, y, dir, true);
        moves--; pending++;
        if (s.how === ctx.WALK.BLOCKED) break;
        x = s.x; y = s.y;
        if (firstMoveAt === null) firstMoveAt = ms;
      }
    }
    const due = (!held || ms - lastSend >= SEND_MS);
    if (due && !inFlight && pending) {
      inFlight = { at: ms, n: pending, fromX: serverX, fromY: serverY };
      sentTotal += pending; pending = 0; lastSend = ms;
    }
    if (!held && !inFlight && !pending) { done.push(ms); break; }
  }
  return { firstMoveAt: firstMoveAt, x: x, y: y, serverX: serverX, sent: sentTotal };
}

/** โมเดลเดิม: กด → ยิงคำสั่ง → รอ ping → เล่นภาพ 500 ms → ค่อยยิงใหม่ */
function oldWay(x0, y0, dir) {
  let x = x0, y = y0, moves = job.moves, firstMoveAt = null;
  let busyUntil = -1, overshoot = 0;
  for (let ms = 0; ms <= HOLD + PING * 3; ms += 1000 / HZ) {
    const held = ms < HOLD;
    if (ms < busyUntil) continue;
    if (busyUntil > 0) {                     // ก้อนก่อนเพิ่งเล่นจบ
      const w = ctx.WALK.walk(map, R, x, y, dir, job.oldSteps, true);
      if (firstMoveAt === null) firstMoveAt = busyUntil - job.animMs;
      if (!held) overshoot += job.oldSteps;  // ปล่อยนิ้วไปแล้วแต่ก้อนนี้ยังเดินต่อ
      x = w.x; y = w.y; moves -= job.oldSteps;
      busyUntil = -1;
    }
    if (held && moves > 0) busyUntil = ms + PING + job.animMs;
  }
  return { firstMoveAt: firstMoveAt, x: x, y: y, overshoot: overshoot };
}

console.log(JSON.stringify({
  predicted: predicted(job.x, job.y, job.dir),
  old: oldWay(job.x, job.y, job.dir),
}));
