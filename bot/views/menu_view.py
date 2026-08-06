import discord
from collections import Counter

import bot.models.player_model as player_model
from bot import config_loader, gold_bars
from bot.cogs.player_commands import (apply_item_effect, bank_action, build_bag_embed, item_use_file,
                                      build_bank_embed, build_bestiary_embed, build_codex_embed,
                                      build_top_embed, craft_for, craftable_now, drop_item_for,
                                      sell_all_junk)
from bot.views.profile_embed import create_profile_embed

# ค่าแทน "ไม่เลือกอะไร" ใน dropdown — ห้ามใช้สตริงว่าง Discord ปฏิเสธทั้ง dropdown
NONE_CHOICE = "__none__"

# หัวข้อคู่มือในปุ่ม 📖 — ค่า value ตรงกับ topic ของ !codex เป๊ะ
CODEX_TOPICS = [
    ("📘 วิธีเล่น (เริ่มต้นที่นี่)", "วิธีเล่น"),
    ("⌨️ คำสั่งทั้งหมด", "คำสั่ง"),
    ("🧬 ธาตุทั้ง 7", "ธาตุ"),
    ("🩸 สถานะติดตัว + ของแก้", "สถานะ"),
    ("🎒 ไอเทมทุกชิ้น", "ไอเทม"),
    ("🗺️ ทวีปทั้ง 9", "ทวีป"),
    ("🏰 กิลด์ & กิลด์วอร์", "กิลด์"),
    ("🎁 รางวัลรายวัน · ซีซั่นพาส · อันดับ", "รางวัล"),
    ("🏅 ความสำเร็จ & 🐾 สัตว์เลี้ยง", "สะสม"),
    ("🏪 ตลาดผู้เล่น & 💍 คู่หู", "สังคม"),
    ("🔨 ตารางคราฟของ", "คราฟ"),
    ("🏺 อาร์ติแฟกต์ & ช่องสวมใส่", "อาร์ติแฟกต์"),
]


class CodexSelect(discord.ui.Select):
    def __init__(self):
        options = [discord.SelectOption(label=label, value=value) for label, value in CODEX_TOPICS]
        super().__init__(placeholder="เลือกหัวข้อคู่มือที่อยากอ่าน...", options=options)

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.send_message(embed=build_codex_embed(self.values[0]), ephemeral=True)


class CodexView(discord.ui.View):
    def __init__(self, show_portal=False):
        super().__init__(timeout=120)
        self.add_item(CodexSelect())
        # 🌏 P8: ปุ่มข้ามมิติไปเซิร์ฟหลัก — โผล่เฉพาะตอนเล่นในเซิร์ฟรอง (กดแล้วเปิดหน้าเชิญทันที)
        invite = config_loader.get_main_server_invite()
        if show_portal and invite:
            self.add_item(discord.ui.Button(
                label="🌏 ไปต่างโลก (เซิร์ฟหลัก)", style=discord.ButtonStyle.link, url=invite))


class ProfilePageView(discord.ui.View):
    """ปุ่มสลับหน้าโปรไฟล์ (B2) — สถานะ / อุปกรณ์ / ความคืบหน้า"""
    PAGES = [("👤 สถานะ", "status"), ("🛡️ อุปกรณ์", "equip"), ("📊 ความคืบหน้า", "progress")]

    def __init__(self, member, current="status"):
        super().__init__(timeout=180)
        self.member = member
        for label, key in self.PAGES:
            btn = discord.ui.Button(
                label=label,
                style=discord.ButtonStyle.primary if key == current else discord.ButtonStyle.secondary,
                disabled=(key == current))
            btn.callback = self._make_cb(key)
            self.add_item(btn)

    def _make_cb(self, page):
        async def cb(interaction: discord.Interaction):
            player = player_model.get_player(self.member.id)
            if not player:
                return await interaction.response.send_message("❌ ไม่พบข้อมูลตัวละคร!", ephemeral=True)
            await interaction.response.edit_message(
                embed=create_profile_embed(self.member, player, page=page),
                view=ProfilePageView(self.member, current=page))
        return cb


