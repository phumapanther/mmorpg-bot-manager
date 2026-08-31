"""🎴 สำรับไพ่รูน 108 ใบ — ขั้น 1 ของศึกไพ่รูน

สำรับผิดตั้งแต่ต้น = เกมเพี้ยนทั้งเกมโดยไม่มีใครรู้ว่าเพี้ยนตรงไหน
เทสชุดนี้จึงนับของจริงทุกใบ ไม่ใช่เชื่อว่าโค้ดสร้างถูก
"""
import collections
import random

from bot.cards import uno_deck as D


# ── จำนวนและสัดส่วน ──

def test_the_deck_has_one_hundred_and_eight_cards():
    assert len(D.build()) == D.DECK_SIZE == 108


def test_there_is_exactly_one_zero_of_each_element():
    """เลข 0 มีสีละใบเดียว — ผิดข้อนี้คนจะเจอเลข 0 บ่อยผิดปกติ"""
    deck = D.build()
    for suit in D.SUITS:
        zeros = [c for c in deck if c["suit"] == suit and c["value"] == 0]
        assert len(zeros) == 1, f"{suit} มีเลข 0 {len(zeros)} ใบ"


def test_every_other_number_comes_in_pairs():
    deck = D.build()
    for suit in D.SUITS:
        for n in range(1, 10):
            got = [c for c in deck if c["suit"] == suit and c["value"] == n]
            assert len(got) == 2, f"{suit} เลข {n} มี {len(got)} ใบ"


def test_each_element_has_the_same_number_of_cards():
    """สีไหนมีมากกว่าสีอื่น = สีนั้นได้เปรียบตั้งแต่แจกไพ่"""
    by_suit = collections.Counter(c["suit"] for c in D.build() if c["suit"])
    assert len(set(by_suit.values())) == 1, f"จำนวนไพ่ต่อสีไม่เท่ากัน: {dict(by_suit)}"
    assert sum(by_suit.values()) == 100          # 108 ลบไวลด์ 8 ใบ


def test_action_cards_come_two_per_element():
    deck = D.build()
    for kind in (D.SKIP, D.REVERSE, D.DRAW_TWO):
        for suit in D.SUITS:
            got = [c for c in deck if c["suit"] == suit and c["value"] == kind]
            assert len(got) == 2, f"{suit} {kind} มี {len(got)} ใบ"


def test_there_are_four_of_each_wild():
    deck = D.build()
    for kind in (D.WILD, D.WILD_DRAW_FOUR):
        got = [c for c in deck if c["value"] == kind]
        assert len(got) == D.WILD_COUNT == 4


def test_wild_cards_have_no_colour_until_played():
    """ไวลด์ต้องไม่มีสีติดมา ไม่งั้นมันจะกลายเป็นไพ่สีธรรมดาที่แรงเกิน"""
    for c in D.build():
        if D.is_wild(c):
            assert c["suit"] is None, f"ไพ่ไวลด์ติดสีมาด้วย: {c}"


# ── การสับไพ่ ──

def test_shuffling_keeps_every_single_card():
    """สับแล้วไพ่ต้องไม่หายและไม่งอก — เทียบทีละใบ ไม่ใช่แค่นับจำนวน"""
    def fingerprint(deck):
        return collections.Counter((c["suit"], c["value"]) for c in deck)

    assert fingerprint(D.new_deck(random.Random(1))) == fingerprint(D.build())


def test_shuffling_actually_changes_the_order():
    assert D.new_deck(random.Random(7)) != D.build()


def test_the_same_seed_deals_the_same_deck():
    """เทสอื่นต้องสั่งลำดับไพ่ที่แน่นอนได้ ไม่งั้นเทสจะกะพริบ"""
    assert D.new_deck(random.Random(42)) == D.new_deck(random.Random(42))


def test_shuffling_does_not_eat_the_original_deck():
    """สับแล้วต้องไม่ไปแก้ของเดิม ไม่งั้นเปิดโต๊ะที่สองแล้วสำรับหาย"""
    before = D.build()
    D.new_deck(random.Random(3))
    assert D.build() == before


# ── หน้าตาไพ่ที่ผู้เล่นเห็น ──

def test_every_card_has_a_readable_name():
    for c in D.build():
        name = D.label(c)
        assert name and not name.startswith("None"), f"ไพ่ไม่มีชื่อ: {c}"


def test_the_elements_are_real_game_elements():
    """สีไพ่ต้องเป็นธาตุจริงในเกม ผู้เล่นจะได้ไม่ต้องเรียนของใหม่"""
    from bot import game_modifiers
    for suit in D.SUITS:
        assert suit in game_modifiers.ELEMENTS, f"{suit} ไม่ใช่ธาตุในเกม"


def test_wilds_are_worth_more_than_action_cards_which_beat_numbers():
    """แต้มต้องเรียงตามความแรง ไม่งั้นตอนคิดคะแนนจบเกมจะจูงใจผิด"""
    wild = D.points(D.card(None, D.WILD_DRAW_FOUR))
    action = D.points(D.card("fire", D.SKIP))
    high_number = D.points(D.card("fire", 9))
    assert wild > action > high_number


def test_number_cards_score_their_face_value():
    for n in range(10):
        assert D.points(D.card("fire", n)) == n


def test_action_cards_are_not_mistaken_for_numbers():
    assert D.is_action(D.card("fire", D.SKIP))
    assert D.is_action(D.card(None, D.WILD))
    assert not D.is_action(D.card("fire", 0))     # เลข 0 ต้องไม่ถูกนับเป็นท่าพิเศษ


def test_action_names_do_not_clash_with_the_element_colour():
    """ชื่อท่าต้องใช้ได้กับทุกสี

    ท่าเดียวกันมีครบทั้ง 4 สี ตั้งชื่อตามธาตุจะได้ชื่อประหลาด
    เช่น "✨ สุริยะ · 🔥 เพลิงประหาร" — สองธาตุในใบเดียว
    """
    marks = [D.SUITS[s]["label"].split()[0] for s in D.SUITS]
    for kind in (D.SKIP, D.REVERSE, D.DRAW_TWO):
        name = D.ACTION_NAME[kind]
        for m in marks:
            assert m not in name, f"ชื่อท่า {kind!r} มีสัญลักษณ์ธาตุ {m} ติดมา"
