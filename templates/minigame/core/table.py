"""🎯 โต๊ะซ้อมกับบอท — ขั้น 4 ของเกมทายเลข 1-10

ขั้นนี้ทำให้ "เล่นกับบอทผ่านหน้าเว็บได้จริง" — ยังไม่มีห้องเพื่อน (ขั้น 5 = room.py)

🔒 หัวใจของไฟล์นี้: view() คือ **ประตูเดียว** ก่อนส่งอะไรขึ้นเบราว์เซอร์
   เลขลับ (secret) ห้ามหลุดไปก่อนเกมจบ — ไม่งั้นเปิด F12 อ่านเฉลยได้ตั้งแต่ตาแรก
   ซ่อนด้วย CSS ไม่นับว่าซ่อน ต้องไม่ส่งลงไปตั้งแต่แรก (ดู tests/test_room.py
   กับ tests/test_template_minigame.py ที่คุมเรื่องนี้ 2 ชั้น: ฟังก์ชัน + HTTP)

ที่เก็บสถานะ: sqlite ตัวเดียวกับ bot.models.player_model.DB_NAME (DB กลางของเกม)
ตัวอย่างจริงที่ทำตามแบบนี้: bot/games/casino/uno/table.py
"""
import json
import random
import sqlite3
import time

import bot.models.player_model as player_model

from . import bot_ai as B
from . import engine as E

TABLE_MAX_AGE = 60 * 60      # โต๊ะที่ทิ้งไว้เกิน 1 ชม. = ล้างทิ้ง
HUMAN = 0                    # ผู้เล่นจริงนั่งที่นั่งแรกเสมอในโหมดซ้อมกับบอท
DEFAULT_BOTS = 1

# 🔁 เปลี่ยนชื่อตารางเป็นของเกมคุณตอนก๊อปไปใช้จริง (กันชนกับเกมอื่นในดีบีเดียวกัน)
_TABLE_NAME = "template_guessnum_tables"


def _conn():
    conn = sqlite3.connect(player_model.DB_NAME)
    conn.execute(f"""CREATE TABLE IF NOT EXISTS {_TABLE_NAME} (
        user_id INTEGER PRIMARY KEY, state TEXT NOT NULL, updated_at REAL NOT NULL)""")
    return conn


def load(uid):
    """โต๊ะที่ค้างอยู่ของคนนี้ — ไม่มี/เก่าเกินไป = None"""
    conn = _conn()
    try:
        row = conn.execute(f"SELECT state, updated_at FROM {_TABLE_NAME} WHERE user_id=?",
                           (int(uid),)).fetchone()
        if not row:
            return None
        if time.time() - row[1] > TABLE_MAX_AGE:
            conn.execute(f"DELETE FROM {_TABLE_NAME} WHERE user_id=?", (int(uid),))
            conn.commit()
            return None
        return json.loads(row[0])
    finally:
        conn.close()


def save(uid, st):
    conn = _conn()
    try:
        conn.execute(f"INSERT OR REPLACE INTO {_TABLE_NAME} (user_id, state, updated_at) "
                     "VALUES (?,?,?)", (int(uid), json.dumps(st), time.time()))
        conn.commit()
    finally:
        conn.close()
    return st


def clear(uid):
    conn = _conn()
    try:
        conn.execute(f"DELETE FROM {_TABLE_NAME} WHERE user_id=?", (int(uid),))
        conn.commit()
    finally:
        conn.close()


def start(uid, name="คุณ", bots=DEFAULT_BOTS, rng=None):
    """เปิดโต๊ะซ้อมกับบอท — ผู้เล่นจริงนั่งที่นั่งแรก"""
    bots = max(1, min(int(bots or 1), E.MAX_PLAYERS - 1))
    st = E.new_game([name] + B.bot_names(bots), rng=rng)
    st["human"] = HUMAN
    _run_bots(st, rng)
    return save(uid, st)


def _run_bots(st, rng=None):
    """ให้บอททุกตัวที่ถึงตาทายจนกว่าจะถึงตาคนจริงหรือเกมจบ

    ทำให้จบในคำขอเดียว เบราว์เซอร์จะได้ไม่ต้องคอยถามซ้ำว่า "บอททายยัง"
    """
    rng = rng or random.Random()
    for _ in range(len(st["players"]) * E.MAX_GUESSES + 2):     # เพดานกันวนไม่รู้จบ
        if st.get("over") or st["turn"] == st["human"]:
            break
        ok, _r = B.take_turn(E, st, rng)
        if not ok:
            break
    return st


def guess(uid, number, rng=None):
    """ทายเลขหนึ่งครั้งของคนจริง แล้วปล่อยบอทเดินต่อ — คืน (ok, ผล)"""
    st = load(uid)
    if not st:
        return False, {"error": "ยังไม่ได้เปิดโต๊ะ — กดเปิดโต๊ะก่อน"}
    if st.get("over"):
        return False, {"error": "เกมนี้จบแล้ว — กดเปิดโต๊ะใหม่ได้เลย"}
    if st["turn"] != st["human"]:
        return False, {"error": "ยังไม่ถึงตาคุณ"}

    ok, r = E.guess(st, number)
    if not ok:
        return False, r
    _run_bots(st, rng)
    save(uid, st)
    return True, {**r, "table": view(uid, st)}


# ── 🔒 ประตูเดียวก่อนส่งขึ้นเว็บ ──

def view(uid, st=None):
    """สถานะที่ส่งขึ้นเบราว์เซอร์ได้ — คัด secret ออกจนกว่าเกมจะจบ"""
    st = st or load(uid)
    if not st:
        return {"playing": False}
    out = {
        "playing": True,
        "turn": st["turn"],
        "my_turn": st["turn"] == st["human"] and not st.get("over"),
        "over": bool(st.get("over")),
        "winner": st.get("winner"),
        "players": [{"name": p["name"], "guesses": len(p["guesses"]),
                     "you": i == st["human"]}
                    for i, p in enumerate(st["players"])],
        "log": st["log"][-12:],
    }
    if st.get("over"):
        out["secret"] = st["secret"]        # ✅ เฉลยได้ก็ต่อเมื่อเกมจบแล้วเท่านั้น
    return out
