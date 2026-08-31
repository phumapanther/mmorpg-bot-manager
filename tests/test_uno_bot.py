"""🤖 บอทนั่งโต๊ะไพ่รูน — ขั้น 4 ของศึกไพ่รูน

สองอย่างที่ต้องคุมให้แน่น:
  1. บอทวางไพ่ถูกกติกาเสมอ (วางผิดได้ = บอทโกงได้)
  2. บอทดูได้เฉพาะไพ่ในมือตัวเอง (แอบดูได้ = ผู้เล่นไม่มีทางชนะ)
"""
import inspect
import random

from bot.cards import uno_bot as B
from bot.cards import uno_deck as D
from bot.cards import uno_engine as E
from bot.cards import uno_rules as R


def c(suit, value):
    return D.card(suit, value)


# ── 🔒 บอทต้องไม่แอบดูไพ่คนอื่น ──

def test_the_bot_only_ever_sees_its_own_hand():
    """choose() ต้องรับแค่ของที่ทุกคนบนโต๊ะเห็น ไม่ใช่สถานะทั้งก้อน

    รับสถานะทั้งก้อนเมื่อไหร่ = บอทอ่านไพ่คนอื่นได้ทันที และไม่มีใครสังเกตเห็น
    """
    args = set(inspect.signature(B.choose).parameters)
    assert "st" not in args and "state" not in args and "players" not in args, \
        f"บอทรับสถานะทั้งก้อนเข้ามา: {sorted(args)}"
    assert "hand_sizes" in args, "ต้องรับแค่จำนวนไพ่ของคนอื่น ไม่ใช่ตัวไพ่"


def test_the_bot_body_never_reads_other_hands():
    src = inspect.getsource(B.choose)
    assert '["hand"]' not in src, "บอทเปิดดูมือของคนอื่นในโค้ด"


# ── บอทวางไพ่ถูกกติกา ──

def test_the_bot_plays_a_legal_card():
    hand = [c("water", 9), c("fire", 5), c("wood", 3)]
    top = c("fire", 2)
    move = B.choose(hand, top, "fire")
    assert move["action"] == "play"
    assert R.playable(hand[move["index"]], top, "fire"), "บอทวางไพ่ผิดกติกา"


def test_the_bot_draws_when_it_has_nothing():
    hand = [c("water", 9), c("wood", 3)]
    assert B.choose(hand, c("fire", 5), "fire")["action"] == "draw"


def test_the_bot_always_picks_a_colour_for_a_wild():
    """ไม่เลือกสี = เกมปฏิเสธการวาง แล้วตาไม่เดิน เกมค้างทั้งโต๊ะ"""
    move = B.choose([c(None, D.WILD)], c("fire", 5), "fire")
    assert move["suit"] in D.SUITS, "บอทวางไวลด์โดยไม่เลือกสี"


def test_the_bot_picks_the_colour_it_holds_most():
    hand = [c(None, D.WILD), c("wood", 1), c("wood", 4), c("fire", 2)]
    assert B.choose(hand, c("light", 5), "light")["suit"] == "wood"


# ── โดนสแตค ──

def test_the_bot_stacks_back_when_it_can():
    hand = [c("fire", 5), c("water", D.DRAW_TWO)]
    move = B.choose(hand, c("fire", D.DRAW_TWO), "fire", stack=2, stack_kind=D.DRAW_TWO)
    assert move["action"] == "play"
    assert hand[move["index"]]["value"] == D.DRAW_TWO


def test_the_bot_takes_the_cards_when_it_cannot_stack():
    hand = [c("fire", 5), c("wood", 9)]
    move = B.choose(hand, c("fire", D.DRAW_TWO), "fire", stack=2, stack_kind=D.DRAW_TWO)
    assert move["action"] == "take_stack"


