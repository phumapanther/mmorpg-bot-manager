"""👥 ระบบเพื่อน — ฐานของหมวด PVP

สองเรื่องที่พังแล้วเจ็บที่สุด และเทสไฟล์นี้คุมเป็นหลัก:
  1. **ความเป็นส่วนตัว** — โปรไฟล์เพื่อนต้องไม่มีทอง/ธนาคาร/ของในกระเป๋าหลุดออกไป
  2. **การปั๊มตัวละคร** — get_player() สร้างตัวละครใหม่ให้ทันทีถ้ายังไม่มี
     วางไอดีมั่ว ๆ แล้วกดเพิ่มจึงต้องไม่ไปแตะฟังก์ชันนั้น
"""
import pathlib
import re
import time

import pytest

import bot.models.player_model as pm
from bot import friends

# ไอดีหน้าตาเหมือน Discord จริง (snowflake 18 หลัก) — เลขปลอมสั้น ๆ ทำให้เทสไม่ตรงของจริง
ME, PAL, STRANGER = 500100000000000001, 500200000000000002, 500300000000000003
WEB = pathlib.Path("license_server/web_static")
PLAY = (WEB / "play.js").read_text(encoding="utf-8")
HTML = (WEB / "play.html").read_text(encoding="utf-8")


@pytest.fixture
def world(tmp_path, monkeypatch):
    monkeypatch.setattr(pm, "DB_NAME", str(tmp_path / "f.db"))
    pm.init_db()
    for uid, name in ((ME, "ฉันเอง"), (PAL, "เพื่อนซี้"), (STRANGER, "คนแปลกหน้า")):
        pm.get_player(uid)
        pm.update_player_fields(uid, {"rank": name, "level": 42, "cash": 999_999_999,
                                      "bank": 123_456, "inventory": '["1","2"]',
                                      "race": "Human", "class_name": "Warrior"})
    return None


# ── เพิ่มเพื่อน ──

def test_pasting_a_real_id_works(world):
    ok, msg = friends.add(ME, str(PAL))
    assert ok, msg
    assert friends.are_friends(ME, PAL)


def test_friendship_goes_both_ways(world):
    """เพิ่มทางเดียว = ฝั่งหนึ่งชวนได้ อีกฝั่งชวนไม่ได้"""
    friends.add(ME, str(PAL))
    assert friends.are_friends(PAL, ME), "เพิ่มแล้วเป็นเพื่อนข้างเดียว"


def test_an_id_that_never_played_is_refused(world):
    ok, msg = friends.add(ME, "999888777666555444")
    assert not ok and "ยังไม่เคยเล่น" in msg


def test_adding_a_stranger_never_creates_a_character(world):
    """get_player() สร้างตัวละครให้ทันที — เพิ่มเพื่อนต้องไม่ไปเรียกมันกับไอดีที่ไม่มี"""
    ghost = 777666555444333222
    friends.add(ME, str(ghost))
    assert not friends.exists(ghost), "วางไอดีมั่วแล้วเกิดตัวละครเปล่าในฐานข้อมูล"


def test_you_cannot_add_yourself(world):
    ok, msg = friends.add(ME, str(ME))
    assert not ok and "ตัวเอง" in msg


def test_you_cannot_add_twice(world):
    friends.add(ME, str(PAL))
    ok, msg = friends.add(ME, str(PAL))
    assert not ok and "อยู่แล้ว" in msg
    assert len(friends.ids_of(ME)) == 1, "เพิ่มซ้ำแล้วมีสองแถว"


@pytest.mark.parametrize("junk", ["", "   ", "abc", "12", "๑๒๓๔๕", None, "1.5"])
def test_junk_input_is_refused(world, junk):
    ok, msg = friends.add(ME, junk)
    assert not ok and "ไอดีไม่ถูกต้อง" in msg


@pytest.mark.parametrize("wrapped", ["<@500200000000000002>", "<@!500200000000000002>",
                          "  500200000000000002  ", "500200000000000002"])
def test_the_shapes_discord_copies_all_work(world, wrapped):
    """คัดลอกจากดิสได้หลายแบบ ทุกแบบต้องใช้ได้"""
    assert friends.parse_id(wrapped) == PAL


def test_the_list_has_a_ceiling(world, monkeypatch):
    monkeypatch.setattr(friends, "_max_friends", lambda: 1)
    assert friends.add(ME, str(PAL))[0]
    ok, msg = friends.add(ME, str(STRANGER))
    assert not ok and "เต็ม" in msg


# ── ลบเพื่อน ──

def test_removing_cuts_both_ways(world):
    friends.add(ME, str(PAL))
    assert friends.remove(ME, str(PAL))[0]
    assert not friends.are_friends(ME, PAL) and not friends.are_friends(PAL, ME)


def test_removing_a_non_friend_says_so(world):
    ok, msg = friends.remove(ME, str(PAL))
    assert not ok and "ไม่ได้เป็นเพื่อน" in msg


# ── 🔒 ความเป็นส่วนตัว ──

PRIVATE = ("cash", "bank", "inventory", "exp", "artifact_slots", "fashion_gems",
           "fashion_owned", "capacity", "current_state", "mana")


