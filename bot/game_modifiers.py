"""แกนกลาง modifier ของเกม — รวมผล "ทวีป" (Continent Mode) + "อีเวนต์รายสัปดาห์" (Weekly Chaos)
เป็นชุดตัวคูณชุดเดียวที่ระบบเกมเรียกใช้ผ่าน 3 จุด hook ใน game_views.py

เพิ่มทวีป/ธีมใหม่ = เพิ่ม entry ใน CONTINENTS / WEEKLY_THEMES ในไฟล์นี้ ไม่ต้องแตะโค้ดเกม
(เจตนาเดียวกับ Factory/Strategy ในสเปก แต่ทวีป/ธีมของเราคือ "ข้อมูล" ไม่ใช่พฤติกรรม
จึงเก็บเป็น dict — เพิ่มได้โดยไม่แก้โค้ดเดิมตามหลัก Open-Closed เหมือนกัน)
"""
import datetime
import json
import random

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
            "monster_dmg_mult": 1.3,
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
            # แดนปีศาจ: ธาตุมืดชุก ไฟรองลงมา (ธาตุอื่นเรทมาตรฐาน 10)
            "element_weights": {"dark": 35, "fire": 20},
        },
    },
    "frozen": {
        "label": "❄️ ทวีปน้ำแข็ง",
        "arrival_text": "ลมหนาวบาดผิวราวมีดกรีด แผ่นน้ำแข็งลั่นกรอบแกรบใต้ฝ่าเท้า... ดินแดนที่พายุหิมะไม่เคยหลับใหล",
        "mods": {
            # Blizzard Ambush: ทัศนวิสัยต่ำ เจอมอนถี่ขึ้น; โหด-รางวัลกลางๆ ระหว่าง ocean กับ demon
            "event_weight_mult": {"monster": 1.5},
            "monster_hp_mult": 1.2,
            "monster_gold_mult": 1.6,
            "monster_exp_mult": 1.3,
            "element_weights": {"water": 30, "wind": 20},
            # ความหนาวทำมือแข็ง: มอนที่นี่ตีติด "เต๋าหลุดมือ" ได้
            "on_hit_status": {"key": "fumble", "chance": 20},
            "monster_pool": {
                "Common": ["🦣 เยติ (Yeti)", "🐺 หมาป่าหิมะ (Snow Wolf)"],
                "Mini-Boss": ["⚔️ อัศวินน้ำแข็งโบราณ (Ancient Ice Knight)"],
                "Main-Boss": ["🐉 มังกรน้ำแข็ง (Ice Dragon)"],
            },
            "theme_texts": {
                "treasure": "🧊 คุณพบ **'หีบสมบัติแช่แข็งในผลึกน้ำแข็งพันปี'** เปล่งประกายเย็นเยียบ",
                "trap":     "🕳️ *เพล้ง!* แผ่นน้ำแข็งใต้เท้าแตกร้าว — **'หลุมน้ำแข็งลวง'** เปิดอ้ารอกลืนคุณ!",
            },
            "special_events": [
                {
                    "key": "blizzard_ambush", "chance": 12, "template": "dice_check",
                    "intro": "🌨️ พายุหิมะโหมกระหน่ำจนมองไม่เห็นปลายจมูก! เงาตะคุ่มขนาดมหึมากำลังเคลื่อนเข้ามาในม่านหิมะ... ทอยเต๋าหลบให้พ้น!",
                    "pass_roll": 11,
                    "success": {
                        "text": "🫥 คุณหมอบต่ำหลบหลังโขดน้ำแข็งได้ทันเวลา... เงานั้นเดินผ่านไป และคุณเหลือบเห็นบางอย่างฝังอยู่ในน้ำแข็ง",
                        "items": [{"id": "46", "qty": 1, "chance": 8}],  # 🧊 เกราะเกล็ดน้ำแข็ง (แรร์)
                    },
                    "fail": {
                        "text": "💥 *โครม!* ร่างมหึมาพุ่งทะลุม่านหิมะเข้าใส่คุณเต็มแรง!",
                        "damage": [8, 18],
                        "apply_status": {"key": "numb"},
                        "start_fight": True,
                    },
                },
            ],
        },
    },
    "nether": {
        "label": "💀 ทวีปเนเธอร์",
        "arrival_text": "หมอกสีม่วงหม่นปกคลุมแผ่นดินร้าง เสียงกระซิบของวิญญาณแว่วมาจากทุกทิศ... ที่นี่คือแดนของคนตาย",
        "mods": {
            # แดนวิญญาณ: โหดรองจากปีศาจ + Life Drain ระหว่างสู้ แลกทอง/EXP งาม
            "monster_hp_mult": 1.3,
            "monster_dmg_mult": 1.2,
            "monster_gold_mult": 1.8,
            "monster_exp_mult": 1.4,
            "element_weights": {"dark": 30, "water": 15},
            "combat_hp_drain": [2, 5],
            # แดนวิญญาณ: มอนตีติดคำสาปแต้มคี่ได้
            "on_hit_status": {"key": "odd_curse", "chance": 18},
            "monster_pool": {
                "Common": ["👻 แบนชี (Banshee)", "🧟 กูล (Ghoul)"],
                "Mini-Boss": ["💀 ลิช (Lich)"],
                "Main-Boss": ["👑 ราชันอันเดด (Undead King)"],
            },
            "theme_texts": {
                "treasure": "⚰️ คุณพบ **'โลงศพโบราณลงอาคม'** ฝาโลงแง้มออกเผยประกายสมบัติข้างใน",
                "trap":     "🕸️ วิญญาณอาฆาตผุดขึ้นจากพื้น — **'กับดักมนตร์ต้องสาป'** ล้อมรอบตัวคุณ!",
            },
            "special_events": [
                {
                    "key": "ancestral_feast", "chance": 10, "template": "instant",
                    "intro": (
                        "🕯️ เทียนนับร้อยเล่มจุดสว่างวาบพร้อมกัน... ดวงวิญญาณบรรพชนล้อมวงรอบตัวคุณ\n"
                        "**งานเลี้ยงบรรพชนเริ่มขึ้นแล้ว — เจอแล้วไม่มีทางปฏิเสธ**"
                    ),
                    "outcomes": [
                        {"weight": 1, "text": "💖 บรรพชนพอใจในตัวคุณ ประทานพรฟื้นฟูร่างกายทั้งหมด!", "heal": "full"},
                        {"weight": 1, "text": "✨ บรรพชนเป่ามนตร์ชำระล้างมลทินทั้งปวงออกจากร่าง!", "cleanse_all": True, "exp": [10, 30],
                         "items": [{"id": "47", "qty": 1, "chance": 8}]},  # 📿 สร้อยวิญญาณ (แรร์ — ของขวัญบรรพชน)
                        {"weight": 1, "text": "🌟 บรรพชนหยิบมลทินหนึ่งออกจากวิญญาณของคุณ", "cleanse_random": True, "exp": [10, 30]},
                        {"weight": 1, "text": "😱 บรรพชนพิโรธ! คำสาปโบราณแผดเผาร่างของคุณ!", "damage": [25, 45]},
                        {"weight": 1, "text": "🪙 บรรพชนเรียกร้องเครื่องเซ่น... เงินในถุงของคุณลอยหายไปในความมืด", "gold": [-10000, -2000]},
                        {"weight": 1, "text": "☠️ ไอหมอกพิษแห่งแดนมรณะซึมเข้าสู่ผิวกายของคุณ", "apply_status": {"key": "poison"}},
                    ],
                },
            ],
        },
    },
    "volcanic": {
        "label": "🌋 ทวีปภูเขาไฟ",
        "arrival_text": "อากาศร้อนระอุจนเหงื่อระเหยก่อนหยด แม่น้ำลาวาไหลเอื่อยตัดผ่านแผ่นดินไหม้เกรียม... ระวังการปะทุ!",
        "mods": {
            # Searing Heat: ไฟดุกว่าที่อื่น (override ธาตุไฟ 1.5 → 1.8) + แจกอัญมณีจากการปะทุ
            "monster_hp_mult": 1.25,
            "monster_dmg_mult": 1.15,
            "monster_gold_mult": 1.7,
            "monster_exp_mult": 1.35,
            "element_weights": {"fire": 35, "earth": 15},
            "element_overrides": {"fire": {"dmg_mult": 1.8}},
            "monster_pool": {
                "Common": ["🦎 ซาลาแมนเดอร์เพลิง (Fire Salamander)"],
                "Mini-Boss": ["🗿 โกเลมลาวา (Lava Golem)", "🐦‍🔥 ฟีนิกซ์เถ้าถ่าน (Ash Phoenix)"],
                "Main-Boss": ["🐲 มังกรแสง (Light Dragon)"],
            },
            "theme_texts": {
                "treasure": "🔥 คุณพบ **'หีบเหล็กหลอมกลางธารลาวา'** ยังอุ่นระอุอยู่เลย",
                "trap":     "🌋 พื้นหินสั่นสะเทือน — **'ปล่องไอพิษภูเขาไฟ'** พ่นไอร้อนเข้าใส่คุณ!",
            },
            "special_events": [
                {
                    "key": "volcanic_eruption", "chance": 10, "template": "dice_check",
                    "intro": "🌋 **ภูเขาไฟปะทุ!** เศษหินร้อนแดงพุ่งขึ้นฟ้าแล้วดิ่งลงมาเป็นห่าฝน... ทอยเต๋าหลบให้ทัน!",
                    "pass_roll": 12,
                    "success": {
                        "text": "🏃 คุณพุ่งตัวหลบเข้าซอกผาได้ทัน! และเถ้าถ่านที่ปลิวออกไปเผยให้เห็นอัญมณีฝังอยู่เต็มลานหิน",
                        "items": [{"id": "11", "qty": 10}, {"id": "40", "qty": 1},
                                  {"id": "45", "qty": 1, "chance": 8}],  # 💍 แหวนหินอัคนี (แรร์)
                        "exp": [15, 30],
                    },
                    "fail": {
                        "text": "💥 หินภูเขาไฟถล่มลงมาตรงตัวคุณเต็มๆ!",
                        "damage": [20, 40],
                    },
                },
            ],
        },
    },
    "sylvan": {
        "label": "🌲 ทวีปพงไพร",
        "arrival_text": "เรือนยอดไม้บดบังแสงอาทิตย์จนป่าทั้งผืนมืดสลัว เสียงใบไม้กระซิบราวกับมีชีวิต... ทุกย่างก้าวมีดวงตาจับจ้อง",
        "mods": {
            # Ferocious Flora: ไม้โหด root 50% แต่ฆ่าได้ EXP x2; ทวีปสายฟาร์ม EXP
            "monster_hp_mult": 1.2,
            "monster_dmg_mult": 1.1,
            "monster_gold_mult": 1.5,
            "monster_exp_mult": 1.5,
            "element_weights": {"wood": 35, "earth": 15},
            "element_overrides": {"wood": {"root_chance": 50, "exp_mult": 2.0}},
            "monster_pool": {
                "Common": ["🧝 เอลฟ์ป่าเถื่อน (Savage Forest Elf)", "🪴 พืชกินคนกลายพันธุ์ (Mutant Carnivorous Plant)"],
                "Mini-Boss": ["🌳 เอนท์ ต้นไม้ยักษ์ (Ent)"],
                "Main-Boss": ["🧚 ดรายแอดต้องสาป (Cursed Dryad)"],
            },
            "theme_texts": {
                "treasure": "🌺 คุณพบ **'หีบไม้ถูกเถาวัลย์พันรัดแน่น'** ซ่อนอยู่ใต้พุ่มดอกไม้ประหลาด",
                "trap":     "🌿 รากไม้มีชีวิตพุ่งขึ้นจากพื้นดิน — **'กับดักพฤกษาคลั่ง'** รัดขาคุณไว้!",
            },
            "special_events": [
                {
                    "key": "poison_thicket", "chance": 12, "template": "choice",
                    "intro": (
                        "🌿 พงหนามพิษหนาทึบขวางเส้นทางข้างหน้าจนสุดสายตา หนามทุกอันเยิ้มด้วยยางสีม่วง...\n"
                        "จะฝ่าไปตรงๆ หรือจ้างพรานนำทางอ้อม?"
                    ),
                    "choices": [
                        {
                            "label": "🌿 ลุยฝ่าพงหนาม (เร็วแต่เสี่ยง)",
                            "outcome": {
                                "text": "คุณกัดฟันมุดฝ่าดงหนาม... หนามพิษข่วนตามแขนขาจนแสบร้อนไปทั้งตัว",
                                "apply_status": {"key": "poison"},
                                "items": [{"id": "44", "qty": 1, "chance": 8},   # 🧥 เสื้อคลุมเปลือกไม้ (แรร์ — รางวัลคนกล้า)
                                          {"id": "49", "qty": 1, "chance": 8}],  # 🌟 คทาไม้เทวา (แรร์)
                            },
                        },
                        {
                            "label": "🚶 จ้างพรานนำทางอ้อม (ปลอดภัยแต่เสียเงิน)",
                            "outcome": {
                                "text": "พรานพเนจรพาคุณลัดเลาะออกจากแนวหนามอย่างปลอดภัย",
                                "gold": [-3000, -800],
                            },
                        },
                    ],
                },
            ],
        },
    },
    "mechanized": {
        "label": "⚙️ ทวีปจักรกล",
        "arrival_text": "เสียงเฟืองหมุนดังกึกก้องใต้พื้นโลหะ ไอน้ำพวยพุ่งจากปล่องมหึมา... อารยธรรมโบราณที่ยังไม่เคยหยุดทำงาน",
        "mods": {
            # แดนเทคโนโลยีโบราณ: มอนจักรกลอึด สมบัติแน่น
            "monster_hp_mult": 1.3,
            "monster_dmg_mult": 1.1,
            "monster_gold_mult": 1.9,
            "monster_exp_mult": 1.3,
            "element_weights": {"earth": 25, "fire": 20, "wind": 15},
            # เครื่องจักรปล่อยไฟฟ้าสถิต: มอนตีติดช็อกได้ (สกิลเสี่ยงลัดวงจร)
            "on_hit_status": {"key": "shock", "chance": 20},
            "monster_pool": {
                "Common": ["🤖 หุ่นเชิดไอน้ำ (Steam Puppet)", "🕷️ แมงมุมเฟืองเลเซอร์ (Laser Gear Spider)"],
                "Mini-Boss": ["⚙️ โกเลมลานไก (Clockwork Golem)"],
                "Main-Boss": ["🛡️ ผู้พิทักษ์โบราณ (Ancient Guardian)"],
            },
            "theme_texts": {
                "treasure": "⚙️ คุณพบ **'ตู้นิรภัยจักรกลโบราณ'** เฟืองบนฝายังหมุนติ๊กๆ อยู่เลย",
                "trap":     "⚡ *ฉึก!* พื้นโลหะเปิดออก — **'กับดักสายฟ้าอัตโนมัติ'** ล็อกเป้าตัวคุณ!",
            },
            "special_events": [
                {
                    "key": "emp_field", "chance": 10, "template": "choice",
                    "intro": (
                        "⚡ สนามพลัง EMP สีฟ้าคลื่นแผ่คลุมทางลัดตรงหน้า มองเห็นเศษเหล็กมีค่ากระจัดกระจายอยู่ข้างใน...\n"
                        "จะฝ่าเข้าไปเก็บของ หรือเดินอ้อมแนวปลอดภัย?"
                    ),
                    "choices": [
                        {
                            "label": "⚡ ฝ่าสนาม EMP เก็บเศษเหล็ก (คุ้มแต่เสี่ยง)",
                            "outcome": {
                                "text": "คลื่น EMP วิ่งผ่านร่างจนชาไปทั้งตัว... แต่คุณกอบเศษเหล็กมีค่าติดมือมาได้!",
                                "gold": [500, 2000],
                                "apply_status": {"key": "emp"},
                            },
                        },
                        {
                            "label": "🚶 เดินอ้อมแนวปลอดภัย",
                            "outcome": {
                                "text": "คุณเลาะแนวขอบสนามพลังผ่านไปอย่างระมัดระวัง ไม่มีอะไรเกิดขึ้น",
                            },
                        },
                    ],
                },
                {
                    "key": "ancient_excavation", "chance": 10, "template": "dice_check",
                    "intro": "⚙️ คุณพบ **'หีบกลไกโบราณ'** ฝังครึ่งตัวอยู่ในซากเครื่องจักร แผงปริศนาบนฝากะพริบรอการไข... ทอยเต๋าไขกลไก!",
                    "pass_roll": 12,
                    "success": {
                        "text": "🔓 *คลิก!* กลไกทุกชั้นปลดล็อกพร้อมกัน — ข้างในอัดแน่นด้วยสมบัติสองเท่าของหีบปกติ!",
                        "gold": [1500, 4000],
                        "exp": [20, 40],
                        "items": [{"id": "42", "qty": 1, "chance": 8},    # 🧤 ถุงมือกันคลื่น (แรร์)
                                  {"id": "48", "qty": 1, "chance": 8},    # ⚔️ ดาบคู่แฝด (แรร์)
                                  {"id": "55", "qty": 1, "chance": 10}],  # 🧪 ยาพลิกธาตุ
                    },
                    "fail": {
                        "text": "💥 ไขพลาด! กระแสไฟฟ้าแล่นเข้าใส่มือคุณเต็มเปา!",
                        "damage": [12, 25],
                    },
                },
            ],
        },
    },
    "skyward": {
        "label": "☁️ ทวีปนภา",
        "arrival_text": "คุณเหยียบลงบนเกาะลอยฟ้ากลางทะเลเมฆ แสงอาทิตย์สาดส่องไม่มีอะไรบดบัง... แต่พื้นใต้เท้าสั่นเบาๆ เป็นระยะ",
        "mods": {
            # Gale Winds: แดนของธาตุลม (เต๋าแรง + EXP งาม) และมอนแสงชุกกว่าที่ไหน — แต่เกาะพร้อมถล่มทุกเมื่อ
            "monster_hp_mult": 1.25,
            "monster_dmg_mult": 1.15,
            "monster_gold_mult": 1.6,
            "monster_exp_mult": 1.4,
            "element_weights": {"wind": 35, "light": 15},
            "element_overrides": {"wind": {"dice_bonus": [3, 6], "exp_mult": 1.75}},
            "monster_pool": {
                "Common": ["🦅 อสูรปีก (Winged Beast)", "🗿 การ์กอยล์เวหา (Sky Gargoyle)"],
                "Mini-Boss": ["🦁 กริฟฟิน (Griffin)", "🪶 ครุฑ (Garuda)"],
                "Main-Boss": ["😇 เทวทูตตกสวรรค์ (Fallen Angel)"],
            },
            "theme_texts": {
                "treasure": "☁️ คุณพบ **'หีบเมฆทองคำ'** ลอยเคว้งอยู่ริมขอบเกาะ",
                "trap":     "🌪️ กระแสลมกรรโชก — **'ลมหมุนขอบผา'** ดูดร่างคุณเข้าหาปากเหว!",
            },
            "special_events": [
                {
                    "key": "falling_island", "chance": 10, "template": "dice_check",
                    "intro": (
                        "🏝️ **เกาะที่คุณยืนอยู่สั่นสะเทือนรุนแรง — มันกำลังร่วงจากฟ้า!**\n"
                        "เศษหินหลุดร่วงรอบทิศ... ทอยเต๋าเอาตัวรอด! (ไม่ว่ายังไงคุณจะร่วงกลับทวีปหลัก)"
                    ),
                    "pass_roll": 12,
                    "success": {
                        "text": "🪂 คุณกระโดดคว้าปีกเมฆร่อนลงอย่างหวุดหวิด บาดเจ็บเพียงเล็กน้อย",
                        "items": [{"id": "43", "qty": 1, "chance": 10}],  # 🥾 รองเท้าวายุ (แรร์ — รางวัลนักรอด)
                        "damage": [5, 15],
                        "force_continent": "main",
                    },
                    "fail": {
                        "text": "💥 คุณร่วงลงมาพร้อมซากเกาะทั้งเกาะ!!",
                        "damage": [40, 80],
                        "force_continent": "main",
                    },
                },
            ],
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
            # แดนทะเล: ธาตุน้ำชุก ลมรองลงมา (ธาตุอื่นเรทมาตรฐาน 10)
            "element_weights": {"water": 35, "wind": 20},
        },
    },
}

