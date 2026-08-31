"""🔄 ลำดับเทิร์นและการ์ดพิเศษ — ขั้น 3 ของศึกไพ่รูน

ลำดับเทิร์นผิด = เกมค้างหรือมีคนได้เล่นสองรอบโดยไม่มีใครทันสังเกต
เทสชุดนี้จึงจับ "ตาไปถึงใคร" ทุกกรณี ไม่ใช่แค่ดูว่าไม่ crash
"""
import random

import pytest

from bot.cards import uno_deck as D
from bot.cards import uno_engine as E


def c(suit, value):
    return D.card(suit, value)


def game(names=("ก", "ข", "ค"), seed=1, cards=7):
    return E.new_game(list(names), rng=random.Random(seed), start_cards=cards)


def rig(st, hand=None, top=None, suit=None, turn=0, spare=True):
    """จัดฉากให้เทสคุมสถานการณ์ได้แน่นอน แทนที่จะรอสุ่มให้ตรง

    ⚠️ แถมไพ่สำรองให้เสมอ (spare) — มือที่เหลือใบเดียวพอวางแล้วชนะทันที
       เกมจึงจบก่อนที่การ์ดพิเศษจะทำงาน เทสก็จะวัดอะไรไม่ได้เลย
    """
    st["turn"] = turn
    if hand is not None:
        st["players"][turn]["hand"] = list(hand) + ([c("wood", 0)] if spare else [])
    if top is not None:
        st["pile"] = [top]
        st["suit"] = suit or top["suit"]
    if suit:
        st["suit"] = suit
    return st


# ── เปิดโต๊ะ ──

def test_everyone_starts_with_seven_cards():
    st = game()
    for p in st["players"]:
        assert len(p["hand"]) == E.START_CARDS == 7


def test_no_card_is_lost_when_the_game_starts():
    """ไพ่ในมือ + กองจั่ว + กองทิ้ง ต้องรวมได้ 108 ใบเป๊ะ"""
    st = game()
    total = sum(len(p["hand"]) for p in st["players"]) + len(st["deck"]) + len(st["pile"])
    assert total == D.DECK_SIZE == 108


def test_the_game_never_opens_on_an_action_card():
    """เปิดมาเป็น +4 = ลงโทษคนแรกที่ยังไม่ได้ทำอะไร"""
    for seed in range(40):
        st = game(seed=seed)
        assert not D.is_action(E.top_card(st)), f"seed {seed} เปิดด้วยไพ่ท่าพิเศษ"


def test_a_table_needs_at_least_two_players():
    with pytest.raises(ValueError):
        E.new_game(["คนเดียว"])


def test_a_table_holds_no_more_than_six():
    with pytest.raises(ValueError):
        E.new_game([f"คน{i}" for i in range(7)])


# ── เดินตาปกติ ──

def test_playing_a_number_passes_the_turn_along():
    st = rig(game(), hand=[c("fire", 5)], top=c("fire", 2))
    E.play(st, 0)
    assert st["turn"] == 1


def test_skip_jumps_over_the_next_player():
    st = rig(game(), hand=[c("fire", D.SKIP)], top=c("fire", 2))
    E.play(st, 0)
    assert st["turn"] == 2, "ม่านสะกดไม่ได้ข้ามใคร"


def test_reverse_turns_the_order_around():
    st = rig(game(), hand=[c("fire", D.REVERSE)], top=c("fire", 2))
    E.play(st, 0)
    assert st["dir"] == -1
    assert st["turn"] == 2, "ย้อนทางแล้วต้องวนกลับไปคนก่อนหน้า"


def test_with_two_players_reverse_acts_like_skip():
    """2 คนย้อนทาง = กลับมาที่ตัวเอง ถ้าไม่ดักไว้จะเล่นต่อไม่รู้จบ"""
    st = rig(game(names=("ก", "ข")), hand=[c("fire", D.REVERSE)], top=c("fire", 2))
    E.play(st, 0)
    assert st["turn"] == 0, "2 คนแล้วย้อนทางต้องได้เล่นต่อ (เหมือนข้ามตา)"


def test_you_cannot_play_a_card_that_does_not_match():
    st = rig(game(), hand=[c("water", 9)], top=c("fire", 2))
    ok, r = E.play(st, 0)
    assert not ok and "วางไม่ได้" in r["error"]
    assert st["turn"] == 0, "วางไม่สำเร็จแล้วตาต้องไม่เดิน"


