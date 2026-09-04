"""🎭 คิวเทิร์น + คำสั่ง — หัวใจของโหมดปาร์ตี้

⚠️ **กติกาเหล็ก**: คนที่ไม่ใช่เจ้าของตาปัจจุบันสั่งอะไรไม่ได้
   ศึกไพ่รูนเคยพลาดข้อนี้ คนอื่นลงไพ่แทนกันได้ กว่าจะเจอก็ตอนเทสจริง
   → `_check()` เป็นด่านเดียวที่ทุกคำสั่งต้องผ่าน

⚠️ **`view(uid)` เป็นประตูเดียว** — ห้ามส่ง HP จริงของมอนลงเบราว์เซอร์
   ส่งเป็นเปอร์เซ็นต์แทน ไม่งั้นผู้เล่นคำนวณได้เป๊ะว่าอีกกี่ทีตาย

ไฟล์นี้ไม่รู้จักการวาดภาพ — ทุกอย่างที่เกิดขึ้นออกไปเป็น "เหตุการณ์" (events.py)
"""
import time

from bot import adventure_core, config_loader
from bot.games.party import bot_ai, combat, contest, events, monsters, rules, skills

# โบนัสความไวตามอาชีพ — อาชีพที่ไม่รู้จักได้ 0 (ไม่พัง)
CLASS_SPEED = {
    "Rogue": 6,      # โจรไวสุด
    "Mage": 3,
    "Cleric": 2,
    "Warrior": 0,    # นักรบช้าสุด แลกกับพลังโจมตี
}


def initiative(player, rng):
    """ความไว = level + โบนัสอาชีพ + เต๋า

    ผู้เล่นไม่มีช่อง agility/speed ในฐานข้อมูล (ยืนยันแล้ว 43 ช่อง)
    จึงคำนวณจากของที่มี — เจ้าของเกมเคาะวิธีนี้ 2026-09-03
    """
    lv = int(player.get("level") or 1)
    bonus = CLASS_SPEED.get(player.get("class_name"), 0)
    return lv + bonus + adventure_core.roll_player_die(rng)


def _unit_from_player(p):
    return {
        "id": f"p{p['uid']}", "uid": str(p["uid"]), "side": "party",
        "name": p.get("name") or "ผู้เล่น",
        "hp": int(p.get("hp") or 100), "hp_max": int(p.get("max_hp") or 100),
        "atk": int(p.get("atk") or 10), "def": int(p.get("def") or 0),
        "level": int(p.get("level") or 1),
        "element": p.get("element"), "class_name": p.get("class_name"),
        "defending": False,
        # 🛡️ คุ้มกันรอบแรก — มอนที่ไวกว่าทุกคนกวาดปาร์ตี้ร่วงก่อนใครทันกดอะไร
        #    ไม่สนุกเลย (เจ้าของเกมสั่งให้กันไว้ 2026-09-04)
        "grace": True,
        "fx": {},                   # สถานะชั่วคราว (ช้า · มึน · หลบ · ออร่า)
        "cd": {},                   # คูลดาวน์รายสกิล
    }


def _unit_from_monster(m, idx):
    mid = m.get("id") or f"m{idx + 1}"
    return {
        "id": mid, "side": "monster",
        "name": m.get("name") or (m.get("stats") or {}).get("name") or mid,
        "hp": int(m.get("hp") or 50), "hp_max": int(m.get("hp_max") or m.get("hp") or 50),
        "atk": int(m.get("atk") or 8), "def": int(m.get("def") or 0),
        "level": int(m.get("level") or 1),
        "element": m.get("element"), "defending": False,
        "fx": {},                   # สถานะชั่วคราว
        # ⚠️ ต้องพก rank/stats ติดตัวมาด้วย — rewards.pay คิดทองจาก gold_mult
        #    ในนี้ ไม่มีก็ตกกลับเป็น 1 ทุกตัว บอส Unbeatable (gold_mult 1000)
        #    จ่ายเท่ามอนทั่วไป และ roll_drop ก็แยกแรงค์ไม่ออก
        #    (เจ้าของเกมเห็น "ได้ 8 ทอง" ตอนเทสด้วยมือ 2026-09-04 จึงจับได้)
        "rank": m.get("rank"),
        "stats": dict(m.get("stats") or {}),
        # ── สถานะบอส (เฟส 4) — ห้ามหลุดขึ้นเบราว์เซอร์ ดู view() ──
        "boss": bool(m.get("boss")),
        "phase": None,              # เฟสล่าสุดที่ประกาศไปแล้ว
        "since_big": 0,             # ผ่านมากี่ตาแล้วตั้งแต่ท่าใหญ่ครั้งก่อน
        "charging": False,          # เตือนไว้แล้ว ตาหน้าปล่อยท่า
    }


