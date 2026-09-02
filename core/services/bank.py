"""ธนาคาร — ฝาก/ถอน/โอน + ค่าธรรมเนียมตามยอด

ย้ายมาจาก bot/cogs/player_commands.py ตรง ๆ (ไม่เปลี่ยนพฤติกรรม) เพื่อให้ทั้งคำสั่งดิสคอร์ด
(!deposit/!withdraw/!transfer) และเว็บเรียกตรรกะเดียวกันได้ โดยเว็บไม่ต้อง import ผ่าน bot/cogs/
"""
import time

import bot.models.player_model as player_model
from bot import config_loader

# 🏦 ค่าธรรมเนียมธุรกรรมตามยอดต่อครั้ง (spec 2026-08-06) — [เพดานยอด, %] ขั้นสุดท้าย null = ไม่จำกัด
_BANK_FEE_TIERS = [[100_000, 5], [1_000_000, 10], [10_000_000, 20], [100_000_000, 35], [None, 50]]


def bank_fee(amount):
    """คืน (ค่าธรรมเนียม, %) ของยอดธุรกรรมนี้ — ขั้นตั้งได้ที่ Panel (bank.fee_tiers) เพี้ยน = ใช้ค่าเดิม"""
    tiers = config_loader.get_balance("bank.fee_tiers", None)
    if not (isinstance(tiers, list) and tiers
            and all(isinstance(t, (list, tuple)) and len(t) == 2 for t in tiers)):
        tiers = _BANK_FEE_TIERS
    pct = tiers[-1][1]
    for limit, p in tiers:
        if limit is None or amount < int(limit):
            pct = p
            break
    return amount * int(pct) // 100, int(pct)


def bank_action(user_id, action, amount, target_id=None):
    """ฝาก/ถอน/โอน — ตรรกะกลางที่ทั้งคำสั่งพิมพ์ (!deposit/!withdraw/!transfer) และปุ่มเมนูเรียกใช้
    คืน (สำเร็จ: bool, ข้อความ: str) — เช็คติดคุกในนี้ด้วย เพราะปุ่มไม่ผ่าน decorator @not_arrested"""
    player = player_model.get_player(user_id)
    if not player:
        return False, "❌ ไม่พบข้อมูลตัวละครของคุณ! พิมพ์ `!play` ก่อนนะ"
    if player.get("current_state") == "arrested" and time.time() < int(player.get("arrest_until", 0) or 0):
        return False, "❌ คุณติดคุกอยู่ ทำธุรกรรมไม่ได้! รอพ้นโทษก่อนนะ"
    if amount <= 0:
        return False, "❌ จำนวนเงินต้องมากกว่า 0!"

    fee, pct = bank_fee(amount)
    fee_note = f" (ค่าธรรมเนียม {pct}% = `{fee:,}` ทอง)"

    if action == "deposit":
        if player.get("cash", 0) < amount:
            return False, "❌ เงินสดไม่พอฝาก!"
        player_model.update_player_field(user_id, "cash", player["cash"] - amount)
        player_model.update_player_field(user_id, "bank", player.get("bank", 0) + amount - fee)
        return True, f"💰 ฝากเงิน `{amount:,}` ทอง — เข้าธนาคาร `{amount - fee:,}` ทอง{fee_note}"

    if action == "withdraw":
        if player.get("bank", 0) < amount:
            return False, "❌ เงินในธนาคารไม่พอถอนครับ!"
        player_model.update_player_field(user_id, "bank", player["bank"] - amount)
        player_model.update_player_field(user_id, "cash", player.get("cash", 0) + amount - fee)
        return True, f"💸 ถอนเงิน `{amount:,}` ทอง — ได้รับ `{amount - fee:,}` ทอง{fee_note}"

    if action == "transfer":
        if target_id == user_id:
            return False, "❌ โอนให้ตัวเองไม่ได้นะ!"
        if player.get("bank", 0) < amount:
            return False, "❌ เงินในธนาคารไม่พอโอน!"
        target = player_model.get_player(target_id)
        if not target:
            return False, "❌ ไม่พบข้อมูลผู้เล่นปลายทาง"
        player_model.update_player_field(user_id, "bank", player["bank"] - amount)
        player_model.update_player_field(target_id, "bank", target.get("bank", 0) + amount - fee)
        return True, f"💸 โอนเงิน `{amount:,}` ทอง ให้ <@{target_id}> — ปลายทางได้รับ `{amount - fee:,}` ทอง{fee_note}"

    return False, "❌ ไม่รู้จักธุรกรรมนี้"