def test_you_cannot_play_a_card_you_do_not_have():
    st = rig(game(), hand=[c("fire", 5)], top=c("fire", 2))
    ok, r = E.play(st, 9)
    assert not ok and "ไม่มีไพ่ใบนั้น" in r["error"]


# ── ไวลด์และการเลือกสี ──

def test_a_wild_sets_the_colour_the_player_chose():
    st = rig(game(), hand=[c(None, D.WILD)], top=c("fire", 2))
    ok, _ = E.play(st, 0, chosen_suit="water")
    assert ok and st["suit"] == "water"


def test_a_wild_without_a_colour_is_refused():
    """ไม่เลือกสีแล้วปล่อยผ่าน = กองไม่มีสี เกมตันทันที"""
    st = rig(game(), hand=[c(None, D.WILD)], top=c("fire", 2))
    before = len(st["players"][0]["hand"])
    ok, r = E.play(st, 0)
    assert not ok and "เลือกสี" in r["error"]
    assert len(st["players"][0]["hand"]) == before, "วางไม่สำเร็จแต่ไพ่หายจากมือ"


def test_a_made_up_colour_is_refused_too():
    st = rig(game(), hand=[c(None, D.WILD)], top=c("fire", 2))
    ok, _ = E.play(st, 0, chosen_suit="rainbow")
    assert not ok


# ── 🔥 ระบบสแตค (บั๊กที่แก้จาก uno-engine2) ──

def test_a_draw_two_does_not_deal_cards_immediately():
    """ต้องตั้งกองค้างไว้ ไม่ใช่ยัดไพ่ให้ทันที — คนถัดไปมีสิทธิ์เลือก"""
    st = rig(game(), hand=[c("fire", D.DRAW_TWO)], top=c("fire", 2))
    before = len(st["players"][1]["hand"])
    E.play(st, 0)
    assert st["stack"] == 2
    assert len(st["players"][1]["hand"]) == before, "จั่วให้ทันทีโดยไม่ให้เลือก"
    assert st["turn"] == 1, "ตาต้องไปถึงคนที่โดนสแตค"


def test_the_next_player_may_choose_to_stack_instead_of_drawing():
    """หัวใจของการแก้บั๊ก: คนถัดไปเลือกเองว่าจะวางต่อ ไม่ใช่ถูกบังคับ"""
    st = rig(game(), hand=[c("fire", D.DRAW_TWO)], top=c("fire", 2))
    E.play(st, 0)
    st["players"][1]["hand"] = [c("water", D.DRAW_TWO), c("wood", 0)]
    ok, _ = E.play(st, 0)                      # คนที่ 1 วาง +2 ต่อ
    assert ok and st["stack"] == 4, "สแตคไม่สะสม"
    assert st["winner"] is None, "ยังไม่ควรมีใครชนะ"


def test_the_next_player_may_also_just_take_the_cards():
    """มี +2 อยู่ในมือแต่เลือกจั่วก็ต้องได้ — เก็บไพ่ไว้ใช้ทีหลัง"""
    st = rig(game(), hand=[c("fire", D.DRAW_TWO)], top=c("fire", 2))
    E.play(st, 0)
    st["players"][1]["hand"] = [c("water", D.DRAW_TWO)]
    before = len(st["players"][1]["hand"])
    ok, r = E.take_stack(st)
    assert ok and len(r["drew"]) == 2
    assert len(st["players"][1]["hand"]) == before + 2
    assert st["stack"] == 0 and st["turn"] == 2, "จั่วแล้วต้องอดเล่นและส่งตาต่อ"


def test_stacking_piles_the_penalty_onto_whoever_gives_up():
    """สแตค 3 ชั้นแล้วคนที่ยอมต้องจั่วรวดเดียวทั้งกอง"""
    st = rig(game(), hand=[c("fire", D.DRAW_TWO)], top=c("fire", 2))
    E.play(st, 0)
    for _ in range(2):
        # แถมใบสำรองด้วย — มือใบเดียวพอวางแล้วชนะ เกมจบก่อนสแตคจะครบ 3 ชั้น
        st["players"][st["turn"]]["hand"] = [c("water", D.DRAW_TWO), c("wood", 0)]
        E.play(st, 0)
    assert st["stack"] == 6
    ok, r = E.take_stack(st)
    assert ok and len(r["drew"]) == 6


def test_you_cannot_dodge_a_stack_with_an_ordinary_card():
    st = rig(game(), hand=[c("fire", D.DRAW_TWO)], top=c("fire", 2))
    E.play(st, 0)
    st["players"][1]["hand"] = [c("fire", 5)]
    ok, r = E.play(st, 0)
    assert not ok and "ยอมจั่ว" in r["error"]


