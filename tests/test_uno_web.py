"""🎴 ศึกไพ่รูนบนเว็บ — ปุ่มในเมนู หน้าโต๊ะ และ API

เทสสำคัญที่สุด: HTTP จริงต้องไม่ส่งไพ่คนอื่นลงมา
(เทสที่ระดับฟังก์ชันผ่านแล้วไม่พอ — ต้องคุมที่คำตอบจริงอีกชั้น
 แบบเดียวกับกับดักในสนามรบผลัดเทิร์น)
"""
import collections
import json
import pathlib
import time

import pytest

WEB = pathlib.Path("license_server/web_static")
HTML = (WEB / "play.html").read_text(encoding="utf-8")
JS = (WEB / "uno.js").read_text(encoding="utf-8")
PLAY_JS = (WEB / "play.js").read_text(encoding="utf-8")
CSS = (WEB / "play.css").read_text(encoding="utf-8")


@pytest.fixture
def web(tmp_path, monkeypatch):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    import bot.models.player_model as pm
    from license_server import web_api

    uid = 7710
    monkeypatch.setattr(pm, "DB_NAME", str(tmp_path / "w.db"))
    pm.init_db()
    pm.get_player(uid)
    from license_server.api_web import deps as _api_web_deps

    monkeypatch.setattr(_api_web_deps, "GAME_DB_PATH", tmp_path / "w.db")

    monkeypatch.setattr(web_api, "GAME_DB_PATH", tmp_path / "w.db")  # เผื่อโค้ดเก่าอ่านผ่าน web_api
    app = FastAPI()
    app.include_router(web_api.router)
    c = TestClient(app)
    c.cookies.set("web_session", web_api.sign({"uid": str(uid), "exp": time.time() + 3600}))
    return c


# ── 🔒 HTTP ต้องไม่รั่วไพ่คนอื่น ──

def test_http_never_leaks_other_hands(web):
    """คำตอบจริงจากเซิร์ฟเวอร์ต้องไม่มีไพ่ของคู่แข่งปนมา"""
    d = web.post("/api/web/uno", json={"action": "start", "bots": 3}).json()
    table = d["table"]

    sent = collections.Counter()

    def count(x):
        if isinstance(x, dict):
            if set(x) == {"suit", "value"}:
                sent[(x["suit"], x["value"])] += 1
            else:
                for v in x.values():
                    count(v)
        elif isinstance(x, list):
            for i in x:
                count(i)

    count(table)
    allowed = collections.Counter((c["suit"], c["value"]) for c in table["hand"])
    allowed[(table["top"]["suit"], table["top"]["value"])] += 1
    for key, n in sent.items():
        assert n <= allowed[key], f"HTTP ส่งไพ่ {key} เกินที่ควรเห็น ({n} ใบ)"


def test_http_never_leaks_the_draw_pile(web):
    d = web.post("/api/web/uno", json={"action": "start"}).json()
    assert "deck" not in d["table"]
    assert isinstance(d["table"]["deck_left"], int)


def test_http_hides_the_bot_hand_too(web):
    """ไพ่บอทก็ต้องซ่อน ไม่งั้นเปิด DevTools ชนะบอทตลอดกาล"""
    d = web.post("/api/web/uno", json={"action": "start"}).json()
    for p in d["table"]["players"]:
        assert "hand" not in p, "ส่งมือของผู้เล่นคนอื่นมาด้วย"


# ── API ทำงานจริง ──

def test_you_can_open_a_table_over_http(web):
    d = web.post("/api/web/uno", json={"action": "start"}).json()
    assert d["ok"] and d["table"]["playing"]
    assert len(d["table"]["hand"]) == 7


def test_the_table_is_still_there_on_the_next_request(web):
    """ปิดหน้าเว็บแล้วเปิดใหม่ต้องเจอโต๊ะเดิม"""
    web.post("/api/web/uno", json={"action": "start"})
    d = web.get("/api/web/uno").json()
    assert d["table"]["playing"]


def test_no_table_yet_is_not_an_error(web):
    d = web.get("/api/web/uno").json()
    assert d["ok"] and d["table"] == {"playing": False}


def test_quitting_clears_the_table(web):
    web.post("/api/web/uno", json={"action": "start"})
    web.post("/api/web/uno", json={"action": "quit"})
    assert web.get("/api/web/uno").json()["table"] == {"playing": False}


def test_an_unknown_command_is_refused(web):
    assert web.post("/api/web/uno", json={"action": "ระเบิด"}).status_code == 400


def test_playing_an_illegal_card_is_refused_over_http(web):
    """เบราว์เซอร์แก้โค้ดแล้วส่งไพ่มั่วมาต้องไม่ผ่าน"""
    web.post("/api/web/uno", json={"action": "start"})
    r = web.post("/api/web/uno", json={"action": "play", "index": 999})
    assert r.status_code == 400


def test_you_can_draw_over_http(web):
    web.post("/api/web/uno", json={"action": "start"})
    before = len(web.get("/api/web/uno").json()["table"]["hand"])
    r = web.post("/api/web/uno", json={"action": "draw"})
    assert r.status_code in (200, 400)      # จั่วได้ หรือมีไพ่วางได้อยู่แล้ว
    if r.status_code == 200:
        after = len(r.json()["table"]["hand"])
        assert after >= before


def test_a_stranger_cannot_touch_the_table(web):
    """ไม่มีคุกกี้ = เล่นไม่ได้"""
    web.cookies.clear()
    assert web.post("/api/web/uno", json={"action": "start"}).status_code in (401, 403)


# ── ปุ่มและหน้าจอ ──

def test_the_casino_menu_has_a_card_game_button():
    i = HTML.index("<h3>คาสิโน</h3>")
    # ตัดถึง <h3> ของหมวดถัดไป — ทนการจัดรูปแบบ HTML ใหม่ (ไม่พึ่ง </div></div> ติดกัน)
    section = HTML[i:HTML.index("<h3>", i + 4)]
    assert 'data-go="uno"' in section, "ไม่มีปุ่มเกมไพ่ในหมวดคาสิโน"
    assert "ศึกไพ่รูน" in section


def test_the_game_screen_exists():
    assert 'id="v-uno"' in HTML
    assert 'id="unoCanvas"' in HTML


def test_opening_the_screen_loads_the_table():
    assert "if (id === 'uno') fillUno();" in PLAY_JS, "เปิดหน้าแล้วไม่ได้โหลดโต๊ะ"


def test_the_page_loads_the_card_script():
    assert '<script src="/uno.js"></script>' in HTML


def test_the_screen_has_its_own_styles():
    assert ".uno-stage" in CSS and ".uno-suits" in CSS


# ── กติกาเหล็กฝั่งเบราว์เซอร์ ──

def test_the_browser_only_sends_button_presses():
    """เบราว์เซอร์ห้ามตัดสินกฎเอง — ส่งไปแค่ว่ากดอะไร แล้วรอคำตอบ"""
    # ต้องอ่านรายการ playable ที่เซิร์ฟเวอร์ส่งมา ไม่ใช่คิดกฎเอง
    assert "UNO.playable" in JS, "ไม่ได้ใช้รายการที่เซิร์ฟเวอร์ส่งมา"
    # ห้ามมีตัวตัดสินว่า "วางได้หรือไม่" อยู่ฝั่งนี้
    # (เทียบ value เพื่อดูว่าเป็นไวลด์ไหมจะได้ถามสี — ไม่ใช่การตัดสินกฎ)
    for banned in ("canPlay", "isPlayable", "matches(", "R.playable"):
        assert banned not in JS, f"เบราว์เซอร์ตัดสินกฎเอง ({banned})"
    # การวางไพ่ต้องยิงไปถามเสมอ ไม่ใช่ตัดสินจบในจอ
    assert "unoDo('play'" in JS
    assert "'play'" in JS, "ไม่ได้ส่งคำสั่งวางไพ่ไปหาเซิร์ฟเวอร์"


def test_the_browser_draws_only_card_backs_for_others():
    """คู่แข่งต้องวาดจากจำนวนใบ ไม่ใช่จากตัวไพ่ (ซึ่งไม่เคยถูกส่งมา)"""
    assert "p.cards" in JS, "ไม่ได้ใช้จำนวนไพ่ของคู่แข่งมาวาด"


def test_a_wild_asks_for_a_colour_before_playing():
    """วางไวลด์โดยไม่เลือกสี = เซิร์ฟเวอร์ปฏิเสธ ตาไม่เดิน เกมค้าง"""
    assert "unoAskSuit" in JS
    i = JS.index("const up = async ()")
    body = JS[i:JS.index("cv.addEventListener('mousedown'", i)]
    assert "unoAskSuit" in body, "ลากไวลด์ลงกองแล้วไม่ถามสี"


def test_the_animation_runs_on_real_time():
    """จอ 60 Hz กับ 144 Hz ต้องเร็วเท่ากัน (บทเรียนจากสนามรบผลัดเทิร์น)"""
    assert "UNO_DT" in JS and "requestAnimationFrame" in JS
    assert "Math.min(3, gap * 60 / 1000)" in JS


def test_cards_can_be_dragged_onto_the_pile():
    for fn in ("unoHit", "unoNearPile", "touchstart"):
        assert fn in JS, f"ขาด {fn} — ลากไพ่ไม่ได้"


