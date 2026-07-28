# 🎟️ Season Pass รายเดือน (C2)
#
# แต้มซีซั่น = EXP ที่หาได้ในเดือนนั้น (เก็บจาก add_exp จุดเดียวกับอันดับรายสัปดาห์)
# ซีซั่นเปลี่ยนเองตามเดือนปฏิทิน ไม่มีโค้ดรีเซ็ต — ขึ้นเดือนใหม่ = คีย์ใหม่ = แต้มเริ่มศูนย์
#
# สายฟรีทุกคนได้ · สายพรีเมียมต้องซื้อ (ทองในเกม หรือแอดมินแจกให้หลังโอนจริง)
# ไม่มีตารางใหม่สำหรับสถานะ/การรับรางวัล — ใช้สมุดจอง claim_once ที่มีอยู่แล้ว
import json

import discord

import bot.models.player_model as player_model
from bot import config_loader


def _cfg(key, default=None):
    return config_loader.get_config().get("season_pass", {}).get(key, default)


def tiers():
    return list(_cfg("tiers", []) or [])


def is_premium(user_id, season=None):
    season = season or player_model.season_key()
    return f"sp:{season}:premium" in player_model.get_claimed_rewards(user_id)


def grant_premium(user_id, season=None):
    """เปิดสายพรีเมียมให้ผู้เล่น — คืน True ถ้าเพิ่งเปิด, False ถ้ามีอยู่แล้ว"""
    season = season or player_model.season_key()
    return player_model.claim_once(user_id, f"sp:{season}:premium")


def buy_premium(user_id):
    """ซื้อพรีเมียมด้วยทองในเกม (เติมทองผ่าน !payment ได้ตามปกติ)"""
    if not _cfg("enabled", True):
        return False, "❌ ตอนนี้ยังไม่เปิดซีซั่นพาส"
    if is_premium(user_id):
        return False, "✅ คุณเปิดสายพรีเมียมของซีซั่นนี้ไว้แล้ว!"
    price = int(_cfg("price_gold", 0) or 0)
    player = player_model.get_player(user_id)
    if not player:
        return False, "❌ ไม่พบข้อมูลตัวละครของคุณ!"
    if player.get("cash", 0) < price:
        return False, (f"❌ เงินสดไม่พอ! ต้องใช้ 🪙 `{price:,}` ทอง "
                       f"(มีอยู่ `{player.get('cash', 0):,}`)\n"
                       "เติมทองได้ที่คำสั่ง `!payment`")
    player_model.update_player_field(user_id, "cash", player.get("cash", 0) - price)
    grant_premium(user_id)
    return True, (f"🎟️ **เปิดสายพรีเมียมสำเร็จ!** จ่าย 🪙 `{price:,}` ทอง\n"
                  "กดรับรางวัลสายพรีเมียมที่ปลดไว้แล้วได้เลย")


def _give(user_id, reward):
    """จ่ายรางวัลหนึ่งช่อง — คืนข้อความสรุปสั้น ๆ"""
    parts = []
    gold, exp, item = int(reward.get("gold", 0)), int(reward.get("exp", 0)), reward.get("item")
    if gold:
        player = player_model.get_player(user_id)
        if player:
            player_model.update_player_field(user_id, "bank", player.get("bank", 0) + gold)
            parts.append(f"🪙 {gold:,}")
    if exp:
        player_model.add_exp(user_id, exp)
        parts.append(f"🔷 {exp:,} EXP")
    if item:
        player = player_model.get_player(user_id)
        if player:
            inv = player_model.load_inventory(player.get("inventory", ""))
            inv.append(str(item))
            player_model.update_player_field(user_id, "inventory", json.dumps(inv))
            parts.append(config_loader.get_item_config(str(item)).get("name", f"ไอเทม {item}"))
    return " · ".join(parts)


def claim_all(user_id, season=None):
    """รับรางวัลทุกขั้นที่ปลดแล้วและยังไม่ได้รับ (สายฟรีเสมอ + สายพรีเมียมถ้าซื้อไว้)"""
    season = season or player_model.season_key()
    points = player_model.get_season_points(user_id, season)
    premium = is_premium(user_id, season)
    got = []
    for i, tier in enumerate(tiers()):
        if points < int(tier.get("points", 0)):
            break                                   # ขั้นเรียงจากน้อยไปมาก เจอขั้นที่ยังไม่ถึง = จบ
        for track in ("free", "premium"):
            reward = tier.get(track)
            if not reward or (track == "premium" and not premium):
                continue
            if not player_model.claim_once(user_id, f"sp:{season}:{i}:{track}"):
                continue
            summary = _give(user_id, reward)
            if summary:
                got.append(f"ขั้น {i + 1} ({'ฟรี' if track == 'free' else 'พรีเมียม'}) — {summary}")
    if not got:
        return ("📭 ยังไม่มีรางวัลให้รับ — ออกไปหา EXP เพิ่มก่อนนะ!"
                if premium or not tiers() else
                "📭 ยังไม่มีรางวัลสายฟรีให้รับ (สายพรีเมียมต้องเปิดก่อนถึงจะรับได้)")
    return "🎁 **รับรางวัลซีซั่นสำเร็จ!**\n" + "\n".join(f"• {g}" for g in got)


def build_season_embed(user_id, display_name):
    season = player_model.season_key()
    points = player_model.get_season_points(user_id, season)
    premium = is_premium(user_id, season)
    claimed = player_model.get_claimed_rewards(user_id)
    all_tiers = tiers()

    done_tiers = sum(1 for t in all_tiers if points >= int(t.get("points", 0)))
    embed = discord.Embed(
        title=f"🎟️ ซีซั่นพาส {season} — {display_name}",
        color=0xe67e22 if premium else 0x95a5a6,
        description=(f"{'⭐ **สายพรีเมียมเปิดอยู่**' if premium else '🆓 สายฟรี (ยังไม่เปิดพรีเมียม)'}\n"
                     f"แต้มซีซั่น **{points:,}** · ปลดแล้ว **{done_tiers}/{len(all_tiers)}** ขั้น"))

    for i, tier in enumerate(all_tiers[:24]):
        need = int(tier.get("points", 0))
        reached = points >= need
        lines = []
        for track, icon in (("free", "🆓"), ("premium", "⭐")):
            reward = tier.get(track)
            if not reward:
                continue
            got = f"sp:{season}:{i}:{track}" in claimed
            if got:
                mark = "✅ รับแล้ว"
            elif not reached:
                mark = "🔒 ยังไม่ถึง"
            elif track == "premium" and not premium:
                mark = "🔐 ต้องเปิดพรีเมียม"
            else:
                mark = "🎁 **กดรับได้!**"
            bits = []
            if reward.get("gold"):
                bits.append(f"🪙 {int(reward['gold']):,}")
            if reward.get("exp"):
                bits.append(f"🔷 {int(reward['exp']):,}")
            if reward.get("item"):
                bits.append(config_loader.get_item_config(str(reward["item"])).get("name", "ไอเทมพิเศษ"))
            lines.append(f"{icon} {' · '.join(bits) or '—'} → {mark}")
        embed.add_field(name=f"ขั้น {i + 1} · ต้องมี {need:,} แต้ม", value="\n".join(lines), inline=False)

    price = int(_cfg("price_gold", 0) or 0)
    embed.set_footer(text=("แต้ม = EXP ที่หาได้ในเดือนนี้ · รางวัลทองเข้าธนาคาร"
                           if premium else
                           f"แต้ม = EXP ที่หาได้ในเดือนนี้ · เปิดพรีเมียม {price:,} ทอง (เติมทอง: !payment)"))
    return embed