def test_only_the_same_kind_can_stack():
    """+2 กับ +4 สแตครวมกันไม่ได้ (กติกาบ้านที่ชัดที่สุด)"""
    st = rig(game(), hand=[c("fire", D.DRAW_TWO)], top=c("fire", 2))
    E.play(st, 0)
    st["players"][1]["hand"] = [c(None, D.WILD_DRAW_FOUR)]
    ok, _ = E.play(st, 0, chosen_suit="water")
    assert not ok, "+4 ไม่ควรสแตคทับ +2 ได้"


def test_a_wild_draw_four_stacks_four_at_a_time():
    st = rig(game(), hand=[c(None, D.WILD_DRAW_FOUR)], top=c("fire", 2))
    E.play(st, 0, chosen_suit="wood")
    assert st["stack"] == 4 and st["suit"] == "wood"


def test_during_a_stack_only_stackable_cards_are_offered():
    """หน้าเว็บต้องหรี่ไพ่ที่วางไม่ได้ให้ถูกตอนโดนสแตค"""
    st = rig(game(), hand=[c("fire", D.DRAW_TWO)], top=c("fire", 2))
    E.play(st, 0)
    st["players"][1]["hand"] = [c("fire", 5), c("water", D.DRAW_TWO), c(None, D.WILD)]
    assert E.playable_now(st) == [c("water", D.DRAW_TWO)]


def test_you_cannot_draw_normally_while_a_stack_is_pending():
    st = rig(game(), hand=[c("fire", D.DRAW_TWO)], top=c("fire", 2))
    E.play(st, 0)
    ok, r = E.draw(st)
    assert not ok and "ยอมจั่ว" in r["error"]


# ── จั่วไพ่ ──

def test_drawing_a_playable_card_lets_you_keep_your_turn():
    st = rig(game(), hand=[c("water", 9)], top=c("fire", 2))
    st["deck"] = [c("fire", 7)]
    ok, r = E.draw(st)
    assert ok and r["playable"] is True
    assert st["turn"] == 0, "จั่วได้ใบที่วางได้แล้วต้องยังเป็นตาเราอยู่"


def test_drawing_a_dead_card_ends_your_turn():
    st = rig(game(), hand=[c("water", 9)], top=c("fire", 2))
    st["deck"] = [c("wood", 8)]
    ok, r = E.draw(st)
    assert ok and r["playable"] is False
    assert st["turn"] == 1


def test_you_only_draw_once_per_turn():
    """จั่วรัวได้ = ดูดไพ่จนเจอใบที่ชอบ"""
    st = rig(game(), hand=[c("water", 9)], top=c("fire", 2))
    st["deck"] = [c("fire", 7), c("fire", 3)]
    E.draw(st)
    ok, r = E.draw(st)
    assert not ok and "จั่วไปแล้ว" in r["error"]


def test_you_may_pass_after_drawing():
    st = rig(game(), hand=[c("water", 9)], top=c("fire", 2))
    st["deck"] = [c("fire", 7)]
    E.draw(st)
    ok, _ = E.passes(st)
    assert ok and st["turn"] == 1


def test_you_cannot_pass_without_drawing_first():
    st = rig(game(), hand=[c("water", 9)], top=c("fire", 2))
    ok, r = E.passes(st)
    assert not ok and "จั่วก่อน" in r["error"]


def test_the_discard_pile_comes_back_when_the_deck_runs_out():
    """กองจั่วหมดแล้วต้องเอากองทิ้งมาสับใหม่ ไม่งั้นเกมค้างถาวร"""
    st = rig(game(), hand=[c("water", 9)], top=c("fire", 2))
    st["deck"] = []
    st["pile"] = [c("fire", 2), c("fire", 3), c("fire", 4)]
    ok, r = E.draw(st)
    assert ok and len(r["drew"]) == 1
    assert len(st["pile"]) == 1, "ต้องเหลือแค่ใบบนสุดไว้ในกองทิ้ง"


