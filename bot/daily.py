# 📅 เควสรายวัน + Login Streak (C1) — ตรรกะกลาง ใช้ทั้งคำสั่ง ปุ่ม และ hook ในเกม
import json

import discord

import bot.models.player_model as player_model
from bot import config_loader


def track(user_id, quest_key, amount=1):
    """เรียกจากในเกมเมื่อผู้เล่นทำอะไรที่นับเป็นเควส — เงียบเสมอ ไม่ให้พังเกมหลัก"""
    try:
        if any(q.get("key") == quest_key for q in config_loader.get_daily_quests()):
            player_model.add_daily_progress(user_id, quest_key, amount)
    except Exception as e:
        print(f"⚠️ [daily] track {quest_key} พัง: {e}")


def _bar(cur, target, length=10):
    filled = min(length, round(min(cur / max(1, target), 1) * length))
    return "█" * filled + "░" * (length - filled)


def build_daily_embed(user_id, display_name):
    """หน้าเควสรายวัน — ความคืบหน้า + streak + สรุปว่ารับรางวัลได้ไหม"""
    quests = config_loader.get_daily_quests()
    progress = player_model.get_daily_progress(user_id)
    streak, best, _new = player_model.touch_login_streak(user_id)

    embed = discord.Embed(
        title=f"📅 ภารกิจรายวันของ {display_name}",
        color=0x3498db,
        description=f"🔥 **ล็อกอินต่อเนื่อง {streak} วัน** (สถิติสูงสุด {best} วัน) — รีเซ็ตเที่ยงคืนทุกวัน")

    done_all = True
    for q in quests:
        cur, claimed = progress.get(q["key"], (0, False))
        target = int(q.get("target", 1))
        cur = min(cur, target)
        if claimed:
            status = "✅ รับรางวัลแล้ว"
        elif cur >= target:
            status = "🎁 **กดรับรางวัลได้!**"
            done_all = False
        else:
            status = f"`{_bar(cur, target)}` {cur}/{target}"
            done_all = False
        embed.add_field(
            name=f"{q['label']} ({target} ครั้ง)",
            value=f"{status}\n🪙 {int(q.get('gold', 0)):,} ทอง · 🔷 {int(q.get('exp', 0)):,} EXP",
            inline=False)

    bonus = config_loader.get_daily_cfg("all_clear_bonus", {}) or {}
    if bonus:
        got = all(progress.get(q["key"], (0, False))[1] for q in quests) if quests else False
        embed.add_field(
            name="🏆 โบนัสเคลียร์ครบทุกภารกิจ",
            value=(f"{'✅ รับแล้ว' if got else '🔒 ยังไม่ครบ'} — "
                   f"🪙 {int(bonus.get('gold', 0)):,} ทอง · 🔷 {int(bonus.get('exp', 0)):,} EXP"),
            inline=False)

    next_reward = next((r for r in sorted(config_loader.get_daily_cfg("streak_rewards", []) or [],
                                          key=lambda r: r["day"]) if r["day"] > streak), None)
    if next_reward:
        embed.set_footer(text=f"🔥 อีก {next_reward['day'] - streak} วันติดกัน รับ {int(next_reward['gold']):,} ทอง!")
    return embed


def claim_all(user_id):
    """รับรางวัลเควสที่ทำครบทุกอัน + โบนัสเคลียร์ครบ — คืนข้อความสรุป"""
    quests = config_loader.get_daily_quests()
    progress = player_model.get_daily_progress(user_id)
    player = player_model.get_player(user_id)
    if not player:
        return "❌ ไม่พบข้อมูลตัวละครของคุณ!"

    gold, exp, names = 0, 0, []
    for q in quests:
        cur, claimed = progress.get(q["key"], (0, False))
        if claimed or cur < int(q.get("target", 1)):
            continue
        if player_model.claim_daily(user_id, q["key"]):
            gold += int(q.get("gold", 0))
            exp += int(q.get("exp", 0))
            names.append(q["label"])

    if not names:
        return "📭 ยังไม่มีภารกิจที่ทำครบและรอรับรางวัลอยู่เลย — ออกไปผจญภัยก่อนนะ!"

    # โบนัสเคลียร์ครบ (รับได้ครั้งเดียวต่อวัน — ใช้คีย์พิเศษ)
    after = player_model.get_daily_progress(user_id)
    bonus_line = ""
    if quests and all(after.get(q["key"], (0, False))[1] for q in quests):
        bonus = config_loader.get_daily_cfg("all_clear_bonus", {}) or {}
        if bonus:
            player_model.add_daily_progress(user_id, "__all_clear__", 1)   # สร้างแถวไว้กันรับซ้ำ
            if player_model.claim_daily(user_id, "__all_clear__"):         # True ครั้งเดียวต่อวัน
                gold += int(bonus.get("gold", 0))
                exp += int(bonus.get("exp", 0))
                bonus_line = f"\n🏆 **โบนัสเคลียร์ครบทุกภารกิจ!** +{int(bonus.get('gold', 0)):,} ทอง"

    player_model.update_player_field(user_id, "cash", player.get("cash", 0) + gold)
    if exp:
        player_model.add_exp(user_id, exp)
    return (f"🎁 **รับรางวัลสำเร็จ!** ({', '.join(names)})\n"
            f"🪙 +{gold:,} ทอง · 🔷 +{exp:,} EXP{bonus_line}")


def claim_streak_reward(user_id, streak):
    """รางวัลล็อกอินต่อเนื่องตามหลักไมล์ — คืนข้อความ หรือ None ถ้ายังไม่ถึง/รับแล้ว"""
    rewards = config_loader.get_daily_cfg("streak_rewards", []) or []
    hit = next((r for r in rewards if int(r["day"]) == streak), None)
    if not hit:
        return None
    key = f"__streak_{streak}__"
    player_model.add_daily_progress(user_id, key, 1)      # สร้างแถวไว้กันรับซ้ำในวันเดียวกัน
    if not player_model.claim_daily(user_id, key):
        return None
    player = player_model.get_player(user_id)
    if not player:
        return None
    gold = int(hit.get("gold", 0))
    player_model.update_player_field(user_id, "cash", player.get("cash", 0) + gold)
    item_line = ""
    if hit.get("item"):
        inv = player_model.load_inventory(player.get("inventory", ""))
        inv.append(str(hit["item"]))
        player_model.update_player_field(user_id, "inventory", json.dumps(inv))
        item_line = f" + {config_loader.get_item_config(str(hit['item'])).get('name', 'ไอเทมพิเศษ')}"
    return f"🔥 **ล็อกอินครบ {streak} วันติด!** รับ 🪙 {gold:,} ทอง{item_line}"
