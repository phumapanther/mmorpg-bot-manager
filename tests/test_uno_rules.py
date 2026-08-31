"""🎯 กฎการวางไพ่รูน — ขั้น 2 ของศึกไพ่รูน

กฎวางไพ่ผิด = เกมโกงได้เงียบ ๆ (วางใบที่ไม่ควรวางได้ หรือวางใบที่ควรได้ไม่ได้)
เทสชุดนี้จึงไล่ "ทุกคู่ที่เป็นไปได้" ไม่ใช่สุ่มตัวอย่างมาลอง
"""
import itertools

from bot.cards import uno_deck as D
from bot.cards import uno_rules as R


def c(suit, value):
    return D.card(suit, value)


# ── กติกาพื้นฐาน ──

def test_matching_colour_can_be_played():
    assert R.playable(c("fire", 5), c("fire", 9))


def test_matching_number_can_be_played_across_colours():
    """เลขตรงกันวางข้ามสีได้ — ไม่งั้นเกมจะตันเร็วมาก"""
    assert R.playable(c("water", 7), c("fire", 7))


def test_matching_action_can_be_played_across_colours():
    assert R.playable(c("water", D.SKIP), c("fire", D.SKIP))


def test_a_different_colour_and_number_cannot_be_played():
    assert not R.playable(c("water", 3), c("fire", 8))


def test_wilds_can_always_be_played():
    """ไวลด์ต้องวางได้ทุกสถานการณ์ ไม่งั้นจะมีมือที่ตันทั้งที่ถือไวลด์อยู่"""
    for wild in (D.WILD, D.WILD_DRAW_FOUR):
        for suit in D.SUITS:
            for value in (0, 9, D.SKIP, D.REVERSE, D.DRAW_TWO):
                assert R.playable(c(None, wild), c(suit, value))


def test_a_number_never_matches_an_action_of_the_same_colour_slot():
    """เลข 2 กับไพ่ +2 ต้องไม่ถูกนับว่า 'หน้าไพ่ตรงกัน'"""
    assert not R.playable(c("water", 2), c("fire", D.DRAW_TWO))


# ── ไล่ทุกคู่ที่เป็นไปได้ ──

def test_every_pair_follows_exactly_one_rule():
    """ไล่ไพ่ทุกแบบ × กองทุกแบบ — ผลต้องตรงกับกติกาที่เขียนไว้เป๊ะ"""
    values = list(range(10)) + [D.SKIP, D.REVERSE, D.DRAW_TWO]
    faces = [c(s, v) for s in D.SUITS for v in values]
    wilds = [c(None, w) for w in (D.WILD, D.WILD_DRAW_FOUR)]

    for card, top in itertools.product(faces + wilds, faces):
        want = (D.is_wild(card)
                or card["suit"] == top["suit"]
                or card["value"] == top["value"])
        assert R.playable(card, top) is bool(want), f"{D.label(card)} ทับ {D.label(top)}"


# ── สีที่เลือกหลังวางไวลด์ (จุดที่พลาดกันบ่อย) ──

def test_after_a_wild_the_chosen_colour_is_what_matters():
    """วางไวลด์เลือกสีน้ำ ไพ่สีน้ำต้องวางต่อได้ แม้ไพ่บนสุดจะไม่มีสี"""
    top = c(None, D.WILD)
    assert R.playable(c("water", 4), top, active_suit="water")
    assert not R.playable(c("fire", 4), top, active_suit="water")


def test_the_chosen_colour_beats_the_card_underneath():
    """สีที่เลือกต้องชนะสีของไพ่บนสุด ไม่ใช่อ่านจากไพ่อย่างเดียว"""
    top = c("fire", 5)
    assert R.playable(c("water", 8), top, active_suit="water")
    assert not R.playable(c("fire", 8), top, active_suit="water")


def test_playing_a_wild_sets_the_colour_the_player_picked():
    assert R.suit_after(c(None, D.WILD), "wood") == "wood"


def test_a_normal_card_sets_its_own_colour():
    assert R.suit_after(c("light", 6)) == "light"


def test_a_made_up_colour_is_refused():
    """เบราว์เซอร์ส่งสีมั่วมาต้องไม่ติด — ไม่งั้นตั้งสีที่ไม่มีจริงแล้วเกมตัน"""
    assert R.suit_after(c(None, D.WILD), "rainbow") is None


# ── ไพ่ที่ทำให้คนถัดไปจั่ว ──

def test_the_draw_cards_say_how_many_to_draw():
    assert R.draw_penalty(c("fire", D.DRAW_TWO)) == 2
    assert R.draw_penalty(c(None, D.WILD_DRAW_FOUR)) == 4


def test_ordinary_cards_make_nobody_draw():
    for card in (c("fire", 5), c("fire", D.SKIP), c("fire", D.REVERSE), c(None, D.WILD)):
        assert R.draw_penalty(card) == 0, D.label(card)


# ── ไพ่ใบแรกของกอง ──

def test_the_pile_never_starts_on_an_action_card():
    """เปิดเกมมาเป็น +4 = ลงโทษคนที่ยังไม่ได้ทำอะไรเลย"""
    for value in (D.SKIP, D.REVERSE, D.DRAW_TWO, D.WILD, D.WILD_DRAW_FOUR):
        suit = None if value in (D.WILD, D.WILD_DRAW_FOUR) else "fire"
        assert not R.can_start_pile(c(suit, value)), value


def test_the_pile_can_start_on_any_number():
    for n in range(10):
        assert R.can_start_pile(c("fire", n))


def test_a_real_deck_always_has_a_legal_opening_card():
    """ต้องมีไพ่เปิดเกมได้จริงในสำรับ ไม่งั้นวนหาไม่เจอจนค้าง"""
    assert any(R.can_start_pile(card) for card in D.build())


# ── ตัวช่วยของหน้าเว็บ ──

def test_the_hand_reports_which_cards_are_playable():
    hand = [c("fire", 5), c("water", 9), c(None, D.WILD), c("wood", 2)]
    got = R.playable_cards(hand, c("fire", 2))
    assert c("fire", 5) in got          # สีตรง
    assert c("wood", 2) in got          # เลขตรง
    assert c(None, D.WILD) in got       # ไวลด์
    assert c("water", 9) not in got     # ไม่ตรงอะไรเลย


def test_a_hand_with_nothing_to_play_says_so():
    hand = [c("water", 9), c("wood", 3)]
    assert not R.has_play(hand, c("fire", 5))


def test_a_hand_with_something_to_play_says_so():
    assert R.has_play([c("water", 9), c("fire", 5)], c("fire", 2))


def test_an_empty_hand_has_nothing_to_play():
    assert not R.has_play([], c("fire", 5))
    assert R.playable_cards([], c("fire", 5)) == []


def test_only_wild_cards_ask_for_a_colour():
    assert R.needs_colour_choice(c(None, D.WILD))
    assert R.needs_colour_choice(c(None, D.WILD_DRAW_FOUR))
    assert not R.needs_colour_choice(c("fire", D.SKIP))
    assert not R.needs_colour_choice(c("fire", 5))


def test_a_missing_card_or_empty_pile_is_never_playable():
    """คำขอที่ไม่มีไพ่ต้องไม่ผ่าน

    เบราว์เซอร์ส่งของเพี้ยนมาได้เสมอ (แก้โค้ดเอง หรือเน็ตหลุด)
    ถ้าตอบ True ตอนไม่มีไพ่ = วางไพ่ที่ไม่มีอยู่จริงได้
    """
    assert not R.playable(None, c("fire", 5))
    assert not R.playable(c("fire", 5), None)
    assert not R.playable(None, None)
