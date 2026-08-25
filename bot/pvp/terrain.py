"""🪱 แผนที่สนามรบผลัดเทิร์น — เกาะลอย + สิ่งปลูกสร้างที่ยิงพังได้

ทำไมแผนที่ต้องอยู่ที่เซิร์ฟเวอร์: ตำแหน่งพื้น = ที่กำบัง ที่ยืน และทางตก
ถ้าเบราว์เซอร์สร้างเอง เปิด devtools แล้วแก้ให้ตัวเองยืนกลางอากาศได้ทันที
(บทเรียนเดียวกับ NPC ปลอมตัวที่เคยแก้ไปแล้ว)

**ตัดสินใจสำคัญ: บ้าน/ปราสาท/ต้นไม้ = เนื้อเดียวกับพื้น ไม่ใช่วัตถุแยก**
ผลที่ได้ฟรีทันทีโดยไม่ต้องเขียนกลไกใหม่เลย:
  · เดินเข้าไปแอบในปราสาทได้     — เพราะข้างในกลวงจริง มีประตูจริง
  · ยิงกำแพงพังได้                — ใช้ carve() ตัวเดียวกับพื้นดิน
  · กระสุนถูกกำแพงบัง             — ใช้ solid() ตัวเดียวกับพื้นดิน
ต่างกันแค่ "วัสดุ" ที่เก็บไว้ในกริดเดียวกัน ไว้ให้เบราว์เซอร์รู้ว่าจะทาสีอะไร

หีบสมบัติกับกับดักเป็น "ของวางบนแผนที่" (ไม่ใช่พื้น) จึงเก็บแยก
⚠️ กับดักต้องไม่ส่งไปให้เบราว์เซอร์จนกว่าจะเหยียบโดน ไม่งั้นเปิด devtools ดูได้หมด
"""
import math
import random

W, H = 720, 270          # ใหญ่กว่าเดิม 2.7 เท่า — จอแคบเลื่อนดูตามแนวนอนได้
WATER = 18               # น้ำก้นจอ — ตกลงไปคือตาย (กติกาคลาสสิกของแนวนี้)
MIN_ISLANDS, MAX_ISLANDS = 4, 6
SPAWN_GAP = 45           # ระยะเกิดขั้นต่ำ — ต้องไกลกว่าระยะฟัน (24-30) แต่ไม่มากจน
                         # ไม่มีเกาะไหนกว้างพอ แล้วต้องไปเกิดคนละเกาะจนคลาสประชิดสู้ไม่ได้
FLAT_SPAN, FLAT_DROP = 3, 4     # ต้องเดินออกไปได้เท่านี้ทั้งสองข้างโดยไม่เจอหน้าผา
                                # เข้มกว่านี้แล้วแผนที่บางใบเหลือที่ยืนไม่ถึง 10 จุด เกิดไม่ครบคน

# 🧍 ขนาดตัวละครในสนาม — ทุกอย่างที่ "เดินลอดได้/ยืนได้" ต้องอ้างอิงตัวเลขนี้
# สไปรต์วาด 16×22 · กล่องชนแคบกว่าเพราะสองคอลัมน์ริมของสไปรต์ว่างอยู่แล้ว
CH_W, CH_H = 9, 21

# วัสดุในกริด — 0 คืออากาศ ที่เหลือคือพื้นแข็งทั้งหมด (เบราว์เซอร์แปลงเป็นสีเอง)
AIR, GRASS, DIRT, ROCK, WOOD, BRICK, TRUNK, LEAF = range(8)
GRASS_DEPTH, DIRT_DEPTH = 3, 10

# 💎 ของบนแผนที่ · น้ำหนักคือโอกาสถูกสุ่มวางเมื่อเทียบกัน
PROPS = {"chest": 3, "trap": 4, "ferry": 1}


def _noise(rng, n, octaves=3):
    """เส้นขรุขระยาว n ช่อง จากผลรวมคลื่นไซน์หลายชั้น — ค่าอยู่ราว -1..1"""
    waves = [(rng.uniform(0.6, 1.0) / (2 ** i),
              rng.uniform(1.5, 3.5) * (2 ** i) / max(n, 1),
              rng.uniform(0, math.tau))
             for i in range(octaves)]
    return [max(-1.0, min(1.0, sum(a * math.sin(f * x + p) for a, f, p in waves)))
            for x in range(n)]


