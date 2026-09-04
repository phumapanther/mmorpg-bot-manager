"""🎭 รางวัลปาร์ตี้ — ทอง · EXP · ดรอป

⚠️ **นี่คือประตูเงินของโหมดนี้ ทองงอกที่นี่ = เงินเฟ้อทั้งเกม**
   แก้ทีหลังยากมากเพราะต้องไปไล่ลดของผู้เล่นที่ได้ไปแล้ว ซึ่งไม่มีใครยอม

กฎเหล็ก 2 ข้อ (เจ้าของเกมเคาะ 2026-09-03):
  1. ทองรวมที่จ่ายออก = **1.5 เท่าของที่ควรได้ตอนเล่นเดี่ยว** แล้วหารกัน
  2. ไอเทมดรอป **ชิ้นเดียวต่อสมรภูมิ ตกที่คนเดียว** (สุ่มว่าใคร)
     — หลังบ้านมี !give ให้กิฟกันเองอยู่แล้ว

⚠️ **ทองคิดจาก "จำนวนคน" ไม่ใช่ "จำนวนมอน"** — เหมือน monsters._budget
   ปาร์ตี้ 2 คนเจอมอน 3 ตัวที่เลือดรวมเท่ามอน 2 ตัว ถ้าจ่ายทอง 3 ตัวเต็ม
   ก็คือพิมพ์เงินฟรี 1.5 ตัวทุกกระดาน
"""
import json

from bot import config_loader
from bot.models import player_model

PARTY_MULT = 1.5

# แรงค์ที่ดรอปของหายากได้ (ตรงกับโหมดเดี่ยว)
RARE_RANKS = ("Secret", "Unbeatable")
RARE_POOL = ("8", "21")
COMMON_POOL = ("9", "10", "11", "12", "13", "14", "15", "16", "17", "18")
BOSS_POOL = COMMON_POOL + ("22", "23", "24", "25", "26", "27", "28",
                           "3", "4", "5", "6", "7")


def monster_gold(m, rng):
    """ทองของมอนตัวเดียว — สูตรเดียวกับโหมดเดี่ยว (ฐานสุ่ม × gold_mult ของแรงค์)"""
    mult = float((m.get("stats") or {}).get("gold_mult") or 1)
    return max(1, int(rng.randint(1, 25) * mult))


def monster_exp(m, rng):
    """EXP ของมอนตัวเดียว — สูตรเดียวกับโหมดเดี่ยว"""
    base = float((m.get("stats") or {}).get("exp_reward") or 10)
    return max(1, int(base + rng.randint(5, 15)))


def encounter_value(monsters, party_size, rng):
    """ทอง+EXP ของสมรภูมินี้ "ถ้าเล่นคนเดียว" — คืน (ทอง, EXP)

    ⚠️ คูณด้วย **จำนวนคน** หารด้วย **จำนวนมอน** เพื่อให้ตรงกับ monsters._budget
       ที่ย่อเลือดมอนลงตามอัตราส่วนเดียวกัน คิดตามจำนวนตัวเมื่อไหร่ = เงินเฟ้อ
    """
    if not monsters:
        return 0, 0
    n = len(monsters)
    size = max(1, int(party_size or 1))
    gold = sum(monster_gold(m, rng) for m in monsters) * size // n
    exp = sum(monster_exp(m, rng) for m in monsters) * size // n
    return int(gold), int(exp)


def split_gold(total_solo, party_size):
    """เพดาน 1.5 เท่า แล้วหารกัน — คืนลิสต์เรียงตามลำดับสมาชิก

    เศษแจกทีละ 1 จนหมด ผลรวมจึงเท่าเพดานพอดีเสมอ ไม่หล่นหายและไม่งอก
    """
    n = max(1, int(party_size or 1))
    pot = max(0, int(int(total_solo) * PARTY_MULT))
    base, extra = divmod(pot, n)
    return [base + (1 if i < extra else 0) for i in range(n)]


def roll_drop(monsters, party, rng):
    """สุ่มดรอป **ชิ้นเดียวต่อสมรภูมิ** ตกที่คนเดียว — คืน dict หรือ None

    ใช้แรงค์สูงสุดในกลุ่มเป็นตัวตัดสินคุณภาพของ (บอสอยู่ในกลุ่ม = มีลุ้นของดี)
    เรทเดียวกับโหมดเดี่ยว (`drops.*` ใน Panel) เพราะกลิ้งครั้งเดียวต่อกระดาน
    """
    party = [str(u) for u in (party or [])]
    if not party or not monsters:
        return None

    ranks = {m.get("rank") for m in monsters}
    item_id = None
    if ranks & set(RARE_RANKS) and \
            rng.randint(1, 100) <= int(config_loader.get_balance("drops.rare_chance", 1)):
        item_id = rng.choice(list(RARE_POOL))
    elif rng.randint(1, 100) <= int(config_loader.get_balance("drops.normal_chance", 70)):
        pool = list(COMMON_POOL if ranks == {"Common"} else BOSS_POOL)
        items = config_loader.get_all_items()
        weights = [100000 / max(1, items.get(i, {}).get("buy", 100)) for i in pool]
        item_id = rng.choices(pool, weights=weights, k=1)[0]

    if not item_id:
        return None
    name = config_loader.get_all_items().get(item_id, {}).get("name", "ไอเทมปริศนา")
    return {"uid": rng.choice(party), "item": str(item_id), "name": name}


def _give_item(uid, item_id):
    """ใส่ของลงกระเป๋า — กระเป๋าเต็มก็ไม่ใส่ (คืน False ให้คนเรียกไปบอกผู้เล่น)"""
    p = player_model.get_player(uid) or {}
    inv = player_model.load_inventory(p.get("inventory", ""))
    cap = int(p.get("capacity") or 0)
    if cap and len(inv) >= cap:
        return False
    inv.append(str(item_id))
    player_model.update_player_field(uid, "inventory", json.dumps(inv))
    return True


def pay(uids, monsters, rng):
    """จ่ายรางวัลให้ทั้งปาร์ตี้จริง ๆ — คืนสรุปที่ส่งขึ้นหน้าเว็บได้เลย

    ⚠️ คนเรียกต้องกันการจ่ายซ้ำเอง (ดู room.settle) ฟังก์ชันนี้จ่ายทุกครั้งที่ถูกเรียก
    """
    uids = [str(u) for u in (uids or [])]
    if not uids:
        return {"gold": {}, "exp": 0, "drop": None}

    total_gold, exp = encounter_value(monsters, len(uids), rng)
    shares = split_gold(total_gold, len(uids))

    paid = {}
    for uid, gold in zip(uids, shares):
        p = player_model.get_player(int(uid)) or {}
        player_model.update_player_field(
            int(uid), "cash", int(p.get("cash") or 0) + int(gold))
        if exp > 0:
            player_model.add_exp(int(uid), int(exp))
        paid[uid] = int(gold)

    drop = roll_drop(monsters, uids, rng)
    if drop and not _give_item(int(drop["uid"]), drop["item"]):
        drop["full_bag"] = True         # กระเป๋าเต็ม — ของหลุดมือ บอกให้รู้
    return {"gold": paid, "exp": int(exp), "drop": drop}
