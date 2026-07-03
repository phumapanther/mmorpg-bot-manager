import discord
from discord.ext import commands

class OwnerAnnounce(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # ─── 📢 คำสั่งประกาศเฉพาะกิจ ล็อกสิทธิ์คุณอาเธอร์คนเดียวเท่านั้น (!announce) ───
    @commands.command(name="announce")
    async def announce(self, ctx):
        """คำสั่งประกาศข้อความที่ฟิกซ์ไว้ในโค้ด @everyone แบบเงียบ ล็อกเฉพาะ ID คุณอาเธอร์"""
        
        # 🛡️ [กฎเหล็ก] เช็ก ID คนพิมพ์สั่ง ถ้าไม่ใช่คุณอาเธอร์... เตะทิ้งและไม่ทำงานต่อทันที!
        if ctx.author.id != 300201059459268609:
            await ctx.send("❌ **[ปฏิเสธเข้าถึง]** คำสั่งควบคุมระดับสูงนี้ล็อกสิทธิ์ให้เจ้าของบอทใช้งานได้เท่านั้นครับ", delete_after=5.0)
            return

        # 📝 [กล่องข้อความคอนเทนต์] อัปเดตข้อมูลระบบเกมเวอร์ชันล่าสุดของคุณอาเธอร์เรียบร้อยครับ
        announcement_title = "📢 [ANNOUNCEMENT] ระบบเปิดทำการแล้วตอนนี้!"
        # 📝 [กล่องข้อความคอนเทนต์ - เวอร์ชันขยายตัวใหญ่เบิ้มกระแทกตา]
        # 📝 [กล่องข้อความคอนเทนต์ - อัปเดตเพิ่มระบบช่องผจญภัยส่วนตัว !adv]
        announcement_text = (
            "==========================================\n\n"
            "## 🎙️ ONLINE FOR XP\n"
            "> ยิ่งออนนานเวลยิ่งอัพ เลเวลสูงปลดล็อคยศใหม่อัตโนมัต!\n\n"
            "## 💬 CHAT FOR MONEY\n"
            "> ทุกข้อความที่พิมพ์แชทคุยกัน จะเปลี่ยนเป็นเงิน\n\n"
            "## 🎲 GACHA\n"
            "> เอาเงินที่ได้ มาเสี่ยงดวงสุ่มยศเปลี่ยนเผ่าได้ที่ `!shop`\n\n"
            "## 🌲 PRIVATE ADVENTURE\n"
            "> พิมพ์ `!adv` เพื่อเปิดประตูมิติสร้างห้องผจญภัยส่วนตัว ลุยได้แบบไม่รบกวนใคร!\n\n"
            "==========================================\n\n"
            "# ⌨️ [COMMANDS]\n"
            "### 🧭 เปิดประตูมิติส่วนตัว พิมพ์คำสั่ง: `!adv`\n"
            "### 📊 ตรวจสอบสถานะตัวเอง พิมพ์คำสั่ง: `!profile`\n"
            "### ⚔️ เริ่มออกเดินทาง พิมพ์คำสั่ง: `!play` *(ใช้งานได้เฉพาะในห้องมิติส่วนตัวเท่านั้น)*\n\n"
            "=========================================="
        )

        # 🎨 สร้างโครง Embed ประกาศ (จัดกลุ่มสีฟ้าเข้มสไตล์ MMORPG คลีนๆ)
        embed = discord.Embed(
            title=announcement_title,
            description=announcement_text,
            color=0x2b6cb0 
        )
        embed.set_footer(text=f"ประกาศโดยหัวหน้าสมาคม: {ctx.author.name} | โลก D&D MMORPG", icon_url=ctx.author.display_avatar.url)

        try:
            # 🧼 ลบข้อความคำสั่ง !announce ที่คุณอาเธอร์พิมพ์ เพื่อความเนียนของช่องแชท
            await ctx.message.delete()
            
            # 💥 ลอจิกส่งคำแจ้งเตือน @everyone แบบปิดแท็ก (แท็กจะเด้งหาทุกคน แต่จะไม่มีคำว่า @everyone โผล่เป็นตัวอักษรรกแฝง)
            allowed_mentions = discord.AllowedMentions(everyone=True)
            
            # ยิงประกาศลงห้องแชทนั้น ๆ ทันที
            await ctx.send(content="@everyone", embed=embed, allowed_mentions=allowed_mentions)
            print(f"📢 [OWNER ANNOUNCE] คุณอาเธอร์ ได้สั่งรันประกาศเปิดระบบเรียบร้อยแล้ว")
            
        except discord.Forbidden:
            # เผื่อกรณีบอทไม่มีสิทธิ์ลบข้อความในห้องนั้น ให้พ่น Embed ออกไปก่อนเลย
            await ctx.send(embed=embed, allowed_mentions=discord.AllowedMentions(everyone=True))
        except Exception as e:
            print(f"⚠️ เกิดข้อผิดพลาดในระบบประกาศของโอเนอร์: {e}")

# ฟังก์ชันสำหรับให้บอทโหลดโมดูลนี้เข้าสู่ระบบ
async def setup(bot):
    await bot.add_cog(OwnerAnnounce(bot))