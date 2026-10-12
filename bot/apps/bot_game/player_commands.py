import discord
from collections import Counter
from discord.ext import commands
import random
import bot.models.player_model as player_model
import time
import sqlite3
from contextlib import contextmanager
from bot.utils import not_arrested, allowed_channel, main_server_only, adventure_room_only, has_permission
from bot.views.profile_embed import GAME_CLASSES
from bot import config_loader
from bot import game_modifiers
from bot.views.game_views import DeathRespawnView
from bot.event_images import event_image, item_use_image, file_kwargs
import json
import traceback # อย่าลืม import อันนี้ที่ด้านบนสุดของไฟล์นะครับ


# 📖 _SET_STATE_DESC/_item_effect_desc/_monster_element_desc ย้ายไป core/services/codex.py แล้ว
# (ใช้เฉพาะใน build_codex_embed ที่ย้ายไปพร้อมกัน) — เหลือสะพานไว้ตรงนี้เผื่อมีที่อื่นเรียกผ่าน pc.
from core.services.codex import _item_effect_desc, _monster_element_desc  # noqa: F401

# 🏦 bank_fee/bank_action ย้ายไป core/services/bank.py แล้ว (ใช้ร่วมกับเว็บ) — เหลือสะพานไว้ตรงนี้
from core.services.bank import bank_fee, bank_action  # noqa: F401


def item_use_file(ok, item_id, user_id):
    """ภาพประกอบหลังใช้ไอเทมสำเร็จ — จุดเดียวให้ทั้ง !use และปุ่มเมนูใช้ร่วมกัน (คืน discord.File|None)"""
    if not ok:
        return None
    info = config_loader.get_item_config(item_id) or {}
    player = player_model.get_player(user_id) or {}
    cont = player.get("continent") or "main"   # ตั๋ววาร์ปสุ่ม: continent ถูกอัปเดตไปแล้ว → ได้ภาพทวีปปลายทางพอดี
    if info.get("effect") == "random_continent":
        return event_image(f"arrival_{cont}")
    return item_use_image(info, cont)


# 🛍️ usable_kind/apply_item_effect ย้ายไป core/services/items.py แล้ว (ใช้ร่วมกับเว็บ) — เหลือสะพานไว้ตรงนี้
from core.services.items import EQUIP_TYPES, usable_kind, apply_item_effect  # noqa: F401


def build_bank_embed(player):
    """สร้าง Embed บัญชีธนาคาร — ใช้ร่วมกันระหว่างคำสั่ง !bank และปุ่มเมนู"""
    bank_balance = player.get("bank", 0)
    cash_balance = player.get("cash", 0)
    embed = discord.Embed(title="🏦 บัญชีธนาคารของคุณ", color=discord.Color.gold())
    embed.add_field(name="💰 เงินสดติดตัว", value=f"`{cash_balance:,}` ทอง", inline=True)
    embed.add_field(name="🏦 เงินในธนาคาร", value=f"`{bank_balance:,}` ทอง", inline=True)
    embed.set_footer(text="ใช้คำสั่ง !deposit [จำนวน] เพื่อฝากเงิน (ถ้ามี)")
    return embed


def build_bag_embed(display_name, avatar_url, player):
    """สร้าง Embed กระเป๋าเดินทาง — ใช้ร่วมกันระหว่างคำสั่ง !bag และปุ่มเมนู"""
    inv_array = player_model.load_inventory(player.get("inventory", ""))

    embed = discord.Embed(
        title=f"🎒 กระเป๋าเดินทางของ {display_name}",
        description=f"💰 **เงินสดกลาง:** {player.get('cash', 0):,} ทอง",
        color=discord.Color(player.get("profile_color") or 0x3498DB)  # 🎨 สีย้อมส่วนตัว (ไม่เคยย้อม = ฟ้าเดิม)
    )

    capacity = player.get("capacity", 10)
    current_count = len(inv_array)
    cap_display = "ไม่จำกัด" if capacity == 0 else f"{current_count} / {capacity}"

    if not inv_array:
        embed.add_field(
            name=f"📦 ไอเทมในกระเป๋า ({cap_display})",
            value="*~ กระเป๋าว่างเปล่า ไม่มีไอเทมเลย ~*",
            inline=False
        )
    else:
        item_counts = Counter(inv_array)
        all_items = config_loader.get_all_items()

        def _sort_key(item_id):
            return (0, int(item_id)) if str(item_id).isdigit() else (1, 0)

        # 🎒 B5: จัดกลุ่มตามประเภท — หาของที่ต้องการเจอเร็วขึ้นมาก
        groups = {"use": [], "equip": [], "artifact": [], "junk": []}
        junk_value = 0
        for item_id in sorted(item_counts, key=_sort_key):
            count = item_counts[item_id]
            data = all_items.get(item_id, {})
            name = data.get("name", "❓ ไอเทมปริศนา")
            line = f"`{item_id}` {name} ×**{count}**"
            eff = data.get("effect")
            if eff == "equip_artifact":
                groups["artifact"].append(line)
            elif data.get("equip_key"):
                groups["equip"].append(line)
            elif eff or data.get("type") == "use":
                groups["use"].append(line)
            else:
                groups["junk"].append(line + f" *(ขายได้ {data.get('sell', 0):,}/ชิ้น)*")
                junk_value += int(data.get("sell", 0)) * count

        cap_line = f"({len(inv_array)} / {'ไม่จำกัด' if capacity == 0 else capacity})"
        sections = [
            (f"💊 ของใช้ {cap_line}", groups["use"]),
            ("🏺 อาร์ติแฟกต์", groups["artifact"]),
            ("⚔️ อุปกรณ์สวมใส่", groups["equip"]),
            (f"🧱 วัสดุ/ของขาย — ขายหมดได้ **{junk_value:,}** ทอง", groups["junk"]),
        ]
        for title, lines in sections:
            if not lines:
                continue
            chunk, first = "", True
            for line in lines:  # ตัดท่อนละ ≤1024 ตามลิมิต Discord
                if len(chunk) + len(line) + 1 > 1024:
                    embed.add_field(name=title if first else "​", value=chunk, inline=False)
                    chunk, first = "", False
                chunk += line + "\n"
            if chunk:
                embed.add_field(name=title if first else "​", value=chunk, inline=False)

    embed.set_thumbnail(url=avatar_url)
    return embed


def build_codex_embed(topic=""):
    """สร้าง embed คู่มือรายหัวข้อ — ใช้ร่วมกันระหว่าง !codex และปุ่ม 📖 ในเมนู
    ข้อมูลจริงอยู่ที่ core/services/codex.py (ไม่รู้จัก discord) — ฟังก์ชันนี้แค่เอา dict มาแปะเป็น discord.Embed
    """
    from core.services.codex import codex_topic_full
    d = codex_topic_full(topic)
    embed = discord.Embed(title=d["title"], description=d["description"], color=d["color"])
    for f in d["fields"]:
        embed.add_field(name=f["name"], value=f["value"], inline=f.get("inline", False))
    if d["footer"] is not None:
        embed.set_footer(text=d["footer"])
    return embed



def build_bestiary_embed(user_id, display_name, avatar_url):
    """สมุดสะสมมอนสเตอร์รายคน — ใช้ร่วมกันระหว่าง !bestiary และปุ่ม 📕 ในเมนู"""
    book = player_model.get_bestiary(user_id)
    embed = discord.Embed(
        title=f"📕 สมุดสะสมมอนสเตอร์ — {display_name}", color=0x8d6e63,
        description=("ล้มมอนแรงค์ไหนในทวีปไหน ช่องนั้นติ๊ก ✅\n"
                     "ครบ 4 แรงค์/ทวีป `+100,000` • ⭐ ไร้พ่าย `+200,000` • ครบทั้งสมุด `+1,000,000` + 💊"))
    rank_icons = [("Common", "🟢"), ("Mini-Boss", "🟡"), ("Main-Boss", "🔴"), ("Secret", "🟣")]
    done_slots, stars, total_kills = 0, 0, 0
    for key, c in game_modifiers.CONTINENTS.items():
        marks = []
        for rank, icon in rank_icons:
            have = (key, rank) in book
            done_slots += 1 if have else 0
            marks.append(f"{icon}{'✅' if have else '▫️'}")
        star = (key, "Unbeatable") in book
        stars += 1 if star else 0
        kills = sum(v for (c2, _r), v in book.items() if c2 == key)
        total_kills += kills
        line = " ".join(marks) + (" ⭐" if star else "") + (f" — ล้มสะสม `{kills:,}`" if kills else "")
        embed.add_field(name=c["label"], value=line, inline=False)
    embed.add_field(name="📊 ความคืบหน้า",
                    value=f"ช่องสมุด `{done_slots}/36` | ดาวไร้พ่าย `{stars}/9` | ล้มรวมทั้งหมด `{total_kills:,}` ตัว",
                    inline=False)
    elem = player_model.get_element_book(user_id)
    got = sum(game_modifiers.element_progress(elem, c)[0] for c in game_modifiers.CONTINENTS)
    per = game_modifiers.element_progress(elem, "main")[1]
    embed.add_field(name="🧬 สมุดธาตุ",
                    value=(f"เก็บได้ `{got}/{per * len(game_modifiers.CONTINENTS)}` ช่อง "
                           f"— กดปุ่ม **🧬 สมุดธาตุ** ด้านล่างเพื่อดูรายทวีป"), inline=False)
    embed.set_thumbnail(url=avatar_url)
    return embed


