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
    """lobby.js เรียก pbMount/pbSetState — โหลดทีหลังจะพัง

    ไม่ผูกกับชื่อไฟล์ตัวใดตัวหนึ่ง เพราะสลับ renderer ได้ (เฟส 7)
    """
    at = re.search(r"/games/party/renderer_[a-z_]+\.js", HTML)
    assert at, "play.html ไม่ได้โหลด renderer เลย"
    assert at.start() < HTML.index("/games/party/lobby.js")


def test_หน้าจอต่อสู้วาดได้จริง():
    """เทสอ่านข้อความจับไม่ได้ว่าโค้ดรันแล้วพังไหม (บทเรียนจาก !login เงียบ)

    party_boot.js โหลด JS จริงเข้า vm แล้ววาดเฟรม + ป้อน events ทุกชนิด
    """
    if not shutil.which("node"):
        pytest.skip("เครื่องนี้ไม่มี node")
    r = subprocess.run(["node", "tests/party_boot.js"],
                       capture_output=True, text=True, encoding="utf-8")
    assert r.returncode == 0, r.stdout + r.stderr


def test_แถบคำสั่งสร้างจากคลาสไม่ใช่ฝังรายชื่อไว้():
    """⭐ เจ้าของเกมสั่ง 2026-09-04: คลาสต่างกันปุ่มต้องต่างกัน

    ฝังรายชื่อท่าไว้ในหน้าเว็บเมื่อไหร่ = เพิ่มคลาสใหม่หรือปรับท่าที่เกมหลัก
    แล้วหน้าเว็บไม่ตามไปด้วย ต้องสร้างจาก me.skills ที่เซิร์ฟเวอร์ส่งมา
    """
    from bot.games.party import skills
    assert "me.skills" in LOBBY, "ไม่ได้สร้างปุ่มจากชุดสกิลที่เซิร์ฟเวอร์ส่งมา"
    for key in skills.SPEC:
        assert f'data-a="{key}"' not in LOBBY, \
            f"ฝังชื่อท่า {key} ไว้ในหน้าเว็บ — ต้องสร้างจากข้อมูลเซิร์ฟเวอร์"
    for fixed in ("attack", "flee"):
        assert f'data-a="{fixed}"' in LOBBY, f"ไม่มีปุ่ม {fixed}"


def test_ปุ่มสกิลเทาไว้ตอนติดคูลดาวน์หรือเม็ดหมด():
    assert "sk.cd > 0" in LOBBY and "me.mana" in LOBBY
    assert "disabled" in LOBBY


def test_หน้าเว็บโชว์เม็ดคริสตัล():
    """ไม่โชว์ = กดสกิลไม่ได้แล้วไม่รู้ว่าทำไม"""
    assert "me.mana_max" in LOBBY


def test_ท่าที่ไม่ต้องเล็งดูจากข้อมูลเซิร์ฟเวอร์():
    """เช็คชื่อท่าทีละตัวแล้วเพิ่มท่าใหม่ทีไรก็ต้องมาแก้ที่นี่ทุกที"""
    assert "['self', 'all', 'party'].includes(btn.dataset.t)" in LOBBY
    assert "a === 'defend'" not in LOBBY, "ยังเช็คชื่อท่าทีละตัวอยู่"


def test_หัวห้องเลือกล่าบอสได้():
    """ธง boss_raid มีในเซิร์ฟเวอร์แล้ว ต้องมีทางกดจริง ไม่งั้นเป็นโค้ดตาย"""
    assert 'id="partyBoss"' in LOBBY
    assert "boss_raid:" in LOBBY, "ติ๊กแล้วแต่ไม่ได้ส่งไปเซิร์ฟเวอร์"
    assert ".party-raid" in CSS


def test_api_รับธงล่าบอส():
    from license_server.api_web.games.party import PartyBody
    assert "boss_raid" in PartyBody.model_fields


# ── สรุปรางวัล (เฟส 5) ──

def test_หน้าเว็บโชว์รางวัลหลังจบ():
    for want in ("partyRewardHtml", "party-reward"):
        assert want in LOBBY, f"ไม่มี {want} — ชนะแล้วผู้เล่นไม่รู้ว่าได้อะไร"
    assert ".party-reward" in CSS