def test_unplayable_cards_are_dimmed():
    """ไม่หรี่ = ลากแล้วเด้งกลับโดยไม่รู้ว่าทำไม"""
    assert "dim" in JS and "playable" in JS


# ── ✨ ขอบเรืองแสงบอกไพ่ที่ลงได้ (เจ้าของเกมสั่ง 08-29) ──

def test_playable_cards_get_a_glowing_border():
    """ไพ่ที่ลงได้ต้องมีขอบทองเรืองแสง ไม่ใช่แค่หรี่ใบที่ลงไม่ได้"""
    assert "glow" in JS, "ไม่มีขอบเรืองแสงเลย"
    i = JS.index("function unoDrawCard")
    body = JS[i:JS.index("function unoFan", i)]
    assert "c.glow" in body, "วาดไพ่แล้วไม่ได้เช็คว่าต้องเรืองแสงไหม"
    assert "shadowBlur" in body and "#e8b04b" in body, "ขอบไม่ได้เรืองแสงสีทอง"


def test_the_glow_marks_exactly_the_playable_cards():
    """รันตรรกะจริงจาก uno.js — เช็คข้อความอย่างเดียวจับตรรกะผิดไม่ได้

    เคยพลาด: เทสที่ดูแค่ว่าโค้ดมีคำว่า glow ไหม ผ่านหมดแม้จะเรืองทุกใบ
    หรือไม่เรืองสักใบก็ตาม
    """
    import shutil
    import subprocess

    if not shutil.which("node"):
        pytest.skip("เครื่องนี้ไม่มี node")
    r = subprocess.run(["node", "tests/uno_glow.js"],
                       capture_output=True, text=True, encoding="utf-8")
    assert r.returncode == 0, r.stdout + r.stderr


def test_the_glow_is_drawn_under_the_card_not_over_it():
    """วาดทับหน้าไพ่ = อ่านเลขไม่ออก ต้องวาดก่อนตัวไพ่"""
    i = JS.index("function unoDrawCard")
    body = JS[i:JS.index("function unoFan", i)]
    assert body.index("c.glow") < body.index("showFace ? '#f2e7d8'"), \
        "วาดขอบเรืองทับหน้าไพ่"


def test_the_pulse_follows_real_time():
    """แสงเต้นต้องเดินตามเวลาจริง ไม่งั้นจอ 144 Hz เต้นเร็วกว่า 2 เท่า"""
    assert "UNO_PULSE += 0.07 * UNO_DT" in JS


# ── ❓ ปุ่มคู่มือไพ่ ──

def test_there_is_a_help_button_on_the_game_screen():
    i = HTML.index('id="v-uno"')
    section = HTML[i:HTML.index('<!-- ══', i + 10)]
    assert 'id="unoHelpBtn"' in section, "ไม่มีปุ่ม ? ในหน้าเกม"
    # ทนช่องว่าง/ขึ้นบรรทัดใหม่จากการจัดรูปแบบ IDE — เดิมเช็คแบบเป๊ะ ">?<"
    btn = section[section.index('id="unoHelpBtn"'):section.index("</button>", section.index('id="unoHelpBtn"'))]
    assert "?" in btn, "ปุ่มไม่ได้เขียนว่า ?"


def test_the_help_box_starts_hidden():
    """เปิดเกมมาต้องไม่มีกล่องบังจอ ต้องกดถึงจะขึ้น"""
    i = HTML.index('id="unoHelp"')
    assert "hidden" in HTML[i:i + 60], "กล่องคู่มือโผล่ทับจอตั้งแต่เปิดเกม"


def test_the_help_button_opens_and_closes_the_box():
    assert "unoHelpBtn" in JS and "unoHelpClose" in JS
    assert "unoHelp(true)" in JS and "unoHelp(false)" in JS


def test_escape_also_closes_the_help():
    """คนชินคีย์บอร์ดจะกด Esc ก่อนหาปุ่มกากบาท"""
    assert "'Escape'" in JS


def test_the_help_explains_every_action_card():
    """ไพ่ท่าพิเศษทุกใบต้องมีคำอธิบาย ไม่งั้นเจอใบที่ไม่รู้จักแล้วงง"""
    i = HTML.index('id="unoHelp"')
    # ใช้ marker หมวดถัดไปเป็นขอบเขต — ทนการจัดรูปแบบ HTML ใหม่
    box = HTML[i:HTML.index("<!-- ══", i + 10)]
    for name in ("ม่านสะกด", "วาร์ปกลับทาง", "ทัณฑ์สองใบ",
                 "ศิลาเปลี่ยนธาตุ", "ประตูนิรันดร์"):
        assert name in box, f"คู่มือไม่ได้อธิบาย {name}"


def test_the_help_explains_how_to_play_a_card():
    i = HTML.index('id="unoHelp"')
    box = HTML[i:HTML.index("<!-- ══", i + 10)]
    assert "สีตรง" in box and "ลาก" in box, "ไม่ได้บอกวิธีลงไพ่"
    assert "เรืองแสง" in box, "ไม่ได้บอกว่าขอบเรืองแสงแปลว่าลงได้"


def test_the_help_explains_stacking():
    """สแตคเป็นกติกาที่งงที่สุด ต้องอธิบาย"""
    i = HTML.index('id="unoHelp"')
    box = HTML[i:HTML.index("<!-- ══", i + 10)]
    assert "สแตค" in box and "ยอมจั่ว" in box


def test_the_help_box_is_translucent_but_readable():
    """เจ้าของเกมสั่ง: กล่องโปร่งใสแต่สีทึบพอ"""
    i = CSS.index(".uno-help {")
    block = CSS[i:CSS.index("}", i)]
    assert "rgba(23,17,13,.90)" in block, "พื้นกล่องไม่โปร่ง หรือทึบเกินไป"
    assert "backdrop-filter" in block, "ไม่ได้เบลอฉากหลัง อ่านยาก"


def test_the_help_scrolls_when_it_is_too_long():
    i = CSS.index(".uno-help {")
    block = CSS[i:CSS.index("}", i)]
    assert "overflow-y:auto" in block, "เนื้อหายาวเกินจอแล้วเลื่อนดูไม่ได้"


# ── 🐞 บั๊กปุ่มเลือกสีค้าง (เจ้าของเกมเจอ 08-29) ──

def test_the_colour_picker_closes_after_choosing():
    """กดเลือกสีแล้วไพ่ต้องหาย

    บั๊กเก่า (สมัยยังเป็นปุ่ม): กดแล้วปุ่มค้างคาหน้าจอ
    ตอนนี้เป็นไพ่ลอยบนจอ กดแล้วต้องล้างทั้งไพ่และไพ่ที่รออยู่
    """
    i = JS.index("if (UNO_SUIT_CARDS.length) {")
    body = JS[i:i + 600]
    assert "UNO_SUIT_CARDS = []" in body, "เลือกสีแล้วไพ่ยังลอยค้างอยู่"
    assert "UNO_PICK = null" in body, "ไม่ได้ล้างไพ่ที่รอเลือกสี"


# ── 🂠 กองจั่วบนโต๊ะ ──

def test_there_is_a_draw_pile_on_the_table():
    assert "unoPilePos" in JS, "ไม่มีจุดวางกองจั่ว"
    assert "deck_left" in JS, "ไม่ได้ใช้จำนวนไพ่ที่เหลือมาวาดกอง"


def test_clicking_the_pile_draws_a_card():
    i = JS.index("const down = e =>")
    body = JS[i:JS.index("const move = e =>", i)]
    assert "unoOnDeck" in body, "กดกองจั่วแล้วไม่มีอะไรเกิดขึ้น"
    assert "'draw'" in body, "กดกองจั่วแล้วไม่ได้สั่งจั่ว"


def test_clicking_the_pile_answers_a_stack_too():
    """โดนสแตคอยู่แล้วกดกอง = ยอมจั่วทั้งกอง ไม่ใช่จั่วใบเดียว"""
    i = JS.index("const down = e =>")
    body = JS[i:JS.index("const move = e =>", i)]
    assert "'take'" in body


def test_the_pile_glows_when_drawing_is_the_only_option():
    """เจ้าของเกมสั่ง: ทำอะไรไม่ได้นอกจากจั่ว ให้ขึ้นขอบเหลืองที่กองไพ่"""
    assert "unoMustDraw" in JS
    i = JS.index("function unoMustDraw")
    body = JS[i:JS.index("function unoOnDeck", i)]
    assert "UNO.playable" in body, "ไม่ได้ดูว่ามีไพ่ลงได้ไหม"
    assert "UNO.drew" in body, "จั่วไปแล้วยังเรืองอยู่อีก"
    # เช็คตาผ่าน unoMyTurn() แล้ว (รวม UNO_THINK ด้วย)
    assert "unoMyTurn()" in body, "ตาคนอื่นก็เรือง"


def test_drawing_a_card_makes_it_fly_from_the_pile():
    assert "unoFlyDraw" in JS, "จั่วไพ่แล้วไม่มีอนิเมชัน"
    i = JS.index("function unoFlyDraw")
    body = JS[i:JS.index("function unoApply", i)]
    assert "unoPilePos" in body, "ไพ่ไม่ได้บินออกมาจากกองจั่ว"


