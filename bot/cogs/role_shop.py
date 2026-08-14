import discord
from discord.ext import commands
import random
import bot.models.player_model as player_model
from bot.utils import not_arrested, allowed_channel, main_server_gate
from bot import config_loader, role_shop_core

# ==========================================
# 🛠️ ฟังก์ชันซื้อแบบระบุตัว (จ่ายเต็ม)
# ==========================================
async def process_role_purchase(interaction: discord.Interaction, selected_value: str, role_list: list):
    """ซื้อยศเจาะจง — ตรวจเงิน/หักเงินอยู่ใน role_shop_core (ใช้ร่วมกับเว็บ)"""
    faction = "dark" if role_list is config_loader.get_trade_roles("dark") else _faction_of(role_list)
    role_obj = None
    role_info = role_shop_core.find_role(faction, selected_value)
    if role_info:
        role_obj = interaction.guild.get_role(role_info["role_id"])
    if not role_obj:
        return await interaction.response.send_message(
            "❌ แอดมินยังไม่ได้ตั้งค่า Role ID ให้ถูกต้อง!", ephemeral=True)
    if role_obj in interaction.user.roles:
        return await interaction.response.send_message(
            f"❌ คุณมียศ **{role_info['label']}** อยู่แล้ว!", ephemeral=True)

    ok, data = role_shop_core.prepare_buy(interaction.user.id, faction, selected_value)
    if not ok:
        return await interaction.response.send_message(data["error"], ephemeral=True)

    try:
        await interaction.user.add_roles(role_obj)
        await interaction.response.send_message(
            f"🎉 **สำเร็จ!** {interaction.user.mention} ได้สวมใส่ยศ **{data['label']}** "
            f"ด้วยการจ่ายเต็มจำนวน `{data['price']:,}` ทอง!")
    except discord.Forbidden:
        role_shop_core.refund(interaction.user.id, data["price"])
        await interaction.response.send_message(
            "❌ บอทไม่มีสิทธิ์มอบยศนี้ให้คุณได้ (กรุณาให้แอดมินเลื่อนยศของบอท — คืนเงินแล้ว)",
            ephemeral=True)


def _faction_of(role_list):
    """เดาฝ่ายจากลิสต์ที่ส่งเข้ามา (ของเดิมส่งลิสต์มาไม่ได้ส่งชื่อฝ่าย)"""
    for f in ("dark", "light"):
        known = {r.get("value") for r in config_loader.get_trade_roles(f) or []}
        if known and {r.get("value") for r in role_list} <= known:
            return f
    return "dark"


# ==========================================
# 🎲 กาชาสุ่มยศ — ตรรกะสุ่ม/หักเงินอยู่ใน core ใช้ร่วมกับเว็บ
# ==========================================
async def process_role_gacha(interaction: discord.Interaction, role_list: list, faction_name: str):
    faction = _faction_of(role_list)
    ok, data = role_shop_core.prepare_gacha(interaction.user.id, faction)
    if not ok:
        return await interaction.response.send_message(data["error"], ephemeral=True)

    role_obj = interaction.guild.get_role(data["role_id"])
    if not role_obj:
        role_shop_core.refund(interaction.user.id, data["price"])
        return await interaction.response.send_message(
            "❌ ระบบขัดข้อง: ไม่พบข้อมูลยศที่สุ่มได้ในดิสคอร์ด (คืนเงินแล้ว)", ephemeral=True)

    head = (f"🎲 {interaction.user.mention} จ่าย `{data['price']:,}` ทอง "
            f"หมุนกาชา {faction_name}...\n")
    # ใช้ fetch_member เพื่อให้ได้สถานะยศที่อัปเดตที่สุดจากเซิร์ฟเวอร์
    member = await interaction.guild.fetch_member(interaction.user.id)
    if role_obj in member.roles:
        return await interaction.response.send_message(
            head + f"💀 **เกลือ!!** คุณสุ่มได้ยศ **{data['label']}** ซึ่งคุณมีอยู่แล้ว!")
    try:
        await interaction.user.add_roles(role_obj)
        await interaction.response.send_message(
            head + f"🎉 **แจ็คพอตแตก!!** คุณได้รับยศ **{data['label']}** ยินดีด้วย!!")
    except discord.Forbidden:
        role_shop_core.refund(interaction.user.id, data["price"])
        await interaction.response.send_message(
            "❌ บอทไม่มีสิทธิ์มอบยศนี้ให้คุณได้ (คืนเงินแล้ว)", ephemeral=True)