def _island(rng, g, cx, cy, half, thick):
    """เกาะลอยหนึ่งก้อน — ผิวบนขรุขระ ท้องเกาะเรียวเป็นทรงเลนส์"""
    span = half * 2
    top_n, bot_n = _noise(rng, span + 1), _noise(rng, span + 1, 2)
    for i in range(span + 1):
        x = cx - half + i
        if not (0 <= x < W):
            continue
        t = 1 - (i - half) ** 2 / (half * half)
        if t <= 0:
            continue
        taper = math.sqrt(t)
        top = int(cy + top_n[i] * 5)
        bottom = int(top + thick * taper + bot_n[i] * 4 * taper)
        for y in range(max(0, top), min(H - WATER, bottom + 1)):
            g[y][x] = ROCK


def _arch(rng, g, cx, cy, half):
    """เสาหินสูง — ที่กำบังแนวตั้ง ไม่ให้แผนที่แบนจนน่าเบื่อ"""
    h = rng.randint(40, 80)
    n = _noise(rng, h + 1, 2)
    for i in range(h + 1):
        y = cy - i
        if not (0 <= y < H - WATER):
            continue
        w = max(2, int(half * (1 - i / (h * 1.6)) + n[i] * 3))
        for x in range(max(0, cx - w), min(W, cx + w + 1)):
            g[y][x] = ROCK


def _skin(g):
    """ทาผิวดินให้เป็นหญ้า→ดิน→หิน ตามความลึกจากผิว

    ทำที่เซิร์ฟเวอร์เพราะที่นี่รู้อยู่แล้วว่าอะไรเป็นดินธรรมชาติ อะไรเป็นกำแพงบ้าน
    (ถ้าปล่อยให้เบราว์เซอร์เดาจากความลึก หลังคาบ้านจะกลายเป็นหญ้า)
    """
    for x in range(W):
        depth = -1
        for y in range(H):
            if g[y][x] == ROCK:
                depth += 1
                g[y][x] = GRASS if depth < GRASS_DEPTH else DIRT if depth < DIRT_DEPTH else ROCK
            elif g[y][x] == AIR:
                depth = -1
            else:
                depth = DIRT_DEPTH        # ใต้สิ่งปลูกสร้างไม่ต้องมีหญ้า


# ── 🏗️ สิ่งปลูกสร้าง (เป็นเนื้อเดียวกับพื้น จึงยิงพังได้และแอบข้างในได้) ──