def test_the_bot_never_answers_a_plus_two_with_a_plus_four():
    """+4 สแตคทับ +2 ไม่ได้ตามกติกาบ้านเรา — บอทต้องไม่ลอง"""
    hand = [c(None, D.WILD_DRAW_FOUR), c("wood", 9)]
    move = B.choose(hand, c("fire", D.DRAW_TWO), "fire", stack=2, stack_kind=D.DRAW_TWO)
    assert move["action"] == "take_stack"


def test_a_wild_four_stack_still_gets_a_colour():
    hand = [c(None, D.WILD_DRAW_FOUR), c("wood", 9)]
    move = B.choose(hand, c(None, D.WILD_DRAW_FOUR), "fire",
                    stack=4, stack_kind=D.WILD_DRAW_FOUR)
    assert move["action"] == "play" and move["suit"] in D.SUITS


# ── ไหวพริบ ──

def test_the_bot_attacks_a_player_who_is_about_to_win():
    """คนถัดไปเหลือใบเดียว ต้องงัดไพ่กวนใส่ ไม่ใช่ทิ้งเลขเฉย ๆ"""
    hand = [c("fire", 9), c("fire", D.DRAW_TWO)]
    move = B.choose(hand, c("fire", 2), "fire", hand_sizes=[5, 1], next_i=1)
    assert hand[move["index"]]["value"] == D.DRAW_TWO, "ปล่อยให้คนใกล้ชนะรอด"


def test_the_bot_does_not_waste_attacks_when_nobody_is_close():
    hand = [c("fire", 9), c("fire", D.DRAW_TWO)]
    move = B.choose(hand, c("fire", 2), "fire", hand_sizes=[5, 6], next_i=1)
    assert hand[move["index"]]["value"] == 9, "ทิ้งไพ่กวนทั้งที่ยังไม่มีใครใกล้ชนะ"


def test_the_bot_saves_its_wilds_for_later():
    """ไวลด์ใช้ได้ทุกสถานการณ์ ทิ้งไปตอนมีตัวเลือกอื่นน่าเสียดาย"""
    hand = [c(None, D.WILD), c("fire", 4)]
    move = B.choose(hand, c("fire", 2), "fire", hand_sizes=[5, 5], next_i=1)
    assert not D.is_wild(hand[move["index"]]), "ทิ้งไวลด์ทั้งที่มีไพ่ปกติวางได้"


def test_the_bot_sheds_its_biggest_numbers_first():
    """แต้มที่เหลือในมือคือแต้มที่ยกให้คนชนะ ทิ้งใบแพงก่อนถูกแล้ว"""
    hand = [c("fire", 1), c("fire", 9), c("fire", 5)]
    move = B.choose(hand, c("fire", 2), "fire", hand_sizes=[5, 5], next_i=1)
    assert hand[move["index"]]["value"] == 9


# ── ชื่อบอท ──

def test_several_bots_get_different_names():
    names = B.bot_names(5)
    assert len(set(names)) == 5, "บอทชื่อซ้ำกัน แยกไม่ออกว่าใครเป็นใคร"


def test_one_bot_keeps_the_plain_name():
    assert B.bot_names(1) == [B.BOT_NAME]


def test_no_bots_means_no_names():
    assert B.bot_names(0) == []


def test_bots_are_recognisable_by_name():
    assert B.is_bot(B.BOT_NAME)
    assert not B.is_bot("ผู้เล่นจริง")


# ── เล่นกับเกมจริง ──

def test_a_bot_turn_always_moves_the_game_forward():
    """บอทเล่นแล้วต้องเกิดอะไรขึ้นเสมอ ไม่งั้นเกมค้างตรงตาบอท"""
    for seed in range(20):
        st = E.new_game(["คน", B.BOT_NAME], rng=random.Random(seed))
        st["turn"] = 1
        before = (st["turn"], len(E.hand_of(st, 1)), len(st["pile"]))
        ok, _ = B.take_turn(E, st, random.Random(seed))
        after = (st["turn"], len(E.hand_of(st, 1)), len(st["pile"]))
        assert ok, f"seed {seed}: บอทเล่นไม่สำเร็จ"
        assert before != after, f"seed {seed}: บอทเล่นแล้วไม่มีอะไรเปลี่ยน"


