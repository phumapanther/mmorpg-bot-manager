// ⏱️ พิสูจน์ว่าภาพในสนามเดินตาม "เวลาจริง" ไม่ใช่ "จำนวนเฟรมที่จอวาด"
//    รันฟังก์ชันของจริงจาก play.js / worms.js ไม่ได้ก๊อปสูตรมาเขียนซ้ำ
const fs = require('fs'), vm = require('vm');
const CR = String.fromCharCode(13), NL = String.fromCharCode(10);
const read = f => fs.readFileSync(f, 'utf8').split(CR + NL).join(NL);
const play = read('license_server/web_static/play.js');
const worms = read('license_server/web_static/worms.js');

const cut = (src, head, tail) => {
  const a = src.indexOf(head);
  if (a < 0) throw new Error('หาไม่เจอ: ' + head);
  const b = src.indexOf(tail, a);
  if (b < 0) throw new Error('หาปลายไม่เจอ: ' + head);
  return src.slice(a, b + tail.length);
};

const ctx = { console, Math, WM_DT: 1, WM_LAST_MS: 0 };
vm.createContext(ctx);
vm.runInContext([
  cut(play, 'let WM_DT = 1, WM_LAST_MS = 0;', NL + 'const WM_FPS = 60;'),
  cut(play, 'function wmClock(', NL + '}' + NL),
  cut(play, 'const WM_SHOT_STEP =', NL),
  // เมธอดของกล้อง — ดึงตัวจริงออกมาแล้วห่อเป็นฟังก์ชันธรรมดา
  'const glide = function ' + cut(worms, 'glide(dt) {', NL + '  }' + NL).slice(5),
  // let/const ในสคริปต์ไม่ติดไปกับ context ต้องยื่นออกมาเอง
  'globalThis.API = { clock: wmClock, glide: glide, shotStep: WM_SHOT_STEP,'
  + ' dt: () => WM_DT, reset: () => { WM_LAST_MS = 0; } };',
].join(NL), ctx);
const API = ctx.API;

/** เล่นไป 1 วินาทีด้วยจอที่รีเฟรชกี่ครั้งต่อวินาที แล้วดูว่าอะไรเดินไปเท่าไหร่ */
function runOneSecond(hz) {
  API.reset();
  const gap = 1000 / hz;
  let now = 1000, frames = 0, dtSum = 0, shot = 0;
  const cam = { x: 0, y: 0, tx: 300, ty: 0, z: 3, ease: 0.10, maxStep: 18,
                clamp() {}, arrivedAt: null };
  for (let ms = 0; ms < 1000; ms += gap) {
    now += gap;
    API.clock(now);
    frames++;
    dtSum += API.dt();
    shot += API.shotStep * API.dt();          // กระสุนเดินไปกี่จุด
    API.glide.call(cam, API.dt());
    if (cam.arrivedAt === null && cam.x > 299) cam.arrivedAt = ms;
  }
  return { hz, frames, dtSum: +dtSum.toFixed(2), shot: +shot.toFixed(2),
           camX: +cam.x.toFixed(1) };
}

console.log(JSON.stringify([30, 60, 75, 120, 144, 240].map(runOneSecond)));
