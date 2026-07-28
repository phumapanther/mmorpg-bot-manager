"""แกนกลาง modifier ของเกม — รวมผล "ทวีป" (Continent Mode) + "อีเวนต์รายสัปดาห์" (Weekly Chaos)
เป็นชุดตัวคูณชุดเดียวที่ระบบเกมเรียกใช้ผ่าน 3 จุด hook ใน game_views.py

เพิ่มทวีป/ธีมใหม่ = เพิ่ม entry ใน CONTINENTS / WEEKLY_THEMES ในไฟล์นี้ ไม่ต้องแตะโค้ดเกม
(เจตนาเดียวกับ Factory/Strategy ในสเปก แต่ทวีป/ธีมของเราคือ "ข้อมูล" ไม่ใช่พฤติกรรม
จึงเก็บเป็น dict — เพิ่มได้โดยไม่แก้โค้ดเดิมตามหลัก Open-Closed เหมือนกัน)
"""
import datetime
import json
import random

from bot.game_data import CONTINENTS, STATUS_EFFECTS, WEEKLY_THEMES  # noqa: F401 (B6 re-export)

# ชุดตัวคูณมาตรฐาน (identity) — ทุกค่าเท่านี้ = เกมทำงานเหมือนไม่มีระบบนี้อยู่
DEFAULT_MODS = {
    "event_weight_mult": {},   # คูณน้ำหนักรายอีเวนต์ เช่น {"monster": 1.5} (ว่าง = ปกติ)
    "rank_weight_mult": {},    # คูณน้ำหนักสุ่มแรงค์มอนสเตอร์ เช่น {"Secret": 3.0} (ว่าง = ปกติ)
    "monster_hp_mult": 1.0,    # คูณ HP มอนสเตอร์ตอนเกิดใหม่
    "monster_dmg_mult": 1.0,   # คูณดาเมจที่มอนสเตอร์ตีใส่ผู้เล่น
    "monster_gold_mult": 1.0,  # คูณทองรางวัลชนะมอนสเตอร์
    "monster_exp_mult": 1.0,   # คูณ EXP รางวัลชนะมอนสเตอร์
    "monster_pool": {},        # ชื่อมอนสเตอร์ธีมราย "แรงค์" เช่น {"Common": ["😈 อิมป์"]} (แรงค์ที่ไม่มี = ใช้ชื่อเดิม)
    "theme_texts": {},         # ข้อความ reskin อีเวนต์ เช่น {"treasure": "...", "trap": "..."} (ไม่มี = ข้อความเดิม)
    "element_weights": {},     # เรทธาตุทับค่ามาตรฐานราย key เช่น {"dark": 35} (ว่าง = เรทสมดุล)
    "element_overrides": {},   # ปรับพารามิเตอร์ธาตุเฉพาะถิ่น เช่น {"wood": {"root_chance": 50}} — ทับรายพารามิเตอร์
    "special_events": [],      # อีเวนต์สุ่มประจำทวีป/ธีม (ต่อกัน) — ดู SpecialEventView ใน game_views
    "combat_hp_drain": None,   # [lo, hi] เลือดผู้เล่นไหลทุกเทิร์นที่สู้ (เช่น เนเธอร์) — None = ไม่มี
    "infusion": None,          # มอนติดบัฟพิเศษตอนเกิด {chance, badge, dmg_mult, drop_items} — None = ไม่มี
    "ambient_status": None,    # สถานะแวดล้อมของธีม (เช่น "frostbite") — ยังไม่ติดจะติดอัตโนมัติทุกก้าว
    "dice_rules": False,       # เปิดกติกาเต๋ารายวัน (ธีมเต๋าแห่งเทพี) — ดู DICE_RULES
    "masquerade": None,        # NPC อาจเป็นมอนปลอมตัว {chance, inspect_fee} (ธีมหน้ากาก) — None = ปิด
    "on_hit_status": None,     # มอนเสกสถานะใส่ผู้เล่นตอนตีโดน {key, chance, turns} ระดับทวีป/ธีม — None = ปิด
                               # (ระดับ "รายธาตุ" ใส่ผ่าน ELEMENTS/element_overrides ด้วย key เดียวกัน)
    "travel_chance_mult": 1.0, # คูณโอกาสเจอพาหนะข้ามทวีป (เช่น แม่น้ำน้ำแข็ง = ×2)
}

# ทวีป — ตัวคูณเกมเพลย์ (mods) เติมในข้อ 3
# CONTINENTS: ย้ายไป bot/game_data.py แล้ว (B6) — ใช้งานเหมือนเดิมทุกอย่าง

# ===== ระบบธาตุมอนสเตอร์ (Elements) =====
# ธาตุ = ข้อมูล + พารามิเตอร์เอฟเฟกต์ที่จุดต่อสู้อ่านไปใช้ — เพิ่มธาตุใหม่ = เพิ่ม entry ที่นี่
# (พารามิเตอร์ที่ไม่ใส่ = ไม่มีเอฟเฟกต์นั้น)

