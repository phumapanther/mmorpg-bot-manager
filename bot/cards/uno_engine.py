"""🔄 ลำดับเทิร์นและการ์ดพิเศษ — ขั้น 3 ของศึกไพ่รูน

ขั้นนี้ทำให้ "เล่นจบเกมได้จริง" — แจกไพ่ เดินตา วางไพ่ จั่วไพ่ รู้ว่าใครชนะ
ยังไม่มีบอท ยังไม่มีเงิน ยังไม่มีหน้าเว็บ (ขั้น 4-6)

📐 การ์ดพิเศษ
   🛡️ ม่านสะกด (ข้ามตา)      คนถัดไปอดเล่น
   🌀 วาร์ปกลับทาง (ย้อนทาง)  สลับทิศวนซ้าย/ขวา
   ⚔️ ทัณฑ์สองใบ (+2)         คนถัดไปจั่ว 2 แล้วอดเล่น
   🌑 ประตูนิรันดร์ (+4)       คนถัดไปจั่ว 4 แล้วอดเล่น + เปลี่ยนสี

⚠️ เล่น 2 คนแล้ว "ย้อนทาง" ทำงานเหมือน "ข้ามตา"
   เพราะย้อนทางในวงกลม 2 คน = กลับมาที่คนเดิม ถ้าไม่ดักไว้จะกลายเป็น
   คนวางได้เล่นต่อไม่รู้จบ (uno-engine ทั้งสองตัวที่ดูมาก็ดักข้อนี้เหมือนกัน)

🔥 ระบบสแตค: บั๊กที่ยกมาจาก uno-engine2 แล้วแก้
   ต้นทาง (src/logic/Game.js:239) ตัดสินสแตคด้วยการ **แอบดูไพ่ในมือคนถัดไป**
   ถ้าเขามี +2 ก็บังคับให้เขาวางต่อทันที — ผิดกติกา เพราะของจริงคนถัดไป
   ต้อง *เลือกเอง* ว่าจะวางต่อหรือยอมจั่ว (จะเก็บ +2 ไว้ใช้ทีหลังก็ได้)
   ที่นี่จึงทำเป็นสถานะ "กองสแตคค้างอยู่" แล้วรอคำสั่งจากคนถัดไปจริง ๆ
"""
import random

from bot.cards import uno_deck as D
from bot.cards import uno_rules as R

START_CARDS = 7          # แจกคนละ 7 ใบตามสำรับจริง
MIN_PLAYERS = 2
MAX_PLAYERS = 6          # เท่ากับห้องสนามรบ (rooms.MAX_SEATS)


# ── สร้างเกม ──

def new_game(names, rng=None, start_cards=START_CARDS):
    """เปิดโต๊ะใหม่ — คืนสถานะทั้งก้อน (เก็บลงฐานข้อมูลได้เลย)"""
    if not MIN_PLAYERS <= len(names) <= MAX_PLAYERS:
        raise ValueError(f"ต้องมี {MIN_PLAYERS}-{MAX_PLAYERS} คน")
    rng = rng or random.Random()
    deck = D.new_deck(rng)
    players = [{"name": n, "hand": [], "said_uno": False} for n in names]
    for _ in range(start_cards):
        for p in players:
            p["hand"].append(deck.pop())

    # ไพ่เปิดกองต้องเป็นไพ่ตัวเลข — ไล่หาใบแรกที่ใช้ได้ ที่เหลือดันลงกองไว้เหมือนเดิม
    idx = next(i for i, c in enumerate(deck) if R.can_start_pile(c))
    top = deck.pop(idx)

    return {
        "players": players,
        "deck": deck,
        "pile": [top],
        "suit": top["suit"],        # สีที่ใช้อยู่จริง (ไวลด์จะเปลี่ยนค่านี้)
        "turn": 0,
        "dir": 1,                   # 1 = ตามเข็ม, -1 = ทวนเข็ม
        "stack": 0,                 # กอง +2/+4 ที่ค้างอยู่ รอคนถัดไปตัดสินใจ
        "stack_kind": None,         # สแตคอยู่คือแบบไหน (+2 ต่อ +2 เท่านั้น)
        "drew": False,              # เทิร์นนี้จั่วไปแล้วหรือยัง (จั่วได้ครั้งเดียว)
        "winner": None,
        # 🏁 ลำดับที่ทิ้งไพ่หมด — คนแรกคือที่ 1 ที่เหลือเล่นต่อจนเหลือคนสุดท้าย
        #    (เจ้าของเกมสั่ง: คนชนะนั่งดูเพื่อนเล่นจนกว่าจะเหลือ 2 คนสุดท้าย)
        "finished": [],
        "over": False,          # จบจริงตอนเหลือคนเดียว ไม่ใช่ตอนมีคนชนะ
        "log": [],
    }


