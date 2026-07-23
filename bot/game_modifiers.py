"""แกนกลาง modifier ของเกม — รวมผล "ทวีป" (Continent Mode) + "อีเวนต์รายสัปดาห์" (Weekly Chaos)
เป็นชุดตัวคูณชุดเดียวที่ระบบเกมเรียกใช้ผ่าน 3 จุด hook ใน game_views.py

เพิ่มทวีป/ธีมใหม่ = เพิ่ม entry ใน CONTINENTS / WEEKLY_THEMES ในไฟล์นี้ ไม่ต้องแตะโค้ดเกม
(เจตนาเดียวกับ Factory/Strategy ในสเปก แต่ทวีป/ธีมของเราคือ "ข้อมูล" ไม่ใช่พฤติกรรม
จึงเก็บเป็น dict — เพิ่มได้โดยไม่แก้โค้ดเดิมตามหลัก Open-Closed เหมือนกัน)
"""
import datetime
import random

# ชุดตัวคูณมาตรฐาน (identity) — ทุกค่าเท่านี้ = เกมทำงานเหมือนไม่มีระบบนี้อยู่
DEFAULT_MODS = {
    "event_weight_mult": {},   # คูณน้ำหนักรายอีเวนต์ เช่น {"monster": 1.5} (ว่าง = ปกติ)
    "monster_hp_mult": 1.0,    # คูณ HP มอนสเตอร์ตอนเกิดใหม่
    "monster_gold_mult": 1.0,  # คูณทองรางวัลชนะมอนสเตอร์
    "monster_exp_mult": 1.0,   # คูณ EXP รางวัลชนะมอนสเตอร์
    "monster_pool": {},        # ชื่อมอนสเตอร์ธีมราย "แรงค์" เช่น {"Common": ["😈 อิมป์"]} (แรงค์ที่ไม่มี = ใช้ชื่อเดิม)
    "theme_texts": {},         # ข้อความ reskin อีเวนต์ เช่น {"treasure": "...", "trap": "..."} (ไม่มี = ข้อความเดิม)
}

# ทวีป — ตัวคูณเกมเพลย์ (mods) เติมในข้อ 3
CONTINENTS = {
    "main": {
        "label": "🏰 ทวีปหลัก",
        "arrival_text": "คุณกลับสู่แผ่นดินอันคุ้นเคยของทวีปหลัก ผู้คนพลุกพล่านและปลอดภัย",
        "mods": {},
    },
    "demon": {
        "label": "😈 ทวีปปีศาจ",
        "arrival_text": "ท้องฟ้าสีเลือดทอดเงาทะมึน... คุณเหยียบแผ่นดินทวีปปีศาจแล้ว — ที่นี่อันตรายกว่า แต่รางวัลก็ล้ำค่ากว่า",
        "mods": {
            # เสี่ยงสูง-รางวัลสูง: เจอมอน/กับดักถี่ขึ้น หมู่บ้านหายาก มอนอึดขึ้นแต่จ่ายหนัก
            "event_weight_mult": {"monster": 1.5, "trap": 1.3, "village": 0.5},
            "monster_hp_mult": 1.5,
            "monster_gold_mult": 2.0,
            "monster_exp_mult": 1.5,
            "monster_pool": {
                "Common":    ["😈 อิมป์ (Imp)"],
                "Mini-Boss": ["🖤 อัศวินมืด (Dark Knight)"],
                "Main-Boss": ["👿 จอมมารปีศาจ (Demon Lord)"],
            },
            "theme_texts": {
                "treasure": "🕸️ คุณพบ **'หีบต้องคำสาป (Dark Curse)'** ออร่าดำมืดพวยพุ่งออกมาจากรอยแยกของฝา",
                "trap":     "🌋 พื้นดินแตกร้าว! **'รอยแยกปีศาจ (Demon Rift)'** เปิดอ้าใต้ฝ่าเท้าคุณ!",
            },
        },
    },
    "ocean": {
        "label": "🌊 ทวีปมหาสมุทร",
        "arrival_text": "กลิ่นไอเกลือและเสียงคลื่นต้อนรับคุณสู่ทวีปมหาสมุทร ดินแดนแห่งโจรสลัดและสมบัติใต้ทะเล",
        "mods": {
            # สายสมบัติ: เจอหีบถี่ขึ้น พายุ=กับดักถี่ขึ้นเล็กน้อย มอนแกร่งขึ้นนิดแต่ทองดี
            "event_weight_mult": {"treasure": 1.6, "trap": 1.2},
            "monster_hp_mult": 1.2,
            "monster_gold_mult": 1.5,
            "monster_pool": {
                "Common":    ["🏴‍☠️ โจรสลัดผี (Ghost Pirate)"],
                "Mini-Boss": ["🦈 ฉลามคลั่ง (Mad Shark)"],
                "Main-Boss": ["🧜‍♀️ เงือกโบราณ (Ancient Mermaid)"],
            },
            "theme_texts": {
                "treasure": "🏝️ คลื่นซัดคุณไปเกยหาด **'สมบัติเกาะร้าง (Treasure Island)'** ตรงหน้า",
                "trap":     "🌀 **'พายุเขตร้อน (Tropical Storm)'** โหมกระหน่ำใส่คุณกลางเส้นทาง!",
            },
        },
    },
}

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