class CraftSelect(discord.ui.Select):
    """เลือกสูตรที่คราฟได้ตอนนี้ (B1) — ไม่ต้องจำรหัสไอเทม"""
    def __init__(self, options_data):
        options = [discord.SelectOption(label=name[:100], value=str(iid), description=mats[:100])
                   for iid, name, mats in options_data[:25]]
        super().__init__(placeholder="เลือกของที่จะคราฟ...", options=options)

    async def callback(self, interaction: discord.Interaction):
        _ok, msg = craft_for(interaction.user.id, self.values[0])
        left = craftable_now(interaction.user.id)
        view = CraftView(left) if left else None
        await interaction.response.edit_message(
            content=msg + ("" if left else "\n\n🎒 ตอนนี้ไม่มีสูตรไหนที่วัตถุดิบครบแล้ว"), view=view)


class CraftView(discord.ui.View):
    def __init__(self, options_data):
        super().__init__(timeout=120)
        self.add_item(CraftSelect(options_data))


class DropSelect(discord.ui.Select):
    """เลือกของที่จะทิ้ง (B1) — ทิ้งได้โดยไม่ต้องจำรหัสไอเทม"""
    def __init__(self, inv_array):
        all_items = config_loader.get_all_items()
        counts = Counter(inv_array)
        options = [discord.SelectOption(label=f"{all_items.get(i, {}).get('name', i)} ×{n}"[:100], value=str(i))
                   for i, n in list(counts.items())[:25]]
        super().__init__(placeholder="เลือกของที่จะทิ้ง (ทิ้งทีละ 1 ชิ้น)...", options=options)

    async def callback(self, interaction: discord.Interaction):
        _ok, msg = drop_item_for(interaction.user.id, self.values[0], 1)
        player = player_model.get_player(interaction.user.id)
        inv = player_model.load_inventory(player.get("inventory", ""))
        view = DropView(inv) if inv else None
        await interaction.response.edit_message(content=msg, view=view)


class DropView(discord.ui.View):
    def __init__(self, inv_array):
        super().__init__(timeout=120)
        self.add_item(DropSelect(inv_array))


class TopBoardView(discord.ui.View):
    """ปุ่มสลับหมวดอันดับ (O6) — รวม !rich/!toplvl/!toptext/!toptime ไว้ที่เดียว"""
    KINDS = [("🗓️ สัปดาห์นี้", "weekly"), ("💰 เศรษฐี", "rich"), ("⭐ เลเวล", "level"),
             ("💬 นักแชท", "text"), ("🎙️ ออนไลน์", "time")]

    def __init__(self, viewer_id, current="rich"):
        super().__init__(timeout=180)
        self.viewer_id = viewer_id
        for label, key in self.KINDS:
            btn = discord.ui.Button(
                label=label,
                style=discord.ButtonStyle.primary if key == current else discord.ButtonStyle.secondary,
                disabled=(key == current))
            btn.callback = self._cb(key)
            self.add_item(btn)

    def _cb(self, kind):
        async def cb(interaction: discord.Interaction):
            await interaction.response.edit_message(
                embed=build_top_embed(kind, interaction.user.id),
                view=TopBoardView(self.viewer_id, current=kind))
        return cb


