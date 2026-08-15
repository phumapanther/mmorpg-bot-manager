"""🧪 กินยาระหว่างสู้มอนแล้วไฟต์ต้องไม่หาย

บั๊กที่ผู้เล่นเจอ: กำลังสู้อยู่ เปิดกระเป๋าไปหายาใหญ่มากิน พอกลับมาหน้าผจญภัย
มอนหายไปเฉย ๆ เหลือแต่ปุ่ม "ออกเดินทาง"

ต้นเหตุ: เหตุการณ์ที่ค้างอยู่หมดอายุใน 60 วินาที และการกินยาไม่ได้ต่ออายุให้
เดินไปเปิดกระเป๋า เลือกยา กดยืนยัน กว่าจะกลับมาก็เกิน 60 วิ ไฟต์เลยถูกล้างทิ้ง
"""
import time

import pytest

import bot.models.player_model as pm
from bot import adventure_core

UID = 6001
FIGHT = {"stats": {"name": "มอนทดสอบ"}, "rank": "Common", "element": "fire",
         "hp": 80, "hp_max": 80, "turn": 1}


@pytest.fixture
def web(tmp_path, monkeypatch):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from license_server import web_api

    monkeypatch.setattr(pm, "DB_NAME", str(tmp_path / "g.db"))
    pm.init_db()
    pm.get_player(UID)
    pm.update_player_fields(UID, {"current_state": "fighting", "hp": 50, "max_hp": 900,
                                  "inventory": ["1", "77"], "capacity": 20})
    monkeypatch.setattr(web_api, "GAME_DB_PATH", tmp_path / "g.db")
    app = FastAPI()
    app.include_router(web_api.router)
    c = TestClient(app)
    c.cookies.set("web_session", web_api.sign({"uid": str(UID), "exp": time.time() + 3600}))
    return c


def _age_the_fight(seconds):
    """ทำให้ไฟต์ดูเหมือนค้างมานาน N วินาที (เหมือนผู้เล่นแวะไปทำอย่างอื่น)"""
    import sqlite3
    with sqlite3.connect(pm.DB_NAME, timeout=10) as conn:
        conn.execute("UPDATE adventure_pending SET updated_at=? WHERE user_id=?",
                     (time.time() - seconds, UID))


@pytest.mark.parametrize("potion", ["1", "77"])
def test_drinking_a_potion_keeps_the_fight_alive(web, potion):
    adventure_core.set_pending(UID, "monster", FIGHT)
    _age_the_fight(120)                       # แวะเปิดกระเป๋าอยู่ 2 นาที

    r = web.post("/api/web/item/use", json={"item_id": potion}).json()
    assert r["ok"], r["message"]

    st = web.get("/api/web/adventure/state").json()
    assert st["pending"] == "monster", "กินยาแล้วมอนหายไป — ไฟต์ถูกล้างทิ้ง"
    assert pm.get_player(UID)["current_state"] == "fighting"


def test_buying_a_potion_mid_fight_keeps_the_fight_alive(web):
    """ซื้อยาระหว่างสู้ก็นับว่ายังอยู่กับไฟต์นั้น"""
    pm.update_player_field(UID, "cash", 99999)
    adventure_core.set_pending(UID, "monster", FIGHT)
    _age_the_fight(120)

    assert web.post("/api/web/shop", json={"action": "buy", "item_id": "1", "count": 2}).json()["ok"]
    assert web.get("/api/web/adventure/state").json()["pending"] == "monster"


def test_an_abandoned_fight_still_expires(web):
    """ต่ออายุได้ก็จริง แต่ปิดหน้าหนีไปเลยต้องหลุดเองได้ ไม่งั้นค้างถาวร
    (สถานะ fighting ไม่อยู่ใน lock_states ของ !play — หมดอายุคือทางออกทางเดียว)"""
    adventure_core.set_pending(UID, "monster", FIGHT)
    _age_the_fight(adventure_core.PENDING_TIMEOUT["monster"] + 10)

    assert web.get("/api/web/adventure/state").json()["pending"] is None


def test_the_fight_window_is_long_enough_to_open_your_bag(web):
    """60 วิไม่พอสำหรับเปิดกระเป๋าหายา — เว็บไม่มีนาฬิกานับถอยหลังให้เห็นด้วย"""
    assert adventure_core.PENDING_TIMEOUT.get("monster", 60) >= 600


def test_touching_does_not_change_what_is_pending(web):
    """ต่ออายุต้องแตะแค่เวลา ห้ามไปเขียนทับข้อมูลไฟต์ (เลือดมอน/เทิร์น)"""
    adventure_core.set_pending(UID, "monster", FIGHT)
    adventure_core.touch_pending(UID)
    event, data = adventure_core.get_pending(UID)
    assert event == "monster" and data["hp"] == 80 and data["turn"] == 1


def test_touching_when_nothing_is_pending_is_harmless(web):
    adventure_core.clear_pending(UID)
    adventure_core.touch_pending(UID)
    assert adventure_core.get_pending(UID)[0] is None
