// 🪱 สนามรบ Worms — ย้ายมาจาก play.js (09-02 รื้อโครงสร้าง ขั้นที่ 5)
// ฟังก์ชัน wm* ทั้งหมด + fillWorms + ตัวแปร global ที่ใช้ร่วมกันในหมวดนี้
// ⚠️ ต้องโหลดหลัง play.js เสมอ — ใช้ตัวช่วยกลาง 4 ตัวจาก play.js:
//    bindInviteButtons · inviteFriendsHtml · reload · toast
// ห้ามใช้ import/export — ไฟล์นี้เป็น script ธรรมดา ไม่ใช่ ES module

document.getElementById('wmNew')?.addEventListener('click', () => wmNewMatch(0));
document.getElementById('wmSame')?.addEventListener('click', () => {
  const seed = prompt('วางรหัสแผนที่ที่อยากเปิด', document.getElementById('wmSeed').textContent);
  if (seed && /^\d+$/.test(seed.trim())) wmNewMatch(seed.trim());
});
document.getElementById('wmRoomOpen')?.addEventListener('click', () => wmRoomDo('create'));
document.getElementById('wmRoomJoin')?.addEventListener('click', () => {
  const code = prompt('ใส่รหัสห้องที่เพื่อนส่งมา (5 ตัว)');
  if (code && code.trim()) wmRoomDo('join', { code: code.trim().toUpperCase() });
});
document.getElementById('wmGiveUp')?.addEventListener('click', wmGiveUp);

// ══════════ 🚪 หน้าเลือกโหมด (บอท / เพื่อน) — จัดหน้าจอแบบเดียวกับศึกไพ่รูน ══════════
// เจ้าของเกมสั่ง (09-02): เข้าสนามรบต้องเจอหน้าเลือกโหมดก่อน ไม่ใช่เห็นปุ่มทั้งหมดพร้อมกัน
// ⚠️ ไม่แตะกติกาเกม/bot/pvp ใด ๆ — แค่ซ่อน/โชว์ปุ่มเดิมที่มีอยู่แล้ว ปุ่มทำงานเหมือนเดิมทุกอย่าง

/** เปิดหน้าสนามรบ — เจอหน้าเลือกโหมดก่อนเสมอ (เว้นแต่กำลังเล่นแมตช์ค้างอยู่แล้ว) */
function wmShowGate() {
  document.getElementById('wmModeGate')?.classList.remove('hidden');
  const bot = document.getElementById('wmBotButtons'); if (bot) bot.hidden = true;
  const fr = document.getElementById('wmFriendButtons'); if (fr) fr.hidden = true;
  wmGameArea(false);          // ซ่อนจอเกมด้วย ไม่งั้นโผล่มาคาหน้าเลือกโหมด
  wmRoomWatch(false);
}

/** เปิด/ปิดจอเกมทั้งก้อน (จอ · ปุ่มซูม · แถบสกิล · ล็อก) */
function wmGameArea(on) {
  const box = document.getElementById('wmGameArea');
  if (box) box.hidden = !on;
}

document.getElementById('wmModeBot')?.addEventListener('click', async () => {
  SFX.play('click');
  document.getElementById('wmModeGate')?.classList.add('hidden');
  wmGameArea(true);
  const bot = document.getElementById('wmBotButtons'); if (bot) bot.hidden = false;
  await fillWorms();
});

document.getElementById('wmModeFriend')?.addEventListener('click', async () => {
  SFX.play('click');
  document.getElementById('wmModeGate')?.classList.add('hidden');
  wmGameArea(true);
  const fr = document.getElementById('wmFriendButtons'); if (fr) fr.hidden = false;
  await fillWorms();
});
document.getElementById('wmIn')?.addEventListener('click', () => wmZoom(1));
document.getElementById('wmOut')?.addEventListener('click', () => wmZoom(-1));
document.getElementById('wmFit')?.addEventListener('click', () => {
  WM_CAM?.fit(); document.getElementById('wmZoom').textContent = '×' + WM_CAM.z; });

// ปุ่มบนจอ (มือถือ) — กดค้างเดินต่อเนื่อง
const WM_ACT = { left: ['walk', -1], right: ['walk', 1], jumpL: ['jump', -1], jumpR: ['jump', 1] };
document.querySelectorAll('[data-wm]').forEach(b => {
  const a = WM_ACT[b.dataset.wm];
  // ต้องห่อด้วยลูกศร ไม่งั้น MouseEvent จะถูกส่งไปเป็นชื่อคำสั่ง เซิร์ฟเวอร์ปฏิเสธทุกครั้ง
  if (!a) { b.addEventListener('click', () => wmEndTurn()); return; }
  b.addEventListener('pointerdown', e => { e.preventDefault(); wmHoldStart(a[0], a[1]); });
  ['pointerup', 'pointerleave', 'pointercancel'].forEach(ev =>
    b.addEventListener(ev, () => wmHoldStop(a[0])));
});

// คีย์บอร์ด (คอม) — ทำงานเฉพาะตอนอยู่หน้าสนามรบ
const WM_KEY = { ArrowLeft: ['walk', -1], ArrowRight: ['walk', 1],
                 ArrowUp: ['jump', 1], ' ': ['jump', 1] };
document.addEventListener('keydown', e => {
  if (!document.getElementById('v-worms')?.classList.contains('on')) return;
  if (e.repeat) return;
  if (e.key === 'Enter') return void wmEndTurn();
  const a = WM_KEY[e.key];
  if (!a) return;
  e.preventDefault();
  wmHoldStart(a[0], e.key === 'ArrowUp' || e.key === ' '
              ? (WM_ST && wmMe().face < 0 ? -1 : 1) : a[1]);
});
document.addEventListener('keyup', e => {
  const a = WM_KEY[e.key];
  if (a) wmHoldStop(a[0]);              // ปล่อยเฉพาะปุ่มนั้น ไม่ใช่ปล่อยหมดทุกอย่าง
});
document.getElementById('wmSame')?.addEventListener('click', async () => {
  const seed = prompt('วางรหัสแผนที่ที่อยากเปิด', document.getElementById('wmSeed').textContent);
  if (seed && /^\d+$/.test(seed.trim())) wormsReroll(seed.trim());
});

// ── 🪱 สนามรบผลัดเทิร์น ──
// แผนที่มาจากเซิร์ฟเวอร์ทั้งใบ ที่นี่แค่วาด + คุมกล้อง (ซูม/เลื่อน/กระโดดไปดูคนอื่น)
let WM = null, WM_CAM = null, WM_ST = null;
let wmLoop = 0, wmHold = 0, wmBusy = false;
let WM_TIME_LEFT = 0;
let WM_DEADLINE = 0;       // เวลาหมดเทิร์น (เทียบจาก time_left ที่เซิร์ฟเวอร์ส่งมา)

let WM_ANIM = null;        // เส้นทางที่เซิร์ฟเวอร์ส่งมา กำลังเล่นภาพอยู่

// ก้าวต่อการยิงคำสั่งหนึ่งครั้ง — ยิงก้อนใหญ่ห่าง ๆ ดีกว่าก้อนเล็กถี่ ๆ
// 36 ก้าวเล่นภาพที่ 60fps = 600ms พอดีกับช่วงยิง ภาพจึงเดินต่อเนื่องไม่สะดุด
// ตกเหลือ 1.7 ครั้ง/วินาที (แรงเดินมีแค่ 60/เทิร์นอยู่แล้ว สองคำสั่งก็หมดเทิร์น)
const WM_WALK_STEPS = 6;
const WM_HOLD_MS = 500;
let WM_BACKOFF = 0;        // โดน 429 แล้วหยุดยิงชั่วคราว กันวนยิงซ้ำจนแย่ลงกว่าเดิม

async function fillWorms() {
  try { wmApply(await api('GET', '/api/web/pvp/worms/match')); }
  catch (e) { toast(e.message, true); }
}
async function wmNewMatch(seed) {
  try {
    wmApply(await api('POST', '/api/web/pvp/worms/match', { action: 'new', seed: seed || 0 }));
    SFX.music('battle');       // เพลงคลอสนามรบ (battle เป็นเพลง ไม่ใช่เสียงเอฟเฟกต์)
  } catch (e) { toast(e.message, true); }
}
/** รับสถานะจากเซิร์ฟเวอร์มาแสดง — พื้นสร้างใหม่เฉพาะตอนแมตช์เปลี่ยน */
function wmApply(d) {
  const fresh = !WM || !WM_ST || WM_ST.seed !== d.seed;
  wmStepsClear();
  WM_TOUR_HIDE = [];               // คิวถูกล้าง = ไม่มีใครมาปล่อยของที่ซ่อนไว้แล้ว
  WM_WARPING = -1;                 // และไม่มีใครมาพาตัวที่ถูกดูดวาร์ปกลับมาโผล่
  WM_ANIM = null; WM_QUEUE = [];   // สถานะถูกแทนทั้งก้อน ภาพที่ค้างเป็นของสถานะเก่าไปแล้ว
  WM_HIDDEN = null;                // ค่าที่ซ่อนไว้ก็เป็นของก้อนเก่า ทิ้งได้เลย
  if (!d || !d.over) WM_OVER_SHOWN = false;
  if (d && (d.drops || []).length && d.round !== WM_TOUR_ROUND) {
    WM_TOUR_ROUND = d.round;               // ของรอบนี้พาไปดูแล้ว ไม่พาซ้ำ
    wmStartTour(d.drops);
  }
  if (!WM_ST || !d || WM_ST.seed !== d.seed) {      // สนามใหม่ = เริ่มนับคนตายใหม่
    Object.keys(WM_DEAD_SEEN).forEach(k => delete WM_DEAD_SEEN[k]);
    Object.keys(WM_DYING).forEach(k => delete WM_DYING[k]);
    WM_AFTER = [];
  }
  WM_ST = d;
  document.getElementById('v-worms').classList.toggle('wm-idle', !d.active);
  // ⚠️ ห้ามวาดแผงสรุปผลตรงนี้ — ภาพของคำตอบนี้ยังไม่ถูกต่อคิวเลยสักอย่าง
  //    (ตาบอท ร่างระเบิด วิถีกระสุน ถูกต่อคิวโดยผู้เรียกหลังจากบรรทัดนี้)
  //    wmBusyFx() จึงยังว่าง แผงเลยโผล่ทันทีแล้วหายไปตอนภาพเริ่มเล่น
  //    ผู้เล่นเห็นผลแพ้ชนะก่อนเห็นตัวเองตายด้วยซ้ำ — โชว์ได้ที่ wmTick ที่เดียว
  if (!d.active) {
    wmPaintOver();                     // ออกจากสนามแล้ว — ขึ้นหน้าเริ่มเกม
    cancelAnimationFrame(wmLoop); wmLoop = 0; WM = WM_ST = null; return;
  }
  // 🚪 แมตช์กำลังเล่นอยู่ = ปิดแผงเสมอ (ทั้งหน้าเริ่มเกมและแผงสรุปผลของแมตช์ก่อน)
  //    "ปิด" ปลอดภัยเสมอ ต่างจาก "เปิด" ที่ต้องรอภาพเล่นจบก่อน จึงทำตรงนี้ได้
  //    ⚠️ ไม่มีบรรทัดนี้ = กดเริ่มเกมใหม่แล้วหน้าเริ่มเกมค้างทับสนามที่เล่นอยู่
  wmShutOver();

  WM_TIME_LEFT = d.time_left || 0;
  WM_DEADLINE = performance.now() + WM_TIME_LEFT * 1000;
  // 👥 เทิร์นของคนอื่นที่ยังไม่เคยดู — ต่อคิวภาพให้ ไม่ใช่ปล่อยให้ตัววาปไปโผล่
  //    วางไว้ "หลัง" ล้างคิวข้างบน ไม่งั้นภาพที่เพิ่งต่อโดนล้างทิ้งทันที
  // ⚠️ เฉพาะห้องเล่นหลายคน — ซ้อมกับบอทมี wmQueueBot() เล่นภาพอยู่แล้ว
  //    ใส่ทั้งสอง = บอทเดินสองรอบ (ทดสอบแล้วเกิดจริงตอนเล่นมาสักพัก)
  if (d.room && !d.my_turn) wmQueueOther(d);
  else wmSeenTurn(d);          // ตาเรา/ซ้อมบอท = มีคนเล่นภาพให้อยู่แล้ว แค่จดว่าดูแล้ว
  if (fresh) {
    WM = new WormsMap(d);
    WM.props = wmPropsNow(d.props); WM.repaint();
    const cv = document.getElementById('wmCanvas');
    wmFitCanvas();                     // ตั้งขนาดภาพจริงก่อน กล้องจะได้จำขนาดที่ถูก
    WM_CAM = new WormsCam(cv, WM);
    WM_CAM.attach(null);
    if (!cv.dataset.aimed) { cv.dataset.aimed = '1'; wmBindAim(cv); }
    WM_CAM.z = 3;
    WM_CAM.center(WM_ST.fighters[WM_ST.turn].x,
                  WM_ST.fighters[WM_ST.turn].y - 10, true);   // ครั้งแรกจัดให้ทันที
    WM_TURN_SHOWN = '';
    WM_GROUND = d.terrain;
    wmFocus(null, true);
    wmStartLoop();
  } else {
    WM.props = wmPropsNow(d.props); WM.repaint();
  }
  // 🌊 ระดับภัยพิบัติไต่ขึ้นทุกรอบ — ต้องอัปเดตก่อนวาดเฟรมถัดไป
  if (WM) { WM.flood = d.flood || 0; WM.disaster = d.disaster || 'water'; }
  if (d.disaster_hit) wmWarnDisaster(d.disaster_hit, d.disaster);
  wmPaintHud();
}
/** 🌊 ประกาศภัยพิบัติ — ครั้งแรกเตือนใหญ่ ครั้งต่อไปแค่บอกว่ามันขึ้นมาอีกขั้น */
function wmWarnDisaster(hit, kind) {
  const name = { water: '🌊 น้ำท่วม', lava: '🌋 ลาวาไหล',
                 poison: '☠️ บ่อพิษ' }[kind] || '🌊 น้ำท่วม';
  if (hit.first) {
    SFX.play('danger');
    toast(name + 'เริ่มขึ้นแล้ว — รีบหนีขึ้นที่สูง!', true);
  }
  wmStep(() => {
    WM_POPS.push({ x: WM.w / 2, y: hit.line - 14, t: 0, text: name + ' ขึ้นมาอีก!' });
    if (!hit.first) SFX.play('trap');
  }, () => true);
}
function wmMe() { return WM_ST.fighters[WM_ST.turn]; }
/** เลื่อนกล้องตามเฉพาะตอนตัวใกล้ขอบจอ

    ตามทุกเฟรมแล้วตัวจะค้างกลางจอ พื้นไหลอยู่ข้างใต้ — เห็นเป็นยืนลื่นไถลไปกับพื้น
    ต้องปล่อยให้ตัวเดินข้ามพื้นจริง ๆ แล้วค่อยเลื่อนจอตามเมื่อจะตกขอบ
 */
