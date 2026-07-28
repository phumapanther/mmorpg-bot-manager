# 🏰 ระบบกิลด์ (P6) — สร้างกิลด์ 3,000,000,000 ทอง (เงินสด) → ยศ + ห้องบ้านกิลด์อัตโนมัติ
# คลังกิลด์: สมาชิกฝากได้ทุกคน / ถอน-แจกจ่ายได้เฉพาะหัวหน้า | ยุบกิลด์ = คลังคืนธนาคารหัวหน้า
import discord
from discord.ext import commands

import bot.models.player_model as player_model
from bot import game_modifiers
from bot.utils import allowed_channel, is_main_server

GUILD_CREATE_COST = 3_000_000_000
# หมวดหมู่ห้องกิลด์ — ใช้ตัวที่มีอยู่แล้วในเซิร์ฟ (ชื่อต้องตรงเป๊ะ) ไม่มีค่อยสร้างใหม่
GUILD_CATEGORY = "⌈🏛⌋ ▏▬▬ ห้องกิลด์ส่วนตัว ▬▬▕"
GUILD_ICON = "🏰"  # ไอคอนกลาง — ผู้ใช้ตัดพารามิเตอร์ไอคอนออก (มีปัญหา) เหลือชื่ออย่างเดียว
# ยศคั่น "╔══❖═══ยศกิลด์═══❖══╗" ในเซิร์ฟหลัก — ยศกิลด์ใหม่ต้องเรียงใต้ยศนี้เสมอ
# (เซิร์ฟอื่นไม่มียศนี้ = ข้ามการจัดตำแหน่งเฉย ๆ ไม่พัง)
GUILD_ROLE_DIVIDER_ID = 1160555382977081415
GUILD_RENAME_COST = 100_000_000  # ค่าเปลี่ยนชื่อกิลด์ (เงินสดหัวหน้า)
# ยศ "หัวหน้ากิลด์" ในเซิร์ฟหลัก — แจกตอนก่อตั้ง ถอดตอนยุบ (เซิร์ฟไม่มียศนี้ = ข้ามเฉย ๆ)
GUILD_LEADER_ROLE_ID = 1148195663222411357


async def _sync_leader_role(member, is_leader):
    """ให้/ถอดยศหัวหน้ากิลด์ตามสถานะจริง — DB คือความจริงหลัก ยศคือป้ายแสดง"""
    role = member.guild.get_role(GUILD_LEADER_ROLE_ID)
    if not role:
        return
    try:
        if is_leader and role not in member.roles:
            await member.add_roles(role, reason="ก่อตั้งกิลด์ — รับตำแหน่งหัวหน้า")
        elif not is_leader and role in member.roles:
            await member.remove_roles(role, reason="พ้นตำแหน่งหัวหน้ากิลด์")
    except (discord.Forbidden, discord.HTTPException):
        pass

# ตรรกะเช็คห้องเดียวกับคำสั่งอื่น (config channels.guild — ตั้งได้ในแท็บ Channels ของ panel)
_guild_channel_check = allowed_channel("guild").predicate


def _is_leader(user_id):
    g = player_model.get_guild_of(user_id)
    return g if g and g["leader_id"] == user_id else None


