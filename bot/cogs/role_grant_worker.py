"""🌉 สะพานแจกยศจากเว็บ (เว็บเกม เฟส 7.3)

เว็บแจกยศ Discord เองไม่ได้ — เว็บหักเงินแล้วโยนรายการเข้า role_grant_queue
บอทตัวนี้คอยหยิบมาแจกให้ แจกไม่สำเร็จเมื่อไหร่ต้องคืนเงินเสมอ

สถานะในคิว: pending -> done | duplicate | refunded (พร้อมเหตุผลใน note)
  duplicate = กาชาสุ่มได้ของที่มีอยู่แล้ว (เกลือตามกติกา ไม่คืนเงิน)
              ถ้าเป็นการ "ซื้อเจาะจง" แล้วซ้ำ = คืนเงิน เพราะผู้เล่นตั้งใจซื้อของที่ยังไม่มี
"""
import discord
from discord.ext import commands, tasks

from bot import role_shop_core
from license_server import web_db

POLL_SECONDS = 15
BATCH = 10


class RoleGrantWorker(commands.Cog):
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
                    "SELECT * FROM role_grant_queue WHERE status='pending' ORDER BY id LIMIT ?",
                    (BATCH,)).fetchall()
        except Exception as e:
            print(f"⚠️ [ROLE-QUEUE] อ่านคิวไม่ได้: {e}")
            return

        for row in rows:
            status, note = await self._grant(row)
            try:
                with web_db.connect() as conn:
                    conn.execute("UPDATE role_grant_queue SET status=?, note=?, "
                                 "resolved_at=datetime('now','localtime') WHERE id=?",
                                 (status, note, row["id"]))
            except Exception as e:
                print(f"⚠️ [ROLE-QUEUE] อัปเดตสถานะแถว {row['id']} ไม่ได้: {e}")

    async def _grant(self, row):
        """แจกยศหนึ่งรายการ — คืน (สถานะใหม่, หมายเหตุ)"""
        uid, price, kind = int(row["discord_id"]), int(row["price"] or 0), row["kind"]

        member = role_obj = None
        for guild in self.bot.guilds:                       # หาเซิร์ฟที่มียศนี้อยู่จริง
            r = guild.get_role(int(row["role_id"]))
            if not r:
                continue
            try:
                member = guild.get_member(uid) or await guild.fetch_member(uid)
            except Exception:
                continue
            if member:
                role_obj, guild_found = r, guild
                break

        if not role_obj or not member:
            role_shop_core.refund(uid, price)
            print(f"[LOG] [ROLE-QUEUE] คืนเงิน {price:,} ให้ {uid} — ไม่เจอยศ/ผู้เล่นในเซิร์ฟ")
            return "refunded", "ไม่พบยศหรือผู้เล่นในเซิร์ฟเวอร์ — คืนเงินแล้ว"

        if role_obj in member.roles:
            if kind == "gacha":
                print(f"[LOG] [ROLE-QUEUE] {uid} หมุนกาชาได้ {row['label']} ซ้ำ (เกลือ)")
                return "duplicate", "สุ่มได้ยศที่มีอยู่แล้ว — เกลือตามกติกากาชา"
            role_shop_core.refund(uid, price)
            return "refunded", "มียศนี้อยู่แล้ว — คืนเงินแล้ว"

        try:
            await member.add_roles(role_obj, reason="ซื้อ/สุ่มผ่านเว็บไซต์เกม")
            print(f"[LOG] [ROLE-QUEUE] 🎖️ แจกยศ {row['label']} ให้ {member.display_name} สำเร็จ")
            return "done", ""
        except discord.Forbidden:
            role_shop_core.refund(uid, price)
            print(f"[LOG] [ROLE-QUEUE] ❌ บอทไม่มีสิทธิ์แจก {row['label']} — คืนเงิน {price:,}")
            return "refunded", "บอทไม่มีสิทธิ์มอบยศนี้ — คืนเงินแล้ว"
        except Exception as e:
            role_shop_core.refund(uid, price)
            print(f"[LOG] [ROLE-QUEUE] ❌ แจกยศพัง: {e} — คืนเงิน {price:,}")
            return "refunded", f"แจกยศไม่สำเร็จ ({type(e).__name__}) — คืนเงินแล้ว"

    @drain.before_loop
    async def before_drain(self):
        await self.bot.wait_until_ready()


async def setup(bot):
    await bot.add_cog(RoleGrantWorker(bot))