ELEMENTS = {
    # key "player" = passive ประจำธาตุฝั่ง "ผู้เล่น" (จากยศเผ่า, ถือหลายธาตุ = ได้ทุก passive อิสระต่อกัน)
    "fire":  {"label": "🔥 ธาตุไฟ",  "dmg_mult": 1.5,                           # ตีแรงขึ้น 50%
              "on_hit_status": {"key": "burn", "chance": 15},                   # 25% ตีติดแผลแผดเผา
              "player": {"dmg_mult": 1.15, "desc": "ตี +15%"}},                                    # ผู้เล่น: ดาเมจ +15%
    "water": {"label": "💧 ธาตุน้ำ", "lifesteal": 0.35,                         # ดูดเลือด 35% ของดาเมจที่ตีโดน
              "player": {"lifesteal": 0.15, "desc": "ดูดเลือด 15%"}},                                   # ผู้เล่น: ดูดเลือด 15%
    "earth": {"label": "🪨 ธาตุดิน", "hp_mult": 2.0,                            # เลือดหนา 2 เท่า
              "player": {"def_mult": 0.9, "desc": "รับดาเมจ -10%"}},                                     # ผู้เล่น: รับดาเมจ -10%
    "wind":  {"label": "💨 ธาตุลม",  "dice_bonus": (2, 4),                      # เต๋ามอน +2 ถึง +4
              "on_hit_status": {"key": "sealed_dice", "chance": 15},            # 25% ตีติดเต๋าถูกผนึก
              "player": {"roll_bonus": 1, "desc": "เต๋า +1"}},                                     # ผู้เล่น: เต๋า +1 ทุกเทิร์น
    "wood":  {"label": "🌿 ธาตุไม้", "dice_bonus": (2, 4), "root_chance": 25,   # เต๋า+ และ 25% รากล็อกเต๋าผู้เล่น = 0
              "on_hit_status": {"key": "entangled", "chance": 15},              # 25% ตีติดรากพันธนาการ (ห้ามหนี)
              "player": {"step_regen": 0.02, "desc": "ฟื้น 2% MaxHP/ก้าว"}},                                  # ผู้เล่น: สังเคราะห์แสง ฟื้น 2% MaxHP/ก้าว
    "dark":  {"label": "🌑 ธาตุมืด", "pre_enraged": True,                       # คลั่งตั้งแต่เทิร์นแรก
              "player": {"dmg_mult": 1.25, "def_mult": 1.1, "desc": "ตี +25% แต่รับ +10%"}},                   # ผู้เล่น: กระหายเลือด ตี +25% แต่รับ +10%
    "light": {"label": "✨ ธาตุแสง", "monster_flee_chance": 40, "gold_mult": 3.5,  # หนีเก่ง (แบบ Metal Slime) แต่ล้มได้ทองหนัก
              "player": {"reward_mult": 1.1, "desc": "ทอง/EXP +10%"}},                                  # ผู้เล่น: ทอง+EXP ที่ได้ +10%
}


def player_passive_mult(player_elements, param):
    """ผลคูณ passive ธาตุผู้เล่น (dmg_mult/def_mult/reward_mult) — ไม่มีธาตุ/พารามิเตอร์ = 1.0"""
    mult = 1.0
    for e in player_elements or []:
        mult *= ELEMENTS.get(e, {}).get("player", {}).get(param, 1.0)
    return mult


def player_passive_sum(player_elements, param):
    """ผลรวม passive ธาตุผู้เล่น (roll_bonus/lifesteal/step_regen) — ไม่มี = 0"""
    return sum(ELEMENTS.get(e, {}).get("player", {}).get(param, 0) for e in player_elements or [])

# เรทสุ่มธาตุมาตรฐาน (ทวีปหลัก) — สมดุลทุกธาตุ; ทวีป/ธีมทับรายธาตุผ่าน mods["element_weights"]
DEFAULT_ELEMENT_WEIGHTS = {key: 10 for key in ELEMENTS}


def roll_element(mods, rng=None):
    """สุ่มธาตุมอนสเตอร์ตามเรทของทวีป/ธีมสัปดาห์ (overlay ทับเรทมาตรฐานราย key)"""
    weights = {**DEFAULT_ELEMENT_WEIGHTS, **(mods.get("element_weights") or {})}
    keys = list(weights)
    return (rng or random).choices(keys, weights=[weights[k] for k in keys], k=1)[0]


def get_element_data(mods, element_key):
    """ข้อมูลธาตุ "ที่มีผลจริง" = ค่ามาตรฐานจาก ELEMENTS ทับด้วย element_overrides ของทวีป/ธีม
    (ธาตุไม่รู้จัก/None = dict ว่าง ไม่มีเอฟเฟกต์)"""
    base = ELEMENTS.get(element_key)
    if base is None:
        return {}
    override = (mods.get("element_overrides") or {}).get(element_key, {})
    return {**base, **override}


# ===== ระบบสถานะติดตัว (Status Effects) =====
# ติดได้หลายสถานะพร้อมกัน แต่ละตัวมีตัวนับเทิร์นของตัวเอง หมด = ลบออกอัตโนมัติ
# tick "step" = ลดตอนกดเริ่มออกเดินทาง | tick "fight" = ลดตอนเริ่มไฟต์ใหม่ (สแนปช็อตไฟต์นั้นยังมีผลเต็ม)
# เพิ่มสถานะใหม่ = เพิ่ม entry ที่นี่

# STATUS_EFFECTS: ย้ายไป bot/game_data.py แล้ว (B6) — ใช้งานเหมือนเดิมทุกอย่าง


def parse_statuses(player):
    """อ่าน status_effects ของผู้เล่น (JSON str หรือ dict) → {key: เทิร์นเหลือ} เฉพาะที่รู้จักและเทิร์น > 0"""
    raw = (player or {}).get("status_effects") or "{}"
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except ValueError:
            raw = {}
    return {k: int(v) for k, v in (raw or {}).items() if k in STATUS_EFFECTS and int(v) > 0}


