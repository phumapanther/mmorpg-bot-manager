"""🎴 บอททัก DM ชวนเพื่อนเข้าห้อง — ใช้ร่วมได้ทุกเกม (UNO / สนามรบ / เกมอนาคต)

เว็บกับบอทเป็นคนละโปรเซส เว็บเรียกฟังก์ชันในไฟล์นี้ตรง ๆ ไม่ได้
จึงใช้สะพานคิวแบบเดียวกับ role_grant_worker: เว็บตรวจสิทธิ์แล้วโยนแถวลง
lobby_invite_queue → บอทตัวนี้ไล่มาส่ง DM จริงให้

🔒 กติกาทั้งหมดตัดสินที่ _validate() เท่านั้น เว็บกับบอทเรียกฟังก์ชันเดียวกัน
   ไม่มีทางเลี่ยงเช็คฝั่งใดฝั่งหนึ่ง
"""
import time

import discord
from discord.ext import commands, tasks

from bot import friends, lobby
from license_server import web_db

POLL_SECONDS = 10
BATCH = 10

INVITE_LIMIT = 5          # ชวนได้กี่ครั้งต่อหน้าต่างเวลา
INVITE_WINDOW = 60         # วินาที

GAME_NAMES = {"uno": "🎴 ศึกไพ่รูน", "worms": "🪱 สนามรบผลัดเทิร์น"}

# ponytail: ตัวนับความถี่แบบ dict ในแรม พอสำหรับสเกลปัจจุบัน (โปรเซสเดียว)
# ถ้าต้องรันหลายอินสแตนซ์ค่อยย้ายไปตาราง/redis
_invite_hits = {}


def game_label(game):
    return GAME_NAMES.get(game, str(game))


def _rate_limited(from_uid, now=None):
    """คนหนึ่งชวนได้ไม่เกิน INVITE_LIMIT ครั้งต่อ INVITE_WINDOW วินาที"""
    now = time.time() if now is None else now
    key = str(from_uid)
    hits = [t for t in _invite_hits.get(key, []) if now - t < INVITE_WINDOW]
    _invite_hits[key] = hits
    if len(hits) >= INVITE_LIMIT:
        return True
    hits.append(now)
    return False


def reset_rate_limit():
    """สำหรับเทส — เคลียร์ตัวนับความถี่ทั้งหมด"""
    _invite_hits.clear()


def validate(from_uid, to_uid, game, code):
    """เช็คสิทธิ์ทั้งหมดที่ฝั่งเซิร์ฟเวอร์ — ไม่แตะ Discord เลย

    ใช้ร่วมกันทั้งฝั่งเว็บ (ตัดสินก่อนลงคิว) และฝั่งบอท (กันคนแก้คิวตรง ๆ)
    คืน (ok, ข้อความ)
    """
    from_uid, to_uid = int(from_uid), int(to_uid)
    if from_uid == to_uid:
        return False, "❌ ชวนตัวเองไม่ได้นะ"
    if not friends.are_friends(from_uid, to_uid):
        return False, "❌ ต้องเป็นเพื่อนกันก่อนถึงจะชวนได้"
    if lobby.room_of(game, from_uid) != str(code):
        return False, "❌ คุณไม่ได้อยู่ในห้องนี้"
    st = lobby.load(code)
    if not st or st.get("game") != str(game):
        return False, "❌ ห้องไม่มีแล้ว"
    if st.get("started"):
        return False, "❌ ห้องนี้เริ่มเกมไปแล้ว"
    if len(st.get("seats", [])) >= lobby.MAX_SEATS:
        return False, "❌ ห้องเต็มแล้ว"
    if _rate_limited(from_uid):
        return False, "⏳ ชวนถี่เกินไป รอสักครู่แล้วลองใหม่"
    return True, ""


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
