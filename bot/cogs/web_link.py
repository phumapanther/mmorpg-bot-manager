# bot/cogs/web_link.py
"""สะพานเว็บไซต์เกม ↔ ดิสคอร์ด — !weblogin (ยืนยันโค้ดล็อกอินเว็บ) + !web (ส่งลิงก์เว็บ)

โหลดเฉพาะเซิร์ฟหลัก และทำงานเฉพาะเครื่องที่มีโฟลเดอร์ license_server (เครื่องผู้พัฒนา/เจ้าของเกม)
— เครื่องลูกค้าที่ลงจาก exe ไม่มีโฟลเดอร์นี้ cog จะข้ามตัวเองเงียบๆ ไม่กระทบอะไร
"""
import os
import re
import sqlite3
import time

import discord
from discord.ext import commands

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
WEB_DB = os.path.join(_ROOT, "license_server", "web.db")
URL_FILE = os.path.join(_ROOT, "LICENSE_SERVER_URL.txt")
_CODE_RE = re.compile(r"^[A-Z0-9]{6}$")


def confirm_login_code(code, discord_id, db_path=None):
    """ยืนยันโค้ดล็อกอินเว็บ — คืน (สำเร็จไหม, ข้อความตอบผู้เล่น) — แยกจาก discord เพื่อเทสตรงได้"""
    code = (code or "").strip().upper()
    if not _CODE_RE.match(code):
        return False, "❌ รูปแบบโค้ดไม่ถูกต้อง — ต้องเป็นโค้ด 6 ตัวจากหน้าเว็บ เช่น `!weblogin AB12CD`"
    path = db_path or WEB_DB
    if not os.path.exists(path):
        return False, "❌ ระบบเว็บยังไม่เปิดใช้งานบนเซิร์ฟนี้"
    conn = sqlite3.connect(path, timeout=5)
    try:
        conn.execute("PRAGMA busy_timeout=5000")
        cur = conn.execute(
            "UPDATE login_codes SET discord_id=? "
            "WHERE code=? AND discord_id IS NULL AND used=0 AND expires_at > ?",
            (str(discord_id), code, time.time()))
        conn.commit()
        if cur.rowcount == 0:
            return False, "❌ โค้ดไม่ถูกต้องหรือหมดอายุแล้ว — กลับไปกดขอโค้ดใหม่ที่หน้าเว็บ"
        return True, "✅ **ล็อกอินสำเร็จ!** กลับไปที่หน้าเว็บได้เลย ระบบจะพาเข้าโปรไฟล์อัตโนมัติ"
    finally:
        conn.close()


def website_url():
    try:
        return open(URL_FILE, encoding="utf-8").read().strip()
    except OSError:
        return ""


# ── เติมเงินจากในเกม — ใช้ web.db/คิวแอดมิน ชุดเดียวกับหน้าเว็บทุกประการ ──

UPLOAD_DIR = os.path.join(_ROOT, "license_server", "web_uploads")


def create_topup(discord_id, amount_thb):
    """สร้างรายการเติมเงินจากในเกม — คืน (ok, ข้อความ error, {id, gold, qr, promptpay})"""
    try:
        from license_server import web_db
    except ImportError:
        return False, "❌ ระบบเติมเงินยังไม่เปิดบนเซิร์ฟนี้", None
    from bot import config_loader
    from bot.promptpay import build_qr_png

    pay = config_loader.get_config().get("payment", {})
    pp = pay.get("promptpay", {})
    if not pp.get("enabled") or not pp.get("id"):
        return False, "❌ ยังไม่เปิดรับเติมเงิน (แอดมินยังไม่ตั้งค่า PromptPay)", None
    try:
        amt = float(amount_thb)
    except (TypeError, ValueError):
        return False, "❌ ใส่จำนวนเงินเป็นตัวเลข เช่น 100", None
    mn = float(pay.get("min_amount") or 0)
    mx = float(pay.get("max_amount") or 0)
    if amt <= 0 or (mn and amt < mn) or (mx and amt > mx):
        return False, f"❌ จำนวนเงินต้องอยู่ระหว่าง {mn:g} - {mx:g} บาท", None
    gold = int(amt * float(pay.get("exchange_rate") or 0))
    if gold <= 0:
        return False, "❌ อัตราแลกเปลี่ยนยังไม่ถูกตั้งค่า — แจ้งแอดมิน", None

    with web_db.connect() as conn:
        cur = conn.execute(
            "INSERT INTO topups(discord_id, amount_thb, gold, ip, user_agent) VALUES (?,?,?,?,?)",
            (str(discord_id), amt, gold, "discord", "ปุ่มเติมเงินในเกม"))
    return True, "", {"id": cur.lastrowid, "gold": gold,
                      "qr": build_qr_png(pp["id"], amt), "promptpay": pp}


