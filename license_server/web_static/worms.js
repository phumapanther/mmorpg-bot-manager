// 🪱 สนามรบผลัดเทิร์น — ตัววาดแผนที่ + กล้อง (หมวด PVP)
//
// ไฟล์นี้ "ไม่มีกฎเกมเลย" — พื้นอยู่ตรงไหน ใครยืนที่ไหน ตัดสินที่เซิร์ฟเวอร์ทั้งหมด
// ที่นี่รับกริดวัสดุมาวาด กับเจาะหลุมตามที่เซิร์ฟเวอร์บอกเท่านั้น
//
// แผนที่ใหญ่กว่าจอ จึงมีกล้อง: ซูมเข้าออก · ลากเลื่อน · กดชื่อคนเพื่อกระโดดไปดู
// ซูมเป็นจำนวนเต็มเท่านั้น (1× 2× 3× 4×) พิกเซลจะได้คมเสมอ ไม่มีวันเบลอ

// วัสดุ — เลขตรงกับ bot/pvp/terrain.py (มีเทสคุมว่าตรงกัน)
const AIR = 0, GRASS = 1, DIRT = 2, ROCK = 3, WOOD = 4, BRICK = 5, TRUNK = 6, LEAF = 7;

// สีรายทวีป — ท้องฟ้าใช้ MAPS ของ scene.js ร่วมกัน ตรงนี้มีเฉพาะส่วนที่ scene.js ไม่มี
// ลำดับ: [หญ้า, ดิน, หิน, ไม้บ้าน, อิฐปราสาท, ลำต้น, ใบไม้]
const WORM_GROUND = {
  main:       ['#6fa84e', '#6b5433', '#4a3f30', '#8a5a30', '#8f8c86', '#5a3d22', '#4f8a3a'],
  demon:      ['#a84a6a', '#4a2030', '#3a1626', '#6a2a3a', '#6e5a66', '#3a1a24', '#7a2a4a'],
  frozen:     ['#cfe6f2', '#5f7d92', '#48606f', '#7a6a58', '#9fb4c4', '#4a3f38', '#8fbcd0'],
  nether:     ['#c85a2a', '#5a2716', '#3d1a10', '#7a3a1a', '#7a6058', '#40200f', '#8a3a18'],
  volcanic:   ['#c87a3a', '#4a2c1e', '#332028', '#6a3a22', '#6e6068', '#3a2016', '#8a4a24'],
  sylvan:     ['#7fc255', '#4a3a20', '#33301f', '#7a5a2a', '#8a8a70', '#4a3418', '#4f8a3a'],
  mechanized: ['#8a8a70', '#4a4436', '#3a3a42', '#7a6a48', '#9a9a92', '#4a4030', '#6a7a58'],
  skyward:    ['#bfd8f0', '#6a6f90', '#4c5474', '#8a7f9a', '#b0bcd8', '#4a4560', '#9fb8e0'],
  ocean:      ['#5fc0b0', '#1f5a5e', '#173f4e', '#4a6a5a', '#7a9aa0', '#274a48', '#3f9a8a'],
};
const ZOOM_MAX = 5;

/** RLE `วัสดุ:จำนวน` รายแถว → Uint8Array แบนราบ */
function decodeTerrain(text, w, h) {
  const g = new Uint8Array(w * h);
  const rows = text.split(';');
  for (let y = 0; y < h && y < rows.length; y++) {
    let x = 0;
    for (const part of rows[y].split(',')) {
      const c = part.indexOf(':');
      const m = +part.slice(0, c), n = +part.slice(c + 1);
      if (m) g.fill(m, y * w + x, y * w + Math.min(w, x + n));
      x += n;
      if (x >= w) break;
    }
  }
  return g;
}

class WormsMap {
  constructor(data) {
    this.w = data.w; this.h = data.h; this.water = data.water;
    this.seed = data.seed;
    this.continent = data.continent || 'main';
    this.props = data.props || [];
    this.g = decodeTerrain(data.terrain, this.w, this.h);
    // วาดพื้นลงผ้าใบซ่อนครั้งเดียว แล้ว copy ทุกเฟรม — ไม่งั้นคิดสีใหม่ 190,000 พิกเซลต่อเฟรม
    this.buf = document.createElement('canvas');
    this.buf.width = this.w; this.buf.height = this.h;
    this.bctx = this.buf.getContext('2d');
    this.repaint();
  }

