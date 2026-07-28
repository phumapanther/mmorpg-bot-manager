# ⚔️ กิลด์วอร์ (P7) — !warguild ท้าศึก + เดิมพันคลังกิลด์ → ห้องรบ 30 นาที → !fight เก็บแต้ม
# ห้องลบเองเมื่อเงียบ 1 นาที (แบบ !adv) | ผู้ชนะรับกองกลาง 2×เดิมพัน | เดิมพันจดลง DB กันบอทรีสตาร์ทกลางศึก
import random
import time

import discord
from discord.ext import commands, tasks
from bot.utils import is_main_server

import bot.models.player_model as player_model
from bot import config_loader
from bot.cogs.guild import GUILD_CATEGORY, _is_leader

# ค่าพื้นฐาน (fallback) — ตั้งจริงที่ Panel: game_balance.guild_war.*
WAR_DURATION = 30 * 60      # ศึกยาว 30 นาที
IDLE_TIMEOUT = 60           # ห้องเงียบ 1 นาที = เตือนก่อน (ยังสู้ต่อได้!)
IDLE_GRACE = 30             # หลังเตือน ถ้ายังเงียบต่ออีกเท่านี้ค่อยจบศึกจริง
FIGHT_COOLDOWN = 10         # วินาทีต่อคน

# (ชนิด, โอกาส%, แต้ม, ฝั่งที่โดน: "me"=ได้แต้ม / "enemy"=ศัตรูโดนหัก, ความยากโบนัสเต๋าศัตรู)
DEFAULT_ENCOUNTERS = [
    ("soldier", 60, 1, "me", 0),
    ("leader", 15, 10, "me", 5),
    ("fort", 20, -10, "enemy", 3),
    ("castle", 5, -100, "enemy", 8),
]


def war_duration():
    return int(config_loader.get_balance("guild_war.duration_min", 30)) * 60


def idle_warn():
    return int(config_loader.get_balance("guild_war.idle_warn_sec", IDLE_TIMEOUT))


def idle_grace():
    return int(config_loader.get_balance("guild_war.idle_grace_sec", IDLE_GRACE))


def fight_cooldown():
    return int(config_loader.get_balance("guild_war.fight_cooldown_sec", FIGHT_COOLDOWN))


def encounters():
    """ตารางเป้าหมายในศึก — โอกาส/แต้มตั้งได้ที่ Panel (ไม่ตั้ง = ค่าเริ่มต้น)"""
    chances = config_loader.get_balance("guild_war.chances", {}) or {}
    points = config_loader.get_balance("guild_war.points", {}) or {}
    out = []
    for key, ch, pt, side, diff in DEFAULT_ENCOUNTERS:
        out.append((key, int(chances.get(key, ch)), int(points.get(key, pt)), side, diff))
    return out


def roll_encounter(rng=None):
    rng = rng or random
    table = encounters()
    keys = [e[0] for e in table]
    weights = [e[1] for e in table]
    key = rng.choices(keys, weights=weights, k=1)[0]
    return next(e for e in table if e[0] == key)


def apply_encounter(scores, my_gid, enemy_gid, encounter):
    """อัปเดตสกอร์ตามผลชนะ — คืนข้อความสรุปแต้ม"""
    _key, _w, points, target, _diff = encounter
    if target == "me":
        scores[my_gid] += points
        return f"แต้มกิลด์เรา `+{points}`"
    scores[enemy_gid] += points  # points ติดลบ = หักศัตรู
    return f"แต้มกิลด์ศัตรู `{points}`"


class ActiveWar:
    def __init__(self, channel_id, guild_a, guild_b, stake, origin_channel_id=None):
        self.channel_id = channel_id
        self.origin_channel_id = origin_channel_id  # ห้องที่ใช้คำสั่งท้าศึก — ประกาศผลที่นี่เสมอ
        self.info = {guild_a["guild_id"]: guild_a, guild_b["guild_id"]: guild_b}
        self.scores = {guild_a["guild_id"]: 0, guild_b["guild_id"]: 0}
        self.stake = stake
        self.ends_at = time.time() + war_duration()
        self.last_activity = time.time()
        self.warned_at = None   # เวลาแจ้งเตือนห้องเงียบ — None = ยังไม่เตือน/มีคนกลับมาแล้ว
        self.cooldowns = {}

    def enemy_of(self, gid):
        a, b = self.scores.keys()
        return b if gid == a else a


