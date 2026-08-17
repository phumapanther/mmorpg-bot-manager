# 👗 ระบบแฟชั่น — เปลี่ยนแค่การแสดงผล ไม่แตะค่าต่อสู้สักตัว
#
# กติกาเหล็ก: แฟชั่นห้ามบวก/ลบค่าอะไรทั้งสิ้น ใส่เท่ ๆ อย่างเดียว
# (มีเทสบังคับใน tests/test_fashion.py — ใส่/ถอดแล้วค่าต่อสู้ต้องเท่าเดิมเป๊ะ)
#
# ของจริงที่ใส่อยู่ไม่ขยับเลย เกราะเหล็กยังเป็นเกราะเหล็ก ค่าป้องกัน/ความคงทนเหมือนเดิม
# แค่ "วาดออกมาเป็นชุดอื่น" — ตัววาดอยู่ที่ license_server/web_static/sprite.js
#
# ที่มาของแฟชั่น: กาชาแฟชั่นเท่านั้น (จ่ายด้วยทอง — ดูท้ายไฟล์)
# เปิดแจกชุดเปิดตัวฟรีชั่วคราวได้ที่ balance fashion.free_starter_sets (ตอนนี้ปิดแล้ว)
import datetime
import json
import random

import bot.models.player_model as player_model
from bot import config_loader

# ช่องใส่แฟชั่น — เพิ่มประเภทใหม่ที่นี่ที่เดียว (pet/ui รอทำทีหลัง)
SLOTS = ("outfit", "weapon", "aura")

# ตู้แฟชั่นทั้งหมด · key ต้องตรงกับตาราง FASHION_* ใน sprite.js (มีเทสคุมว่าตรงกัน)
CATALOG = {
    # ── ✨ สายแสงสว่าง ──
    "light_knight": {"slot": "outfit", "theme": "light", "name": "✨ เกราะอัศวินแสง",
                     "desc": "เกราะขาวมุกขอบทอง ผ้าคลุมทองพลิ้วตามลม", "rarity": "legend"},
    "light_blade":  {"slot": "weapon", "theme": "light", "name": "✨ ศาสตราแสงสว่าง",
                     "desc": "ใบมีดโปร่งเรืองขาว เรืองรอบตัวตลอดเวลา", "rarity": "legend"},
    "light_halo":   {"slot": "aura",   "theme": "light", "name": "✨ วงแหวนศักดิ์สิทธิ์",
                     "desc": "วงแหวนแสงหมุนรอบตัว ประกายลอยขึ้นไม่หยุด", "rarity": "legend"},
    # ── 🌑 สายความมืด ──
    "dark_cloak":   {"slot": "outfit", "theme": "dark", "name": "🌑 ชุดคลุมทมิฬ",
                     "desc": "ผ้าคลุมดำอมม่วง ขอบเรืองม่วง เงาพลิ้วไหว", "rarity": "legend"},
    "dark_scythe":  {"slot": "weapon", "theme": "dark", "name": "🌑 เคียวมรณะ",
                     "desc": "ใบมีดดำสนิทขอบม่วง เรืองแสงจากความมืด", "rarity": "legend"},
    "dark_mist":    {"slot": "aura",   "theme": "dark", "name": "🌑 หมอกอาถรรพ์",
                     "desc": "หมอกดำม่วงคลุ้งขึ้นจากพื้นรอบตัว", "rarity": "legend"},
}

THEMES = {
    "light": {"name": "✨ สายแสงสว่าง", "color": "#ffe9a8"},
    "dark":  {"name": "🌑 สายความมืด", "color": "#b06be0"},
}


def _starter_sets_free():
    """ชุดเปิดตัวแจกให้ทุกคนก่อนไหม — ปิดแล้วตั้งแต่กาชาแฟชั่นเปิด"""
    return bool(config_loader.get_balance("fashion.free_starter_sets", False))


