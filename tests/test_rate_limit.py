"""🚦 จำกัดอัตราการยิง API (เว็บเกม เฟส 6)

กันสคริปต์ยิงรัวฟาร์มของ และกันยิงถล่มจนเซิร์ฟล่ม
สิ่งที่ต้องคุม: นับรายคนไม่ใช่รายไอพี · เส้นทางเงินคุมแน่นกว่าเส้นทางอ่าน ·
ตัวนับต้องคลายเองเมื่อเวลาผ่านไป · หน่วยความจำต้องไม่โตไม่หยุด
"""
import pathlib

import pytest

from license_server import rate_limit


@pytest.fixture(autouse=True)
def clean():
    rate_limit.reset()
    yield
    rate_limit.reset()


def _spam(user, path, method="POST", times=100, now=1000.0):
    """ยิงรัวจนโดนบล็อก — คืนจำนวนครั้งที่ผ่าน"""
    ok = 0
    for _ in range(times):
        passed, _retry = rate_limit.check(user, path, method, now=now)
        if not passed:
            break
        ok += 1
    return ok


def test_money_routes_are_the_tightest():
    """ธนาคาร/คาสิโน/กาชา = ของที่แตะเงินก้อน ต้องคุมแน่นกว่าอย่างอื่น"""
    assert _spam("a", "/api/web/casino") == rate_limit.LIMITS["money"][0]
    assert _spam("b", "/api/web/adventure/walk") == rate_limit.LIMITS["write"][0]
    assert rate_limit.LIMITS["money"][0] < rate_limit.LIMITS["write"][0] < rate_limit.LIMITS["read"][0]


def test_reading_the_screen_is_not_punished():
    """โหลดข้อมูลหน้าจอเป็นเรื่องปกติ ต้องไม่โดนบล็อกง่าย ๆ"""
    assert _spam("a", "/api/web/me/game", "GET", times=200) >= 200


def test_one_player_hitting_the_wall_never_blocks_another():
    """นับรายคน — คนเดียวยิงรัวต้องไม่ทำให้ทั้งเซิร์ฟใช้ไม่ได้"""
    _spam("คนยิงรัว", "/api/web/casino")
    assert rate_limit.check("คนปกติ", "/api/web/casino", "POST", now=1000.0)[0]


def test_the_counter_relaxes_after_the_window():
    limit, window = rate_limit.LIMITS["money"]
    _spam("a", "/api/web/bank", now=1000.0)
    assert not rate_limit.check("a", "/api/web/bank", "POST", now=1000.0)[0]
    assert rate_limit.check("a", "/api/web/bank", "POST", now=1000.0 + window + 1)[0]


def test_being_blocked_tells_you_how_long_to_wait():
    _spam("a", "/api/web/bank", now=1000.0)
    ok, retry = rate_limit.check("a", "/api/web/bank", "POST", now=1000.0)
    assert not ok and 0 < retry <= rate_limit.LIMITS["money"][1] + 1


def test_groups_are_counted_separately():
    """ยิงคาสิโนจนเต็มโควตา ต้องไม่ทำให้เดินทางไม่ได้"""
    _spam("a", "/api/web/casino")
    assert rate_limit.check("a", "/api/web/adventure/walk", "POST", now=1000.0)[0]


def test_login_codes_are_rate_limited_hardest():
    """ขอโค้ดล็อกอินรัว = สุ่มเดาโค้ดคนอื่น ต้องคุมแน่นและหน้าต่างยาว"""
    assert rate_limit.LIMITS["auth"][0] <= 10 and rate_limit.LIMITS["auth"][1] >= 300
    assert rate_limit.group_for("/api/web/login/code", "POST") == "auth"
    assert rate_limit.group_for("/api/web/login/t/abc", "GET") == "auth"


