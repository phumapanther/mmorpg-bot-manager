"""🎪 ล็อบบี้กลาง — ห้องเล่นหลายคนที่ทุกเกมใช้ร่วมกันได้

เจ้าของเกมเคาะ (09-02): "อยากได้หน้าล็อบบี้แบบนี้เป็นมาตรฐานสำหรับเกมอื่น ๆ ด้วย"

แยกจาก bot/pvp/rooms.py เดิมตรงที่:
  - ผูกกับ "เกม" ด้วย จึงอยู่ได้หลายห้องพร้อมกัน (UNO ห้องหนึ่ง สนามรบอีกห้อง)
  - ไม่รู้จักทีม/หน้าตาตัวละคร/เงินเดิมพัน — ของพวกนั้นอยู่ใน extra ของแต่ละเกม

⚠️ ชั้นนี้ไม่ตัดสินกติกาเกมใด ๆ ทั้งสิ้น หน้าที่มีแค่ "ใครนั่งห้องไหน"
   เกมเอาไปต่อยอดเองผ่าน extra กับ seat ที่ส่งเข้ามา
"""
import json
import random
import string
import time

from license_server import web_db

MAX_SEATS = 6              # เท่าของเดิมใน rooms.py — เจ้าของเกมเคาะไว้ตั้งแต่สนามรบ
ROOM_TTL = 3 * 3600        # ห้องที่ทิ้งไว้เกินนี้ = ล้างทิ้ง

_SCHEMA = """
CREATE TABLE IF NOT EXISTS lobby_rooms (
    room_id    TEXT PRIMARY KEY,
    game       TEXT NOT NULL,
    state      TEXT NOT NULL,
    updated_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS lobby_seats (
    user_id    TEXT NOT NULL,
    game       TEXT NOT NULL,
    room_id    TEXT NOT NULL,
    updated_at REAL NOT NULL,
    PRIMARY KEY (user_id, game)
);
"""


def _conn():
    conn = web_db.connect()
    conn.executescript(_SCHEMA)
    return conn


def _sweep(conn):
    """ล้างห้องร้าง — เรียกทุกครั้งที่ถามว่าใครอยู่ห้องไหน"""
    old = time.time() - ROOM_TTL
    conn.execute("DELETE FROM lobby_rooms WHERE updated_at < ?", (old,))
    conn.execute("DELETE FROM lobby_seats WHERE updated_at < ?", (old,))


def new_code():
    """รหัสห้องสั้น ๆ พิมพ์ตามกันได้ — ตัดตัวที่อ่านสับสน (0/O · 1/I) ออก"""
    pool = "".join(c for c in string.ascii_uppercase + string.digits if c not in "O0I1")
    return "".join(random.choice(pool) for _ in range(5))


def room_of(game, uid):
    """ตอนนี้อยู่ห้องไหนของเกมนี้ — None ถ้าไม่ได้อยู่"""
    with _conn() as conn:
        _sweep(conn)
        row = conn.execute("SELECT room_id FROM lobby_seats WHERE user_id=? AND game=?",
                           (str(uid), str(game))).fetchone()
    return row["room_id"] if row else None


def load(room_id):
    with _conn() as conn:
        row = conn.execute("SELECT state FROM lobby_rooms WHERE room_id=?",
                           (str(room_id),)).fetchone()
    return json.loads(row["state"]) if row else None


def save(room_id, st):
    st["updated_at"] = time.time()
    with _conn() as conn:
        conn.execute("INSERT INTO lobby_rooms(room_id, game, state, updated_at) "
                     "VALUES (?,?,?,?) ON CONFLICT(room_id) DO UPDATE SET "
                     "state=excluded.state, updated_at=excluded.updated_at",
                     (str(room_id), str(st.get("game", "")), json.dumps(st),
                      st["updated_at"]))
        conn.execute("UPDATE lobby_seats SET updated_at=? WHERE room_id=?",
                     (st["updated_at"], str(room_id)))
    return st


def _sit(conn, game, uid, room_id):
    conn.execute("INSERT INTO lobby_seats(user_id, game, room_id, updated_at) "
                 "VALUES (?,?,?,?) ON CONFLICT(user_id, game) DO UPDATE SET "
                 "room_id=excluded.room_id, updated_at=excluded.updated_at",
                 (str(uid), str(game), str(room_id), time.time()))


