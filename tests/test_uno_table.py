"""🎰 โต๊ะไพ่รูน — ที่เก็บเกม + ประตูเดียวก่อนส่งขึ้นเว็บ

เทสที่สำคัญที่สุดในไฟล์นี้คือ "ไพ่คนอื่นต้องไม่รั่วลงเบราว์เซอร์"
ส่งลงไปเมื่อไหร่ = เปิด F12 อ่านไพ่คู่แข่งได้หมด เกมจบเลย
"""
import collections
import json
import random

import pytest

import bot.models.player_model as pm
from bot.cards import uno_bot as B
from bot.cards import uno_deck as D
from bot.cards import uno_engine as E
from bot.cards import uno_table as T

UID = 7701


@pytest.fixture
def world(tmp_path, monkeypatch):
    monkeypatch.setattr(pm, "DB_NAME", str(tmp_path / "g.db"))
    pm.init_db()
    pm.get_player(UID)
    return None


def c(suit, value):
    return D.card(suit, value)


# ── 🔒 ไพ่คนอื่นต้องไม่รั่ว ──

def test_the_browser_never_sees_another_players_hand(world):
    """ทั้งก้อนที่ส่งขึ้นเว็บต้องไม่มีไพ่ของใครนอกจากเรา"""
    T.start(UID, bots=3, rng=random.Random(1))
    st = T.load(UID)
    v = T.view(UID)

    # นับไพ่ทุกใบที่ view ส่งออกไป เทียบกับที่ "ควรเห็นได้"
    # ⚠️ เทียบทีละใบตรง ๆ ไม่ได้ เพราะสำรับมีไพ่ซ้ำกัน (สีละ 2 ใบ)
    #    เจอไพ่หน้าเหมือนกันไม่ได้แปลว่ารั่ว — ต้องดูว่า "ส่งไปกี่ใบ"
    sent = collections.Counter()

    def count(x):
        if isinstance(x, dict):
            if set(x) == {"suit", "value"}:
                sent[(x["suit"], x["value"])] += 1
            else:
                for val in x.values():
                    count(val)
        elif isinstance(x, list):
            for item in x:
                count(item)

    count(v)
    allowed = collections.Counter(
        (card["suit"], card["value"]) for card in st["players"][st["human"]]["hand"])
    allowed[(v["top"]["suit"], v["top"]["value"])] += 1   # ไพ่บนกองทิ้งทุกคนเห็นอยู่แล้ว

    for key, n in sent.items():
        assert n <= allowed[key], \
            f"ส่งไพ่ {key} ไป {n} ใบ แต่ควรเห็นได้แค่ {allowed[key]} — ไพ่คนอื่นรั่ว"


def test_the_browser_never_sees_the_draw_pile(world):
    """รู้ลำดับกองจั่ว = รู้ล่วงหน้าว่าจะจั่วได้อะไร"""
    T.start(UID, rng=random.Random(1))
    v = T.view(UID)
    assert "deck" not in v
    assert isinstance(v["deck_left"], int), "ต้องบอกแค่จำนวนที่เหลือ"


def test_other_players_show_only_a_card_count(world):
    T.start(UID, bots=2, rng=random.Random(1))
    v = T.view(UID)
    for p in v["players"]:
        assert set(p) == {"name", "cards", "you", "said_uno"}, \
            f"ส่งข้อมูลเกินจำเป็น: {sorted(p)}"
        assert isinstance(p["cards"], int)


def test_you_do_see_your_own_hand(world):
    """ซ่อนคนอื่นได้ แต่ต้องไม่ซ่อนของตัวเองด้วย ไม่งั้นเล่นไม่ได้"""
    T.start(UID, rng=random.Random(1))
    assert len(T.view(UID)["hand"]) == E.START_CARDS == 7


# ── เปิดโต๊ะ / เก็บสถานะ ──

def test_starting_deals_a_table(world):
    T.start(UID, rng=random.Random(1))
    v = T.view(UID)
    assert v["playing"] and len(v["players"]) == 2


def test_the_table_survives_between_requests(world):
    """ปิดหน้าเว็บแล้วเปิดใหม่ต้องเจอโต๊ะเดิม ไม่ใช่เกมหาย"""
    T.start(UID, rng=random.Random(1))
    hand = T.view(UID)["hand"]
    assert T.view(UID)["hand"] == hand


def test_no_table_says_so(world):
    assert T.view(UID) == {"playing": False}


def test_clearing_removes_the_table(world):
    T.start(UID, rng=random.Random(1))
    T.clear(UID)
    assert T.load(UID) is None


def test_you_can_sit_with_several_bots(world):
    T.start(UID, bots=3, rng=random.Random(1))
    assert len(T.view(UID)["players"]) == 4


def test_the_table_never_grows_past_six(world):
    T.start(UID, bots=99, rng=random.Random(1))
    assert len(T.view(UID)["players"]) <= E.MAX_PLAYERS == 6


