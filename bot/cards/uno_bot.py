"""🤖 บอทนั่งโต๊ะไพ่รูน — ขั้น 4 ของศึกไพ่รูน

ทำไมต้องมีบอท: ไม่มีบอท = ต้องรอคนออนไลน์พร้อมกัน 2-6 คน
ช่วงเปิดใหม่อาจไม่มีใครได้เล่นเลยสักตา (สนามรบผลัดเทิร์นก็ติดปัญหานี้อยู่)

🔒 กติกาเหล็ก: บอทดูได้เฉพาะไพ่ในมือตัวเอง
   ฟังก์ชันในไฟล์นี้รับ "มือของบอท" กับ "สิ่งที่ทุกคนบนโต๊ะเห็นอยู่แล้ว"
   (ไพ่บนสุด สีปัจจุบัน กองสแตค คนอื่นเหลือกี่ใบ) — ไม่รับสถานะทั้งก้อน
   ถ้ารับทั้งก้อนเมื่อไหร่ บอทจะแอบดูไพ่คนอื่นได้ทันทีโดยไม่มีใครสังเกต
   นี่คือบั๊กแบบเดียวกับที่ uno-engine2 ทำผิดในระบบสแตค

🎯 บอทเล่นยังไง (ไม่ฉลาดมาก ตั้งใจให้พอสูสี)
   1. โดนสแตคจ่อ -> วางต่อถ้ามี ไม่มีก็ยอมจั่ว
   2. คนถัดไปเหลือ 1-2 ใบ -> งัดไพ่กวนใส่ก่อน (+4 +2 ข้ามตา)
   3. ปกติ -> ทิ้งไพ่ตัวเลขแต้มสูงก่อน เก็บไวลด์ไว้ตอนจำเป็น
   4. เลือกสี -> สีที่ถือมากที่สุดในมือ
"""
import random

from bot.cards import uno_deck as D
from bot.cards import uno_rules as R

BOT_NAME = "🤖 บอท"
THREAT = 2               # คนถัดไปเหลือไพ่ไม่เกินนี้ = อันตราย ต้องกวน

# ลำดับความอยากทิ้งของไพ่ท่าพิเศษตอน "ไม่ได้กำลังกวนใคร"
# เก็บไวลด์ไว้ท้ายสุดเพราะใช้ได้ทุกสถานการณ์ ทิ้งทิ้งไปก่อนน่าเสียดาย
_ACTION_ORDER = {D.DRAW_TWO: 0, D.SKIP: 1, D.REVERSE: 2,
                 D.WILD_DRAW_FOUR: 3, D.WILD: 4}


def is_bot(name):
    """ชื่อนี้เป็นบอทไหม

    ⚠️ โต๊ะหลายบอทชื่อจะมีเลขต่อท้าย ("🤖 บอท 1")
       เทียบชื่อเต็ม ๆ จึงตอบ False กับบอททุกตัวบนโต๊ะหลายบอท
    """
    return str(name or "").startswith(BOT_NAME)


def bot_names(count):
    """ชื่อบอทหลายตัวไม่ให้ซ้ำกัน — โต๊ะ 6 คนอาจมีบอท 5 ตัว"""
    if count <= 1:
        return [BOT_NAME] if count == 1 else []
    return [f"{BOT_NAME} {i + 1}" for i in range(count)]


def _pick_suit(hand):
    """เลือกสีที่ถือมากที่สุด — เท่ากันก็เอาสีที่แต้มรวมสูงกว่า (ทิ้งง่ายกว่า)"""
    best, score = None, (-1, -1)
    for suit in D.SUITS:
        mine = [c for c in hand if c["suit"] == suit]
        rank = (len(mine), sum(D.points(c) for c in mine))
        if rank > score:
            best, score = suit, rank
    return best


def _threatened(hand_sizes, next_i):
    """คนถัดไปใกล้ชนะแล้วหรือยัง"""
    if next_i is None or next_i >= len(hand_sizes):
        return False
    return hand_sizes[next_i] <= THREAT


