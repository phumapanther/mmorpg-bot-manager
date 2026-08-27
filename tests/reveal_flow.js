// 🔬 รันฟังก์ชัน "ซ่อนผลไว้ก่อน แล้วค่อยเฉลย" ของจริงจาก play.js
//    (ไม่ก๊อปโค้ดมาเขียนซ้ำ — เทสต้องพังถ้าของจริงพัง)
const fs = require('fs'), vm = require('vm');
const CR = String.fromCharCode(13), NL = String.fromCharCode(10);
const play = fs.readFileSync('license_server/web_static/play.js', 'utf8')
               .split(CR + NL).join(NL);
const grab = (head) => {
  const a = play.indexOf(head);
  if (a < 0) throw new Error('หาไม่เจอ: ' + head);
  const b = play.indexOf(NL + '}' + NL, a);
  if (b < 0) throw new Error('หาปลายฟังก์ชันไม่เจอ: ' + head);
  return play.slice(a, b + 3);
};
const ctx = { console, Math, JSON, Object, Array, wmPaintHud: () => {}, WM_HIDDEN: null };
vm.createContext(ctx);
vm.runInContext([grab('function wmSnapshot('), grab('function wmHideOutcome('),
                 grab('function wmRevealOne('), grab('function wmRevealAll(')].join(NL), ctx);

const say = o => console.log(JSON.stringify(o));
ctx.WM_ST = { fighters: [{ name: 'คุณ', x: 10, y: 20, hp: 100, dead: false },
                         { name: 'บอท', x: 90, y: 20, hp: 30, dead: false }] };
const old = ctx.wmSnapshot();
// สถานะใหม่จากเซิร์ฟเวอร์: เราโดน 40 · บอทโดน 30 ตายและถูกผลักไปไกล
ctx.WM_ST.fighters[0].hp = 60;
ctx.WM_ST.fighters[1].hp = 0; ctx.WM_ST.fighters[1].dead = true; ctx.WM_ST.fighters[1].x = 140;
ctx.wmHideOutcome(old);
say({ step: 'hidden', f: ctx.WM_ST.fighters });
ctx.wmRevealOne('บอท', 0);       // เลือดหลังหมัดนี้ ตามที่เซิร์ฟเวอร์บอกมา
ctx.wmRevealOne('คุณ', 75);      // หมัดแรกของเรา — อีก 15 เป็นของบอทที่ยังไม่ได้เล่นภาพ
say({ step: 'one', f: ctx.WM_ST.fighters });
ctx.wmRevealAll();
say({ step: 'all', f: ctx.WM_ST.fighters, left: ctx.WM_HIDDEN });

// ── ยุบหลายหมัดของคนเดียวกัน แล้วส่งต่อ "เลือดหลังหมัดนี้" ให้คนเฉลย ──
//    (ดาบคู่ฟันรัวสี่ครั้ง = สี่รายการของคนเดียว ต้องเหลือรายการเดียว)
const settled = [];
Object.assign(ctx, {
  wmStep: (run) => run(),
  wmPlayKnocks: () => false,
  wmFxIdle: () => true,
  wmSettleVictim: v => settled.push(v),
});
vm.runInContext(grab('function wmPlayVictims('), ctx);
ctx.wmPlayVictims({ hits: [{ name: 'บอท', damage: 12, hp: 88, x: 1, y: 2 },
                           { name: 'บอท', damage: 18, hp: 70, x: 1, y: 2 }] });
say({ step: 'victims', v: settled });