def start_battle(st, players, monsters, rng):
    """เริ่มสมรภูมิ — ทอยคิวครั้งเดียวแล้วใช้ทั้งรอบ

    ทอยใหม่ทุกตา = ผู้เล่นวางแผนไม่ได้เลย ("อีก 2 ตาถึงเรา เก็บสกิลไว้")
    """
    units = {}
    for p in players:
        u = _unit_from_player(p)
        units[u["id"]] = u
    for i, m in enumerate(monsters):
        u = _unit_from_monster(m, i)
        units[u["id"]] = u

    speed = {}
    for uid, u in units.items():
        speed[uid] = initiative(u, rng)
    order = sorted(units, key=lambda k: (-speed[k], k))

    st.setdefault("extra", {})["battle"] = {
        "order": order, "turn": 0, "round": 1,
        "units": units, "speed": speed,
        "over": False, "winner": None, "log": [],
        "turn_at": time.time(),     # นาฬิกาของตานี้ — หมดเวลาแล้วบอทเล่นแทน
        "seq": 0, "recent": [],     # เหตุการณ์ล่าสุด + เลขลำดับ ให้คนที่ poll ตามทัน
        # ⚠️ รหัสประจำสมรภูมิ — หน้าเว็บใช้จับว่า "ขึ้นรอบใหม่แล้ว"
        #    ดูแค่ seq ถอยหลังไม่พอ: รอบเก่าจบที่ 1 รอบใหม่ก็เริ่มที่ 1 เหมือนกัน
        #    แล้วหน้าเว็บจะนิ่งสนิท ไม่เล่นอนิเมชันอะไรเลยทั้งรอบ
        "bid": time.time(),
    }
    return st


def current_actor(st):
    """ใครถึงตาตอนนี้ — ข้ามคนที่ตายแล้วให้อัตโนมัติ"""
    b = st["extra"]["battle"]
    n = len(b["order"])
    for step in range(n):
        who = b["order"][(b["turn"] + step) % n]
        if b["units"][who]["hp"] > 0:
            if step:
                b["turn"] = (b["turn"] + step) % n
            return who
    return b["order"][b["turn"]]      # ตายหมดทุกคน (check_over จะจบเกมเอง)


def _advance(st):
    """เลื่อนไปคนถัดไปที่ยังไม่ตาย — ครบรอบแล้วนับ round เพิ่ม"""
    b = st["extra"]["battle"]
    n = len(b["order"])
    for step in range(1, n + 1):
        i = (b["turn"] + step) % n
        if b["units"][b["order"][i]]["hp"] > 0:
            if i <= b["turn"]:
                b["round"] += 1
                if b["round"] > 1:
                    for u in b["units"].values():
                        u["grace"] = False      # พ้นรอบแรกแล้ว ล้มได้ตามปกติ
            b["turn"] = i
            b["turn_at"] = time.time()      # เริ่มนาฬิกาใหม่ทุกตา
            return
    b["turn"] = (b["turn"] + 1) % n


def check_over(st):
    """ฝ่ายไหนล้มหมดแล้วจบเกม — คืน True ถ้าจบ"""
    b = st["extra"]["battle"]
    alive = lambda side: any(
        u["hp"] > 0 for u in b["units"].values() if u["side"] == side)
    if not alive("monster"):
        b["over"], b["winner"] = True, "party"
    elif not alive("party"):
        b["over"], b["winner"] = True, "monster"
    return b["over"]