class GuildInviteView(discord.ui.View):
    """ปุ่มยืนยันคำเชิญ — เฉพาะคนถูกเชิญกดได้ ภายใน 2 นาที"""
    def __init__(self, target_id, guild_row):
        super().__init__(timeout=120)
        self.target_id = target_id
        self.guild_row = guild_row

    async def interaction_check(self, interaction):
        if interaction.user.id != self.target_id:
            await interaction.response.send_message("❌ คำเชิญนี้ไม่ใช่ของคุณ!", ephemeral=True)
            return False
        return True

    @discord.ui.button(label="✅ เข้าร่วมกิลด์", style=discord.ButtonStyle.success)
    async def accept(self, interaction: discord.Interaction, button: discord.ui.Button):
        g = self.guild_row
        if player_model.get_guild_of(self.target_id):
            return await interaction.response.edit_message(content="❌ คุณมีกิลด์อยู่แล้ว!", view=None)
        if not player_model.add_guild_member(self.target_id, g["guild_id"]):
            return await interaction.response.edit_message(content="❌ เข้าร่วมไม่สำเร็จ ลองใหม่อีกครั้ง", view=None)
        role = interaction.guild.get_role(g["role_id"])
        if role:
            try:
                await interaction.user.add_roles(role, reason="เข้าร่วมกิลด์")
            except discord.Forbidden:
                pass
        await interaction.response.edit_message(
            content=f"🏰 **{interaction.user.display_name}** เข้าร่วมกิลด์ **{g['icon']} {g['name']}** แล้ว! ยินดีต้อนรับ!", view=None)

    @discord.ui.button(label="❌ ปฏิเสธ", style=discord.ButtonStyle.secondary)
    async def decline(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.edit_message(content="🕊️ คำเชิญถูกปฏิเสธ", view=None)


class GuildCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        print("[LOG] [LOAD_COG] โหลดโมดูลระบบกิลด์เรียบร้อยแล้ว")

    async def cog_check(self, ctx):
        """เซิร์ฟหลักเท่านั้น (P8) + ห้องที่ตั้งใน channels.guild (ไม่ตั้ง = ทุกห้อง)"""
        if not is_main_server(ctx):
            return False
        return await _guild_channel_check(ctx)

    @commands.group(name="guild", aliases=["กิลด์"], invoke_without_command=True)
    async def guild(self, ctx):
        """!guild เฉย ๆ = ดูหน้ากิลด์ตัวเอง / วิธีใช้"""
        g = player_model.get_guild_of(ctx.author.id)
        if g:
            return await self.info(ctx)
        await ctx.send(embed=discord.Embed(
            title="🏰 ระบบกิลด์", color=0x7f8c8d,
            description=(f"คุณยังไม่มีกิลด์ — สร้างเองด้วย `!guild create <ชื่อ> <ไอคอน>` "
                         f"(ค่าสร้าง `{GUILD_CREATE_COST:,}` ทองสด) หรือรอคำเชิญจากหัวหน้ากิลด์\n\n"
                         "`!guild info` หน้ากิลด์ • `!guild deposit <จำนวน>` ฝากคลัง\n"
                         "หัวหน้า: `invite @คน` / `kick @คน` / `withdraw` / `pay @คน <จำนวน>` / `disband`")))

    @guild.command(name="create")
    async def create(self, ctx, *, name: str = None):
        if not name:
            return await ctx.send("❓ วิธีใช้: `!guild create <ชื่อกิลด์>` เช่น `!guild create มังกรทมิฬ`")
        name = name.strip()
        if player_model.get_guild_of(ctx.author.id):
            return await ctx.send("❌ คุณมีกิลด์อยู่แล้ว! ออกจากกิลด์เดิมก่อน")
        if player_model.get_guild_by_name(name):
            return await ctx.send(f"❌ ชื่อกิลด์ **{name}** ถูกใช้ไปแล้ว")
        player = player_model.get_player(ctx.author.id)
        if not player or player.get("cash", 0) < GUILD_CREATE_COST:
            return await ctx.send(f"❌ ต้องถือ **เงินสด** `{GUILD_CREATE_COST:,}` ทองเพื่อก่อตั้งกิลด์! "
                                  f"(ตอนนี้มี `{(player or {}).get('cash', 0):,}`)")

        # สร้างยศ + บ้านกิลด์เป็น "ห้องเสียงส่วนตัว" ใต้หมวดหมู่ห้องกิลด์ที่มีอยู่แล้วในเซิร์ฟ
        try:
            import random as _r
            role = await ctx.guild.create_role(
                name=name, colour=discord.Colour(_r.randint(0x111111, 0xffffff)),
                mentionable=True, reason=f"ก่อตั้งกิลด์โดย {ctx.author.display_name}")
            # 📌 จัดตำแหน่งยศ: ต้องอยู่ใต้ยศคั่น ╔══❖═══ยศกิลด์═══❖══╗ เสมอ
            divider = ctx.guild.get_role(GUILD_ROLE_DIVIDER_ID)
            if divider:
                try:
                    await role.edit(position=max(1, divider.position - 1))
                except (discord.Forbidden, discord.HTTPException):
                    pass  # ยศบอทอยู่ต่ำกว่ายศคั่น = จัดไม่ได้ แต่กิลด์ยังใช้งานได้
            category = discord.utils.get(ctx.guild.categories, name=GUILD_CATEGORY)
            if category is None:
                category = await ctx.guild.create_category(GUILD_CATEGORY)
            overwrites = {
                ctx.guild.default_role: discord.PermissionOverwrite(view_channel=False),
                role: discord.PermissionOverwrite(view_channel=True, connect=True, speak=True, send_messages=True),
                ctx.guild.me: discord.PermissionOverwrite(view_channel=True, connect=True),
            }
            channel = await ctx.guild.create_voice_channel(f"{GUILD_ICON}︱{name}", category=category, overwrites=overwrites)
        except discord.Forbidden:
            return await ctx.send("❌ บอทไม่มีสิทธิ์สร้างยศ/ห้อง (ต้องการ Manage Roles + Manage Channels)")

        gid = player_model.create_guild(name, GUILD_ICON, ctx.author.id, role.id, channel.id)
        if gid is None:  # กันชนกันเสี้ยววินาที — ถอยของที่สร้างไป
            await role.delete()
            await channel.delete()
            return await ctx.send("❌ สร้างไม่สำเร็จ (ชื่อซ้ำ/คุณเป็นหัวหน้ากิลด์อื่นอยู่)")

        player_model.update_player_field(ctx.author.id, "cash", player["cash"] - GUILD_CREATE_COST)
        await ctx.author.add_roles(role, reason="หัวหน้ากิลด์")
        await _sync_leader_role(ctx.author, True)  # แจกยศหัวหน้ากิลด์ (id กลางของเซิร์ฟ)
        await ctx.send(embed=discord.Embed(
            title=f"🏰 ก่อตั้งกิลด์ {name} สำเร็จ!", color=role.colour,
            description=(f"👑 หัวหน้ากิลด์: {ctx.author.mention}\n"
                         f"🔊 บ้านกิลด์ (ห้องเสียงส่วนตัว): {channel.mention} — เฉพาะสมาชิก\n"
                         f"💸 ค่าก่อตั้ง: `{GUILD_CREATE_COST:,}` ทอง\n\n"
                         f"เชิญสมาชิกด้วย `!guild invite @คน`")))

    @guild.command(name="invite")
    async def invite(self, ctx, member: discord.Member = None):
        g = _is_leader(ctx.author.id)
        if not g:
            return await ctx.send("❌ เฉพาะหัวหน้ากิลด์เท่านั้นที่เชิญสมาชิกได้!")
        if member is None or member.bot:
            return await ctx.send("❓ วิธีใช้: `!guild invite @คน`")
        if player_model.get_guild_of(member.id):
            return await ctx.send(f"❌ {member.display_name} มีกิลด์อยู่แล้ว!")
        await ctx.send(f"💌 {member.mention} — **{g['icon']} {g['name']}** เชิญคุณเข้าร่วมกิลด์!",
                       view=GuildInviteView(member.id, g))

    @guild.command(name="leave")
    async def leave(self, ctx):
        g = player_model.get_guild_of(ctx.author.id)
        if not g:
            return await ctx.send("❌ คุณไม่มีกิลด์!")
        if g["leader_id"] == ctx.author.id:
            return await ctx.send("❌ หัวหน้าออกจากกิลด์ไม่ได้ — ใช้ `!guild disband` เพื่อยุบกิลด์")
        player_model.remove_guild_member(ctx.author.id)
        role = ctx.guild.get_role(g["role_id"])
        if role:
            try:
                await ctx.author.remove_roles(role, reason="ออกจากกิลด์")
            except discord.Forbidden:
                pass
        await ctx.send(f"👋 คุณออกจากกิลด์ **{g['icon']} {g['name']}** แล้ว")

    @guild.command(name="kick")
    async def kick(self, ctx, member: discord.Member = None):
        g = _is_leader(ctx.author.id)
        if not g:
            return await ctx.send("❌ เฉพาะหัวหน้ากิลด์เท่านั้น!")
        if member is None or member.id == ctx.author.id:
            return await ctx.send("❓ วิธีใช้: `!guild kick @คน` (เตะตัวเองไม่ได้)")
        target_guild = player_model.get_guild_of(member.id)
        if not target_guild or target_guild["guild_id"] != g["guild_id"]:
            return await ctx.send(f"❌ {member.display_name} ไม่ได้อยู่กิลด์ของคุณ!")
        player_model.remove_guild_member(member.id)
        role = ctx.guild.get_role(g["role_id"])
        if role:
            try:
                await member.remove_roles(role, reason="ถูกเตะออกจากกิลด์")
            except discord.Forbidden:
                pass
        await ctx.send(f"🥾 {member.mention} ถูกเชิญออกจากกิลด์ **{g['icon']} {g['name']}**")

    @guild.command(name="disband")
    async def disband(self, ctx):
        g = _is_leader(ctx.author.id)
        if not g:
            return await ctx.send("❌ เฉพาะหัวหน้ากิลด์เท่านั้น!")
        # คลังที่เหลือคืนเข้าธนาคารหัวหน้า (ตามที่ตกลง)
        treasury = g["treasury"]
        if treasury:
            player = player_model.get_player(ctx.author.id)
            player_model.update_player_field(ctx.author.id, "bank", player.get("bank", 0) + treasury)
        role = ctx.guild.get_role(g["role_id"])
        channel = ctx.guild.get_channel(g["channel_id"])
        try:
            if role:
                await role.delete(reason="ยุบกิลด์")
            if channel:
                await channel.delete(reason="ยุบกิลด์")
        except discord.Forbidden:
            pass
        player_model.delete_guild(g["guild_id"])
        await _sync_leader_role(ctx.author, False)  # ถอดยศหัวหน้ากิลด์
        await ctx.send(f"💥 กิลด์ **{g['icon']} {g['name']}** ถูกยุบแล้ว — คลัง `{treasury:,}` ทองคืนเข้าธนาคารหัวหน้า")

    @guild.command(name="deposit")
    async def deposit(self, ctx, amount: int = 0):
        g = player_model.get_guild_of(ctx.author.id)
        if not g:
            return await ctx.send("❌ คุณไม่มีกิลด์!")
        if amount <= 0:
            return await ctx.send("❓ วิธีใช้: `!guild deposit <จำนวน>` (หักจากธนาคารของคุณ)")
        player = player_model.get_player(ctx.author.id)
        if player.get("bank", 0) < amount:
            return await ctx.send("❌ เงินในธนาคารของคุณไม่พอ!")
        player_model.update_player_field(ctx.author.id, "bank", player["bank"] - amount)
        total = player_model.guild_add_treasury(g["guild_id"], amount)
        await ctx.send(f"🏰 ฝากเข้าคลังกิลด์ `{amount:,}` ทอง — คลังรวม `{total:,}` ทอง ขอบคุณที่บำรุงกิลด์!")

    @guild.command(name="withdraw")
    async def withdraw(self, ctx, amount: int = 0):
        g = _is_leader(ctx.author.id)
        if not g:
            return await ctx.send("❌ ถอนคลังได้เฉพาะหัวหน้ากิลด์เท่านั้น!")
        if amount <= 0:
            return await ctx.send("❓ วิธีใช้: `!guild withdraw <จำนวน>`")
        total = player_model.guild_add_treasury(g["guild_id"], -amount)
        if total is None:
            return await ctx.send(f"❌ คลังกิลด์มีไม่พอ! (คงเหลือ `{g['treasury']:,}`)")
        player = player_model.get_player(ctx.author.id)
        player_model.update_player_field(ctx.author.id, "bank", player.get("bank", 0) + amount)
        await ctx.send(f"💰 ถอนจากคลังกิลด์ `{amount:,}` ทองเข้าธนาคารหัวหน้า — คลังเหลือ `{total:,}`")

    @guild.command(name="pay")
    async def pay(self, ctx, member: discord.Member = None, amount: int = 0):
        g = _is_leader(ctx.author.id)
        if not g:
            return await ctx.send("❌ แจกจ่ายคลังได้เฉพาะหัวหน้ากิลด์เท่านั้น!")
        if member is None or amount <= 0:
            return await ctx.send("❓ วิธีใช้: `!guild pay @สมาชิก <จำนวน>`")
        target_guild = player_model.get_guild_of(member.id)
        if not target_guild or target_guild["guild_id"] != g["guild_id"]:
            return await ctx.send(f"❌ {member.display_name} ไม่ได้อยู่กิลด์ของคุณ!")
        total = player_model.guild_add_treasury(g["guild_id"], -amount)
        if total is None:
            return await ctx.send(f"❌ คลังกิลด์มีไม่พอ! (คงเหลือ `{g['treasury']:,}`)")
        target = player_model.get_player(member.id)
        player_model.update_player_field(member.id, "bank", target.get("bank", 0) + amount)
        await ctx.send(f"💸 หัวหน้าแจกจ่าย `{amount:,}` ทองให้ {member.mention} (เข้าธนาคาร) — คลังเหลือ `{total:,}`")

    @guild.command(name="rename")
    async def rename(self, ctx, *, new_name: str = None):
        g = _is_leader(ctx.author.id)
        if not g:
            return await ctx.send("❌ เปลี่ยนชื่อกิลด์ได้เฉพาะหัวหน้ากิลด์เท่านั้น!")
        if not new_name:
            return await ctx.send(f"❓ วิธีใช้: `!guild rename <ชื่อใหม่>` (ค่าธรรมเนียม `{GUILD_RENAME_COST:,}` ทองสด)")
        new_name = new_name.strip()
        if player_model.get_guild_by_name(new_name):
            return await ctx.send(f"❌ ชื่อ **{new_name}** ถูกใช้ไปแล้ว")
        player = player_model.get_player(ctx.author.id)
        if not player or player.get("cash", 0) < GUILD_RENAME_COST:
            return await ctx.send(f"❌ ค่าเปลี่ยนชื่อกิลด์ `{GUILD_RENAME_COST:,}` ทอง**สด** — "
                                  f"ตอนนี้คุณมี `{(player or {}).get('cash', 0):,}`")
        old_name = g["name"]
        if not player_model.rename_guild(g["guild_id"], new_name):
            return await ctx.send("❌ เปลี่ยนชื่อไม่สำเร็จ ลองใหม่อีกครั้ง (ยังไม่ถูกหักเงิน)")
        player_model.update_player_field(ctx.author.id, "cash", player["cash"] - GUILD_RENAME_COST)
        # เปลี่ยนชื่อยศ + ห้องเสียงให้ตรงกัน (พลาดตรงไหนก็ไม่ล้มคำสั่ง — DB คือความจริงหลัก)
        role = ctx.guild.get_role(g["role_id"])
        channel = ctx.guild.get_channel(g["channel_id"])
        try:
            if role:
                await role.edit(name=new_name, reason="เปลี่ยนชื่อกิลด์")
            if channel:
                await channel.edit(name=f"{GUILD_ICON}︱{new_name}", reason="เปลี่ยนชื่อกิลด์")
        except (discord.Forbidden, discord.HTTPException):
            pass
        await ctx.send(f"✏️ เปลี่ยนชื่อกิลด์ **{old_name}** → **{new_name}** เรียบร้อย! "
                       f"(หักค่าธรรมเนียม `{GUILD_RENAME_COST:,}` ทอง — ยศ+ห้องเปลี่ยนตามแล้ว)")

    @guild.command(name="bank")
    async def bank(self, ctx):
        g = player_model.get_guild_of(ctx.author.id)
        if not g:
            return await ctx.send("❌ คุณไม่มีกิลด์!")
        await ctx.send(f"🏰 คลังกิลด์ **{g['icon']} {g['name']}**: 💰 `{g['treasury']:,}` ทอง")

    @guild.command(name="info")
    async def info(self, ctx):
        g = player_model.get_guild_of(ctx.author.id)
        if not g:
            return await ctx.send("❌ คุณไม่มีกิลด์! ดูวิธีสร้าง: `!guild`")
        members = player_model.get_guild_members(g["guild_id"])
        member_list = " ".join(f"<@{uid}>" for uid in members[:30])
        if len(members) > 30:
            member_list += f" …และอีก {len(members) - 30} คน"
        embed = discord.Embed(
            title=f"🏰 กิลด์ {g['icon']} {g['name']}", color=0xd4af37,
            description=(f"👑 หัวหน้า: <@{g['leader_id']}>\n"
                         f"👥 สมาชิก `{len(members)}` คน: {member_list}\n"
                         f"💰 คลังกิลด์: `{g['treasury']:,}` ทอง"))
        await ctx.send(embed=embed)


async def setup(bot):
    await bot.add_cog(GuildCog(bot))