def roll_travel_chance(rng=None):
    """ทอยว่าการสุ่มปกติครั้งนี้เจอเหตุการณ์เดินทางไหม"""
    return (rng or random).randint(1, 100) <= TRAVEL_EVENT_CHANCE


def roll_travel_encounter(player_cash, rng=None):
    """สุ่มพาหนะ + ค่าโดยสาร (0 ถึงเงินสดทั้งกระเป๋า — ไม่แตะธนาคาร)"""
    rng = rng or random
    keys = list(VEHICLES.keys())
    vehicle_key = rng.choices(keys, weights=[VEHICLES[k]["weight"] for k in keys], k=1)[0]
    fare = rng.randint(0, max(0, int(player_cash)))
    return {"vehicle": vehicle_key, "label": VEHICLES[vehicle_key]["label"], "fare": fare}


def roll_destination(vehicle_key, current_continent, rng=None):
    """สุ่มทวีปปลายทางตามเรทของพาหนะ โดยตัดทวีปที่ยืนอยู่ออก"""
    rng = rng or random
    dest_weights = VEHICLES[vehicle_key]["dest_weights"]
    choices = [(k, w) for k, w in dest_weights.items() if k != current_continent and w > 0]
    if not choices:
        choices = [(k, 1) for k in CONTINENTS if k != current_continent]
    keys, weights = zip(*choices)
    return rng.choices(keys, weights=weights, k=1)[0]

# ธีมรายสัปดาห์ — ข้อ 4-5 จะเติม palette/zombie
WEEKLY_THEMES = []


def _merge(base, extra):
    """รวม mods สองชุด: *_mult = คูณกัน, event_weight_mult = คูณราย key,
    monster_pool = ต่อกัน, theme_texts = extra ทับ base"""
    out = dict(base)
    for key, value in (extra or {}).items():
        if key == "event_weight_mult":
            merged = dict(out.get(key, {}))
            for evt, mult in value.items():
                merged[evt] = merged.get(evt, 1.0) * mult
            out[key] = merged
        elif key == "monster_pool":
            merged_pool = {rank: list(names) for rank, names in out.get(key, {}).items()}
            for rank, names in value.items():
                merged_pool[rank] = merged_pool.get(rank, []) + list(names)
            out[key] = merged_pool
        elif key == "theme_texts":
            out[key] = {**out.get(key, {}), **value}
        elif key.endswith("_mult"):
            out[key] = out.get(key, 1.0) * value
    return out


def get_continent(player):
    """ทวีปปัจจุบันของผู้เล่น — ไม่มี field/ค่าเพี้ยน = ทวีปหลักเสมอ (ปลอดภัยกับผู้เล่นเก่า)"""
    key = (player or {}).get("continent") or "main"
    return CONTINENTS.get(key, CONTINENTS["main"])


def get_weekly_theme(when=None):
    """ธีมประจำสัปดาห์ ISO — deterministic: สัปดาห์เดียวกันได้ธีมเดิมเสมอ ทุกเครื่อง ทุก restart
    เปลี่ยนเองทุกวันจันทร์โดยไม่ต้องมี scheduler/state; ไม่มีธีมในระบบ = None"""
    if not WEEKLY_THEMES:
        return None
    day = when or datetime.date.today()
    year, week, _ = day.isocalendar()
    return random.Random(f"{year}-W{week}").choice(WEEKLY_THEMES)


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
