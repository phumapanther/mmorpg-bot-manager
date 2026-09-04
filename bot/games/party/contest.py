"""🎲 ทอยเต๋าแข่งกัน — ตรรกะล้วน ไม่แตะ DB ไม่รู้จักการวาดภาพ

เจ้าของเกมสั่ง 2026-09-04: **ทุกการโจมตีต้องทอยแข่งกันสองฝั่ง**
ผู้โจมตีได้มากกว่าหรือเท่า = โดน · น้อยกว่า = พลาด

⚠️ **เกณฑ์ยืมจากเกมหลักเป๊ะ ๆ** — `adventure_core` ใช้ `player_roll >= monster_roll`
   ตั้งเกณฑ์ใหม่เมื่อไหร่ สองโหมดจะตัดสินไม่เหมือนกัน ผู้เล่นงง
   (มีเทสอ่านซอร์สเกมหลักมายืนยันว่ายังใช้เกณฑ์เดิมอยู่)

⚠️ เต๋าฝั่งผู้เล่นใช้ `adventure_core.roll_player_die` ของเดิม
   ซึ่งแยกกติกา "ตีปกติ" กับ "ออกท่า" ไว้แล้ว (ออกท่าเสี่ยงกว่าแต่แตะ 20 ได้)
"""
from bot import adventure_core, config_loader

# สถานะที่มีผลกับแต้มเต๋า — ตัวเลขติดลบคือโดนหักแต้ม
ROLL_PENALTY = {
    "slow": -4,      # ❄️ Frostbolt — ทอยได้น้อยลงหลายตา
}

MONSTER_DIE = 20     # มอนทอย d20 ต่อลูก เหมือนเกมหลัก


def _pen(unit):
    """แต้มที่โดนหักจากสถานะทั้งหมดรวมกัน"""
    fx = unit.get("fx") or {}
    return sum(v for k, v in ROLL_PENALTY.items() if int(fx.get(k) or 0) > 0)


def dice_count(unit):
    """หน่วยนี้ทอยกี่ลูก

    ผู้เล่น: ฐาน 1 + เพิ่มตามเลเวล (ยืมกฎเกมหลัก ทุก `dice.level_per_die` เลเวล)
    มอน: ตาม `dice_count` ของแรงค์ (บอสทอยหลายลูกกว่า)
    """
    if unit.get("side") == "monster":
        return max(1, int((unit.get("stats") or {}).get("dice_count") or 1))
    try:
        per = int(config_loader.get_balance("dice.level_per_die", 25)) or 25
        cap = int(config_loader.get_balance("dice.max_dice", 8))
    except (TypeError, ValueError):
        per, cap = 25, 8
    return max(1, min(cap, 1 + int(unit.get("level") or 1) // per))


def roll_for(unit, rng, skill_used=False):
    """ทอยของหน่วยนี้หนึ่งครั้ง (รวมทุกลูก) แล้วหักแต้มจากสถานะ

    ต่ำสุด 1 เสมอ — สถานะซ้อนกันเยอะ ๆ ต้องไม่ทำให้แต้มติดลบ
    """
    n = dice_count(unit)
    if unit.get("side") == "monster":
        total = sum(rng.randint(1, MONSTER_DIE) for _ in range(n))
    else:
        total = sum(adventure_core.roll_player_die(rng, skill_used=skill_used)
                    for _ in range(n))
    return max(1, total + _pen(unit))


def roll_off(attacker, defender, rng, skill_used=False):
    """ทอยแข่งกันหนึ่งครั้ง — คืน dict ที่ส่งขึ้นหน้าจอได้เลย

    คืน `{atk, def, hit, evaded}`
      hit=True  ผู้โจมตีได้มากกว่าหรือเท่า → โดน
      hit=False → พลาด (ไม่ใช่โดนน้อยลง)

    💨 Evasion กันได้แน่นอนโดยไม่ต้องทอย และใช้แล้วหมดไป
    """
    fx = defender.get("fx")
    if fx and int(fx.get("evade") or 0) > 0:
        fx["evade"] = 0
        return {"atk": 0, "def": 0, "hit": False, "evaded": True}

    atk = roll_for(attacker, rng, skill_used)
    dfn = roll_for(defender, rng)
    return {"atk": atk, "def": dfn, "hit": atk >= dfn, "evaded": False}


def tick_fx(unit):
    """นับถอยหลังสถานะของหน่วยนี้ลง 1 — เรียกตอนจบตาของเจ้าตัว"""
    fx = unit.get("fx")
    if not fx:
        return
    for k in list(fx):
        left = int(fx[k] or 0) - 1
        if left > 0:
            fx[k] = left
        else:
            fx.pop(k, None)
