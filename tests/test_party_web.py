"""🎭 API + หน้าล็อบบี้ปาร์ตี้บนเว็บ (เฟส 2)

⚠️ เทสชั้นนี้คุม "ทางเข้าฝั่งเว็บ" — กติกาคุมที่ test_party_room.py แล้ว
"""
import pathlib
import re
import shutil
import subprocess

import pytest

WEB = pathlib.Path("license_server/web_static")
HTML = (WEB / "play.html").read_text(encoding="utf-8")
CSS = (WEB / "play.css").read_text(encoding="utf-8")
PLAY = (WEB / "play.js").read_text(encoding="utf-8")
LOBBY = (WEB / "games/party/lobby.js").read_text(encoding="utf-8")


# ── API ──

def test_endpoint_ลงทะเบียนแล้ว():
    """ลืม include_router = เว็บ 404 ตอนรันจริง แต่เทสอื่นจับไม่ได้"""
    from license_server import web_api

    def flat(r, pre=""):
        out = []
        for x in getattr(r, "routes", []):
            o = getattr(x, "original_router", None)
            if o is not None:
                out += flat(o, pre + getattr(x, "prefix", ""))
            elif hasattr(x, "path"):
                out.append(pre + x.path)
        return out

    paths = flat(web_api.router)
    assert "/party/room" in paths, "ยังไม่ได้ include_router ของปาร์ตี้"


def test_route_เดิมไม่หายไปเพราะเพิ่มของใหม่():
    from license_server import web_api

    def flat(r, pre=""):
        out = []
        for x in getattr(r, "routes", []):
            o = getattr(x, "original_router", None)
            if o is not None:
                out += flat(o, pre + getattr(x, "prefix", ""))
            elif hasattr(x, "path"):
                out.append(pre + x.path)
        return out

    n = len(flat(web_api.router))
    assert n >= 83, f"route หายไป เหลือ {n} (ก่อนเพิ่มปาร์ตี้มี 81 + ของปาร์ตี้ 2)"


def test_api_ห้ามรับ_uid_จาก_body():
    """คนยิง API ตรง ๆ ต้องปลอมเป็นคนอื่นไม่ได้ (คำเชิญ UNO เคยพลาดข้อนี้)"""
    from license_server.api_web.games.party import PartyBody

    fields = set(PartyBody.model_fields)
    for banned in ("uid", "from_uid", "host", "user_id"):
        assert banned not in fields, \
            f"PartyBody รับ {banned} จาก body — ต้องเอามาจาก session เท่านั้น"


def test_api_ตอบด้วย_view_ไม่ใช่_state_ดิบ():
    """เฟส 3 จะมีค่าลับของมอนใน state — ต้องผ่านประตูเดียวตั้งแต่ตอนนี้"""
    src = pathlib.Path("license_server/api_web/games/party.py").read_text(encoding="utf-8")
    assert "room.view(uid)" in src
    assert "lobby.load" not in src, "API ห้ามอ่าน state ดิบเอง ต้องผ่าน room.view()"


def test_api_เช็คล็อกอินทุกทาง():
    src = pathlib.Path("license_server/api_web/games/party.py").read_text(encoding="utf-8")
    routes = src.count("@router.")
    guards = src.count("require_player(request)")
    assert guards >= routes, f"มี {routes} เส้นทาง แต่เช็คล็อกอินแค่ {guards} จุด"


# ── หน้าเว็บ ──

def test_โหลดไฟล์ล็อบบี้ในหน้าเว็บ():
    assert "/games/party/lobby.js" in HTML, "play.html ไม่ได้โหลด lobby.js"


def test_lobby_js_โหลดหลัง_play_js():
    """lobby.js ใช้ api() กับ toast() จาก play.js/web.js — โหลดก่อนจะพัง"""
    assert HTML.index("/games/party/lobby.js") > HTML.index("/play.js")


