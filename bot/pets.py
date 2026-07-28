# 🐾 สัตว์เลี้ยง/มาสคอต (C4) — จับมอนที่ล้มได้มาเลี้ยง ติดตัวได้ทีละตัว ช่วยหนุนลูกเต๋าตอนสู้
#
# ของที่เลี้ยงไว้เก็บในสมุดจอง claim_once (คีย์ "pet:<key>") เหมือนความสำเร็จ/ซีซั่นพาส
# ตัวที่ติดอยู่เก็บในคอลัมน์ players.pet — ไม่มีตารางใหม่
import random

import discord

import bot.models.player_model as player_model
from bot import config_loader


def _cfg(key, default=None):
    return config_loader.get_config().get("pets", {}).get(key, default)


def all_pets():
    return list(_cfg("list", []) or [])


def owned(user_id):
    return {k[4:] for k in player_model.get_claimed_rewards(user_id) if k.startswith("pet:")}


def active(player):
    """สัตว์เลี้ยงที่ติดตัวอยู่ (รับ dict ผู้เล่นที่โหลดมาแล้ว — ไม่ยิง DB ซ้ำกลางไฟต์)"""
    key = (player or {}).get("pet") or ""
    if not key:
        return None
    return next((p for p in all_pets() if p.get("key") == key), None)


def roll_bonus(player):
    pet = active(player)
    return int(pet.get("dice", 0)) if pet else 0


def try_tame(user_id, monster_rank):
    """ทอยโอกาสจับมอนที่เพิ่งล้ม — คืน dict สัตว์เลี้ยงถ้าได้ตัวใหม่ ไม่ได้ = None"""
    chance = int((_cfg("tame_chance", {}) or {}).get(monster_rank, 0) or 0)
    if chance <= 0 or random.randint(1, 100) > chance:
        return None
    have = owned(user_id)
    pool = [p for p in all_pets() if p.get("from_rank") == monster_rank and p.get("key") not in have]
    if not pool:
        return None                                   # เก็บครบแรงค์นี้แล้ว
    pet = random.choice(pool)
    if not player_model.claim_once(user_id, f"pet:{pet['key']}"):
        return None
    player = player_model.get_player(user_id)
    if player and not (player.get("pet") or ""):      # ตัวแรกในชีวิต = ติดให้เลย ไม่ต้องไปกดเอง
        player_model.update_player_field(user_id, "pet", pet["key"])
        pet = dict(pet, auto_equipped=True)
    return pet


def tame_message(pet):
    if not pet:
        return ""
    bonus = f" (เต๋า +{int(pet.get('dice', 0))} ตอนสู้)" if pet.get("dice") else ""
    tail = " — ติดให้อัตโนมัติแล้ว!" if pet.get("auto_equipped") else " — เลือกติดตัวได้ที่ `!pet`"
    return f"\n🐾 **จับมาเลี้ยงได้!** {pet['name']}{bonus}{tail}"


def set_active(user_id, key):
    if key and key not in owned(user_id):
        return False, "❌ คุณยังไม่มีสัตว์เลี้ยงตัวนี้!"
    player_model.update_player_field(user_id, "pet", key or "")
    if not key:
        return True, "🧹 ปล่อยสัตว์เลี้ยงกลับกรงแล้ว (ไม่มีตัวติดตาม)"
    pet = next((p for p in all_pets() if p.get("key") == key), {})
    return True, f"🐾 ให้ {pet.get('name', 'สัตว์เลี้ยง')} ออกเดินทางกับคุณแล้ว!"


def build_pet_embed(user_id, display_name):
    player = player_model.get_player(user_id) or {}
    have = owned(user_id)
    current = active(player)
    pets = all_pets()

    embed = discord.Embed(
        title=f"🐾 สัตว์เลี้ยงของ {display_name}",
        color=0x27ae60,
        description=(f"ติดตัวอยู่: **{current['name']}** (เต๋า +{int(current.get('dice', 0))})"
                     if current else "ยังไม่มีตัวไหนติดตาม — จับได้จากการล้มมอนสเตอร์!")
                    + f"\nสะสมแล้ว **{len(have)}/{len(pets)}** ตัว")

    rank_label = {"Common": "มอนธรรมดา", "Mini-Boss": "มินิบอส", "Main-Boss": "บอสใหญ่",
                  "Secret": "มอนลับ", "Unbeatable": "ไร้พ่าย"}
    for pet in pets[:24]:
        got = pet.get("key") in have
        where = rank_label.get(pet.get("from_rank"), pet.get("from_rank", "?"))
        chance = int((_cfg("tame_chance", {}) or {}).get(pet.get("from_rank"), 0) or 0)
        value = (f"{pet.get('desc', '')}\n🎲 เต๋า +{int(pet.get('dice', 0))} · "
                 + ("✅ **มีแล้ว**" if got else f"🔒 ล้ม{where}เพื่อลุ้นจับ (โอกาส {chance}%)"))
        embed.add_field(name=pet["name"], value=value, inline=False)

    embed.set_footer(text="ติดได้ทีละตัว — เลือกจากเมนูด้านล่าง")
    return embed
