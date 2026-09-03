"""เทสลำดับเทิร์น — เล่นจบเกมได้จริง (ยังไม่มีบอท/เว็บ)"""
import random

import pytest

from templates.minigame.core import bot_ai as B
from templates.minigame.core import engine as E


def test_เปิดเกมใหม่ต้องมีคนคนละ_2_ถึง_6():
    with pytest.raises(ValueError):
        E.new_game(["คนเดียว"])
    with pytest.raises(ValueError):
        E.new_game([f"คน{i}" for i in range(7)])


def test_ทายผิดส่งตาให้คนถัดไป():
    st = E.new_game(["เอ", "บี"], rng=random.Random(1))
    wrong = 1 if st["secret"] != 1 else 2
    ok, r = E.guess(st, wrong)
    assert ok and r["result"] in ("higher", "lower")
    assert st["turn"] == 1, "ทายผิดแล้วต้องส่งตาให้คนถัดไป"
    assert not st["over"]


def test_ทายถูกจบเกมทันทีและบันทึกผู้ชนะ():
    st = E.new_game(["เอ", "บี"], rng=random.Random(1))
    ok, r = E.guess(st, st["secret"])
    assert ok and r["result"] == "correct"
    assert "secret" not in r, "ผลลัพธ์ต้องไม่มีเลขลับติดมาด้วย (view() เป็นคนตัดสินว่าจะเฉลยตอนไหน)"
    assert st["over"] and st["winner"] == 0


def test_ทายนอกช่วงไม่ขยับตาและไม่ถือว่าเป็นการทาย():
    st = E.new_game(["เอ", "บี"], rng=random.Random(1))
    ok, r = E.guess(st, 99)
    assert not ok and "error" in r
    assert st["turn"] == 0
    assert st["players"][0]["guesses"] == []


def test_ทายหลังเกมจบแล้วไม่ได้():
    st = E.new_game(["เอ", "บี"], rng=random.Random(1))
    E.guess(st, st["secret"])
    ok, r = E.guess(st, 1)
    assert not ok and "error" in r


def test_บอทเล่นจนกว่าจะถึงตาคนหรือเกมจบ():
    rng = random.Random(2)
    st = E.new_game(["🤖 บอท 1", "🤖 บอท 2"], rng=rng)
    for _ in range(E.MAX_GUESSES + 2):
        if st["over"]:
            break
        B.take_turn(E, st, rng)
    assert st["over"], "บอทเล่นกันเองต้องจบเกมได้โดยไม่ค้าง"


def test_บอทแคบช่วงตามผลทายจริง():
    low, high = B.narrow(1, 10, 5, "higher")
    assert (low, high) == (6, 10)
    low, high = B.narrow(1, 10, 5, "lower")
    assert (low, high) == (1, 4)