def test_ไม่คำนวณทองฝั่งเบราว์เซอร์():
    """🔒 ตัวเลขเงินต้องมาจากเซิร์ฟเวอร์ล้วน ๆ"""
    for bad in ("PARTY_MULT", "* 1.5", "split_gold"):
        assert bad not in LOBBY, f"lobby.js คำนวณเงินเอง ({bad})"


# ── คนหลุด/ชุบ (เฟส 6) ──

def test_ปุ่มชุบเทาไว้เมื่อใช้ไม่ได้():
    """ให้กดแล้วค่อยด่าคือ UX แย่ — เซิร์ฟเวอร์บอก can_revive มาแล้ว"""
    assert "me.can_revive" in LOBBY
    assert "disabled" in LOBBY


def test_หน้าเว็บโชว์เวลาถอยหลัง():
    """ไม่โชว์ = อยู่ ๆ บอทก็เล่นแทน ผู้เล่นงงว่าเกิดอะไรขึ้น"""
    assert "turn_left" in LOBBY
    assert ".party-clock" in CSS


# ── บั๊กที่เจอตอนเทสด้วยมือ 2026-09-04 ──

def test_ยัง_poll_ต่อตอนสู้อยู่():
    """⭐ หยุด poll ตอนเข้าสู้ = พังสองเด้ง

    1. คนที่นั่งรอเห็นจอค้าง เพื่อนกดอะไรก็ไม่รู้
    2. นาฬิกาเทิร์นฝั่งเซิร์ฟเวอร์เดินตอน view() เท่านั้น — ไม่มีใคร poll
       ก็ไม่มีใครปลด ตาค้างตลอดกาลแม้หมดเวลา
    โค้ดเดิมมี partyWatch(false) ตอน phase === 'battle' พร้อมคอมเมนต์ว่า
    "เฟส 3 รับช่วงต่อ" แต่เฟส 3 ไม่เคยทำต่อ
    """
    assert "phase !== 'battle'" not in LOBBY, "ยังกันไม่ให้ poll ตอนสู้อยู่"
    assert "PARTY.phase === 'battle') partyWatch(false)" not in LOBBY


def test_จบสมรภูมิแล้วยังฟังต่อว่าหัวห้องพาไปต่อไหม():
    """⭐ เทสข้อนี้เคยเขียนกลับด้าน — บังคับให้ "หยุด poll เมื่อจบ"
       ผลคือหัวห้องกดออกเดินทางต่อแล้ว **เพื่อนค้างหน้าสรุปผลตลอดกาล**
       (เจ้าของเกมเจอตอนเทสด้วยมือ 2026-09-04)
       หยุดได้อย่างเดียวคือตอนออกจากห้อง
    """
    assert "PARTY.battle.over) partyWatch(false)" not in LOBBY,         "ยังหยุดฟังตอนจบสมรภูมิ เพื่อนจะไม่รู้ว่าหัวห้องพาไปต่อ"
    assert "if (!PARTY.in_room) partyWatch(false)" in LOBBY


def test_สมรภูมิใหม่นับเหตุการณ์ใหม่():
    """seq รอบใหม่เริ่มจาก 0 — ไม่รีเซ็ตฝั่งเบราว์เซอร์ก็ไม่มีอนิเมชันเลย
       จนกว่าจะเกินเลขรอบเก่า"""
    assert "b.bid !== PARTY_BID" in LOBBY, "ไม่มีตัวจับว่าสมรภูมิเริ่มใหม่"
    assert "PARTY_SEQ = 0;" in LOBBY
    # ⚠️ ห้ามกลับไปใช้ "เลขถอยหลัง" — รอบเก่าจบที่ 1 รอบใหม่เริ่มที่ 1 จับไม่ได้
    assert "b.seq < PARTY_SEQ" not in LOBBY


def test_เล่นอนิเมชันของเพื่อนไม่ซ้ำ():
    """เห็นแต่เลือดเปลี่ยนวูบไม่รู้ว่าใครทำอะไร — ต้องเล่น events ของเพื่อนด้วย
       และต้องมี seq กันเล่นซ้ำรอบ poll ถัดไป"""
    assert "partyPlayNew" in LOBBY
    # ⚠️ เช็คแค่ว่ามีชื่อ PARTY_SEQ ไม่พอ — ย้อนเทสถอดเงื่อนไขทิ้งแล้วยังเขียว
    #    ต้องตรึงตัวเปรียบเทียบจริง ไม่งั้นเลขดาเมจเด้งซ้ำทุก 2 วิไม่หยุด
    assert "b.seq > PARTY_SEQ" in LOBBY, "ไม่มีตัวกันเล่นอนิเมชันซ้ำ"
    assert "PARTY_SEQ = PARTY.battle.seq" in LOBBY, "กดเองแล้วไม่จำ seq จะเล่นซ้ำ"


