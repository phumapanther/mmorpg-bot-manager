const fs = require('fs'), vm = require('vm');
const CR = String.fromCharCode(13), NL = String.fromCharCode(10);
const read = f => fs.readFileSync(f, 'utf8').split(CR + NL).join(NL);
const play = read('license_server/web_static/play.js');
const web  = read('license_server/web_static/web.js');
const grab = (src, head) => {
  const a = src.indexOf(head);
  if (a < 0) throw new Error('หาไม่เจอ: ' + head);
  const b = src.indexOf(NL + '}' + NL, a);
  if (b < 0) throw new Error('หาปลายฟังก์ชันไม่เจอ: ' + head);
  return src.slice(a, b + 3);
};
const boxes = {};
const ctx = {
  document: { getElementById: id => (boxes[id] = boxes[id] || { id, innerHTML: '', hidden: false }) },
  SFX: { play() {} }, wmNewMatch: () => {}, api: async () => ({}), toast: () => {},
  console, Math, JSON, Object, Array, String, Number,
  WM_ANIM: null, WM_QUEUE: [], WM_SHOT: null, WM_BOOMS: [],
  WM_AFTER: [], WM_DYING: {}, WM_OVER_SHOWN: false,
  WM_ST: JSON.parse(fs.readFileSync(process.argv[2], 'utf8')),
};
vm.createContext(ctx);
vm.runInContext([grab(web, 'function esc('),
                 grab(play, 'function wmBusyFx('),
                 grab(play, 'function wmPaintOver('),
                 'wmPaintOver();'].join(NL), ctx);
const box = boxes['wmOver'];
console.log('hidden =', box.hidden);
console.log(box.innerHTML.split(NL).map(s => s.trim()).filter(Boolean).join(NL));
