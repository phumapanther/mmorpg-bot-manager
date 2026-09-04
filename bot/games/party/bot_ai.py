"""🎭 บอทเล่นแทนคนที่หลุดหรือ AFK — ตรรกะล้วน ไม่แตะ DB ไม่แตะห้อง

⚠️ **หน้าที่เดียวคือ "ทำให้เกมเดินต่อ" ไม่ใช่เล่นเก่ง**
   คน AFK คนเดียวห้ามค้างทั้งปาร์ตี้ (สเปกข้อ 4)
   บอทเก่งเกินไปกลับแย่ — คนจะปล่อยให้บอทเล่นแทนแล้วไปทำอย่างอื่น

⚠️ **ห้ามสั่ง `flee` เด็ดขาด** — หนีคือจบเกมให้ทั้งปาร์ตี้
   คนหลุดคนเดียวไม่มีสิทธิ์ตัดสินใจแทนอีก 4 คน
"""

CRITICAL_HP = 0.35      # เลือดต่ำกว่านี้ถือว่าวิกฤต ต้องฮีลก่อน
SWARM = 3               # ศัตรูเยอะกว่านี้ กวาดคุ้มกว่าตีเดี่ยว


def _alive(units):
    return [u for u in units or [] if (u.get("hp") or 0) > 0]


def can_revive(unit):
    """ชุบได้ไหม — ดูจาก "ธงที่แกนคำนวณมาให้แล้ว" ไม่ใช่ไปเช็คกระเป๋าเอง

    ไฟล์นี้ต้องเทสได้โดยไม่ต้องมีฐานข้อมูล engine จึงเป็นคนเติม can_revive ให้
    (นักบวชชุบได้ฟรี คนอื่นต้องมีใบชุบชีวิต)
    """
    if unit.get("can_revive") is not None:
        return bool(unit["can_revive"])
    return unit.get("class_name") == "Cleric"


def choose(unit, allies, enemies, rng):
    """เลือกหนึ่งท่าแทนผู้เล่น — คืน (action, target_id)

    ลำดับความสำคัญ:
      1. ชุบเพื่อนที่ล้ม (ถ้าชุบได้) — คนตายนั่งดูอยู่ ช่วยก่อน
      2. ฮีลคนที่เลือดวิกฤต — กันล้มเพิ่ม
      3. กวาดเมื่อศัตรูเยอะ
      4. ตีตัวที่ใกล้ตายที่สุด — เก็บให้ตายทีละตัว ลดดาเมจที่จะโดน
    """
    foes = _alive(enemies)
    if not foes:
        return "defend", None

    fallen = [a for a in allies or [] if (a.get("hp") or 0) <= 0]
    if fallen and can_revive(unit):
        return "revive", fallen[0]["id"]

    hurt = [a for a in _alive(allies)
            if a["hp"] <= max(1, a.get("hp_max") or 1) * CRITICAL_HP]
    if hurt:
        return "heal", min(hurt, key=lambda a: a["hp"])["id"]

    if len(foes) >= SWARM:
        return "aoe", None

    return "attack", min(foes, key=lambda f: f["hp"])["id"]
