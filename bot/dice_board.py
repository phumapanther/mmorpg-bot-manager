"""🎲 กระดานทอยเต๋ารับของรายวัน (เว็บเกม เฟส 8)

กติกาที่ตกลงกับผู้เล่นไว้:
  • ทอยได้ 3 ครั้ง/วัน เท่านั้น (ไม่มีคูลดาวน์ ไม่มีซื้อเพิ่ม) รีเซ็ตเที่ยงคืน
  • เดินวนกระดาน 24 ช่อง ตกช่องไหนได้ของช่องนั้น ครบรอบได้รางวัลใหญ่
  • หน้าตา/ของรางวัลเปลี่ยนตามธีมอีเวนต์สัปดาห์ (เกาะ get_weekly_theme() เดิม)
  • รางวัลตั้งใจให้เล็ก — ทองจิปาถะ / EXP / บัฟชั่วคราว / ไอเทมที่มีอยู่แล้ว

⚠️ นี่คือทางเข้าเงินและไอเทมใหม่ของเศรษฐกิจ จึงคุมสองชั้น:
   1. โควตาเช็คและหักใน "จังหวะเดียวกัน" กับการทอย (กดรัวไม่ได้ของเกิน)
   2. ตัวเลขรางวัลผ่าน reward.gold_mult ตัวเดียวกับที่ใช้หรี่ทองทั้งเกม
"""
import datetime
import json
import random

import bot.models.player_model as player_model
from bot import config_loader, game_modifiers

ROLLS_PER_DAY = 3
BOARD_SIZE = 24

# ── ช่องพื้นฐาน (ใช้ทุกธีม) — ธีมสัปดาห์จะมาทับบางช่องทีหลัง ──
# kind: gold | exp | item | buff | none | lap (ช่องเริ่ม/ครบรอบ)
_BASE = [
    {"kind": "lap", "icon": "🏁", "label": "จุดเริ่ม"},
    {"kind": "gold", "icon": "🪙", "label": "ถุงเงินเล็ก", "amount": [80, 220]},
    {"kind": "item", "icon": "💉", "label": "ยาฮีล", "item": "1"},
    {"kind": "exp", "icon": "🌟", "label": "ประกายประสบการณ์", "amount": [15, 45]},
    {"kind": "gold", "icon": "🪙", "label": "ถุงเงินเล็ก", "amount": [80, 220]},
    {"kind": "none", "icon": "🧭", "label": "ทางแยกเงียบสงบ"},
    {"kind": "item", "icon": "🛠️", "label": "ใบซ่อมแซม", "item": "2"},
    {"kind": "gold", "icon": "🪙", "label": "ถุงเงินเล็ก", "amount": [80, 220]},
    {"kind": "buff", "icon": "🌟", "label": "พรบรรพชน", "status": "exp_blessing"},
    {"kind": "exp", "icon": "🎁", "label": "กล่องประสบการณ์", "amount": [40, 90]},
    {"kind": "gold", "icon": "🪙", "label": "ถุงเงินเล็ก", "amount": [80, 220]},
    {"kind": "item", "icon": "💉", "label": "ยาฮีล", "item": "1"},
    {"kind": "exp", "icon": "🌟", "label": "ประกายประสบการณ์", "amount": [15, 45]},
    {"kind": "gold", "icon": "🪙", "label": "ถุงเงินเล็ก", "amount": [80, 220]},
    {"kind": "gold", "icon": "💎", "label": "ผลึกล้ำค่า", "amount": [300, 700]},
    {"kind": "gold", "icon": "🪙", "label": "ถุงเงินเล็ก", "amount": [80, 220]},
    {"kind": "none", "icon": "🧱", "label": "ทางตัน"},
    {"kind": "gold", "icon": "🪙", "label": "ถุงเงินเล็ก", "amount": [80, 220]},
    {"kind": "item", "icon": "💉", "label": "ยาฮีล", "item": "1"},
    {"kind": "buff", "icon": "💪", "label": "ยาโด๊ปเถื่อน", "status": "illegal_buff"},
    {"kind": "gold", "icon": "🪙", "label": "ถุงเงินเล็ก", "amount": [80, 220]},
    {"kind": "none", "icon": "🧭", "label": "ทางแยกเงียบสงบ"},
    {"kind": "gold", "icon": "🪙", "label": "ถุงเงินเล็ก", "amount": [80, 220]},
    {"kind": "exp", "icon": "🏆", "label": "ถ้วยรางวัลนักเดินทาง", "amount": [90, 160]},
]