def owned(player):
    """รหัสแฟชั่นที่ผู้เล่นมี — คืนเป็น set"""
    raw = (player or {}).get("fashion_owned") or "[]"
    try:
        got = set(json.loads(raw) if isinstance(raw, str) else (raw or []))
    except (ValueError, TypeError):
        got = set()
    if _starter_sets_free():
        got |= set(CATALOG)          # ยังไม่มีกาชา — เปิดชุดเปิดตัวให้ลองใส่ก่อน
    return {k for k in got if k in CATALOG}


def worn(player):
    """ช่องไหนใส่อะไรอยู่ — คืน dict ที่มีครบทุกช่องเสมอ (ไม่ใส่ = '')"""
    raw = (player or {}).get("fashion") or "{}"
    try:
        cur = json.loads(raw) if isinstance(raw, str) else (raw or {})
    except (ValueError, TypeError):
        cur = {}
    # กันข้อมูลเก่า/มั่ว: ต้องเป็นรหัสที่มีจริงและอยู่ในช่องที่ถูกต้อง
    return {s: (cur.get(s) if CATALOG.get(cur.get(s), {}).get("slot") == s else "") or ""
            for s in SLOTS}


def wear(user_id, key):
    """ใส่แฟชั่นหนึ่งชิ้น — คืน (ok, ข้อความ)"""
    key = str(key or "")
    item = CATALOG.get(key)
    if not item:
        return False, "❌ ไม่มีแฟชั่นชิ้นนี้ในระบบ"
    player = player_model.get_player(user_id)
    if not player:
        return False, "❌ ไม่พบข้อมูลตัวละครของคุณ"
    if key not in owned(player):
        return False, f"❌ คุณยังไม่มี **{item['name']}** — ได้จากกาชาแฟชั่นเท่านั้น"

    cur = worn(player)
    cur[item["slot"]] = key
    player_model.update_player_field(user_id, "fashion", json.dumps(cur))
    return True, f"👗 ใส่ **{item['name']}** แล้ว!"


def take_off(user_id, slot):
    """ถอดแฟชั่นทีละช่อง — คืน (ok, ข้อความ)"""
    slot = str(slot or "")
    if slot not in SLOTS:
        return False, "❌ ไม่มีช่องนี้"
    player = player_model.get_player(user_id)
    if not player:
        return False, "❌ ไม่พบข้อมูลตัวละครของคุณ"

    cur = worn(player)
    if not cur.get(slot):
        return False, "❌ ช่องนี้ไม่ได้ใส่อะไรอยู่แล้ว"
    cur[slot] = ""
    player_model.update_player_field(user_id, "fashion", json.dumps(cur))
    return True, "👕 ถอดแล้ว — กลับไปเห็นของจริงที่ใส่อยู่"


def wardrobe(user_id):
    """ตู้เสื้อผ้าทั้งใบสำหรับหน้าเว็บ — มีอะไร ใส่อะไรอยู่ แยกตามช่องและตามสาย"""
    player = player_model.get_player(user_id) or {}
    have, on = owned(player), worn(player)
    items = [{"key": k, **v, "owned": k in have, "worn": on.get(v["slot"]) == k,
              "theme_name": THEMES.get(v["theme"], {}).get("name", v["theme"])}
             for k, v in CATALOG.items()]
    items.sort(key=lambda i: (i["slot"], i["theme"]))
    return {
        "slots": list(SLOTS),
        "worn": on,
        "items": items,
        "themes": THEMES,
        "owned_count": len(have),
        "total": len(CATALOG),
        "from_gacha_only": not _starter_sets_free(),
    }


# ═══════════════════════════════════════════════════════════════════════════
# 🎁 กาชาแฟชั่น — จ่ายด้วยทอง เป็นทางเดียวที่จะได้แฟชั่น
#
# ห้ามลืม: กาชาห้ามออกเหรียญคริปโต และแฟชั่นห้ามบวกค่าต่อสู้
# สุ่มได้ + ถอนเป็นเงินจริงได้ = เข้าใกล้การพนันทันที (ดู docs/plan-2026-08-15-future-systems.md)
# ═══════════════════════════════════════════════════════════════════════════

