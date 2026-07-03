import discord
from discord.ext import commands
import asyncio
from utils import not_arrested, allowed_channels  # 👈 ใส่บรรทัดนี้ลงไป
class AdventureZone(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        # 🔒 ทะเบียนเช็กสถานะห้อง {user_id: channel_id}
        # เพื่อล็อกให้ 1 คนสร้างได้แค่ 1 ห้องจนกว่าจะโดนทำลาย
        self.active_rooms = {}

    @not_arrested() #ตรวจการถูกจับกุมก่อนอนุญาตให้ใช้คำสั่ง
    @commands.command(name="adv")
    @allowed_channels(["⚔-เริ่มเกม-⚔"])
    @commands.cooldown(1, 5.0, commands.BucketType.user)
    async def create_adventure_room(self, ctx):
        """คำสั่งสร้างห้องแชทผจญภัยออโต้ ถัดจากห้องเดิม ล็อกให้สร้างได้แค่คนละ 1 ห้องจนกว่าจะสลายไป"""
        guild = ctx.guild
        author = ctx.author
        current_channel = ctx.channel

        # 🛡️ [ระบบล็อก 1 คนต่อ 1 ห้อง] เช็กว่าผู้เล่นคนนี้มีห้องที่ทำงานค้างอยู่ไหม
        if author.id in self.active_rooms:
            # ดึงข้อมูลห้องจาก Discord มาตรวจสอบว่าห้องยังอยู่จริงไหม
            existing_channel = self.bot.get_channel(self.active_rooms[author.id])
            if not existing_channel:
                try:
                    existing_channel = await guild.fetch_channel(self.active_rooms[author.id])
                except:
                    existing_channel = None

            if existing_channel:
                # ถ้าห้องเก่ายังอยู่จริง ดักปฏิเสธไม่ให้สร้างใหม่ทันที!
                await ctx.send(
                    f"❌ **[สิทธิ์เต็ม]** คุณ {author.mention} มีมิติส่วนตัวที่เปิดค้างไว้ชั่วคราวแล้วครับ!\n"
                    f"📌 กรุณาไปใช้งานที่ห้องเดิมก่อน ➡️ {existing_channel.mention} หรือรอให้ห้องนั้นเงียบครบ 1 นาทีจนสลายไปก่อนครับ",
                    delete_after=10.0
                )
                return
            else:
                # ถ้าห้องสลายไปแล้วแต่ทะเบียนยังค้างอยู่ ให้ล้างทะเบียนห้องของไอดีนี้ทิ้งเพื่อเปิดให้สร้างใหม่
                if author.id in self.active_rooms:
                    del self.active_rooms[author.id]

        # ⏳ ส่งข้อความเริ่มร่ายเวทสร้างมิติ
        status_msg = await ctx.send(f"⏳ **[สมาคมนักผจญภัย]** กำลังจัดเตรียมมิติส่วนตัวให้คุณ {author.mention}...")

        # 🛡️ เซ็ตค่าสิทธิ์การมองเห็น (เห็นคนเดียว)
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(view_channel=False),
            author: discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True),
            guild.me: discord.PermissionOverwrite(view_channel=True, send_messages=True)
        }

        try:
            # 📐 กลับมาใช้ลอจิกเดิม: ให้ห้องใหม่สร้างอยู่ถัดลงมาจากห้องเดิมเป๊ะๆ
            target_category = current_channel.category
            new_position = current_channel.position + 1

            room_name = f"⚔️-มิติส่วนตัว-{author.name}"
            adv_channel = await guild.create_text_channel(
                name=room_name,
                category=target_category,
                position=new_position,
                overwrites=overwrites,
                topic=f"ห้องผจญภัยส่วนตัวของ {author.name} | เงียบครบ 1 นาทีห้องจะปิดตัวลงทันที"
            )

            # 🔥 ลงทะเบียนล็อกสิทธิ์ทันทีว่าไอดีนี้ยึดห้องนี้ไว้แล้ว
            self.active_rooms[author.id] = adv_channel.id

            # 🎨 ข้อความ Embed ต้อนรับ
            embed = discord.Embed(
                title=f"🌲 มิติผจญภัยส่วนตัวของ {author.name}",
                description=(
                    f"ยินดีต้อนรับคุณ {author.mention} เข้าสู่ห้องจำลองการเดินทาง!\n"
                    f"🔒 **ห้องนี้เป็นห้องลับ:** มีเพียงคุณและผู้ดูแลระบบเท่านั้นที่มองเห็นเนื้อหาในนี้\n\n"
                    f"⚠️ **[ระบบทำลายตัวเองทำงาน]:** หากไม่มีการพิมพ์ข้อความใด ๆ ในห้องนี้เป็นเวลา **1 นาที** ห้องนี้จะสลายหายไปทันทีครับ!\n"
                    f"⚔️ **[ซื้อยศคลาสได้ที่]:** <#💸ซื้อยศออโต้💸> หรือ #💸ซื้อยศออโต้💸\n"
                    f"⚔️ **[เริ่มออกเดินทาง]:** พิมพ์คำสั่ง `!play` ในห้องนี้เพื่อเปิดฉากการผจญภัยได้เลย!\n"
                    f"🎒 **[คำสั่งพื้นฐาน]:** พิมพ์คำสั่ง `!bag` เพื่อเปิดดูช่องเก็บของ และพิมพ์ `!use <เลขไอเทม>` เพื่อใช้งานอุปกรณ์ต่างๆ\n"
                ),
                color=0x319795
            )
            embed.set_thumbnail(url=author.display_avatar.url)
            await adv_channel.send(embed=embed)

            # 🧼 ส่งปุ่มกด Link Button วาร์ปเข้าห้อง
            view = discord.ui.View()
            view.add_item(discord.ui.Button(label="⚔️ คลิกเพื่อเข้าสู่มิติผจญภัย", url=f"https://discord.com/channels/{guild.id}/{adv_channel.id}"))
            await status_msg.edit(content=f"✨ **[ประตูมิติเปิดออกแล้ว!]** ประตูมิติส่วนตัวของคุณจัดเตรียมเสร็จสิ้นแล้วครับคุณ {author.mention}", view=view)

           # ⏱️ ระบบดักตรวจจับความเคลื่อนไหว (รองรับทั้งการพิมพ์และการกดปุ่ม/โต้ตอบ)
            def check_message(message):
                return message.channel.id == adv_channel.id

            def check_interaction(interaction):
                return interaction.channel_id == adv_channel.id

            while True:
                try:
                    # สร้างงานพร้อมกัน 2 ขา: ขาหนึ่งรอข้อความ อีกขารอการกดปุ่ม
                    done, pending = await asyncio.wait(
                        [
                            asyncio.create_task(self.bot.wait_for('message', check=check_message)),
                            asyncio.create_task(self.bot.wait_for('interaction', check=check_interaction))
                        ],
                        timeout=60.0,
                        return_when=asyncio.FIRST_COMPLETED
                    )

                    # เคลียร์งานที่ยังค้างคาอยู่ทิ้งไปเพื่อเริ่มนับ 1 นาทีใหม่ในลูปถัดไป
                    for task in pending:
                        task.cancel()

                    # ถ้ามีเหตุการณ์อย่างใดอย่างหนึ่งเกิดขึ้นมา (done ไม่ว่าง) แปลว่ายังแอคทีฟอยู่ -> วนลูปต่อเวลาทันที
                    if done:
                        continue
                    else:
                        # กรณีหลุดมาโดยไม่มีอะไรทำ (Timeout)
                        raise asyncio.TimeoutError

                except asyncio.TimeoutError:
                    # 💥 เมื่อห้องเงียบสนิทครบ 1 นาที ไม่มีทั้งการพิมพ์และกดปุ่ม สั่งลบห้องทันที
                    try:
                        await adv_channel.delete(reason="ห้องผจญภัยไม่มีการเคลื่อนไหวครบ 1 นาที")
                    except:
                        pass
                        
                    if author.id in self.active_rooms:
                        del self.active_rooms[author.id]
                    
                    try:
                        await ctx.send(f"🌌 **[มิติสลาย]** มิติส่วนตัวของคุณ {author.mention} ได้สลายหายไปเรียบร้อยแล้วเนื่องจากไม่มีการเคลื่อนไหว", delete_after=5.0)
                    except:
                        pass
                    break

        except discord.Forbidden:
            await status_msg.edit(content="❌ **บอทเกิดข้อผิดพลาด:** บอทไม่มีสิทธิ์ในการจัดการห้องแชท")
            if author.id in self.active_rooms:
                del self.active_rooms[author.id]
        except Exception as e:
            print(f"⚠️ เกิดข้อผิดพลาดในระบบสร้างห้อง: {e}")
            if author.id in self.active_rooms:
                del self.active_rooms[author.id]

# โหลดเข้าบอทหลัก
async def setup(bot):
    await bot.add_cog(AdventureZone(bot))