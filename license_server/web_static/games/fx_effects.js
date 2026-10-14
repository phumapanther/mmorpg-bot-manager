// 🎨 คลังเอฟเฟกต์อิมแพกต์ — วาดด้วย canvas 2D สไตล์พิกเซล ไม่ใช้ไฟล์ภาพ
// สร้างเทียบเคียงสไตล์ anime-impact VFX · ใช้ได้ทั้งห้องแล็บ (/fxlab) และในเกม
// สัญญา: FX.<key> = { label, loop, params:[{key,label,min,max,step,def}], colors:[{key,label,def}], draw(ctx,cx,cy,s,p,t) }
//   p = ค่าทุก param + ทุก color รวมกัน · t = เลขเฟรม (เพิ่มทีละ 1) · เอฟเฟกต์วนลูปที่ t % loop
window.FX = window.FX || {};

FX.slash = {
  label: 'รอยฟันเฉียง',
  loop: 90,                                             // พรีวิววนด้วย t % 90
  params: [
    {key:'count',     label:'จำนวนรอย', min:1, max:5,  step:1, def:3},
    {key:'thickness', label:'ความหนา',  min:1, max:5,  step:1, def:3},
    {key:'angle',     label:'องศาเอียง', min:-60, max:60, step:5, def:35},
    {key:'length',    label:'ความยาว',  min:6, max:18, step:1, def:14},
  ],
  colors: [
    {key:'c1', label:'สีขอบ',  def:'#176fa6'},
    {key:'c2', label:'สีตัว',   def:'#5fd0ff'},
    {key:'c3', label:'แกนขาว', def:'#ffffff'},
  ],
  draw(ctx, cx, cy, s, p, t) {
    ctx.save();
    const PER = 90;                                     // ต้องตรงกับ loop (วนเนียน)
    const PI = Math.PI;
    const snap = v => Math.round(v / s) * s;            // บังคับลงช่องพิกเซล
    const px = (x, y, w, h, c) => { ctx.fillStyle = c;
      ctx.fillRect(snap(x), snap(y), Math.max(s, snap(w)), Math.max(s, snap(h))); };

    const count = Math.round(p.count);
    const L = p.length * s;                             // ครึ่งความยาวรอย
    const baseTh = p.thickness * s;                     // ความหนากลางรอย
    const N = Math.max(10, Math.round(p.length * 2));   // จำนวนก้อนตลอดรอย
    const sweep = 0.22;                                 // สัดส่วนเวลาช่วง "ลากดาบ"
    const spread = 16 * PI / 180;                       // กางรอยเป็นพัด

    for (let i = 0; i < count; i++) {
      // เฟสรอยนี้ 0..1 เหลื่อมเวลากัน · วนลูปเนียนเพราะอิง t % PER
      const ph = ((t + i * PER / count) % PER) / PER;
      const appear = ph < sweep ? ph / sweep : 1;       // เผยรอยจากหัว→ท้าย
      let a = ph < sweep ? 0.5 + 0.5 * (ph / sweep)     // วาบสว่างขึ้นตอนลาก
                         : 1 - (ph - sweep) / (1 - sweep); // แล้วจางหาย (a→0 ที่ ph→1)
      if (a <= 0) continue;

      const mid = (count - 1) / 2;
      const ang = p.angle * PI / 180 + (i - mid) * spread;
      const dx = Math.cos(ang), dy = Math.sin(ang);
      const nx = -dy, ny = dx;                          // แกนตั้งฉาก (เลื่อนรอยไม่ให้ทับกันสนิท)
      const off = (i - mid) * 2 * s;

      const uMax = -1 + 2 * appear;
      for (let k = 0; k <= N; k++) {
        const u = -1 + 2 * k / N;
        if (u > uMax) break;
        const prof = baseTh * Math.sqrt(1 - u * u);     // ทรงเลนส์: อ้วนกลาง เรียวปลาย
        if (prof < s) continue;
        const bx = cx + u * L * dx + off * nx;
        const by = cy + u * L * dy + off * ny;
        const core = Math.max(s, prof * 0.4);

        ctx.globalAlpha = a * 0.9;
        px(bx - prof, by - prof, prof * 2, prof * 2, p.c1);                 // ขอบเข้ม
        ctx.globalAlpha = a;
        px(bx - prof * 0.6, by - prof * 0.6, prof * 1.2, prof * 1.2, p.c2); // ตัว
        px(bx - core, by - core, core * 2, core * 2, p.c3);                 // แกนขาว
      }
    }
    ctx.globalAlpha = 1;                                // คืนค่าก่อนจบ
    ctx.restore();
  },
};