function wmFocus(f, force) {
  f = f || wmMe();
  if (!WM_CAM || !f) return;
  const x = WM_CAM.sx(f.x), y = WM_CAM.sy(f.y);
  const mx = WM_CAM.vw * 0.28, my = WM_CAM.vh * 0.28;
  if (force || x < mx || x > WM_CAM.vw - mx || y < my || y > WM_CAM.vh - my)
    WM_CAM.center(f.x, f.y - 10);
}
function wmStartLoop() {
  const cv = document.getElementById('wmCanvas'), ctx = cv.getContext('2d');
  cancelAnimationFrame(wmLoop);
  let t = 0, last = 0;
  // 🛟 error เฟรมเดียวเคยฆ่าลูปวาดทั้งอัน = ภาพค้าง กดอะไรไม่ได้ ปุ่มยอมแพ้ก็ตาย
  //    ผู้เล่นเห็นเป็น "พังหมดทุกอย่าง" ทั้งที่ต้นเหตุคือบัคเล็ก ๆ จุดเดียว
  //    ห่อไว้ให้เฟรมถัดไปยังวาดต่อได้ และพ่น error ลง console ให้เห็นเต็ม ๆ
  const tick = (now) => {
    try {
      frame(now);
    } catch (e) {
      console.error('[worms] เฟรมนี้พัง — เล่นต่อเฟรมหน้า', e);
      wmLoop = requestAnimationFrame(tick);
    }
  };
  const frame = (now) => {
    if (!document.getElementById('v-worms').classList.contains('on')) { wmLoop = 0; return; }
    wmClock(now);
    // เล่นภาพเส้นทางที่เซิร์ฟเวอร์ส่งมาทีละเฟรม (ตำแหน่งจริงเซิร์ฟเวอร์ตัดสินไปแล้ว)
    if (WM_ANIM && WM_ANIM.i < WM_ANIM.path.length) {
      // ก้าวสั้น ๆ ค้างจุดละหลายเฟรม จะได้เดินเตาะแตะทีละก้าวให้เห็น ไม่ใช่วืดไปทีเดียว
      // ส่วนท่อนยาว (ตาบอททั้งเทิร์น) เล่นรวดเดียว ไม่งั้นนั่งดูบอทเดินนาน
      // สามชั้น: ก้าวสั้นของเราเอง / ท่อนกลาง ๆ อย่างการกระเด็น / ท่อนยาวอย่างตาบอทเดิน
      const hold = WM_ANIM.path.length <= 12 ? 5 : WM_ANIM.path.length <= 60 ? 3 : 1;
      // ⚠️ เดินหน้าทีละ 1/hold จุดแล้วเกลี่ยตำแหน่งระหว่างจุด — ไม่ใช่ค้าง hold เฟรม
      //    แล้วกระโดดทีเดียว จุดในวิถีกระโดดห่างกันได้ 3-4 px ค้างแล้วกระโดดจึงเห็นเป็นวาป
      const before = Math.floor(WM_ANIM.i);
      WM_ANIM.i = Math.min(WM_ANIM.path.length, WM_ANIM.i + WM_DT / hold);
      {
        const last = WM_ANIM.path.length - 1;
        const at = Math.min(Math.floor(WM_ANIM.i), last);
        const pa = WM_ANIM.path[at], pb = WM_ANIM.path[Math.min(at + 1, last)];
        const mix = Math.min(1, WM_ANIM.i - at);
        const x = pa[0] + (pb[0] - pa[0]) * mix;
        const y = pa[1] + (pb[1] - pa[1]) * mix;
        const stepped = Math.floor(WM_ANIM.i) !== before;   // ข้ามจุดใหม่หรือยัง
        const af = WM_ST.fighters[WM_ANIM.fi];    // อ่านสดทุกเฟรม สถานะอาจถูกแทนไปแล้ว
        if (af) {
          if (stepped) WM_ANIM.dy = pb[1] - pa[1];   // ลบ = ลอยขึ้น · บวกเยอะ = กำลังตก
          if (WM_ANIM.dy > 2) wmDust(af.x, af.y, 2);        // ฝุ่นตามตัวตอนดิ่ง
          if (WM_ANIM.air && WM_ANIM.dy <= 0) {   // เพิ่งแตะพื้น = ฝุ่นฟุ้งตรงจุดลง
            wmDust(x, y, 12); SFX.play('walk');
          }
          WM_ANIM.air = WM_ANIM.dy > 2 || WM_ANIM.dy < -1;
          const wl = WM.h - WM.water;                  // ผิวน้ำ
          if (af.y < wl && y >= wl) { wmSplash(x, wl); SFX.play('lose'); }
          // 🤕 หัวชนเกิดกลางอากาศ แต่เดิมเอฟเฟกต์รอไปขึ้นตอนเท้าแตะพื้น (ท้ายอนิเมชั่น)
          //    จุดชนคือจุดสูงสุดของวิถีพอดี — วิถีหลังจากนั้นคือการร่วงลง
          if (WM_ANIM.bump && WM_ANIM.dy >= 0) {
            wmBump(WM_ANIM.bump[0], WM_ANIM.bump[1]);
            WM_ANIM.bump = null;                       // ครั้งเดียวพอ
          }
          af.x = x; af.y = y;
        }
        if (af && stepped && Math.floor(WM_ANIM.i) % 3 === 0) SFX.play('walk');
        // ตามคนที่กำลังขยับ ไม่ใช่ตาปัจจุบัน จะได้เห็นบอทเดินด้วย
        // ท่อนที่ fi < 0 คือ "ค้างกล้องไว้ตรงจุดหนึ่ง" (เช่นดูร่างระเบิด) ไม่มีตัวใครให้ตาม
        wmFocus(af || { x: x, y: y });
      }
    } else if (WM_ANIM) {
      const done = WM_ANIM.onEnd;              // งานต่อท้ายของท่อนนี้ (อาจต่อคิวเพิ่ม)
      WM_ANIM = null;
      if (done) done();
      WM_ANIM = WM_QUEUE.shift() || null;
      if (!WM_ANIM) {
        // ตัวหยุดกระเด็นแล้ว ถึงค่อยสรุปว่าโดนไปเท่าไหร่ ตายหรือไม่ตาย
        while (WM_AFTER.length) WM_AFTER.shift()();
        wmPaintHud();
      }
    }
    // ถึงตาใครก็เลื่อนกล้องไปหาคนนั้นเอง — รอให้ภาพที่ค้างเล่นจบก่อน ไม่งั้นตัดกลางคัน
    const turnKey = WM_ST.round + ':' + WM_ST.turn;
    // ⚠️ ต้องรอ "ทุกอย่าง" ที่ถือกล้องอยู่เล่นจบก่อน ไม่ใช่แค่ท่อนเดินกับกระสุน
    //    เดิมเช็คแค่ WM_ANIM/WM_SHOT — ตอนพากล้องไปดูของที่ลงสนาม (WM_TOUR) สองอย่างนั้นว่าง
    //    บรรทัดนี้เลยแย่งกล้องกลับมาที่ตัวเราทุกเฟรม สลับไปมากับทัวร์จนดูเหมือนกล้องสับสน
    if (!wmBusyFx() && turnKey !== WM_TURN_SHOWN) {
      WM_TURN_SHOWN = turnKey;
      wmFocus(wmMe(), true);
    }
    wmTick();
    wmWalkTick();

    WM_CAM.glide(WM_DT);   // เลื่อนเข้าหาเป้าทีละนิด — จอไม่กระโดด
    WM.draw(ctx, WM_CAM, t++);
    WM_ST.fighters.forEach((f, i) => {
      const moving = !!(WM_ANIM && WM_ANIM.fi === i)
                  || !!(WM_PRED && !WM_PRED.done && i === WM_ST.turn);
      // ตายแล้วแต่ภาพร่วง/จมน้ำ/ภาพตายยังเล่นค้างอยู่ = ต้องวาดต่อ ไม่งั้นหายวับ
      if (WM_DYING[i]) { if ((WM_DYING[i] -= WM_DT) <= 0) delete WM_DYING[i]; }
      if (i === WM_WARPING) return;     // ถูกดูดเข้าวาร์ปแล้ว ยังไม่โผล่ที่ปลายทาง
      if (!f.dead || moving || WM_DYING[i]) wmDrawFighter(ctx, f, i === WM_ST.turn, t, moving);
    });
    wmDrawFx(ctx);
    wmLoop = requestAnimationFrame(tick);
  };
  tick();
}
/** วาดนักสู้ตามกล้อง — ซูมออกสุดตัวจะเล็กมาก จึงมีแถบเลือดกับลูกศรชี้ตาปัจจุบัน */
function wmDrawFighter(ctx, f, active, t, walking) {
  const z = WM_CAM.z, x = WM_CAM.sx(f.x), y = WM_CAM.sy(f.y);
  if (x < -60 || x > WM_CAM.vw + 60) return;
  // เดินอยู่ก็สลับท่าขาตามก้าวจริง ไม่ใช่ยืนท่าเดิมแล้วเลื่อนตัวไป (เห็นเป็นลื่นไถล)
  // ⚠️ เดินเองฝั่งจอไม่มี WM_ANIM — นับก้าวจากตัวทำนายแทน (แตะ WM_ANIM ตรง ๆ จะพัง)
  const anim = WM_ANIM && WM_ANIM.fi === WM_ST.turn ? WM_ANIM : null;
  const air = walking && anim && anim.air;
  const beat = anim ? Math.floor(anim.i) : (WM_PRED ? WM_PRED.pending + WM_PRED.beat : 0);
  const pose = !walking ? 'idle' : air ? 'run1' : (beat % 2 ? 'run1' : 'run2');
  const look = { ...(f.look || {}), pose: pose, flip: f.face < 0 };
  const hurt = WM_FLASH[f.name] || 0;
  if (hurt) { WM_FLASH[f.name] = hurt - 1; ctx.globalAlpha = hurt % 4 < 2 ? .35 : 1; }
  // จมอยู่ใต้ผิวน้ำ — ยิ่งลึกยิ่งจาง ให้เห็นว่าค่อย ๆ จมหายไป ไม่ใช่หายวับ
  const deep = f.y - (WM.h - WM.water);
  if (deep > 0) ctx.globalAlpha = Math.max(0, 1 - deep / 18) * .8;
  if (air) {                       // ลอยอยู่ = เอียงตัวสะบัดไปมา ให้เห็นว่าไม่ได้ยืน
    ctx.save();
    ctx.translate(x, y - 11 * z);
    ctx.rotate(Math.sin(t / 2.5) * 0.28 * (WM_ANIM.dy > 0 ? 1 : -1));
    ctx.translate(-x, -(y - 11 * z));
  }
  if (z >= 2) drawCharacter(ctx, x - 8 * z, y - 21 * z, z, look);
  else { ctx.fillStyle = f.bot ? '#ff9d84' : '#8fd0a0'; ctx.fillRect(x - 3, y - 10, 6, 10); }
  if (air) ctx.restore();
  ctx.globalAlpha = 1;

  const bw = Math.max(16, 14 * z / 2), by = y - 22 * z - 8;
  ctx.fillStyle = '#00000099'; ctx.fillRect(x - bw / 2 - 1, by - 1, bw + 2, 5);
  ctx.fillStyle = f.bot ? '#ff6a4a' : '#6fd07a';
  ctx.fillRect(x - bw / 2, by, bw * Math.max(0, f.hp) / f.max_hp, 3);
  if (active) {                                  // ลูกศรกระพริบชี้คนที่ถึงตา
    ctx.fillStyle = '#ffd66b';
    const bob = Math.round(Math.sin(t / 9) * 2);
    for (let i = 0; i < 5; i++) ctx.fillRect(x - 4 + i, by - 12 + bob + i, 9 - i * 2, 1);
  }
}
let WM_QUEUE = [];         // ท่อนเดินที่รอเล่นภาพ (บอทเดินหลายท่อนต่อกัน)

let WM_AFTER = [];         // งานที่ต้องรอภาพเล่นจบก่อน (สรุปดาเมจ · ประกาศคนตาย)

let WM_DEATHS = [];        // ร่างที่รอระเบิด — เล่นหลังสรุปดาเมจของหมัดนั้นเสร็จ

const WM_DYING = {};       // ลำดับ -> เฟรมที่เหลือของภาพตาย (ตายแล้วยังต้องวาดต่อ)

let WM_OVER_SHOWN = false; // ตอนนี้แผง (หน้าเริ่มเกม/สรุปผล) โชว์อยู่ไหม

let WM_TOUR_ROUND = 0;     // พาไปดูของรอบไหนแล้ว

const WM_TOUR_HOLD = 180;  // ค้างที่ของแต่ละชิ้น 3 วินาที — เริ่มนับ "หลัง" กล้องเลื่อนไปถึงแล้ว

const WM_SPAWN_LIFE = 110; // เอฟเฟกต์ของที่ลงสนามอยู่ได้กี่เฟรม

let WM_GROUND = '';        // พื้นผืนที่ฝั่งเว็บใช้อยู่ตอนนี้ (ไว้เทียบกับของเซิร์ฟเวอร์)

let WM_TURN_SHOWN = '';    // 'รอบ:ตา' ที่เลื่อนกล้องไปให้แล้ว

                           // ต้องมีเลขรอบด้วย — ซ้อมกับบอทจบเทิร์นแล้ว turn กลับมาเป็น 0
                           // เท่าเดิมทุกครั้ง เทียบแค่ turn กล้องเลยไม่เคยขยับเลย
let wmTimingOut = false, wmNextTimeout = 0;
/** นับถอยหลังบนจอ + พอหมดเวลาก็ขอจบเทิร์น (เซิร์ฟเวอร์เช็คเวลาเองอีกชั้น) */
function wmTick() {
  // ⏱️ ภาพตาบอทยังเล่นค้างอยู่ = เทิร์นเรายังไม่ได้เริ่มจริงในสายตาผู้เล่น
  //    ปล่อยให้นับต่อไปจะกลายเป็นหมดเวลาระหว่างนั่งดูบอทเดิน แล้วขอจบเทิร์น
  //    ไปตัดภาพบอทกลางคันด้วย — เลื่อนเส้นตายหนีไปเรื่อย ๆ จนกว่าภาพจะเล่นจบ
  // ⏱️ หยุดนาฬิกาตลอดช่วงที่ระบบกำลังเล่นลำดับให้ดู (รวมช่วงเว้นจังหวะของคิวขั้นตอน)
  //    เดิมหยุดเฉพาะตอนมีภาพเล่นอยู่ ช่วงเว้นจังหวะ 3 วินาทีต่อขั้นจึงกินเวลาเทิร์นผู้เล่น
  //    ลำดับยาว ๆ กินไป 15-20 วิ พอถึงตาจริงเลยเหลือเวลานิดเดียว บางทีหมดเวลาไปแล้ว
  if (wmBusyFx()) WM_DEADLINE = performance.now() + WM_TIME_LEFT * 1000;
  // ⚠️ งานที่ค้างต้องสะสางแม้ไม่มีภาพเล่นอยู่ ไม่ใช่รอจังหวะที่ภาพเพิ่งเล่นจบอย่างเดียว
  //    ยิงพลาดไม่โดนใคร = งานถูกเข้าคิวทั้งที่ไม่มีอะไรเล่น แล้วไม่มีใครมาสะสาง
  //    ผลคือ wmWaiting() ค้างเป็น true ตลอดกาล กดอะไรไม่ได้อีกเลยทั้งเกม
  if (!WM_ANIM && WM_AFTER.length) {
    while (WM_AFTER.length) WM_AFTER.shift()();
    wmPaintHud();
  }
  if (WM_HIDDEN && !wmBusyFx()) wmRevealAll();   // ภาพจบแล้วค่อยเฉลยที่เหลือ
  wmPeekTurn();                                  // เล่นหลายคน — คอยดูว่าถึงตาเรายัง
  // 🧭 ภาพเล่นจบหมดแล้วค่อยเทียบพื้นกับของเซิร์ฟเวอร์ — เจอต่างเมื่อไหร่โหลดใหม่ทั้งผืน
  //    (เทียบตอนภาพยังเล่นไม่ได้ หลุมจะโผล่ก่อนกระสุนจะบินถึง)
  if (WM && WM_ST && WM_ST.terrain && !wmBusyFx() && WM_ST.terrain !== WM_GROUND) {
    WM_GROUND = WM_ST.terrain;
    WM.reload(WM_ST.terrain);
  }
  wmRunSteps();
  // 🔒 ระหว่างกล้องแพนอัตโนมัติ ห้ามลากจอ — ลากสวนทางแล้วจะเห็นเป็นจอกระตุก/วาป
  //    (เจ้าของเกมสั่ง: ช่วงแพนออโต้ ทุกคนทำอะไรไม่ได้เลยแม้แต่เลื่อนจอ)
  if (WM_CAM) WM_CAM.locked = !!WM_AIM || wmWaiting() || !WM_CAM.arrived();
  wmSyncLock();
  // ภาพเล่นจบแล้วค่อยเฉลยว่าใครแพ้ใครชนะ (วาดครั้งเดียว ไม่ใช่ทุกเฟรม)
  // 🏁 แผงสรุปผลโชว์ได้จากที่นี่ที่เดียว — วาดใหม่เมื่อ "ที่โชว์อยู่" ไม่ตรงกับ "ควรโชว์ไหม"
  //    (ครอบทั้งขาโชว์ตอนภาพจบ และขาซ่อนคืนตอนมีภาพโผล่มาทีหลัง เช่นระเบิดลูกโซ่)
  if (WM_ST.over && WM_OVER_SHOWN !== !wmBusyFx()) wmPaintOver();
  if (WM_AIM) WM_AIM.pow = Math.min(100, 10 + (performance.now() - WM_AIM.t0) * 90 / WM_CHARGE_MS);
  const el = document.getElementById('wmClock');
  if (!el || !WM_ST || !WM_ST.active) return;
  const left = WM_ST.over ? 0 : Math.max(0, Math.ceil((WM_DEADLINE - performance.now()) / 1000));
  el.textContent = '⏱️ ' + String(Math.floor(left / 60)) + ':' + String(left % 60).padStart(2, '0');
  el.classList.toggle('low', left <= 10 && !WM_ST.over);
  // ⚠️ ขอจบเทิร์นแล้วพลาด (เน็ตหลุด/โดนจำกัดอัตรา) ห้ามวนยิงใหม่ทุกเฟรม
  //    ไม่งั้นกลายเป็นยิง 60 ครั้งต่อวินาที ซึ่งยิ่งทำให้โดนจำกัดหนักกว่าเดิม
  const now = performance.now();
  if (left <= 0 && !WM_ST.over && !wmTimingOut && now >= WM_BACKOFF && now >= wmNextTimeout) {
    wmTimingOut = true;
    wmNextTimeout = now + 4000;
    wmHoldStop();
    wmEndTurn('timeout').finally(() => { wmTimingOut = false; });
  }
}
function wmPaintHud() {
  const d = WM_ST;
  if (!d || !d.active) return;
  document.getElementById('wmSeed').textContent = d.seed;
  document.getElementById('wmWhere').innerHTML =
    '🗺️ ' + esc(d.continent_label) + ' · 🎁 ' + d.props.length + ' ชิ้น · 🕳️ ' +
    d.traps + ' กับดัก';
  wmPaintWind(d.wind || 0);
  // ตาใคร = ดูจากภาพที่กำลังเล่น ไม่ใช่ d.turn (บอทเดินจบไปแล้วฝั่งเซิร์ฟเวอร์)
  const acting = WM_ANIM && d.fighters[WM_ANIM.fi] ? d.fighters[WM_ANIM.fi] : wmMe();
  document.getElementById('wmTurn').innerHTML = d.over
    ? '🏁 <b>จบแล้ว</b> — ' + (d.winner ? esc(d.winner) + ' ชนะ!' : 'เสมอ')
    : 'รอบ ' + d.round + ' · ตาของ <b>' + esc(acting.name) + '</b>'
      + (acting.bot ? ' <i class="wm-hold">รอก่อน…</i>' : '');
  const pct = Math.round(d.moves * 100 / d.move_budget);
  document.getElementById('wmMoves').style.width = pct + '%';
  document.getElementById('wmMovesTxt').textContent = d.moves + '/' + d.move_budget;
  document.getElementById('wmWho').innerHTML = d.fighters.map((f, i) =>
    `<button data-look="${i}" class="${f.dead ? 'dead' : ''}${i === d.turn ? ' now' : ''}">
       ${esc(f.name)} ${f.dead ? '☠️' : f.hp + '❤️'}</button>`).join('');
  document.getElementById('wmWho').querySelectorAll('[data-look]').forEach(b =>
    b.onclick = () => { const f = d.fighters[+b.dataset.look];
                        WM_CAM.center(f.x, f.y - 10); SFX.play('click'); });
  document.getElementById('wmLog').innerHTML = (d.log || []).map(l => '<div>' + esc(l) + '</div>').join('');
  WM_LOCK_SHOWN = null; wmSyncLock();      // ล็อก/ปลดล็อกที่เดียว จะได้ไม่ขัดกันเอง
  wmPaintSkills();
}
/** 🌬️ แถบลม — ยืมกติกามาจาก hedgewars: ลมเปลี่ยนทุกเทิร์น เป่ากระสุนวิถีโค้งให้เบน

    เซิร์ฟเวอร์ส่งมาเป็น -100 (พัดไปทางซ้ายสุด) ถึง 100 (ขวาสุด) ไม่ใช่ค่าฟิสิกส์จริง
    วาดจากกลางแถบยื่นออกไปตามทางที่ลมพัด ยาวตามความแรง
 */