def test_bots_can_finish_a_game_between_themselves():
    """โต๊ะบอทล้วนต้องเล่นจบได้ — จับเกมค้างที่เทสรายข้อมองไม่เห็น"""
    for seed in range(15):
        st = E.new_game(B.bot_names(3), rng=random.Random(seed))
        rng = random.Random(seed)
        for _ in range(4000):
            if st["winner"] is not None:
                break
            ok, _ = B.take_turn(E, st, rng)
            assert ok, f"seed {seed}: บอทติดขัด"
        assert st["winner"] is not None, f"seed {seed}: โต๊ะบอทเล่นไม่จบ"


def test_bots_never_break_the_deck():
    """เล่นยาว ๆ แล้วไพ่ทั้งโต๊ะต้องยังครบ 108 ใบ"""
    st = E.new_game(B.bot_names(4), rng=random.Random(2))
    rng = random.Random(2)
    for _ in range(600):
        if st["winner"] is not None:
            break
        B.take_turn(E, st, rng)
        total = (sum(len(p["hand"]) for p in st["players"])
                 + len(st["deck"]) + len(st["pile"]))
        assert total == D.DECK_SIZE, f"ไพ่เพี้ยนเหลือ {total} ใบ"


def test_a_human_can_beat_a_bot_sometimes():
    """บอทต้องไม่ชนะทุกเกม ไม่งั้นไม่มีใครอยากเล่น

    ให้ "คน" เล่นแบบง่ายที่สุด (เจอใบไหนวางได้ก็วาง) แล้วดูว่ายังชนะได้บ้าง
    """
    human_wins = 0
    for seed in range(30):
        st = E.new_game(["คน", B.BOT_NAME], rng=random.Random(seed))
        rng = random.Random(seed)
        for _ in range(4000):
            if st["winner"] is not None:
                break
            if st["turn"] == 1:
                B.take_turn(E, st, rng)
                continue
            if E.must_answer_stack(st):
                opts = E.playable_now(st)
                if opts:
                    E.play(st, E.hand_of(st, 0).index(opts[0]),
                           chosen_suit="fire" if D.is_wild(opts[0]) else None)
                else:
                    E.take_stack(st, rng)
                continue
            opts = E.playable_now(st)
            if opts:
                E.play(st, E.hand_of(st, 0).index(opts[0]),
                       chosen_suit="fire" if D.is_wild(opts[0]) else None, rng=rng)
            else:
                ok, r = E.draw(st, rng)
                if ok and r.get("playable"):
                    E.passes(st)
        if st["winner"] == 0:
            human_wins += 1
    assert 5 <= human_wins <= 25, f"คนชนะ {human_wins}/30 — เอียงไปข้างเดียวเกินไป"


def test_the_bot_plays_a_card_it_just_drew_if_it_can():
    """จั่วได้ใบที่วางได้ต้องวางเลย — ไม่งั้นไพ่ในมือบวมขึ้นเรื่อย ๆ

    กติกาให้วางได้อยู่แล้ว ถือไว้เฉย ๆ = เสียเปรียบตัวเองฟรี ๆ
    """
    st = E.new_game(["คน", B.BOT_NAME], rng=random.Random(1))
    st["turn"] = 1
    st["players"][1]["hand"] = [c("water", 9)]        # วางไม่ได้
    st["pile"] = [c("fire", 2)]
    st["suit"] = "fire"
    st["deck"] = [c("fire", 7)]                       # จั่วแล้ววางได้ทันที
    B.take_turn(E, st, random.Random(1))
    assert E.top_card(st) == c("fire", 7), "จั่วได้ใบที่วางได้แต่ไม่วาง"
    assert len(E.hand_of(st, 1)) == 1, "ไพ่ค้างมือแทนที่จะถูกวาง"