class ProposalView(discord.ui.View):
    """คำขอเป็นคู่หู (C7) — เฉพาะคนที่ถูกชวนกดได้ ภายใน 2 นาที"""
    def __init__(self, proposer_id, target_id):
        super().__init__(timeout=120)
        self.proposer_id = proposer_id
        self.target_id = target_id

    async def interaction_check(self, interaction):
        if interaction.user.id != self.target_id:
            await interaction.response.send_message("❌ คำชวนนี้ไม่ใช่ของคุณ!", ephemeral=True)
            return False
        return True

    @discord.ui.button(label="💍 ตกลงเป็นคู่หู", style=discord.ButtonStyle.success)
    async def accept(self, interaction: discord.Interaction, button: discord.ui.Button):
        from bot import partner
        from bot.event_images import event_image
        _ok, msg = partner.marry(self.proposer_id, self.target_id)
        ring_f = event_image("item_wedding_ring") if _ok else None
        await interaction.response.edit_message(content=msg, view=None,
                                                **({"attachments": [ring_f]} if ring_f else {}))

    @discord.ui.button(label="💔 ขอบคุณ แต่ไม่", style=discord.ButtonStyle.secondary)
    async def decline(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.edit_message(
            content=f"💔 <@{self.target_id}> ปฏิเสธคำชวนของ <@{self.proposer_id}>", view=None)


class MarketBuySelect(discord.ui.Select):
    """เลือกซื้อของจากตลาด (C5) — ของตัวเองไม่ขึ้นในลิสต์ให้กดพลาด"""
    def __init__(self, user_id):
        from bot import market
        rows = [r for r in market.open_listings() if r[1] != user_id][:25]
        options = [discord.SelectOption(
            label=f"#{lid} {market._item_name(item)}"[:100],
            value=str(lid),
            description=f"{price:,} ทอง") for lid, _seller, item, price in rows]
        super().__init__(placeholder="เลือกของที่จะซื้อ...", options=options or
                         [discord.SelectOption(label="ยังไม่มีของขาย", value="none")],
                         disabled=not options)

    async def callback(self, interaction: discord.Interaction):
        from bot import market
        _ok, msg = market.buy_listing(interaction.user.id, int(self.values[0]))
        await interaction.response.edit_message(
            content=msg, embed=market.build_market_embed(interaction.user.id),
            view=MarketView(interaction.user.id))


class MarketView(discord.ui.View):
    def __init__(self, user_id):
        super().__init__(timeout=180)
        self.add_item(MarketBuySelect(user_id))


class PetSelect(discord.ui.Select):
    """เลือกสัตว์เลี้ยงที่จะติดตัว (C4) — ponytail: 24 ตัวแรก ลิมิต Select คือ 25"""
    def __init__(self, user_id):
        from bot import pets
        have = pets.owned(user_id)
        # ⚠️ value ห้ามเป็นสตริงว่าง — Discord ตอบ 400 "Must be between 1 and 100 in length"
        # แล้ว dropdown ทั้งอันส่งไม่ออก (ตรวจฝั่ง Discord ไม่ใช่ตอนสร้างใน Python)
        options = [discord.SelectOption(label="— ไม่ติดตัวไหน —", value=NONE_CHOICE)]
        options += [discord.SelectOption(label=p["name"], value=p["key"],
                                         description=f"เต๋า +{int(p.get('dice', 0))}")
                    for p in pets.all_pets() if p["key"] in have][:24]
        super().__init__(placeholder="เลือกสัตว์เลี้ยงที่จะออกเดินทางด้วย...", options=options)

    async def callback(self, interaction: discord.Interaction):
        from bot import pets
        chosen = "" if self.values[0] == NONE_CHOICE else self.values[0]
        _ok, msg = pets.set_active(interaction.user.id, chosen)
        await interaction.response.edit_message(
            content=msg,
            embed=pets.build_pet_embed(interaction.user.id, interaction.user.display_name),
            view=PetView(interaction.user.id))


class PetView(discord.ui.View):
    def __init__(self, user_id):
        super().__init__(timeout=180)
        from bot import pets
        if pets.owned(user_id):       # ยังไม่มีสักตัว = ไม่ต้องมี dropdown ว่าง
            self.add_item(PetSelect(user_id))


class SeasonView(discord.ui.View):
    """ปุ่มรับรางวัล/เปิดพรีเมียมของซีซั่นพาส (C2)"""
    def __init__(self, user_id):
        super().__init__(timeout=180)
        self.user_id = user_id
        from bot import season
        if not season.is_premium(user_id):
            btn = discord.ui.Button(label="⭐ เปิดสายพรีเมียม", style=discord.ButtonStyle.primary)
            btn.callback = self._buy
            self.add_item(btn)

    async def interaction_check(self, interaction):
        return interaction.user.id == self.user_id

    async def show_season(self, interaction, msg):
        """วาดหน้าซีซั่นใหม่พร้อมข้อความผลลัพธ์

        ⚠️ ห้ามตั้งชื่อเมธอดขึ้นต้นด้วย _ ที่ซ้ำกับของ discord.py (เคยชื่อ _refresh
        แล้วไปทับเมธอดภายในของ View ทำให้บอททั้งตัวล่มตอนมีคนแก้ข้อความ)
        """
        from bot import season
        await interaction.response.edit_message(
            content=msg,
            embed=season.build_season_embed(interaction.user.id, interaction.user.display_name),
            view=SeasonView(interaction.user.id))

    async def _buy(self, interaction: discord.Interaction):
        from bot import season
        _ok, msg = season.buy_premium(interaction.user.id)
        await self.show_season(interaction, msg)

    @discord.ui.button(label="🎁 รับรางวัลที่ปลดแล้ว", style=discord.ButtonStyle.success)
    async def claim(self, interaction: discord.Interaction, button: discord.ui.Button):
        from bot import season
        await self.show_season(interaction, season.claim_all(interaction.user.id))


class ElementBookSelect(discord.ui.Select):
    """เลือกทวีปเพื่อดูตารางธาตุ 5 แรงค์ × 7 ธาตุ ของทวีปนั้น"""
    def __init__(self):
        from bot import game_modifiers
        super().__init__(placeholder="เลือกทวีปเพื่อดูตารางธาตุ...", options=[
            discord.SelectOption(label=c["label"][:100], value=key)
            for key, c in list(game_modifiers.CONTINENTS.items())[:25]])

    async def callback(self, interaction: discord.Interaction):
        from bot.cogs.player_commands import build_element_book_embed
        await interaction.response.edit_message(
            embed=build_element_book_embed(interaction.user.id, interaction.user.display_name,
                                           self.values[0]),
            view=ElementBookView())


class ElementBookView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=180)
        self.add_item(ElementBookSelect())

    @discord.ui.button(label="🗺️ ดูสรุปทุกทวีป", style=discord.ButtonStyle.secondary, row=1)
    async def overview(self, interaction: discord.Interaction, button: discord.ui.Button):
        from bot.cogs.player_commands import build_element_book_embed
        await interaction.response.edit_message(
            embed=build_element_book_embed(interaction.user.id, interaction.user.display_name),
            view=ElementBookView())