# ── ตัวช่วยอ่านสถานะ ──

def current(st):
    return st["players"][st["turn"]]


def next_index(st, step=1):
    """ใครเป็นคนถัดไป — นับตามทิศที่วนอยู่"""
    n = len(st["players"])
    return (st["turn"] + st["dir"] * step) % n


def top_card(st):
    return st["pile"][-1]


def hand_of(st, i):
    return st["players"][i]["hand"]


def playable_now(st, i=None):
    """ไพ่ในมือใบไหนวางได้ตอนนี้ — ระหว่างสแตคจะเหลือแค่ไพ่ที่สแตคต่อได้"""
    i = st["turn"] if i is None else i
    hand = hand_of(st, i)
    if st["stack"]:
        return [c for c in hand if c["value"] == st["stack_kind"]]
    return R.playable_cards(hand, top_card(st), st["suit"])


def must_answer_stack(st):
    """ตอนนี้คนที่ถึงตาโดนสแตคจ่ออยู่ไหม (ต้องวางต่อหรือยอมจั่ว)"""
    return st["stack"] > 0


# ── เดินตา ──

def _advance(st, extra_skip=0):
    """ส่งตาให้คนถัดไป — extra_skip=1 คือข้ามไปอีกหนึ่งคน

    ⚠️ ข้ามคนที่ทิ้งไพ่หมดไปแล้วเสมอ — เขานั่งดูอยู่ ไม่มีตาแล้ว
       ไม่ข้าม = ตาไปหยุดที่คนมือเปล่า เกมค้างทันที
    """
    st["drew"] = False
    n = len(st["players"])
    for _ in range(n * 2 + 2):
        st["turn"] = next_index(st, 1 + extra_skip)
        extra_skip = 0                      # ข้ามเพิ่มใช้ครั้งเดียว ที่เหลือคือข้ามคนที่ออกไปแล้ว
        if st["turn"] not in st["finished"]:
            return


def _reshuffle(st, rng):
    """กองจั่วหมด — เอากองทิ้ง (เว้นใบบนสุด) มาสับใหม่

    ⚠️ ไม่มีตัวนี้ = เล่นยาว ๆ แล้วจั่วไม่ได้ เกมค้างถาวร
       ไวลด์ที่เคยถูกเลือกสีไว้ต้องคืนเป็นไม่มีสีก่อน ไม่งั้นมันจะกลาย
       เป็นไพ่สีธรรมดาที่วางทับอะไรก็ได้
    """
    if len(st["pile"]) <= 1:
        return False
    keep = st["pile"].pop()
    recycled = []
    for c in st["pile"]:
        recycled.append(D.card(None, c["value"]) if D.is_wild(c) else c)
    rng.shuffle(recycled)
    st["deck"] = recycled + st["deck"]
    st["pile"] = [keep]
    return True