def choose(hand, top, suit, stack=0, stack_kind=None,
           hand_sizes=(), next_i=None, rng=None):
    """บอทจะทำอะไรในตานี้ — คืน dict บอกการกระทำ

    ⚠️ พารามิเตอร์ทั้งหมดคือ "ของที่ทุกคนบนโต๊ะเห็นได้" เท่านั้น
       hand_sizes = คนอื่นเหลือกี่ใบ (แค่จำนวน ไม่ใช่ตัวไพ่)

    คืนอย่างใดอย่างหนึ่ง:
      {"action": "play", "index": i, "suit": สีที่เลือก|None}
      {"action": "take_stack"}      ยอมจั่วกองสแตค
      {"action": "draw"}            จั่วปกติ
    """
    rng = rng or random.Random()

    # 1) โดนสแตคจ่ออยู่ — วางต่อได้เฉพาะชนิดเดียวกัน
    if stack:
        same = [i for i, c in enumerate(hand) if c["value"] == stack_kind]
        if same:
            i = same[0]
            return {"action": "play", "index": i,
                    "suit": _pick_suit(hand) if D.is_wild(hand[i]) else None}
        return {"action": "take_stack"}

    options = [i for i, c in enumerate(hand) if R.playable(c, top, suit)]
    if not options:
        return {"action": "draw"}

    # 2) คนถัดไปใกล้ชนะ — งัดไพ่กวนใส่ก่อน
    if _threatened(hand_sizes, next_i):
        nasty = [i for i in options
                 if hand[i]["value"] in (D.WILD_DRAW_FOUR, D.DRAW_TWO, D.SKIP)]
        if nasty:
            i = min(nasty, key=lambda k: _ACTION_ORDER.get(hand[k]["value"], 9)
                    if hand[k]["value"] != D.WILD_DRAW_FOUR else -1)
            return {"action": "play", "index": i,
                    "suit": _pick_suit(hand) if D.is_wild(hand[i]) else None}

    # 3) ปกติ — ทิ้งไพ่ตัวเลขแต้มสูงก่อน แล้วค่อยไพ่ท่า เก็บไวลด์ไว้ท้ายสุด
    def rank(i):
        card = hand[i]
        if D.is_wild(card):
            return (2, _ACTION_ORDER.get(card["value"], 9))
        if D.is_action(card):
            return (1, _ACTION_ORDER.get(card["value"], 9))
        return (0, -card["value"])          # ตัวเลข: แต้มสูงทิ้งก่อน

    i = min(options, key=rank)
    return {"action": "play", "index": i,
            "suit": _pick_suit(hand) if D.is_wild(hand[i]) else None}


def take_turn(engine, st, rng=None):
    """ให้บอทที่ถึงตาเล่นหนึ่งตา — คืน (ok, ผล)

    รับ engine เข้ามาเพื่อไม่ให้ไฟล์นี้ต้อง import วนกลับไปหา uno_engine
    (uno_engine เป็นคนเรียกใช้บอท ไม่ใช่ทางกลับกัน)
    """
    rng = rng or random.Random()
    i = st["turn"]
    hand = engine.hand_of(st, i)
    sizes = [len(p["hand"]) for p in st["players"]]
    move = choose(hand, engine.top_card(st), st["suit"],
                  stack=st["stack"], stack_kind=st["stack_kind"],
                  hand_sizes=sizes, next_i=engine.next_index(st), rng=rng)

    if move["action"] == "take_stack":
        return engine.take_stack(st, rng)
    if move["action"] == "draw":
        ok, r = engine.draw(st, rng)
        # จั่วได้ใบที่วางได้ = วางเลย (ไม่งั้นบอทจะถือไว้เฉย ๆ แล้วผ่าน)
        if ok and r.get("playable"):
            card = engine.hand_of(st, i)[-1]
            return engine.play(st, len(engine.hand_of(st, i)) - 1,
                               chosen_suit=_pick_suit(hand) if D.is_wild(card) else None,
                               rng=rng)
        return ok, r
    return engine.play(st, move["index"], chosen_suit=move["suit"], rng=rng)
