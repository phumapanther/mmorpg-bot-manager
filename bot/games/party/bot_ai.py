"""🎭 บอทเล่นแทนคนที่หลุดหรือ AFK — ตรรกะล้วน ไม่แตะ DB ไม่แตะห้อง

⚠️ **หน้าที่เดียวคือ "ทำให้เกมเดินต่อ" ไม่ใช่เล่นเก่ง**
   คน AFK คนเดียวห้ามค้างทั้งปาร์ตี้ (สเปกข้อ 4)
   บอทเก่งเกินไปกลับแย่ — คนจะปล่อยให้บอทเล่นแทนแล้วไปทำอย่างอื่น

⚠️ **ห้ามสั่ง `flee` เด็ดขาด** — หนีคือจบเกมให้ทั้งปาร์ตี้
   คนหลุดคนเดียวไม่มีสิทธิ์ตัดสินใจแทนอีก 4 คน

⚠️ บอทเลือกได้เฉพาะท่าที่ **คลาสตัวเองมีจริงและพร้อมใช้** — สั่งท่าที่ใช้ไม่ได้
   แล้วเซิร์ฟปฏิเสธ เกมจะค้างตรงนั้นตลอดกาล
"""
from bot.games.party import skills

CRITICAL_HP = 0.35      # เลือดต่ำกว่านี้ถือว่าวิกฤต ต้องฮีลก่อน
SWARM = 3               # ศัตรูเยอะกว่านี้ กวาดคุ้มกว่าตีเดี่ยว


def _alive(units):
    return [u for u in units or [] if (u.get("hp") or 0) > 0]


def ready(unit, key):
    """ท่านี้พร้อมใช้ไหม — คลาสตรง คูลดาวน์หมด และยังมีเม็ดคริสตัล"""
    if key not in skills.kit_for(unit.get("class_name")):
        return False
    if int((unit.get("cd") or {}).get(key) or 0) > 0:
        return False
    return unit.get("mana_left") is None or int(unit["mana_left"]) > 0


def choose(unit, allies, enemies, rng):
    """เลือกหนึ่งท่าแทนผู้เล่น — คืน (action, target_id)

    ลำดับความสำคัญ:
      1. ชุบเพื่อนที่ล้ม (Cleric ใช้ ✨ Heal · คนอื่นใช้ใบชุบชีวิต)
      2. ฮีลคนที่เลือดวิกฤต
      3. กวาดเมื่อศัตรูเยอะ (🔥 Fireball)
      4. ท่าโจมตีของคลาสตัวเองถ้าพร้อม
      5. ตีปกติใส่ตัวที่ใกล้ตายที่สุด
    """
    foes = _alive(enemies)
    if not foes:
        return "attack", None

    fallen = [a for a in allies or [] if (a.get("hp") or 0) <= 0]
    if fallen:
        if ready(unit, "heal"):
            return "heal", fallen[0]["id"]
        if unit.get("can_revive"):
            return "revive", fallen[0]["id"]

    hurt = [a for a in _alive(allies)
            if a["hp"] <= max(1, a.get("hp_max") or 1) * CRITICAL_HP]
    if hurt and ready(unit, "heal"):
        return "heal", min(hurt, key=lambda a: a["hp"])["id"]

    if len(foes) >= SWARM and ready(unit, "fireball"):
        return "fireball", None

    weakest = min(foes, key=lambda f: f["hp"])["id"]
    for key in skills.kit_for(unit.get("class_name")):
        spec = skills.SPEC[key]
        if spec["target"] != "single" or not ready(unit, key):
            continue
        return key, weakest

    if ready(unit, "holy_aura") and len(_alive(allies)) > 1:
        return "holy_aura", None
    if ready(unit, "evasion") and unit.get("hp", 1) <= \
            max(1, unit.get("hp_max") or 1) * CRITICAL_HP:
        return "evasion", None

    return "attack", weakest