class BestiaryView(discord.ui.View):
    """ปุ่มสลับระหว่างสมุดเดิมกับสมุดธาตุ"""
    def __init__(self):
        super().__init__(timeout=180)

    @discord.ui.button(label="🧬 สมุดธาตุ", style=discord.ButtonStyle.primary)
    async def element_book(self, interaction: discord.Interaction, button: discord.ui.Button):
        from bot.cogs.player_commands import build_element_book_embed
        await interaction.response.send_message(
            embed=build_element_book_embed(interaction.user.id, interaction.user.display_name),
            view=ElementBookView(), ephemeral=True)


class TitleSelect(discord.ui.Select):
    """เลือกตำแหน่งอวดจากที่ปลดล็อกแล้ว (C8) — ponytail: 24 อันแรกพอ ลิมิต Select คือ 25"""
    def __init__(self, user_id):
        from bot import achievements
        options = [discord.SelectOption(label="— ถอดตำแหน่งออก —", value=NONE_CHOICE)]
        options += [discord.SelectOption(label=t, value=t)
                    for t in achievements.unlocked_titles(user_id)[:24]]
        super().__init__(placeholder="เลือกตำแหน่งที่จะติดหน้าโปรไฟล์...", options=options)

    async def callback(self, interaction: discord.Interaction):
        from bot import achievements
        chosen = "" if self.values[0] == NONE_CHOICE else self.values[0]
        _ok, msg = achievements.set_title(interaction.user.id, chosen)
        await interaction.response.edit_message(
            content=msg,
            embed=achievements.build_achievement_embed(interaction.user.id, interaction.user.display_name),
            view=AchievementView(interaction.user.id))


