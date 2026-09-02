import discord
from discord.ext import commands

import bot.models.player_model as player_model
import bot.models.payment_model as payment_model
from bot import config_loader, promptpay
from bot.utils import has_permission, allowed_channel, main_server_gate


class PaymentCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        payment_model.init_db()

    # ─── 💳 เติมเงิน: สร้างคำสั่งซื้อ + แสดง QR PromptPay (ถ้าเปิดใช้งาน) ───
    @allowed_channel("payment")
    @commands.command(name="payment")
    async def payment(self, ctx, amount: float = None):
        cfg = config_loader.get_payment_config()
        if amount is None or amount <= 0:
            return await ctx.send("❓ **วิธีใช้:** `!payment [จำนวนเงิน]` เช่น `!payment 100`")

        currency = cfg.get("currency", "THB")
        min_amount = cfg.get("min_amount", 0)
        max_amount = cfg.get("max_amount", 0)
        if amount < min_amount or (max_amount and amount > max_amount):
            return await ctx.send(f"❌ ยอดเติมต้องอยู่ระหว่าง `{min_amount:,}` ถึง `{max_amount:,}` {currency}")

        exchange_rate = cfg.get("exchange_rate", 0)
        gold = int(amount * exchange_rate)
        if gold <= 0:
            return await ctx.send("❌ ระบบเติมเงินยังไม่ได้ตั้งค่าอัตราแลกเปลี่ยน! (แอดมินต้องตั้งค่าในแผงควบคุมก่อน)")

        promptpay_cfg = cfg.get("promptpay", {})
        paypal_cfg = cfg.get("paypal", {})
        truemoney_cfg = cfg.get("truemoney", {})
        if not any(c.get("enabled") for c in (promptpay_cfg, paypal_cfg, truemoney_cfg)):
            return await ctx.send("❌ ยังไม่มีช่องทางชำระเงินที่เปิดใช้งาน! (แอดมินต้องตั้งค่าในแผงควบคุมก่อน)")

        method = "promptpay" if promptpay_cfg.get("enabled") else ("paypal" if paypal_cfg.get("enabled") else "truemoney")
        order_id = payment_model.create_order(ctx.author.id, amount, currency, gold, method)

        embed = discord.Embed(
            title=f"💳 คำสั่งเติมเงิน #{order_id}",
            description=f"ยอดชำระ: `{amount:,.2f}` {currency} ➔ ได้รับ `{gold:,}` ทอง",
            color=discord.Color.blue()
        )
        file = None
        if promptpay_cfg.get("enabled") and promptpay_cfg.get("id"):
            buf = promptpay.build_qr_png(promptpay_cfg["id"], amount)
            file = discord.File(buf, filename="promptpay_qr.png")
            embed.set_image(url="attachment://promptpay_qr.png")
            embed.add_field(name="📱 สแกน QR PromptPay", value=f"โอนให้ {promptpay_cfg.get('name') or 'ผู้รับ'}", inline=False)
        if paypal_cfg.get("enabled") and paypal_cfg.get("link"):
            embed.add_field(name="🅿️ PayPal", value=paypal_cfg["link"], inline=False)
        if truemoney_cfg.get("enabled") and truemoney_cfg.get("phone"):
            embed.add_field(name="💰 TrueMoney Wallet", value=truemoney_cfg["phone"], inline=False)

        embed.set_footer(text="โอนแล้วรอแอดมินตรวจสลิปและกด !confirm_payment ยืนยัน (ทองเข้าอัตโนมัติทันทีที่ยืนยัน)")
        if file:
            await ctx.send(embed=embed, file=file)
        else:
            await ctx.send(embed=embed)

    @commands.command(name="my_orders")
    async def my_orders(self, ctx):
        orders = payment_model.get_pending_orders_for_user(ctx.author.id)
        if not orders:
            return await ctx.send("📭 คุณไม่มีคำสั่งเติมเงินที่รอดำเนินการ")
        lines = [f"#{o['order_id']}: `{o['amount']:,.2f}` {o['currency']} ➔ `{o['gold']:,}` ทอง ({o['method']})" for o in orders]
        await ctx.send("📋 **คำสั่งเติมเงินที่รอดำเนินการ:**\n" + "\n".join(lines))

    # ─── ✅ แอดมินยืนยันการชำระเงิน (หลังตรวจสลิป/ยอดเข้าบัญชีจริงด้วยตาตัวเอง) — เติมทองอัตโนมัติ ───
    # ponytail: ยังไม่เชื่อมต่อ API ตรวจสลิปอัตโนมัติ (ต้องใช้บัญชีผู้ให้บริการภายนอกที่ยังไม่มี) แอดมินยืนยันมือ ณ ตอนนี้
    @has_permission("admin")
    @commands.command(name="confirm_payment")
    async def confirm_payment(self, ctx, order_id: int = None):
        if order_id is None:
            return await ctx.send("❓ **วิธีใช้:** `!confirm_payment [เลขคำสั่งซื้อ]`")
        order = payment_model.get_order(order_id)
        if not order:
            return await ctx.send(f"❌ ไม่พบคำสั่งซื้อ #{order_id}")
        if order["status"] != "pending":
            return await ctx.send(f"❌ คำสั่งซื้อ #{order_id} ถูกดำเนินการไปแล้ว (สถานะ: {order['status']})")

        player_model.increment_player_field(order["user_id"], "cash", order["gold"])
        payment_model.set_order_status(order_id, "confirmed", confirmed_by=ctx.author.id)

        await ctx.send(f"✅ ยืนยันคำสั่งซื้อ #{order_id} สำเร็จ! เติมทอง `{order['gold']:,}` ให้ <@{order['user_id']}> เรียบร้อยแล้ว")
        try:
            member = ctx.guild.get_member(order["user_id"]) or await ctx.guild.fetch_member(order["user_id"])
            await member.send(f"🎉 การเติมเงิน #{order_id} ของคุณได้รับการยืนยันแล้ว! ได้รับทอง `{order['gold']:,}` ทอง")
        except Exception:
            pass

    @commands.command(name="cancel_payment")
    async def cancel_payment(self, ctx, order_id: int = None):
        if order_id is None:
            return await ctx.send("❓ **วิธีใช้:** `!cancel_payment [เลขคำสั่งซื้อ]`")
        order = payment_model.get_order(order_id)
        if not order:
            return await ctx.send(f"❌ ไม่พบคำสั่งซื้อ #{order_id}")
        is_owner = order["user_id"] == ctx.author.id
        is_admin = ctx.author.id == ctx.guild.owner_id or ctx.author.guild_permissions.administrator
        if not (is_owner or is_admin):
            return await ctx.send("❌ คุณไม่มีสิทธิ์ยกเลิกคำสั่งซื้อนี้!")
        if order["status"] != "pending":
            return await ctx.send(f"❌ คำสั่งซื้อ #{order_id} ถูกดำเนินการไปแล้ว (สถานะ: {order['status']})")
        payment_model.set_order_status(order_id, "cancelled", confirmed_by=ctx.author.id)
        await ctx.send(f"🚫 ยกเลิกคำสั่งซื้อ #{order_id} แล้ว")


async def setup(bot):
    await bot.add_cog(PaymentCommands(bot))

    async def cog_check(self, ctx):
        """P8: ฟีเจอร์นี้เล่นได้เฉพาะเซิร์ฟหลัก (เซิร์ฟรองเล่นได้แค่ผจญภัย)"""
        return await main_server_gate(ctx)
