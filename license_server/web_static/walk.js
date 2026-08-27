// 🏃 กฎการเดิน — สำเนาฝั่งเบราว์เซอร์ของ bot/pvp/physics.py
//
// ⚠️ อ่านตรงนี้ก่อนแก้อะไรในไฟล์นี้
//
// กติกาเหล็กเดิมคือ "เบราว์เซอร์ไม่มีกฎเกม" ไฟล์นี้ดูเหมือนขัดกติกา แต่ไม่ขัด
// เพราะเซิร์ฟเวอร์ยังเป็นคนตัดสินตำแหน่งจริงทุกครั้งเหมือนเดิม — ไฟล์นี้ทำแค่
// "เดาไว้ก่อน" ให้ตัวละครขยับทันทีที่นิ้วแตะปุ่ม แล้วเซิร์ฟเวอร์ตามมายืนยันทีหลัง
// API ยังไม่รับพิกัดจากเบราว์เซอร์เลยสักตัว รับแค่ "กดทิศไหนไปกี่ก้าว"
//
// ทำไมต้องมี: เซิร์ฟเวอร์อยู่หลัง Cloudflare tunnel วัดแล้วไปกลับครั้งละ ~300 ms
// โมเดลเดิม (กด → ถามเซิร์ฟเวอร์ → รอ → เล่นภาพ) จึงได้ 6 พิกเซลต่อครึ่งวินาที
// และนิ้วปล่อยไปแล้วตัวยังเดินต่อ — คุมไม่ได้เลย
// hedgewars ใช้ธงปุ่มที่กดค้างแล้วขยับทุก 8 ms (uGearsHedgehog.pas:920)
// เราทำแบบเดียวกันฝั่งจอ แล้วให้เซิร์ฟเวอร์คำนวณซ้ำจากอินพุตชุดเดียวกัน
//
// ⚠️ ห้ามแก้ไฟล์นี้โดยไม่แก้ physics.py ให้ตรงกัน — มีเทสบังคับว่าสองฝั่งต้องได้
//    ผลเหมือนกันเป๊ะทุกพิกเซล (tests/test_worms_predict.py) เพี้ยนเมื่อไหร่เทสแดง

