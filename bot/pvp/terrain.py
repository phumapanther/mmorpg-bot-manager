"""🪱 แผนที่สนามรบผลัดเทิร์น — เกาะลอยที่ยิงจนพังได้

ทำไมแผนที่ต้องอยู่ที่เซิร์ฟเวอร์: ตำแหน่งพื้น = ที่กำบัง ที่ยืน และทางตก
ถ้าเบราว์เซอร์สร้างเอง เปิด devtools แล้วแก้ให้ตัวเองยืนกลางอากาศได้ทันที
(บทเรียนเดียวกับ NPC ปลอมตัวที่เคยแก้ไปแล้ว)

รูปแบบข้อมูล: บิตกริด W×H — 1 = พื้นแข็ง · 0 = อากาศ
ส่งให้เบราว์เซอร์เป็น RLE รายแถว (เกาะลอยบีบได้ดีมาก ~5KB) แล้วยิงจนพัง
ค่อยส่งเฉพาะหลุมที่เกิดใหม่ ไม่ต้องส่งทั้งแผนที่ซ้ำ

**ไม่มีสีอยู่ในไฟล์นี้เลย** — สีมาจากพาเลตต์ 9 ทวีปใน scene.js ที่มีอยู่แล้ว
เบราว์เซอร์คิดเองว่าพิกเซลไหนเป็นหญ้า/ดิน/หิน จากความลึกใต้ผิว
"""
import math
import random

W, H = 400, 180          # ขนาดในพิกัดพิกเซล (เบราว์เซอร์ขยายด้วย image-rendering: pixelated)
WATER = 14               # ความสูงของน้ำที่ก้นจอ — ตกลงไปคือตาย (กติกาคลาสสิกของแนวนี้)
MIN_ISLANDS, MAX_ISLANDS = 3, 5
SPAWN_GAP = 40           # ผู้เล่นสองคนต้องห่างกันอย่างน้อยเท่านี้ ไม่งั้นเกิดมาติดกันแล้วตายทันที


def _noise(rng, n, octaves=3):
    """เส้นขรุขระยาว n ช่อง จากผลรวมคลื่นไซน์หลายชั้น — ค่าอยู่ราว -1..1

    ใช้คลื่นไซน์แทน Perlin เพราะสั้นกว่ามากและได้ผิวเกาะที่ดูเป็นธรรมชาติพอ ๆ กัน
    """
    waves = [(rng.uniform(0.6, 1.0) / (2 ** i),                       # ความสูง
              rng.uniform(1.5, 3.5) * (2 ** i) / max(n, 1),           # ความถี่
              rng.uniform(0, math.tau))                               # เฟส
             for i in range(octaves)]
    out = []
    for x in range(n):
        v = sum(a * math.sin(f * x + p) for a, f, p in waves)
        out.append(max(-1.0, min(1.0, v)))
    return out


def _island(rng, grid, cx, cy, half, thick):
    """วางเกาะลอยหนึ่งก้อน — ผิวบนขรุขระ ท้องเกาะเรียวลงเป็นทรงเลนส์เหมือนเกาะจริงในเกมแนวนี้"""
    span = half * 2
    top_n = _noise(rng, span + 1)
    bot_n = _noise(rng, span + 1, octaves=2)
    for i in range(span + 1):
        x = cx - half + i
        if not (0 <= x < W):
            continue
        # เรียวปลายทั้งสองข้างด้วยทรงวงรี — ตรงกลางหนา ปลายบาง
        t = 1 - (i - half) ** 2 / (half * half)
        if t <= 0:
            continue
        taper = math.sqrt(t)
        top = int(cy + top_n[i] * 4)
        bottom = int(top + thick * taper + bot_n[i] * 3 * taper)
        for y in range(max(0, top), min(H - WATER, bottom + 1)):
            grid[y][x] = 1


def _arch(rng, grid, cx, cy, half):
    """เสาหินสูงชะลูดที่โผล่ขึ้นมาจากเกาะ — ช่วยให้แผนที่มีที่กำบังแนวตั้ง ไม่แบนจนน่าเบื่อ"""
    h = rng.randint(30, 60)
    n = _noise(rng, h + 1, octaves=2)
    for i in range(h + 1):
        y = cy - i
        if not (0 <= y < H - WATER):
            continue
        w = max(2, int(half * (1 - i / (h * 1.6)) + n[i] * 3))
        for x in range(cx - w, cx + w + 1):
            if 0 <= x < W:
                grid[y][x] = 1