# ── 🏁 อนิเมชันประกาศอันดับ ──

def test_finishing_shows_a_fanfare():
    assert "unoCheckFanfare" in JS and "unoDrawFanfare" in JS


def test_first_place_is_grander_than_second_and_third():
    """เจ้าของเกมสั่ง: ที่ 1 อลัง · ที่ 2-3 มีแต่ไม่เด่นเท่า"""
    i = JS.index("function unoCheckFanfare")
    body = JS[i:JS.index("function unoDrawFanfare", i)]
    assert "place === 1 ? 90" in body, "ที่ 1 ไม่ได้อลังกว่าคนอื่น"
    i2 = JS.index("const UNO_PLACE_MS")
    line = JS[i2:JS.index("\n", i2)]
    assert "1: 190" in line and "2: 120" in line, "ที่ 1 ไม่ได้ค้างนานกว่า"


def test_fourth_place_gets_no_fanfare():
    """เจ้าของเกมสั่ง: ส่วนที่เหลือไม่มีอนิเมชัน"""
    i = JS.index("function unoCheckFanfare")
    body = JS[i:JS.index("function unoDrawFanfare", i)]
    assert "place > 3) return" in body, "ที่ 4 ขึ้นไปก็ยังมีอนิเมชัน"


def test_each_place_is_only_celebrated_once():
    """ไม่งั้นทุกครั้งที่วาดใหม่จะฉลองซ้ำไม่จบ"""
    assert "UNO_SEEN_PLACE" in JS


def test_the_fanfare_fades_away_by_itself():
    """เจ้าของเกมสั่ง: ขึ้นมาแล้วหายไป ให้คนที่เหลือเล่นต่อ"""
    i = JS.index("function unoDrawFanfare")
    body = JS[i:JS.index("function unoFlyDraw", i)] if "function unoFlyDraw" in JS[i:] else JS[i:i + 2000]
    assert "UNO_FANFARE = null" in body, "แผงประกาศค้างจอไม่หายเอง"


def test_a_player_who_is_out_sees_they_are_watching():
    assert "my_place" in JS, "ไม่ได้บอกว่าเราเข้าเส้นชัยอันดับไหน"
    assert "นั่งดู" in JS, "ไม่ได้บอกว่ากำลังนั่งดูเพื่อนเล่น"


def test_the_final_ranking_is_shown_at_the_end():
    assert "unoPlaceText" in JS


# ── 🐞🎨 บั๊กไพ่คว่ำ/เปลี่ยนสี + ที่นั่งล้อมวง (เจ้าของเกมเจอ+สั่ง 08-29) ──

def test_the_animation_logic_actually_works():
    """รันตรรกะจริงจาก uno.js — เทสข้อความจับบั๊กพวกนี้ไม่ได้

    คุม 3 อย่าง: จั่วแล้วไพ่พลิกหงายจริง · ไพ่ไม่เปลี่ยนสีตอนเลื่อนช่อง ·
    ที่นั่งล้อมวงอยู่ในจอและไม่ทับกัน ตั้งแต่ 2 ถึง 6 คน
    """
    import shutil
    import subprocess

    if not shutil.which("node"):
        pytest.skip("เครื่องนี้ไม่มี node")
    r = subprocess.run(["node", "tests/uno_anim.js"],
                       capture_output=True, text=True, encoding="utf-8")
    assert r.returncode == 0, r.stdout + r.stderr


def test_drawing_flips_the_card_face_up():
    """บั๊ก: ลูปวาดไล่ค่า x/y/rot แต่ลืม face — จั่วแล้วไพ่ค้างคว่ำตลอด"""
    i = JS.index("      c.t = Math.min(c.dur, c.t + UNO_DT);")
    body = JS[i:JS.index("      if (c.t >= c.dur)", i)]
    assert "c.face" in body, "อนิเมชันไม่ได้ไล่ค่าหน้าไพ่ จั่วแล้วไพ่คว่ำ"


def test_cards_are_matched_by_face_not_by_slot():
    """บั๊ก: จำไพ่ด้วยเลขช่อง พอไพ่เลื่อนช่องก็กลายเป็นคนละใบ = เปลี่ยนสีเอง"""
    i = JS.index("function unoLayout")
    body = JS[i:JS.index("function unoHit", i)]
    assert "const old = keep[i]" not in body, "ยังจำไพ่ด้วยเลขช่องอยู่"
    assert "c.card.suit}:${c.card.value" in body, "ไม่ได้จำด้วยหน้าไพ่"


def test_you_can_choose_how_many_bots_to_play_with():
    i = HTML.index('id="v-uno"')
    section = HTML[i:HTML.index("<!-- ══", i + 10)]
    assert 'data-bots="1"' in section and 'data-bots="5"' in section, "เลือกจำนวนบอทไม่ได้"
    assert "UNO_BOTS" in JS, "ไม่ได้ส่งจำนวนบอทไปให้เซิร์ฟเวอร์"


def test_the_chosen_bot_count_is_actually_used():
    i = JS.index("document.getElementById('unoStart')")
    body = JS[i:i + 400]
    assert "bots: UNO_BOTS" in body, "กดเปิดโต๊ะแล้วยังใช้จำนวนบอทค่าตายตัว"


def test_players_sit_around_the_table():
    assert "unoSeats" in JS
    i = JS.index("function unoSeats")
    body = JS[i:JS.index("function unoFan", i)]
    assert "Math.cos(a)" in body and "Math.sin(a)" in body, "ที่นั่งไม่ได้วางเป็นวง"


def test_the_seat_shows_a_person_or_a_bot_icon():
    assert "'🤖'" in JS and "'🧑'" in JS, "ไม่มีไอคอนคน/บอทที่ที่นั่ง"


def test_only_the_player_whose_turn_it_is_gets_an_aura():
    """เจ้าของเกมสั่ง: ออร่าโฟกัสทีละคน"""
    i = JS.index("unoSeats(cv).forEach")
    body = JS[i:JS.index("UNO_CARDS.forEach", i)]
    assert "s.index === UNO.turn" in body, "ออร่าไม่ได้ผูกกับคนที่ถึงตา"
    assert "createRadialGradient" in body, "ไม่มีออร่าเรือง"


def test_a_player_who_is_out_is_shown_faded_with_their_place():
    i = JS.index("unoSeats(cv).forEach")
    body = JS[i:JS.index("UNO_CARDS.forEach", i)]
    assert "s.out" in body, "คนที่ออกไปแล้วยังดูเหมือนกำลังเล่น"
    assert "s.place" in body, "ไม่ได้โชว์อันดับที่ที่นั่ง"


def test_opponent_cards_are_drawn_from_the_count_only():
    """ยังต้องวาดหลังไพ่จากจำนวน ไม่ใช่ตัวไพ่ (ซึ่งไม่เคยถูกส่งมา)"""
    i = JS.index("unoSeats(cv).forEach")
    body = JS[i:JS.index("UNO_CARDS.forEach", i)]
    assert "s.cards" in body


# ── 🧲 ดูดไพ่เข้ากอง + ตัดปุ่มจั่ว (เจ้าของเกมสั่ง 08-29) ──

def test_dragging_a_card_off_the_hand_drops_it():
    """เจ้าของเกมเจอ: ลากวางบางทีไม่ตรงแล้วไม่ลงเลย

    เดิมต้องลากเข้าใกล้กองภายใน 150px — บนมือถือเล็งเล็กกว่านั้นยาก
    ตอนนี้ลากพ้นแถวไพ่ในมือขึ้นมาก็ถือว่าวาง แล้วไพ่ดูดเข้ากองเอง
    """
    i = JS.index("function unoNearPile")
    body = JS[i:JS.index("function unoFrame", i)]
    assert "cv.height" in body, "ยังตัดสินจากระยะห่างกองอย่างเดียว"


def test_the_card_slides_into_the_pile_by_itself():
    i = JS.index("const up = async ()")
    body = JS[i:JS.index("cv.addEventListener('mousedown'", i)]
    drop = body[body.index("const t = unoPilePos"):body.index("unoBurst")]
    # ต้องมีครบทั้งชุด: ตั้งท่า ตั้งจุดเริ่ม ตั้งจุดจบ ไม่งั้นไพ่ค้างกลางอากาศ
    assert "c.anim" in drop, "ปล่อยแล้วไพ่ไม่ดูดเข้ากอง"
    assert "c.from" in drop and "c.to" in drop, "ตั้งท่าไม่ครบ ไพ่จะค้างกลางอากาศ"
    assert "t.x" in drop and "t.y" in drop, "ไพ่ไม่ได้ดูดไปที่กองทิ้ง"


def test_the_pile_glows_when_you_must_take_a_stack_too():
    """เจ้าของเกมสั่ง: ไม่ว่าจะยอมจั่วหรือต้องจั่วเอง ก็ให้เรืองแสง"""
    i = JS.index("function unoMustDraw")
    body = JS[i:JS.index("function unoOnDeck", i)]
    assert "if (UNO.must_answer) return false" not in body, \
        "โดนสแตคแล้วกองไม่เรือง ทั้งที่ต้องยอมจั่ว"


