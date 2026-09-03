// 🔬 ไล่ลำดับจริง: สถานะ "จบแล้ว" มาถึง → ต่อคิวภาพตาย → ภาพเล่นจบ
//    แผงสรุปผลต้องโผล่ครั้งเดียวตอนท้าย ไม่ใช่โผล่ก่อนแล้วหายไป
const fs = require('fs'), vm = require('vm');
const { playSource } = require('./_js_source');
const CR = String.fromCharCode(13), NL = String.fromCharCode(10);
const play = playSource().split(CR + NL).join(NL);
const web = fs.readFileSync('license_server/web_static/web.js', 'utf8')
               .split(CR + NL).join(NL);
const grab = (src, head) => {
  const a = src.indexOf(head);
  if (a < 0) throw new Error('หาไม่เจอ: ' + head);
  const b = src.indexOf(NL + '}' + NL, a);
  return src.slice(a, b + 3);
};

const boxes = {};
const seen = [];                       // บันทึกว่าแผงโชว์/ซ่อนตอนไหนบ้าง
const ctx = {
  console, Math, JSON, Object, Array, String, Number,
  document: { getElementById: id => (boxes[id] = boxes[id] ||
    { id, innerHTML: '', _hidden: true,
      get hidden() { return this._hidden; },
      set hidden(v) { if (v !== this._hidden) seen.push(v ? 'ซ่อน' : 'โชว์'); this._hidden = v; },
      querySelectorAll: () => [] }) },
  SFX: { play() {} }, wmNewMatch: () => {}, api: async () => ({}), toast: () => {},
  WM_ANIM: null, WM_QUEUE: [], WM_SHOT: null, WM_BOOMS: [],
  WM_AFTER: [], WM_DYING: {}, WM_OVER_SHOWN: false, WM_FIRES: [],
  wmStepsBusy: () => ctx.STEPS > 0,
  STEPS: 0,
};
vm.createContext(ctx);
vm.runInContext([grab(web, 'function esc('), grab(play, 'function wmBusyFx('),
                 grab(play, 'function wmShutOver('), grab(play, 'function wmPaintOver(')].join(NL)
  + NL + 'globalThis.API = { paint: wmPaintOver, busy: wmBusyFx,'
  + ' shown: () => WM_OVER_SHOWN, shut: wmShutOver };', ctx);
const API = ctx.API;

ctx.WM_ST = { active: true, over: true, winner: 'บอท', fighters: [
  { name: 'คุณ', hp: 0, dead: true, dealt: 12, kills: 0 },
  { name: 'บอท', hp: 80, dead: false, dealt: 40, kills: 1 }], standings: [] };

/** ลูปวาดจำลอง — ใช้เงื่อนไขเดียวกับใน wmTick */
function tick() {
  if (ctx.WM_ST.over && API.shown() !== !API.busy()) API.paint();
}

// ── ลำดับจริง: คำตอบมาถึงแล้วผู้เรียกต่อคิวภาพทันทีในจังหวะเดียวกัน ──
//    (wmApply → ผู้เรียกต่อคิว → เฟรมถัดไปลูปวาดถึงจะทำงาน)
ctx.STEPS = 1;                      // ภาพระเบิดร่างถูกต่อคิวแล้ว
for (let i = 0; i < 6; i++) tick(); // ภาพเล่นอยู่หลายเฟรม
const duringDeath = seen.slice();   // ระหว่างนี้ห้ามมีอะไรโผล่
ctx.STEPS = 0;                      // ภาพตายเล่นจบ
tick(); tick(); tick();
const afterDeath = seen.slice();
ctx.STEPS = 1; tick();              // ระเบิดลูกโซ่โผล่มาทีหลัง
ctx.STEPS = 0; tick(); tick();      // แล้วจบจริง
const endOfMatch = seen.slice();

// ── กดเริ่มเกมใหม่หลังจบเกม: แมตช์ใหม่มาถึง แผงต้องปิด ──
//    (ทางเดียวกับที่ wmApply ทำ — "ปิด" ทำได้ทุกเมื่อ ไม่ต้องรอภาพ)
seen.length = 0;
ctx.WM_ST = { active: true, over: false, fighters: [], standings: [] };
API.shut();                          // wmApply เรียกตัวนี้ตอนแมตช์ยังเล่นอยู่
for (let i = 0; i < 5; i++) tick();  // ลูปวาดต้องไม่เอากลับมาโชว์
const newMatch = { seen: seen.slice(), hidden: boxes['wmOver'].hidden,
                   shown: API.shown() };

console.log(JSON.stringify({ duringDeath: duringDeath, afterDeath: afterDeath,
                             endOfMatch: endOfMatch, newMatch: newMatch }));
