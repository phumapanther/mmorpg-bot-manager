# 👗 ระบบแฟชั่น — เปลี่ยนแค่การแสดงผล ไม่แตะค่าต่อสู้สักตัว
#
# กติกาเหล็ก: แฟชั่นห้ามบวก/ลบค่าอะไรทั้งสิ้น ใส่เท่ ๆ อย่างเดียว
# (มีเทสบังคับใน tests/test_fashion.py — ใส่/ถอดแล้วค่าต่อสู้ต้องเท่าเดิมเป๊ะ)
#
# ของจริงที่ใส่อยู่ไม่ขยับเลย เกราะเหล็กยังเป็นเกราะเหล็ก ค่าป้องกัน/ความคงทนเหมือนเดิม
# แค่ "วาดออกมาเป็นชุดอื่น" — ตัววาดอยู่ที่ license_server/web_static/sprite.js
#
# ที่มาของแฟชั่น: กาชาแฟชั่นเท่านั้น (ยังไม่ได้ทำ — ดู docs/plan-2026-08-15-future-systems.md)
# ระหว่างนี้เปิดชุดเปิดตัวให้ทุกคนใส่ได้ก่อน ปิดได้ที่ balance fashion.free_starter_sets
import json

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
    """ชุดเปิดตัวแจกให้ทุกคนก่อนไหม — ปิดเมื่อกาชาแฟชั่นพร้อมใช้งาน"""
    return bool(config_loader.get_balance("fashion.free_starter_sets", True))


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