def test_the_draw_buttons_are_gone():
    """เจ้าของเกมสั่ง: เหลือแค่เปิดโต๊ะ ผ่าน และ UNO"""
    i = HTML.index('id="v-uno"')
    section = HTML[i:HTML.index("<!-- ══", i + 10)]
    assert 'id="unoDraw"' not in section, "ยังมีปุ่มจั่วไพ่"
    assert 'id="unoTake"' not in section, "ยังมีปุ่มยอมจั่ว"


def test_the_buttons_that_remain_are_the_three_asked_for():
    i = HTML.index('id="v-uno"')
    section = HTML[i:HTML.index("<!-- ══", i + 10)]
    for keep in ("unoStart", "unoPass", "unoSayUno"):
        assert f'id="{keep}"' in section, f"ปุ่ม {keep} หายไปด้วย"


def test_nothing_still_points_at_the_removed_buttons():
    """เหลือโค้ดอ้างปุ่มที่ลบไปแล้ว = คลิกไม่ติดโดยไม่มีใครรู้"""
    for gone in ("unoDraw", "unoTake"):
        assert f"'{gone}'" not in JS, f"ยังมีโค้ดอ้างถึงปุ่ม {gone}"


def test_the_help_tells_you_to_click_the_pile():
    i = HTML.index('id="unoHelp"')
    box = HTML[i:HTML.index("<!-- ══", i + 10)]
    assert "กดที่กองไพ่" in box, "คู่มือยังบอกให้กดปุ่มที่ลบไปแล้ว"


# ── 🏁🎴 ตารางอันดับ · ไพ่เลือกสี · บอทคิด (เจ้าของเกมสั่ง 08-29) ──

def test_the_end_shows_a_ranking_table():
    i = HTML.index('id="v-uno"')
    section = HTML[i:HTML.index("<!-- ══", i + 10)]
    assert 'id="unoOver"' in section and 'id="unoRank"' in section, "ไม่มีตารางอันดับตอนจบ"


def test_the_ranking_offers_play_again_and_leave():
    i = HTML.index('id="unoOver"')
    box = HTML[i:HTML.index("</div>", HTML.index("uno-over-btns", i))]
    assert 'id="unoAgain"' in box and 'id="unoLeave"' in box, "ไม่มีปุ่มเล่นต่อ/ออกจากเกม"


def test_the_ranking_only_shows_when_the_game_is_over():
    """โผล่กลางเกม = บังจอจนเล่นไม่ได้"""
    i = JS.index("function unoPaintOver")
    body = JS[i:JS.index("function unoPaint()", i)]
    assert "UNO.over" in body, "ตารางอันดับไม่ได้รอให้เกมจบก่อน"


def test_the_ranking_marks_which_row_is_you():
    i = JS.index("function unoPaintOver")
    body = JS[i:JS.index("function unoPaint()", i)]
    assert "f.you" in body and "'you'" in body, "หาแถวตัวเองในตารางไม่เจอ"


def test_the_ranking_shows_the_points_left_in_hand():
    i = JS.index("function unoPaintOver")
    body = JS[i:JS.index("function unoPaint()", i)]
    assert "f.left" in body, "ไม่ได้โชว์แต้มที่เหลือในมือ"


def test_playing_again_resets_the_fanfare():
    """ไม่รีเซ็ต = รอบใหม่ไม่มีอนิเมชันประกาศอันดับเลย"""
    i = JS.index("document.getElementById('unoAgain')")
    body = JS[i:i + 400]
    assert "UNO_SEEN_PLACE = 0" in body


def test_the_colour_picker_is_now_cards_on_the_table():
    """เจ้าของเกมสั่ง: ให้เป็นไพ่ลอยมาในจอ 4 ใบ แทนปุ่มด้านล่าง"""
    assert "UNO_SUIT_CARDS" in JS
    assert 'id="unoSuits"' not in HTML, "ยังมีแถวปุ่มเลือกสีอันเดิม"


def test_hovering_a_suit_card_lifts_it():
    i = JS.index("function unoDrawSuitCards")
    body = JS[i:JS.index("function unoBind", i)]
    assert "c.hover" in body, "ชี้ไพ่แล้วไม่มีอะไรเกิดขึ้น"


def test_picking_a_suit_plays_the_card():
    i = JS.index("if (UNO_SUIT_CARDS.length) {")
    body = JS[i:i + 500]
    assert "hit.suit" in body and "'play'" in body, "เลือกสีแล้วไม่ได้วางไพ่"


def test_the_suit_cards_block_everything_else_while_open():
    """ไม่ดักก่อน = กดทะลุไปโดนไพ่ในมือข้างหลัง"""
    i = JS.index("const down = e =>")
    body = JS[i:JS.index("const move = e =>", i)]
    assert body.index("UNO_SUIT_CARDS.length") < body.index("unoHit("), \
        "ไม่ได้ดักการกดตอนกำลังเลือกสี"


def test_bots_take_a_moment_to_think():
    """เจ้าของเกมสั่ง: เพิ่มระยะเวลาพร้อมเอฟเฟกต์คล้ายบอทกำลังคิด"""
    assert "UNO_THINK_MS" in JS and "unoPlayBotMoves" in JS
    i = JS.index("async function unoPlayBotMoves")
    body = JS[i:JS.index("function unoFlyToPile", i)]
    assert "await unoWait(UNO_THINK_MS)" in body, "บอทเล่นรวดเดียวไม่มีจังหวะคิด"
    # ต้องตั้งว่า "ใครกำลังคิด" ก่อนหน่วง ไม่งั้นหน่วงเฉย ๆ ไม่มีอะไรให้ดู
    assert body.index("UNO_THINK = {") < body.index("await unoWait(UNO_THINK_MS)"),         "หน่วงก่อนแล้วค่อยบอกว่าใครคิด — จอจะนิ่งเฉย ๆ ไม่รู้ว่ารออะไร"


def test_the_thinking_bot_is_shown_on_its_seat():
    i = JS.index("unoSeats(cv).forEach")
    body = JS[i:JS.index("UNO_CARDS.forEach", i)]
    assert "thinking" in body, "ไม่รู้ว่าบอทตัวไหนกำลังคิด"


def test_a_played_card_flies_into_the_pile():
    assert "unoFlyToPile" in JS
    i = JS.index("function unoFlyToPile")
    body = JS[i:JS.index("async function unoDo", i)]
    assert "unoSeats" in body, "ไพ่ไม่ได้บินออกมาจากที่นั่งคนที่ลง"
    assert "unoPilePos" in body, "ไพ่ไม่ได้บินไปที่กองทิ้ง"


def test_flying_cards_survive_a_state_refresh():
    """ไม่งั้นสถานะใหม่มาถึงแล้วไพ่ที่กำลังบินหายกลางอากาศ"""
    i = JS.index("function unoLayout")
    body = JS[i:JS.index("function unoHit", i)]
    assert "c.flying" in body, "ไพ่ที่กำลังบินโดนล้างทิ้ง"


def test_the_server_reports_each_bot_move_separately():
    """ต้องรู้ว่าบอทแต่ละตัวทำอะไร ไม่ใช่ก้อนเดียวจบ"""
    import inspect

    from bot.cards import uno_table
    src = inspect.getsource(uno_table._run_bots)
    assert '"seat"' in src and '"card"' in src, "ไม่ได้บอกว่าใครลงไพ่อะไร"


def test_numbered_bots_are_still_recognised_as_bots():
    """โต๊ะหลายบอทชื่อมีเลขต่อท้าย — เทียบชื่อเต็มจะไม่ตรงสักตัว"""
    from bot.cards import uno_bot
    assert uno_bot.is_bot("🤖 บอท")
    assert uno_bot.is_bot("🤖 บอท 3"), "บอทที่มีเลขต่อท้ายไม่ถูกนับเป็นบอท"
    assert not uno_bot.is_bot("คุณ")


# ── 🐞 ตารางอันดับค้างไม่หาย (เจ้าของเกมเจอ 08-29) ──

def test_the_page_boots_and_draws_without_crashing():
    """โหลด uno.js จริงแล้ววาดเฟรม — จับ error ที่เทสอ่านข้อความมองไม่เห็น

    รวมถึงลำดับจบเกม -> เปิดโต๊ะใหม่ -> ตารางอันดับต้องหาย
    """
    import shutil
    import subprocess

    if not shutil.which("node"):
        pytest.skip("เครื่องนี้ไม่มี node")
    r = subprocess.run(["node", "tests/uno_boot.js"],
                       capture_output=True, text=True, encoding="utf-8")
    assert r.returncode == 0, r.stdout + r.stderr


def test_the_buttons_hide_the_panel_immediately():
    """ไม่รอคำตอบเซิร์ฟเวอร์ — เน็ตช้าหรือคำขอพลาด แผงก็ต้องหาย

    ไม่งั้นผู้เล่นติดค้างกดอะไรก็ไม่ได้ (อาการที่เจ้าของเกมเจอ)
    """
    for btn in ("unoAgain", "unoLeave"):
        i = JS.index(f"getElementById('{btn}')")
        body = JS[i:i + 500]
        assert "box.hidden = true" in body, f"ปุ่ม {btn} ไม่ได้ซ่อนแผงทันที"
        assert body.index("box.hidden = true") < body.index("await unoDo"), \
            f"ปุ่ม {btn} รอเซิร์ฟเวอร์ก่อนค่อยซ่อน"


