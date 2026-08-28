// 🔬 รันวงจรกระโดดของจริงจาก play.js ตั้งแต่ปล่อยปุ่มจนเท้าแตะพื้น
//    เพื่อหาว่า "กระโดดพัง" พังตรงไหน
const fs = require('fs'), vm = require('vm');
const CR = String.fromCharCode(13), NL = String.fromCharCode(10);
const read = f => fs.readFileSync(f, 'utf8').split(CR + NL).join(NL);
const play = read('license_server/web_static/play.js');
const walk = read('license_server/web_static/walk.js');
const grab = head => {
  const a = play.indexOf(head);
  if (a < 0) throw new Error('หาไม่เจอ: ' + head);
  const b = play.indexOf(NL + '}' + NL, a);
  return play.slice(a, b + 3);
};

const job = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'));
const flat = job.grid;
const log = [];
const ctx = {
  console, Math, Object, JSON,
  WM: { w: job.w, h: job.h, at: (x, y) => flat[y * job.w + x] },
  WM_DT: 1, WM_HIDDEN: null, WM_ANIM: null, WM_QUEUE: [], wmBusy: false,
  WM_JUMP_SEND: null, WM_PRED: null, WM_ST: null, WM_FLY: null, WM_JUMP_END: null,
  SFX: { play: n => log.push('sfx:' + n) },
  toast: m => log.push('toast:' + m),
  wmFocus: () => {},
  wmBump: (x, y) => log.push('bump:' + x + ',' + y),
  wmChunk: (fi, path) => log.push('chunk:' + path.length),
  wmDo: (a, d, e) => log.push('send:' + a + ' dir=' + d + ' predicted=' + e.predicted),
  wmJumpSend: j => log.push('sendQueued:' + j.dir),
  wmWalkStop: () => {},
  wmSettleJump: null,
};
vm.createContext(ctx);
vm.runInContext(walk + NL + 'globalThis.WALK = WALK;', ctx);
vm.runInContext([grab('function wmJumpFire('), grab('function wmFlyTick('),
                 grab('function wmSettleJump('), grab('function wmLandJump(')].join(NL)
  + NL + 'globalThis.API = { fire: wmJumpFire, fly: wmFlyTick, land: wmLandJump,'
  + ' state: () => ({ fly: WM_FLY ? { x: Math.round(WM_FLY.x), y: Math.round(WM_FLY.y),'
  + ' done: WM_FLY.done, landed: WM_FLY.landed } : null, end: WM_JUMP_END }) };', ctx);

function fresh() {
  ctx.WM_ST = {
    turn: 0, moves: 60, over: false, rules: job.rules,
    fighters: [{ name: 'คุณ', x: job.x, y: job.y, face: 1, bot: false, dead: false },
               { name: 'บอท', x: 600, y: job.y, face: -1, bot: true, dead: false }],
  };
  ctx.WM_FLY = null; ctx.WM_JUMP_END = null; ctx.WM_ANIM = null; log.length = 0;
}

const out = {};
// ① ปล่อยปุ่มแล้วลอยจนถึงพื้น โดยคำตอบจากเซิร์ฟเวอร์ยังไม่มา
fresh();
ctx.API.fire(1, 1.0, 0);
const trail = [];
for (let i = 0; i < 300 && ctx.API.state().fly; i++) {
  ctx.API.fly();
  const f = ctx.WM_ST.fighters[0];
  trail.push([f.x, f.y]);
}
out.noAnswer = { frames: trail.length, start: [job.x, job.y],
                 end: ctx.WM_ST.fighters[0] ? [ctx.WM_ST.fighters[0].x, ctx.WM_ST.fighters[0].y] : null,
                 峰: trail.length ? Math.min(...trail.map(p => p[1])) : null,
                 log: log.slice() };

// ② คำตอบมาถึงกลางอากาศ (เฟรมที่ 10)
fresh();
ctx.API.fire(1, 1.0, 0);
let answered = false;
const t2 = [];
for (let i = 0; i < 300 && ctx.API.state().fly; i++) {
  ctx.API.fly();
  t2.push([ctx.WM_ST.fighters[0].x, ctx.WM_ST.fighters[0].y]);
  if (i === 10 && !answered) {
    answered = true;
    const truth = ctx.WALK.jump(ctx.WM, job.rules, job.x, job.y, 1, 1.0, 0);
    ctx.API.land(0, { move: { x: truth.x, y: truth.y, path: truth.path } },
                 () => log.push('after()'));
  }
}
out.midAir = { frames: t2.length, end: [ctx.WM_ST.fighters[0].x, ctx.WM_ST.fighters[0].y],
               log: log.slice() };

// ③ คำตอบมาถึงหลังลงพื้นแล้ว
fresh();
ctx.API.fire(1, 1.0, 0);
for (let i = 0; i < 300 && ctx.API.state().fly; i++) ctx.API.fly();
const landed = [ctx.WM_ST.fighters[0].x, ctx.WM_ST.fighters[0].y];
const truth3 = ctx.WALK.jump(ctx.WM, job.rules, job.x, job.y, 1, 1.0, 0);
ctx.API.land(0, { move: { x: truth3.x, y: truth3.y, path: truth3.path } },
             () => log.push('after()'));
out.lateAnswer = { landed: landed, server: [truth3.x, truth3.y],
                   after: [ctx.WM_ST.fighters[0].x, ctx.WM_ST.fighters[0].y], log: log.slice() };
// ④ สถานะถูกแทนทั้งก้อนกลางอากาศ (เปิดหน้าใหม่/จบเทิร์น) — ห้ามค้าง
fresh();
ctx.API.fire(1, 1.0, 0);
ctx.API.fly(); ctx.API.fly();
ctx.WM_FLY = null; ctx.WM_JUMP_END = null;      // สิ่งที่ wmApply ต้องทำ
fresh();
const before = ctx.API.state();
ctx.API.fire(1, 1.0, 0);
out.afterStateSwap = { stuckBefore: before.fly !== null, canJumpAgain: ctx.API.state().fly !== null };

// ⑤ ลงพื้นแล้วเทิร์นเปลี่ยนไปเป็นบอท — ห้ามวาปบอทมาที่จุดเราลง
fresh();
ctx.API.fire(1, 1.0, 0);
for (let i = 0; i < 300 && ctx.API.state().fly; i++) ctx.API.fly();
const meLanded = [ctx.WM_ST.fighters[0].x, ctx.WM_ST.fighters[0].y];
const botWas = [ctx.WM_ST.fighters[1].x, ctx.WM_ST.fighters[1].y];
ctx.WM_ST.turn = 1;                              // เซิร์ฟเวอร์จบเทิร์นให้แล้ว
const t5 = ctx.WALK.jump(ctx.WM, job.rules, job.x, job.y, 1, 1.0, 0);
ctx.API.land(0, { move: { x: t5.x, y: t5.y, path: t5.path } }, () => {});
out.turnFlipped = { me: [ctx.WM_ST.fighters[0].x, ctx.WM_ST.fighters[0].y],
                    meLanded: meLanded,
                    bot: [ctx.WM_ST.fighters[1].x, ctx.WM_ST.fighters[1].y],
                    botWas: botWas };

console.log(JSON.stringify(out));
