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
                    "success": {"text": "🫥 คุณหมอบต่ำหลบหลังโขดน้ำแข็งได้ทันเวลา... เงานั้นเดินผ่านไปอย่างเฉียดฉิว"},
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
                        {"weight": 1, "text": "✨ บรรพชนเป่ามนตร์ชำระล้างมลทินทั้งปวงออกจากร่าง!", "cleanse_all": True, "exp": [10, 30]},
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
                        "items": {"id": "11", "qty": 10},
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
    "fire":  {"label": "🔥 ธาตุไฟ",  "dmg_mult": 1.5},                          # ตีแรงขึ้น 50%
    "water": {"label": "💧 ธาตุน้ำ", "lifesteal": 0.35},                        # ดูดเลือด 35% ของดาเมจที่ตีโดน
    "earth": {"label": "🪨 ธาตุดิน", "hp_mult": 2.0},                           # เลือดหนา 2 เท่า
    "wind":  {"label": "💨 ธาตุลม",  "dice_bonus": (2, 4)},                     # เต๋ามอน +2 ถึง +4
    "wood":  {"label": "🌿 ธาตุไม้", "dice_bonus": (2, 4), "root_chance": 25},  # เต๋า+ และ 25% รากพันธนาการล็อกเต๋าผู้เล่น = 0
    "dark":  {"label": "🌑 ธาตุมืด", "pre_enraged": True},                      # คลั่งตั้งแต่เทิร์นแรก
    "light": {"label": "✨ ธาตุแสง", "monster_flee_chance": 40, "gold_mult": 3.5},  # หนีเก่ง (แบบ Metal Slime) แต่ล้มได้ทองหนัก
}

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
    """ติดสถานะ — ติดซ้ำ = รีเซ็ตตัวนับเป็นค่าใหม่ถ้ามากกว่าของเดิม; คืน dict ใหม่"""
    if key not in STATUS_EFFECTS:
        return dict(statuses)
    if turns is None:
        turns = STATUS_EFFECTS[key].get("default_turns", 1)
    out = dict(statuses)
    out[key] = max(int(out.get(key, 0)), int(turns))
    return out


def tick_statuses(statuses, tick_type):
    """ลดตัวนับสถานะประเภท tick นั้นลง 1 — คืน (dict ใหม่, รายชื่อที่หมดฤทธิ์)"""
    out, expired = {}, []
    for key, turns in statuses.items():
        if STATUS_EFFECTS[key].get("tick") == tick_type:
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


def roll_step_damage(statuses, rng=None):
    """รวมเลือดไหลต่อก้าวเดินจากทุกสถานะ — คืน (ดาเมจรวม, [(label, dmg), ...])"""
    rng = rng or random
    total, details = 0, []
    for key in statuses:
        dmg_range = STATUS_EFFECTS[key].get("step_damage")
        if dmg_range:
            dmg = rng.randint(dmg_range[0], dmg_range[1])
            total += dmg
            details.append((STATUS_EFFECTS[key]["label"], dmg))
    return total, details


def format_status_line(statuses):
    """บรรทัดสรุปสถานะสำหรับหน้า !play เช่น "☠️ พิษป่า (เหลือ 12 ก้าว) · ⚡ โดน EMP (เหลือ 1 ไฟต์)" """
    parts = []
    for key, turns in statuses.items():
        cfg = STATUS_EFFECTS[key]
        unit = "ไฟต์" if cfg.get("tick") == "fight" else "ก้าว"
        parts.append(f"{cfg['label']} (เหลือ {turns} {unit})")
    return " · ".join(parts)


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
        "weight": 2,  # โผล่บ่อยกว่าธีมพิเศษ (~ครึ่งหนึ่งของสัปดาห์ทั้งหมด)
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
        },
    },
]


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
        elif key == "combat_hp_drain":
            out[key] = value  # แทนที่ (ธีมทับทวีป)
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