FX.lightning = {
  label: 'สายฟ้าฟาด',
  loop: 90,                                  // วนครบ 1 รอบทุก 90 เฟรม
  params: [
    {key:'branches',  label:'กิ่งย่อย',    min:0, max:3, step:1, def:2},
    {key:'jitter',    label:'ความหักเห',  min:1, max:8, step:1, def:4},
    {key:'thickness', label:'ความหนา',    min:1, max:3, step:1, def:1},
    {key:'strikes',   label:'ฟาด/รอบ',    min:1, max:4, step:1, def:2},
  ],
  colors: [
    {key:'c1', label:'สีขอบ',    def:'#4a2d8f'},  // ขอบเข้ม
    {key:'c2', label:'สีตัว',    def:'#7b6cff'},  // ตัวสายฟ้า
    {key:'c3', label:'แกนสว่าง', def:'#ffffff'},  // แกนวาบขาว
  ],
  draw(ctx, cx, cy, s, p, t) {
    ctx.save();
    const L = 90;                                  // = loop (ใช้คำนวณจังหวะฟาด)
    const snap = v => Math.round(v / s) * s;       // บังคับลงช่องพิกเซล
    const px = (gx, gy, w, h, c, a) => {           // ก้อนพิกเซล 1 ก้อน
      ctx.globalAlpha = a; ctx.fillStyle = c;
      ctx.fillRect(snap(gx), snap(gy), Math.max(s, snap(w)), Math.max(s, snap(h)));
    };

    // ── จังหวะ: แบ่งรอบเป็น strikes หน้าต่าง แต่ละหน้าต่างฟาด 1 ที ──
    const win   = L / p.strikes;                   // ความยาวหน้าต่าง 1 การฟาด
    const si    = Math.floor((t % L) / win);       // ฟาดครั้งที่เท่าไรในรอบนี้
    const lt    = (t % L) - si * win;              // เฟรมนับจากเริ่มฟาดครั้งนี้
    const seed  = si * 2.7 + 1;                     // ทำให้รูปแต่ละครั้งต่างกัน (ไม่ random)
    const flash = Math.max(0, 1 - lt / (win * 0.45)); // วาบจัดตอนต้นแล้วจางเร็ว
    // จางหมดก่อนปลายหน้าต่าง → t=loop-1 มืดสนิทต่อกับ t=0 ได้ไม่กระตุก
    if (flash <= 0.001) { ctx.globalAlpha = 1; ctx.restore(); return; }

    const top = cy - 20 * s, N = 11, th = p.thickness * s; // เริ่มจากขอบบน ลง 20 ช่อง
    // ── ข้อหักของเส้นหลัก: x เฉจาก sin(index+seed) แล้วบีบเข้าหา cx ตอนปลาย ──
    const nx = [], ny = [];
    for (let i = 0; i <= N; i++) {
      const f = i / N;
      ny[i] = top + f * (cy - top);
      const wob = Math.sin(i * 1.7 + seed * 3) + Math.sin(i * 0.6 + seed);
      nx[i] = cx + wob * p.jitter * s * (1 - f);
    }
    nx[N] = cx; ny[N] = cy;                         // ปลายล็อกที่ (cx,cy)

    // เดินทีละช่วงแล้วหยอดพิกเซล 3 โทนซ้อน (ขอบกว้าง→ตัว→แกนสว่างบาง)
    const drawBolt = (xs, ys, n) => {
      for (let i = 0; i < n; i++) {
        const x0 = xs[i], y0 = ys[i], x1 = xs[i+1], y1 = ys[i+1];
        const steps = Math.max(1, Math.round((y1 - y0) / s));
        for (let k = 0; k <= steps; k++) {
          const u = k / steps, x = x0 + (x1 - x0) * u, y = y0 + (y1 - y0) * u;
          px(x - th - s, y, th * 2 + 2 * s, s, p.c1, 0.5 * flash);
          px(x - th,     y, th * 2,         s, p.c2, 0.85 * flash);
          px(x,          y, th,             s, p.c3, flash);
        }
      }
    };
    drawBolt(nx, ny, N);

    // ── กิ่งย่อย: แตกจากข้อกลาง ๆ สลับซ้าย-ขวา เฉออกข้างแล้วลง ──
    for (let b = 0; b < p.branches; b++) {
      const bi = 3 + b * 2 + (si % 2);              // ข้อเริ่มกิ่ง (จาก b,si ไม่ random)
      if (bi >= N - 1) continue;
      const dir = (b % 2 === 0) ? 1 : -1;
      const bx = [nx[bi]], by = [ny[bi]], bn = 3;   // ยาว 3 ช่วง
      for (let j = 1; j <= bn; j++) {
        bx[j] = bx[j-1] + dir * (2 + Math.sin(j + seed + b)) * p.jitter * 0.5 * s;
        by[j] = by[j-1] + (2 + j) * s;
      }
      drawBolt(bx, by, bn);
    }

    // แสงวาบจาง ๆ รอบจุดตก
    const glow = th + 3 * s;
    px(cx - glow, cy - glow, glow * 2, glow * 2, p.c3, 0.12 * flash);

    ctx.globalAlpha = 1;
    ctx.restore();
  },
};

