"""🎪 ห้องเล่นหลายคน — ชวนเพื่อนมาลงสนามเดียวกันได้สูงสุด 6 คน

เจ้าของเกมเคาะ (08-28): "ทำโหมด PVP ที่สามารถชวนผู้เล่นมาเล่นได้สูงสุด 6 คน
โดยสามารถแบ่งทีมได้แบบ 2-2-2 หรือ 3-3 ได้"

⚠️ หัวใจของไฟล์นี้: **สถานะแมตช์มีก้อนเดียว ใช้ร่วมกันทุกคนในห้อง**
   ของเดิมเก็บแมตช์ต่อคน (ตาราง worms_matches มี user_id เป็นคีย์) ซึ่งใช้กับ
   การซ้อมกับบอทได้ เพราะแต่ละคนมีสนามของตัวเอง
   พอเล่นหลายคนต้องเห็นสนามเดียวกัน จึงเพิ่ม "ห้อง" ที่ถือสถานะไว้ก้อนเดียว
   แล้วให้ "ที่นั่ง" ชี้ว่าใครอยู่ห้องไหน

   match.load()/save() จะถามที่นี่ก่อนเสมอ — อยู่ในห้องก็อ่าน/เขียนของห้อง
   ไม่ได้อยู่ก็ใช้ทางเดิม (ซ้อมกับบอท) โค้ดเดิมทุกบรรทัดจึงทำงานเหมือนเดิม

🔒 กติกาเหล็กเดิมยังอยู่ครบ: เบราว์เซอร์ส่งมาแค่ "ปุ่มที่กด"
   ตำแหน่งทุกตัวยังตัดสินที่เซิร์ฟเวอร์ และตอนนี้ต้องเช็คเพิ่มว่า
   **คนที่ส่งคำสั่งมาเป็นเจ้าของตาปัจจุบันจริงไหม** ไม่งั้นคนอื่นสั่งแทนกันได้
"""
import json
import random
import string
import time

from license_server import web_db

MAX_SEATS = 6            # เจ้าของเกมเคาะ: สูงสุด 6 คน
ROOM_TTL = 3 * 3600      # ห้องที่ทิ้งไว้เกินนี้ = ล้างทิ้ง
TEAM_PLANS = {           # แผนแบ่งทีมที่เลือกได้ — จำนวนคนต้องลงตัวพอดี
    "ffa": {"name": "🔥 ตัวใครตัวมัน", "teams": 0},
    "3v3": {"name": "⚔️ 3 ต่อ 3", "teams": 2, "size": 3},
    "2v2v2": {"name": "🎲 2-2-2", "teams": 3, "size": 2},
}
TEAM_NAME = ["🔴 ทีมแดง", "🔵 ทีมน้ำเงิน", "🟢 ทีมเขียว", "🟡 ทีมเหลือง",
             "🟣 ทีมม่วง", "🟠 ทีมส้ม"]

_SCHEMA = """
CREATE TABLE IF NOT EXISTS worms_rooms (
    room_id    TEXT PRIMARY KEY,
    state      TEXT NOT NULL,
    updated_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS worms_seats (
    user_id    TEXT PRIMARY KEY,
    room_id    TEXT NOT NULL,
    updated_at REAL NOT NULL
);
"""


def _conn():
    conn = web_db.connect()
    conn.executescript(_SCHEMA)
    return conn


def _sweep(conn):
    old = time.time() - ROOM_TTL
    conn.execute("DELETE FROM worms_rooms WHERE updated_at < ?", (old,))
    conn.execute("DELETE FROM worms_seats WHERE updated_at < ?", (old,))


def new_code():
    """รหัสห้องสั้น ๆ พิมพ์ตามกันได้ — ตัดตัวที่อ่านสับสน (0/O · 1/I) ออก"""
    pool = "".join(c for c in string.ascii_uppercase + string.digits if c not in "O0I1")
    return "".join(random.choice(pool) for _ in range(5))


