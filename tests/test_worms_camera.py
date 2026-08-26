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
            w = P.walk(g, x, y, 1, 12, no_drown=True)
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
    w = P.walk(g, 390, 180, 1, 30, no_drown=True)
    assert w["x"] <= 400, f"ปีนกำแพงสูง {T.CH_H} px ขึ้นไปได้ (ไปถึง x={w['x']})"


# ── ทัวร์ของที่ลงสนาม: รอกล้องถึงก่อน แล้วค้าง 3 วินาที ──

def test_arrived_really_measures_the_distance_left():
    """arrived() ที่คืน true ตลอด = ทุกจุดที่รอกล้องจะผ่านฉลุยโดยไม่รออะไรเลย"""
    body = _method("arrived()")
    assert "Math.abs(this.tx - this.x)" in body, "ไม่ได้วัดระยะที่เหลือแกน x"
    assert "Math.abs(this.ty - this.y)" in body, "ไม่ได้วัดระยะที่เหลือแกน y"
    assert "true ||" not in body and "false ||" not in body, "มีทางลัดให้ตอบตายตัว"


def test_the_tour_is_made_of_steps_like_everything_else():
    """เจ้าของเกมเจอ: ดึงจอไปดูกล่องแล้วค้างไปเลย ไม่เลื่อนจอ ไม่ทำอะไรต่อ

    ทัวร์เคยเดินด้วยตัวจับเวลาของตัวเอง ขนานไปกับคิวขั้นตอน
    ขั้นหนึ่งของทัวร์คือ "รอกล้องเลื่อนไปถึง" แต่ลูปเล่นภาพตั้งเป้ากล้องไปที่ตัวที่ขยับ
    ทุกเฟรม กล้องเลยไม่มีวันถึง = ทัวร์ค้างตลอดกาล = ทั้งเกมค้างตาม
    """
    assert "function wmTickTour(" not in PLAY, "ยังมีตัวจับเวลาทัวร์แยกอยู่"
    body = _fn("function wmStartTour(")
    assert "wmStep(() => wmFocus({ x: d.x, y: d.y }, true)" in body, "ไม่ได้ทำขั้นเลื่อนกล้อง"
    assert "WM_CAM.arrived()" in body, "ขั้นเลื่อนกล้องไม่ได้รอให้ถึงจริง"
    assert "wmHoldAt(d.x, d.y, WM_TOUR_HOLD" in body, "ไม่ได้ค้างดูของจนครบ"
    assert "WM_TURN_SHOWN = ''" in body, "ทัวร์จบแล้วไม่ได้คืนกล้องให้คนที่ถึงตา"


def test_a_step_cannot_hang_the_game_forever():
    """กันเหตุการณ์เดิมซ้ำ — ขั้นที่ done() ไม่ยอมเป็นจริง ต้องถูกข้ามไป ไม่ใช่ค้างตาย"""
    body = _fn("function wmRunSteps(")
    assert "WM_STEP.age" in body, "ไม่ได้จับเวลาว่าขั้นนี้ค้างมานานแค่ไหน"
    assert "++WM_STEP.age < WM_STEP_MAX" in body, "ไม่มีเพดานเวลาต่อขั้น"
    m = re.search(r"WM_STEP_MAX = (\d+)", PLAY)
    assert m and int(m.group(1)) <= 1200, "เพดานสูงเกินไป ค้างเป็นนาทีกว่าจะหลุด"


def test_dragging_is_blocked_while_the_camera_pans_itself():
    """เจ้าของเกมสั่ง: ช่วงแพนออโต้ ทุกคนทำอะไรไม่ได้เลยแม้แต่เลื่อนจอ"""
    body = _fn("function wmTick(")
    assert "WM_CAM.locked = !!WM_AIM || wmWaiting() || !WM_CAM.arrived();" in body,         "ลากจอสวนทางกล้องที่กำลังแพนเองได้ — จะเห็นเป็นจอกระตุก"


def test_the_lock_is_not_undone_while_waiting():
    body = _fn("function wmSyncLock(")
    assert "WM_CAM.locked = false" not in body,         "ตอนรอเทิร์นกลับปลดล็อกกล้องให้ลากได้ — สวนกับการแพนอัตโนมัติ"


