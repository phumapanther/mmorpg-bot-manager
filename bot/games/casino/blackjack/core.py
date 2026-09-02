"""ตรรกะแบล็กแจ็ค 24 กลาง (เว็บเกม เฟส 3.4)

ต่างจากไฮโล/สล็อตตรงที่เป็นเกมหลายเทิร์น — กองไพ่กับมือต้องอยู่ข้ามคำขอ
เดิมเก็บไว้ในอ็อบเจ็กต์ View ของ Discord (อยู่ในหน่วยความจำบอท) เว็บจึงใช้ไม่ได้
ตอนนี้ย้ายมาเก็บใน game_data.db → เริ่มมือในดิสแล้วไปเล่นต่อบนเว็บได้ (กติกาสองแพลตฟอร์ม)

สูตรตุกติกและเรทจ่ายยกมาจากของเดิมทั้งหมด
"""
import json
import random
import sqlite3
import time

import bot.models.player_model as player_model
from bot import config_loader

BUST = 24                    # เกินแต้มนี้ = แตก
RANKS = ['A', '2', '3', '4', '5', '6', '7', '8', '9', '10', 'J', 'Q', 'K']
VALUES = {'A': 1, '2': 2, '3': 3, '4': 4, '5': 5, '6': 6, '7': 7, '8': 8, '9': 9,
          '10': 10, 'J': 10, 'Q': 10, 'K': 10}
GAME_MAX_AGE = 60 * 60       # มือค้างเกิน 1 ชม. = ทิ้ง (เปิดโต๊ะแล้วหายไปเลย)

# ── ระบบเจ้ามือตุกติก (spec 2026-08-06) ──
_RIG_TIERS = [[100_000, 90], [10_000, 70], [1_000, 60]]   # [เดิมพันขั้นต่ำ, โอกาสล็อคไพ่ %]


def rig_chance_for(bet):
    """โอกาสที่เจ้ามือจะล็อคไพ่ให้ชนะตานี้ — ตั้งขั้นได้ที่ Panel (blackjack.rig_tiers)"""
    tiers = config_loader.get_balance("blackjack.rig_tiers", None)
    if not (isinstance(tiers, list) and tiers
            and all(isinstance(t, (list, tuple)) and len(t) == 2 for t in tiers)):
        tiers = _RIG_TIERS
    for threshold, pct in tiers:
        if bet >= int(threshold):
            return int(pct) / 100.0
    return 0.0


def stack_bot_hand(deck, bot_hand, p_score):
    """ล็อคไพ่: บอทเลือกใบจากกองเองให้แต้มชนะผู้เล่น (ผู้เล่นได้ 24 พอดี = ล็อคเสมอ)
    คืนลิสต์ไพ่ที่จั่วไปแสดงใน log ของเกม"""
    drawn = []
    target = min(p_score + 1, BUST)
    while score(bot_hand) < target:
        b = score(bot_hand)
        need, room = target - b, BUST - b
        idx = next((i for i, c in enumerate(deck) if need <= c[1] <= room), None)
        if idx is None:
            fits = [i for i, c in enumerate(deck) if c[1] <= room]
            if not fits:
                break
            idx = max(fits, key=lambda i: deck[i][1])
        card = deck.pop(idx)
        bot_hand.append(card)
        drawn.append(card)
    return drawn


def new_deck(rng=random):
    deck = [[r, VALUES[r]] for r in RANKS for _ in range(4)]
    rng.shuffle(deck)
    return deck


def score(hand):
    return sum(c[1] for c in hand)


# ── ที่เก็บสถานะมือที่กำลังเล่น ──

def _conn():
    conn = sqlite3.connect(player_model.DB_NAME)
    conn.execute("""CREATE TABLE IF NOT EXISTS blackjack_games (
        user_id INTEGER PRIMARY KEY, state TEXT NOT NULL, updated_at REAL NOT NULL)""")
    return conn


def load_game(user_id):
    """มือที่ค้างอยู่ของผู้เล่นคนนี้ — ไม่มี/เก่าเกินไป = None"""
    conn = _conn()
    try:
        row = conn.execute("SELECT state, updated_at FROM blackjack_games WHERE user_id=?",
                           (int(user_id),)).fetchone()
        if not row:
            return None
        if time.time() - row[1] > GAME_MAX_AGE:
            conn.execute("DELETE FROM blackjack_games WHERE user_id=?", (int(user_id),))
            conn.commit()
            return None
        return json.loads(row[0])
    finally:
        conn.close()


def _save_game(user_id, state):
    conn = _conn()
    try:
        conn.execute("INSERT OR REPLACE INTO blackjack_games (user_id, state, updated_at) "
                     "VALUES (?,?,?)", (int(user_id), json.dumps(state), time.time()))
        conn.commit()
    finally:
        conn.close()


def clear_game(user_id):
    conn = _conn()
    try:
        conn.execute("DELETE FROM blackjack_games WHERE user_id=?", (int(user_id),))
        conn.commit()
    finally:
        conn.close()


def _view(state, over=False):
    """สภาพโต๊ะที่ส่งให้ผู้เล่นเห็น — ยังไม่จบเกมต้องซ่อนไพ่ใบที่สองของบอท"""
    out = {"bet": state["bet"],
           "player": state["player"], "player_score": score(state["player"]),
           "over": over}
    if over:
        out["bot"] = state["bot"]
        out["bot_score"] = score(state["bot"])
    else:
        out["bot"] = [state["bot"][0], ["?", 0]]
        out["bot_score"] = None
    return out


