"""🪱 แมตช์สนามรบผลัดเทิร์น — สถานะเกมที่กำลังเล่นอยู่

เก็บใน web.db เพราะบอทดิสคอร์ดไม่เกี่ยวกับหมวด PVP เลย (เล่นบนเว็บอย่างเดียว)
หนึ่งคนมีได้แมตช์เดียว — กด "ซ้อมกับบอท" ใหม่คือทิ้งของเดิม

⚠️ ตำแหน่งทุกตัวและพื้นทุกพิกเซลอยู่ฝั่งนี้เท่านั้น เบราว์เซอร์ส่งมาแค่ปุ่มที่กด
   ถ้าเชื่อพิกัดที่เบราว์เซอร์ส่งมา เปิด devtools แล้วเทเลพอร์ตไปยืนหลังศัตรูได้ทันที

🔒 กับดักส่งไปให้เบราว์เซอร์ไม่ได้จนกว่าจะเหยียบโดน — view() คัดออกให้แล้ว
"""
import json
import math
import random
import time

from license_server import web_db

from bot.pvp import physics, terrain, weapons

MOVE_BUDGET = 60         # ก้าวได้กี่ก้าวต่อหนึ่งเทิร์น
TURN_SECONDS = 60        # หมดเวลาเทิร์นแล้วสลับให้เอง (ปิดจอหนีไม่ได้ ทั้งห้องจะได้ไม่ค้าง)
BOT_REACH = 36           # บอทเดินเข้าหาจนใกล้เท่านี้ — ต้องน้อยกว่าระยะฟันสั้นสุด (48) ไม่งั้นเข้าไม่ถึงตัว
TRAP_RADIUS = 7          # เดินเข้าใกล้กับดักเท่านี้ = โดน
TRAP_DAMAGE = (12, 26)
MATCH_TTL = 6 * 3600     # แมตช์ที่ทิ้งไว้เกินนี้ = ล้างทิ้ง (กันตารางบวม)

_SCHEMA = """
CREATE TABLE IF NOT EXISTS worms_matches (
    user_id TEXT PRIMARY KEY,
    state TEXT NOT NULL,
    updated_at REAL NOT NULL
);
"""


def _conn():
    conn = web_db.connect()
    conn.executescript(_SCHEMA)
    return conn


def save(uid, st):
    st["updated_at"] = time.time()
    with _conn() as conn:
        conn.execute("INSERT INTO worms_matches(user_id, state, updated_at) VALUES (?,?,?) "
                     "ON CONFLICT(user_id) DO UPDATE SET state=excluded.state, "
                     "updated_at=excluded.updated_at",
                     (str(uid), json.dumps(st), st["updated_at"]))
    return st


def load(uid):
    with _conn() as conn:
        conn.execute("DELETE FROM worms_matches WHERE updated_at < ?", (time.time() - MATCH_TTL,))
        row = conn.execute("SELECT state FROM worms_matches WHERE user_id=?", (str(uid),)).fetchone()
    return json.loads(row["state"]) if row else None


def drop(uid):
    with _conn() as conn:
        conn.execute("DELETE FROM worms_matches WHERE user_id=?", (str(uid),))


def _grid(st):
    return terrain.decode(st["terrain"])


def _fighter(st, idx=None):
    return st["fighters"][st["turn"] if idx is None else idx]


def new_practice(uid, player_look, seed=0, continent=""):
    """🤖 เริ่มซ้อมกับบอท — คนจริง 1 บอท 1"""
    from bot.game_data import CONTINENTS

    rng = random.Random()
    seed = int(seed) or rng.randrange(1, 10 ** 14)
    if continent not in CONTINENTS:
        continent = rng.choice(list(CONTINENTS))

    grid = terrain.generate(seed, continent)["grid"]
    prng = random.Random(seed ^ 0x5EED)
    props = terrain.place_props(grid, prng)
    # ทุกคนควรเกิดบนผืนที่เดินถึงกันได้ ไม่งั้นคลาสสกิลประชิดเข้าไม่ถึงตัวเลยทั้งเกม
    # แต่ห้ามแลกมาด้วยการเกิดทับกัน — ถ้าเกาะนั้นแคบไป ใช้ทั้งแผนที่แทน
    open_spots = terrain._open_spots(grid)
    island = physics.connected_spots(grid, open_spots, need_span=terrain.SPAWN_GAP)
    spots = terrain.spawns(grid, 2, prng, avoid=props, spots=island)
    if abs(spots[0][0] - spots[1][0]) < terrain.SPAWN_GAP:
        wide = terrain.spawns(grid, 2, prng, avoid=props, spots=open_spots)
        if abs(wide[0][0] - wide[1][0]) > abs(spots[0][0] - spots[1][0]):
            spots = wide
    look = dict(player_look or {})
    bot_look = {**look, "cls": "Mage" if look.get("cls") != "Mage" else "Warrior", "fashion": {}}

    st = {
        "seed": seed, "continent": continent,
        "continent_label": CONTINENTS.get(continent, {}).get("label", continent),
        "terrain": terrain.encode(grid),
        "props": props,                    # รวมกับดัก — ฝั่งนี้เท่านั้น
        "turn": 0, "round": 1, "moves": MOVE_BUDGET, "over": False, "log": [],
        "turn_started": time.time(),
        "fighters": [
            {"name": "คุณ", "bot": False, "hp": 100, "max_hp": 100, "face": 1,
             "x": spots[0][0], "y": spots[0][1], "look": look, "dead": False,
             "buffs": {}, "cd": {}, "bag": {}, "dealt": 0, "kills": 0},
            {"name": "🤖 บอท", "bot": True, "hp": 100, "max_hp": 100, "face": -1,
             "x": spots[1][0], "y": spots[1][1], "look": bot_look, "dead": False,
             "buffs": {}, "cd": {}, "bag": {}, "dealt": 0, "kills": 0},
        ],
    }
    return save(uid, st)


