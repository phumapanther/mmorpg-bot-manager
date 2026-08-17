"""👑 ร้านขายยศ + กาชาสุ่มยศ — ยศต้องให้บอทเป็นคนแจก

บั๊กที่ผู้เล่นเจอ 2 อย่างพร้อมกัน:
  1. กาชาสุ่มยศกดแล้วไม่ทำงาน — กาชาแฟชั่นที่ทำทีหลังตั้งชื่อฟังก์ชันชนกัน
     ใน JS ตัวที่ประกาศทีหลังทับตัวแรกเงียบ ๆ ปุ่มกาชายศเลยไปเรียกตู้แฟชั่นแทน
  2. บอทดิสดับแล้วยังซื้อยศได้ — เงินหักไปแล้วรายการค้างในคิว ไม่มีใครมาแจก
"""
import pathlib
import re
import time

import pytest

import bot.models.player_model as pm
from license_server import web_db

UID = 7701
WEB = pathlib.Path("license_server/web_static")
PLAY = (WEB / "play.js").read_text(encoding="utf-8")


# ── บั๊ก 1: ชื่อฟังก์ชันชนกัน ──

def _top_level_functions(src):
    return re.findall(r"^(?:async )?function ([A-Za-z0-9_]+)", src, re.M)


def test_no_two_functions_share_a_name():
    """ชื่อชนกันใน JS = ตัวหลังทับตัวแรกเงียบ ๆ ไม่มี error ให้เห็น

    เคยพลาดมาแล้ว: fillGacha ของกาชายศ ถูก fillGacha ของกาชาแฟชั่นทับ
    ปุ่มกาชายศเลยไปวาดลงแผงแฟชั่น หน้าตัวเองว่างเปล่า
    """
    names = _top_level_functions(PLAY)
    dupes = sorted({n for n in names if names.count(n) > 1})
    assert not dupes, f"ชื่อฟังก์ชันซ้ำใน play.js (ตัวหลังทับตัวแรก): {dupes}"


@pytest.mark.parametrize("f", ["play.js", "scene.js", "sprite.js", "sfx.js", "web.js"])
def test_every_browser_file_is_free_of_name_clashes(f):
    src = (WEB / f).read_text(encoding="utf-8")
    names = _top_level_functions(src)
    dupes = sorted({n for n in names if names.count(n) > 1})
    assert not dupes, f"{f} มีชื่อฟังก์ชันซ้ำ: {dupes}"


def test_each_gacha_panel_calls_its_own_loader():
    """ปุ่มกาชายศกับกาชาแฟชั่นต้องเรียกคนละตัว ไม่งั้นกดปุ่มหนึ่งไปเปิดอีกหน้า"""
    assert "if (id === 'gacha') fillGacha()" in PLAY, "ปุ่มกาชายศไม่ได้เรียกตัวโหลดของตัวเอง"
    assert "if (id === 'fgacha') fillFashionGacha()" in PLAY, "ปุ่มกาชาแฟชั่นเรียกผิดตัว"


def test_the_role_gacha_still_writes_into_its_own_panel():
    fn = PLAY[PLAY.index("async function fillGacha()"):]
    fn = fn[:fn.index("\n}\n")]
    assert "gachaPrice" in fn and "gachaBtn" in fn, "ตัวโหลดกาชายศไม่ได้แตะแผงของตัวเอง"
    assert "fgTiers" not in fn, "ตัวโหลดกาชายศไปเขียนลงแผงแฟชั่น"


# ── บั๊ก 2: บอทดับแล้วห้ามซื้อ ──

@pytest.fixture
def web(tmp_path, monkeypatch):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from license_server import web_api

    monkeypatch.setattr(pm, "DB_NAME", str(tmp_path / "g.db"))
    monkeypatch.setattr(web_db, "DB_PATH", tmp_path / "web.db")
    pm.init_db()
    pm.get_player(UID)
    pm.update_player_fields(UID, {"cash": 10_000_000_000})
    monkeypatch.setattr(web_api, "GAME_DB_PATH", tmp_path / "g.db")
    app = FastAPI()
    app.include_router(web_api.router)
    c = TestClient(app)
    c.cookies.set("web_session", web_api.sign({"uid": str(UID), "exp": time.time() + 3600}))
    return c