def test_opening_a_table_also_clears_the_panel():
    i = JS.index("getElementById('unoStart')")
    body = JS[i:i + 500]
    assert "overBox.hidden = true" in body, "กดเปิดโต๊ะแล้วแผงไม่หาย"


def test_one_broken_frame_does_not_freeze_the_game():
    """บทเรียนจากสนามรบผลัดเทิร์น: error เฟรมเดียวหยุด rAF ทั้งจอค้าง"""
    assert "unoSafeFrame" in JS
    i = JS.index("function unoSafeFrame")
    body = JS[i:i + 400]
    assert "catch" in body and "requestAnimationFrame" in body, \
        "เฟรมพังแล้วไม่ได้เล่นต่อเฟรมหน้า"
    assert "console.error" in body, "พังแล้วเงียบ หาสาเหตุไม่ได้"


def test_a_broken_ranking_row_hides_the_panel_instead_of_sticking():
    """ข้อมูลอันดับขาดฟิลด์ต้องไม่ทำให้แผงค้างคาจอ

    เกมที่ค้างใน DB จากก่อนเพิ่มฟิลด์ bot/left จะไม่มีค่าเหล่านี้
    ถ้า throw กลางคัน แผงจะโชว์ค้างโดยตารางว่างเปล่า กดอะไรก็ไม่หาย
    """
    i = JS.index("function unoPaintOver")
    body = JS[i:JS.index("function unoPaint()", i)]
    assert "try {" in body and "catch" in body, "สร้างตารางพังแล้วแผงค้าง"
    assert "box.hidden = true" in body[body.index("catch"):], \
        "พังแล้วไม่ได้ซ่อนแผงทิ้ง"


def test_there_is_a_way_to_diagnose_a_stuck_panel():
    """ยังหาต้นเหตุไม่เจอ — ต้องมีทางถามจากเบราว์เซอร์จริง"""
    assert "function unoWhy" in JS
    i = JS.index("function unoWhy")
    body = JS[i:i + 600]
    for key in ("hidden", "over", "finished", "UNO_LOOP"):
        assert key in body, f"unoWhy() ไม่ได้บอก {key}"


def test_everything_hidden_in_the_html_can_actually_hide():
    """สั่ง hidden แล้วต้องหายจากจอจริง

    🐞 เจ้าของเกมเจอ 08-29: JS ซ่อนสำเร็จ (DOM มี hidden="" จริง ๆ)
       แต่แผงยังโชว์อยู่ กดปุ่มไหนก็ไม่หาย
       ต้นเหตุ: CSS ตั้ง display:grid ซึ่งทับกฎ [hidden]{display:none} ของเบราว์เซอร์
       แผงอื่นในไฟล์มีกฎคู่กันหมด (wm-over, #wmAim) — ของศึกไพ่รูนตกหล่นไป

    เทสนี้กวาดทั้งไฟล์ ไม่ใช่เช็คเฉพาะแผงเดียว เพราะตอนเขียนเจออีก 3 จุด
    ที่พลาดแบบเดียวกัน (.g-tile ทำให้ปุ่มผ่าน/UNO ซ่อนไม่ได้ด้วย)
    """
    import shutil
    import subprocess

    if not shutil.which("node"):
        pytest.skip("เครื่องนี้ไม่มี node")
    r = subprocess.run(["node", "tests/uno_hidden.js"],
                       capture_output=True, text=True, encoding="utf-8")
    assert r.returncode == 0, r.stdout + r.stderr


# ── 🎯 ตาใครลงได้ · แสดงความยินดี · ดีเลย์จั่ว (เจ้าของเกมสั่ง 08-29) ──

def test_you_cannot_play_on_someone_elses_turn():
    """เจ้าของเกมเจอ: ถึงเทิร์นคนอื่นแล้วยังลงไพ่ได้

    ต้นเหตุ: ระหว่างเล่นภาพตาบอท UNO ยังเป็นสถานะเก่าที่ my_turn เป็น true
    unoMyTurn() จึงต้องเช็ค UNO_THINK ด้วย
    """
    assert "function unoMyTurn" in JS
    i = JS.index("function unoMyTurn")
    body = JS[i:JS.index("function unoMustDraw", i)]
    assert "UNO_THINK" in body, "บอทเล่นอยู่แต่ยังนับเป็นตาเรา"
    assert "UNO.over" in body and "my_place" in body


def test_dropping_a_card_out_of_turn_bounces_back():
    i = JS.index("const up = async ()")
    body = JS[i:JS.index("cv.addEventListener('mousedown'", i)]
    assert "!unoMyTurn()" in body, "ยังไม่ถึงตาแล้วยังปล่อยลงกองได้"


def test_the_whole_hand_greys_out_until_your_turn():
    """เจ้าของเกมสั่ง: ยังไม่ถึงเทิร์นตัวเองให้เป็นสีเทา"""
    i = JS.index("function unoLayout")
    body = JS[i:JS.index("function unoHit", i)]
    assert "const dim = !mine || !can" in body, "ตาคนอื่นแล้วไพ่ไม่หรี่"


def test_you_can_still_rearrange_cards_when_it_is_not_your_turn():
    """เจ้าของเกมสั่ง: แต่สามารถจัดตำแหน่งไพ่บนมือได้"""
    i = JS.index("const down = e =>")
    body = JS[i:JS.index("const move = e =>", i)]
    assert "if (!unoMyTurn()) return;" not in body, "ยังไม่ถึงตาแล้วจับไพ่ไม่ได้เลย"


def test_the_deck_can_only_be_clicked_on_your_turn():
    i = JS.index("const down = e =>")
    body = JS[i:JS.index("const move = e =>", i)]
    assert "unoOnDeck(p, cv) && unoMyTurn()" in body, "ตาคนอื่นแล้วยังกดจั่วได้"


def test_the_ranking_waits_for_the_congratulations():
    """เจ้าของเกมเจอ: ลงไพ่ใบท้ายแล้วไม่มีอะไรขึ้น

    ต้นเหตุ: เล่น 2 คน ลงใบสุดท้าย = จบทันที ตารางขึ้นทับอนิเมชันพอดี
    """
    i = JS.index("function unoPaintOver")
    body = JS[i:JS.index("function unoPaint()", i)]
    assert "!UNO_FANFARE" in body, "ตารางขึ้นทับอนิเมชันแสดงความยินดี"


def test_the_ranking_appears_after_the_animation_ends():
    """ไม่เรียกตอนจบ = รอไปตลอด ตารางไม่ขึ้นเลย"""
    i = JS.index("function unoDrawFanfare")
    body = JS[i:i + 900]
    assert "unoPaintOver()" in body, "อนิเมชันจบแล้วตารางไม่โผล่"


def test_the_winner_is_congratulated_by_name():
    """เจ้าของเกมสั่ง: ขึ้นว่าคุณได้อันดับ 1 2 3"""
    i = JS.index("function unoDrawFanfare")
    body = JS[i:i + 2000]
    assert "f.you" in body and "ยินดี" in body, "ชนะแล้วไม่ได้แสดงความยินดีกับเรา"


def test_drawing_shows_the_card_before_the_bots_move():
    """เจ้าของเกมสั่ง: มีดีเลย์ตอนจั่วก็ให้เป็นเทิร์นคนนั้นจนกว่าอนิเมชันจะจบ"""
    assert "UNO_DRAW_MS" in JS
    i = JS.index("async function unoDo")
    body = JS[i:JS.index("// 🏁 อนิเมชันตอนมีคนเข้าเส้นชัย", i)]
    assert "'draw'" in body and "UNO_DRAW_MS" in body
    assert body.index("unoApply(d.table)") < body.index("unoPlayBotMoves(bots)"), \
        "บอทเล่นก่อนไพ่ที่จั่วจะขึ้นมือ"


def test_the_turn_rules_actually_work():
    """รันตรรกะจริง — เช็คข้อความอย่างเดียวจับตรรกะผิดไม่ได้"""
    import shutil
    import subprocess

    if not shutil.which("node"):
        pytest.skip("เครื่องนี้ไม่มี node")
    r = subprocess.run(["node", "tests/uno_anim.js"],
                       capture_output=True, text=True, encoding="utf-8")
    assert r.returncode == 0, r.stdout + r.stderr


# ── 🛑 ลงไพ่แล้วจบตาทันที + 🃏 อนิเมชันแจกไพ่ (เจ้าของเกมสั่ง 08-29) ──

def test_playing_a_card_closes_your_turn_at_once():
    """เจ้าของเกมเจอ: ลงไพ่แล้วยังลงต่อได้อีก

    unoMyTurn() เช็ค UNO_THINK อย่างเดียวไม่พอ — ระหว่างรอคำตอบ (~หลักร้อย ms)
    UNO.my_turn ยังเป็น true อยู่ ต้องปิดตาทันทีที่ "ส่งคำสั่งไป"
    """
    i = JS.index("function unoMyTurn")
    body = JS[i:JS.index("function unoMustDraw", i)]
    assert "UNO_SENT" in body, "ส่งคำสั่งไปแล้วยังนับเป็นตาเรา ลงไพ่ซ้ำได้"


