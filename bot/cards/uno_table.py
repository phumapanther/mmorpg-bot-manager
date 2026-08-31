"""🎰 โต๊ะไพ่รูน — ที่เก็บเกมข้ามคำขอ + ประตูเดียวก่อนส่งขึ้นเว็บ

ขั้นนี้ทำให้ "เล่นกับบอทผ่านหน้าเว็บได้จริง" — ยังไม่มีเดิมพัน ยังไม่มีห้องเพื่อน

🔒 หัวใจของไฟล์นี้: view() คือ **ประตูเดียว** ก่อนส่งอะไรขึ้นเบราว์เซอร์
   ส่งไพ่ในมือคนอื่นลงไปเมื่อไหร่ = เปิด F12 อ่านไพ่คู่แข่งได้หมด เกมจบเลย
   ซ่อนด้วย CSS ไม่นับว่าซ่อน — ต้องไม่ส่งลงไปตั้งแต่แรก
   แบบแผนเดียวกับ match.view() ที่คัดพิกัดกับดักออก (bot/pvp/match.py)

   คนอื่นจะเห็นแค่ "เหลือกี่ใบ" — ไพ่บอทก็ซ่อนเหมือนกัน
   ไม่งั้นคนเปิด DevTools ชนะบอทตลอดกาล
"""
import json
import random
import sqlite3
import time

import bot.models.player_model as player_model
from bot.cards import uno_bot as B
from bot.cards import uno_deck as D
from bot.cards import uno_engine as E

TABLE_MAX_AGE = 60 * 60      # โต๊ะที่ทิ้งไว้เกิน 1 ชม. = ล้างทิ้ง (เหมือนแบล็กแจ็ค)
HUMAN = 0                    # ผู้เล่นจริงนั่งที่นั่งแรกเสมอในโหมดซ้อมกับบอท
DEFAULT_BOTS = 1


# ── ที่เก็บสถานะ (ลอกโครงจาก blackjack_core) ──

def _conn():
    conn = sqlite3.connect(player_model.DB_NAME)
    conn.execute("""CREATE TABLE IF NOT EXISTS uno_tables (
        user_id INTEGER PRIMARY KEY, state TEXT NOT NULL, updated_at REAL NOT NULL)""")
    return conn


def load(uid):
    """โต๊ะที่ค้างอยู่ของคนนี้ — ไม่มี/เก่าเกินไป = None"""
    conn = _conn()
    try:
        row = conn.execute("SELECT state, updated_at FROM uno_tables WHERE user_id=?",
                           (int(uid),)).fetchone()
        if not row:
            return None
        if time.time() - row[1] > TABLE_MAX_AGE:
            conn.execute("DELETE FROM uno_tables WHERE user_id=?", (int(uid),))
            conn.commit()
            return None
        return json.loads(row[0])
    finally:
        conn.close()


def save(uid, st):
    conn = _conn()
    try:
        conn.execute("INSERT OR REPLACE INTO uno_tables (user_id, state, updated_at) "
                     "VALUES (?,?,?)", (int(uid), json.dumps(st), time.time()))
        conn.commit()
    finally:
        conn.close()
    return st


def clear(uid):
    conn = _conn()
    try:
        conn.execute("DELETE FROM uno_tables WHERE user_id=?", (int(uid),))
        conn.commit()
    finally:
        conn.close()


# ── เปิดโต๊ะ / เล่น ──

def start(uid, name="คุณ", bots=DEFAULT_BOTS, rng=None):
    """เปิดโต๊ะซ้อมกับบอท — ผู้เล่นจริงนั่งที่นั่งแรก"""
    bots = max(1, min(int(bots or 1), E.MAX_PLAYERS - 1))
    st = E.new_game([name] + B.bot_names(bots), rng=rng)
    st["human"] = HUMAN
    _run_bots(st, rng)
    return save(uid, st)