# ── กล้องต้องมีเจ้าของเดียว ──

def test_only_one_thing_owns_the_camera_at_a_time():
    """เจ้าของเกมทัก: บางทีกล้องเลื่อนสลับไปมาแบบไม่รู้จะโฟกัสอะไร

    ตอนพากล้องไปดูของที่ลงสนาม (WM_TOUR) ทั้ง WM_ANIM และ WM_SHOT ว่าง
    เงื่อนไขเดิมเลยแย่งกล้องกลับมาที่คนที่ถึงตาทุกเฟรม สลับกับทัวร์จนดูสับสน
    """
    body = PLAY[PLAY.index("function wmStartLoop("):PLAY.index("/** วาดนักสู้")]
    assert "if (!wmBusyFx() && turnKey !== WM_TURN_SHOWN)" in body,         "ยังเช็คแค่บางอย่าง — อันอื่นที่ถือกล้องอยู่จะโดนแย่ง"
    assert "!WM_ANIM && !WM_SHOT && turnKey" not in body, "ยังใช้เงื่อนไขเดิมที่ครอบไม่ครบ"


def test_the_busy_check_covers_every_camera_owner():
    body = _fn("function wmBusyFx(")
    for fx, why in [("WM_ANIM", "ท่อนที่กำลังเล่น"), ("WM_QUEUE.length", "ท่อนที่รอเล่น"),
                    ("WM_SHOT", "กระสุน"), ("WM_BOOMS.length", "ระเบิด"),
                    ("WM_AFTER.length", "งานสรุปผลที่ค้าง"), ("wmStepsBusy()", "ขั้นตอนที่ค้างอยู่"),
                    ("WM_DYING", "ภาพตาย")]:
        assert fx in body, f"ไม่ได้นับ {fx} ({why}) ว่ากำลังถือกล้องอยู่"


# ── ตัวละครต้องเคลื่อนที่ลื่น ไม่ค้างแล้วกระโดด ──

def test_the_fighter_is_interpolated_between_path_points():
    """เจ้าของเกมทัก: เวลากระโดดตัวละครวาป

    จุดในวิถีกระโดดห่างกันได้ 3-4 px · เดิมค้าง hold เฟรมแล้วกระโดดทีเดียว
    """
    body = PLAY[PLAY.index("function wmStartLoop("):PLAY.index("/** วาดนักสู้")]
    assert "WM_ANIM.i + 1 / hold" in body, "ยังเดินทีละจุดเต็ม ๆ แล้วค้างรอ"
    assert "const mix = Math.min(1, WM_ANIM.i - at);" in body,         "ไม่ได้คิดสัดส่วนระหว่างจุดจากตัวนับจริง"
    assert "pa[0] + (pb[0] - pa[0]) * mix" in body, "ไม่ได้เกลี่ยตำแหน่งระหว่างจุด"
    assert "WM_ANIM.w" not in body, "ยังมีตัวนับค้างเฟรมแบบเดิมหลงเหลืออยู่"


def test_footsteps_only_fire_when_a_real_step_is_taken():
    """เกลี่ยตำแหน่งแล้วถ้าไม่ระวัง เสียงฝีเท้าจะดังทุกเฟรม"""
    body = PLAY[PLAY.index("function wmStartLoop("):PLAY.index("/** วาดนักสู้")]
    assert "const stepped = Math.floor(WM_ANIM.i) !== before;" in body,         "ไม่ได้ดูว่าข้ามไปจุดใหม่แล้วหรือยัง"
    assert "stepped && Math.floor(WM_ANIM.i) % 3 === 0" in body, "เสียงฝีเท้าไม่ได้ผูกกับก้าวจริง"


def test_the_walk_pace_did_not_change():
    """เกลี่ยตำแหน่งแล้วความเร็วรวมต้องเท่าเดิม ไม่งั้นชนเพดานยิงคำสั่ง"""
    m = re.search(r"const hold = WM_ANIM\.path\.length <= \d+ \? (\d+) :", PLAY)
    assert m, "หาค่าหน่วงไม่เจอ"
    steps = int(re.search(r"const WM_WALK_STEPS = (\d+)", PLAY).group(1))
    ms = int(re.search(r"const WM_HOLD_MS = (\d+)", PLAY).group(1))
    played = steps * int(m.group(1)) / 60 * 1000
    assert played >= ms * 0.85, f"เล่นภาพจบใน {played:.0f}ms แต่คำสั่งถัดไปมาที่ {ms}ms"


