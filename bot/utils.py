# utils.py
from discord.ext import commands
import time
import models.player_model as player_model
import asyncio

def not_arrested():
    async def predicate(ctx):
        player = player_model.get_player(ctx.author.id)
        
        # 1. เช็กว่าเจอข้อมูลผู้เล่นไหม
        if not player:
            print(f"DEBUG: [not_arrested] ไม่พบข้อมูลผู้เล่น {ctx.author.name}")
            return True

        # 2. เช็กสถานะติดคุก
        if player.get("current_state") == "arrested":
            arrest_until = player.get("arrest_until", 0)
            print(f"DEBUG: [not_arrested] ผู้เล่น {ctx.author.name} ติดคุกอยู่ (จะพ้นคุกตอน {arrest_until})")
            
            # 3. เช็กว่าหมดเวลาคุกหรือยัง
            if time.time() >= int(arrest_until):
                print(f"DEBUG: [not_arrested] เวลาคุกหมดแล้ว! กำลังปลดคุกให้ผู้เล่น {ctx.author.name}")
                player_model.update_player_field(ctx.author.id, "current_state", "idle")
                player_model.update_player_field(ctx.author.id, "arrest_until", 0)
                return True
            
            # 4. กรณีติดคุกอยู่จริง
            print(f"DEBUG: [not_arrested] ผู้เล่น {ctx.author.name} ยังติดคุกอยู่ (ปฏิเสธคำสั่ง)")
            raise commands.CheckFailure("arrested")
            
        print(f"DEBUG: [not_arrested] ผู้เล่น {ctx.author.name} สถานะปกติ (อนุญาตให้ผ่าน)")
        return True
    return commands.check(predicate)

def allowed_channels(channel_names):
    async def predicate(ctx):
        if ctx.channel.name not in channel_names:
            # 1. ส่งข้อความเตือน
            msg = await ctx.send(f"❌ **ผิดห้อง!** คำสั่งนี้ใช้ได้เฉพาะในห้อง: `{'`, `'.join(channel_names)}` เท่านั้นครับ")
            
            # 2. รอ 5 วินาทีแล้วลบทั้งคำสั่งของผู้เล่น และข้อความเตือนของบอททิ้ง
            try:
                await asyncio.sleep(5) # รอ 5 วินาที
                await msg.delete()     # ลบข้อความบอท
                await ctx.message.delete() # ลบข้อความที่ผู้เล่นพิมพ์
            except:
                pass # กันกรณีบอทไม่มีสิทธิ์ลบ
            
            return False
        return True
    return commands.check(predicate)

def has_role_or_owner(role_name: str):
    async def predicate(ctx):
        is_owner = ctx.author.id == ctx.guild.owner_id
        has_role = any(role.name == role_name for role in ctx.author.roles)
        if not (is_owner or has_role):
            await ctx.send(f"❌ คำสั่งนี้ใช้ได้เฉพาะ ยศ `{role_name}` หรือ เจ้าของเซิร์ฟเวอร์เท่านั้น!")
            return False
        return True
    return commands.check(predicate)