function wmPaintWind(w) {
  const bar = document.getElementById('wmWind');
  const txt = document.getElementById('wmWindTxt');
  if (!bar || !txt) return;
  const size = Math.min(50, Math.abs(w) / 2);       // ครึ่งแถบ = ลมเต็มแรง
  bar.style.width = size + '%';
  bar.style.left = w >= 0 ? '50%' : (50 - size) + '%';
  txt.textContent = (w > 4 ? '🌬️→ ' : w < -4 ? '←🌬️ ' : '🌬️ นิ่ง ') +
                    (Math.abs(w) > 4 ? Math.abs(w) : '');
}
let WM_SKILL = null;       // สกิลที่เลือกไว้ (ที่ต้องเล็งจะรอกดยิงอีกที)

// 🎯 เล็งด้วยการกดค้างบนแผนที่ — ไม่มีปุ่มมุม/แรง/ยิงมารกจอ
//    กดฝั่งไหน = ยิงไปทางนั้น · ค้างนาน = แรงขึ้น(ไกลขึ้น) · เลื่อนขึ้นลง = ปรับองศา · ปล่อย = ยิง
let WM_AIM = null;
const WM_CHARGE_MS = 1100;    // กดค้างนานเท่านี้แถบชาร์จเต็ม

function wmSpec(key) {
  return (WM_ST.skills || []).concat(WM_ST.items || []).find(x => x.key === key);
}
/** ผูกการเล็งเข้ากับผืนผ้าใบ — เรียกครั้งเดียวตอนเปิดสนามแรก */
function wmBindAim(cv) {
  const at = e => {
    const r = cv.getBoundingClientRect(), t = e.touches ? e.touches[0] : e;
    return { x: (t.clientX - r.left) * cv.width / r.width,
             y: (t.clientY - r.top) * cv.height / r.height };
  };
  const down = e => {
    if (!WM_SKILL || wmBusy || wmWaiting()) return;
    const p = at(e), sp = wmSpec(WM_SKILL);
    if (!sp) return;
    WM_AIM = { t0: performance.now(), y0: p.y, pow: 10, kind: sp.kind,
               ang: sp.kind === 'melee' ? 0 : 45,     // ฟันตรงหน้า / โยนโค้ง 45°
               dir: WM_CAM.mx(p.x) >= wmMe().x ? 1 : -1 };
    WM_CAM.locked = true;              // ห้ามลากเลื่อนกล้องทับการเล็ง
    SFX.play('click');
    e.preventDefault();
  };
  const move = e => {
    if (!WM_AIM) return;
    const base = WM_AIM.kind === 'melee' ? 0 : 45;
    WM_AIM.ang = Math.max(-89, Math.min(89, base + (WM_AIM.y0 - at(e).y) * 0.5));
    e.preventDefault();
  };
  const up = () => {
    if (!WM_AIM) return;
    const a = WM_AIM;
    WM_AIM = null; WM_CAM.locked = false;
    wmAttack(WM_SKILL, Math.round(a.ang), Math.round(a.pow), a.dir);
  };
  cv.addEventListener('mousedown', down);
  cv.addEventListener('touchstart', down, { passive: false });
  addEventListener('mousemove', move);
  cv.addEventListener('touchmove', move, { passive: false });
  addEventListener('mouseup', up);
  cv.addEventListener('touchend', up);
  cv.addEventListener('touchcancel', up);
}
/** แผงคลุมสนาม — ยังไม่เริ่มก็เป็นหน้าเริ่มเกม จบแล้วก็เป็นหน้าสรุปผล

    เดิมกดจบเกมแล้วเด้งออกเมนู แต่แมตช์ที่จบยังค้างอยู่ในฐานข้อมูล
    กลับเข้ามาทีไรก็เจอกระดานสรุปเดิมให้กดจบซ้ำอีก
 */
/** ยังมีภาพค้างเล่นอยู่ไหม — ร่วงลงน้ำ กระสุนกำลังบิน ระเบิดยังไม่จาง */
/** ยังไม่ถึงตาเราจริง ๆ หรือเปล่า — ระหว่างนี้ห้ามกดอะไรทั้งนั้น

    ⚠️ ซ้อมกับบอท: เซิร์ฟเวอร์เดินตาบอทจบในคำขอเดียว d.turn จึงกลับมาเป็นเราทันที
       เช็คแค่ wmMe().bot เลยไม่มีวันเป็นจริง ผู้เล่นกดสั่งได้ทั้งที่บอทยังเดินอยู่บนจอ
       ต้องดูว่า "ภาพของใครกำลังเล่นอยู่" ไม่ใช่ดูแค่ตาใครในสถานะ
 */
function wmWaiting() {
  if (!WM_ST || !WM_ST.active || WM_ST.over) return true;
  if (wmMe().bot) return true;
  // 🎪 เล่นหลายคน — ไม่ใช่ตาเราก็กดอะไรไม่ได้ (เซิร์ฟเวอร์ปฏิเสธอยู่แล้ว
  //    แต่ต้องล็อกฝั่งจอด้วย ไม่งั้นตัวเดินไปแล้วค่อยเด้งกลับ)
  if (WM_ST.room && WM_ST.my_turn === false) return true;
  const isBot = fi => !!(WM_ST.fighters[fi] && WM_ST.fighters[fi].bot);
  return !!((WM_ANIM && isBot(WM_ANIM.fi)) || WM_QUEUE.some(q => isBot(q.fi)) ||
            WM_SHOT || WM_BOOMS.length || WM_AFTER.length ||
            wmStepsBusy() || Object.keys(WM_DYING).length);
}
let WM_LOCK_SHOWN = null;
/** เปิด/ปิดการควบคุมตามว่าถึงตาเราหรือยัง — แตะ DOM เฉพาะตอนสถานะเปลี่ยนจริง */
function wmSyncLock() {
  const wait = wmWaiting();
  if (wait === WM_LOCK_SHOWN) return;
  WM_LOCK_SHOWN = wait;
  document.querySelectorAll('[data-wm]').forEach(b => b.disabled = wait);
  const give = document.getElementById('wmGiveUp');
  if (give) give.disabled = wait;
  document.getElementById('v-worms').classList.toggle('wm-wait', wait);
  if (wait) { WM_SKILL = null; WM_AIM = null; wmHoldStop(); }
  if (WM_ST && WM_ST.active) wmPaintSkills();
}
const WM_SPAWN_FALL = 34;   // กี่เฟรมกว่าของจะร่วงจากบนจอถึงพื้น

let WM_SPAWNS = [];
/** ✨ ของกำลังร่วงลงสนาม — ลำแสงจากฟ้า + ตัวของค่อย ๆ ตกลงมา + วงกระเพื่อมตอนถึงพื้น

    จงใจให้ช้า (ราวครึ่งวินาทีกว่าจะถึงพื้น) เพราะกล้องต้องมีเวลาเลื่อนมาถึงก่อน
 */
function wmDrawSpawns(ctx) {
  WM_SPAWNS = WM_SPAWNS.filter(v => v.t < WM_SPAWN_LIFE);
  WM_SPAWNS.forEach(v => {
    const z = WM_CAM.z, k = Math.min(1, v.t / WM_SPAWN_FALL);
    const gx = WM_CAM.sx(v.x), gy = WM_CAM.sy(v.y);
    ctx.globalAlpha = .30 * (1 - v.t / WM_SPAWN_LIFE);   // ลำแสงจากฟ้าลงมาที่จุดนั้น
    ctx.fillStyle = v.color;
    ctx.fillRect(gx - 5 * z / 2, 0, 5 * z, gy);
    ctx.globalAlpha = 1;
    if (k < 1) {                                          // ตัวของกำลังร่วงลงมา
      const fy = gy - (1 - k) * 90 * z;
      ctx.fillStyle = v.color;
      ctx.fillRect(gx - 3 * z / 2, fy - 3 * z, 3 * z, 3 * z);
      ctx.globalAlpha = .5;
      ctx.fillRect(gx - z / 2, fy - 9 * z, z, 5 * z);     // หางไฟตามหลัง
      ctx.globalAlpha = 1;
    } else {                                              // ถึงพื้นแล้ว — วงกระเพื่อม
      const r = (v.t - WM_SPAWN_FALL) / (WM_SPAWN_LIFE - WM_SPAWN_FALL);
      ctx.strokeStyle = v.color; ctx.globalAlpha = 1 - r;
      ctx.lineWidth = Math.max(1.5, z * .7);
      ctx.beginPath();
      ctx.arc(gx, gy - 4 * z, (4 + r * 26) * z, 0, 7);
      ctx.stroke(); ctx.globalAlpha = 1;
    }
    if (v.t < WM_SPAWN_FALL && v.t + WM_DT >= WM_SPAWN_FALL) {
      wmDust(v.x, v.y, 12); SFX.play('boom');       // ของกระแทกพื้น
    }
    v.t += WM_DT;
  });
}
/** 📦 ครบรอบแล้วมีของลงสนาม — พากล้องไปดูทีละชิ้นก่อนเริ่มตาคนแรก

    ระหว่างทัวร์ถือว่า "ยังไม่ถึงตาใคร" กดอะไรไม่ได้ (wmBusyFx นับตัวนี้ด้วย)
 */
function wmStartTour(list) {
  // ⚠️ ของที่เพิ่งลงรอบนี้ต้อง "ยังไม่วาด" จนกว่ากล้องจะไปถึง
  //    เดิม wmApply ใส่ props ทั้งชุดลงแผนที่ทันทีที่คำตอบมาถึง ของเลยโผล่ก่อน
  //    แล้วกล้องค่อยตามไปเล่นเอฟเฟกต์ทับของที่เห็นอยู่แล้ว (เจ้าของเกมทัก)
  WM_TOUR_HIDE = (list || []).slice();
  (list || []).forEach(d => {
    // ① เลื่อนกล้องไปให้ถึงของก่อน (ขั้นนี้จบเมื่อกล้องถึงจริง)
    wmStep(() => wmFocus({ x: d.x, y: d.y }, true), () => !WM_CAM || WM_CAM.arrived());
    // ② ถึงแล้วค่อยปล่อยของลงมา แล้วค้างให้ดูจนครบ
    wmStep(() => {
      const look = { ferry: ['#ff8a6a', '🎈 เรือเหาะมาแล้ว!'],
                     trap:  ['#ff6a6a', '🕳️ ระวังกับดัก!'] }[d.kind]
                 || ['#ffd66b', '🎁 หีบสมบัติมาแล้ว!'];
      SFX.play(d.kind === 'trap' ? 'trap' : 'chest');
      WM_SPAWNS.push({ x: d.x, y: d.y, t: 0, color: look[0] });
      WM_POPS.push({ x: d.x, y: d.y - 30, t: 0, buff: true, text: look[1] });
      wmShowDrop(d);                     // ถึงตรงนี้ของถึงจะโผล่บนแผนที่จริง
      wmHoldAt(d.x, d.y, WM_TOUR_HOLD, null);
    }, wmFxIdle);
  });
  if ((list || []).length) wmStep(() => { WM_TURN_SHOWN = ''; }, () => true);
}
let WM_TOUR_HIDE = [];   // ของที่เพิ่งลงรอบนี้ — ยังไม่ให้วาดจนกว่ากล้องจะไปถึง

let WM_WARPING = -1;     // ตัวที่ถูกดูดเข้าวาร์ปอยู่ (ไม่ต้องวาดจนกว่าจะโผล่)