  /** โหลดพื้นใหม่ทั้งผืนจากที่เซิร์ฟเวอร์ส่งมา

      ⚠️ จำเป็น: เดิมถอดรหัสพื้นครั้งเดียวตอนเปิดสนาม หลังจากนั้นพื้นฝั่งเว็บ
         เปลี่ยนได้จาก carve() ที่เราสั่งเองเท่านั้น พลาดครั้งเดียวก็เพี้ยนถาวร
         อาการคือ "บนจอยังเห็นพื้น แต่เดินแล้วตัวจมลงเหมือนเป็นทางลาด"
   */
  reload(terrain) {
    this.g = decodeTerrain(terrain, this.w, this.h);
    this.repaint();
  }

  at(x, y) {
    x |= 0; y |= 0;
    return (x >= 0 && x < this.w && y >= 0 && y < this.h) ? this.g[y * this.w + x] : AIR;
  }
  solid(x, y) { return this.at(x, y) !== AIR; }

  repaint() {
    const { w, h } = this, ctx = this.bctx;
    const pal = (WORM_GROUND[this.continent] || WORM_GROUND.main)
      .map(hex => [1, 3, 5].map(i => parseInt(hex.slice(i, i + 2), 16)));
    ctx.clearRect(0, 0, w, h);
    const img = ctx.createImageData(w, h);
    const px = img.data;
    for (let i = 0; i < w * h; i++) {
      const m = this.g[i];
      if (!m) continue;
      const c = pal[m - 1];
      // จุดด่างจาง ๆ ให้พื้นผิวไม่เรียบเป็นแผ่นเดียว (คิดจากพิกัด ไม่ใช่สุ่ม จะได้ไม่กระพริบ)
      const k = (((i % w) * 7 + ((i / w) | 0) * 3) % 11 === 0) ? -14 : 0;
      const o = i * 4;
      px[o] = c[0] + k; px[o + 1] = c[1] + k; px[o + 2] = c[2] + k; px[o + 3] = 255;
    }
    ctx.putImageData(img, 0, 0);
    this._edges(ctx, pal);
    this.props.forEach(p => this._prop(ctx, p));
  }

  /** เส้นขอบสว่างบนผิวด้านบน — ทำให้ก้อนพื้นดูมีมิติ ไม่แบนเป็นสีเดียว */
  _edges(ctx, pal) {
    ctx.globalAlpha = .30; ctx.fillStyle = '#ffffff';
    for (let x = 0; x < this.w; x++) {
      for (let y = 1; y < this.h; y++) {
        const m = this.at(x, y);
        if (m && m !== LEAF && !this.solid(x, y - 1)) { ctx.fillRect(x, y, 1, 1); break; }
      }
    }
    ctx.globalAlpha = 1;
  }

  /** 🎁 หีบสมบัติบนแผนที่ (กับดักไม่วาด — เซิร์ฟเวอร์ไม่ส่งมาจนกว่าจะเหยียบโดน) */
  _prop(ctx, p) {
    if (p.kind === 'ferry') {                 // 🎈 เรือเหาะ — ขึ้นแล้วข้ามไปอีกเกาะ
      const bx = p.x - 5, by = p.y - 16;
      ctx.fillStyle = '#c8452f'; ctx.fillRect(bx + 1, by, 9, 7);
      ctx.fillStyle = '#ff8a6a'; ctx.fillRect(bx + 2, by + 1, 3, 4);
      ctx.fillStyle = '#6b4a24'; ctx.fillRect(bx + 3, by + 8, 5, 1);
      ctx.fillStyle = '#8a5a24'; ctx.fillRect(bx + 2, by + 9, 7, 5);
      ctx.fillStyle = '#c89a3a'; ctx.fillRect(bx + 2, by + 9, 7, 1);
      return;
    }
    if (p.kind !== 'chest') return;
    const x = p.x - 4, y = p.y - 7;
    ctx.fillStyle = '#3a2410'; ctx.fillRect(x, y + 2, 9, 6);
    ctx.fillStyle = '#8a5a24'; ctx.fillRect(x + 1, y + 3, 7, 4);
    ctx.fillStyle = '#5a3a16'; ctx.fillRect(x, y, 9, 3);
    ctx.fillStyle = '#c89a3a'; ctx.fillRect(x + 1, y + 1, 7, 1); ctx.fillRect(x + 4, y + 3, 1, 3);
    ctx.fillStyle = '#ffe6a8'; ctx.fillRect(x + 4, y + 4, 1, 1);
  }

  /** 💥 เจาะหลุม — เซิร์ฟเวอร์บอกว่าหลุมอยู่ไหน ที่นี่แค่ลบกับทาสีใหม่ */
  carve(cx, cy, r) {
    for (let y = Math.max(0, cy - r); y <= Math.min(this.h - 1, cy + r); y++) {
      const dx = Math.floor(Math.sqrt(Math.max(0, r * r - (y - cy) ** 2)));
      for (let x = Math.max(0, cx - dx); x <= Math.min(this.w - 1, cx + dx); x++)
        this.g[y * this.w + x] = AIR;
    }
    this.repaint();
  }

