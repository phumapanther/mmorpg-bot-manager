"""ข้อมูลคู่มือเกม (!codex) แบบ dict ล้วน — ไม่รู้จัก discord

ย้ายมาจาก bot/cogs/player_commands.py::build_codex_embed ตรง ๆ (ไม่เปลี่ยนพฤติกรรม) แล้วแยก
"ข้อมูล" ออกจาก "การแสดงผล" (MVC): ไฟล์นี้คืนแต่ dict ล้วน ๆ ไม่สร้าง discord.Embed เลย
- ฝั่งดิส (bot/cogs/player_commands.py::build_codex_embed) เอา codex_topic_full() ไปแปะเป็น
  discord.Embed จริง (คงชื่อฟังก์ชันเดิมไว้ ที่เรียกอยู่ไม่ต้องแก้)
- ฝั่งเว็บเรียก codex_topic()/codex_topics() ตรง ๆ ไม่ต้องผ่าน discord/bot.cogs เลย
"""
from bot import config_loader
from bot import game_modifiers

COLOR = 0x9b59b6

# หัวข้อคู่มือทั้งหมด (คีย์หลักที่ใช้เรียก) — ให้ /codex บนเว็บวนสร้างทีละหน้า
TOPIC_KEYS = ["วิธีเล่น", "ทวีป", "ธาตุ", "สถานะ", "ไอเทม", "คราฟ",
              "อาร์ติแฟกต์", "กิลด์", "รางวัล", "สะสม", "สังคม", "คำสั่ง"]

MEDALS = ["🥇", "🥈", "🥉"]

ELEM_RANK_ICON = [("Common", "🟢 มอนธรรมดา"), ("Mini-Boss", "🟡 มินิบอส"),
                  ("Main-Boss", "🔴 บอสใหญ่"), ("Secret", "🟣 มอนลับ"),
                  ("Unbeatable", "💀 ไร้พ่าย")]

_SET_STATE_DESC = {
    "warp_village": "วาปกลับหมู่บ้านทันที", "warp_dungeon": "วาปเข้าดันเจี้ยน",
    "mini_summon": "เรียกมินิบอสมาสู้", "main_summon": "เรียกบอสหลักมาสู้",
    "unbeatable_summon": "เรียกบอสไร้พ่าย (คิดดี ๆ)", "scan_box": "สแกนหากล่องสมบัติรอบตัว",
}


def _item_effect_desc(it):
    """สรุปผลไอเทมเป็นข้อความ — อ่านจาก effect ใน item_catalog + STATUS_EFFECTS"""
    eff, val = it.get("effect"), it.get("effect_value")
    if eff == "heal":
        return f"ฟื้น HP +{it.get('effect_amount', 0)}"
    if eff == "mana":
        return f"คืนเม็ดคริสตัล 💎 +{it.get('effect_amount', 1)} (ใช้ออกท่าได้อีกครั้ง)"
    if eff == "repair":
        return "ซ่อมความทนทานอาวุธ/เกราะ"
    if eff == "revive":
        return "ชุบชีวิตเมื่อตาย"
    if eff == "set_state":
        return _SET_STATE_DESC.get(val, str(val))
    if eff == "cure_status":
        keys = val if isinstance(val, list) else [val]
        labels = [game_modifiers.STATUS_EFFECTS[k]["label"] for k in keys if k in game_modifiers.STATUS_EFFECTS]
        return "ล้างสถานะ: " + ", ".join(labels) if labels else "ล้างสถานะ"
    if eff == "apply_status":
        cfg = game_modifiers.status_cfg(str(val))   # โชว์เทิร์นตามที่ตั้งใน Panel
        extras = []
        if cfg.get("force_event") == "monster":
            extras.append("บังคับเจอมอนก้าวถัดไป")
        if cfg.get("block_monster_flee"):
            extras.append("มอนหนีไม่ได้")
        if cfg.get("no_tick"):
            # ไม่นับถอยหลังเอง — บอก "n ก้าว" จะโกหกผู้เล่น (เช่นกับดักที่รอจนกว่าจะเจอมอน)
            note = "รอจนได้ใช้งาน" if not extras else " · ".join(extras)
            return f"ติดบัฟ {cfg.get('label', val)} ({note})"
        unit = "ก้าว" if cfg.get("tick") == "step" else "ไฟต์"
        tail = (" · " + " · ".join(extras)) if extras else ""
        return f"ติดบัฟ {cfg.get('label', val)} ({cfg.get('default_turns', 1)} {unit}){tail}"
    if eff == "gamble_status":
        chance = it.get("effect_amount", 50)
        return f"เสี่ยงดวง {chance}/{100 - chance}: สุ่มบัฟดี 1 ตัว หรือสุ่มสถานะร้าย 1 ตัว"
    if eff == "emergency_ration":
        return "ฟื้น 50% MaxHP + ล้างเชื้อซอมบี้"
    if eff == "dye_profile":
        return "ย้อมสี embed โปรไฟล์/กระเป๋า"
    if eff == "equip_artifact":
        return game_modifiers.STATUS_EFFECTS.get(str(val), {}).get("desc", "อาร์ติแฟกต์ถาวร")
    if eff == "random_continent":
        return "วาร์ปสุ่มทวีป (ไม่รู้ปลายทาง!)"
    if eff == "choose_continent":
        return "เลือกทวีปปลายทางได้เอง"
    if eff == "wedding_ring":
        return "ใช้ขอแต่งงาน (`!marry @คน`) — ถูกสวมให้อีกฝ่ายตอนตกลง"
    if eff == "artifact_slot_up":
        cap = int(config_loader.get_balance("artifact.max_slots", 5) or 5)
        return f"เจาะช่องอาร์ติแฟกต์เพิ่ม 1 ช่อง (สูงสุด {cap})"
    if eff == "artifact_remove":
        return "ถอดอาร์ติแฟกต์ที่สวมอยู่ — ของกลับเข้ากระเป๋า"
    return None


