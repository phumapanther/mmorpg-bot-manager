"""📦 หีบสมบัติ — หัวห้องเลือกเปิดเลยหรือเปิดโหวต แล้วลุ้นกับดัก (เฟส 10b)

สเปกข้อ 3.3:
  หัวห้องเลือก "เปิดเลย" หรือ "เปิดโหวต"
  โหวต: สลับเทิร์นให้ทุกคนเลือก เปิด/ข้าม · **เสมอ = ข้าม** (เจ้าของเกมเคาะข้อ 12)
  เปิดแล้ว 50% ได้รางวัล (สุ่มคนเดียวได้) · 50% ติดกับดัก
  กับดัก: **ทุกคนทอย D20 เองในเทิร์นตัวเอง** ≥10 รอด · ไม่รอดเสีย 20% ของเลือดสูงสุด

⚠️ ทอยหลบใช้ `contest.roll_for` ตัวเดียวกับการต่อสู้ ผู้เล่นที่เลือดน้อยจึงหลบ
   ได้แย่ลงเองอัตโนมัติ (คนที่เพิ่งฟื้นมา 1% จะเสียเปรียบ — เจ้าของเกมเคาะข้อ 10)
"""
from bot import config_loader
from bot.games.party import encounter

DEFAULTS = {
    "trap_chance": 50,      # โอกาสติดกับดัก (%)
    "save_need": 10,        # ทอยได้เท่านี้ขึ้นไปถือว่าหลบพ้น
    "trap_dmg_pct": 0.20,   # ไม่รอดเสียกี่ส่วนของเลือดสูงสุด
}

PHASE_CHOOSE = "choose"     # รอหัวห้องเลือกวิธี
PHASE_VOTE = "vote"         # กำลังโหวต
PHASE_SAVE = "save"         # กำลังทอยหลบกับดัก


def _bal(key):
    try:
        return float(config_loader.get_balance(f"party.treasure.{key}", DEFAULTS[key]))
    except (TypeError, ValueError):
        return float(DEFAULTS[key])


def start(members, rng=None):
    ev = encounter.new_state("treasure", members, art="treasure")
    ev["stage"] = PHASE_CHOOSE
    encounter.say(ev, "📦 หีบไม้เก่าตั้งอยู่กลางทาง สลักลายที่ฝาดูไม่คุ้นตา")
    return ev


def options(ev, unit_id, is_host=False):
    """ปุ่มที่คนนี้กดได้ตอนนี้ — ขึ้นกับว่าเหตุการณ์อยู่ช่วงไหน"""
    stage = ev.get("stage")
    if stage == PHASE_CHOOSE:
        if not is_host:
            return []
        return [
            {"key": "open", "name": "🔓 เปิดเลย", "hint": "ลุ้นเอง ไม่ต้องถามใคร"},
            {"key": "vote", "name": "🗳️ เปิดโหวต", "hint": "ให้ทุกคนตัดสินใจร่วมกัน"},
            {"key": "skip", "name": "🚶 ไม่เอา เดินต่อ", "hint": "ปลอดภัยที่สุด"},
        ]
    if stage == PHASE_VOTE:
        return [
            {"key": "yes", "name": "🔓 เปิด", "hint": "อยากลุ้นรางวัล"},
            {"key": "no", "name": "🚶 ข้าม", "hint": "ไม่เสี่ยง"},
        ]
    if stage == PHASE_SAVE:
        return [{"key": "save", "name": "🎲 ทอยหลบกับดัก",
                 "hint": f"ทอยได้ {int(_bal('save_need'))} ขึ้นไปถึงจะพ้น"}]
    return []


