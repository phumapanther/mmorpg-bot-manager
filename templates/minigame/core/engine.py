"""🔄 ลำดับเทิร์น — ขั้น 2 ของเกมทายเลข 1-10

ขั้นนี้ทำให้ "เล่นจบเกมได้จริง" — เปิดเกม ผลัดกันทาย รู้ว่าใครชนะ
ยังไม่มีบอท ยังไม่มีหน้าเว็บ (ขั้นถัดไปอยู่ที่ bot_ai.py / table.py / room.py)

⚠️ ใช้ import แบบ relative (`from . import rules`) ในไฟล์ core/ ทุกไฟล์
   เพราะทั้งโฟลเดอร์นี้จะถูกก๊อปไปที่ bot/games/<หมวด>/<ชื่อเกม>/ ตอนใช้งานจริง
   ถ้า import แบบ absolute (`from templates.minigame.core import rules`) จะพัง
   ทันทีที่ย้ายโฟลเดอร์ — relative import อยู่รอดเพราะไม่สนใจว่า package
   ชื่อจริงคืออะไร สนใจแค่ "ไฟล์ข้างตัวเอง"
"""
import random

from . import rules as R

MIN_PLAYERS = 2
MAX_PLAYERS = 6
MAX_GUESSES = 20     # กันเกมค้างไม่รู้จบ (ปกติทายไม่กี่ตาก็จบ) — เสมอถ้าครบแล้วไม่มีใครถูก


def new_game(names, rng=None):
    """เปิดเกมใหม่ — คืนสถานะทั้งก้อน (เก็บลง DB ได้เลย)"""
    if not MIN_PLAYERS <= len(names) <= MAX_PLAYERS:
        raise ValueError(f"ต้องมี {MIN_PLAYERS}-{MAX_PLAYERS} คน")
    rng = rng or random.Random()
    return {
        "players": [{"name": n, "guesses": []} for n in names],
        "secret": rng.randint(R.MIN_NUM, R.MAX_NUM),   # 🔒 ห้ามส่งขึ้นเว็บก่อนเกมจบ (ดู room.py/table.py)
        "turn": 0,
        "winner": None,
        "over": False,
        "log": [],
    }


def current(st):
    return st["players"][st["turn"]]


def _advance(st):
    st["turn"] = (st["turn"] + 1) % len(st["players"])


def guess(st, number):
    """คนที่ถึงตาทายเลข number — คืน (ok, ผล)

    ⚠️ ผลลัพธ์ที่คืนไม่มีคีย์ "secret" เลยแม้ตอนทายถูก — ให้ view() ของ
       table.py/room.py เป็นคนตัดสินว่าจะเฉลยตอนไหน (ประตูเดียวก่อนขึ้นเว็บ)
    """
    if st.get("over"):
        return False, {"error": "เกมนี้จบแล้ว"}
    if not R.valid_guess(number):
        return False, {"error": f"ทายได้แค่ {R.MIN_NUM}-{R.MAX_NUM}"}

    number = int(number)
    who = current(st)
    result = R.feedback(st["secret"], number)
    who["guesses"].append({"n": number, "result": result})

    if result == "correct":
        st["winner"] = st["turn"]
        st["over"] = True
        st["log"].append(f"🎉 {who['name']} ทาย {number} ถูกต้อง!")
        return True, {"result": result}

    hint = "สูงไป" if result == "lower" else "ต่ำไป"
    st["log"].append(f"{who['name']} ทาย {number} — {hint}")

    if sum(len(p["guesses"]) for p in st["players"]) >= MAX_GUESSES:
        st["over"] = True
        st["log"].append("⏱️ ทายครบจำนวนแล้วไม่มีใครถูก — เสมอ")
        return True, {"result": result}

    _advance(st)
    return True, {"result": result}
