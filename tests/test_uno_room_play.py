"""🎴 UNO ห้องเดิมพัน — เล่นไพ่ต่อได้จริง (play/draw/passes/say_uno/take_stack)

งานที่ 6: งานที่ 3 ทำห้องไว้แค่หักเงิน+แจกไพ่ แต่เล่นไพ่ต่อไม่ได้
กติกาเหล็กที่ต้องกันให้แน่น: คนที่ไม่ใช่เจ้าของตาปัจจุบันสั่งอะไรไม่ได้
"""
import collections
import sqlite3
import time

import pytest

from bot.cards import uno_room


class _Wallet(dict):
    def total(self):
        return sum(self.values())


@pytest.fixture(autouse=True)
def db(tmp_path, monkeypatch):
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


def _open_2p(wallet, bet=0):
    """เปิดโต๊ะ 2 คนแล้วเริ่มเกม — คืน (code, room หลังเริ่ม)"""
    wallet["1"] = 5000
    wallet["2"] = 5000
    _, st = uno_room.open_table(1, "เอ", bet)
    uno_room.sit(2, "บี", st["room"])
    uno_room.begin(1)
    return st["room"]


def got_cards(v):
    """ดึงไพ่ทุกใบในคำตอบของ view() — ไม่นับ "top" (ข้อมูลสาธารณะบนโต๊ะจริง)"""
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


# ── กติกาลำดับตา ──

def test_คนที่ยังไม่ถึงตาลงไพ่ไม่ได้(wallet):
    code = _open_2p(wallet)
    room = uno_room._room(1)
    game = room["extra"]["game"]
    turn_uid = room["seats"][game["turn"]]["uid"]
    other_uid = "2" if turn_uid == "1" else "1"
    ok, r = uno_room.play(other_uid, 0)
    assert not ok and "ตา" in r["error"]


def test_คนที่ถึงตาลงไพ่ได้แล้วตาเลื่อน(wallet):
    code = _open_2p(wallet)
    room = uno_room._room(1)
    game = room["extra"]["game"]
    turn_uid = room["seats"][game["turn"]]["uid"]
    me_idx = game["turn"]
    hand = game["players"][me_idx]["hand"]

    from bot.cards import uno_engine as E
    playable = [i for i, c in enumerate(hand) if c in E.playable_now(game, me_idx)]
    if not playable:
        # ไม่มีไพ่วางได้ — จั่วก่อนเพื่อยืนยันว่าตาเลื่อน/สถานะเปลี่ยนแทน
        ok, r = uno_room.draw(turn_uid)
        assert ok
        return
    idx = playable[0]
    suit = None
    if hand[idx]["suit"] is None:      # ไวลด์ — ต้องเลือกสีก่อนวาง ไม่งั้น engine ปฏิเสธ
        rest = [c["suit"] for j, c in enumerate(hand) if j != idx and c["suit"]]
        suit = rest[0] if rest else "fire"
    played_card = hand[idx]
    ok, r = uno_room.play(turn_uid, idx, suit=suit)
    assert ok, r
    assert "table" in r
    room2 = uno_room._room(1)
    game2 = room2["extra"]["game"]
    # 🛡️🌀 ข้ามตา/ย้อนทาง กับผู้เล่น 2 คน = วนกลับมาที่คนเดิม (กติกาจริง ไม่ใช่บั๊ก)
    #    กรณีอื่นทั้งหมดตาต้องเลื่อนไปคนถัดไปเสมอ ไม่ก็เกมจบไปแล้ว
    if played_card["value"] in ("skip", "reverse"):
        assert game2["turn"] == me_idx or game2.get("over")
    else:
        assert game2["turn"] != me_idx or game2.get("over")


def test_คนนอกห้องยิงคำสั่งเข้ามาไม่ได้(wallet):
    _open_2p(wallet)
    ok, r = uno_room.play(999, 0)
    assert not ok and "error" in r


def test_เกมยังไม่เริ่มสั่งอะไรไม่ได้(wallet):
    wallet["1"] = 5000
    wallet["2"] = 5000
    _, st = uno_room.open_table(1, "เอ", 0)
    uno_room.sit(2, "บี", st["room"])
    ok, r = uno_room.play(1, 0)
    assert not ok and "error" in r


def test_เกมจบแล้วสั่งอะไรไม่ได้(wallet):
    code = _open_2p(wallet)
    room = uno_room._room(1)
    room["extra"]["game"]["over"] = True
    from bot import lobby
    lobby.save(room["room"], room)
    ok, r = uno_room.play(1, 0)
    assert not ok and "error" in r
    ok, r = uno_room.draw(1)
    assert not ok
    ok, r = uno_room.take_stack(1)
    assert not ok
    ok, r = uno_room.passes(1)
    assert not ok


# ── ความลับไพ่ ──

def test_view_เห็นไพ่ตัวเองครบไม่เห็นคนอื่น(wallet):
    _open_2p(wallet)
    room = uno_room._room(1)
    game = room["extra"]["game"]
    seats = [s["uid"] for s in room["seats"]]
    me = seats.index("1")

    sent = collections.Counter((c["suit"], c["value"]) for c in got_cards(uno_room.view(1)))
    mine = collections.Counter((c["suit"], c["value"]) for c in game["players"][me]["hand"])
    assert sent == mine, "ส่งไพ่เกินมือตัวเอง = ไพ่คนอื่นหลุด"

    others = [c for i, p in enumerate(game["players"]) if seats[i] != "1" for c in p["hand"]]
    assert len(others) > 0, "เทสนี้ต้องมีไพ่คนอื่นให้เทียบ ไม่งั้นเทสเปล่า"


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


