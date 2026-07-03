import discord
from discord.ext import commands
import random
import bot.models.player_model as player_model
from bot.utils import not_arrested, allowed_channel
from bot import config_loader

# ==========================================
# 🛠️ ฟังก์ชันซื้อแบบระบุตัว (จ่ายเต็ม)
# ==========================================
async def process_role_purchase(interaction: discord.Interaction, selected_value: str, role_list: list):
    role_info = next((r for r in role_list if r["value"] == selected_value), None)
    if not role_info:
        return await interaction.response.send_message("❌ ไม่พบข้อมูลยศนี้ในระบบ!", ephemeral=True)
    print(f"[DEBUG] process_role_purchase กำลังทำงาน") 
    role_id = role_info["role_id"]
    price = role_info["price"]
    role_name = role_info["label"]
    print(f"[DEBUG] ก่อนโลหด ole Object") 
    role_obj = interaction.guild.get_role(role_id)
    print(f"[DEBUG] Role Object Found: {role_obj}") # เพิ่มบรรทัดนี้
    if not role_obj:
        return await interaction.response.send_message("❌ แอดมินยังไม่ได้ตั้งค่า Role ID ให้ถูกต้อง!", ephemeral=True)

    if role_obj in interaction.user.roles:
        return await interaction.response.send_message(f"❌ คุณมียศ **{role_name}** อยู่แล้ว!", ephemeral=True)

    player = player_model.get_player(interaction.user.id)
    current_cash = player.get("cash", 0) if player else 0

    if current_cash < price:
        return await interaction.response.send_message(f"❌ เงินของคุณไม่พอ! ยศนี้ราคา `{price:,}` ทอง (คุณมี `{current_cash:,}` ทอง)", ephemeral=True)

    try:
        player_model.increment_player_field(interaction.user.id, "cash", -price)
        await interaction.user.add_roles(role_obj)
        await interaction.response.send_message(f"🎉 **สำเร็จ!** {interaction.user.mention} ได้สวมใส่ยศ **{role_name}** ด้วยการจ่ายเต็มจำนวน `{price:,}` ทอง!")
    except discord.Forbidden:
        player_model.increment_player_field(interaction.user.id, "cash", price)
        await interaction.response.send_message("❌ บอทไม่มีสิทธิ์มอบยศนี้ให้คุณได้ (กรุณาให้แอดมินเลื่อนยศของบอท)", ephemeral=True)

# ==========================================
# 🎲 ฟังก์ชันสุ่มยศ (กาชาปอง) - เวอร์ชันอัปเดตความแม่นยำ
# ==========================================
async def process_role_gacha(interaction: discord.Interaction, role_list: list, faction_name: str):
    GACHA_PRICE = config_loader.get_gacha_price()

    # ดึงข้อมูลผู้เล่นจากฐานข้อมูล
    player = player_model.get_player(interaction.user.id)
    current_cash = player.get("cash", 0) if player else 0

    if current_cash < GACHA_PRICE:
        return await interaction.response.send_message(f"❌ เงินของคุณไม่พอสุ่มกาชา! ต้องใช้ `{GACHA_PRICE:,}` ทอง (คุณมี `{current_cash:,}` ทอง)", ephemeral=True)

    # กรองเฉพาะยศที่มีราคา 20,000,000 มาใส่ตู้กาชา
    gacha_pool = [r for r in role_list if r["price"] == config_loader.get_gacha_pool_price()]
    
    # หักเงินทันที
    player_model.increment_player_field(interaction.user.id, "cash", -GACHA_PRICE)
    
    # สุ่มยศ
    won_role = random.choice(gacha_pool)
    role_obj = interaction.guild.get_role(won_role["role_id"])
    
    if not role_obj:
        return await interaction.response.send_message("❌ ระบบขัดข้อง: ไม่พบข้อมูลยศที่สุ่มได้ในดิสคอร์ด", ephemeral=True)

    # 🛠️ ใช้ fetch_member เพื่อให้ได้สถานะ Role ที่อัปเดตที่สุดจาก Server
    member = await interaction.guild.fetch_member(interaction.user.id)

    if role_obj in member.roles:
        # กรณีสุ่มได้ของซ้ำ
        await interaction.response.send_message(
            f"🎲 {interaction.user.mention} จ่าย `{GACHA_PRICE:,}` ทอง หมุนกาชา {faction_name}...\n"
            f"💀 **เกลือ!!** คุณสุ่มได้ยศ **{won_role['label']}** ซึ่งคุณมีอยู่แล้ว!"
        )
    else:
        # กรณีได้ของใหม่
        try:
            await interaction.user.add_roles(role_obj)
            await interaction.response.send_message(
                f"🎲 {interaction.user.mention} จ่าย `{GACHA_PRICE:,}` ทอง หมุนกาชา {faction_name}...\n"
                f"🎉 **แจ็คพอตแตก!!** คุณได้รับยศ **{won_role['label']}** ยินดีด้วย!!"
            )
        except discord.Forbidden:
            # กรณีบอทไม่มีสิทธิ์แจกยศ
            player_model.increment_player_field(interaction.user.id, "cash", GACHA_PRICE)
            await interaction.response.send_message("❌ บอทไม่มีสิทธิ์มอบยศนี้ให้คุณได้ (คืนเงินแล้ว)", ephemeral=True)
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
    print("[LOG] โหลดระบบ Role Shop + Gacha สำเร็จ!")