def act(ev, unit_id, action, rng, is_host=False):
    """สั่งหนึ่งอย่าง — คืน (ok, ข้อความผิดพลาด|None)

    🔒 ด่านเดียวที่ตัดสินว่าสั่งได้ไหม
    """
    if ev.get("over"):
        return False, "เหตุการณ์นี้จบไปแล้ว"
    stage = ev.get("stage")

    if stage == PHASE_CHOOSE:
        if not is_host:
            return False, "รอหัวห้องตัดสินใจก่อน"
        if action == "skip":
            encounter.say(ev, "🚶 หัวห้องตัดสินใจไม่แตะหีบ ปาร์ตี้เดินต่อ")
            _finish(ev)
            return True, None
        if action == "vote":
            ev["stage"] = PHASE_VOTE
            encounter.say(ev, "🗳️ หัวห้องเปิดโหวต — ทุกคนเลือกได้ว่าจะเปิดหรือข้าม")
            return True, None
        if action == "open":
            encounter.say(ev, "🔓 หัวห้องง้างฝาหีบขึ้นทันที!")
            _resolve(ev, rng)
            return True, None
        return False, "ไม่รู้จักคำสั่งนี้"

    if stage == PHASE_VOTE:
        if action not in ("yes", "no"):
            return False, "ไม่รู้จักคำสั่งนี้"
        if encounter.current(ev) != unit_id:
            return False, "ยังไม่ถึงตาคุณ"
        m = encounter.member(ev, unit_id)
        if not m:
            return False, "คุณไม่ได้อยู่ในเหตุการณ์นี้"
        m["done"], m["choice"] = True, action
        encounter.say(ev, f"{'🔓' if action == 'yes' else '🚶'} {m['name']} "
                          f"โหวต{'เปิด' if action == 'yes' else 'ข้าม'}")
        if encounter.all_done(ev):
            _count_vote(ev, rng)
        return True, None

    if stage == PHASE_SAVE:
        if action != "save":
            return False, "ตอนนี้ทำได้แค่ทอยหลบกับดัก"
        if encounter.current(ev) != unit_id:
            return False, "ยังไม่ถึงตาคุณ"
        m = encounter.member(ev, unit_id)
        if not m or m.get("done"):
            return False, "คุณทอยไปแล้ว"
        _save_roll(ev, m, rng)
        if encounter.all_done(ev):
            _finish(ev)
        return True, None

    return False, "ไม่รู้จักคำสั่งนี้"


def _count_vote(ev, rng):
    """นับโหวต — **เสมอถือว่าข้าม** (เจ้าของเกมเคาะข้อ 12: ปลอดภัยไว้ก่อน)"""
    yes = sum(1 for m in ev["members"] if m.get("choice") == "yes")
    no = sum(1 for m in ev["members"] if m.get("choice") == "no")
    if yes > no:
        encounter.say(ev, f"🗳️ ผลโหวต เปิด {yes} : ข้าม {no} — เปิดหีบ!")
        _resolve(ev, rng)
        return
    tie = " (เสมอถือว่าข้าม)" if yes == no else ""
    encounter.say(ev, f"🗳️ ผลโหวต เปิด {yes} : ข้าม {no}{tie} — ปาร์ตี้เดินต่อ")
    _finish(ev)


def _resolve(ev, rng):
    """เปิดหีบแล้วเกิดอะไร — ครึ่งหนึ่งได้รางวัล ครึ่งหนึ่งติดกับดัก"""
    if rng.randint(1, 100) <= int(_bal("trap_chance")):
        ev["stage"] = PHASE_SAVE
        for m in ev["members"]:
            m["done"], m["choice"] = False, None      # เริ่มรอบทอยใหม่
        ev["turn"] = 0
        encounter.say(ev, "💥 กับดัก! ลูกศรพุ่งออกจากผนัง — ทุกคนต้องทอยหลบเอง")
        return
    ev["prize"] = True
    encounter.say(ev, "✨ ในหีบมีของมีค่าอยู่จริง!")
    _finish(ev)


def _save_roll(ev, m, rng):
    """ทอยหลบของคนนี้ — ใช้เต๋าตัวเดียวกับการต่อสู้ เลือดน้อยจึงเสียเปรียบเอง"""
    from bot.games.party import contest

    need = int(_bal("save_need"))
    unit = {"side": "party", "level": 1, "hp": m.get("hp"),
            "hp_max": m.get("hp_max"), "fx": {}}
    roll = contest.roll_for(unit, rng)
    m["done"] = True
    if roll >= need:
        m["choice"] = "dodged"
        m["roll"] = roll
        encounter.say(ev, f"🎲 {m['name']} ทอยได้ {roll} — ✅ หลบพ้น")
        return
    dmg = max(1, int(int(m.get("hp_max") or 1) * _bal("trap_dmg_pct")))
    m["choice"] = "hit"
    m["roll"] = roll
    m["dmg"] = dmg
    encounter.say(ev, f"🎲 {m['name']} ทอยได้ {roll} — 💥 โดนกับดัก เสีย {dmg:,} เลือด")


def bot_pick(ev, unit_id):
    """บอทเลือกแทนคน AFK — โหวตข้าม (ปลอดภัย) · ถ้าต้องทอยก็ทอย"""
    stage = ev.get("stage")
    if stage == PHASE_VOTE:
        return "no"
    if stage == PHASE_SAVE:
        return "save"
    return "skip"


def _finish(ev):
    ev["over"] = True
    ev["stage"] = "done"