def _cash():
    return int(pm.get_player(UID)["cash"])


@pytest.mark.parametrize("action", ["buy", "gacha"])
def test_a_dead_bot_blocks_the_purchase_before_any_gold_moves(web, action):
    """บอทดับ = ไม่มีใครแจกยศ ต้องกันตั้งแต่ก่อนหักเงิน"""
    before = _cash()
    r = web.post("/api/web/roleshop", json={"faction": "dark", "action": action, "value": ""})
    assert r.status_code == 503, f"บอทดับแต่ยังซื้อได้: {r.status_code}"
    assert "ออฟไลน์" in r.json()["detail"]
    assert _cash() == before, "บอทดับแต่เงินหักไปแล้ว"


def test_a_stale_heartbeat_counts_as_dead(web):
    """บอทเคยเต้นแล้วหายไป (ดับกลางทาง) ต้องนับว่าดับ ไม่ใช่ว่าเคยเต้นก็พอ"""
    with web_db.connect() as conn:
        conn.execute("INSERT INTO bot_heartbeat(id, beat_at) VALUES (1, ?)",
                     (time.time() - web_db.BEAT_TIMEOUT - 5,))
    assert not web_db.bot_alive()
    r = web.post("/api/web/roleshop", json={"faction": "dark", "action": "gacha"})
    assert r.status_code == 503


def test_a_live_bot_lets_the_gacha_spin(web):
    web_db.bot_ping()
    assert web_db.bot_alive()
    before = _cash()
    r = web.post("/api/web/roleshop", json={"faction": "dark", "action": "gacha"})
    assert r.status_code == 200, r.text
    assert r.json()["kind"] == "gacha" and r.json()["ticket"]
    assert _cash() < before, "หมุนกาชาแล้วไม่หักเงิน"


def test_the_shop_page_says_whether_the_bot_is_up(web):
    assert web.get("/api/web/roleshop?faction=dark").json()["bot_online"] is False
    web_db.bot_ping()
    assert web.get("/api/web/roleshop?faction=dark").json()["bot_online"] is True


def test_the_page_warns_before_you_click():
    """บอกตั้งแต่เห็นหน้า ดีกว่าปล่อยให้กดแล้วค่อยเด้ง error"""
    assert "function botOfflineBanner" in PLAY, "ไม่มีป้ายเตือนบอทออฟไลน์"
    assert "botOfflineBanner(d.bot_online)" in PLAY
    assert PLAY.count("botOfflineBanner(d.bot_online)") >= 2, "เตือนแค่หน้าเดียว อีกหน้าลืม"
    assert 'id="gachaOffline"' in (WEB / "play.html").read_text(encoding="utf-8")


# ── หัวใจต้องมีคนเต้นให้ ──

def test_the_bot_actually_pings(tmp_path, monkeypatch):
    """ถ้าไม่มีใครเรียก bot_ping เลย ทุกอย่างจะถูกมองว่าบอทดับตลอดกาล"""
    src = pathlib.Path("bot/cogs/role_grant_worker.py").read_text(encoding="utf-8")
    assert "web_db.bot_ping()" in src, "บอทไม่ได้ปั๊มหัวใจ — เว็บจะคิดว่าบอทดับตลอด"
    drain = src[src.index("async def drain"):]
    assert "bot_ping" in drain[:drain.index("try:\n            with web_db.connect()")], \
        "ปั๊มหัวใจอยู่หลังการอ่านคิว — อ่านคิวพังเมื่อไหร่หัวใจจะหยุดเต้นไปด้วย"


def test_the_heartbeat_survives_a_missing_row(tmp_path, monkeypatch):
    monkeypatch.setattr(web_db, "DB_PATH", tmp_path / "w.db")
    assert not web_db.bot_alive(), "ยังไม่เคยมีบอทเต้นเลย แต่ตอบว่ายังอยู่"
    web_db.bot_ping()
    web_db.bot_ping()                       # เต้นซ้ำต้องทับแถวเดิม ไม่ใช่ error
    assert web_db.bot_alive()
    with web_db.connect() as conn:
        assert conn.execute("SELECT COUNT(*) c FROM bot_heartbeat").fetchone()["c"] == 1
