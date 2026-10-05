"""🎪 หน้าล็อบบี้บนเว็บ — ปุ่มเข้าเกม หน้าเลือกโหมด และ API โต๊ะเดิมพัน UNO

เทสสำคัญที่สุด: HTTP จริงต้องไม่ส่งไพ่คนอื่นลงมา (เหมือน test_uno_web.py)
กับ API ต้องผูก uid จาก session เท่านั้น ห้ามรับจาก body
"""
import pathlib
import re
import sqlite3
import time

import pytest

from tests import conftest

WEB = pathlib.Path("license_server/web_static")
HTML = conftest.strip_i18n((WEB / "play.html").read_text(encoding="utf-8"))
CSS = (WEB / "play.css").read_text(encoding="utf-8")


# ── 1) ปุ่มล็อบบี้อยู่บนสุดหมวดออกผจญภัย ──

def test_the_lobby_button_is_first_in_the_adventure_section():
    """ต้องอยู่ก่อนปุ่ม "เริ่มออกเดินทาง" เสมอ"""
    sec = HTML[HTML.index("<h3>ออกผจญภัย</h3>"):HTML.index("<h3>", HTML.index("<h3>ออกผจญภัย</h3>") + 4)]
    lobby_i = sec.index('data-go="lobby"')
    scene_i = sec.index('data-go="scene"')
    assert lobby_i < scene_i, "ปุ่มล็อบบี้ต้องอยู่ก่อนปุ่มเริ่มออกเดินทาง"


# ── 2) ปุ่มสนามรบกับปุ่มไพ่รูนเดิมยังอยู่ที่เดิม ห้ามแตะ ──

def test_worms_and_uno_menu_buttons_are_untouched():
    """เจ้าของเกมสั่งให้อยู่ที่เดิม เข้าเล่นได้เหมือนเดิม — ปุ่มเมนูอยู่ในหน้าแรก (v-home)"""
    pvp = HTML[HTML.index("<h3>PVP</h3>"):HTML.index("<h3>", HTML.index("<h3>PVP</h3>") + 4)]
    assert 'data-go="worms"' in pvp, "ปุ่มสนามรบหายไปจากหมวด PVP"
    casino = HTML[HTML.index("<h3>คาสิโน</h3>"):HTML.index("<h3>", HTML.index("<h3>คาสิโน</h3>") + 4)]
    assert 'data-go="uno"' in casino, "ปุ่มไพ่รูนหายไปจากหมวดคาสิโน"


# ── 3) มีหน้า v-lobby และมีทางเข้าเกมทั้งสอง ──

def test_the_lobby_panel_exists_and_links_both_games():
    assert 'id="v-lobby"' in HTML, "ไม่มีแผงล็อบบี้"
    panel = HTML[HTML.index('id="v-lobby"'):HTML.index("<!-- ══", HTML.index('id="v-lobby"') + 10)]
    assert 'data-go="uno"' in panel, "ล็อบบี้ไม่มีทางไปศึกไพ่รูน"
    assert 'data-go="worms"' in panel, "ล็อบบี้ไม่มีทางไปสนามรบผลัดเทิร์น"


# ── 4) หน้าเลือกโหมดใน v-uno มีทั้งปุ่มบอทและปุ่มเพื่อน ──

def test_uno_panel_has_a_mode_gate_before_the_table():
    panel = HTML[HTML.index('id="v-uno"'):HTML.index("<!-- ══", HTML.index('id="v-uno"') + 10)]
    assert 'id="unoModeBot"' in panel, "ไม่มีปุ่มเล่นกับบอทในหน้าเลือกโหมด"
    assert 'id="unoModeFriend"' in panel, "ไม่มีปุ่มเล่นกับเพื่อนในหน้าเลือกโหมด"
    # ปุ่มเลือกโหมดต้องมาก่อนโต๊ะเกมจริง (unoBotMode) ไม่ใช่โผล่หลัง
    assert panel.index('id="unoModeGate"') < panel.index('id="unoBotMode"')