# ==========================================
# 🛒 UI (Dropdown + ปุ่ม Gacha)
# ==========================================
class DarkRoleSelect(discord.ui.Select):
    print(f"[DEBUG] DarkRoleSelect ทำงานแล้ง")
    def __init__(self):
        roles = config_loader.get_trade_roles("dark")
        options = [discord.SelectOption(label=r["label"], value=r["value"], description=f"ราคา: {r['price']:,} ทอง", emoji=r.get("emoji")) for r in roles]
        super().__init__(placeholder="🩸 เลือกซื้อพลังแห่งความมืด (จ่ายเต็ม)...", min_values=1, max_values=1, options=options)

    async def callback(self, interaction: discord.Interaction):
        await process_role_purchase(interaction, self.values[0], config_loader.get_trade_roles("dark"))

class LightRoleSelect(discord.ui.Select):
    def __init__(self):
        roles = config_loader.get_trade_roles("light")
        options = [discord.SelectOption(label=r["label"], value=r["value"], description=f"ราคา: {r['price']:,} ทอง", emoji=r.get("emoji")) for r in roles]
        super().__init__(placeholder="🕊️ เลือกซื้อพลังแห่งแสงสว่าง (จ่ายเต็ม)...", min_values=1, max_values=1, options=options)

    async def callback(self, interaction: discord.Interaction):
        await process_role_purchase(interaction, self.values[0], config_loader.get_trade_roles("light"))

class DarkShopView(discord.ui.View):
    print(f"[DEBUG] DarkShopView ทำงานแล้ง")
    def __init__(self, user):
        super().__init__(timeout=120)
        self.user = user
        self.add_item(DarkRoleSelect())
    print(f"[DEBUG] DarkShopView กำลีงทำงาน")
    @discord.ui.button(label="🎲 สุ่มยศ 7 บาป (10,000,000 ทอง)", style=discord.ButtonStyle.danger, emoji="🎰", row=1)
    async def btn_gacha_dark(self, interaction: discord.Interaction, button: discord.ui.Button):
        await process_role_gacha(interaction, config_loader.get_trade_roles("dark"), "ฝ่ายความมืด")

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.user.id:
            await interaction.response.send_message("❌ กรุณาพิมพ์ !darkshop เพื่อเปิดร้านของตัวเอง!", ephemeral=True)
            return False
        return True

class LightShopView(discord.ui.View):
    def __init__(self, user):
        super().__init__(timeout=120)
        self.user = user
        self.add_item(LightRoleSelect())

    @discord.ui.button(label="🎲 สุ่มยศเทวทูต (10,000,000 ทอง)", style=discord.ButtonStyle.primary, emoji="🎰", row=1)
    async def btn_gacha_light(self, interaction: discord.Interaction, button: discord.ui.Button):
        await process_role_gacha(interaction, config_loader.get_trade_roles("light"), "ฝ่ายแสงสว่าง")

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.user.id:
            await interaction.response.send_message("❌ กรุณาพิมพ์ !lightshop เพื่อเปิดร้านของตัวเอง!", ephemeral=True)
            return False
        return True

# ==========================================
# 🛒 ตัวโหลดคำสั่ง (Cog)
# ==========================================
class RoleShop(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @allowed_channel("role_shop") 
    @commands.command(name="darkshop")
    @not_arrested()
    async def open_dark_shop(self, ctx):
        try:
            print("[DEBUG] กำลังสร้าง Embed และ View...")
            embed = discord.Embed(
                title="🩸 ร้านค้ายศฝ่ายความมืด (Dark Faction)", 
                description="...", 
                color=discord.Color.dark_red()
            )
            view = DarkShopView(ctx.author)
            await ctx.send(embed=embed, view=view)
            print("[DEBUG] ส่งข้อความสำเร็จ")
        except Exception as e:
            print(f"[ERROR] พังตรงนี้: {e}")

    @allowed_channel("role_shop") 
    @commands.command(name="lightshop")
    @not_arrested()
    async def open_light_shop(self, ctx):
        embed = discord.Embed(
            title="🕊️ ร้านค้ายศฝ่ายแสงสว่าง (Light Faction)", 
            description="จงใช้ความศรัทธาซื้อพลังแห่งสวรรค์...\n\nคุณสามารถ **เลือกซื้อจ่ายเต็ม** จากเมนูด้านล่าง\nหรือกดปุ่ม 🎲 **สุ่มกาชา 10M** เพื่อลุ้นรับยศระดับ 20M แบบสุ่ม (ระวังเกลือได้ซ้ำ!)", 
            color=discord.Color.gold()
        )
        await ctx.send(embed=embed, view=LightShopView(ctx.author))

async def setup(bot):
    await bot.add_cog(RoleShop(bot))

    async def cog_check(self, ctx):
        """P8: ฟีเจอร์นี้เล่นได้เฉพาะเซิร์ฟหลัก (เซิร์ฟรองเล่นได้แค่ผจญภัย)"""
        return await main_server_gate(ctx)
    print("[LOG] โหลดระบบ Role Shop + Gacha สำเร็จ!")