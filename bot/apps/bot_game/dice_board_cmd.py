"""🎲 คำสั่งกระดานทอยเต๋ารายวัน (เว็บเกม เฟส 8.3)

โควตา 3 ครั้ง/วัน ใช้ร่วมกับเว็บ — ทอยที่ไหนก็หักโควตาเดียวกัน
ตรรกะทั้งหมดอยู่ใน bot/dice_board.py ที่นี่ทำแค่หน้าจอ
"""
import discord
from discord.ext import commands

from bot import dice_board
from bot.utils import allowed_channel, not_arrested


def build_board_embed(user_id, display_name, last=None):
    st = dice_board.state(user_id)
    tiles, pos = st["board"], st["pos"]

    rows = []
    for r in range(0, st["size"], 8):                 # วาดเป็น 3 แถว แถวละ 8 ช่อง
        line = []
        for i in range(r, min(r + 8, st["size"])):
            line.append(f"[{tiles[i]['icon']}]" if i == pos else f" {tiles[i]['icon']} ")
        rows.append("".join(line))

    embed = discord.Embed(
        title=f"🎲 กระดานทอยเต๋าของ {display_name}",
        color=0x9f7aea,
        description=(f"ธีมสัปดาห์นี้: **{st['theme_label']}**\n"
                     f"```\n" + "\n".join(rows) + "\n```"
                     f"ยืนอยู่ช่อง **{tiles[pos]['icon']} {tiles[pos]['label']}**"))
    embed.add_field(name="🎯 โควตาวันนี้",
                    value=f"เหลือ **{st['rolls_left']}/{st['rolls_per_day']}** ครั้ง "
                          f"(รีเซ็ตเที่ยงคืน)", inline=False)
    if last:
        embed.add_field(name=f"🎲 ทอยได้ {last['steps']}", value=last["text"], inline=False)
    return embed


class BoardView(discord.ui.View):
    def __init__(self, user_id):
        super().__init__(timeout=180)
        self.user_id = user_id
        self._sync()

    def _sync(self):
        self.children[0].disabled = dice_board.rolls_left(self.user_id) <= 0

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.user_id:
            await interaction.response.send_message(
                "❌ นี่ไม่ใช่กระดานของคุณ! พิมพ์ `!board` เพื่อเปิดของตัวเอง", ephemeral=True)
            return False
        return True

    @discord.ui.button(label="🎲 ทอยเต๋า", style=discord.ButtonStyle.primary)
    async def roll(self, interaction: discord.Interaction, button: discord.ui.Button):
        ok, r = dice_board.roll(self.user_id)
        if not ok:
            return await interaction.response.send_message(r["error"], ephemeral=True)
        self._sync()
        await interaction.response.edit_message(
            embed=build_board_embed(self.user_id, interaction.user.display_name, r), view=self)


class DiceBoard(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="board", aliases=["เต๋า", "กระดาน"])
    @not_arrested()
    @allowed_channel("adventure")
    async def board_cmd(self, ctx):
        """เปิดกระดานทอยเต๋ารับของรายวัน"""
        await ctx.send(embed=build_board_embed(ctx.author.id, ctx.author.display_name),
                       view=BoardView(ctx.author.id))


async def setup(bot):
    await bot.add_cog(DiceBoard(bot))
