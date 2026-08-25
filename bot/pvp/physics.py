"""🏃 การเคลื่อนที่ในสนามรบผลัดเทิร์น — เดิน กระโดด ตก จมน้ำ

**ทุกอย่างในไฟล์นี้ทำงานที่เซิร์ฟเวอร์เท่านั้น** เบราว์เซอร์ส่งมาแค่ "ขอเดินซ้าย 6 ก้าว"
แล้วรับ "เส้นทางที่เดินได้จริง" กลับไปเล่นภาพ ไม่มีการคำนวณตำแหน่งฝั่งเบราว์เซอร์เลย
(ถ้าให้เบราว์เซอร์คิดเอง เปิด devtools แล้วเดินทะลุกำแพง/ลอยกลางอากาศได้ทันที)

ส่งกลับเป็น "เส้นทางทีละก้าว" ไม่ใช่แค่จุดปลาย เพราะเบราว์เซอร์ต้องเล่นภาพให้เห็นว่า
เดินไปยังไง ตกยังไง — และการส่งทีละก้าวทำให้ยิงคำสั่งเป็นก้อน ไม่ต้องยิงทุก 1 ก้าว
"""
import math

from bot.pvp import terrain as T

CLIMB = 5           # ปีนขั้นสูงได้ไม่เกินนี้ (สูงกว่านี้ต้องกระโดด)
STEP_MAX = 40       # กันเบราว์เซอร์ขอเดินรวดเดียวข้ามทั้งแผนที่
GRAVITY = 0.30
JUMP_VX, JUMP_VY = 1.7, -3.6
FALL_HURT_FROM = 40         # ตกสูงเกินนี้เริ่มเจ็บ
FALL_DMG_PER_PX = 0.8


FOOT_W = 2          # ครึ่งความกว้างของกล่องชน — แคบกว่าสไปรต์ (16 px) มาก
#
# ทำไมกล่องชนถึงแคบกว่าภาพ: ถ้ากว้างเท่าภาพ ไหล่จะชนขั้นบันไดก่อนที่เท้าจะก้าวถึง
# ตัวละครเลยปีนขั้นเตี้ย ๆ ไม่ขึ้นเลย และไปติดค้างหน้าขั้นแทน
# (เกมแพลตฟอร์มทั่วไปก็แยกกล่องชนออกจากภาพแบบนี้)


def _clear(grid, x, y):
    """กล่องตัวละครที่เท้าอยู่ (x, y) ว่างไหม — ตัวอยู่เหนือเท้า ไม่รวมแถวที่เหยียบ

    ⚠️ ใบไม้ไม่กั้นทาง — เดินลอดพุ่มไม้ได้ (ลำต้นยังกั้นตามปกติ)
       เคยพลาด: นับใบไม้เป็นกำแพงตัน ต้นไม้ทุกต้นเลยตัดเกาะขาดเป็นท่อน ๆ
       ผู้เล่นสองคนอยู่เกาะเดียวกันแท้ ๆ แต่เดินหากันไม่ได้เพราะมีต้นไม้คั่น
       (surface_at() ไม่นับใบไม้เป็นพื้นอยู่แล้ว ตรงนี้ต้องสอดคล้องกัน)
    """
    for gy in range(y - T.CH_H, y):
        for gx in range(x - FOOT_W, x + FOOT_W + 1):
            if T.material(grid, gx, gy) not in (T.AIR, T.LEAF):
                return False
    return True


def standable(grid, x, y):
    """ยืนตรงนี้ได้ไหม — ตัวไม่จมกำแพง และมีพื้นรองใต้ฝ่าเท้า

    ⚠️ ฝ่าเท้าต้องแคบกว่าลำตัว เคยพลาด: เช็คพื้นตลอดความกว้างตัว (9 ช่อง)
       ตัวละครเลย "ยืน" ได้ด้วยปลายเท้าข้างเดียวเกาะขอบผา ตัวลอยเหนืออากาศ 4 ช่อง
       แล้วก้าวต่อไปไหนไม่ได้เลย — บอทไปติดค้างตรงนั้นทั้งเกม
    """
    if not (0 <= x < T.W and 0 <= y < T.H - T.WATER):
        return False
    return _clear(grid, x, y) and any(T.solid(grid, gx, y)
                                      for gx in range(x - FOOT_W, x + FOOT_W + 1))


