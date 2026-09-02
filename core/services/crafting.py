"""คราฟไอเทม — เช็กสูตร/วัตถุดิบ + คราฟจริง

ย้ายมาจาก bot/cogs/player_commands.py ตรง ๆ (ไม่เปลี่ยนพฤติกรรม) เพื่อให้ทั้งคำสั่งดิสคอร์ด
(!craft) และเว็บเรียกตรรกะเดียวกันได้ โดยเว็บไม่ต้อง import ผ่าน bot/cogs/
"""
import json
import random
import traceback

import bot.models.player_model as player_model
from bot import config_loader


def craft_for(user_id, item_id):
    """🔨 B1: ตรรกะคราฟกลาง — ใช้ทั้งคำสั่ง !craft และปุ่มในเมนู คืน (สำเร็จ, ข้อความ)"""
    try:
        if not item_id or not config_loader.get_crafting_recipe(str(item_id)):
            return False, "❌ รหัสไอเทมนี้ไม่มีสูตรคราฟ หรือรหัสไม่ถูกต้อง!"
        item_id = str(item_id)
        player = player_model.get_player(user_id)
        if not player:
            return False, "❌ ไม่พบข้อมูลตัวละครของคุณ!"
        inv_list = player_model.load_inventory(player.get("inventory", []))
        recipe_data = config_loader.get_crafting_recipe(item_id)
        recipe = recipe_data["recipe"]
        fail_rate = recipe_data.get("fail_rate", 0.2)

        # 1. เช็กวัตถุดิบ
        for ing_id, amount in recipe.items():
            if inv_list.count(str(ing_id)) < amount:
                needed_name = config_loader.get_item_config(str(ing_id)).get("name", "Unknown")
                return False, f"❌ วัตถุดิบไม่พอ! คุณขาด `{needed_name}`"

        # 2. เช็กกระเป๋าเต็ม
        capacity = player.get("capacity", 10)
        if capacity != 0 and len(inv_list) >= capacity:
            return False, "⚠️ กระเป๋าของคุณเต็ม!"

        # 3. โอกาสล้มเหลว — เสียวัตถุดิบครึ่งหนึ่ง
        if random.random() < fail_rate:
            for ing_id, amount in recipe.items():
                for _ in range((amount + 1) // 2):
                    if str(ing_id) in inv_list:
                        inv_list.remove(str(ing_id))
            player_model.update_player_field(user_id, "inventory", json.dumps(inv_list))
            return False, f"💥 **ล้มเหลว ({int(fail_rate * 100)}%)!** วัตถุดิบเสียหายไปบางส่วน!"

        # 4. คราฟสำเร็จ
        for ing_id, amount in recipe.items():
            for _ in range(amount):
                inv_list.remove(str(ing_id))
        inv_list.append(item_id)
        player_model.update_player_field(user_id, "inventory", json.dumps(inv_list))
        craft_name = config_loader.get_item_config(item_id).get("name", item_id)
        return True, f"✨ คราฟสำเร็จ! คุณได้รับ `{craft_name}` 1 ชิ้น!"

    except Exception as e:
        print(f"❌ [CRITICAL ERROR] การคราฟพัง! สาเหตุ: {e}")
        traceback.print_exc()
        return False, f"⚠️ ระบบคราฟมีปัญหาทางเทคนิค! (Error: {e})"


def craftable_now(user_id):
    """สูตรที่วัตถุดิบครบพร้อมคราฟตอนนี้ — [(item_id, ชื่อ, ข้อความวัตถุดิบ), ...]"""
    player = player_model.get_player(user_id)
    if not player:
        return []
    inv = player_model.load_inventory(player.get("inventory", []))
    recipes = config_loader.get_config().get("item_catalog", {}).get("crafting_recipes", {})
    out = []
    for item_id, data in recipes.items():
        recipe = (data or {}).get("recipe") or {}
        if not recipe or not all(inv.count(str(i)) >= n for i, n in recipe.items()):
            continue
        mats = " + ".join(f"{config_loader.get_item_config(str(i)).get('name', i)}×{n}"
                          for i, n in recipe.items())
        out.append((item_id, config_loader.get_item_config(item_id).get("name", item_id), mats))
    return out