def test_recycled_wilds_lose_their_chosen_colour():
    """ไวลด์ที่เคยเลือกสีไว้ ถ้ากลับมาพร้อมสีจะกลายเป็นไพ่สีที่แรงเกิน"""
    st = rig(game(), hand=[c("water", 9)], top=c("fire", 2))
    st["deck"] = []
    # ใส่ไวลด์ติดสีหลายใบ จะได้เหลือให้ตรวจแน่ ๆ หลังจั่วไปหนึ่งใบ
    st["pile"] = [D.card("fire", D.WILD), D.card("water", D.WILD_DRAW_FOUR),
                  D.card("wood", D.WILD), c("fire", 3), c("fire", 2)]
    E.draw(st)
    # ไวลด์ทุกใบไม่ว่าไปอยู่กองไหน (กองจั่ว/มือ/กองทิ้ง) ต้องไม่มีสีติด
    everywhere = st["deck"] + E.hand_of(st, 0) + st["pile"]
    wilds = [x for x in everywhere if D.is_wild(x)]
    assert wilds, "ไวลด์หายไปไหนหมด"
    for card in wilds:
        assert card["suit"] is None, f"ไวลด์กลับมาพร้อมสีที่เคยเลือก: {card}"


# ── จบเกม ──

def test_emptying_your_hand_wins_the_game():
    st = rig(game(), hand=[c("fire", 5)], top=c("fire", 2), spare=False)
    ok, r = E.play(st, 0)
    assert ok and r["winner"] == 0 and st["winner"] == 0


def test_a_finished_game_takes_no_more_moves():
    """จบจริงตอนเหลือคนเดียว — มีคนชนะแล้วยังเล่นต่อได้"""
    st = rig(game(names=("ก", "ข")), hand=[c("fire", 5)], top=c("fire", 2), spare=False)
    E.play(st, 0)
    assert st["over"], "เล่น 2 คน คนหนึ่งหมดมือ = จบทันที"
    assert not E.play(st, 0)[0]
    assert not E.draw(st)[0]


def test_the_game_keeps_going_after_the_first_winner():
    """เจ้าของเกมสั่ง: คนชนะนั่งดูเพื่อนเล่นต่อจนเหลือ 2 คนสุดท้าย"""
    st = rig(game(), hand=[c("fire", 5)], top=c("fire", 2), spare=False)
    E.play(st, 0)
    assert st["winner"] == 0
    assert not st["over"], "เล่น 3 คน คนแรกหมดมือแล้วไม่ควรจบ"
    assert st["finished"] == [0]
    assert st["turn"] != 0, "คนที่เข้าเส้นชัยแล้วต้องไม่มีตาอีก"


def test_the_finishing_order_is_remembered():
    """ต้องรู้ว่าใครที่ 1 2 3 — อนิเมชันตอนจบต่างกันตามอันดับ"""
    st = game()
    p1 = E._finish(st, 1)
    p2 = E._finish(st, 2)
    assert (p1, p2) == (1, 2)
    assert st["winner"] == 1, "คนที่หนึ่งคือผู้ชนะ"
    assert st["over"], "เหลือคนเดียวแล้วต้องจบ"
    assert st["finished"] == [1, 2, 0], "คนสุดท้ายต้องถูกเติมเข้าอันดับสุดท้ายให้เอง"


def test_winning_scores_the_cards_left_in_everyone_elses_hands():
    st = rig(game(), hand=[c("fire", 5)], top=c("fire", 2), spare=False)
    st["players"][1]["hand"] = [c("fire", 9), c(None, D.WILD)]      # 9 + 50
    st["players"][2]["hand"] = [c("fire", D.SKIP)]                  # 20
    E.play(st, 0)
    assert E.score(st) == 79


def test_an_unfinished_game_scores_nothing():
    assert E.score(game()) == 0


# ── ร้อง UNO ──

def test_you_can_shout_uno_on_your_last_card():
    st = rig(game(), hand=[c("fire", 5), c("fire", 6)], top=c("fire", 2), spare=False)
    E.play(st, 0)
    ok, _ = E.say_uno(st, 0)
    assert ok and st["players"][0]["said_uno"]


def test_you_cannot_shout_uno_with_a_full_hand():
    st = game()
    ok, r = E.say_uno(st, 0)
    assert not ok and "ใบเดียว" in r["error"]


def test_drawing_cancels_your_uno_call():
    """ร้องแล้วโดนสแตคจนมือกลับมาเยอะ ต้องไม่ยังนับว่าร้องไว้"""
    st = rig(game(), hand=[c("fire", 5), c("fire", 6)], top=c("fire", 2), spare=False)
    E.play(st, 0)
    E.say_uno(st, 0)
    E._draw(st, 0, 2, random.Random(1))
    assert not st["players"][0]["said_uno"]


# ── เล่นจนจบจริง ──