def _check(st, uid, action, target):
    """ด่านเดียวที่ทุกคำสั่งต้องผ่าน — คืน (ok, ข้อความผิดพลาด|หน่วยผู้สั่ง, หน่วยเป้า)"""
    b = st.get("extra", {}).get("battle")
    if not b:
        return False, {"error": "ยังไม่ได้เริ่มสมรภูมิ"}, None
    if b.get("over"):
        return False, {"error": "สมรภูมินี้จบไปแล้ว"}, None

    me_id = f"p{uid}"
    me = b["units"].get(me_id)
    if not me:
        return False, {"error": "คุณไม่ได้อยู่ในสมรภูมินี้"}, None
    if me["hp"] <= 0:
        return False, {"error": "คุณล้มแล้ว — รอเพื่อนชุบ"}, None
    if current_actor(st) != me_id:
        return False, {"error": "ยังไม่ถึงตาคุณ"}, None

    kind = ACTIONS.get(action)
    if kind is None:
        return False, {"error": "ไม่รู้จักคำสั่งนี้"}, None

    if action in skills.SPEC:
        ok, why = can_use_skill(me, action)
        if not ok:
            return False, {"error": why}, None

    # 🐛 "all" ต้องอยู่ตรงนี้ด้วย — AoE กวาดทุกตัวอยู่แล้ว ไม่ต้องเล็ง
    #    เฟส 3 ลืมข้อนี้ ปุ่ม 💥 บนเว็บจึงตอบ "ไม่มีเป้าหมายนี้ในสมรภูมิ" มาตลอด
    #    (เจอตอนเขียนบอทเล่นแทนในเฟส 6 — บอทสั่ง aoe แล้วโดนปฏิเสธ)
    if kind in ("self", "all", None):
        return True, me, None

    tgt = b["units"].get(target)
    if tgt is None:
        return False, {"error": "ไม่มีเป้าหมายนี้ในสมรภูมิ"}, None
    if kind == "fallen":
        # ท่าชุบกลับกัน: เล็งได้เฉพาะคนที่ล้มแล้ว
        if tgt["hp"] > 0:
            return False, {"error": "คนนี้ยังไม่ล้ม ชุบไม่ได้"}, None
        if not can_revive(me):
            return False, {"error": "คุณชุบไม่เป็น — ต้องเป็นนักบวชหรือมีใบชุบชีวิต"}, None
    elif kind == "ally_any":
        pass                    # ✨ Heal ของ Cleric ฟื้นได้ทั้งคนที่ยืนอยู่และคนที่ล้ม
    elif tgt["hp"] <= 0:
        return False, {"error": "เป้าหมายนี้ล้มไปแล้ว"}, None
    if not rules.can_target(kind, me["side"], tgt["side"]):
        return False, {"error": "เล็งเป้าหมายฝั่งนี้ไม่ได้"}, None
    return True, me, tgt


# คำสั่ง -> ชนิดการเล็ง (None = ไม่ต้องเล็ง)
#
# ⚠️ เจ้าของเกมสั่ง 2026-09-04: **ไม่มีคำสั่งกลางอย่างฮีล/ป้องกัน/กวาดแล้ว**
#    เพราะเป็นสกิลของคลาสอยู่แล้ว ทุกคนกดปุ่มเหมือนกันหมดทั้งที่คลาสต่างกันไม่ได้
#    เหลือ: ตีปกติ · หนี · ชุบ(ใช้ไอเทม) + สกิลของคลาสตัวเอง
ACTIONS = {
    "attack": "single",
    "revive": "fallen",     # เล็งเพื่อนที่ล้มแล้วเท่านั้น (ใช้ใบชุบชีวิต)
    "flee": "self",
}
_TARGET_KIND = {"single": "single", "all": "all", "ally": "ally",
                "ally_any": "ally_any", "self": "self", "party": "self"}
for _k, _s in skills.SPEC.items():
    ACTIONS[_k] = _TARGET_KIND[_s["target"]]

TURN_SECONDS = 60           # ช้ากว่านี้บอทเล่นแทน (สเปกข้อ 4)
REVIVE_CLASS = "Cleric"     # นักบวชชุบได้ฟรี
REVIVE_PCT = 0.4            # ฟื้นมาพร้อมเลือดกี่ส่วน


