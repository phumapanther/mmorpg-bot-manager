"""ไฮโล — ตรรกะเกม (แยกจาก bot/casino_core.py เดิม, รื้อโครงสร้าง 2026-09-02)

ดึงออกจากปุ่ม Discord เพื่อให้ทั้งบอทและเว็บเรียกชุดเดียวกัน
สูตรตุกติกและเรทจ่ายยกมาจากของเดิมทั้งหมด ห้ามเปลี่ยนตัวเลขโดยไม่ได้ตั้งใจ
"""
import random

import bot.models.player_model as player_model
from bot.games.casino.shared import _take_bet

MAX_REROLL = 10                               # ล็อคผลได้ไม่เกินนี้ กันวนไม่รู้จบ


def hilo_rig_chance(bet):
    """โอกาสเจ้ามือล็อคผลไม่ให้ชนะ — ยิ่งเดิมพันสูงยิ่งเยอะ (เพดาน 85%)"""
    return min(0.85, (bet / 10000.0) * 0.15)


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