def status_cfg(key):
    """ค่าสถานะหลังทับด้วยค่าที่ตั้งใน Panel

    ปรับได้เฉพาะ "จำนวนเทิร์น" กับ "ดาเมจต่อก้าว" ซึ่งเป็นค่าบาลานซ์จริง —
    ที่เหลือ (blocks/transform/cleanse/ตัวคูณ) เป็นโครงสร้างกลไก ไม่เปิดให้แก้
    ตั้งค่าเพี้ยนก็ตกกลับไปใช้ค่าเดิม เกมต้องไม่พังเพราะพิมพ์ผิดในพาแนล
    """
    base = STATUS_EFFECTS.get(key)
    if not base:
        return {}
    ov = (_balance("status_overrides", {}) or {}).get(key)
    if not isinstance(ov, dict):
        return base
    cfg = dict(base)
    try:
        if ov.get("turns") not in (None, ""):
            cfg["default_turns"] = max(1, int(ov["turns"]))
        lo, hi = ov.get("dmg_min"), ov.get("dmg_max")
        if lo not in (None, "") and hi not in (None, ""):
            lo, hi = max(0, int(lo)), max(0, int(hi))
            cfg["step_damage"] = (min(lo, hi), max(lo, hi))
    except (TypeError, ValueError):
        return base
    return cfg


def apply_status(statuses, key, turns=None):
    """ติดสถานะ — ปกติ: ติดซ้ำ = รีเซ็ตตัวนับเป็นค่าใหม่ถ้ามากกว่าของเดิม
    สถานะแบบสะสม (stacking): ติดซ้ำ = สแตกเพิ่ม และครบ transform_at → แปลงร่างเป็นสถานะใหม่
    คืน dict ใหม่เสมอ"""
    if key not in STATUS_EFFECTS:
        return dict(statuses)

    # 🛡️ สถานะภูมิคุ้มกัน: ถ้ามีสถานะที่ block key นี้อยู่ ติดไม่เข้า
    for existing in statuses:
        if key in STATUS_EFFECTS.get(existing, {}).get("blocks", []):
            return dict(statuses)

    cfg = status_cfg(key)
    out = dict(statuses)

    # ติดสถานะนี้แล้วล้างสถานะที่ระบุทิ้ง (เช่น อบอุ่นล้างหนาว)
    for doomed in cfg.get("cleanse_on_apply", []):
        out.pop(doomed, None)

    if cfg.get("stacking"):
        stacks = int(out.get(key, 0)) + int(turns if turns is not None else 1)
        transform_at = cfg.get("transform_at")
        if transform_at and stacks >= transform_at:
            out.pop(key, None)
            transform_to = cfg.get("transform_to")
            if transform_to in STATUS_EFFECTS:
                return apply_status(out, transform_to)
            return out
        out[key] = stacks
        return out

    if turns is None:
        turns = cfg.get("default_turns", 1)
    out[key] = max(int(out.get(key, 0)), int(turns))
    return out


def tick_statuses(statuses, tick_type):
    """ลดตัวนับสถานะประเภท tick นั้นลง 1 — คืน (dict ใหม่, รายชื่อที่หมดฤทธิ์)
    สถานะ no_tick (เช่น เชื้อสะสมสแตก) ไม่ลดเอง"""
    out, expired = {}, []
    for key, turns in statuses.items():
        cfg = STATUS_EFFECTS[key]
        if cfg.get("tick") == tick_type and not cfg.get("no_tick"):
            turns -= 1
        if turns > 0:
            out[key] = turns
        else:
            expired.append(key)
    return out, expired


def cleanse_statuses(statuses, trigger):
    """ล้างสถานะที่มี trigger ใน cleanse_on — คืน (dict ใหม่, รายชื่อที่ถูกล้าง)"""
    out, cleansed = {}, []
    for key, turns in statuses.items():
        if trigger in STATUS_EFFECTS[key].get("cleanse_on", []):
            cleansed.append(key)
        else:
            out[key] = turns
    return out, cleansed


def status_combat_mult(statuses, param):
    """ผลคูณรวมของพารามิเตอร์จากทุกสถานะที่ติดอยู่ (ไม่มี = 1.0)"""
    mult = 1.0
    for key in statuses:
        mult *= STATUS_EFFECTS[key].get(param, 1.0)
    return mult


def has_status_flag(statuses, param):
    """มีสถานะไหนที่เปิดธง param นี้ไหม (เช่น disable_skills)"""
    return any(STATUS_EFFECTS[key].get(param) for key in statuses)


def status_seal_threshold(statuses):
    """เพดานเต๋าจากสถานะผนึก — ทอยถึง/เกินค่านี้ถูกกดเหลือ 1 (ไม่มีสถานะ = None)"""
    values = [STATUS_EFFECTS[k]["seal_high_roll"] for k in statuses if "seal_high_roll" in STATUS_EFFECTS[k]]
    return min(values) if values else None


def status_fumble_chance(statuses):
    """โอกาสเต๋าหลุดมือสูงสุดจากสถานะที่ติด (%)"""
    return max((STATUS_EFFECTS[k].get("fumble_chance", 0) for k in statuses), default=0)


def status_pct_damage(statuses):
    """% MaxHP ที่เสียต่อเทิร์นสู้ (รวมทุกสถานะเผาไหม้)"""
    return sum(STATUS_EFFECTS[k].get("combat_pct_damage", 0) for k in statuses)


def status_monster_dice_bonus(statuses):
    """โบนัสเต๋ามอนสเตอร์รวมจากสถานะที่ติด (เช่น โดนรากรัด)"""
    return sum(STATUS_EFFECTS[k].get("monster_dice_bonus", 0) for k in statuses)


def status_min_roll(statuses):
    """แต้มเต๋าขั้นต่ำการันตีจากสถานะ (เช่น เต๋าถ่วงน้ำหนัก) — ไม่มี = 0"""
    return max((STATUS_EFFECTS[k].get("min_roll", 0) for k in statuses), default=0)