def revive_item(uid):
    """ใบชุบชีวิตในกระเป๋า — คืน item_id หรือ None

    หาจาก effect == "revive" ไม่ใช่ hard-code เลขไอเทม
    (คนแก้ไฟล์ไอเทมจะได้ไม่ต้องมาตามแก้ตรงนี้)
    """
    from bot.models import player_model
    try:
        p = player_model.get_player(int(uid)) or {}
        inv = player_model.load_inventory(p.get("inventory", ""))
        items = config_loader.get_all_items()
        for i in inv:
            if str(items.get(str(i), {}).get("effect", "")) == "revive":
                return str(i)
    except Exception as e:
        print(f"⚠️ [party] หาใบชุบชีวิตไม่ได้: {e}")
    return None


def can_revive(unit):
    """นักบวชชุบได้ฟรี คนอื่นต้องมีใบชุบชีวิต"""
    if unit.get("class_name") == REVIVE_CLASS:
        return True
    return bool(unit.get("uid") and revive_item(unit["uid"]))


def can_use_skill(unit, key):
    """ออกท่านี้ได้ไหม — คืน (ได้ไหม, เหตุผล)

    🔒 ด่านนี้กันคนยิง API ตรง ๆ ใช้ท่าของคลาสอื่น หรือกดรัวข้ามคูลดาวน์
    """
    spec = skills.SPEC.get(key)
    if not spec:
        return False, "ไม่รู้จักท่านี้"
    if key not in skills.kit_for(unit.get("class_name")):
        return False, f"ท่านี้เป็นของคลาส {spec['cls']} ไม่ใช่ของคุณ"
    left = int((unit.get("cd") or {}).get(key) or 0)
    if left > 0:
        return False, f"{spec['name']} ยังไม่พร้อม รออีก {left} ตา"
    if unit.get("uid") and not _has_mana(unit["uid"]):
        return False, "💎 เม็ดคริสตัลหมดแล้ว — ออกท่าไม่ได้ (ไปนอนพักที่เมือง)"
    return True, ""


def _has_mana(uid):
    from bot import mana as _mana
    try:
        return _mana.can_use_skill(int(uid))
    except Exception as e:
        print(f"⚠️ [party] อ่านมานาไม่ได้ uid={uid}: {e}")
        return True          # อ่านไม่ได้ก็อย่าไปขวางผู้เล่น


def _tick_cd(unit):
    """คูลดาวน์ลดลง 1 ตอนถึงตาเจ้าตัว"""
    cd = unit.get("cd")
    if not cd:
        return
    for k in list(cd):
        left = int(cd[k] or 0) - 1
        if left > 0:
            cd[k] = left
        else:
            cd.pop(k, None)


def hurt(tgt, dmg):
    """หักเลือดหนึ่งครั้ง — **รอบแรกไม่ล้ม** เหลืออย่างน้อย 1

    ⚠️ ทางเดียวที่เลือดจะลดในโหมดนี้ ทุกที่ต้องผ่านตรงนี้
       ไม่งั้นมีช่องที่ข้ามการคุ้มกันรอบแรกไปได้
    """
    low = 1 if tgt.get("grace") else 0
    tgt["hp"] = max(low, tgt["hp"] - int(dmg))
    return tgt["hp"]


def strike(me, tgt, action, rng, mult=1.0, skill_used=False, crit_bonus=0):
    """ตีหนึ่งครั้งด้วยกติกา **ทอยแข่งกัน** — คืนรายการเหตุการณ์

    ⚠️ ทางเดียวที่ดาเมจจะเกิดในโหมดนี้ ทั้งฝั่งคนและฝั่งมอน
       ทอยแพ้ = พลาดสนิท ไม่ใช่โดนน้อยลง (เจ้าของเกมสั่ง 2026-09-04)
    """
    out = []
    r = contest.roll_off(me, tgt, rng, skill_used=skill_used)
    out.append(events.contest(me["id"], tgt["id"], r["atk"], r["def"],
                              r["hit"], r["evaded"]))
    if not r["hit"]:
        out.append(events.miss(me["id"], tgt["id"]))
        return out

    dmg, crit = combat.damage(me, tgt, action, r["atk"] + crit_bonus)
    dmg = combat.incoming(me, tgt, int(dmg * mult), tgt["defending"])
    if dmg <= 0:
        out.append(events.miss(me["id"], tgt["id"]))
        return out
    hurt(tgt, dmg)
    out.append(events.attack(me["id"], tgt["id"], dmg, me.get("element"), crit))
    if tgt["hp"] == 0:
        out.append(events.die(tgt["id"]))
    return out