def settle(grid, x, y, max_fall=400):
    """ปล่อยให้ตกจนถึงพื้น — คืน (x, y, ตกไปกี่พิกเซล, จมน้ำไหม)"""
    start = y
    for gy in range(y, T.H - T.WATER):
        if standable(grid, x, gy):
            return x, gy, gy - start, False
    return x, T.H - T.WATER, T.H - T.WATER - start, True      # ไม่มีพื้นเลย = ตกน้ำ


BLOCKED, MOVED, DROWNED = "blocked", "moved", "drowned"


def step(grid, x, y, direction):
    """ก้าวหนึ่งก้าว — คืน (สถานะ, x, y)

    ⚠️ ต้องแยก "ชนกำแพง" กับ "เดินตกน้ำ" ออกจากกันให้ชัด
       เคยพลาด: คืน None เหมือนกันทั้งสองกรณี พอชนกำแพงเลยถูกนับเป็นจมน้ำตายทันที
    ก้าวขึ้นได้ไม่เกิน CLIMB (ปีนขั้นบันได) · ก้าวลงได้ไม่จำกัด (ตกลงไปเฉย ๆ)
    """
    nx = x + direction
    if not 0 <= nx < T.W:
        return BLOCKED, x, y
    for ny in range(y - CLIMB, y + 1):          # ลองปีนขึ้นก่อน แล้วค่อยระดับเดิม
        if standable(grid, nx, ny):
            return MOVED, nx, ny
    if not _clear(grid, nx, y):                 # ตัวชนกำแพง = ไปต่อไม่ได้ (ยังไม่ตาย)
        return BLOCKED, x, y
    nx, ny, _, drowned = settle(grid, nx, y)    # ไม่มีพื้นข้างหน้า = เดินตกลงไป
    return (DROWNED if drowned else MOVED), nx, ny


def walk(grid, x, y, direction, steps):
    """เดินหลายก้าว — คืน {path, x, y, drowned, fell}

    หยุดเองเมื่อชนกำแพงหรือตกน้ำ ไม่ต้องให้เบราว์เซอร์คอยเช็ค
    """
    steps = max(0, min(int(steps), STEP_MAX))
    path, cx, cy = [], x, y
    drowned = False
    for _ in range(steps):
        how, nx, ny = step(grid, cx, cy, direction)
        if how == BLOCKED:
            break
        cx, cy = nx, ny
        path.append([cx, cy])
        if how == DROWNED:
            drowned = True
            break
    return {"path": path, "x": cx, "y": cy, "drowned": drowned,
            "fell": max(0, cy - y)}


def jump(grid, x, y, direction):
    """กระโดด — จำลองวิถีจริงทีละเฟรม คืนเส้นทางทั้งเส้นให้เบราว์เซอร์เล่นภาพ"""
    px, py = float(x), float(y)
    vx, vy = JUMP_VX * direction, JUMP_VY
    path, top = [], y
    for _ in range(200):
        vy += GRAVITY
        nx, ny = px + vx, py + vy
        ix, iy = int(round(nx)), int(round(ny))
        if not 0 <= ix < T.W:
            vx = -vx * .4                       # ชนขอบแผนที่ เด้งกลับเบา ๆ
            nx = px
            ix = int(round(nx))
        if iy >= T.H - T.WATER:
            path.append([ix, T.H - T.WATER])
            return {"path": path, "x": ix, "y": T.H - T.WATER,
                    "drowned": True, "fell": 0}
        if not _clear(grid, ix, iy):            # หัวหรือตัวชน — หยุดพุ่ง แล้วตกลง
            break
        px, py = nx, ny
        top = min(top, iy)
        path.append([ix, iy])
        if vy > 0 and standable(grid, ix, iy):
            return {"path": path, "x": ix, "y": iy, "drowned": False,
                    "fell": max(0, iy - top)}

    fx, fy, fell, drowned = settle(grid, int(round(px)), int(round(py)))
    path.append([fx, fy])
    return {"path": path, "x": fx, "y": fy, "drowned": drowned,
            "fell": max(0, fy - top)}


def fall_damage(fell):
    """ตกสูงเกิน FALL_HURT_FROM ถึงจะเจ็บ — ตกเตี้ย ๆ ระหว่างเดินไม่ควรเสียเลือด"""
    return int(max(0, fell - FALL_HURT_FROM) * FALL_DMG_PER_PX)


# ── 💥 กระสุน ──