/** ของบนแผนที่ที่ "มองเห็นได้ตอนนี้" — ตัดของที่รอกล้องไปถึงออก */
function wmPropsNow(all) {
  if (!WM_TOUR_HIDE.length) return all || [];
  return (all || []).filter(p => !WM_TOUR_HIDE.some(
    h => h.kind === p.kind && h.x === p.x && h.y === p.y));
}
/** ปล่อยของชิ้นนี้ให้โผล่บนแผนที่ (เรียกตอนกล้องไปถึงแล้ว) */
function wmShowDrop(d) {
  WM_TOUR_HIDE = WM_TOUR_HIDE.filter(
    h => !(h.kind === d.kind && h.x === d.x && h.y === d.y));
  if (WM && WM_ST) { WM.props = wmPropsNow(WM_ST.props); WM.repaint(); }
}
function wmBusyFx() {
  return !!(WM_ANIM || WM_QUEUE.length || WM_SHOT || WM_BOOMS.length ||
            WM_AFTER.length || wmStepsBusy() || WM_FIRES.length ||
            Object.keys(WM_DYING).length);
}
/** ปิดแผง (หน้าเริ่มเกม/สรุปผล) — ทำได้ทุกเมื่อ ไม่ต้องรอภาพเล่นจบ */
function wmShutOver() {
  const box = document.getElementById('wmOver');
  if (box) box.hidden = true;
  WM_OVER_SHOWN = false;
}
function wmPaintOver() {
  const box = document.getElementById('wmOver'), d = WM_ST;
  if (!box) return;
  const idle = !d || !d.active;
  // ⚠️ เซิร์ฟเวอร์รู้ผลตั้งแต่วินาทีที่สั่ง แต่ผู้เล่นยังไม่เห็นตัวเองร่วงลงน้ำด้วยซ้ำ
  //    ขึ้น "คุณแพ้" ทับตอนนี้คือสปอยล์ตอนจบก่อนภาพจะเล่น — รอให้ภาพเล่นจบก่อน
  // ⚠️ ซ่อนเพราะยังมีภาพเล่นอยู่ = "ยังไม่ได้โชว์" ต้องล้างธงด้วย
  //    เคยพลาด: กดยอมแพ้แล้ว wmApply เรียกตัวนี้ก่อนที่ระเบิดจะถูกต่อคิว
  //    ตอนนั้นยังว่าง แผงเลยโชว์ + ติดธงว่าโชว์แล้ว พอระเบิดมาถึงก็ถูกซ่อน
  //    แล้วธงกันโชว์ซ้ำทำให้ไม่มีวันกลับมาโชว์อีกเลย — ขึ้นแค่ "จบแล้ว" แต่ไม่มีผลแพ้ชนะ
  if (!idle && wmBusyFx()) { wmShutOver(); return; }
  box.hidden = !idle && !d.over;
  if (box.hidden) { WM_OVER_SHOWN = false; return; }
  // ธงนี้แปลว่า "ตอนนี้แผงโชว์อยู่" ตรง ๆ — ลูปวาดใช้เทียบว่าต้องวาดใหม่ไหม
  WM_OVER_SHOWN = true;

  if (idle) {
    box.innerHTML = `
      <div>
        <div style="font-size:40px">🪱</div>
        <h3>สนามรบผลัดเทิร์น</h3>
        <p class="sub">เกาะลอยที่ยิงจนพังได้ · ตัวละครของคุณลงสนามเอง<br>
          เดินเก็บหีบ หลบกับดัก แล้วสอยคู่ต่อสู้ให้ร่วงลงทะเล</p>
        <div class="bars"><button class="again" id="wmStart">🎲 เริ่มเกม</button></div>
      </div>`;
    document.getElementById('wmStart').onclick = () => { SFX.play('click'); wmNewMatch(0); };
    return;
  }

  // ⚠️ อย่าพึ่ง standings อย่างเดียว — ถ้ามันหายไปด้วยเหตุใดก็ตาม
  //    หัวข้อจะกลายเป็น "คุณแพ้" ทั้งที่ชนะ และตารางจะว่างเปล่าไม่มีชื่อใครเลย
  //    ตัวนักสู้มีเลขดาเมจ/จำนวนที่ล้มติดมาอยู่แล้ว ใช้เป็นตัวสำรองได้ตรง ๆ
  const fighters = d.fighters || [];
  const rows = (d.standings && d.standings.length) ? d.standings
    : fighters.map((f, i) => ({ rank: i + 1, name: f.name, bot: f.bot, dead: f.dead,
                                hp: Math.max(0, f.hp), max_hp: f.max_hp,
                                dealt: f.dealt || 0, kills: f.kills || 0 }));
  const me = fighters.find(f => !f.bot) || rows.find(r => !r.bot);
  const top = Math.max(1, ...rows.map(r => r.dealt));
  box.innerHTML = `
    <div>
      <h3>${me && !me.dead ? '🏆 คุณชนะ!' : '☠️ คุณแพ้'}</h3>
      <p class="sub">${esc(d.winner || 'ไม่มีใครรอด')} เป็นฝ่ายรอดสุดท้าย · จบใน ${d.rounds || 0} รอบ</p>
      <table>
        <tr><th>อันดับ</th><th>ผู้เล่น</th><th>ความเสียหายที่สร้างได้</th><th>ล้ม</th><th>เลือด</th></tr>
        ${rows.map(r => `
          <tr class="${r.rank === 1 ? 'win' : ''}${r.dead ? ' out' : ''}">
            <td>${r.rank === 1 ? '🥇' : r.rank === 2 ? '🥈' : r.rank === 3 ? '🥉' : '#' + r.rank}</td>
            <td>${esc(r.name)}${r.bot ? '' : ' <span class="you">(คุณ)</span>'}</td>
            <td class="num">${r.dealt}
              <i class="dmg" style="width:${Math.round(r.dealt / top * 100)}%"></i></td>
            <td class="num">${r.kills}</td>
            <td class="num">${r.dead ? '☠️ ตกรอบ' : r.hp + '/' + r.max_hp}</td>
          </tr>`).join('')}
      </table>
      <div class="bars">
        <button class="again" id="wmAgain">🎲 เล่นอีกรอบ</button>
        <button class="quit" id="wmQuit">✖️ จบเกม</button>
      </div>
    </div>`;
  document.getElementById('wmAgain').onclick = () => { SFX.play('click'); wmNewMatch(0); };
  document.getElementById('wmQuit').onclick = async () => {
    SFX.play('click');
    try { wmApply(await api('POST', '/api/web/pvp/worms/match', { action: 'quit' })); }
    catch (e) { toast(e.message, true); }
    document.querySelector('#v-worms [data-back]')?.click();
  };
}
function wmPaintSkills() {
  const box = document.getElementById('wmSkills');
  const d = WM_ST;
  if (!box || !d || !d.active) return;
  const locked = wmWaiting();
  box.innerHTML = (d.skills || []).map(s => `
    <button data-skill="${esc(s.key)}" ${locked || s.ready_in ? 'disabled' : ''}
            title="${esc(s.desc)}"
            class="${WM_SKILL === s.key ? 'on' : ''}">
      ${s.ready_in ? `<span class="cd">⏳${s.ready_in}</span>` : ''}
      ${esc(s.name)}</button>`).join('');
  box.querySelectorAll('[data-skill]').forEach(b =>
    b.onclick = () => wmPickSkill(b.dataset.skill));
  wmPaintItems(locked);
  wmShowAim();
}
/** 🏺 อาร์ติแฟกต์ที่เก็บได้จากหีบ — ใช้ครั้งเดียวหมด */
function wmPaintItems(locked) {
  const box = document.getElementById('wmItems');
  if (!box) return;
  const items = WM_ST.items || [];
  box.innerHTML = !items.length
    ? '<div class="wm-empty">🎁 ยังไม่มีไอเทม — เดินทับหีบสมบัติในสนามเพื่อเก็บ</div>'
    : items.map(i => `
      <button data-skill="${esc(i.key)}" ${locked ? 'disabled' : ''}
              title="${esc(i.desc)}"
              class="wm-item${WM_SKILL === i.key ? ' on' : ''}">
        <span class="cd">×${i.count}</span>
        ${esc(i.name)}</button>`).join('');
  box.querySelectorAll('[data-skill]').forEach(b =>
    b.onclick = () => wmPickSkill(b.dataset.skill));
}
/** เลือกสกิล — แบบที่ต้องเล็งจะโชว์แถบมุม/แรงก่อน ที่เหลือใช้ทันที */
function wmPickSkill(key) {
  const s = (WM_ST.skills || []).concat(WM_ST.items || []).find(x => x.key === key);
  if (!s) return;
  SFX.play('click');
  if (s.kind === 'self') { WM_SKILL = null; wmAttack(key, 45, 70, wmMe().face); return; }
  WM_SKILL = WM_SKILL === key ? null : key;    // ที่เหลือรอกดค้างบนแผนที่
  wmPaintSkills();
}
function wmShowAim() {
  const el = document.getElementById('wmAim');
  if (!el) return;
  el.hidden = !WM_SKILL;
  if (!WM_SKILL) return;
  const sp = wmSpec(WM_SKILL) || {};
  el.textContent = sp.kind === 'melee'
    ? '🎯 ' + sp.name + ' — แตะค้างบนแผนที่ ฝั่งที่จะฟาด แล้วปล่อย'
    : '🎯 ' + sp.name + ' — กดค้างบนแผนที่ ฝั่งที่จะยิง (ค้างนาน = ไกลขึ้น) '
      + 'เลื่อนขึ้นลงปรับองศา ปล่อยเพื่อยิง';
}
async function wmAttack(key, ang, pow, dir) {
  if (wmBusy || wmWaiting() || performance.now() < WM_BACKOFF) return;
  wmBusy = true;
  try {
    const d = await api('POST', '/api/web/pvp/worms/match', {
      action: 'attack', skill: key, dir: dir, angle: ang, power: pow,
    });
    WM_SKILL = null;
    wmPlayAttack(d);
  } catch (e) { if (!wmBackoff(e)) toast(e.message, true); }
  finally { wmBusy = false; }
}
/** เล่นภาพผลการโจมตี แล้วต่อด้วยตาบอท (ผลทั้งหมดเซิร์ฟเวอร์ตัดสินไปแล้ว)

    ⚠️ ลำดับนี้ผิดไม่ได้: wmApply ล้างคิวภาพทิ้งทุกครั้ง (wmStepsClear)
       เดิมเรียก wmShowHit ก่อน ภาพท่าประชิดที่เพิ่งต่อคิวไว้เลยถูกล้างทิ้งทั้งชุด
       เห็นแต่ตัวคู่ต่อสู้วาปไปจุดใหม่ ไม่มีทั้งการกระเด็นและตัวเลขดาเมจ
 */
function wmPlayAttack(d) {
  WM_DEATHS = d.deaths || [];
  const old = wmSnapshot();
  wmApply(d);
  wmHideOutcome(old);
  wmShowHit(d.attack || {});
  // ตาบอทต่อ "หลัง" ภาพหมัดเราจบจริง — ต้องเห็นด้วยว่าบอททำอะไรเรา
  // ไม่งั้นเลือดลดแล้วนึกว่าตีตัวเอง (ต่อคิวตอนขั้นนี้เสร็จ จะได้อยู่หลังคิวสรุปผลทีละคน)
  wmStep(() => {}, wmFxIdle, () => wmQueueBot(d));
}
let WM_HIDDEN = null;   // ค่าจริงหลังหมัดนี้ ที่ยังไม่ให้เห็นจนกว่าภาพจะเล่นถึง

/** 📸 จำเลือด/ตำแหน่ง/ความเป็นตาย ก่อนรับสถานะใหม่มาทับ */
function wmSnapshot() {
  const o = {};
  (WM_ST ? WM_ST.fighters : []).forEach(f => {
    o[f.name] = { x: f.x, y: f.y, hp: f.hp, dead: f.dead };
  });
  return o;
}
/** ⏳ ห้ามเฉลยผลก่อนภาพจะเล่นถึง (เจ้าของเกมสั่ง: "ห้ามสรุปผลลัพธ์ก่อน เด็ดขาด")

    เซิร์ฟเวอร์ตอบผลทั้งก้อนมาพร้อมกัน — เลือดลด ตัวกระเด็นไปจุดใหม่ ตายแล้ว
    เอามาแสดงทันทีคือเห็นเลือดตัวเองลดตั้งแต่กระสุนยังไม่ทันบินถึง
    ("ยิงไม่โดนฉันแต่ขึ้นดาเมจที่ฉัน") จึงยืมค่าเก่ามาแสดงไว้ก่อน
    แล้วปล่อยของจริงทีละคนตอนกล้องไปจับเขา — ที่เหลือปล่อยตอนภาพจบหมด
 */
function wmHideOutcome(old) {
  if (!WM_ST) return;
  WM_HIDDEN = {};
  WM_ST.fighters.forEach(f => {
    const o = old[f.name];
    if (!o) return;
    WM_HIDDEN[f.name] = { x: f.x, y: f.y, hp: f.hp, dead: f.dead };
    f.x = o.x; f.y = o.y; f.hp = o.hp; f.dead = o.dead;
  });
  wmPaintHud();
}
/** เฉลยของคนเดียว — ใส่เลือด "หลังหมัดนี้" ที่เซิร์ฟเวอร์คิดมาให้ (ไม่ใช่ค่าสุดท้าย)

    ค่าสุดท้ายรวมหมัดที่ยังไม่ได้เล่นภาพด้วย (บอทยิงสวนมาในคำตอบเดียวกัน)
    ใส่ทีเดียวคือเลือดหายมากกว่าตัวเลขที่เพิ่งเด้งขึ้นมา
    ⚠️ ห้ามคำนวณเองเด็ดขาด — ทุกตัวเลขต้องมาจากเซิร์ฟเวอร์ (กติกาเหล็กของหมวดนี้)
 */
function wmRevealOne(name, hp) {
  const h = WM_HIDDEN && WM_HIDDEN[name];
  const f = WM_ST && WM_ST.fighters.find(x => x.name === name);
  if (!h || !f || hp === undefined) return;
  f.hp = hp;
  if (hp <= 0 && h.dead) f.dead = true;
  wmPaintHud();
}
/** เฉลยที่เหลือทั้งหมด — ภาพเล่นจบแล้ว ค่าบนจอต้องตรงกับเซิร์ฟเวอร์เป๊ะ */
function wmRevealAll() {
  if (WM_ST) {
    WM_ST.fighters.forEach(f => {
      const h = WM_HIDDEN[f.name];
      if (h) { f.x = h.x; f.y = h.y; f.hp = h.hp; f.dead = h.dead; }
    });
  }
  WM_HIDDEN = null;
  wmPaintHud();
}
/** เล่นภาพการโจมตีของบอททีละนัด — นัดถัดไปรอให้นัดก่อนเล่นจบก่อน */
function wmPlayBotShots(shots) {
  (shots || []).forEach(a => wmStep(() => wmShowHit(a, true), wmFxIdle));
}
/** เล่นเอฟเฟกต์ของการโจมตีหนึ่งครั้ง — ใช้ร่วมกันทั้งของเราและของบอท

    ⚠️ ลำดับสำคัญ: สกิลที่มีวิถีต้อง "บินให้เห็นก่อน แล้วค่อยระเบิด"
       เดิมเจาะหลุมทันทีที่ได้ผลกลับมา พื้นเลยหายไปก่อนกระสุนจะบินถึงด้วยซ้ำ
 */
function wmShowHit(a, byBot) {
  if (!a || !a.kind) return;
  SFX.play(a.kind === 'self' ? 'use' : a.kind === 'lob' ? 'skill' : 'hit');
  const hits = (a.hits || []).concat((a.blast || {}).hits || []);

  if (a.path && a.path.length) {
    // 🎯 มีวิถี — วาดเส้นประตามทางที่บินไป พอถึงปลายทางค่อยระเบิด
    //    🎯 หน้าไม้ยิงสามแฉก: ลูกแรกเป็นตัวนำกล้อง ที่เหลือบินคู่ไปด้วย
    WM_SHOT = { path: a.path, i: 0, blast: a.blast || null, hits: hits, byBot: byBot,
                name: a.name, atk: a,
                extra: (a.volley || []).slice(1).map(v => ({ path: v.path, i: 0,
                                                             blast: v.blast || null })) };
    return;
  }

  if (a.kind === 'self') {          // บัฟ/ของป้องกัน — ไม่มีวงฟัน ไม่มีหลุม ไม่มีตัวเลขดาเมจ
    wmBuffFx(a);
    if (byBot) toast(`🤖 บอทใช้ ${a.name}`);
    return;
  }
  if (a.kind === 'melee') wmSwing(a);
  if (a.blast) wmLand(a.blast);
  wmBreakProps((a.blast || {}).broke);      // ของบนแผนที่ที่โดนพังไปด้วย
  const boom = WM_DEATHS; WM_DEATHS = [];
  wmPlayVictims(a, () => wmPlayDeaths(boom, () => WM_AFTER.push(wmCallDeaths)));
  if (byBot) toast(`🤖 บอทใช้ ${a.name}`, hits.some(h => h.name === 'คุณ' && !h.dodged));
}
/** 💥 กระสุนถึงเป้า — เจาะพื้นจริง ระเบิด และสะเก็ดกระเด็น */
function wmLand(b) {
  if (!b) return;
  WM.carve(b.x, b.y, b.crater || 6);
  wmBoom(b);
  SFX.play('boom');                    // ระเบิดมีเสียงของตัวเอง ไม่ใช่ยืมเสียงกับดักมาใช้
  const n = Math.min(26, 6 + (b.crater || 6));
  for (let i = 0; i < n; i++) {
    const ang = Math.PI * (1 + i / n) + (i % 3) * 0.11;   // กระจายขึ้นด้านบนเป็นหลัก
    WM_BITS.push({ x: b.x, y: b.y, vx: Math.cos(ang) * (0.7 + (i % 5) * .45),
                   vy: Math.sin(ang) * (0.7 + (i % 4) * .5), t: 0 });
  }
}
// ⏱️ ทุกอย่างในสนามเดินตาม "เวลาจริง" ไม่ใช่ "จำนวนเฟรมที่จอวาด"
//
//    เดิมทุกตัวนับบวกทีละ 1 ต่อการวาดหนึ่งครั้ง จอ 144 Hz จึงเดินเร็วกว่าจอ 60 Hz
//    2.4 เท่า — กระสุนที่อุตส่าห์ปรับให้ช้ากลับมาเร็ว ค้างดูของ 3 วิเหลือ 1.2 วิ
//    ตัวกันค้าง (WM_STEP_MAX) ก็ตัดเร็วกว่าที่ตั้งไว้
//    LittleJS แก้ด้วยตัวสะสมเวลาแบบคงที่ (engine.js:222) เรายืมแนวคิดเดียวกัน
//    แต่ทำเป็น "ตัวคูณ" แทน จะได้ไม่ต้องแยกอัปเดตกับวาดออกจากกันทั้งไฟล์
//
//    WM_DT = เฟรมมาตรฐาน (1/60 วิ) ที่ผ่านไปนับจากการวาดครั้งก่อน
//    จอ 60 Hz ได้ 1 · จอ 144 Hz ได้ ~0.42 · จอ 30 Hz ได้ 2
let WM_DT = 1, WM_LAST_MS = 0;
const WM_FPS = 60;
/** อัปเดตนาฬิกากลางหนึ่งครั้งต่อการวาดหนึ่งครั้ง — เรียกที่หัวลูปเท่านั้น */
function wmClock(now) {
  const ms = now || 0;
  const gap = WM_LAST_MS ? ms - WM_LAST_MS : 1000 / WM_FPS;
  WM_LAST_MS = ms;
  // เพดานบน: สลับแท็บกลับมาแล้วเวลาโดดไปหลายวินาที ห้ามให้ภาพกระโดดตามทีเดียว
  // เพดานล่าง: กันหารศูนย์ตอนเบราว์เซอร์ยิงสองเฟรมในมิลลิวินาทีเดียว
  WM_DT = Math.max(0.2, Math.min(3, gap * WM_FPS / 1000));
}
const WM_SHOT_STEP = 0.34;   // กระสุนเดินกี่จุดต่อเฟรมมาตรฐาน (น้อย = ช้าและลื่นกว่า)

let WM_SHOT = null, WM_BOOMS = [], WM_POPS = [], WM_SWINGS = [];
let WM_TRAIL = null, WM_BITS = [];    // เส้นประของวิถีที่ผ่านมาแล้ว · สะเก็ดจากหลุม

let WM_FIRES = [];                    // 🔥 กองไฟที่ยังลุกอยู่

const WM_FLASH = {};       // ชื่อ -> เฟรมที่เหลือของการกระพริบตอนโดนตี

/** เด้งตัวเลขดาเมจตรงตัวคนที่โดน + ทำให้ตัวกระพริบ */
function wmPop(hits, kind) {
  (hits || []).forEach(h => {
    if (h.x === undefined) return;
    WM_POPS.push({ x: h.x, y: h.y - 26, t: 0,
                   text: h.dodged ? 'หลบ!' : '-' + h.damage,
                   miss: !!h.dodged });
    if (!h.dodged) WM_FLASH[h.name] = 10;
  });
}
/** ✨ เอฟเฟกต์บัฟ — วงแหวนสีประจำบัฟขยายรอบตัว + ชื่อบัฟลอยขึ้น

    จงใจแยกจากเอฟเฟกต์โจมตีให้ขาด: ไม่มีสะเก็ด ไม่มีหลุม ไม่มีเลขดาเมจสีแดง
    ไม่งั้นกดโล่แล้วเห็นภาพเหมือนตีคน นึกว่าโจมตีตัวเอง
 */
