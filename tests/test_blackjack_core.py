"""แบล็กแจ็ค 24 กลาง — เกมหลายเทิร์นที่เก็บสถานะใน DB (เล่นข้ามดิส/เว็บได้)"""
import random

import pytest

import bot.models.player_model as pm
from bot import blackjack_core as bj
from bot import config_loader


@pytest.fixture
def db(tmp_path, monkeypatch):
    monkeypatch.setattr(pm, "DB_NAME", str(tmp_path / "bj.db"))
    monkeypatch.setattr(config_loader, "get_balance", lambda k, d=None: d)
    pm.init_db()
    pm.get_player(1)
    pm.update_player_fields(1, {"cash": 1_000_000})
    return pm


# ── เรทตุกติก (เท่าเดิมกับที่ตกลงไว้) ──

@pytest.mark.parametrize("bet,expect", [
    (150_000, .90), (100_000, .90), (99_999, .70), (10_000, .70),
    (9_999, .60), (1_000, .60), (999, 0.0),
])
def test_rig_chance_tiers(db, bet, expect):
    assert bj.rig_chance_for(bet) == pytest.approx(expect)


def test_stacked_hand_never_busts_and_never_loses(db):
    rng = random.Random(24)
    for _ in range(300):
        deck = bj.new_deck(rng)
        hand = [deck.pop(), deck.pop()]
        p = rng.randint(4, 24)
        bj.stack_bot_hand(deck, hand, p)
        b = bj.score(hand)
        assert b <= 24
        assert b > p or b == 24


# ── วงจรเกม ──

def test_start_deducts_bet_and_hides_dealer_card(db):
    ok, v = bj.start(1, 1000, rng=random.Random(1))
    assert ok
    assert pm.get_player(1)["cash"] == 999_000
    assert len(v["player"]) == 2 and v["bot"][1] == ["?", 0] and v["bot_score"] is None
    assert v["over"] is False


def test_cannot_open_two_tables(db):
    bj.start(1, 1000, rng=random.Random(1))
    ok, out = bj.start(1, 1000)
    assert not ok and "ค้างอยู่" in out["message"]


def test_cannot_bet_more_than_cash(db):
    pm.update_player_fields(1, {"cash": 100})
    ok, out = bj.start(1, 1000)
    assert not ok and pm.get_player(1)["cash"] == 100


def test_hit_until_bust_ends_the_game(db):
    bj.start(1, 1000, rng=random.Random(3))
    for _ in range(30):
        ok, out = bj.hit(1)
        assert ok
        if out.get("result") == "bust":
            assert out["net"] == -1000 and out["over"] is True
            assert bj.load_game(1) is None, "แตกแล้วต้องล้างโต๊ะทิ้ง"
            return
    pytest.fail("จั่วรัวแล้วต้องแตกสักที")


def test_stand_resolves_and_pays(db):
    bj.start(1, 1000, rng=random.Random(5))
    ok, out = bj.stand(1)
    assert ok and out["result"] in ("win", "lose", "draw")
    assert out["over"] is True and out["bot_score"] is not None   # เปิดไพ่บอทหมดแล้ว
    expect = {"win": 1000, "draw": 0, "lose": -1000}[out["result"]]
    assert out["net"] == expect
    assert pm.get_player(1)["cash"] == 999_000 + out["winnings"]
    assert bj.load_game(1) is None


def test_actions_need_an_open_table(db):
    assert bj.hit(1)[0] is False
    assert bj.stand(1)[0] is False


def test_game_survives_across_calls(db):
    """หัวใจของการเล่นข้ามแพลตฟอร์ม — สถานะอยู่ใน DB ไม่ใช่ในหน่วยความจำ"""
    bj.start(1, 1000, rng=random.Random(9))
    before = bj.load_game(1)
    ok, v = bj.hit(1)
    assert ok
    after = bj.load_game(1)
    if after:                                    # ยังไม่แตก
        assert len(after["player"]) == len(before["player"]) + 1
        assert after["bet"] == 1000


def test_stale_table_is_dropped(db, monkeypatch):
    bj.start(1, 1000, rng=random.Random(2))
    monkeypatch.setattr(bj.time, "time", lambda: 10 ** 12)   # กระโดดไปอนาคตไกลๆ
    assert bj.load_game(1) is None