def test_a_profile_never_leaks_money_or_bags(world):
    friends.add(ME, str(PAL))
    ok, prof = friends.profile_of(ME, str(PAL))
    assert ok, prof
    leaked = [k for k in prof if k in PRIVATE]
    assert not leaked, f"โปรไฟล์เพื่อนหลุดข้อมูลส่วนตัว: {leaked}"
    blob = str(prof)
    assert "999999999" not in blob and "123456" not in blob, "ตัวเลขเงินหลุดออกไปกับข้อมูลอื่น"


def test_you_cannot_peek_at_a_non_friend(world):
    """ไม่งั้นใครก็ไล่ส่องไอดีคนอื่นทั้งเซิร์ฟได้"""
    ok, msg = friends.profile_of(ME, str(STRANGER))
    assert not ok and "เฉพาะโปรไฟล์ของเพื่อน" in msg


def test_you_can_always_see_your_own(world):
    assert friends.profile_of(ME, str(ME))[0]


def test_a_profile_shows_the_stuff_worth_showing(world):
    friends.add(ME, str(PAL))
    prof = friends.profile_of(ME, str(PAL))[1]
    for key in ("name", "level", "race", "class_name", "fashion", "armor", "weapon", "guild"):
        assert key in prof, f"โปรไฟล์ขาด {key}"
    assert prof["name"] == "เพื่อนซี้" and prof["level"] == 42


def test_the_list_survives_a_friend_whose_character_vanished(world):
    """ลบตัวละครทิ้งจาก DB แล้วรายชื่อต้องไม่พัง"""
    friends.add(ME, str(PAL))
    conn = friends._connect()
    conn.execute("DELETE FROM players WHERE user_id=?", (PAL,))
    conn.commit()
    conn.close()
    assert friends.list_of(ME)["friends"] == []


# ── ยิงผ่าน HTTP จริง ──

@pytest.fixture
def web(tmp_path, monkeypatch):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from license_server import web_api

    monkeypatch.setattr(pm, "DB_NAME", str(tmp_path / "w.db"))
    pm.init_db()
    for uid, name in ((ME, "ฉันเอง"), (PAL, "เพื่อนซี้"), (STRANGER, "คนแปลกหน้า")):
        pm.get_player(uid)
        pm.update_player_fields(uid, {"rank": name, "cash": 999_999_999})
    from license_server.api_web import deps as _api_web_deps

    monkeypatch.setattr(_api_web_deps, "GAME_DB_PATH", tmp_path / "w.db")

    monkeypatch.setattr(web_api, "GAME_DB_PATH", tmp_path / "w.db")  # เผื่อโค้ดเก่าอ่านผ่าน web_api
    app = FastAPI()
    app.include_router(web_api.router)
    c = TestClient(app)
    c.cookies.set("web_session", web_api.sign({"uid": str(ME), "exp": time.time() + 3600}))
    return c


def test_the_whole_loop_works_over_http(web):
    assert web.get("/api/web/me/friends").json()["friends"] == []

    r = web.post("/api/web/me/friends", json={"action": "add", "id": str(PAL)})
    assert r.status_code == 200, r.text
    assert [f["id"] for f in r.json()["friends"]] == [str(PAL)]
    assert r.json()["my_id"] == str(ME)

    prof = web.get(f"/api/web/friends/{PAL}/profile")
    assert prof.status_code == 200, prof.text
    assert "cash" not in prof.json() and "999999999" not in str(prof.json())

    r = web.post("/api/web/me/friends", json={"action": "remove", "id": str(PAL)})
    assert r.status_code == 200 and r.json()["friends"] == []


def test_http_blocks_peeking_at_strangers(web):
    assert web.get(f"/api/web/friends/{STRANGER}/profile").status_code == 403


def test_a_logged_out_visitor_gets_nothing(web):
    web.cookies.clear()
    assert web.get("/api/web/me/friends").status_code in (401, 403)
    assert web.get(f"/api/web/friends/{PAL}/profile").status_code in (401, 403)


# ── หน้าเว็บ ──

def test_the_panel_is_wired():
    assert 'data-go="friends"' in HTML and 'id="v-friends"' in HTML
    assert 'id="v-friendcard"' in HTML, "ไม่มีหน้าโปรไฟล์เพื่อน"
    assert "if (id === 'friends') fillFriends()" in PLAY
    for el in ("frInput", "frAdd", "frList", "frMyId", "frCard"):
        assert el in PLAY and el in HTML, f"อ้างถึง #{el} แต่ไม่มีในหน้าเว็บ (หรือกลับกัน)"


def test_the_page_tells_you_where_to_find_the_id():
    """ผู้เล่นส่วนใหญ่ไม่รู้ว่าไอดี Discord หาจากไหน"""
    assert "โหมดนักพัฒนา" in HTML and "คัดลอกไอดีผู้ใช้" in HTML


def test_the_browser_never_decides_who_is_a_friend():
    fn = PLAY[PLAY.index("async function addFriend("):]
    fn = fn[:fn.index("\n}\n")]
    assert "/api/web/me/friends" in fn, "ไม่ได้ถามเซิร์ฟเวอร์"
    assert "players" not in fn, "เบราว์เซอร์ไปเช็คฐานข้อมูลเอง"


def test_no_new_name_clashes():
    """กันพลาดซ้ำรอย fillGacha ที่เคยทับกันเงียบ ๆ"""
    names = re.findall(r"^(?:async )?function ([A-Za-z0-9_]+)", PLAY, re.M)
    dupes = sorted({n for n in names if names.count(n) > 1})
    assert not dupes, f"ชื่อฟังก์ชันซ้ำใน play.js: {dupes}"
