import discord
from discord.ext import commands, tasks
import models.player_model as player_model
from utils import not_arrested, allowed_channels

class PrivateRoom(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.rented_rooms = {} # {owner_id: {"channel_id": int, "visible": bool, "limit": int}}
        self.room_check_loop.start()

    def cog_unload(self):
        self.room_check_loop.cancel()

    @allowed_channels(["📃สัญญาเช่า📃"])
    @not_arrested() # 🛠️ บล็อกคนติดคุก
    @commands.command(name="rent")
    async def rent_room(self, ctx, amount: int = 60):
        if ctx.author.id in self.rented_rooms:
            return await ctx.send("❌ คุณมีห้องเช่าอยู่แล้ว!")

        player = player_model.get_player(ctx.author.id)
        if player.get("cash", 0) < amount:
            return await ctx.send("❌ เงินไม่พอเช่า (ราคา 1 ทอง ต่อ 1 วินาที)")

        # หักเงินก้อนแรก
        player_model.increment_player_field(ctx.author.id, "cash", -amount)

        guild = ctx.guild
        category = discord.utils.get(guild.categories, name="🏠 ห้องเช่าส่วนตัว")
        if not category:
            category = await guild.create_category("🏠 ห้องเช่าส่วนตัว")
            
        channel = await guild.create_voice_channel(f"🏠 {ctx.author.name}'s Room", category=category)
        
        self.rented_rooms[ctx.author.id] = {
            "channel_id": channel.id,
            "seconds_left": amount
        }
        await ctx.send(f"✅ เช่าห้องสำเร็จ! ห้องจะคงอยู่เป็นเวลา {amount} วินาที หักเงิน {amount}")

    @commands.command(name="extend")
    async def extend_room(self, ctx, amount: int):
        room_data = self.rented_rooms.get(ctx.author.id)
        if not room_data: return await ctx.send("❌ คุณไม่ได้เป็นเจ้าของห้อง!")
        
        player = player_model.get_player(ctx.author.id)
        if player.get("cash", 0) < amount:
            return await ctx.send("❌ เงินไม่พอเติมเวลา!")
            
        player_model.increment_player_field(ctx.author.id, "cash", -amount)
        room_data["seconds_left"] += amount
        await ctx.send(f"✅ เติมเวลาให้ห้องสำเร็จ เพิ่มไป {amount} วินาที!")

    @tasks.loop(seconds=1.0)
    async def room_check_loop(self):
        for owner_id, data in list(self.rented_rooms.items()):
            player = player_model.get_player(owner_id)
            if not player or player.get("cash", 0) <= 0:
                data["seconds_left"] = 0
            else:
                data["seconds_left"] -= 1
                player_model.increment_player_field(owner_id, "cash", -1)

            if data["seconds_left"] <= 0:
                channel = self.bot.get_channel(data["channel_id"])
                if channel: await channel.delete()
                if owner_id in self.rented_rooms:
                    del self.rented_rooms[owner_id]
                
                owner = self.bot.get_user(owner_id)
                # if owner: await owner.send("หมดเวลาเช่าห้อง หรือเงินในกระเป๋าหมด ห้องถูกปิดครับ")

    @room_check_loop.before_loop
    async def before_check(self):
        await self.bot.wait_until_ready()

    @commands.command(name="set_room")
    async def set_room(self, ctx, action: str, value: str):
        room_data = self.rented_rooms.get(ctx.author.id)
        if not room_data: return await ctx.send("❌ คุณไม่ได้เป็นเจ้าของห้อง!")
        
        channel = self.bot.get_channel(room_data["channel_id"])
        if not channel:
            del self.rented_rooms[ctx.author.id]
            return await ctx.send("❌ ห้องของคุณถูกลบไปแล้ว!")

        if action == "visible":
            is_visible = (value.lower() == "true")
            overwrites = channel.overwrites
            overwrites[ctx.guild.default_role] = discord.PermissionOverwrite(view_channel=is_visible)
            await channel.edit(overwrites=overwrites)
            await ctx.send(f"✅ ตั้งค่าการมองเห็นเป็น: {'เปิดสาธารณะ' if is_visible else 'ส่วนตัว'}")

        elif action == "limit":
            try:
                limit = int(value)
                await channel.edit(user_limit=limit)
                await ctx.send(f"✅ จำกัดจำนวนคนเข้าห้องเป็น: {limit} คน")
            except ValueError:
                await ctx.send("❌ กรุณาระบุจำนวนคนเป็นตัวเลข!")

async def setup(bot):
    await bot.add_cog(PrivateRoom(bot))