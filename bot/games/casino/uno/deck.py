"""🎴 สำรับไพ่รูน 108 ใบ — ขั้น 1 ของศึกไพ่รูน (UNO ธีมต่างโลก)

ไฟล์นี้ทำอย่างเดียว: **บอกว่าในสำรับมีไพ่อะไรบ้าง และสับมันได้**
ไม่มีกฎการวาง ไม่มีลำดับเทิร์น ไม่มีเงิน — ของพวกนั้นเป็นขั้นถัด ๆ ไป

🎨 ธาตุ 4 สีมาจากธาตุจริงในเกม (bot/game_modifiers.py ELEMENTS)
   ไม่ได้ตั้งใหม่ เพราะผู้เล่นรู้จัก 🔥 ธาตุไฟ 💧 ธาตุน้ำ 🌿 ธาตุไม้ ✨ ธาตุแสง
   อยู่แล้วจากการตีมอน — เจอในไพ่ก็อ่านออกทันที ไม่ต้องเรียนของใหม่
   (เกมมี 7 ธาตุ แต่ UNO ใช้ได้แค่ 4 สี จึงเลือก 4 ตัวที่ภาพชัดที่สุด
    ส่วน 🌑 ธาตุมืด ยกไปเป็นไพ่ไวลด์ซึ่งไม่มีสี — เข้ากับ "นิรันดร์" พอดี)

📊 สัดส่วน 108 ใบ ตามสำรับ UNO จริง:
     เลข 0        สีละ 1 ใบ  =  4
     เลข 1-9      สีละ 2 ใบ  = 72
     ข้ามตา       สีละ 2 ใบ  =  8
     ย้อนทาง      สีละ 2 ใบ  =  8
     +2           สีละ 2 ใบ  =  8
     เปลี่ยนสี             4 ใบ
     +4                    4 ใบ
                          ───────
                           108 ใบ
"""
import random

# ── ธาตุประจำสี (คีย์ตรงกับ ELEMENTS ในเกม) ──
SUITS = {
    "fire":  {"label": "🔥 เพลิง",  "color": "#d4553a"},
    "water": {"label": "💧 มนตรา", "color": "#4a86a8"},
    "wood":  {"label": "🌿 พฤกษา", "color": "#5f9455"},
    "light": {"label": "✨ สุริยะ", "color": "#e8b04b"},
}

# ── ชนิดไพ่พิเศษ + ชื่อท่าแบบต่างโลก (เจ้าของเกมเคาะไว้) ──
SKIP = "skip"
REVERSE = "reverse"
DRAW_TWO = "draw2"
WILD = "wild"
WILD_DRAW_FOUR = "wild4"

# ⚠️ ชื่อท่าต้องไม่ผูกกับธาตุใดธาตุหนึ่ง — เพราะท่าเดียวกันมีครบทั้ง 4 สี
#    ตั้งชื่อตามธาตุจะได้ "✨ สุริยะ · 🔥 เพลิงประหาร" ซึ่งอ่านแล้วงง
#    จึงตั้งตาม "สิ่งที่ท่านั้นทำ" แทน — สีอ่านจากธาตุข้างหน้าอยู่แล้ว
ACTION_NAME = {
    SKIP: "🛡️ ม่านสะกด",        # ข้ามตาคนถัดไป
    REVERSE: "🌀 วาร์ปกลับทาง",     # ย้อนทิศการเล่น
    DRAW_TWO: "⚔️ ทัณฑ์สองใบ",   # คนถัดไปจั่ว 2
    WILD: "🔮 ศิลาเปลี่ยนธาตุ",  # เปลี่ยนสีตามใจ
    WILD_DRAW_FOUR: "🌑 ประตูนิรันดร์",   # เปลี่ยนสี + จั่ว 4
}

# จำนวนไพ่แต่ละแบบ "ต่อหนึ่งสี" — ตัวเลขนี้คือหัวใจของสำรับ
PER_SUIT = {0: 1}                     # เลข 0 มีสีละใบเดียว
PER_SUIT.update({n: 2 for n in range(1, 10)})    # เลข 1-9 สีละ 2 ใบ
PER_SUIT.update({SKIP: 2, REVERSE: 2, DRAW_TWO: 2})

WILD_COUNT = 4                        # ไวลด์แต่ละแบบมีอย่างละ 4 ใบ (ไม่มีสี)
DECK_SIZE = 108                       # ตรวจซ้ำได้ว่าสร้างครบ

# แต้มไว้คิดคะแนนตอนจบเกม (ยังไม่ใช้ในขั้นนี้ แต่ผูกกับไพ่จึงอยู่ที่นี่)
ACTION_POINTS = 20                    # ข้ามตา/ย้อนทาง/+2 ใบละ 20
WILD_POINTS = 50                      # ไวลด์ทั้งสองแบบใบละ 50


def card(suit, value):
    """ไพ่หนึ่งใบ — suit เป็น None แปลว่าไพ่ไวลด์ (ยังไม่มีสีจนกว่าจะถูกวาง)"""
    return {"suit": suit, "value": value}


def is_wild(c):
    return c["value"] in (WILD, WILD_DRAW_FOUR)


def is_action(c):
    """ไพ่ท่าพิเศษ (ไม่ใช่ไพ่ตัวเลข) — ไวลด์ก็นับด้วย"""
    return not isinstance(c["value"], int)


def points(c):
    """แต้มของไพ่ใบนี้ — ไพ่ตัวเลขได้ตามหน้าไพ่"""
    if isinstance(c["value"], int):
        return c["value"]
    return WILD_POINTS if is_wild(c) else ACTION_POINTS


def label(c):
    """ชื่อไพ่ที่คนอ่านรู้เรื่อง — ใช้ทั้งในดิสและบนเว็บ"""
    if is_wild(c):
        return ACTION_NAME[c["value"]]
    suit = SUITS[c["suit"]]["label"]
    if isinstance(c["value"], int):
        return f"{suit} {c['value']}"
    return f"{suit} · {ACTION_NAME[c['value']]}"


def build():
    """สร้างสำรับเรียงตามลำดับ (ยังไม่สับ) — คืนลิสต์ 108 ใบ"""
    deck = []
    for suit in SUITS:
        for value, count in PER_SUIT.items():
            deck += [card(suit, value) for _ in range(count)]
    for value in (WILD, WILD_DRAW_FOUR):
        deck += [card(None, value) for _ in range(WILD_COUNT)]
    return deck


def new_deck(rng=random):
    """สำรับใหม่ที่สับแล้ว — พร้อมแจก

    ⚠️ รับ rng เข้ามาได้เพื่อให้เทสสั่งลำดับไพ่ที่แน่นอนได้
       (แบบเดียวกับ blackjack_core.new_deck)
    """
    deck = build()
    rng.shuffle(deck)
    return deck