def status_event_weight_mult(statuses):
    """รวมตัวคูณน้ำหนักอีเวนต์จากสถานะที่ติด (เช่น เข็มทิศ ×2 หีบ) — คูณราย key"""
    merged = {}
    for key in statuses:
        for evt, mult in STATUS_EFFECTS[key].get("event_weight_mult", {}).items():
            merged[evt] = merged.get(evt, 1.0) * mult
    return merged


def status_roll_bonus(statuses):
    """โบนัสเต๋าผู้เล่นรวมจากสถานะ/อาร์ติแฟกต์ (เช่น ถุงเต๋าเทพี +1)"""
    return sum(STATUS_EFFECTS[k].get("roll_bonus", 0) for k in statuses)


def status_reroll_vs(statuses, monster_element):
    """โอกาสขอทอยใหม่เมื่อแพ้เต๋าให้มอนธาตุที่ระบุ (%) — เช่น รองเท้าวายุ vs ลม"""
    for key in statuses:
        cfg = STATUS_EFFECTS[key].get("reroll_vs_element")
        if cfg and cfg.get("element") == monster_element:
            return cfg.get("chance", 0)
    return 0


def status_reflect_vs(statuses, monster_element):
    """สัดส่วนสะท้อนดาเมจกลับใส่มอนธาตุที่ระบุ — เช่น แหวนอัคนี vs ไฟ"""
    for key in statuses:
        cfg = STATUS_EFFECTS[key].get("reflect_vs_element")
        if cfg and cfg.get("element") == monster_element:
            return cfg.get("pct", 0)
    return 0


def status_fall_damage_mult(statuses):
    """ตัวคูณดาเมจการร่วง/ถูกดีดข้ามทวีป (รองเท้าวายุ = ×0.5)"""
    mult = 1.0
    for key in statuses:
        mult *= STATUS_EFFECTS[key].get("fall_damage_mult", 1.0)
    return mult


def status_curse_for_roll(statuses, roll):
    """คืน key คำสาปที่ทำงานกับเต๋าค่านี้ (parity ตรง) — ไม่เข้าเงื่อนไข = None"""
    for key in statuses:
        parity = STATUS_EFFECTS[key].get("curse_parity")
        if parity == "odd" and roll % 2 == 1:
            return key
        if parity == "even" and roll > 0 and roll % 2 == 0:
            return key
    return None


def status_skill_shock(statuses, rng=None):
    """เช็คสกิลลัดวงจรจากไฟฟ้าสถิต — คืน (ล้มเหลว?, ดาเมจช็อกตัวเอง)"""
    rng = rng or random
    for key in statuses:
        chance = STATUS_EFFECTS[key].get("skill_fail_chance")
        if chance and rng.randint(1, 100) <= chance:
            lo, hi = STATUS_EFFECTS[key].get("shock_damage", (5, 12))
            return True, rng.randint(lo, hi)
    return False, 0


def roll_step_damage(statuses, rng=None, max_hp=100):
    """รวมเลือดไหลต่อก้าวเดินจากทุกสถานะ — คืน (ดาเมจรวม, [(label, dmg), ...])
    รองรับทั้งช่วงคงที่ (step_damage) และสัดส่วน MaxHP (step_damage_pct เช่น เห็ดบาน 5%)
    สถานะ/อาร์ติแฟกต์ที่มี step_damage_mult (เช่น เสื้อคลุมเปลือกไม้) ช่วยหารเบาลง"""
    rng = rng or random
    mult = 1.0
    for key in statuses:
        mult *= STATUS_EFFECTS[key].get("step_damage_mult", 1.0)
    total, details = 0, []
    for key in statuses:
        cfg = status_cfg(key)          # ดาเมจต่อก้าวปรับได้ที่ Panel
        dmg = 0
        if cfg.get("step_damage"):
            dmg += rng.randint(cfg["step_damage"][0], cfg["step_damage"][1])
        if cfg.get("step_damage_pct"):
            dmg += round(max_hp * cfg["step_damage_pct"])
        if dmg:
            dmg = max(1, round(dmg * mult))
            total += dmg
            details.append((cfg["label"], dmg))
    return total, details


def format_status_line(statuses):
    """บรรทัดสรุปสถานะสำหรับหน้า !play เช่น "☠️ พิษป่า (เหลือ 12 ก้าว) · ⚡ โดน EMP (เหลือ 1 ไฟต์)" """
    parts = []
    for key, turns in statuses.items():
        cfg = STATUS_EFFECTS[key]
        if cfg.get("artifact"):
            parts.append(f"{cfg['label']} (∞)")
            continue
        if cfg.get("stacking"):
            parts.append(f"{cfg['label']} ({turns}/{cfg.get('transform_at', '?')} สแตก)")
            continue
        unit = "ไฟต์" if cfg.get("tick") == "fight" else "ก้าว"
        parts.append(f"{cfg['label']} (เหลือ {turns} {unit})")
    return " · ".join(parts)


# ===== ธาตุประจำตัวผู้เล่น (จากยศเผ่า Discord) =====
# จับคู่ด้วย "คำสำคัญ" ในชื่อยศ — ทนต่อช่องว่าง/อีโมจิ/สัญลักษณ์แปลกในชื่อยศจริง
# เผ่าที่สเปกเขียน "or" (มนุษย์/คนแคระ) = ได้สองธาตุในตัว (จุดขายของเผ่า)

