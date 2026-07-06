import discord
from collections import Counter

import bot.models.player_model as player_model
from bot import config_loader
from bot.cogs.player_commands import apply_item_effect, build_bag_embed, build_bank_embed
from bot.views.profile_embed import create_profile_embed


class ItemUseSelect(discord.ui.Select):
    """เลือกไอเทมจากกระเป๋าเพื่อใช้ — สร้างใหม่ทุกครั้งที่กดปุ่ม (ไม่ persistent เหมือนเมนูหลัก)
    ponytail: จำกัด 25 รายการแรกตามลิมิตของ discord.ui.Select
    """
    def __init__(self, inv_array):
        all_items = config_loader.get_all_items()
        counts = Counter(inv_array)
        options = []
        for item_id, count in list(counts.items())[:25]:
            name = all_items.get(item_id, {}).get("name", f"ไอเทม {item_id}")
            options.append(discord.SelectOption(label=f"{name} x{count}", value=item_id))
        super().__init__(placeholder="เลือกไอเทมที่จะใช้...", options=options)

    async def callback(self, interaction: discord.Interaction):
        ok, msg = apply_item_effect(interaction.user.id, self.values[0])
        await interaction.response.send_message(msg, ephemeral=True)


class ItemUseView(discord.ui.View):
    def __init__(self, inv_array):
        super().__init__(timeout=120)
        self.add_item(ItemUseSelect(inv_array))


class GameMenuView(discord.ui.View):
    """เมนูปุ่มสำหรับกระเป๋า/ธนาคาร/โปรไฟล์/ใช้ไอเทม — ระบบเดียวกับคำสั่ง !bag/!bank/!profile/!use
    เพียงแยกออกมาเป็นปุ่มให้กดสะดวกขึ้น ส่วนคำสั่งเดิมยังใช้งานได้ตามปกติ
    ต้อง persistent (timeout=None + custom_id) เพื่อให้ปุ่มใช้งานได้ตลอดแม้บอทรีสตาร์ท
    """
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="🎒 กระเป๋า", style=discord.ButtonStyle.primary, custom_id="game_menu:bag")
    async def bag_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        player = player_model.get_player(interaction.user.id)
        if not player:
            return await interaction.response.send_message("❌ ไม่พบข้อมูลตัวละครของคุณ! พิมพ์ `!play` ก่อนนะ", ephemeral=True)
        embed = build_bag_embed(interaction.user.display_name, interaction.user.display_avatar.url, player)
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @discord.ui.button(label="🏦 ธนาคาร", style=discord.ButtonStyle.success, custom_id="game_menu:bank")
    async def bank_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        player = player_model.get_player(interaction.user.id)
        if not player:
            return await interaction.response.send_message("❌ ไม่พบข้อมูลตัวละครของคุณ! พิมพ์ `!play` ก่อนนะ", ephemeral=True)
        await interaction.response.send_message(embed=build_bank_embed(player), ephemeral=True)

    @discord.ui.button(label="🪪 โปรไฟล์", style=discord.ButtonStyle.secondary, custom_id="game_menu:profile")
    async def profile_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        player = player_model.get_player(interaction.user.id)
        if not player:
            return await interaction.response.send_message("❌ ไม่พบข้อมูลตัวละครของคุณ! พิมพ์ `!play` ก่อนนะ", ephemeral=True)
        embed = create_profile_embed(interaction.user, player)
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @discord.ui.button(label="🧪 ใช้ไอเทม", style=discord.ButtonStyle.danger, custom_id="game_menu:use_item")
    async def use_item_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        player = player_model.get_player(interaction.user.id)
        if not player:
            return await interaction.response.send_message("❌ ไม่พบข้อมูลตัวละครของคุณ! พิมพ์ `!play` ก่อนนะ", ephemeral=True)
        inv_array = player_model.load_inventory(player.get("inventory", ""))
        if not inv_array:
            return await interaction.response.send_message("📦 กระเป๋าของคุณว่างเปล่า ไม่มีไอเทมให้ใช้!", ephemeral=True)
        await interaction.response.send_message("เลือกไอเทมที่จะใช้:", view=ItemUseView(inv_array), ephemeral=True)
