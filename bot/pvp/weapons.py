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
    "evade":  {"name": "💨 หลบหลีก", "turns": 2, "desc": "โจมตีครั้งถัดไปที่โดนจะพลาด"},
    "aura":   {"name": "🛡️ ออร่าศักดิ์สิทธิ์", "turns": 3, "desc": "รับดาเมจครึ่งเดียว"},
    "slow":   {"name": "❄️ แช่แข็ง", "turns": 2, "desc": "แรงเดินเหลือครึ่ง"},
    # จากอาร์ติแฟกต์
    "emp":    {"name": "⚡ คลื่น EMP", "turns": 2, "desc": "ทำได้แค่เดิน ใช้สกิล/ไอเทมไม่ได้"},
    "feather": {"name": "🥾 ขนนกวายุ", "turns": 3, "desc": "ตกจากที่สูงไม่เจ็บ"},
    "bark":   {"name": "🧥 เปลือกไม้", "turns": 4, "desc": "กันการโจมตีได้ 1 ครั้ง"},
    "reflect": {"name": "🧊 เกล็ดน้ำแข็ง", "turns": 3, "desc": "สะท้อนดาเมจกลับครึ่งหนึ่ง"},
}

# ทุกคลาสมีตีปกติ · ที่เหลือมาจาก CLASS_SKILLS ของเกมหลัก
SKILLS = {
    "basic": {"name": "🤜 ตีปกติ", "kind": "melee", "dmg": 15, "reach": 26,
              "cooldown": 0, "crater": 7,
              "desc": "ทุกคลาสใช้ได้ ไม่มีคูลดาวน์ ต่อยจนพื้นเป็นรอย"},

    # ── Warrior ──
    "bash":  {"name": "🛡️ Shield Bash", "kind": "melee", "dmg": 12, "reach": 30,
              "cooldown": 1, "knock": 34, "crater": 8,
              "desc": "กระแทกให้กระเด็นไปไกล พื้นแตกตามแรง"},
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
              "cooldown": 1, "behind": 2.2, "crater": 6,
              "desc": "ลอบแทงจากด้านหลัง แรงกว่าสองเท่า"},
    "evade": {"name": "💨 Evasion", "kind": "self", "cooldown": 3, "buff": "evade",
              "desc": "หลบการโจมตีครั้งถัดไปได้"},

    # ── Cleric ──
    "heal":  {"name": "✨ Heal", "kind": "self", "cooldown": 2, "heal": 35,
              "desc": "ฟื้นเลือดตัวเอง"},
    "aura":  {"name": "🛡️ Holy Aura", "kind": "self", "cooldown": 3, "buff": "aura",
              "desc": "รับดาเมจครึ่งเดียวไปอีกหลายเทิร์น"},
}