# ── ธีมสัปดาห์ทับช่องพิเศษ (index -> ช่องใหม่) + ของรางวัลครบรอบ ──
_THEME_TILES = {
    "goddess_dice":  {14: {"kind": "gold", "icon": "🎲", "label": "เต๋าทองของเทพี", "amount": [600, 1200]}},
    "black_market":  {14: {"kind": "item", "icon": "🏴", "label": "ของตลาดมืด", "item": "2"},
                      16: {"kind": "gold", "icon": "🏴", "label": "ส่วนแบ่งพ่อค้าเถื่อน", "amount": [200, 500]}},
    "mana_meteor":   {8: {"kind": "item", "icon": "🔮", "label": "มานาคริสตัลบริสุทธิ์", "item": "29"},
                      19: {"kind": "item", "icon": "🔮", "label": "มานาคริสตัลบริสุทธิ์", "item": "29"}},
    "blood_moon":    {16: {"kind": "buff", "icon": "🌕", "label": "แรงจันทร์เลือด", "status": "illegal_buff"}},
    "absolute_zero": {5: {"kind": "none", "icon": "❄️", "label": "พื้นน้ำแข็งลื่น"},
                      21: {"kind": "none", "icon": "❄️", "label": "พื้นน้ำแข็งลื่น"}},
    "zombie":        {16: {"kind": "gold", "icon": "🧟", "label": "ของที่ซอมบี้ทิ้งไว้", "amount": [150, 400]}},
    "dragon_nesting": {14: {"kind": "gold", "icon": "🐉", "label": "เกล็ดมังกรตกรัง", "amount": [500, 900]}},
    "royal_convoy":  {14: {"kind": "gold", "icon": "👑", "label": "สมบัติหลวงที่ร่วงหล่น", "amount": [700, 1400]}},
}


def _today():
    return datetime.date.today().isoformat()


def _gold_mult():
    try:
        return float(config_loader.get_balance("reward.gold_mult", 1.0))
    except (TypeError, ValueError):
        return 1.0


def theme_key():
    t = game_modifiers.get_weekly_theme() or {}
    return t.get("key", "normal")


def theme_label():
    t = game_modifiers.get_weekly_theme() or {}
    return t.get("label", "🕊️ สัปดาห์สงบสุข")


def board(theme=None):
    """กระดานของสัปดาห์นี้ — ช่องพื้นฐานทับด้วยช่องพิเศษของธีม"""
    tiles = [dict(t) for t in _BASE]
    for idx, tile in (_THEME_TILES.get(theme or theme_key()) or {}).items():
        if 0 <= idx < len(tiles):
            tiles[idx] = dict(tile)
    return tiles


def rolls_left(user_id, player=None):
    """จำนวนครั้งที่ทอยได้วันนี้ — ข้ามวันแล้วเติมให้เองตอนอ่าน"""
    player = player if player is not None else (player_model.get_player(user_id) or {})
    quota = int(config_loader.get_balance("dice_board.rolls_per_day", ROLLS_PER_DAY))
    if player.get("board_date") != _today():
        return quota
    return max(0, min(quota, int(player.get("board_rolls", 0) or 0)))


def state(user_id, player=None):
    """สถานะกระดานพร้อมแสดงผล — ใช้ได้ทั้ง embed ในดิสและ JSON ของเว็บ"""
    player = player if player is not None else (player_model.get_player(user_id) or {})
    return {"pos": int(player.get("board_pos", 0) or 0) % BOARD_SIZE,
            "rolls_left": rolls_left(user_id, player),
            "rolls_per_day": int(config_loader.get_balance("dice_board.rolls_per_day", ROLLS_PER_DAY)),
            "theme": theme_key(), "theme_label": theme_label(),
            "board": board(), "size": BOARD_SIZE}


