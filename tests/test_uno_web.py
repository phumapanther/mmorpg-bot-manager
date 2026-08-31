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
    monkeypatch.setattr(web_api, "GAME_DB_PATH", tmp_path / "w.db")
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
    section = HTML[i:HTML.index("</div></div>", i)]
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
    assert ">?<" in section, "ปุ่มไม่ได้เขียนว่า ?"


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
    box = HTML[i:HTML.index("</div></div>", i)]
    for name in ("ม่านสะกด", "วาร์ปกลับทาง", "ทัณฑ์สองใบ",
                 "ศิลาเปลี่ยนธาตุ", "ประตูนิรันดร์"):
        assert name in box, f"คู่มือไม่ได้อธิบาย {name}"


def test_the_help_explains_how_to_play_a_card():
    i = HTML.index('id="unoHelp"')
    box = HTML[i:HTML.index("</div></div>", i)]
    assert "สีตรง" in box and "ลาก" in box, "ไม่ได้บอกวิธีลงไพ่"
    assert "เรืองแสง" in box, "ไม่ได้บอกว่าขอบเรืองแสงแปลว่าลงได้"


def test_the_help_explains_stacking():
    """สแตคเป็นกติกาที่งงที่สุด ต้องอธิบาย"""
    i = HTML.index('id="unoHelp"')
    box = HTML[i:HTML.index("</div></div>", i)]
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