def generate(seed, continent="main"):
    """สร้างแผนที่จากเมล็ด — เมล็ดเดียวกันได้แผนที่เดียวกันเป๊ะทุกครั้ง

    (จึงแชร์รหัสแผนที่กับเพื่อนได้ และเทสย้อนกลับมาดูแผนที่เดิมได้)
    """
    rng = random.Random(int(seed))
    grid = [[0] * W for _ in range(H)]

    n = rng.randint(MIN_ISLANDS, MAX_ISLANDS)
    slot = W / n
    for i in range(n):
        cx = int(slot * i + slot / 2 + rng.uniform(-slot * .22, slot * .22))
        cy = rng.randint(40, H - WATER - 40)
        half = int(rng.uniform(.28, .46) * slot)
        _island(rng, grid, cx, cy, half, rng.randint(14, 30))
        if rng.random() < .45:
            _arch(rng, grid, cx + rng.randint(-half // 2, half // 2), cy, max(4, half // 4))

    # เกาะพื้นล่างหนึ่งก้อนเสมอ — ถ้าลอยหมดทั้งจอ พลาดตกน้ำง่ายเกินจนไม่สนุก
    base_cx = rng.randint(int(W * .25), int(W * .75))
    _island(rng, grid, base_cx, H - WATER - rng.randint(18, 30),
            int(W * rng.uniform(.16, .26)), 40)

    return {"seed": int(seed), "w": W, "h": H, "water": WATER,
            "continent": continent, "grid": grid}


# ── อ่าน/แก้พื้น ──

def solid(grid, x, y):
    """ตรงนี้เป็นพื้นแข็งไหม — นอกขอบซ้าย/ขวา/บน ถือว่าโล่ง ก้นจอถือว่าน้ำ (ไม่ใช่พื้น)"""
    return 0 <= x < W and 0 <= y < H and grid[y][x] == 1


def surface_at(grid, x, from_y=0):
    """หาผิวพื้นแข็งจุดแรกเมื่อมองลงมาจาก from_y — คืน y ที่ยืนได้ หรือ None ถ้าตกน้ำ"""
    if not 0 <= x < W:
        return None
    for y in range(max(0, from_y), H - WATER):
        if grid[y][x]:
            return y
    return None


def carve(grid, cx, cy, r):
    """💥 เจาะหลุมวงกลม — คืนรายการพิกเซลที่หายไป ไว้ส่งให้เบราว์เซอร์ลบตาม

    ส่งเฉพาะส่วนที่เปลี่ยน ไม่ต้องส่งแผนที่ทั้งใบซ้ำทุกนัด
    """
    gone = []
    for y in range(max(0, cy - r), min(H, cy + r + 1)):
        dy = y - cy
        dx = int(math.sqrt(max(0, r * r - dy * dy)))
        for x in range(max(0, cx - dx), min(W, cx + dx + 1)):
            if grid[y][x]:
                grid[y][x] = 0
                gone.append((x, y))
    return gone


FLAT_SPAN = 5      # ต้องเดินออกไปได้เท่านี้ทั้งสองข้างโดยไม่เจอหน้าผา
FLAT_DROP = 4      # พื้นสองข้างต่างระดับกันได้ไม่เกินเท่านี้


def _standable(grid, x, y):
    """ยืนตรงนี้แล้วขยับได้จริงไหม — ไม่ใช่ยอดหินแหลมหรือริมหน้าผาที่ก้าวแล้วร่วง

    เคยพลาด: เช็คแค่ ±3 ช่อง จุดเกิดเลยไปโผล่ริมผาที่ห่างออกไป 4 ช่องพอดี
    """
    for d in range(-FLAT_SPAN, FLAT_SPAN + 1):
        s = surface_at(grid, x + d)
        if s is None or abs(s - y) > FLAT_DROP:      # ต้องเช็ค None ตรง ๆ — ผิวที่แถว 0 ก็ falsy
            return False
    return True


def spawns(grid, count, rng=None):
    """หาจุดเกิดของผู้เล่น — บนพื้นแข็ง กระจายห่างกัน ยืนแล้วเดินได้จริง"""
    rng = rng or random.Random(0)
    ok = [(x, y) for x in range(6, W - 6)
          for y in [surface_at(grid, x)]
          if y is not None and y >= 8 and _standable(grid, x, y)]
    if not ok:
        return []

    rng.shuffle(ok)
    picked = []
    for x, y in ok:
        if all(abs(x - px) >= SPAWN_GAP for px, _ in picked):
            picked.append((x, y))
            if len(picked) == count:
                break
    # ที่ว่างไม่พอให้ห่างกันครบ — ยอมให้ใกล้กว่าเกณฑ์ดีกว่าเกิดไม่ครบคน
    for x, y in ok:
        if len(picked) >= count:
            break
        if (x, y) not in picked:
            picked.append((x, y))
    return sorted(picked[:count])


# ── ส่งให้เบราว์เซอร์ ──

def encode(grid):
    """บีบเป็น RLE รายแถว: ตัวเลขสลับ ช่วงว่าง,ช่วงพื้น,ช่วงว่าง,... เริ่มที่ว่างเสมอ

    แถวคั่นด้วย ';' ตัวเลขคั่นด้วย ',' — เกาะลอยบีบได้ราว 40 เท่า
    """
    rows = []
    for row in grid:
        runs, cur, n = [], 0, 0
        for v in row:
            if v == cur:
                n += 1
            else:
                runs.append(n)
                cur, n = v, 1
        runs.append(n)
        rows.append(",".join(map(str, runs)))
    return ";".join(rows)


def decode(text, w=W, h=H):
    """คืนกริดจาก RLE — มีไว้ให้เทสพิสูจน์ว่าเข้ารหัสแล้วถอดกลับได้เหมือนเดิมเป๊ะ"""
    grid = []
    for line in text.split(";"):
        row, cur = [], 0
        for n in line.split(","):
            row += [cur] * int(n)
            cur = 1 - cur
        grid.append(row[:w] + [0] * max(0, w - len(row)))
    return grid[:h]


def view(seed, continent="main", players=2):
    """แผนที่พร้อมส่งขึ้นเว็บ — บีบแล้ว พร้อมจุดเกิด"""
    m = generate(seed, continent)
    rng = random.Random(int(seed) ^ 0x5EED)
    from bot.game_data import CONTINENTS
    return {"seed": m["seed"], "w": W, "h": H, "water": WATER, "continent": continent,
            "continent_label": CONTINENTS.get(continent, {}).get("label", continent),
            "terrain": encode(m["grid"]),
            "spawns": [{"x": x, "y": y} for x, y in spawns(m["grid"], players, rng)]}