FX.crystal = {
  label: 'ผลึกแทงพื้น',
  loop: 90,                                  // พรีวิววนด้วย t % 90
  params: [
    { key: 'spikes', label: 'จำนวนแท่ง', min: 3, max: 8,  step: 1, def: 5 },
    { key: 'height', label: 'ความสูง',   min: 4, max: 18, step: 1, def: 11 },
    { key: 'spread', label: 'การกระจาย', min: 2, max: 10, step: 1, def: 7 },
    { key: 'rise',   label: 'ความเร็วผุด', min: 1, max: 6, step: 1, def: 3 },
  ],
  colors: [
    { key: 'c1', label: 'สีขอบ',   def: '#3b1e78' },   // ขอบเข้ม
    { key: 'c2', label: 'สีตัว',   def: '#8a4fe0' },   // เนื้อผลึก
    { key: 'c3', label: 'แกนสว่าง', def: '#e6d2ff' },  // ไฮไลต์
  ],
  draw(ctx, cx, cy, s, p, t) {
    ctx.save();
    const snap = v => Math.round(v / s) * s;                    // บังคับลงช่องพิกเซล
    const px = (gx, gy, w, h, c) => { ctx.fillStyle = c;
      ctx.fillRect(snap(gx), snap(gy), Math.max(s, snap(w)), Math.max(s, snap(h))); };

    const n = Math.round(p.spikes);
    const f = (t % 90) / 90;                                    // 0..1 ความคืบหน้าในรอบ (= loop ด้านบน)
    const riseP = Math.min(0.5, Math.max(0.08, 0.5 / p.rise));  // ช่วงเวลาผุด (rise สูง = ผุดไว)
    const groundY = cy + 4 * s;                                 // แนวพื้นที่ผลึกโผล่
    const half = p.spread * s;                                  // ครึ่งความกว้างการกระจาย

    // แสงเรืองที่พื้น เต้นเบา ๆ ตาม t
    ctx.globalAlpha = 0.12 + 0.06 * Math.sin(t / 7);
    px(cx - half - s, groundY, half * 2 + 3 * s, s, p.c3);

    for (let i = 0; i < n; i++) {
      // ตำแหน่งแนวนอน กระจายเท่า ๆ กันรอบ cx
      const bx = cx + (n === 1 ? 0 : (i / (n - 1) - 0.5) * 2 * half);
      const st = (i / n) * 0.12;                                // สลับเวลาผุดทีละแท่ง

      // envelope: ผุดขึ้น → ค้าง → หด/จาง (หัวท้ายรอบเป็น 0 ต่อกันเนียน)
      let env;
      if (f < st) env = 0;
      else if (f < st + riseP) env = (f - st) / riseP;          // ค่อย ๆ ผุด
      else if (f < 0.75) env = 1;                               // ค้างไว้
      else env = Math.max(0, (1 - f) / 0.25);                   // หดช่วงท้าย
      if (env <= 0) continue;

      const hVar = (i % 2 === 0) ? 1 : 0.62;                    // สูงต่ำสลับ
      const rows = Math.round(p.height * hVar * env);
      if (rows < 1) continue;
      const baseW = Math.max(2, Math.round(rows * 0.45));       // ฐานกว้างตามความสูง
      const hiA = 0.55 + 0.35 * Math.sin(t / 6 + i);            // ไฮไลต์วิบวับ

      for (let r = 0; r < rows; r++) {
        const frac = r / rows;                                  // 0 ฐาน .. ~1 ปลาย
        const wg = Math.max(1, Math.round(baseW * (1 - frac))); // เรียวแหลมขึ้นปลาย
        const x = bx - (wg * s) / 2;
        const y = groundY - (r + 1) * s;
        ctx.globalAlpha = 0.9 * env;
        px(x, y, wg * s, s, p.c2);                              // เนื้อผลึก
        ctx.globalAlpha = 0.95 * env;
        px(x + (wg - 1) * s, y, s, s, p.c1);                    // ขอบเข้มด้านขวา
        if (frac > 0.35) {                                      // ไฮไลต์ซ้ายบน
          ctx.globalAlpha = hiA * env;
          px(x, y, s, s, p.c3);
        }
      }
    }
    ctx.globalAlpha = 1;
    ctx.restore();
  },
};