# ปุ่มหมุน — ราคาและจำนวนครั้ง ปรับได้ที่ balance fashion.gacha.<ปุ่ม>.<คีย์>
GACHA_TIERS = {
    "single": {"price": 1_000_000,   "pulls": 1,  "odds": "low",
               "name": "🎲 สุ่ม 1 ครั้ง", "desc": "ถูกที่สุด แต่เรทต่ำมาก"},
    "lucky":  {"price": 10_000_000,  "pulls": 1,  "odds": "high",
               "name": "🍀 สุ่มเรทดี 1 ครั้ง", "desc": "เรทแฟชั่นดีกว่าราว 14 เท่า"},
    "ten":    {"price": 100_000_000, "pulls": 10, "odds": "high", "free_gems": 1,
               "name": "💎 สุ่มเรทดี 10 ครั้ง", "desc": "ได้ 💎 อัญมณีอย่างน้อย 1 เม็ดแน่นอน"},
}

# เปอร์เซ็นต์ต่อการหมุนหนึ่งครั้ง — ที่เหลือจาก 100 คือ "ของใช้ธรรมดา" (เกลือ)
#
# เรทอาร์ติแฟกต์ตั้งไว้ให้ตกชิ้นละ ~125M ทอง (≈ ล้มมอน 145 ตัว) — วัดจากการจำลองจริง
# ต่ำกว่าเรทแฟชั่นทั้งที่ "ดี" น้อยกว่า เพราะอาร์ติแฟกต์เป็นค่าพลังจริง ส่วนแฟชั่นแค่หน้าตา
# ปรับได้ที่ balance fashion.odds.<low|high>.artifact (ตั้ง 0 = เอาออกจากตู้เลย)
GACHA_ODDS = {
    "low":  {"artifact": 1.2, "fashion": 1.3, "featured": 0.2},
    "high": {"artifact": 8.0, "fashion": 18.0, "featured": 3.0},
}

GEMS_PER_EXCHANGE = 10          # 💎 ครบเท่านี้แลกแฟชั่นได้ 1 ชิ้น


def _tier(key):
    """ข้อมูลปุ่มหมุนหนึ่งปุ่ม โดยให้ค่าใน balance ทับค่าตั้งต้นได้ทีละคีย์"""
    base = GACHA_TIERS.get(str(key or ""))
    if not base:
        return None
    over = config_loader.get_balance(f"fashion.gacha.{key}", {}) or {}
    return {**base, **{k: v for k, v in over.items() if k in base}}


def _odds(name):
    over = config_loader.get_balance(f"fashion.odds.{name}", {}) or {}
    return {**GACHA_ODDS[name], **{k: float(v) for k, v in over.items()
                                   if k in GACHA_ODDS[name]}}