def save_slip(discord_id, topup_id, image_bytes):
    """บันทึกสลิปจากแชท — ไฟล์เดียวกับที่หน้าเว็บ/หลังบ้านแอดมินใช้ (web_uploads/slip_<id>.jpg)"""
    try:
        from license_server import web_db
    except ImportError:
        return False, "❌ ระบบเติมเงินยังไม่เปิดบนเซิร์ฟนี้"
    import io
    from PIL import Image

    with web_db.connect() as conn:
        row = conn.execute("SELECT * FROM topups WHERE id=? AND discord_id=?",
                           (int(topup_id or 0), str(discord_id))).fetchone()
    if not row:
        return False, "❌ ไม่พบรายการนี้ของคุณ — เช็คเลขรายการอีกครั้ง (ดูจากข้อความตอนกดเติมเงิน)"
    if row["status"] != "pending":
        return False, "❌ รายการนี้ถูกตัดสินไปแล้ว"
    if len(image_bytes) > 5 * 1024 * 1024:
        return False, "❌ ไฟล์ใหญ่เกิน 5MB"
    try:
        img = Image.open(io.BytesIO(image_bytes))
        img.load()
    except Exception:
        return False, "❌ ไฟล์ที่แนบเปิดเป็นรูปไม่ได้ — ส่งเป็นรูปภาพ (png/jpg)"
    img = img.convert("RGB")
    img.thumbnail((1280, 1280))
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    img.save(os.path.join(UPLOAD_DIR, f"slip_{int(topup_id)}.jpg"), format="JPEG", quality=85)
    return True, f"✅ รับสลิปรายการ #{topup_id} แล้ว! แอดมินจะตรวจสอบและอนุมัติโดยเร็ว (เช็คสถานะ: เมนู 🌐 เว็บไซต์ → โปรไฟล์)"


class TopupModal(discord.ui.Modal, title="💎 เติมเงินเข้าเกม"):
    amount_input = discord.ui.TextInput(label="จำนวนเงิน (บาท)", placeholder="เช่น 100",
                                        max_length=10, required=True)

    async def on_submit(self, interaction: discord.Interaction):
        ok, msg, data = create_topup(interaction.user.id, str(self.amount_input.value).strip())
        if not ok:
            return await interaction.response.send_message(msg, ephemeral=True)
        pp = data["promptpay"]
        f = discord.File(data["qr"], filename="topup_qr.png")
        embed = discord.Embed(
            title=f"💎 รายการเติมเงิน #{data['id']}",
            description=(f"โอน **{float(self.amount_input.value):g} บาท** → ได้ **🪙 {data['gold']:,} ทอง**\n"
                         f"PromptPay: `{pp.get('id', '')}` ({pp.get('name', '')})\n\n"
                         f"1️⃣ สแกน QR ด้านล่างโอนเงิน\n"
                         f"2️⃣ โอนเสร็จ **ส่งสลิปในห้องนี้** ด้วยคำสั่ง:\n"
                         f"`!slip {data['id']}` พร้อมแนบรูปสลิป\n"
                         f"3️⃣ แอดมินตรวจ → ทองเข้าธนาคารในเกมอัตโนมัติ"),
            color=0xd93b2b)
        # แนบ QR เป็นไฟล์ตรงๆ (ไม่อ้าง attachment:// ใน embed) — ephemeral บางทีไม่เรนเดอร์ภาพใน embed
        await interaction.response.send_message(embed=embed, file=f, ephemeral=True)


