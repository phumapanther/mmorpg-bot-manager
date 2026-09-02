"""ตรรกะสิทธิ์คำเชิญเข้าห้องล็อบบี้ (UNO / สนามรบ / เกมอนาคต) — ไม่แตะ Discord เลย

ย้ายมาจาก bot/cogs/lobby_invite.py ตรง ๆ (ไม่เปลี่ยนพฤติกรรม) เพื่อให้ทั้งฝั่งเว็บ
(ตัดสินก่อนลงคิว) และฝั่งบอท (กันคนแก้คิวตรง ๆ ตอนดึงคิวไปส่ง DM จริง) เรียกตรรกะเดียวกันได้
โดยเว็บไม่ต้อง import ผ่าน bot/cogs/

🔒 กติกาทั้งหมดตัดสินที่ validate() เท่านั้น เว็บกับบอทเรียกฟังก์ชันเดียวกัน ไม่มีทางเลี่ยงเช็คฝั่งใดฝั่งหนึ่ง
"""
import time

from bot import friends, lobby

INVITE_LIMIT = 5          # ชวนได้กี่ครั้งต่อหน้าต่างเวลา
INVITE_WINDOW = 60         # วินาที

# ponytail: ตัวนับความถี่แบบ dict ในแรม พอสำหรับสเกลปัจจุบัน (โปรเซสเดียว)
# ถ้าต้องรันหลายอินสแตนซ์ค่อยย้ายไปตาราง/redis
_invite_hits = {}


def _rate_limited(from_uid, now=None):
    """คนหนึ่งชวนได้ไม่เกิน INVITE_LIMIT ครั้งต่อ INVITE_WINDOW วินาที"""
    now = time.time() if now is None else now
    key = str(from_uid)
    hits = [t for t in _invite_hits.get(key, []) if now - t < INVITE_WINDOW]
    _invite_hits[key] = hits
    if len(hits) >= INVITE_LIMIT:
        return True
    hits.append(now)
    return False


def reset_rate_limit():
    """สำหรับเทส — เคลียร์ตัวนับความถี่ทั้งหมด"""
    _invite_hits.clear()


def validate(from_uid, to_uid, game, code):
    """เช็คสิทธิ์ทั้งหมดที่ฝั่งเซิร์ฟเวอร์ — ไม่แตะ Discord เลย

    ใช้ร่วมกันทั้งฝั่งเว็บ (ตัดสินก่อนลงคิว) และฝั่งบอท (กันคนแก้คิวตรง ๆ)
    คืน (ok, ข้อความ)
    """
    from_uid, to_uid = int(from_uid), int(to_uid)
    if from_uid == to_uid:
        return False, "❌ ชวนตัวเองไม่ได้นะ"
    if not friends.are_friends(from_uid, to_uid):
        return False, "❌ ต้องเป็นเพื่อนกันก่อนถึงจะชวนได้"
    if lobby.room_of(game, from_uid) != str(code):
        return False, "❌ คุณไม่ได้อยู่ในห้องนี้"
    st = lobby.load(code)
    if not st or st.get("game") != str(game):
        return False, "❌ ห้องไม่มีแล้ว"
    if st.get("started"):
        return False, "❌ ห้องนี้เริ่มเกมไปแล้ว"
    if len(st.get("seats", [])) >= lobby.MAX_SEATS:
        return False, "❌ ห้องเต็มแล้ว"
    if _rate_limited(from_uid):
        return False, "⏳ ชวนถี่เกินไป รอสักครู่แล้วลองใหม่"
    return True, ""