def _fill(seat, uid):
    """เติมคีย์ที่ชั้นกลางต้องใช้ — คีย์อื่นเกมใส่อะไรมาก็เก็บไว้ครบ"""
    out = dict(seat or {})
    out["uid"] = str(uid)
    out["name"] = str(out.get("name") or "ผู้เล่น")
    return out


def create(game, uid, seat, extra=None):
    """เปิดห้องใหม่ — คนเปิดเป็นหัวห้องและนั่งที่แรกทันที"""
    leave(game, uid)
    code = new_code()
    st = {
        "room": code, "game": str(game), "host": str(uid), "started": False,
        "seats": [_fill(seat, uid)],
        "extra": dict(extra or {}),
        "opened_at": time.time(),
    }
    with _conn() as conn:
        conn.execute("INSERT INTO lobby_rooms(room_id, game, state, updated_at) "
                     "VALUES (?,?,?,?)",
                     (code, str(game), json.dumps(st), time.time()))
        _sit(conn, game, uid, code)
    return st


def join(game, uid, code, seat):
    """เข้าห้องด้วยรหัส — คืน (ok, ห้อง|ข้อความผิดพลาด)"""
    code = str(code or "").strip().upper()
    st = load(code)
    if not st or st.get("game") != str(game):
        return False, {"error": "❌ ไม่มีห้องรหัสนี้ — เช็ครหัสอีกทีนะ"}
    if st.get("started"):
        return False, {"error": "⏳ ห้องนี้เริ่มเล่นไปแล้ว รอรอบหน้านะ"}
    if any(s["uid"] == str(uid) for s in st["seats"]):
        with _conn() as conn:
            _sit(conn, game, uid, code)
        return True, st                       # อยู่แล้วก็แค่กลับเข้ามาดู
    if len(st["seats"]) >= MAX_SEATS:
        return False, {"error": f"🚪 ห้องเต็มแล้ว (สูงสุด {MAX_SEATS} คน)"}
    leave(game, uid)
    st["seats"].append(_fill(seat, uid))
    save(code, st)
    with _conn() as conn:
        _sit(conn, game, uid, code)
    return True, st


def leave(game, uid):
    """ออกจากห้อง — หัวห้องออกก็ยกให้คนถัดไป ไม่มีคนเหลือก็ปิดห้อง

    คืนสถานะห้องหลังออก (None = ห้องหายไปแล้ว) ให้เกมเอาไปจัดการต่อ
    เช่น UNO เอาไปคืนเงิน/ยกกองกลางให้คนที่เหลือ
    """
    code = room_of(game, uid)
    if not code:
        return None
    st = load(code)
    with _conn() as conn:
        conn.execute("DELETE FROM lobby_seats WHERE user_id=? AND game=?",
                     (str(uid), str(game)))
    if not st:
        return None
    st["seats"] = [s for s in st["seats"] if s["uid"] != str(uid)]
    if not st["seats"]:
        with _conn() as conn:
            conn.execute("DELETE FROM lobby_rooms WHERE room_id=?", (code,))
        return None
    if st["host"] == str(uid):
        st["host"] = st["seats"][0]["uid"]     # หัวห้องออก = ยกให้คนถัดไป
    return save(code, st)


def view(game, uid):
    """ห้องที่ตัวเองอยู่ พร้อมแสดงผลบนเว็บ

    🔒 นี่คือประตูเดียวก่อนส่งขึ้นเบราว์เซอร์ — เกมที่มีของลับ (เช่นไพ่ในมือ)
       ต้องต่อยอดจากตรงนี้ ห้ามส่งก้อน st ดิบ ๆ ออกไป
    """
    code = room_of(game, uid)
    st = load(code) if code else None
    if not st:
        return {"in_room": False}
    return {
        "in_room": True, "code": st["room"], "game": st["game"],
        "host": st["host"] == str(uid),
        "started": bool(st.get("started")),
        "seats": [{"uid": s["uid"], "name": s["name"],
                   "you": s["uid"] == str(uid), "host": s["uid"] == st["host"]}
                  for s in st["seats"]],
        "max": MAX_SEATS,
    }