const WM_BUFF_LOOK = {
  heal:    ['#7ef2a0', '✨ ฟื้นเลือด'],
  evade:   ['#9fd8ff', '💨 หลบหลีก'],
  aura:    ['#ffe08a', '🛡️ ออร่าคุ้มกาย'],
  feather: ['#dff2ff', '🥾 ตกไม่เจ็บ'],
  bark:    ['#d0a878', '🧥 กันหนึ่งครั้ง'],
  reflect: ['#a8e8ff', '🧊 สะท้อนกลับ'],
  slow:    ['#9fd8ff', '❄️ ช้าลง'],
  emp:     ['#c9a6ff', '⚡ EMP'],
};
let WM_AURAS = [];
function wmBuffFx(a) {
  if (!a.from) return;
  const key = a.buff || (a.heal ? 'heal' : '');
  const [color, label] = WM_BUFF_LOOK[key] || ['#ffd66b', a.name];
  WM_AURAS.push({ x: a.from[0], y: a.from[1], color: color, t: 0 });
  WM_POPS.push({ x: a.from[0], y: a.from[1] - 30, t: 0, buff: true,
                 text: a.heal ? `${label} +${a.heal}` : label });
}
// ══════════════════════════════════════════════════════════════════
// 🎬 ตัวคุมลำดับ — ทำทีละขั้นจนจบ แล้วเว้นจังหวะ ก่อนเริ่มขั้นถัดไป
//
// เกมนี้เป็นแบบผลัดเทิร์น ทุกอย่างต้องเกิดทีละอย่างให้เห็นชัด ห้ามซ้อนกัน
// เดิมมีหลายระบบเดินคู่ขนาน (ท่อนเดิน · กระสุน · ทัวร์ของ · ระเบิดร่าง)
// แต่ละอันต้องคอยรู้จักอันอื่นเอง พลาดที่เดียวก็แย่งกล้องกันทันที
// ตอนนี้ทุกอย่างเข้าคิวที่เดียว: เริ่ม → รอจนเสร็จจริง → เว้นจังหวะ → ขั้นถัดไป
// ══════════════════════════════════════════════════════════════════
const WM_GAP_BEFORE = 30;    // เว้นก่อนเริ่มขั้นถัดไป (0.5 วินาที)

const WM_GAP_AFTER = 60;     // เว้นหลังขั้นหนึ่งเสร็จ (1 วินาที)

let WM_STEPS = [];           // ขั้นที่รอคิวอยู่

let WM_STEP = null;          // ขั้นที่กำลังทำ

let WM_WAIT = 0;             // เฟรมที่ต้องรออยู่ (ช่วงเว้นจังหวะ)

const WM_STEP_MAX = 900;     // ขั้นหนึ่งใช้เวลาได้ไม่เกิน 15 วินาที (กันค้างตาย)

/** ต่อคิวหนึ่งขั้น — run() เริ่มทำ · done() คืน true เมื่อขั้นนั้นเสร็จจริง */
function wmStep(run, done, then) {
  WM_STEPS.push({ run: run, done: done || (() => true), then: then || null, on: false });
}
/** มีขั้นค้างอยู่ไหม (รวมช่วงเว้นจังหวะ) — ห้ามให้ใครแย่งทำงานระหว่างนี้ */
function wmStepsBusy() { return !!(WM_STEP || WM_STEPS.length || WM_WAIT > 0); }
/** ล้างคิวทั้งหมด — ใช้ตอนสถานะถูกแทนทั้งก้อน (เปิดสนามใหม่) */
function wmStepsClear() { WM_STEPS = []; WM_STEP = null; WM_WAIT = 0; }
/** เดินคิวทีละเฟรม — หัวใจของ "ทำทีละอย่าง ไม่แย่งกัน" */
function wmRunSteps() {
  if (WM_WAIT > 0) { WM_WAIT -= WM_DT; return; }
  if (!WM_STEP) {
    if (!WM_STEPS.length) return;
    WM_STEP = WM_STEPS.shift();
    WM_WAIT = WM_GAP_BEFORE;          // ① เว้นจังหวะก่อนเริ่ม
    return;
  }
  if (!WM_STEP.on) { WM_STEP.on = true; WM_STEP.age = 0; WM_STEP.run(); return; }
  // ⏱️ กันค้าง: done() ไม่ยอมเป็นจริงภายในเวลาที่กำหนด ให้ข้ามไป ยอมข้ามดีกว่าค้างตาย
  //    เคยเจอ — ขั้นที่รอ 'กล้องเลื่อนไปถึง' ค้างเพราะมีคนอื่นแย่งตั้งเป้ากล้องทุกเฟรม
  if ((WM_STEP.age += WM_DT) < WM_STEP_MAX && !WM_STEP.done()) return;
  const fin = WM_STEP.then;
  WM_STEP = null;
  if (fin) fin();                     // ต่อคิวของถัดไป "หลัง" คิวที่ขั้นนี้เพิ่งแตกออกมา
  WM_WAIT = WM_GAP_AFTER;             // ④ เว้นจังหวะหลังเสร็จ
}
/** ภาพที่ "ขั้นหนึ่ง ๆ" ใช้อยู่เล่นจบหรือยัง — ใช้เป็น done() ของหลายขั้น */
function wmFxIdle() {
  return !WM_ANIM && !WM_QUEUE.length && !WM_SHOT && !WM_BOOMS.length &&
         !WM_FIRES.length && !Object.keys(WM_DYING).length;
}
/** ต่อคิวภาพหนึ่งท่อน พร้อมงานที่ต้องทำตอนท่อนนั้นจบ */
function wmChunk(fi, path, onEnd) {
  WM_QUEUE.push({ fi: fi, path: path, i: 0, onEnd: onEnd });
  if (!WM_ANIM) WM_ANIM = WM_QUEUE.shift();
}
/** ค้างกล้องไว้ที่ "จุดหนึ่ง" สักพัก — ไม่ผูกกับตัวใคร (ใช้ตอนดูร่างระเบิด) */
function wmHoldAt(x, y, frames, onEnd) {
  wmChunk(-1, Array.from({ length: frames }, () => [x, y]), onEnd);
}
const WM_DEATH_HOLD = 66;   // ค้างดูร่างระเบิดกี่เฟรมก่อนไล่ดูคนที่โดนลูกหลง

/** 💀 ร่างคนตายระเบิด — ทีละร่าง แล้วค่อยไล่ดูคนที่โดนลูกหลงของร่างนั้น

    เจ้าของเกมสั่ง: ต้องรอเอฟเฟกต์จบก่อน ถึงจะสรุปว่าใครโดนอะไรและใครแพ้ชนะ
 */
function wmPlayDeaths(list, done) {
  const all = (list || []).filter(d => d && d.blast);
  if (!all.length) { if (done) done(); return false; }
  all.forEach(d => {
    wmStep(() => {
      wmFocus({ x: d.x, y: d.y }, true);
      SFX.play('lose');
      wmLand(d.blast);                     // เจาะพื้นจริง + ลูกไฟ + สะเก็ด
      // ⚠️ ต่อคิวคนที่โดนลูกหลง "ตรงนี้" ไม่ใช่ตอนต่อคิวขั้นนี้
      //    ข้างใน wmPlayVictims ยิงการกระเด็นทันทีโดยไม่รอคิว (ตั้งใจ — โดนปุ๊บปลิวปั๊บ)
      //    เรียกตอนต่อคิวจึงกลายเป็น "คนปลิวก่อนลูกไฟจะขึ้น" (เจ้าของเกมทัก)
      wmPlayVictims(d.blast, null);
      wmHoldAt(d.x, d.y, WM_DEATH_HOLD, null);
    }, wmFxIdle);
  });
  if (done) wmStep(done, () => true);
  return true;
}
/** ค้างกล้องไว้ที่คนคนนี้สักพัก — ให้ทันอ่านเลขดาเมจ/ดูภาพตายก่อนไปคนถัดไป */
function wmHoldOn(fi, frames, onEnd) {
  const f = WM_ST.fighters[fi];
  if (!f) { if (onEnd) onEnd(); return; }
  wmChunk(fi, Array.from({ length: frames }, () => [f.x, f.y]), onEnd);
}
/** 🎬 เล่นผลของหมัดหนึ่ง "ทีละคน" ตามที่เจ้าของเกมสั่ง

    กระสุนกระทบ → กล้องไปที่คนที่โดนคนแรก → เห็นเขากระเด็นจนหยุด
    → ขึ้นเลขดาเมจของเขา → ตายก็เล่นภาพตาย → แล้วค่อยไปคนถัดไปจนครบ
    คืน true ถ้ามีคิวให้เล่น (ผู้เรียกจะได้รู้ว่าต้องรอ)
 */
function wmPlayVictims(a, done) {
  const hits = (a.hits || []).concat((a.blast || {}).hits || []);
  const knocks = (a.knocks || []).concat((a.blast || {}).knocks || []);

  // ยุบหลายหมัดของคนเดียวกันให้เหลือรายการเดียว (ดาบคู่แฝดฟันรัวสี่ครั้ง)
  const order = [];
  hits.forEach(h => {
    let v = order.find(x => x.name === h.name);
    if (!v) order.push(v = { name: h.name, dmg: 0, dodged: true });
    v.dmg += h.damage || 0;
    if (h.hp !== undefined) v.hp = h.hp;   // เลือดที่เหลือหลังหมัดนี้ — เซิร์ฟเวอร์คิดมาให้แล้ว
    v.dodged = v.dodged && !!h.dodged;
  });
  if (!order.length) { if (done) done(); return false; }

  // ① 💥 โดนปุ๊บกระเด็นปั๊บ — ทุกคนที่โดนหมัดนี้ปลิวทันที ไม่ต้องรอคิว
  //    (เจ้าของเกมสั่ง: กระเด็นเลย แต่อย่าเพิ่งคิดค่าเสียหาย)
  const flying = wmPlayKnocks(knocks);
  // ② รอให้ทุกคนปลิวจนตกถึงพื้นก่อน แล้วค่อยเริ่มสรุปผล
  if (flying) wmStep(() => {}, wmFxIdle);
  // ③ 🎬 ค่อยไล่คิดค่าเสียหายทีละคน กล้องจับทีละคน เว้นจังหวะระหว่างคน
  order.forEach(v => wmStep(() => wmSettleVictim(v), wmFxIdle));
  if (done) wmStep(done, () => true);
  return true;
}
/** 💥 ปล่อยให้ทุกคนที่โดนหมัดนี้กระเด็นพร้อมกันทันที — ยังไม่คิดดาเมจ */
function wmPlayKnocks(knocks) {
  let any = false;
  (knocks || []).forEach(k => {
    if (!k || !k.path || !k.path.length) return;
    const fi = WM_ST.fighters.findIndex(f => f.name === k.name);
    if (fi < 0) return;
    wmChunk(fi, k.path, null);
    any = true;
  });
  return any;
}
/** สรุปผลของคนคนเดียว — เลขดาเมจ → ตายก็เล่นภาพตาย (กระเด็นจบไปแล้วก่อนหน้านี้) */
function wmSettleVictim(v) {
  const fi = WM_ST.fighters.findIndex(f => f.name === v.name);
  if (fi < 0) return;

  const f = WM_ST.fighters[fi];
  wmRevealOne(v.name, v.hp);              // ถึงคิวเขาแล้วค่อยใส่เลือดที่เซิร์ฟเวอร์บอก
  wmFocus(f, true);                       // จอจับอยู่ที่คนนี้ตอนสรุปผลของเขา
  WM_POPS.push({ x: f.x, y: f.y - 26, t: 0, miss: v.dodged,
                 text: v.dodged ? 'หลบ!' : '-' + v.dmg });
  if (!v.dodged) { WM_FLASH[f.name] = 10; SFX.play('foehit'); }
  if (f.dead && !WM_DEAD_SEEN[f.name]) {  // ตายค่อยเล่นภาพตายตรงนี้
    WM_DEAD_SEEN[f.name] = true;
    wmDie(fi, f);
    wmHoldOn(fi, 78, null);
  } else {
    wmHoldOn(fi, 46, null);
  }
}
/** ประกาศคนที่เพิ่งตาย — เรียกหลังทุกคนหยุดกระเด็นแล้วเท่านั้น */
function wmCallDeaths() {
  WM_ST.fighters.forEach((f, i) => {
    if (f.dead && !WM_DEAD_SEEN[f.name]) {
      WM_DEAD_SEEN[f.name] = true;
      wmDie(i, f);
    }
  });
}
const WM_DEAD_SEEN = {};   // ประกาศตายไปแล้วหรือยัง (กันเล่นภาพตายซ้ำทุกเฟรม)

/** 🎁 เปิดหีบเป็นจังหวะ — ฝาเด้ง → ของลอยขึ้น → ค่อยขึ้นข้อความว่าได้อะไร

    เดิมเอฟเฟกต์กับข้อความเกิดพร้อมกันหมดในเฟรมเดียว เห็นไม่ทันว่าอะไรเกิดก่อน
 */
function wmOpenChest(o) {
  wmStep(() => {
    SFX.play('chest');
    wmChestFx(o.x, o.y);
    wmFocus({ x: o.x, y: o.y });
    wmHoldAt(o.x, o.y, 26, null);        // ค้างให้ดูฝาเด้งก่อน
  }, wmFxIdle);
  wmStep(() => {
    WM_POPS.push({ x: o.x, y: o.y - 30, t: 0, buff: true,
                   text: '🎁 ' + (o.name || 'ของ') });
    toast('🎁 เปิดหีบได้ ' + (o.name || 'ของ') + '!');
  }, () => true);
}
/** 🎈 ขึ้นเรือเหาะเป็นจังหวะ — ถูกดูดหายที่จุดเดิม → กล้องไปจุดใหม่ → โผล่ออกมา

    เดิมวาร์ปทันทีในเฟรมเดียว ตัวโผล่อีกเกาะพร้อมเอฟเฟกต์ทั้งสองข้าง
    ผู้เล่นไม่ทันเห็นว่าตัวเองหายไปจากตรงไหน (เจ้าของเกมขอให้มีอนิเมชั่น)
 */
function wmRideFerry(fi, ferry) {
  wmStep(() => {                          // ① ถูกดูดหายที่จุดเดิม
    SFX.play('ferry');
    wmFocus({ x: ferry.from[0], y: ferry.from[1] }, true);
    wmWarpFx(ferry.from[0], ferry.from[1], false);
    WM_WARPING = fi;                      // ระหว่างนี้ไม่ต้องวาดตัว — ถูกดูดไปแล้ว
    wmHoldAt(ferry.from[0], ferry.from[1], 30, null);
  }, wmFxIdle);
  wmStep(() => {                          // ② กล้องเลื่อนไปจุดที่จะโผล่
    wmFocus({ x: ferry.x, y: ferry.y }, true);
  }, () => !WM_CAM || WM_CAM.arrived());
  wmStep(() => {                          // ③ โผล่ออกมา
    const f = WM_ST.fighters[fi];
    if (f) { f.x = ferry.x; f.y = ferry.y; }
    WM_WARPING = -1;
    wmWarpFx(ferry.x, ferry.y, true);
    toast('🎈 ขึ้นเรือเหาะข้ามไปอีกเกาะ!');
    wmHoldAt(ferry.x, ferry.y, 26, null);
  }, wmFxIdle);
}
const WM_FIRE_LIFE = 96;   // เปลวไฟอยู่กี่เฟรมก่อนจางหมด

/** 🔥 ไฟลุกเป็นวง — ใช้ตอนเรือเหาะ/หีบโดนยิงพัง
    (ห้ามตั้งชื่อชนกับปุ่มยิงเก่าที่ถอดไปแล้ว — มีเทสเฝ้าไว้ว่าห้ามกลับมา) */
function wmFlames(x, y, r) {
  WM_FIRES.push({ x: x, y: y, r: r, t: 0 });
  for (let i = 0; i < 14; i++)            // สะเก็ดไฟกระเด็นตอนติดไฟ
    WM_BITS.push({ x: x + ((i % 7) - 3) * 2, y: y - 4, t: 0, fire: true,
                   vx: ((i % 5) - 2) * .8, vy: -1.2 - (i % 4) * .5 });
  SFX.play('boom');
}
/** 💥 ของบนแผนที่โดนยิงพัง — เล่นทีละชิ้นเป็นขั้น ๆ ไม่ให้ซ้อนกันจนดูไม่ออก */
function wmBreakProps(list) {
  (list || []).forEach(b => wmStep(() => {
    wmFocus({ x: b.x, y: b.y }, true);
    WM_POPS.push({ x: b.x, y: b.y - 30, t: 0,
                   text: { ferry: '🎈 เรือเหาะพัง!', chest: '🎁 หีบไหม้!',
                           trap: '🕳️ กับดักลั่น!' }[b.kind] || '💥 พัง!' });
    if (b.blast) wmLand(b.blast);         // ระเบิดเจาะพื้นจริง
    if (b.fire) wmFlames(b.x, b.y - 6, b.fire);
    wmPlayVictims(b.burn || b.blast || {}, null);
    wmHoldAt(b.x, b.y, 34, null);
  }, wmFxIdle));
}
/** 🌀 วาร์ป — วงแหวนหดเข้า/ขยายออก + ประกายพุ่งเข้าหาจุดกึ่งกลาง

    up = true คือ "โผล่ออกมา" · false คือ "ถูกดูดหายไป"
 */