def test_checking_your_own_code_is_not_the_same_as_asking_for_one():
    """เดิมรวมสองอย่างนี้ไว้กลุ่มเดียวกัน แล้วล็อกอินพังจริง

    หน้าล็อกอินหมุนถามสถานะทุก 2.5 วิ รอผู้ใช้ไปพิมพ์โค้ดในดิส
    โควตา 10 ครั้ง/5 นาที เลยหมดใน 25 วินาที หน้าเว็บค้างก่อนผู้ใช้จะพิมพ์ทัน
    รายละเอียดครบอยู่ใน tests/test_login_flow.py
    """
    assert rate_limit.group_for("/api/web/login/status", "GET") == "poll"
    assert rate_limit.LIMITS["poll"][0] > 300 / 2.5, "หมุนถามครบ 5 นาทีไม่ได้"


def test_non_api_paths_are_left_alone():
    """หน้าเว็บ/รูป/ไฟล์สแตติก ไม่ใช่เรื่องของตัวจำกัดอัตรา"""
    for path in ("/play", "/assets/events/village.png", "/play.js"):
        assert rate_limit.group_for(path, "GET") is None
        assert rate_limit.check("a", path, "GET")[0]


def test_unknown_api_routes_default_to_write():
    """เพิ่ม endpoint ใหม่แล้วลืมจัดกลุ่ม ต้องตกไปกลุ่มที่คุมไว้ ไม่ใช่ปล่อยฟรี"""
    assert rate_limit.group_for("/api/web/ของใหม่ที่ยังไม่จัดกลุ่ม", "POST") == "write"


def test_memory_does_not_grow_forever():
    """คนเข้าเยอะ ๆ แล้วหายไป ตัวนับต้องถูกเก็บกวาด ไม่งั้นแรมบวมเรื่อย ๆ"""
    for i in range(400):
        rate_limit.check(f"ผู้เล่น{i}", "/api/web/me/game", "GET", now=1000.0)
    before = len(rate_limit._hits)
    rate_limit.check("คนใหม่", "/api/web/me/game", "GET", now=1000.0 + 4000)
    assert len(rate_limit._hits) < before, "ไม่ได้เก็บกวาดรอยเก่าเลย"


def test_it_is_actually_wired_into_the_server():
    api = pathlib.Path("license_server/api.py").read_text(encoding="utf-8")
    assert "rate_limit.check(" in api and "status_code=429" in api
    assert 'request.cookies.get("web_session")' in api, "ต้องนับรายคนก่อน ไม่ใช่รายไอพี"


# ── session หมดอายุ + ทางออก (เฟส 6) ─────────────────────────────────────────

def test_an_expired_session_sends_you_back_to_login():
    """เดิม 401 แล้วขึ้นแค่ toast แดง ผู้เล่นไม่รู้ว่าต้องทำอะไรต่อ"""
    js = pathlib.Path("license_server/web_static/web.js").read_text(encoding="utf-8")
    assert "res.status === 401" in js and "onSessionExpired()" in js
    assert "/login" in js[js.index("function onSessionExpired"):]


def test_the_game_page_has_a_way_to_log_out():
    """session อยู่ 30 วัน เครื่องสาธารณะต้องมีทางออก"""
    html = pathlib.Path("license_server/web_static/play.html").read_text(encoding="utf-8")
    js = pathlib.Path("license_server/web_static/play.js").read_text(encoding="utf-8")
    assert 'id="playLogout"' in html
    assert "/api/web/logout" in js and "location.href = '/login'" in js


def test_the_layout_survives_a_375px_phone():
    """จอมือถือเล็กสุดที่ยังเจอบ่อย — ปุ่มต้องไม่ล้นจอ"""
    css = pathlib.Path("license_server/web_static/play.css").read_text(encoding="utf-8")
    assert "@media (max-width: 400px)" in css
    block = css[css.index("@media (max-width: 400px)"):]
    for sel in (".g-grid", ".bet-row", ".board", ".adv-hud"):
        assert sel in block[:1400], f"จอแคบยังไม่ได้จัด {sel}"