RACE_ELEMENTS = {
    # เผ่าผู้เล่น (GAME_RACES)
    "มนุษย์": ["light", "wind"],
    "เอลฟ์": ["wood"],
    "ยักษ์": ["earth"],
    "คนแคระ": ["earth", "fire"],
    "มังกร": ["fire"],
    "ภูติ": ["wind"],
    "เงือก": ["water"],
    "มิ้ง": ["wind"],
    # เผ่าฝ่ายมอนสเตอร์ (MONSTER_RACES)
    "Dragon": ["fire"],
    "Unicon": ["light"],
    "Slime": ["water"],
    "Ogre": ["earth"],
    "Orc": ["earth"],
    "Goblins": ["wood"],
    "Lich": ["dark"],
    "Skeleton": ["dark"],
    "Zombie": ["dark"],
}

# ตารางแพ้ทาง (ตามสเปก): ธาตุ → ธาตุที่ตีแรงขึ้น ×1.5
ELEMENT_ADVANTAGE = {
    "fire": ["wood"], "water": ["fire"], "earth": ["water"],
    "wood": ["earth"], "wind": ["earth"],
    "light": ["dark"], "dark": ["light"],   # แสง↔มืด สาดใส่กันแรงทั้งคู่
}
# ฝั่งรับ (ตามสเปก): ธาตุ → ธาตุที่รับดาเมจลดเหลือ ×0.75
ELEMENT_RESIST = {
    "fire": ["water"], "water": ["earth"], "earth": ["wood"],
    "wood": ["fire"], "wind": ["fire"],
}


def resolve_player_elements(role_names):
    """แปลงรายชื่อยศของผู้เล่น → รายการธาตุประจำตัว (ไม่ซ้ำ, ลำดับเสถียรตามตาราง)"""
    elements = []
    for keyword, elems in RACE_ELEMENTS.items():
        if any(keyword in str(name) for name in role_names):
            for element in elems:
                if element not in elements:
                    elements.append(element)
    return elements


def player_attack_element_mult(player_elements, monster_element):
    """ตัวคูณดาเมจผู้เล่น→มอนตามธาตุ: ได้เปรียบ 1 ธาตุ = ×1.5, สองธาตุซ้อน = ×2.0 (cap ตามสเปก)"""
    if not monster_element or not player_elements:
        return 1.0
    advantages = sum(1 for e in player_elements if monster_element in ELEMENT_ADVANTAGE.get(e, []))
    if advantages >= 2:
        return 2.0
    if advantages == 1:
        return 1.5
    return 1.0


def forced_weak_element(statuses, player_elements, rng=None):
    """🧪 ยาพลิกธาตุ: คืนธาตุ (สุ่ม) ที่เผ่าผู้เล่นข่ม เมื่อสถานะ force_weak_element ทำงาน — ไม่เข้าเงื่อนไข = None"""
    if not has_status_flag(statuses, "force_weak_element") or not player_elements:
        return None
    pool = sorted({target for e in player_elements for target in ELEMENT_ADVANTAGE.get(e, [])})
    return (rng or random).choice(pool) if pool else None


def player_defense_element_mult(player_elements, monster_element):
    """ตัวคูณดาเมจมอน→ผู้เล่น: ผู้เล่นต้านทานธาตุมอน = ×0.75, ถือธาตุคู่ปรับแสง↔มืด = ×1.5"""
    if not monster_element or not player_elements:
        return 1.0
    if monster_element in ("light", "dark"):
        opposite = "dark" if monster_element == "light" else "light"
        if opposite in player_elements:
            return 1.5
    if any(monster_element in ELEMENT_RESIST.get(e, []) for e in player_elements):
        return 0.75
    return 1.0


# ===== กติกาเต๋ารายวัน (ธีมเต๋าแห่งเทพี) =====
# เปลี่ยนทุกวัน แบบ deterministic จากวันที่ (ทุกเซิร์ฟตรงกัน restart ไม่เปลี่ยน)

DICE_RULES = [
    {"key": "even", "label": "วันเลขคู่ — เต๋าโจมตีออกเลขคู่ ดาเมจ ×2", "match": "even", "dmg_mult": 2.0},
    {"key": "odd", "label": "วันเลขคี่ — เต๋าโจมตีออกเลขคี่ ดาเมจ ×2", "match": "odd", "dmg_mult": 2.0},
    {"key": "high", "label": "วันเต๋าสูง — ทอยได้ 15 ขึ้นไป ดาเมจ ×2.5", "match": "high", "dmg_mult": 2.5},
    {"key": "gamble", "label": "วันเสี่ยงดวง — ทอย 16-20 ดาเมจ ×3 แต่ทอย 1-5 โดนมอนสวนแรงขึ้น",
     "match": "gamble", "dmg_mult": 3.0, "low_penalty_mult": 1.5},
]


def get_daily_dice_rule(when=None):
    """กติกาเต๋าประจำวัน — seed จากวันที่ (แบบเดียวกับธีมรายสัปดาห์แต่หน่วยเป็นวัน)"""
    day = when or datetime.date.today()
    return random.Random(f"dice-{day.isoformat()}").choice(DICE_RULES)


def dice_rule_bonus(rule, roll):
    """เต๋าผู้เล่นเข้ากติกาโบนัสไหม → คืนตัวคูณดาเมจ (ไม่เข้า = 1.0)"""
    match = rule.get("match")
    hit = (
        (match == "even" and roll > 0 and roll % 2 == 0)
        or (match == "odd" and roll % 2 == 1)
        or (match == "high" and roll >= 15)
        or (match == "gamble" and roll >= 16)
    )
    return rule.get("dmg_mult", 1.0) if hit else 1.0


