// 🔬 รันกฎการเดินฝั่งเบราว์เซอร์ (walk.js ตัวจริง) กับเคสที่ฝั่ง Python ส่งมา
//    ใช้พิสูจน์ว่าสองฝั่งคิดเหมือนกันเป๊ะทุกพิกเซล ไม่ใช่ "น่าจะเหมือน"
const fs = require('fs'), vm = require('vm');
const CR = String.fromCharCode(13), NL = String.fromCharCode(10);
const src = fs.readFileSync('license_server/web_static/walk.js', 'utf8')
              .split(CR + NL).join(NL);
const ctx = { console, Math };
vm.createContext(ctx);
vm.runInContext(src + NL + 'globalThis.WALK = WALK;', ctx);

const job = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'));
const flat = job.grid;                       // แถวต่อแถวต่อกันเป็นเส้นเดียว
const map = {
  w: job.w, h: job.h,
  at: (x, y) => flat[y * job.w + x],
};
console.log(JSON.stringify(job.cases.map(c =>
  ctx.WALK.walk(map, job.rules, c[0], c[1], c[2], c[3], !!c[4]))));