SHOT_GRAVITY = 0.16      # เบากว่าตอนกระโดด กระสุนจะได้ลอยไปไกลกว่า
SHOT_SPEED = 0.09        # แรง 100 = ความเร็วต้น 9 พิกเซล/เฟรม
SHOT_FRAMES = 900        # เพดานเวลาบิน กันกระสุนลอยวนไม่จบ

# 🔒 ระยะปลอดภัยก่อนกระสุนจะระเบิดได้ — ต้องพ้นตัวคนยิงไปก่อน
#
# ⚠️ ไม่มีอันนี้แล้วยิงไม่ได้เลยจริง ๆ: วัดจากแผนที่จริง 24 นัด มี 8 นัดที่ระเบิด
#    ห่างตัวไม่ถึง 30 px ซึ่งอยู่ในรัศมี Fireball (26) พอดี = ระเบิดใส่หน้าตัวเอง
#    เพราะยืนติดบ้าน/ก้อนหิน กระสุนเลยชนของที่อยู่ข้างตัวตั้งแต่เฟรมแรก
#    ต้องกว้างกว่ารัศมีระเบิดที่แรงที่สุด (Fireball 26) ไม่งั้นยังโดนตัวเองอยู่ดี
#    และต้องวัดจาก "ปากกระบอก" ไม่ใช่จากเท้า (ปากกระบอกอยู่สูงจากเท้าราว 15 px
#    วัดจากเท้าแล้วกระสุนจะติดอาวุธตั้งแต่เฟรมแรก เท่ากับไม่ได้ใส่อะไรเลย)
ARM_DIST = 30

# ใบไม้ไม่กั้นกระสุน — ลูกไฟทะลุพุ่มไม้ได้ (ลำต้นยังกั้น)
# สอดคล้องกับการเดินที่ลอดพุ่มไม้ได้อยู่แล้ว
PASSES = (T.AIR, T.LEAF)


def _blocks(grid, x, y):
    return T.material(grid, x, y) not in PASSES