def dice_rule_penalty(rule, roll):
    """เต๋าผู้เล่นเข้าโซนโทษของกติกาไหม → คืนตัวคูณดาเมจที่มอนตีสวน (ไม่เข้า = 1.0)"""
    if rule.get("match") == "gamble" and 1 <= roll <= 5:
        return rule.get("low_penalty_mult", 1.0)
    return 1.0


# ===== อีเวนต์พิเศษประจำทวีป/ธีม (Special Events) =====
# โครง event dict: {key, chance(%), template: "dice_check"|"choice"|"instant", intro, ...}
# - dice_check: pass_roll + success/fail (outcome)
# - choice:     choices: [{label, outcome}]
# - instant:    outcomes: [{weight, ...outcome}] สุ่มทันทีไม่มีปุ่ม
# outcome รองรับ: text, gold, damage, heal("full"/เลข/ช่วง), exp, items[{id, qty}],
#                 apply_status[{key, turns}], cleanse_all, cleanse_random, force_continent


def roll_special_event(mods, rng=None):
    """ทอยอีเวนต์พิเศษของถิ่น/ธีมทีละตัวตามลำดับ — คืน event แรกที่ทอยติด หรือ None"""
    rng = rng or random
    for event in mods.get("special_events") or []:
        if rng.randint(1, 100) <= event.get("chance", 0):
            return event
    return None


# ===== อีเวนต์เงียบสงบ (ไม่มีอะไรเกิดขึ้น — แค่บรรยากาศ) =====


def _balance(path, default=None):
    """อ่านค่าสมดุลจาก Panel (import ในฟังก์ชันกัน circular import)"""
    from bot import config_loader
    return config_loader.get_balance(path, default)


CALM_EVENT_CHANCE = 12  # % ต่อการสุ่มอีเวนต์ปกติหนึ่งครั้ง

CALM_TEXTS = [
    "🍃 สายลมพัดเอื่อยๆ เส้นทางช่วงนี้เงียบสงบ ไม่มีอะไรเกิดขึ้น...",
    "🌤️ คุณเดินทอดน่องชมวิวเพลินๆ วันนี้อากาศดีเป็นพิเศษ",
    "🦋 ฝูงผีเสื้อบินผ่านหน้าไป คุณหยุดมองมันครู่หนึ่งแล้วเดินทางต่อ",
    "🔥 คุณหยุดพักก่อกองไฟเล็กๆ ริมทาง ยืดเส้นยืดสายก่อนออกเดินต่อ",
    "🌾 ทุ่งหญ้ากว้างสุดลูกหูลูกตา เส้นทางราบเรียบไร้สิ่งกีดขวาง",
]


def roll_calm_chance(rng=None):
    """ทอยว่าการสุ่มปกติครั้งนี้เป็นอีเวนต์เงียบสงบไหม"""
    return (rng or random).randint(1, 100) <= int(_balance("events.calm_chance", CALM_EVENT_CHANCE))


def pick_calm_text(rng=None):
    return (rng or random).choice(CALM_TEXTS)


# ===== ระบบเดินทางข้ามทวีป (สุ่มเจอระหว่างผจญภัย ไม่มีคำสั่งเรียกเอง) =====

TRAVEL_EVENT_CHANCE = 8  # % ต่อการสุ่มอีเวนต์ปกติหนึ่งครั้ง

# พาหนะ: weight = โอกาสเจอเทียบกัน, dest_weights = เรทปลายทางของพาหนะนั้น
# (ขึ้นยานแล้วค่อยรู้ปลายทาง — วัดดวงตามเรท, ไม่ไปซ้ำทวีปที่ยืนอยู่)
VEHICLES = {
    "airship": {"label": "🎈 เรือเหาะพ่อค้า",    "weight": 25, "dest_weights": {"main": 40, "demon": 30, "ocean": 30}},
    "ship":    {"label": "⛵ เรือข้ามสมุทร",      "weight": 30, "dest_weights": {"main": 25, "demon": 5,  "ocean": 70}},
    "portal":  {"label": "🕳️ ประตูวาร์ปปริศนา",  "weight": 15, "dest_weights": {"main": 20, "demon": 70, "ocean": 10}},
    "caravan": {"label": "🐎 ขบวนนักเดินทาง",    "weight": 30, "dest_weights": {"main": 60, "demon": 20, "ocean": 20}},
}


def roll_travel_chance(mods=None, rng=None):
    """ทอยว่าการสุ่มปกติครั้งนี้เจอเหตุการณ์เดินทางไหม (ธีมคูณโอกาสได้ผ่าน travel_chance_mult)"""
    chance = int(_balance("events.travel_chance", TRAVEL_EVENT_CHANCE)) * (mods or {}).get("travel_chance_mult", 1.0)
    return (rng or random).randint(1, 100) <= chance


def roll_travel_encounter(player_cash, rng=None):
    """สุ่มพาหนะ + ค่าโดยสาร (0 ถึงเงินสดทั้งกระเป๋า — ไม่แตะธนาคาร)"""
    rng = rng or random
    keys = list(VEHICLES.keys())
    vehicle_key = rng.choices(keys, weights=[VEHICLES[k]["weight"] for k in keys], k=1)[0]
    fare = rng.randint(0, max(0, int(player_cash)))
    return {"vehicle": vehicle_key, "label": VEHICLES[vehicle_key]["label"], "fare": fare}


DEFAULT_DEST_WEIGHT = 10  # ทวีปที่พาหนะไม่ได้ระบุในตาราง ได้ weight นี้อัตโนมัติ