function wmWarpFx(x, y, up) {
  const mid = y - 11;
  for (let i = 0; i < 3; i++)
    WM_BOOMS.push({ x: x, y: mid, r: 5 + i * 3, t: up ? i * 3 : 20 - i * 3 });
  for (let i = 0; i < 14; i++) {
    const a = (i / 14) * 6.283, far = up ? 1 : -1;
    WM_BITS.push({ x: x + Math.cos(a) * 14, y: mid + Math.sin(a) * 10, t: 0, dust: true,
                   vx: -Math.cos(a) * far * 1.1, vy: -Math.sin(a) * far * .8 });
  }
  wmDust(x, y, 8);
  WM_POPS.push({ x: x, y: y - 32, t: 0, buff: true, text: up ? '🌀 โผล่!' : '🌀 วาร์ป' });
}
/** 🎁 ฝาหีบเปิด — ไม้กระเด็น แสงพุ่งขึ้น แล้วของลอยออกมา */
function wmChestFx(x, y) {
  for (let i = 0; i < 8; i++)            // เศษไม้ฝาหีบกระเด็น
    WM_BITS.push({ x: x, y: y - 6, t: 0,
                   vx: ((i % 5) - 2) * .7, vy: -1.4 - (i % 3) * .4 });
  for (let i = 0; i < 10; i++)           // ประกายทองพุ่งขึ้น
    WM_BITS.push({ x: x + ((i % 5) - 2) * 2, y: y - 8, t: 0, drop: true,
                   vx: ((i % 3) - 1) * .35, vy: -2.1 - (i % 4) * .35 });
  WM_BOOMS.push({ x: x, y: y - 8, r: 7, t: 12 });
  wmDust(x, y, 10);
}
/** 🕳️ เหยียบกับดัก — ซี่เหล็กงับ ฝุ่นฟุ้ง แล้วเด้งป้ายเตือน */
function wmTrapFx(x, y) {
  wmDust(x, y, 14);
  for (let i = 0; i < 10; i++)
    WM_BITS.push({ x: x, y: y - 2, t: 0,
                   vx: ((i % 5) - 2) * .8, vy: -0.8 - (i % 3) * .5 });
  WM_BOOMS.push({ x: x, y: y - 4, r: 9, t: 0 });
  WM_POPS.push({ x: x, y: y - 30, t: 0, text: '🕳️ กับดัก!' });
}
/** 🧱 กระโดดหัวชนกำแพง — ดาวหมุนกับเศษปูนตรงจุดที่ชน แล้วร่วงลง */
function wmBump(x, y) {
  SFX.play('hit');
  wmDust(x, y, 6);
  for (let i = 0; i < 8; i++)
    WM_BITS.push({ x: x, y: y, t: 0,
                   vx: ((i % 5) - 2) * .7, vy: -0.4 - (i % 3) * .35 });
  WM_POPS.push({ x: x, y: y - 10, t: 0, buff: true, text: '💫' });
}
/** ☠️ ภาพตาย — ร่างสั่นแล้วแตกเป็นสะเก็ด ค่อย ๆ จางไป

    เรียกหลังการกระเด็นหยุดแล้วเท่านั้น ไม่งั้นประกาศตายตั้งแต่ยังปลิวอยู่กลางอากาศ
 */
function wmDie(i, f) {
  WM_DYING[i] = 60;
  wmDust(f.x, f.y, 10);
  for (let k = 0; k < 14; k++)
    WM_BITS.push({ x: f.x, y: f.y - 10, t: 0,
                   vx: ((k % 7) - 3) * .6, vy: -1 - (k % 4) * .4 });
  WM_POPS.push({ x: f.x, y: f.y - 34, t: 0, text: '☠️ ' + f.name });
  SFX.play('lose');
}
/** 💦 น้ำกระจายตอนร่างแตะผิวน้ำ — พุ่งขึ้นสูงกว่าฝุ่น แล้วค่อย ๆ ตกกลับ */
function wmSplash(x, y) {
  for (let i = 0; i < 22; i++)
    WM_BITS.push({ x: x + ((i % 7) - 3), y: y, t: 0, drop: true,
                   vx: ((i % 7) - 3) * .5, vy: -1.5 - (i % 4) * .55 });
}
/** 💨 ฝุ่นตอนตกกระแทกพื้น — ใช้ระบบสะเก็ดเดิม แค่กระจายเตี้ย ๆ ไม่พุ่งขึ้นฟ้า */
function wmDust(x, y, n) {
  for (let i = 0; i < n; i++)
    WM_BITS.push({ x: x, y: y, t: 0, dust: true,
                   vx: ((i % 5) - 2) * .45, vy: -0.25 - (i % 3) * .2 });
}
function wmBoom(b) { WM_BOOMS.push({ x: b.x, y: b.y, r: (b.crater || 8) * 1.6, t: 0 }); }
/** เส้นประตามวิถีกระสุน — บอกว่ามันโค้งไปถึงตรงนั้นได้ยังไง */
function wmDrawTrail(ctx, path, alpha) {
  if (!path || path.length < 2 || alpha <= 0) return;
  const step = Math.max(2, Math.round(6 / WM_CAM.z));
  ctx.globalAlpha = alpha * .85;
  ctx.fillStyle = '#ffd66b';
  const sz = Math.max(1, Math.round(WM_CAM.z / 2));
  for (let i = 0; i < path.length; i += step) {
    ctx.fillRect(WM_CAM.sx(path[i][0]), WM_CAM.sy(path[i][1]), sz, sz);
  }
  ctx.globalAlpha = 1;
}
/** วงเหวี่ยงของสกิลประชิด — บอกให้เห็นว่าฟันไปถึงตรงไหน */
function wmSwing(a) {
  if (!a.from) return;
  const [dx, dy] = a.aim || [a.face || 1, 0];
  wmFocus({ x: a.from[0] + dx * (a.reach || 24) / 2,
            y: a.from[1] + dy * (a.reach || 24) / 2 });   // ให้เห็นจุดที่หมัดลง
  const [ax, ay] = a.aim || [a.face || 1, 0];       // ฟันได้รอบตัว วงเหวี่ยงต้องหันตาม
  WM_SWINGS.push({ x: a.from[0], y: a.from[1], r: a.reach || 24, t: 0,
                   mid: Math.atan2(ay, ax) });
}
/** เส้นเล็ง — บอกทิศ/มุม/แรงที่เลือกไว้ (ไม่ใช่การทำนายวิถี กติกาอยู่ที่เซิร์ฟเวอร์) */
function wmDrawAim(ctx) {
  if (WM_JUMP && WM_ST && WM_CAM) {                // 🦘 แถบชาร์จกระโดดเหนือหัว
    const f = wmMe(), z = WM_CAM.z, pw = wmJumpPower();
    const x0 = WM_CAM.sx(f.x), y0 = WM_CAM.sy(f.y) - 11 * z;
    const bw = 40, bx = x0 - bw / 2, by = y0 - 30;
    ctx.fillStyle = '#000000aa'; ctx.fillRect(bx - 1, by - 1, bw + 2, 7);
    ctx.fillStyle = '#8fd0ff';
    ctx.fillRect(bx, by, bw * pw, 5);
    const lean = wmLean();
    if (lean) {                                    // ลูกศรบอกว่าจะเอนไปทางไหน
      ctx.fillStyle = '#ffd66b';
      for (let i = 0; i < 3; i++)
        ctx.fillRect(x0 + (10 + i * 6) * lean - 2, y0 - 20, 4, 4);
    }
  }
  if (!WM_AIM || !WM_ST || !WM_CAM) return;
  const f = wmMe(), z = WM_CAM.z, pw = WM_AIM.pow;
  const x0 = WM_CAM.sx(f.x), y0 = WM_CAM.sy(f.y) - 11 * z;
  {
    // ประชิดก็เล็งได้รอบตัวเหมือนกัน ต่างแค่ระยะคงที่ ชาร์จไม่ได้ไกลขึ้น
    const melee = WM_AIM.kind === 'melee';
    const ang = WM_AIM.ang * Math.PI / 180;
    const len = melee ? (wmSpec(WM_SKILL) || {}).reach || 26 : 14 + pw * 0.6;
    ctx.strokeStyle = '#ffd66b'; ctx.lineWidth = 1; ctx.setLineDash([4, 3]);
    ctx.beginPath(); ctx.moveTo(x0, y0);
    ctx.lineTo(x0 + Math.cos(ang) * len * WM_AIM.dir, y0 - Math.sin(ang) * len);
    ctx.stroke(); ctx.setLineDash([]);
    ctx.fillStyle = '#ffd66b';
    ctx.fillRect(x0 + Math.cos(ang) * len * WM_AIM.dir - 2, y0 - Math.sin(ang) * len - 2, 5, 5);
    ctx.fillStyle = '#fff'; ctx.font = '10px monospace'; ctx.textAlign = 'left';
    ctx.fillText(Math.round(WM_AIM.ang) + '°', x0 + 8 * WM_AIM.dir, y0 - 16);
  }
  if (WM_AIM.kind === 'melee') return;             // ประชิดชาร์จไม่ได้ ไม่ต้องมีแถบ
  const bw = 44, bx = x0 - bw / 2, by = y0 - 34;   // แถบชาร์จเหนือหัว
  ctx.fillStyle = '#000000aa'; ctx.fillRect(bx - 1, by - 1, bw + 2, 7);
  ctx.fillStyle = pw > 85 ? '#ff6a4a' : pw > 55 ? '#ffd66b' : '#6fd07a';
  ctx.fillRect(bx, by, bw * pw / 100, 5);
}
/** วาดกระสุนที่กำลังบิน + ลูกไฟระเบิด + ตัวเลขดาเมจ + วงเหวี่ยงฟัน */
function wmDrawFx(ctx) {
  wmDrawAim(ctx);
  wmDrawSpawns(ctx);
  // ✨ วงแหวนบัฟ — ขยายออกจากตัวคนใช้แล้วจางหาย
  WM_AURAS = WM_AURAS.filter(v => v.t < 26);
  WM_AURAS.forEach(v => {
    const k = (v.t += WM_DT) / 26, z = WM_CAM.z;
    ctx.strokeStyle = v.color; ctx.globalAlpha = (1 - k) * .9;
    ctx.lineWidth = Math.max(1.5, z * .8);
    ctx.beginPath();
    ctx.arc(WM_CAM.sx(v.x), WM_CAM.sy(v.y - 11), (4 + k * 20) * z, 0, 7);
    ctx.stroke(); ctx.globalAlpha = 1;
  });
  WM_SWINGS = WM_SWINGS.filter(s => s.t < 10);
  WM_SWINGS.forEach(s => {
    const k = (s.t += WM_DT) / 10, z = WM_CAM.z;
    ctx.strokeStyle = '#fff6d8'; ctx.globalAlpha = 1 - k;
    ctx.lineWidth = Math.max(2, z);
    ctx.beginPath();
    ctx.arc(WM_CAM.sx(s.x), WM_CAM.sy(s.y - 10), s.r * z * (.5 + k * .6),
            s.mid - 0.9, s.mid + 0.9);
    ctx.stroke(); ctx.globalAlpha = 1;
  });
  // 🌠 กระสุนที่กำลังบิน — ลากเส้นประไว้ข้างหลังให้เห็นว่าโค้งไปยังไง
  if (WM_SHOT) {
    // ⚠️ จุดในเส้นวิถีห่างกันได้ถึง 9 px ตอนชาร์จเต็ม เดินทีละจุดจึงยังกระตุก
    //    เดินทีละเศษส่วนแล้วเกลี่ยตำแหน่งระหว่างจุด = ลื่นและช้าลงพอให้กล้องตามทัน
    const last = WM_SHOT.path.length - 1;
    WM_SHOT.i = Math.min(WM_SHOT.path.length, WM_SHOT.i + WM_SHOT_STEP * WM_DT);
    const at = Math.floor(WM_SHOT.i);
    const seen = WM_SHOT.path.slice(0, Math.min(at + 1, WM_SHOT.path.length));
    wmDrawTrail(ctx, seen, 1);
    const pa = WM_SHOT.path[Math.min(at, last)];
    const pb = WM_SHOT.path[Math.min(at + 1, last)];
    const mix = WM_SHOT.i - at;
    const p = [pa[0] + (pb[0] - pa[0]) * mix, pa[1] + (pb[1] - pa[1]) * mix];
    wmFocus({ x: p[0], y: p[1] });      // เกาะลูกกระสุนไปจนกว่าจะกระทบเป้า
    const hx = WM_CAM.sx(p[0]), hy = WM_CAM.sy(p[1]);
    ctx.fillStyle = '#fff6d8';
    ctx.fillRect(hx - 2, hy - 2, 5, 5);
    ctx.fillStyle = '#ffb45a';
    ctx.fillRect(hx - 1, hy - 1, 3, 3);
    // 🎯 ลูกที่แยกออกไปพร้อมกัน (หน้าไม้สามแฉก) — บินคู่ ระเบิดของใครของมัน
    (WM_SHOT.extra || []).forEach(e => {
      if (e.done) return;
      e.i = Math.min(e.path.length, e.i + WM_SHOT_STEP * WM_DT);
      const eat = Math.min(Math.floor(e.i), e.path.length - 1);
      wmDrawTrail(ctx, e.path.slice(0, eat + 1), .8);
      const ep = e.path[eat];
      ctx.fillStyle = '#ffd08a';
      ctx.fillRect(WM_CAM.sx(ep[0]) - 1, WM_CAM.sy(ep[1]) - 1, 3, 3);
      if (e.i >= e.path.length) { e.done = true; if (e.blast) wmLand(e.blast); }
    });
    if (WM_SHOT.i >= WM_SHOT.path.length) {
      // ถึงปลายทางแล้ว — เจาะพื้น ระเบิด แล้วค่อยไล่ดูคนที่โดนทีละคน
      const shot = WM_SHOT;
      WM_SHOT = null;
      WM_TRAIL = { path: shot.path, t: 0 };
      wmFocus({ x: p[0], y: p[1] }, true);      // ค้างที่จุดกระทบก่อน
      wmLand(shot.blast);
      const boom = WM_DEATHS; WM_DEATHS = [];
      wmBreakProps((shot.blast || {}).broke);   // ของที่โดนระเบิดพังไปด้วย
      wmPlayVictims(shot.atk || { hits: shot.hits, blast: shot.blast },
                    () => wmPlayDeaths(boom, () => WM_AFTER.push(wmCallDeaths)));
      if (shot.byBot) toast(`🤖 บอทใช้ ${shot.name}`,
                            shot.hits.some(h => h.name === 'คุณ' && !h.dodged));
    }
  }
  // เส้นประค้างไว้อีกครู่หลังระเบิด จะได้ดูทันว่ากระสุนวิ่งไปทางไหน
  if (WM_TRAIL) {
    WM_TRAIL.t += WM_DT;
    wmDrawTrail(ctx, WM_TRAIL.path, Math.max(0, 1 - WM_TRAIL.t / 70));
    if (WM_TRAIL.t > 70) WM_TRAIL = null;
  }
  // 🔥 กองไฟ — เปลวสั่นไหวแล้วค่อยจางลง
  WM_FIRES = WM_FIRES.filter(v => v.t < WM_FIRE_LIFE);
  WM_FIRES.forEach(v => {
    const k = (v.t += WM_DT) / WM_FIRE_LIFE, z = WM_CAM.z;
    const gx = WM_CAM.sx(v.x), gy = WM_CAM.sy(v.y);
    ctx.globalAlpha = Math.min(1, (1 - k) * 1.6);
    for (let i = 0; i < 9; i++) {
      const a = (i / 9) * 6.283 + v.t * .05;
      const rr = v.r * (0.35 + 0.5 * ((i % 3) + 1) / 3);
      const fx = gx + Math.cos(a) * rr * z;
      const fy = gy + Math.sin(a) * rr * z * .45
               - Math.abs(Math.sin(v.t * .18 + i)) * 7 * z;
      ctx.fillStyle = (i + Math.floor(v.t / 4)) % 3 === 0 ? '#ffe07a'
                    : (i % 2 ? '#ff8a3a' : '#d93b2b');
      ctx.fillRect(fx - z, fy - 2 * z, 2 * z, 3 * z);
    }
    ctx.globalAlpha = 1;
  });

  // 🪨 สะเก็ดจากหลุมที่เพิ่งเจาะ
  WM_BITS = WM_BITS.filter(b => b.t < 52);
  WM_BITS.forEach(b => {
    b.vy += (b.dust ? 0.03 : 0.14) * WM_DT;
    b.x += b.vx * WM_DT; b.y += b.vy * WM_DT; b.t += WM_DT;
    ctx.globalAlpha = (1 - b.t / 52) * (b.dust ? .55 : 1);
    ctx.fillStyle = b.fire ? (b.t % 4 < 2 ? '#ffd06a' : '#ff6a2a')
                  : b.drop ? (b.t % 4 < 2 ? '#bfe9ff' : '#6fb6d8')
                  : b.dust ? '#d8cbb4' : b.t % 5 < 2 ? '#c89a4b' : '#6b5433';
    ctx.fillRect(WM_CAM.sx(b.x), WM_CAM.sy(b.y), Math.max(1, WM_CAM.z / 2),
                 Math.max(1, WM_CAM.z / 2));
    ctx.globalAlpha = 1;
  });
  WM_BOOMS = WM_BOOMS.filter(b => b.t < 30);      // ระเบิดค้างให้ดูทัน
  WM_BOOMS.forEach(b => {
    const k = (b.t += WM_DT) / 30, r = b.r * (0.4 + k) * WM_CAM.z;
    ctx.globalAlpha = 1 - k;
    ctx.fillStyle = k < .4 ? '#fff6d8' : k < .7 ? '#ffb45a' : '#8f2317';
    ctx.beginPath(); ctx.arc(WM_CAM.sx(b.x), WM_CAM.sy(b.y), r, 0, 6.29); ctx.fill();
    ctx.globalAlpha = 1;
  });

  // ตัวเลขดาเมจลอยขึ้นตรงตัวคนที่โดน — เห็นชัดว่าใครโดนเท่าไหร่ ตรงไหน
  WM_POPS = WM_POPS.filter(p => p.t < 78);        // เลขดาเมจค้างให้อ่านทัน
  WM_POPS.forEach(p => {
    const k = (p.t += WM_DT) / 78;
    ctx.globalAlpha = k < .75 ? 1 : (1 - k) * 4;
    ctx.font = `bold ${Math.max(10, 8 * WM_CAM.z)}px ` + getComputedStyle(document.body).fontFamily;
    ctx.textAlign = 'center';
    const x = WM_CAM.sx(p.x), y = WM_CAM.sy(p.y) - k * 26 * WM_CAM.z / 2;
    ctx.fillStyle = '#000'; ctx.fillText(p.text, x + 1, y + 1);
    ctx.fillStyle = p.buff ? '#8ef0b0' : p.miss ? '#9fd0e8' : '#ff6a4a';
    ctx.fillText(p.text, x, y);
    ctx.globalAlpha = 1; ctx.textAlign = 'left';
  });
}
/** ส่งคำสั่งไปเซิร์ฟเวอร์ แล้วเอาเส้นทางที่ได้มาเล่นภาพ */
/** โดนจำกัดอัตราแล้วหยุดยิงชั่วคราว — ยิงต่อมีแต่ทำให้รอนานขึ้น */
function wmBackoff(e) {
  if (e.status !== 429) return false;
  const wait = Math.max(2, e.retryAfter || 3);
  WM_BACKOFF = performance.now() + wait * 1000;
  wmHoldStop();
  return true;
}
async function wmDo(action, dir, extra) {
  const predicted = !!(extra && extra.predicted);
  // เดินแบบเดาไว้ก่อนไม่ต้องรอคิวภาพ — ตัวเดินไปแล้ว นี่แค่ส่งไปให้ยืนยัน
  if (wmBusy) return;
  if (!predicted && wmWaiting()) return;
  if (performance.now() < WM_BACKOFF) return;
  wmBusy = true;
  try {
    const d = await api('POST', '/api/web/pvp/worms/match',
                        { action: action, dir: dir, steps: WM_WALK_STEPS, ...(extra || {}) });
    const mine = WM_ST.turn;              // ตาใครตอนสั่ง — แรงหมดแล้วเซิร์ฟเวอร์สลับตาให้แล้ว
    // ⚠️ ท่อนก่อนอาจยังเล่นภาพไม่จบ (กดค้างเดินยิงคำสั่งถี่กว่าภาพเล่นจบ)
    //    ถ้าย้อนไปที่ "ตำแหน่งที่กำลังวาดอยู่" เส้นทางใหม่จะเริ่มจากตำแหน่งของเซิร์ฟเวอร์
    //    ซึ่งอยู่ข้างหน้าไปแล้ว — เห็นเป็นตัววาปย้อนหลังแล้ววาปกลับ
    //    ต้องย้อนไปที่ "ปลายทางของท่อนก่อน" ซึ่งคือจุดที่เซิร์ฟเวอร์เริ่มท่อนใหม่พอดี
    const tail = WM_ANIM && WM_ANIM.fi === mine
      ? WM_ANIM.path[WM_ANIM.path.length - 1] : null;
    const cur = WM_ST.fighters[mine];
    const from = tail ? { x: tail[0], y: tail[1] } : { x: cur.x, y: cur.y };
    const old = wmSnapshot();
    // ⚠️ ห้ามล้างภาพที่ฝั่งจอกำลังเล่นเอง (กระโดด/ร่วงจากการเดิน) — เดิมล้างทุกครั้ง
    //    คำตอบมาถึงกลางอากาศเมื่อไหร่ ภาพกระโดดตายคาที่แล้ววาปไปจุดลงพื้นทันที
    if (!predicted) { WM_ANIM = null; WM_QUEUE = []; }
    WM_ST = { ...d };
    // 🤖 บอทต้องอยู่ที่เดิมจนกว่าภาพเดินของมันจะเริ่มเล่นจริง
    //    wmQueueBot ย้อนบอทกลับจุดเริ่ม "ตอนขั้นนั้นเริ่มทำงาน" ซึ่งช้ากว่าตรงนี้
    //    อย่างน้อย 1 วินาที (WM_GAP_BEFORE) — ระหว่างนั้นจอวาดบอทที่ปลายทางไปแล้ว
    //    ผู้เล่นเห็นเป็น "รู้ผลการเดินของบอทก่อนบอทจะเดิน"
    wmHideOutcome(old);
    // 🚦 ผลลัพธ์ทุกอย่างรอให้ภาพเดิน/กระโดดเล่นจบก่อน — ห้ามสรุปผลก่อนเด็ดขาด
    //    เดิมเก็บหีบ/ขึ้นเรือเหาะ/เหยียบกับดัก เกิดทันทีที่เซิร์ฟเวอร์ตอบ
    //    ผู้เล่นเห็นได้ของตั้งแต่ตัวยังกระโดดไปไม่ถึงกล่องด้วยซ้ำ
    const after = () => {
      (d.sprung || []).forEach(t => {     // 🕳️ กับดักระเบิดตรงจุดที่เหยียบ
        SFX.play('trap');
        wmTrapFx(t.x, t.y);
        toast('🕳️ เหยียบกับดัก!', true);
      });
      (d.opened || []).forEach(o => wmOpenChest(o));
      if (d.ferry) wmRideFerry(mine, d.ferry);
      if ((d.deaths || []).length)        // ตกตาย/เหยียบกับดักตาย ร่างก็ระเบิดเหมือนกัน
        wmPlayDeaths(d.deaths, () => WM_AFTER.push(wmCallDeaths));
      if (d.move && d.move.drowned) WM_AFTER.push(wmCallDeaths);
      WM.props = wmPropsNow(d.props); WM.repaint();   // ของหายตอนเก็บได้จริง ไม่ใช่ก่อนถึง
      if (d.auto_ended) { wmQueueBot(d); toast('⏭️ แรงเดินหมด — จบเทิร์นให้อัตโนมัติ'); }
      wmPaintHud();
    };

    if (predicted) {
      // กำลังลอยอยู่ = ก้อนเดินก้อนนี้เป็นของอดีต อย่าลากตัวกลับลงมากลางอากาศ
      wmReconcile(mine, d, dir);
      after();
    } else if (d.move && d.move.path.length) {
      WM_ST.fighters[mine].x = from.x; WM_ST.fighters[mine].y = from.y;
      WM_ANIM = { fi: mine, path: d.move.path, i: 0, onEnd: after,
                  bump: (d.move.bump || null) };   // ให้เอฟเฟกต์หัวชนขึ้นตอนชนจริง
      if (action === 'jump') SFX.play('jump');
    } else {
      after();                            // ไม่มีภาพให้เล่น (ชนกำแพง) ก็สรุปได้เลย
    }
  } catch (e) { if (!wmBackoff(e)) toast(e.message, true); }
  finally { wmBusy = false; }
}
/** 🦘 ปล่อยปุ่ม = ขอกระโดดจากเซิร์ฟเวอร์ แล้วเล่นภาพวิถีที่มันคืนมา

    ⚠️ เคยลองให้จอลอยเองด้วยฟิสิกส์ (08-27) เพื่อตัดดีเลย์ ~300 ms ออก
       ฟิสิกส์ตรงกับเซิร์ฟเวอร์เป๊ะทุกเฟรม (เทส 360 เคส) แต่ "สภาพการลอย"
       ที่ถืออยู่ฝั่งจอกลายเป็นสถานะค้างได้หลายทาง พอค้างแล้วเกมล็อกทั้งเกม
       เจ้าของเกมเจอของจริง: กระโดดแล้วภาพค้าง · ยอมแพ้ไม่ทำงาน · เปิดแมตช์ใหม่จอเพี้ยน
       จึงถอยกลับมาแบบนี้ — ช้ากว่าแต่ไม่มีสถานะค้างให้พังได้เลย
 */
