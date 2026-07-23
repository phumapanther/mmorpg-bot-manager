"""คำสั่งแอดมินควบคุมโลก (กลุ่มสิทธิ์ admin / เจ้าของเซิร์ฟเท่านั้น)

- !settheme      ล็อก/ปลดล็อกธีมรายสัปดาห์ (persist ข้าม restart ผ่านตาราง weekly_state)
- !setcontinent  ย้ายทวีปรายคน / ทุกคน
- !setstatus     เสก/ล้างสถานะติดตัวรายคน / ทุกคน
"""
from discord.ext import commands

import bot.models.player_model as player_model
from bot import game_modifiers
from bot.cogs import weekly_event
from bot.utils import has_permission


def load_theme_override():
    """อ่านธีมที่ถูกล็อกไว้จาก DB เข้า game_modifiers (เรียกตอนบอทสตาร์ท)"""
    saved = weekly_event.get_state("theme_override")
    game_modifiers.THEME_OVERRIDE = saved or None


class WorldAdmin(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        load_theme_override()

    # ==================== 🎪 ธีมรายสัปดาห์ ====================
    @commands.command(name="settheme")
    @has_permission("admin")
    async def set_theme(self, ctx, key: str = None):
        if key is None:
            current = game_modifiers.get_weekly_theme()
            if game_modifiers.THEME_OVERRIDE:
                state = f"🔒 ธีมถูกล็อกอยู่ที่: **{current['label']}**"
            else:
                state = f"🎲 สุ่มอัตโนมัติรายสัปดาห์ (สัปดาห์นี้: **{current['label']}**)"
            lines = "\n".join(f"`{t['key']}` — {t['label']}" for t in game_modifiers.WEEKLY_THEMES)
            return await ctx.send(f"🎪 **ธีมทั้งหมด:**\n{lines}\n\n{state}\nใช้: `!settheme <key>` ล็อกธีม · `!settheme auto` กลับสู่การสุ่ม")

        if key.lower() == "auto":
            game_modifiers.THEME_OVERRIDE = None
            weekly_event.set_state("theme_override", "")
            current = game_modifiers.get_weekly_theme()
            return await ctx.send(f"🎲 ปลดล็อกธีมแล้ว — กลับสู่การสุ่มรายสัปดาห์ปกติ (สัปดาห์นี้: **{current['label']}**)")

        theme = game_modifiers.get_theme_by_key(key)
        if not theme:
            return await ctx.send(f"❌ ไม่พบธีม `{key}` — พิมพ์ `!settheme` ดูรายชื่อทั้งหมด")
        game_modifiers.THEME_OVERRIDE = key
        weekly_event.set_state("theme_override", key)
        await ctx.send(
            f"🔒 ล็อกธีมเป็น **{theme['label']}** แล้ว — มีผลทันที และค้างไว้จนกว่าจะสั่ง `!settheme auto`\n"
            f"📜 {theme['description']}"
        )

    # ==================== 🗺️ ทวีป ====================
    @commands.command(name="setcontinent")
    @has_permission("admin")
    async def set_continent(self, ctx, key: str = None, target: str = None):
        if key is None:
            lines = "\n".join(f"`{k}` — {c['label']}" for k, c in game_modifiers.CONTINENTS.items())
            return await ctx.send(f"🗺️ **ทวีปทั้งหมด:**\n{lines}\n\nใช้: `!setcontinent <key> @คน` หรือ `!setcontinent <key> all`")

        if key not in game_modifiers.CONTINENTS:
            return await ctx.send(f"❌ ไม่พบทวีป `{key}` — พิมพ์ `!setcontinent` ดูรายชื่อ")
        label = game_modifiers.CONTINENTS[key]["label"]

        if target and target.lower() == "all":
            player_model.execute_raw_sql("UPDATE players SET continent = ?", (key,))
            return await ctx.send(f"🌀 เทเลพอร์ตผู้เล่น**ทุกคน**ไปยัง {label} เรียบร้อย!")

        if ctx.message.mentions:
            member = ctx.message.mentions[0]
            player_model.get_player(member.id)  # สร้างแถวถ้ายังไม่เคยเล่น
            player_model.update_player_field(member.id, "continent", key)
            return await ctx.send(f"🌀 ส่งตัว {member.mention} ไปยัง {label} เรียบร้อย!")

        await ctx.send("❌ ระบุเป้าหมาย: `@คน` หรือ `all`")

    # ==================== 🧬 สถานะติดตัว ====================
    @commands.command(name="setstatus")
    @has_permission("admin")
    async def set_status(self, ctx, key: str = None, arg1: str = None, arg2: str = None):
        if key is None:
            lines = "\n".join(
                f"`{k}` — {cfg['label']} (default {cfg.get('default_turns', 1)} {'ไฟต์' if cfg.get('tick') == 'fight' else 'ก้าว'})"
                for k, cfg in game_modifiers.STATUS_EFFECTS.items()
            )
            return await ctx.send(
                f"🧬 **สถานะทั้งหมด:**\n{lines}\n\n"
                f"ใช้: `!setstatus <key> [เทิร์น] @คน|all` · ล้าง: `!setstatus clear @คน|all`"
            )

        args = [a for a in (arg1, arg2) if a]
        turns = next((int(a) for a in args if a.isdigit()), None)
        is_all = any(a.lower() == "all" for a in args)
        mention = ctx.message.mentions[0] if ctx.message.mentions else None
        if not is_all and not mention:
            return await ctx.send("❌ ระบุเป้าหมาย: `@คน` หรือ `all`")

        if key.lower() == "clear":
            if is_all:
                player_model.execute_raw_sql("UPDATE players SET status_effects = ?", ("{}",))
                return await ctx.send("✨ ล้างสถานะผู้เล่น**ทุกคน**เรียบร้อย!")
            player_model.get_player(mention.id)
            player_model.update_player_field(mention.id, "status_effects", {})
            return await ctx.send(f"✨ ล้างสถานะของ {mention.mention} เรียบร้อย!")

        if key not in game_modifiers.STATUS_EFFECTS:
            return await ctx.send(f"❌ ไม่พบสถานะ `{key}` — พิมพ์ `!setstatus` ดูรายชื่อ")
        label = game_modifiers.STATUS_EFFECTS[key]["label"]

        if is_all:
            count = 0
            for row in player_model.get_all_players():
                player = player_model.get_player(row["user_id"])
                statuses = game_modifiers.apply_status(game_modifiers.parse_statuses(player), key, turns)
                player_model.update_player_field(row["user_id"], "status_effects", statuses)
                count += 1
            return await ctx.send(f"🧬 เสก {label} ใส่ผู้เล่นทั้งหมด `{count}` คนเรียบร้อย!")

        player = player_model.get_player(mention.id)
        statuses = game_modifiers.apply_status(game_modifiers.parse_statuses(player), key, turns)
        player_model.update_player_field(mention.id, "status_effects", statuses)
        shown_turns = statuses[key]
        await ctx.send(f"🧬 เสก {label} ใส่ {mention.mention} (`{shown_turns}` เทิร์น) เรียบร้อย!")


async def setup(bot):
    await bot.add_cog(WorldAdmin(bot))