def shoot(grid, x, y, angle_deg, power, muzzle=None):
    """ยิงกระสุนแบบวิถีโค้ง — คืน {path, hit, x, y, out}

    เริ่มจากปากกระบอกที่เลื่อนออกจากตัวเล็กน้อย ไม่งั้นระเบิดใส่ตัวเองทุกนัด
    path = เส้นทางทั้งเส้นไว้ให้เบราว์เซอร์เล่นภาพ · hit = โดนพื้นไหม
    out = ออกนอกแผนที่/ตกน้ำ (ไม่ระเบิด)
    """
    rad = math.radians(float(angle_deg))
    vx = math.cos(rad) * float(power) * SHOT_SPEED
    vy = -math.sin(rad) * float(power) * SHOT_SPEED
    step = muzzle if muzzle is not None else (T.CH_W // 2 + 3)
    px = float(x) + math.cos(rad) * step
    py = float(y) - T.CH_H // 2 - math.sin(rad) * step
    sx, sy = px, py                              # ปากกระบอก — ใช้เป็นจุดตั้งต้นของระยะปลอดภัย

    # จุดแรกของเส้นวิถีต้องเป็นปากกระบอก ไม่ใช่ตำแหน่งหลังบินไปแล้วหนึ่งก้าว
    # (ก้าวหนึ่งยาวได้ถึง 9 px ตอนชาร์จเต็ม บวกระยะแขนอีก 7 = กระสุนโผล่ห่างตัว 16 px)
    path = [[int(round(px)), int(round(py))]]
    for _ in range(SHOT_FRAMES):
        vy += SHOT_GRAVITY
        px += vx
        py += vy
        ix, iy = int(round(px)), int(round(py))
        path.append([ix, iy])
        if iy >= T.H - T.WATER:                     # ตกน้ำ — จมหายไปเฉย ๆ
            return {"path": path, "hit": False, "x": ix, "y": iy, "out": True}
        if not (0 <= ix < T.W) or iy > T.H:
            return {"path": path, "hit": False, "x": ix, "y": iy, "out": True}
        armed = (px - sx) ** 2 + (py - sy) ** 2 > ARM_DIST ** 2
        if armed and iy >= 0 and _blocks(grid, ix, iy):
            return {"path": path, "hit": True, "x": ix, "y": iy, "out": False}
    return {"path": path, "hit": False, "x": int(round(px)), "y": int(round(py)),
            "out": True}


def beam(grid, x, y, angle_deg, reach=260):
    """ยิงเป็นเส้นตรง — ทะลุอากาศจนกว่าจะชนพื้น (เลเซอร์ ลูกธนู ฯลฯ)"""
    rad = math.radians(float(angle_deg))
    dx, dy = math.cos(rad), -math.sin(rad)
    px, py = float(x), float(y) - T.CH_H // 2
    path = [[int(round(px)), int(round(py))]]    # เริ่มที่อกคนยิง ไม่ใช่ห่างออกไปหนึ่งก้าว
    for i in range(int(reach)):
        px += dx
        py += dy
        ix, iy = int(round(px)), int(round(py))
        if not (0 <= ix < T.W) or iy < 0 or iy >= T.H - T.WATER:
            return {"path": path, "hit": False, "x": ix, "y": iy, "out": True}
        path.append([ix, iy])
        if i > ARM_DIST and _blocks(grid, ix, iy):
            return {"path": path, "hit": True, "x": ix, "y": iy, "out": False}
    return {"path": path, "hit": False, "x": int(round(px)), "y": int(round(py)), "out": True}


def blast_damage(dist, radius, full):
    """แรงระเบิดลดลงตามระยะ — กลางหลุมเต็ม ขอบหลุมเหลือราวหนึ่งในสาม"""
    if not full or dist > radius:
        return 0
    return max(1, int(full * (1 - 0.66 * (dist / max(radius, 1)))))


# ── 🏝️ เกาะที่เดินถึงกันได้ ──

def walk_group(grid, start, limit=3000):
    """ทุกจุดที่เดินไปถึงได้จากจุดเริ่ม — คือ "เกาะเดียวกัน" ในความหมายที่เล่นได้จริง"""
    seen, stack = {start}, [start]
    while stack and len(seen) < limit:
        x, y = stack.pop()
        for d in (-1, 1):
            how, nx, ny = step(grid, x, y, d)
            if how != MOVED or (nx, ny) in seen:
                continue
            seen.add((nx, ny))
            stack.append((nx, ny))
    return seen


def connected_spots(grid, candidates, need_span=0, least=2):
    """คัดเฉพาะจุดบนผืนแผ่นดินที่เดินถึงกันได้และ**กว้างพอ**

    ⚠️ จำเป็นจริง ๆ ไม่ใช่ของแถม: แผนที่เป็นเกาะลอย ถ้าปล่อยให้เกิดคนละเกาะ
       คลาสที่มีแต่สกิลประชิด (Warrior/Rogue) จะเข้าไม่ถึงตัวคู่ต่อสู้ได้เลยทั้งเกม

    วัดด้วย "ความกว้าง" ไม่ใช่ "จำนวนจุด" — เกาะที่มีจุดเยอะแต่แคบ
    จะทำให้สองคนเกิดมาติดกันจนยิงตายในเทิร์นแรก
    """
    # วัดความกว้างจาก "ทุกจุดที่เดินถึง" ไม่ใช่เฉพาะจุดที่ผ่านเกณฑ์จุดเกิด
    # (เกณฑ์จุดเกิดเข้มกว่าการเดินมาก ถ้าวัดจากมันจะได้ตัวเลขต่ำกว่าความจริงหลายเท่า)
    left = list(candidates)
    best, best_span, best_all = [], -1, []
    while left:
        group = walk_group(grid, left[0])
        here = [p for p in left if p in group]
        span = _span(list(group))
        if here and span > best_span:
            best, best_span, best_all = here, span, sorted(group)
        left = [p for p in left if p not in group]
    if need_span and best_span < need_span:
        return list(candidates)      # ไม่มีเกาะไหนกว้างพอ — ยอมคนละเกาะดีกว่าเกิดติดกัน
    # คืน "ทุกจุดที่เดินถึง" ไม่ใช่เฉพาะจุดที่ผ่านเกณฑ์จุดเกิดสวย
    # เกณฑ์นั้นเข้มจนจุดที่ผ่านมักกระจุกอยู่มุมเดียวของเกาะ พอเอามาเลือกจุดเกิด
    # สองคนเลยไปอยู่ใกล้กันทั้งที่เกาะกว้างพอ (ทุกจุดใน best_all ยืนได้อยู่แล้วโดยนิยาม)
    return best_all or best or list(candidates)


def _span(spots):
    return (max(p[0] for p in spots) - min(p[0] for p in spots)) if spots else 0