def _draw(st, i, count, rng):
    """จั่วให้คนที่ i — กองหมดก็สับกองทิ้งกลับมา คืนไพ่ที่จั่วได้จริง"""
    got = []
    for _ in range(count):
        if not st["deck"] and not _reshuffle(st, rng):
            break                       # ไพ่หมดโลกจริง ๆ (เกิดยากมาก) หยุดแค่นี้
        got.append(st["deck"].pop())
    st["players"][i]["hand"] += got
    if got:
        st["players"][i]["said_uno"] = False   # จั่วแล้วไม่ได้เหลือใบเดียวอีกต่อไป
    return got


def play(st, index, chosen_suit=None, rng=None):
    """วางไพ่ใบที่ index ในมือของคนที่ถึงตา — คืน (ok, ผล)"""
    rng = rng or random.Random()
    if st.get("over"):
        return False, {"error": "เกมนี้จบแล้ว"}
    hand = current(st)["hand"]
    if not 0 <= index < len(hand):
        return False, {"error": "ไม่มีไพ่ใบนั้นในมือ"}

    card = hand[index]
    if st["stack"]:
        # 🔥 โดนสแตคจ่ออยู่ — วางต่อได้เฉพาะไพ่ชนิดเดียวกันเท่านั้น
        if card["value"] != st["stack_kind"]:
            return False, {"error": f"ต้องวาง{D.ACTION_NAME[st['stack_kind']]}ต่อ หรือยอมจั่ว"}
    elif not R.playable(card, top_card(st), st["suit"]):
        return False, {"error": "ไพ่ใบนี้วางไม่ได้"}

    if R.needs_colour_choice(card) and R.suit_after(card, chosen_suit) is None:
        return False, {"error": "ต้องเลือกสีก่อนวางไพ่ใบนี้"}

    hand.pop(index)
    st["pile"].append(card)
    st["suit"] = R.suit_after(card, chosen_suit) or st["suit"]
    who = current(st)["name"]
    st["log"].append(f"{who} วาง {D.label(card)}")

    # เหลือใบเดียวแล้วยังไม่ได้ร้อง = ยังไม่ปลอดภัย (ขั้นนี้แค่จำสถานะไว้ก่อน)
    if len(hand) == 1:
        current(st)["said_uno"] = False

    # ⚠️ ไพ่ใบสุดท้ายเป็น +2/+4 — โทษยังตกถึงคนถัดไปอยู่ดี ถึงจะชนะแล้วก็ตาม
    #    ต้อง _apply_action ก่อนเสมอ ไม่งั้นกองสแตคที่ค้างอยู่จะหายไปเฉย
    #    (เคยพลาด: เช็คชนะก่อนแล้ว return ทันที สแตคเลยไม่สะสม)
    won = st["turn"] if not hand else None    # จำไว้ก่อน — _apply_action กำลังจะเปลี่ยน turn
    _apply_action(st, card)
    if won is not None:
        place = _finish(st, won)
        return True, {"card": card, "winner": st["winner"], "finished": won,
                      "place": place, "stack": st["stack"]}
    return True, {"card": card, "stack": st["stack"]}


def _finish(st, i):
    """คนที่ i ทิ้งไพ่หมดมือ — คืนอันดับที่ได้ (1 = ที่หนึ่ง)

    เกมไม่จบทันที — คนที่เหลือเล่นต่อจนกว่าจะเหลือคนสุดท้ายคนเดียว
    """
    if i in st["finished"]:
        return st["finished"].index(i) + 1
    st["finished"].append(i)
    place = len(st["finished"])
    name = st["players"][i]["name"]
    st["log"].append(f"{'🏆' if place == 1 else '🏅'} {name} เข้าเส้นชัยอันดับ {place}")
    if place == 1:
        st["winner"] = i                     # ผู้ชนะคือคนแรกที่หมดมือ
    # เหลือคนเดียวที่ยังมีไพ่ = จบเกม ส่งเขาเข้าเส้นชัยเป็นอันดับสุดท้ายด้วย
    left = [k for k in range(len(st["players"])) if k not in st["finished"]]
    if len(left) <= 1:
        for k in left:
            st["finished"].append(k)
        st["over"] = True
    return place


