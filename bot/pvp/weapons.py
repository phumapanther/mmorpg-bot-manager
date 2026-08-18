"""⚔️ สกิลโจมตีในสนามรบ — ตีปกติ + สกิลประจำคลาส

สกิลมาจาก `CLASS_SKILLS` ชุดเดียวกับเกมหลัก ไม่ได้คิดชื่อใหม่
บางคลาสเป็นแค่บัฟตามที่เจ้าของเกมเคาะ (Cleric ไม่ต้องมีสกิลโจมตี "เขามีฮีล" คือคุ้มแล้ว)

**กติกา: ใช้สกิลแล้วจบเทิร์นทันที** — แนวเดียวกับเกมผลัดเทิร์นทั่วไป
ไม่งั้นยิงรัวทั้งเทิร์นจนอีกฝ่ายไม่มีโอกาสได้เล่น

ชนิดสกิล:
  melee — ฟันระยะประชิดตามทิศที่หัน ไม่ต้องเล็ง
  lob   — กระสุนวิถีโค้ง ต้องเล็งมุมกับแรง ระเบิดเจาะพื้นเป็นหลุม
  beam  — ยิงเป็นเส้นตรง ต้องเล็งมุมอย่างเดียว
  self  — ใช้กับตัวเอง (ฮีล/บัฟ)
"""
from bot.pvp import physics, terrain

# บัฟติดตัวกี่เทิร์น · ทุกอันหมดอายุเอง ไม่งั้นใช้ทีเดียวติดตลอดเกม
BUFFS = {
    "evade": {"name": "💨 หลบหลีก", "turns": 2, "desc": "โจมตีครั้งถัดไปที่โดนจะพลาด"},
    "aura":  {"name": "🛡️ ออร่าศักดิ์สิทธิ์", "turns": 3, "desc": "รับดาเมจครึ่งเดียว"},
    "slow":  {"name": "❄️ แช่แข็ง", "turns": 2, "desc": "แรงเดินเหลือครึ่ง"},
}

# ทุกคลาสมีตีปกติ · ที่เหลือมาจาก CLASS_SKILLS ของเกมหลัก
SKILLS = {
    "basic": {"name": "🤜 ตีปกติ", "kind": "melee", "dmg": 15, "reach": 26,
              "cooldown": 0, "desc": "ทุกคลาสใช้ได้ ไม่มีคูลดาวน์"},

    # ── Warrior ──
    "bash":  {"name": "🛡️ Shield Bash", "kind": "melee", "dmg": 12, "reach": 30,
              "cooldown": 1, "knock": 34, "desc": "กระแทกให้กระเด็นไปไกล"},
    "heavy": {"name": "⚔️ Heavy Strike", "kind": "melee", "dmg": 34, "reach": 26,
              "cooldown": 2, "crater": 12, "desc": "ฟันหนัก พื้นแตกเป็นหลุม"},

    # ── Mage ──
    "fire":  {"name": "🔥 Fireball", "kind": "lob", "dmg": 40, "radius": 26,
              "cooldown": 2, "crater": 26, "desc": "ลูกไฟวิถีโค้ง เจาะพื้นเป็นหลุมใหญ่"},
    "frost": {"name": "❄️ Frostbolt", "kind": "lob", "dmg": 24, "radius": 18,
              "cooldown": 2, "crater": 14, "buff": "slow",
              "desc": "เย็นจนแรงเดินเหลือครึ่งในเทิร์นถัดไป"},

    # ── Rogue ──
    "stab":  {"name": "🗡️ Backstab", "kind": "melee", "dmg": 20, "reach": 24,
              "cooldown": 1, "behind": 2.2, "desc": "ลอบแทงจากด้านหลัง แรงกว่าสองเท่า"},
    "evade": {"name": "💨 Evasion", "kind": "self", "cooldown": 3, "buff": "evade",
              "desc": "หลบการโจมตีครั้งถัดไปได้"},

    # ── Cleric ──
    "heal":  {"name": "✨ Heal", "kind": "self", "cooldown": 2, "heal": 35,
              "desc": "ฟื้นเลือดตัวเอง"},
    "aura":  {"name": "🛡️ Holy Aura", "kind": "self", "cooldown": 3, "buff": "aura",
              "desc": "รับดาเมจครึ่งเดียวไปอีกหลายเทิร์น"},
}

# คลาสไหนใช้อะไรได้ — ตรงกับ CLASS_SKILLS ในเกมหลัก + ตีปกติที่ทุกคนมี
CLASS_KIT = {
    "Warrior": ["basic", "bash", "heavy"],
    "Mage":    ["basic", "fire", "frost"],
    "Rogue":   ["basic", "stab", "evade"],
    "Cleric":  ["basic", "heal", "aura"],
}
DEFAULT_KIT = ["basic"]


def kit_for(cls):
    """สกิลที่คลาสนี้ใช้ได้ — คลาสที่ไม่รู้จักได้แค่ตีปกติ"""
    return CLASS_KIT.get(str(cls or ""), DEFAULT_KIT)


def needs_aim(key):
    """ต้องเล็งมุม/แรงไหม — เว็บจะได้รู้ว่าต้องโชว์แถบเล็งหรือกดยิงได้เลย"""
    return SKILLS.get(key, {}).get("kind") in ("lob", "beam")


def view(cls, cooldowns=None):
    """รายการสกิลพร้อมแสดงผลบนเว็บ"""
    cd = cooldowns or {}
    out = []
    for key in kit_for(cls):
        s = SKILLS[key]
        out.append({"key": key, "name": s["name"], "kind": s["kind"],
                    "desc": s["desc"], "aim": needs_aim(key),
                    "cooldown": s["cooldown"], "ready_in": int(cd.get(key, 0))})
    return out


def hit_box(f, other):
    """ระยะห่างระหว่างจุดกึ่งกลางตัวสองคน"""
    return ((f["x"] - other["x"]) ** 2
            + ((f["y"] - terrain.CH_H // 2) - (other["y"] - terrain.CH_H // 2)) ** 2) ** .5


def melee_targets(attacker, fighters, reach):
    """ใครอยู่ในระยะฟันบ้าง — ต้องอยู่ฝั่งที่หันหน้าไปเท่านั้น"""
    out = []
    for f in fighters:
        if f is attacker or f["dead"]:
            continue
        dx = f["x"] - attacker["x"]
        if dx * attacker["face"] < 0:            # อยู่ข้างหลัง ฟันไม่ถึง
            continue
        if hit_box(attacker, f) <= reach:
            out.append(f)
    return out


def blast_targets(cx, cy, fighters, radius, full):
    """ใครโดนแรงระเบิดบ้าง — คืน [(คน, ดาเมจ)] ลดหลั่นตามระยะ"""
    out = []
    for f in fighters:
        if f["dead"]:
            continue
        d = ((f["x"] - cx) ** 2 + ((f["y"] - terrain.CH_H // 2) - cy) ** 2) ** .5
        dmg = physics.blast_damage(d, radius, full)
        if dmg:
            out.append((f, dmg))
    return out