def test_css_เลือกโดนแคนวาสที่ซ้อนอยู่():
    """⭐ lobby.js ห่อ canvas ไว้ใน <div id="partyCanvas"> อีกชั้น
       CSS ที่ใช้ลูกตรง (>) จะไม่โดน canvas กางเต็ม 900px ทะลุจอมือถือ
    """
    assert 'id="partyCanvas"' in LOBBY, "โครง DOM เปลี่ยนไป ต้องมาทบทวน CSS ด้วย"
    assert ".party-mount > canvas" not in CSS, "ใช้ลูกตรงแล้วไม่โดนแคนวาสที่ซ้อนอยู่"
    assert ".party-mount canvas" in CSS


def test_จอกับแถบคำสั่งเรียงบนล่างไม่ใช่ซ้ายขวา():
    """.party-mount เป็น flex — ไม่ตั้ง column แถบคำสั่งจะไปแปะข้างจอ
       จนบีบเป็นเสาผอม ๆ (เจอตอนเทสด้วยมือ)"""
    block = CSS[CSS.index(".party-mount {"):CSS.index(".party-mount canvas")]
    assert "flex-direction: column" in block


def test_มี_media_query_สำหรับจอแคบ():
    assert "@media (max-width: 560px)" in CSS


def test_มีปุ่มออกเดินทางต่อหลังจบ():
    """ชนะแล้วมีแต่ปุ่มออกจากปาร์ตี้ = ต้องตั้งห้องใหม่ทุกรอบ"""
    assert 'id="partyAgain"' in LOBBY
    assert "partyDo('again')" in LOBBY
    assert "PARTY_SEQ = 0" in LOBBY, "สมรภูมิใหม่ต้องนับเหตุการณ์ใหม่"


def test_ตัวหนาในกล่องรางวัลไม่กลายเป็นบรรทัดใหญ่():
    """⭐ .party-result b (ไม่มี >) ไปโดน <b> ในกล่องรางวัลด้วย
       ตัวเลขทองกับชื่อไอเทมเด้งขึ้นบรรทัดใหม่ 22px หน้าเบี้ยวทั้งแถบ
       (เจ้าของเกมเจอตอนเทสด้วยมือบนเดสก์ท็อป)
    """
    assert ".party-result b {" not in CSS, "ต้องใช้ลูกตรง (>) ไม่งั้นโดนกล่องรางวัลด้วย"
    assert ".party-result > b {" in CSS
    assert ".party-reward b { display: inline" in CSS
    # สีชนะ/แพ้ก็ต้องลูกตรง ไม่งั้นทับสีตัวเลขในกล่องรางวัล
    for sel in (".party-result.win b {", ".party-result.lose b {"):
        assert sel not in CSS, f"{sel} ไม่มี > จะโดนกล่องรางวัลด้วย"


def test_เตือนก่อนติ๊กล่าบอส():
    """วัดจริง 2026-09-04: ปาร์ตี้เลเวล 1 ล่าบอสชนะ 0/30 — ต้องบอกก่อนกด"""
    assert "party-warn" in LOBBY and ".party-warn" in CSS


# ── รอบการเดินทาง + ล้มยกทีม (เฟส 10a) ──

def test_หน้าเว็บโชว์รอบการเดินทาง():
    """ผู้เล่นต้องรู้ว่าเดินมาไกลแค่ไหน ไม่งั้นไม่รู้ว่าเสี่ยงแค่ไหน"""
    assert "PARTY.round ?" in LOBBY, "ไม่ได้เอารอบมาแสดงจริง"
    assert "🧭 รอบที่ ${PARTY.round}" in LOBBY


def test_ล้มยกทีมโชว์ปุ่มเริ่มใหม่ไม่ใช่ไปต่อ():
    """⭐ กด "ไปต่อ" หลังล้มยกทีมไม่ได้ (เซิร์ฟเวอร์ปฏิเสธ) — ปุ่มต้องเปลี่ยนด้วย"""
    assert 'id="partyRestart"' in LOBBY
    assert "partyDo('restart')" in LOBBY
    assert "PARTY.wiped" in LOBBY, "ไม่ได้ดูธงล้มยกทีมเลย"