# 🏺 อาร์ติแฟกต์ = ไอเทมโจมตีในสนาม — เจอจากหีบสมบัติ ใช้ได้ครั้งเดียวแล้วหมด
#
# ⚠️ **ไม่ได้ดึงมาจากกระเป๋าในเกมหลัก** — มินิเกมแยกขาดจากเกมปกติตามที่เจ้าของเกมเคาะ
#    ทุกคนเข้าสนามมือเปล่าเท่ากัน ของหาเอาในสนาม
# ใส่แค่ 8 ชิ้นจาก 11 ชิ้น (แว่นเดี่ยวหน้ากาก · ถุงเต๋าเทพี · ปริซึมมานา ไม่ใส่)
ARTIFACTS = {
    "emp_glove": {"name": "🧤 ถุงมือกันคลื่น EMP", "kind": "lob", "dmg": 14, "radius": 30,
                  "crater": 10, "buff": "emp",
                  "desc": "ยิงคลื่น EMP — คนที่โดนทำได้แค่เดิน ใช้สกิลไม่ได้"},
    "feather_boots": {"name": "🥾 รองเท้าขนนกวายุ", "kind": "self", "buff": "feather",
                      "desc": "ตกจากที่สูงไม่เจ็บไปอีกหลายเทิร์น"},
    "bark_cloak": {"name": "🧥 เสื้อคลุมเปลือกไม้", "kind": "self", "buff": "bark",
                   "desc": "กันการโจมตีได้ 1 ครั้ง"},
    "flame_ring": {"name": "💍 แหวนหินอัคนี", "kind": "lob", "dmg": 46, "radius": 24,
                   "crater": 22, "desc": "ยิงไฟวิถีโค้ง แรงกว่าลูกไฟธรรมดา"},
    "ice_scale": {"name": "🧊 เกราะเกล็ดน้ำแข็ง", "kind": "self", "buff": "reflect",
                  "desc": "สะท้อนดาเมจที่รับมาครึ่งหนึ่งกลับไป"},
    "nether_beads": {"name": "📿 สร้อยวิญญาณเนเธอร์", "kind": "lob", "dmg": 30, "radius": 52,
                     "crater": 16,
                     "desc": "ปล่อยวิญญาณเป็นวงกว้าง ใครอยู่ใกล้โดนหมด"},
    "twin_blades": {"name": "⚔️ ดาบคู่แฝด", "kind": "melee", "dmg": 13, "reach": 30,
                    "times": 4, "crater": 9,
                    "desc": "ฟันรัวสี่ครั้งไปทางที่เลือก พื้นแหลกไปด้วย"},
    "divine_staff": {"name": "🌟 คทาไม้เทวา", "kind": "beam", "dmg": 38, "radius": 18,
                     "crater": 12, "desc": "ยิงเลเซอร์เป็นเส้นตรง ทะลุไปไกล"},
}

# อาร์ติแฟกต์ทุกชิ้นใช้ครั้งเดียวหมด และไม่มีคูลดาวน์ (ของหายากอยู่แล้ว)
for _a in ARTIFACTS.values():
    _a.setdefault("cooldown", 0)
    _a["artifact"] = True

ALL = {**SKILLS, **ARTIFACTS}


def spec(key):
    """ข้อมูลสกิล/อาร์ติแฟกต์ชิ้นหนึ่ง — None ถ้าไม่มีจริง"""
    return ALL.get(str(key or ""))


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
    return (spec(key) or {}).get("kind") in ("lob", "beam")


def items_view(bag):
    """อาร์ติแฟกต์ที่ถืออยู่ พร้อมแสดงผลบนเว็บ"""
    return [{"key": k, "name": ARTIFACTS[k]["name"], "kind": ARTIFACTS[k]["kind"],
             "desc": ARTIFACTS[k]["desc"], "aim": needs_aim(k), "count": n}
            for k, n in sorted((bag or {}).items()) if k in ARTIFACTS and n > 0]


def view(cls, cooldowns=None):
    """รายการสกิลประจำคลาสพร้อมแสดงผลบนเว็บ (อาร์ติแฟกต์แยกไปที่ items_view)"""
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


def path_targets(path, fighters, exclude=None):
    """ใครโดนลำแสงที่พาดผ่านบ้าง — เช็คว่าเส้นทางตัดผ่านตัวใคร

    เลเซอร์ต้องโดนทุกคนที่มันวิ่งผ่าน ไม่ใช่แค่คนที่อยู่ตรงจุดที่ลำแสงชนพื้น
    (เคยพลาด: คิดดาเมจแค่ปลายทาง ยิงทะลุกลางตัวคู่ต่อสู้ก็ไม่โดนเลย)
    """
    half = terrain.CH_W // 2
    hit = []
    for f in fighters:
        if f["dead"] or f is exclude or f in hit:
            continue
        for px, py in path:
            if abs(px - f["x"]) <= half and f["y"] - terrain.CH_H <= py <= f["y"]:
                hit.append(f)
                break
    return hit


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