# ── 8) คลาสที่ซ่อนด้วย [hidden] ต้องอยู่ในบล็อก display:none !important ──

def test_new_hidden_classes_are_in_the_important_block():
    """กันกับดัก [hidden] ถูก display: อื่นทับ — เจอมาแล้วเสียเวลาหาหลายรอบ"""
    i = CSS.index(".uno-over[hidden]")
    block = CSS[i:CSS.index("{", i) + 1]
    for cls in (".wm-room[hidden]", ".wm-buttons[hidden]"):
        assert cls in block, f"{cls} ยังไม่อยู่ในบล็อกกัน [hidden] โดน display: ทับ"


# ── งานเพิ่ม: หน้าเลือกโหมดของสนามรบผลัดเทิร์น (จัดหน้าจออย่างเดียว ไม่แตะกติกาเกม) ──

# ── 11) v-worms มีหน้าเลือกโหมดก่อนเข้าเกม ──

def test_worms_panel_has_a_mode_gate():
    panel = HTML[HTML.index('id="v-worms"'):HTML.index("<!-- ══", HTML.index('id="v-worms"') + 10)]
    assert 'id="wmModeGate"' in panel, "ไม่มีหน้าเลือกโหมดในสนามรบ"
    assert 'id="wmModeBot"' in panel, "ไม่มีปุ่มซ้อมกับบอทในหน้าเลือกโหมด"
    assert 'id="wmModeFriend"' in panel, "ไม่มีปุ่มเล่นกับเพื่อนในหน้าเลือกโหมด"
    # ปุ่มเลือกโหมดต้องมาก่อนกลุ่มปุ่มเข้าเกมจริง ไม่ใช่โผล่หลัง
    assert panel.index('id="wmModeGate"') < panel.index('id="wmNew"')


# ── 12) ปุ่มเดิมทั้ง 4 ตัวยังอยู่ครบ — ห้ามเปลี่ยน id หรือพฤติกรรม ──

def test_worms_original_four_buttons_still_exist():
    for btn_id in ("wmNew", "wmSame", "wmRoomOpen", "wmRoomJoin"):
        assert f'id="{btn_id}"' in HTML, f"ปุ่ม {btn_id} หายไปหลังจัดหน้าจอใหม่"


# ── 13) กลุ่มปุ่มที่ซ่อนด้วย [hidden] อยู่ในบล็อกกัน display: ทับแล้ว (เช็คซ้ำจากอีกมุม) ──

def test_worms_button_groups_use_the_hidden_attribute_not_a_display_style():
    panel = HTML[HTML.index('id="v-worms"'):HTML.index("<!-- ══", HTML.index('id="v-worms"') + 10)]
    for box_id in ("wmBotButtons", "wmFriendButtons"):
        tag = panel[panel.index(f'id="{box_id}"') - 120:panel.index(f'id="{box_id}"') + 40]
        assert "hidden" in tag, f"{box_id} ต้องเริ่มต้นซ่อนด้วย attribute hidden"


# ══════════ API ══════════

@pytest.fixture
def web(tmp_path, monkeypatch):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    import bot.models.player_model as pm
    from license_server import web_api, web_db

    pmdb = tmp_path / "w.db"
    monkeypatch.setattr(pm, "DB_NAME", str(pmdb))
    pm.init_db()
    from license_server.api_web import deps as _api_web_deps

    monkeypatch.setattr(_api_web_deps, "GAME_DB_PATH", pmdb)

    monkeypatch.setattr(web_api, "GAME_DB_PATH", pmdb)  # เผื่อโค้ดเก่าอ่านผ่าน web_api

    lobbydb = tmp_path / "lobby.db"

    def _connect():
        conn = sqlite3.connect(str(lobbydb), timeout=5)
        conn.row_factory = sqlite3.Row
        conn.executescript(web_db._SCHEMA)
        return conn

    monkeypatch.setattr(web_db, "connect", _connect)

    app = FastAPI()
    app.include_router(web_api.router)

    def _client_for(uid):
        pm.get_player(uid)
        pm.increment_player_field(uid, "cash", 10000)
        c = TestClient(app)
        c.cookies.set("web_session", web_api.sign({"uid": str(uid), "exp": time.time() + 3600}))
        return c

    return _client_for


