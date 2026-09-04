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
    "exp_scale": 0.25,       # EXP เพิ่มกี่ส่วนต่อรอบ (ช้ากว่าทอง — เจ้าของเกมเคาะข้อ 6)
    "drop_scale": 0.15,      # โอกาสดรอปของหายากเพิ่มกี่ส่วนต่อรอบ
    "drop_cap": 0.85,        # เพดานโอกาสดรอป (ข้อเดียวที่มีเพดาน ตามสเปก)
    "revive_pct": 0.01,      # ตายแต่ปาร์ตี้ยังรอด — ฟื้นมาเท่าไหร่
    "respawn_pct": 0.50,     # ตายยกทีม — ฟื้นมาเท่าไหร่
    # ── โทษตอนตายยกทีม (เจ้าของเกมสั่ง 2026-09-04: "แพ้ต้องเสียตัง เสีย EXP และเลเวล") ──
    "wipe_gold_pct": 0.10,   # เสียเงิน **สดที่พกติดตัว** กี่ส่วน (ในธนาคารปลอดภัย)
    "wipe_exp_pct": 0.20,    # เสีย EXP กี่ส่วนของที่ต้องใช้เลื่อนเลเวลปัจจุบัน
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


def exp_mult(rnd):
    """ตัวคูณ EXP ตามรอบ — **ช้ากว่าทอง** (เจ้าของเกมเคาะข้อ 6)

    เลเวลขึ้นเร็วเกินจะทำให้เนื้อหาที่เหลือหมดความหมาย ทองเฟ้อยังพอแก้ได้
    """
    return 1.0 + _steps(rnd) * _bal("exp_scale")


def monster_count(rnd, party_size):
    """เจอมอนกี่ตัวในรอบนี้ — ตามสเปกข้อ 3.1 แต่มี **ขั้นต่ำตามจำนวนคน**

    ⚠️ สเปกเปล่า ๆ ว่า "รอบ 1-3 เจอ 1-2 ตัว" ซึ่งปาร์ตี้ 5 คนจะรุมมอนตัวเดียว
       จบในตาเดียว อีก 4 คนนั่งดู — เจ้าของเกมเคาะให้มีขั้นต่ำครึ่งหนึ่งของจำนวนคน
    """
    r = max(1, int(rnd or 1))
    if r <= 3:
        base = 1 + (r >= 2)
    elif r <= 6:
        base = 3
    else:
        base = min(5, 3 + (r - 6 + 1) // 2)
    floor = max(1, int(party_size or 1) // 2)
    return max(floor, min(5, base))


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

    คืน `(ผลลัพธ์, รายชื่อคนที่ฟื้น)`
      ผลลัพธ์ `"wipe"`    = ตายยกทีม (ต้องเริ่มเดินทางใหม่จากรอบ 1)
              `"survive"` = ยังมีคนรอด คนที่ล้มฟื้นมา 1% เดินทางต่อได้
      รายชื่อ = [(id, เลือดที่ฟื้นมา), ...] เฉพาะคนที่ **เคยล้มแล้วฟื้น**

    ⚠️ ต้องคืนรายชื่อออกไปด้วย เพราะหน้าเว็บต้องเล่นอนิเมชัน "ตาย → ฟื้น"
       ตามลำดับ ไม่งั้นการตายกับการฟื้นถูกยัดลงสถานะก้อนเดียวกัน
       จอจะไม่เคยแสดงว่าตาย เห็นแต่เลือดเด้งขึ้นเฉย ๆ
       (เจ้าของเกมเห็นอาการนี้ตอนเทสด้วยมือ 2026-09-04)

    ⚠️ ตรงนี้เป็นที่เดียวที่ตัดสินว่า "จบยังไง" — ห้ามเขียนกฎการฟื้นซ้ำที่อื่น
    """
    party = [u for u in units if u.get("side") == "party"]
    if not party:
        return "survive", []
    if wiped(party):
        # ⚠️ **ล้มยกทีมแล้วห้ามฟื้นตรงนี้** — ตายก็ต้องเห็นว่าตาย
        #    เลือดกลับมาตอนกด "เริ่มออกเดินทางใหม่" เท่านั้น (respawn_party)
        #    เจ้าของเกมสั่ง 2026-09-04: เห็นเลือดเด้งกลับตอนแพ้แล้วรู้สึกว่าไม่ได้แพ้
        return "wipe", []
    back = []
    for u in party:
        if int(u.get("hp") or 0) <= 0:
            u["hp"] = revived_hp(u.get("hp_max"))
            back.append((u.get("id"), u["hp"]))
    return "survive", back


def wipe_penalty(player):
    """โทษตอนตายยกทีม — คืน dict บอกว่าต้องหักอะไรเท่าไหร่ (**ยังไม่เขียน DB**)

    เจ้าของเกมสั่ง 2026-09-04: แพ้แล้วต้องเสียเงิน เสีย EXP และเสียเลเวล
    เกมหลักไม่มีบทลงโทษตอนตายมาก่อน กติกานี้จึงตั้งใหม่ (ปรับได้ที่ Panel)

    ⚠️ เสียเฉพาะ **เงินสดที่พกติดตัว** เงินในธนาคารปลอดภัย
       ให้เข้ากับระบบธนาคาร/โจรปล้นที่มีอยู่แล้ว — ฝากไว้ก่อนออกเดินทางคือการเล่นที่ฉลาด
    ⚠️ เลเวลลดได้ไม่ต่ำกว่า 1 และ EXP ไม่ติดลบ
    """
    from bot.models import player_model

    lvl = max(1, int(player.get("level") or 1))
    cash = max(0, int(player.get("cash") or 0))
    exp = max(0, int(player.get("exp") or 0))

    gold_lost = int(cash * _bal("wipe_gold_pct"))
    need = int(player_model.exp_required(lvl) or 0)
    exp_lost = int(need * _bal("wipe_exp_pct"))

    new_exp = exp - exp_lost
    new_lvl = lvl
    if new_exp < 0 and lvl > 1:
        new_lvl = lvl - 1
        # ตกเลเวลแล้วได้ EXP ที่เหลือของเลเวลใหม่คืนมาบางส่วน ไม่ใช่เริ่มศูนย์
        new_exp = max(0, int(player_model.exp_required(new_lvl) or 0) + new_exp)
    new_exp = max(0, new_exp)

    return {
        "gold_lost": gold_lost,
        "exp_lost": exp_lost,
        "cash": cash - gold_lost,
        "exp": new_exp,
        "level": new_lvl,
        "level_lost": lvl - new_lvl,
        # เลเวลลด = เลือดสูงสุดลดตามสูตรเกมหลัก (+20 ต่อเลเวล)
        "max_hp": max(1, int(player.get("max_hp") or 100) - (lvl - new_lvl) * 20),
    }


def respawn_party(units):
    """ฟื้นทั้งปาร์ตี้ครึ่งเลือด — เรียกตอนกด "เริ่มออกเดินทางใหม่" เท่านั้น

    ⚠️ แยกออกมาจาก close_out เพราะจอต้องได้แสดง "แพ้" ให้เห็นก่อน
       ฟื้นทันทีตอนจบสมรภูมิ = ผู้เล่นไม่รู้สึกว่าแพ้จริง
    """
    for u in units:
        if u.get("side") == "party":
            u["hp"] = respawn_hp(u.get("hp_max"))
    return units
