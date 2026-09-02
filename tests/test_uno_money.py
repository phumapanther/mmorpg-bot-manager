"""💰 UNO เดิมพัน — ทองรวมในระบบต้องเท่าเดิมเป๊ะทุกกรณี

เจ้าของเกมเคาะ (09-02): เล่นกับบอทไม่ได้เงิน · ที่ 1 กินเรียบ · ออกกลางคันเสียเงิน
"""
import pytest

from bot.cards import uno_room


class _Wallet(dict):
    """dict ธรรมดา + total() — เก็บของเดิมจาก brief ไว้ แค่ให้ตั้ง attribute ได้"""

    def total(self):
        return sum(self.values())


@pytest.fixture(autouse=True)
def db(tmp_path, monkeypatch):
    import sqlite3

    from license_server import web_db

    path = tmp_path / "web.db"

    def _connect():
        conn = sqlite3.connect(str(path), timeout=5)
        conn.row_factory = sqlite3.Row
        conn.executescript(web_db._SCHEMA)
        return conn

    monkeypatch.setattr(web_db, "connect", _connect)
    yield


@pytest.fixture
def wallet(monkeypatch):
    """กระเป๋าเงินปลอม — นับยอดรวมได้ง่าย ไม่แตะฐานข้อมูลจริง"""
    money = _Wallet()

    def get_player(uid):
        return {"cash": money.get(str(uid), 0)}

    def inc(uid, field, amount=1):
        assert field == "cash"
        money[str(uid)] = money.get(str(uid), 0) + amount
        assert money[str(uid)] >= 0, "เงินติดลบ = บั๊ก"
        return True

    from bot.models import player_model
    monkeypatch.setattr(player_model, "get_player", get_player)
    monkeypatch.setattr(player_model, "increment_player_field", inc)
    return money


def test_เข้าโต๊ะหักเงินทันที(wallet):
    wallet["1"] = 5000
    ok, _ = uno_room.open_table(1, "เอ", 1000)
    assert ok
    assert wallet["1"] == 4000


def test_เงินไม่พอเข้าโต๊ะไม่ได้(wallet):
    wallet["1"] = 500
    ok, got = uno_room.open_table(1, "เอ", 1000)
    assert not ok and "ไม่พอ" in got["error"]
    assert wallet["1"] == 500, "เข้าไม่ได้ต้องไม่หักเงิน"


def test_ทองรวมไม่เปลี่ยนตลอดเกม(wallet):
    """กฎเหล็ก — เงินย้ายมือ ไม่งอก ไม่หาย"""
    wallet["1"] = 5000
    wallet["2"] = 5000
    before = sum(wallet.values())

    ok, st = uno_room.open_table(1, "เอ", 1000)
    assert ok
    assert uno_room.sit(2, "บี", st["room"])[0]
    assert sum(wallet.values()) + 2000 == before, "เงินเข้ากองกลางแล้ว"

    uno_room.begin(1)
    uno_room._payout(uno_room._room(1), "1")      # จบเกม เอชนะ
    assert sum(wallet.values()) == before, "ทองรวมต้องเท่าเดิมเป๊ะ"


def test_ที่หนึ่งกินเรียบ(wallet):
    wallet["1"] = 5000
    wallet["2"] = 5000
    _, st = uno_room.open_table(1, "เอ", 1000)
    uno_room.sit(2, "บี", st["room"])
    uno_room.begin(1)
    uno_room._payout(uno_room._room(1), "1")
    assert wallet["1"] == 6000      # 4000 + กองกลาง 2000
    assert wallet["2"] == 4000


def test_ยุบโต๊ะก่อนเริ่มคืนเงินครบ(wallet):
    wallet["1"] = 5000
    wallet["2"] = 5000
    _, st = uno_room.open_table(1, "เอ", 1000)
    uno_room.sit(2, "บี", st["room"])
    uno_room.stand(2)
    uno_room.stand(1)
    assert wallet["1"] == 5000 and wallet["2"] == 5000, "ยังไม่เล่นต้องคืนครบ"


def test_ออกกลางเกมเสียเงิน(wallet):
    wallet["1"] = 5000
    wallet["2"] = 5000
    before = sum(wallet.values())
    _, st = uno_room.open_table(1, "เอ", 1000)
    uno_room.sit(2, "บี", st["room"])
    uno_room.begin(1)
    uno_room.stand(2)                    # บีหนีกลางเกม
    assert wallet["2"] == 4000, "ออกกลางเกมไม่คืนเงิน"
    uno_room._payout(uno_room._room(1), "1")
    assert wallet["1"] == 6000, "เอได้กองกลางทั้งหมด"
    assert sum(wallet.values()) == before


def test_จ่ายรางวัลซ้ำไม่ได้(wallet):
    """เน็ตกระตุกแล้วเบราว์เซอร์ยิงซ้ำ ห้ามได้เงินสองรอบ"""
    wallet["1"] = 5000
    wallet["2"] = 5000
    before = sum(wallet.values())
    _, st = uno_room.open_table(1, "เอ", 1000)
    uno_room.sit(2, "บี", st["room"])
    uno_room.begin(1)
    room = uno_room._room(1)
    uno_room._payout(room, "1")
    uno_room._payout(room, "1")
    uno_room._payout(room, "1")
    assert sum(wallet.values()) == before
    assert wallet["1"] == 6000, "จ่ายได้ครั้งเดียว"