def roll_destination(vehicle_key, current_continent, rng=None):
    """สุ่มทวีปปลายทางตามเรทของพาหนะ โดยตัดทวีปที่ยืนอยู่ออก

    ทวีปที่ไม่อยู่ใน dest_weights ของพาหนะ = ได้ DEFAULT_DEST_WEIGHT อัตโนมัติ
    (เพิ่มทวีปใหม่ใน CONTINENTS แล้วโผล่เป็นปลายทางเองทันที ไม่ต้องแก้พาหนะ)
    ระบุ weight 0 = พาหนะนั้นไม่ไปทวีปนั้นเด็ดขาด"""
    rng = rng or random
    dest_weights = VEHICLES[vehicle_key]["dest_weights"]
    choices = [(k, dest_weights.get(k, DEFAULT_DEST_WEIGHT)) for k in CONTINENTS if k != current_continent]
    choices = [(k, w) for k, w in choices if w > 0]
    if not choices:
        choices = [(k, 1) for k in CONTINENTS if k != current_continent]
    keys, weights = zip(*choices)
    return rng.choices(keys, weights=weights, k=1)[0]

# ธีมรายสัปดาห์ — สุ่มจากเลขสัปดาห์ ISO (get_weekly_theme) เปลี่ยนทุกวันจันทร์
# เพิ่มธีมใหม่ = เพิ่ม entry ที่นี่ (ต้องมี key/label/description/mods; weight = โอกาสเทียบกัน ไม่ใส่ = 1)
# WEEKLY_THEMES: ย้ายไป bot/game_data.py แล้ว (B6) — ใช้งานเหมือนเดิมทุกอย่าง


def _merge(base, extra):
    """รวม mods สองชุด: *_mult = คูณกัน, event_weight_mult = คูณราย key,
    monster_pool = ต่อกัน, theme_texts = extra ทับ base"""
    out = dict(base)
    for key, value in (extra or {}).items():
        if key in ("event_weight_mult", "rank_weight_mult"):
            merged = dict(out.get(key, {}))
            for evt, mult in value.items():
                merged[evt] = merged.get(evt, 1.0) * mult
            out[key] = merged
        elif key == "monster_pool":
            merged_pool = {rank: list(names) for rank, names in out.get(key, {}).items()}
            for rank, names in value.items():
                merged_pool[rank] = merged_pool.get(rank, []) + list(names)
            out[key] = merged_pool
        elif key in ("theme_texts", "element_weights"):
            out[key] = {**out.get(key, {}), **value}
        elif key == "element_overrides":
            # ซ้อนสองชั้น: ราย "ธาตุ" → ราย "พารามิเตอร์" (ธีมทับทวีปรายพารามิเตอร์ ไม่ล้างทั้งธาตุ)
            merged_ov = {elem: dict(params) for elem, params in out.get(key, {}).items()}
            for elem, params in value.items():
                merged_ov[elem] = {**merged_ov.get(elem, {}), **params}
            out[key] = merged_ov
        elif key == "special_events":
            out[key] = list(out.get(key, [])) + list(value)
        elif key in ("combat_hp_drain", "infusion", "ambient_status", "dice_rules", "masquerade", "on_hit_status", "faction_war"):
            out[key] = value  # แทนที่ (ธีมทับทวีป)
        elif key.endswith("_mult"):
            out[key] = out.get(key, 1.0) * value
    return out


# ===== ⚔️ สงครามฝ่าย (Faction War) — P5 =====
# ฝ่ายจากยศเผ่า: เผ่าผู้เล่น (ไทย) = มนุษย์ / เผ่ามอนสเตอร์ (อังกฤษ) = ปีศาจ — keyword match แบบเดียวกับธาตุ
HUMAN_RACES = ("มนุษย์", "เอลฟ์", "ยักษ์", "คนแคระ", "มังกร", "ภูติ", "เงือก", "มิ้ง")
DEMON_RACES = ("Dragon", "Unicon", "Slime", "Ogre", "Orc", "Goblins", "Lich", "Skeleton", "Zombie")

FACTIONS = {
    "human": {"label": "🔵 ฝ่ายมนุษย์", "element": "light", "champion_title": "ผู้กล้าฝ่ายมนุษย์"},
    "demon": {"label": "🔴 ฝ่ายปีศาจ", "element": "dark", "champion_title": "ขุนศึกฝ่ายปีศาจ"},
}
FACTION_WAR_GOLD_MULT = 2.0
FACTION_WAR_EXP_MULT = 1.5


def resolve_player_faction(role_names):
    """ฝ่ายของผู้เล่นจากยศเผ่า: "human" / "demon" / ไม่มียศเผ่า = None (คนกลาง ไม่เกี่ยวสงคราม)
    ถือทั้งสองฝ่าย = ยึดมนุษย์ก่อน (สอดคล้องลำดับตรวจใน profile)"""
    names = [str(n) for n in role_names or []]
    if any(k in n for n in names for k in HUMAN_RACES):
        return "human"
    if any(k in n for n in names for k in DEMON_RACES):
        return "demon"
    return None


# ===== ⚖️ ล่าค่าหัว (Bounty) — P4 =====
BOUNTY_BASE = 10_000
BOUNTY_PER_DEFICIT = 2_000
BOUNTY_CAP = 100_000
BOUNTY_HUNT_SANITY_REWARD = 10   # ฆ่าอาชญากรสำเร็จ = สติคืน (ผดุงยุติธรรม)


def bounty_for(sanity):
    """ค่าหัวตามสติ — สติไม่ติดลบ = ไม่มีหัว (0) | ตัวเลขตั้งได้ที่ Panel"""
    if sanity >= 0:
        return 0
    from bot import config_loader
    base = int(config_loader.get_balance("bounty.base", BOUNTY_BASE))
    per = int(config_loader.get_balance("bounty.per_deficit", BOUNTY_PER_DEFICIT))
    cap = int(config_loader.get_balance("bounty.cap", BOUNTY_CAP))
    return min(cap, base + abs(sanity) * per)


