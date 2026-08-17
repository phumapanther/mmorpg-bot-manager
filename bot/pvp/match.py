"""🪱 แมตช์สนามรบผลัดเทิร์น — สถานะเกมที่กำลังเล่นอยู่

เก็บใน web.db เพราะบอทดิสคอร์ดไม่เกี่ยวกับหมวด PVP เลย (เล่นบนเว็บอย่างเดียว)
หนึ่งคนมีได้แมตช์เดียว — กด "ซ้อมกับบอท" ใหม่คือทิ้งของเดิม

⚠️ ตำแหน่งทุกตัวและพื้นทุกพิกเซลอยู่ฝั่งนี้เท่านั้น เบราว์เซอร์ส่งมาแค่ปุ่มที่กด
   ถ้าเชื่อพิกัดที่เบราว์เซอร์ส่งมา เปิด devtools แล้วเทเลพอร์ตไปยืนหลังศัตรูได้ทันที

🔒 กับดักส่งไปให้เบราว์เซอร์ไม่ได้จนกว่าจะเหยียบโดน — view() คัดออกให้แล้ว
"""
import json
import random
import time

from license_server import web_db

from bot.pvp import physics, terrain

MOVE_BUDGET = 60         # ก้าวได้กี่ก้าวต่อหนึ่งเทิร์น
TURN_SECONDS = 60        # หมดเวลาเทิร์นแล้วสลับให้เอง (ปิดจอหนีไม่ได้ ทั้งห้องจะได้ไม่ค้าง)
BOT_REACH = 26           # บอทเดินเข้าหาจนใกล้เท่านี้แล้วพอ
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
    spots = terrain.spawns(grid, 2, prng, avoid=props)
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
             "x": spots[0][0], "y": spots[0][1], "look": look, "dead": False},
            {"name": "🤖 บอท", "bot": True, "hp": 100, "max_hp": 100, "face": -1,
             "x": spots[1][0], "y": spots[1][1], "look": bot_look, "dead": False},
        ],
    }
    return save(uid, st)


def _hurt(st, f, dmg, why):
    f["hp"] = max(0, f["hp"] - int(dmg))
    st["log"].append(f"{f['name']} {why} -{int(dmg)} HP")
    if f["hp"] <= 0:
        f["dead"] = True
        st["log"].append(f"☠️ {f['name']} ตกรอบ!")


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


def _open_chests(st, f):
    """เดินทับหีบ = เปิดเลย (ของที่ได้จะต่อกับระบบไอเทมตอนทำเฟสอาวุธ)"""
    got = []
    for p in list(st["props"]):
        if p["kind"] != "chest" or abs(p["x"] - f["x"]) > 8 or abs(p["y"] - f["y"]) > 12:
            continue
        st["props"].remove(p)
        st["log"].append(f"🎁 {f['name']} เปิดหีบสมบัติ!")
        got.append({"x": p["x"], "y": p["y"]})
    return got


def move(uid, action, direction=1, steps=1):
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
        r = physics.jump(grid, f["x"], f["y"], direction)
    elif action == "walk":
        steps = max(1, min(int(steps), st["moves"]))
        if st["moves"] <= 0:
            return False, {"error": "แรงเดินหมดแล้ว — จบเทิร์นได้เลย"}
        r = physics.walk(grid, f["x"], f["y"], direction, steps)
        st["moves"] -= max(len(r["path"]), 1)
    else:
        return False, {"error": "ไม่รู้จักท่านี้"}

    f["x"], f["y"] = r["x"], r["y"]
    if r["drowned"]:
        _drown(st, f)
    else:
        dmg = physics.fall_damage(r["fell"])
        if dmg:
            _hurt(st, f, dmg, "ตกจากที่สูง")

    traps = [] if f["dead"] else _spring_traps(st, f)     # กับดักที่เพิ่งเหยียบโดน
    chests = [] if f["dead"] else _open_chests(st, f)     # หีบที่เพิ่งเปิด
    _check_over(st)
    save(uid, st)
    return True, {"move": r, "sprung": traps, "opened": chests} | view(uid, st)


def time_left(st):
    """เหลือเวลาในเทิร์นนี้กี่วินาที — เซิร์ฟเวอร์เป็นคนนับ ไม่ใช่นาฬิกาในเบราว์เซอร์"""
    if st.get("over"):
        return 0
    return max(0, int(TURN_SECONDS - (time.time() - st.get("turn_started", 0))))


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
    st["moves"] = MOVE_BUDGET
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
            dmg = physics.fall_damage(r["fell"])
            if dmg:
                _hurt(st, me, dmg, "ตกจากที่สูง")
        if not me["dead"]:
            _spring_traps(st, me)
            _open_chests(st, me)
        out.append(r)
        stuck = stuck + 1 if me["x"] == before else 0

    _check_over(st)
    return out


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
        "log": st["log"][-6:],
        "fighters": [{k: v for k, v in f.items() if k != "look"} | {"look": f["look"]}
                     for f in st["fighters"]],
    }