def act(st, uid, action, target, rng):
    """ผู้เล่นสั่งหนึ่งท่า — คืน (ok, {"events": [...]})"""
    ok, me, tgt = _check(st, uid, action, target)
    if not ok:
        return False, me

    b = st["extra"]["battle"]
    out = [events.turn_start(me["id"])]
    me["defending"] = False        # ป้องกันมีผลแค่ตาเดียว
    contest.tick_fx(me)            # สถานะนับถอยหลังตอนถึงตาเจ้าตัว
    _tick_cd(me)

    if action == "flee":
        b["over"], b["winner"] = True, "flee"

    elif action in skills.SPEC:
        allies = [u for u in b["units"].values()
                  if u["side"] == me["side"] and u["hp"] > 0]
        foes = [u for u in b["units"].values()
                if u["side"] != me["side"] and u["hp"] > 0]
        evs, lost = skills.use(me, tgt, action, allies, foes, rng)
        out += evs
        me.setdefault("cd", {})[action] = int(skills.SPEC[action]["cd"])
        if lost and me.get("uid"):
            _spend_mana(me["uid"])       # กฎเกมหลัก: ทอยแพ้เท่านั้นถึงเสียเม็ด

    elif action == "revive":
        # นักบวชชุบฟรี คนอื่นใบชุบชีวิตหายไปหนึ่งใบ (ไม่หัก = ใบเดียวชุบไม่จำกัด)
        if me.get("class_name") != REVIVE_CLASS:
            _consume_revive_item(me.get("uid"))
        tgt["hp"] = max(1, int(tgt["hp_max"] * REVIVE_PCT))
        out.append(events.heal(me["id"], tgt["id"], tgt["hp"]))

    else:                           # attack / skill
        out += strike(me, tgt, action, rng, skill_used=(action == "skill"))

    if not check_over(st):
        _advance(st)
    return True, {"events": out, "state": view(st, uid)}


def _boss_turn(st, me, alive, rng):
    """ตาของบอส — คืน (events, จบตาแล้วไหม)

    ⚠️ ท่าใหญ่ยิงได้ **เฉพาะตอน `charging`** และ `charging` ตั้งได้ที่เดียว
       คือตาที่เตือน → เตือนก่อนเสมอโดยโครงสร้าง ไม่ต้องพึ่งการเช็ค
       (สเปก: ห้ามให้ผู้เล่นตายแบบไม่ทันตั้งตัว)
    """
    out = []
    ph = monsters.boss_phase(me["hp"], me["hp_max"])
    if ph != me.get("phase"):
        me["phase"] = ph
        out.append(events.phase(me["id"], ph))

    if me.get("charging"):
        me["charging"] = False
        me["since_big"] = 0
        dmgs = []
        for t in alive:
            r = contest.roll_off(me, t, rng, skill_used=True)
            out.append(events.contest(me["id"], t["id"], r["atk"], r["def"],
                                      r["hit"], r["evaded"]))
            if not r["hit"]:
                dmgs.append(0)                    # กันไว้ได้ = ไม่โดน
                continue
            d = combat.incoming(me, t, combat.splash(me, [t], "skill", r["atk"])[0],
                                t["defending"])
            hurt(t, d)
            dmgs.append(d)
        out.append(events.aoe(me["id"], [t["id"] for t in alive], dmgs,
                              me.get("element")))
        for t in alive:
            if t["hp"] == 0:
                out.append(events.die(t["id"]))
        return out, True

    tel = monsters.telegraph(me)
    if tel:
        me["charging"] = True
        # ตาเตือนไม่ทำดาเมจเลย — ผู้เล่นจะได้มีตาให้ป้องกัน/ฮีล
        out.append(events.telegraph(me["id"], tel["move"],
                                    [t["id"] for t in alive]))
        return out, True

    me["since_big"] = int(me.get("since_big") or 0) + 1
    return out, False


