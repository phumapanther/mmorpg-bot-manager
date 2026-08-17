"""🏃 การเคลื่อนที่ในสนามรบผลัดเทิร์น — เดิน กระโดด ตก จมน้ำ

**ทุกอย่างในไฟล์นี้ทำงานที่เซิร์ฟเวอร์เท่านั้น** เบราว์เซอร์ส่งมาแค่ "ขอเดินซ้าย 6 ก้าว"
แล้วรับ "เส้นทางที่เดินได้จริง" กลับไปเล่นภาพ ไม่มีการคำนวณตำแหน่งฝั่งเบราว์เซอร์เลย
(ถ้าให้เบราว์เซอร์คิดเอง เปิด devtools แล้วเดินทะลุกำแพง/ลอยกลางอากาศได้ทันที)

ส่งกลับเป็น "เส้นทางทีละก้าว" ไม่ใช่แค่จุดปลาย เพราะเบราว์เซอร์ต้องเล่นภาพให้เห็นว่า
เดินไปยังไง ตกยังไง — และการส่งทีละก้าวทำให้ยิงคำสั่งเป็นก้อน ไม่ต้องยิงทุก 1 ก้าว
"""
from bot.pvp import terrain as T

CLIMB = 5           # ปีนขั้นสูงได้ไม่เกินนี้ (สูงกว่านี้ต้องกระโดด)
STEP_MAX = 40       # กันเบราว์เซอร์ขอเดินรวดเดียวข้ามทั้งแผนที่
GRAVITY = 0.30
JUMP_VX, JUMP_VY = 1.7, -3.6
FALL_HURT_FROM = 40         # ตกสูงเกินนี้เริ่มเจ็บ
FALL_DMG_PER_PX = 0.8


def _clear(grid, x, y):
    """กล่องตัวละครที่เท้าอยู่ (x, y) ว่างไหม — ตัวอยู่เหนือเท้า ไม่รวมแถวที่เหยียบ"""
    half = T.CH_W // 2
    for gy in range(y - T.CH_H, y):
        for gx in range(x - half, x + half + 1):
            if T.solid(grid, gx, gy):
                return False
    return True


def standable(grid, x, y):
    """ยืนตรงนี้ได้ไหม — ตัวไม่จมกำแพง และมีพื้นรองเท้า"""
    if not (0 <= x < T.W and 0 <= y < T.H - T.WATER):
        return False
    return _clear(grid, x, y) and any(T.solid(grid, gx, y)
                                      for gx in range(x - T.CH_W // 2, x + T.CH_W // 2 + 1))


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