function wmJumpFire(dir, power, lean) {
  if (!WM_ST || WM_ST.over) return;
  const me = WM_ST.fighters[WM_ST.turn];
  if (!me || me.bot || me.dead) return;
  if (WM_ST.moves < 6) {                // เงียบไปเฉย ๆ = ผู้เล่นนึกว่าปุ่มเสีย
    toast('🔋 แรงไม่พอกระโดด — กดจบเทิร์นได้เลย', true);
    return;
  }
  wmWalkStop();                         // ปิดก้อนเดินที่ค้างก่อน จะได้ไม่ปนกัน
  me.face = dir;
  wmDo('jump', dir, { jump_power: power, lean: lean });
}
/** 🎯 เอาคำตอบของเซิร์ฟเวอร์มาทาบกับตำแหน่งที่จอเดาไว้

    เซิร์ฟเวอร์ตอบ "เดิน n ก้าวที่ส่งไปแล้วอยู่ตรงนี้" แต่ระหว่างรอ ~300 ms
    ผู้เล่นกดค้างต่อ จอจึงเดินไปอีกหลายก้าวที่เซิร์ฟเวอร์ยังไม่เห็น
    ต้องเดินก้าวพวกนั้นซ้ำต่อจากตำแหน่งจริง ไม่ใช่ทิ้ง (ตัวจะกระตุกถอยหลัง)

    ⚠️ เชื่อเซิร์ฟเวอร์เสมอ ต่างกันเท่าไหร่ก็ยอมตามนั้น — ไม่งั้นเปิด devtools
       แล้วปล่อยให้ฝั่งจอชนะการทาบ = เดินทะลุกำแพงได้
 */
function wmReconcile(mine, d, dir) {
  const f = WM_ST.fighters[mine];
  const server = d.move ? { x: d.move.x, y: d.move.y } : { x: f.x, y: f.y };
  const ahead = WM_PRED && WM_PRED.dir === dir ? WM_PRED.pending : 0;
  const spot = ahead > 0
    ? WALK.walk(WM, WALK.rules(WM_ST), server.x, server.y, dir, ahead, true)
    : server;
  const off = Math.abs(f.x - spot.x) + Math.abs(f.y - spot.y);
  f.x = spot.x; f.y = spot.y;
  if (off > 3) wmFocus(f);          // ต่างกันเยอะ (กับดัก/พื้นหาย) พากล้องตามไปด้วย
  // ตัวเราไม่ได้รอภาพอะไร — ทาบเสร็จคือของจริงแล้ว เอาออกจากรายการที่ซ่อนไว้
  // (ไม่งั้นตอนเฉลยรวมทีหลังจะเอาตำแหน่งดิบของเซิร์ฟเวอร์มาทับ เห็นเป็นตัวเด้งถอย)
  if (WM_HIDDEN) {
    delete WM_HIDDEN[f.name];
    if (!Object.keys(WM_HIDDEN).length) WM_HIDDEN = null;
  }
}
/** 🏳️ ยอมแพ้ — ระเบิดตัวเองทิ้งแล้วจบแมตช์ (ถามก่อน กดพลาดแล้วเสียใจ) */
async function wmGiveUp() {
  if (wmWaiting()) return;
  if (!confirm('ยอมแพ้เลยไหม? ตัวละครจะระเบิดตัวเองทิ้งแล้วจบแมตช์ทันที')) return;
  try {
    const d = await api('POST', '/api/web/pvp/worms/match', { action: 'surrender' });
    const s = d.surrender || {};
    wmApply(d);
    SFX.play('lose');
    if (s.blast) wmLand(s.blast);                 // ระเบิดตรงจุดที่ยืน + เจาะพื้นจริง
    WM_POPS.push({ x: s.x, y: s.y - 30, t: 0, buff: true, text: '🏳️ ยอมแพ้' });
  } catch (e) { if (!wmBackoff(e)) toast(e.message, true); }
}
async function wmEndTurn(how) {
  try {
    const d = await api('POST', '/api/web/pvp/worms/match', { action: how || 'end' });
    const old = wmSnapshot();
    wmApply(d);
    wmHideOutcome(old);
    wmQueueBot(d);
    SFX.play('click');
  } catch (e) { if (!wmBackoff(e)) toast(e.message, true); }
}
/** ต่อคิวภาพตาบอท — บอทเดินไปแล้วฝั่งเซิร์ฟเวอร์ ที่นี่แค่เล่นภาพตามเส้นทางที่ได้มา

    ⚠️ ต้องย้อนบอทกลับไปจุดเริ่มก่อน ไม่งั้นมันโผล่ที่หมายทันทีแล้วค่อยเด้งกลับมาเดินซ้ำ
 */
let WM_SEEN_TURN = 0;        // เลขเทิร์นล่าสุดที่เล่นภาพไปแล้ว (กันเล่นซ้ำตอนโพล)

/** 👥 เล่นภาพเทิร์นของ "คนอื่น" ที่เรายังไม่เคยดู

    เจ้าของเกมเจอ (08-29): เทิร์นของคนอื่นไม่มีอนิเมชันเลย ตัววาปไปโผล่เฉย ๆ
    ต้นเหตุ: ทางที่เล่นภาพมีแค่ wmDo (ของเราเอง) กับ wmQueueBot (ตอนเราจบเทิร์น)
    ทางโพล (wmPeekTurn → fillWorms → wmApply) ได้แค่พิกัดใหม่ ไม่มีใครต่อคิวภาพให้

    ⚠️ ต้องเช็คเลขลำดับ: โพลถามซ้ำทุกไม่กี่วินาที ถ้าไม่เช็คจะเล่นภาพเดิมวนไม่จบ
 */
/** จำว่าเทิร์นนี้เล่นภาพไปแล้ว — กัน wmQueueOther มาเล่นซ้ำตอนโพลครั้งถัดไป */
function wmSeenTurn(d) {
  const q = d && d.last_turn && d.last_turn.seq;
  if (q && q > WM_SEEN_TURN) WM_SEEN_TURN = q;
}
function wmQueueOther(d) {
  const lt = d && d.last_turn;
  if (!lt || !lt.seq) return;
  if (lt.seq <= WM_SEEN_TURN) return;        // ดูไปแล้ว
  const first = !WM_SEEN_TURN;
  WM_SEEN_TURN = lt.seq;
  if (first) return;      // เพิ่งเข้ามาดู ไม่ต้องย้อนของเก่าให้ดูทั้งหมด

  const moves = (lt.moves || []).filter(m => (m.path || []).length);
  moves.forEach(m => {
    const fi = WM_ST.fighters.findIndex(f => f.name === lt.by);
    if (fi < 0) return;
    wmStep(() => {
      // ย้อนตัวกลับจุดเริ่ม "ตอนขั้นนี้เริ่มจริง" แบบเดียวกับตาบอท
      WM_ST.fighters[fi].x = m.path[0][0];
      WM_ST.fighters[fi].y = m.path[0][1];
      WM_QUEUE.push({ fi: fi, path: m.path, i: 0 });
      if (!WM_ANIM) WM_ANIM = WM_QUEUE.shift();
      wmFocus(WM_ST.fighters[fi], true);     // จับกล้องไปหาคนที่กำลังเล่น
    }, wmFxIdle);
  });
  wmPlayBotShots(lt.shots || []);            // ยิงก็ใช้ตัวเดียวกับบอท
  (lt.opened || []).forEach(o => wmStep(() => wmOpenChest(o), wmFxIdle));
  if ((lt.deaths || []).length) wmPlayDeaths(lt.deaths, () => {});
}
function wmQueueBot(d) {
  wmSeenTurn(d);               // เล่นภาพตาบอทตรงนี้แล้ว อย่าให้โพลมาเล่นซ้ำ
  const bi = WM_ST.fighters.findIndex(f => f.bot);
  const moves = (d.bot_moves || []).filter(m => (m.path || []).length);
  const shots = (d.bot_moves || []).filter(m => m.attack).map(m => m.attack);
  if (bi < 0) return;
  if (!moves.length) {
    // ⚠️ บอทยืนยิงอยู่กับที่ ถ้าไม่เล่นภาพตรงนี้ หลุมที่เซิร์ฟเวอร์เจาะไปแล้ว
    //    จะไม่ถูกลบบนจอเลย = เห็นพื้นอยู่แต่เหยียบแล้วร่วงทะลุ
    wmPlayBotShots(shots);
    return;
  }
  // เดินเป็นขั้นหนึ่ง ยิงเป็นอีกขั้น — เว้นจังหวะระหว่างกันให้ดูทัน
  wmStep(() => {
    // ⚠️ ย้อนบอทกลับจุดเริ่มตอน "ขั้นนี้เริ่มจริง" ไม่ใช่ตอนต่อคิว
    //    ไม่งั้นบอทไปยืนรออยู่จุดเริ่มตั้งแต่ขั้นก่อนหน้ายังเล่นไม่จบ
    WM_ST.fighters[bi].x = moves[0].path[0][0];
    WM_ST.fighters[bi].y = moves[0].path[0][1];
    moves.forEach(m => WM_QUEUE.push({ fi: bi, path: m.path, i: 0 }));
    if (!WM_ANIM) WM_ANIM = WM_QUEUE.shift();
    wmFocus(WM_ST.fighters[bi], true);    // จับกล้องไปที่บอทตั้งแต่ต้นตา
  }, wmFxIdle);
  wmPlayBotShots(shots);
}
/** กดค้าง = เดินต่อเนื่อง (ยิงเป็นก้อนละ 5 ก้าว ไม่ใช่ยิงทุกก้าว) */
/** 🦘 กระโดด: กดค้างเพื่อชาร์จแรง · กดลูกศรค้างไว้ด้วยเพื่อเอนตัวกลางอากาศ

    ⚠️ ทำไมไม่บังคับซ้ายขวากลางอากาศแบบเกมแพลตฟอร์ม:
       กระโดดหนึ่งครั้งลอยอยู่ 0.4-0.6 วิ แต่ยิงคำสั่งได้เร็วสุดราว 2 ครั้ง/วินาที
       คำสั่งที่สองมาถึงก็ลงพื้นไปแล้ว จึงเลือกทิศ/แรง/การเอนตัวตั้งแต่ตอนกระโดดแทน
 */