def test_the_turn_closes_before_waiting_for_the_server():
    i = JS.index("async function unoDo")
    body = JS[i:i + 800]
    assert body.index("UNO_SENT = true") < body.index("await api"), \
        "รอคำตอบก่อนค่อยปิดตา — ช่วงนั้นลงไพ่ซ้ำได้"


def test_a_failed_request_gives_the_turn_back():
    """เน็ตพลาดแล้วไม่คืนตา = ค้างกดอะไรไม่ได้เลย"""
    i = JS.index("async function unoDo")
    body = JS[i:JS.index("// 🏁 อนิเมชันตอนมีคนเข้าเส้นชัย", i)]
    assert "catch" in body and "UNO_SENT = false" in body[body.index("catch"):]


def test_a_wild_locks_the_turn_while_choosing_a_colour():
    """รอเลือกสีอยู่ = ลงไพ่ใบอื่นซ้อนไม่ได้"""
    # ล็อกด้วย "กำลังเลือกสีอยู่" แทน UNO_SENT
    # เพราะ UNO_SENT จะทำให้ด่านใน unoDo บล็อกการวางไวลด์เอง
    i = JS.index("function unoMyTurn")
    body = JS[i:JS.index("function unoMustDraw", i)]
    assert "UNO_SUIT_CARDS.length" in body, "กำลังเลือกสีอยู่แต่ยังลงไพ่อื่นซ้อนได้"


def test_the_turn_reopens_when_new_state_arrives():
    i = JS.index("function unoApply")
    body = JS[i:i + 400]
    assert "UNO_SENT = false" in body, "สถานะใหม่มาแล้วยังกดอะไรไม่ได้"


def test_opening_a_table_deals_cards_from_the_deck():
    """เจ้าของเกมสั่ง: เปิดโต๊ะแล้วมีอนิเมชันแจกไพ่จากเด็คบนโต๊ะ"""
    assert "unoDealAnim" in JS
    i = JS.index("async function unoDealAnim")
    body = JS[i:JS.index("async function unoDo", i)]
    assert "unoPilePos" in body, "ไพ่ไม่ได้ออกมาจากกองบนโต๊ะ"
    assert "unoSeats" in body, "แจกให้แต่ที่นั่งไม่ครบ"
    assert "UNO_DEAL_MS" in body, "แจกรวดเดียว ไม่เห็นว่าแจกทีละใบ"


def test_dealing_happens_when_a_table_starts():
    i = JS.index("async function unoDo")
    body = JS[i:JS.index("// 🏁 อนิเมชันตอนมีคนเข้าเส้นชัย", i)]
    assert "action === 'start'" in body and "unoDealAnim()" in body


def test_you_cannot_touch_anything_while_dealing():
    i = JS.index("function unoMyTurn")
    body = JS[i:JS.index("function unoMustDraw", i)]
    assert "UNO_DEALING" in body, "กำลังแจกไพ่อยู่แต่กดลงไพ่ได้"


def test_the_dealt_cards_are_cleared_afterwards():
    """ไม่เก็บกวาด = ไพ่หลอกค้างบนจอทับไพ่จริง"""
    i = JS.index("async function unoDealAnim")
    body = JS[i:JS.index("async function unoDo", i)]
    assert "UNO_CARDS.filter" in body, "ไพ่ที่ใช้แจกไม่ถูกเก็บทิ้ง"


# ── 🎬 ยังไม่ถึงตาเราจนกว่าภาพจะเล่นจบ (เจ้าของเกมสั่ง 08-29) ──

def test_the_turn_waits_for_the_animation_to_finish():
    """เจ้าของเกมสั่ง: อนิเมชันของแต่ละคนยังไม่จบ ยังไม่ถึงเทิร์นเรา

    ⚠️ เดิมใช้ setTimeout เดาว่าภาพน่าจะจบแล้ว — วัดจริงแล้วไม่ตรง:
       ไพ่บินเข้ากอง 22 เฟรม = ~367 ms แต่โค้ดรอแค่ 220 ms
       เหลือช่องว่าง ~147 ms ที่ไพ่ยังลอยอยู่แต่เป็นตาเราแล้ว
    """
    i = JS.index("function unoMyTurn")
    body = JS[i:JS.index("function unoBusyFx", i)]
    assert "unoBusyFx()" in body, "ไม่ได้ดูว่าไพ่ยังบินอยู่ไหม"


def test_the_busy_check_looks_at_real_animations():
    i = JS.index("function unoBusyFx")
    body = JS[i:JS.index("function unoMustDraw", i)]
    assert "UNO_CARDS.some" in body and "c.anim" in body, "ไม่ได้นับจากอนิเมชันจริง"
    assert "c.flying" in body, "นับไพ่ในมือที่ขยับด้วย จะค้างตลอด"


def test_waiting_follows_the_animation_not_a_timer():
    """รอด้วยตัวเลขคงที่ = เดาผิดเมื่อไหร่ก็หลุดเมื่อนั้น"""
    assert "async function unoWaitFx" in JS
    i = JS.index("async function unoWaitFx")
    body = JS[i:i + 400]
    assert "unoBusyFx()" in body, "ไม่ได้รอภาพจริง"
    # เพดานต้องอยู่ในเงื่อนไขของ while จริง — มีแค่ตัวแปรไม่พอ
    loop = body[body.index("while"):body.index(chr(10), body.index("while"))]
    assert "Date.now()" in loop,         "วนรอไม่มีเพดาน — อนิเมชันค้างเมื่อไหร่เกมค้างถาวร"


def test_the_bot_move_waits_for_its_card_to_land():
    i = JS.index("async function unoPlayBotMoves")
    body = JS[i:JS.index("/** 🃏 ไพ่บินจาก", i)]
    assert "unoWaitFx()" in body, "บอทลงไพ่แล้วไม่รอให้บินถึงกอง"


def test_dealing_waits_for_the_last_card():
    i = JS.index("async function unoDealAnim")
    body = JS[i:JS.index("async function unoDo", i)]
    assert "unoWaitFx()" in body, "แจกไพ่ยังไม่ถึงมือก็เริ่มเกมแล้ว"


def test_the_animation_gate_actually_works():
    """รันตรรกะจริง — เช็คข้อความจับ 'ช่องว่างระหว่างภาพยังเล่น' ไม่ได้"""
    import shutil
    import subprocess

    if not shutil.which("node"):
        pytest.skip("เครื่องนี้ไม่มี node")
    r = subprocess.run(["node", "tests/uno_anim.js"],
                       capture_output=True, text=True, encoding="utf-8")
    assert r.returncode == 0, r.stdout + r.stderr


def test_the_hand_locks_the_moment_a_card_is_played():
    """เจ้าของเกมสั่ง: ลงไพ่แล้วล็อกไพ่ทันที ไม่ให้ขยับไพ่เพื่อลงต่อ

    ⚠️ ตัวกันเดิม (c.dim) บอกแค่ "ใบนี้ลงไม่ได้" — ยังจับลากจัดตำแหน่งได้อยู่
       ต้องดักตั้งแต่ก่อนจับไพ่ ไม่งั้นระหว่างรอคำตอบยังหยิบไพ่ใบใหม่มาจ่อได้
    """
    i = JS.index("const down = e =>")
    body = JS[i:JS.index("const move = e =>", i)]
    assert "UNO_SENT || UNO_DEALING || UNO_THINK" in body, "ส่งคำสั่งแล้วยังจับไพ่ได้"
    assert body.index("UNO_SENT") < body.index("unoHit(p)"), \
        "ดักหลังจับไพ่แล้ว — สายไป"


def test_locked_cards_do_not_glow():
    """เจ้าของเกมสั่ง: ตอนล็อกไพ่ไม่ให้ขยับ ก็ไม่ต้องเรืองแสงด้วย

    ทั้งขอบเรืองและการล็อกมาจาก unoMyTurn() ตัวเดียวกัน
    ล็อกเมื่อไหร่แสงก็ดับตามเอง — เทสนี้กันไม่ให้ใครแยกสองอย่างนี้ออกจากกัน
    (uno_glow.js รันตรรกะจริงตรวจครบทั้งสามกรณี: สั่งไปแล้ว/แจกไพ่/ไพ่ยังบิน)
    """
    i = JS.index("function unoLayout")
    body = JS[i:JS.index("function unoHit", i)]
    assert "const glow = mine && can" in body, "แสงไม่ได้ผูกกับตัวเดียวกับการล็อก"
    assert "const mine = unoMyTurn()" in body


# ── 🔄 วาดใหม่ทันทีที่ลงไพ่ + ฉลองก่อนบอทเล่น (เจ้าของเกมเจอ 08-29) ──

