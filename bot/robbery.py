"""ระบบโจรปล้น (spec 2026-08-06) — ยิ่งรวยยิ่งตกเป็นเป้า กันได้ด้วยบัตรประกันจากร้านหมู่บ้าน

ทุกขั้นตั้งได้ที่ Panel (robbery.*) รูปแบบ [เพดานเงิน, ค่า] ขั้นสุดท้าย null = ไม่จำกัด
ตั้งเพี้ยน = ตกกลับค่าในโค้ด เกมต้องไม่พังเพราะพิมพ์ผิดในพาแนล
"""
import json
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


def apply_item_theft(user_id, player=None):
    """🎒 โจรฉกของแพง (spec 2026-08-06): ทอยครั้งเดียวต่อเหตุการณ์ปล้น — คืนข้อความแจ้ง ('' = รอด)

    หยิบ 1-2 ชิ้นจาก top 5 ของแพงสุดในกระเป๋า (มูลค่า = ราคาซื้อ) โอกาสตามขั้นความรวย
    """
    from bot.models import player_model
    player = player or player_model.get_player(user_id) or {}
    inv = player_model.load_inventory(player.get("inventory", ""))
    total = int(player.get("cash", 0) or 0) + int(player.get("bank", 0) or 0)
    catalog = config_loader.get_all_items()
    taken = roll_item_theft(inv, total, catalog)
    if not taken:
        return ""
    names = []
    for i in sorted(taken, reverse=True):
        iid = inv.pop(i)
        names.append(catalog.get(str(iid), {}).get("name", f"ไอเทม {iid}"))
    player_model.update_player_field(user_id, "inventory", json.dumps(inv))
    print(f"[LOG] [ROBBERY] 🎒 ผู้เล่น {user_id} โดนฉกของแพง: {', '.join(names)}")
    return f"\n🎒💨 **โจรฉกของแพงในกระเป๋าไปด้วย:** {', '.join(names)}!"


def resolve_bank_robbery(user_id, player=None):
    """🏦💥 ปล้นธนาคาร — เหตุการณ์ทันที ไม่มีให้เลือก คืน dict ผลลัพธ์ (ใช้ทั้งดิสและเว็บ)"""
    from bot.models import player_model
    player = player or player_model.get_player(user_id) or {}
    bank = int(player.get("bank", 0) or 0)
    left = bank_rob_left(bank)
    player_model.update_player_field(user_id, "bank", left)
    theft = apply_item_theft(user_id, player)      # ทอยฉกของจากความรวย "ก่อน" โดนปล้น
    print(f"[LOG] [ROBBERY] 🏦 ผู้เล่น {user_id} โดนปล้นธนาคาร -{bank - left:,} ทอง (เหลือ {left:,})")
    return {"lost": bank - left, "left": left, "theft": theft}


def resolve_mugging(user_id, action, rng=random):
    """🥷 ตัดสินผลดักปล้น — action: fight | flee (หมดเวลาในดิสนับเป็น flee)

    คืน dict {won, lost, gain, cash, win_pct, roll, theft} — ผู้เรียกเอาไปแต่งข้อความเอง
    """
    from bot.models import player_model
    player = player_model.get_player(user_id) or {}
    cash = int(player.get("cash", 0) or 0)
    win_pct = mug_win_chance(cash + int(player.get("bank", 0) or 0))
    out = {"won": False, "lost": 0, "gain": 0, "win_pct": win_pct, "roll": 0}

    if action == "flee":
        out["lost"] = cash // 2
        player_model.update_player_field(user_id, "cash", cash - out["lost"])
    else:
        out["roll"] = rng.randint(1, 100)
        out["won"] = out["roll"] <= win_pct
        if out["won"]:
            out["gain"] = cash // 10
            player_model.update_player_field(user_id, "cash", cash + out["gain"])
        else:
            out["lost"] = cash
            player_model.update_player_field(user_id, "cash", 0)

    player_model.update_player_field(user_id, "current_state", "idle")
    out["cash"] = int((player_model.get_player(user_id) or {}).get("cash", 0) or 0)
    out["theft"] = apply_item_theft(user_id)
    print(f"[LOG] [MUGGING] {'⚔️' if action == 'fight' else '🏃'} ผู้เล่น {user_id} "
          f"{action} (ชนะ {win_pct}% ทอย {out['roll']}) → เหลือ {out['cash']:,} ทอง")
    return out
