// 🔬 ของที่เพิ่งลงสนามต้องยังไม่โผล่จนกว่ากล้องจะไปถึงและเล่นเอฟเฟกต์
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
const painted = [];
const ctx = {
  console, Math, Array, Object,
  WM_TOUR_HIDE: [], WM_SPAWNS: [], WM_POPS: [], WM_STEPS: [],
  WM_CAM: { arrived: () => true }, SFX: { play() {} },
  wmFocus: () => {}, wmHoldAt: () => {},
  WM: { props: [], repaint() { painted.push(ctx.WM.props.map(p => p.kind).join(',')); } },
  wmStep: (run, done) => ctx.WM_STEPS.push({ run, done }),
  wmFxIdle: () => true, WM_TURN_SHOWN: '', WM_TOUR_HOLD: 180,
};
vm.createContext(ctx);
vm.runInContext([grab('function wmPropsNow('), grab('function wmShowDrop('),
                 grab('function wmStartTour(')].join(NL)
  + NL + 'globalThis.API = { now: wmPropsNow, tour: wmStartTour, steps: () => WM_STEPS,'
  + ' hidden: () => WM_TOUR_HIDE.length };', ctx);
const API = ctx.API;

// สนามมีหีบเก่าอยู่แล้ว 1 ใบ · รอบนี้ลงใหม่ 3 ชิ้น
const old = [{ kind: 'chest', x: 50, y: 200 }];
const drops = [{ kind: 'ferry', x: 100, y: 200 },
               { kind: 'chest', x: 200, y: 200 },
               { kind: 'trap', x: 300, y: 200 }];
ctx.WM_ST = { props: old.concat(drops) };

API.tour(drops);
const atArrival = API.now(ctx.WM_ST.props).map(p => p.kind);

// เดินคิวทีละขั้น: ขั้นคู่คือเลื่อนกล้อง ขั้นคี่คือปล่อยของ
const revealed = [];
API.steps().forEach(s => { s.run(); revealed.push(API.now(ctx.WM_ST.props).map(p => p.kind).join(',')); });

console.log(JSON.stringify({ beforeTour: atArrival, afterEachStep: revealed,
                             stillHidden: API.hidden() }));