def banner(today=None):
    """✨ แฟชั่นหน้าตู้รอบนี้ — หมุนเปลี่ยนทุกสัปดาห์

    ponytail: คิดจากวันที่ตรง ๆ เลยไม่ต้องมีตารางตู้ในดาต้าเบสและไม่ต้องมีหน้าแอดมิน
    ถ้าวันหนึ่งอยากจัดตู้เองเมื่อไหร่ค่อยเปลี่ยนมาอ่านจาก config
    """
    keys = sorted(CATALOG)
    d = today or datetime.date.today()
    monday = d.toordinal() - d.weekday()          # ตู้เปลี่ยนวันจันทร์ ไม่ใช่กลางสัปดาห์
    return keys[(monday // 7) % len(keys)]


def _gold_pool():
    """ของใช้ธรรมดาที่หลุดออกมาเป็นรางวัลสุ่มได้ — ใช้กติกาเดียวกับหีบสมบัติ"""
    from bot.adventure_core import is_random_rewardable
    items = config_loader.get_all_items()
    return items, [i for i, d in items.items() if is_random_rewardable(d)]


def _artifact_pool():
    items = config_loader.get_all_items()
    return items, [i for i, d in items.items() if d.get("effect") == "equip_artifact"]


def _pick_item(rng, items, ids):
    """สุ่มไอเทมโดยถ่วงน้ำหนักด้วยราคา — ของแพงออกยากกว่า (เหมือนของแลก NPC)"""
    if not ids:
        return ""
    return rng.choices(ids, weights=[1.0 / max(int(items[i].get("buy", 1)), 1)
                                     for i in ids], k=1)[0]


def _roll_one(rng, odds_name, have, feat):
    """หมุนหนึ่งครั้ง → (ชนิด, รหัส) โดยยังไม่แตะดาต้าเบส

    ชนิด: featured | fashion | artifact | junk
    """
    o = _odds(odds_name)
    r = rng.random() * 100
    if r < o["featured"]:
        return "featured", feat
    r -= o["featured"]
    if r < o["fashion"]:
        pool = sorted(set(CATALOG) - {feat}) or [feat]
        return "fashion", rng.choice(pool)
    r -= o["fashion"]
    if r < o["artifact"]:
        items, ids = _artifact_pool()
        left = [i for i in ids if i not in have["inv"]] or ids
        return "artifact", _pick_item(rng, items, left)
    return "junk", ""


def pull(user_id, tier_key, rng=random):
    """🎁 หมุนกาชาแฟชั่น — คืน (ok, ผล)

    หักทองก่อนหมุนเสมอ (จ่ายค่าหมุน ไม่ใช่จ่ายค่าของ) แล้วเขียนผลลงดาต้าเบสครั้งเดียว
    ผู้เรียกต้องล็อกผู้เล่นคนนี้ไว้ก่อน ไม่งั้นกดรัวสองหน้าต่างพร้อมกันจะหมุนฟรี
    """
    tier = _tier(tier_key)
    if not tier:
        return False, {"error": "❌ ไม่รู้จักปุ่มหมุนนี้"}

    player = player_model.get_player(user_id)
    if not player:
        return False, {"error": "❌ ไม่พบข้อมูลตัวละครของคุณ"}
    price = int(tier["price"])
    cash = int(player.get("cash", 0) or 0)
    if cash < price:
        return False, {"error": f"❌ ทองไม่พอ! ต้องใช้ `{price:,}` ทอง "
                                f"(คุณมี `{cash:,}` ทอง)"}

    feat = banner()
    have = {"fash": set(owned(player)),
            "inv": player_model.load_inventory(player.get("inventory", "[]"))}
    items = config_loader.get_all_items()
    cap = int(player.get("capacity", 10) or 0)
    gems = int(player.get("fashion_gems", 0) or 0)
    gold = cash - price
    results = []

    for _ in range(int(tier["pulls"])):
        kind, key = _roll_one(rng, tier["odds"], have, feat)

        if kind in ("fashion", "featured"):
            if key in have["fash"]:                       # ได้ซ้ำ → กลายเป็นอัญมณี
                gems += 1
                results.append({"kind": "dup", "key": key, "name": CATALOG[key]["name"],
                                "gems": 1, "featured": kind == "featured"})
            else:
                have["fash"].add(key)
                results.append({"kind": kind, "key": key, "name": CATALOG[key]["name"],
                                "slot": CATALOG[key]["slot"], "featured": kind == "featured"})
            continue

        if kind == "junk" or not key:
            kind, key = "junk", _pick_item(rng, *_gold_pool())

        # ของชิ้นจริง — กระเป๋าเต็มแล้วจ่ายเป็นราคาขายแทน จะได้ไม่ตันจนหมุนต่อไม่ได้
        item = items.get(key) or {}
        if cap and len(have["inv"]) >= cap:
            paid = int(item.get("sell", 0) or 0)
            gold += paid
            results.append({"kind": "sold", "name": item.get("name", "?"), "gold": paid})
        else:
            have["inv"].append(str(key))
            results.append({"kind": kind, "name": item.get("name", "?"), "item": str(key)})

    gems += int(tier.get("free_gems", 0) or 0)
    if tier.get("free_gems"):
        results.append({"kind": "bonus", "gems": int(tier["free_gems"]),
                        "name": "💎 อัญมณีการันตี (โบนัสชุด 10 ครั้ง)"})

    player_model.update_player_fields(user_id, {
        "cash": gold,
        "fashion_gems": gems,
        "inventory": json.dumps(have["inv"]),
        "fashion_owned": json.dumps(sorted(have["fash"])),
    })
    return True, {"tier": tier_key, "price": price, "pulls": results,
                  "gems": gems, "cash": gold, "featured": feat,
                  "got_fashion": [r for r in results if r["kind"] in ("fashion", "featured")]}


def exchange(user_id, key):
    """💎 จ่ายอัญมณีแลกแฟชั่นที่ยังไม่มี — คืน (ok, ข้อความ)

    แลกได้ทุกชิ้นในตู้ ไม่ใช่แค่ของหน้าตู้รอบนี้ ไม่งั้นคนที่เก็บครบตู้ปัจจุบัน
    จะเหลือแต่อัญมณีที่ไม่มีอะไรให้แลก และคนที่เข้าไม่ทันตู้เก่าก็ไม่มีทางตามเก็บ
    """
    key = str(key or "")
    item = CATALOG.get(key)
    if not item:
        return False, "❌ ไม่มีแฟชั่นชิ้นนี้ในระบบ"
    player = player_model.get_player(user_id)
    if not player:
        return False, "❌ ไม่พบข้อมูลตัวละครของคุณ"
    if key in owned(player):
        return False, f"❌ คุณมี **{item['name']}** อยู่แล้ว"

    need = int(config_loader.get_balance("fashion.gems_per_exchange", GEMS_PER_EXCHANGE))
    gems = int(player.get("fashion_gems", 0) or 0)
    if gems < need:
        return False, f"❌ 💎 อัญมณีไม่พอ — ต้องใช้ {need} เม็ด (คุณมี {gems} เม็ด)"

    raw = player.get("fashion_owned") or "[]"
    try:
        got = set(json.loads(raw) if isinstance(raw, str) else (raw or []))
    except (ValueError, TypeError):
        got = set()
    got.add(key)
    player_model.update_player_fields(user_id, {
        "fashion_gems": gems - need,
        "fashion_owned": json.dumps(sorted(got)),
    })
    return True, f"💎 แลก **{item['name']}** สำเร็จ! (เหลืออัญมณี {gems - need} เม็ด)"


def gacha_view(user_id):
    """ข้อมูลหน้าตู้ทั้งหน้าสำหรับเว็บ — ปุ่มหมุน เรท ของหน้าตู้ อัญมณีที่มี"""
    player = player_model.get_player(user_id) or {}
    have = owned(player)
    feat = banner()
    need = int(config_loader.get_balance("fashion.gems_per_exchange", GEMS_PER_EXCHANGE))
    return {
        "cash": int(player.get("cash", 0) or 0),
        "gems": int(player.get("fashion_gems", 0) or 0),
        "gems_per_exchange": need,
        "featured": {"key": feat, **CATALOG[feat], "owned": feat in have},
        "tiers": [{"key": k, **_tier(k), "odds": _odds(_tier(k)["odds"])}
                  for k in GACHA_TIERS],
        "exchangeable": [{"key": k, **v} for k, v in sorted(CATALOG.items())
                         if k not in have],
        "owned_count": len(have),
        "total": len(CATALOG),
    }