const WALK = (() => {
  const AIR_M = 0, LEAF_M = 7;              // ต้องตรงกับ terrain.AIR / terrain.LEAF

  /** ค่าคงที่ทั้งหมดมาจากเซิร์ฟเวอร์ ไม่ฝังตัวเลขไว้ที่นี่ (กันสองฝั่งเพี้ยนจากกัน) */
  function rules(st) {
    return st.rules || {};
  }

  function material(map, x, y) {
    x |= 0; y |= 0;
    return (x >= 0 && x < map.w && y >= 0 && y < map.h) ? map.at(x, y) : AIR_M;
  }

  function solid(map, x, y) {
    return material(map, x, y) !== AIR_M;
  }

  /** กล่องตัวละครที่เท้าอยู่ (x, y) ว่างไหม — ใบไม้ไม่กั้น (เดินลอดพุ่มไม้ได้) */
  function clear(map, r, x, y) {
    for (let gy = y - r.ch_h; gy < y; gy++)
      for (let gx = x - r.foot_w; gx <= x + r.foot_w; gx++) {
        const m = material(map, gx, gy);
        if (m !== AIR_M && m !== LEAF_M) return false;
      }
    return true;
  }

  /** ยืนตรงนี้ได้ไหม — ตัวไม่จมกำแพง และมีพื้นรองใต้ฝ่าเท้า */
  function standable(map, r, x, y) {
    if (!(x >= 0 && x < map.w && y >= 0 && y < map.h - r.water)) return false;
    if (!clear(map, r, x, y)) return false;
    for (let gx = x - r.foot_w; gx <= x + r.foot_w; gx++)
      if (solid(map, gx, y)) return true;
    return false;
  }

  /** ปล่อยให้ตกจนถึงพื้น — คืน {x, y, fell, drowned} */
  function settle(map, r, x, y) {
    for (let gy = y; gy < map.h - r.water; gy++)
      if (standable(map, r, x, gy)) return { x: x, y: gy, fell: gy - y, drowned: false };
    const floor = map.h - r.water;
    return { x: x, y: floor, fell: floor - y, drowned: true };
  }

  const BLOCKED = 'blocked', MOVED = 'moved', DROWNED = 'drowned';

  /** ก้าวหนึ่งก้าว — ปีนขั้นได้ไม่เกิน climb · ห้ามก้าวลงทะเลเมื่อ noDrown */
  function step(map, r, x, y, dir, noDrown) {
    const nx = x + dir;
    if (!(nx >= 0 && nx < map.w)) return { how: BLOCKED, x: x, y: y };
    for (let ny = y - r.climb; ny <= y; ny++)      // ลองปีนขึ้นก่อน แล้วค่อยระดับเดิม
      if (standable(map, r, nx, ny)) return { how: MOVED, x: nx, y: ny };
    if (!clear(map, r, nx, y)) return { how: BLOCKED, x: x, y: y };
    const s = settle(map, r, nx, y);              // ไม่มีพื้นข้างหน้า = ตกลงไป
    if (noDrown && s.drowned) return { how: BLOCKED, x: x, y: y };
    return { how: s.drowned ? DROWNED : MOVED, x: s.x, y: s.y };
  }

  /** เดินหลายก้าว — คืน {x, y, steps, drowned} · steps = ก้าวที่เดินได้จริง */
  function walk(map, r, x, y, dir, steps, noDrown) {
    let cx = x, cy = y, used = 0, drowned = false;
    const cap = Math.max(0, Math.min(steps | 0, r.step_max));
    for (let i = 0; i < cap; i++) {
      const s = step(map, r, cx, cy, dir, noDrown);
      if (s.how === BLOCKED) break;
      cx = s.x; cy = s.y; used++;
      if (s.how === DROWNED) { drowned = true; break; }
    }
    return { x: cx, y: cy, steps: used, drowned: drowned, fell: Math.max(0, cy - y) };
  }

  /** 🦘 ตั้งต้นการกระโดด — คืน "สภาพการลอย" ที่เอาไปเดินทีละเฟรมได้

      ⚠️ จงใจแยกเป็น start/step แทนที่จะคำนวณวิถีทั้งเส้นรวดเดียว
         เจ้าของเกมสั่ง: "จุดลงพื้นไม่ควรถูกกำหนดไว้ล่วงหน้า ต้องคำนวณต่อเนื่อง
         จากจุดที่อยู่ปัจจุบันแบบเรียลไทม์" — ตัวจึงลอยไปตามฟิสิกส์จริงทีละเฟรม
         ไม่ใช่เล่นเทปวิถีที่คิดจบไปแล้ว
   */
  function jumpStart(r, x, y, dir, power, lean) {
    power = Math.pow(Math.max(0, Math.min(1, power)), r.jump_curve);
    return {
      x: x, y: y,
      vx: r.jump_vx * dir * (0.10 + 0.90 * power),
      vy: r.jump_vy * (0.28 + 0.72 * power),
      lean: Math.max(-1, Math.min(1, lean)),
      top: y, frames: 0, done: false, landed: false, drowned: false, bump: null,
    };
  }

  /** เดินการลอยไปหนึ่งเฟรม — คืน [x, y] ที่ต้องวาด หรือ null ถ้าจบแล้ว */
  function jumpStep(map, r, f) {
    if (f.done) return null;
    if (++f.frames > 200) { f.done = true; return null; }   // กันลอยวนไม่จบ
    f.vy += r.gravity;
    f.vx = Math.max(-r.air_max, Math.min(r.air_max, f.vx + r.air_accel * f.lean));
    let nx = f.x + f.vx;
    const ny = f.y + f.vy;
    let ix = Math.round(nx);
    const iy = Math.round(ny);
    if (!(ix >= 0 && ix < map.w)) {           // ชนขอบแผนที่ เด้งกลับเบา ๆ
      f.vx = -f.vx * .4;
      nx = f.x;
      ix = Math.round(nx);
    }
    if (iy >= map.h - r.water) {              // ถึงผิวน้ำ — จมหายไป
      f.x = ix; f.y = map.h - r.water;
      f.done = true; f.drowned = true;
      return [f.x, f.y];
    }
    if (!clear(map, r, ix, iy)) {             // หัวหรือตัวชน — หยุดพุ่ง แล้วร่วงลง
      f.bump = [ix, iy];
      f.done = true;
      return null;
    }
    f.x = nx; f.y = ny;
    f.top = Math.min(f.top, iy);
    if (f.vy > 0 && standable(map, r, ix, iy)) {
      f.x = ix; f.y = iy;
      f.done = true; f.landed = true;
      return [ix, iy];
    }
    return [ix, iy];
  }

  /** วิถีกระโดดทั้งเส้น — ใช้ตัวเดินทีละเฟรมข้างบนวนจนจบ ไม่ได้เขียนสูตรซ้ำ

      เก็บไว้ให้เทสเทียบกับ physics.jump() ฝั่งเซิร์ฟเวอร์ได้ทั้งเส้น
   */
  function jump(map, r, x, y, dir, power, lean) {
    const f = jumpStart(r, x, y, dir, power, lean);
    const path = [];
    let pt;
    while ((pt = jumpStep(map, r, f)) !== null) {
      path.push(pt);
      if (f.done) break;
    }
    if (f.drowned) {
      for (let gy = f.y + 1; gy < f.y + r.sink; gy++) path.push([f.x, gy]);
      return { path: path, x: f.x, y: f.y, drowned: true, fell: 0, bump: null };
    }
    if (f.landed)
      return { path: path, x: f.x, y: f.y, drowned: false,
               fell: Math.max(0, f.y - f.top), bump: null };
    // หัวชนหรือลอยครบเพดานเฟรม — ร่วงลงจากตรงนั้น
    const s = settle(map, r, Math.round(f.x), Math.round(f.y));
    for (let gy = Math.round(f.y) + 1; gy < s.y; gy++) path.push([s.x, gy]);
    path.push([s.x, s.y]);
    if (s.drowned)
      for (let gy = s.y + 1; gy < s.y + r.sink; gy++) path.push([s.x, gy]);
    return { path: path, x: s.x, y: s.y, drowned: s.drowned, bump: f.bump,
             fell: Math.max(0, s.y - f.top) };
  }

  return { rules, standable, settle, step, walk, jump, jumpStart, jumpStep,
           BLOCKED, MOVED, DROWNED };
})();