def test_there_is_always_at_least_one_bot(world):
    """ไม่มีบอท = นั่งคนเดียวไม่มีใครเล่นด้วย"""
    T.start(UID, bots=0, rng=random.Random(1))
    assert len(T.view(UID)["players"]) >= 2


# ── เล่นจริง ──

def test_you_cannot_move_before_opening_a_table(world):
    ok, r = T.draw(UID)
    assert not ok and "เปิดโต๊ะ" in r["error"]


def test_playing_an_illegal_card_is_refused(world):
    T.start(UID, rng=random.Random(1))
    st = T.load(UID)
    st["players"][0]["hand"] = [c("water", 9)]
    st["pile"] = [c("fire", 2)]
    st["suit"] = "fire"
    st["turn"] = 0
    T.save(UID, st)
    ok, r = T.play(UID, 0)
    assert not ok and "วางไม่ได้" in r["error"]


def test_playing_a_legal_card_works_and_the_bot_answers(world):
    """วางเสร็จแล้วบอทต้องเล่นต่อในคำขอเดียว ไม่ต้องให้เว็บถามซ้ำ"""
    T.start(UID, rng=random.Random(1))
    st = T.load(UID)
    st["players"][0]["hand"] = [c("fire", 5), c("wood", 3)]
    st["pile"] = [c("fire", 2)]
    st["suit"] = "fire"
    st["turn"] = 0
    T.save(UID, st)
    ok, r = T.play(UID, 0, rng=random.Random(1))
    assert ok
    assert r["table"]["my_turn"] or r["table"]["winner"] is not None, \
        "บอทไม่ได้เล่นต่อ ตาค้างอยู่ที่บอท"


def test_you_cannot_play_out_of_turn(world):
    T.start(UID, rng=random.Random(1))
    st = T.load(UID)
    st["turn"] = 1                       # ตาบอท
    T.save(UID, st)
    ok, r = T.play(UID, 0)
    assert not ok and "ยังไม่ถึงตาคุณ" in r["error"]


def test_a_finished_table_takes_no_more_moves(world):
    T.start(UID, rng=random.Random(1))
    st = T.load(UID)
    st["winner"] = 0
    st["over"] = True                 # จบจริงตอนเหลือคนเดียว ไม่ใช่ตอนมีคนชนะ
    T.save(UID, st)
    ok, r = T.draw(UID)
    assert not ok and "จบแล้ว" in r["error"]


def test_the_web_is_told_which_cards_are_playable(world):
    """หน้าเว็บต้องหรี่ไพ่ที่วางไม่ได้ — ไม่งั้นลากแล้วเด้งกลับโดยไม่รู้ทำไม"""
    T.start(UID, rng=random.Random(1))
    st = T.load(UID)
    st["players"][0]["hand"] = [c("fire", 5), c("water", 9), c(None, D.WILD)]
    st["pile"] = [c("fire", 2)]
    st["suit"] = "fire"
    st["turn"] = 0
    T.save(UID, st)
    assert T.view(UID)["playable"] == [0, 2], "บอกไพ่ที่วางได้ผิด"


def test_nothing_is_playable_when_it_is_not_your_turn(world):
    T.start(UID, rng=random.Random(1))
    st = T.load(UID)
    st["turn"] = 1
    T.save(UID, st)
    assert T.view(UID)["playable"] == []


# ── สแตค ──

def test_a_pending_stack_is_shown_to_the_player(world):
    T.start(UID, rng=random.Random(1))
    st = T.load(UID)
    st["turn"] = 0
    st["stack"] = 4
    st["stack_kind"] = D.WILD_DRAW_FOUR
    T.save(UID, st)
    v = T.view(UID)
    assert v["stack"] == 4 and v["must_answer"]


def test_you_can_give_in_and_take_the_stack(world):
    T.start(UID, rng=random.Random(1))
    st = T.load(UID)
    st["turn"] = 0
    st["stack"] = 2
    st["stack_kind"] = D.DRAW_TWO
    st["players"][0]["hand"] = [c("wood", 3)]
    T.save(UID, st)
    before = len(T.view(UID)["hand"])
    ok, _ = T.take_stack(UID, rng=random.Random(1))
    assert ok
    assert len(T.load(UID)["players"][0]["hand"]) == before + 2


# ── เล่นจนจบผ่านชั้นโต๊ะ ──

def test_a_whole_table_game_can_be_finished(world):
    """เล่นผ่านชั้นโต๊ะจนจบ — จับเกมค้างที่เทสรายข้อมองไม่เห็น"""
    for seed in range(6):
        T.clear(UID)
        T.start(UID, rng=random.Random(seed))
        rng = random.Random(seed)
        for _ in range(500):
            v = T.view(UID)
            if v["winner"] is not None:
                break
            if not v["my_turn"]:
                break                       # บอทค้าง = ผิดตั้งแต่ _run_bots
            if v["must_answer"]:
                if v["playable"]:
                    T.play(UID, v["playable"][0], suit="fire", rng=rng)
                else:
                    T.take_stack(UID, rng)
                continue
            if v["playable"]:
                T.play(UID, v["playable"][0], suit="fire", rng=rng)
            else:
                ok, r = T.draw(UID, rng)
                if ok and T.view(UID)["my_turn"]:
                    T.passes(UID, rng)
        assert T.view(UID)["winner"] is not None, f"seed {seed}: เล่นไม่จบ"


