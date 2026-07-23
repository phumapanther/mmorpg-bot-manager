import discord
from discord.ext import commands
import bot.models.player_model as player_model
from bot import config_loader
from bot.views.profile_embed import create_profile_embed
from bot.views.profile_embed import GAME_RACES, GAME_CLASSES
from bot.utils import not_arrested, allowed_channel  # 👈 ใส่บรรทัดนี้ลงไป

class GameCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        # 🎮 [คลีนระบบ] ถอดคำสั่งสั่งเริ่มทำงานของลูปแจก EXP และ Cooldown แชทออกทั้งหมดแล้ว (ย้ายไปโมดูลอื่นสำเร็จ)

    # ─── 🛒 คำสั่งเปิดร้านค้าและซื้อขายยศ + ระบบกาชาคู่ (สุ่มเผ่า/สุ่มคลาส) (!shop) ───
    @commands.command(name="shop")
    @allowed_channel("role_shop")
    @commands.cooldown(1, 3.0, commands.BucketType.user) # ⏱️ คูลดาวน์ 3 วินาที ต่อผู้เล่น 1 คน
    async def shop(self, ctx, action: str = None, item_num: int = None):
        import random
        from bot.views.profile_embed import GAME_RACES, MONSTER_RACES, GAME_CLASSES

        user_id = ctx.author.id
        player = player_model.get_player(user_id)
        
        # print(f"🛒 [SHOP DEBUG] เริ่มคำสั่งโดย: {ctx.author.name} (ID: {user_id}) | action: {action} | item_num: {item_num}")

        if not player:
            # print(f"❌ [SHOP DEBUG] ไม่พบข้อมูลผู้เล่น ID: {user_id} ในฐานข้อมูล")
            await ctx.send("❌ 不พบข้อมูลตัวละครของคุณ กรุณาพิมพ์ `!play` เพื่อลงทะเบียนก่อนครับ")
            return

        # 📋 อ่านรายการสินค้าจาก config (ตั้งค่าได้ในหน้า Panel) — ลำดับในลิสต์ = เลขไอเทม (เริ่มที่ 1)
        shop_items = {i + 1: item for i, item in enumerate(config_loader.get_shop_items())}

        # 🛑 เคสที่ 1: พิมพ์ !shop เฉยๆ -> บอทเปิดใบรายการหน้าร้านให้ดู
        if action is None:
            lines = []
            for num in sorted(shop_items.keys()):
                it = shop_items[num]
                note = " *(สุ่ม)*" if it["type"] in ("gacha_human", "gacha_monster", "gacha_class") else ""
                lines.append(f"🔸 **[{num}]** {it['name']} — ราคา `{it['price']:,}` ทอง{note}")
            embed = discord.Embed(
                title="🛒 สมาคมนักผจญภัย - ร้านค้าตราเกียรติยศ & ตู้กาชาเวทมนตร์",
                description=(
                    f"ยินดีต้อนรับคุณ **{ctx.author.name}** เข้าสู่หอเกียรติยศ\n"
                    f"💰 เงินคงเหลือปัจจุบัน: `{player.get('cash', 0):,}` ทอง\n\n"
                    f"📌 **รายการสินค้าที่มีวางจำหน่าย:**\n"
                    + "\n".join(lines) +
                    f"\n\n⌨️ **วิธีสั่งซื้อ:** พิมพ์คำสั่ง `!shop ซื้อ [เลขไอเทม]` (เช่น `!shop ซื้อ 1`)"
                ),
                color=0xecc94b
            )
            await ctx.send(embed=embed)
            return

        # 🛑 เคสที่ 2: พิมพ์คำสั่งซื้อแต่กรอกพารามิเตอร์ไม่ครบ
        if action not in ["ซื้อ", "buy"] or item_num is None:
            # print(f"⚠️ [SHOP DEBUG] เงื่อนไขที่ 2: กรอกพารามิเตอร์ไม่ครบหรือคำสั่งซื้อเพี้ยน (action={action})")
            await ctx.send("❓ **รูปแบบคำสั่งไม่ถูกต้อง:** กรุณาพิมพ์ `!shop ซื้อ [เลขไอเทม]` เช่น `!shop ซื้อ 1` ครับ")
            return

        # 🛑 เคสที่ 3: กรอกเลขไอเทมที่ไม่มีในร้าน
        if item_num not in shop_items:
            # print(f"❌ [SHOP DEBUG] เงื่อนไขที่ 3: ค้นหาเลขสินค้าไม่เจอในดิกชันนารี (ไอเทมเบอร์ {item_num})")
            await ctx.send("❌ **ไม่มีสินค้านี้ในระบบ:** กรุณาตรวจสอบเลขไอเทมใหม่อีกครั้ง")
            return

        item = shop_items[item_num]
        price = item["price"]
        current_cash = player.get("cash", 0)

        # print(f"💰 [SHOP DEBUG] ยืนยันข้อมูลราคาสินค้า: {item['name']} ราคา {price} ทอง | กระเป๋าเงินผู้เล่นปัจจุบัน: {current_cash} ทอง")

        if current_cash < price:
            # print(f"❌ [SHOP DEBUG] เงินทองไม่พอจ่าย: ขาดเงินทุนในการจ่ายสินค้ารายการนี้")
            await ctx.send(f"❌ **ทองไม่พอ!** คุณมีเงินเพียง `{current_cash:,}` ทอง แต่ไอเทมนี้ราคา `{price:,}` ทองครับ")
            return

        guild = ctx.guild
        member = ctx.author
        new_cash = current_cash - price

        # ==========================================================
        # 🏆 [ประเภทที่ 1]: ระบบซื้อยศตรง ๆ (รายการ 1 - 3)
        # ==========================================================
        if item["type"] == "rank_role":
            role_id = item.get("role_id")
            role = guild.get_role(role_id) if role_id else None

            if role:
                if role in member.roles:
                    await ctx.send(f"⚠️ คุณมีชั้นยศ **{role.name}** อยู่กับตัวแล้วครับ!")
                    return

                try:
                    player_model.update_player_field(user_id, "cash", new_cash)
                    await member.add_roles(role)
                    await ctx.send(f"✨ 🎉 **ซื้อยศสำเร็จ!** สมาคมได้มอบยศ **{role.name}** ให้แก่คุณเรียบร้อยแล้ว!")
                except discord.Forbidden:
                    await ctx.send("❌ บอทไม่มีสิทธิ์แจกยศนี้ให้คุณได้ (กรุณาแจ้งแอดมินให้ช่วยปรับยศบอทขึ้นสูงด้านบนสุดในเซิร์ฟเวอร์)")
            else:
                await ctx.send(f"❌ **พบข้อผิดพลาด:** แอดมินยังไม่ได้ตั้งค่า Role สำหรับไอเทม **{item['name']}** ในหน้า Panel (หรือ Role ID ไม่ถูกต้อง)")

        # ==========================================================
        # 👲🏻 [ประเภทที่ 2]: ตู้กาชาเผ่ามนุษย์ (รายการ 4)
        # ==========================================================
        elif item["type"] == "gacha_human":
            # print("🔵 [SHOP DEBUG] กำลังสุ่มตู้กาชาเผ่ามนุษย์...")
            chosen_race_name = random.choice(GAME_RACES)
            new_role = discord.utils.get(guild.roles, name=chosen_race_name)
            # print(f"🎲 [SHOP DEBUG] ผลการสุ่มได้: {chosen_race_name}")
            
            if not new_role:
                # print(f"❌ [SHOP ERROR] หาวัตถุยศไม่เจอตามชื่อยศ: {chosen_race_name}")
                await ctx.send(f"⚠️ สุ่มได้เผ่า `{chosen_race_name}` แต่หาระบบยศในดิสคอร์ดไม่เจอ")
                return

            try:
                player_model.update_player_field(user_id, "cash", new_cash)
                # 🧼 ดึงยศปัจจุบันทั้งหมดคัดกรองเผ่าพันธุ์เดิมออกทั้งหมดไร้รอยต่อ
                removed_races = [r.name for r in member.roles if r.name in GAME_RACES or r.name in MONSTER_RACES]
                updated_roles = [role for role in member.roles if role.name not in GAME_RACES and role.name not in MONSTER_RACES]
                updated_roles.append(new_role)
                
                await member.edit(roles=updated_roles)
                removed_msg = f" (ปลดเผ่าเดิม: `{removed_races[0]}` ออกแล้ว)" if removed_races else ""
                # print(f"✅ [SHOP DEBUG] สลับยศเผ่ามนุษย์เสร็จสิ้น เงินคงเหลือล่าสุด: {new_cash}")
                await ctx.send(
                    f"🎰🔮 **[ตู้กาชาโบราณ]** คุณ {member.mention} ได้ฉีกคัมภีร์สุ่มเผ่าพันธุ์สำเร็จ!\n"
                    f"🧬 พรแห่งโชคชะตาเปลี่ยนร่างของคุณเป็น: **{chosen_race_name}** ✨{removed_msg}\n"
                    f"💸 เสียค่าธรรมเนียมกาชา: `- {price:,}` ทอง (คงเหลือ: `{new_cash:,}` ทอง)"
                )
            except discord.Forbidden:
                # print("🚨 [SHOP ERROR] ไม่สามารถแก้ไขยศได้เนื่องจากลำดับยศบอทอยู่ต่ำเกินไป")
                await ctx.send("❌ บอทไม่มีสิทธิ์จัดการยศแก้ไขโครงสร้างยศเผ่าพันธุ์ของคุณ")

        # ==========================================================
        # 👹 [ประเภทที่ 3]: ตู้กาชาเผ่าปีศาจ (รายการ 5)
        # ==========================================================
        elif item["type"] == "gacha_monster":
            # print("🔴 [SHOP DEBUG] กำลังสุ่มตู้กาชาเผ่าปีศาจมอนสเตอร์...")
            chosen_monster_name = random.choice(MONSTER_RACES)
            new_role = discord.utils.get(guild.roles, name=chosen_monster_name)
            # print(f"🎲 [SHOP DEBUG] ผลการสุ่มได้: {chosen_monster_name}")
            
            if not new_role:
                # print(f"❌ [SHOP ERROR] หาวัตถุยศไม่เจอตามชื่อยศปีศาจ: {chosen_monster_name}")
                await ctx.send(f"⚠️ สุ่มได้ปีศาจ `{chosen_monster_name}` แต่หาระบบยศในดิสคอร์ดไม่เจอ")
                return

            try:
                player_model.update_player_field(user_id, "cash", new_cash)
                removed_races = [r.name for r in member.roles if r.name in GAME_RACES or r.name in MONSTER_RACES]
                updated_roles = [role for role in member.roles if role.name not in GAME_RACES and role.name not in MONSTER_RACES]
                updated_roles.append(new_role)
                
                await member.edit(roles=updated_roles)
                removed_msg = f" (ปลดเผ่าเดิม: `{removed_races[0]}` ออกแล้ว)" if removed_races else ""
                # print(f"✅ [SHOP DEBUG] สลับยศเผ่าปีศาจเสร็จสิ้น เงินคงเหลือล่าสุด: {new_cash}")
                await ctx.send(
                    f"🎲 🔥 **[กาชาสุ่มเผ่าปีศาจ]** จิตวิญญาณสยบสู่ความมืดสลัดร่างเดิมทิ้งพังทลาย!\n"
                    f"👑 พลังแห่งมิติเวทมนตร์เลือกเผ่าใหม่ให้คุณคือ: **{chosen_monster_name}** 🔴{removed_msg}\n"
                    f"💸 เสียค่าธรรมเนียมกาชา: `- {price:,}` ทอง (คงเหลือ: `{new_cash:,}` ทอง)"
                )
            except discord.Forbidden:
                # print("🚨 [SHOP ERROR] บอทไม่มีสิทธิ์สลับแก้ไขลำดับยศของผู้เล่น")
                await ctx.send("❌ บอทไม่มีสิทธิ์จัดการยศแก้ไขโครงสร้างยศเผ่าพันธุ์ของคุณ")

        # ==========================================================
        # 🔮 [ประเภทที่ 4]: ตู้กาชาเปลี่ยนคลาสอาชีพ (รายการ 6)
        # ==========================================================
        elif item["type"] == "gacha_class":
            # print("🔮 [SHOP DEBUG] กำลังดำเนินการตู้กาชาปรับเปลี่ยนคลาสอาชีพ...")
            chosen_class_name = random.choice(GAME_CLASSES)
            new_role = discord.utils.get(guild.roles, name=chosen_class_name)
            # print(f"🎲 [SHOP DEBUG] ผลการสุ่มได้คลาส: {chosen_class_name}")
            
            if not new_role:
                # print(f"❌ [SHOP ERROR] ค้นหายศอาชีพเป้าหมายไม่เจอในระบบเซิร์ฟเวอร์: {chosen_class_name}")
                await ctx.send(f"⚠️ สุ่มได้คลาส `{chosen_class_name}` แต่หาระบบยศในดิสคอร์ดไม่เจอ")
                return

            try:
                player_model.update_player_field(user_id, "cash", new_cash)
                removed_classes = [r.name for r in member.roles if r.name in GAME_CLASSES]
                updated_roles = [role for role in member.roles if role.name not in GAME_CLASSES]
                updated_roles.append(new_role)
                
                await member.edit(roles=updated_roles)
                removed_msg = f" (สละอาชีพเดิม: `{removed_classes[0]}` เคลียร์ออกเรียบร้อย)" if removed_classes else ""
                # print(f"✅ [SHOP DEBUG] สลับอาชีพใหม่สำเร็จแล้ว เงินคงเหลือล่าสุด: {new_cash}")
                await ctx.send(
                    f"🔮✨ **[แท่นทำนายวิญญาณ]** คุณ {member.mention} ได้เบิกเนตรสุ่มคลาสอาชีพใหม่สำเร็จ!\n"
                    f"⚔️ จิตวิญญาณแห่งการต่อสู้เลือกให้คุณเป็นคลาส: **{chosen_class_name}** 🛡️{removed_msg}\n"
                    f"💸 เสียค่าธูปทำนายวิญญาณ: `- {price:,}` ทอง (คงเหลือ: `{new_cash:,}` ทอง)"
                )
            except discord.Forbidden:
                # print("🚨 [SHOP ERROR] ไม่สามารถแก้ไขสิทธิ์จัดการปรับยศคลาสอาชีพได้")
                await ctx.send("❌ บอทไม่มีสิทธิ์จัดการยศ กรุณาลากยศบอทให้อยู่สูงกว่ายศคลาสอาชีพทั้งหมดด้วยครับ")

    # ─── 📊 คำสั่งพิมพ์ดูโปรไฟล์ ───
    @commands.command(name="profile", aliases=["info"])
    @allowed_channel("profile")
    @commands.cooldown(1, 30.0, commands.BucketType.user) # ⏱️ คูลดาวน์ 
    async def profile(self, ctx, member: discord.Member = None):
        target_member = member if member else ctx.author
        player_data = player_model.get_player(target_member.id)
        
        embed = create_profile_embed(target_member, player_data)
        await ctx.send(embed=embed)

    # ─── 🕹️ เมนูปุ่มสะดวก (กระเป๋า/ธนาคาร/โปรไฟล์/ใช้ไอเทม) — ระบบเดียวกับคำสั่งเดิม แค่แยกเป็นปุ่ม ───
    @commands.command(name="menu")
    async def game_menu(self, ctx):
        from bot.views.menu_view import GameMenuView
        embed = discord.Embed(
            title="🕹️ เมนูผู้เล่น",
            description="กดปุ่มด้านล่างเพื่อเช็กกระเป๋า/ธนาคาร/โปรไฟล์ หรือใช้ไอเทม (คำสั่งพิมพ์เดิม เช่น `!bag` `!bank` ยังใช้ได้ตามปกติ)",
            color=discord.Color.blurple()
        )
        await ctx.send(embed=embed, view=GameMenuView())

    # ─── ⚔️ คำสั่งเล่นเกมคอร์หลัก (ระบบแสดงผลเฉพาะคนใช้คำสั่ง - Ephemeral + ล็อกห้องมิติ) ───
    @commands.hybrid_command(name="play", description="เริ่มออกเดินทางในโลก D&D MMORPG")
    @commands.cooldown(1, 3.0, commands.BucketType.user) # ⏱️ แก้กลับเป็นคูลดาวน์ 3 วินาทีตามที่คุยกันรอบก่อนครับน้า
    async def play(self, ctx):
        user_id = ctx.author.id
        
        # 🔒 [ระบบรักษาความปลอดภัยพื้นที่] ดักเช็กให้ใช้คำสั่งได้เฉพาะในห้องมิติส่วนตัวของตัวเองเท่านั้น!
        required_room_part = f"มิติส่วนตัว-{ctx.author.name.lower()}"
        current_room_name = ctx.channel.name.lower()

        if required_room_part not in current_room_name:
            # ใช้ ephemeral=True เพื่อส่งข้อความกระซิบเตือนเห็นคนเดียว ไม่รบกวนช่องแชทหลัก
            await ctx.send(
                f"❌ **[พื้นที่ไม่ถูกต้อง]** คุณ {ctx.author.mention} ไม่สามารถเริ่มผจญภัยตรงนี้ได้ครับ!\n"
                f"📌 กรุณาไปเปิดมิติส่วนตัวโดยพิมพ์ `!adv` ในห้องหลักก่อน แล้วเข้าไปรันคำสั่งเล่นเกมในห้องลับนั้นนะครับ", 
                ephemeral=True
            )
            return

        # ─── 🟢 โครงสร้างโค้ดระบบเกมเดิมทำงานต่อจากตรงนี้ด้านล่างเมื่อผ่านประตูมิติเข้ามา ───
        player = player_model.get_player(user_id)
        
        if not player:
            await ctx.send("❌ **ไม่พบข้อมูลตัวละครของคุณ!** กรุณาลงทะเบียนสร้างตัวละครก่อนครับ", ephemeral=True)
            return

        current_level = player.get("level", 1)
        _, current_rank = player_model.check_and_update_rank(user_id, current_level)
        
        guild = ctx.guild
        member = ctx.author
        
        if guild and isinstance(member, discord.Member):
            def get_eligible_ranks(lvl):
                eligible = ["F"]
                if lvl >= 5: eligible.append("E")
                if lvl >= 10: eligible.append("D")
                if lvl >= 20: eligible.append("C")
                if lvl >= 50: eligible.append("B")
                if lvl >= 80: eligible.append("A")
                if lvl >= 100: eligible.append("SSS")
                return eligible

            eligible_ranks = get_eligible_ranks(current_level)
            roles_to_add = []

            for r in eligible_ranks:
                role_name = f"นักผจญภัยแรงค์ {r}"
                role = discord.utils.get(guild.roles, name=role_name)
                if role and role not in member.roles:
                    roles_to_add.append(role)

            if roles_to_add:
                try:
                    await member.add_roles(*roles_to_add)
                    role_names_str = ", ".join([r.name for r in roles_to_add])
                    # print(f"🏅 [Auto-Sync] เติมยศที่ขาดหายให้คุณ {member.name}: {role_names_str}")
                except discord.Forbidden:
                    print(f"❌ บอทไม่มีสิทธิ์จัดการยศ (Manage Roles) ตอนรันคำสั่ง !play")
                except Exception as e:
                    print(f"⚠️ เกิดข้อผิดพลาดในการซิงค์ยศตอน !play: {e}")

        if player["current_state"] in ["fighting", "dead"] or player["hp"] <= 0:
            player_model.update_player_field(user_id, "current_state", "dead")
            
            embed = discord.Embed(
                title="💀 คุณพ่ายแพ้ในการต่อสู้และหมดสติลง...",
                description=f"วิญญาณของคุณยังล่องลอยอยู่กลางสนามรบ\n❤️ HP ของคุณ: `0/{player['max_hp']}`\n\n📌 กรุณากดปุ่มด้านล่างเพื่อฟื้นตัวและยอมรับบทลงโทษกลับหมู่บ้าน",
                color=0xe53e3e
            )
            from bot.views.game_views import RespawnView
            await ctx.send(embed=embed, view=RespawnView(user_id), ephemeral=True)
            return 

        lock_states = ["npc_choice", "treasure_choice", "dungeon_choice", "trap_defense", "village", "shopping", "travel_choice"]
        if player["current_state"] in lock_states:
            player_model.update_player_field(user_id, "current_state", "idle")
            player = player_model.get_player(user_id)

        from bot import game_modifiers
        weekly_theme = game_modifiers.get_weekly_theme()
        theme_line = f"\n🎪 อีเวนต์สัปดาห์นี้: {weekly_theme['label']}" if weekly_theme else ""
        player_statuses = game_modifiers.parse_statuses(player)
        status_line = f"\n🩸 สถานะติดตัว: {game_modifiers.format_status_line(player_statuses)}" if player_statuses else ""
        embed = discord.Embed(
            title="⚔️ ยินดีต้อนรับสู่โลก D&D MMORPG",
            description=(
                f"กระเป๋าเงินกลางของคุณ: `{player['cash']}` ทอง\n"
                f"สถานะปัจจุบัน: `{player['current_state']}`\n"
                f"🗺️ ทวีปปัจจุบัน: {game_modifiers.get_continent(player)['label']}"
                f"{theme_line}{status_line}"
            ),
            color=0x2b6cb0
        )

        from bot.views.game_views import AdventureView
        await ctx.send(embed=embed, view=AdventureView(author_id=user_id), ephemeral=True)

    # ─── 🚨 ระบบตรวจจับและดักจับ Error คูลดาวน์ของ Cog นี้ ───
    async def cog_command_error(self, ctx, error):
        """เมื่อเกิด Error ในระบบคำสั่งของ Cog นี้ ตัวดักจับจะทำงานอัตโนมัติ"""
        if isinstance(error, commands.CommandOnCooldown):
            # ดักจับแล้วส่งข้อความเตือนผู้เล่นแบบเป็นมิตร (บอกเวลาที่เหลืออยู่เป็นทศนิยม 1 ตำแหน่ง)
            # ถ้าเป็น Hybrid / Slash Command (เช่น !play) จะกระซิบตอบแบบ ephemeral อัตโนมัติถ้าตั้งค่าไว้
            try:
                await ctx.send(
                    f"⏱️ **[คูลดาวน์]** ใจเย็น ๆ ครับนักผจญภัย! กรุณารออีก `{error.retry_after:.1f}` วินาที ถึงจะสามารถใช้คำสั่งถัดไปได้นะ", 
                    delete_after=3.0 # ลบข้อความบอทบ่นออโต้ใน 3 วิ เพื่อรักษาความสะอาดของช่องแชท
                )
            except discord.HTTPException:
                pass
        else:
            # ถ้าเป็น Error ตัวอื่นที่ไม่ใช่คูลดาวน์ ให้ระบบพ่นออกมาที่หน้า Terminal ตามปกติเพื่อไว้ไล่บั๊ก
            raise error

# ฟังก์ชันสำหรับให้ตัวบอทหลักโหลด Cog นี้เข้าสู่ระบบ
async def setup(bot):
    await bot.add_cog(GameCommands(bot))