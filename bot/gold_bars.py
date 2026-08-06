"""🧈 ทองคำแท่ง (ส่วนขยาย spec 2026-08-06) — แปลงเหรียญทองเป็นไอเทมมีมูลค่าในกระเป๋า

แลกซื้อ/ขายคืนที่ธนาคาร ค่าธรรมเนียม flat (default 5% — Panel: gold_bar.fee_pct)
ขายที่ร้านหมู่บ้านได้ด้วยราคา sell ในแคตตาล็อก (ตั้งไว้ 85% ของมูลค่า = แพงกว่าธนาคาร)
ไอเทมแท่งทอง = entry ในแคตตาล็อกที่มีฟิลด์ bar_value (id 72-75)
"""
import json
import time

import bot.models.player_model as player_model
from bot import config_loader


def fee_pct():
    try:
        return max(0, min(100, int(config_loader.get_balance("gold_bar.fee_pct", 5) or 0)))
    except (TypeError, ValueError):
        return 5


def bar_items():
    """{item_id: มูลค่าหน้าแท่ง} เรียงจากเล็กไปใหญ่ — อ่านจากแคตตาล็อก เพิ่มแท่งใหม่ใน config ได้เลย"""
    out = {iid: int(d.get("bar_value") or 0)
           for iid, d in config_loader.get_all_items().items() if d.get("bar_value")}
    return dict(sorted(out.items(), key=lambda kv: kv[1]))


def _player_ok(user_id):
    player = player_model.get_player(user_id)
    if not player:
        return None, "❌ ไม่พบข้อมูลตัวละครของคุณ! พิมพ์ `!play` ก่อนนะ"
    if player.get("current_state") == "arrested" and time.time() < int(player.get("arrest_until", 0) or 0):
        return None, "❌ คุณติดคุกอยู่ ทำธุรกรรมไม่ได้!"
    return player, ""


def buy_bar(user_id, item_id):
    """แลกเหรียญ (ตัดจากธนาคาร) → ทองคำแท่งเข้ากระเป๋า — คืน (สำเร็จ, ข้อความ)"""
    item_id = str(item_id)
    item = config_loader.get_item_config(item_id)
    face = int(item.get("bar_value") or 0)
    if face <= 0:
        return False, "❌ ไอเทมนี้ไม่ใช่ทองคำแท่ง"
    player, err = _player_ok(user_id)
    if not player:
        return False, err

    fee = face * fee_pct() // 100
    cost = face + fee
    if int(player.get("bank", 0) or 0) < cost:
        return False, f"❌ เงินในธนาคารไม่พอ! ต้องมี `{cost:,}` ทอง (รวมค่าธรรมเนียม {fee_pct()}%)"

    inv = player_model.load_inventory(player.get("inventory", ""))
    capacity = int(player.get("capacity", 10) or 0)
    if capacity != 0 and len(inv) >= capacity:
        return False, f"❌ กระเป๋าเต็ม ({len(inv)}/{capacity}) — เคลียร์ของก่อนค่อยมาแลกทองคำแท่ง"

    inv.append(item_id)
    player_model.update_player_field(user_id, "bank", player["bank"] - cost)
    player_model.update_player_field(user_id, "inventory", json.dumps(inv))
    print(f"[LOG] [GOLD_BAR] 🧈 {user_id} แลกซื้อ {item.get('name', item_id)} หักธนาคาร {cost:,}")
    return True, (f"🧈 แลกซื้อ **{item.get('name', item_id)}** สำเร็จ! เข้ากระเป๋าแล้ว\n"
                  f"หักธนาคาร `{cost:,}` ทอง (มูลค่า `{face:,}` + ค่าธรรมเนียม {fee_pct()}% = `{fee:,}`)")


def sell_bar(user_id, item_id):
    """ขายทองคำแท่งคืนธนาคาร → ได้เหรียญเข้าธนาคาร — คืน (สำเร็จ, ข้อความ)"""
    item_id = str(item_id)
    item = config_loader.get_item_config(item_id)
    face = int(item.get("bar_value") or 0)
    if face <= 0:
        return False, "❌ ไอเทมนี้ไม่ใช่ทองคำแท่ง"
    player, err = _player_ok(user_id)
    if not player:
        return False, err

    inv = player_model.load_inventory(player.get("inventory", ""))
    if item_id not in inv:
        return False, "❌ ไม่มีทองคำแท่งชนิดนี้ในกระเป๋า"

    fee = face * fee_pct() // 100
    credit = face - fee
    inv.remove(item_id)
    player_model.update_player_field(user_id, "inventory", json.dumps(inv))
    player_model.update_player_field(user_id, "bank", int(player.get("bank", 0) or 0) + credit)
    print(f"[LOG] [GOLD_BAR] 💰 {user_id} ขายคืน {item.get('name', item_id)} ได้ {credit:,}")
    return True, (f"💰 ขาย **{item.get('name', item_id)}** คืนธนาคารสำเร็จ!\n"
                  f"ได้รับ `{credit:,}` ทองเข้าธนาคาร (มูลค่า `{face:,}` − ค่าธรรมเนียม {fee_pct()}% = `{fee:,}`)")