def room_of(uid):
    """ตอนนี้อยู่ห้องไหน — None ถ้าไม่ได้อยู่ห้องไหนเลย"""
    with _conn() as conn:
        _sweep(conn)
        row = conn.execute("SELECT room_id FROM worms_seats WHERE user_id=?",
                           (str(uid),)).fetchone()
    return row["room_id"] if row else None


def load(room_id):
    with _conn() as conn:
        row = conn.execute("SELECT state FROM worms_rooms WHERE room_id=?",
                           (str(room_id),)).fetchone()
    return json.loads(row["state"]) if row else None


def save(room_id, st):
    st["updated_at"] = time.time()
    with _conn() as conn:
        conn.execute("INSERT INTO worms_rooms(room_id, state, updated_at) VALUES (?,?,?) "
                     "ON CONFLICT(room_id) DO UPDATE SET state=excluded.state, "
                     "updated_at=excluded.updated_at",
                     (str(room_id), json.dumps(st), st["updated_at"]))
        conn.execute("UPDATE worms_seats SET updated_at=? WHERE room_id=?",
                     (st["updated_at"], str(room_id)))
    return st


def _sit(conn, uid, room_id):
    conn.execute("INSERT INTO worms_seats(user_id, room_id, updated_at) VALUES (?,?,?) "
                 "ON CONFLICT(user_id) DO UPDATE SET room_id=excluded.room_id, "
                 "updated_at=excluded.updated_at",
                 (str(uid), str(room_id), time.time()))


def create(uid, name, look):
    """เปิดห้องใหม่ — คนเปิดเป็นหัวห้องและนั่งที่แรกทันที"""
    leave(uid)
    code = new_code()
    st = {
        "room": code, "host": str(uid), "plan": "ffa", "started": False,
        "seats": [_seat(uid, name, look, 0)],
        "opened_at": time.time(),
    }
    with _conn() as conn:
        conn.execute("INSERT INTO worms_rooms(room_id, state, updated_at) VALUES (?,?,?)",
                     (code, json.dumps(st), time.time()))
        _sit(conn, uid, code)
    return st


def _seat(uid, name, look, team):
    return {"uid": str(uid), "name": str(name or "ผู้เล่น"), "look": look or {},
            "team": int(team), "ready": False}


def join(uid, code, name, look):
    """เข้าห้องด้วยรหัส — คืน (ok, ห้อง|ข้อความผิดพลาด)"""
    code = str(code or "").strip().upper()
    st = load(code)
    if not st:
        return False, {"error": "❌ ไม่มีห้องรหัสนี้ — เช็ครหัสอีกทีนะ"}
    if st.get("started"):
        return False, {"error": "⏳ ห้องนี้เริ่มเล่นไปแล้ว รอรอบหน้านะ"}
    if any(s["uid"] == str(uid) for s in st["seats"]):
        with _conn() as conn:
            _sit(conn, uid, code)
        return True, st                       # อยู่แล้วก็แค่กลับเข้ามาดู
    if len(st["seats"]) >= MAX_SEATS:
        return False, {"error": f"🚪 ห้องเต็มแล้ว (สูงสุด {MAX_SEATS} คน)"}
    leave(uid)
    st["seats"].append(_seat(uid, name, look, len(st["seats"]) % 2))
    save(code, st)
    with _conn() as conn:
        _sit(conn, uid, code)
    return True, st


def leave(uid):
    """ออกจากห้อง — หัวห้องออกก็ยกให้คนถัดไป ไม่มีคนเหลือก็ปิดห้อง"""
    code = room_of(uid)
    if not code:
        return None
    st = load(code)
    with _conn() as conn:
        conn.execute("DELETE FROM worms_seats WHERE user_id=?", (str(uid),))
    if not st:
        return None
    st["seats"] = [s for s in st["seats"] if s["uid"] != str(uid)]
    if not st["seats"]:
        with _conn() as conn:
            conn.execute("DELETE FROM worms_rooms WHERE room_id=?", (code,))
        return None
    if st["host"] == str(uid):
        st["host"] = st["seats"][0]["uid"]     # หัวห้องออก = ยกให้คนถัดไป
    return save(code, st)