# ===== 📕 สมุดสะสมมอนสเตอร์ (Bestiary) — P3 =====
BESTIARY_RANKS = ["Common", "Mini-Boss", "Main-Boss", "Secret"]  # ครบ 4 นี้ = จบทวีป (ไร้พ่าย = ⭐ โบนัส)
BESTIARY_REWARD_CONTINENT = 100_000
BESTIARY_REWARD_STAR = 200_000
BESTIARY_REWARD_COMPLETE = 1_000_000
BESTIARY_COMPLETE_ITEM = "60"  # 💊 ยาครอบจักรวาล


# 🧬 สมุดธาตุ (ส่วนขยาย): ทวีป × แรงค์ × ธาตุ — นับครบทั้ง 5 แรงค์รวมไร้พ่าย
ELEMENT_BOOK_RANKS = ["Common", "Mini-Boss", "Main-Boss", "Secret", "Unbeatable"]


def element_rank_done(elem_book, continent, rank):
    """ครบทุกธาตุของแรงค์นี้ ในทวีปนี้หรือยัง"""
    return all((continent, rank, e) in elem_book for e in ELEMENTS)


def element_continent_done(elem_book, continent):
    """ครบทุกแรงค์ทุกธาตุในทวีปนี้หรือยัง"""
    return all(element_rank_done(elem_book, continent, r) for r in ELEMENT_BOOK_RANKS)


def element_book_complete(elem_book):
    """ครบทุกทวีป = จบสมุดธาตุทั้งเล่ม"""
    return all(element_continent_done(elem_book, c) for c in CONTINENTS)


def element_progress(elem_book, continent):
    """ความคืบหน้าของทวีปนี้ — (เก็บได้กี่ช่อง, ทั้งหมดกี่ช่อง)"""
    total = len(ELEMENT_BOOK_RANKS) * len(ELEMENTS)
    got = sum(1 for r in ELEMENT_BOOK_RANKS for e in ELEMENTS if (continent, r, e) in elem_book)
    return got, total


def bestiary_continent_done(book, continent):
    """ทวีปนี้เก็บครบ 4 แรงค์หลักหรือยัง — book = {(continent, rank): kills}"""
    return all((continent, r) in book for r in BESTIARY_RANKS)


def bestiary_complete(book):
    """สมุดสมบูรณ์ = ครบ 4 แรงค์หลักในทุกทวีป"""
    return all(bestiary_continent_done(book, c) for c in CONTINENTS)


def get_continent(player):
    """ทวีปปัจจุบันของผู้เล่น — ไม่มี field/ค่าเพี้ยน = ทวีปหลักเสมอ (ปลอดภัยกับผู้เล่นเก่า)"""
    key = (player or {}).get("continent") or "main"
    return CONTINENTS.get(key, CONTINENTS["main"])


# ล็อกธีมโดยแอดมิน (!settheme) — None = สุ่มตามสัปดาห์ปกติ
# (world_admin cog เป็นคนตั้ง/อ่าน และ persist ลงตาราง weekly_state ให้ข้าม restart)
THEME_OVERRIDE = None


def get_theme_by_key(key):
    for theme in WEEKLY_THEMES:
        if theme["key"] == key:
            return theme
    return None


def get_weekly_theme(when=None):
    """ธีมประจำสัปดาห์ ISO — deterministic: สัปดาห์เดียวกันได้ธีมเดิมเสมอ ทุกเครื่อง ทุก restart
    เปลี่ยนเองทุกวันจันทร์โดยไม่ต้องมี scheduler/state; ไม่มีธีมในระบบ = None
    ถ้าแอดมินล็อกธีมไว้ (THEME_OVERRIDE) ใช้ธีมนั้นแทนการสุ่ม"""
    if THEME_OVERRIDE:
        forced = get_theme_by_key(THEME_OVERRIDE)
        if forced:
            return forced
    if not WEEKLY_THEMES:
        return None
    day = when or datetime.date.today()
    year, week, _ = day.isocalendar()
    weights = [theme.get("weight", 1) for theme in WEEKLY_THEMES]
    return random.Random(f"{year}-W{week}").choices(WEEKLY_THEMES, weights=weights, k=1)[0]


def get_active_modifiers(player, when=None):
    """ชุดตัวคูณรวม (ทวีปของผู้เล่น + ธีมสัปดาห์นี้) — จุดเดียวที่โค้ดเกมควรเรียก"""
    mods = _merge(DEFAULT_MODS, get_continent(player).get("mods"))
    theme = get_weekly_theme(when)
    if theme:
        mods = _merge(mods, theme.get("mods"))
    return mods


def pick_monster_name(mods, rank, rng=None):
    """สุ่มชื่อมอนสเตอร์ธีมของแรงค์นี้จากทวีป/ธีมสัปดาห์ — ไม่มีธีมสำหรับแรงค์นี้ = None (ใช้ชื่อเดิม)"""
    pool = (mods.get("monster_pool") or {}).get(rank) or []
    if not pool:
        return None
    return (rng or random).choice(pool)


def apply_event_weights(weights, event_list, mods):
    """คูณน้ำหนักอีเวนต์ตาม event_weight_mult — mult ว่าง = คืน list เดิมค่าเดิมเป๊ะ"""
    mult = mods.get("event_weight_mult") or {}
    if not mult:
        return weights
    return [w * mult.get(evt, 1.0) for w, evt in zip(weights, event_list)]
