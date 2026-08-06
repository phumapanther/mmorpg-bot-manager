"""ระบบโจรปล้น (spec 2026-08-06) — ยิ่งรวยยิ่งตกเป็นเป้า กันได้ด้วยบัตรประกันจากร้านหมู่บ้าน

ทุกขั้นตั้งได้ที่ Panel (robbery.*) รูปแบบ [เพดานเงิน, ค่า] ขั้นสุดท้าย null = ไม่จำกัด
ตั้งเพี้ยน = ตกกลับค่าในโค้ด เกมต้องไม่พังเพราะพิมพ์ผิดในพาแนล
"""
import random

from bot import config_loader, game_modifiers

ROBBERY_MIN = 1_000_000   # เริ่มมีสิทธิ์โดน: เงินติดตัวหรือธนาคาร "เกินล้าน"

# โอกาสเจอโจรต่อก้าว (%) ตามเงินรวมติดตัว+ธนาคาร
_CHANCE_TIERS = [[1_000_000, 0], [10_000_000, 10], [100_000_000, 25], [1_000_000_000, 50], [None, 100]]
# โอกาสชนะตอนเลือกสู้ (%) — เงินยิ่งเยอะยิ่งถ่วงแข้งขา
_MUG_WIN_TIERS = [[10_000_000, 50], [100_000_000, 35], [1_000_000_000, 20], [None, 10]]
# ปล้นธนาคาร: [ยอดขั้นต่ำ, เหลือเท่าไหร่] ไล่จากรวยสุด — ต่ำกว่าขั้นแรกสุดหัก 50%
_BANK_FLOORS = [[1_000_000_000, 10_000], [100_000_000, 100_000], [10_000_000, 1_000_000]]


def _valid(tiers):
    return (isinstance(tiers, list) and tiers
            and all(isinstance(t, (list, tuple)) and len(t) == 2 for t in tiers))


def _tiered(amount, key, default_tiers):
    tiers = config_loader.get_balance(key, None)
    if not _valid(tiers):
        tiers = default_tiers
    for limit, val in tiers:
        if limit is None or amount < int(limit):
            return int(val)
    return int(tiers[-1][1])


def robbery_chance(total_wealth):
    """% โอกาสเจอโจรต่อก้าว"""
    return _tiered(total_wealth, "robbery.chance_tiers", _CHANCE_TIERS)


def mug_win_chance(total_wealth):
    """% โอกาสชนะเมื่อเลือกสู้กับโจรดักปล้น"""
    return _tiered(total_wealth, "robbery.mug_win_tiers", _MUG_WIN_TIERS)


def insured(statuses, total_wealth):
    """มีบัตรประกันที่ยังคุ้มครองไหม — เงินรวมเกินเพดานบัตร = ใบนั้นไม่ช่วย"""
    for key in statuses or {}:
        cfg = game_modifiers.STATUS_EFFECTS.get(key, {})
        if "insurance_cap" not in cfg:
            continue
        cap = cfg["insurance_cap"]
        if cap is None or total_wealth < int(cap):
            return True
    return False


def roll_robbery(cash, bank, statuses, rng=random):
    """ทอยต่อก้าวเดิน: คืน None | "bank_robbery" | "mugging" """
    cash, bank = int(cash or 0), int(bank or 0)
    hit_bank, hit_cash = bank > ROBBERY_MIN, cash > ROBBERY_MIN
    if not (hit_bank or hit_cash):
        return None
    total = cash + bank
    if insured(statuses, total):
        return None
    if rng.random() * 100 >= robbery_chance(total):
        return None
    if hit_bank and hit_cash:
        return rng.choice(["bank_robbery", "mugging"])
    return "bank_robbery" if hit_bank else "mugging"


def bank_rob_left(bank):
    """ยอดธนาคารที่เหลือหลังโดนปล้น (10ล้าน→เหลือ 1ล้าน, 100ล้าน→1แสน, 1000ล้าน→1หมื่น, ต่ำกว่านั้นหัก 50%)"""
    b = int(bank or 0)
    floors = config_loader.get_balance("robbery.bank_floors", None)
    if not _valid(floors):
        floors = _BANK_FLOORS
    for threshold, left in floors:
        if b >= int(threshold):
            return min(b, int(left))
    return b // 2


# ── 🎒 ขโมยของแพงในกระเป๋า (ส่วนขยาย 2026-08-06) ──
# โอกาสทอยติดต่อเหตุการณ์ปล้น (%) ตามขั้นความรวยเดิม — ติดแล้วหยิบ 1-2 ชิ้นจาก top 5 ของแพงสุด
_STEAL_TIERS = [[1_000_000, 0], [10_000_000, 10], [100_000_000, 20], [1_000_000_000, 30], [None, 40]]


def steal_chance(total_wealth):
    """% โอกาสโจรฉกของแพงในกระเป๋า ต่อเหตุการณ์ปล้นหนึ่งครั้ง"""
    return _tiered(total_wealth, "robbery.steal_tiers", _STEAL_TIERS)


def roll_item_theft(inventory, total_wealth, item_catalog, rng=random):
    """ทอยขโมยของ: คืนลิสต์ index ในกระเป๋าที่โดนหยิบ (ว่าง = รอด)

    มูลค่าไอเทมวัดจากราคาซื้อ (buy) — เรียง top 5 แล้วสุ่มหยิบ 1-2 ชิ้น
    """
    if not inventory:
        return []
    if rng.random() * 100 >= steal_chance(total_wealth):
        return []
    ranked = sorted(range(len(inventory)),
                    key=lambda i: int(item_catalog.get(str(inventory[i]), {}).get("buy", 0) or 0),
                    reverse=True)[:5]
    ranked = [i for i in ranked
              if int(item_catalog.get(str(inventory[i]), {}).get("buy", 0) or 0) > 0]
    if not ranked:
        return []
    return rng.sample(ranked, min(len(ranked), rng.randint(1, 2)))