def test_playing_a_card_repaints_at_once():
    """เจ้าของเกมเจอ: ลงไพ่แล้วไพ่ยังเรืองแสง ยังไม่จัดไพ่ใหม่ และยังขึ้น "ตาคุณ"

    ต้นเหตุ: ตั้งธง UNO_SENT แล้วแต่ไม่ได้วาดใหม่ หน้าจอจึงค้างสภาพเดิมทั้งหมด
    """
    i = JS.index("async function unoDo")
    body = JS[i:i + 700]
    assert "unoPaint();" in body, "ส่งคำสั่งแล้วไม่วาดใหม่ — แสงกับข้อความค้าง"
    assert "unoLayout();" in body, "ไม่จัดไพ่ใหม่"
    assert body.index("UNO_SENT = true") < body.index("unoPaint();"), \
        "วาดก่อนตั้งธง — วาดออกมาเป็นสภาพเดิม"


def test_the_status_line_follows_the_real_turn():
    """ขึ้น 'ตาคุณ' ทั้งที่ลงไพ่ไปแล้ว = สับสนว่ายังลงได้อีก"""
    i = JS.index("function unoPaint()")
    body = JS[i:JS.index("function unoAskSuit", i)]
    assert "unoMyTurn() ?" in body, "ข้อความยังอ่านจาก UNO.my_turn ดิบ ๆ"


def test_the_hand_stays_hidden_while_dealing():
    """เจ้าของเกมสั่ง: ตอนอนิเมชันแจกไพ่ยังไม่ต้องโชว์ไพ่ในมือ"""
    i = JS.index("function unoLayout")
    body = JS[i:JS.index("function unoHit", i)]
    assert "if (UNO_DEALING) return;" in body, "แจกไพ่ยังไม่จบแต่ไพ่จริงโผล่มาแล้ว"


def test_winning_celebrates_before_the_bots_finish():
    """เจ้าของเกมเจอ: ลงไพ่ใบสุดท้ายแล้วไม่ขึ้นว่าได้ที่เท่าไหร่

    เดิมเล่นภาพบอทก่อน กว่าจะถึง unoApply (ที่จุดอนิเมชัน) ก็ผ่านไปหลายวินาที
    """
    i = JS.index("async function unoDo")
    body = JS[i:JS.index("// 🏁 อนิเมชันตอนมีคนเข้าเส้นชัย", i)]
    assert "my_place" in body, "ไม่ได้ดูว่าเราเพิ่งเข้าเส้นชัยไหม"
    assert "if (iWon) {" in body, "เงื่อนไขไม่ได้อ่านค่าจริง — ปิดตายไว้ก็ไม่มีใครรู้"
    assert "unoWaitFanfare()" in body, "ไม่ได้รอให้ดูอนิเมชันจบ"
    j = body.index("const iWon")
    tail = body[j:]
    assert tail.index("unoApply") < tail.index("unoPlayBotMoves"), \
        "ยังเล่นภาพบอทก่อนแล้วค่อยฉลอง"


def test_the_celebration_wait_has_a_ceiling():
    i = JS.index("async function unoWaitFanfare")
    body = JS[i:i + 300]
    loop = body[body.index("while"):body.index(chr(10), body.index("while"))]
    assert "Date.now()" in loop, "วนรอไม่มีเพดาน — อนิเมชันค้างแล้วเกมค้างตาม"


# ── 🃏 ไพ่ที่ทิ้งแล้ว/กำลังแจก ต้องไม่โผล่บนมือ (เจ้าของเกมเจอ 08-29) ──

def test_a_played_card_leaves_the_hand_at_once():
    """เจ้าของเกมเจอ: ทิ้งไพ่ 3 ไปแล้ว ไพ่ 3 ยังอยู่บนมือจนบอทเล่นจบ

    ต้นเหตุ: UNO.hand ยังเป็นมือเก่าจากเซิร์ฟเวอร์จนกว่าสถานะใหม่จะมา
    แก้: นับใบที่กำลังบินไปกอง แล้วตัดออกจากมือตอนวาด
    """
    i = JS.index("function unoLayout")
    body = JS[i:JS.index("function unoHit", i)]
    assert "c.toPile" in body, "ไม่ได้แยกว่าใบไหนกำลังบินไปกอง"
    assert "gone[key]--" in body, "ไม่ได้ตัดใบที่ทิ้งแล้วออกจากมือ"


def test_the_played_card_is_marked_when_dropped():
    i = JS.index("const up = async ()")
    body = JS[i:JS.index("cv.addEventListener('mousedown'", i)]
    # ต้องทำเครื่องหมายตั้งแต่ตอนดูดเข้ากอง — ไม่ใช่เฉพาะทางไวลด์
    snap = body[body.index("const t = unoPilePos"):body.index("unoBurst")]
    assert "c.toPile = true" in snap, "ปล่อยไพ่ลงกองแล้วไม่ได้ทำเครื่องหมาย"


def test_a_wild_also_leaves_the_hand_while_choosing():
    """วางไวลด์รอเลือกสีอยู่ ไพ่ก็ต้องหายจากมือแล้ว"""
    i = JS.index("const up = async ()")
    body = JS[i:JS.index("cv.addEventListener('mousedown'", i)]
    j = body.index("unoAskSuit")
    assert "c.toPile = true" in body[:j], "ไวลด์ยังค้างบนมือระหว่างเลือกสี"


def test_cards_that_reached_the_pile_are_cleaned_up():
    """ไพ่ที่บินถึงกองต้องกลายเป็นใบบนสุด แล้วหายตอนสถานะใหม่มา

    ไม่เก็บกวาด = ไพ่ค้างทับกองจริงไปเรื่อย ๆ
    """
    assert "c.onPile = true" in JS, "ไพ่ที่บินถึงกองไม่ได้กลายเป็นใบบนสุด"
    assert "filter(c => !c.onPile)" in JS, "ไพ่ค้างทับกองไม่ถูกล้าง"


def test_dealing_starts_before_the_hand_is_applied():
    """เจ้าของเกมเจอ: เห็นไพ่ 7 ใบอยู่แล้ว แล้วอนิเมชันแจกมาทับข้างบน

    ต้นเหตุ: unoApply วาดมือเต็มก่อน แล้ว unoDealAnim ค่อยตั้งธง — สายไป
    """
    # ตัดเฉพาะบล็อก start — มี unoApply ของทางจั่วไพ่อยู่ข้างบนด้วย
    i = JS.index("if (action === 'start') {")
    body = JS[i:JS.index("return d;", i)]
    # ตัดคอมเมนต์ทิ้งก่อน ไม่งั้นคำว่า unoApply ในคอมเมนต์จะนับด้วย
    code = "".join(l for l in body.splitlines(True)
                   if not l.strip().startswith("//"))
    assert "UNO_DEALING = true" in code, "ไม่ได้ตั้งธงก่อนเริ่ม"
    assert code.index("UNO_DEALING = true") < code.index("unoApply"), \
        "วาดมือเต็มก่อนตั้งธง — ไพ่จริงโผล่มาก่อน"


def test_your_own_played_card_does_not_block_your_next_turn():
    """เจ้าของเกมเจอ: เล่น 2 คน วางไพ่ข้ามตา แล้วจอค้าง "รอคู่แข่ง..."

    ต้นเหตุ: 2 คน + ไพ่ข้ามตา = บอทถูกข้าม กลับมาเป็นตาเราทันที (ไม่มี bot_moves)
    แต่ไพ่ที่เราเพิ่งทิ้งยังบินอยู่ unoBusyFx() จึงยังเป็น true
    -> unoMyTurn() เป็น false ค้าง ทั้งที่เซิร์ฟเวอร์บอกว่าเป็นตาเราแล้ว
    (กดกองจั่วได้เพราะ unoDo วาดใหม่ ทำให้หลุดจากสภาพค้าง — จึงดูเหมือนได้ไพ่ฟรี)
    """
    i = JS.index("function unoBusyFx")
    body = JS[i:JS.index("function unoMustDraw", i)]
    assert "!c.mine" in body, "ไพ่ที่เราทิ้งเองยังบล็อกตาเราอยู่"


def test_the_card_we_play_is_marked_as_ours():
    i = JS.index("const up = async ()")
    body = JS[i:JS.index("cv.addEventListener('mousedown'", i)]
    assert body.count("c.mine = true") >= 2, "ทั้งไพ่ปกติและไวลด์ต้องทำเครื่องหมาย"


def test_other_peoples_cards_still_block():
    """ของบอทกับไพ่ที่กำลังแจกต้องยังบล็อกอยู่ ไม่งั้นกดแทรกได้"""
    i = JS.index("function unoFlyToPile")
    body = JS[i:JS.index("async function unoDo", i)]
    assert "c.mine" not in body, "ไพ่บอทถูกทำเครื่องหมายเป็นของเรา"


# ── 🔮 ไวลด์ค้างบนมือ + ไพ่ที่วางต้องอยู่บนสุดกอง (เจ้าของเกมเจอ 08-29) ──

def test_a_finished_flight_still_counts_as_out_of_hand():
    """เจ้าของเกมเจอ: 🌑 ประตูนิรันดร์ เลือกสีเสร็จแล้วไพ่ยังอยู่บนมือ

    ต้นเหตุ: ไพ่บินจบใน 8 เฟรม (~133 ms) แต่ไวลด์ต้องรอเราเลือกสี
    พอ anim จบ c.anim = null -> หลุดจากรายการ flying -> ไม่ถูกตัดออกจากมือ
    ไพ่ปกติไม่เจอเพราะเซิร์ฟเวอร์ตอบกลับก่อนภาพจะจบ
    """
    i = JS.index("const flying = UNO_CARDS.filter")
    line = JS[i:JS.index(chr(10), i)]
    assert "c.toPile" in line, "ไพ่ที่บินจบแล้วหลุดจากรายการ ไพ่เลยกลับมาโชว์ในมือ"


