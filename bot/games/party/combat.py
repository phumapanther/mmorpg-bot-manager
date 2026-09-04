"""🎭 คำนวณดาเมจในโหมดปาร์ตี้ — ตรรกะล้วน ไม่มี I/O

⚠️ ตัวเลขสมดุลทุกตัวตั้งได้ใน Panel ผ่าน `config_loader.get_balance()`
   ตั้งเพี้ยนก็ตกกลับค่าในโค้ด ไม่พังเกม (แบบเดียวกับ adventure_core)

ธาตุใช้ `rules.element_multiplier` ซึ่งยืมตารางของเกมหลักมา
→ ตีมอนธาตุเดียวกันในสองโหมดได้ตัวคูณเท่ากันเป๊ะ
"""
from bot import config_loader
from bot.games.party import rules

# ── ค่าเริ่มต้น (ทับได้ใน Panel ที่ party.*) ──
DEFAULTS = {
    "crit_roll": 20,        # ทอยได้เท่านี้ = คริติคอล
    "crit_mult": 2.0,       # คริแล้วคูณเท่าไหร่
    "skill_mult": 1.6,      # สกิลแรงกว่าตีปกติ (แลกกับเต๋าที่เสี่ยงกว่า)
    "guard_cut": 0.5,       # ป้องกันแล้วโดนเหลือกี่ส่วน
    "aoe_cut": 0.6,         # AoE ต่อตัวอ่อนกว่าตีเดี่ยว
    "aura_cut": 0.5,        # 🛡️ Holy Aura รับดาเมจเหลือกี่ส่วน
    "level_scale": 1.5,     # เลเวลมีผลกับดาเมจแค่ไหน
    "roll_scale": 2.0,      # เต๋ามีผลกับดาเมจแค่ไหน
}


def _bal(key):
    """อ่านค่าสมดุลจาก Panel — ตั้งเพี้ยน/ไม่ตั้ง ก็ตกกลับค่าในโค้ด"""
    try:
        v = config_loader.get_balance(f"party.{key}", DEFAULTS[key])
        return float(v)
    except (TypeError, ValueError):
        return float(DEFAULTS[key])


def _stat(unit, key, default=0):
    try:
        return float(unit.get(key, default) or default)
    except (TypeError, ValueError):
        return float(default)


def damage(attacker, defender, action, roll):
    """ดาเมจที่ attacker ทำใส่ defender — คืน (ดาเมจ, คริติคอลไหม)

    ดาเมจ = (พลังโจมตี + เลเวล + เต๋า) x ตัวคูณคำสั่ง x ตัวคูณธาตุ x คริ - เกราะ
    ไม่ต่ำกว่า 0 เสมอ (ตีแล้วศัตรูเลือดขึ้นไม่ได้)
    """
    base = (_stat(attacker, "atk")
            + _stat(attacker, "level") * _bal("level_scale")
            + float(roll) * _bal("roll_scale"))

    if action == "skill":
        base *= _bal("skill_mult")

    base *= rules.element_multiplier(
        attacker.get("element"), defender.get("element"))

    crit = int(roll) >= int(_bal("crit_roll"))
    if crit:
        base *= _bal("crit_mult")

    return max(0, int(base - _stat(defender, "def"))), crit


def incoming(attacker, defender, dmg, defending=False):
    """ดาเมจที่ defender รับจริง — สั่งป้องกันไว้จะลดลง

    แยกจาก damage() เพราะการป้องกันเป็นสถานะของ "ผู้รับ" ที่ตั้งไว้ตาก่อน
    ตอนคำนวณดาเมจฝั่งผู้ตียังไม่รู้ว่าเป้าป้องกันอยู่ไหม
    """
    out = float(dmg)
    if defending:
        out *= _bal("guard_cut")
    fx = defender.get("fx") or {}
    # 🛡️ Holy Aura ของ Cleric — ทั้งปาร์ตี้รับดาเมจครึ่งเดียวหลายตา
    if int(fx.get("aura") or 0) > 0:
        out *= _bal("aura_cut")
    # 🛡️ Shield Bash ของ Warrior — ยกโล่รับ ลดตามคอนฟิกเกมหลัก
    if int(fx.get("ward") or 0) > 0:
        from bot.games.party import skills
        cut = min(0.9, skills.cfg("shield_bash", "reduction_base", 0.6)
                  + skills.cfg("shield_bash", "reduction_lvl_scale", 0)
                  * int(defender.get("level") or 1))
        out *= max(0.1, 1.0 - cut)
    return max(0, int(out))


def splash(attacker, targets, action, roll):
    """AoE — คืนดาเมจเรียงตามลำดับ targets

    แต่ละตัวอ่อนกว่าตีเดี่ยว ไม่งั้น AoE จะดีกว่าทุกกรณี
    ไม่มีเหตุผลให้ใครเลือกตีเดี่ยวเลย
    """
    cut = _bal("aoe_cut")
    out = []
    for t in targets:
        dmg, _ = damage(attacker, t, action, roll)
        out.append(max(0, int(dmg * cut)))
    return out
