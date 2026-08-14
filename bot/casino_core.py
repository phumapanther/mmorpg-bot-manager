"""ตรรกะคาสิโนกลาง (เว็บเกม เฟส 3.1) — ไฮโล + สล็อต

ดึงออกจากปุ่ม Discord เพื่อให้ทั้งบอทและเว็บเรียกชุดเดียวกัน
สูตรตุกติกและเรทจ่ายยกมาจากของเดิมทั้งหมด ห้ามเปลี่ยนตัวเลขโดยไม่ได้ตั้งใจ

หมายเหตุ: แบล็กแจ็ค 24 ยังไม่อยู่ที่นี่ เพราะเป็นเกมหลายเทิร์นที่เก็บสถานะกอง
ไพ่ไว้ใน View (ต้องออกแบบที่เก็บสถานะข้ามคำขอก่อน) — ระบบตุกติกของมันอยู่ที่
`bot/cogs/blackjack.py` (rig_chance_for / stack_bot_hand) ซึ่งเป็นฟังก์ชันล้วนอยู่แล้ว
"""
import random

import bot.models.player_model as player_model
from bot import config_loader

SLOT_EMOJIS = ["🍒", "🍇", "🍊", "💎", "🔔", "💰"]
DEFAULT_SLOT_WEIGHTS = [30, 25, 20, 10, 10, 5]
TRIPLE_MULT = {"💰": 15, "💎": 10, "🔔": 7}   # นอกนั้น 5
TRIPLE_MULT_DEFAULT = 5
PAIR_MULT = 1.5
MAX_REROLL = 10                               # ล็อคผลได้ไม่เกินนี้ กันวนไม่รู้จบ


def hilo_rig_chance(bet):
    """โอกาสเจ้ามือล็อคผลไม่ให้ชนะ — ยิ่งเดิมพันสูงยิ่งเยอะ (เพดาน 85%)"""
    return min(0.85, (bet / 10000.0) * 0.15)


def slots_rig_chance(bet):
    """เหมือนไฮโลแต่เพดาน 90%"""
    return min(0.90, (bet / 10000.0) * 0.15)


def slot_weights():
    """น้ำหนักสัญลักษณ์ที่ตั้งได้ที่ Panel — ตั้งไม่ครบ 6 ช่องหรือเพี้ยน = ใช้ของเดิม"""
    w = config_loader.get_balance("casino.slot_weights", DEFAULT_SLOT_WEIGHTS)
    try:
        w = [max(1, int(x)) for x in w]
        if len(w) != len(SLOT_EMOJIS):
            return list(DEFAULT_SLOT_WEIGHTS)
        return w
    except (TypeError, ValueError):
        return list(DEFAULT_SLOT_WEIGHTS)


def _hilo_result(d1, d2, d3):
    total = d1 + d2 + d3
    return total, ("11hilo" if total == 11 else ("low" if total <= 10 else "high"))


def roll_hilo(choice, bet, rng=random):
    """ทอยเต๋าไฮโล 3 ลูก — คืนผลดิบ (ยังไม่ยุ่งกับเงิน)"""
    rigged = rng.random() < hilo_rig_chance(bet)
    d1, d2, d3 = rng.randint(1, 6), rng.randint(1, 6), rng.randint(1, 6)
    total, result = _hilo_result(d1, d2, d3)

    # ตุกติก: ทายถูกเมื่อไหร่ ทอยใหม่จนกว่าจะไม่ถูก (ไม่เกิน 10 ครั้ง)
    if rigged and choice == result:
        for _ in range(MAX_REROLL):
            d1, d2, d3 = rng.randint(1, 6), rng.randint(1, 6), rng.randint(1, 6)
            total, result = _hilo_result(d1, d2, d3)
            if choice != result:
                break

    return {"dice": [d1, d2, d3], "total": total, "result": result,
            "rigged": rigged, "won": choice == result}


def spin_slots(bet, rng=random):
    """หมุนสล็อต 3 วง — คืนผลดิบ (ยังไม่ยุ่งกับเงิน)"""
    weights = slot_weights()
    rigged = rng.random() < slots_rig_chance(bet)
    pick = lambda: rng.choices(SLOT_EMOJIS, weights=weights)[0]
    any_match = lambda a, b, c: a == b or b == c or a == c

    r = [pick(), pick(), pick()]
    if rigged and any_match(*r):
        for _ in range(MAX_REROLL):
            r = [pick(), pick(), pick()]
            if not any_match(*r):
                break
    return {"reels": r, "rigged": rigged}


