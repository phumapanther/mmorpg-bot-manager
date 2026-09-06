"""⚡ ภัยพิบัติ — ทอยหลบรายคน ไม่รอดเจ็บและติดสถานะ (เฟส 10c)

สเปกข้อ 3.4: สุ่มภัยธรรมชาติ · สลับเทิร์นให้แต่ละคนทอย D20 หลบ
ทอยรอด = ไม่เป็นไร · ทอยไม่รอด = เจ็บ + ติดสถานะติดลบ

⚠️ **สถานะติดเฉพาะการเดินทางนี้ ไม่ตามไปโหมดเดี่ยว** (เจ้าของเกมเคาะ 2026-09-05)
   จึงเก็บไว้ที่ `extra["party_fx"]` ของห้อง **ไม่เขียนลง status_effects ของตัวละคร**
   ชื่อสถานะกับตัวเลขความเสียหายยังยืมของเกมหลัก (`game_modifiers.STATUS_EFFECTS`)

⚠️ ทอยหลบใช้ `contest.roll_for` ตัวเดียวกับการต่อสู้ — เลือดน้อยหลบแย่ลงเอง
"""
import random

from bot import config_loader, game_modifiers
from bot.games.party import encounter

KIND = "trap"          # ชื่อเหตุการณ์ตามเกมหลัก (EVENT_LIST)

DEFAULTS = {
    "save_need": 10,      # ทอยได้เท่านี้ขึ้นไปถือว่าหลบพ้น
    "dmg_pct": 0.15,      # ไม่รอดเสียกี่ส่วนของเลือดสูงสุด
    "status_turns": 5,    # ติดสถานะกี่รอบการเดินทาง
}

# ⚠️ **จำนวนรอบมาจากที่นี่ ไม่ใช่ `default_turns` ของเกมหลัก**
#    เพราะ `frostbite` ของเกมหลักตั้งไว้ 999 รอบ — ธีมนั้นเสกใส่ซ้ำทุกก้าวอยู่แล้ว
#    ความหนาวเป็น "สภาพแวดล้อม" ไม่ใช่บาดแผล เอามาใช้ตรง ๆ กับภัยที่เจอหนเดียว
#    จะกลายเป็นเลือดไหลไปตลอดการเดินทาง (ล้างได้แค่หมู่บ้าน/NPC/ดันเจี้ยน)
#    → เหตุการณ์เป็นเจ้าของ "นานแค่ไหน" · เกมหลักเป็นเจ้าของ "เจ็บแค่ไหน"

# ภัยแต่ละแบบ -> สถานะที่ติด
# ⚠️ เลือกเฉพาะสถานะที่มี `step_damage` ในเกมหลัก — กลไกเดียวคือ "เลือดไหลต่อรอบ"
#    สถานะอย่าง numb/burn ทำงานผ่าน hook ในไฟต์ของโหมดเดี่ยวที่โหมดนี้ไม่มี
#    ติดให้ก็ไม่มีผลอะไร หลอกผู้เล่นเปล่า ๆ
KINDS = (
    {"name": "☄️ อุกกาบาตตก", "status": "bleed",
     "intro": "☄️ ท้องฟ้าแดงฉาน ก้อนไฟพุ่งลงมาจากฟากฟ้า!"},
    {"name": "🌋 เถ้าภูเขาไฟ", "status": "poison",
     "intro": "🌋 เถ้าร้อนคละคลุ้งจนหายใจไม่ออก!"},
    {"name": "🥶 พายุหิมะ", "status": "frostbite",
     "intro": "🥶 ลมหนาวเฉือนกระดูกพัดมาเป็นกำแพง!"},
)


def _bal(key):
    try:
        return float(config_loader.get_balance(f"party.disaster.{key}", DEFAULTS[key]))
    except (TypeError, ValueError):
        return float(DEFAULTS[key])


def start(members, rng=None):
    rng = rng or random.Random()
    pick = rng.choice(list(KINDS))
    ev = encounter.new_state(KIND, members, art="trap")
    ev["disaster"] = pick["name"]
    ev["status"] = pick["status"]
    encounter.say(ev, pick["intro"])
    encounter.say(ev, f"🎲 ทุกคนต้องทอยหลบเอง — ได้ {int(_bal('save_need'))} ขึ้นไปถึงจะพ้น")
    return ev


def options(ev, unit_id, is_host=False):
    return [{"key": "dodge", "name": "🎲 ทอยหลบ",
             "hint": f"ได้ {int(_bal('save_need'))} ขึ้นไปถึงจะพ้น"}]


