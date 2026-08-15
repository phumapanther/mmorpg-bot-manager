# 📦 ข้อมูลโลกของเกม (B6) — แยกจาก game_modifiers.py เพื่อให้ไฟล์ตรรกะอ่านง่ายขึ้น
# ไฟล์นี้เป็น "ข้อมูลล้วน" ไม่มีตรรกะ — game_modifiers ยัง import กลับไปใช้เหมือนเดิมทุกจุด

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
            # เขี้ยวคมปีศาจ: โดนตีมีลุ้นแผลเลือดไหล (P2 ชุด 1)
            "on_hit_status": {"key": "bleed", "chance": 10},
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
            "on_hit_status": {"key": "fumble", "chance": 12},
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
            "on_hit_status": {"key": "odd_curse", "chance": 12},
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
            # ป่ามีชีวิต: โดนตีมีลุ้นสปอร์เกาะ (สะสมครบ 3 = เห็ดบาน) (P2 ชุด 2)
            "on_hit_status": {"key": "spores", "chance": 10},
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
            "on_hit_status": {"key": "shock", "chance": 12},
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
            "special_events": [
                {
                    "key": "sunken_shrine", "chance": 12, "template": "choice",
                    "intro": (
                        "🔱 **น้ำทะเลใสจนมองทะลุถึงพื้น — เบื้องล่างคือซากวิหารจมน้ำ**\n"
                        "แสงสีฟ้าเรืองออกมาจากใจกลางวิหาร เต้นเป็นจังหวะเหมือนหัวใจ...\n"
                        "จะดำลงไปเอง หรือจ้างนักดำน้ำท้องถิ่นงมขึ้นมาให้?"
                    ),
                    "choices": [
                        {
                            "label": "🤿 กลั้นหายใจดำลงไปเอง (เสี่ยงแต่ได้เต็ม ๆ)",
                            "outcome": {
                                "text": ("คุณดำดิ่งลงไปจนหูอื้อ แรงดันน้ำบีบร่างจนแทบสำลัก "
                                         "แต่มือคว้าถึงแท่นบูชากลางวิหารได้พอดี..."),
                                "gold": [2000, 9000],
                                "damage": [10, 30],
                                # 💠 ปริซึมมานา — อาร์ติแฟกต์ประจำทวีปมหาสมุทร (แรร์: รางวัลคนกล้าดำเอง)
                                "items": [{"id": "76", "qty": 1, "chance": 8}],
                            },
                        },
                        {
                            "label": "⚓ จ้างนักดำน้ำงมให้ (ปลอดภัยแต่เสียค่าจ้าง)",
                            "outcome": {
                                "text": ("นักดำน้ำผิวสีแทนดำลงไปแล้วโผล่ขึ้นมาพร้อมของเล็ก ๆ น้อย ๆ "
                                         "'ของเรืองแสงชิ้นนั้นน่ะเหรอ? ข้าไม่กล้าแตะหรอก...'"),
                                "gold": [-4000, -1200],
                                "items": [{"id": "11", "qty": 1, "chance": 60},
                                          {"id": "29", "qty": 1, "chance": 12}],
                            },
                        },
                        {
                            "label": "🚣 ไม่เอาดีกว่า พายเรือต่อ",
                            "outcome": {"text": "คุณมองแสงสีฟ้านั้นครั้งสุดท้ายแล้วพายเรือจากไปเงียบ ๆ"},
                        },
                    ],
                },
            ],
        },
    },
}
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
    "bleed": {
        "label": "🩸 เลือดไหล", "tick": "step", "default_turns": 5,
        "step_damage": (4, 8),               # แผลเขี้ยวปีศาจ — แรงกว่าพิษแต่หายไวกว่า (P2 ชุด 1)
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
    "spores": {
        "label": "🍄 สปอร์เห็ดรา", "tick": "step", "default_turns": 1,
        "stacking": True, "no_tick": True,   # สะสมเงียบ ๆ ไม่เจ็บสักนิด... จนครบ 3 (P2 ชุด 2)
        "transform_at": 3, "transform_to": "mushroom_bloom",
    },
    "mushroom_bloom": {
        "label": "🍄 เห็ดงอกทั่วร่าง", "tick": "step", "default_turns": 6,
        "step_damage_pct": 0.05,             # รากเห็ดสูบเลือด 5% MaxHP ทุกก้าว
        "roll_bonus": -1,                    # น้ำหนักเห็ดถ่วงร่าง เต๋า -1
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
    "monster_lure": {
        "label": "🥩 กลิ่นเหยื่อล่อ", "tick": "step", "default_turns": 15,
        "event_weight_mult": {"monster": 2.0},   # กลิ่นคาวเรียกมอน ×2 (สายฟาร์ม) (P2 ชุด 4)
        "cleanse_on_apply": ["monster_ward"],    # กลิ่นเหยื่อกลบควันธูป — ใช้ทับกันไม่ได้
    },
    "monster_ward": {
        "label": "🕯️ ควันธูปไล่มอน", "tick": "step", "default_turns": 15,
        "event_weight_mult": {"monster": 0.5},   # ควันศักดิ์สิทธิ์ไล่มอน ×0.5 (สายเก็บของ/หนีตาย)
        "cleanse_on_apply": ["monster_lure"],    # ควันธูปดับกลิ่นเหยื่อ
    },
    "monster_trap": {
        "label": "🪤 กับดักมอนสเตอร์", "tick": "step", "default_turns": 1,
        "no_tick": True,              # ไม่นับถอยหลังเอง — รอจนกว่าจะเจอมอน แล้วค่อยถูกใช้ไป
        "force_event": "monster",     # ก้าวถัดไปเจอมอนแน่นอน (แรงค์/ธาตุยังสุ่มตามปกติ)
        "block_monster_flee": True,   # มอนหนีไม่ได้ — รวมมอนธาตุแสงที่ปกติเผ่น 40%
        "cleanse_on_apply": ["monster_ward"],   # วางกับดักแล้วควันธูปไล่มอนหมดความหมาย
    },
    "obsidian_edge": {
        "label": "🌋 คมอัคนีเพลิง", "tick": "fight", "default_turns": 1,
        "player_dmg_mult": 1.2,              # อาบคมอาวุธด้วยหินภูเขาไฟ
    },
    # ── บัตรประกันกันโจรปล้น (spec 2026-08-06) — คุ้มครองเมื่อเงินรวม (ติดตัว+ธนาคาร) < insurance_cap ──
    "insurance_1m": {
        "label": "🪪 ประกันหลักล้าน", "tick": "step", "default_turns": 10,
        "insurance_cap": 10_000_000,         # เงินรวมเกินเพดาน = โจรไม่สนบัตร
    },
    "insurance_10m": {
        "label": "💳 ประกันหลัก 10 ล้าน", "tick": "step", "default_turns": 50,
        "insurance_cap": 100_000_000,
    },
    "insurance_1b": {
        "label": "👑 ประกันพันล้าน", "tick": "step", "default_turns": 100,
        "insurance_cap": None,               # ไม่จำกัดความรวย
    },
    # ── อาร์ติแฟกต์ (สถานะถาวร ใส่ได้ตามจำนวนช่องที่เจาะไว้ — ถอดออกได้ด้วยชุดถอด) ──
    "art_emp_gauntlet": {
        "label": "🧤 ถุงมือกันคลื่น EMP", "tick": "step", "default_turns": 1,
        "desc": "กันคลื่น EMP ถาวร",
        "artifact": True, "no_tick": True,
        "blocks": ["emp"], "cleanse_on_apply": ["emp"],
    },
    "art_gale_boots": {
        "label": "🥾 รองเท้าขนนกวายุ", "tick": "step", "default_turns": 1,
        "desc": "แพ้เต๋ามอนลมมีลุ้นทอยใหม่ 40% + ดาเมจการร่วงลดครึ่ง",
        "artifact": True, "no_tick": True,
        "reroll_vs_element": {"element": "wind", "chance": 40},  # แพ้เต๋าให้มอนลม → ขอทอยใหม่
        "fall_damage_mult": 0.5,                                 # ดาเมจการร่วงลดครึ่ง
    },
    "art_sylvan_cloak": {
        "label": "🧥 เสื้อคลุมเปลือกไม้", "tick": "step", "default_turns": 1,
        "desc": "พิษ/เลือดไหลรายก้าวเหลือ 20% + กันรากไม้ถาวร (ทั้งล็อกเต๋าและรากพันธนาการ)",
        "artifact": True, "no_tick": True,
        "step_damage_mult": 0.2,             # เลือดไหลจากพิษ/สถานะเหลือ 20%
        "block_root": True,                  # ① กันธาตุไม้ล็อกเต๋าเหลือ 0 (ไม่สลายแบบโคลเวอร์)
        # ② กันสถานะ 🌱 รากไม้พันธนาการ ที่มอนธาตุไม้ตีติด — "ราก" ในเกมมี 2 กลไก
        # เดิมกันแค่ ① ผู้เล่นเลยเจออาการ "บางครั้งเสื้อคลุมกันรากไม่ได้"
        "blocks": ["entangled"],
        "cleanse_on_apply": ["entangled"],   # สวมตอนติดรากอยู่ = สลัดหลุดทันที
    },
    "art_fire_ring": {
        "label": "💍 แหวนหินอัคนี", "tick": "step", "default_turns": 1,
        "desc": "สะท้อนดาเมจมอนไฟ 20%",
        "artifact": True, "no_tick": True,
        "reflect_vs_element": {"element": "fire", "pct": 0.2},   # สะท้อนดาเมจมอนไฟ 20%
    },
    "art_frostward_mail": {
        "label": "🧊 เกราะเกล็ดน้ำแข็ง", "tick": "step", "default_turns": 1,
        "desc": "กันชา + เต๋าหลุดมือถาวร",
        "artifact": True, "no_tick": True,
        "blocks": ["numb", "fumble"], "cleanse_on_apply": ["numb", "fumble"],  # ภูมิคุ้มกันความหนาวครบชุด
    },
    "art_nether_amulet": {
        "label": "📿 สร้อยวิญญาณเนเธอร์", "tick": "step", "default_turns": 1,
        "desc": "อยู่ทวีปเนเธอร์: แปลงพลังดูดชีวิตเป็นฮีล 3% MaxHP/เทิร์น + กันสาปคี่ (ทุกที่)",
        "artifact": True, "no_tick": True,
        "hp_drain_heal": 0.03,                                   # แปลง Life Drain เป็นฮีล +3% MaxHP/เทิร์น (ตามสเปก)
        "blocks": ["odd_curse"], "cleanse_on_apply": ["odd_curse"],
    },
    "art_mana_prism": {
        "label": "🔮 ปริซึมมานา", "tick": "step", "default_turns": 1,
        "desc": "คืนเม็ดคริสตัล 1 เม็ดทุกก้าวที่เดิน (ไม่เกินเพดานของเลเวล)",
        "artifact": True, "no_tick": True,
        "mana_regen_per_step": 1,                                # 💎 คืนมานา 1 เม็ด/ก้าว
    },
    "art_twin_blade": {
        "label": "⚔️ ดาบคู่แฝด", "tick": "step", "default_turns": 1,
        "desc": "ดาเมจ +15% ถาวร",
        "artifact": True, "no_tick": True,
        "player_dmg_mult": 1.15,                                 # ดาเมจถาวร +15%
    },
    "art_celestial_staff": {
        "label": "🌟 คทาไม้เทวา", "tick": "step", "default_turns": 1,
        "desc": "EXP +25% ถาวร",
        "artifact": True, "no_tick": True,
        "exp_mult": 1.25,                                        # EXP ถาวร +25%
    },
    "art_masquerade_monocle": {
        "label": "🎭 แว่นเดี่ยวหน้ากาก", "tick": "step", "default_turns": 1,
        "desc": "ส่อง NPC ฟรีตลอดกาล — ใช้ได้เฉพาะสัปดาห์ธีม 🎭 เทศกาลหน้ากากสวมรอย",
        "artifact": True, "no_tick": True,
        "free_inspect": True,                                    # ตรวจสอบ NPC ฟรีตลอดกาล
    },
    "art_goddess_dicebag": {
        "label": "👝 ถุงเต๋าเทพี", "tick": "step", "default_turns": 1,
        "desc": "เต๋า +1 ทุกเทิร์นถาวร",
        "artifact": True, "no_tick": True,
        "roll_bonus": 1,                                         # เต๋าผู้เล่น +1 ทุกเทิร์นถาวร
    },
}
WEEKLY_THEMES = [
    {
        "key": "normal",
        "label": "🕊️ สัปดาห์สงบสุข",
        "description": "สัปดาห์นี้โลกดำเนินไปตามปกติ ไม่มีเหตุการณ์พิเศษใดๆ — ออกผจญภัยได้อย่างสบายใจ",
        "weight": 12,  # = ผลรวมธีมพิเศษทั้ง 12 ตัว → ครึ่งหนึ่งของสัปดาห์ทั้งหมดเป็นสัปดาห์ปกติ
        "mods": {},
    },
    {
        "key": "faction_war",
        "label": "⚔️ สงครามฝ่าย (Faction War)",
        "description": (
            "กลองศึกดังก้องทั้งแผ่นดิน! มนุษย์และปีศาจเปิดศึกชิงศักดิ์ศรี — "
            "ระหว่างผจญภัยมีลุ้นเจอ **แชมเปี้ยนฝ่ายตรงข้าม** ดักทาง "
            "โค่นได้รับทอง ×2, EXP ×1.5 และเก็บแต้มให้ฝ่ายตัวเอง (ดูสกอร์: `!war`)"
        ),
        "mods": {
            # ยามสงคราม สนามรบวุ่นวาย: เจอมอนถี่ขึ้น ×1.5 และ 40% ของมอนเป็นแชมเปี้ยนฝ่ายตรงข้าม
            # (ปรับจาก 25% หลังเทสจริง 2026-07-27 — ผู้ใช้บอกเจอน้อยไป: ของเดิม ~6%/ก้าว → ใหม่ ~13%/ก้าว)
            "event_weight_mult": {"monster": 1.5},
            "faction_war": {"chance": 40},
        },
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
            "on_hit_status": {"key": "even_curse", "chance": 12},
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
            "on_hit_status": {"key": "zombie_parasite", "chance": 25},
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
