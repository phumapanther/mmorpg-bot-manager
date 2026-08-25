"""🎥 กล้องต้องไถลไป ไม่ใช่วาปไป

เจ้าของเกมทัก: "แทนที่จอจะวาปไปมา ทำให้คนเล่นมึนหัว ให้จอค่อย ๆ เลื่อนไปโฟกัสดีกว่า
การเคลื่อนไหวทั้งหมดต้องดูลื่นไหล"

เดิม center() ย้ายกล้องทันที ทุกครั้งที่เปลี่ยนจุดสนใจจอเลยกระโดด — ทั้งตอนสลับตา
ตามลูกกระสุน ไล่ดูคนที่โดน และพาไปดูของที่เพิ่งลงสนาม
"""
import pathlib
import re

WEB = pathlib.Path("license_server/web_static")
PLAY = (WEB / "play.js").read_text(encoding="utf-8")
WORMS = (WEB / "worms.js").read_text(encoding="utf-8")


def _method(name):
    a = WORMS.index("  " + name)
    return WORMS[a:WORMS.index(chr(10) + "  }", a)]


def _fn(head):
    body = PLAY[PLAY.index(head):]
    return body[:body.index(chr(10) + "}")]


# ── กล้องไถล ──

def test_the_camera_has_a_target_it_eases_toward():
    assert "this.tx" in WORMS and "this.ty" in WORMS, "กล้องไม่มีเป้าให้ไถลเข้าหา"
    body = _method("glide()")
    assert "let sx = dx * this.ease, sy = dy * this.ease;" in body, \
        "ไม่ได้ขยับเข้าหาเป้าทีละนิดตามสัดส่วนระยะที่เหลือ"
    assert "this.x += sx;" in body and "this.y += sy;" in body, "ขยับแค่แกนเดียว"


def test_centering_only_sets_the_target(self=None):
    """center() ต้องตั้งเป้า ไม่ใช่ย้ายกล้องทันที — ไม่งั้นจอกระโดดเหมือนเดิม"""
    body = _method("center(mx, my, instant)")
    assert "this.tx = mx" in body, "ไม่ได้ตั้งเป้าแกน x"
    assert "this.ty = my" in body, "ไม่ได้ตั้งเป้าแกน y"
    head = body[:body.index("if (instant)")]
    assert "this.x =" not in head, "ยังย้ายกล้องทันทีอยู่ (จอจะวาป)"


def test_there_is_still_a_way_to_snap_instantly():
    """เปิดสนามครั้งแรกต้องเห็นตัวเองเลย ไม่ใช่ค่อย ๆ ไถลมาจากมุมแผนที่"""
    body = _method("center(mx, my, instant)")
    assert "if (instant) { this.x = this.tx; this.y = this.ty;" in body, \
        "ไม่มีทางจัดกล้องให้ทันทีเลย"
    fresh = PLAY[PLAY.index("WM_CAM.z = 3;"):][:400]
    assert "y - 10, true);" in fresh, \
        "เปิดสนามใหม่ไม่ได้จัดกล้องให้ทันที (จะไถลมาจากมุมแผนที่)"


def test_the_glide_runs_every_frame():
    body = PLAY[PLAY.index("function wmStartLoop("):PLAY.index("/** วาดนักสู้")]
    assert "WM_CAM.glide();" in body, "ตั้งเป้าไว้แต่ไม่มีใครขยับกล้องเข้าหา"
    assert body.index("WM_CAM.glide();") < body.index("WM.draw(ctx, WM_CAM"), \
        "ขยับกล้องหลังวาดไปแล้ว — ภาพจะช้ากว่ากล้องหนึ่งเฟรม"


def test_dragging_and_zooming_do_not_snap_back():
    """ลากดูแล้วกล้องไถลกลับเอง = ลากไม่ได้เลย"""
    for name in ("pan(dxScreen, dyScreen)", "zoomAt(dz, mx, my)"):
        assert "this.hold()" in _method(name), f"{name} ไม่ได้ตรึงเป้าไว้ที่ตำแหน่งใหม่"


def test_the_ease_is_gentle_enough_to_read():
    m = re.search(r"this\.ease = ([\d.]+)", WORMS)
    assert m, "ไม่ได้ตั้งความนุ่มของการไถล"
    ease = float(m.group(1))
    assert 0 < ease <= 0.2, f"ease {ease} แรงเกินไป จอจะยังดูกระชากอยู่"


