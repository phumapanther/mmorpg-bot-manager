"""🎭 กติกาปาร์ตี้เทิร์นเบส — ตรรกะล้วน ไม่มี I/O ไม่มี DB ไม่รู้จักการวาดภาพ

แยกไว้ต่างหากเพื่อให้เทสง่ายและอ่านจบในไฟล์เดียว
ใครจะปรับสมดุลเกมมาแก้ที่นี่ที่เดียว

⚠️ **ธาตุใช้ตารางของเกมหลัก ไม่ตั้งใหม่**
   ตอนเขียนแผนเคยร่างตารางเองแล้ว**ผิด 2 จุด** (earth/wind สลับกัน)
   ธาตุที่ไม่ตรงกันสองโหมด = ผู้เล่นงงว่าทำไมตีแล้วดาเมจไม่เหมือนกัน
"""
from bot import game_modifiers

# ชนิดการเล็งเป้าที่รองรับ (สเปก 2026-09-03) -> เล็งฝั่งไหนได้
#   same = ฝั่งเดียวกับคนใช้ · enemy = ฝั่งตรงข้าม
TARGET_KINDS = {
    "single": "enemy",   # ตัวเดียว
    "all": "enemy",      # ทุกตัว (AoE)
    "ally": "same",      # ฮีล / ชุบเพื่อน
    "self": "same",      # บัฟตัวเอง
}

PENALTY = 0.7            # โดนธาตุที่ข่มเราอยู่ = ดาเมจลด


def _as_list(elements):
    """รับได้ทั้ง "fire" และ ["fire", "water"] — ผู้เล่นถือได้หลายธาตุ (ยศเผ่าหลายอัน)"""
    if not elements:
        return []
    return [elements] if isinstance(elements, str) else list(elements)


def element_multiplier(attacker_elements, target_element):
    """ตัวคูณดาเมจจากธาตุ — ไม่มีธาตุ/ธาตุแปลก = 1.0 (ไม่ได้ไม่เสีย)

    ได้เปรียบ 1 ธาตุ = ×1.5 · สองธาตุซ้อน = ×2.0 (ยืมสูตรเกมหลักตรง ๆ)
    เสียเปรียบ = ×0.7
    """
    attackers = _as_list(attacker_elements)
    if not attackers or not target_element:
        return 1.0

    # ได้เปรียบ — ใช้สูตรเดียวกับโหมดเดี่ยวเป๊ะ
    mult = game_modifiers.player_attack_element_mult(attackers, target_element)
    if mult > 1.0:
        return mult

    # เสียเปรียบ — ธาตุเป้าข่มธาตุเราอยู่
    beaten = game_modifiers.ELEMENT_ADVANTAGE.get(target_element, [])
    if any(e in beaten for e in attackers):
        return PENALTY
    return 1.0


def can_target(kind, actor_side, target_side):
    """สกิลชนิดนี้เล็งเป้าฝั่งนี้ได้ไหม

    actor_side / target_side = "party" หรือ "monster"
    ชนิดที่ไม่รู้จัก = เล็งไม่ได้ (กันคนยิง API ส่งค่ามั่ว)
    """
    want = TARGET_KINDS.get(kind)
    if want is None:
        return False
    same = actor_side == target_side
    return same if want == "same" else not same
