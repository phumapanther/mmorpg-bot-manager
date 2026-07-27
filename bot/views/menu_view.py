import discord
from collections import Counter

import bot.models.player_model as player_model
from bot import config_loader
from bot.cogs.player_commands import (apply_item_effect, bank_action, build_bag_embed,
                                      build_bank_embed, build_bestiary_embed, build_codex_embed)
from bot.views.profile_embed import create_profile_embed

# หัวข้อคู่มือในปุ่ม 📖 — ค่า value ตรงกับ topic ของ !codex เป๊ะ
CODEX_TOPICS = [
    ("📘 วิธีเล่น (เริ่มต้นที่นี่)", "วิธีเล่น"),
    ("⌨️ คำสั่งทั้งหมด", "คำสั่ง"),
    ("🧬 ธาตุทั้ง 7", "ธาตุ"),
    ("🩸 สถานะติดตัว + ของแก้", "สถานะ"),
    ("🎒 ไอเทมทุกชิ้น", "ไอเทม"),
    ("🗺️ ทวีปทั้ง 9", "ทวีป"),
]


class CodexSelect(discord.ui.Select):
    def __init__(self):
        options = [discord.SelectOption(label=label, value=value) for label, value in CODEX_TOPICS]
        super().__init__(placeholder="เลือกหัวข้อคู่มือที่อยากอ่าน...", options=options)

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.send_message(embed=build_codex_embed(self.values[0]), ephemeral=True)


class CodexView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=120)
        self.add_item(CodexSelect())


class BankAmountModal(discord.ui.Modal):
    """ฟอร์มกรอกธุรกรรมธนาคาร — โอนมีช่องผู้รับเพิ่ม (รับ @เมนชั่น หรือไอดีตัวเลข)"""
    def __init__(self, action):
        titles = {"deposit": "💰 ฝากเงินเข้าธนาคาร", "withdraw": "💸 ถอนเงินจากธนาคาร", "transfer": "💸 โอนเงินให้ผู้เล่นอื่น"}
        super().__init__(title=titles[action])
        self.action = action
        if action == "transfer":
            self.target = discord.ui.TextInput(label="ผู้รับ (@เมนชั่น หรือไอดีตัวเลข)", placeholder="เช่น @Panther หรือ 123456789012345678")
            self.add_item(self.target)
        self.amount = discord.ui.TextInput(label="จำนวนเงิน (ตัวเลข)", placeholder="เช่น 5000")
        self.add_item(self.amount)

    async def on_submit(self, interaction: discord.Interaction):
        try:
            amount = int(str(self.amount.value).replace(",", "").strip())
        except ValueError:
            return await interaction.response.send_message("❌ จำนวนเงินต้องเป็นตัวเลขล้วน!", ephemeral=True)
        target_id = None
        if self.action == "transfer":
            digits = "".join(ch for ch in str(self.target.value) if ch.isdigit())
            if not digits:
                return await interaction.response.send_message("❌ ระบุผู้รับเป็น @เมนชั่น หรือไอดีตัวเลขเท่านั้น!", ephemeral=True)
            target_id = int(digits)
        _, msg = bank_action(interaction.user.id, self.action, amount, target_id=target_id)
        # แนบยอดล่าสุดต่อท้ายให้เห็นทันทีโดยไม่ต้องกดธนาคารซ้ำ
        player = player_model.get_player(interaction.user.id)
        if player:
            msg += f"\n💵 เงินสด `{player.get('cash', 0):,}` | 🏦 ธนาคาร `{player.get('bank', 0):,}`"
        await interaction.response.send_message(msg, ephemeral=True)


class BankActionView(discord.ui.View):
    """ปุ่มธุรกรรมใต้ยอดธนาคาร — ส่งแบบ ephemeral เห็นคนเดียว จึงไม่ต้อง persistent"""
    def __init__(self):
        super().__init__(timeout=120)

    @discord.ui.button(label="💰 ฝาก", style=discord.ButtonStyle.success)
    async def deposit_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(BankAmountModal("deposit"))

    @discord.ui.button(label="💸 ถอน", style=discord.ButtonStyle.primary)
    async def withdraw_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(BankAmountModal("withdraw"))

    @discord.ui.button(label="🤝 โอน", style=discord.ButtonStyle.secondary)
    async def transfer_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(BankAmountModal("transfer"))


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
        await interaction.response.send_message(
            embed=build_bank_embed(player), view=BankActionView(), ephemeral=True)

    @discord.ui.button(label="🪪 โปรไฟล์", style=discord.ButtonStyle.secondary, custom_id="game_menu:profile")
    async def profile_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        player = player_model.get_player(interaction.user.id)
        if not player:
            return await interaction.response.send_message("❌ ไม่พบข้อมูลตัวละครของคุณ! พิมพ์ `!play` ก่อนนะ", ephemeral=True)
        embed = create_profile_embed(interaction.user, player)
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @discord.ui.button(label="📕 สมุดมอน", style=discord.ButtonStyle.secondary, custom_id="game_menu:bestiary")
    async def bestiary_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = build_bestiary_embed(
            interaction.user.id, interaction.user.display_name, interaction.user.display_avatar.url)
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @discord.ui.button(label="📖 คู่มือ", style=discord.ButtonStyle.secondary, custom_id="game_menu:codex")
    async def codex_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message(
            "📖 **คู่มือนักผจญภัย** — เลือกหัวข้อ:", view=CodexView(), ephemeral=True)

    @discord.ui.button(label="🧪 ใช้ไอเทม", style=discord.ButtonStyle.danger, custom_id="game_menu:use_item")
    async def use_item_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        player = player_model.get_player(interaction.user.id)
        if not player:
            return await interaction.response.send_message("❌ ไม่พบข้อมูลตัวละครของคุณ! พิมพ์ `!play` ก่อนนะ", ephemeral=True)
        inv_array = player_model.load_inventory(player.get("inventory", ""))
        if not inv_array:
            return await interaction.response.send_message("📦 กระเป๋าของคุณว่างเปล่า ไม่มีไอเทมให้ใช้!", ephemeral=True)
        await interaction.response.send_message("เลือกไอเทมที่จะใช้:", view=ItemUseView(inv_array), ephemeral=True)