# ── กระสุนลื่นและช้าพอให้ตามทัน ──

def test_the_shell_steps_a_fraction_at_a_time():
    m = re.search(r"WM_SHOT_STEP = ([\d.]+)", PLAY)
    assert m, "ไม่ได้ตั้งความเร็วกระสุน"
    assert float(m.group(1)) <= 0.5, f"เดินทีละ {m.group(1)} จุด เร็วเกินกว่ากล้องจะตามทัน"


def test_the_shell_is_drawn_between_path_points():
    body = PLAY[PLAY.index("  if (WM_SHOT) {"):]
    body = body[:body.index(chr(10) + "  }")]
    assert "const mix = WM_SHOT.i - at;" in body, "ไม่ได้เกลี่ยตำแหน่งระหว่างจุด"
    assert "pa[0] + (pb[0] - pa[0]) * mix" in body, "ตำแหน่งที่วาดยังกระโดดทีละจุด"
    assert "WM_SHOT.i + WM_SHOT_STEP" in body, "ยังเดินทีละจุดเต็ม ๆ"


def test_the_shell_still_lands_exactly_at_the_end():
    """เดินทีละเศษส่วนแล้วต้องไม่เลยปลายทางหรือค้างไม่ถึง"""
    body = PLAY[PLAY.index("  if (WM_SHOT) {"):]
    body = body[:body.index(chr(10) + "  }")]
    assert "Math.min(WM_SHOT.path.length, WM_SHOT.i + WM_SHOT_STEP)" in body, \
        "ไม่ได้กันไม่ให้เดินเลยปลายเส้นวิถี"
    assert "WM_SHOT.i >= WM_SHOT.path.length" in body, "ไม่มีเงื่อนไขว่ากระสุนถึงเป้าแล้ว"


def test_a_long_jump_is_capped_so_it_never_snaps():
    """ขยับ 10% ของระยะที่เหลือ ระยะไกล ๆ เฟรมแรกก็ยังกระโดดหลายสิบพิกเซล"""
    body = _method("glide()")
    assert "this.maxStep / this.z" in body, "ไม่ได้จำกัดความเร็วสูงสุดต่อเฟรม"
    assert "sx = sx / len * max" in body, "จำกัดแล้วแต่ไม่ได้ย่อทั้งสองแกนตามสัดส่วน"
    m = re.search(r"this\.maxStep = (\d+)", WORMS)
    assert m and int(m.group(1)) <= 24,         f"ปล่อยให้เลื่อนได้ {m.group(1) if m else '?'} px ต่อเฟรม ยังเห็นเป็นวาปอยู่"


def test_the_shell_never_outruns_the_camera():
    """กล้องช้ากว่ากระสุน = ตามไม่ทัน หลุดเฟรม"""
    step = float(re.search(r"WM_SHOT_STEP = ([\d.]+)", PLAY).group(1))
    cap = int(re.search(r"this\.maxStep = (\d+)", WORMS).group(1))
    # จุดในวิถีห่างกันมากสุดราว 9 px · ซูมมากสุด 5
    assert step * 9 * 5 <= cap * 1.05,         f"กระสุนวิ่ง {step * 9 * 5:.0f} px/เฟรม บนจอ แต่กล้องตามได้แค่ {cap}"


# ── ตกหลุมแล้วต้องขึ้นได้ ──

def test_you_can_walk_out_of_any_crater():
    """เจ้าของเกมทัก: ตกหลุมจากการโจมตีแล้วขึ้นไม่ได้หรือขึ้นยากมาก

    ผนังหลุมวงกลมตรงปากเกือบตั้งฉาก · กระโดดก็หัวชนผนังทันทีเพราะผนังโค้งเข้าหาตัว
    วัดแล้ว: ปีนได้ทีละ 5 px ติดหลุมรัศมี 22 ขึ้นไป ค้างอยู่ต่ำกว่าปากหลุม 7-8 px
    """
    from bot.pvp import physics as P, terrain as T

    def flat():
        g = [[T.AIR] * T.W for _ in range(T.H)]
        for x in range(T.W):
            for y in range(180, T.H - T.WATER):
                g[y][x] = T.ROCK
        return g

    stuck = []
    for r in (7, 12, 16, 22, 26, 30):
        g = flat()
        T.carve(g, 360, 180, r)
        x, y, _, _ = P.settle(g, 360, 180)
        out = False
        for _ in range(30):                       # เดินอย่างเดียว ไม่กระโดดช่วย
            w = P.walk(g, x, y, 1, 12, P.SAFE_DROP)
            if not w["path"]:
                break
            x, y = w["x"], w["y"]
            if y <= 180 and abs(x - 360) > r:
                out = True
                break
        if not out:
            stuck.append(f"r={r} (ค้างต่ำกว่าปากหลุม {y - 180} px)")
    assert not stuck, "เดินขึ้นจากหลุมไม่ได้: " + " · ".join(stuck)