let WM_JUMP = null;             // {dir, t0} ระหว่างกดค้างชาร์จกระโดด

const WM_JUMP_MS = 620;         // กดค้างนานเท่านี้แรงเต็ม

const WM_KEYS = {};             // ปุ่มลูกศรที่กดค้างอยู่ตอนนี้ (ใช้หาทิศเอนตัว)

function wmJumpPower() {
  return WM_JUMP ? Math.min(1, 0.05 + (performance.now() - WM_JUMP.t0) / WM_JUMP_MS) : 1;
}
function wmLean() {
  return (WM_KEYS.right ? 1 : 0) - (WM_KEYS.left ? 1 : 0);
}
function wmHoldStart(action, dir) {
  if (wmWaiting()) return;
  if (action === 'jump') {                 // ชาร์จก่อน ปล่อยแล้วค่อยกระโดดจริง
    WM_JUMP = { dir: dir, t0: performance.now() };
    return;
  }
  WM_KEYS[dir > 0 ? 'right' : 'left'] = true;
  if (WM_JUMP) return;                     // กำลังชาร์จกระโดดอยู่ — ลูกศรคือ "เอนตัว" ไม่ใช่เดิน
  wmWalkStart(dir);
}
// ── 🏃 เดินเองทันนิ้ว แล้วให้เซิร์ฟเวอร์ตามมายืนยัน ──
//
// เดิม: กดค้าง → ยิง HTTP ขอ "เดิน 6 ก้าว" → รอ ~300 ms (เซิร์ฟเวอร์อยู่หลัง tunnel)
//       → เล่นภาพ 500 ms → ค่อยขอรอบใหม่ = 12 พิกเซล/วินาที เป็นก้อน ๆ
//       และปล่อยนิ้วไปแล้วตัวยังเดินต่ออีกก้อนหนึ่ง
// ใหม่: จอเดินเองด้วยกฎชุดเดียวกัน (walk.js) ทุก WM_WALK_TICKS เฟรม
//       ส่ง "กดทิศไหนไปกี่ก้าว" ไปเป็นระยะ แล้วเอาตำแหน่งจริงจากเซิร์ฟเวอร์มาทาบ
//
// 🔒 ยังโกงไม่ได้: API ไม่เคยรับพิกัด รับแค่จำนวนก้าว แล้วเซิร์ฟเวอร์เดินเองซ้ำ
//    ตัดด้วยแรงเดินที่เหลือ ก้าวที่เกินมาถูกทิ้งทั้งหมด
const WM_WALK_TICKS = 3;      // ก้าวหนึ่งทุกกี่เฟรมมาตรฐาน (3 = ~20 พิกเซล/วินาที)

const WM_SEND_MS = 250;       // ส่งให้เซิร์ฟเวอร์ยืนยันทุกกี่มิลลิวินาที

// { dir, tick, pending, done } · pending = ก้าวที่เดินไปแล้วแต่ยังไม่ได้ส่ง
let WM_PRED = null;
function wmWalkStart(dir) {
  if (!WM_ST || WM_ST.over) return;
  if (WM_PRED && WM_PRED.dir !== dir) WM_PRED.done = true;   // สลับทิศ = ปิดก้อนเดิม
  if (!WM_PRED || WM_PRED.done) wmWalkFlush();
  if (!WM_PRED)
    WM_PRED = { dir: dir, tick: 0, pending: 0, beat: 0, done: false, probed: false, at: 0 };
  WM_PRED.dir = dir;
  WM_PRED.done = false;
  WM_PRED.at = WM_PRED.at || performance.now();
}
function wmWalkStop() {
  if (WM_PRED) WM_PRED.done = true;      // ปิดก้อน — ลูปวาดจะส่งให้เองเมื่อสายว่าง
}
/** เดินฝั่งจอหนึ่งเฟรม + ส่งให้เซิร์ฟเวอร์ยืนยันเป็นระยะ — เรียกจากลูปวาดเท่านั้น */
function wmWalkTick() {
  if (!WM_ST) return;
  if (!WM_PRED) return;
  const me = wmMe();
  const held = (WM_KEYS.left || WM_KEYS.right) && !WM_PRED.done;
  const can = held && !WM_ST.over && !WM_JUMP && !me.bot && !me.dead && !wmBusyFx();
  if (can) {
    WM_PRED.tick += WM_DT;
    while (WM_PRED.tick >= WM_WALK_TICKS && WM_ST.moves > 0) {
      WM_PRED.tick -= WM_WALK_TICKS;
      const s = WALK.step(WM, WALK.rules(WM_ST), me.x, me.y, WM_PRED.dir, true);
      me.face = WM_PRED.dir;
      // 🔋 หักแรงให้ตรงกับเซิร์ฟเวอร์เป๊ะ: เซิร์ฟเวอร์หัก max(ก้าวที่เดินได้จริง, 1)
      //    "ต่อหนึ่งคำขอ" ไม่ใช่ต่อหนึ่งครั้งที่พยายามก้าว
      //    ⚠️ เดิมหักทุกครั้งแม้ชนกำแพง — กดค้างดันกำแพงแล้วจอคิดว่าแรงหมด
      //       ทั้งที่เซิร์ฟเวอร์ยังเหลือเยอะ จอเลยหยุดส่งคำสั่ง เซิร์ฟเวอร์ไม่มีทางรู้
      //       ว่าต้องจบเทิร์น = กดอะไรไม่ได้เลยทั้งเทิร์น (ทั้งเดินและกระโดด)
      if (s.how === WALK.BLOCKED) {
        if (!WM_PRED.pending) { WM_ST.moves--; WM_PRED.pending++; }
        break;                            // ชนกำแพง/ขอบน้ำ — ก้อนนี้จบแค่นี้
      }
      WM_ST.moves--;
      WM_PRED.pending++;
      if (s.y > me.y + 1) {               // ก้าวนี้ตกหน้าผา — ต้องร่วงให้เห็น ไม่ใช่วาปลง
        me.x = s.x;
        const drop = [];
        for (let gy = me.y + 1; gy <= s.y; gy++) drop.push([s.x, gy]);
        wmChunk(WM_ST.turn, drop, null);  // ระหว่างร่วงเดินต่อไม่ได้ (wmBusyFx เป็นจริง)
        break;
      }
      me.x = s.x; me.y = s.y;
      if (WM_PRED.pending % 3 === 0) SFX.play('walk');
      wmFocus(me);
    }
    wmPaintHud();
  }
  // 🔋 จอคิดว่าแรงหมดแล้ว — ต้องให้เซิร์ฟเวอร์เป็นคนชี้ขาดและจบเทิร์นให้
  //    (จอคิดผิดได้ ห้ามปล่อยให้เงียบไปเฉย ๆ ไม่งั้นค้างทั้งเทิร์น)
  if (can && WM_ST.moves <= 0 && !WM_PRED.pending && !WM_PRED.probed) {
    WM_PRED.probed = true;
    WM_PRED.pending = 1;                  // ขอเดินอีกก้าว — เซิร์ฟเวอร์จะจบเทิร์นให้เอง
    WM_PRED.done = true;
  }
  wmWalkFlush();
}
/** ส่งก้าวที่สะสมไว้ — รอให้คำขอก่อนหน้ากลับมาก่อนเสมอ ก้าวที่เดินระหว่างรอไม่หาย */
function wmWalkFlush() {
  const p = WM_PRED;
  if (!p) return;
  const due = p.done || performance.now() - p.at >= WM_SEND_MS;
  if (!due || wmBusy) return;
  if (!p.pending) { if (p.done) WM_PRED = null; return; }
  const n = p.pending, dir = p.dir;
  p.beat += n;                     // ท่าขาเดินต่อเนื่อง ไม่รีเซ็ตทุกครั้งที่ส่งก้อนไป
  p.pending = 0;
  p.at = performance.now();
  if (p.done) WM_PRED = null;
  wmDo('walk', dir, { steps: n, predicted: true });
}
/** ปล่อยปุ่ม — what = 'walk' | 'jump' | undefined (ปล่อยทุกอย่าง)

    ⚠️ ต้องแยกให้ชัด ไม่งั้นปล่อยลูกศรระหว่างชาร์จกระโดด = กระโดดออกไปก่อนเวลา
 */
function wmHoldStop(what) {
  if (what !== 'jump') {
    clearInterval(wmHold); wmHold = 0;
    WM_KEYS.left = WM_KEYS.right = false;
    wmWalkStop();                          // ปิดก้อนที่เดินไว้ ส่งให้เซิร์ฟเวอร์ยืนยันทันที
  }
  if (what === 'walk') return;
  if (WM_JUMP) {                           // ปล่อยปุ่มกระโดด = ออกตัวจริง
    const j = WM_JUMP, pow = wmJumpPower(), lean = wmLean();
    WM_JUMP = null;
    wmJumpFire(j.dir, pow, lean);
  }
}
function wmZoom(dz) {
  if (!WM_CAM) return;
  WM_CAM.zoomAt(dz, WM_CAM.mx(WM_CAM.vw / 2), WM_CAM.my(WM_CAM.vh / 2));
  document.getElementById('wmZoom').textContent = '×' + WM_CAM.z;
}
// ══════════════════════════════════════════════════════════════════════
// 🎪 ห้องเล่นหลายคน — แยกขาดจากปุ่มซ้อมกับบอทตามที่เจ้าของเกมสั่ง
//
// เบราว์เซอร์ทำแค่ "กดปุ่ม" เหมือนเดิม — ห้อง ทีม และลำดับเทิร์น
// ตัดสินที่เซิร์ฟเวอร์ทั้งหมด (bot/pvp/rooms.py)
// ══════════════════════════════════════════════════════════════════════
// ⏳ เล่นหลายคน: ตาคนอื่นอยู่ ต้องคอยถามเซิร์ฟเวอร์ว่ามีอะไรเกิดขึ้นบ้าง
//    (ไม่มีตัวนี้ = นั่งมองจอนิ่ง ๆ ไม่มีวันรู้ว่าถึงตาตัวเองแล้ว)
const WM_PEEK_MS = 2200;
let WM_PEEK_AT = 0;
/** 📱 ปรับขนาดแคนวาสจริงให้เท่ากล่องบนจอ — ไม่งั้นภาพถูกยืดจาก 720×270

    แคนวาสมีสองขนาด: ขนาดกล่อง (CSS) กับขนาดภาพจริง (width/height ของ element)
    ถ้าไม่ปรับขนาดภาพจริงตาม ภาพ 720×270 จะถูกยืดให้เต็มกล่อง = เบลอและสัดส่วนเพี้ยน
    ปรับแล้วกล้องจะเห็นพื้นที่กว้าง/สูงขึ้นจริง (vw/vh อ่านจากขนาดนี้)

    ⚠️ ต้องเรียกใหม่ทุกครั้งที่หมุนจอ/เปลี่ยนขนาดหน้าต่าง ไม่งั้นหมุนจอแล้วภาพเพี้ยนค้าง
 */
function wmFitCanvas() {
  const cv = document.getElementById('wmCanvas');
  if (!cv) return false;
  const box = cv.getBoundingClientRect();
  if (!box.width || !box.height) return false;
  // เพดานไว้กันเครื่องช้า — ภาพใหญ่กว่านี้ตาก็ไม่เห็นความต่างแต่วาดหนักขึ้นมาก
  const w = Math.min(1280, Math.round(box.width));
  const h = Math.min(720, Math.round(box.height));
  if (cv.width === w && cv.height === h) return false;
  cv.width = w; cv.height = h;
  if (WM_CAM) {
    WM_CAM.vw = w; WM_CAM.vh = h;
    WM_CAM.clamp(); WM_CAM.hold();
  }
  return true;
}
addEventListener('resize', () => wmFitCanvas());
addEventListener('orientationchange', () => setTimeout(wmFitCanvas, 120));

function wmPeekTurn() {
  if (!WM_ST || !WM_ST.room || WM_ST.over) return;
  if (WM_ST.my_turn || wmBusyFx() || wmBusy) return;
  const now = performance.now();
  if (now - WM_PEEK_AT < WM_PEEK_MS) return;
  WM_PEEK_AT = now;
  fillWorms().catch(() => {});                   // เน็ตสะดุดครั้งเดียวไม่ต้องทำอะไร
}
let WM_ROOM = null;          // สถานะห้องล่าสุดที่เซิร์ฟเวอร์ตอบมา

let WM_ROOM_POLL = 0;        // ตัวจับเวลาถามซ้ำ (คนอื่นเข้า/ออก/เปลี่ยนทีมต้องเห็น)

async function wmRoomDo(action, extra) {
  try {
    WM_ROOM = await api('POST', '/api/web/pvp/worms/room',
                        { action: action, ...(extra || {}) });
    wmPaintRoom();
    if (action === 'start') { WM_ROOM = null; wmPaintRoom(); await fillWorms(); }
  } catch (e) { toast(e.message, true); }
}
/** ถามสถานะห้องซ้ำเป็นระยะ — ไม่งั้นเพื่อนเข้ามาแล้วเราไม่เห็น */
function wmRoomWatch(on) {
  clearInterval(WM_ROOM_POLL);
  WM_ROOM_POLL = 0;
  if (!on) return;
  WM_ROOM_POLL = setInterval(async () => {
    try {
      const r = await api('GET', '/api/web/pvp/worms/room');
      const changed = JSON.stringify(r) !== JSON.stringify(WM_ROOM);
      WM_ROOM = r;
      if (changed) wmPaintRoom();
      if (r.started) { wmRoomWatch(false); await fillWorms(); }
    } catch (e) { /* เน็ตสะดุดครั้งเดียวไม่ต้องปิดห้องทิ้ง */ }
  }, 2500);
}
async function wmPaintRoom() {
  const box = document.getElementById('wmRoom');
  if (!box) return;
  const r = WM_ROOM;
  if (!r || !r.in_room) {
    box.hidden = true;
    wmRoomWatch(false);
    INVITE_FRIENDS = null;                       // ออกห้องแล้ว — เข้าห้องใหม่ค่อยดึงเพื่อนใหม่
    return;
  }
  box.hidden = false;
  wmRoomWatch(true);
  const plans = r.plans.map(p => `
    <button data-plan="${esc(p.key)}" class="${p.key === r.plan ? 'on' : ''}"
      ${r.host ? '' : 'disabled'}>${esc(p.name)}${p.need ? ` (${p.need} คน)` : ''}</button>`).join('');
  const teams = r.teams > 1 ? `<div class="teams">` + r.team_names.map((n, i) =>
    `<button data-team="${i}">${esc(n)}</button>`).join('') + `</div>` : '';
  const invite = await inviteFriendsHtml(false);
  box.innerHTML = `
    <div class="code">${esc(r.code)}</div>
    <div class="why">ส่งรหัสนี้ให้เพื่อนกด “เข้าห้องด้วยรหัส” · ${r.seats.length}/${r.max} คน</div>
    <div class="plans">${plans}</div>
    ${teams}
    <div class="seats">${r.seats.map(s => `
      <div class="seat${s.you ? ' you' : ''}">
        ${s.host ? '👑' : '🙋'} ${esc(s.name)}
        <span class="tag">${r.teams > 1 ? esc(r.team_names[s.team] || '') : ''}
          ${s.you ? '· คุณ' : ''}</span>
      </div>`).join('')}</div>
    ${r.why ? `<div class="why">⚠️ ${esc(r.why)}</div>` : ''}
    ${invite}
    <button class="go" id="wmRoomGo" ${r.can_start && r.host ? '' : 'disabled'}>
      ${r.host ? '🚀 เริ่มเกม' : '⏳ รอหัวห้องกดเริ่ม'}</button>
    <button class="go" id="wmRoomOut" style="background:none;color:var(--g-muted);
      border-color:var(--g-line)">🚪 ออกจากห้อง</button>`;
  box.querySelectorAll('[data-plan]').forEach(b =>
    b.onclick = () => wmRoomDo('plan', { plan: b.dataset.plan }));
  box.querySelectorAll('[data-team]').forEach(b =>
    b.onclick = () => wmRoomDo('team', { team: +b.dataset.team }));
  bindInviteButtons(box, 'worms');
  document.getElementById('wmRoomGo').onclick = () => wmRoomDo('start');
  document.getElementById('wmRoomOut').onclick = () => wmRoomDo('leave');
}
