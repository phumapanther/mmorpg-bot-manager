"""🎴 บอททัก DM ชวนเพื่อนเข้าห้อง — ใช้ร่วมได้ทุกเกม (UNO / สนามรบ / เกมอนาคต)

เว็บกับบอทเป็นคนละโปรเซส เว็บเรียกฟังก์ชันในไฟล์นี้ตรง ๆ ไม่ได้
จึงใช้สะพานคิวแบบเดียวกับ role_grant_worker: เว็บตรวจสิทธิ์แล้วโยนแถวลง
lobby_invite_queue → บอทตัวนี้ไล่มาส่ง DM จริงให้

🔒 กติกาทั้งหมดตัดสินที่ _validate() เท่านั้น เว็บกับบอทเรียกฟังก์ชันเดียวกัน
   ไม่มีทางเลี่ยงเช็คฝั่งใดฝั่งหนึ่ง
"""
import discord
from discord.ext import commands, tasks

from license_server import web_db

# 🔒 validate()/_rate_limited()/reset_rate_limit()/INVITE_LIMIT/INVITE_WINDOW ย้ายไป
# core/services/lobby_invite.py แล้ว (ตรรกะสิทธิ์ล้วน ๆ ไม่แตะ discord — ใช้ร่วมกับเว็บ)
# เหลือสะพานไว้ตรงนี้ ให้โค้ดเดิม/เทสเดิมเรียกผ่านโมดูลนี้ได้เหมือนก่อนรื้อ
from core.services.lobby_invite import (  # noqa: F401
    INVITE_LIMIT, INVITE_WINDOW, validate, reset_rate_limit,
)

POLL_SECONDS = 10
BATCH = 10

GAME_NAMES = {"uno": "🎴 ศึกไพ่รูน", "worms": "🪱 สนามรบผลัดเทิร์น"}


def game_label(game):
    return GAME_NAMES.get(game, str(game))


async def send_invite(bot, from_uid, to_uid, game, code):
    """ส่งคำเชิญ — เช็คสิทธิ์ก่อนเสมอ แล้วค่อยยิง DM จริง

    คืน (สำเร็จไหม, ข้อความบอกผล) — ห้าม crash แม้เพื่อนปิด DM อยู่
    """
    ok, msg = validate(from_uid, to_uid, game, code)
    if not ok:
        return False, msg

    to_uid = int(to_uid)
    member = None
    for guild in bot.guilds:
        member = guild.get_member(to_uid)
        if member:
            break
    if not member:
        try:
            member = await bot.fetch_user(to_uid)
        except discord.HTTPException:
            member = None
    if not member:
        return False, f"เพื่อนปิด DM อยู่ — ส่งรหัสห้องให้เองได้เลย: {code}"

    from_name = "เพื่อนของคุณ"
    try:
        from bot.models import player_model
        p = player_model.get_player(int(from_uid))
        from_name = (p or {}).get("rank") or from_name
    except Exception:
        pass

    label = game_label(game)
    text = (f"🎴 **{from_name}** ชวนคุณเล่น{label}!\n"
            f"รหัสห้อง **{code}**")
    view = LobbyInviteView(int(to_uid), game, code)
    try:
        await member.send(text, view=view)
    except discord.Forbidden:
        return False, f"เพื่อนปิด DM อยู่ — ส่งรหัสห้องให้เองได้เลย: {code}"
    except discord.HTTPException as e:
        return False, f"ส่งคำเชิญไม่สำเร็จ ({type(e).__name__}) — ส่งรหัสห้องให้เองได้เลย: {code}"
    return True, "✅ ส่งคำเชิญแล้ว"


class LobbyInviteView(discord.ui.View):
    """ปุ่มรับคำเชิญ — ยึดแบบ GuildInviteView (bot/cogs/guild.py)"""

    def __init__(self, target_id, game, code):
        super().__init__(timeout=120)
        self.target_id = int(target_id)
        self.game = game
        self.code = code

    async def interaction_check(self, interaction: discord.Interaction):
        if interaction.user.id != self.target_id:
            await interaction.response.send_message("❌ คำเชิญนี้ไม่ใช่ของคุณ!", ephemeral=True)
            return False
        return True

    @discord.ui.button(label="✅ เข้าร่วม", style=discord.ButtonStyle.success)
    async def accept(self, interaction: discord.Interaction, button: discord.ui.Button):
        label = game_label(self.game)
        await interaction.response.edit_message(
            content=f"🎉 เข้าร่วม{label}ได้เลย! เปิดเว็บแล้วกรอกรหัสห้อง **{self.code}**",
            view=None)

    @discord.ui.button(label="❌ ไม่เล่น", style=discord.ButtonStyle.secondary)
    async def decline(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.edit_message(content="🕊️ ปฏิเสธคำเชิญแล้ว", view=None)


class LobbyInviteCog(commands.Cog):
    """สะพานคิว — เว็บเขียนคำขอชวนลง lobby_invite_queue บอทมาไล่ส่งจริง"""

    def __init__(self, bot):
        self.bot = bot
        self.drain.start()

    def cog_unload(self):
        self.drain.cancel()

    @tasks.loop(seconds=POLL_SECONDS)
    async def drain(self):
        try:
            with web_db.connect() as conn:
                rows = conn.execute(
                    "SELECT * FROM lobby_invite_queue WHERE status='pending' ORDER BY id LIMIT ?",
                    (BATCH,)).fetchall()
        except Exception as e:
            print(f"⚠️ [LOBBY-INVITE] อ่านคิวไม่ได้: {e}")
            return

        for row in rows:
            try:
                ok, msg = await send_invite(self.bot, row["from_uid"], row["to_uid"],
                                             row["game"], row["code"])
            except Exception as e:
                ok, msg = False, f"ส่งคำเชิญพัง: {type(e).__name__}"
                print(f"⚠️ [LOBBY-INVITE] แถว {row['id']} พัง: {e}")
            try:
                with web_db.connect() as conn:
                    conn.execute(
                        "UPDATE lobby_invite_queue SET status=?, note=?, "
                        "resolved_at=datetime('now','localtime') WHERE id=?",
                        ("done" if ok else "failed", msg, row["id"]))
            except Exception as e:
                print(f"⚠️ [LOBBY-INVITE] อัปเดตแถว {row['id']} ไม่ได้: {e}")

    @drain.before_loop
    async def before_drain(self):
        await self.bot.wait_until_ready()


async def setup(bot):
    await bot.add_cog(LobbyInviteCog(bot))