# ── 🎬 ตัวคุมลำดับ: ทำทีละขั้น เว้นจังหวะ ไม่แย่งกัน ──

def test_there_is_one_central_step_queue():
    """เจ้าของเกมสั่ง: ทำสิ่งหนึ่งให้เสร็จก่อนเสมอ ระบบไม่ควรแย่งกันทำงาน"""
    body = _fn("function wmRunSteps(")
    assert "if (WM_WAIT > 0) { WM_WAIT--; return; }" in body, "ไม่มีช่วงเว้นจังหวะ"
    assert "WM_STEP = WM_STEPS.shift();" in body, "ไม่ได้ดึงขั้นถัดไปมาทำ"
    assert "if (!WM_STEP.on) { WM_STEP.on = true; WM_STEP.age = 0; WM_STEP.run(); return; }" in body,         "ไม่ได้เริ่มขั้นแค่ครั้งเดียว"
    assert "!WM_STEP.done()) return;" in body, "ไม่ได้รอให้ขั้นนั้นเสร็จจริงก่อนไปต่อ"


def test_the_gaps_are_what_the_owner_asked_for():
    """2 วิหลังเสร็จ · 1 วิก่อนเริ่มขั้นถัดไป"""
    after = int(re.search(r"WM_GAP_AFTER = (\d+)", PLAY).group(1))
    before = int(re.search(r"WM_GAP_BEFORE = (\d+)", PLAY).group(1))
    assert after >= 110, f"เว้นหลังเสร็จแค่ {after} เฟรม (~{after / 60:.1f} วิ) ไม่ถึง 2 วินาที"
    assert before >= 55, f"เว้นก่อนเริ่มแค่ {before} เฟรม (~{before / 60:.1f} วิ) ไม่ถึง 1 วินาที"


def test_the_queue_runs_every_frame():
    body = _fn("function wmTick(")
    assert "wmRunSteps();" in body, "เขียนคิวไว้แต่ไม่มีใครเดินคิว"


def test_a_step_waits_for_its_animation_to_finish():
    """done() ที่ตอบ true ทันที = ขั้นถัดไปเริ่มทับขั้นก่อนหน้า"""
    body = _fn("function wmFxIdle(")
    for fx in ("WM_ANIM", "WM_QUEUE.length", "WM_SHOT", "WM_BOOMS.length", "WM_DYING"):
        assert fx in body, f"ไม่ได้นับ {fx} ว่าขั้นนั้นยังทำงานอยู่"


def test_every_beat_goes_through_the_queue():
    """ตาบอท · บอทยิง · คนที่โดนแต่ละคน · ร่างระเบิดแต่ละร่าง ต้องเป็นขั้นทั้งหมด"""
    for fn, why in [("function wmQueueBot(", "ตาบอทเดิน"),
                    ("function wmPlayBotShots(", "บอทยิง"),
                    ("function wmPlayVictims(", "คนที่โดน"),
                    ("function wmPlayDeaths(", "ร่างระเบิด")]:
        assert "wmStep(" in _fn(fn), f"{why} ไม่ได้เข้าคิวขั้นตอน — จะไปทับขั้นอื่น"


def test_nothing_can_act_while_a_step_is_running():
    for fn, why in [("function wmWaiting(", "ปุ่มบังคับ"), ("function wmBusyFx(", "แผงสรุปผล/กล้อง")]:
        assert "wmStepsBusy()" in _fn(fn), f"{why} ไม่ได้นับช่วงที่มีขั้นค้างอยู่"


def test_a_new_match_clears_the_queue():
    body = PLAY[PLAY.index("function wmApply("):PLAY.index("function wmMe(")]
    assert "wmStepsClear();" in body, "เปิดสนามใหม่แล้วขั้นของสนามเก่ายังค้างอยู่ในคิว"