def test_http_ไม่หลุดไพ่คนอื่นตอนเล่น(web):
    """🔒 ผ่าน HTTP จริง — เรียก endpoint ด้วย TestClient"""
    alice = web(4001)
    bob = web(4002)

    d = alice.post("/api/web/uno/room", json={"action": "create", "bet": 0}).json()
    code = d["code"]
    bob.post("/api/web/uno/room", json={"action": "join", "code": code})
    alice.post("/api/web/uno/room", json={"action": "start"})

    view = alice.get("/api/web/uno/room").json()
    found = got_cards(view)
    for seat in view.get("seats", []):
        if not seat.get("you"):
            assert "hand" not in seat, "ส่งไพ่ของผู้เล่นคนอื่นลง HTTP จริง"
    assert len(found) > 0, "เทสนี้ต้องมีไพ่ให้เทียบ ไม่งั้นเทสเปล่า"
    # นับใบให้แน่ชัดจากสถานะจริงในเซิร์ฟเวอร์ — ไม่ใช้ view["hand"] มาเทียบเอง
    # (ถ้า view() รั่วยัดไพ่ทุกคนลงมาทั้ง out["hand"] และที่อื่น ๆ เทียบกับตัวเองจะผ่านหลอกได้)
    from bot.cards import uno_room as UR
    room = UR._room(4001)
    my_hand_len = len(room["extra"]["game"]["players"][0]["hand"]) \
        if room["seats"][0]["uid"] == "4001" else len(room["extra"]["game"]["players"][1]["hand"])
    assert len(found) == my_hand_len, "จำนวนไพ่ที่ส่งมาต้องเท่ากับมือของอลิซเท่านั้น — เกินนี้คือไพ่คนอื่นหลุด"

    # คนที่ยังไม่ถึงตายิง play ผ่าน HTTP ต้องโดนปฏิเสธ (400)
    from bot.cards import uno_room as UR
    room = UR._room(4001)
    game = room["extra"]["game"]
    turn_uid = room["seats"][game["turn"]]["uid"]
    other = bob if turn_uid == "4001" else alice
    r = other.post("/api/web/uno/room", json={"action": "play", "index": 0})
    assert r.status_code == 400


# ── เงิน ──

def test_เล่นจนจบเกมจริงผู้ชนะได้กองกลางทองรวมเท่าเดิม(wallet):
    wallet["1"] = 5000
    wallet["2"] = 5000
    before = wallet.total()
    code = _open_2p(wallet, bet=1000)
    room = uno_room._room(1)
    game = room["extra"]["game"]

    from bot.cards import uno_engine as E
    import random
    rng = random.Random(42)

    def _play_best(turn_uid, turn_idx, hand, game):
        """เลือกไพ่ที่วางได้ วางไว — ไวลด์ให้เลือกสีจากใบแรกในมือกันค้าง"""
        playable = [i for i, c in enumerate(hand) if c in E.playable_now(game, turn_idx)]
        if not playable:
            return False
        idx = playable[0]
        card = hand[idx]
        suit = None
        if card["suit"] is None:      # ไวลด์ — ต้องเลือกสีเอง ไม่งั้น engine ปฏิเสธ
            rest = [c["suit"] for j, c in enumerate(hand) if j != idx and c["suit"]]
            suit = rest[0] if rest else "fire"
        ok, r = uno_room.play(turn_uid, idx, suit=suit, rng=rng)
        assert ok, r
        return True

    guard = 0
    while not game.get("over") and guard < 500:
        guard += 1
        turn_idx = game["turn"]
        turn_uid = room["seats"][turn_idx]["uid"]
        hand = game["players"][turn_idx]["hand"]
        if _play_best(turn_uid, turn_idx, hand, game):
            pass
        elif game["stack"]:
            ok, r = uno_room.take_stack(turn_uid, rng=rng)
            assert ok, r
        else:
            ok, r = uno_room.draw(turn_uid, rng=rng)
            assert ok, r
            if r.get("playable"):
                room2 = uno_room._room(1)
                g2 = room2["extra"]["game"]
                h2 = g2["players"][turn_idx]["hand"]
                _play_best(turn_uid, turn_idx, h2, g2)
        room = uno_room._room(1)
        game = room["extra"]["game"]

    assert game.get("over"), "เกมต้องจบได้จริงภายในจำนวนตาที่กันไว้"
    assert wallet.total() == before, "ทองรวมต้องเท่าเดิมเป๊ะ"
    winner_uid = room["seats"][game["winner"]]["uid"]
    assert wallet[winner_uid] == 5000 - 1000 + 2000, "ผู้ชนะต้องได้กองกลางไปครบ"


def test_เล่นจบแล้วยิงซ้ำไม่ได้เงินเพิ่ม(wallet):
    code = _open_2p(wallet, bet=1000)
    room = uno_room._room(1)
    room["extra"]["game"]["over"] = True
    room["extra"]["game"]["winner"] = 0
    from bot import lobby
    lobby.save(room["room"], room)
    uno_room._payout(uno_room._room(1), room["seats"][0]["uid"])
    total_after_first = wallet.total()
    win_uid = room["seats"][0]["uid"]
    before_win = wallet[win_uid]

    ok, r = uno_room.play(win_uid, 0)
    assert not ok
    assert wallet[win_uid] == before_win
    assert wallet.total() == total_after_first