def monster_turn(st, rng):
    """มอนเดินหนึ่งตา — เล็งผู้เล่นที่ยังไม่ล้มแบบสุ่ม"""
    b = st["extra"]["battle"]
    me_id = current_actor(st)
    me = b["units"][me_id]
    if me["side"] != "monster" or me["hp"] <= 0:
        return []

    out = [events.turn_start(me_id)]
    me["defending"] = False
    contest.tick_fx(me)
    alive = [u for u in b["units"].values() if u["side"] == "party" and u["hp"] > 0]
    if not alive:
        check_over(st)
        return out

    if me.get("boss"):
        evs, done = _boss_turn(st, me, alive, rng)
        out += evs
        if done:
            if not check_over(st):
                _advance(st)
            return out

    tgt = rng.choice(alive)
    out += strike(me, tgt, "attack", rng)

    if not check_over(st):
        _advance(st)
    return out


def view(st, uid):
    """🔒 ประตูเดียวก่อนส่งขึ้นเบราว์เซอร์

    **ห้ามส่ง HP จริงของมอน** — ส่งเป็นเปอร์เซ็นต์แทน
    ไม่งั้นผู้เล่นคำนวณได้เป๊ะว่าอีกกี่ทีตาย ซึ่งทำลายความตื่นเต้น
    (และเฟส 4 จะมีท่าถัดไปของบอสที่ห้ามหลุดยิ่งกว่า)
    """
    b = st.get("extra", {}).get("battle")
    if not b:
        return {"in_battle": False}

    units = []
    for uid_key in b["order"]:
        u = b["units"][uid_key]
        item = {"id": u["id"], "side": u["side"], "name": u["name"],
                "alive": u["hp"] > 0, "defending": u["defending"]}
        if u["side"] == "party":
            item.update(hp=u["hp"], hp_max=u["hp_max"], grace=bool(u.get("grace")),
                        you=(u.get("uid") == str(uid)))
            if item["you"]:
                # ปุ่มชุบต้องเทาไว้ถ้าใช้ไม่ได้ ไม่ใช่ให้กดแล้วค่อยด่า
                item["can_revive"] = can_revive(u)
                # หน้าเว็บสร้างปุ่มจากตรงนี้ — คลาสต่างกันปุ่มต่างกัน
                item["skills"] = [
                    {"key": k, "name": skills.SPEC[k]["name"],
                     "desc": skills.SPEC[k]["desc"],
                     "target": skills.SPEC[k]["target"],
                     "cd": int((u.get("cd") or {}).get(k) or 0)}
                    for k in skills.kit_for(u.get("class_name"))]
                item["mana"], item["mana_max"] = _mana_of(u.get("uid"))
        else:
            item["hp_pct"] = int(u["hp"] * 100 / max(1, u["hp_max"]))
            item["boss"] = bool(u.get("boss"))
            # ⚠️ ห้ามส่ง charging/since_big — หลุดแล้วผู้เล่นกันท่าได้เป๊ะ
        units.append(item)

    return {
        "in_battle": True,
        "order": list(b["order"]),
        "turn_of": current_actor(st),
        "round": b["round"],
        "over": b["over"],
        "winner": b["winner"],
        "units": units,
        "actions": sorted(ACTIONS),
        # คนที่นั่งรออยู่ poll มาเจอ seq ใหม่ = มีอะไรเกิดขึ้น เอา recent ไปเล่นอนิเมชัน
        # (ไม่มีสองอย่างนี้ เพื่อนกดอะไรเราเห็นแค่เลือดเปลี่ยนวูบ ไม่รู้ว่าเกิดอะไร)
        "seq": int(b.get("seq") or 0),
        "recent": list(b.get("recent") or []),
        "bid": str(b.get("bid") or ""),
        # หน้าเว็บเอาไปนับถอยหลัง — หมดเวลาแล้วบอทเล่นแทน
        "turn_left": max(0, int(TURN_SECONDS - (time.time() - float(b.get("turn_at") or 0)))),
    }