class WarChallengeView(discord.ui.View):
    def __init__(self, cog, target_leader_id, my_guild, enemy_guild, stake):
        super().__init__(timeout=120)
        self.cog = cog
        self.target_leader_id = target_leader_id
        self.my_guild = my_guild
        self.enemy_guild = enemy_guild
        self.stake = stake

    async def interaction_check(self, interaction):
        if interaction.user.id != self.target_leader_id:
            await interaction.response.send_message("❌ คำท้านี้ไม่ใช่ของคุณ!", ephemeral=True)
            return False
        return True

    @discord.ui.button(label="⚔️ รับคำท้า!", style=discord.ButtonStyle.danger)
    async def accept(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        msg = await self.cog.start_war(interaction, self.my_guild, self.enemy_guild, self.stake)
        await interaction.edit_original_response(content=msg, view=None)

    @discord.ui.button(label="🕊️ ปฏิเสธ", style=discord.ButtonStyle.secondary)
    async def decline(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.edit_message(content="🕊️ คำท้าถูกปฏิเสธ — สันติภาพยังคงอยู่", view=None)


class GuildWarCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.wars = {}  # channel_id -> ActiveWar
        # 💸 คืนเดิมพันศึกที่ตายเพราะรีสตาร์ท (จดไว้ใน DB) + จำห้องรบกำพร้าไว้ลบตอน ready
        self._orphan_channels = []
        for cid, ga, gb, stake in player_model.pop_all_war_stakes():
            self._orphan_channels.append(cid)
            if stake:
                player_model.guild_add_treasury(ga, stake)
                player_model.guild_add_treasury(gb, stake)
        self.watch_wars.start()
        print("[LOG] [LOAD_COG] โหลดโมดูลกิลด์วอร์เรียบร้อยแล้ว")

    def cog_unload(self):
        self.watch_wars.cancel()

    # ── เปิดศึก ──
    @commands.command(name="warguild", aliases=["วอกิลด์"])
    async def warguild(self, ctx, member: discord.Member = None, stake: int = 0):
        g = _is_leader(ctx.author.id)
        if not g:
            return await ctx.send("❌ เฉพาะหัวหน้ากิลด์เท่านั้นที่ประกาศสงครามได้!")
        if member is None:
            return await ctx.send("❓ วิธีใช้: `!warguild @หัวหน้ากิลด์อื่น [เดิมพันคลัง]` เช่น `!warguild @Boss 1000000`")
        enemy = _is_leader(member.id)
        if not enemy or enemy["guild_id"] == g["guild_id"]:
            return await ctx.send("❌ เป้าหมายต้องเป็น **หัวหน้ากิลด์อื่น** เท่านั้น!")
        if any(g["guild_id"] in w.scores or enemy["guild_id"] in w.scores for w in self.wars.values()):
            return await ctx.send("❌ มีศึกที่เกี่ยวข้องกับกิลด์ใดกิลด์หนึ่งดำเนินอยู่แล้ว!")
        if stake < 0:
            return await ctx.send("❌ เดิมพันต้องไม่ติดลบ!")
        if stake and (g["treasury"] < stake or enemy["treasury"] < stake):
            return await ctx.send(f"❌ คลังกิลด์ทั้งสองฝ่ายต้องมีอย่างน้อย `{stake:,}` ทองเพื่อวางเดิมพัน!")
        stake_text = f"\n💰 เดิมพันคลังกิลด์ฝ่ายละ `{stake:,}` ทอง — ผู้ชนะรับทั้งกองกลาง `{stake * 2:,}`!" if stake else "\n🏅 ศึกชิงเกียรติยศ (ไม่มีเดิมพัน)"
        await ctx.send(
            f"⚔️ {member.mention} — **{g['icon']} {g['name']}** ประกาศสงครามต่อ **{enemy['icon']} {enemy['name']}**!{stake_text}",
            view=WarChallengeView(self, member.id, g, enemy, stake))

    async def start_war(self, interaction, guild_a, guild_b, stake):
        """รับคำท้าแล้ว: หักเดิมพัน + สร้างห้องรบ + เปิดศึก — คืนข้อความผลลัพธ์"""
        guild_a = player_model.get_guild_of(guild_a["leader_id"])
        guild_b = player_model.get_guild_of(guild_b["leader_id"])
        if not guild_a or not guild_b:
            return "❌ กิลด์ฝ่ายใดฝ่ายหนึ่งหายไปแล้ว — ศึกยกเลิก"
        if stake:
            if player_model.guild_add_treasury(guild_a["guild_id"], -stake) is None:
                return "❌ คลังฝ่ายท้ามีไม่พอแล้ว — ศึกยกเลิก"
            if player_model.guild_add_treasury(guild_b["guild_id"], -stake) is None:
                player_model.guild_add_treasury(guild_a["guild_id"], stake)  # คืนฝ่ายแรก
                return "❌ คลังฝ่ายรับมีไม่พอแล้ว — ศึกยกเลิก"
        role_a = interaction.guild.get_role(guild_a["role_id"])
        role_b = interaction.guild.get_role(guild_b["role_id"])
        try:
            category = discord.utils.get(interaction.guild.categories, name=GUILD_CATEGORY)
            overwrites = {interaction.guild.default_role: discord.PermissionOverwrite(view_channel=False),
                          interaction.guild.me: discord.PermissionOverwrite(view_channel=True)}
            for role in (role_a, role_b):
                if role:
                    overwrites[role] = discord.PermissionOverwrite(view_channel=True, send_messages=True)
            channel = await interaction.guild.create_text_channel(
                f"⚔️︱{guild_a['name']}-vs-{guild_b['name']}", category=category, overwrites=overwrites)
        except discord.Forbidden:
            if stake:  # สร้างห้องไม่ได้ = คืนเดิมพัน
                player_model.guild_add_treasury(guild_a["guild_id"], stake)
                player_model.guild_add_treasury(guild_b["guild_id"], stake)
            return "❌ บอทไม่มีสิทธิ์สร้างห้องรบ (Manage Channels) — ศึกยกเลิก คืนเดิมพันแล้ว"

        player_model.record_war_stake(channel.id, guild_a["guild_id"], guild_b["guild_id"], stake)
        self.wars[channel.id] = ActiveWar(channel.id, guild_a, guild_b, stake,
                                          origin_channel_id=interaction.channel.id)
        await channel.send(embed=discord.Embed(
            title=f"⚔️ สงคราม {guild_a['icon']} {guild_a['name']} ⚡ {guild_b['icon']} {guild_b['name']}",
            color=0xe74c3c,
            description=(f"🕰️ ศึกยาว **30 นาที** — เงียบเกิน 1 นาทีจะมี**คำเตือน** ถ้ายังเงียบต่ออีก 30 วิ ศึกจบด้วยสกอร์ปัจจุบัน\n"
                         + (f"💰 กองกลางเดิมพัน `{stake * 2:,}` ทอง — ผู้ชนะรับไปทั้งก้อน!\n" if stake else "🏅 ศึกชิงเกียรติยศ\n")
                         + "\n**วิธีเล่น:** พิมพ์ `!fight` เพื่อออกปะทะ!\n"
                         "⚔️ ทหารศัตรู ชนะ `+1` | 👑 หัวหน้าศัตรู `+10`\n"
                         "🛡️ ป้อมศัตรู = แต้มศัตรู `-10` | 🏰 ปราสาทศัตรู = แต้มศัตรู `-100`\n"
                         f"(คูลดาวน์ {FIGHT_COOLDOWN} วิ/คน — แพ้เต๋าไม่เสียอะไร แต่เสียเวลา!)")))
        return f"⚔️ **สงครามเริ่มแล้ว!** เข้าสนามรบที่ {channel.mention}"

    # ── สู้ ──
    @commands.command(name="fight", aliases=["สู้ศึก"])
    async def fight(self, ctx):
        war = self.wars.get(ctx.channel.id)
        if not war:
            return  # ไม่ใช่ห้องรบ — เงียบไว้ไม่รกห้องอื่น
        my_guild = player_model.get_guild_of(ctx.author.id)
        if not my_guild or my_guild["guild_id"] not in war.scores:
            return await ctx.send("❌ คุณไม่ใช่ทหารของกิลด์คู่สงครามนี้!")
        now = time.time()
        if now - war.cooldowns.get(ctx.author.id, 0) < fight_cooldown():
            remain = fight_cooldown() - (now - war.cooldowns[ctx.author.id])
            return await ctx.send(f"⏳ พักหายใจก่อน! อีก `{remain:.0f}` วิค่อยบุกใหม่", delete_after=5)
        war.cooldowns[ctx.author.id] = now
        war.last_activity = now

        my_gid = my_guild["guild_id"]
        enemy_gid = war.enemy_of(my_gid)
        enemy_info = war.info[enemy_gid]
        encounter = roll_encounter()
        key, _w, _pts, _target, difficulty = encounter

        # ตั้งชื่อเป้าหมาย — ทหาร/หัวหน้าใช้ชื่อคนจริงของกิลด์ศัตรู
        if key == "soldier":
            members = [m for m in player_model.get_guild_members(enemy_gid) if m != enemy_info["leader_id"]]
            target_name = f"⚔️ ทหาร <@{random.choice(members)}>" if members else "⚔️ ทหารนิรนามกิลด์ศัตรู"
        elif key == "leader":
            target_name = f"👑 หัวหน้ากิลด์ <@{enemy_info['leader_id']}>"
        elif key == "fort":
            target_name = f"🛡️ ป้อมปราการแห่ง {enemy_info['icon']} {enemy_info['name']}"
        else:
            target_name = f"🏰 ปราสาทหลวงแห่ง {enemy_info['icon']} {enemy_info['name']}"

        player = player_model.get_player(ctx.author.id)
        my_roll = random.randint(1, 20) + int(player.get("level", 1) * 0.25)
        enemy_roll = random.randint(1, 20) + difficulty
        a_gid, b_gid = war.scores.keys()

        if my_roll > enemy_roll:
            result = apply_encounter(war.scores, my_gid, enemy_gid, encounter)
            outcome = f"🎉 **ชัยชนะ!** ({my_roll} vs {enemy_roll}) — {result}"
        else:
            outcome = f"💥 **พ่ายแพ้...** ({my_roll} vs {enemy_roll}) — ถอยมาตั้งหลักก่อน!"

        score_line = " : ".join(
            f"{war.info[g]['icon']} `{war.scores[g]}`" for g in (a_gid, b_gid))
        remain_min = max(0, int((war.ends_at - now) / 60))
        await ctx.send(f"{ctx.author.mention} บุกปะทะ {target_name}\n{outcome}\n"
                       f"📊 สกอร์: {score_line} | ⏳ เหลือ ~{remain_min} นาที")

    # ── จบศึก ──
    @tasks.loop(seconds=15)
    async def watch_wars(self):
        now = time.time()
        for cid, war in list(self.wars.items()):
            if now > war.ends_at:
                await self.end_war(war, "⏰ ครบ 30 นาที — หมดเวลาสงคราม!")
                continue
            # มีคนกลับมาขยับหลังโดนเตือน = ยกเลิกนับถอยหลัง ศึกดำเนินต่อ
            if war.warned_at and war.last_activity > war.warned_at:
                war.warned_at = None
            if now - war.last_activity > idle_warn():
                if war.warned_at is None:
                    war.warned_at = now
                    battlefield = self.bot.get_channel(cid)
                    if battlefield:
                        try:
                            await battlefield.send(
                                "⚠️ **สนามรบเงียบเชียบ...** ถ้าไม่มีใครขยับภายใน **30 วินาที** ศึกจะยุติด้วยสกอร์ปัจจุบัน!\n"
                                "พิมพ์ `!fight` (หรืออะไรก็ได้) เพื่อสู้ต่อ!")
                        except Exception:
                            pass
                elif now - war.warned_at > idle_grace():
                    await self.end_war(war, "🍂 สนามรบเงียบจนสิ้นเสียงดาบ — สงครามยุติ")

    @watch_wars.before_loop
    async def _wait_ready(self):
        await self.bot.wait_until_ready()

    @commands.Cog.listener()
    async def on_ready(self):
        # 🧹 ลบห้องรบกำพร้าจากศึกที่ตายกลางคัน (เช่น รีสตาร์ทช่วงนับถอยหลังสลายห้อง)
        for cid in self._orphan_channels:
            channel = self.bot.get_channel(cid)
            if channel:
                try:
                    await channel.delete(reason="เก็บกวาดห้องรบค้างจากรีสตาร์ท")
                    print(f"🧹 [Guild War] ลบห้องรบค้าง: {cid}")
                except Exception as e:
                    print(f"⚠️ [Guild War] ลบห้องรบค้าง {cid} ไม่สำเร็จ: {e}")
        self._orphan_channels = []

    @commands.Cog.listener()
    async def on_message(self, message):
        war = self.wars.get(getattr(message.channel, "id", None))
        if war and not message.author.bot:
            war.last_activity = time.time()

    async def end_war(self, war, reason):
        self.wars.pop(war.channel_id, None)
        stake_row = player_model.pop_war_stake(war.channel_id)
        a_gid, b_gid = war.scores.keys()
        sa, sb = war.scores[a_gid], war.scores[b_gid]
        ia, ib = war.info[a_gid], war.info[b_gid]
        if sa == sb:
            headline = "⚖️ **เสมอกัน!** ทั้งสองกิลด์รักษาเกียรติไว้ได้"
            if stake_row and stake_row[2]:
                player_model.guild_add_treasury(a_gid, stake_row[2])
                player_model.guild_add_treasury(b_gid, stake_row[2])
                headline += " — คืนเดิมพันทั้งสองฝ่าย"
        else:
            win_gid = a_gid if sa > sb else b_gid
            w = war.info[win_gid]
            headline = f"🏆 **{w['icon']} {w['name']} ชนะสงคราม!**"
            if stake_row and stake_row[2]:
                pot = stake_row[2] * 2
                player_model.guild_add_treasury(win_gid, pot)
                headline += f" รับกองกลาง `{pot:,}` ทองเข้าคลังกิลด์!"
        summary = (f"{reason}\n{headline}\n"
                   f"📊 สกอร์สุดท้าย: {ia['icon']} {ia['name']} `{sa}` : `{sb}` {ib['icon']} {ib['name']}")
        # 📯 ประกาศผลที่ "ห้องที่ใช้คำสั่งท้าศึก" เสมอ — ทุกกรณีจบศึก (หมดเวลา/ห้องเงียบ)
        origin = self.bot.get_channel(war.origin_channel_id) if war.origin_channel_id else None
        if origin:
            try:
                await origin.send(f"📯 **ข่าวสงครามกิลด์**\n{summary}")
            except Exception:
                pass
        battlefield = self.bot.get_channel(war.channel_id)
        if battlefield:
            # ส่งข้อความลาพลาดก็ต้องลบห้องให้ได้ — แยก try กัน
            try:
                await battlefield.send(summary + "\n\n🔒 สกอร์ล็อกแล้ว — 💨 ห้องรบจะสลายใน 30 วินาที...")
            except Exception:
                pass
            try:
                import asyncio
                await asyncio.sleep(30)
                await battlefield.delete(reason="สงครามจบ")
            except Exception as e:
                print(f"⚠️ [Guild War] ลบห้องรบ {war.channel_id} ไม่สำเร็จ: {e}")


async def setup(bot):
    await bot.add_cog(GuildWarCog(bot))

    async def cog_check(self, ctx):
        """P8: ฟีเจอร์นี้เล่นได้เฉพาะเซิร์ฟหลัก (เซิร์ฟรองเล่นได้แค่ผจญภัย)"""
        return is_main_server(ctx)