def test_คนเดียวเริ่มเกมไม่ได้(wallet):
    wallet["1"] = 5000
    uno_room.open_table(1, "เอ", 1000)
    ok, got = uno_room.begin(1)
    assert not ok and "2 คน" in got["error"]


def test_เดิมพันติดลบไม่ได้(wallet):
    wallet["1"] = 5000
    assert not uno_room.open_table(1, "เอ", -100)[0]
    assert wallet["1"] == 5000


def test_เล่นซ้ำ_20_รอบทองรวมนิ่ง(wallet):
    """ฟอกทองไม่ได้ — เล่นกี่รอบยอดรวมก็เท่าเดิม"""
    wallet["1"] = 50000
    wallet["2"] = 50000
    before = sum(wallet.values())
    for i in range(20):
        _, st = uno_room.open_table(1, "เอ", 1000)
        uno_room.sit(2, "บี", st["room"])
        uno_room.begin(1)
        uno_room._payout(uno_room._room(1), "1" if i % 2 else "2")
        uno_room.stand(1)
        uno_room.stand(2)
    assert sum(wallet.values()) == before, "เล่น 20 รอบทองรวมต้องนิ่งสนิท"


def got_cards(v):
    """ดึงไพ่ทุกใบที่โผล่ในคำตอบของ view() — ไม่ว่าซ่อนอยู่ชั้นไหน

    ยกเว้นคีย์ "top" (ไพ่บนสุดกอง) — เป็นข้อมูลสาธารณะจริงตามกติกา
    ทุกคนเห็นบนโต๊ะอยู่แล้ว ไม่นับเป็น "ไพ่หลุด"
    """
    out = []
    def walk(x):
        if isinstance(x, dict):
            if "suit" in x and "value" in x:
                out.append(x)
            for k, v in x.items():
                if k != "top":
                    walk(v)
        elif isinstance(x, list):
            for v in x:
                walk(v)
    walk(v)
    return out


def test_view_ไม่หลุดไพ่คนอื่น(wallet):
    """🔒 ประตูเดียว — ไพ่ในมือคนอื่นห้ามหลุดลงเบราว์เซอร์แม้ใบเดียว"""
    wallet["1"] = 5000
    wallet["2"] = 5000
    _, st = uno_room.open_table(1, "เอ", 1000)
    uno_room.sit(2, "บี", st["room"])
    uno_room.begin(1)
    room = uno_room._room(1)
    # โครงจริงของ uno_engine: players[i]["hand"] — แต่ละใบเป็น dict ไม่ใช่ข้อความ
    game = room["extra"]["game"]
    seats = [s["uid"] for s in room["seats"]]
    others = [c for i, p in enumerate(game["players"])
              if seats[i] != "1" for c in p["hand"]]
    # ไพ่หนึ่งใบ = {"suit": ..., "value": ...} — นับจำนวนใบที่หลุดแทนเทียบข้อความ
    # (ไพ่ซ้ำกันได้ เทียบตรง ๆ จะฟ้องผิดเวลาไพ่ในมือเราชนกับของคนอื่น)
    import collections
    sent = collections.Counter(
        (c["suit"], c["value"]) for c in got_cards(uno_room.view(1)))
    mine = collections.Counter(
        (c["suit"], c["value"]) for c in game["players"][seats.index("1")]["hand"])
    assert sent == mine, "ส่งไพ่เกินมือตัวเอง = ไพ่คนอื่นหลุด"
    # เทสนี้ต้องมีไพ่คนอื่นให้เทียบ ไม่งั้นเทสเปล่า (ไม่ได้ยืนยันอะไรจริง)
    assert len(others) > 0, "เทสนี้ต้องมีไพ่คนอื่นให้เทียบ ไม่งั้นเทสเปล่า"
    # ไพ่บนสุดกองเป็นข้อมูลสาธารณะ — ต้องส่งจริง ตรงกับใบบนสุดของกองจริง
    top = uno_room.view(1)["top"]
    real_top = game["pile"][-1]
    assert (top["suit"], top["value"]) == (real_top["suit"], real_top["value"])


def test_ทุกคน_stand_กลางเกมทองรวมไม่หาย(wallet):
    """🐛 บั๊กที่เจอ: คนสุดท้ายออกกลางเกม → ห้องถูกลบทิ้งพร้อม pot ที่ยังไม่จ่าย

    เริ่มเกมแล้วทุกคนทยอยหนีจนห้องว่าง — ทองรวมต้องเท่าเดิมเป๊ะ
    (คนสุดท้ายที่เหลืออยู่คนเดียวไม่มีคู่แข่งแล้ว ต้องได้ pot ไปก่อนห้องถูกลบ)
    """
    wallet["1"] = 5000
    wallet["2"] = 5000
    before = sum(wallet.values())
    _, st = uno_room.open_table(1, "เอ", 1000)
    uno_room.sit(2, "บี", st["room"])
    uno_room.begin(1)
    uno_room.stand(1)      # เอาหนีก่อน — ไม่คืนเงิน (เริ่มเกมแล้ว)
    uno_room.stand(2)      # บีคือคนสุดท้าย ต้องได้ pot ไปแทนที่จะหายไปกับห้อง
    assert sum(wallet.values()) == before, "ทองรวมต้องเท่าเดิมเป๊ะ แม้ทุกคนหนีหมด"
