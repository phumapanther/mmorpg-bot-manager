"""😈 เจ้ามือตุกติก BJ24: เรทตามขนาดเดิมพัน + ล็อคไพ่แล้วบอทต้องไม่แพ้"""
import random

from bot.cogs.blackjack import rig_chance_for, stack_bot_hand


def _deck():
    values = {'A': 1, **{str(n): n for n in range(2, 11)}, 'J': 10, 'Q': 10, 'K': 10}
    deck = [(r, v) for r, v in values.items() for _ in range(4)]
    random.shuffle(deck)
    return deck


def test_rig_chance_tiers():
    assert rig_chance_for(150_000) == 0.90
    assert rig_chance_for(100_000) == 0.90
    assert rig_chance_for(99_999) == 0.70
    assert rig_chance_for(10_000) == 0.70
    assert rig_chance_for(9_999) == 0.60
    assert rig_chance_for(1_000) == 0.60
    assert rig_chance_for(999) == 0.0


def test_stack_bot_hand_never_loses():
    random.seed(24)
    for _ in range(500):
        deck = _deck()
        bot_hand = [deck.pop(), deck.pop()]
        p_score = random.randint(4, 24)
        stack_bot_hand(deck, bot_hand, p_score)
        b_score = sum(c[1] for c in bot_hand)
        assert b_score <= 24, "บอทห้ามแตกเอง"
        # ผู้เล่นได้ 24 พอดี = อย่างแย่ล็อคเสมอ นอกนั้นต้องชนะ
        assert b_score > p_score or b_score == 24