REFLECT_SHARE = 0.5      # เกล็ดน้ำแข็งสะท้อนกลับเท่าไหร่ของดาเมจที่รับมา


def _hurt(st, f, dmg, why, dodgeable=True, by=None):
    """เข้าดาเมจ — บัฟหักล้างกันเป็นชั้น ๆ ก่อนถึงเลือดจริง

    ลำดับ: หลบ (พลาดทั้งหมด) → เปลือกไม้ (กันหมดหนึ่งครั้ง) → ออร่า (ครึ่งเดียว)
    แล้วค่อยสะท้อนกลับถ้าใส่เกล็ดน้ำแข็งอยู่
    """
    buffs = f.setdefault("buffs", {})
    if dodgeable and buffs.get("evade"):
        buffs.pop("evade", None)
        st["log"].append(f"💨 {f['name']} หลบพ้น!")
        return 0
    if dodgeable and buffs.get("bark"):
        buffs.pop("bark", None)
        st["log"].append(f"🧥 เปลือกไม้ของ {f['name']} รับไว้หมด!")
        return 0
    dmg = int(dmg)
    if buffs.get("aura"):
        dmg = max(1, dmg // 2)
    # 🧊 สะท้อนกลับก่อนหักเลือดตัวเอง — ต้องเช็ค by is not f ไม่งั้นระเบิดใส่ตัวเอง
    #    จะสะท้อนใส่ตัวเองซ้ำอีกรอบเป็นวงวน
    if buffs.get("reflect") and by is not None and by is not f and not by["dead"]:
        back = max(1, int(dmg * REFLECT_SHARE))
        st["log"].append(f"🧊 เกล็ดน้ำแข็งสะท้อนกลับใส่ {by['name']}!")
        _hurt(st, by, back, "โดนสะท้อนกลับ", dodgeable=False)
    f["hp"] = max(0, f["hp"] - dmg)
    if by is not None and by is not f:            # เก็บสถิติไว้โชว์ตอนจบเกม
        by["dealt"] = int(by.get("dealt", 0)) + dmg
    st["log"].append(f"{f['name']} {why} -{dmg} HP")
    if f["hp"] <= 0:
        f["dead"] = True
        st["log"].append(f"☠️ {f['name']} ตกรอบ!")
        if by is not None and by is not f:
            by["kills"] = int(by.get("kills", 0)) + 1
    return dmg


def _fall_hurt(st, f, fell, why="ตกจากที่สูง"):
    """เจ็บจากการตก — 🥾 รองเท้าขนนกวายุกันไว้ได้ทั้งหมด"""
    dmg = physics.fall_damage(fell)
    if not dmg:
        return 0
    if f.get("buffs", {}).get("feather"):
        st["log"].append(f"🥾 {f['name']} ร่อนลงเบา ๆ ไม่เจ็บเลย")
        return 0
    return _hurt(st, f, dmg, why, dodgeable=False)


def _drown(st, f):
    f["hp"], f["dead"] = 0, True
    st["log"].append(f"🌊 {f['name']} ตกน้ำ!")


def _spring_traps(st, f):
    """เดินไปโดนกับดักไหม — โดนแล้วกับดักหายไป (ใช้ครั้งเดียว) และเพิ่งเปิดเผยตอนนี้"""
    hit = []
    for p in list(st["props"]):
        if p["kind"] != "trap" or abs(p["x"] - f["x"]) > TRAP_RADIUS:
            continue
        if abs(p["y"] - f["y"]) > TRAP_RADIUS:
            continue
        st["props"].remove(p)
        dmg = random.Random(st["seed"] ^ p["x"]).randint(*TRAP_DAMAGE)
        _hurt(st, f, dmg, "เหยียบกับดัก 🕳️")
        hit.append({"x": p["x"], "y": p["y"], "damage": dmg})
    return hit


def _ride_ferry(st, grid, f):
    """🎈 เดินทับเรือเหาะ = ลอยข้ามไปอีกเกาะ

    เลือกจุดลงที่ "เดินจากตรงนี้ไปไม่ถึง" เท่านั้น — ไม่งั้นก็แค่วาร์ปข้ามฝั่งเกาะเดิม
    ซึ่งไม่ได้แก้ปัญหาที่เจ้าของเกมทักมาว่าเดินข้ามเกาะแทบเป็นไปไม่ได้
    """
    for p in list(st["props"]):
        if p["kind"] != "ferry" or abs(p["x"] - f["x"]) > 8 or abs(p["y"] - f["y"]) > 12:
            continue
        here = physics.walk_group(grid, (f["x"], f["y"]))
        rng = random.Random(st["seed"] ^ (p["x"] * 6997))
        far = [xy for xy in terrain._open_spots(grid) if xy not in here]
        if not far:
            continue                       # ไม่มีเกาะอื่นให้ไป ก็เก็บเรือไว้ก่อน
        st["props"].remove(p)
        x, y = rng.choice(far)
        f["x"], f["y"] = x, y
        st["log"].append(f"🎈 {f['name']} ขึ้นเรือเหาะข้ามไปอีกเกาะ!")
        return {"x": x, "y": y, "from": [p["x"], p["y"]]}
    return None


def _open_chests(st, f):
    """เดินทับหีบ = เปิดเลย ได้อาร์ติแฟกต์หนึ่งชิ้น

    นี่คือ **ทางเดียว** ที่จะได้ไอเทมโจมตีในสนาม — ไม่ได้ดึงจากกระเป๋าในเกมหลัก
    ทุกคนเข้าสนามมือเปล่าเท่ากันตามที่เจ้าของเกมเคาะ
    """
    got = []
    for p in list(st["props"]):
        if p["kind"] != "chest" or abs(p["x"] - f["x"]) > 8 or abs(p["y"] - f["y"]) > 12:
            continue
        st["props"].remove(p)
        rng = random.Random(st["seed"] ^ (p["x"] * 7919))     # หีบเดิมได้ของเดิมเสมอ
        key = rng.choice(sorted(weapons.ARTIFACTS))
        bag = f.setdefault("bag", {})
        bag[key] = bag.get(key, 0) + 1
        st["log"].append(f"🎁 {f['name']} เปิดหีบได้ {weapons.ARTIFACTS[key]['name']}!")
        got.append({"x": p["x"], "y": p["y"], "item": key,
                    "name": weapons.ARTIFACTS[key]["name"]})
    return got


def move(uid, action, direction=1, steps=1, jump_power=1.0, lean=0.0):
    """เดิน/กระโดด — คืน (ok, ผล) · ตำแหน่งใหม่ตัดสินที่นี่เท่านั้น"""
    st = load(uid)
    if not st:
        return False, {"error": "ยังไม่ได้เริ่มแมตช์ — กดซ้อมกับบอทก่อน"}
    if st["over"]:
        return False, {"error": "แมตช์นี้จบแล้ว"}

    if time_left(st) <= 0:
        return False, {"error": "⏱️ หมดเวลาเทิร์นแล้ว — กดจบเทิร์นได้เลย"}

    f = _fighter(st)
    if f["bot"]:
        return False, {"error": "ยังไม่ถึงตาคุณ"}
    if f["dead"]:
        return False, {"error": "ตัวละครของคุณตกรอบแล้ว"}

    direction = 1 if int(direction) >= 0 else -1
    f["face"] = direction
    grid = _grid(st)

    if action == "jump":
        if st["moves"] < 6:
            return False, {"error": "แรงเดินหมดแล้ว — จบเทิร์นได้เลย"}
        st["moves"] -= 6
        r = physics.jump(grid, f["x"], f["y"], direction, jump_power, lean)
    elif action == "walk":
        steps = max(1, min(int(steps), st["moves"]))
        if st["moves"] <= 0:
            return False, {"error": "แรงเดินหมดแล้ว — จบเทิร์นได้เลย"}
        r = physics.walk(grid, f["x"], f["y"], direction, steps, physics.SAFE_DROP)
        st["moves"] -= max(len(r["path"]), 1)
    else:
        return False, {"error": "ไม่รู้จักท่านี้"}

    hp_before = f["hp"]
    f["x"], f["y"] = r["x"], r["y"]
    if r["drowned"]:
        _drown(st, f)
    else:
        _fall_hurt(st, f, r["fell"])

    traps = [] if f["dead"] else _spring_traps(st, f)     # กับดักที่เพิ่งเหยียบโดน
    chests = [] if f["dead"] else _open_chests(st, f)     # หีบที่เพิ่งเปิด
    ferry = None if f["dead"] else _ride_ferry(st, grid, f)
    _check_over(st)
    save(uid, st)
    deaths = _death_blasts(st, _grid(st))
    _check_over(st)
    mine = {"move": r, "sprung": traps, "opened": chests, "ferry": ferry,
            "deaths": deaths}

    # 🩸 เจ็บเมื่อไหร่จบเทิร์นทันที (เจ้าของเกมสั่ง) — ตกจากที่สูง เหยียบกับดัก
    #    ระเบิดใส่ตัวเอง หรือโดนลูกหลง ล้วนจบเทิร์นเหมือนกันหมด
    # แรงเดินหมด = จบเทิร์นให้เลย ไม่ต้องให้ผู้เล่นมากดเอง
    # (ใช้สกิลก็จบเทิร์นอยู่แล้ว เดินจนหมดแรงจึงเท่ากับเลือกทางเดินแทนทางยิง)
    if not st["over"] and (st["moves"] <= 0 or f["hp"] < hp_before):
        ok, after = end_turn(uid)
        if ok:
            return True, mine | {"auto_ended": True} | after
    return True, mine | view(uid, st)


KNOCK_PER_DMG = 0.5     # ดาเมจหนึ่งหน่วย = กระเด็นออกไปกี่พิกเซล
KNOCK_MAX = 34          # กระเด็นไกลสุดต่อหนึ่งหมัด


def _knock_back(st, grid, f, from_x, dmg, dist=None):
    """💥 โดนแล้วต้องกระเด็น — แรงตามดาเมจ ทิศออกจากจุดที่โดน

    คืนเส้นทางไว้ให้เว็บเล่นภาพ (ไม่ส่งไปก็เห็นตัวเทเลพอร์ตไปโผล่)
    ไม่ใส่เพดานความลึกให้ walk() — โดนกระแทกตกหน้าผาหรือลงทะเลได้ตามจริง
    """
    if f["dead"] or dmg <= 0:
        return None
    dist = int(min(KNOCK_MAX, dist if dist is not None else dmg * KNOCK_PER_DMG))
    if dist < 2:
        return None
    d = 1 if f["x"] >= from_x else -1
    kb = physics.walk(grid, f["x"], f["y"], d, dist)
    if kb["drowned"]:
        # ⚠️ กระเด็นตกหน้าผาได้ (นั่นคือเสน่ห์ของท่ากระแทก) แต่ห้ามปลิวลงทะเลตายเอง
        #    วัดแล้ว: ยืนเฉย ๆ ไม่ทำอะไร 40 เมล็ด ตกทะเลตายไป 30 — จบเกมเฉลี่ย 5 เทิร์น
        #    ผู้เล่นเห็นเป็น "อยู่ ๆ ก็ตกรอบแพ้เอง" เพราะโดนหมัดธรรมดาก็ปลิวลงน้ำแล้ว
        kb = physics.walk(grid, f["x"], f["y"], d, dist, physics.SAFE_DROP)
    f["x"], f["y"] = kb["x"], kb["y"]
    if kb["drowned"]:
        _drown(st, f)
    else:
        _fall_hurt(st, f, kb["fell"], "กระเด็นตกจากที่สูง")
    return {"name": f["name"], "path": kb["path"]} if kb["path"] else None


def _explode(st, grid, cx, cy, radius, dmg, crater, why, by=None):
    """💥 ระเบิด ณ จุดหนึ่ง — เจาะพื้นเป็นหลุมแล้วกระจายดาเมจตามระยะ

    เจาะหลุมด้วย carve() ตัวเดียวกับที่ใช้กับพื้นดิน กำแพงปราสาท/ต้นไม้จึงพังด้วยเลย
    ระเบิดหลบไม่ได้ (dodgeable=False) — สกิลหลบมีไว้กันการฟันตรง ๆ
    """
    gone = terrain.carve(grid, cx, cy, crater) if crater else []
    hits, knocks = [], []
    for f, raw in weapons.blast_targets(cx, cy, st["fighters"], radius, dmg):
        got = _hurt(st, f, raw, why, dodgeable=False, by=by)
        if got:
            hits.append({"name": f["name"], "damage": got, "x": f["x"], "y": f["y"]})
    if gone:
        st["terrain"] = terrain.encode(grid)
        _settle_everyone(st, grid)
    for h in hits:                       # ผลักหลังเจาะหลุมเสร็จ จะได้กระเด็นบนพื้นใหม่
        f = next((x for x in st["fighters"] if x["name"] == h["name"]), None)
        kb = _knock_back(st, grid, f, cx, h["damage"]) if f else None
        if kb:
            knocks.append(kb)
    return {"x": cx, "y": cy, "crater": crater, "hits": hits, "knocks": knocks}


SCRAMBLE = 46           # พื้นหายแล้วไถลไปเกาะขอบได้ไกลสุดเท่านี้


def _scramble(grid, x, y):
    """หาที่ยืนใกล้ ๆ ตอนพื้นใต้เท้าหายไป — คืน None ถ้าไม่มีจริง ๆ

    ⚠️ ไม่มีข้อนี้แล้วเกมพัง: ยิงทะลุเกาะทีเดียวคนที่ยืนอยู่ร่วงลงทะเลตายทันที
       วัดแล้ว ผู้เล่นยืนเฉย ๆ 40 เมล็ด จบเกมด้วยการตกน้ำ 22 ครั้ง
       ผู้เล่นเห็นเป็น "อยู่ ๆ ก็ตกรอบแพ้เอง" เพราะไม่ได้ทำอะไรผิดเลย
    """
    for d in range(1, SCRAMBLE + 1):
        for nx in (x - d, x + d):
            for ny in range(y - physics.CLIMB, y + SCRAMBLE):
                if physics.standable(grid, nx, ny):
                    return nx, ny
    return None


DEATH_RADIUS, DEATH_DMG, DEATH_CRATER = 36, 24, 20


def _death_blasts(st, grid):
    """💀 ใครตายก็ระเบิดทิ้งตัวเอง ทำดาเมจรอบด้าน

    วนจนไม่มีใครตายเพิ่ม — ระเบิดของคนหนึ่งฆ่าอีกคนได้ คนนั้นก็ต้องระเบิดต่อ
    คืนรายการไว้ให้เว็บเล่นภาพทีละลูก แล้วค่อยสรุปผลตอนภาพจบ
    """
    out = []
    for _ in range(len(st["fighters"]) + 1):
        pending = [f for f in st["fighters"] if f["dead"] and not f.get("boomed")]
        if not pending:
            break
        for f in pending:
            f["boomed"] = True
            st["log"].append(f"💥 ร่างของ {f['name']} ระเบิด!")
            blast = _explode(st, grid, f["x"], f["y"] - terrain.CH_H // 2,
                             DEATH_RADIUS, DEATH_DMG, DEATH_CRATER, "โดนแรงระเบิดจากร่าง")
            out.append({"name": f["name"], "x": f["x"], "y": f["y"], "blast": blast})
    return out


def _settle_everyone(st, grid):
    """พื้นใต้เท้าหายไปแล้วต้องร่วงลง ไม่ใช่ยืนลอยอยู่กลางอากาศ"""
    for f in st["fighters"]:
        if f["dead"]:
            continue
        if physics.standable(grid, f["x"], f["y"]):
            continue
        x, y, fell, drowned = physics.settle(grid, f["x"], f["y"])
        if drowned:
            spot = _scramble(grid, f["x"], f["y"])       # ตะกายขึ้นขอบที่ใกล้ที่สุดก่อน
            if spot:
                x, y = spot
                fell, drowned = max(0, y - f["y"]), False
                st["log"].append(f"🧗 {f['name']} คว้าขอบไว้ทัน!")
        f["x"], f["y"] = x, y
        if drowned:
            _drown(st, f)
        else:
            _fall_hurt(st, f, fell, "ร่วงลงมาเพราะพื้นหาย")


def attack(uid, skill, angle=None, power=70, direction=None):
    """⚔️ ใช้สกิล — คืน (ok, ผล) · ใช้แล้วจบเทิร์นทันทีเสมอ

    เบราว์เซอร์ส่งมาแค่ "ใช้สกิลอะไร เล็งมุมไหน แรงเท่าไหร่"
    ผลทั้งหมด (โดนใคร พื้นพังตรงไหน) ตัดสินที่นี่
    """
    st = load(uid)
    if not st:
        return False, {"error": "ยังไม่ได้เริ่มแมตช์ — กดซ้อมกับบอทก่อน"}
    if st["over"]:
        return False, {"error": "แมตช์นี้จบแล้ว"}
    if time_left(st) <= 0:
        return False, {"error": "⏱️ หมดเวลาเทิร์นแล้ว — กดจบเทิร์นได้เลย"}

    f = _fighter(st)
    if f["bot"]:
        return False, {"error": "ยังไม่ถึงตาคุณ"}
    if f["dead"]:
        return False, {"error": "ตัวละครของคุณตกรอบแล้ว"}

    if f.get("buffs", {}).get("emp"):
        return False, {"error": "⚡ โดนคลื่น EMP อยู่ — เทิร์นนี้ทำได้แค่เดิน"}

    key = str(skill or "")
    artifact = key in weapons.ARTIFACTS
    if artifact:
        if int(f.get("bag", {}).get(key, 0)) <= 0:
            return False, {"error": "❌ คุณไม่มีไอเทมชิ้นนี้ — หาจากหีบสมบัติในสนาม"}
    elif key not in weapons.kit_for((f.get("look") or {}).get("cls")):
        return False, {"error": "คลาสของคุณใช้สกิลนี้ไม่ได้"}
    left = int(f.setdefault("cd", {}).get(key, 0))
    if left > 0:
        return False, {"error": f"⏳ สกิลนี้ยังคูลดาวน์อีก {left} เทิร์น"}

    if direction is not None:
        f["face"] = 1 if int(direction) >= 0 else -1      # เล็งซ้าย/ขวาได้ ไม่ใช่ยิงตามที่เดินล่าสุด
    grid = _grid(st)
    r = _use_skill(st, grid, f, key, angle, power)
    if artifact:
        f["bag"][key] -= 1           # อาร์ติแฟกต์ใช้ครั้งเดียวหมด
        if f["bag"][key] <= 0:
            f["bag"].pop(key, None)
    cd = weapons.spec(key)["cooldown"]
    if cd:
        f["cd"][key] = cd + 1        # +1 เพราะจะถูกลบหนึ่งตอนขึ้นเทิร์นของตัวเอง

    deaths = _death_blasts(st, grid)   # ตายจากหมัดนี้ก็ระเบิดต่อ (ลูกโซ่ได้)
    _check_over(st)
    save(uid, st)
    ok, after = end_turn(uid)        # ใช้สกิลแล้วจบเทิร์นทันที
    return True, {"attack": r, "deaths": deaths} | (after if ok else view(uid))


def _use_skill(st, grid, f, key, angle, power):
    """ลงมือใช้สกิลหนึ่งอัน — คืนผลไว้ให้เบราว์เซอร์เล่นภาพ"""
    s = weapons.spec(key)
    if angle is None:
        # ท่าประชิดตั้งต้น = ฟันตรงหน้า · ท่ายิงตั้งต้น = โยนโค้ง 45°
        angle = 0 if s["kind"] == "melee" else 45
    angle = max(-89, min(89, float(angle)))
    power = max(10, min(100, float(power)))
    out = {"skill": key, "name": s["name"], "kind": s["kind"]}

    if s["kind"] == "self":
        # บัฟ/ของป้องกัน — ไม่มีดาเมจ ไม่มีหลุม ไม่มีเป้า เว็บจะได้เล่นเอฟเฟกต์บัฟล้วน ๆ
        out["from"] = [f["x"], f["y"]]
        out["hits"] = []
        if s.get("heal"):
            before = f["hp"]
            f["hp"] = min(f["max_hp"], f["hp"] + s["heal"])
            st["log"].append(f"✨ {f['name']} ฟื้นเลือด +{f['hp'] - before} HP")
            out["heal"] = f["hp"] - before
        if s.get("buff"):
            b = weapons.BUFFS[s["buff"]]
            f.setdefault("buffs", {})[s["buff"]] = b["turns"] + 1
            st["log"].append(f"{b['name']} ติดตัว {f['name']} แล้ว")
            out["buff"] = s["buff"]
        return out

    if s["kind"] == "melee":
        # ฟันได้ 360° — ทิศมาจากมุมที่เล็ง คูณกับฝั่งที่กด ไม่ใช่แค่ซ้าย/ขวาแบน ๆ
        rad = math.radians(angle)
        ax, ay = math.cos(rad) * f["face"], -math.sin(rad)
        out["reach"] = s["reach"]
        out["from"] = [f["x"], f["y"]]
        out["face"] = f["face"]
        out["aim"] = [round(ax, 3), round(ay, 3)]
        hits, knocks = [], []
        out["times"] = s.get("times", 1)
        for t in weapons.melee_targets(f, st["fighters"], s["reach"], (ax, ay)) * s.get("times", 1):
            if t["dead"]:
                continue
            dmg = s["dmg"]
            if s.get("behind") and t["face"] == f["face"]:     # หันหลังให้เรา = ลอบแทง
                dmg = int(dmg * s["behind"])
                st["log"].append(f"🗡️ ลอบแทงจากด้านหลัง!")
            got = _hurt(st, t, dmg, f"โดน {s['name']}", by=f)
            hits.append({"name": t["name"], "damage": got, "x": t["x"], "y": t["y"],
                         "dodged": got == 0})
            # ทุกหมัดที่เข้าต้องผลักให้กระเด็น ไม่ใช่แค่ท่าที่ตั้ง knock ไว้
            kb = _knock_back(st, grid, t, f["x"], got, dist=s.get("knock"))
            if kb:
                knocks.append(kb)
        out["hits"] = hits
        out["knocks"] = knocks
        if s.get("crater"):
            # เจาะที่ระดับเข่า — ต่ำพอให้กัดพื้นตรงหน้าจริง (ระดับอกอย่างเดียว
            # ยืนบนลานราบแล้วต่อยไปก็ไม่โดนอะไรเลย) แต่ยังสูงพอไม่ตัดพื้นใต้เท้าขาด
            # จนคู่ต่อสู้ร่วงลงทะเลตายทุกครั้ง — เทสไล่ 15 เมล็ด × ทุกท่าคุมไว้อยู่
            # ระยะฟันไกลได้ แต่หลุมต้องอยู่ตรงหน้าตัวเสมอ ไม่ใช่ไปโผล่สุดปลายระยะ
            # (พอเพิ่มระยะเป็นสองเท่า จุดเจาะเลยลอยไปกลางอากาศ ไม่โดนพื้นอีกเลย)
            reach = min(s["reach"] // 2, 16)
            cx = int(f["x"] + ax * reach)
            cy = int(f["y"] - terrain.CH_H // 4 + ay * reach)
            out["blast"] = _explode(st, grid, cx, cy, 0, 0, s["crater"], "")
        if not hits:
            st["log"].append(f"{f['name']} ใช้ {s['name']} แต่ไม่โดนใคร")
        return out

    # lob / beam — ต้องเล็ง
    aim = angle * f["face"] if f["face"] < 0 else angle
    if f["face"] < 0:
        aim = 180 - angle
    out["angle"], out["power"] = angle, power
    shot = (physics.beam(grid, f["x"], f["y"], aim) if s["kind"] == "beam"
            else physics.shoot(grid, f["x"], f["y"], aim, power))
    out["path"] = shot["path"]

    if s["kind"] == "beam":
        # ⚡ ลำแสงโดนทุกคนที่มันพาดผ่าน ไม่ใช่แค่คนที่อยู่ตรงปลายทาง
        beam_hits = []
        for t in weapons.path_targets(shot["path"], st["fighters"], exclude=f):
            got = _hurt(st, t, s["dmg"], f"โดน {s['name']}", by=f)
            beam_hits.append({"name": t["name"], "damage": got, "x": t["x"], "y": t["y"],
                              "dodged": got == 0})
        out["hits"] = beam_hits
        if not beam_hits:
            st["log"].append(f"{f['name']} ยิง {s['name']} พลาดไม่โดนใคร")

    if not shot["hit"]:
        st["log"].append(f"{f['name']} ยิง {s['name']} พลาดออกนอกสนาม")
        return out

    out["blast"] = _explode(st, grid, shot["x"], shot["y"], s["radius"],
                            s["dmg"], s.get("crater", 0), f"โดน {s['name']}", by=f)
    if s.get("buff"):
        b = weapons.BUFFS[s["buff"]]
        for h in out["blast"]["hits"]:
            t = next((x for x in st["fighters"] if x["name"] == h["name"]), None)
            if t and not t["dead"]:
                t.setdefault("buffs", {})[s["buff"]] = b["turns"]
                st["log"].append(f"{b['name']} ติดตัว {t['name']}")
    return out


def time_left(st):
    """เหลือเวลาในเทิร์นนี้กี่วินาที — เซิร์ฟเวอร์เป็นคนนับ ไม่ใช่นาฬิกาในเบราว์เซอร์"""
    if st.get("over"):
        return 0
    return max(0, int(TURN_SECONDS - (time.time() - st.get("turn_started", 0))))


DROP_EVERY = 1          # ครบกี่รอบถึงเติมของใหม่ลงสนาม
DROP_MAX = 14           # ของบนแผนที่พร้อมกันได้มากสุดเท่านี้


def _supply_drop(st):
    """📦 ครบหนึ่งรอบ (ทุกคนเล่นครบ) = เติมของใหม่ลงสนาม

    ⚠️ จำเป็นจริง ๆ ไม่ใช่ของแถม: แผนที่เป็นเกาะลอย เดินข้ามเกาะแทบไม่ได้เลย
       เกมเลยกลายเป็นยืนยิงกันข้ามน้ำอย่างเดียว
       เรือเหาะให้ข้ามเกาะได้ · หีบให้ของโจมตี · กับดักให้ต้องระวังทางเดิน
    """
    grid = _grid(st)
    rng = random.Random(st["seed"] ^ (st["round"] * 104729))
    taken = [p["x"] for p in st["props"]] + [f["x"] for f in st["fighters"]]
    room = DROP_MAX - len(st["props"])
    if room <= 0:
        return []
    # ⚠️ ยิ่งของเยอะ ที่ว่างยิ่งหายาก ถ้ายืนกรานระยะห่างเดียวการเติมของจะหยุดเงียบ ๆ
    #    ตั้งแต่รอบสาม (วัดแล้ว: 13 รอบเติมได้แค่ครั้งเดียว) — ผ่อนลงจนหาที่วางได้
    spots = terrain._open_spots(grid)
    for gap in (24, 16, 10):
        pool = [xy for xy in spots if all(abs(xy[0] - t) >= gap for t in taken)]
        if pool:
            break
    if not pool:
        return []
    rng.shuffle(pool)
    # 🎈 เกาะละลำเดียวพอ — วางซ้ำเกาะเดิมก็แค่วาร์ปวนอยู่แถวเดิม ไม่ได้ช่วยข้ามเกาะ
    taken_isles = set()
    for p in st["props"]:
        if p["kind"] == "ferry":
            taken_isles |= physics.walk_group(grid, (p["x"], p["y"]))

    kinds = ["ferry", "chest", "chest", "trap"]
    fresh = []
    for x, y in pool:
        if len(fresh) >= min(room, len(kinds)):
            break
        if any(abs(x - u["x"]) < 24 for u in fresh):
            continue
        kind = kinds[len(fresh)]
        if kind == "ferry":
            if (x, y) in taken_isles:
                continue                       # เกาะนี้มีเรืออยู่แล้ว ข้ามไปหาที่อื่น
            taken_isles |= physics.walk_group(grid, (x, y))
        fresh.append({"kind": kind, "x": x, "y": y})
    st["props"].extend(fresh)
    if fresh:
        st["log"].append(f"📦 ของใหม่ลงสนาม {len(fresh)} จุด (รอบ {st['round']})")
    # 🔒 กับดักห้ามหลุดไปฝั่งเบราว์เซอร์เด็ดขาด — ตัดทิ้งตั้งแต่ตรงนี้
    #    (รายการนี้ถูกส่งขึ้นเว็บจริงเพื่อพากล้องไปดูของใหม่ทีละชิ้น)
    st["drops"] = [{"kind": p["kind"], "x": p["x"], "y": p["y"]}
                   for p in fresh if p["kind"] != "trap"]
    return st["drops"]


def _pass_turn(st):
    """สลับไปคนถัดไปที่ยังไม่ตาย แล้วรีเซ็ตแรงเดินกับนาฬิกา"""
    if not [f for f in st["fighters"] if not f["dead"]]:
        st["over"] = True
        return
    for _ in range(len(st["fighters"])):
        st["turn"] = (st["turn"] + 1) % len(st["fighters"])
        if not st["fighters"][st["turn"]]["dead"]:
            break
    if st["turn"] == 0:
        st["round"] += 1
        st["drops"] = []
        if st["round"] % DROP_EVERY == 0:
            _supply_drop(st)
    f = _fighter(st)
    for d, key in ((f.setdefault("buffs", {}), "buffs"), (f.setdefault("cd", {}), "cd")):
        for k in list(d):
            d[k] -= 1
            if d[k] <= 0:
                d.pop(k)
    st["moves"] = MOVE_BUDGET // 2 if f.get("buffs", {}).get("slow") else MOVE_BUDGET
    st["turn_started"] = time.time()
    _check_over(st)


BOT_MAX_FALL = 30        # บอทยอมกระโดดลงได้สูงสุดเท่านี้ ลึกกว่านี้ไม่เอา


def _bot_safe_walk(grid, x, y, d, steps):
    """เดินแบบมองล่วงหน้า — ตัดก้าวที่จะพาไปตกน้ำหรือตกสูงจนเจ็บหนักออก

    ไม่งั้นบอทเดินตรงเข้าหาผู้เล่นแล้วร่วงลงทะเลตายตั้งแต่เทิร์นแรก
    (เจอจริงตอนเทส: บอทตายเองในรอบที่ 3 ทุกครั้ง ซ้อมไม่ได้เลย)
    """
    while steps > 0:
        r = physics.walk(grid, x, y, d, steps)
        if not r["drowned"] and physics.fall_damage(r["fell"]) == 0 and r["fell"] <= BOT_MAX_FALL:
            return r
        steps -= 1
    return {"path": [], "x": x, "y": y, "drowned": False, "fell": 0}


def _bot_turn(st):
    """🤖 บอทเดินเข้าหาศัตรูที่ใกล้ที่สุด ติดกำแพงก็กระโดดข้าม แล้วจบเทิร์น

    ยังไม่มีระบบโจมตี บอทจึงทำได้แค่ขยับ — พอทำสกิลเสร็จค่อยมาเพิ่มการยิงตรงนี้
    คืนรายการผลการเคลื่อนที่ ไว้ให้เบราว์เซอร์เล่นภาพเรียงกัน
    """
    me = _fighter(st)
    prey = [f for f in st["fighters"] if not f["dead"] and f is not me]
    if not prey:
        return []
    target = min(prey, key=lambda f: abs(f["x"] - me["x"]))
    grid = _grid(st)
    out, stuck = [], 0

    while st["moves"] > 0 and not me["dead"] and stuck < 2:
        gap = target["x"] - me["x"]
        if abs(gap) <= BOT_REACH:
            break
        d = 1 if gap > 0 else -1
        me["face"] = d
        before = me["x"]
        r = _bot_safe_walk(grid, me["x"], me["y"], d, min(12, st["moves"]))
        if not r["path"] and st["moves"] >= 6:      # ไปต่อไม่ได้ — ลองกระโดดข้าม
            j = physics.jump(grid, me["x"], me["y"], d)
            st["moves"] -= 6
            r = j if not j["drowned"] else r        # กระโดดแล้วตกน้ำก็อยู่เฉย ๆ ดีกว่า
        else:
            st["moves"] -= max(len(r["path"]), 1)

        me["x"], me["y"] = r["x"], r["y"]
        if r["drowned"]:
            _drown(st, me)
        else:
            _fall_hurt(st, me, r["fell"])
        if not me["dead"]:
            _spring_traps(st, me)
            _open_chests(st, me)
        out.append(r)
        stuck = stuck + 1 if me["x"] == before else 0

    if not me["dead"] and not st["over"]:
        shot = _bot_attack(st, grid, me, target)
        if shot:
            out.append({"attack": shot})
    _check_over(st)
    return out


def _bot_aim(grid, me, target):
    """หามุมกับแรงที่ยิงแล้วตกใกล้เป้าที่สุด — ลองยิงจริงหลายชุดแล้วเลือกอันที่ดีที่สุด

    ใช้ฟิสิกส์ตัวเดียวกับผู้เล่น ไม่ได้คำนวณสูตรวิถีแยก บอทจึงพลาดได้เหมือนคนจริง
    """
    d = 1 if target["x"] > me["x"] else -1
    best = None
    for ang in (25, 35, 45, 55, 65):
        for pw in (35, 50, 65, 80, 95):
            aim = ang if d > 0 else 180 - ang
            r = physics.shoot(grid, me["x"], me["y"], aim, pw)
            if not r["hit"]:
                continue
            miss = abs(r["x"] - target["x"]) + abs(r["y"] - target["y"]) * .5
            if best is None or miss < best[0]:
                best = (miss, ang, pw, d)
    return best


def _bot_attack(st, grid, me, target):
    """🤖 บอทเลือกสกิลเอง — ใกล้ก็ฟัน ไกลก็ยิง เลือดน้อยก็ฮีล"""
    if me.get("buffs", {}).get("emp"):
        return None                      # โดน EMP ก็ทำได้แค่เดินเหมือนคนจริง

    kit = weapons.kit_for((me.get("look") or {}).get("cls"))
    bag = [k for k, n in (me.get("bag") or {}).items() if n > 0 and k in weapons.ARTIFACTS]
    ready = [k for k in kit + bag if int(me.get("cd", {}).get(k, 0)) <= 0]
    if not ready:
        return None
    gap = abs(target["x"] - me["x"])

    # เลือดน้อยแล้วมีฮีล = ฮีลก่อน
    if me["hp"] <= me["max_hp"] * .4 and "heal" in ready:
        pick, aim = "heal", None
    else:
        def kind(k):
            return weapons.spec(k)["kind"]

        melee = [k for k in ready
                 if kind(k) == "melee" and gap <= weapons.spec(k)["reach"]]
        shots = [k for k in ready if kind(k) in ("lob", "beam")]
        buff = [k for k in ready if kind(k) == "self" and weapons.spec(k).get("buff")]
        if melee:
            pick, aim = max(melee, key=lambda k: weapons.spec(k)["dmg"]
                            * weapons.spec(k).get("times", 1)), None
        elif shots:
            aim = _bot_aim(grid, me, target)
            if not aim:
                return None
            pick = max(shots, key=lambda k: weapons.spec(k)["dmg"])
        elif buff:
            pick, aim = buff[0], None
        else:
            return None

    if aim:
        me["face"] = aim[3]
    elif weapons.spec(pick)["kind"] == "melee":
        me["face"] = 1 if target["x"] > me["x"] else -1

    r = _use_skill(st, grid, me, pick,
                   aim[1] if aim else None, aim[2] if aim else 70)
    if pick in weapons.ARTIFACTS:              # ของใช้แล้วหมดเหมือนคนจริง
        me["bag"][pick] -= 1
        if me["bag"][pick] <= 0:
            me["bag"].pop(pick, None)
    cd = weapons.spec(pick)["cooldown"]
    if cd:
        me.setdefault("cd", {})[pick] = cd + 1
    return r


def end_turn(uid, auto=False):
    """จบเทิร์น — สลับไปคนถัดไป ถ้าตาถัดไปเป็นบอทก็ให้บอทเดินเลยในคำขอเดียวกัน

    ทำให้จบในคำขอเดียวเพราะไม่งั้นเบราว์เซอร์ต้องคอยถามซ้ำว่า "บอทเดินยัง"
    """
    st = load(uid)
    if not st:
        return False, {"error": "ยังไม่ได้เริ่มแมตช์"}
    if st["over"]:
        return False, {"error": "แมตช์นี้จบแล้ว"}
    if auto and time_left(st) > 0:
        return True, view(uid, st)            # ยังไม่หมดเวลา ไม่ต้องทำอะไร

    _pass_turn(st)
    bot_moves = []
    for _ in range(len(st["fighters"])):      # ไล่ให้บอททุกตัวเดินจนกว่าจะถึงตาคนจริง
        if st["over"] or not _fighter(st)["bot"]:
            break
        bot_moves += _bot_turn(st)
        _pass_turn(st)
    save(uid, st)
    return True, {"bot_moves": bot_moves} | view(uid, st)


SURRENDER_CRATER = 26


def surrender(uid):
    """🏳️ ยอมแพ้ — ระเบิดตัวเองทิ้งตามธรรมเนียมเกมแนวนี้ แล้วจบแมตช์

    ไม่ทำดาเมจใส่คู่ต่อสู้ (radius 0) แค่เจาะหลุมกับเก็บตัวเองออกจากสนาม
    """
    st = load(uid)
    if not st:
        return False, {"error": "ยังไม่ได้เริ่มแมตช์"}
    if st["over"]:
        return False, {"error": "แมตช์นี้จบแล้ว"}
    me = next((f for f in st["fighters"] if not f["bot"]), None)
    if not me or me["dead"]:
        return False, {"error": "ตัวละครของคุณตกรอบไปแล้ว"}

    st["log"].append(f"🏳️ {me['name']} ยอมแพ้ — ระเบิดตัวเองทิ้ง!")
    blast = _explode(st, _grid(st), me["x"], me["y"] - terrain.CH_H // 2,
                     0, 0, SURRENDER_CRATER, "")
    me["hp"], me["dead"] = 0, True
    _check_over(st)
    save(uid, st)
    return True, {"surrender": {"x": me["x"], "y": me["y"], "blast": blast}} | view(uid, st)


def standings(st):
    """อันดับตอนจบ — รอดก่อน แล้วค่อยดูว่าใครสร้างความเสียหายได้มากกว่ากัน"""
    order = sorted(st["fighters"],
                   key=lambda f: (f["dead"], -int(f.get("dealt", 0)), -f["hp"]))
    return [{"rank": i + 1, "name": f["name"], "bot": f["bot"], "dead": f["dead"],
             "hp": max(0, f["hp"]), "max_hp": f["max_hp"],
             "dealt": int(f.get("dealt", 0)), "kills": int(f.get("kills", 0))}
            for i, f in enumerate(order)]


def _check_over(st):
    alive = [f for f in st["fighters"] if not f["dead"]]
    if len(alive) <= 1:
        st["over"] = True
        st["winner"] = alive[0]["name"] if alive else ""


def view(uid, st=None):
    """สถานะที่ส่งขึ้นเว็บได้ — 🔒 คัดพิกัดกับดักออกเสมอ ส่งแค่จำนวนที่ยังเหลือ"""
    st = st or load(uid)
    if not st:
        return {"active": False}
    return {
        "active": True,
        "seed": st["seed"], "continent": st["continent"],
        "continent_label": st["continent_label"],
        "w": terrain.W, "h": terrain.H, "water": terrain.WATER,
        "terrain": st["terrain"],
        "props": [p for p in st["props"] if p["kind"] != "trap"],
        "traps": sum(1 for p in st["props"] if p["kind"] == "trap"),
        "turn": st["turn"], "round": st["round"], "moves": st["moves"],
        "move_budget": MOVE_BUDGET, "over": st["over"], "winner": st.get("winner", ""),
        "time_left": time_left(st), "turn_seconds": TURN_SECONDS,
        "standings": standings(st),
        "drops": st.get("drops", []),
        "rounds": st["round"],
        "log": st["log"][-6:],
        "fighters": [{k: v for k, v in f.items() if k != "look"} | {"look": f["look"]}
                     for f in st["fighters"]],
        "skills": weapons.view((_fighter(st).get("look") or {}).get("cls"),
                               _fighter(st).get("cd")),
        "items": weapons.items_view(_fighter(st).get("bag")),
        "buff_names": {k: v["name"] for k, v in weapons.BUFFS.items()},
    }
