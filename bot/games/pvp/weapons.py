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
from bot.games.pvp import physics, terrain

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
    "basic": {"name": "🤜 ตีปกติ", "kind": "melee", "dmg": 15, "reach": 52,
              "cooldown": 0, "crater": 7,
              "desc": "ทุกคลาสใช้ได้ ไม่มีคูลดาวน์ ต่อยจนพื้นเป็นรอย"},

    # ── Warrior ──
    "bash":  {"name": "🛡️ Shield Bash", "kind": "melee", "dmg": 12, "reach": 60,
              "cooldown": 1, "knock": 34, "crater": 8,
              "desc": "กระแทกให้กระเด็นไปไกล พื้นแตกตามแรง"},
    "heavy": {"name": "⚔️ Heavy Strike", "kind": "melee", "dmg": 34, "reach": 52,
              "cooldown": 2, "crater": 12, "desc": "ฟันหนัก พื้นแตกเป็นหลุม"},

    # ── Mage ──
    "fire":  {"name": "🔥 Fireball", "kind": "lob", "dmg": 40, "radius": 26,
              "cooldown": 2, "crater": 26, "desc": "ลูกไฟวิถีโค้ง เจาะพื้นเป็นหลุมใหญ่"},
    "frost": {"name": "❄️ Frostbolt", "kind": "lob", "dmg": 24, "radius": 18,
              "cooldown": 2, "crater": 14, "buff": "slow",
              "desc": "เย็นจนแรงเดินเหลือครึ่งในเทิร์นถัดไป"},

    # ── Rogue ──
    "stab":  {"name": "🗡️ Backstab", "kind": "melee", "dmg": 20, "reach": 48,
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
    "twin_blades": {"name": "⚔️ ดาบคู่แฝด", "kind": "melee", "dmg": 13, "reach": 60,
                    "times": 4, "crater": 9,
                    "desc": "ฟันรัวสี่ครั้งไปทางที่เลือก พื้นแหลกไปด้วย"},
    "divine_staff": {"name": "🌟 คทาไม้เทวา", "kind": "beam", "dmg": 38, "radius": 18,
                     "crater": 12, "desc": "ยิงเลเซอร์เป็นเส้นตรง ทะลุไปไกล"},
}

# 🧪 ยาฮีล — เจอจากหีบเหมือนกัน ใช้ครั้งเดียวหมด
#    ⚠️ ติดป้าย arena_only ไว้ — สองชิ้นนี้ไม่มีในเกมหลัก คิดขึ้นมาสำหรับสนามนี้
#       เทสที่เฝ้าว่า "อาร์ติแฟกต์ในสนามต้องตรงกับเกมหลัก" จะได้ไม่นับรวม
ARTIFACTS.update({
    "herb_potion": {"name": "🧪 ยาสมุนไพร", "kind": "self", "heal": 30,
                    "arena_only": True, "desc": "ฟื้นเลือด 30 ทันที"},
    "great_potion": {"name": "🍶 ยาฟื้นกำลังใหญ่", "kind": "self", "heal": 65,
                     "arena_only": True, "desc": "ฟื้นเลือด 65 ทันที"},
})

# 🏹 อาวุธที่เก็บได้ — ต่างจากอาร์ติแฟกต์ตรงที่ **ใช้ได้ตลอด ไม่มีวันหมด**
#    แต่มีกระสุนจำกัด ยิงจนหมดแล้วต้องรอรีโหลด พอครบก็เต็มกลับมาเอง
#    เก็บซ้ำ = กระสุนสะสมเพิ่ม (เจ้าของเกมเคาะ)
#
#    glide = ยิงตรงไปกี่เฟรมก่อนจะเริ่มตก — นี่คือสิ่งที่ทำให้ธนูต่างจากลูกไฟ
#    (ลูกไฟโค้งตั้งแต่เฟรมแรก · ธนูพุ่งตรงยาวแล้วค่อยย้อยลง)
GEAR = {
    "bow": {"name": "🏹 ธนู", "kind": "lob", "dmg": 26, "radius": 16, "crater": 12,
            "glide": 22, "ammo": 10, "reload": 2, "shots": 1,
            "desc": "ยิงตรงยาวแล้วค่อยตก · 10 นัด หมดแล้วรอ 2 เทิร์น"},
    "crossbow": {"name": "🎯 หน้าไม้", "kind": "lob", "dmg": 17, "radius": 13, "crater": 9,
                 "glide": 18, "ammo": 6, "reload": 3, "shots": 3, "spread": 8,
                 "desc": "ยิงแยกสามแฉกทีเดียว · 6 นัด หมดแล้วรอ 3 เทิร์น"},
}
for _g in GEAR.values():
    _g["gear"] = True
    _g.setdefault("cooldown", 0)

# อาร์ติแฟกต์ทุกชิ้นใช้ครั้งเดียวหมด และไม่มีคูลดาวน์ (ของหายากอยู่แล้ว)
for _a in ARTIFACTS.values():
    _a.setdefault("cooldown", 0)
    _a["artifact"] = True

ALL = {**SKILLS, **ARTIFACTS, **GEAR}

# ของที่ออกจากหีบได้
# ⚠️ เจ้าของเกมสั่ง (08-28): "ทำให้ธนู/หน้าไม้ มีให้เก็บง่ายที่สุด"
#    เดิมอาวุธหายากกว่าเพราะใช้ได้ตลอด (6%) — กลับด้านให้อาวุธเป็นของที่เจอบ่อยที่สุด
CHEST_LOOT = sorted(ARTIFACTS) + sorted(GEAR) * 5


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


def items_view(bag, ammo=None, cooldowns=None):
    """ของที่ถืออยู่ พร้อมแสดงผลบนเว็บ — อาร์ติแฟกต์ (นับชิ้น) + อาวุธ (นับกระสุน)"""
    cds = cooldowns or {}
    out = [{"key": k, "name": ARTIFACTS[k]["name"], "kind": ARTIFACTS[k]["kind"],
            "desc": ARTIFACTS[k]["desc"], "aim": needs_aim(k), "count": n}
           for k, n in sorted((bag or {}).items()) if k in ARTIFACTS and n > 0]
    for k, n in sorted((ammo or {}).items()):
        if k not in GEAR:
            continue
        left = int(cds.get(k, 0))
        out.append({"key": k, "name": GEAR[k]["name"], "kind": GEAR[k]["kind"],
                    "desc": GEAR[k]["desc"], "aim": needs_aim(k), "count": n,
                    "gear": True, "ready_in": left,
                    "reloading": left > 0 or n <= 0})
    return out


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


def melee_targets(attacker, fighters, reach, aim=None):
    """ใครอยู่ในระยะฟันบ้าง — ฟันได้รอบตัว 360° ตามทิศที่เล็ง ไม่ใช่แค่ซ้ายขวา

    aim = เวกเตอร์หนึ่งหน่วยที่เล็งไป · ไม่ส่งมาก็ถือว่าฟันตามทิศที่หันหน้า
    นับเฉพาะครึ่งวงกลมด้านที่หมัดไป — ฟันขึ้นแล้วโดนคนที่อยู่ใต้เท้าด้วยก็แปลก
    """
    ax, ay = aim if aim else (attacker["face"], 0)
    out = []
    for f in fighters:
        if f is attacker or f["dead"]:
            continue
        dx, dy = f["x"] - attacker["x"], f["y"] - attacker["y"]
        if dx * ax + dy * ay < 0:                # อยู่ด้านหลังหมัด ฟันไม่ถึง
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