def _run_bots(st, rng=None):
    """ให้บอททุกตัวที่ถึงตาเล่นจนกว่าจะถึงตาคนจริง

    ทำให้จบในคำขอเดียว เบราว์เซอร์จะได้ไม่ต้องคอยถามซ้ำว่า "บอทเดินยัง"
    (แบบเดียวกับ match.end_turn ในสนามรบผลัดเทิร์น)
    """
    rng = rng or random.Random()
    moves = []
    for _ in range(len(st["players"]) * 40):     # เพดานกันวนไม่รู้จบ
        if st["winner"] is not None or st["turn"] == st["human"]:
            break
        before = len(st["log"])
        ok, _ = B.take_turn(E, st, rng)
        if not ok:
            break
        moves += st["log"][before:]
    return moves


def _act(uid, fn, rng=None):
    """ทำท่าหนึ่งของคนจริง แล้วปล่อยบอทเดินต่อ — คืน (ok, ผล)"""
    st = load(uid)
    if not st:
        return False, {"error": "ยังไม่ได้เปิดโต๊ะ — กดเปิดโต๊ะก่อน"}
    if st["winner"] is not None:
        return False, {"error": "เกมนี้จบแล้ว — กดเปิดโต๊ะใหม่ได้เลย"}
    if st["turn"] != st["human"]:
        return False, {"error": "ยังไม่ถึงตาคุณ"}

    ok, r = fn(st)
    if not ok:
        return False, r
    _run_bots(st, rng)
    save(uid, st)
    return True, {**r, "table": view(uid, st)}


def play(uid, index, suit=None, rng=None):
    return _act(uid, lambda st: E.play(st, int(index), chosen_suit=suit, rng=rng), rng)


def draw(uid, rng=None):
    return _act(uid, lambda st: E.draw(st, rng), rng)


def take_stack(uid, rng=None):
    return _act(uid, lambda st: E.take_stack(st, rng), rng)


def passes(uid, rng=None):
    return _act(uid, lambda st: E.passes(st), rng)


def say_uno(uid):
    st = load(uid)
    if not st:
        return False, {"error": "ยังไม่ได้เปิดโต๊ะ"}
    ok, r = E.say_uno(st, st["human"])
    if ok:
        save(uid, st)
    return ok, ({**r, "table": view(uid, st)} if ok else r)


# ── 🔒 ประตูเดียวก่อนส่งขึ้นเว็บ ──

def view(uid, st=None):
    """สถานะที่ส่งขึ้นเบราว์เซอร์ได้ — คัดไพ่ในมือคนอื่นออกเสมอ

    ⚠️ ห้ามส่ง st["players"][i]["hand"] ของคนอื่น และห้ามส่ง st["deck"]
       (ลำดับกองจั่ว = รู้ล่วงหน้าว่าจะจั่วได้อะไร)
    """
    st = st or load(uid)
    if not st:
        return {"playing": False}
    me = st["human"]
    top = E.top_card(st)
    return {
        "playing": True,
        "hand": st["players"][me]["hand"],          # ✅ มือตัวเองเท่านั้น
        "playable": [i for i, c in enumerate(st["players"][me]["hand"])
                     if c in E.playable_now(st, me)] if st["turn"] == me else [],
        "top": top,
        "top_label": D.label(top),
        "suit": st["suit"],
        "suits": {k: v["label"] for k, v in D.SUITS.items()},
        "turn": st["turn"],
        "my_turn": st["turn"] == me and st["winner"] is None,
        "dir": st["dir"],
        "stack": st["stack"],
        "stack_kind": st["stack_kind"],
        "must_answer": E.must_answer_stack(st) and st["turn"] == me,
        "drew": st["drew"],
        "deck_left": len(st["deck"]),               # จำนวนเท่านั้น ไม่ใช่ตัวไพ่
        "players": [{"name": p["name"], "cards": len(p["hand"]),   # ✅ แค่จำนวน
                     "you": i == me, "said_uno": p["said_uno"]}
                    for i, p in enumerate(st["players"])],
        "winner": st["winner"],
        "winner_name": (st["players"][st["winner"]]["name"]
                        if st["winner"] is not None else ""),
        "score": E.score(st),
        "log": st["log"][-12:],
    }