FX.petal = {
  label: 'กลีบดอกหมุน',
  loop: 120,                                   // พรีวิววนด้วย t % 120
  params: [
    {key:'count',  label:'จำนวนกลีบ', min:4, max:12, step:1, def:8},
    {key:'radius', label:'รัศมีวง',   min:2, max:16, step:1, def:8},
    {key:'rise',   label:'ลอยสูง',    min:0, max:20, step:1, def:12},
    {key:'spin',   label:'ความเร็วหมุน', min:1, max:6, step:1, def:2},  // รอบต่อ 1 ลูป (เลขเต็ม → วนเนียน)
    {key:'size',   label:'ขนาดกลีบ',  min:1, max:4,  step:1, def:2},
  ],
  colors: [
    {key:'c1', label:'สีขอบ',   def:'#7a2d5a'},  // ขอบเข้ม
    {key:'c2', label:'สีตัว',   def:'#e86aa6'},  // ตัวกลีบ
    {key:'c3', label:'แกนสว่าง', def:'#ffd6ec'},  // แกนสว่าง
  ],
  draw(ctx, cx, cy, s, p, t) {
    ctx.save();
    const snap = v => Math.round(v / s) * s;                 // บังคับลงช่องพิกเซล
    const px = (gx, gy, w, h, c) => { ctx.fillStyle = c;
      ctx.fillRect(snap(gx), snap(gy), Math.max(s, snap(w)), Math.max(s, snap(h))); };
    const TAU = Math.PI * 2, L = 120, n = p.count;
    for (let i = 0; i < n; i++) {
      const phase = ((t / L) + i / n) % 1;                   // เฟสกลีบ 0..1 (วนครบที่ t=loop)
      const a = Math.sin(phase * Math.PI);                   // จาง: 0→1→0 ต่อหัวท้ายเนียน
      if (a <= 0) continue;
      const ang = i / n * TAU + (t / L) * TAU * p.spin;       // มุมโคจร = index + t*ความเร็ว (รอบเต็ม → ไม่กระตุก)
      const r = p.radius * s;
      const x = cx + Math.cos(ang) * r;                      // วงรีมองเฉียง (y แบน) + ค่อย ๆ ลอยขึ้น
      const y = cy + Math.sin(ang) * r * 0.5 - phase * p.rise * s;
      const w = p.size * s;
      px(x - w / 2, y - w / 2, w, w, p.c1);                  // ขอบเข้ม (ก้อนเต็ม) — alpha เต็ม a
      ctx.globalAlpha = a;
      px(x - w / 2 + s, y - w / 2, w - s * 2, w - s, p.c2);  // ตัวกลีบ (หดเข้า 1 ช่อง)
      px(x - s / 2, y - w / 2, s, s, p.c3);                  // แกนสว่าง (ช่องบนสุด)
      ctx.globalAlpha = a * 0.85;                            // ตั้งค่าให้ก้อนขอบรอบถัดไป
    }
    ctx.globalAlpha = 1;
    ctx.restore();
  },
};

