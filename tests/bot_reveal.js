// 🔬 จำลองว่า "หลังรับคำตอบจากเซิร์ฟเวอร์ แต่ก่อนภาพเดินของบอทจะเริ่ม"
//    จอวาดบอทไว้ที่ไหน — ต้องเป็นจุดเดิม ไม่ใช่ปลายทาง
const fs = require('fs'), vm = require('vm');
const { playSource } = require('./_js_source');
const CR = String.fromCharCode(13), NL = String.fromCharCode(10);
const play = playSource().split(CR + NL).join(NL);
const grab = head => {
  const a = play.indexOf(head);
  if (a < 0) throw new Error('หาไม่เจอ: ' + head);
  const b = play.indexOf(NL + '}' + NL, a);
  return play.slice(a, b + 3);
};

const ctx = { console, Math, Object, WM_HIDDEN: null, wmPaintHud: () => {} };
vm.createContext(ctx);
vm.runInContext([grab('function wmSnapshot('), grab('function wmHideOutcome('),
                 grab('function wmRevealAll(')].join(NL)
                + NL + 'globalThis.API = { snap: wmSnapshot, hide: wmHideOutcome,'
                + ' reveal: wmRevealAll, hidden: () => WM_HIDDEN };', ctx);
const API = ctx.API;

// ตาเราจบ → เซิร์ฟเวอร์ตอบมาพร้อมกันหมด บอทเดินไปไกลแล้วในคำตอบนั้น
ctx.WM_ST = { fighters: [{ name: 'คุณ', x: 100, y: 200, hp: 90, dead: false },
                         { name: 'บอท', x: 300, y: 200, hp: 100, dead: false }] };
const old = API.snap();
ctx.WM_ST = { fighters: [{ name: 'คุณ', x: 100, y: 200, hp: 70, dead: false },
                         { name: 'บอท', x: 420, y: 188, hp: 100, dead: false }] };
API.hide(old);
const duringGap = JSON.parse(JSON.stringify(ctx.WM_ST.fighters));
API.reveal();
console.log(JSON.stringify({ duringGap: duringGap, after: ctx.WM_ST.fighters }));