def test_เข้าหน้าปาร์ตี้แล้วเรียก_fillParty():
    assert "if (id === 'party') fillParty();" in PLAY, \
        "showPanel ไม่ได้เรียก fillParty — เข้าหน้าแล้วจอว่าง"


def test_ใช้ตัวช่วยเรียก_api_ตัวจริง():
    """โปรเจ็คนี้ใช้ api(method, url, body) — เขียนชื่ออื่นจะพังตอนรัน"""
    assert "await api('GET'" in LOBBY or 'await api("GET"' in LOBBY
    assert "await api('POST'" in LOBBY or 'await api("POST"' in LOBBY
    assert "await API(" not in LOBBY, "ไม่มีฟังก์ชันชื่อ API() ในโปรเจ็คนี้"


def test_หยุด_poll_เมื่อออกจากห้อง():
    """ยิงทิ้งไว้ = เปลืองทั้งเครื่องผู้เล่นและเซิร์ฟเวอร์"""
    assert "clearInterval(PARTY_POLL)" in LOBBY


def test_ไม่คำนวณกติกาฝั่งเบราว์เซอร์():
    """เบราว์เซอร์ส่งแค่ 'กดปุ่มไหน' — เจอคำพวกนี้แปลว่าเริ่มตัดสินเองแล้ว"""
    for bad in ("Math.random", "rollDice", "calcDamage"):
        assert bad not in LOBBY, f"lobby.js มี {bad} — กติกาต้องตัดสินที่เซิร์ฟเวอร์"


def test_มี_css_ของล็อบบี้():
    for cls in (".party-lobby", ".party-seats", ".party-code"):
        assert cls in CSS, f"ไม่มี CSS {cls} — หน้าจะเพี้ยน"


def test_ใช้ตัวแปรสีที่นิยามจริง():
    """--g-text ไม่มีนิยามในโปรเจ็ค (ของเดิมใช้ผิดอยู่ 3 จุด) ของใหม่ต้องไม่ทำตาม"""
    block = CSS[CSS.index("/* ── ล็อบบี้ปาร์ตี้"):]
    assert "var(--g-text)" not in block
    for used in set(re.findall(r"var\((--g-[a-z]+)\)", block)):
        assert f"{used}:" in CSS, f"ใช้ {used} แต่ไม่มีนิยามในไฟล์"


# ── หน้าจอต่อสู้ (เฟส 3) ──

def test_โหลด_renderer_ก่อน_lobby():
    """lobby.js เรียก pbMount/pbSetState — โหลดทีหลังจะพัง"""
    assert HTML.index("/games/party/renderer_basic.js") < HTML.index("/games/party/lobby.js")


def test_หน้าจอต่อสู้วาดได้จริง():
    """เทสอ่านข้อความจับไม่ได้ว่าโค้ดรันแล้วพังไหม (บทเรียนจาก !login เงียบ)

    party_boot.js โหลด JS จริงเข้า vm แล้ววาดเฟรม + ป้อน events ทุกชนิด
    """
    if not shutil.which("node"):
        pytest.skip("เครื่องนี้ไม่มี node")
    r = subprocess.run(["node", "tests/party_boot.js"],
                       capture_output=True, text=True, encoding="utf-8")
    assert r.returncode == 0, r.stdout + r.stderr


def test_แถบคำสั่งมีครบ_6_ท่า():
    """ต้องตรงกับ engine.ACTIONS ฝั่งเซิร์ฟเวอร์ ไม่งั้นกดแล้วเซิร์ฟปฏิเสธ"""
    from bot.games.party import engine
    for a in engine.ACTIONS:
        assert f'data-a="{a}"' in LOBBY, f"แถบคำสั่งไม่มีปุ่ม {a}"


def test_ท่าที่ไม่ต้องเล็งสั่งได้เลย():
    """defend/flee/aoe ไม่ต้องเลือกเป้า — บังคับเลือกจะกดไม่ได้"""
    assert "a === 'defend' || a === 'flee' || a === 'aoe'" in LOBBY
