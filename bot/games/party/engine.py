"""🎭 คิวเทิร์น + คำสั่ง — หัวใจของโหมดปาร์ตี้

⚠️ **กติกาเหล็ก**: คนที่ไม่ใช่เจ้าของตาปัจจุบันสั่งอะไรไม่ได้
   ศึกไพ่รูนเคยพลาดข้อนี้ คนอื่นลงไพ่แทนกันได้ กว่าจะเจอก็ตอนเทสจริง
   → `_check()` เป็นด่านเดียวที่ทุกคำสั่งต้องผ่าน

⚠️ **`view(uid)` เป็นประตูเดียว** — ห้ามส่ง HP จริงของมอนลงเบราว์เซอร์
   ส่งเป็นเปอร์เซ็นต์แทน ไม่งั้นผู้เล่นคำนวณได้เป๊ะว่าอีกกี่ทีตาย

ไฟล์นี้ไม่รู้จักการวาดภาพ — ทุกอย่างที่เกิดขึ้นออกไปเป็น "เหตุการณ์" (events.py)
"""
from bot import adventure_core, config_loader
from bot.games.party import combat, events, rules

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
            b["turn"] = i
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

    if kind in ("self", None):
        return True, me, None

    tgt = b["units"].get(target)
    if tgt is None:
        return False, {"error": "ไม่มีเป้าหมายนี้ในสมรภูมิ"}, None
    if tgt["hp"] <= 0:
        return False, {"error": "เป้าหมายนี้ล้มไปแล้ว"}, None
    if not rules.can_target(kind, me["side"], tgt["side"]):
        return False, {"error": "เล็งเป้าหมายฝั่งนี้ไม่ได้"}, None
    return True, me, tgt


# คำสั่ง -> ชนิดการเล็ง (None = ไม่ต้องเล็ง)
ACTIONS = {
    "attack": "single",
    "skill": "single",
    "aoe": "all",
    "heal": "ally",
    "defend": "self",
    "flee": "self",
}


def act(st, uid, action, target, rng):
    """ผู้เล่นสั่งหนึ่งท่า — คืน (ok, {"events": [...]})"""
    ok, me, tgt = _check(st, uid, action, target)
    if not ok:
        return False, me

    b = st["extra"]["battle"]
    out = [events.turn_start(me["id"])]
    me["defending"] = False        # ป้องกันมีผลแค่ตาเดียว

    if action == "defend":
        me["defending"] = True

    elif action == "flee":
        b["over"], b["winner"] = True, "flee"

    elif action == "heal":
        amount = int(me["level"] * 3 + adventure_core.roll_player_die(rng))
        tgt["hp"] = min(tgt["hp_max"], tgt["hp"] + amount)
        out.append(events.heal(me["id"], tgt["id"], amount))

    elif action == "aoe":
        foes = [u for u in b["units"].values()
                if u["side"] != me["side"] and u["hp"] > 0]
        roll = adventure_core.roll_player_die(rng, skill_used=True)
        out.append(events.dice(me["id"], [roll]))
        dmgs = combat.splash(me, foes, "skill", roll)
        for f, d in zip(foes, dmgs):
            f["hp"] = max(0, f["hp"] - combat.incoming(me, f, d, f["defending"]))
        out.append(events.aoe(me["id"], [f["id"] for f in foes], dmgs, me.get("element")))
        for f in foes:
            if f["hp"] == 0:
                out.append(events.die(f["id"]))

    else:                           # attack / skill
        roll = adventure_core.roll_player_die(rng, skill_used=(action == "skill"))
        out.append(events.dice(me["id"], [roll]))
        dmg, crit = combat.damage(me, tgt, action, roll)
        dmg = combat.incoming(me, tgt, dmg, tgt["defending"])
        if dmg <= 0:
            out.append(events.miss(me["id"], tgt["id"]))
        else:
            tgt["hp"] = max(0, tgt["hp"] - dmg)
            out.append(events.attack(me["id"], tgt["id"], dmg, me.get("element"), crit))
            if tgt["hp"] == 0:
                out.append(events.die(tgt["id"]))

    if not check_over(st):
        _advance(st)
    return True, {"events": out, "state": view(st, uid)}


def monster_turn(st, rng):
    """มอนเดินหนึ่งตา — เล็งผู้เล่นที่ยังไม่ล้มแบบสุ่ม"""
    b = st["extra"]["battle"]
    me_id = current_actor(st)
    me = b["units"][me_id]
    if me["side"] != "monster" or me["hp"] <= 0:
        return []

    out = [events.turn_start(me_id)]
    me["defending"] = False
    alive = [u for u in b["units"].values() if u["side"] == "party" and u["hp"] > 0]
    if not alive:
        check_over(st)
        return out

    tgt = rng.choice(alive)
    roll = adventure_core.roll_player_die(rng)
    out.append(events.dice(me_id, [roll]))
    dmg, crit = combat.damage(me, tgt, "attack", roll)
    dmg = combat.incoming(me, tgt, dmg, tgt["defending"])
    if dmg <= 0:
        out.append(events.miss(me_id, tgt["id"]))
    else:
        tgt["hp"] = max(0, tgt["hp"] - dmg)
        out.append(events.attack(me_id, tgt["id"], dmg, me.get("element"), crit))
        if tgt["hp"] == 0:
            out.append(events.die(tgt["id"]))

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
            item.update(hp=u["hp"], hp_max=u["hp_max"],
                        you=(u.get("uid") == str(uid)))
        else:
            item["hp_pct"] = int(u["hp"] * 100 / max(1, u["hp_max"]))
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
    }