class AchievementView(discord.ui.View):
    def __init__(self, user_id):
        super().__init__(timeout=180)
        from bot import achievements
        if achievements.unlocked_titles(user_id):     # ยังไม่ปลดตำแหน่งไหนเลย = ไม่ต้องมี dropdown ว่าง
            self.add_item(TitleSelect(user_id))


class DailyView(discord.ui.View):
    """ปุ่มรับรางวัลภารกิจรายวัน (C1)"""
    def __init__(self, user_id):
        super().__init__(timeout=180)
        self.user_id = user_id

    async def interaction_check(self, interaction):
        return interaction.user.id == self.user_id

    @discord.ui.button(label="🎁 รับรางวัลที่ทำครบแล้ว", style=discord.ButtonStyle.success)
    async def claim(self, interaction: discord.Interaction, button: discord.ui.Button):
        from bot import daily
        msg = daily.claim_all(interaction.user.id)
        embed = daily.build_daily_embed(interaction.user.id, interaction.user.display_name)
        await interaction.response.edit_message(content=msg, embed=embed, view=self)


class BagActionView(discord.ui.View):
    """ปุ่มลัดในกระเป๋า (B5) — ขายวัสดุรวดเดียว ไม่ต้องขายทีละชิ้นที่ร้าน"""
    def __init__(self, user_id):
        super().__init__(timeout=120)
        self.user_id = user_id

    async def interaction_check(self, interaction):
        return interaction.user.id == self.user_id

    @discord.ui.button(label="🔨 คราฟของ", style=discord.ButtonStyle.primary)
    async def craft_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        options = craftable_now(interaction.user.id)
        if not options:
            return await interaction.response.send_message(
                "🔨 ยังไม่มีสูตรไหนที่วัตถุดิบครบเลย — ดูสูตรทั้งหมดที่ `!recipes`", ephemeral=True)
        await interaction.response.send_message(
            f"🔨 **คราฟได้ตอนนี้ {len(options)} สูตร** — เลือกจากรายการ:",
            view=CraftView(options), ephemeral=True)

    @discord.ui.button(label="🗑️ ทิ้งของ", style=discord.ButtonStyle.danger)
    async def drop_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        player = player_model.get_player(interaction.user.id)
        inv = player_model.load_inventory((player or {}).get("inventory", ""))
        if not inv:
            return await interaction.response.send_message("🎒 กระเป๋าว่างเปล่า ไม่มีอะไรให้ทิ้ง!", ephemeral=True)
        await interaction.response.send_message("🗑️ เลือกของที่จะทิ้ง:", view=DropView(inv), ephemeral=True)

    @discord.ui.button(label="🧱 ขายวัสดุทั้งหมด", style=discord.ButtonStyle.success)
    async def sell_junk(self, interaction: discord.Interaction, button: discord.ui.Button):
        _sold, _gold, msg = sell_all_junk(interaction.user.id)
        player = player_model.get_player(interaction.user.id)
        embed = build_bag_embed(interaction.user.display_name, interaction.user.display_avatar.url, player)
        await interaction.response.edit_message(content=msg, embed=embed, view=self)


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

    @discord.ui.button(label="🧈 ทองคำแท่ง", style=discord.ButtonStyle.secondary)
    async def gold_bar_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """แลกเหรียญ↔ทองคำแท่ง (spec 2026-08-06) — ตัด/เข้าเงินธนาคาร ค่าธรรมเนียม flat"""
        pct = gold_bars.fee_pct()
        lines = [f"🧈 **แลกทองคำแท่งที่ธนาคาร** (ค่าธรรมเนียม {pct}% ทั้งซื้อและขายคืน)",
                 "ทองคำแท่งเป็นไอเทมในกระเป๋า ขายที่ร้านหมู่บ้านก็ได้แต่โดนหักแพงกว่า — ระวังโจรฉกของแพง!"]
        for iid, face in gold_bars.bar_items().items():
            name = config_loader.get_item_config(iid).get("name", iid)
            lines.append(f"• {name} — ซื้อ `{face + face * pct // 100:,}` / ขายคืน `{face - face * pct // 100:,}` ทอง")
        await interaction.response.send_message("\n".join(lines),
                                                view=GoldBarView(interaction.user.id), ephemeral=True)


