# bot/event_images.py
"""ภาพพิกเซลอาร์ตประกอบเหตุการณ์ — แหล่งเดียวของ logic หาไฟล์ภาพใน assets/events/

ทุกฟังก์ชันคืน discord.File หรือ None — ไม่มีไฟล์ = ผู้เรียกไม่แนบภาพ เกมทำงานแบบเดิม
(สเปค: docs/superpowers/specs/2026-08-03-event-images-design.md)
"""
import re
from pathlib import Path

import discord

ASSETS_DIR = Path(__file__).resolve().parent.parent / "assets" / "events"

# ไอเทมติดสถานะที่เห็นผลตอนเดิน — มีภาพตอนใช้สำเร็จ (ยาบัฟไฟต์ทั่วไปไม่ใส่ กันแชทรก)
_WALK_STATUS_ITEMS = {"convoy_compass", "monster_lure", "monster_ward", "monster_trap"}
# ใบวาปบังคับเหตุการณ์ → ใช้ภาพอีเวนต์ของทวีปปัจจุบันซ้ำ
_WARP_EVENT = {"warp_village": "village", "warp_dungeon": "dungeon", "scan_box": "treasure"}
_SUMMONS = {"mini_summon", "main_summon", "unbeatable_summon"}
# อุปกรณ์ระดับตำนาน 2 ชิ้น (สเปคระบุเฉพาะ 2 ตัวนี้)
_LEGENDARY_EQUIP = {"Legen_Weapon": "item_legend_weapon", "Magic_Bag": "item_magic_bag"}


def _file(stem):
    p = ASSETS_DIR / f"{stem}.png"
    if p.is_file():
        return discord.File(str(p), filename=f"{stem}.png")
    return None


def monster_slug(name):
    """'🐉 มังกรน้ำแข็ง (Ice Dragon)' → 'ice_dragon' — ไม่มีวงเล็บอังกฤษ → None"""
    m = re.search(r"\(([A-Za-z0-9' \-]+)\)", name or "")
    if not m:
        return None
    return re.sub(r"[^a-z0-9]+", "_", m.group(1).lower()).strip("_")


def event_image(key, continent=None):
    """ภาพอีเวนต์ — ลองภาพเฉพาะทวีปก่อน แล้ว fallback ภาพกลาง"""
    if continent:
        f = _file(f"{continent}_{key}")
        if f:
            return f
    return _file(key)


def monster_image(name, rank=None):
    """ภาพมอนรายตัว — ไม่มีภาพเฉพาะตัว → fallback ภาพแรงค์ → None"""
    slug = monster_slug(name)
    if slug:
        f = _file(f"monster_{slug}")
        if f:
            return f
    if rank:
        # ชื่อแรงค์ใน MONSTER_RANKS มีวงเล็บอังกฤษ (Common/Mini-Boss/...) — slug ตรงกันเสมอ
        f = _file(f"monster_{re.sub(r'[^a-z0-9]+', '_', rank.lower()).strip('_')}")
        if f:
            return f
    return None


def item_use_image(item_info, continent=None):
    """ภาพตอนใช้/สวมไอเทมพิเศษสำเร็จ — effect นอกลิสต์คืน None (ยาทั่วไปไม่มีภาพ)"""
    eff = (item_info or {}).get("effect")
    val = (item_info or {}).get("effect_value")
    if eff == "wedding_ring":
        return _file("item_wedding_ring")
    if eff == "dye_profile":
        return _file("item_dye_profile")
    if eff == "revive":
        return _file("respawn")
    if eff == "equip_artifact" and val:
        return _file(f"item_{val}")
    if eff == "apply_status" and val in _WALK_STATUS_ITEMS:
        return _file(f"item_{val}")
    if eff == "set_state":
        if val in _SUMMONS:
            return _file(val)
        if val in _WARP_EVENT:
            return event_image(_WARP_EVENT[val], continent)
        return None
    if (item_info or {}).get("equip_key") in _LEGENDARY_EQUIP:
        return _file(_LEGENDARY_EQUIP[item_info["equip_key"]])
    return None


def file_kwargs(f):
    """แปลง File|None → kwargs สำหรับ send/followup — ไม่มีภาพ = ไม่ส่ง kwarg"""
    return {"file": f} if f else {}