def _monster_element_desc(data):
    """สรุปความสามารถธาตุฝั่งมอนเป็นข้อความ — อ่านจาก ELEMENTS ตรง ๆ เพิ่มธาตุใหม่แล้วขึ้นเอง"""
    parts = []
    if data.get("dmg_mult", 1.0) > 1.0:
        parts.append(f"ตีแรง ×{data['dmg_mult']:g}")
    if data.get("lifesteal"):
        parts.append(f"ดูดเลือด {int(data['lifesteal'] * 100)}%")
    if data.get("hp_mult", 1.0) > 1.0:
        parts.append(f"เลือดหนา ×{data['hp_mult']:g}")
    if data.get("dice_bonus"):
        parts.append(f"เต๋ามอน +{data['dice_bonus'][0]}-{data['dice_bonus'][1]}")
    if data.get("root_chance"):
        parts.append(f"{data['root_chance']}% รากล็อกเต๋าคุณ = 0")
    on_hit = data.get("on_hit_status")
    if on_hit:
        parts.append(f"{on_hit['chance']}% ตีติด {game_modifiers.STATUS_EFFECTS[on_hit['key']]['label']}")
    if data.get("pre_enraged"):
        parts.append("คลั่งตั้งแต่เทิร์นแรก")
    if data.get("monster_flee_chance"):
        parts.append(f"หนีเก่ง {data['monster_flee_chance']}% *(🪤 กับดักล็อกไว้ได้)*")
    if data.get("gold_mult", 1.0) > 1.0:
        parts.append(f"ล้มได้ทอง ×{data['gold_mult']:g}")
    return ", ".join(parts) or "-"


class _Doc:
    """ตัวช่วยสร้างข้อมูลคู่มือ — หน้าตา/อินเตอร์เฟซคล้าย discord.Embed แต่เป็น dict ล้วน
    (เขียนแยกจาก discord.Embed จริงเพื่อไม่ให้ core/services/ ต้อง import discord)"""

    def __init__(self, title, description="", color=COLOR):
        self.title = title
        self.description = description
        self.color = color
        self.footer = None
        self.fields = []  # [{"name","value","inline"}]

    def add_field(self, name, value, inline=False):
        self.fields.append({"name": name, "value": value, "inline": inline})

    def set_footer(self, text):
        self.footer = text