def slots_multiplier(reels):
    """ตัวคูณรางวัลจากหน้าวง — 0 = ไม่ถูกอะไรเลย"""
    a, b, c = reels
    if a == b == c:
        return TRIPLE_MULT.get(a, TRIPLE_MULT_DEFAULT)
    if a == b or b == c or a == c:
        return PAIR_MULT
    return 0


def _take_bet(user_id, bet):
    """ตรวจและหักเงินเดิมพัน — คืน (ok, ข้อความผิดพลาด)"""
    if bet <= 0:
        return False, "❌ เดิมพันต้องมากกว่า 0 ทอง!"
    player = player_model.get_player(user_id)
    if not player:
        return False, "❌ ไม่พบข้อมูลตัวละครของคุณ!"
    if player.get("cash", 0) < bet:
        return False, "❌ เงินในกระเป๋าของคุณไม่พอ!"
    player_model.increment_player_field(user_id, "cash", -bet)
    return True, ""


def play_hilo(user_id, choice, bet, rng=random):
    """เล่นไฮโลหนึ่งตา — หักเงิน ทอย จ่ายรางวัล คืน (ok, ผลลัพธ์)

    ชนะสูง/ต่ำ = คืน 2 เท่า | ชนะ 11 ไฮโล = คืน 7 เท่า (เงินเดิมพันหักไปแล้ว)
    """
    if choice not in ("high", "low", "11hilo"):
        return False, {"message": "❌ ต้องเลือก สูง / ต่ำ / 11 ไฮโล เท่านั้น"}
    ok, err = _take_bet(user_id, bet)
    if not ok:
        return False, {"message": err}

    out = roll_hilo(choice, bet, rng)
    winnings = 0
    if out["won"]:
        winnings = bet * (7 if choice == "11hilo" else 2)
        player_model.increment_player_field(user_id, "cash", winnings)

    out.update({"bet": bet, "choice": choice, "winnings": winnings,
                "net": winnings - bet,
                "message": (f"🎉 แจ็คพอตแตก!! 11 ไฮโล!! ได้รับ `{winnings:,}` ทอง!"
                            if out["won"] and choice == "11hilo" else
                            f"✅ คุณชนะ! รับไป `{winnings:,}` ทอง!" if out["won"] else
                            f"❌ คุณแพ้! เสีย `{bet:,}` ทอง")})
    print(f"[LOG] [HILO] {user_id} แทง {choice} เดิมพัน {bet:,} → "
          f"{out['dice']} รวม {out['total']} = {out['result']} "
          f"{'(ตุกติก)' if out['rigged'] else ''} สุทธิ {out['net']:+,}")
    return True, out


def play_slots(user_id, bet, rng=random):
    """หมุนสล็อตหนึ่งครั้ง — หักเงิน หมุน จ่ายรางวัล คืน (ok, ผลลัพธ์)"""
    ok, err = _take_bet(user_id, bet)
    if not ok:
        return False, {"message": err}

    out = spin_slots(bet, rng)
    mult = slots_multiplier(out["reels"])
    winnings = int(bet * mult)
    if winnings:
        player_model.increment_player_field(user_id, "cash", winnings)

    a, b, c = out["reels"]
    if a == b == c:
        msg = f"🎉 แจ็คพอต!! ตรงกัน 3 ตัว! รับ `{winnings:,}` ทอง (×{mult})"
    elif mult:
        msg = f"✨ เกือบแจ็คพอต! ตรงกัน 2 ตัว รับ `{winnings:,}` ทอง (×{mult})"
    else:
        msg = f"❌ เสียใจด้วย! คุณเสีย `{bet:,}` ทอง"

    out.update({"bet": bet, "multiplier": mult, "winnings": winnings,
                "net": winnings - bet, "message": msg})
    print(f"[LOG] [SLOTS] {user_id} เดิมพัน {bet:,} → {' '.join(out['reels'])} "
          f"×{mult} {'(ตุกติก)' if out['rigged'] else ''} สุทธิ {out['net']:+,}")
    return True, out