FX.meteor = {
  label: 'อุกกาบาต',
  loop: 90,                                            // วนครบรอบทุก 90 เฟรม
  params: [
    {key:'tail',   label:'ความยาวหาง',  min:4, max:14, step:1, def:9},
    {key:'size',   label:'ขนาดหัว',      min:1, max:4,  step:1, def:2},
    {key:'speed',  label:'ความเร็ว',     min:1, max:4,  step:1, def:2},
    {key:'sparks', label:'ประกายกระแทก', min:4, max:16, step:1, def:9},
  ],
  colors: [
    {key:'c1', label:'สีขอบ',    def:'#7a1f0a'},        // หางด้านนอก/เถ้าเข้ม
    {key:'c2', label:'สีไฟ',     def:'#ff7b2e'},        // ตัวเปลวส้ม
    {key:'c3', label:'แกนสว่าง', def:'#ffe9a8'},        // หัว/แกนร้อนสว่าง
  ],
  draw(ctx, cx, cy, s, p, t) {
    ctx.save();
    const snap = v => Math.round(v / s) * s;            // บังคับลงช่องพิกเซล
    const px = (gx, gy, w, h, c, a) => {                // ก้อนพิกเซลเดียว
      ctx.globalAlpha = a < 0 ? 0 : a > 1 ? 1 : a;
      ctx.fillStyle = c;
      ctx.fillRect(snap(gx), snap(gy), Math.max(s, snap(w)), Math.max(s, snap(h)));
    };
    const loop = 90;
    const ph = (t % loop) / loop;                        // 0..1 ของรอบนี้
    // speed สูง = หัวถึงเร็ว เหลือเวลาโชว์ประกายมากขึ้น
    const flightEnd = 0.68 - (p.speed - 1) * 0.08;       // ช่วงเวลาที่ใช้บิน
    const dist = 19 * s;                                 // ระยะเริ่มทแยงมุมบน
    const dgx = Math.SQRT1_2, dgy = Math.SQRT1_2;        // ทิศพุ่ง (ลง-ขวา)
    const sx = cx - dist * dgx, sy = cy - dist * dgy;    // จุดเกิดมุมบนซ้าย

    if (ph < flightEnd) {
      // ── ช่วงบิน: หัวไล่จากมุมบนลงมากระแทกที่ (cx,cy) ──
      const f = ph / flightEnd;                          // 0..1
      const fin = Math.min(1, f * 6);                    // เฟดเข้าตอนโผล่ → ต่อ loop เนียน
      const hx = sx + (cx - sx) * f;
      const hy = sy + (cy - sy) * f;
      const hw = p.size * s;
      // หาง: ไล่ถอยหลังตามทิศพุ่ง c3(หัว)→c2→c1(ปลาย) จางลงเรื่อย ๆ
      for (let i = p.tail; i >= 0; i--) {
        const flick = 1 + 0.35 * Math.sin(t / 3 + i);    // ไฟสั่นเล็กน้อย
        const bx = hx - dgx * i * s * flick;
        const by = hy - dgy * i * s * flick;
        const k = i / p.tail;                            // 0=หัว 1=ปลายหาง
        const col = k < 0.35 ? p.c3 : k < 0.7 ? p.c2 : p.c1;
        const sz = Math.max(s, (p.size - k * p.size * 0.8) * s);
        px(bx - sz / 2, by - sz / 2, sz, sz, col, ((1 - k) * 0.9 + 0.1) * fin);
      }
      // แกนหัวร้อนสว่าง
      px(hx - hw / 2, hy - hw / 2, hw, hw, p.c3, fin);
    } else {
      // ── ช่วงกระแทก: แฟลช + ประกายพุ่งออก + คลื่นแผ่ (จางหายท้าย loop) ──
      const g = (ph - flightEnd) / (1 - flightEnd);      // 0..1
      const fade = 1 - g;                                // ท้าย loop = 0 → ต่อ t=0 เนียน
      px(cx - 2.5 * s, cy - 2.5 * s, 5 * s, 5 * s, p.c3, fade * fade * 0.8); // แฟลชแรก
      const rr = g * 16 * s;                             // รัศมีคลื่น
      for (let a = 0; a < p.sparks; a++) {
        const ang = (a / p.sparks) * Math.PI * 2;
        const ca = Math.cos(ang), sa = Math.sin(ang);
        const ex = cx + ca * rr;                         // ประกายพุ่งออก
        const ey = cy + sa * rr * 0.7 + g * g * 5 * s;   // + ตกตามแรงโน้มถ่วงนิด ๆ
        const col = g < 0.4 ? p.c3 : g < 0.75 ? p.c2 : p.c1;
        px(ex - s, ey - s, 2 * s, 2 * s, col, fade);
        px(cx + ca * rr * 0.6 - s / 2, cy + sa * rr * 0.6 - s / 2, s, s, p.c2, fade * 0.7); // วงใน
      }
    }
    ctx.globalAlpha = 1;
    ctx.restore();
  },
};