def _build_doc(topic=""):
    """ย้ายมาจาก build_codex_embed ตรง ๆ — เปลี่ยนแค่ discord.Embed( → _Doc( เท่านั้น"""
    topic = (topic or "").strip().lower()

    if topic in ("ธาตุ", "element", "elements"):
        embed = _Doc(
            title="📖 Codex — ธาตุทั้ง 7", color=0x9b59b6,
            description="ธาตุประจำตัวมาจาก **ยศเผ่า** — ถือหลายเผ่าได้หลายธาตุ, สองธาตุข่มเป้าเดียวกัน = ดาเมจ ×2.0")
        # ใช้ค่าที่ "มีผลจริง" (ทับด้วย Panel แล้ว) — คู่มือจะได้ไม่บอกเรทหนีคนละเลขกับในเกม
        for key, data in ((k, game_modifiers.get_element_data({}, k)) for k in game_modifiers.ELEMENTS):
            prey = [game_modifiers.ELEMENTS[t]["label"] for t in game_modifiers.ELEMENT_ADVANTAGE.get(key, [])]
            resist = [game_modifiers.ELEMENTS[t]["label"] for t in game_modifiers.ELEMENT_RESIST.get(key, [])]
            lines = [f"👤 ติดตัวผู้เล่น: {data['player']['desc']}",
                     f"👹 ฝั่งมอนสเตอร์: {_monster_element_desc(data)}"]
            if prey:
                lines.append(f"⚔️ ข่ม (×1.5): {', '.join(prey)}")
            if resist:
                lines.append(f"🛡️ รับเบา (×0.75): {', '.join(resist)}")
            embed.add_field(name=data["label"], value="\n".join(lines), inline=False)
        return embed

    if topic in ("วิธีเล่น", "เริ่มเล่น", "howto", "guide"):
        embed = _Doc(
            title="📖 Codex — วิธีเล่นฉบับเริ่มต้น", color=0x9b59b6,
            description="โลกนี้เดินด้วย **ลูกเต๋า** — ทุกการผจญภัยคือการทอยวัดดวงกับโชคชะตา")
        embed.add_field(name="1️⃣ เกิดใหม่ในโลกนี้", inline=False, value=(
            "รับ **ยศเผ่า** และ **ยศคลาสอาชีพ** จากเซิร์ฟก่อน (เผ่ากำหนดธาตุประจำตัว ดู `!codex ธาตุ`)\n"
            "พิมพ์ `!adv` สร้างห้องผจญภัยส่วนตัว แล้ว `!play` เพื่อออกเดินทาง"))
        embed.add_field(name="2️⃣ ออกเดินทาง", inline=False, value=(
            "กดปุ่ม **🧭 เริ่มออกเดินทาง** เดินทีละก้าว หรือ **⏩ เดินต่อ ×5** เดินรวด "
            "(หยุดเองเมื่อเจอมอน/หีบ/กับดัก หรือเลือดต่ำกว่า 30%)\n"
            "สุ่มเจอมอนสเตอร์ กับดัก สมบัติ หมู่บ้าน NPC หรือพาหนะข้ามทวีป (ทางเดียวที่จะไปทวีปอื่น!)\n"
            "เจอมอน = ทอยเต๋าสู้กันเป็นเทิร์น ชนะได้ทอง+EXP แพ้เต๋า = โดนสวน · "
            "กลางไฟต์กดปุ่ม 🧪 ใช้ไอเทมได้ทันที"))
        embed.add_field(name="3️⃣ ของติดตัวคือชีวิต", inline=False, value=(
            "`!bag` ดูกระเป๋า *(มีปุ่ม 🔨 คราฟ · 🗑️ ทิ้ง · 🧱 ขายวัสดุ ในตัว)* / `!use <เลขไอเทม>`\n"
            "พกยาแก้สถานะให้ตรงทวีป (`!codex สถานะ`) · คราฟของเองได้ (`!codex คราฟ`)\n"
            "🏺 **อาร์ติแฟกต์** = ของถาวร เริ่มมี 1 ช่อง เจาะเพิ่มได้ถึง 5 ช่อง — `!codex อาร์ติแฟกต์`"))
        embed.add_field(name="4️⃣ เงินและเมือง", inline=False, value=(
            "ทองที่ถือตายแล้วหาย — ฝากธนาคารด้วย `!deposit` ไว้ก่อน\n"
            "`!shop` ซื้อของ · `!market` **ตลาดผู้เล่น** ซื้อ-ขายกับเพื่อนร่วมเซิร์ฟ\n"
            "คาสิโนมี `!bj` `!hilo` `!slots` เสี่ยงดวงเพิ่ม (หรือหมดตัว)"))
        embed.add_field(name="5️⃣ เข้ามาทุกวันคุ้มกว่า", inline=False, value=(
            "📅 `!daily` ภารกิจรายวัน + ล็อกอินต่อเนื่อง — นับให้เองจากการเล่นปกติ\n"
            "🎟️ `!season` ซีซั่นพาสรายเดือน (สายฟรีทุกคนได้) · 🗓️ `!top` อันดับรายสัปดาห์ ท็อป 3 รับทอง\n"
            "🏅 `!ach` ความสำเร็จ + ตำแหน่งอวด · 💍 `!marry @คน` คู่หู (คู่เล่นวันเดียวกัน = โบนัสเพิ่ม)"))
        embed.add_field(name="6️⃣ โลกที่หมุนเอง", inline=False, value=(
            "ทุกสัปดาห์มี **ธีมโลก** สุ่มใหม่ (ประกาศวันจันทร์) เปลี่ยนมอน/เรท/อีเวนต์ทั้งเซิร์ฟ\n"
            "แต่ละทวีปมีธาตุ สถานะ และบอสประจำถิ่น — `!codex ทวีป` ก่อนออกเดิน"))
        embed.add_field(name="7️⃣ เส้นทางสายเทพ (ระบบปลายเกม)", inline=False, value=(
            "📕 `!bestiary` สมุดล่ามอน + 🧬 **สมุดธาตุ** (315 ช่อง) — ครบทวีปได้อาร์ติแฟกต์ ครบหมดได้ 🐉 ลูกมังกร\n"
            "🐾 `!pet` สัตว์เลี้ยง — ล้มมอนแล้วลุ้นจับ ยิ่งมอนโหดตัวยิ่งแรง\n"
            "🎯 `!bounty` ล่าหัวคนสติติดลบ รับทองไม่บาป • ⚔️ `!war` สงครามฝ่ายมนุษย์↔ปีศาจ (ธีมพิเศษ)\n"
            "🏰 `!guild` ก่อตั้งกิลด์ + ประกาศศึก `!warguild` ชิงเดิมพันคลัง — `!codex กิลด์`"))
        embed.set_footer(text="อ่านต่อ: !codex คราฟ · !codex อาร์ติแฟกต์ · !codex รางวัล · !codex สะสม · !codex สังคม")
        return embed

    if topic in ("กิลด์", "guild", "กิลด์วอร์"):
        embed = _Doc(
            title="📖 Codex — กิลด์ & กิลด์วอร์", color=0x9b59b6,
            description="รวมตัวตั้งแก๊ง สร้างบ้าน สะสมคลัง แล้วเปิดศึกชิงเงินกิลด์อื่น")
        embed.add_field(name="🏰 ก่อตั้งกิลด์", inline=False, value=(
            "`!guild create <ชื่อ>` — ค่าก่อตั้ง `3,000,000,000` ทอง**สด**\n"
            "ได้ทันที: ยศกิลด์ (สีสุ่ม) + ห้องเสียงส่วนตัวเฉพาะสมาชิก\n"
            "`!guild rename <ชื่อใหม่>` เปลี่ยนชื่อ (ค่าธรรมเนียม `100,000,000`)"))
        embed.add_field(name="👥 สมาชิก", inline=False, value=(
            "หัวหน้า: `!guild invite @คน` (มีปุ่มยืนยัน) / `!guild kick @คน`\n"
            "สมาชิก: `!guild leave` ออกเอง • ทุกคนอยู่ได้ **1 กิลด์เท่านั้น**\n"
            "`!guild info` หน้ากิลด์ • `!guild disband` ยุบ (หัวหน้า — คลังคืนธนาคารหัวหน้า)"))
        embed.add_field(name="💰 คลังกิลด์", inline=False, value=(
            "`!guild deposit <จำนวน>` ทุกคนฝากได้ (หักธนาคารตัวเอง) — **ฝากแล้วถอนเองไม่ได้**\n"
            "หัวหน้าเท่านั้น: `!guild withdraw <จำนวน>` / `!guild pay @สมาชิก <จำนวน>`"))
        embed.add_field(name="⚔️ กิลด์วอร์", inline=False, value=(
            "`!warguild @หัวหน้ากิลด์อื่น [เดิมพัน]` — หัวหน้าท้าหัวหน้า วางเดิมพันคลังเท่ากัน\n"
            "รับคำท้า → เปิด**ห้องรบ 30 นาที** (เงียบเกิน 1 นาที = จบศึกทันที)\n"
            "`!fight` ในห้องรบ: ⚔️ ทหารศัตรู `+1` • 👑 หัวหน้า `+10` • 🛡️ ป้อม = ศัตรู `-10` • 🏰 ปราสาท = ศัตรู `-100`\n"
            "จบศึก: แต้มมากกว่าชนะ **รับกองกลาง 2×เดิมพัน** เข้าคลังกิลด์ (เสมอ = คืนเดิมพัน)"))
        return embed

    if topic in ("คำสั่ง", "commands", "cmd"):
        embed = _Doc(
            title="📖 Codex — คำสั่งผู้เล่นทั้งหมด", color=0x9b59b6,
            description="พิมพ์ในห้องที่เซิร์ฟกำหนดไว้ (บางคำสั่งจำกัดห้อง) — `!menu` มีปุ่มลัดของที่ใช้บ่อย")
        embed.add_field(name="🗺️ ผจญภัย", inline=False, value=(
            "`!adv` สร้างห้องผจญภัยส่วนตัว • `!play` เริ่มออกเดินทาง\n"
            "`!profile` (`!info`) โปรไฟล์+ธาตุ+อาร์ติแฟกต์ • `!scan @คน` ส่องข้อมูลคนอื่น\n"
            "`!codex <หมวด>` สารานุกรมกติกา • `!reward` รับรางวัลประจำยศ\n"
            "`!bestiary` สมุดสะสมมอนสเตอร์ (ล่าครบมีโบนัสทอง)\n"
            "`!daily` **ภารกิจรายวัน + เช็คอินต่อเนื่อง** — ทำครบรับทองก้อนโต!\n"
            "`!season` **ซีซั่นพาสรายเดือน** • `!ach` **ความสำเร็จ + ตำแหน่งอวด**\n"
            "`!pet` **สัตว์เลี้ยง** ที่จับมาได้ — ติดตัวช่วยหนุนเต๋าตอนสู้"))
        embed.add_field(name="🎒 กระเป๋า & ไอเทม", inline=False, value=(
            "`!bag` ดูกระเป๋า *(มีปุ่ม 🔨 คราฟ · 🗑️ ทิ้ง · 🧱 ขายวัสดุ ในตัว)* • `!use <เลข>` • `!drop <เลข>`\n"
            "`!give @คน <เลข>` ส่งของให้เพื่อน • `!recipes` สูตรคราฟ • `!craft <เลข>` คราฟของ"))
        embed.add_field(name="💰 เงิน & ธนาคาร", inline=False, value=(
            "`!bank` ยอดธนาคาร *(มีปุ่ม 💰 ฝาก · 💸 ถอน · 🤝 โอน ในตัว)* • `!deposit` • `!withdraw`\n"
            "`!transfer @คน <จำนวน>` โอน • `!beg` ขอทาน • `!rob @คน` ปล้น (เสี่ยงติดคุก!)\n"
            "`!top` **อันดับรวมทุกหมวด** (🗓️ สัปดาห์นี้/เศรษฐี/เลเวล/แชท/ออนไลน์ — กดปุ่มสลับได้)\n"
            "`!market` **ตลาดผู้เล่น** — `sell` ลงขาย · `buy` ซื้อ · `cancel` เอาคืน · `mine` ของฉัน\n"
            "`!mytext` `!mytime` สถิติตัวเอง"))
        embed.add_field(name="🎰 คาสิโน & PvP", inline=False, value=(
            "`!bj <เงินเดิมพัน>` แบล็กแจ็ก • `!hilo` ไฮโล • `!slots` สล็อต\n"
            "`!att @คน` เปิดฉากปล้นกลางเมือง (ต้องอยู่ห้องเสียง) • `!challenge @คน` ท้าดวล PvP\n"
            "`!bounty` กระดานล่าค่าหัว — ฆ่าคนสติติดลบรับทอง ไม่เสียสติ\n"
            "`!war` สกอร์สงครามฝ่าย มนุษย์↔ปีศาจ (ธีมสงคราม)\n"
            "`!warguild @หัวหน้า [เดิมพัน]` ประกาศกิลด์วอร์ 30 นาที • `!fight` สู้ในห้องรบ"))
        embed.add_field(name="🏪 ร้านค้า & อื่น ๆ", inline=False, value=(
            "`!shop` ร้านไอเทม • `!darkshop` / `!lightshop` ร้านยศสองฝ่าย\n"
            "`!rent` เช่าห้องส่วนตัว (`!extend` ต่ออายุ, `!set_room` ตั้งค่า)\n"
            "`!guild` ระบบกิลด์: create/invite/deposit/pay (ก่อตั้ง 3,000,000,000 ทองสด)\n"
            "`!marry @คน` **ชวนเป็นคู่หู** (ต้องมี 💍 แหวนแต่งงานจาก `!shop`) • `!partner` • `!divorce`\n"
            "`!payment` เติมเงิน • `!my_orders` เช็คคำสั่งซื้อ • `!menu` เมนูปุ่มลัด"))
        return embed

    if topic in ("สถานะ", "status"):
        cures, guards, cure_all = {}, {}, []
        for iid, it in config_loader.get_all_items().items():
            name, eff, val = it.get("name", f"#{iid}"), it.get("effect"), it.get("effect_value")
            if eff == "cure_status":
                if val == "all":
                    cure_all.append(name)
                else:
                    for k in (val if isinstance(val, list) else [val]):
                        cures.setdefault(k, []).append(name)
            elif eff in ("apply_status", "equip_artifact"):
                for k in game_modifiers.STATUS_EFFECTS.get(str(val), {}).get("blocks", []):
                    guards.setdefault(k, []).append(name)
        lines = []
        for key in game_modifiers.STATUS_EFFECTS:
            cfg = game_modifiers.status_cfg(key)    # คู่มือต้องบอกเทิร์นตามที่ตั้งใน Panel
            if cfg.get("artifact"):
                continue
            extra = []
            if key in cures:
                extra.append("แก้: " + ", ".join(cures[key]))
            if key in guards:
                extra.append("กัน: " + ", ".join(guards[key]))
            unit = "ก้าว" if cfg.get("tick") == "step" else "ไฟต์"
            lines.append(f"{cfg['label']} `{cfg.get('default_turns', 1)} {unit}`"
                         + (" — " + " / ".join(extra) if extra else ""))
        desc = "สถานะหมดเองเมื่อครบเวลา (นับเป็นก้าวเดิน/ไฟต์)"
        if cure_all:
            desc += f"\n💊 ล้างได้ทุกสถานะ: {', '.join(cure_all)}"
        embed = _Doc(title="📖 Codex — สถานะติดตัว", color=0x9b59b6, description=desc)
        chunk = ""
        for line in lines:  # ตัดลง field ละ ≤1024 ตัวอักษร (ลิมิต Discord — บทเรียนจาก !bag)
            if len(chunk) + len(line) + 1 > 1024:
                embed.add_field(name="​", value=chunk, inline=False)
                chunk = ""
            chunk += line + "\n"
        if chunk:
            embed.add_field(name="​", value=chunk, inline=False)
        return embed

    if topic in ("ไอเทม", "ของ", "item", "items"):
        groups = {"use": [], "artifact": [], "equip": [], "material": []}
        for iid, it in sorted(config_loader.get_all_items().items(), key=lambda kv: int(kv[0])):
            name, eff = it.get("name", f"#{iid}"), it.get("effect")
            desc = _item_effect_desc(it)
            if str(iid) == "38":  # แว่นส่องสัจจะ: ไม่มี effect ใน config — ถูกหักอัตโนมัติตอนกดปุ่มตรวจ NPC (game_views อ้าง id 38 ตรง ๆ)
                desc = "พกไว้เฉย ๆ — ใช้เองอัตโนมัติตอนตรวจตัวตน NPC งานหน้ากาก (ฟรี, เลนส์แตกหลังใช้)"
            price = f"💰{it['buy']:,}" if it.get("purchasable", True) and it.get("buy") else "ดรอป/คราฟเท่านั้น"
            if eff == "equip_artifact":
                groups["artifact"].append(f"`{iid}` {name} — {desc}")
            elif desc:
                groups["use"].append(f"`{iid}` {name} — {desc} ({price})")
            elif it.get("equip_key"):
                groups["equip"].append(f"`{iid}` {name} ({price})")
            else:
                groups["material"].append(f"`{iid}` {name} (ขายร้าน 💰{it.get('sell', 0):,})")
        embed = _Doc(
            title="📖 Codex — ไอเทมทั้งหมด", color=0x9b59b6,
            description="ใช้ของด้วย `!use <เลข>` — เลขไอเทมคือตัวหน้าแต่ละบรรทัด\n"
                        "รายละเอียดว่าบัฟแต่ละตัวกัน/ทำอะไร → `!codex สถานะ`")
        sections = [("💊 ของใช้", groups["use"]), ("🏺 อาร์ติแฟกต์ (ใส่ได้ตามจำนวนช่อง — `!codex อาร์ติแฟกต์`)", groups["artifact"]),
                    ("⚔️ อุปกรณ์สวมใส่", groups["equip"]), ("🧱 วัสดุคราฟ/ของขายร้าน", groups["material"])]
        for title, lines in sections:
            chunk, first = "", True
            for line in lines:  # ตัดท่อนละ ≤1024 (ลิมิต Discord)
                if len(chunk) + len(line) + 1 > 1024:
                    embed.add_field(name=title if first else "​", value=chunk, inline=False)
                    chunk, first = "", False
                chunk += line + "\n"
            if chunk:
                embed.add_field(name=title if first else "​", value=chunk, inline=False)
        return embed

    if topic in ("ทวีป", "continent", "continents"):
        embed = _Doc(
            title="📖 Codex — ทวีปทั้ง 9", color=0x9b59b6,
            description="การข้ามทวีปมีทางเดียว: **สุ่มเจอพาหนะ** ระหว่างผจญภัย (รู้ปลายทางเมื่อไปถึง)")
        for key, c in game_modifiers.CONTINENTS.items():
            weights = (c.get("mods") or {}).get("element_weights") or {}
            top = sorted(weights, key=weights.get, reverse=True)[:2]
            elem_txt = " ".join(game_modifiers.ELEMENTS[t]["label"] for t in top if t in game_modifiers.ELEMENTS) or "สมดุลทุกธาตุ"
            embed.add_field(name=c["label"], value=f"ธาตุชุกชุม: {elem_txt}", inline=True)
        return embed

    if topic in ("อาร์ติแฟกต์", "อาติแฟก", "artifact", "artifacts"):
        cap = int(config_loader.get_balance("artifact.max_slots", 5) or 5)
        chance = int(config_loader.get_balance("artifact.punch_drop_chance", 0) or 0)
        punch = config_loader.get_item_config(str(config_loader.get_balance("artifact.punch_item", "") or ""))
        remover = next((i for i in config_loader.get_all_items().values()
                        if i.get("effect") == "artifact_remove"), {})
        embed = _Doc(
            title="📖 Codex — อาร์ติแฟกต์ & ช่องสวมใส่", color=0x9b59b6,
            description=(f"อาร์ติแฟกต์คือของถาวร ใส่แล้วมีผลตลอด ไม่หมดอายุ\n"
                         f"เริ่มต้นมี **1 ช่อง** เจาะเพิ่มได้สูงสุด **{cap} ช่อง**"))
        embed.add_field(name=f"{punch.get('name', '💠 สว่านเจาะรู')} — เพิ่มช่อง", inline=False, value=(
            f"**ดรอปจากบอสไร้พ่ายเท่านั้น** โอกาส `{chance}%` ต่อการล้ม 1 ตัว (แทบได้ทุกครั้ง)\n"
            "ซื้อไม่ได้ · คราฟไม่ได้ · ใช้แล้วช่องเพิ่มถาวร 1 ช่อง"))
        embed.add_field(name=f"{remover.get('name', '🔧 ชุดถอด')} — ถอดออก", inline=False, value=(
            f"ซื้อที่ `!shop` ราคา 🪙 {int(remover.get('buy', 0)):,} ทอง (ไม่มีดรอป)\n"
            "พิมพ์ `!use` แล้วเลือกชิ้นที่จะถอด — **ของกลับเข้ากระเป๋า** เอาไปใส่ใหม่/ขาย/ส่งต่อได้"))
        embed.add_field(name="ℹ️ กติกา", inline=False, value=(
            "• ช่องเต็มแล้วสวมชิ้นใหม่ไม่ได้ (ของเก่าไม่แตกแล้ว — ต้องถอดเองก่อน)\n"
            "• อาร์ติแฟกต์ไม่โดนล้างด้วยยาถอนพิษ/หมู่บ้าน · ไม่หายตอนตาย\n"
            "• ดูช่องที่ใช้อยู่ได้ที่ `!profile`"))
        return embed

    if topic in ("คราฟ", "craft", "สูตร", "recipes"):
        all_items = config_loader.get_all_items()
        recipes = config_loader.get_config().get("item_catalog", {}).get("crafting_recipes", {}) or {}
        embed = _Doc(
            title="📖 Codex — ตารางคราฟของ", color=0x9b59b6,
            description=("เก็บวัสดุจากการล่ามอนแล้วเอามาคราฟ — พิมพ์ `!craft <เลขไอเทม>` "
                         "หรือกดปุ่ม 🔨 ในหน้า `!bag` (ปุ่มจะโชว์เฉพาะสูตรที่วัตถุดิบครบแล้ว)\n"
                         "⚠️ คราฟพลาด = **เสียวัสดุฟรี** ยิ่งของแรงยิ่งพลาดง่าย"))

        def _line(out_id, r):
            mats = " + ".join(f"{all_items.get(m, {}).get('name', m)}×**{n}**"
                              for m, n in (r.get("recipe") or {}).items())
            fail = int(float(r.get("fail_rate", 0)) * 100)
            return f"`{out_id}` {all_items.get(out_id, {}).get('name', out_id)}\n　└ {mats} · พลาด {fail}%"

        # แยกของที่ใช้ปั๊มสมุด/ล่ามอนออกมาเด่น ๆ เพราะเป็นตัวที่คนมองข้ามบ่อยสุด
        hunt_keys = [k for k in ("24", "25", "26", "66", "27") if k in recipes]
        if hunt_keys:
            embed.add_field(name="🎯 ของสายล่ามอน (คราฟเองได้ ไม่ต้องรอดรอป!)", inline=False,
                            value="\n".join(_line(k, recipes[k]) for k in hunt_keys))
        rest = [k for k in recipes if k not in hunt_keys]
        for i in range(0, len(rest), 5):
            chunk = rest[i:i + 5]
            embed.add_field(name="🔨 สูตรอื่น ๆ" if i == 0 else "​", inline=False,
                            value="\n".join(_line(k, recipes[k]) for k in chunk))
        embed.set_footer(text="วัสดุหาได้จากการล้มมอน/เปิดหีบ — ดูของในกระเป๋าด้วย !bag")
        return embed

    if topic in ("รางวัล", "กิจกรรม", "daily", "season"):
        cfg = config_loader.get_config()
        embed = _Doc(
            title="📖 Codex — รางวัลรายวัน · ซีซั่นพาส · อันดับสัปดาห์", color=0x9b59b6,
            description="สามระบบนี้ให้รางวัลจาก **การเล่นปกติ** ไม่ต้องทำอะไรพิเศษ — แค่เข้ามาเล่นทุกวัน")

        quests = config_loader.get_daily_quests()
        bonus = config_loader.get_daily_cfg("all_clear_bonus", {}) or {}
        embed.add_field(name="📅 ภารกิจรายวัน (`!daily`)", inline=False, value=(
            "\n".join(f"• {q['label']} {int(q.get('target', 1)):,} ครั้ง → 🪙 {int(q.get('gold', 0)):,}"
                      for q in quests)
            + (f"\n🏆 เคลียร์ครบทุกข้อ → 🪙 **{int(bonus.get('gold', 0)):,}**" if bonus else "")
            + "\n*ความคืบหน้านับเองจากการเล่นปกติ · รีเซ็ตเที่ยงคืน*"))

        streak = sorted(config_loader.get_daily_cfg("streak_rewards", []) or [], key=lambda r: r["day"])
        if streak:
            embed.add_field(name="🔥 ล็อกอินต่อเนื่อง", inline=False, value=(
                " · ".join(f"**{int(r['day'])} วัน** 🪙 {int(r.get('gold', 0)):,}" for r in streak)
                + "\n*ขาดวันเดียวนับใหม่หมด แต่สถิติสูงสุดยังอยู่*"))

        season = cfg.get("season_pass", {}) or {}
        if season.get("enabled", True):
            tiers = season.get("tiers", []) or []
            embed.add_field(name="🎟️ ซีซั่นพาส (`!season`)", inline=False, value=(
                f"แต้ม = **EXP ที่หาได้ในเดือนนี้** · มี {len(tiers)} ขั้น\n"
                f"🆓 สายฟรีทุกคนได้ · ⭐ สายพรีเมียม {int(season.get('price_gold', 0)):,} ทอง "
                "(ซื้อแล้วย้อนเก็บขั้นที่ปลดไปแล้วได้ทันที)\n"
                "*ขึ้นเดือนใหม่ = ซีซั่นใหม่ แต้มเริ่มศูนย์ พรีเมียมต้องซื้อใหม่*"))

        weekly = cfg.get("weekly_ranking", {}) or {}
        if weekly.get("enabled", True):
            rw = weekly.get("rewards", []) or []
            embed.add_field(name="🗓️ อันดับรายสัปดาห์ (`!top` → 🗓️)", inline=False, value=(
                "แต้ม = **EXP ที่หาได้ในสัปดาห์นี้** · ปิดอันดับเช้าวันจันทร์\n"
                + " · ".join(f"{m} 🪙 {int(r.get('gold', 0)):,}" for m, r in zip(MEDALS, rw))
                + "\n*รางวัลโอนเข้าธนาคารอัตโนมัติ ตายแล้วไม่หาย*"))
        return embed

    if topic in ("สะสม", "ความสำเร็จ", "สัตว์เลี้ยง", "pet", "achievement"):
        cfg = config_loader.get_config()
        embed = _Doc(
            title="📖 Codex — ความสำเร็จ & สัตว์เลี้ยง", color=0x9b59b6,
            description="ของสะสมระยะยาว — เก็บไปเรื่อย ๆ ระหว่างเล่นปกติ ไม่ต้องไล่เก็บเป็นพิเศษ")

        achs = cfg.get("achievements", []) or []
        if achs:
            embed.add_field(name=f"🏅 ความสำเร็จ {len(achs)} รายการ (`!ach`)", inline=False, value=(
                "นับย้อนหลังให้อัตโนมัติ — เล่นมานานแล้วเปิดครั้งแรกได้เลยหลายอัน\n"
                + "\n".join(f"• {a['label']} — {a.get('desc', '')}" for a in achs[:6])
                + (f"\n*...และอีก {len(achs) - 6} รายการ ดูครบที่ `!ach`*" if len(achs) > 6 else "")
                + "\n🎖️ ปลดแล้วได้ **ตำแหน่ง** เลือกติดโชว์ใต้ชื่อในโปรไฟล์"))

        rank_rw = config_loader.get_balance("bestiary.element_rank_rewards", {}) or {}
        embed.add_field(name="🧬 สมุดธาตุ (`!bestiary` → ปุ่ม 🧬)", inline=False, value=(
            "มอนทุกตัวมีธาตุ — **เก็บแยกทีละธาตุ** ในทุกแรงค์ ทุกทวีป (5 แรงค์ × 7 ธาตุ × 9 ทวีป)\n"
            + " · ".join(f"{lbl.split()[1]} 🪙 {int(rank_rw.get(r, 0)):,}" for r, lbl in ELEM_RANK_ICON)
            + "\n🏺 ครบทุกแรงค์ทุกธาตุใน 1 ทวีป → **อาร์ติแฟกต์ประจำทวีปนั้น**\n"
              "🐉 ครบทั้ง 9 ทวีป → **สัตว์เลี้ยงขั้นสูงสุด**\n"
              "*ปั๊มเร็วขึ้น: 📃 ใบเชิญบอส เรียกแรงค์ที่ต้องการ · "
              "🪤 กับดักมอนสเตอร์ บังคับเจอมอนก้าวถัดไปและมอนหนีไม่ได้ (ล่ามอนแสงได้จริง)*"))

        pets = (cfg.get("pets", {}) or {}).get("list", []) or []
        chances = (cfg.get("pets", {}) or {}).get("tame_chance", {}) or {}
        if pets:
            rank_th = {"Common": "มอนธรรมดา", "Mini-Boss": "มินิบอส", "Main-Boss": "บอสใหญ่",
                       "Secret": "มอนลับ", "Unbeatable": "ไร้พ่าย"}
            embed.add_field(name=f"🐾 สัตว์เลี้ยง {len(pets)} ตัว (`!pet`)", inline=False, value=(
                "**ล้มมอนแล้วลุ้นจับมาเลี้ยง** — ยิ่งมอนโหด ตัวที่ได้ยิ่งแรง ติดตัวได้ทีละตัว\n"
                + "\n".join(f"• {p['name']} — 🎲 เต๋า +{int(p.get('dice', 0))} "
                            f"(ล้ม{rank_th.get(p.get('from_rank'), '?')} โอกาส {int(chances.get(p.get('from_rank'), 0))}%)"
                            for p in pets)
                + "\n*ตัวที่มีแล้วจะไม่ออกซ้ำ · ตัวแรกติดให้อัตโนมัติ*"))
        return embed

    if topic in ("สังคม", "ตลาด", "คู่หู", "market", "partner"):
        cfg = config_loader.get_config()
        market = cfg.get("market", {}) or {}
        partner = cfg.get("partner", {}) or {}
        embed = _Doc(
            title="📖 Codex — ตลาดผู้เล่น & คู่หู", color=0x9b59b6,
            description="สองระบบที่ต้องมีคนอื่นถึงจะได้ประโยชน์เต็ม")
        if market.get("enabled", True):
            embed.add_field(name="🏪 ตลาดผู้เล่น (`!market`)", inline=False, value=(
                "ฝากขายไอเทมให้ผู้เล่นคนอื่นซื้อด้วยทองในเกม\n"
                "`!market sell <เลขไอเทม> <ราคา>` ลงขาย *(ของออกจากกระเป๋าทันที)*\n"
                "`!market buy <เลขรายการ>` ซื้อ • `!market cancel <เลขรายการ>` เอาของคืน\n"
                "`!market mine` ดูของที่ตัวเองลงขายอยู่\n"
                f"💸 ค่าธรรมเนียม **{int(market.get('tax_percent', 0))}%** หักจากคนขาย · "
                f"ราคา {int(market.get('min_price', 0)):,}–{int(market.get('max_price', 0)):,} ทอง · "
                f"ลงขายพร้อมกันได้ {int(market.get('max_listings_per_player', 0))} รายการ\n"
                "*เงินคนขายเข้าธนาคาร · ขายไปแล้วยกเลิกไม่ได้*"))
        ring_key = str(partner.get("ring_item", "") or "")
        ring = config_loader.get_item_config(ring_key) if ring_key else {}
        embed.add_field(name="💍 คู่หู (`!marry` / `!partner` / `!divorce`)", inline=False, value=(
            (f"**ต้องซื้อ {ring.get('name', 'แหวน')} ที่ `!shop` ก่อน** ราคา 🪙 {int(ring.get('buy', 0)):,} ทอง\n"
             "แหวนถูกสวมให้อีกฝ่ายตอนกดตกลง (ใช้แล้วหมดไป) — หย่าแล้วไม่ได้คืน\n" if ring else "")
            + f"ชวนใครสักคนเป็นคู่ (อีกฝ่ายต้องกดยืนยัน) ค่าจัดงานคนละ 🪙 {int(partner.get('wedding_cost', 0)):,}\n"
            f"💍 มีคู่: รางวัลจากการล่า **+{int(partner.get('solo_bonus_percent', 0))}%**\n"
            f"💞 **คู่เข้ามาเล่นวันเดียวกัน: +{int(partner.get('together_bonus_percent', 0))}%** ทั้งสองฝ่าย\n"
            f"*เลิกได้ด้วย `!divorce` (ค่าดำเนินการ {int(partner.get('divorce_cost', 0)):,} ทอง หักจากคนขอ)*"))
        return embed

    embed = _Doc(
        title="📖 Codex — สารานุกรมนักผจญภัย", color=0x9b59b6,
        description=("เลือกหมวดที่อยากอ่าน:\n"
                     "`!codex วิธีเล่น` — ไกด์เริ่มต้นตั้งแต่เกิดจนออกผจญภัย\n"
                     "`!codex คำสั่ง` — คำสั่งผู้เล่นทั้งหมดแยกหมวด\n"
                     "`!codex ธาตุ` — ธาตุทั้ง 7, ตารางข่ม, passive ประจำเผ่า\n"
                     "`!codex สถานะ` — สถานะทั้งหมด + ไอเทมที่ใช้แก้/กัน\n"
                     "`!codex ไอเทม` — ไอเทมทุกชิ้น ใช้ทำอะไร ราคาเท่าไหร่\n"
                     "`!codex ทวีป` — ทวีปทั้ง 9 และธาตุประจำถิ่น\n"
                     "`!codex กิลด์` — ก่อตั้งกิลด์ คลังกิลด์ และกิลด์วอร์\n"
                     "`!codex รางวัล` — ภารกิจรายวัน ซีซั่นพาส อันดับสัปดาห์\n"
                     "`!codex สะสม` — ความสำเร็จ + สัตว์เลี้ยง\n"
                     "`!codex สังคม` — ตลาดผู้เล่น + ระบบคู่หู\n"
                     "`!codex คราฟ` — ตารางคราฟของทั้งหมด (ใบเชิญบอส/กับดัก คราฟเองได้!)\n"
                     "`!codex อาร์ติแฟกต์` — ช่องสวมใส่ เจาะเพิ่ม และวิธีถอด"))
    return embed


def codex_topic_full(topic=""):
    """ข้อมูลเต็มหนึ่งหมวด (มี color/footer/inline) — ให้ build_codex_embed ฝั่งดิสแปะเป็น discord.Embed จริง"""
    doc = _build_doc(topic)
    return {"title": doc.title, "description": doc.description, "color": doc.color,
            "footer": doc.footer, "fields": doc.fields}


def codex_topic(topic=""):
    """หัวข้อคู่มือหนึ่งหมวด — {"title","description","fields":[{"name","value"}]} ให้ฝั่งเว็บเรียกตรง ๆ"""
    full = codex_topic_full(topic)
    return {"title": full["title"], "description": full["description"],
            "fields": [{"name": f["name"], "value": f["value"]} for f in full["fields"]]}


def codex_topics():
    """หัวข้อคู่มือทั้งหมด (ตามลำดับ TOPIC_KEYS) — ให้ /codex บนเว็บเรียกตรง ๆ ไม่ต้องผ่าน discord/bot.cogs"""
    out = []
    for t in TOPIC_KEYS:
        d = codex_topic(t)
        out.append({"topic": t, "title": d["title"] or t, "description": d["description"] or "",
                    "fields": d["fields"]})
    return out