  /** ท้องฟ้า + พื้น + น้ำ ลงผ้าใบจริง (กล้องจัดการเรื่องซูม/เลื่อนให้แล้ว) */
  draw(ctx, cam, t) {
    const sky = ((typeof MAPS !== 'undefined' && MAPS[this.continent]) || {}).sky
                || ['#2a3a5c', '#5b6f94', '#c99a6a'];
    const vw = cam.vw, vh = cam.vh;
    const grad = ctx.createLinearGradient(0, 0, 0, vh);
    sky.forEach((c, i) => grad.addColorStop(i / (sky.length - 1), c));
    ctx.fillStyle = grad; ctx.fillRect(0, 0, vw, vh);

    ctx.imageSmoothingEnabled = false;
    const sw = vw / cam.z, sh = vh / cam.z;
    ctx.drawImage(this.buf, cam.x, cam.y, sw, sh, 0, 0, vw, vh);

    // น้ำ — ต้องเห็นชัดว่าตกลงไปคือตาย
    const wy = (this.h - this.water - cam.y) * cam.z;
    if (wy < vh) {
      ctx.fillStyle = sky[0];
      ctx.globalAlpha = .55; ctx.fillRect(0, wy, vw, vh - wy); ctx.globalAlpha = 1;
      ctx.fillStyle = '#ffffff';
      for (let x = 0; x < vw; x += 4) {
        const k = Math.sin((x + (t || 0) * .7) / 9) + Math.sin((x - (t || 0) * .4) / 5);
        ctx.globalAlpha = .10 + .10 * (k + 2) / 4;
        ctx.fillRect(x, wy + 1 + Math.round(k), 3, 1);
      }
      ctx.globalAlpha = 1;
    }
  }
}

/** 🎥 กล้อง — แผนที่ใหญ่กว่าจอ ต้องซูมกับเลื่อนไปดูคนอื่นได้
 *
 *  ซูมเป็นจำนวนเต็มเท่านั้น พิกเซลจะได้คมเสมอ · x,y เก็บเป็นพิกัดแผนที่ (มุมซ้ายบนของภาพ)
 */
class WormsCam {
  constructor(cv, map) {
    this.cv = cv; this.map = map;
    this.vw = cv.width; this.vh = cv.height;
    this.z = 1; this.x = 0; this.y = 0;
    this.tx = 0; this.ty = 0;      // เป้าที่กล้องกำลังไถลเข้าหา
    this.ease = 0.10;              // ยิ่งน้อยยิ่งนุ่ม (ต่อเฟรม)
    this.maxStep = 18;             // เลื่อนได้มากสุดกี่พิกเซลบนจอต่อเฟรม
    this.fit();
  }

  /** ซูมออกสุดจนเห็นทั้งแผนที่ */
  fit() { this.z = 1; this.x = 0; this.y = 0; this.clamp(); this.hold(); }

  /** เลื่อนไปถึงเป้าแล้วหรือยัง — ตัวจับเวลาต่าง ๆ ต้องรอให้ถึงก่อนค่อยเริ่มนับ */
  arrived() { return Math.abs(this.tx - this.x) < 0.6 && Math.abs(this.ty - this.y) < 0.6; }

  /** ตรึงเป้าไว้ที่ตำแหน่งปัจจุบัน — ใช้หลังลาก/ซูม ไม่งั้นกล้องจะไถลกลับเอง */
  hold() { this.tx = this.x; this.ty = this.y; }

  /** ขยับเข้าหาเป้าทีละนิดทุกเฟรม — หัวใจของ "จอไม่วาป"

      ⚠️ เดิม center() ย้ายกล้องทันที ทุกครั้งที่เปลี่ยนจุดสนใจจอเลยกระโดด
         ทั้งตอนสลับตา ตามลูกกระสุน และไล่ดูคนที่โดน — เล่นนาน ๆ แล้วมึนหัว
   */
  glide() {
    const dx = this.tx - this.x, dy = this.ty - this.y;
    if (Math.abs(dx) < 0.35 && Math.abs(dy) < 0.35) { this.x = this.tx; this.y = this.ty; return; }
    let sx = dx * this.ease, sy = dy * this.ease;
    // ⚠️ ขยับทีละ 10% ของระยะที่เหลือ — ระยะไกล ๆ เฟรมแรกจึงกระโดดทีเดียวหลายสิบพิกเซล
    //    ยังเห็นเป็น "จอวาป" อยู่ดี ต้องคุมความเร็วสูงสุดต่อเฟรมด้วย
    const max = this.maxStep / this.z, len = Math.hypot(sx, sy);
    if (len > max) { sx = sx / len * max; sy = sy / len * max; }
    this.x += sx;
    this.y += sy;
    this.clamp();
  }