def is_admin_gated(command):
    """คำสั่งนี้ล็อกสิทธิ์แอดมินไหม — ดูจากชื่อ check ที่ decorator แปะไว้
    ครอบทั้ง has_permission(กลุ่มยศ) ของโปรเจ็ค และ @commands.has_permissions ของ discord.py"""
    for chk in getattr(command, "checks", []):
        q = getattr(chk, "__qualname__", "")
        if "has_permission" in q:   # ครอบ has_permission + has_permissions
            return True
    return False


def log_admin_command(discord_id, user_name, command, full_text, channel="", guild=""):
    """จดการใช้คำสั่งแอดมินลง web.db — พังเงียบ ไม่มีทางทำให้คำสั่งจริงล้ม"""
    try:
        from license_server import web_db
        with web_db.connect() as conn:
            conn.execute(
                "INSERT INTO admin_logs(discord_id, user_name, command, full_text, channel, guild) "
                "VALUES (?,?,?,?,?,?)",
                (str(discord_id), str(user_name)[:100], str(command)[:100],
                 str(full_text)[:500], str(channel)[:100], str(guild)[:100]))
        return True
    except Exception:
        return False


class WebLink(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_command(self, ctx):
        """🛡️ log ทุกคำสั่งที่ล็อกสิทธิ์แอดมิน — ใคร ใช้อะไร เมื่อไหร่ พิมพ์ว่าอะไร (ดูได้ที่เว็บ /admin)"""
        if ctx.command and is_admin_gated(ctx.command):
            log_admin_command(ctx.author.id, ctx.author, ctx.command.qualified_name,
                              ctx.message.content or "",
                              getattr(ctx.channel, "name", "DM"),
                              getattr(ctx.guild, "name", "-"))

    # ⚠️ ไม่ล็อกเซิร์ฟหลัก — บอทแจก (เซิร์ฟรอง) ก็ยืนยันล็อกอิน/รับสลิปได้
    # ปลอดภัยเพราะตัวตนอิงจากบัญชี Discord ผู้พิมพ์เสมอ และ cog โหลดเฉพาะเครื่องที่มี license_server
    @commands.command(name="weblogin")
    async def weblogin(self, ctx, code: str = ""):
        ok, msg = confirm_login_code(code, ctx.author.id)
        try:
            await ctx.message.delete()   # ลบโค้ดออกจากแชท (best-effort)
        except Exception:
            pass
        await ctx.send(f"{ctx.author.mention} {msg}", delete_after=30 if ok else 20)

    @commands.command(name="slip")
    async def slip(self, ctx, topup_id: int = 0):
        """ส่งสลิปโอนเงิน: !slip <เลขรายการ> พร้อมแนบรูป — ขึ้นคิวแอดมินทันที"""
        if not ctx.message.attachments:
            return await ctx.send(f"{ctx.author.mention} 📎 แนบรูปสลิปมาพร้อมคำสั่งด้วยครับ เช่นพิมพ์ `!slip {topup_id or 12}` แล้วแนบรูปในข้อความเดียวกัน")
        data = await ctx.message.attachments[0].read()
        ok, msg = save_slip(ctx.author.id, topup_id, data)
        if ok:
            try:
                await ctx.message.delete()   # ลบรูปสลิปออกจากแชท (เก็บเข้าระบบแล้ว — กันคนอื่นเห็นข้อมูลบัญชี)
            except Exception:
                pass
        await ctx.send(f"{ctx.author.mention} {msg}")

    @commands.command(name="web")
    async def web(self, ctx):
        url = website_url()
        if not url:
            return await ctx.send("🌐 เว็บไซต์ยังไม่เปิดให้บริการตอนนี้ครับ")
        embed = discord.Embed(
            title="🌐 เว็บไซต์เกม",
            description=(f"ข่าวสาร · อัพเดทแพทช์ · ข้อมูลเกม · เติมเกม · โปรไฟล์\n{url}\n\n"
                         f"🔑 ล็อกอินเว็บ: กดขอโค้ดที่หน้าเว็บ แล้วพิมพ์ `!weblogin <โค้ด>` ที่นี่"),
            color=0xd93b2b)
        await ctx.send(embed=embed)


async def setup(bot):
    if not os.path.isdir(os.path.join(_ROOT, "license_server")):
        print("🌐 [web_link] เครื่องนี้ไม่มี license_server — ข้าม cog เว็บ")
        return
    await bot.add_cog(WebLink(bot))