def test_the_card_you_played_becomes_the_top_of_the_pile():
    """เจ้าของเกมสั่ง: วางไพ่แล้วต้องเห็นไพ่ที่วางใหม่บนสุด

    เดิมพอไพ่บินถึงกองก็ลบทิ้ง (c.dead) กองเลยกลับไปโชว์ไพ่เก่า
    จนกว่าสถานะใหม่จะมาถึง — ซึ่งคือหลังบอทเล่นจบ
    """
    assert "c.onPile" in JS, "ไม่ได้เก็บไพ่ที่วางไว้เป็นใบบนสุด"
    # ตอนไพ่บินถึงกองต้องตั้ง onPile — ไม่ใช่ลบทิ้ง (c.dead)
    assert "if (c.toPile) c.onPile = true;" in JS,         "ไพ่ที่บินถึงกองโดนลบทิ้ง — กองกลับไปโชว์ไพ่เก่า"
    i = JS.index("const onPile = toPile.find")
    body = JS[i:i + 500]
    assert "UNO.top && !onPile" in body, "ยังวาดไพ่เก่าทับไพ่ที่เราเพิ่งวาง"


def test_the_pile_card_is_cleared_when_new_state_arrives():
    """ไม่ล้าง = ไพ่เราค้างทับกองจริงตลอดไป"""
    i = JS.index("function unoApply")
    body = JS[i:i + 600]
    assert "filter(c => !c.onPile)" in body, "ไพ่ที่วางค้างทับกองไม่ถูกล้าง"


def test_the_pile_and_hand_logic_actually_works():
    """รันตรรกะจริง — เช็คข้อความจับ 'ไพ่บินจบแล้วหลุด' ไม่ได้"""
    import shutil
    import subprocess

    if not shutil.which("node"):
        pytest.skip("เครื่องนี้ไม่มี node")
    r = subprocess.run(["node", "tests/uno_anim.js"],
                       capture_output=True, text=True, encoding="utf-8")
    assert r.returncode == 0, r.stdout + r.stderr


def test_two_identical_cards_only_lose_one_when_you_play_one():
    """เจ้าของเกมเจอ: มี 🌑 ประตูนิรันดร์ 2 ใบ วางไป 1 แต่หายจากมือ 2 ใบ

    ต้นเหตุ: UNO_CARDS = flying (ตัวเดียวกัน) แล้ว push(onPile) ทับเข้าไปอีก
    ไพ่ใบเดียวจึงอยู่ใน array สองที่ ตัวนับ gone เลยนับซ้ำ ตัดออก 2 ใบ
    """
    i = JS.index("const flying = UNO_CARDS.filter")
    body = JS[i:JS.index("if (UNO_DEALING) return;", i)]
    # ไพ่ที่เราวางถูกแยกออกมากองเดียว (toPile) แล้วต่อท้ายครั้งเดียว
    # ไม่มีทางที่ไพ่ใบเดียวจะอยู่ใน array สองที่อีกต่อไป
    assert "UNO_CARDS = flying.filter(c => !c.toPile)" in body,         "ไม่ได้แยกไพ่ที่วางออก — เสี่ยงนับซ้ำ"
    assert body.count("push(...toPile)") == 1, "เติมไพ่ที่วางกลับเข้ามากกว่าหนึ่งครั้ง"


# ── 🔒 ด่านกันเล่นนอกตา ต้องคุมทุกทาง (เจ้าของเกมสั่ง 08-29) ──

def test_every_command_goes_through_one_gate():
    """เจ้าของเกมเจอ: "เงื่อนไขกันวางไพ่ในเทิร์นคนอื่นยังมีหลุดอยู่บ้าง"

    เดิมดักทีละจุด (ลากไพ่ / กดกองจั่ว) แต่ปุ่มผ่านกับ UNO! ไม่ได้ดักเลย
    ย้ายด่านมาไว้ใน unoDo ที่เดียว — ทุกคำสั่งลอดผ่านตรงนั้นหมด
    """
    i = JS.index("async function unoDo")
    head = JS[i:JS.index("try {", i)]
    assert "!unoMyTurn()" in head, "ไม่มีด่านกลางใน unoDo"
    assert head.index("unoMyTurn()") < head.index("UNO_SENT = true"), \
        "ด่านอยู่หลังตั้งธง — สายไป"


def test_only_harmless_commands_bypass_the_gate():
    """เปิดโต๊ะ/ออกจากเกม ต้องทำได้เสมอ · คำสั่งที่เปลี่ยนเกมต้องผ่านด่าน"""
    i = JS.index("const UNO_ANYTIME")
    line = JS[i:JS.index(chr(10), i)]
    for ok in ("start", "quit"):
        assert f"'{ok}'" in line, f"{ok} ควรทำได้ตลอด"
    for guarded in ("play", "draw", "take", "pass", "uno"):
        assert f"'{guarded}'" not in line, f"{guarded} หลุดด่าน"


def test_nothing_calls_the_api_behind_the_gate():
    """มีทางลัดยิง api ตรง ๆ = ด่านไร้ความหมาย"""
    assert JS.count("api('POST', '/api/web/uno'") == 1, "มีทางลัดข้ามด่าน"


def test_choosing_a_wild_colour_still_gets_through():
    """ด่านต้องไม่บล็อกการวางไวลด์เอง

    ระหว่างรอเลือกสี UNO_SUIT_CARDS มีของ = ล็อก (ลงไพ่อื่นไม่ได้)
    แต่ตอนกดเลือกต้องล้างก่อนเรียก unoDo ไม่งั้นด่านบล็อกตัวเอง
    """
    i = JS.index("if (UNO_SUIT_CARDS.length) {")
    body = JS[i:i + 600]
    assert body.index("UNO_SUIT_CARDS = []") < body.index("unoDo('play'"), \
        "ไม่ได้ล้างก่อนเรียก — วางไวลด์ไม่ได้เลย"


def test_the_gate_covers_every_blocking_case():
    """รันตรรกะจริง 10 กรณี — เช็คข้อความไล่ครบทุกทางไม่ได้"""
    import shutil
    import subprocess

    if not shutil.which("node"):
        pytest.skip("เครื่องนี้ไม่มี node")
    r = subprocess.run(["node", "tests/uno_guard.js"],
                       capture_output=True, text=True, encoding="utf-8")
    assert r.returncode == 0, r.stdout + r.stderr


def test_you_cannot_even_pick_up_a_card_on_someone_elses_turn():
    """เจ้าของเกมเจอ: จั่วไพ่แล้วบอทเล่นต่อ แต่ยังลากไพ่ได้ (ถึงจะเด้งกลับก็ตาม)

    ต้นเหตุ: ตัวกันตอนจับไพ่ไล่เช็คธงเอง 3 ตัว (SENT/DEALING/THINK)
    ขาด unoBusyFx() กับตัวล็อกไวลด์ที่ unoMyTurn() มีให้อยู่แล้ว
    เพิ่มเงื่อนไขใหม่ทีไรก็ต้องมาไล่เติมตรงนี้ด้วย — พลาดง่าย
    """
    i = JS.index("const down = e =>")
    body = JS[i:JS.index("const move = e =>", i)]
    # ต้องคุมครบทุกเงื่อนไขที่ "มีอะไรกำลังเกิดขึ้น" ไม่ใช่แค่ 3 ธงเดิม
    # (ตาคนอื่นเฉย ๆ ยังจับจัดตำแหน่งไพ่ได้ ตามที่เจ้าของเกมสั่งไว้ก่อนหน้า)
    for cond in ("UNO_SENT", "UNO_DEALING", "UNO_THINK",
                 "unoBusyFx()", "UNO_SUIT_CARDS"):
        assert cond in body, f"ขาดเงื่อนไข {cond} — แตะไพ่ได้ตอนที่ไม่ควร"


def test_the_card_you_play_is_drawn_last_so_it_sits_on_top():
    """เจ้าของเกมเจอ: วางไพ่แล้วเหมือนไปวางใต้ไพ่ก่อนหน้า

    UNO_CARDS วาดตามลำดับใน array — ใบท้ายอยู่บนสุด
    ไพ่ที่เราวางเคยอยู่ต้น array (มาจาก flying) จึงถูกไพ่กองเดิมวาดทับ
    """
    i = JS.index("const flying = UNO_CARDS.filter")
    body = JS[i:JS.index("if (UNO_DEALING) return;", i)]
    assert "const toPile = flying.filter(c => c.toPile)" in body, \
        "ไม่ได้แยกไพ่ที่เราวางออกมา"
    assert "UNO_CARDS.push(...toPile)" in body, "ไม่ได้ดันไพ่ที่เราวางไปท้ายสุด"
    assert body.index("UNO.top && !onPile") < body.index("push(...toPile)"), \
        "วาดไพ่เราก่อนกองเดิม — กองเดิมจะทับ"
