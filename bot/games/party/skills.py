"""⚔️ สกิลตามคลาส — ยืมของเกมหลักทั้งชื่อและตัวเลข

⚠️ **ห้ามคิดชื่อสกิลใหม่ ห้ามเขียนตัวเลขสมดุลลงในไฟล์นี้**
   ชื่ออยู่ที่ `bot/views/profile_embed.py: CLASS_SKILLS`
   ตัวเลขอยู่ที่ `config_loader.get_skill_config(คลาส, คีย์)` ซึ่งปรับได้ที่ Panel
   เขียนทับไว้เองเมื่อไหร่ = ปรับที่ Panel แล้วสองโหมดไม่ตรงกัน (มีเทสคุม)

เกมหลักเป็นการต่อสู้ตัวต่อตัว ท่าบางท่าจึงต้องตีความใหม่ให้เข้ากับปาร์ตี้
ตีความไว้ในคอมเมนต์ของแต่ละท่าแล้ว — ยึด "คาแรกเตอร์" ของท่าเดิมไว้
"""
from bot import config_loader

# คีย์ต้องสะกดตรงกับคอนฟิกเกมหลัก (มีเทสคุม)
SPEC = {
    "shield_bash": {
        "name": "🛡️ Shield Bash", "cls": "Warrior", "target": "single", "cd": 3,
        "desc": "กระแทกแล้วยกโล่รับ — รับดาเมจน้อยลงหลายตา",
    },
    "heavy_strike": {
        "name": "⚔️ Heavy Strike", "cls": "Warrior", "target": "single", "cd": 2,
        "desc": "ฟันเต็มแรง ดาเมจหนักและมีลุ้นคริติคอลแรง",
    },
    "fireball": {
        "name": "🔥 Fireball", "cls": "Mage", "target": "all", "cd": 3,
        "desc": "ลูกไฟกวาดศัตรูทั้งหมด พร้อมเผาต่อเนื่อง",
    },
    "frostbolt": {
        "name": "❄️ Frostbolt", "cls": "Mage", "target": "single", "cd": 2,
        "desc": "เย็นจนศัตรูเชื่องช้า ทอยเต๋าได้น้อยลงหลายตา",
    },
    "backstab": {
        "name": "🗡️ Backstab", "cls": "Rogue", "target": "single", "cd": 2,
        "desc": "ลอบแทงจุดตาย ดาเมจทวีคูณ",
    },
    "evasion": {
        "name": "💨 Evasion", "cls": "Rogue", "target": "self", "cd": 3,
        "desc": "หลบการโจมตีครั้งถัดไปได้แน่นอน",
    },
    "heal": {
        "name": "✨ Heal", "cls": "Cleric", "target": "ally_any", "cd": 2,
        "desc": "ฟื้นเลือดเพื่อน · เพื่อนที่ล้มแล้วจะฟื้นคืนสติ",
    },
    "holy_aura": {
        "name": "🛡️ Holy Aura", "cls": "Cleric", "target": "party", "cd": 4,
        "desc": "แสงศักดิ์สิทธิ์คุ้มทั้งปาร์ตี้ รับดาเมจน้อยลงหลายตา",
    },
}

KIT = {}
for _k, _s in SPEC.items():
    KIT.setdefault(_s["cls"], []).append(_k)


def kit_for(cls):
    """สองสกิลของคลาสนี้ — คลาสที่ยังไม่มียศได้ลิสต์ว่าง (ตีกับหนีเท่านั้น)"""
    return list(KIT.get(str(cls or ""), []))


def cfg(key, field, default=0.0):
    """ตัวเลขของท่านี้จากคอนฟิกเกมหลัก — ไม่มีก็ตกกลับค่าที่ส่งมา"""
    spec = SPEC.get(key) or {}
    try:
        c = config_loader.get_skill_config(spec.get("cls", ""), key) or {}
        return float(c.get(field, default))
    except (TypeError, ValueError):
        return float(default)


def _dur(key, level, base_field="duration", scale_field=None):
    """จำนวนตาที่สถานะอยู่ — บางท่ามีตัวคูณตามเลเวลในคอนฟิก"""
    n = cfg(key, base_field, 0)
    if scale_field:
        n += cfg(key, scale_field, 0) * int(level or 1)
    return max(1, int(round(n)))


