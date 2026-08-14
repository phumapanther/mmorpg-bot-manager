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


def premium_price():
    """ราคาสายพรีเมียมของซีซั่นนี้ — ตัวที่โชว์บนปุ่มกับตัวที่หักเงินต้องอ่านที่เดียวกัน
    (เคยพลาด: หน้าเว็บอ่านคนละคีย์ เลยโชว์ 0 ทั้งที่หักจริง 5 ล้าน)"""
    return int(_cfg("price_gold", 0) or 0)


def enabled():
    return bool(_cfg("enabled", True))


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
    if not enabled():
        return False, "❌ ตอนนี้ยังไม่เปิดซีซั่นพาส"
    if is_premium(user_id):
        return False, "✅ คุณเปิดสายพรีเมียมของซีซั่นนี้ไว้แล้ว!"
    price = premium_price()
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


def _reward_view(reward):
    """รางวัลหนึ่งช่อง -> ข้อมูลที่เอาไปโชว์ได้เลย (ชื่อไอเทมแปลงให้แล้ว)"""
    item_id = reward.get("item")
    item = None
    if item_id:
        cfg = config_loader.get_item_config(str(item_id)) or {}
        item = {"id": str(item_id), "name": cfg.get("name", f"ไอเทม {item_id}")}
    bits = []
    if reward.get("gold"):
        bits.append(f"🪙 {int(reward['gold']):,}")
    if reward.get("exp"):
        bits.append(f"🔷 {int(reward['exp']):,} EXP")
    if item:
        bits.append(item["name"])
    return {"gold": int(reward.get("gold", 0) or 0), "exp": int(reward.get("exp", 0) or 0),
            "item": item, "text": " · ".join(bits) or "—"}


def season_view(user_id, season=None):
    """สถานะซีซั่นพาสทั้งใบ — ทั้งเอมเบดในดิสและหน้าเว็บอ่านจากตัวนี้ตัวเดียว

    เคยเป็นปัญหา: เว็บคำนวณเองว่าช่องไหนรับแล้ว/ยังไม่ถึง แล้วไม่ตรงกับดิส
    """
    season = season or player_model.season_key()
    points = int(player_model.get_season_points(user_id, season) or 0)
    premium = is_premium(user_id, season)
    claimed = player_model.get_claimed_rewards(user_id)
    all_tiers = tiers()

    rows, claimable, nxt = [], 0, None
    for i, tier in enumerate(all_tiers):
        need = int(tier.get("points", 0))
        reached = points >= need
        if not reached and nxt is None:
            nxt = {"index": i, "points": need, "need_more": need - points}
        tracks = []
        for track in ("free", "premium"):
            reward = tier.get(track)
            if not reward:
                continue
            if f"sp:{season}:{i}:{track}" in claimed:
                status = "claimed"
            elif not reached:
                status = "locked"
            elif track == "premium" and not premium:
                status = "need_premium"
            else:
                status = "ready"
                claimable += 1
            tracks.append({"track": track, "status": status, **_reward_view(reward)})
        rows.append({"index": i, "points": need, "reached": reached, "tracks": tracks})

    done = sum(1 for t in all_tiers if points >= int(t.get("points", 0)))
    return {"season": season, "points": points, "premium": premium, "enabled": enabled(),
            "premium_price": premium_price(), "tiers": rows,
            "tiers_done": done, "tiers_total": len(all_tiers),
            "claimable": claimable, "next": nxt}


STATUS_MARK = {"claimed": "✅ รับแล้ว", "locked": "🔒 ยังไม่ถึง",
               "need_premium": "🔐 ต้องเปิดพรีเมียม", "ready": "🎁 **กดรับได้!**"}
TRACK_ICON = {"free": "🆓", "premium": "⭐"}


def build_season_embed(user_id, display_name):
    v = season_view(user_id)
    season, points, premium = v["season"], v["points"], v["premium"]
    all_tiers = tiers()

    done_tiers = v["tiers_done"]
    embed = discord.Embed(
        title=f"🎟️ ซีซั่นพาส {season} — {display_name}",
        color=0xe67e22 if premium else 0x95a5a6,
        description=(f"{'⭐ **สายพรีเมียมเปิดอยู่**' if premium else '🆓 สายฟรี (ยังไม่เปิดพรีเมียม)'}\n"
                     f"แต้มซีซั่น **{points:,}** · ปลดแล้ว **{done_tiers}/{len(all_tiers)}** ขั้น"))

    for row in v["tiers"][:24]:
        lines = [f"{TRACK_ICON[t['track']]} {t['text']} → {STATUS_MARK[t['status']]}"
                 for t in row["tracks"]]
        embed.add_field(name=f"ขั้น {row['index'] + 1} · ต้องมี {row['points']:,} แต้ม",
                        value="\n".join(lines) or "—", inline=False)

    price = int(_cfg("price_gold", 0) or 0)
    embed.set_footer(text=("แต้ม = EXP ที่หาได้ในเดือนนี้ · รางวัลทองเข้าธนาคาร"
                           if premium else
                           f"แต้ม = EXP ที่หาได้ในเดือนนี้ · เปิดพรีเมียม {price:,} ทอง (เติมทอง: !payment)"))
    return embed