def _apply_action(st, card):
    """ผลของการ์ดพิเศษหลังวางลงกอง"""
    value = card["value"]
    two_players = len(st["players"]) == 2

    if value == D.REVERSE:
        st["dir"] *= -1
        # ⚠️ 2 คน: ย้อนทาง = กลับมาที่ตัวเอง ต้องทำเป็นข้ามตาแทน
        _advance(st, 1 if two_players else 0)
        return
    if value == D.SKIP:
        _advance(st, 1)
        return
    if value in (D.DRAW_TWO, D.WILD_DRAW_FOUR):
        # 🔥 ไม่จั่วให้ทันที — ตั้งกองค้างไว้แล้วส่งตาให้คนถัดไป *เลือกเอง*
        #    ว่าจะวางต่อ (สแตค) หรือยอมจั่ว นี่คือจุดที่ uno-engine2 ทำผิด
        st["stack"] += R.draw_penalty(card)
        st["stack_kind"] = value
        _advance(st)
        return
    _advance(st)


def take_stack(st, rng=None):
    """ยอมจั่วกองสแตคที่ค้างอยู่ — แล้วอดเล่นเทิร์นนี้"""
    rng = rng or random.Random()
    if not st["stack"]:
        return False, {"error": "ตอนนี้ไม่มีกองให้จั่ว"}
    n = st["stack"]
    got = _draw(st, st["turn"], n, rng)
    st["log"].append(f"{current(st)['name']} ยอมจั่ว {len(got)} ใบ")
    st["stack"] = 0
    st["stack_kind"] = None
    _advance(st)
    return True, {"drew": got}


def draw(st, rng=None):
    """จั่วหนึ่งใบตอนไม่มีไพ่วางได้ — จั่วแล้ววางได้เลยถ้าใบนั้นวางได้"""
    rng = rng or random.Random()
    if st.get("over"):
        return False, {"error": "เกมนี้จบแล้ว"}
    if st["stack"]:
        return False, {"error": "ต้องเลือกวางต่อหรือยอมจั่วกองก่อน"}
    if st["drew"]:
        return False, {"error": "เทิร์นนี้จั่วไปแล้ว — วางไพ่หรือผ่าน"}

    got = _draw(st, st["turn"], 1, rng)
    st["drew"] = True
    if not got:
        _advance(st)
        return True, {"drew": [], "playable": False}
    st["log"].append(f"{current(st)['name']} จั่วไพ่")
    can = R.playable(got[0], top_card(st), st["suit"])
    if not can:
        _advance(st)                    # จั่วแล้วยังวางไม่ได้ = จบตา
    return True, {"drew": got, "playable": can}


def passes(st):
    """ผ่านตาหลังจั่วแล้ว (จั่วได้ใบที่วางได้แต่ไม่อยากวาง)"""
    if not st["drew"]:
        return False, {"error": "ต้องจั่วก่อนถึงจะผ่านได้"}
    _advance(st)
    return True, {}


def say_uno(st, i):
    """ร้อง UNO ตอนเหลือใบเดียว"""
    if len(hand_of(st, i)) != 1:
        return False, {"error": "ร้องได้ตอนเหลือไพ่ใบเดียวเท่านั้น"}
    st["players"][i]["said_uno"] = True
    st["log"].append(f"🔔 {st['players'][i]['name']} ร้อง UNO!")
    return True, {}


def score(st):
    """แต้มที่ผู้ชนะได้ — รวมแต้มไพ่ที่เหลือในมือคนอื่นทั้งหมด"""
    if st["winner"] is None:
        return 0
    return sum(D.points(c)
               for i, p in enumerate(st["players"]) if i != st["winner"]
               for c in p["hand"])
