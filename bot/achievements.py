# 🏅 ความสำเร็จ + ตำแหน่งอวดหน้าโปรไฟล์ (C8)
#
# ไม่มีตัวนับใหม่สักตัว — อ่านจากข้อมูลที่เกมเก็บอยู่แล้ว (สมุดล่า / ตารางผู้เล่น / login streak)
# ผลพลอยได้: ผู้เล่นเก่าที่เล่นมาก่อนฟีเจอร์นี้ ได้ความสำเร็จย้อนหลังทันทีที่เปิดหน้าแรก
import discord

import bot.models.player_model as player_model
from bot import config_loader

BOSS_RANKS = ("Mini-Boss", "Main-Boss", "Secret", "Unbeatable")


def player_stats(user_id):
    """สถิติปัจจุบันของผู้เล่น — คำนวณสดจากข้อมูลที่มีอยู่ ไม่เก็บซ้ำ"""
    player = player_model.get_player(user_id) or {}
    book = player_model.get_bestiary(user_id)
    return {
        "kills": sum(book.values()),
        "boss_kills": sum(k for (_c, rank), k in book.items() if rank in BOSS_RANKS),
        "continents": len({c for (c, _r), k in book.items() if k > 0}),
        "level": player.get("level", 1) or 1,
        "wealth": (player.get("cash", 0) or 0) + (player.get("bank", 0) or 0),
        "streak": player_model.get_best_streak(user_id),
        "text": player.get("total_text", 0) or 0,
        "online_hours": int(player.get("total_online_time", 0) or 0) // 3600,
    }


def _defs():
    return list(config_loader.get_config().get("achievements", []))


def check_and_unlock(user_id):
    """ปลดล็อกอันที่ถึงเกณฑ์ + จ่ายรางวัลเข้าธนาคาร — คืนรายการที่ "เพิ่งปลด" รอบนี้เท่านั้น

    เรียกบ่อยแค่ไหนก็ได้ ปลอดภัย: claim_bestiary_reward เป็น INSERT OR IGNORE
    """
    stats = player_stats(user_id)
    done = unlocked_keys(user_id)     # อ่านครั้งเดียว — ไม่งั้นคนที่ปลดครบแล้วจะสั่งเขียนซ้ำทุกอันทุกครั้งที่ฆ่ามอน
    fresh = []
    for ach in _defs():
        if ach.get("key") in done:
            continue
        if stats.get(ach.get("stat"), 0) < int(ach.get("target", 0)):
            continue
        if not player_model.claim_once(user_id, f"ach:{ach['key']}"):
            continue                      # กันแข่งกันเขียนพร้อมกัน (ปกติ done กรองไปแล้ว)
        gold = int(ach.get("gold", 0))
        if gold:
            player = player_model.get_player(user_id)
            if player:
                player_model.update_player_field(user_id, "bank", player.get("bank", 0) + gold)
        fresh.append(ach)
    return fresh


def unlock_message(fresh):
    """ข้อความแจ้งกลางเกม (ต่อท้ายผลไฟต์) — ไม่มีอะไรปลดใหม่ = สตริงว่าง"""
    lines = []
    for ach in fresh:
        gold = int(ach.get("gold", 0))
        bonus = f" — 🪙 +{gold:,} ทองเข้าธนาคาร" if gold else ""
        title = f" · ได้ตำแหน่ง **{ach['title']}**" if ach.get("title") else ""
        lines.append(f"\n🏅 **ปลดล็อกความสำเร็จ: {ach['label']}**{bonus}{title}")
    return "".join(lines)


def unlocked_keys(user_id):
    return {k[4:] for k in player_model.get_claimed_rewards(user_id) if k.startswith("ach:")}


def unlocked_titles(user_id):
    done = unlocked_keys(user_id)
    return [a["title"] for a in _defs() if a.get("title") and a["key"] in done]


def set_title(user_id, title):
    """ติดตำแหน่งอวด — ต้องเป็นตำแหน่งที่ปลดล็อกแล้วเท่านั้น (ว่าง = ถอด)"""
    if title and title not in unlocked_titles(user_id):
        return False, "❌ คุณยังไม่ได้ปลดล็อกตำแหน่งนี้!"
    player_model.update_player_field(user_id, "title", title or "")
    return True, (f"✨ ติดตำแหน่ง **{title}** เรียบร้อย! ไปดูได้ที่ `!profile`"
                  if title else "🧹 ถอดตำแหน่งออกแล้ว")


def build_achievement_embed(user_id, display_name):
    check_and_unlock(user_id)                     # เปิดหน้าแล้วเก็บของค้างให้เลย
    stats = player_stats(user_id)
    done = unlocked_keys(user_id)
    defs = _defs()[:25]        # ลิมิต field ของ embed — เพิ่มในคอนฟิกเกินนี้ก็ไม่พังหน้า

    embed = discord.Embed(
        title=f"🏅 ความสำเร็จของ {display_name}",
        color=0x9b59b6,
        description=f"ปลดล็อกแล้ว **{len(done)}/{len(defs)}** รายการ")

    for ach in defs:
        target = int(ach.get("target", 1))
        cur = min(stats.get(ach.get("stat"), 0), target)
        if ach["key"] in done:
            status = "✅ **ปลดล็อกแล้ว**"
        else:
            filled = min(10, round(cur / max(1, target) * 10))
            status = f"`{'█' * filled}{'░' * (10 - filled)}` {cur:,}/{target:,}"
        reward = []
        if ach.get("gold"):
            reward.append(f"🪙 {int(ach['gold']):,}")
        if ach.get("title"):
            reward.append(f"🎖️ ตำแหน่ง “{ach['title']}”")
        embed.add_field(name=f"{ach['label']}",
                        value=f"{ach.get('desc', '')}\n{status}" + (f"\n{' · '.join(reward)}" if reward else ""),
                        inline=False)

    player = player_model.get_player(user_id) or {}
    current = player.get("title") or "ยังไม่ได้ติดตำแหน่ง"
    embed.set_footer(text=f"ตำแหน่งที่ติดอยู่: {current} — กดปุ่มด้านล่างเพื่อเปลี่ยน")
    return embed