def _consume_revive_item(uid):
    """หักใบชุบชีวิตออกจากกระเป๋าหนึ่งใบ"""
    import json

    from bot.models import player_model
    item = revive_item(uid)
    if not item:
        return False
    p = player_model.get_player(int(uid)) or {}
    inv = player_model.load_inventory(p.get("inventory", ""))
    inv.remove(item)
    player_model.update_player_field(int(uid), "inventory", json.dumps(inv))
    return True


def timeout_act(st, rng, now=None):
    """ถึงตาผู้เล่นแต่ไม่ขยับเกิน TURN_SECONDS → บอทเล่นแทนตานั้น

    ⚠️ ไม่มีตัวนี้ **คน AFK คนเดียวค้างทั้งปาร์ตี้** (สเปกข้อ 4)
       คนที่หลุดกลับเข้ามาเมื่อไหร่ก็คุมตัวเองต่อได้ทันที — บอทไม่ยึดตัวถาวร

    คืนรายการเหตุการณ์ ([] = ยังไม่ถึงเวลา หรือไม่ใช่ตาผู้เล่น)
    """
    b = st.get("extra", {}).get("battle")
    if not b or b.get("over"):
        return []
    me_id = current_actor(st)
    me = b["units"].get(me_id) or {}
    if me.get("side") != "party" or me.get("hp", 0) <= 0:
        return []
    if (now or time.time()) - float(b.get("turn_at") or 0) < TURN_SECONDS:
        return []

    allies = [u for u in b["units"].values() if u["side"] == "party"]
    foes = [u for u in b["units"].values() if u["side"] == "monster"]
    # บอทต้องรู้ว่าชุบได้ไหมกับยังมีเม็ดคริสตัลไหม ไม่งั้นเลือกท่าที่สั่งไม่ได้
    left = _mana_of(me.get("uid"))[0] if me.get("uid") else None
    me = dict(me, can_revive=can_revive(me), mana_left=left)
    action, target = bot_ai.choose(me, allies, foes, rng)
    ok, r = act(st, int(me_id[1:]), action, target, rng)
    if ok:
        return r["events"]

    # บอทเลือกท่าที่สั่งไม่ได้ — ห้ามปล่อยให้ค้าง ตีปกติแทน
    #
    # ⚠️ ตัวสำรองเคยเป็น "defend" ซึ่งถูกถอดออกตอนเฟส 9 (กลายเป็นสกิลของคลาส)
    #    ผลคือตัวสำรองพังเงียบ ๆ — บอทเลือกท่าไม่ได้เมื่อไหร่ เกมค้างถาวร
    #    ซึ่งเป็นสิ่งเดียวที่เฟส 6 ตั้งใจกันไว้ (เจอเพราะเทสแดงแบบสุ่ม 2026-09-04)
    #    ตีปกติไม่มีเงื่อนไขอะไรเลย จึงเป็นตัวสำรองที่พังไม่ได้
    print(f"⚠️ [party] บอทสั่ง {action} ไม่ผ่าน: {r.get('error')} — ตีปกติแทน")
    foe = next((u["id"] for u in b["units"].values()
                if u["side"] != me.get("side") and u["hp"] > 0), None)
    if foe is None:
        return []
    ok, r = act(st, int(me_id[1:]), "attack", foe, rng)
    return r["events"] if ok else []


def _spend_mana(uid):
    from bot import mana as _mana
    try:
        _mana.spend(int(uid), 1)
    except Exception as e:
        print(f"⚠️ [party] หักมานาไม่ได้ uid={uid}: {e}")


def _mana_of(uid):
    """เม็ดคริสตัลที่เหลือกับเต็ม — อ่านไม่ได้ก็ส่ง 0/0 ไม่ทำให้หน้าเว็บพัง"""
    from bot import mana as _mana
    from bot.models import player_model
    try:
        p = player_model.get_player(int(uid)) or {}
        return int(_mana.get(int(uid), p)), int(_mana.max_mana(p.get("level", 1)))
    except Exception as e:
        print(f"⚠️ [party] อ่านมานาไม่ได้ uid={uid}: {e}")
        return 0, 0
