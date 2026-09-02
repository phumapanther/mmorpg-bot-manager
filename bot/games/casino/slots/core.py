"""สล็อต — ตรรกะเกม (แยกจาก bot/casino_core.py เดิม, รื้อโครงสร้าง 2026-09-02)

ดึงออกจากปุ่ม Discord เพื่อให้ทั้งบอทและเว็บเรียกชุดเดียวกัน
สูตรตุกติกและเรทจ่ายยกมาจากของเดิมทั้งหมด ห้ามเปลี่ยนตัวเลขโดยไม่ได้ตั้งใจ
"""
import random

import bot.models.player_model as player_model
from bot import config_loader
from bot.games.casino.shared import _take_bet

SLOT_EMOJIS = ["🍒", "🍇", "🍊", "💎", "🔔", "💰"]
DEFAULT_SLOT_WEIGHTS = [30, 25, 20, 10, 10, 5]
TRIPLE_MULT = {"💰": 15, "💎": 10, "🔔": 7}   # นอกนั้น 5
TRIPLE_MULT_DEFAULT = 5
PAIR_MULT = 1.5
MAX_REROLL = 10                               # ล็อคผลได้ไม่เกินนี้ กันวนไม่รู้จบ


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