def test_a_whole_game_can_be_played_to_the_end():
    """เล่นอัตโนมัติจนมีคนชนะ — จับเกมค้างและไพ่หายที่เทสรายข้อมองไม่เห็น"""
    for seed in range(12):
        st = game(seed=seed)
        rng = random.Random(seed)
        for _ in range(4000):
            if st["winner"] is not None:
                break
            if E.must_answer_stack(st):
                opts = E.playable_now(st)
                if opts:
                    # ⚠️ สแตค +4 ก็ต้องเลือกสีเหมือนกัน ไม่ส่งสี = วางไม่สำเร็จ ตาไม่เดิน วนไม่จบ
                    E.play(st, E.hand_of(st, st["turn"]).index(opts[0]),
                           chosen_suit="fire" if D.is_wild(opts[0]) else None)
                else:
                    E.take_stack(st, rng)
                continue
            opts = E.playable_now(st)
            if opts:
                card = opts[0]
                E.play(st, E.hand_of(st, st["turn"]).index(card),
                       chosen_suit="fire" if D.is_wild(card) else None, rng=rng)
            else:
                ok, r = E.draw(st, rng)
                if ok and r.get("playable"):
                    E.passes(st)
        assert st["winner"] is not None, f"seed {seed} เล่นไม่จบ (เกมค้าง)"


def test_cards_are_never_lost_during_a_long_game():
    """เล่นยาว ๆ แล้วนับไพ่ทั้งโต๊ะ ต้องยังครบ 108 ใบ"""
    st = game(seed=3)
    rng = random.Random(3)
    for _ in range(300):
        if st["winner"] is not None:
            break
        if E.must_answer_stack(st):
            E.take_stack(st, rng)
            continue
        opts = E.playable_now(st)
        if opts:
            card = opts[0]
            E.play(st, E.hand_of(st, st["turn"]).index(card),
                   chosen_suit="fire" if D.is_wild(card) else None, rng=rng)
        else:
            E.draw(st, rng)
        total = (sum(len(p["hand"]) for p in st["players"])
                 + len(st["deck"]) + len(st["pile"]))
        assert total == D.DECK_SIZE, f"ไพ่เพี้ยนเหลือ {total} ใบ"


def test_a_stack_can_always_be_answered_somehow():
    """โดนสแตคแล้วต้องมีทางออกเสมอ ไม่งั้นเกมค้างถาวร

    เคยเกือบพลาด: ถือ +4 อยู่แต่วางไม่ได้เพราะยังไม่ได้เลือกสี
    และ take_stack ก็ไม่ถูกเรียก — ตาไม่เดิน วนไม่จบ
    ยอมจั่วต้องทำได้เสมอไม่ว่ามือจะถืออะไรอยู่
    """
    st = rig(game(names=("ก", "ข")), hand=[c(None, D.WILD_DRAW_FOUR)], top=c("fire", 2))
    E.play(st, 0, chosen_suit="fire")
    assert st["stack"] == 4 and st["turn"] == 1
    st["players"][1]["hand"] = [c(None, D.WILD_DRAW_FOUR)]
    ok, r = E.take_stack(st)
    assert ok, "ถือ +4 แต่ยอมจั่วไม่ได้ = เกมค้าง"
    assert len(r["drew"]) == 4 and st["stack"] == 0


def test_the_turn_skips_players_who_already_went_out():
    """คนที่ทิ้งไพ่หมดแล้วต้องไม่มีตาอีก — ไม่งั้นตาไปหยุดที่คนมือเปล่า เกมค้าง"""
    st = game(names=("ก", "ข", "ค"))
    st["finished"] = [1]                 # ข ออกไปแล้ว
    st["turn"] = 0
    E._advance(st)
    assert st["turn"] == 2, "ตาไปหยุดที่คนที่ออกไปแล้ว"


def test_the_turn_skips_several_finished_players_in_a_row():
    st = E.new_game(["ก", "ข", "ค", "ง"], rng=random.Random(1))
    st["finished"] = [1, 2]              # ข กับ ค ออกไปแล้ว
    st["turn"] = 0
    E._advance(st)
    assert st["turn"] == 3


def test_skipping_still_works_backwards():
    """ย้อนทางแล้วก็ต้องข้ามคนที่ออกไปแล้วเหมือนกัน"""
    st = game(names=("ก", "ข", "ค"))
    st["finished"] = [2]
    st["dir"] = -1
    st["turn"] = 0
    E._advance(st)
    assert st["turn"] == 1
