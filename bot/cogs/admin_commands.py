import discord
from discord.ext import commands
from bot.models import player_model  # ดึงโมเดลจัดการฐานข้อมูลมาใช้งาน
from bot.utils import has_permission, allowed_channel, not_arrested, is_main_server
from bot import config_loader
import sqlite3
import json  
import random

class AdminCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # 🔒 [ระบบตรวจสิทธิ์ + พิมพ์ LOG ลง Terminal เท่านั้น]
    async def cog_check(self, ctx):
        # 🌍 P8: คำสั่งแอดมินใช้ได้เฉพาะเซิร์ฟหลักเสมอ — เช็คก่อนเช็คยศ/สิทธิ์
        # (ไม่งั้นเจ้าของเซิร์ฟรองซึ่งเป็น owner/admin ของเซิร์ฟตัวเอง จะยิงคำสั่งแก้ DB ได้ทันที)
        if not is_main_server(ctx):
            print(f"🚨 [P8 BLOCK] {ctx.author.name} พยายามใช้คำสั่งแอดมินจากเซิร์ฟรอง: {ctx.message.content}")
            return False
        is_owner = ctx.author.id == ctx.guild.owner_id
        is_admin = ctx.author.guild_permissions.administrator
        has_permission = is_owner or is_admin

        # 📄 เตรียมข้อความเพื่อฟ้องลงหน้าจอ Terminal บนเซิร์ฟเวอร์คลาวด์
        log_title = "🟢 [ADMIN COMMAND USED]" if has_permission else "🚨 [UNAUTHORIZED ATTEMPT]"
        log_text = (
            f"\n--------------------------------------------------\n"
            f"{log_title} ตรวจพบการเรียกใช้คำสั่งแอดมิน\n"
            f"👤 ผู้ใช้งาน: {ctx.author.name} (ID: {ctx.author.id})\n"
            f"💬 คำสั่งที่พิมพ์: {ctx.message.content}\n"
            f"📍 ช่องแชท: #{ctx.channel.name}\n"
            f"🛡️ Status สิทธิ์: {'✅ ผ่าน (Authorized)' if has_permission else '❌ บล็อกระบบ (Blocked)'}\n"
            f"--------------------------------------------------"
        )

        # 🖥️ สั่งพิมพ์ข้อความลงหน้าจอ Terminal ทันที
        print(log_text)

        # 🛑 ถ้าสิทธิ์ไม่ผ่าน ให้บล็อกไม่ให้คำสั่งทำงาน
        if not has_permission:
            return False
        return True

    # ─── 💰 1. คำสั่งเซ็ตเงินติดตัว (!set_cash แบบแปรผัน บวกลบตามค่า) ───
    @has_permission("admin")
    @not_arrested() #ตรวจการถูกจับกุมก่อนอนุญาตให้ใช้คำสั่ง
    @commands.command(name="set_cash")
    async def set_cash(self, ctx, target: discord.User = None, amount: int = None):
        print(f"🪙 [CASH ADMIN DEBUG] แอดมิน {ctx.author.name} เรียกใช้คำสั่ง !set_cash | target: {target} | amount: {amount}")

        if target is None or amount is None:
            await ctx.send("❓ **วิธีใช้งาน:** `!set_cash [@ชื่อผู้เล่น หรือ ID] [จำนวน]`\n*(ตัวอย่าง: ใส่ `200` เพื่อบวกเพิ่ม / ใส่ `-200` เพื่อหักเงินออก)*")
            return
            
        user_id = target.id
        name = target.display_name

        player = player_model.get_player(user_id)
        if not player:
            await ctx.send(f"❌ ไม่พบข้อมูลตัวละครของ **{name}** ในฐานข้อมูล")
            return
            
        current_cash = player.get("cash", 0)
        new_cash = current_cash + amount
        
        if new_cash < 0:
            new_cash = 0

        player_model.update_player_field(user_id, "cash", new_cash)
        
        if amount >= 0:
            await ctx.send(f"⚡ **[Admin]** ได้เพิ่มทองให้กับ **{name}** จำนวน `+ {amount:,}` ทอง\n🪙 (เงินสดปัจจุบัน: `{new_cash:,}` ทอง) 📈💸")
        else:
            await ctx.send(f"⚡ **[Admin]** ได้หักทองของ **{name}** ออกจำนวน `- {abs(amount):,}` ทอง\n🪙 (เงินสดปัจจุบัน: `{new_cash:,}` ทอง) 📉💸")

    # ─── 🩸 2. คำสั่งเซ็ตเลือดปัจจุบัน (!set_hp) ───
    @has_permission("admin")
    @not_arrested() #ตรวจการถูกจับกุมก่อนอนุญาตให้ใช้คำสั่ง
    @commands.command(name="set_hp")
    async def set_hp(self, ctx, target: discord.User = None, amount: int = None):
        if target is None or amount is None:
            await ctx.send("❓ **วิธีใช้งาน:** `!set_hp [@ชื่อผู้เล่น หรือ ID] [จำนวน]`")
            return
        user_id = target.id
        name = target.display_name
        if not player_model.get_player(user_id):
            await ctx.send(f"❌ ไม่พบข้อมูลตัวละครในฐานข้อมูล")
            return
        player_model.update_player_field(user_id, "hp", amount)
        await ctx.send(f"⚡ **[Admin]** ปรับเปลี่ยนค่าพลังชีวิต (HP) ของ **{name}** เป็น `{amount:,}` HP เรียบร้อยแล้วครับ! 🩸")

    # ─── 🧪 3. คำสั่งเซ็ตเลือดสูงสุด (!set_max_hp) ───
    @has_permission("admin")
    @not_arrested() #ตรวจการถูกจับกุมก่อนอนุญาตให้ใช้คำสั่ง
    @commands.command(name="set_max_hp")
    async def set_max_hp(self, ctx, target: discord.User = None, amount: int = None):
        if target is None or amount is None:
            await ctx.send("❓ **วิธีใช้งาน:** `!set_max_hp [@ชื่อผู้เล่น หรือ ID] [จำนวน]`")
            return
        user_id = target.id
        name = target.display_name
        if not player_model.get_player(user_id):
            await ctx.send(f"❌ ไม่พบข้อมูลตัวละครในฐานข้อมูล")
            return
        player_model.update_player_field(user_id, "max_hp", amount)
        await ctx.send(f"⚡ **[Admin]** ปรับเปลี่ยนขีดจำกัดเลือดสูงสุด (Max HP) ของ **{name}** เป็น `{amount:,}` Max HP เรียบร้อยแล้วครับ! 🧪")

    # ─── 🛡️ 4. คำสั่งเซ็ตค่าเกราะ (!set_armor) ───
    @has_permission("admin")
    @not_arrested() #ตรวจการถูกจับกุมก่อนอนุญาตให้ใช้คำสั่ง
    @commands.command(name="set_armor")
    async def set_armor(self, ctx, target: discord.User = None, amount: str = "None"):
        if target is None:
            await ctx.send("❓ **วิธีใช้งาน:** `!set_armor [@ชื่อผู้เล่น หรือ ID] [ชื่อคีย์เวิร์ดเกราะ]`")
            return
        user_id = target.id
        name = target.display_name
        if not player_model.get_player(user_id):
            await ctx.send(f"❌ ไม่พบข้อมูลตัวละครในฐานข้อมูล")
            return
        player_model.update_player_field(user_id, "armor", amount)
        await ctx.send(f"⚡ **[Admin]** ปรับเปลี่ยนชุดเกราะของ **{name}** เป็นคีย์ `{amount}` เรียบร้อยแล้วครับ! 🛡️")

    # ─── 📈 5. คำสั่งเซ็ตค่า EXP (!set_exp) ───
    @has_permission("admin")
    @not_arrested() #ตรวจการถูกจับกุมก่อนอนุญาตให้ใช้คำสั่ง
    @commands.command(name="set_exp")
    async def set_exp(self, ctx, target: discord.User = None, amount: int = None):
        if target is None or amount is None:
            await ctx.send("❓ **วิธีใช้งาน:** `!set_exp [@ชื่อผู้เล่น หรือ ID] [จำนวน EXP]`")
            return
        user_id = target.id
        name = target.display_name
        if not player_model.get_player(user_id):
            await ctx.send(f"❌ ไม่พบข้อมูลตัวละครในฐานข้อมูล")
            return
        player_model.update_player_field(user_id, "exp", amount)
        await ctx.send(f"⚡ **[Admin]** ปรับเปลี่ยนค่า EXP ของ **{name}** เป็น `{amount:,}` EXP เรียบร้อยแล้วครับ! 🎯")

    # ─── 🎖️ 6. คำสั่งเซ็ตแรงค์ (!set_rank) ───
    @has_permission("admin")
    @not_arrested() #ตรวจการถูกจับกุมก่อนอนุญาตให้ใช้คำสั่ง
    @commands.command(name="set_rank")
    async def set_rank(self, ctx, target: discord.User = None, *, rank_name: str = None):
        if target is None or rank_name is None:
            await ctx.send("❓ **วิธีใช้งาน:** `!set_rank [@ชื่อผู้เล่น หรือ ID] [ชื่อแรงค์]`")
            return
        user_id = target.id
        name = target.display_name
        if not player_model.get_player(user_id):
            await ctx.send(f"❌ ไม่พบข้อมูลตัวละครในฐานข้อมูล")
            return
        player_model.update_player_field(user_id, "rank", rank_name)
        await ctx.send(f"⚡ **[Admin]** ปรับเปลี่ยนตำแหน่งแรงค์ของ **{name}** เป็น **\"{rank_name}\"** เรียบร้อยแล้วครับ! 🎖️")
    
    # ─── 🏦 7. คำสั่งแอดมิน: เซ็ตเงินในธนาคาร (!set_bank บวกลบตามค่า) ───
    @has_permission("admin")
    @not_arrested() #ตรวจการถูกจับกุมก่อนอนุญาตให้ใช้คำสั่ง
    @commands.command(name="set_bank")
    async def set_bank(self, ctx, target: discord.User = None, amount: int = None):
        print(f"🏦 [BANK ADMIN DEBUG] แอดมิน {ctx.author.name} เรียกใช้คำสั่ง !set_bank | target: {target} | amount: {amount}")

        if target is None or amount is None:
            await ctx.send("❓ **วิธีใช้งาน:** `!set_bank [@ชื่อผู้เล่น หรือ ID] [จำนวน]`\n*(ตัวอย่าง: ใส่ `500` เพื่อฝากเพิ่ม / ใส่ `-500` เพื่อหักเงินฝากออก)*")
            return
            
        user_id = target.id
        name = target.display_name

        player = player_model.get_player(user_id)
        if not player:
            await ctx.send(f"❌ ไม่พบข้อมูลตัวละครของ **{name}** ในฐานข้อมูล")
            return
            
        current_bank = player.get("bank", 0)
        new_bank = current_bank + amount
        
        if new_bank < 0:
            new_bank = 0

        player_model.update_player_field(user_id, "bank", new_bank)
        print(f"💾 [BANK ADMIN DEBUG] อัปเดตเงินในบัญชี {name} สำเร็จ: {current_bank:,} -> {new_bank:,} ทอง")
        
        if amount >= 0:
            await ctx.send(f"⚡ **[Admin]** ได้เพิ่มเงินฝากในธนาคารให้กับ **{name}** จำนวน `+ {amount:,}` ทอง\n🏦 (เงินฝากปัจจุบัน: `{new_bank:,}` ทอง) 📈💳")
        else:
            await ctx.send(f"⚡ **[Admin]** ได้ยึด/หักเงินฝากในธนาคารของ **{name}** ออกจำนวน `- {abs(amount):,}` ทอง\n🏦 (เงินฝากปัจจุบัน: `{new_bank:,}` ทอง) 📉💳")

    # ─── 🧹 8. คำสั่งแอดมิน: เคลียร์ข้อมูลเฉพาะส่วน (รายบุคคล / ทั้งเซิร์ฟเวอร์) ───
    @has_permission("admin")
    @not_arrested() #ตรวจการถูกจับกุมก่อนอนุญาตให้ใช้คำสั่ง
    @commands.command(name="reset_player")
    async def reset_player(self, ctx, scope: str = None, target: str = None, confirm: str = None):
        print(f"🧹 [RESET DEBUG] แอดมิน {ctx.author.name} เรียกใช้คำสั่ง !reset_player | scope: {scope}, target: {target}, confirm: {confirm}")

        valid_scopes = ["cash", "bank", "level", "rank", "all_data"]
        if not scope or scope.lower() not in valid_scopes or not target:
            embed_help = discord.Embed(
                title="🧹 วิธีใช้งานคำสั่ง !reset_player (เฉพาะแอดมิน)",
                description=(
                    "**📌 เคลียร์เฉพาะบุคคล:**\n"
                    "`!reset_player [ประเภท] [@ชื่อผู้เล่น หรือ ID]`\n"
                    "*ตัวอย่าง: `!reset_player cash @Arthur`*\n\n"
                    "**🚨 เคลียร์ทั้งเซิร์ฟเวอร์ (ล้างกระดาน):**\n"
                    "`!reset_player [ประเภท] all ยืนยัน`\n"
                    "*ตัวอย่าง: `!reset_player level all ยืนยัน`*\n\n"
                    "**📋 ประเภทการเคลียร์ (Scope):**\n"
                    "🔹 `cash` : รีเซ็ตเงินสดติดตัวเป็น 0 ทอง\n"
                    "🔹 `bank` : รีเซ็ตเงินในธนาคารเป็น 0 ทอง\n"
                    "🔹 `level` : รีเซ็ตเลเวลเป็น 1 และ EXP เป็น 0\n"
                    "🔹 `rank` : ปลดชั้นยศ Rank (F-SSS) ทั้งหมดออกจากตัวในดิสคอร์ด และเซ็ตค่าใน DB กลับเป็น F\n"
                    "🔹 `all_data` : ล้างทุกอย่างข้างต้นกลับไปจุดเริ่มต้นเหมือนไอดีเกิดใหม่ซิง ๆ"
                ),
                color=0xe53e3e
            )
            await ctx.send(embed=embed_help)
            return

        scope = scope.lower()
        target = target.lower()
        guild = ctx.guild

        rank_roles_names = [
            "• นักผจญภัยแรงค์ F",
            "• นักผจญภัยแรงค์ E",
            "• นักผจญภัยแรงค์ D",
            "• นักผจญภัยแรงค์ C",
            "• นักผจญภัยแรงค์ B",
            "• นักผจญภัยแรงค์ A",
            "• นักผจญภัยแรงค์ S 🗺️",
            "• นักผจญภัยแรงค์ SS 💰",
            "• นักผจญภัยแรงค์ SSS 👑"
        ]

        # ==========================================================
        # 🚨 [CASE 1]: รีเซ็ตทั้งเซิร์ฟเวอร์ (Target == 'all') แบบพิมพ์เช็กละเอียด
        # ==========================================================
        print(f"\n🔍 [RESET ALL DEBUG - STEP 1] เช็กค่าเปรียบเทียบก่อนเข้าเงื่อนไข:")
        print(f"👉 scope ตัวพิมพ์เล็ก: '{scope}'")
        print(f"👉 target ตัวพิมพ์เล็ก: '{target}'")
        print(f"👉 confirm คีย์เวิร์ด: '{confirm}'")

        if target == "all":
            print(f"🎯 [RESET ALL DEBUG - STEP 2] ผ่านเข้าบล็อก target == 'all' สำเร็จ")
            
            if confirm != "ยืนยัน":
                print(f"❌ [RESET ALL DEBUG - STEP 2.1] หลุดคัดกรอง: คำยืนยันไม่ถูกต้อง (กรอกมาคือ: '{confirm}')")
                await ctx.send("⚠️ **โปรดตรวจสอบคีย์เวิร์ด:** หากต้องการรีเซ็ตข้อมูล**ทั้งเซิร์ฟเวอร์** กรุณาพิมพ์คำว่า `ยืนยัน` ปิดท้ายคำสั่งด้วยครับ\n*(เช่น `!reset_player cash all ยืนยัน`)*")
                return

            print(f"🚀 [RESET ALL DEBUG - STEP 3] ผ่านการเช็กตัวคีย์เวิร์ดยืนยันแล้ว กำลังเข้าเช็กประเภท scope...")
            await ctx.send(f"⏳ **[System]** กำลังเริ่มกระบวนการล้างข้อมูลประเภท `{scope}` ของผู้เล่นทุกคนในเซิร์ฟเวอร์...")

            if scope == "cash":
                print("🪙 [RESET ALL DEBUG] เริ่มระบบล้างเงินสดติดตัว (cash) ทั้งเซิร์ฟ...")
                player_model.execute_raw_sql("UPDATE players SET cash = 0, bank = 0;")
                await ctx.send("✅ **[Reset All]** เคลียร์**เงินสดและเงินในธนาคาร**ของผู้เล่นทุกคนเป็น `0` ทอง เรียบร้อยแล้ว! 🪙💥")

            elif scope == "bank":
                print("💳 [RESET ALL DEBUG] เริ่มระบบล้างเงินในคลังบัญชี (bank) ทั้งเซิร์ฟ...")
                player_model.execute_raw_sql("UPDATE players SET bank = 0;")
                await ctx.send("✅ **[Reset All]** เคลียร์**เงินในธนาคาร**ของผู้เล่นทุกคนเป็น `0` ทอง เรียบร้อยแล้ว! 💳💥")

            elif scope == "level":
                print("📈 [RESET ALL DEBUG] เริ่มระบบรีเวล (level) ทั้งเซิร์ฟ...")
                player_model.execute_raw_sql("UPDATE players SET level = 1, exp = 0;")
                await ctx.send("✅ **[Reset All]** รีเซ็ตเลเวลเป็น `Lv.1` และเคลียร์ค่า `EXP = 0` ของทุกคนเรียบร้อยแล้ว! 📈💥")

            elif scope == "rank":
                print("🎖️ [RESET ALL DEBUG] เริ่มระบบล้างแต้มยศ (rank) ทั้งเซิร์ฟ...")
                player_model.execute_raw_sql("UPDATE players SET rank = 'F';")
                
                print("👼 [RESET ALL DEBUG] กำลังเริ่มกวาดถอดยศ Rank ออกจากสมาชิกในดิสคอร์ด...")
                for role_name in rank_roles_names:
                    role = discord.utils.get(guild.roles, name=role_name)
                    if role:
                        for member in role.members:
                            try: await member.remove_roles(role)
                            except: pass
                await ctx.send(f"✅ **[Reset All]** เซ็ตค่า Rank ใน DB กลับเป็น F และสั่งปลดยศกลุ่ม Rank (F-SSS) ออกจากสมาชิกรวดเดียวสำเร็จ! 🎖️❌")

            elif scope == "all_data":
                print("🔥 [RESET ALL DEBUG - STEP 4] พบคีย์เวิร์ด 'all_data' ! เริ่มกระบวนการถล่มตารางฐานข้อมูล...")
                
                try:
                    # 🔌 1. เปิดการเชื่อมต่อตรงดิ่งไปที่ไฟล์ฐานข้อมูล (แก้ชื่อไฟล์ DB ให้ตรงกับเครื่องของคุณอาเธอร์ เช่น game_data.db หรือ database.db)
                    db_name = getattr(player_model, "DB_NAME", "game_data.db") # ดึงชื่อไฟล์จากโมเดล หรือใช้ค่า Default
                    conn = sqlite3.connect(db_name)
                    cursor = conn.cursor()
                    
                    # 💥 2. รันคำสั่งกวาดล้างข้อมูลผู้เล่นเกลี้ยงตาราง
                    print("🧹 [RESET ALL DEBUG - STEP 4.1] กำลังยิงคำสั่ง: DELETE FROM players;")
                    cursor.execute("DELETE FROM players;")
                    
                    # 🧼 3. รีเซ็ตตัวนับ ID (AUTOINCREMENT) ให้กลับไปนับ 1 ใหม่
                    print("🧼 [RESET ALL DEBUG - STEP 4.3] กำลังเคลียร์ตัวนับ ID ตาราง...")
                    try:
                        cursor.execute("DELETE FROM sqlite_sequence WHERE name='players';")
                    except:
                        pass
                        
                    # บันทึกการเปลี่ยนแปลงและปิดการเชื่อมต่อ
                    conn.commit()
                    conn.close()
                    print("✅ [RESET ALL DEBUG - STEP 4.4] เคลียร์ฐานข้อมูลเกลี้ยงตารางสำเร็จ!")

                    # 👑 4. สั่งปลดยศในดิสคอร์ดค้างไว้เหมือนเดิม
                    print("👑 [RESET ALL DEBUG - STEP 4.5] กำลังเริ่มลูปปลดยศ Rank บนหัวทุกคนในดิสคอร์ด...")
                    success_roles_count = 0
                    for role_name in rank_roles_names:
                        role = discord.utils.get(guild.roles, name=role_name)
                        if role:
                            for member in role.members:
                                try: 
                                    await member.remove_roles(role)
                                    success_roles_count += 1
                                except: 
                                    pass
                    print(f"✅ [RESET ALL DEBUG - STEP 4.6] ลูปถอดยศเสร็จสิ้น ถอดไปทั้งหมด {success_roles_count} ครั้ง")

                    await ctx.send("🔥 **[RESET GRAND CHAMPION]** สั่งล้างฐานข้อมูลผู้เล่นเกลี้ยงตาราง `DELETE FROM players;` พร้อมเคลียร์ยศ Rank F-SSS ออกจากดิสคอร์ด ต้อนรับซีซันใหม่อย่างเป็นทางการเรียบร้อยแล้วครับ!")
                    print("📢 [RESET ALL DEBUG - STEP 4.7] ส่งข้อความประกาศความสำเร็จลงแชทเรียบร้อย!")

                except Exception as sql_error:
                    print(f"💥 [RESET ALL CRITICAL ERROR] โค้ดฝั่ง SQL ระเบิดคามือ: {sql_error}")
                    await ctx.send(f"⚠️ **ระบบล้างตารางขัดข้องเนื่องจาก:** `{sql_error}`")
            
            else:
                print(f"❓ [RESET ALL DEBUG] โค้ดวิ่งมาถึงทางตันเนื่องจากไม่รู้จักคีย์เวิร์ดสล็อต scope: '{scope}'")
            
            return

        # ==========================================================
        # 👤 [CASE 2]: รีเซ็ตรายบุคคล (Target == ID/Tag)
        # ==========================================================
        # ดึงสิทธิ์แปลงไอดีด้วยระบบแปลงของตัวดิสคอร์ดแบบแมนนวลกรณีพิมพ์ข้อความดิบ
        clean_id = target.replace("<@", "").replace(">", "").replace("!", "")
        if not clean_id.isdigit():
            await ctx.send("❌ **ไม่พบผู้เล่น:** กรุณาระบุเป็น Tag `@ชื่อผู้เล่น` หรือกรอก `Discord ID` ให้ถูกต้องครับ")
            return
            
        user_id = int(clean_id)
        member = guild.get_member(user_id) or await self.bot.fetch_user(user_id)
        name = member.display_name if member else f"User ID: {user_id}"

        player = player_model.get_player(user_id)
        if not player:
            await ctx.send(f"❌ ไม่พบข้อมูลตัวละครของ **{name}** ในฐานข้อมูล")
            return

        if scope == "cash":
            player_model.update_player_field(user_id, "cash", 0)
            await ctx.send(f"🧹 **[Reset]** เคลียร์**เงินสดติดตัว**ของ **{name}** กลับเป็น `0` ทอง เรียบร้อยแล้วครับ 🪙")

        elif scope == "bank":
            player_model.update_player_field(user_id, "bank", 0)
            await ctx.send(f"🧹 **[Reset]** เคลียร์**เงินในธนาคาร**ของ **{name}** กลับเป็น `0` ทอง เรียบร้อยแล้วครับ 💳")

        elif scope == "level":
            player_model.update_player_field(user_id, "level", 1)
            player_model.update_player_field(user_id, "exp", 0)
            await ctx.send(f"🧹 **[Reset]** รีเซ็ตเลเวลของ **{name}** กลับเป็น `Lv.1` (EXP: 0) เรียบร้อยแล้วครับ ⚔️")

        elif scope == "rank":
            player_model.update_player_field(user_id, "rank", "F")
            removed_ranks = []
            if member and isinstance(member, discord.Member):
                for role_name in rank_roles_names:
                    role = discord.utils.get(guild.roles, name=role_name)
                    if role and role in member.roles:
                        try:
                            await member.remove_roles(role)
                            removed_ranks.append(role_name)
                        except discord.Forbidden:
                            await ctx.send("❌ บอทไม่มีสิทธิ์ถอดยศ กรุณาเช็กเลเยอร์ยศของบอทให้สูงกว่ากลุ่มยศ Rank ครับ")
                            return
            msg_rank = f" และปลดยศ Rank `{', '.join(removed_ranks)}` ออกจากตัวแล้ว" if removed_ranks else " (ผู้เล่นไม่มียศ Rank ติดตัวอยู่แล้ว)"
            await ctx.send(f"🧹 **[Reset]** เซ็ตค่าฐานข้อมูลกลับเป็น Rank F{msg_rank} เรียบร้อยครับ 🎖️❌")

        elif scope == "all_data":
            player_model.update_player_field(user_id, "cash", 0)
            player_model.update_player_field(user_id, "bank", 0)
            player_model.update_player_field(user_id, "level", 1)
            player_model.update_player_field(user_id, "exp", 0)
            player_model.update_player_field(user_id, "rank", "F")
            
            if member and isinstance(member, discord.Member):
                for role_name in rank_roles_names:
                    role = discord.utils.get(guild.roles, name=role_name)
                    if role and role in member.roles:
                        try: await member.remove_roles(role)
                        except: pass
            await ctx.send(f"💥 **[Reset All Data]** ข้อมูลทั้งหมดของ **{name}** ถูกล้างกลับสู่จุดเริ่มต้น และล้างยศ Rank เดิมออกเรียบร้อยแล้วครับ!")

        print(f"✅ [RESET INDIVIDUAL SUCCESS] ล้างข้อมูลของ {name} ประเภท {scope} สำเร็จ")

    # ─── 🔮 9. คำสั่งเซ็ตสถานะทั่วไป (!set_state) ───
    @has_permission("admin")
    @not_arrested() #ตรวจการถูกจับกุมก่อนอนุญาตให้ใช้คำสั่ง
    @commands.command(name="set_state")
    async def set_state(self, ctx, target: discord.User = None, state: str = "idle"):
        if target is None:
            await ctx.send("❓ **วิธีใช้งาน:** `!set_state [@ชื่อผู้เล่น] [ชื่อสถานะ (เช่น idle/dungeon/rest)]`")
            return
            
        user_id = target.id
        name = target.display_name
        player_model.update_player_field(user_id, "current_state", state)
        await ctx.send(f"🔮 **[Admin]** ได้ปรับสถานะตัวละครของ **{name}** เป็น `{state}` เรียบร้อยแล้วครับ! (แก้อาการตัวค้าง)")

    # ─── 🎒 10. คำสั่งล้างกระเป๋าไอเทม (!clear_inventory) ───
    @has_permission("admin")
    @not_arrested() #ตรวจการถูกจับกุมก่อนอนุญาตให้ใช้คำสั่ง
    @commands.command(name="clear_inventory")
    async def clear_inventory(self, ctx, target: str = None, confirm: str = None):
        if target is None:
            await ctx.send("❓ **วิธีใช้งาน:** \nรายคน: `!clear_inventory [@ชื่อผู้เล่น]`\nทั้งเซิร์ฟ: `!clear_inventory all ยืนยัน`")
            return

        if target.lower() == "all":
            if confirm != "ยืนยัน":
                await ctx.send("⚠️ กรุณาพิมพ์ `ยืนยัน` ต่อท้ายเพื่อล้างกระเป๋าผู้เล่นทุกคน")
                return
            player_model.execute_raw_sql("UPDATE players SET inventory = '[]';")
            await ctx.send("🔥 **[Reset Inventory]** ล้างกระเป๋าไอเทมของผู้เล่นทุกคนในเซิร์ฟเวอร์เกลี้ยงแล้วครับ!")
            return

        clean_id = target.replace("<@", "").replace(">", "").replace("!", "")
        if clean_id.isdigit():
            user_id = int(clean_id)
            player_model.update_player_field(user_id, "inventory", "[]")
            await ctx.send(f"🧹 ล้างไอเทมในกระเป๋าของ ID `{user_id}` จนโล่งเรียบร้อยแล้วครับ!")

    # ─── 🪙 11. คำสั่งแจกเงินกิจกรรมทุกคนในฐานข้อมูล (!give_cash_all) ───
    @has_permission("admin")
    @not_arrested() #ตรวจการถูกจับกุมก่อนอนุญาตให้ใช้คำสั่ง
    @commands.command(name="give_cash_all")
    async def give_cash_all(self, ctx, amount: int = None):
        if amount is None:
            await ctx.send("❓ **วิธีใช้งาน:** `!give_cash_all [จำนวนทอง]`")
            return
        
        # ตรวจสอบว่าโมเดลมีการ commit หรือไม่
        player_model.execute_raw_sql("UPDATE players SET cash = cash + ?", (amount,))
        await ctx.send(f"📢 **[ประกาศ]** แจกทองทุกคนคนละ `{amount:,}` ทอง!")

    
    @has_permission("admin")
    @not_arrested() #ตรวจการถูกจับกุมก่อนอนุญาตให้ใช้คำสั่ง
    @commands.command(name="give_bank_all")
    async def give_bank_all(self, ctx, amount: int = None):
        if amount is None:
            await ctx.send("❓ **วิธีใช้งาน:** `!give_bank_all [จำนวนทอง]`")
            return
        
        print(f"🪙 [ADMIN LOG] แจกเงินผู้เล่นทุกคนคนละ +{amount:,} ทอง")
        player_model.execute_raw_sql("UPDATE players SET bank = bank + ?", (amount,))
        await ctx.send(f"📢 **[ประกาศจากสมาคม]** ท่านแอดมินได้ทำการแจกทองให้กับนักผจญภัยทุกคนในฐานข้อมูล จำนวน `+ {amount:,}` ทอง! 🪙✨")

    # ─── 🚫 12. คำสั่งแอดมิน: สั่งจับกุมแบบกำหนดเวลา / ปลดปล่อยผู้เล่น (!arrest) ───
    @has_permission("police") 
    @not_arrested() #ตรวจการถูกจับกุมก่อนอนุญาตให้ใช้คำสั่ง
    @commands.command(name="arrest")
    @allowed_channel("police")
    async def arrest(self, ctx, target: discord.User = None, duration_mins: int = None):
        import time
        print(f"\n🔍 [ARREST STEP 1] เริ่มฟังก์ชัน !arrest | target: {target} | duration_mins: {duration_mins}")

        if target is None or duration_mins is None:
            print("❌ [ARREST STEP 1.1] หลุดเงื่อนไข: กรอกพารามิเตอร์ไม่ครบ (เป็น None)")
            await ctx.send("❓ **วิธีใช้งาน:**\n🚨 สั่งจับกุม: `!arrest [@ชื่อผู้เล่น] [จำนวนนาที]` *(เช่น `!arrest @Arthur 30`)*\n🔓 ปลดปล่อยทันที: `!arrest [@ชื่อผู้เล่น] 0`")
            return

        user_id = target.id
        name = target.display_name
        print(f"🆔 [ARREST STEP 2] แปลง User สำเร็จ -> ชื่อ: {name} | ID: {user_id}")

        try:
            print("🗄️ [ARREST STEP 3] กำลังดึงข้อมูลผู้เล่นจากฐานข้อมูล...")
            player = player_model.get_player(user_id)
            print(f"📦 [ARREST STEP 3.1] ข้อมูลที่ได้จาก DB: {player}")

            if not player:
                print(f"❌ [ARREST STEP 3.2] หลุดเงื่อนไข: ไม่พบข้อมูลไอดี {user_id} ใน Database")
                await ctx.send(f"❌ ไม่พบข้อมูลตัวละครของ **{name}** ในฐานข้อมูล (ผู้เล่นต้องพิมพ์ `!play` ก่อน)")
                return

            if duration_mins <= 0:
                print("🔓 [ARREST STEP 4] เข้าสู่เงื่อนไขปลดปล่อยตัว (เวลาน้อยกว่าหรือเท่ากับ 0)")
                player_model.update_player_field(user_id, "current_state", "idle")
                player_model.update_player_field(user_id, "arrest_until", 0)
                await ctx.send(f"🔓 **[กองปราบปราม]** นักผจญภัย **{name}** ได้รับการปล่อยตัวเป็นอิสระแล้ว! 🕊️✨")
                return

            print("🚨 [ARREST STEP 5] เข้าสู่เงื่อนไขสั่งขังคุกตามเวลา")
            current_timestamp = int(time.time())
            release_timestamp = current_timestamp + (duration_mins * 60)

            player_model.update_player_field(user_id, "current_state", "arrested")
            player_model.update_player_field(user_id, "arrest_until", release_timestamp)

            await ctx.send(
                f"🚨 **[กองปราบปราม]** นักผจญภัย **{name}** ถูกสั่ง **จับกุมควบคุมตัว** เป็นเวลา `{duration_mins}` นาที! 🔗⛓️\n"
                f"🚫 จะไม่สามารถใช้คำสั่งใดๆ ของบอทได้จนกว่าจะครบกำหนดเวลา!"
            )

        except Exception as e:
            print(f"💥 [ARREST CRITICAL ERROR] โค้ดระเบิดภายในฟังก์ชัน: {e}")
            await ctx.send(f"⚠️ **ระบบหลังบ้านขัดข้อง:** เกิดข้อผิดพลาดตัวแปรระเบิด `({e})` กรุณาแจ้งแอดมินเช็กด่วน")

    # ==========================================
    # ⚖️ คำสั่งปรับเงิน/ริบทรัพย์ (!fine @ผู้ใช้ จำนวนเงิน)
    # ==========================================
    @has_permission("police") # 🛠️ ล็อกสิทธิ์เฉพาะอัศวินและเจ้าของเซิร์ฟ
    @commands.command(name="fine")
    @allowed_channel("police")
    async def fine_player(self, ctx, member: discord.Member, amount: int):
        # 1. ป้องกันการใส่ค่าติดลบหรือ 0
        if amount <= 0:
            return await ctx.send("❌ จำนวนเงินที่ต้องการปรับต้องมากกว่า `0` ทอง!")

        # 2. ป้องกันการปรับเงินตัวเอง
        if member.id == ctx.author.id:
            return await ctx.send("❌ คุณไม่สามารถปรับเงินตัวเองได้!")

        # 3. โหลดข้อมูลผู้เล่นทั้งสองฝ่าย
        target = player_model.get_player(member.id)
        executor = player_model.get_player(ctx.author.id)

        if not target:
            return await ctx.send("❌ ไม่พบข้อมูลตัวละครเป้าหมายในระบบ!")
        if not executor:
            return await ctx.send("❌ ไม่พบข้อมูลตัวละครของคุณในระบบ!")

        # 4. คำนวณยอดเงิน (ดึงเงินจากเป้าหมาย เข้ากระเป๋าคนปรับ)
        target_cash = target.get("cash", 0)
        executor_cash = executor.get("cash", 0)

        new_target_cash = target_cash - amount
        new_executor_cash = executor_cash + amount

        # 5. อัปเดตข้อมูลกลับเข้า Database
        player_model.update_player_field(member.id, "cash", new_target_cash)
        player_model.update_player_field(ctx.author.id, "cash", new_executor_cash)

        # จัดฟอร์แมตตัวเลขให้สวยงาม
        cash_status = f"`{new_target_cash:,}` ทอง" if new_target_cash >= 0 else f"`{new_target_cash:,}` ทอง ⚠️ (ถูกปรับจนติดหนี้!)"

        # 6. ส่งข้อความรายงานผล
        await ctx.send(f"⚖️ **การริบทรัพย์สำเร็จ!** {ctx.author.mention} ในนามของอัศวิน ได้ทำการปรับเงิน {member.mention} จำนวน `{amount:,}` ทอง!\n"
                       f"💰 เงินค่าปรับถูกโอนเข้ากระเป๋าของท่านอัศวินเรียบร้อยแล้ว\n"
                       f"📉 (เงินคงเหลือของเป้าหมาย: {cash_status})")

    # ==========================================
    # 💡 ตัวอย่างการดักจับ Error กรณีผู้เล่นพิมพ์คำสั่งผิดรูปแบบ
    # ==========================================
    @fine_player.error
    async def fine_player_error(self, ctx, error):
        if isinstance(error, commands.MissingRequiredArgument) or isinstance(error, commands.BadArgument):
            await ctx.send("❌ **รูปแบบคำสั่งไม่ถูกต้อง!** วิธีใช้: `!fine @ผู้ใช้ จำนวนเงิน` (เช่น `!fine @Arthur 500`)")

    # ==========================================================
    # 🏅 [COMMAND]: !add_role [ยศ] [ผู้เล่น หรือ all] (เวอร์ชันเสถียร 100%)
    # ==========================================================
    @not_arrested() #ตรวจการถูกจับกุมก่อนอนุญาตให้ใช้คำสั่ง
    @commands.command(name="add_role")
    @commands.has_permissions(administrator=True)
    async def add_role_command(self, ctx, role: discord.Role = None, target: str = None):
        """คำสั่งแอดมิน: แจกยศให้ผู้เล่นรายคน หรือทุกคนในเซิร์ฟเวอร์ (!add_role @ยศ @ชื่อคน/all)"""
        if role is None or target is None:
            await ctx.send("❓ **วิธีใช้งาน:** `!add_role [@แท็กยศ หรือ ชื่อยศ] [@แท็กผู้เล่น หรือ ID หรือ all]`")
            return

        guild = ctx.guild
        role_name = role.name

        # 👥 [CASE 1]: แจกยศให้ทุกคนในเซิร์ฟเวอร์ (target == "all")
        if target.lower() == "all":
            await ctx.send(f"⏳ **[System]** กำลังเริ่มกระบวนการแจกยศ `{role_name}` ให้แก่สมาชิกทุกคนในเซิร์ฟเวอร์ (อาจใช้เวลาสักครู่)...")
            success_count = 0
            
            for member in guild.members:
                if member.bot: 
                    continue
                if role not in member.roles:
                    try:
                        await member.add_roles(role)
                        success_count += 1
                    except:
                        pass
            
            await ctx.send(f"✅ **[Role All Success]** แจกยศ **{role_name}** ให้แก่ผู้เล่นทุกคนสำเร็จรวมทั้งหมด `{success_count}` คนเรียบร้อยแล้วครับ! 👑")
            print(f"🏅 [ADMIN ROLE] แจกยศ {role_name} ให้ทุกคนสำเร็จ ({success_count} คน)")

        # 👤 [CASE 2]: แจกยศให้ผู้เล่นรายคน
        else:
            try:
                converter = commands.MemberConverter()
                member = await converter.convert(ctx, target)
            except:
                await ctx.send("❌ **ไม่พบผู้เล่น:** กรุณาทำการแท็ก `@ผู้เล่น` หรือใส่ `Discord ID` ให้ถูกต้องครับ")
                return

            if role in member.roles:
                await ctx.send(f"⚠️ ผู้เล่น **{member.display_name}** มีสิทธิ์ยศ `{role_name}` อยู่แล้วครับ")
                return

            try:
                await member.add_roles(role)
                await ctx.send(f"✅ แจกยศ **{role_name}** ให้แก่ **{member.mention}** เรียบร้อยแล้วครับ! ⚔️")
                print(f"🏅 [ADMIN ROLE] แจกยศ {role_name} ให้แก่ {member.name} สำเร็จ")
            except discord.Forbidden:
                await ctx.send("❌ **บอทไม่มีสิทธิ์จัดการยศ:** ยศของบอทอยู่ต่ำกว่ายศที่ต้องการแจก กรุณาลากยศของบอทให้สูงขึ้นในตารางตั้งค่ายศของดิสคอร์ดครับ")
            except Exception as e:
                await ctx.send(f"⚠️ เกิดข้อผิดพลาด: `{e}`")

    # ==========================================================
    # ❌ [COMMAND]: !remove_role [ยศ] [ผู้เล่น หรือ all] (เวอร์ชันเสถียร 100%)
    # ==========================================================
    @not_arrested() #ตรวจการถูกจับกุมก่อนอนุญาตให้ใช้คำสั่ง
    @commands.command(name="remove_role")
    @commands.has_permissions(administrator=True)
    async def remove_role_command(self, ctx, role: discord.Role = None, target: str = None):
        """คำสั่งแอดมิน: ริบยศคืนจากผู้เล่นรายคน หรือทุกคนในเซิร์ฟเวอร์ (!remove_role @ยศ @ชื่อคน/all)"""
        if role is None or target is None:
            await ctx.send("❓ **วิธีใช้งาน:** `!remove_role [@แท็กยศ หรือ ชื่อยศ] [@แท็กผู้เล่น หรือ ID หรือ all]`")
            return

        guild = ctx.guild
        role_name = role.name

        # 👥 [CASE 1]: ลบยศออกจากทุกคนในเซิร์ฟเวอร์ (target == "all")
        if target.lower() == "all":
            await ctx.send(f"⏳ **[System]** กำลังเริ่มกระบวนการลบยศ `{role_name}` ออกจากสมาชิกทุกคนในเซิร์ฟเวอร์...")
            success_count = 0
            
            for member in role.members:
                if member.bot: 
                    continue
                try:
                    await member.remove_roles(role)
                    success_count += 1
                except:
                    pass
            
            await ctx.send(f"🧹 **[Remove Role All Success]** ทำการริบยศ **{role_name}** ออกจากสมาชิกทุกคนสำเร็จรวมทั้งหมด `{success_count}` คนเรียบร้อยแล้วครับ!")
            print(f"❌ [ADMIN ROLE] ลบยศ {role_name} ออกจากทุกคนสำเร็จ ({success_count} คน)")

        # 👤 [CASE 2]: ลบยศออกรายบุคคล
        else:
            try:
                converter = commands.MemberConverter()
                member = await converter.convert(ctx, target)
            except:
                await ctx.send("❌ **ไม่พบผู้เล่น:** กรุณาทำการแท็ก `@ผู้เล่น` หรือใส่ `Discord ID` ให้ถูกต้องครับ")
                return

            if role not in member.roles:
                await ctx.send(f"⚠️ ผู้เล่น **{member.display_name}** ไม่มีสิทธิ์ยศ `{role_name}` อยู่แล้วครับ")
                return

            try:
                await member.remove_roles(role)
                await ctx.send(f"✅ ลบยศ **{role_name}** ออกจากโปรไฟล์ของ **{member.mention}** เรียบร้อยแล้วครับ! 🧼")
                print(f"❌ [ADMIN ROLE] ลบยศ {role_name} ออกจาก {member.name} สำเร็จ")
            except discord.Forbidden:
                await ctx.send("❌ **บอทไม่มีสิทธิ์จัดการยศ:** ยศของบอทอยู่ต่ำกว่ายศดังกล่าว กรุณาขยับเลเยอร์ยศบอทให้สูงขึ้นครับ")
            except Exception as e:
                await ctx.send(f"⚠️ เกิดข้อผิดพลาด: `{e}`")

    # ─── 🔍 13. แอดมินส่องดูสเตตัสโปรไฟล์ผู้เล่น (!check_profile) ───
    @not_arrested()
    @commands.command(name="check_profile")
    async def check_profile(self, ctx, target: discord.User = None):
        if target is None:
            await ctx.send("❓ **วิธีใช้งาน:** `!check_profile [@ชื่อผู้เล่น หรือ ID]`")
            return

        user_id = target.id
        name = target.display_name

        player = player_model.get_player(user_id)
        if not player:
            await ctx.send(f"❌ ไม่พบข้อมูลตัวละครของ **{name}** ในฐานข้อมูลครับ")
            return

        level = player.get("level", 1)
        exp = player.get("exp", 0)
        cash = player.get("cash", 0)
        bank = player.get("bank", 0)
        hp = player.get("hp", 100)
        max_hp = player.get("max_hp", 100)
        armor = player.get("armor", "0")
        rank = player.get("rank", "นักผจญภัยฝึกหัด")
        current_state = player.get("current_state", "ปกติ")

        total_mins = player.get("total_online_time", 0)
        
        MINS_IN_HOUR = 60
        MINS_IN_DAY = 60 * 24
        MINS_IN_MONTH = MINS_IN_DAY * 30
        MINS_IN_YEAR = MINS_IN_DAY * 365

        years = total_mins // MINS_IN_YEAR
        months = (total_mins % MINS_IN_YEAR) // MINS_IN_MONTH
        days = (total_mins % MINS_IN_MONTH) // MINS_IN_DAY
        hours = (total_mins % MINS_IN_DAY) // MINS_IN_HOUR
        mins = total_mins % MINS_IN_HOUR

        time_parts = []
        if years > 0: time_parts.append(f"`{years}` ปี")
        if months > 0: time_parts.append(f"`{months}` เดือน")
        if days > 0: time_parts.append(f"`{days}` วัน")
        if hours > 0: time_parts.append(f"`{hours}` ชม.")
        if mins > 0 or len(time_parts) == 0: 
            time_parts.append(f"`{mins}` นาที")
        
        formatted_time = " ".join(time_parts)

        embed = discord.Embed(
            title=f"🔎 Admin Inspection — {name}",
            description=f"📂 ข้อมูลสเตตัสในระบบอย่างละเอียด\n💻 User ID: `{user_id}`",
            color=0x3182ce
        )
        
        embed.add_field(name="🎖️ ตำแหน่ง / เลเวล", value=f"**Rank:** {rank}\n**Level:** `{level}`\n**EXP:** `{exp:,}`", inline=True)
        embed.add_field(name="💰 Status การเงิน", value=f"**เงินติดตัว:** `{cash:,}` ทอง\n**ในธนาคาร:** `{bank:,}` ทอง", inline=True)
        embed.add_field(name="⏳ เวลาออนไลน์สะสม", value=f"⏱️: {formatted_time}", inline=False)
        embed.add_field(name="🩸 พลังชีวิตและป้องกัน", value=f"**HP:** `{hp}` / `{max_hp}` | **Armor:** `{armor}` แต้ม\n**สถานะตัวละคร:** `{current_state}`", inline=False)
        
        embed.set_footer(text=f"ตรวจสอบโดย Admin: {ctx.author.name}", icon_url=ctx.author.display_avatar.url)
        
        await ctx.send(embed=embed)
    
    # ==========================================
    # 🏥 คำสั่งชุบชีวิตผู้เล่น (!rv @ผู้ใช้)
    # ==========================================
    @has_permission("priest") # 🛠️ ใช้ Decorator บล็อกยศ
    @not_arrested() # 🛠️ บล็อกคนติดคุก
    @commands.command(name="rv")
    async def revive_player(self, ctx, member: discord.Member):
        target = player_model.get_player(member.id)
        if not target:
            return await ctx.send("❌ ไม่พบข้อมูลตัวละครเป้าหมาย!")

        # เงื่อนไข: ต้องเป็นผู้เล่นที่ตายเท่านั้น
        if target.get("current_state") != "death":
            return await ctx.send(f"❌ {member.display_name} ยังไม่ตาย! ไม่จำเป็นต้องประกอบพิธีชุบชีวิต")

        # ดึงโบนัสเลือดจากเกราะปัจจุบันมาคำนวณ Max HP เต็มหลอด
        armor_key = target.get("armor", "None")
        armor_hp_bonus = config_loader.get_armor_stats(armor_key).get("hp", 0)
        max_hp_total = target.get("max_hp", 100) + armor_hp_bonus

        # ตรรกะโอนเงินค่าธรรมเนียมชุบชีวิต 500 ทอง
        target_cash = target.get("cash", 0) - 500
        caster = player_model.get_player(ctx.author.id)
        caster_cash = caster.get("cash", 0) + 500

        # อัปเดตข้อมูลทั้งสองฝั่งลง DB
        player_model.update_player_field(member.id, "current_state", "village")
        player_model.update_player_field(member.id, "hp", max_hp_total)
        player_model.update_player_field(member.id, "cash", target_cash)

        player_model.update_player_field(ctx.author.id, "cash", caster_cash)

        await ctx.send(f"♱✨ **พิธีชุบชีวิตเสร็จสิ้น!** {ctx.author.mention} ได้สวดภาวนาปลุกร่างของ {member.mention} ให้ฟื้นคืนชีพขึ้นมาอีกครั้ง!\n"
                       f"🏡 สถานะถูกย้ายกลับไปที่ **หมู่บ้านอุ่นใจ** (HP ฟื้นฟูเต็มหลอด: `❤️ {max_hp_total}/{max_hp_total}`)\n"
                       f"💸 ระบบหักเงินค่าทำพิธีจากผู้ตาย `-500` ทอง โอนเข้ากระเป๋าของนักบวชผู้ร่ายมนตร์เรียบร้อย!")
        
    # ==========================================
    # 🧪 คำสั่งรักษาฟื้นฟู (!heal @ผู้ใช้)
    # ==========================================
    @has_permission("priest") # 🛠️ ล็อกสิทธิ์นักบวชและเจ้าของเซิร์ฟ
    @not_arrested() # 🛠️ บล็อกคนติดคุก
    @commands.command(name="heal")
    async def heal_player(self, ctx, member: discord.Member):
        # 1. ป้องกันการฮีลและเก็บเงินตัวเอง
        if member.id == ctx.author.id:
            return await ctx.send("❌ คุณไม่สามารถคิดค่ารักษาจากตัวเองได้! (แนะนำให้ใช้ไอเทมยาฮีลแทนนะครับ)")

        # 2. โหลดข้อมูลผู้เล่น
        target = player_model.get_player(member.id)
        caster = player_model.get_player(ctx.author.id)

        if not target:
            return await ctx.send("❌ ไม่พบข้อมูลตัวละครเป้าหมายในระบบ!")
        if not caster:
            return await ctx.send("❌ ไม่พบข้อมูลตัวละครของคุณในระบบ!")

        # 3. เช็กสถานะคนตาย (ถ้าตายต้องใช้ !rv)
        if target.get("current_state") == "death":
            return await ctx.send(f"❌ {member.display_name} เสียชีวิตไปแล้ว! เวทรักษาไม่ได้ผล ต้องใช้คำสั่ง `!rv` เพื่อประกอบพิธีชุบชีวิตเท่านั้น")

        # 4. คำนวณ Max HP และเช็กเลือดปัจจุบัน
        armor_key = target.get("armor", "None")
        armor_hp_bonus = config_loader.get_armor_stats(armor_key).get("hp", 0)
        max_hp_total = target.get("max_hp", 100) + armor_hp_bonus

        current_hp = target.get("hp", 100)

        if current_hp >= max_hp_total:
            return await ctx.send(f"❌ {member.display_name} พลังชีวิตเต็มเปี่ยมอยู่แล้ว! (`{current_hp}/{max_hp_total}`) ไม่จำเป็นต้องรับการรักษา")

        # 5. ค่าบริการรักษา (หักจากเป้าหมาย โอนให้นักบวช) — ตั้งได้ที่ Panel
        fee = int(config_loader.get_balance("village.heal_fee", 300))
        new_target_cash = target.get("cash", 0) - fee
        new_caster_cash = caster.get("cash", 0) + fee

        # 6. อัปเดตข้อมูลลง Database
        player_model.update_player_field(member.id, "hp", max_hp_total)
        player_model.update_player_field(member.id, "cash", new_target_cash)
        player_model.update_player_field(ctx.author.id, "cash", new_caster_cash)

        cash_status = f"`{new_target_cash:,}` ทอง" if new_target_cash >= 0 else f"`{new_target_cash:,}` ทอง ⚠️ (ถูกหักจนติดหนี้!)"

        # 7. ส่งข้อความรายงานผล
        await ctx.send(f"✨ **เวทมนตร์แห่งการเยียวยา!** {ctx.author.mention} ได้ร่ายเวทแห่งแสงฟื้นฟูบาดแผลให้ {member.mention} จนหายสนิท!\n"
                       f"❤️ พลังชีวิต: `{current_hp}` ➔ `{max_hp_total}/{max_hp_total}`\n"
                       f"💸 หักค่ารักษาพยาบาล `-300` ทอง โอนเข้ากระเป๋านักบวชเรียบร้อย (เงินคงเหลือของเป้าหมาย: {cash_status})")

    # ==========================================
    # 💡 ตัวดักจับ Error กรณีพิมพ์คำสั่งไม่ครบ
    # ==========================================
    @heal_player.error
    async def heal_player_error(self, ctx, error):
        if isinstance(error, commands.MissingRequiredArgument) or isinstance(error, commands.BadArgument):
            await ctx.send("❌ **รูปแบบคำสั่งไม่ถูกต้อง!** วิธีใช้: `!heal @ผู้ใช้` (เช่น `!heal @Arthur`)")


    # ==========================================
    # 💀 คำสั่งแอดมินปลิดชีพ (!kill @ผู้ใช้)
    # ==========================================
    @has_permission("admin") # 🛠️ ใช้ Decorator บล็อกยศคนบ้า
    @commands.command(name="kill")
    async def admin_kill(self, ctx, member: discord.Member):
        target = player_model.get_player(member.id)
        if not target:
            return await ctx.send("❌ ไม่พบข้อมูลตัวละครเป้าหมาย!")

        player_model.update_player_field(member.id, "hp", 0)
        player_model.update_player_field(member.id, "current_state", "death")

        await ctx.send(f"⚡ **สายฟ้าลงทัณฑ์!** {ctx.author.mention} ใช้อำนาจเบ็ดเสร็จปลิดชีพ {member.mention} จนดับดิ้นทันที! (HP: `0`, สถานะ: `death`) 💀")

    # ==========================================
    # ⚡ 1. คำสั่งเสกไอเทมให้ผู้เล่นรายคน (!spawn)
    # ==========================================
    @has_permission("admin") # 🛠️ ใช้ Decorator บล็อกยศคนบ้า
    @commands.command(name="spawn")
    @commands.has_permissions(administrator=True) # 🛡️ ล็อกสิทธิ์เฉพาะแอดมิน
    async def spawn_item(self, ctx, member: discord.Member = None, item_id: str = None, amount: int = 1):
        if member is None or item_id is None:
            return await ctx.send("❌ วิธีใช้: `!spawn @ชื่อผู้เล่น [เลขไอเทม] [จำนวน]`\n💡 เช่น: `!spawn @Arthur 28 5`")

        if not config_loader.get_item_config(item_id):
            return await ctx.send(f"❌ ไม่พบไอเทมรหัส `{item_id}` ในระบบ!")
            
        if amount <= 0:
            return await ctx.send("❌ จำนวนต้องมากกว่า 0 ครับแอดมิน!")

        target_id = member.id
        player = player_model.get_player(target_id)
        
        if not player:
            return await ctx.send(f"❌ ไม่พบข้อมูลของ {member.display_name} ในระบบ")

        # 🧹 ถอดรหัสและทำความสะอาดกระเป๋า
        raw_inv = player.get("inventory", "")
        clean_inv = str(raw_inv)
        for char in ["(", ")", "[", "]", "'", '"', " "]:
            clean_inv = clean_inv.replace(char, "")
        inv_array = clean_inv.split(",") if clean_inv and clean_inv not in ["None", "null"] else []
        inv_array = [i for i in inv_array if i]

        # ยัดของเข้ากระเป๋า (แอดมินเสกจะทะลุ Capacity ทันที)
        for _ in range(amount):
            inv_array.append(item_id)
            
        # บันทึกคืนฐานข้อมูล
        player_model.update_player_field(target_id, "inventory", inv_array)

        item_name = config_loader.get_item_config(item_id)["name"]
        await ctx.send(f"⚡ **[ADMIN]** ได้เสก `{item_name}` จำนวน `{amount}` ชิ้น เข้ากระเป๋าของ {member.mention} เรียบร้อยแล้ว!")

    # ==========================================
    # 🎉 2. คำสั่งเสกไอเทมให้ผู้เล่นทุกคน (!giveall)
    # ==========================================
    @has_permission("admin")
    @commands.command(name="giveall")
    @commands.has_permissions(administrator=True)
    async def give_item_to_all(self, ctx, item_id: str = None, amount: int = 1):
        if item_id is None:
            return await ctx.send("❌ วิธีใช้: `!giveall [เลขไอเทม] [จำนวน]`\n💡 เช่น: `!giveall 22 1`")

        if not config_loader.get_item_config(item_id):
            return await ctx.send(f"❌ ไม่พบไอเทมรหัส `{item_id}` ในระบบ!")
            
        if amount <= 0:
            return await ctx.send("❌ จำนวนต้องมากกว่า 0 ครับแอดมิน!")

        await ctx.send("⏳ **[ระบบ]** กำลังดำเนินการแพ็คของขวัญแจกผู้เล่นทุกคน โปรดรอสักครู่...")

        # 1. เชื่อมต่อฐานข้อมูล
        db_name = getattr(player_model, "DB_NAME", "game_data.db")
        conn = sqlite3.connect(db_name)
        cursor = conn.cursor()
        
        cursor.execute("SELECT user_id, inventory FROM players")
        all_players = cursor.fetchall()

        # 2. สร้างลิสต์เพื่อเตรียมข้อมูลสำหรับอัปเดตรวดเดียว
        update_data = []
        
        for user_id, raw_inv in all_players:
            # ทำความสะอาดข้อมูลเหมือนเดิม
            clean_inv = str(raw_inv)
            for char in ["(", ")", "[", "]", "'", '"', " "]:
                clean_inv = clean_inv.replace(char, "")
            
            inv_array = clean_inv.split(",") if clean_inv and clean_inv not in ["None", "null"] else []
            inv_array = [i for i in inv_array if i]

            # 🚀 ทริคเพิ่มความเร็ว: ใช้ .extend เข้าไปทีเดียวแทนการวนลูป for
            inv_array.extend([item_id] * amount)

            # เก็บค่าใส่ List ในรูปแบบ Tuple: (ข้อมูลใหม่, user_id)
            update_data.append((json.dumps(inv_array), user_id))

        # ⚡ 3. ท่าไม้ตาย! อัปเดตฐานข้อมูลทุกคนพร้อมกันในคำสั่งเดียว
        cursor.executemany("UPDATE players SET inventory = ? WHERE user_id = ?", update_data)

        conn.commit()
        conn.close()

        item_name = config_loader.get_item_config(item_id)["name"]
        count_players = len(update_data)
        await ctx.send(f"🎉 **[ADMIN GLOBAL]** แจกของขวัญสำเร็จ!\nเสก `{item_name}` x`{amount}` ให้ผู้เล่นทุกคนในฐานข้อมูลเรียบร้อย! (รวมทั้งหมด `{count_players}` คน)")
    
    # ==========================================
    # 🛡️ ระบบดัก Error กรณีผู้เล่นทั่วไปแอบใช้คำสั่งแอดมิน
    # ==========================================
    @spawn_item.error
    @give_item_to_all.error
    async def admin_commands_error(self, ctx, error):
        if isinstance(error, commands.MissingPermissions):
            await ctx.send("⛔ **ปฏิเสธคำสั่ง:** คุณไม่มีสิทธิ์ของระบบ (Administrator) ไม่สามารถใช้งานคำสั่งนี้ได้!")

    # ==========================================
    # 🧲 1. คำสั่งดึงไอเทมออกจากผู้เล่นรายคน (!remove)
    # ==========================================
    @has_permission("police") 
    @commands.command(name="remove")
    @allowed_channel("police")
    @commands.has_permissions(administrator=True) # 🛡️ ล็อกสิทธิ์เฉพาะแอดมิน
    async def remove_item(self, ctx, member: discord.Member = None, item_id: str = None, amount: int = 1):
        if member is None or item_id is None:
            return await ctx.send("❌ วิธีใช้: `!remove @ชื่อผู้เล่น [เลขไอเทม] [จำนวน]`\n💡 เช่น: `!remove @Arthur 28 5`")

        if not config_loader.get_item_config(item_id):
            return await ctx.send(f"❌ ไม่พบไอเทมรหัส `{item_id}` ในระบบ!")
            
        if amount <= 0:
            return await ctx.send("❌ จำนวนต้องมากกว่า 0 ครับแอดมิน!")

        target_id = member.id
        player = player_model.get_player(target_id)
        
        if not player:
            return await ctx.send(f"❌ ไม่พบข้อมูลของ {member.display_name} ในระบบ")

        # 🧹 ถอดรหัสและทำความสะอาดกระเป๋า
        raw_inv = player.get("inventory", "")
        clean_inv = str(raw_inv)
        for char in ["(", ")", "[", "]", "'", '"', " "]:
            clean_inv = clean_inv.replace(char, "")
        inv_array = clean_inv.split(",") if clean_inv and clean_inv not in ["None", "null"] else []
        inv_array = [i for i in inv_array if i]

        # เช็กว่าเขามีไอเทมนี้กี่ชิ้น
        current_count = inv_array.count(item_id)
        item_name = config_loader.get_item_config(item_id)["name"]

        if current_count == 0:
            return await ctx.send(f"❌ {member.display_name} ไม่มี `{item_name}` ในกระเป๋าเลยครับ!")

        # 🧮 คำนวณยอดที่ริบได้จริง (ถ้าริบ 10 แต่เขามี 3 ก็ริบแค่ 3 จะได้ไม่ Error)
        actual_remove = min(current_count, amount)

        for _ in range(actual_remove):
            inv_array.remove(item_id)
            
        # บันทึกคืนฐานข้อมูล
        player_model.update_player_field(target_id, "inventory", inv_array)
        
        await ctx.send(f"🧲 **[ADMIN]** ได้ทำการริบ `{item_name}` จำนวน `{actual_remove}` ชิ้น ออกจากกระเป๋าของ {member.mention} เรียบร้อยแล้ว!")

    # ==========================================
    # 🌪️ 2. คำสั่งดึงไอเทมออกจากผู้เล่นทุกคน (!removeall)
    # ==========================================
    @has_permission("admin")
    @commands.command(name="removeall")
    @commands.has_permissions(administrator=True) # 🛡️ ล็อกสิทธิ์เฉพาะแอดมิน
    async def remove_item_from_all(self, ctx, item_id: str = None, amount: int = 1):
        if item_id is None:
            return await ctx.send("❌ วิธีใช้: `!removeall [เลขไอเทม] [จำนวน]`\n💡 เช่น: `!removeall 22 1` (ริบทีละ 1 ชิ้นจากทุกคน)")

        if not config_loader.get_item_config(item_id):
            return await ctx.send(f"❌ ไม่พบไอเทมรหัส `{item_id}` ในระบบ!")
            
        if amount <= 0:
            return await ctx.send("❌ จำนวนต้องมากกว่า 0 ครับแอดมิน!")

        await ctx.send("⏳ **[ระบบ]** กำลังตรวจสอบและริบไอเทมจากผู้เล่นทุกคน โปรดรอสักครู่...")

        # 1. เชื่อมต่อฐานข้อมูล
        db_name = getattr(player_model, "DB_NAME", "game_data.db")
        conn = sqlite3.connect(db_name)
        cursor = conn.cursor()
        
        cursor.execute("SELECT user_id, inventory FROM players")
        all_players = cursor.fetchall()

        update_data = []
        affected_players = 0
        total_removed = 0

        # 2. วนลูปเช็กทุกคน
        for user_id, raw_inv in all_players:
            clean_inv = str(raw_inv)
            for char in ["(", ")", "[", "]", "'", '"', " "]:
                clean_inv = clean_inv.replace(char, "")
            inv_array = clean_inv.split(",") if clean_inv and clean_inv not in ["None", "null"] else []
            inv_array = [i for i in inv_array if i]

            current_count = inv_array.count(item_id)
            
            # ถ้ายูสเซอร์คนนี้มีไอเทมเป้าหมาย ถึงจะทำการริบ
            if current_count > 0:
                actual_remove = min(current_count, amount)
                for _ in range(actual_remove):
                    inv_array.remove(item_id)
                
                # เก็บข้อมูลเฉพาะคนที่โดนริบ เพื่อเอาไปอัปเดต
                update_data.append((json.dumps(inv_array), user_id))
                affected_players += 1
                total_removed += actual_remove

        # 3. อัปเดตฐานข้อมูลเฉพาะคนที่โดนริบ (ใช้ executemany เพื่อความเร็วปานสายฟ้า)
        if update_data:
            cursor.executemany("UPDATE players SET inventory = ? WHERE user_id = ?", update_data)
            conn.commit()
            
        conn.close()

        item_name = config_loader.get_item_config(item_id)["name"]

        if affected_players == 0:
            await ctx.send(f"✅ ตรวจสอบแล้ว ไม่มีใครในเซิร์ฟเวอร์ครอบครอง `{item_name}` เลยครับ!")
        else:
            await ctx.send(f"🌪️ **[ADMIN GLOBAL]** ปฏิบัติการกวาดล้างสำเร็จ!\nริบ `{item_name}` ไปทั้งหมด `{total_removed}` ชิ้น (จากผู้เล่น `{affected_players}` คน)")

    # 🛡️ ดัก Error (แชร์ร่วมกับคำสั่งแอดมินอื่นๆ ได้เลย)
    @remove_item.error
    @remove_item_from_all.error
    async def admin_remove_error(self, ctx, error):
        if isinstance(error, commands.MissingPermissions):
            await ctx.send("⛔ **ปฏิเสธคำสั่ง:** คุณไม่มีสิทธิ์ใช้งานคำสั่งนี้!")

    # 💰 1. คำสั่งเคลียร์เงินทั้งหมด (เงินสด + ธนาคาร)
    @has_permission("admin")
    @commands.command(name="clearmoney")
    @commands.has_permissions(administrator=True) # จำกัดสิทธิ์ให้เฉพาะแอดมินใช้
    async def clear_money(self, ctx, member: discord.Member = None):
        if not member:
            return await ctx.send("❌ **กรุณาระบุชื่อผู้เล่น!** เช่น `!clearmoney @username`")
        
        # ทำการรีเซ็ตเงินสดและธนาคารให้กลับเป็น 0
        updates = {
            "cash": 0,
            "bank": 0
        }
        player_model.update_player_fields(member.id, updates)
        
        await ctx.send(f"🧹 เคลียร์เงินสดและเงินในธนาคารของ {member.mention} เป็น `0` ทอง เรียบร้อยแล้ว!")

    # 🌟 2. คำสั่งเคลียร์เลเวล, EXP, และถอดยศแรงค์ทั้งหมดในดิสคอร์ด
    @has_permission("admin")
    @commands.command(name="clearlevel")
    @commands.has_permissions(administrator=True) # จำกัดสิทธิ์ให้เฉพาะแอดมินใช้
    async def clear_level(self, ctx, member: discord.Member = None):
        if not member:
            return await ctx.send("❌ **กรุณาระบุชื่อผู้เล่น!** เช่น `!clearlevel @username`")
        
        # 1. รีเซ็ตข้อมูลในฐานข้อมูลกลับเป็นสเตตัสเริ่มต้น (เลเวล 1, แรงค์ F, เลือดเต็ม)
        updates = {
            "level": 1,
            "exp": 0,
            "rank": "F",
            "hp": 100,
            "max_hp": 100
        }
        player_model.update_player_fields(member.id, updates)
        
        # 2. รายชื่อยศ/บทบาทแรงค์ทั้งหมดในดิสคอร์ดที่คุณอาเธอร์กำหนดไว้
        rank_roles_names = [
            "• นักผจญภัยแรงค์ F",
            "• นักผจญภัยแรงค์ E",
            "• นักผจญภัยแรงค์ D",
            "• นักผจญภัยแรงค์ C",
            "• นักผจญภัยแรงค์ B",
            "• นักผจญภัยแรงค์ A",
            "• นักผจญภัยแรงค์ S 🗺️",
            "• นักผจญภัยแรงค์ SS 💰",
            "• นักผจญภัยแรงค์ SSS 👑"
        ]
        
        removed_count = 0
        
        # ลูปตรวจสอบและถอดยศในเซิร์ฟเวอร์ดิสคอร์ด
        for role_name in rank_roles_names:
            role = discord.utils.get(ctx.guild.roles, name=role_name)
            # ถ้าเจอยศในเซิร์ฟเวอร์ และผู้เล่นคนนั้นมียศนี้อยู่จริง
            if role and role in member.roles:
                try:
                    await member.remove_roles(role)
                    removed_count += 1
                except discord.Forbidden:
                    print(f"⚠️ [WARNING] บอทไม่มีสิทธิ์ถอดยศ '{role_name}' (ยศบอทอาจจะอยู่ต่ำกว่ายศนี้)")
                except Exception as e:
                    print(f"⚠️ [ERROR] เกิดข้อผิดพลาดในการถอดยศ {role_name}: {e}")
                    
        await ctx.send(
            f"🌟 รีเซ็ตเลเวล, EXP, และแรงค์ของ {member.mention} กลับเป็นเลเวล 1 เรียบร้อยแล้ว!\n"
            f"🚫 ดึงยศแรงค์เดิมออกจากตัวผู้เล่นเรียบร้อยทั้งหมด `{removed_count}` ยศ"
        )

    # 👑 กำหนด ID ของยศกษัตริย์ (ใส่เป็นตัวเลข Integer ได้เลย)
    KING_ROLE_ID = 1148147180243267624   # fallback — ตั้งจริงที่ Panel (game_balance.roles.king_role_id)

    def get_king_ids(self, ctx):
        """ฟังก์ชันช่วยหาว่าใครมียศกษัตริย์บ้างผ่าน Role ID"""
        # ใช้ get_role(ID) แทนการหาด้วยชื่อ
        role = ctx.guild.get_role(config_loader.get_balance_role_id("king_role_id") or self.KING_ROLE_ID)
        
        if not role:
            print(f"⚠️ [WARNING] หายศกษัตริย์ ID {self.KING_ROLE_ID} ไม่เจอในเซิร์ฟเวอร์นี้!")
            return []
            
        # คืนค่า List ของ ID ผู้เล่นทุกคนที่มียศกษัตริย์
        return [member.id for member in role.members]

    # ==========================================
    # ⚖️ 1. คำสั่งเก็บภาษีขุนนาง (!tax)
    # ==========================================
    @commands.command(name="tax")
    @commands.has_permissions(administrator=True)
    async def collect_tax(self, ctx, min_wealth: int = None, tax_rate: int = None):
        if min_wealth is None or tax_rate is None:
            return await ctx.send("❌ **กรุณาระบุเงื่อนไขให้ครบ!**\nวิธีใช้: `!tax [เงินขั้นต่ำ] [เปอร์เซ็นต์]`")

        if tax_rate <= 0 or tax_rate > 100:
            return await ctx.send("❌ เปอร์เซ็นต์ภาษีต้องอยู่ระหว่าง 1 - 100%")

        await ctx.send("⏳ **กำลังเริ่มกระบวนการจัดเก็บภาษีหลวงทั่วอาณาจักร...**")

        king_ids = self.get_king_ids(ctx)
        all_players = player_model.get_all_players()
        
        taxed_players_count = 0
        total_tax_collected = 0

        for p_info in all_players:
            p_id = p_info["user_id"]
            
            # กษัตริย์ทุกคนได้รับการยกเว้นภาษี
            if p_id in king_ids:
                continue

            player = player_model.get_player(p_id)
            cash = player.get("cash", 0)
            bank = player.get("bank", 0)
            total_wealth = cash + bank

            if total_wealth >= min_wealth:
                tax_amount = int(total_wealth * (tax_rate / 100))
                
                if tax_amount > 0:
                    total_tax_collected += tax_amount
                    taxed_players_count += 1

                    if cash >= tax_amount:
                        player_model.update_player_fields(p_id, {"cash": cash - tax_amount})
                    else:
                        remaining_tax = tax_amount - cash
                        player_model.update_player_fields(p_id, {"cash": 0, "bank": max(0, bank - remaining_tax)})

        if taxed_players_count == 0:
            return await ctx.send("🍃 ไม่พบขุนนางที่มีทรัพย์สินเกินเกณฑ์ที่กำหนดในรอบนี้")

        # สรุปยอดปันส่วนภาษี
        burned_amount = int(total_tax_collected * 0.5) 
        king_pool_amount = total_tax_collected - burned_amount 

        # นำอีก 50% มาหารแบ่งให้กษัตริย์ทุกคน (ถ้ามีกษัตริย์)
        split_per_king = 0
        if king_ids and king_pool_amount > 0:
            split_per_king = king_pool_amount // len(king_ids)
            for k_id in king_ids:
                k_data = player_model.get_player(k_id)
                new_cash = k_data.get("cash", 0) + split_per_king
                player_model.update_player_field(k_id, "cash", new_cash)

        # ส่ง Embed รายงานท้องพระโรง
        embed = discord.Embed(
            title="📜 ประกาศจัดเก็บภาษีหลวงป้องกันเงินเฟ้อ",
            color=discord.Color.dark_gold()
        )
        embed.add_field(name="👥 ขุนนางที่ถูกเก็บภาษี", value=f"`{taxed_players_count}` ท่าน (ทรัพย์สิน >= `{min_wealth:,}`)", inline=False)
        embed.add_field(name="💰 ยอดภาษีรวม", value=f"`{total_tax_collected:,}` ทอง (อัตรา `{tax_rate}`%)", inline=False)
        embed.add_field(name="🔥 ทำลายทิ้ง (50%)", value=f"`{burned_amount:,}` ทอง", inline=True)
        
        king_count_text = f"{len(king_ids)} พระองค์ (องค์ละ {split_per_king:,} ทอง)" if king_ids else "ไม่มีกษัตริย์รับเงิน"
        embed.add_field(name="👑 เข้าพระคลังกษัตริย์ (50%)", value=king_count_text, inline=True)
        
        await ctx.send(embed=embed)


    # ==========================================
    # 🏦 2. คำสั่งแจกจ่ายดอกเบี้ยเยียวยา (!interest)
    # ==========================================
    @commands.command(name="interest")
    @commands.has_permissions(administrator=True)
    async def distribute_interest(self, ctx, max_wealth: int = None, interest_rate: int = None):
        if max_wealth is None or interest_rate is None:
            return await ctx.send("❌ **กรุณาระบุเงื่อนไขให้ครบ!**\nวิธีใช้: `!interest [เงินสูงสุด] [เปอร์เซ็นต์ดอกเบี้ย]`")

        king_ids = self.get_king_ids(ctx)
        if not king_ids:
            return await ctx.send("❌ ไม่สามารถแจกจ่ายได้เนื่องจากไม่มีผู้เล่นที่มียศกษัตริย์ในเซิร์ฟเวอร์นี้เลย!")

        all_players = player_model.get_all_players()
        payout_list = []
        total_interest_needed = 0

        # 1. คำนวณเงินที่จะต้องแจกให้ประชาชน
        for p_info in all_players:
            p_id = p_info["user_id"]
            if p_id in king_ids: # กษัตริย์ไม่ได้ดอกเบี้ยช่วยเหลือ
                continue

            player = player_model.get_player(p_id)
            cash = player.get("cash", 0)
            bank = player.get("bank", 0)
            total_wealth = cash + bank

            if total_wealth <= max_wealth and bank > 0:
                interest_amount = int(bank * (interest_rate / 100))
                if interest_amount > 0:
                    total_interest_needed += interest_amount
                    payout_list.append((p_id, bank, interest_amount))

        if not payout_list:
            return await ctx.send("🍃 ไม่มีราษฎรคนไหนเข้าเกณฑ์รับเงินเยียวยาในรอบนี้")

        # 2. เช็กเงินรวมของกษัตริย์ทุกคนว่าพอจ่ายไหม
        kings_data = []
        total_king_wealth = 0
        for k_id in king_ids:
            k_cash = player_model.get_player(k_id).get("cash", 0)
            total_king_wealth += k_cash
            kings_data.append({"id": k_id, "cash": k_cash})

        if total_king_wealth < total_interest_needed:
            return await ctx.send(f"❌ **เงินกองทุนกษัตริย์รวมกันไม่พอแจก!**\nต้องการ: `{total_interest_needed:,}` ทอง | กษัตริย์มีรวมกัน: `{total_king_wealth:,}` ทอง")

        # 3. หักเงินจากกษัตริย์ (ดึงจากคนรวยสุดก่อน เพื่อความแฟร์)
        kings_data.sort(key=lambda x: x["cash"], reverse=True) 
        remaining_to_deduct = total_interest_needed

        for k in kings_data:
            if remaining_to_deduct <= 0:
                break
            # หักเท่าที่หักได้ (ไม่เกินยอดเงินของกษัตริย์คนนั้น หรือไม่เกินยอดหนี้ที่เหลือ)
            take_amount = min(k["cash"], remaining_to_deduct)
            player_model.update_player_field(k["id"], "cash", k["cash"] - take_amount)
            remaining_to_deduct -= take_amount

        # 4. โอนเงินเข้าธนาคารคนจน
        for p_id, current_bank, interest_amount in payout_list:
            player_model.update_player_field(p_id, "bank", current_bank + interest_amount)

        embed = discord.Embed(
            title="🏦 ท้องพระโรงประกาศมอบดอกเบี้ยเยียวยาประชากร",
            description=f"กษัตริย์ทรงรวมเงินทรัพย์สินส่วนพระองค์แจกจ่ายแก่ราษฎร!",
            color=discord.Color.green()
        )
        embed.add_field(name="📊 เกณฑ์การช่วยเหลือ", value=f"ทรัพย์สินรวม <= `{max_wealth:,}` ทอง\nดอกเบี้ย `{interest_rate}`%", inline=False)
        embed.add_field(name="👥 ราษฎรที่ได้รับการช่วยเหลือ", value=f"`{len(payout_list)}` ท่าน", inline=True)
        embed.add_field(name="💰 ยอดเงินเยียวยารวม", value=f"`{total_interest_needed:,}` ทอง", inline=True)

        await ctx.send(embed=embed)

    # CURRENT_EVENT_MULTIPLIER = 1
    
    @commands.command(name="Xexp")
    @commands.has_permissions(administrator=True)
    async def set_exp_multiplier(self, ctx, multiplier: float):
        if multiplier <= 0:
            return await ctx.send("❌ ตัวคูณต้องมากกว่า 0!")
        
        # เข้าถึงค่าที่ฝากไว้ในตัวบอท
        ctx.bot.CURRENT_EVENT_MULTIPLIER = multiplier
        
        status = "ปกติ" if multiplier == 1 else f"{multiplier} เท่า"
        await ctx.send(f"✅ **ปรับระบบคูณ EXP แล้ว!** ปัจจุบันค่าคูณอยู่ที่: `{status}`")

async def setup(bot):
    await bot.add_cog(AdminCommands(bot))