# ── 5) ต้องล็อกอินก่อน ──

def test_room_api_requires_login(web):
    """ไม่มีคุกกี้ = ยิงไม่ได้เลย (เหมือน test_a_stranger_cannot_touch_the_table)"""
    from fastapi.testclient import TestClient
    from fastapi import FastAPI
    from license_server import web_api

    app = FastAPI()
    app.include_router(web_api.router)
    c = TestClient(app)
    assert c.post("/api/web/uno/room", json={"action": "create", "bet": 100}).status_code in (401, 403)
    assert c.get("/api/web/uno/room").status_code in (401, 403)


# ── 6) API ไม่รับ uid จาก body ──

def test_room_api_ignores_uid_in_body(web):
    """ส่ง uid ของคนอื่นมาในเนื้อคำขอ — ต้องไม่มีผล ยึด uid จาก session เท่านั้น"""
    alice = web(1001)
    bob_uid = 1002

    r = alice.post("/api/web/uno/room", json={"action": "create", "bet": 100, "uid": bob_uid})
    d = r.json()
    assert d["in_room"] and d["host"], "ต้องเปิดห้องให้อลิซ (เจ้าของ session) ไม่ใช่บ็อบ"

    # ยิงคำสั่งอ้าง uid บ็อบซ้ำ — ยังต้องเห็นห้องของอลิซเหมือนเดิม เพราะ session คืออลิซ
    r2 = alice.get("/api/web/uno/room")
    assert r2.json()["host"], "ห้องต้องยังเป็นของอลิซ ไม่ใช่ของ uid ที่แนบมาใน body"


# ── 7) 🔒 HTTP ไม่หลุดไพ่คนอื่น ──

def test_http_never_leaks_other_hands_in_a_room(web):
    """เรียก endpoint จริงผ่าน TestClient — คำตอบต้องไม่มีไพ่ในมือคนอื่น"""
    alice = web(2001)
    bob = web(2002)

    d = alice.post("/api/web/uno/room", json={"action": "create", "bet": 0}).json()
    code = d["code"]
    bob.post("/api/web/uno/room", json={"action": "join", "code": code})
    alice.post("/api/web/uno/room", json={"action": "start"})

    view = alice.get("/api/web/uno/room").json()

    def walk(x, out):
        if isinstance(x, dict):
            if "suit" in x and "value" in x:
                out.append(x)
            for k, v in x.items():
                if k != "top":
                    walk(v, out)
        elif isinstance(x, list):
            for v in x:
                walk(v, out)

    found = []
    walk(view, found)
    # มือของอลิซเองส่งมาได้ (คนละก้อนกับ seats[i]["hand"] ของคนอื่น) — เช็คว่า seat อื่นไม่มี "hand"
    for seat in view.get("seats", []):
        if not seat.get("you"):
            assert "hand" not in seat, "ส่งไพ่ของผู้เล่นคนอื่นลง HTTP จริง"
    assert len(found) > 0, "เทสนี้ต้องมีไพ่ให้เทียบ ไม่งั้นเทสเปล่า"


def test_creating_a_room_over_http_works(web):
    alice = web(3001)
    d = alice.post("/api/web/uno/room", json={"action": "create", "bet": 500}).json()
    assert d["in_room"] and d["host"] and d["bet"] == 500


def test_an_unknown_room_action_is_refused(web):
    alice = web(3002)
    assert alice.post("/api/web/uno/room", json={"action": "ระเบิด"}).status_code == 400


def test_joining_a_missing_code_is_refused(web):
    alice = web(3003)
    r = alice.post("/api/web/uno/room", json={"action": "join", "code": "ZZZZZ"})
    assert r.status_code == 400