def use(me, tgt, key, allies, foes, rng):
    """ออกท่าหนึ่งครั้ง — คืน (events, ทอยแพ้ไหม)

    ทอยแพ้ = คนเรียกต้องหักมานา 1 เม็ด (กฎเกมหลัก: ทอยชนะไม่หัก)
    ท่าที่ไม่ต้องทอยแข่ง (บัฟ/ฮีล) ถือว่าไม่แพ้ ไม่เสียมานา
    """
    from bot.games.party import contest, engine, events

    spec = SPEC[key]
    lvl = int(me.get("level") or 1)
    out, lost = [], False

    if key == "heavy_strike":
        # เกมหลัก: damage_multiplier ×2 · คริเมื่อทอยถึง crit_roll_min
        out = engine.strike(me, tgt, "skill", rng, skill_used=True,
                            mult=cfg(key, "damage_multiplier", 2))

    elif key == "backstab":
        # เกมหลัก: damage_reflect_mult ×1.5 — ในปาร์ตี้ใช้เป็นตัวคูณดาเมจตรง ๆ
        out = engine.strike(me, tgt, "skill", rng, skill_used=True,
                            mult=cfg(key, "damage_reflect_mult", 1.5))

    elif key == "shield_bash":
        # เกมหลัก: บัฟลดดาเมจใส่ตัวเอง (reduction_base) นาน duration ตา
        # นี่คือ "ท่าป้องกัน" ของนักรบ — เจ้าของเกมบอกว่าไม่ต้องมีปุ่มป้องกันกลาง
        # เพราะคลาสมีท่านี้อยู่แล้ว จึงต้องคงคาแรกเตอร์เดิมไว้ ไม่ใช่เปลี่ยนเป็นท่าตี
        out = engine.strike(me, tgt, "skill", rng, skill_used=True)
        me.setdefault("fx", {})["ward"] = _dur(key, lvl, "duration")
        out.append(events.buff(me["id"], "ward", me["fx"]["ward"]))

    elif key == "frostbolt":
        out = engine.strike(me, tgt, "skill", rng, skill_used=True)
        if any(e["t"] == "attack" for e in out):
            tgt.setdefault("fx", {})["slow"] = _dur(
                key, lvl, "duration_base", "duration_lvl_scale")

    elif key == "fireball":
        # กวาดทุกตัว — ทอยแข่งทีละเป้าเหมือน AoE ของบอส
        alive = [f for f in foes if f["hp"] > 0]
        dmgs = []
        for f in alive:
            hit = engine.strike(me, f, "skill", rng, skill_used=True,
                                mult=combat_aoe_cut())
            out += [e for e in hit if e["t"] == "contest"]
            dmg = next((e["dmg"] for e in hit if e["t"] == "attack"), 0)
            dmgs.append(dmg)
            if dmg:
                f.setdefault("fx", {})["burn"] = _dur(key, lvl, "duration")
            out += [e for e in hit if e["t"] == "die"]
        out.append(events.aoe(me["id"], [f["id"] for f in alive], dmgs,
                              me.get("element")))

    elif key == "evasion":
        me.setdefault("fx", {})["evade"] = 1
        out.append(events.buff(me["id"], "evade", 1))

    elif key == "holy_aura":
        n = _dur(key, lvl, "chance_base", "chance_lvl_scale")
        n = max(1, min(4, n // 25))        # แปลงเปอร์เซ็นต์ของเกมหลักเป็นจำนวนตา
        for a in allies:
            a.setdefault("fx", {})["aura"] = n
            out.append(events.buff(a["id"], "aura", n))

    elif key == "heal":
        pct = cfg(key, "heal_percent_base", 0.4) + cfg(key, "heal_lvl_scale", 0.01) * lvl
        amount = max(1, int(tgt["hp_max"] * pct))
        was_down = tgt["hp"] <= 0
        tgt["hp"] = min(tgt["hp_max"], max(0, tgt["hp"]) + amount)
        out.append(events.heal(me["id"], tgt["id"], amount))
        if was_down:
            out.append(events.buff(tgt["id"], "revived", 1))

    if spec["target"] in ("single", "all"):
        lost = not any(e.get("hit") for e in out if e["t"] == "contest")
    return out, lost


def combat_aoe_cut():
    """ตัวคูณ AoE ต่อเป้า — อ่านจากค่าสมดุลเดียวกับ combat.splash"""
    from bot.games.party import combat
    return combat._bal("aoe_cut")
