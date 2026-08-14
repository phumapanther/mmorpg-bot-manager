"""🛒 ร้านขายยศ + กาชา — ตรรกะกลาง (เว็บเกม เฟส 7.1)

เดิมฝังอยู่ใน cog ของ Discord ทั้งก้อน เว็บเรียกไม่ได้เลย

จุดที่ต่างจากระบบอื่น: **เว็บแจกยศ Discord เองไม่ได้** ต้องให้บอทเป็นคนแจก
จึงแยกเป็นสองจังหวะ
  1. prepare_*  ตรวจเงิน/ตรวจของ แล้ว "หักเงินจอง" ไว้ก่อน — ทำได้ทั้งสองแพลตฟอร์ม
  2. การแจกยศจริง — ดิสแจกทันทีเอง ส่วนเว็บโยนเข้าคิว role_grant_queue ให้บอทมาแจก
     แจกไม่สำเร็จเมื่อไหร่ ต้องคืนเงินด้วย refund() เสมอ

หมายเหตุเรื่อง "มียศนี้อยู่แล้วไหม": ความจริงอยู่ที่ Discord เท่านั้น เว็บเช็คเองไม่ได้
จึงให้ฝั่งที่แจกจริงเป็นคนตัดสิน — ซื้อเจาะจงแล้วซ้ำ = คืนเงิน / กาชาแล้วซ้ำ = เกลือตามกติกา
"""
import random

import bot.models.player_model as player_model
from bot import config_loader


def list_roles(faction):
    """ยศทั้งหมดของฝ่ายนั้นพร้อมราคา (dark | light)"""
    return config_loader.get_trade_roles(faction) or []


def gacha_pool(faction):
    """เฉพาะยศที่อยู่ในตู้กาชา — คัดด้วยราคาตามที่ตั้งไว้ใน config"""
    price = config_loader.get_gacha_pool_price()
    return [r for r in list_roles(faction) if r.get("price") == price]


def find_role(faction, value):
    return next((r for r in list_roles(faction) if r.get("value") == value), None)


def _cash(user_id):
    return int((player_model.get_player(user_id) or {}).get("cash", 0) or 0)


def refund(user_id, amount):
    """คืนเงินที่จองไว้ — เรียกทุกครั้งที่แจกยศไม่สำเร็จ"""
    if amount:
        player_model.increment_player_field(user_id, "cash", int(amount))


def prepare_buy(user_id, faction, value):
    """ซื้อยศเจาะจง — ตรวจของ/ตรวจเงินแล้วหักเงินจองไว้

    คืน (ok, data) — data มี role_id/label/price ไว้ให้ผู้เรียกไปแจกยศต่อ
    """
    role = find_role(faction, value)
    if not role:
        return False, {"error": "❌ ไม่พบข้อมูลยศนี้ในระบบ!"}
    price = int(role.get("price", 0))
    if _cash(user_id) < price:
        return False, {"error": f"❌ เงินของคุณไม่พอ! ยศนี้ราคา `{price:,}` ทอง "
                                f"(คุณมี `{_cash(user_id):,}` ทอง)"}

    player_model.increment_player_field(user_id, "cash", -price)
    return True, {"role_id": role["role_id"], "label": role["label"],
                  "price": price, "kind": "buy"}


def prepare_gacha(user_id, faction, rng=random):
    """หมุนกาชา — หักค่าหมุนแล้วสุ่มยศออกมาหนึ่งใบ

    หักเงินก่อนสุ่มเหมือนของเดิม (จ่ายค่าหมุน ไม่ใช่จ่ายค่ายศ)
    """
    price = config_loader.get_gacha_price()
    if _cash(user_id) < price:
        return False, {"error": f"❌ เงินของคุณไม่พอสุ่มกาชา! ต้องใช้ `{price:,}` ทอง "
                                f"(คุณมี `{_cash(user_id):,}` ทอง)"}
    pool = gacha_pool(faction)
    if not pool:
        return False, {"error": "❌ ตู้กาชาฝ่ายนี้ยังไม่มียศให้สุ่ม (แอดมินยังไม่ได้ตั้งค่า)"}

    player_model.increment_player_field(user_id, "cash", -price)
    won = rng.choice(pool)
    return True, {"role_id": won["role_id"], "label": won["label"],
                  "price": price, "kind": "gacha", "pool_size": len(pool)}


def shop_view(faction, user_id=None):
    """ข้อมูลร้านพร้อมแสดงผล — ใช้ได้ทั้ง embed ในดิสและ JSON ของเว็บ"""
    roles = list_roles(faction)
    pool = gacha_pool(faction)
    return {
        "faction": faction,
        "roles": [{"value": r.get("value"), "label": r.get("label"),
                   "price": int(r.get("price", 0)), "emoji": r.get("emoji") or ""}
                  for r in roles],
        "gacha": {"price": config_loader.get_gacha_price(),
                  "pool_size": len(pool),
                  "pool": [r.get("label") for r in pool]},
        "cash": _cash(user_id) if user_id else 0,
    }
