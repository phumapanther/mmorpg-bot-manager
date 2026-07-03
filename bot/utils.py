# utils.py
from discord.ext import commands
import time
import models.player_model as player_model
import asyncio
from bot import config_loader

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

def allowed_channel(feature_key):
    async def predicate(ctx):
        target = config_loader.get_channel_id(feature_key)
        if target is None:
            return True  # feature not mapped to a channel yet → don't block
        if ctx.channel.id != target:
            try:
                msg = await ctx.send(f"❌ **ผิดห้อง!** คำสั่งนี้ใช้ได้เฉพาะห้องที่แอดมินตั้งไว้เท่านั้นครับ")
                await asyncio.sleep(5)
                await msg.delete()
                await ctx.message.delete()
            except Exception:
                pass
            return False
        return True
    return commands.check(predicate)

def has_permission(group):
    async def predicate(ctx):
        if ctx.author.id == ctx.guild.owner_id:
            return True
        allowed = set(config_loader.get_role_ids(group))
        if any(r.id in allowed for r in ctx.author.roles):
            return True
        await ctx.send("❌ คุณไม่มีสิทธิ์ใช้คำสั่งนี้ (ติดต่อแอดมินเพื่อขอสิทธิ์)")
        return False
    return commands.check(predicate)