def test_จอสรุปโทษบอกครบว่าเสียอะไร():
    """เงินหายเงียบ ๆ = ผู้เล่นคิดว่าเป็นบั๊ก"""
    # ⚠️ เช็คแค่ว่า "มีฟังก์ชันอยู่" ไม่พอ — ตัวนิยามก็นับ แม้ไม่มีใครเรียก
    #    ต้องตรึง **จุดที่เรียก** ด้วย (ย้อนเทสจับได้ 2026-09-04)
    assert "wiped ? partyPenaltyHtml() : partyRewardHtml()" in LOBBY,         "ไม่ได้เรียกจอสรุปโทษตอนล้มยกทีม"
    for want in ("เสีย", "ทอง", "EXP", "เลเวลลด", "รอบ 1"):
        assert want in LOBBY, f"จอสรุปโทษไม่บอกเรื่อง {want}"


def test_ไม่คำนวณโทษฝั่งเบราว์เซอร์():
    """🔒 ตัวเลขที่เสียต้องมาจากเซิร์ฟเวอร์ล้วน ๆ"""
    for bad in ("wipe_gold_pct", "* 0.1", "wipe_exp_pct"):
        assert bad not in LOBBY, f"lobby.js คำนวณโทษเอง ({bad})"


def test_api_รับคำสั่งเริ่มออกเดินทางใหม่():
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

    assert "/party/room" in flat(web_api.router)
    src = pathlib.Path("license_server/api_web/games/party.py").read_text(encoding="utf-8")
    assert 'body.action == "restart"' in src
    assert "room.restart(uid)" in src


# ── ห้ามแซงอนิเมชัน (เจ้าของเกมเจอตอนเทสด้วยมือ 2026-09-04) ──

def test_รอให้อนิเมชันจบก่อนโชว์ผลกับเปิดปุ่ม():
    """⭐ เซิร์ฟเวอร์สรุปผลทั้งตาเสร็จก่อนอนิเมชันเริ่มเล่น

    วาดตามสถานะทันที = เห็น "ปาร์ตี้ชนะ!" ตั้งแต่เลือดมอนยังไม่ทันลด
    และกดปุ่มได้ทั้งที่ตายังเป็นของมอน
    """
    assert "pbPending() > 0" in LOBBY, "ไม่ได้เช็คว่าอนิเมชันจบหรือยัง"
    i = LOBBY.index("function partyPaintBar()")
    head = LOBBY[i:i + 1200]
    assert head.index("pbPending() > 0") < head.index("if (b.over)"), \
        "เช็คอนิเมชันทีหลังการโชว์ผล — ผลจะขึ้นก่อนอยู่ดี"


def test_เช็คซ้ำจนอนิเมชันนิ่ง():
    """เช็คครั้งเดียวไม่พอ — ต้องมีตัวนัดมาดูใหม่ ไม่งั้นค้างที่ "กำลังต่อสู้" """
    assert "setTimeout(partyPaintBar" in LOBBY


def test_ออกจากห้องแล้วไม่มีตัวจับเวลาค้าง():
    """ยิงทิ้งไว้ = เปลืองเครื่องผู้เล่น (บทเรียนเดียวกับ PARTY_POLL)"""
    assert "clearTimeout(PARTY_ANIM)" in LOBBY


def test_เข้าคิวเหตุการณ์แล้ววาดปุ่มใหม่():
    """⭐ รอบ poll เรียก partyPaint() ก่อน partyPlayNew() เสมอ

    ถ้าไม่วาดปุ่มใหม่หลังเข้าคิว ตอนวาดปุ่มจะยังเห็นคิวว่างแล้วเปิดปุ่มทันที
    ทั้งที่อนิเมชันกำลังจะเริ่ม (เจ้าของเกมเจอ: เพื่อนตีปุ๊บ อีกคนกดได้เลย)
    """
    i = LOBBY.index("function partyPlayNew()")
    body = LOBBY[i:LOBBY.index("function partyPaint()", i)]
    assert "partyPaintBar()" in body, "เข้าคิวแล้วไม่ได้วาดปุ่มใหม่"
    assert body.index("pbPlay(") < body.index("partyPaintBar()"), \
        "วาดปุ่มก่อนเข้าคิว — ปุ่มจะเปิดทั้งที่อนิเมชันยังไม่เริ่ม"