class GoldBarSellSelect(discord.ui.Select):
    """เลือกขายทองคำแท่งจากกระเป๋าคืนธนาคาร"""
    def __init__(self, inv_array):
        counts = Counter(i for i in inv_array if i in gold_bars.bar_items())
        options = [discord.SelectOption(
            label=f"{config_loader.get_item_config(iid).get('name', iid)} x{n}", value=iid)
            for iid, n in list(counts.items())[:25]]
        super().__init__(placeholder="💰 ขายทองคำแท่งคืนธนาคาร...", options=options)

    async def callback(self, interaction: discord.Interaction):
        _, msg = gold_bars.sell_bar(interaction.user.id, self.values[0])
        await interaction.response.edit_message(content=msg, view=GoldBarView(interaction.user.id))


class GoldBarView(discord.ui.View):
    """ปุ่มซื้อแท่ง 4 ขนาด + เมนูขายคืน — ephemeral เห็นคนเดียว สร้างใหม่ทุกครั้งให้ยอดสดเสมอ"""
    def __init__(self, user_id):
        super().__init__(timeout=120)
        self.user_id = user_id
        for iid, face in gold_bars.bar_items().items():
            label = f"ซื้อ {face // 1_000_000}M" if face >= 1_000_000 else f"ซื้อ {face:,}"
            btn = discord.ui.Button(label=f"🧈 {label}", style=discord.ButtonStyle.primary)
            btn.callback = self._make_buy(iid)
            self.add_item(btn)
        player = player_model.get_player(user_id)
        inv = player_model.load_inventory((player or {}).get("inventory", ""))
        if any(i in gold_bars.bar_items() for i in inv):
            self.add_item(GoldBarSellSelect(inv))

    def _make_buy(self, item_id):
        async def _buy(interaction: discord.Interaction):
            _, msg = gold_bars.buy_bar(interaction.user.id, item_id)
            await interaction.response.edit_message(content=msg, view=GoldBarView(interaction.user.id))
        return _buy


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
        from bot.event_images import file_kwargs
        await interaction.response.send_message(msg, ephemeral=True,
                                                **file_kwargs(item_use_file(ok, self.values[0], interaction.user.id)))


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

    async def on_error(self, interaction: discord.Interaction, error: Exception, item: discord.ui.Item):
        """ปุ่มเมนูพังห้ามเงียบ — เดิมกดแล้วขึ้นแค่ 'interaction failed' ตามหาสาเหตุไม่ได้เลย"""
        import traceback
        traceback.print_exception(type(error), error, error.__traceback__)
        msg = (f"⚠️ ปุ่ม **{getattr(item, 'label', '?')}** ขัดข้อง (`{type(error).__name__}: {error}`)\n"
               "ส่งข้อความนี้ให้แอดมินดูได้เลย")
        try:
            if interaction.response.is_done():
                await interaction.followup.send(msg, ephemeral=True)
            else:
                await interaction.response.send_message(msg, ephemeral=True)
        except Exception:
            pass

    @discord.ui.button(label="🎒 กระเป๋า", style=discord.ButtonStyle.primary, custom_id="game_menu:bag")
    async def bag_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        player = player_model.get_player(interaction.user.id)
        if not player:
            return await interaction.response.send_message("❌ ไม่พบข้อมูลตัวละครของคุณ! พิมพ์ `!play` ก่อนนะ", ephemeral=True)
        embed = build_bag_embed(interaction.user.display_name, interaction.user.display_avatar.url, player)
        await interaction.response.send_message(embed=embed, view=BagActionView(interaction.user.id), ephemeral=True)

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
        await interaction.response.send_message(embed=embed, view=ProfilePageView(interaction.user), ephemeral=True)

    @discord.ui.button(label="📅 ภารกิจวันนี้", style=discord.ButtonStyle.success, custom_id="game_menu:daily")
    async def daily_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        from bot import daily
        await interaction.response.send_message(
            embed=daily.build_daily_embed(interaction.user.id, interaction.user.display_name),
            view=DailyView(interaction.user.id), ephemeral=True)

    @discord.ui.button(label="🏪 ตลาดผู้เล่น", style=discord.ButtonStyle.secondary, custom_id="game_menu:market")
    async def market_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        from bot import market
        await interaction.response.send_message(
            embed=market.build_market_embed(interaction.user.id),
            view=MarketView(interaction.user.id), ephemeral=True)

    @discord.ui.button(label="🐾 สัตว์เลี้ยง", style=discord.ButtonStyle.secondary, custom_id="game_menu:pet")
    async def pet_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        from bot import pets
        await interaction.response.send_message(
            embed=pets.build_pet_embed(interaction.user.id, interaction.user.display_name),
            view=PetView(interaction.user.id), ephemeral=True)

    @discord.ui.button(label="🎟️ ซีซั่นพาส", style=discord.ButtonStyle.primary, custom_id="game_menu:season")
    async def season_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        from bot import season
        await interaction.response.send_message(
            embed=season.build_season_embed(interaction.user.id, interaction.user.display_name),
            view=SeasonView(interaction.user.id), ephemeral=True)

    @discord.ui.button(label="🏅 ความสำเร็จ", style=discord.ButtonStyle.secondary, custom_id="game_menu:ach")
    async def ach_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        from bot import achievements
        await interaction.response.send_message(
            embed=achievements.build_achievement_embed(interaction.user.id, interaction.user.display_name),
            view=AchievementView(interaction.user.id), ephemeral=True)

    @discord.ui.button(label="📕 สมุดมอน", style=discord.ButtonStyle.secondary, custom_id="game_menu:bestiary")
    async def bestiary_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = build_bestiary_embed(
            interaction.user.id, interaction.user.display_name, interaction.user.display_avatar.url)
        await interaction.response.send_message(embed=embed, view=BestiaryView(), ephemeral=True)

    @discord.ui.button(label="📖 คู่มือ", style=discord.ButtonStyle.secondary, custom_id="game_menu:codex")
    async def codex_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        from bot.utils import is_main_server
        on_guest = not is_main_server(interaction)   # เซิร์ฟรอง = โชว์ปุ่มข้ามมิติ + ข้อความชวน
        text = "📖 **คู่มือนักผจญภัย** — เลือกหัวข้อ:"
        if on_guest:
            text += ("\n\n✨ *รางวัลรายวัน ร้านค้า คาสิโน กิลด์ PvP และระบบเต็มทั้งหมด "
                     "เล่นได้ที่**เซิร์ฟหลัก**เท่านั้น — กดปุ่ม 🌏 ด้านล่างเพื่อข้ามมิติไปเลย!*")
        await interaction.response.send_message(text, view=CodexView(show_portal=on_guest), ephemeral=True)

    @discord.ui.button(label="💎 เติมเงิน", style=discord.ButtonStyle.success, custom_id="game_menu:topup")
    async def topup_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        from bot.cogs.web_link import TopupModal
        await interaction.response.send_modal(TopupModal())

    @discord.ui.button(label="🌐 เว็บไซต์", style=discord.ButtonStyle.secondary, custom_id="game_menu:website")
    async def website_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        # อ่านลิงก์สดทุกครั้งที่กด — tunnel รีสตาร์ทแล้วลิงก์ใหม่มาเองโดยไม่ต้องโพสต์เมนูใหม่
        from bot.cogs.web_link import website_url
        url = website_url()
        if not url:
            return await interaction.response.send_message("🌐 เว็บไซต์ยังไม่เปิดให้บริการตอนนี้ครับ", ephemeral=True)
        embed = discord.Embed(
            title="🌐 เว็บไซต์เกม Fragment Rift",
            description=(f"ข่าวสาร · อัพเดทแพทช์ · ข้อมูลเกม · เติมเกม · โปรไฟล์\n{url}\n\n"
                         f"🔑 ล็อกอินเว็บ: กดขอโค้ดที่หน้าเว็บ แล้วพิมพ์ `!weblogin <โค้ด>` ในเซิร์ฟนี้"),
            color=0xd93b2b)
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