def test_a_wall_as_tall_as_you_still_blocks():
    """กันแก้เกินจนปีนกำแพงปราสาทได้ ประตูจะไร้ความหมาย"""
    from bot.pvp import physics as P, terrain as T

    g = [[T.AIR] * T.W for _ in range(T.H)]
    for x in range(T.W):
        for y in range(180, T.H - T.WATER):
            g[y][x] = T.ROCK
    for x in range(400, 410):
        for y in range(180 - T.CH_H, 180):
            g[y][x] = T.BRICK
    w = P.walk(g, 390, 180, 1, 30, P.SAFE_DROP)
    assert w["x"] <= 400, f"ปีนกำแพงสูง {T.CH_H} px ขึ้นไปได้ (ไปถึง x={w['x']})"


# ── ทัวร์ของที่ลงสนาม: รอกล้องถึงก่อน แล้วค้าง 3 วินาที ──

def test_arrived_really_measures_the_distance_left():
    """arrived() ที่คืน true ตลอด = ทุกจุดที่รอกล้องจะผ่านฉลุยโดยไม่รออะไรเลย"""
    body = _method("arrived()")
    assert "Math.abs(this.tx - this.x)" in body, "ไม่ได้วัดระยะที่เหลือแกน x"
    assert "Math.abs(this.ty - this.y)" in body, "ไม่ได้วัดระยะที่เหลือแกน y"
    assert "true ||" not in body and "false ||" not in body, "มีทางลัดให้ตอบตายตัว"


def test_the_tour_waits_for_the_camera_to_arrive():
    """เจ้าของเกมสั่ง: ต้องรอจอเลื่อนไปอยู่ตรงของก่อน แล้วค่อยรอ 3 วินาที"""
    body = _fn("function wmTickTour(")
    assert "if (!WM_CAM.arrived()) return;" in body,         "เริ่มนับเวลาตั้งแต่ยังเลื่อนไม่ถึง — 3 วินาทีถูกกินไปกับการเดินทาง"
    assert body.index("WM_TOUR.aimed = true;") < body.index("WM_CAM.arrived()"),         "ยังไม่ได้ตั้งเป้าก็เช็คว่าถึงหรือยัง"


def test_the_tour_holds_three_seconds_at_each_drop():
    m = re.search(r"WM_TOUR_HOLD = (\d+)", PLAY)
    assert m, "ไม่ได้ตั้งเวลาค้างที่ของแต่ละชิ้น"
    frames = int(m.group(1))
    assert frames >= 170, f"ค้างแค่ {frames} เฟรม (~{frames / 60:.1f} วิ) ไม่ถึง 3 วินาที"
    assert "WM_TOUR.t < WM_TOUR_HOLD" in _fn("function wmTickTour("), "ตั้งค่าไว้แต่ไม่ได้ใช้"


def test_each_drop_resets_the_arrival_flag():
    body = _fn("function wmTickTour(")
    assert "WM_TOUR.aimed = false;" in body,         "ชิ้นถัดไปจะไม่ตั้งเป้าใหม่ กล้องค้างอยู่ที่ชิ้นเดิมแล้วนับเวลาไปเรื่อย"


def test_dragging_is_blocked_while_the_camera_pans_itself():
    """เจ้าของเกมสั่ง: ช่วงแพนออโต้ ทุกคนทำอะไรไม่ได้เลยแม้แต่เลื่อนจอ"""
    body = _fn("function wmTick(")
    assert "WM_CAM.locked = !!WM_AIM || wmWaiting() || !WM_CAM.arrived();" in body,         "ลากจอสวนทางกล้องที่กำลังแพนเองได้ — จะเห็นเป็นจอกระตุก"


def test_the_lock_is_not_undone_while_waiting():
    body = _fn("function wmSyncLock(")
    assert "WM_CAM.locked = false" not in body,         "ตอนรอเทิร์นกลับปลดล็อกกล้องให้ลากได้ — สวนกับการแพนอัตโนมัติ"
