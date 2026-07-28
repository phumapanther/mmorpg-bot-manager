"""C5: ตลาดผู้เล่น — เส้นทางเงินและของ ห้ามหาย ห้ามงอก ห้ามขายซ้ำ"""
import json
import sqlite3

import pytest

import bot.models.player_model as pm
from bot import config_loader, market

CFG = {"market": {"enabled": True, "tax_percent": 5, "min_price": 100,
                  "max_price": 1000000, "max_listings_per_player": 2}}


@pytest.fixture
def db(tmp_path, monkeypatch):
    path = str(tmp_path / "t.db")
    monkeypatch.setattr(pm, "DB_NAME", path)
    monkeypatch.setattr(config_loader, "get_config", lambda: CFG)
    conn = sqlite3.connect(path)
    conn.execute("""CREATE TABLE players (user_id INTEGER PRIMARY KEY, cash INTEGER, bank INTEGER,
                    inventory TEXT, capacity INTEGER)""")
    conn.execute("INSERT INTO players VALUES (1, 50000, 0, ?, 10)", (json.dumps(["30", "30", "60"]),))
    conn.execute("INSERT INTO players VALUES (2, 20000, 0, ?, 10)", (json.dumps([]),))
    conn.commit()
    conn.close()
    return path


def _player(db, uid):
    conn = sqlite3.connect(db)
    row = conn.execute("SELECT cash, bank, inventory FROM players WHERE user_id = ?", (uid,)).fetchone()
    conn.close()
    return {"cash": row[0], "bank": row[1], "inv": json.loads(row[2])}


def test_listing_takes_the_item_out_of_the_bag(db):
    ok, msg = market.list_item(1, "30", 5000)
    assert ok and "#1" in msg
    assert _player(db, 1)["inv"].count("30") == 1, "ของต้องออกจากกระเป๋าทันที กันขายซ้ำ"
    assert len(market.open_listings()) == 1


def test_cannot_list_what_you_dont_have(db):
    ok, msg = market.list_item(1, "999", 5000)
    assert not ok and "ไม่มีไอเทม" in msg
    assert market.open_listings() == []


def test_price_bounds(db):
    assert market.list_item(1, "30", 5)[0] is False          # ต่ำกว่า min
    assert market.list_item(1, "30", 99999999)[0] is False   # เกิน max
    assert market.list_item(1, "30", "abc")[0] is False      # ไม่ใช่ตัวเลข
    assert _player(db, 1)["inv"].count("30") == 2, "ลงขายไม่สำเร็จ ของต้องอยู่ครบ"


def test_listing_slot_limit(db):
    market.list_item(1, "30", 1000)
    market.list_item(1, "30", 1000)
    ok, msg = market.list_item(1, "60", 1000)
    assert not ok and "สูงสุด 2" in msg


def test_buy_moves_money_and_item_exactly_once(db):
    market.list_item(1, "30", 10000)
    ok, msg = market.buy_listing(2, 1)
    assert ok and "ซื้อ" in msg

    buyer, seller = _player(db, 2), _player(db, 1)
    assert buyer["cash"] == 20000 - 10000 and buyer["inv"] == ["30"]
    assert seller["bank"] == 10000 - 500, "คนขายได้เงินเข้าธนาคาร หักค่าธรรมเนียม 5%"
    assert seller["cash"] == 50000, "เงินสดคนขายต้องไม่ถูกแตะ"


def test_double_buy_is_impossible(db):
    market.list_item(1, "30", 10000)
    assert market.buy_listing(2, 1)[0] is True
    ok, msg = market.buy_listing(2, 1)
    assert not ok and "ถูกซื้อ" in msg
    assert _player(db, 2)["cash"] == 10000, "ครั้งที่สองห้ามตัดเงินซ้ำ"
    assert _player(db, 2)["inv"] == ["30"], "และห้ามได้ของสองชิ้น"


def test_not_enough_cash_changes_nothing(db):
    market.list_item(1, "30", 999999)
    ok, msg = market.buy_listing(2, 1)
    assert not ok and "เงินสดไม่พอ" in msg
    assert _player(db, 2) == {"cash": 20000, "bank": 0, "inv": []}
    assert len(market.open_listings()) == 1, "ของต้องยังอยู่บนแผง"


def test_full_bag_blocks_the_buy(db):
    conn = sqlite3.connect(db)
    conn.execute("UPDATE players SET inventory = ?, capacity = 2 WHERE user_id = 2",
                 (json.dumps(["1", "2"]),))
    conn.commit()
    conn.close()
    market.list_item(1, "30", 1000)
    ok, msg = market.buy_listing(2, 1)
    assert not ok and "กระเป๋าเต็ม" in msg
    assert _player(db, 2)["cash"] == 20000


def test_cannot_buy_your_own_listing(db):
    market.list_item(1, "30", 1000)
    ok, msg = market.buy_listing(1, 1)
    assert not ok and "ของตัวเอง" in msg
    assert _player(db, 1)["cash"] == 50000


def test_cancel_returns_the_item(db):
    market.list_item(1, "30", 1000)
    before = len(_player(db, 1)["inv"])
    ok, msg = market.cancel_listing(1, 1)
    assert ok and "กลับเข้ากระเป๋า" in msg
    assert len(_player(db, 1)["inv"]) == before + 1
    assert market.open_listings() == []


def test_only_the_seller_can_cancel(db):
    market.list_item(1, "30", 1000)
    ok, msg = market.cancel_listing(2, 1)
    assert not ok and "ของตัวเอง" in msg
    assert len(market.open_listings()) == 1


def test_cannot_cancel_after_sold(db):
    market.list_item(1, "30", 1000)
    market.buy_listing(2, 1)
    ok, msg = market.cancel_listing(1, 1)
    assert not ok and "ปิดไปแล้ว" in msg
    assert _player(db, 1)["inv"].count("30") == 1, "ของขายไปแล้วห้ามงอกกลับมา"


def test_ten_people_click_buy_at_the_same_instant(db):
    """เคสที่ทำเงินหายจริงถ้าพลาด: หลายคนกดซื้อชิ้นเดียวกันพร้อมกัน
    ต้องมีคนได้ของคนเดียว และเงินต้องถูกตัดครั้งเดียวเท่านั้น"""
    import threading

    conn = sqlite3.connect(db)
    for uid in range(10, 20):
        conn.execute("INSERT INTO players VALUES (?, 50000, 0, ?, 10)", (uid, json.dumps([])))
    conn.commit()
    conn.close()

    market.list_item(1, "30", 10000)
    results, barrier = [], threading.Barrier(10)

    def buy(uid):
        barrier.wait()                       # ปล่อยพร้อมกันเป๊ะ
        results.append(market.buy_listing(uid, 1)[0])

    threads = [threading.Thread(target=buy, args=(uid,)) for uid in range(10, 20)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert results.count(True) == 1, f"ต้องสำเร็จคนเดียว แต่ได้ {results.count(True)} คน"
    winners = [uid for uid in range(10, 20) if _player(db, uid)["inv"] == ["30"]]
    assert len(winners) == 1
    assert _player(db, winners[0])["cash"] == 40000
    assert all(_player(db, uid)["cash"] == 50000 for uid in range(10, 20) if uid != winners[0]), \
        "คนที่ซื้อไม่ทันห้ามโดนตัดเงิน"
    assert _player(db, 1)["bank"] == 9500, "คนขายได้เงินก้อนเดียว"


def test_nothing_survives_a_missing_listing(db):
    assert market.buy_listing(2, 999)[0] is False
    assert market.cancel_listing(1, 999)[0] is False
