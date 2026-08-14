"""💎 มานา = เม็ดคริสตัล (2026-08-14) — จำนวนครั้งที่ "ใช้สกิลแล้วพลาด" ได้ต่อวัน

กติกา (ตั้งค่าได้ที่ Panel ทุกตัว):
  • เริ่มวันใหม่ได้เต็มเสมอ — ฐาน 3 เม็ด
  • เพิ่มแบบขั้นบันได +1 เม็ดทุก 20 เลเวล เพดาน 10 เม็ด
  • ใช้สกิลแล้ว "ทอยชนะ" ไม่เสียเม็ด — เสียก็ต่อเมื่อ "ทอยแพ้" เท่านั้น (เสียครั้งละ 1)
  • เม็ดหมด = ใช้สกิลไม่ได้จนกว่าจะข้ามวัน (โจมตีปกติ/หนี ยังทำได้)

รีเซ็ตพร้อมเควสรายวัน (เที่ยงคืนตามเวลาเครื่อง) ใช้ปฏิทินเดียวกับ player_model._today()
"""
import datetime

import bot.models.player_model as player_model
from bot import config_loader

MANA_BASE = 3          # เม็ดตั้งต้นของทุกคน
MANA_PER_LEVELS = 20   # ทุกกี่เลเวลได้เพิ่ม 1 เม็ด
MANA_MAX = 10          # เพดานสูงสุด


def _today():
    return datetime.date.today().isoformat()


def _cfg(key, default):
    try:
        return int(config_loader.get_balance(f"mana.{key}", default))
    except (TypeError, ValueError):
        return default          # ตั้งเพี้ยนใน Panel = ใช้ค่าในโค้ด เกมต้องไม่พัง


def max_mana(level):
    """เม็ดเต็มของเลเวลนี้ — ฐาน + ขั้นบันได ตัดที่เพดาน"""
    step = _cfg("per_levels", MANA_PER_LEVELS)
    if step <= 0:
        step = MANA_PER_LEVELS
    return max(0, min(_cfg("max", MANA_MAX),
                      _cfg("base", MANA_BASE) + int(level or 0) // step))


def get(user_id, player=None):
    """เม็ดที่เหลือวันนี้ — ข้ามวันแล้วเติมเต็มให้เองทันที

    เติมตอน "อ่าน" ไม่ใช่ตอนเที่ยงคืน เพราะบอทอาจปิดอยู่ตอนข้ามวัน
    """
    player = player if player is not None else (player_model.get_player(user_id) or {})
    full = max_mana(player.get("level", 1))
    if player.get("mana_date") != _today():
        player_model.update_player_fields(user_id, {"mana": full, "mana_date": _today()})
        return full
    return max(0, min(full, int(player.get("mana", 0) or 0)))


def can_use_skill(user_id, player=None):
    return get(user_id, player) > 0


def spend(user_id, amount=1, player=None):
    """หักเม็ด (เรียกเมื่อใช้สกิลแล้วทอยแพ้เท่านั้น) — คืนจำนวนที่เหลือ"""
    left = max(0, get(user_id, player) - max(0, int(amount)))
    player_model.update_player_fields(user_id, {"mana": left, "mana_date": _today()})
    return left


def restore(user_id, amount=1, player=None):
    """คืนเม็ด (ไอเทม/รางวัล) — ล้นเต็มไม่ได้"""
    player = player if player is not None else (player_model.get_player(user_id) or {})
    full = max_mana(player.get("level", 1))
    left = min(full, get(user_id, player) + max(0, int(amount)))
    player_model.update_player_fields(user_id, {"mana": left, "mana_date": _today()})
    return left


def bar(cur, full):
    """💎💎💎🖤🖤 — เม็ดที่เหลือกับที่หมดไป (ยาวเกิน 10 เม็ดสลับเป็นตัวเลขล้วน)"""
    cur, full = max(0, int(cur)), max(0, int(full))
    if full > 10:
        return f"💎 {cur}/{full}"
    return ("💎" * cur + "🖤" * max(0, full - cur)) or "🖤"


def status_line(user_id, player=None):
    """บรรทัดพร้อมแสดงผล — ใช้ได้ทั้ง embed ในดิสและ JSON ของเว็บ"""
    player = player if player is not None else (player_model.get_player(user_id) or {})
    full = max_mana(player.get("level", 1))
    cur = get(user_id, player)
    return {"mana": cur, "mana_max": full, "bar": bar(cur, full),
            "next_at": _next_level_up(player.get("level", 1), full)}


def _next_level_up(level, full):
    """เลเวลถัดไปที่จะได้เม็ดเพิ่ม — None ถ้าเต็มเพดานแล้ว"""
    step = _cfg("per_levels", MANA_PER_LEVELS)
    if step <= 0 or full >= _cfg("max", MANA_MAX):
        return None
    return (int(level or 0) // step + 1) * step