def test_cards_stay_complete_through_the_table_layer(world):
    T.start(UID, bots=2, rng=random.Random(5))
    rng = random.Random(5)
    for _ in range(120):
        v = T.view(UID)
        if v["winner"] is not None or not v["my_turn"]:
            break
        if v["must_answer"] and not v["playable"]:
            T.take_stack(UID, rng)
        elif v["playable"]:
            T.play(UID, v["playable"][0], suit="fire", rng=rng)
        else:
            T.draw(UID, rng)
        st = T.load(UID)
        total = (sum(len(p["hand"]) for p in st["players"])
                 + len(st["deck"]) + len(st["pile"]))
        assert total == D.DECK_SIZE, f"ไพ่เพี้ยนเหลือ {total} ใบ"


def test_the_winner_is_announced_by_name(world):
    T.start(UID, rng=random.Random(1))
    st = T.load(UID)
    st["winner"] = 1
    T.save(UID, st)
    v = T.view(UID)
    assert v["winner_name"] == st["players"][1]["name"]


def test_two_players_keep_separate_tables(world, tmp_path, monkeypatch):
    """โต๊ะของแต่ละคนต้องแยกกัน ไม่ใช่ใช้ก้อนเดียวกันทั้งเซิร์ฟเวอร์"""
    pm.get_player(UID + 1)
    T.start(UID, rng=random.Random(1))
    T.start(UID + 1, rng=random.Random(2))
    assert T.view(UID)["hand"] != T.view(UID + 1)["hand"]


# ── 🏁 อันดับที่เข้าเส้นชัย (เจ้าของเกมสั่ง 08-29) ──

def test_finishing_first_does_not_end_a_three_player_game(world):
    """คนชนะนั่งดูเพื่อนเล่นต่อ จนเหลือ 2 คนสุดท้าย"""
    T.start(UID, bots=2, rng=random.Random(1))
    st = T.load(UID)
    E._finish(st, 1)
    T.save(UID, st)
    v = T.view(UID)
    assert not v["over"], "คนแรกหมดมือแล้วเกมจบเลย"
    assert v["finished"][0]["place"] == 1


def test_a_player_who_is_out_can_still_watch(world):
    """เราออกไปแล้วต้องยังเห็นสถานะโต๊ะ ไม่ใช่จอดับ"""
    T.start(UID, bots=2, rng=random.Random(1))
    st = T.load(UID)
    E._finish(st, st["human"])
    T.save(UID, st)
    v = T.view(UID)
    assert v["playing"] and v["my_place"] == 1
    assert not v["my_turn"], "ออกไปแล้วยังมีตาให้เล่นอีก"


def test_a_player_who_is_out_cannot_keep_playing(world):
    T.start(UID, bots=2, rng=random.Random(1))
    st = T.load(UID)
    E._finish(st, st["human"])
    st["turn"] = st["human"]
    T.save(UID, st)
    ok, r = T.draw(UID)
    assert not ok and "ทิ้งไพ่หมดแล้ว" in r["error"]


def test_the_last_player_left_is_added_to_the_order(world):
    """เหลือคนเดียว = จบ และคนนั้นต้องได้อันดับสุดท้าย ไม่ใช่ตกหล่น"""
    T.start(UID, bots=2, rng=random.Random(1))
    st = T.load(UID)
    E._finish(st, 1)
    E._finish(st, 2)
    T.save(UID, st)
    v = T.view(UID)
    assert v["over"]
    assert len(v["finished"]) == 3, "คนสุดท้ายไม่ได้อันดับ"
    assert v["finished"][2]["you"], "คนสุดท้ายควรเป็นเรา"


def test_the_game_always_reaches_a_full_ranking(world):
    """เล่นจริงจนจบ — ต้องได้อันดับครบทุกคนเสมอ ไม่ค้างกลางทาง"""
    for seed in range(8):
        T.clear(UID)
        T.start(UID, bots=2, rng=random.Random(seed))
        rng = random.Random(seed)
        for _ in range(500):
            v = T.view(UID)
            if v["over"] or not v["my_turn"]:
                break
            if v["must_answer"] and not v["playable"]:
                T.take_stack(UID, rng)
            elif v["playable"]:
                T.play(UID, v["playable"][0], suit="fire", rng=rng)
            else:
                ok, _ = T.draw(UID, rng)
                if ok and T.view(UID)["drew"]:
                    T.passes(UID, rng)
        v = T.view(UID)
        assert v["over"], f"seed {seed}: เกมค้าง ไม่จบ"
        assert len(v["finished"]) == 3, f"seed {seed}: อันดับไม่ครบ"
        assert [f["place"] for f in v["finished"]] == [1, 2, 3]
