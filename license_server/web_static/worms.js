// 🪱 สนามรบผลัดเทิร์น — ตัววาดแผนที่ (หมวด PVP)
//
// ไฟล์นี้ "ไม่มีกฎเกมเลย" — พื้นอยู่ตรงไหน ใครยืนที่ไหน ตัดสินที่เซิร์ฟเวอร์ทั้งหมด
// ที่นี่รับบิตกริดมาแล้ววาดให้สวย กับเจาะหลุมตามที่เซิร์ฟเวอร์บอกเท่านั้น
//
// พื้นเป็นบิตล้วน (1 = แข็ง) ไม่มีสีติดมาด้วย — เบราว์เซอร์คิดเองว่าพิกเซลไหนเป็น
// หญ้า/ดิน/หิน จาก "ลึกจากผิวเท่าไหร่" เลยเปลี่ยนธีมทวีปได้โดยไม่ต้องส่งข้อมูลเพิ่ม

// สีพื้นรายทวีป — ท้องฟ้าใช้ MAPS ของ scene.js ร่วมกัน ตรงนี้มีแค่ส่วนที่ scene.js ไม่มี
const WORM_GROUND = {
  main:       { grass: ['#7fb35c', '#4a7a38', '#2f5226'], dirt: '#6b5433', rock: ['#4a3f30', '#2b241b'] },
  demon:      { grass: ['#a84a6a', '#6e2440', '#45152a'], dirt: '#4a2030', rock: ['#3a1626', '#210c16'] },
  frozen:     { grass: ['#d8ecf6', '#a8ccdd', '#6f93a8'], dirt: '#5f7d92', rock: ['#48606f', '#2b3a45'] },
  nether:     { grass: ['#c85a2a', '#8a3416', '#4e1d0c'], dirt: '#5a2716', rock: ['#3d1a10', '#221009'] },
  volcanic:   { grass: ['#c87a3a', '#8a4a22', '#4e2814'], dirt: '#4a2c1e', rock: ['#332028', '#1d1218'] },
  sylvan:     { grass: ['#8fd06a', '#4f8a3a', '#2c5224'], dirt: '#4a3a20', rock: ['#33301f', '#1c1c11'] },
  mechanized: { grass: ['#8a8a70', '#5c5c48', '#3a3a2c'], dirt: '#4a4436', rock: ['#3a3a42', '#20202a'] },
  skyward:    { grass: ['#bfd8f0', '#8fa8d0', '#5f6d94'], dirt: '#6a6f90', rock: ['#4c5474', '#2e3450'] },
  ocean:      { grass: ['#6fd0c0', '#2f8a84', '#17514f'], dirt: '#1f5a5e', rock: ['#173f4e', '#0c2630'] },
};
const GRASS_DEPTH = 3;      // ลึกจากผิวเท่านี้ยังเป็นหญ้า
const DIRT_DEPTH = 10;      // ลึกกว่าหญ้าถึงเท่านี้เป็นดิน ลึกกว่านั้นเป็นหิน