  clamp() {
    this.z = Math.max(1, Math.min(ZOOM_MAX, Math.round(this.z)));
    this.x = Math.max(0, Math.min(this.map.w - this.vw / this.z, this.x));
    this.y = Math.max(0, Math.min(this.map.h - this.vh / this.z, this.y));
    if (this.map.w <= this.vw / this.z) this.x = 0;
    if (this.map.h <= this.vh / this.z) this.y = 0;
  }

  /** ซูมโดยตรึงจุดบนแผนที่ (mx,my) ไว้กับที่ — ซูมเข้าแล้วไม่หลุดไปคนละที่ */
  zoomAt(dz, mx, my) {
    const before = this.z;
    this.z = Math.max(1, Math.min(ZOOM_MAX, Math.round(this.z + dz)));
    if (this.z === before) return;
    this.x = mx - (mx - this.x) * (before / this.z);
    this.y = my - (my - this.y) * (before / this.z);
    this.clamp(); this.hold();
  }

  /** เลื่อนกล้องเป็นพิกเซลบนหน้าจอ (ตอนลากนิ้ว/เมาส์) */
  pan(dxScreen, dyScreen) {
    this.x -= dxScreen / this.z; this.y -= dyScreen / this.z; this.clamp(); this.hold();
  }

  /** จับใครสักคนไว้กลางจอ — ใช้ตอนกดดูผู้เล่นคนอื่น */
  center(mx, my, instant) {
    this.tx = mx - this.vw / this.z / 2;
    this.ty = my - this.vh / this.z / 2;
    const w = this.map.w - this.vw / this.z, h = this.map.h - this.vh / this.z;
    this.tx = this.map.w <= this.vw / this.z ? 0 : Math.max(0, Math.min(w, this.tx));
    this.ty = this.map.h <= this.vh / this.z ? 0 : Math.max(0, Math.min(h, this.ty));
    if (instant) { this.x = this.tx; this.y = this.ty; this.clamp(); }
  }

  /** พิกัดแผนที่ → พิกัดบนผ้าใบ */
  sx(mx) { return (mx - this.x) * this.z; }
  sy(my) { return (my - this.y) * this.z; }

  /** พิกัดบนผ้าใบ → พิกัดแผนที่ (ใช้ตอนซูมด้วยล้อ/นิ้ว) */
  mx(px) { return this.x + px / this.z; }
  my(py) { return this.y + py / this.z; }

  /** ต่อเมาส์/นิ้วเข้ากับกล้อง — ลากเลื่อน · ล้อซูม · หุบสองนิ้วซูม */
  attach(onChange) {
    const cv = this.cv, note = onChange || (() => { });
    const pt = e => {
      const r = cv.getBoundingClientRect();
      const t = e.touches ? e.touches[0] : e;
      return { x: (t.clientX - r.left) * cv.width / r.width,
               y: (t.clientY - r.top) * cv.height / r.height };
    };
    let last = null, pinch = 0;

    // locked = กำลังกดค้างเล็งอยู่ ลากนิ้ว/เมาส์ตอนนั้นคือปรับองศา ไม่ใช่เลื่อนกล้อง
    const down = e => { if (!this.locked) last = pt(e); };
    const move = e => {
      if (this.locked) return;
      if (e.touches && e.touches.length === 2) {           // หุบสองนิ้ว = ซูม
        const [a, b] = e.touches;
        const d = Math.hypot(a.clientX - b.clientX, a.clientY - b.clientY);
        if (pinch && Math.abs(d - pinch) > 40) {
          this.zoomAt(d > pinch ? 1 : -1, this.mx(this.vw / 2), this.my(this.vh / 2));
          pinch = d; note();
        }
        if (!pinch) pinch = d;
        e.preventDefault();
        return;
      }
      if (!last) return;
      const p = pt(e);
      this.pan(p.x - last.x, p.y - last.y);
      last = p; note();
      if (e.touches) e.preventDefault();
    };
    const up = () => { last = null; pinch = 0; };

    cv.addEventListener('mousedown', down);
    window.addEventListener('mousemove', move);
    window.addEventListener('mouseup', up);
    cv.addEventListener('touchstart', down, { passive: true });
    cv.addEventListener('touchmove', move, { passive: false });
    cv.addEventListener('touchend', up);
    cv.addEventListener('wheel', e => {
      e.preventDefault();
      const p = pt(e);
      this.zoomAt(e.deltaY < 0 ? 1 : -1, this.mx(p.x), this.my(p.y));
      note();
    }, { passive: false });
  }
}
