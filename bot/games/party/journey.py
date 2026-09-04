"""🧭 รอบการเดินทาง — ความยากไต่ระดับ + กฎการตาย

สเปกเสริม 2026-09-04 (เจ้าของเกมสั่ง) — ตรรกะล้วน ไม่แตะ DB ไม่รู้จักการวาดภาพ

⚠️ **เจ้าของเกมเคาะว่า "ไม่มีเพดาน" สำหรับทอง** ทั้งที่โตเร็วกว่าความยาก
   (ทอง +40%/รอบ · มอน +25%/รอบ) รู้ตัวแล้วว่าคุ้มค่ายิ่งเดินไกล
   ความเสี่ยงคือตายยกทีมแล้วกลับรอบ 1 — อย่าเปลี่ยนเองโดยไม่ถาม

⚠️ ตัวเลขทุกตัวตั้งได้ที่ Panel (`party.journey.*`) ตั้งเพี้ยนก็ตกกลับค่าในโค้ด
"""
import math

from bot import config_loader

DEFAULTS = {
    "monster_scale": 0.25,   # มอนแรงขึ้นกี่ส่วนต่อรอบ
    "gold_scale": 0.40,      # ทองเพิ่มกี่ส่วนต่อรอบ
    "drop_scale": 0.15,      # โอกาสดรอปของหายากเพิ่มกี่ส่วนต่อรอบ
    "drop_cap": 0.85,        # เพดานโอกาสดรอป (ข้อเดียวที่มีเพดาน ตามสเปก)
    "revive_pct": 0.01,      # ตายแต่ปาร์ตี้ยังรอด — ฟื้นมาเท่าไหร่
    "respawn_pct": 0.50,     # ตายยกทีม — ฟื้นมาเท่าไหร่
}


def _bal(key):
    try:
        return float(config_loader.get_balance(f"party.journey.{key}", DEFAULTS[key]))
    except (TypeError, ValueError):
        return float(DEFAULTS[key])


def _steps(rnd):
    """รอบที่ 1 คือจุดเริ่ม ยังไม่มีตัวคูณ — รอบ 5 นับเป็น 4 ขั้น"""
    return max(0, int(rnd or 1) - 1)


def monster_mult(rnd):
    """ตัวคูณ HP / โจมตี / ป้องกัน ของมอนตามรอบ"""
    return 1.0 + _steps(rnd) * _bal("monster_scale")


def gold_mult(rnd):
    """ตัวคูณทองตามรอบ — **ไม่มีเพดาน** ตามที่เจ้าของเกมเคาะ"""
    return 1.0 + _steps(rnd) * _bal("gold_scale")


def rare_drop_chance(base, rnd):
    """โอกาสดรอปของหายากตามรอบ — ตัวเดียวที่มีเพดาน (0.85)"""
    return min(float(base) * (1.0 + _steps(rnd) * _bal("drop_scale")), _bal("drop_cap"))


def revived_hp(max_hp):
    """ตายแต่เพื่อนยังรอด — ฟื้นมาเลือดน้อยนิด (ต่ำสุด 1 ไม่ใช่ 0)"""
    return max(1, math.floor(int(max_hp or 1) * _bal("revive_pct")))


def respawn_hp(max_hp):
    """ตายยกทีม — ฟื้นมาครึ่งเลือด แล้วเริ่มเดินทางใหม่จากรอบ 1"""
    return max(1, math.floor(int(max_hp or 1) * _bal("respawn_pct")))


def wiped(units):
    """ปาร์ตี้ล้มหมดทุกคนไหม — ว่างเปล่าไม่นับว่าตายยกทีม"""
    party = [u for u in units if u.get("side") == "party"]
    return bool(party) and all(int(u.get("hp") or 0) <= 0 for u in party)


def close_out(units):
    """ปิดฉากการต่อสู้ — คืนชื่อผลลัพธ์ แล้วแก้เลือดในหน่วยให้เรียบร้อย

    คืน `"wipe"` = ตายยกทีม (ต้องเริ่มเดินทางใหม่จากรอบ 1)
        `"survive"` = ยังมีคนรอด คนที่ล้มฟื้นมา 1% เดินทางต่อได้

    ⚠️ ตรงนี้เป็นที่เดียวที่ตัดสินว่า "จบยังไง" — ห้ามเขียนกฎการฟื้นซ้ำที่อื่น
    """
    party = [u for u in units if u.get("side") == "party"]
    if not party:
        return "survive"
    if wiped(party):
        for u in party:
            u["hp"] = respawn_hp(u.get("hp_max"))
        return "wipe"
    for u in party:
        if int(u.get("hp") or 0) <= 0:
            u["hp"] = revived_hp(u.get("hp_max"))
    return "survive"