def act(ev, unit_id, action, rng=None, is_host=False):
    """ทอยหลบของคนนี้ — คืน (ok, ข้อความผิดพลาด|None)"""
    if ev.get("over"):
        return False, "เหตุการณ์นี้จบไปแล้ว"
    if action != "dodge":
        return False, "ตอนนี้ทำได้แค่ทอยหลบ"
    if encounter.current(ev) != unit_id:
        return False, "ยังไม่ถึงตาคุณ"
    m = encounter.member(ev, unit_id)
    if not m or m.get("done"):
        return False, "คุณทอยไปแล้ว"

    from bot.games.party import contest
    rng = rng or random.Random()
    need = int(_bal("save_need"))
    unit = {"side": "party", "level": 1, "hp": m.get("hp"),
            "hp_max": m.get("hp_max"), "fx": {}}
    roll = contest.roll_for(unit, rng)
    m["done"], m["roll"] = True, roll

    if roll >= need:
        m["choice"] = "dodged"
        encounter.say(ev, f"🎲 {m['name']} ทอยได้ {roll} — ✅ หลบพ้น")
    else:
        m["choice"] = "hit"
        m["dmg"] = max(1, int(int(m.get("hp_max") or 1) * _bal("dmg_pct")))
        m["status"] = ev["status"]
        m["turns"] = int(_bal("status_turns"))
        lbl = label(ev["status"])
        encounter.say(ev, f"🎲 {m['name']} ทอยได้ {roll} — 💥 เสีย {m['dmg']:,} เลือด "
                          f"และติด {lbl}")

    if encounter.all_done(ev):
        ev["over"] = True
    return True, None


def label(key):
    return (game_modifiers.STATUS_EFFECTS.get(key) or {}).get("label", key)


def bot_pick(ev, unit_id):
    """หนีไม่ได้อยู่แล้ว บอทก็ทอยให้"""
    return "dodge"


# ─────────────────────────────────────────────────────────────
# 🧪 สถานะติดลบของ "การเดินทางนี้" — เก็บที่ห้อง ไม่ใช่ที่ตัวละคร
#    st["extra"]["party_fx"] = {"<uid>": {"poison": เทิร์นเหลือ}}
#    ออกเดินทางใหม่/เริ่มใหม่ = ล้างทิ้ง (room เป็นคนล้าง)
# ─────────────────────────────────────────────────────────────

def of(st, uid):
    """สถานะที่คนนี้ติดอยู่ตอนนี้ — {key: เทิร์นเหลือ}"""
    return dict(((st.get("extra") or {}).get("party_fx") or {}).get(str(uid)) or {})


def afflict(st, uid, key, turns=None):
    """ติดสถานะให้คนนี้ — ติดซ้ำเอาอันที่นานกว่า (กติกาเดียวกับเกมหลัก)"""
    if key not in game_modifiers.STATUS_EFFECTS:
        return
    cfg = game_modifiers.status_cfg(key) or {}
    turns = int(turns or cfg.get("default_turns") or 1)
    box = st.setdefault("extra", {}).setdefault("party_fx", {}).setdefault(str(uid), {})
    box[key] = max(int(box.get(key) or 0), turns)


def tick_round(st, rng=None):
    """ขึ้นรอบใหม่ = สถานะกัดกินหนึ่งครั้งแล้วนับถอยหลัง

    คืน [(uid, key, ดาเมจ)] ให้คนเรียกไปหักเลือดจริงกับเล่าเรื่องเอง
    หักเลือดไม่ถึงตาย — เหลือ 1 เสมอ (ตายเพราะสถานะระหว่างเดินไม่มีในสเปก)
    """
    rng = rng or random.Random()
    box = (st.get("extra") or {}).get("party_fx") or {}
    hits = []
    for uid, fx in list(box.items()):
        for key, left in list(fx.items()):
            cfg = game_modifiers.status_cfg(key) or {}
            lo, hi = cfg.get("step_damage") or (0, 0)
            dmg = rng.randint(int(lo), int(hi)) if int(hi) > 0 else 0
            if dmg:
                hits.append((uid, key, dmg))
            left = int(left) - 1
            if left > 0:
                fx[key] = left
            else:
                fx.pop(key, None)
        if not fx:
            box.pop(uid, None)
    return hits


def cleanse(st, where):
    """ล้างสถานะที่เกมหลักบอกว่า "หายเมื่อเจอที่แบบนี้" — คืนชื่อสถานะที่หายไป"""
    box = (st.get("extra") or {}).get("party_fx") or {}
    gone = []
    for uid, fx in list(box.items()):
        for key in list(fx):
            if where in ((game_modifiers.status_cfg(key) or {}).get("cleanse_on") or []):
                fx.pop(key, None)
                gone.append(label(key))
        if not fx:
            box.pop(uid, None)
    return gone
