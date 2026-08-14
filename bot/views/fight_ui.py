# 🖼️ ส่วนแสดงผลหน้าจอต่อสู้ (B6) — แยกจาก game_views.py
# มีแต่การ "วาดหน้าจอ" ไม่มีตรรกะเกม แก้หน้าตาได้ที่ไฟล์นี้ที่เดียว
import discord

from bot import game_modifiers
from bot.event_images import event_image

def hp_bar(current, maximum, length=10):
    """แถบเลือดแบบข้อความ ███████░░░ — กันหารศูนย์และค่าติดลบ"""
    maximum = max(1, int(maximum or 1))
    current = max(0, min(int(current or 0), maximum))
    filled = round(current / maximum * length)
    return "█" * filled + "░" * (length - filled)


ELEMENT_COLORS = {"fire": 0xe74c3c, "water": 0x3498db, "earth": 0x8d6e63, "wind": 0x1abc9c,
                  "wood": 0x27ae60, "dark": 0x2c3e50, "light": 0xf1c40f}
RANK_BADGES = {"Common": "🟢 ทั่วไป", "Mini-Boss": "🟡 มินิบอส", "Main-Boss": "🔴 บอสหลัก",
               "Secret": "🟣 ลับ", "Unbeatable": "💀 ไร้พ่าย"}


def _mana_bar(player):
    """💎 เม็ดคริสตัลที่เหลือวันนี้ — ใช้สกิลแล้วทอยแพ้ถึงจะเสีย"""
    from bot import mana as _mana
    full = _mana.max_mana(player.get("level", 1))
    cur = max(0, min(full, int(player.get("mana", 0) or 0)))
    return f"{_mana.bar(cur, full)}  `{cur}/{full}`"


def build_fight_embed(view, player, dice, damage_line, events, turn):
    """หน้าจอต่อสู้ — จัดกลุ่มข้อมูลให้อ่านง่ายแต่ครบเหมือนเดิม (B3)
    dice = {"player": แต้มสุดท้าย, "player_parts": [...], "monster": แต้ม, "monster_parts": [...]}"""
    max_hp = player.get("max_hp", 100)
    cur_hp = max(0, player.get("hp", 0))
    mon_max = getattr(view, "monster_hp_max", None) or max(1, view.monster_hp)
    embed = discord.Embed(
        title=f"⚔️ เทิร์น {turn} · {view.m_stats.get('name', 'มอนสเตอร์')}",
        color=ELEMENT_COLORS.get(getattr(view, "element", None), 0x95a5a6))
    # ภาพมอนรายตัว — ไฟล์ถูกแนบครั้งเดียวตอนเทิร์นแรก (game_views) เทิร์นถัดไป attachment เดิมค้างบนข้อความ
    embed.set_thumbnail(url="attachment://monster.png")

    badge = RANK_BADGES.get(view.monster_rank, view.monster_rank)
    embed.add_field(
        name="​",
        value=(f"👾 **ศัตรู** `{hp_bar(view.monster_hp, mon_max)}` `{view.monster_hp:,}/{mon_max:,}`  [{badge}]\n"
               f"❤️ **คุณ**  `{hp_bar(cur_hp, max_hp)}` `{cur_hp:,}/{max_hp:,}`"),
        inline=False)

    if dice:
        p_parts = " ".join(dice.get("player_parts") or []) or "—"
        m_parts = " ".join(dice.get("monster_parts") or []) or "—"
        verdict = "**ชนะเต๋า** ✅" if dice["player"] >= dice["monster"] else "**แพ้เต๋า** ❌"
        embed.add_field(
            name="🎲 ทอยเต๋า",
            value=(f"คุณ **`{dice['player']}`** = {p_parts}\n"
                   f"ศัตรู **`{dice['monster']}`** = {m_parts}\n{verdict}"),
            inline=False)

    if damage_line:
        embed.add_field(name="💥 ดาเมจ", value=damage_line, inline=False)

    if events:
        text = events.strip()
        embed.add_field(name="📜 เหตุการณ์", value=text[:1024], inline=False)
        if len(text) > 1024:
            embed.add_field(name="​", value=text[1024:2048], inline=False)

    statuses = getattr(view, "statuses", {}) or {}
    shown = [f"{game_modifiers.STATUS_EFFECTS[k]['label']} `{v}`" for k, v in statuses.items()
             if k in game_modifiers.STATUS_EFFECTS and not game_modifiers.STATUS_EFFECTS[k].get("artifact")]
    if shown:
        embed.add_field(name="🩸 สถานะติดตัว", value=" · ".join(shown)[:1024], inline=False)
    return embed




def build_respawn_embed(player, respawn_hp, max_hp, penalty_fee, new_cash, lost_steps=0, hp_pct=30):
    """หน้าจอฟื้นคืนชีพ (O3) — ใช้ร่วมกันทุกเส้นทางตาย เพื่อให้ค่าธรรมเนียม/หน้าตาตรงกันเสมอ"""
    embed = discord.Embed(
        title="😇 ปาฏิหาริย์! คุณฟื้นคืนสติที่หมู่บ้านอุ่นใจ", color=0xe67e22,
        description="มีนักเดินทางใจดีแบกร่างอันหมดสติของคุณมาส่งถึงโรงหมอ...")
    # ภาพแสงชุบชีวิต — ผู้ส่ง embed นี้ต้องแนบไฟล์ respawn.png มาด้วย (ไม่มีไฟล์ = embed เดิม)
    if event_image("respawn"):
        embed.set_image(url="attachment://respawn.png")
    lost = [f"💸 ค่าชุบชีวิต **-{penalty_fee:,}** ทอง"]
    if lost_steps:
        lost.append(f"🕳️ ความคืบหน้าดันเจี้ยน **{lost_steps} ชั้น** (เริ่มใหม่จากหมู่บ้าน)")
    embed.add_field(name="📉 สิ่งที่เสียไป", value="\n".join(lost), inline=False)
    debt = "  ⚠️ **ติดหนี้สมาคมนักผจญภัย!**" if new_cash < 0 else ""
    embed.add_field(
        name="📊 สถานะปัจจุบัน",
        value=(f"❤️ พลังชีวิต `{hp_bar(respawn_hp, max_hp)}` `{respawn_hp:,}/{max_hp:,}` *(ฟื้นมา {hp_pct}%)*\n"
               f"💰 เงินสด `{new_cash:,}` ทอง{debt}\n"
               f"🎒 ของในกระเป๋า **ปลอดภัยครบ** (ตายไม่ทำของหาย)"),
        inline=False)
    embed.add_field(
        name="👉 ทำอะไรต่อดี",
        value=("• 💊 ซื้อยาฮีลเติมเลือดก่อนออกเดินทาง (`!shop`)\n"
               "• 🛠️ เช็คความทนทานอาวุธ/เกราะที่ `!profile`\n"
               "• 🧭 พร้อมแล้วกดปุ่มด้านล่างเพื่อลุยต่อ!"),
        inline=False)
    return embed