/** RLE รายแถวจากเซิร์ฟเวอร์ → Uint8Array แบนราบ (1 = พื้นแข็ง) */
function decodeTerrain(text, w, h) {
  const g = new Uint8Array(w * h);
  const rows = text.split(';');
  for (let y = 0; y < h && y < rows.length; y++) {
    let x = 0, cur = 0;
    for (const part of rows[y].split(',')) {
      const n = +part;
      if (cur) g.fill(1, y * w + x, y * w + Math.min(w, x + n));
      x += n; cur ^= 1;
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
    this.g = decodeTerrain(data.terrain, this.w, this.h);
    // วาดพื้นลงผ้าใบซ่อนไว้ครั้งเดียว แล้ว copy ทุกเฟรม — ไม่งั้นคิดสีใหม่ 72,000 พิกเซลต่อเฟรม
    this.buf = document.createElement('canvas');
    this.buf.width = this.w; this.buf.height = this.h;
    this.bctx = this.buf.getContext('2d');
    this.repaint();
  }

  solid(x, y) {
    x |= 0; y |= 0;
    return x >= 0 && x < this.w && y >= 0 && y < this.h && this.g[y * this.w + x] === 1;
  }

  /** ลึกจากผิวกี่พิกเซล — ใช้ตัดสินว่าเป็นหญ้า/ดิน/หิน */
  _depths() {
    const d = new Int16Array(this.w * this.h);
    for (let x = 0; x < this.w; x++) {
      let run = -1;
      for (let y = 0; y < this.h; y++) {
        const i = y * this.w + x;
        run = this.g[i] ? run + 1 : -1;
        d[i] = run;
      }
    }
    return d;
  }

  /** วาดพื้นใหม่ทั้งใบ (เรียกตอนสร้าง และตอนโดนยิงจนพัง) */
  repaint() {
    const { w, h } = this, ctx = this.bctx;
    const pal = WORM_GROUND[this.continent] || WORM_GROUND.main;
    ctx.clearRect(0, 0, w, h);
    const img = ctx.createImageData(w, h);
    const px = img.data;
    const d = this._depths();
    const rgb = hex => [1, 3, 5].map(i => parseInt(hex.slice(i, i + 2), 16));
    const cols = [...pal.grass.map(rgb), rgb(pal.dirt), ...pal.rock.map(rgb)];

    for (let i = 0; i < w * h; i++) {
      if (!this.g[i]) continue;
      const depth = d[i];
      let c;
      if (depth < GRASS_DEPTH) c = cols[depth];                       // หญ้า 3 ชั้น สว่าง→เข้ม
      else if (depth < DIRT_DEPTH) c = cols[3];                       // ดิน
      else c = cols[4 + (((i % w) + ((i / w) | 0)) % 7 === 0 ? 0 : 1)]; // หินมีจุดด่างให้ไม่เรียบ
      const o = i * 4;
      px[o] = c[0]; px[o + 1] = c[1]; px[o + 2] = c[2]; px[o + 3] = 255;
    }
    ctx.putImageData(img, 0, 0);
    this._tufts(ctx, pal);
  }

  /** พุ่มหญ้า/ก้อนหินเล็ก ๆ บนผิว — สุ่มจากเมล็ดกับพิกัด ไม่ใช่ Math.random จะได้ไม่กระพริบ */
  _tufts(ctx, pal) {
    for (let x = 2; x < this.w - 2; x += 1) {
      const r = ((x * 2654435761) ^ (this.seed & 0xffff)) >>> 0;
      if (r % 11) continue;
      let y = 0;
      while (y < this.h && !this.solid(x, y)) y++;
      if (y >= this.h - this.water || !this.solid(x, y)) continue;
      const tall = 2 + (r >> 8) % 4;
      ctx.fillStyle = pal.grass[0];
      for (let i = 0; i < tall; i++) ctx.fillRect(x + ((r >> (i + 4)) & 1), y - 1 - i, 1, 1);
    }
  }

  /** 💥 เจาะหลุม — เซิร์ฟเวอร์เป็นคนบอกว่าหลุมอยู่ไหน ที่นี่แค่ลบกับทาสีใหม่ */
  carve(cx, cy, r) {
    for (let y = Math.max(0, cy - r); y <= Math.min(this.h - 1, cy + r); y++) {
      const dx = Math.floor(Math.sqrt(Math.max(0, r * r - (y - cy) ** 2)));
      for (let x = Math.max(0, cx - dx); x <= Math.min(this.w - 1, cx + dx); x++)
        this.g[y * this.w + x] = 0;
    }
    this.repaint();
  }

  /** ท้องฟ้า + พื้น + น้ำ ลงผ้าใบจริง */
  draw(ctx, t) {
    const { w, h } = this;
    const sky = ((typeof MAPS !== 'undefined' && MAPS[this.continent]) || {}).sky
                || ['#2a3a5c', '#5b6f94', '#c99a6a'];
    const grad = ctx.createLinearGradient(0, 0, 0, h);
    sky.forEach((c, i) => grad.addColorStop(i / (sky.length - 1), c));
    ctx.fillStyle = grad;
    ctx.fillRect(0, 0, w, h);
    ctx.drawImage(this.buf, 0, 0);

    // น้ำก้นจอ — ตกลงไปคือตาย ต้องเห็นชัดว่าเป็นเขตอันตราย
    const wy = h - this.water;
    ctx.fillStyle = sky[0];
    ctx.globalAlpha = .55; ctx.fillRect(0, wy, w, this.water); ctx.globalAlpha = 1;
    ctx.fillStyle = '#ffffff';
    for (let x = 0; x < w; x += 4) {
      const k = Math.sin((x + (t || 0) * .7) / 9) + Math.sin((x - (t || 0) * .4) / 5);
      ctx.globalAlpha = .10 + .10 * (k + 2) / 4;
      ctx.fillRect(x, wy + 1 + Math.round(k), 3, 1);
    }
    ctx.globalAlpha = 1;
  }
}