def set_plan(uid, plan):
    """หัวห้องเลือกแผนแบ่งทีม"""
    code = room_of(uid)
    st = load(code) if code else None
    if not st:
        return False, {"error": "ยังไม่ได้อยู่ห้องไหน"}
    if st["host"] != str(uid):
        return False, {"error": "เฉพาะหัวห้องเท่านั้นที่เลือกแผนทีมได้"}
    if plan not in TEAM_PLANS:
        return False, {"error": "ไม่รู้จักแผนทีมนี้"}
    st["plan"] = plan
    _rebalance(st)
    return True, save(code, st)


def set_team(uid, team):
    """ย้ายทีมตัวเอง — แผนตัวใครตัวมันย้ายไม่ได้ (ไม่มีทีม)"""
    code = room_of(uid)
    st = load(code) if code else None
    if not st:
        return False, {"error": "ยังไม่ได้อยู่ห้องไหน"}
    plan = TEAM_PLANS[st["plan"]]
    if not plan["teams"]:
        return False, {"error": "แผนนี้เป็นตัวใครตัวมัน ไม่มีทีมให้ย้าย"}
    team = int(team)
    if not 0 <= team < plan["teams"]:
        return False, {"error": "ไม่มีทีมนี้ในแผนที่เลือกไว้"}
    mine = next((s for s in st["seats"] if s["uid"] == str(uid)), None)
    if not mine:
        return False, {"error": "ไม่พบที่นั่งของคุณ"}
    if sum(1 for s in st["seats"] if s["team"] == team) >= plan["size"] \
            and mine["team"] != team:
        return False, {"error": f"ทีมนี้เต็มแล้ว (ทีมละ {plan['size']} คน)"}
    mine["team"] = team
    return True, save(code, st)


def _rebalance(st):
    """เกลี่ยคนลงทีมใหม่ให้เข้ากับแผนที่เพิ่งเลือก"""
    plan = TEAM_PLANS[st["plan"]]
    for i, s in enumerate(st["seats"]):
        s["team"] = 0 if not plan["teams"] else i % plan["teams"]


def plan_ready(st):
    """แผนนี้เริ่มได้หรือยัง — คืน (ได้ไหม, เหตุผลถ้าไม่ได้)"""
    plan = TEAM_PLANS[st["plan"]]
    n = len(st["seats"])
    if n < 2:
        return False, "ต้องมีอย่างน้อย 2 คนถึงจะเริ่มได้"
    if not plan["teams"]:
        return True, ""
    need = plan["teams"] * plan["size"]
    if n != need:
        return False, f"แผนนี้ต้องมี {need} คนพอดี (ตอนนี้ {n} คน)"
    for t in range(plan["teams"]):
        got = sum(1 for s in st["seats"] if s["team"] == t)
        if got != plan["size"]:
            return False, f"{TEAM_NAME[t]} มี {got} คน (ต้องเป็น {plan['size']})"
    return True, ""


def view(uid):
    """ห้องที่ตัวเองอยู่ พร้อมแสดงผลบนเว็บ"""
    code = room_of(uid)
    st = load(code) if code else None
    if not st:
        return {"in_room": False, "plans": _plans_view()}
    ok, why = plan_ready(st)
    plan = TEAM_PLANS[st["plan"]]
    return {
        "in_room": True, "code": st["room"], "host": st["host"] == str(uid),
        "started": bool(st.get("started")),
        "plan": st["plan"], "plans": _plans_view(),
        "teams": plan["teams"], "team_names": TEAM_NAME[:max(1, plan["teams"])],
        "seats": [{"uid": s["uid"], "name": s["name"], "team": s["team"],
                   "you": s["uid"] == str(uid), "host": s["uid"] == st["host"]}
                  for s in st["seats"]],
        "can_start": ok, "why": why, "max": MAX_SEATS,
    }


def _plans_view():
    return [{"key": k, "name": v["name"],
             "need": v["teams"] * v.get("size", 0) if v["teams"] else 0}
            for k, v in TEAM_PLANS.items()]