# ===== ระบบธาตุมอนสเตอร์ (Elements) =====
# ธาตุ = ข้อมูล + พารามิเตอร์เอฟเฟกต์ที่จุดต่อสู้อ่านไปใช้ — เพิ่มธาตุใหม่ = เพิ่ม entry ที่นี่
# (พารามิเตอร์ที่ไม่ใส่ = ไม่มีเอฟเฟกต์นั้น)

ELEMENTS = {
    # key "player" = passive ประจำธาตุฝั่ง "ผู้เล่น" (จากยศเผ่า, ถือหลายธาตุ = ได้ทุก passive อิสระต่อกัน)
    "fire":  {"label": "🔥 ธาตุไฟ",  "dmg_mult": 1.5,                           # ตีแรงขึ้น 50%
              "on_hit_status": {"key": "burn", "chance": 25},                   # 25% ตีติดแผลแผดเผา
              "player": {"dmg_mult": 1.15, "desc": "ตี +15%"}},                                    # ผู้เล่น: ดาเมจ +15%
    "water": {"label": "💧 ธาตุน้ำ", "lifesteal": 0.35,                         # ดูดเลือด 35% ของดาเมจที่ตีโดน
              "player": {"lifesteal": 0.15, "desc": "ดูดเลือด 15%"}},                                   # ผู้เล่น: ดูดเลือด 15%
    "earth": {"label": "🪨 ธาตุดิน", "hp_mult": 2.0,                            # เลือดหนา 2 เท่า
              "player": {"def_mult": 0.9, "desc": "รับดาเมจ -10%"}},                                     # ผู้เล่น: รับดาเมจ -10%
    "wind":  {"label": "💨 ธาตุลม",  "dice_bonus": (2, 4),                      # เต๋ามอน +2 ถึง +4
              "on_hit_status": {"key": "sealed_dice", "chance": 25},            # 25% ตีติดเต๋าถูกผนึก
              "player": {"roll_bonus": 1, "desc": "เต๋า +1"}},                                     # ผู้เล่น: เต๋า +1 ทุกเทิร์น
    "wood":  {"label": "🌿 ธาตุไม้", "dice_bonus": (2, 4), "root_chance": 25,   # เต๋า+ และ 25% รากล็อกเต๋าผู้เล่น = 0
              "on_hit_status": {"key": "entangled", "chance": 25},              # 25% ตีติดรากพันธนาการ (ห้ามหนี)
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

STATUS_EFFECTS = {
    "poison": {
        "label": "☠️ พิษป่า", "tick": "step", "default_turns": 20,
        "step_damage": (3, 6),               # เลือดไหลต่อก้าวเดิน
        "cleanse_on": ["village", "npc"],    # หายเมื่อเจอหมู่บ้าน/NPC
    },
    "numb": {
        "label": "🥶 ชา", "tick": "step", "default_turns": 6,
        "player_dmg_mult": 0.5,              # ดาเมจผู้เล่นในไฟต์ลดครึ่ง
    },
    "emp": {
        "label": "⚡ โดน EMP", "tick": "fight", "default_turns": 1,
        "disable_skills": True,              # ปิดปุ่มสกิลในไฟต์
    },
    "exp_blessing": {
        "label": "🌟 พรบรรพชน", "tick": "step", "default_turns": 10,
        "exp_mult": 1.5,                     # EXP จากมอนสเตอร์คูณระหว่างติด
    },
    "frostbite": {
        "label": "🥶 หนาวกัดกระดูก", "tick": "step", "default_turns": 999,
        "step_damage": (2, 4),               # ความหนาวกัดกินตลอดทาง (ธีม Absolute Zero ติดให้ใหม่เรื่อยๆ)
        "cleanse_on": ["village", "npc", "dungeon"],  # แหล่งความอบอุ่นตามสเปก
    },
    "illegal_buff": {
        "label": "💪 ยาโด๊ปเถื่อน", "tick": "step", "default_turns": 15,
        "player_dmg_mult": 1.3,              # บัฟดาเมจผู้เล่น (สถานะบัฟตัวแรก — hook เดียวกับ "ชา")
    },
    "sealed_dice": {
        "label": "🎲 เต๋าถูกผนึก", "tick": "step", "default_turns": 5,
        "seal_high_roll": 15,                # ทอยได้ >= ค่านี้ ถูกกดเหลือ 1 (ช่วงเต๋าทองหายไป)
    },
    "fumble": {
        "label": "🤲 เต๋าหลุดมือ", "tick": "step", "default_turns": 4,
        "fumble_chance": 30,                 # ต่อเทิร์นสู้: เต๋าหลุดมือ = เต๋าเป็น 0 เสียจังหวะโจมตี
    },
    "burn": {
        "label": "🔥 แผลแผดเผา", "tick": "fight", "default_turns": 3,
        "combat_pct_damage": 0.05,           # เสียเลือด % ของ MaxHP ทุกเทิร์นที่สู้
    },
    "entangled": {
        "label": "🌱 รากไม้พันธนาการ", "tick": "fight", "default_turns": 3,
        "no_flee": True,                     # กดปุ่มวิ่งหนีไม่ได้
        "monster_dice_bonus": 2,             # รากรัดขาขยับยาก — เต๋ามอนสเตอร์ +2
    },
    "odd_curse": {
        "label": "🌑 คำสาปแต้มคี่", "tick": "step", "default_turns": 8,
        "curse_parity": "odd",               # ทอยได้เลขคี่ = โจมตีแป้ก + สะท้อนดาเมจใส่ตัวเอง
        "reflect_pct": 0.2,
    },
    "even_curse": {
        "label": "🌕 คำสาปแต้มคู่", "tick": "step", "default_turns": 8,
        "curse_parity": "even",              # ทอยได้เลขคู่ = ดาเมจกลายเป็นฮีลให้มอนสเตอร์
    },
    "shock": {
        "label": "⚡ ไฟฟ้าสถิต", "tick": "fight", "default_turns": 2,
        "skill_fail_chance": 50,             # กดสกิลมีโอกาสลัดวงจร (กลายเป็นโจมตีธรรมดา)
        "shock_damage": (5, 12),             # + ช็อกตัวเอง
    },
    "zombie_parasite": {
        "label": "🧟 เชื้อซอมบี้", "tick": "step", "default_turns": 1,
        "stacking": True, "no_tick": True,   # ค่าที่เก็บ = จำนวนสแตก (ไม่ลดเอง — แก้ด้วยเสบียง/ล้างสถานะ)
        "transform_at": 3,                   # ครบ 3 สแตก → แปลงร่างเป็นคลั่งซอมบี้
        "transform_to": "zombie_frenzy",
    },
    "zombie_frenzy": {
        "label": "🧟 คลั่งซอมบี้", "tick": "step", "default_turns": 5,
        "seal_high_roll": 2,                 # เต๋าทุกลูกถูกกดเหลือ 1 (ใช้กลไกผนึกเดิม)
    },
    "element_flux": {
        "label": "🧪 ธาตุวิปริต", "tick": "fight", "default_turns": 1,
        "force_weak_element": True,          # ไฟต์ถัดไป: มอนถูกบังคับเกิดเป็นธาตุที่เผ่าผู้เล่นข่ม
    },
    # ── สถานะภูมิคุ้มกันจากไอเทม (เฟส T) ──
    "warm": {
        "label": "🔆 อบอุ่น", "tick": "step", "default_turns": 10,
        "blocks": ["frostbite"],             # กันไม่ให้ติดหนาวกัดกระดูก
        "cleanse_on_apply": ["frostbite"],   # ติดปุ๊บล้างความหนาวเดิมทิ้ง
    },
    "emp_shield": {
        "label": "💾 เกราะกันคลื่น", "tick": "fight", "default_turns": 1,
        "blocks": ["emp"],
        "cleanse_on_apply": ["emp"],
    },
    "featherfall": {
        "label": "🪶 ขนนก", "tick": "step", "default_turns": 30,
        "fall_guard": True,                  # เกาะถล่ม/การร่วง = รอดเสมอ (ดาเมจเหลือขั้นต่ำ) ใช้แล้วหมด
    },
    "holy_guard": {
        "label": "✝️ คุ้มครองศักดิ์สิทธิ์", "tick": "fight", "default_turns": 3,
        "block_hp_drain": True,              # กัน Life Drain (เนเธอร์) สนิท
    },
    "weighted_dice": {
        "label": "🎲 เต๋าถ่วงน้ำหนัก", "tick": "fight", "default_turns": 1,
        "min_roll": 14,                      # การันตีแต้มขั้นต่ำ (ก่อนผลราก/เต๋าหลุดมือ)
        "cleanse_on_apply": ["sealed_dice"], # ใช้แล้วล้างตราผนึกเต๋าทิ้ง
    },
    "clover": {
        "label": "🍀 โคลเวอร์นำโชค", "tick": "fight", "default_turns": 1,
        "block_root": True,                  # กันรากธาตุไม้ (เต๋า=0) หนึ่งครั้งแล้วสลาย
    },
    "convoy_compass": {
        "label": "🧭 เข็มทิศขบวนหลวง", "tick": "step", "default_turns": 20,
        "event_weight_mult": {"treasure": 2.0},  # เจอหีบสมบัติถี่ขึ้นสองเท่า
    },
    "obsidian_edge": {
        "label": "🌋 คมอัคนีเพลิง", "tick": "fight", "default_turns": 1,
        "player_dmg_mult": 1.2,              # อาบคมอาวุธด้วยหินภูเขาไฟ
    },
    # ── อาร์ติแฟกต์ (สถานะถาวรช่องเดียว — สวมทับ = ของเก่าถูกทำลายถาวรตามสเปก) ──
    "art_emp_gauntlet": {
        "label": "🧤 ถุงมือกันคลื่น EMP", "tick": "step", "default_turns": 1,
        "artifact": True, "no_tick": True,
        "blocks": ["emp"], "cleanse_on_apply": ["emp"],
    },
    "art_gale_boots": {
        "label": "🥾 รองเท้าขนนกวายุ", "tick": "step", "default_turns": 1,
        "artifact": True, "no_tick": True,
        "reroll_vs_element": {"element": "wind", "chance": 40},  # แพ้เต๋าให้มอนลม → ขอทอยใหม่
        "fall_damage_mult": 0.5,                                 # ดาเมจการร่วงลดครึ่ง
    },
    "art_sylvan_cloak": {
        "label": "🧥 เสื้อคลุมเปลือกไม้", "tick": "step", "default_turns": 1,
        "artifact": True, "no_tick": True,
        "step_damage_mult": 0.2,             # เลือดไหลจากพิษ/สถานะเหลือ 20%
        "block_root": True,                  # กันรากธาตุไม้ถาวร (ไม่สลายแบบโคลเวอร์)
    },
    "art_fire_ring": {
        "label": "💍 แหวนหินอัคนี", "tick": "step", "default_turns": 1,
        "artifact": True, "no_tick": True,
        "reflect_vs_element": {"element": "fire", "pct": 0.2},   # สะท้อนดาเมจมอนไฟ 20%
    },
    "art_frostward_mail": {
        "label": "🧊 เกราะเกล็ดน้ำแข็ง", "tick": "step", "default_turns": 1,
        "artifact": True, "no_tick": True,
        "blocks": ["numb", "fumble"], "cleanse_on_apply": ["numb", "fumble"],  # ภูมิคุ้มกันความหนาวครบชุด
    },
    "art_nether_amulet": {
        "label": "📿 สร้อยวิญญาณเนเธอร์", "tick": "step", "default_turns": 1,
        "artifact": True, "no_tick": True,
        "hp_drain_heal": 0.03,                                   # แปลง Life Drain เป็นฮีล +3% MaxHP/เทิร์น (ตามสเปก)
        "blocks": ["odd_curse"], "cleanse_on_apply": ["odd_curse"],
    },
    "art_twin_blade": {
        "label": "⚔️ ดาบคู่แฝด", "tick": "step", "default_turns": 1,
        "artifact": True, "no_tick": True,
        "player_dmg_mult": 1.15,                                 # ดาเมจถาวร +15%
    },
    "art_celestial_staff": {
        "label": "🌟 คทาไม้เทวา", "tick": "step", "default_turns": 1,
        "artifact": True, "no_tick": True,
        "exp_mult": 1.25,                                        # EXP ถาวร +25%
    },
    "art_masquerade_monocle": {
        "label": "🎭 แว่นเดี่ยวหน้ากาก", "tick": "step", "default_turns": 1,
        "artifact": True, "no_tick": True,
        "free_inspect": True,                                    # ตรวจสอบ NPC ฟรีตลอดกาล
    },
    "art_goddess_dicebag": {
        "label": "👝 ถุงเต๋าเทพี", "tick": "step", "default_turns": 1,
        "artifact": True, "no_tick": True,
        "roll_bonus": 1,                                         # เต๋าผู้เล่น +1 ทุกเทิร์นถาวร
    },
}


def parse_statuses(player):
    """อ่าน status_effects ของผู้เล่น (JSON str หรือ dict) → {key: เทิร์นเหลือ} เฉพาะที่รู้จักและเทิร์น > 0"""
    raw = (player or {}).get("status_effects") or "{}"
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except ValueError:
            raw = {}
    return {k: int(v) for k, v in (raw or {}).items() if k in STATUS_EFFECTS and int(v) > 0}


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

    cfg = STATUS_EFFECTS[key]
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


def roll_step_damage(statuses, rng=None):
    """รวมเลือดไหลต่อก้าวเดินจากทุกสถานะ — คืน (ดาเมจรวม, [(label, dmg), ...])
    สถานะ/อาร์ติแฟกต์ที่มี step_damage_mult (เช่น เสื้อคลุมเปลือกไม้) ช่วยหารเบาลง"""
    rng = rng or random
    mult = 1.0
    for key in statuses:
        mult *= STATUS_EFFECTS[key].get("step_damage_mult", 1.0)
    total, details = 0, []
    for key in statuses:
        dmg_range = STATUS_EFFECTS[key].get("step_damage")
        if dmg_range:
            dmg = max(1, round(rng.randint(dmg_range[0], dmg_range[1]) * mult))
            total += dmg
            details.append((STATUS_EFFECTS[key]["label"], dmg))
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
    return (rng or random).randint(1, 100) <= CALM_EVENT_CHANCE


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
    chance = TRAVEL_EVENT_CHANCE * (mods or {}).get("travel_chance_mult", 1.0)
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
WEEKLY_THEMES = [
    {
        "key": "normal",
        "label": "🕊️ สัปดาห์สงบสุข",
        "description": "สัปดาห์นี้โลกดำเนินไปตามปกติ ไม่มีเหตุการณ์พิเศษใดๆ — ออกผจญภัยได้อย่างสบายใจ",
        "weight": 11,  # = ผลรวมธีมพิเศษทั้ง 11 ตัว → ครึ่งหนึ่งของสัปดาห์ทั้งหมดเป็นสัปดาห์ปกติ
        "mods": {},
    },
    {
        "key": "palette",
        "label": "🎨 จานสีมอนสเตอร์ (Monster Palette)",
        "description": (
            "สัปดาห์นี้มอนสเตอร์ทั้งแผ่นดินกลายร่างเป็นสีประหลาด! "
            "เจอตัวไหนได้สีอะไรวัดดวงล้วนๆ — กำจัดได้รับทองเพิ่มเป็น 150%"
        ),
        "mods": {
            "monster_gold_mult": 1.5,
            "monster_pool": {
                "Common": [
                    "🔴 สไลม์เพลิงแดงเดือด (Crimson)",
                    "🔵 ก็อบลินน้ำแข็งคราม (Azure)",
                    "🟣 ค้างคาวพิษม่วง (Violet)",
                    "🟡 หมาป่าทองคำ (Golden)",
                ],
                "Mini-Boss": [
                    "🟠 โทรลล์ลาวาส้ม (Amber)",
                    "🟢 อสูรป่ามรกต (Emerald)",
                ],
                "Main-Boss": [
                    "🌈 จอมมารรุ้งสลับสี (Prismatic)",
                ],
            },
            # มอนบางตัวอาบสีเข้มข้น — ล้มได้ดรอปผงสีรุ้ง (ของสะสม/ขาย รอระบบย้อมสีในอนาคต)
            "infusion": {
                "chance": 30,
                "badge": "🎨",
                "label": "อาบสีเข้มข้น",
                "dmg_mult": 1.0,
                "drop_items": {"id": "41", "qty": 1},
            },
        },
    },
    {
        "key": "royal_convoy",
        "label": "👑 ขบวนราชสมบัติล่ม (Royal Convoy Crash)",
        "description": (
            "ขบวนขนสมบัติหลวงถูกซุ่มโจมตี ทรัพย์สินกระจัดกระจายไปทั่วแผ่นดิน! "
            "สัปดาห์นี้เจอหีบสมบัติถี่ขึ้นมาก และทองจากการต่อสู้ทั้งหมด ×2 — ล่าสมบัติกันให้สนุก!"
        ),
        "mods": {
            "event_weight_mult": {"treasure": 1.8},
            "monster_gold_mult": 2.0,
            "theme_texts": {
                "treasure": "👑 คุณพบ **'หีบราชสมบัติหลวงตกหล่น'** ตราประจำราชวงศ์ยังประทับอยู่บนฝา",
            },
        },
    },
    {
        "key": "dragon_nesting",
        "label": "🐉 ฤดูมังกรทำรัง (Dragon Nesting Season)",
        "description": (
            "ฝูงมังกรบินลงมาทำรังทั่วทุกทวีป! มังกรช่วงหวงรังตื่นตัวและดุร้ายกว่าปกติ — "
            "แต่ผู้กล้าที่ล้มมันได้จะได้ทองมหาศาลจากกองสมบัติในรัง"
        ),
        "mods": {
            "event_weight_mult": {"monster": 1.2},
            "monster_dmg_mult": 1.2,
            "monster_gold_mult": 1.8,
            "monster_pool": {
                "Common": ["🐲 ลูกมังกรเพลิง (Dragon Whelp)"],
                "Mini-Boss": ["🐉 มังกรหนุ่มเขี้ยวเพชร (Young Drake)"],
                "Main-Boss": ["🐲 มังกรราชันเวหา (Sky Dragon King)"],
            },
        },
    },
    {
        "key": "solar_eclipse",
        "label": "🌑 สุริยุปราคามืดมิด (Solar Eclipse)",
        "description": (
            "เงาจันทร์กลืนดวงอาทิตย์ ความมืดปกคลุมทุกทวีป! มอนสเตอร์ธาตุมืดแข็งแกร่งและชุกชุมผิดปกติ — "
            "และประตูดันเจี้ยนลับเปิดออก มอนสเตอร์ลับ (Secret) โผล่บ่อยขึ้น 3 เท่า ล่าให้ทันก่อนแสงกลับมา!"
        ),
        "mods": {
            "element_weights": {"dark": 40},
            "element_overrides": {"dark": {"hp_mult": 1.5, "dice_bonus": [2, 4]}},
            "rank_weight_mult": {"Secret": 3.0},
            "monster_exp_mult": 1.3,
        },
    },
    {
        "key": "mana_meteor",
        "label": "☄️ ฝนดาวตกมานา (Mana Meteor Shower)",
        "description": (
            "อุกกาบาตมานาโปรยปรายทั่วฟ้า! มอนสเตอร์ครึ่งหนึ่งอาบพลังอุกกาบาตจนตีแรงขึ้นสองเท่า — "
            "แต่ล้มมันได้จะทิ้ง 🔮 มานาคริสตัลบริสุทธิ์ วัตถุดิบคราฟ 🗡️ อาวุธในตำนาน (คริสตัล ×5)!"
        ),
        "mods": {
            "infusion": {
                "chance": 50,
                "badge": "☄️",
                "label": "อาบพลังอุกกาบาต",
                "dmg_mult": 2.0,
                "drop_items": {"id": "29", "qty": [1, 2]},
            },
        },
    },
    {
        "key": "absolute_zero",
        "label": "🥶 พายุหิมะศูนย์สัมบูรณ์ (Absolute Zero Blizzard)",
        "description": (
            "ความหนาวเหน็บสุดขั้วปกคลุมทุกทวีป! ทุกคนติดสภาวะหนาวกัดกระดูก เลือดไหลไม่หยุด "
            "จนกว่าจะพบความอบอุ่น (หมู่บ้าน/NPC/ดันเจี้ยน) — มอนธาตุน้ำแกร่งเป็นสองเท่า "
            "แต่แม่น้ำที่กลายเป็นน้ำแข็งทำให้พบพาหนะข้ามทวีปบ่อยขึ้นสองเท่า!"
        ),
        "mods": {
            "ambient_status": "frostbite",
            "element_weights": {"water": 35},
            "element_overrides": {"water": {"hp_mult": 2.0}},
            "travel_chance_mult": 2.0,
        },
    },
    {
        "key": "blood_moon",
        "label": "🌕 ล่าจันทร์เลือด (Blood Moon Hunt)",
        "description": (
            "จันทร์เลือดลอยเด่นกลางฟ้า ฝูงอสูรป่าออกล่าทั่วทุกทวีป! หนังหนา ตีเจ็บ และมากันเป็นฝูง — "
            "แต่ซากของพวกมันอุดมด้วยวัสดุ: ทุกการล่าดรอปวัสดุคราฟเพิ่ม 1 ชิ้น และทอง ×1.5"
        ),
        "mods": {
            "event_weight_mult": {"monster": 1.3},
            "monster_hp_mult": 1.5,
            "monster_dmg_mult": 1.25,
            "monster_gold_mult": 1.5,
            "monster_pool": {
                "Common": ["🐺 หมาป่าเวอร์วูล์ฟ (Werewolf)", "🐗 อสูรเขี้ยวโค้ง (Tusked Beast)"],
                "Mini-Boss": ["🌕 จ่าฝูงจันทร์เลือด (Blood Moon Alpha)"],
                "Main-Boss": ["🐺 ราชาหมาป่าจันทรา (Lunar Wolf King)"],
            },
            # ทุกตัวถือเป็น "สัตว์ล่าใต้จันทร์เลือด" — ไม่บัฟดาเมจเพิ่ม (ใช้ monster_dmg_mult แล้ว)
            # แต่ดรอปวัสดุคราฟสุ่มชนิดเพิ่ม 1 ชิ้นทุกการฆ่า
            "infusion": {
                "chance": 100,
                "badge": "🌕",
                "label": "สัตว์ล่าใต้จันทร์เลือด",
                "dmg_mult": 1.0,
                "drop_items": {"id_pool": ["9", "10", "11", "12", "13", "14", "15", "16", "17", "18"], "qty": 1},
            },
        },
    },
    {
        "key": "goddess_dice",
        "label": "🎲 เต๋าแห่งเทพี (Goddess's Dice)",
        "description": (
            "เทพีแห่งโชคชะตาลงมาเล่นเต๋ากับมนุษย์! กติกาพิเศษเปลี่ยนใหม่ทุกวัน "
            "(เช็คกติกาวันนี้ได้ที่หน้า !play) — และตลอดสัปดาห์ EXP ×1.5 ทอง ×1.5"
        ),
        "mods": {
            "dice_rules": True,
            "monster_exp_mult": 1.5,
            "monster_gold_mult": 1.5,
            # เทพีขี้เล่น: มอนตีติดคำสาปแต้มคู่ได้
            "on_hit_status": {"key": "even_curse", "chance": 18},
            "special_events": [
                {
                    "key": "goddess_gamble", "chance": 10, "template": "dice_check",
                    "intro": "🎲 เทพีปรากฏพร้อมโต๊ะพนันลอยฟ้า... *'มาเล่นเต๋ากับข้าสักตาไหม ผู้กล้า?'* — ทอยให้ถึง 15!",
                    "pass_roll": 15,
                    "success": {
                        "text": "🎉 เทพีปรบมือหัวเราะร่วน! 'เจ้ามีดวงของนักพนัน... รับรางวัลไปเถอะ'",
                        "gold": [2000, 6000],
                        "items": [{"id": "51", "qty": 1, "chance": 8},    # 👝 ถุงเต๋าเทพี (แรร์)
                                  {"id": "55", "qty": 1, "chance": 20}],  # 🧪 ยาพลิกธาตุ
                    },
                    "fail": {
                        "text": "😏 เทพีเก็บเต๋าพร้อมรอยยิ้มเจ้าเล่ห์ — 'ค่าเล่นตามระเบียบนะจ๊ะ'",
                        "gold": [-3000, -1000],
                    },
                },
            ],
        },
    },
    {
        "key": "masquerade",
        "label": "🎭 เทศกาลหน้ากากสวมรอย (Masquerade Festival)",
        "description": (
            "เทศกาลหน้ากากมาถึง... แต่มอนสเตอร์ก็แฝงตัวมาร่วมงานด้วย! NPC ที่เจอระหว่างทาง "
            "อาจเป็นของปลอม — จ่ายค่าตรวจสอบก่อนคุยเพื่อความปลอดภัย ไม่งั้นเสี่ยงโดนซุ่มทำร้าย "
            "(ทอง ×1.6 และ EXP ×1.2 ตลอดสัปดาห์)"
        ),
        "mods": {
            "masquerade": {"chance": 40, "inspect_fee": 1500},
            "monster_gold_mult": 1.6,
            "monster_exp_mult": 1.2,
        },
    },
    {
        "key": "black_market",
        "label": "🏴 ตลาดมืดมาบรรจบ (Black Market Convergence)",
        "description": (
            "พ่อค้าตลาดมืดแทรกซึมทุกทวีป! เจอพวกเขาระหว่างทางเพื่อซื้อ 'ของต้องห้าม' — "
            "ยาโด๊ปเถื่อนเพิ่มพลังโจมตี และของหนีภาษีราคาถูกกว่าตลาด (ทอง ×1.4 ตลอดสัปดาห์)"
        ),
        "mods": {
            "monster_gold_mult": 1.4,
            "special_events": [
                {
                    "key": "black_market_dealer", "chance": 14, "template": "choice",
                    "intro": (
                        "🏴 ชายคลุมหน้าโผล่จากเงามืด เปิดผ้าคลุมโชว์สินค้าแวววาว...\n"
                        "*'ของดีราคามิตรภาพ สนใจไหมสหาย? ตำรวจหลวงไม่ต้องรู้...'*"
                    ),
                    "choices": [
                        {
                            "label": "💪 ยาโด๊ปเถื่อน (5,000 ทอง)",
                            "outcome": {
                                "text": "คุณกรอกยาสีม่วงเรืองแสงลงคอ... เลือดลมสูบฉีดพลังพุ่งพล่าน!",
                                "gold": -5000,
                                "apply_status": {"key": "illegal_buff"},
                            },
                        },
                        {
                            "label": "🎒 เหมาของหนีภาษี (4,000 ทอง)",
                            "outcome": {
                                "text": "พ่อค้ายัดห่อของใส่มือคุณแล้วรีบชิ่งหายเข้าเงามืด",
                                "gold": -4000,
                                "items": {"id_pool": ["1", "2", "9", "10", "12", "13", "14", "15", "18", "27"], "qty": [2, 4]},
                            },
                        },
                        {
                            "label": "🎭 ของหายากใต้ผ้าคลุม (15,000 ทอง — วัดดวง)",
                            "outcome": {
                                "text": "พ่อค้าล้วงห่อผ้าดำจากก้นถุง... 'ของชิ้นนี้ข้าได้มาจากงานเต้นรำหลวง อย่าถามต่อ'",
                                "gold": -15000,
                                "items": [{"id": "50", "qty": 1, "chance": 30}],  # 🎭 แว่นเดี่ยวหน้ากาก (วัดดวง 30%)
                            },
                        },
                        {
                            "label": "🚶 เดินผ่านไป",
                            "outcome": {"text": "คุณส่ายหัวแล้วเดินจากไป — ดีลมืดๆ แบบนี้ไม่ใช่แนว"},
                        },
                    ],
                },
            ],
        },
    },
    {
        "key": "zombie",
        "label": "🧟 ซอมบี้บุก (Zombie Invasion)",
        "description": (
            "ฝูงซอมบี้กลายพันธุ์ทะลักเข้าทุกทวีป! เจอมอนสเตอร์ถี่ขึ้น อึดขึ้น ตีเจ็บขึ้น — "
            "แต่กำจัดได้รับทองเป็น 200% และ EXP 150%"
        ),
        "mods": {
            "event_weight_mult": {"monster": 1.4},
            "monster_hp_mult": 1.3,
            "monster_dmg_mult": 1.2,
            "monster_gold_mult": 2.0,
            "monster_exp_mult": 1.5,
            "monster_pool": {
                "Common": ["🧟 ซอมบี้กลายพันธุ์ (Mutant Zombie)", "💥 ซอมบี้ระเบิด (Exploding Zombie)"],
                "Mini-Boss": ["🧟‍♂️ ซอมบี้ไททัน (Zombie Titan)"],
            },
            # กัดแล้วติดเชื้อสะสม (ครบ 3 สแตก = คลั่ง) — แก้ด้วยกล่องเสบียงฉุกเฉินที่พาหะดรอป
            "on_hit_status": {"key": "zombie_parasite", "chance": 35},
            "infusion": {
                "chance": 25,
                "badge": "🦠",
                "label": "พาหะเชื้อกลายพันธุ์",
                "dmg_mult": 1.0,
                "drop_items": {"id": "31", "qty": 1},
            },
        },
    },
]


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
        elif key in ("combat_hp_drain", "infusion", "ambient_status", "dice_rules", "masquerade", "on_hit_status"):
            out[key] = value  # แทนที่ (ธีมทับทวีป)
        elif key.endswith("_mult"):
            out[key] = out.get(key, 1.0) * value
    return out


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