# 🧬 ELEM_RANK_ICON ย้ายไป core/services/codex.py แล้ว (ใช้ร่วมกับ build_bestiary_embed/build_element_book_embed) — เหลือสะพานไว้ตรงนี้
from core.services.codex import ELEM_RANK_ICON  # noqa: F401


def build_element_book_embed(user_id, display_name, continent=None):
    """🧬 สมุดธาตุ — ไม่ระบุทวีป = สรุปทุกทวีป | ระบุ = ตาราง 5 แรงค์ × 7 ธาตุของทวีปนั้น"""
    book = player_model.get_element_book(user_id)
    els = list(game_modifiers.ELEMENTS)
    rewards = config_loader.get_balance("bestiary.element_rank_rewards", {}) or {}

    if continent and continent in game_modifiers.CONTINENTS:
        c = game_modifiers.CONTINENTS[continent]
        got, total = game_modifiers.element_progress(book, continent)
        art_id = str((config_loader.get_balance("bestiary.continent_artifacts", {}) or {}).get(continent, ""))
        art = config_loader.get_item_config(art_id).get("name", "อาร์ติแฟกต์") if art_id else "—"
        embed = discord.Embed(
            title=f"🧬 สมุดธาตุ — {c['label']}", color=0x8d6e63,
            description=(f"ล้มมอนแต่ละแรงค์ให้ครบทั้ง 7 ธาตุ · เก็บได้ `{got}/{total}` ช่อง\n"
                         f"🏺 ครบทั้งทวีปนี้ได้ **{art}**"))
        header = "　" + " ".join(game_modifiers.ELEMENTS[e]["label"].split()[0] for e in els)
        embed.add_field(name="ธาตุ", value=header, inline=False)
        for rank, label in ELEM_RANK_ICON:
            marks = " ".join("✅" if (continent, rank, e) in book else "▫️" for e in els)
            done = game_modifiers.element_rank_done(book, continent, rank)
            bonus = " · **ครบแล้ว!**" if done else f" · ครบแล้วรับ 🪙 {int(rewards.get(rank, 0)):,}"
            embed.add_field(name=label, value=f"{marks}{bonus}", inline=False)
        return embed

    embed = discord.Embed(
        title=f"🧬 สมุดธาตุของ {display_name}", color=0x8d6e63,
        description=("มอนแต่ละแรงค์เก็บแยกทีละธาตุ (5 แรงค์ × 7 ธาตุ ต่อทวีป)\n"
                     "ครบ 1 แรงค์ = ทอง · ครบ 1 ทวีป = **อาร์ติแฟกต์ประจำทวีป** · "
                     "ครบทุกทวีป = **สัตว์เลี้ยงขั้นสูงสุด**"))
    total_got = 0
    for key, c in game_modifiers.CONTINENTS.items():
        got, total = game_modifiers.element_progress(book, key)
        total_got += got
        bar = "█" * round(got / total * 10) + "░" * (10 - round(got / total * 10))
        done_ranks = sum(1 for r, _lbl in ELEM_RANK_ICON if game_modifiers.element_rank_done(book, key, r))
        flag = " 🏺" if game_modifiers.element_continent_done(book, key) else ""
        embed.add_field(name=c["label"],
                        value=f"`{bar}` {got}/{total} · แรงค์ที่ครบ {done_ranks}/5{flag}", inline=True)
    embed.set_footer(text=f"รวมทั้งเล่ม {total_got}/{35 * len(game_modifiers.CONTINENTS)} ช่อง "
                          "— เลือกทวีปจากเมนูด้านล่างเพื่อดูรายละเอียด")
    return embed


class PlayerCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db_path = player_model.DB_NAME   # ไฟล์เดียวกับทุกที่ (Docker/NAS ชี้เข้า volume) ไม่ใช่ path ตายตัว
        self.pk_cooldowns = {} #

    # --- Database Context Manager ---
    @contextmanager
    def get_db(self):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        try:
            yield cursor
            conn.commit()
        finally:
            conn.close()

    # --- ฟังก์ชันเสริม: ดึงข้อมูลชื่อผู้เล่นแบบมีประสิทธิภาพ ---
    async def get_user_name(self, uid):
        user = self.bot.get_user(uid) or await self.bot.fetch_user(uid)
        return user.name if user else f"User {uid}"

    # 1. ฝากเงิน: ย้ายเงินจาก Cash -> Bank
    @not_arrested() 
    @commands.command(name="deposit")
    @allowed_channel("bank")
    async def deposit(self, ctx, amount: int):
        _, msg = bank_action(ctx.author.id, "deposit", amount)
        await ctx.send(msg)
        
    @not_arrested() 
    @commands.command(name="withdraw")
    @allowed_channel("bank")
    async def withdraw(self, ctx, amount: int):
        _, msg = bank_action(ctx.author.id, "withdraw", amount)
        await ctx.send(msg)
    
    # 2. โอนเงิน: โอนจาก Bank -> ผู้เล่นอื่น
    @not_arrested() 
    @main_server_only()   # P8: เซิร์ฟหลักเท่านั้น
    @commands.command(name="transfer")
    @allowed_channel("bank")
    async def transfer(self, ctx, member: discord.Member, amount: int):
        _, msg = bank_action(ctx.author.id, "transfer", amount, target_id=member.id)
        await ctx.send(msg)

    # 3. ขอเงิน (Beg)
    @not_arrested() 
    @main_server_only()   # P8: เซิร์ฟหลักเท่านั้น
    @commands.command(name="beg")
    @allowed_channel("bank")
    async def beg(self, ctx):
        if not any(role.name == "ขอทาน" for role in ctx.author.roles):
            return await ctx.send("❌ เฉพาะคนมียศ 'ขอทาน' เท่านั้นที่จะขอเงินคนอื่นได้!")

        top_players = player_model.get_all_players_sorted_by_wealth()[:10] 
        if not top_players: return await ctx.send("❌ ไม่มีเศรษฐีให้ขอเลย...")

        target = random.choice(top_players)
        tax = int(target.get("bank", 0) * 0.01)
        
        player_model.update_player_field(target["user_id"], "bank", target["bank"] - tax)
        player_model.update_player_field(ctx.author.id, "cash", player_model.get_player(ctx.author.id)["cash"] + tax)
        await ctx.send(f"🤲 ขอทานได้เงิน `{tax}` ทอง จากเศรษฐี {target['username']}!")

    # 4. ปล้น (Rob)
    @not_arrested() 
    @main_server_only()   # P8: เซิร์ฟหลักเท่านั้น
    @commands.command(name="rob")
    @allowed_channel("bank")
    async def rob(self, ctx, member: discord.Member):
        if member.id == ctx.author.id:
            return await ctx.send("❌ จะปล้นตัวเองทำไมล่ะ!")

        player = player_model.get_player(ctx.author.id)
        if player.get("current_state") == "arrested":
            if time.time() < player.get("arrest_until", 0):
                return await ctx.send("❌ คุณกำลังติดคุกอยู่! ยังไม่ถึงเวลาพ้นโทษ")
            else:
                player_model.update_player_field(ctx.author.id, "current_state", "idle")

        if random.random() <= 0.05:
            victim = player_model.get_player(member.id)
            rob_amount = int(victim.get("cash", 0) * 0.5)
            player_model.update_player_field(member.id, "cash", victim["cash"] - rob_amount)
            player_model.update_player_field(ctx.author.id, "cash", player["cash"] + rob_amount)
            await ctx.send(f"🥷 ปล้นสำเร็จ! คุณได้เงินจาก {member.mention} มา `{rob_amount:,}` ทอง")
        else:
            jail_time = int(time.time() + 180)
            player_model.update_player_field(ctx.author.id, "current_state", "arrested")
            player_model.update_player_field(ctx.author.id, "arrest_until", jail_time)
            await ctx.send(f"👮 **ปล้นพลาด!** คุณถูกตำรวจจับ! ถูกขังคุกเป็นเวลา 3 นาที")

    # 5. rich
    @main_server_only()   # P8: เซิร์ฟหลักเท่านั้น
    @main_server_only()   # P8: เซิร์ฟหลักเท่านั้น
    @main_server_only()   # P8: เซิร์ฟหลักเท่านั้น
    @commands.command(name="mytext")
    @allowed_channel("bank")
    async def check_my_text(self, ctx):
        player = player_model.get_player(ctx.author.id)
        if not player:
            return await ctx.send("❌ ไม่พบข้อมูลตัวละครของคุณในระบบ!")
        
        total_text = player.get("total_text", 0)
        event_text = player.get("event_text", 0)
        
        embed = discord.Embed(
            title="📊 สถิติการพิมพ์แชทของคุณ", 
            color=discord.Color.blue()
        )
        
        # ใส่รูปโปรไฟล์ของผู้เล่น
        if ctx.author.avatar:
            embed.set_thumbnail(url=ctx.author.avatar.url)
            
        embed.add_field(name="💬 ข้อความทั้งหมด (ตลอดชีพ)", value=f"`{total_text:,}` ข้อความ", inline=False)
        embed.add_field(name="🏆 ข้อความกิจกรรม (ซีซั่นนี้)", value=f"`{event_text:,}` ข้อความ", inline=False)
        
        await ctx.send(embed=embed)


    # ==========================================
    # 🏆 คำสั่งเช็ก 10 อันดับคนพิมพ์เยอะที่สุด (!toptext)
    # ==========================================
    @main_server_only()   # P8: เซิร์ฟหลักเท่านั้น
    @commands.command(name="bank")
    @allowed_channel("bank")
    async def check_bank(self, ctx):
        player = player_model.get_player(ctx.author.id)
        from bot.views.menu_view import BankActionView   # B1: พิมพ์ !bank ก็ได้ปุ่มธุรกรรมเหมือนกดจากเมนู
        await ctx.send(embed=build_bank_embed(player), view=BankActionView())

    # ==========================================
    # 🎖️ คำสั่งรับรางวัลตามยศ (!reward) — รวมรางวัลทุกยศที่มีสิทธิ์ในครั้งเดียว
    # ponytail: คูลดาวน์เดียวรวมทุกยศ (ไม่ใช่แยกคูลดาวน์ต่อยศ) — ง่ายกว่าและพอสำหรับสเปกปัจจุบัน
    # ==========================================
    @not_arrested()
    @main_server_only()   # P8: เซิร์ฟหลักเท่านั้น
    @adventure_room_only()   # P8: เซิร์ฟหลักใช้ได้เฉพาะมิติส่วนตัว
    @commands.command(name="reward")
    async def claim_rank_reward(self, ctx):
        user_id = ctx.author.id
        player = player_model.get_player(user_id)
        if not player:
            return await ctx.send("❌ ไม่พบข้อมูลตัวละครของคุณ! พิมพ์ `!play` เพื่อสร้างตัวละครก่อนน้า")

        my_role_ids = {role.id for role in ctx.author.roles}
        matched = [r for r in config_loader.get_rank_rewards() if r.get("role_id") in my_role_ids]
        if not matched:
            return await ctx.send("❌ ยศของคุณยังไม่มีรางวัลให้รับในตอนนี้!")

        cooldown_seconds = config_loader.get_rank_reward_cooldown_hours() * 3600
        last_claim = player.get("last_reward_claim", 0) or 0
        now = time.time()
        remaining = cooldown_seconds - (now - last_claim)
        if remaining > 0:
            hours = int(remaining // 3600)
            minutes = int((remaining % 3600) // 60)
            return await ctx.send(f"⏳ คุณรับรางวัลไปแล้ว! กรุณารออีก `{hours}` ชั่วโมง `{minutes}` นาที")

        total_cash = sum(int(r.get("cash", 0)) for r in matched)
        total_exp = sum(int(r.get("exp", 0)) for r in matched)
        item_grants = Counter()
        for r in matched:
            for it in r.get("items", []):
                item_grants[str(it.get("item_id"))] += int(it.get("amount", 1))

        if total_cash:
            player_model.increment_player_field(user_id, "cash", total_cash)
        is_lvl_up, new_level, _ = (False, None, None)
        if total_exp:
            is_lvl_up, new_level, _ = player_model.add_exp(user_id, total_exp)

        if item_grants:
            inv_list = player_model.load_inventory(player.get("inventory", ""))
            all_items = config_loader.get_all_items()
            for item_id, amount in item_grants.items():
                if item_id not in all_items:
                    continue
                inv_list.extend([item_id] * amount)
            player_model.update_player_field(user_id, "inventory", inv_list)

        player_model.update_player_field(user_id, "last_reward_claim", int(now))

        labels = ", ".join(r.get("label", "ยศ") for r in matched)
        lines = [f"🎖️ **รับรางวัลจากยศสำเร็จ!** ({labels})"]
        if total_cash:
            lines.append(f"💰 เงินสด: `+{total_cash:,}` ทอง")
        if total_exp:
            lvl_txt = f" (✨ Level Up! → {new_level})" if is_lvl_up else ""
            lines.append(f"⭐ EXP: `+{total_exp}`{lvl_txt}")
        all_items = config_loader.get_all_items()
        for item_id, amount in item_grants.items():
            name = all_items.get(item_id, {}).get("name", f"ไอเทม {item_id}")
            lines.append(f"📦 {name} x`{amount}`")
        await ctx.send("\n".join(lines))

    # --- 📖 !codex: สารานุกรมกติกา — เนื้อหาจริงอยู่ใน build_codex_embed (แชร์กับปุ่มเมนู) ---
    @adventure_room_only()   # P8: เซิร์ฟหลักใช้ได้เฉพาะมิติส่วนตัว
    @commands.command(name="codex")
    async def codex(self, ctx, *, topic: str = ""):
        await ctx.send(embed=build_codex_embed(topic))

    # --- ⚔️ !war: สกอร์สงครามฝ่ายประจำสัปดาห์ (ธีม faction_war) ---
    @adventure_room_only()   # P8: เซิร์ฟหลักใช้ได้เฉพาะมิติส่วนตัว
    @commands.command(name="war", aliases=["สงคราม"])
    async def war_scores(self, ctx):
        scores = player_model.get_faction_war_scores()
        h, d = scores.get("human", 0), scores.get("demon", 0)
        theme = game_modifiers.get_weekly_theme()
        active = bool(theme and theme.get("key") == "faction_war")
        if h > d:
            headline = "🔵 **ฝ่ายมนุษย์กำลังนำ!**"
        elif d > h:
            headline = "🔴 **ฝ่ายปีศาจกำลังนำ!**"
        else:
            headline = "⚖️ **สูสีคู่คี่ ไม่มีใครยอมใคร!**"
        embed = discord.Embed(
            title="⚔️ สกอร์สงครามฝ่าย — สัปดาห์นี้", color=0x992d22,
            description=(f"{headline}\n\n🔵 ฝ่ายมนุษย์ `{h:,}` แต้ม\n🔴 ฝ่ายปีศาจ `{d:,}` แต้ม\n\n"
                         + ("🔥 ธีมสงครามฝ่ายกำลังลุกโหม — ออกล่าแชมเปี้ยนได้เลย!" if active
                            else "🕊️ สัปดาห์นี้ไม่ใช่ธีมสงคราม — แต้มจะเริ่มนับเมื่อธีม ⚔️ สงครามฝ่าย มาถึง")))
        await ctx.send(embed=embed)

    # --- 📅 !daily: ภารกิจรายวัน + ล็อกอินต่อเนื่อง (C1) ---
    @adventure_room_only()   # เล่นในมิติส่วนตัวเหมือนคำสั่งผู้เล่นอื่น
    @commands.command(name="daily", aliases=["เควส", "quest"])
    async def daily_quests(self, ctx):
        from bot import daily
        from bot.views.menu_view import DailyView
        streak, _best, is_new = player_model.touch_login_streak(ctx.author.id)
        if is_new:
            bonus_gold = int(config_loader.get_daily_cfg("streak_daily_gold", 0))
            if bonus_gold:
                player = player_model.get_player(ctx.author.id)
                player_model.update_player_field(ctx.author.id, "cash", player.get("cash", 0) + bonus_gold)
                await ctx.send(f"🌅 **เช็คอินวันใหม่!** รับ 🪙 `{bonus_gold:,}` ทอง (ต่อเนื่องวันที่ {streak})")
            milestone = daily.claim_streak_reward(ctx.author.id, streak)
            if milestone:
                await ctx.send(milestone)
        await ctx.send(embed=daily.build_daily_embed(ctx.author.id, ctx.author.display_name),
                       view=DailyView(ctx.author.id))

    # --- 🏆 !top: อันดับรวมทุกหมวด (O6 — ยุบจาก 4 คำสั่งเดิม ชื่อเดิมยังใช้เป็นทางลัดได้) ---
    @main_server_only()   # P8: เซิร์ฟหลักเท่านั้น
    @commands.command(name="top", aliases=["rich", "toplvl", "toptext", "toptime", "อันดับ"])
    @allowed_channel("bank")
    async def top_board(self, ctx, kind: str = None):
        from bot.views.menu_view import TopBoardView
        alias_map = {"rich": "rich", "toplvl": "level", "toptext": "text", "toptime": "time"}
        # !top เปล่า ๆ เปิดหมวดสัปดาห์นี้ก่อน (C3) — หมวดที่มีของรางวัลรออยู่ | alias เดิมยังพาไปหมวดเดิม
        start = alias_map.get(ctx.invoked_with, None) or {
            "เงิน": "rich", "เลเวล": "level", "แชท": "text", "เวลา": "time",
            "สัปดาห์": "weekly", "week": "weekly"}.get(kind or "", "weekly")
        await ctx.send(embed=build_top_embed(start, ctx.author.id),
                       view=TopBoardView(ctx.author.id, current=start))

    # --- 🎯 !bounty: กระดานล่าค่าหัว (คนสติติดลบ = อาชญากร) ---
    @main_server_only()   # P8: เซิร์ฟหลักเท่านั้น
    @commands.command(name="bounty", aliases=["wanted", "ล่าหัว"])
    @allowed_channel("arena")   # อยู่ห้องเดียวกับ !att/!scan — เช็คกระดานแล้วตีต่อได้เลย
    async def bounty_board(self, ctx):
        outlaws = player_model.get_outlaws()
        embed = discord.Embed(
            title="🎯 กระดานล่าค่าหัว", color=0xc0392b,
            description=("ผู้คลุ้มคลั่ง (สติติดลบ) มีค่าหัวรอนักล่า — สังหารด้วย `!att` รับทองเต็ม ๆ\n"
                         "ปราบอาชญากรไม่เสียสติ แถมฆ่าสำเร็จได้สติคืน `+10`"))
        if not outlaws:
            embed.description += "\n\n🕊️ **บ้านเมืองสงบสุข** — ยังไม่มีหัวให้ล่าในตอนนี้"
        else:
            lines = []
            for uid, sanity in outlaws[:15]:  # โชว์ 15 หัวแรก (เรียงจากคลั่งสุด)
                lines.append(f"💀 <@{uid}> — สติ `{sanity}` | ค่าหัว 💰 `{game_modifiers.bounty_for(sanity):,}` ทอง")
            embed.add_field(name=f"หมายหัว {len(outlaws)} ราย", value="\n".join(lines), inline=False)
        await ctx.send(embed=embed)

    # --- 📕 !bestiary: สมุดสะสมมอนสเตอร์ — เนื้อหาจริงอยู่ใน build_bestiary_embed (แชร์กับปุ่มเมนู) ---
    @adventure_room_only()   # P8: เซิร์ฟหลักใช้ได้เฉพาะมิติส่วนตัว
    @commands.command(name="bestiary", aliases=["สมุดมอน"])
    async def bestiary(self, ctx):
        from bot.views.menu_view import BestiaryView
        await ctx.send(embed=build_bestiary_embed(
            ctx.author.id, ctx.author.display_name, ctx.author.display_avatar.url),
            view=BestiaryView())

    # --- 💍 !marry / !partner / !divorce: คู่หู (C7) ---
    @adventure_room_only()   # P8: เซิร์ฟหลักใช้ได้เฉพาะมิติส่วนตัว
    @commands.command(name="partner", aliases=["คู่หู", "couple"])
    async def partner_status(self, ctx):
        from bot import partner
        await ctx.send(embed=partner.build_partner_embed(ctx.author.id, ctx.author.display_name))

    @adventure_room_only()
    @commands.command(name="marry", aliases=["แต่งงาน"])
    async def marry_cmd(self, ctx, member: discord.Member = None):
        from bot import partner
        from bot.views.menu_view import ProposalView
        if member is None:
            return await ctx.send("❓ **วิธีใช้:** `!marry @ผู้เล่น` — ชวนเป็นคู่หู (อีกฝ่ายต้องกดยืนยัน)")
        if member.bot or member.id == ctx.author.id:
            return await ctx.send("❌ เลือกผู้เล่นคนอื่นที่ไม่ใช่บอทนะ")
        if partner.partner_of(ctx.author.id):
            return await ctx.send("❌ คุณมีคู่อยู่แล้ว! หย่าก่อนด้วย `!divorce`")
        if partner.partner_of(member.id):
            return await ctx.send(f"❌ {member.display_name} มีคู่อยู่แล้ว")
        # 💍 เช็คแหวนตั้งแต่ตอนพิมพ์ — จะได้ไม่ชวนเขาแล้วมาล้มตอนเขากดตกลง
        if not partner.has_ring(ctx.author.id):
            return await ctx.send(
                f"❌ ต้องมี **{partner.ring_name()}** ก่อนถึงจะขอแต่งงานได้!\n"
                f"ซื้อที่ `!shop` ราคา 🪙 `{partner.ring_price():,}` ทอง")
        cost = int(config_loader.get_config().get("partner", {}).get("wedding_cost", 0) or 0)
        ring_note = f"\n💍 {ctx.author.mention} เตรียม **{partner.ring_name()}** มาแล้ว" if partner.ring_id() else ""
        await ctx.send(f"💌 {member.mention} — {ctx.author.mention} ชวนคุณเป็นคู่หู!{ring_note}\n"
                       f"ค่าจัดงานคนละ 🪙 `{cost:,}` ทอง (หักตอนกดตกลง)",
                       view=ProposalView(ctx.author.id, member.id))

    @adventure_room_only()
    @commands.command(name="divorce", aliases=["หย่า"])
    async def divorce_cmd(self, ctx):
        from bot import partner
        _ok, msg = partner.divorce(ctx.author.id)
        await ctx.send(msg)

    # --- 🏪 !market: ตลาดผู้เล่น (C5) ---
    @adventure_room_only()   # P8: เซิร์ฟหลักใช้ได้เฉพาะมิติส่วนตัว
    @commands.command(name="market", aliases=["ตลาด"])
    async def market_board(self, ctx, action: str = None, arg1: str = None, arg2: str = None):
        from bot import market
        from bot.views.menu_view import MarketView

        if action in ("sell", "ขาย"):
            if not arg1 or not arg2:
                return await ctx.send("❓ **วิธีใช้:** `!market sell [เลขไอเทม] [ราคา]`")
            _ok, msg = market.list_item(ctx.author.id, arg1, arg2)
            return await ctx.send(msg)

        if action in ("cancel", "ยกเลิก"):
            if not arg1 or not arg1.lstrip("#").isdigit():
                return await ctx.send("❓ **วิธีใช้:** `!market cancel [เลขรายการ]`")
            _ok, msg = market.cancel_listing(ctx.author.id, int(arg1.lstrip("#")))
            return await ctx.send(msg)

        if action in ("mine", "ของฉัน"):
            rows = market.my_listings(ctx.author.id)
            if not rows:
                return await ctx.send("📭 คุณไม่มีของลงขายอยู่")
            lines = [f"`#{lid}` {market._item_name(item)} — 🪙 `{price:,}` ทอง"
                     for lid, item, price in rows]
            return await ctx.send("🏪 **ของที่คุณลงขายอยู่:**\n" + "\n".join(lines)
                                  + "\n*ยกเลิก: `!market cancel [เลขรายการ]`*")

        if action in ("buy", "ซื้อ"):
            if not arg1 or not arg1.lstrip("#").isdigit():
                return await ctx.send("❓ **วิธีใช้:** `!market buy [เลขรายการ]`")
            _ok, msg = market.buy_listing(ctx.author.id, int(arg1.lstrip("#")))
            return await ctx.send(msg)

        await ctx.send(embed=market.build_market_embed(ctx.author.id),
                       view=MarketView(ctx.author.id))

    # --- 🐾 !pet: สัตว์เลี้ยงที่จับมาได้ + เลือกตัวติดตาม (C4) ---
    @adventure_room_only()   # P8: เซิร์ฟหลักใช้ได้เฉพาะมิติส่วนตัว
    @commands.command(name="pet", aliases=["pets", "สัตว์เลี้ยง"])
    async def pet_board(self, ctx):
        from bot import pets
        from bot.views.menu_view import PetView
        await ctx.send(embed=pets.build_pet_embed(ctx.author.id, ctx.author.display_name),
                       view=PetView(ctx.author.id))

    # --- 🎟️ !season: ซีซั่นพาสรายเดือน (C2) ---
    @adventure_room_only()   # P8: เซิร์ฟหลักใช้ได้เฉพาะมิติส่วนตัว
    @commands.command(name="season", aliases=["pass", "ซีซั่น", "ซีซัน"])
    async def season_pass(self, ctx):
        from bot import season
        from bot.views.menu_view import SeasonView
        await ctx.send(embed=season.build_season_embed(ctx.author.id, ctx.author.display_name),
                       view=SeasonView(ctx.author.id))

    # --- 🎟️ แอดมินเปิดพรีเมียมให้คนที่โอนเงินจริงมาแล้ว (คู่กับ !confirm_payment) ---
    @main_server_only()
    @has_permission("admin")
    @allowed_channel("payment")   # ห้องเดียวกับที่แอดมินกด !confirm_payment
    @commands.command(name="grant_season")
    async def grant_season(self, ctx, member: discord.Member = None):
        if member is None:
            return await ctx.send("❓ **วิธีใช้:** `!grant_season @ผู้เล่น` — เปิดสายพรีเมียมซีซั่นนี้ให้")
        from bot import season
        if season.grant_premium(member.id):
            await ctx.send(f"🎟️ เปิดสายพรีเมียมซีซั่น `{player_model.season_key()}` ให้ {member.mention} แล้ว!")
        else:
            await ctx.send(f"ℹ️ {member.mention} เปิดสายพรีเมียมของซีซั่นนี้ไว้อยู่แล้ว")

    # --- 🏅 !ach: ความสำเร็จ + เลือกตำแหน่งอวด (C8) ---
    @adventure_room_only()   # P8: เซิร์ฟหลักใช้ได้เฉพาะมิติส่วนตัว
    @commands.command(name="ach", aliases=["achievement", "title", "ความสำเร็จ", "ตำแหน่ง"])
    async def achievements_board(self, ctx):
        from bot import achievements
        from bot.views.menu_view import AchievementView
        await ctx.send(embed=achievements.build_achievement_embed(ctx.author.id, ctx.author.display_name),
                       view=AchievementView(ctx.author.id))

    # --- โค้ดคำสั่ง !bag ---
    @adventure_room_only()   # P8: เซิร์ฟหลักใช้ได้เฉพาะมิติส่วนตัว
    @commands.command(name="bag")
    async def check_bag(self, ctx): # 🚨 จุดสำคัญ: เติม self ลงไปตรงนี้ครับ
        user_id = ctx.author.id
        player = player_model.get_player(user_id)

        if not player:
            print(f"ERROR: [Bag] ไม่พบข้อมูลผู้เล่นสำหรับ User ID: {user_id}")
            await ctx.send("❌ ไม่พบข้อมูลตัวละครของคุณ! พิมพ์ `!play` เพื่อสร้างตัวละครก่อนน้า")
            return

        embed = build_bag_embed(ctx.author.display_name, ctx.author.display_avatar.url, player)
        from bot.views.menu_view import BagActionView   # B1: ปุ่มคราฟ/ขายวัสดุ ติดมากับ !bag ด้วย
        await ctx.send(embed=embed, view=BagActionView(ctx.author.id))
    
    # ⏱️ เช็กเวลาออนไลน์ของตัวเอง
    @main_server_only()   # P8: เซิร์ฟหลักเท่านั้น
    @commands.command(name="mytime")
    @allowed_channel("bank")
    async def check_my_time(self, ctx):
        player = player_model.get_player(ctx.author.id)
        if not player:
            return await ctx.send("❌ คุณยังไม่มีข้อมูลในระบบ!")
        
        total_minutes = player.get("total_online_time", 0)
        hours = total_minutes // 60
        minutes = total_minutes % 60
        
        await ctx.send(f"👤 **{ctx.author.name}**\n⏱️ เวลาออนไลน์ทั้งหมดของคุณ: **{hours} ชั่วโมง {minutes} นาที**")

    # 🏆 เช็กอันดับ Top 10 เวลาออนไลน์
    @main_server_only()   # P8: เซิร์ฟหลักเท่านั้น
    @adventure_room_only()   # P8: เซิร์ฟหลักใช้ได้เฉพาะมิติส่วนตัว
    @commands.command(name="use")
    async def use_item(self, ctx, item_id: str):
        item_cfg = config_loader.get_item_config(item_id)

        # 🧪 ยาพลิกธาตุ: ต้องมีธาตุประจำเผ่าก่อน (เช็คจากยศ — ทำได้เฉพาะตรงนี้ที่เห็น roles)
        if item_cfg and item_cfg.get("effect") == "apply_status" and item_cfg.get("effect_value") == "element_flux":
            player_elements = game_modifiers.resolve_player_elements([r.name for r in ctx.author.roles])
            if not player_elements:
                return await ctx.send("❌ **ยาพลิกธาตุต้องอาศัยพลังธาตุประจำเผ่า!** คุณยังไม่มียศเผ่า — รับยศเผ่าก่อนแล้วค่อยใช้ (ยายังอยู่ในกระเป๋า)")

        # 🎨 ผงสีรุ้ง: เปิดเมนูเลือกสีย้อมโปรไฟล์ (ผงถูกหักตอนยืนยันใน view)
        if item_cfg and item_cfg.get("effect") == "dye_profile":
            player = player_model.get_player(ctx.author.id)
            inv = player_model.load_inventory(player.get("inventory", ""))
            if str(item_id) not in inv:
                return await ctx.send(f"❌ คุณไม่มีไอเทมหมายเลข `{item_id}` ในกระเป๋า! (พิมพ์ `!bag` เพื่อเช็ก)")
            from bot.views.game_views import ProfileDyeView
            view = ProfileDyeView(ctx.author.id, item_id)
            view.message = await ctx.send("🎨 **เทผงสีรุ้งลงจานผสม** — เลือกสีที่จะย้อมโปรไฟล์ (ผงถูกใช้เมื่อยืนยัน):", view=view)
            return

        # 🔧 ชุดถอดอาร์ติแฟกต์: เปิดเมนูเลือกชิ้นที่จะถอด (ของถูกหักตอนเลือกใน view)
        if item_cfg and item_cfg.get("effect") == "artifact_remove":
            player = player_model.get_player(ctx.author.id)
            inv = player_model.load_inventory(player.get("inventory", ""))
            if str(item_id) not in inv:
                return await ctx.send(f"❌ คุณไม่มีไอเทมหมายเลข `{item_id}` ในกระเป๋า! (พิมพ์ `!bag` เพื่อเช็ก)")
            worn = game_modifiers.worn_artifacts(game_modifiers.parse_statuses(player))
            if not worn:
                return await ctx.send("❌ คุณยังไม่ได้สวมอาร์ติแฟกต์สักชิ้น — ไม่มีอะไรให้ถอด (ชุดถอดยังอยู่ครบ)")
            from bot.views.game_views import ArtifactRemoveView
            view = ArtifactRemoveView(ctx.author.id, item_id, worn)
            view.message = await ctx.send(
                f"🔧 **กางชุดถอดอาร์ติแฟกต์** — สวมอยู่ {len(worn)}/"
                f"{game_modifiers.artifact_slots(player)} ช่อง เลือกชิ้นที่จะถอด "
                "(ถอดแล้วของกลับเข้ากระเป๋า ชุดถอดถูกใช้ไป):", view=view)
            return

        # 🎫 ตั๋วเรือเหมาลำ: เปิดเมนูเลือกทวีป (ตั๋วถูกหักตอนยืนยันใน view ไม่ใช่ตอนนี้)
        if item_cfg and item_cfg.get("effect") == "choose_continent":
            player = player_model.get_player(ctx.author.id)
            inv = player_model.load_inventory(player.get("inventory", ""))
            if str(item_id) not in inv:
                return await ctx.send(f"❌ คุณไม่มีไอเทมหมายเลข `{item_id}` ในกระเป๋า! (พิมพ์ `!bag` เพื่อเช็ก)")
            if player.get("current_state") in ("fighting", "dead") or player.get("dungeon_steps", 0) > 0:
                return await ctx.send("❌ ตอนนี้ออกเรือไม่ได้! (ติดการต่อสู้/อยู่ในดันเจี้ยน — เคลียร์ให้จบก่อน)")
            from bot.views.game_views import ContinentWarpView
            view = ContinentWarpView(ctx.author.id, item_id)
            view.message = await ctx.send(
                "🎫 **กัปตันเรือเหมาลำกางแผนที่โลก** — เลือกทวีปปลายทางได้เลย (ตั๋วจะถูกใช้เมื่อยืนยัน):",
                view=view)
            return

        ok, msg = apply_item_effect(ctx.author.id, item_id)
        await ctx.send(msg, **file_kwargs(item_use_file(ok, item_id, ctx.author.id)))

    @adventure_room_only()   # P8: เซิร์ฟหลักใช้ได้เฉพาะมิติส่วนตัว
    @commands.command(name="drop")
    async def drop_item(self, ctx, item_id: str = None, amount: int = None):
        user_id = ctx.author.id
        player = player_model.get_player(user_id)
        
        if not player:
            return await ctx.send("❌ ไม่พบข้อมูลตัวละครของคุณ! พิมพ์ `!play` ก่อนนะ")

        # ---------------------------------------------------------
        # 1. 🧹 ถอดรหัสกระเป๋า (ใช้ Logic เดียวกับ !bag ของคุณอาเธอร์เป๊ะๆ)
        # ---------------------------------------------------------
        raw_inv = player.get("inventory", "")
        clean_inv = str(raw_inv)
        for char in ["(", ")", "[", "]", "'", '"', " "]:
            clean_inv = clean_inv.replace(char, "")
            
        inv_array = clean_inv.split(",") if clean_inv and clean_inv not in ["None", "null"] else []
        inv_array = [i for i in inv_array if i] # กันเหนียว กรองพวกค่าว่างที่อาจจะหลุดมาทิ้งไป
        
        capacity = player.get("capacity", 10)

        # ---------------------------------------------------------
        # 2. 🧳 กรณีที่พิมพ์แค่ !drop (แสดงรายการกระเป๋า)
        # ---------------------------------------------------------
        if item_id is None:
            item_counts = Counter(inv_array)
            
            embed = discord.Embed(title="🗑️ โยนไอเทมทิ้ง", color=discord.Color.red())
            embed.add_field(name="ความจุกระเป๋า", value=f"{len(inv_array)} / {'ไม่จำกัด' if capacity == 0 else capacity}", inline=False)
            
            if not inv_array:
                embed.description = "*~ กระเป๋าว่างเปล่า ไม่มีอะไรให้ทิ้ง ~*"
            else:
                drop_text = "💡 **วิธีใช้:** พิมพ์ `!drop [เลขไอเทม] [จำนวน]` เพื่อทิ้งของ\n\n**รายการที่มี:**\n"
                all_items = config_loader.get_all_items()
                for i_id, count in item_counts.items():
                    if i_id in all_items:
                        item_name = all_items[i_id]["name"]
                        drop_text += f"**[{i_id}]** {item_name} x`{count}`\n"
                    else:
                        drop_text += f"**[{i_id}]** ❓ ไอเทมปริศนา x`{count}`\n"
                embed.description = drop_text
                
            embed.set_thumbnail(url=ctx.author.display_avatar.url)
            return await ctx.send(embed=embed)

        # ---------------------------------------------------------
        # 3. 🗑️ กรณีที่พิมพ์เพื่อทิ้งของ (เช่น !drop 22 1)
        # ---------------------------------------------------------
        if amount is None or amount <= 0:
            return await ctx.send("❌ โปรดระบุจำนวนที่ต้องการทิ้งให้ถูกต้อง เช่น `!drop 22 1`")

        # ตรวจสอบว่าในกระเป๋ามีของนี้พอไหม
        current_count = inv_array.count(item_id)
        if current_count < amount:
            item_name = config_loader.get_item_config(item_id).get("name", f"ไอเทมรหัส {item_id}")
            return await ctx.send(f"❌ คุณมี {item_name} ไม่พอให้ทิ้ง! (ในกระเป๋ามีแค่ {current_count} ชิ้น)")

        # ทำการลบไอเทมตามจำนวนที่ระบุ
        for _ in range(amount):
            inv_array.remove(item_id)
            
        # บันทึกข้อมูลกลับลงฐานข้อมูล (inv_array เป็น list แล้ว update_player_field จะแปลงเป็น JSON ให้เอง)
        player_model.update_player_field(user_id, "inventory", inv_array)
        
        # แสดงข้อความยืนยัน
        item_name = config_loader.get_item_config(item_id).get("name", "ไอเทมปริศนา")
        await ctx.send(f"🗑️ คุณได้โยน **{item_name}** ทิ้งไปจำนวน `{amount}` ชิ้นเรียบร้อยแล้ว!")
    
    @adventure_room_only()   # P8: เซิร์ฟหลักใช้ได้เฉพาะมิติส่วนตัว
    @commands.command(name="give")
    async def give_item_to_player(self, ctx, member: discord.Member = None, item_id: str = None, amount: int = 1):
        # 1. เช็กความถูกต้องเบื้องต้น
        if member is None or item_id is None:
            return await ctx.send("❌ วิธีใช้: `!give @ชื่อเพื่อน [เลขไอเทม] [จำนวน]`\n💡 เช่น: `!give @Arthur 1 5`")
            
        if amount <= 0:
            return await ctx.send("❌ จำนวนไอเทมต้องมากกว่า 0!")
            
        if member.id == ctx.author.id:
            return await ctx.send("❌ คุณจะโอนของให้ตัวเองทำไมเนี่ย!")
            
        if member.bot:
            return await ctx.send("❌ บอทไม่ต้องการไอเทมของคุณหรอกนะ!")

        if not config_loader.get_item_config(item_id):
            return await ctx.send(f"❌ ไม่พบไอเทมรหัส `{item_id}` ในระบบ!")

        # 2. ดึงข้อมูลและถอดรหัสกระเป๋า "คนส่ง" (ตัวเราเอง)
        sender_id = ctx.author.id
        sender = player_model.get_player(sender_id)
        
        raw_inv_s = sender.get("inventory", "")
        clean_inv_s = str(raw_inv_s)
        for char in ["(", ")", "[", "]", "'", '"', " "]:
            clean_inv_s = clean_inv_s.replace(char, "")
        sender_inv = clean_inv_s.split(",") if clean_inv_s and clean_inv_s not in ["None", "null"] else []
        sender_inv = [i for i in sender_inv if i]

        # ตรวจสอบว่าคนส่งมีของพอไหม
        sender_item_count = sender_inv.count(item_id)
        item_name = config_loader.get_item_config(item_id)["name"]
        
        if sender_item_count < amount:
            return await ctx.send(f"❌ คุณมี {item_name} ไม่พอโอน! (ในกระเป๋าคุณมีแค่ {sender_item_count} ชิ้น)")

        # 3. ดึงข้อมูลและถอดรหัสกระเป๋า "คนรับ" (เพื่อน)
        receiver = player_model.get_player(member.id)
        if not receiver:
            return await ctx.send(f"❌ ไม่พบข้อมูลของ {member.display_name} ในระบบ (เขาต้องเคยพิมพ์เริ่มเล่นเกมก่อน)")

        raw_inv_r = receiver.get("inventory", "")
        clean_inv_r = str(raw_inv_r)
        for char in ["(", ")", "[", "]", "'", '"', " "]:
            clean_inv_r = clean_inv_r.replace(char, "")
        receiver_inv = clean_inv_r.split(",") if clean_inv_r and clean_inv_r not in ["None", "null"] else []
        receiver_inv = [i for i in receiver_inv if i]

        # เช็กความจุกระเป๋าคนรับ
        receiver_capacity = receiver.get("capacity", 10)
        if len(receiver_inv) + amount > receiver_capacity:
            free_space = receiver_capacity - len(receiver_inv)
            return await ctx.send(f"❌ กระเป๋าของ {member.display_name} เต็มแล้ว! (รับเพิ่มได้อีกแค่ {free_space} ชิ้น)")

        # 4. ทำการโอนย้ายไอเทม (หักจากเรา -> ย้ายไปเพื่อน)
        for _ in range(amount):
            sender_inv.remove(item_id)
            receiver_inv.append(item_id)

        # 5. บันทึกข้อมูลกลับลงฐานข้อมูลทั้ง 2 คน
        player_model.update_player_field(sender_id, "inventory", sender_inv)
        player_model.update_player_field(member.id, "inventory", receiver_inv)

        # 6. แจ้งเตือนความสำเร็จ
        await ctx.send(f"🤝 **โอนไอเทมสำเร็จ!**\nคุณได้มอบ `{item_name}` จำนวน `{amount}` ชิ้น ให้กับ {member.mention} เรียบร้อยแล้ว!")

    # ==========================================
    # ⚔️ คำสั่ง PVP (!att @ผู้ใช้)
    # ==========================================
    @allowed_channel("arena") # 🛠️ ใช้ Decorator บล็อกห้อง
    @not_arrested() # 🛠️ บล็อกคนติดคุก
    @main_server_only()   # P8: เซิร์ฟหลักเท่านั้น
    @commands.command(name="att")
    async def pvp_attack(self, ctx, member: discord.Member):
        # 1. ป้องกันการตีตัวเอง
        if member.id == ctx.author.id:
            return await ctx.send("❌ คุณไม่สามารถเปิดฉากโจมตีตัวเองได้!")

        # 2. เช็กสถานะผู้โจมตี (ต้องอยู่ในห้องเสียง)
        if not ctx.author.voice or not ctx.author.voice.channel:
            return await ctx.send(f"❌ {ctx.author.mention} **การประลองถูกยกเลิก!** คุณต้องอยู่ในห้องเสียงก่อนถึงจะท้าดวลได้!")

        # 3. เช็กสถานะเป้าหมาย (ต้องออนไลน์อยู่)
        if member.status == discord.Status.offline:
            return await ctx.send(f"⚠️ **ล้มเหลว!** เป้าหมาย {member.mention} ไม่ได้ออนไลน์อยู่! (ลูกผู้ชายเขาไม่ลอบโจมตีคนหลับกันหรอกนะ!)")
        
        # 4.เช็กว่าเป้าหมายต้องอยู่ในห้องเสียงด้วย
        if not member.voice or not member.voice.channel:
            return await ctx.send(f"⚠️ {member.mention} ไม่ได้อยู่ในห้องเสียง เลยท้าดวลไม่ได้นะ!")

        # โหลดข้อมูลผู้เล่นทั้งสองฝ่าย
        attacker = player_model.get_player(ctx.author.id)
        defender = player_model.get_player(member.id)
        
        if not attacker or not defender:
            return await ctx.send("❌ ไม่พบข้อมูลตัวละครของฝ่ายใดฝ่ายหนึ่งในฐานข้อมูล!")

        # 5. เช็กสถานะห้ามต่อสู้ (village หรือ death)
        if attacker.get("current_state") in ["village", "death"] or defender.get("current_state") in ["village", "death"]:
            return await ctx.send("❌ ไม่สามารถต่อสู้ได้เนื่องจากมีฝ่ายใดฝ่ายหนึ่งอยู่ในเซฟโซนหมู่บ้าน หรืออยู่ในสถานะเสียชีวิตแล้ว!")

        # 6. เช็กเงื่อนไขเลเวลต่ำกว่า 20
        pvp_min_level = int(config_loader.get_balance("pvp.min_level", 20))
        if attacker.get("level", 0) < pvp_min_level or defender.get("level", 0) < pvp_min_level:
            return await ctx.send(f"❌ ระบบ PVP รองรับเฉพาะผู้กล้าเลเวล {pvp_min_level} ขึ้นไปเท่านั้น! (และห้ามรังแกผู้เล่นเลเวลต่ำกว่านี้)")
        
        now = time.time()
        if ctx.author.id in self.pk_cooldowns:
            cooldown_end = self.pk_cooldowns[ctx.author.id]
            if now < cooldown_end:
                remaining = int(cooldown_end - now)
                minutes = remaining // 60
                seconds = remaining % 60
                return await ctx.send(f"⏳ **คุณอยู่ในช่วงพักทำใจหลังการสังหาร!** โปรดรออีก `{minutes} นาที {seconds} วินาที` จึงจะสั่งโจมตีครั้งถัดไปได้")
        
        #คำนวณความห่างของเลเวลเพื่อเพิ่มความยากในการทอย
        lv_diff = attacker.get("level", 0) - defender.get("level", 0)
        
        # แต้มเต๋าพื้นฐาน 1-20 บวกรวมแต้มโบนัสตามระดับเลเวล
        atk_bonus = lv_diff if lv_diff > 0 else 0
        def_bonus = abs(lv_diff) if lv_diff < 0 else 0

        atk_roll = random.randint(1, 20) + atk_bonus
        def_roll = random.randint(1, 20) + def_bonus

        # หาผู้ชนะจากการทอยเต๋า
        if atk_roll == def_roll:
            return await ctx.send(f"⚔️ **{ctx.author.display_name}** บุกโจมตี **{member.display_name}** แต่แต้มเต๋าเสมอกันที่ `{atk_roll}` แต้ม! ทั้งคู่ตั้งรับและปัดป้องอาวุธไว้ได้!")

        if atk_roll > def_roll:
            winner, loser = attacker, defender
            w_member, l_member = ctx.author, member
            base_dmg = atk_roll
        else:
            winner, loser = defender, attacker
            w_member, l_member = member, ctx.author
            base_dmg = def_roll

        # 4. คำนวณพลังโจมตีอาวุธผู้ชนะ และ พลังป้องกันเกราะผู้แพ้
        w_weapon = winner.get("weapon", "None")
        w_atk_bonus = config_loader.get_weapon_stats(w_weapon).get("atk", 0)

        l_armor = loser.get("armor", "None")
        l_def_bonus = int(config_loader.get_armor_stats(l_armor).get("hp", 0) * 0.2)

        # สรุปความเสียหายรวม (ขั้นต่ำ 1 ดาเมจ)
        final_damage = max(1, base_dmg + w_atk_bonus - l_def_bonus)
        
        # หักลบพลังชีวิตผู้แพ้
        loser_current_hp = loser.get("hp", 100)
        loser_new_hp = max(0, loser_current_hp - final_damage)
        player_model.update_player_field(l_member.id, "hp", loser_new_hp)

        # 5. เช็กผลการตาย (HP เหลือ 0) และการให้รางวัล
        death_status_text = ""
        reward_text = "" 

        if loser_new_hp <= 0:
            # --- 🏆 ระบบให้รางวัลผู้ชนะ ---
            reward_exp = int(config_loader.get_balance("pvp.reward_exp_base", 100)) + (loser.get("level", 1) * int(config_loader.get_balance("pvp.reward_exp_per_level", 1000)))
            reward_gold = int(config_loader.get_balance("pvp.reward_gold_base", 500)) + (loser.get("level", 1) * int(config_loader.get_balance("pvp.reward_gold_per_level", 500)))

            is_lvl_up, new_lvl, new_exp = player_model.add_exp(w_member.id, reward_exp)

            # ⚖️ ล่าค่าหัว (P4): ฝ่ายบุกฆ่าอาชญากร (สติติดลบ) = รับค่าหัว + เหยื่อชดใช้กรรม (สติรีเซ็ต 0)
            bounty = 0
            if loser is defender and defender.get("sanity", 100) < 0:
                bounty = game_modifiers.bounty_for(defender.get("sanity", 100))
                player_model.update_player_field(l_member.id, "sanity", 0)

            new_winner_cash = winner.get("cash", 0) + reward_gold + bounty
            player_model.update_player_field(w_member.id, "cash", new_winner_cash)

            lvl_up_msg = f"\n✨ **Level Up!** คุณเลเวลอัปเป็น {new_lvl}!" if is_lvl_up else ""
            reward_text = f"\n💰 **ได้รับรางวัล:** `{reward_gold}` ทอง | `EXP +{reward_exp}`{lvl_up_msg}"
            if bounty:
                reward_text += (f"\n🎯 **ล่าหัวสำเร็จ!** รับค่าหัว `{bounty:,}` ทอง — "
                                f"{l_member.mention} ชดใช้กรรมแล้ว (สติกลับเป็น 0 หลุดจากกระดานล่าหัว)")
            
            cooldown_seconds = random.randint(int(config_loader.get_balance("pvp.kill_cooldown_min_sec", 300)), int(config_loader.get_balance("pvp.kill_cooldown_max_sec", 600)))
            self.pk_cooldowns[ctx.author.id] = time.time() + cooldown_seconds
            player_model.update_player_field(l_member.id, "current_state", "death")
            death_status_text = f"\n💀 **☠️ สิ้นชีพ!** พลังชีวิตของ {l_member.mention} หมดลงและเข้าสู่สถานะเสียชีวิต!"

        # ==========================================
        # 🧠 6. ระบบสูญเสียสติ (Sanity) ของผู้โจมตี
        # ==========================================
        # ⚖️ P4: เป้าหมายเป็นอาชญากร (สติติดลบ) = ปราบโจรไม่บาป — ไม่เสียสติ ไม่มีเวรกรรม
        if defender.get("sanity", 100) < 0:
            if loser_new_hp <= 0 and loser is defender:
                hunter_sanity = min(100, attacker.get("sanity", 100) + int(config_loader.get_balance("bounty.hunt_sanity_reward", game_modifiers.BOUNTY_HUNT_SANITY_REWARD)))
                player_model.update_player_field(ctx.author.id, "sanity", hunter_sanity)
                sanity_text = f"\n🧠 **จิตใจผ่องใสจากการผดุงยุติธรรม** สติ `+{int(config_loader.get_balance("bounty.hunt_sanity_reward", game_modifiers.BOUNTY_HUNT_SANITY_REWARD))}` (ปัจจุบัน: {hunter_sanity})"
            else:
                sanity_text = "\n🧠 การไล่ล่าอาชญากรไม่ใช่บาป — สติไม่ลดลง"
            karma_text = ""
            new_sanity = 0  # sentinel: การล่าโจรไม่นับเป็นบาป — ข้ามเช็คสติแตกด้านล่างเสมอ (แม้นักล่าเองสติติดลบ)
        else:
            sanity_loss = int(config_loader.get_balance("pvp.sanity_loss_base", 5)) + int(attacker.get("level", 1) * float(config_loader.get_balance("pvp.sanity_loss_per_level", 0.25)))
            current_sanity = attacker.get("sanity", 100)
            new_sanity = current_sanity - sanity_loss

            # อัปเดตสติลงฐานข้อมูล
            player_model.update_player_field(ctx.author.id, "sanity", new_sanity)
            sanity_text = f"\n🧠 **สติสัมปชัญญะ (ผู้โจมตี):** ลดลง `{sanity_loss}` หน่วย (ปัจจุบัน: {new_sanity})"
            karma_text = ""

        # เช็กเงื่อนไขสติแตก (ค่าสติติดลบ) - จะเช็กเฉพาะตอนผู้โจมตีเป็นฝ่ายเปิด
        if new_sanity < 0:
            deficit = abs(new_sanity) 
            trigger_chance = min(0.90, 0.10 + (deficit * 0.02))
            
            if random.random() < trigger_chance:                
                event_type = random.choice(["arrest", "execute"])
                
                if event_type == "arrest":
                    jail_mins = int(config_loader.get_balance("pvp.jail_base_min", 10)) + (deficit * int(config_loader.get_balance("pvp.jail_per_deficit_min", 3)))
                    jail_until = time.time() + (jail_mins * 60)
                    
                    player_model.update_player_fields(ctx.author.id, {
                        "current_state": "arrested",
                        "arrest_until": jail_until
                    })
                    karma_text = f"\n\n🚨 **เวรกรรมตามสนอง!** ความคลุ้มคลั่งทำให้ {ctx.author.mention} ถูกจับเข้าคุกเป็นเวลา `{jail_mins}` นาที!"
                    
                elif event_type == "execute":
                    money_penalty = int(config_loader.get_balance("pvp.fine_base", 1000)) + (deficit * int(config_loader.get_balance("pvp.fine_per_deficit", 200)))
                    level_penalty = 1 + int(deficit / 10)
                    
                    atk_current_cash = attacker.get("cash", 0)
                    atk_current_level = attacker.get("level", 1)
                    
                    new_cash = max(0, atk_current_cash - money_penalty)
                    new_level = max(1, atk_current_level - level_penalty)
                    
                    player_model.update_player_fields(ctx.author.id, {
                        "cash": new_cash,
                        "level": new_level,
                        "current_state": "death",
                        "hp": 0
                    })
                    karma_text = f"\n\n⚖️ **ถูกทางการวิสามัญ!** {ctx.author.mention} คลุ้มคลั่งจนถูกทหารรักษาพระนครประหารชีวิต!\n💸 ถูกยึดทรัพย์ `{money_penalty}` ทอง และถูกลดเลเวลลง `{level_penalty}` ระดับ!"

        # 7. ส่งข้อความสรุปผลการประลอง (นำ Sanity Text เข้ามารวมแล้ว)
        embed = discord.Embed(
            title="⚔️ ผลการดวลศัสตราวุธ ลานประลอง ⚔️",
            description=f"**{w_member.display_name}** ทอยได้ `{base_dmg}` แต้ม ชนะการประลองในตานี้!\n"
                        f"💥 สร้างความเสียหายใส่ **{l_member.display_name}** จำนวน `💥 {final_damage}` หน่วย\n"
                        f"🩸 พลังชีวิตของ {l_member.display_name}: `{loser_current_hp}` ➔ `{loser_new_hp}`"
                        f"{death_status_text}"
                        f"{reward_text}"
                        f"\n{'-'*30}"
                        f"{sanity_text}"
                        f"{karma_text}",
            color=discord.Color.red()
        )
        await ctx.send(embed=embed)

    # ==========================================
    # 👻 ระบบดักจับวิญญาณ (ห้ามคนตายพิมพ์แชทช่องอื่น)
    # ==========================================
    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot:
            return

        player = player_model.get_player(message.author.id)
        if not player:
            return

        if player.get("current_state") == "death":
            # 1. ยกเว้น: ถ้าเป็นแชทโลก
            if message.channel.name == "⌒🌍chat╯แชทโลก":
                return
            
            # 2. ยกเว้น: ถ้าผู้เล่นพิมพ์ !use 28 เพื่อใช้ใบชุบ (เช็กจากข้อความ)
            if message.content.strip() == "!use 28":
                return # ปล่อยผ่านให้ระบบคำสั่งไปทำงานต่อเอง
            
            # 3. ถ้าไม่ใช่แชทโลก และไม่ใช่การพิมพ์ใช้ใบชุบ ให้ลบข้อความ
            try:
                await message.delete()
            except discord.Forbidden:
                pass
                
            # 4. ส่งข้อความเตือน (เช็กสถานะ last_event)
            if player.get("last_event") != "death_warned":
                view = DeathRespawnView(message.author.id)
                warning_msg = await message.channel.send(
                    f"👻 {message.author.mention} **คุณเสียชีวิตอยู่!** วิญญาณไม่สามารถสื่อสารในช่องทางนี้ได้\n"
                    f"ต้องการจ่ายเงิน `1,000` ทอง เพื่อกลับไปเกิดใหม่ หรือใช้ใบชุบชีวิต (`!use 28`) หรือไม่?",
                    view=view, **file_kwargs(event_image("death"))
                )
                view.message = warning_msg
                player_model.update_player_field(message.author.id, "last_event", "death_warned")

    # 📜 คำสั่งเช็กสูตรคราฟ (ปรับให้ดึงจากโครงสร้างใหม่)
    @adventure_room_only()   # P8: เซิร์ฟหลักใช้ได้เฉพาะมิติส่วนตัว
    @commands.command(name="recipes")
    async def show_recipes(self, ctx):
        msg = "📜 **สูตรการคราฟไอเทม (พิมพ์ `!craft [เลขไอเทม]` เพื่อเริ่มคราฟ):**\n"
        all_items = config_loader.get_all_items()
        for item_id in all_items:
            data = config_loader.get_crafting_recipe(item_id)
            if not data:
                continue
            name = all_items[item_id]['name']
            recipe = data["recipe"]
            fail_rate = int(data["fail_rate"] * 100)
            ing_list = [f"{all_items[ing_id]['name']} x{amt}" for ing_id, amt in recipe.items()]
            # เพิ่ม [ID: item_id] เข้าไปหน้าชื่อ
            msg += f"• **[ID: {item_id}] {name}** (Fail: {fail_rate}%): ใช้ {', '.join(ing_list)}\n"
        await ctx.send(msg)

    # 🛠️ คำสั่งคราฟไอเทม (ปรับให้ใช้ fail_rate ของแต่ละไอเทม)
    @adventure_room_only()   # P8: เซิร์ฟหลักใช้ได้เฉพาะมิติส่วนตัว
    @commands.command(name="craft")
    async def craft_item(self, ctx, item_id: str = None):
        _ok, msg = craft_for(ctx.author.id, item_id)
        await ctx.send(msg)
            
    # สแกนผู้เล่นว่าตีได้หรือไม่
    @allowed_channel("arena") # 🛠️ ใช้ Decorator บล็อกห้อง
    @not_arrested() # 🛠️ บล็อกคนติดคุก
    @main_server_only()   # P8: เซิร์ฟหลักเท่านั้น
    @commands.command(name="scan")
    async def scan_target(self, ctx, member: discord.Member):
        # 1. โหลดข้อมูลเป้าหมายจาก DB
        target = player_model.get_player(member.id)
        if not target:
            return await ctx.send(f"❌ ไม่พบข้อมูลของ {member.name} ในฐานข้อมูล!")

        # 2. ตรวจสอบสถานะและเงื่อนไข
        lvl = target.get("level", 1)
        state = target.get("current_state", "unknown")
        is_online = member.status != discord.Status.offline
        in_voice = member.voice is not None
        
        # 3. สรุปผล
        can_attack = (lvl >= 20 and state not in ["village", "death"] and is_online and in_voice)
        
        status_msg = (
            f"🔍 **รายงานการสแกนเป้าหมาย: {member.name}**\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"📊 **เลเวล:** {lvl} {'✅' if lvl >= 20 else '❌'}\n"
            f"📍 **สถานที่:** {state} {'✅' if state not in ['village', 'death'] else '❌'}\n"
            f"🟢 **ออนไลน์:** {'ใช่' if is_online else 'ไม่ใช่'} {'✅' if is_online else '❌'}\n"
            f"🎧 **อยู่ในห้องเสียง:** {'ใช่' if in_voice else 'ไม่ใช่'} {'✅' if in_voice else '❌'}\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"⚔️ **ผลลัพธ์:** {'**[ตีได้! ล่าได้เลย!]**' if can_attack else '**[ยังตีไม่ได้/เงื่อนไขไม่ครบ]**'}"
        )
        
        await ctx.send(status_msg)

# 🚨 ลบอันที่ซ้ำออกเหลือแค่อันเดียว
async def setup(bot):
    await bot.add_cog(PlayerCommands(bot))

# 🧱 sell_all_junk ย้ายไป core/services/items.py แล้ว — เหลือสะพานไว้ตรงนี้
from core.services.items import sell_all_junk  # noqa: F401


# 🔨 craft_for/craftable_now ย้ายไป core/services/crafting.py แล้ว — เหลือสะพานไว้ตรงนี้
from core.services.crafting import craft_for, craftable_now  # noqa: F401


# 🛒 buy_item_for/sell_item_for/drop_item_for ย้ายไป core/services/items.py แล้ว — เหลือสะพานไว้ตรงนี้
from core.services.items import MAX_BUY_AT_ONCE, buy_item_for, sell_item_for, drop_item_for  # noqa: F401


# ===== 🏆 อันดับรวม (O6) — 6 คำสั่งเดิมยุบเหลือ !top หน้าเดียว =====

TOP_KINDS = {
    "rich":  ("💰 เศรษฐี", "ทอง", lambda v: f"{v:,} ทอง"),
    "level": ("⭐ เลเวล", "Lv.", lambda v: f"Lv. {v:,}"),
    "text":  ("💬 นักแชท", "ข้อความ", lambda v: f"{v:,} ข้อความ"),
    "time":  ("🎙️ เวลาออนไลน์", "ชั่วโมง", lambda v: f"{int(v) // 3600:,} ชม. {int(v) % 3600 // 60} นาที"),
    "weekly": ("🗓️ นักผจญภัยแห่งสัปดาห์", "แต้ม", lambda v: f"{v:,} แต้ม"),
}
# 🏅 MEDALS ย้ายไป core/services/codex.py แล้ว (ใช้ร่วมกับ build_top_embed ด้านล่าง) — เหลือสะพานไว้ตรงนี้
from core.services.codex import MEDALS  # noqa: F401


def build_top_embed(kind, viewer_id=None):
    """หน้าอันดับหมวดเดียว + บอกอันดับของคนดูด้วย"""
    title, _unit, fmt = TOP_KINDS.get(kind, TOP_KINDS["rich"])
    rows = player_model.get_leaderboard(kind, 10)
    embed = discord.Embed(title=f"🏆 อันดับ {title} — TOP 10", color=0xf1c40f)
    if not rows:
        embed.description = "*ยังไม่มีข้อมูลผู้เล่น*"
    else:
        lines = []
        for i, (uid, value) in enumerate(rows):
            badge = MEDALS[i] if i < 3 else f"`{i + 1:>2}.`"
            me = " ⬅️ **คุณ**" if uid == viewer_id else ""
            lines.append(f"{badge} <@{uid}> — {fmt(value or 0)}{me}")
        embed.description = "\n".join(lines)
    if viewer_id:
        mine = player_model.get_my_rank(viewer_id, kind)
        if mine:
            rank, value, total = mine
            embed.add_field(name="📍 อันดับของคุณ",
                            value=f"อันดับ **{rank:,}** จาก {total:,} คน · {fmt(value or 0)}", inline=False)
    if kind == "weekly":
        rewards = config_loader.get_weekly_ranking("rewards", []) or []
        if rewards:
            embed.add_field(
                name="🎁 รางวัลตอนปิดสัปดาห์ (เข้าธนาคารอัตโนมัติ)",
                value=" · ".join(f"{m} {int(r.get('gold', 0)):,} ทอง"
                                 for m, r in zip(MEDALS, rewards)),
                inline=False)
        import datetime
        left = 7 - datetime.date.today().weekday()      # จันทร์=0 → เหลือ 7 วัน, อาทิตย์=6 → เหลือ 1
        embed.set_footer(text=f"แต้ม = EXP ที่หาได้ในสัปดาห์นี้ · ปิดอันดับอีก {left} วัน (เช้าวันจันทร์)")
    else:
        embed.set_footer(text="กดปุ่มด้านล่างเพื่อสลับหมวด")
    return embed