FX.runecircle = {
  label: 'วงเวทรูน',
  loop: 120,                                  // พรีวิววนด้วย t % 120
  params: [
    { key:'rings',  label:'จำนวนวง',       min:1, max:3,  step:1, def:2 },
    { key:'runes',  label:'ขีดรูนต่อวง',   min:4, max:16, step:1, def:10 },
    { key:'radius', label:'รัศมี',          min:6, max:18, step:1, def:14 },
    { key:'spin',   label:'รอบหมุน/ลูป',    min:1, max:4,  step:1, def:1 },
    { key:'tilt',   label:'ความแบน',        min:2, max:9,  step:1, def:5 },
  ],
  colors: [
    { key:'c1', label:'สีขอบ',     def:'#3a2a6a' },
    { key:'c2', label:'สีตัว',     def:'#7a5cff' },
    { key:'c3', label:'แกนสว่าง',  def:'#d9ccff' },
  ],
  draw(ctx, cx, cy, s, p, t) {
    ctx.save();
    const TAU = Math.PI * 2;
    const snap = v => Math.round(v / s) * s;                 // บังคับลงช่องพิกเซล
    const px = (gx, gy, c, a) => {                           // ก้อนพิกเซล 1 ช่อง
      ctx.globalAlpha = a < 0 ? 0 : (a > 1 ? 1 : a);
      ctx.fillStyle = c;
      ctx.fillRect(snap(gx), snap(gy), s, s);
    };
    const ph = (t % 120) / 120;                              // 0..1 วนครบ 1 รอบ
    const ratio = 0.55 - p.tilt * 0.05;                      // ยิ่ง tilt มาก ยิ่งแบน (วางบนพื้น)
    const pulse = 0.6 + 0.3 * Math.sin(TAU * ph);            // เรืองแสงเต้นเบา ๆ ทั้งวง

    for (let i = 0; i < p.rings; i++) {
      const dir = i % 2 ? -1 : 1;                            // วงสลับทิศหมุน
      const spin = dir * TAU * p.spin * ph;                  // หมุน p.spin รอบ/ลูป → ต่อเนียน
      const rr = p.radius * s * (1 - i * 0.26);              // วงในเล็กลงเป็นชั้น
      const col = i === 0 ? p.c2 : p.c1;
      // ── เส้นวงรีแบน (แถบสว่างไหลรอบวง) ──
      const seg = 54;
      for (let k = 0; k < seg; k++) {
        const a = TAU * k / seg + spin;
        const bright = 0.5 + 0.5 * Math.sin(a * 2 - TAU * ph * 2);
        px(cx + Math.cos(a) * rr, cy + Math.sin(a) * rr * ratio,
           bright > 0.75 ? p.c3 : col, pulse * (0.45 + 0.55 * bright));
      }
      // ── ขีดอักขระรูนรอบวง (พุ่งออกนอก กะพริบไม่พร้อมกัน) ──
      for (let j = 0; j < p.runes; j++) {
        const a = TAU * j / p.runes + spin;
        const ca = Math.cos(a), sa = Math.sin(a) * ratio;
        const flick = 0.55 + 0.45 * Math.sin(TAU * ph * 2 + j + i);
        for (let d = 0; d <= 2; d++) {
          const rd = rr + d * s;
          px(cx + ca * rd, cy + sa * rd, d === 2 ? p.c3 : p.c2, pulse * flick);
        }
      }
    }
    // ── แกนเรืองแสงกลางวง ──
    const core = pulse * 0.7;
    px(cx, cy, p.c3, core);
    px(cx - s, cy, p.c3, core * 0.6);
    px(cx + s, cy, p.c3, core * 0.6);

    ctx.globalAlpha = 1;                                     // คืนค่าก่อนจบ
    ctx.restore();
  },
};