def _brain():
    from bot.controller.bot_brain import BlackjackBot
    return BlackjackBot()


def _save_brain(brain):
    try:
        from bot.controller import db_manager
        db_manager.save_bot_memory(json.dumps(brain.q_table), 'AlphaBot')
    except Exception as e:
        print(f"[ERROR] [ML_TRAIN] ⚠️ ไม่สามารถบันทึกความจำบอทได้: {e}")


# ── การกระทำในเกม ──

def start(user_id, bet, rng=random):
    """เปิดโต๊ะใหม่ — หักเงินเดิมพัน แจกไพ่ คืน (ok, สภาพโต๊ะ|ข้อความ)"""
    if bet <= 0:
        return False, {"message": "❌ เดิมพันต้องมากกว่า 0 ทอง!"}
    if load_game(user_id):
        return False, {"message": "❌ คุณมีโต๊ะที่ยังเล่นค้างอยู่ — เล่นให้จบก่อน"}

    player = player_model.get_player(user_id)
    if not player:
        return False, {"message": "❌ ไม่พบข้อมูลตัวละครของคุณ!"}
    if player.get("cash", 0) < bet:
        return False, {"message": "❌ เงินในกระเป๋าของคุณไม่พอ!"}

    player_model.increment_player_field(user_id, "cash", -bet)
    deck = new_deck(rng)
    state = {"bet": bet, "deck": deck,
             "player": [deck.pop(), deck.pop()], "bot": [deck.pop(), deck.pop()],
             "rigged": rng.random() < rig_chance_for(bet)}
    _save_game(user_id, state)
    print(f"[LOG] [BJ24_START] 🃏 เปิดโต๊ะให้ {user_id} | เดิมพัน {bet:,}"
          f"{' (ตุกติก)' if state['rigged'] else ''}")
    return True, _view(state)


def hit(user_id):
    """ผู้เล่นจั่วไพ่ — แตกเมื่อไหร่จบเกมทันที"""
    state = load_game(user_id)
    if not state:
        return False, {"message": "❌ ไม่มีโต๊ะที่กำลังเล่นอยู่"}

    card = state["deck"].pop()
    state["player"].append(card)
    p = score(state["player"])
    print(f"[LOG] [BJ24_HIT] {user_id} จั่วได้ [{card[0]}] แต้มรวม {p}")

    if p > BUST:
        brain = _brain()
        brain.learn(f"{score(state['bot'])}-{state['player'][0][1]}", "!c", 1)   # บอทได้รางวัล
        _save_brain(brain)
        clear_game(user_id)
        out = _view(state, over=True)
        out.update({"result": "bust", "winnings": 0, "net": -state["bet"],
                    "message": f"💥 เกิน {BUST}! (Bust) คุณแพ้และเสียเงินเดิมพัน "
                               f"`{state['bet']:,}` ทอง"})
        return True, out

    _save_game(user_id, state)
    return True, _view(state)


def stand(user_id):
    """ผู้เล่นหยุด — ถึงตาบอท แล้วตัดสินแพ้ชนะ"""
    state = load_game(user_id)
    if not state:
        return False, {"message": "❌ ไม่มีโต๊ะที่กำลังเล่นอยู่"}

    p = score(state["player"])
    bet = state["bet"]
    log, history = [], []

    if state["rigged"]:
        # 😈 ตุกติก: บอทเลือกไพ่เอาชนะเอง — ข้าม ML และไม่สอนสมองตานี้
        print(f"[LOG] [BJ24_RIG] 😈 ล็อคไพ่เอาชนะ {user_id} (เดิมพัน {bet:,})")
        for card in stack_bot_hand(state["deck"], state["bot"], p):
            log.append(f"🤖 บอทจั่วได้ไพ่ [{card[0]}]")
        log.append("🤖 บอทพอแค่นี้!")
        brain = None
    else:
        brain = _brain()
        while True:
            b = score(state["bot"])
            if b > BUST:
                break
            action = brain.get_action(b, state["player"][0][1])
            history.append((b, action))
            if action == "!hit":
                card = state["deck"].pop()
                state["bot"].append(card)
                log.append(f"🤖 บอทจั่วได้ไพ่ [{card[0]}]")
            else:
                log.append("🤖 บอทพอแค่นี้!")
                break

    b = score(state["bot"])
    if b > BUST or (p <= BUST and p > b):
        result, reward, winnings = "win", -1, bet * 2
        msg = f"🏆 คุณชนะ! รับเงินรางวัล `{winnings:,}` ทอง"
    elif p < b:
        result, reward, winnings = "lose", 1, 0
        msg = "❌ บอทชนะ! บอทแต้มสูงกว่า คุณเสียเงินเดิมพัน"
    else:
        result, reward, winnings = "draw", 0.1, bet
        msg = f"🤝 เสมอ! คืนเงินทุน `{winnings:,}` ทอง"

    if winnings:
        player_model.increment_player_field(user_id, "cash", winnings)

    if brain and history:                      # ตาตุกติกไม่สอนสมอง (จะทำ Q-Table เพี้ยน)
        dealer_up = state["bot"][0][1]
        for s, act in history:
            brain.learn(f"{s}-{dealer_up}", act, reward)
        _save_brain(brain)

    clear_game(user_id)
    out = _view(state, over=True)
    out.update({"result": result, "winnings": winnings, "net": winnings - bet,
                "bot_log": log, "message": msg})
    print(f"[LOG] [BJ24_RESULT] {user_id} ผู้เล่น {p} vs บอท {b} → {result} สุทธิ {winnings - bet:+,}")
    return True, out