def _give(user_id, player, tile, rng):
    """จ่ายของช่องนั้น — คืน (ข้อความ, ข้อมูลดิบ) โดยไม่แตะโควตา"""
    kind = tile.get("kind")

    if kind == "gold":
        lo, hi = tile.get("amount", [50, 100])
        gold = max(1, int(rng.randint(int(lo), int(hi)) * _gold_mult()))
        player_model.increment_player_field(user_id, "cash", gold)
        return f"🪙 ได้รับ `{gold:,}` ทอง", {"gold": gold}

    if kind == "exp":
        lo, hi = tile.get("amount", [10, 30])
        exp = rng.randint(int(lo), int(hi))
        player_model.add_exp(user_id, exp)
        return f"🔷 ได้รับ `{exp:,}` EXP", {"exp": exp}

    if kind == "item":
        item_id = str(tile.get("item", ""))
        info = config_loader.get_item_config(item_id) or {}
        if not info:
            return "…ช่องนี้ว่างเปล่า (แอดมินยังไม่ได้ตั้งไอเทม)", {}
        inv = player_model.load_inventory(player.get("inventory", ""))
        cap = player.get("capacity", 10)
        if cap and len(inv) >= cap:
            return f"🎒 เจอ **{info.get('name')}** แต่กระเป๋าเต็ม เก็บไม่ได้", {"bag_full": True}
        inv.append(item_id)
        player_model.update_player_field(user_id, "inventory", json.dumps(inv))
        return f"🎁 ได้รับ **{info.get('name')}**", {"item": info.get("name")}

    if kind == "buff":
        key = tile.get("status", "")
        cfg = game_modifiers.STATUS_EFFECTS.get(key)
        if not cfg:
            return "…ช่องนี้ว่างเปล่า", {}
        statuses = game_modifiers.apply_status(game_modifiers.parse_statuses(player), key)
        player_model.update_player_field(user_id, "status_effects", statuses)
        return f"✨ ได้รับบัฟ **{cfg['label']}** ({cfg.get('default_turns', 0)} ก้าว)", {"buff": key}

    return "…ไม่มีอะไรเกิดขึ้น", {}


def roll(user_id, rng=random):
    """ทอยหนึ่งครั้ง — เดินหมาก จ่ายของช่องที่ตก และโบนัสถ้าครบรอบ

    เช็คและหักโควตาในจังหวะเดียวกัน — กดรัวแล้วได้ของเกินโควตาไม่ได้
    คืน (ok, ผลลัพธ์)
    """
    player = player_model.get_player(user_id)
    if not player:
        return False, {"error": "❌ ไม่พบข้อมูลตัวละครของคุณ"}

    left = rolls_left(user_id, player)
    if left <= 0:
        return False, {"error": "🎲 วันนี้ทอยครบโควตาแล้ว — พรุ่งนี้มาใหม่นะ"}
    # หักโควตาก่อนจ่ายของเสมอ (พังกลางทางก็เสียแค่ตาเดียว ไม่ใช่แจกฟรีไม่จำกัด)
    player_model.update_player_fields(user_id, {"board_rolls": left - 1, "board_date": _today()})

    steps = rng.randint(1, 6)
    old_pos = int(player.get("board_pos", 0) or 0) % BOARD_SIZE
    new_pos = (old_pos + steps) % BOARD_SIZE
    lapped = old_pos + steps >= BOARD_SIZE
    player_model.update_player_field(user_id, "board_pos", new_pos)

    tiles = board()
    text, data = _give(user_id, player, tiles[new_pos], rng)

    lap_text = ""
    if lapped:
        bonus = max(1, int(int(config_loader.get_balance("dice_board.lap_bonus", 2000)) * _gold_mult()))
        player_model.increment_player_field(user_id, "cash", bonus)
        data["lap_bonus"] = bonus
        lap_text = f"\n🏁 **เดินครบหนึ่งรอบ!** รับโบนัส `{bonus:,}` ทอง"

    return True, {"steps": steps, "from": old_pos, "to": new_pos, "lapped": lapped,
                  "tile": tiles[new_pos], "text": text + lap_text,
                  "rolls_left": left - 1, **data}