def _tree(rng, g, x, y):
    """🌳 ต้นไม้ — ลำต้นบังกระสุนแนวตั้ง พุ่มใบบังจากด้านบน (สูงกว่าตัวละครเสมอ)"""
    h = rng.randint(CH_H + 6, CH_H + 22)
    tw = 1 if h < CH_H + 12 else 2
    for i in range(h):
        for dx in range(-tw, tw + 1):
            if 0 <= x + dx < W and 0 <= y - i < H:
                g[y - i][x + dx] = TRUNK
    r = rng.randint(10, 17)
    top = y - h
    for dy in range(-r, r // 2 + 1):
        for dx in range(-r, r + 1):
            if dx * dx + dy * dy * 2 <= r * r and 0 <= x + dx < W and 0 <= top + dy < H:
                if g[top + dy][x + dx] == AIR:
                    g[top + dy][x + dx] = LEAF


def _boulder(rng, g, x, y):
    """🪨 ก้อนหิน — ที่กำบังเตี้ย ๆ หมอบหลบได้"""
    r = rng.randint(7, 14)
    n = _noise(rng, r * 2 + 1, 2)
    for dy in range(-r, 3):
        for dx in range(-r, r + 1):
            if dx * dx + dy * dy <= (r + n[abs(dx)] * 2) ** 2:
                if 0 <= x + dx < W and 0 <= y + dy < H:
                    g[y + dy][x + dx] = ROCK


# ช่องประตูต้องสูงกว่าตัวละคร ไม่งั้นเดินลอดไม่ได้เลยสักหลัง (เจอตอนจะทำระบบเดิน)
DOOR_H = CH_H + 4


def _building(g, x, y, w, h, mat, door=True, battlement=False):
    """กล่องกลวงมีประตู — เดินเข้าไปแอบข้างในได้จริง ยิงกำแพงพังได้จริง

    ตันตรงกำแพง โล่งตรงกลาง = สองอย่างที่ต้องการเกิดขึ้นเองโดยไม่ต้องเขียนกฎเพิ่ม
    **ไม่มีพื้นห้อง** — ใช้พื้นดินเดิมเป็นพื้น ไม่งั้นตัวละครยืนบนหลังคาชั้นล่างแทนที่จะเข้าไปข้างใน
    ประตูเจาะทะลุ "กำแพงข้าง" ไม่ใช่เจาะในห้อง (เจาะในห้องคือไม่ได้ทำอะไรเลย ห้องก็โล่งอยู่แล้ว)
    """
    x0, y0 = x - w // 2, y - h
    # จดผิวดินเดิมของแต่ละคอลัมน์ไว้ก่อน — ห้องต้องกลวงเฉพาะ "เหนือพื้น"
    # เคยพลาด: เจาะ AIR ลงไปทุกแถวจนทะลุพื้นดิน บ้านเลยกลายเป็นหลุมไม่มีก้น ยืนไม่ได้เลย
    floor = {gx: (surface_at(g, gx) or H) for gx in range(x0, x0 + w + 1)}
    for dy in range(h + 1):
        for dx in range(w + 1):
            gx, gy = x0 + dx, y0 + dy
            if not (0 <= gx < W and 0 <= gy < H):
                continue
            if dx in (0, w) or dy == 0:
                g[gy][gx] = mat          # กำแพงซ้าย/ขวา + หลังคา
            elif gy < floor.get(gx, H):
                g[gy][gx] = AIR          # ข้างในกลวงเหนือพื้น = ที่แอบ (พื้นดินเดิมเป็นพื้นห้อง)
    if battlement:                        # ใบเสมาปราสาท — เว้นฟันหวีบนหลังคา
        for dx in range(w + 1):
            if 0 <= x0 + dx < W and dx % 4 < 2:
                for k in (1, 2):
                    if 0 <= y0 - k < H:
                        g[y0 - k][x0 + dx] = mat
    if door:
        # ประตูทั้งสองข้าง — ข้างเดียวไม่พอ เพราะบ้านบางหลังไปตั้งชิดหน้าผาพอดี
        # ประตูด้านนั้นจะเปิดออกไปสู่ที่ว่าง เดินเข้าไม่ได้เลยทั้งหลัง (เทสจับได้)
        #
        # ต้องเหลือกำแพงเหนือช่องประตูอย่างน้อย 3 แถวเสมอ — เคยพลาด: บ้านสูง 10
        # เจอประตูสูง 7 บวกแถวล่างอีก 1 กินกำแพงไป 8 จาก 11 แถว เหลือเป็นเสาลอย
        dh = max(CH_H + 2, min(DOOR_H, h - 4))
        for side in (x0, x0 + w):
            for dy in range(h - dh, h + 1):
                if 0 <= side < W and 0 <= y0 + dy < H:
                    g[y0 + dy][side] = AIR


def _roof(g, x, y, w, mat):
    """หลังคาจั่วบนตัวบ้าน — ให้ดูเป็นบ้านไม่ใช่กล่องเปล่า"""
    for i in range((w + 1) // 2 + 1):
        for dx in range(-(w // 2 - i), w // 2 - i + 1):
            gx, gy = x + dx, y - i
            if 0 <= gx < W and 0 <= gy < H:
                g[gy][gx] = mat


def _flat_run(g, x, y, need):
    """มีพื้นราบกว้าง need ช่องรอบจุดนี้ไหม (ไว้หาที่ตั้งบ้าน/ปราสาท)"""
    for dx in range(-need // 2, need // 2 + 1):
        s = surface_at(g, x + dx)
        if s is None or abs(s - y) > 3:
            return False
    return True


TREE_GAP = 22        # ระยะห่างต้นไม้/ก้อนหิน — ต้องกว้างกว่าพุ่มใบ ไม่งั้นคลุมพื้นหมด
DOOR_CLEAR = 14      # ที่โล่งหน้าประตูทั้งสองข้าง — ไม่งั้นต้นไม้ขึ้นขวางทางเข้าจนใช้ไม่ได้


def _decorate(rng, g):
    """วางของบนผิวเกาะ — ปราสาทก่อน (ต้องการที่กว้างสุด) แล้วบ้าน ต้นไม้ หิน

    เก็บ "ความกว้างที่จอง" ของแต่ละอย่างไว้ด้วย ไม่ใช่แค่จุดกึ่งกลาง
    เคยพลาด: จองแค่จุดกึ่งกลาง ต้นไม้เลยไปงอกทะลุกำแพงปราสาทกว้าง 42 ช่อง
    แล้วขวางประตูจนเดินเข้าไม่ได้ทั้งหลัง
    """
    taken = []          # [(กึ่งกลาง, ครึ่งความกว้างที่จอง)]

    def free(x, half):
        return all(abs(x - tx) >= half + th for tx, th in taken)

    spots = [(x, surface_at(g, x)) for x in range(12, W - 12, 3)]
    spots = [(x, y) for x, y in spots if y is not None and y >= 12]
    rng.shuffle(spots)

    # 🏰 ปราสาท 1 หลัง — ที่แอบที่ใหญ่ที่สุดในสนาม
    for x, y in spots:
        if _flat_run(g, x, y, 84) and free(x, 40 + DOOR_CLEAR):
            _building(g, x, y + 1, 80, CH_H + 34, BRICK, door=True, battlement=True)
            taken.append((x, 40 + DOOR_CLEAR))
            break

    # 🏘️ หมู่บ้าน 2-4 หลัง เกาะกลุ่มกัน
    for x, y in spots:
        if len(taken) >= 5:
            break
        w = rng.randint(30, 40)
        if _flat_run(g, x, y, w + 4) and free(x, w // 2 + DOOR_CLEAR):
            h = rng.randint(CH_H + 10, CH_H + 16)
            _building(g, x, y + 1, w, h, WOOD)
            _roof(g, x, y + 1 - h, w + 2, WOOD)
            taken.append((x, w // 2 + DOOR_CLEAR))

    # 🌳🪨 ต้นไม้กับก้อนหิน
    # ระยะห่างต้องเผื่อ "พุ่มใบ/ก้อนหิน" ที่กว้างได้ถึง ~34 ช่อง ไม่ใช่แค่ลำต้น
    # เคยพลาด: เว้นแค่ 16 ช่อง ต้นไม้เลยขึ้นชิดกันจนคลุมผิวดินทั้งเกาะ
    # ทั้งแผนที่เหลือที่ยืนได้แค่ 37 จุด เกิดไม่ได้ เดินไม่ได้ สู้ไม่ได้
    for x, y in spots:
        if not free(x, TREE_GAP):
            continue
        if rng.random() < .55:
            _tree(rng, g, x, y)
        else:
            _boulder(rng, g, x, y)
        taken.append((x, TREE_GAP))
        if len(taken) > 30:
            break


def generate(seed, continent="main"):
    """สร้างแผนที่จากเมล็ด — เมล็ดเดียวกันได้แผนที่เดียวกันเป๊ะทุกครั้ง"""
    rng = random.Random(int(seed))
    g = [[AIR] * W for _ in range(H)]

    n = rng.randint(MIN_ISLANDS, MAX_ISLANDS)
    slot = W / n
    for i in range(n):
        cx = int(slot * i + slot / 2 + rng.uniform(-slot * .22, slot * .22))
        cy = rng.randint(60, H - WATER - 55)
        half = int(rng.uniform(.28, .46) * slot)
        # หนาพอให้ทนหลุมใหญ่สุดในเกม (ลูกไฟรัศมี 26) — เดิม 18-38 ทำให้
        # ยิงนัดเดียวทะลุเกาะ คนที่ยืนอยู่ร่วงลงทะเลตายโดยไม่ทันรู้ตัว
        # วัดแล้ว: ยืนเฉย ๆ 40 เมล็ด จบเกมด้วยการตกน้ำ 27 ครั้ง
        _island(rng, g, cx, cy, half, rng.randint(34, 56))
        if rng.random() < .45:
            _arch(rng, g, cx + rng.randint(-half // 2, half // 2), cy, max(4, half // 4))

    # เกาะพื้นล่างเสมอ — ลอยหมดทั้งจอแล้วพลาดตกน้ำง่ายเกินจนไม่สนุก
    _island(rng, g, rng.randint(int(W * .25), int(W * .75)),
            H - WATER - rng.randint(24, 40), int(W * rng.uniform(.16, .26)), 68)

    _skin(g)                 # ทาหญ้า/ดิน/หิน ก่อนปลูกของ ไม่งั้นหลังคาบ้านกลายเป็นหญ้า
    _decorate(rng, g)
    return {"seed": int(seed), "w": W, "h": H, "water": WATER,
            "continent": continent, "grid": g}


# ── อ่าน/แก้พื้น ──

def solid(grid, x, y):
    """ตรงนี้ตันไหม — กำแพงบ้านกับพื้นดินตันเท่ากัน (ใบไม้ก็บัง แต่ยิงทะลุง่ายกว่า)"""
    return 0 <= x < W and 0 <= y < H and grid[y][x] != AIR


def material(grid, x, y):
    return grid[y][x] if 0 <= x < W and 0 <= y < H else AIR


def surface_at(grid, x, from_y=0):
    """ผิวที่ยืนได้จุดแรกเมื่อมองลงมาจาก from_y — None ถ้าไม่มีพื้นเลย (ตกน้ำ)

    ใบไม้ไม่นับเป็นพื้น — เดินบนพุ่มไม้ไม่ได้
    """
    if not 0 <= x < W:
        return None
    for y in range(max(0, from_y), H - WATER):
        if grid[y][x] not in (AIR, LEAF):
            return y
    return None


def surfaces_at(grid, x):
    """ผิวที่ยืนได้ **ทุกชั้น** ในคอลัมน์นี้ เรียงจากบนลงล่าง

    จำเป็นเพราะมีอาคาร: หลังคาเป็นชั้นหนึ่ง พื้นในห้องเป็นอีกชั้นหนึ่ง
    surface_at() คืนแค่ชั้นบนสุด (ที่ตกจากฟ้าแล้วเจอ) ซึ่งไม่พอสำหรับ "ยืนอยู่ในบ้าน"
    """
    if not 0 <= x < W:
        return []
    out, prev_air = [], True
    for y in range(H - WATER):
        cur = grid[y][x] not in (AIR, LEAF)
        if cur and prev_air:
            out.append(y)
        prev_air = not cur
    return out


def carve(grid, cx, cy, r):
    """💥 เจาะหลุมวงกลม — คืนพิกเซลที่หายไป ไว้ส่งให้เบราว์เซอร์ลบตาม

    ใช้ได้กับทุกอย่างเท่ากัน ดิน หิน กำแพงปราสาท ต้นไม้ พังหมดด้วยฟังก์ชันเดียว
    """
    gone = []
    for y in range(max(0, cy - r), min(H, cy + r + 1)):
        dx = int(math.sqrt(max(0, r * r - (y - cy) ** 2)))
        for x in range(max(0, cx - dx), min(W, cx + dx + 1)):
            if grid[y][x] != AIR:
                grid[y][x] = AIR
                gone.append((x, y))
    return gone


# ── 💎 ของบนแผนที่ ──

def _headroom(grid, x, y):
    """ตัวสูง CH_H กว้าง CH_W ยัดลงตรงนี้ได้ไหม

    เคยพลาด: เช็คแค่ "มีพื้นให้เหยียบ" ผู้เล่นเลยไปเกิดใต้พุ่มไม้/ในซอกหิน
    แล้วตัวจมอยู่ในเนื้อพื้นตั้งแต่วินาทีแรก
    """
    for gy in range(y - CH_H, y):
        for gx in range(x - CH_W // 2, x + CH_W // 2 + 1):
            if solid(grid, gx, gy):
                return False
    return True


def _standable(grid, x, y):
    """ยืนตรงนี้แล้วขยับได้จริงไหม — ไม่ใช่ยอดแหลม ริมผา หรือซอกที่ตัวไม่พอดี"""
    if not _headroom(grid, x, y):
        return False
    for d in range(-FLAT_SPAN, FLAT_SPAN + 1):
        s = surface_at(grid, x + d)
        if s is None or abs(s - y) > FLAT_DROP or not _headroom(grid, x + d, s):
            return False
    return True


def _open_spots(grid):
    """ผิวที่ยืนได้และไม่ได้อยู่ในกำแพง — ใช้ทั้งจุดเกิด หีบ และกับดัก"""
    return [(x, y) for x in range(8, W - 8)
            for y in [surface_at(grid, x)]
            if y is not None and y >= 10 and _standable(grid, x, y)]


def place_props(grid, rng, spots=None):
    """🎁 หีบสมบัติ + 🕳️ กับดัก วางบนผิว

    หีบเปิดแล้วสุ่มไอเทมไว้ใช้ · กับดักซ่อนไว้ เหยียบโดนถึงจะทำงาน
    (ตัวสุ่มของในหีบกับผลของกับดักอยู่ตอนทำระบบเดิน — ตรงนี้แค่วางตำแหน่ง)
    """
    pool = spots if spots is not None else _open_spots(grid)
    rng.shuffle(pool)
    out, used = [], []
    kinds = [k for k, n in PROPS.items() for _ in range(n)]
    want = min(len(kinds) + rng.randint(2, 6), max(0, len(pool) // 18))
    for x, y in pool:
        if len(out) >= want:
            break
        if any(abs(x - ux) < 22 for ux in used):
            continue
        out.append({"kind": rng.choice(kinds), "x": x, "y": y})
        used.append(x)
    return out


def spawns(grid, count, rng=None, avoid=(), spots=None):
    """จุดเกิดของผู้เล่น — ยืนได้จริง กระจายให้ห่างกันที่สุดเท่าที่แผนที่ยอมให้

    ส่ง spots เข้ามาได้ถ้าอยากจำกัดให้เกิดเฉพาะบางจุด (เช่น เกาะเดียวกันทั้งหมด)

    ⚠️ ห้ามแค่ "คัดจุดที่ห่างเกินเกณฑ์ แล้วเติมจุดที่เหลือมั่ว ๆ" — เคยพลาดแบบนั้น
       พอแผนที่แคบจนไม่มีคู่ไหนห่างถึงเกณฑ์ สองคนเลยไปเกิดห่างกัน 1 พิกเซล
       ใช้วิธีเลือกจุดที่ไกลจากคนที่เลือกไปแล้วมากที่สุดแทน ได้ระยะดีที่สุดเสมอ
    """
    rng = rng or random.Random(0)
    pool = _open_spots(grid) if spots is None else list(spots)
    ok = [(x, y) for x, y in pool if all(abs(x - p["x"]) >= 10 for p in avoid)]
    ok = ok or pool                  # เลี่ยงของบนแผนที่แล้วไม่เหลือที่ — ยอมเกิดใกล้หีบ
    if not ok:
        return []

    picked = [rng.choice(ok)]
    while len(picked) < count:
        far = max(ok, key=lambda p: min(abs(p[0] - q[0]) for q in picked))
        if far in picked:
            break                    # จุดหมดแล้ว ที่เหลือซ้ำกับที่เลือกไปแล้ว
        picked.append(far)
    while len(picked) < count:       # แผนที่มีจุดน้อยกว่าจำนวนคน — จำเป็นต้องซ้ำ
        picked.append(picked[-1])
    return sorted(picked[:count])


# ── ส่งให้เบราว์เซอร์ ──

def encode(grid):
    """RLE รายแถวแบบมีวัสดุ: `วัสดุ:จำนวน` คั่นด้วย ',' แถวคั่นด้วย ';'"""
    rows = []
    for row in grid:
        runs, cur, n = [], row[0], 0
        for v in row:
            if v == cur:
                n += 1
            else:
                runs.append(f"{cur}:{n}")
                cur, n = v, 1
        runs.append(f"{cur}:{n}")
        rows.append(",".join(runs))
    return ";".join(rows)


def decode(text, w=W, h=H):
    """คืนกริดจาก RLE — มีไว้ให้เทสพิสูจน์ว่าเข้ารหัสแล้วถอดกลับได้เหมือนเดิมเป๊ะ"""
    grid = []
    for line in text.split(";"):
        row = []
        for part in line.split(","):
            m, _, n = part.partition(":")
            row += [int(m)] * int(n)
        grid.append(row[:w] + [AIR] * max(0, w - len(row)))
    return grid[:h]


def view(seed, continent="main", players=2):
    """แผนที่พร้อมส่งขึ้นเว็บ

    🔒 กับดักส่งไปแค่ "มีกี่อัน" ไม่ส่งพิกัด — ไม่งั้นเปิด devtools แล้วเดินหลบได้หมด
       เซิร์ฟเวอร์เก็บพิกัดจริงไว้เอง เหยียบโดนเมื่อไหร่ค่อยเฉลย
    """
    from bot.game_data import CONTINENTS

    m = generate(seed, continent)
    rng = random.Random(int(seed) ^ 0x5EED)
    props = place_props(m["grid"], rng)
    return {
        "seed": m["seed"], "w": W, "h": H, "water": WATER, "continent": continent,
        "continent_label": CONTINENTS.get(continent, {}).get("label", continent),
        "terrain": encode(m["grid"]),
        "props": [p for p in props if p["kind"] != "trap"],
        "traps": sum(1 for p in props if p["kind"] == "trap"),
        "spawns": [{"x": x, "y": y}
                   for x, y in spawns(m["grid"], players, rng, avoid=props)],
    }
