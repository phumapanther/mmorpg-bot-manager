# ล็อบบี้กลาง + UNO เดิมพัน — แผนลงมือ

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** สร้างระบบล็อบบี้กลางที่ทุกเกมใช้ร่วมกันได้ แล้วย้ายสนามรบมาใช้ พร้อมเพิ่ม UNO เดิมพันทองเล่นกับเพื่อน

**Architecture:** แยก 2 ชั้น — `bot/lobby.py` ถือเรื่องห้อง/รหัส/ที่นั่งที่ทุกเกมเหมือนกัน ส่วนของเฉพาะเกม (ทีมของสนามรบ · เงินเดิมพันของ UNO) อยู่ในก้อน `extra` ที่ชั้นกลางไม่แตะ `rooms.py` เปลี่ยนเป็นเปลือกบางเรียกชั้นกลาง โดยคงชื่อ public เดิมครบทุกตัว เพื่อให้ `match.py` และ `web_api.py` ไม่ต้องแก้

**Tech Stack:** Python 3.12 · SQLite (`license_server/web_db.py`) · FastAPI · pytest · vanilla JS + Canvas 2D

**Spec:** `docs/superpowers/specs/2026-09-02-lobby-uno-betting-design.md`

## Global Constraints

- **ภาษาไทยทั้งหมด** — คอมเมนต์ · ข้อความ error · ชื่อเทส · ข้อความ commit
- **เซิร์ฟเวอร์ตัดสินทุกอย่าง** เบราว์เซอร์ส่งมาแค่ "กดปุ่มไหน" ห้ามให้เบราว์เซอร์ตัดสินกติกาหรือเงิน
- **`view(uid)` เป็นประตูเดียว** ก่อนส่งข้อมูลขึ้นเบราว์เซอร์ — ซ่อนด้วย CSS ไม่นับว่าซ่อน
- **ทองรวมในระบบต้องเท่าเดิมเป๊ะ** ทุกกรณี เงินย้ายมือ ไม่งอก ไม่หาย
- **โต๊ะเดิมพันต้องมีคนจริง 2 คนขึ้นไป** มีบอท → เดิมพันเป็น 0 อัตโนมัติ
- `MAX_SEATS = 6` · `ROOM_TTL = 3 * 3600` (ค่าเดิมจาก `rooms.py` ห้ามเปลี่ยน)
- รหัสห้อง 5 ตัว ตัด `O 0 I 1` ออก (ค่าเดิมจาก `new_code()`)
- **ทุกงานจบด้วย**: เขียนเทสให้แดงก่อน → แก้ → กลับด้านเทส (mutate โค้ดยืนยันเทสจับได้) → รันชุดเต็ม → commit
- รันเทส: `PYTHONIOENCODING=utf-8 python -m pytest <path> -q` (คอนโซล Windows เป็น cp874 ไม่ตั้งจะพัง)

---

## โครงสร้างไฟล์

| ไฟล์ | หน้าที่ | งานที่ |
|---|---|---|
| `bot/lobby.py` | ชั้นกลาง: ห้อง · รหัส · ที่นั่ง · กวาดห้องร้าง | 1 |
| `tests/test_lobby.py` | เทสชั้นกลาง | 1 |
| `bot/pvp/rooms.py` | เปลือกบาง: ทีมของสนามรบ + เรียกชั้นกลาง | 2 |
| `bot/cards/uno_room.py` | UNO เสียบล็อบบี้ + เงินเดิมพัน | 3 |
| `tests/test_uno_money.py` | เทสเงิน (สำคัญสุด) | 3 |
| `license_server/web_api.py` | API ล็อบบี้ + UNO หลายคน | 4 |
| `license_server/web_static/play.html` `uno.js` `play.js` `play.css` | หน้าล็อบบี้ + เลือกโหมด | 4 |
| `bot/cogs/lobby_invite.py` | DM คำเชิญ (ใช้ร่วมทุกเกม) | 5 |

---

# งานที่ 1: ชั้นกลาง `bot/lobby.py`

**ความเสี่ยง:** ไม่มี — ไฟล์ใหม่ล้วน ยังไม่แตะของเดิม

**Files:**
- Create: `bot/lobby.py`
- Test: `tests/test_lobby.py`

**Interfaces:**
- Consumes: `license_server.web_db.connect()` — คืน `sqlite3.Connection` ที่มี `row_factory = sqlite3.Row` แล้ว
- Produces (งานที่ 2-5 เรียกใช้):
  - `new_code() -> str` — รหัส 5 ตัว
  - `room_of(game: str, uid) -> str | None`
  - `load(room_id) -> dict | None`
  - `save(room_id, st: dict) -> dict`
  - `create(game, uid, seat: dict, extra: dict | None = None) -> dict`
  - `join(game, uid, code, seat: dict) -> tuple[bool, dict]`
  - `leave(game, uid) -> dict | None`
  - `view(game, uid) -> dict`
  - `MAX_SEATS = 6` · `ROOM_TTL = 10800`

รูปร่างของ `st` (สถานะห้อง) ที่ทุกงานใช้ร่วมกัน:
```python
{"room": "A7K2X", "game": "worms", "host": "123", "started": False,
 "seats": [{"uid": "123", "name": "ผู้เล่น", ...ของเกม}],
 "extra": {},                # เกมใส่อะไรก็ได้ ชั้นกลางไม่แตะ
 "opened_at": 1234.5, "updated_at": 1234.5}
```

`seat` ที่ส่งเข้า `create`/`join` ต้องมี `uid` กับ `name` เป็นอย่างน้อย ชั้นกลางเติม 2 คีย์นี้ให้เองถ้าไม่มี คีย์อื่นเกมใส่เพิ่มได้ตามใจ (สนามรบใส่ `look`/`team` · UNO ใส่ `bet_paid`)

- [ ] **Step 1: เขียนเทสให้แดงก่อน**

สร้าง `tests/test_lobby.py`:

```python
"""🎪 ล็อบบี้กลาง — ห้องที่ทุกเกมใช้ร่วมกันได้

เจ้าของเกมเคาะ (09-02): ทำระบบกลางก่อน แล้วย้ายทั้งสนามรบและ UNO มาใช้
"""
import pytest

from bot import lobby


@pytest.fixture(autouse=True)
def db(tmp_path, monkeypatch):
    """ฐานข้อมูลใหม่ทุกเทส — ไม่ให้ห้องจากเทสก่อนหน้าค้างมากวน"""
    import sqlite3

    from license_server import web_db

    path = tmp_path / "web.db"

    def _connect():
        conn = sqlite3.connect(str(path), timeout=5)
        conn.row_factory = sqlite3.Row
        conn.executescript(web_db._SCHEMA)
        return conn

    monkeypatch.setattr(web_db, "connect", _connect)
    yield


def _seat(uid, name="ผู้เล่น"):
    return {"uid": str(uid), "name": name}


def test_สร้างห้องแล้วได้รหัสกับที่นั่งแรก():
    st = lobby.create("worms", 1, _seat(1, "เอ"))
    assert len(st["room"]) == 5
    assert st["host"] == "1"
    assert st["game"] == "worms"
    assert [s["name"] for s in st["seats"]] == ["เอ"]
    assert st["started"] is False


def test_รหัสห้องไม่มีตัวที่อ่านสับสน():
    # 0/O และ 1/I พิมพ์ตามกันแล้วผิด — ตัดออกตั้งแต่ต้น
    for _ in range(200):
        assert not (set(lobby.new_code()) & set("O0I1"))


def test_เข้าห้องด้วยรหัสแล้วนั่งเพิ่ม():
    st = lobby.create("worms", 1, _seat(1, "เอ"))
    ok, got = lobby.join("worms", 2, st["room"], _seat(2, "บี"))
    assert ok
    assert [s["name"] for s in got["seats"]] == ["เอ", "บี"]


def test_รหัสผิดเข้าไม่ได้():
    ok, got = lobby.join("worms", 2, "ZZZZZ", _seat(2))
    assert not ok and "error" in got


def test_ห้องเต็มเข้าไม่ได้():
    st = lobby.create("worms", 1, _seat(1))
    for uid in range(2, lobby.MAX_SEATS + 1):
        assert lobby.join("worms", uid, st["room"], _seat(uid))[0]
    ok, got = lobby.join("worms", 99, st["room"], _seat(99))
    assert not ok and "เต็ม" in got["error"]


def test_เริ่มเล่นแล้วเข้าไม่ได้():
    st = lobby.create("worms", 1, _seat(1))
    st["started"] = True
    lobby.save(st["room"], st)
    ok, got = lobby.join("worms", 2, st["room"], _seat(2))
    assert not ok


def test_คนเดิมเข้าซ้ำไม่เพิ่มที่นั่ง():
    # เน็ตหลุดแล้วกดเข้าใหม่ ต้องกลับเข้าที่เดิม ไม่ใช่นั่งซ้ำสองที่
    st = lobby.create("worms", 1, _seat(1))
    lobby.join("worms", 2, st["room"], _seat(2))
    ok, got = lobby.join("worms", 2, st["room"], _seat(2))
    assert ok and len(got["seats"]) == 2


def test_ออกห้องแล้วที่นั่งหาย():
    st = lobby.create("worms", 1, _seat(1))
    lobby.join("worms", 2, st["room"], _seat(2))
    lobby.leave("worms", 2)
    assert len(lobby.load(st["room"])["seats"]) == 1
    assert lobby.room_of("worms", 2) is None


def test_หัวห้องออกยกให้คนถัดไป():
    st = lobby.create("worms", 1, _seat(1))
    lobby.join("worms", 2, st["room"], _seat(2))
    lobby.leave("worms", 1)
    assert lobby.load(st["room"])["host"] == "2"


def test_คนสุดท้ายออกห้องหายไปเลย():
    st = lobby.create("worms", 1, _seat(1))
    lobby.leave("worms", 1)
    assert lobby.load(st["room"]) is None


def test_คนเดียวอยู่ได้เกมละห้อง():
    """เล่น UNO อยู่แล้วเข้าห้องสนามรบพร้อมกันได้ — ของเดิมทำไม่ได้"""
    a = lobby.create("worms", 1, _seat(1))
    b = lobby.create("uno", 1, _seat(1))
    assert lobby.room_of("worms", 1) == a["room"]
    assert lobby.room_of("uno", 1) == b["room"]
    assert a["room"] != b["room"]


def test_ออกเกมหนึ่งไม่กระทบอีกเกม():
    lobby.create("worms", 1, _seat(1))
    b = lobby.create("uno", 1, _seat(1))
    lobby.leave("worms", 1)
    assert lobby.room_of("worms", 1) is None
    assert lobby.room_of("uno", 1) == b["room"]


def test_เข้าห้องเกมอื่นด้วยรหัสข้ามเกมไม่ได้():
    """รหัสห้อง UNO เอาไปกรอกในสนามรบไม่ได้ — กันเข้าผิดห้อง"""
    st = lobby.create("uno", 1, _seat(1))
    ok, got = lobby.join("worms", 2, st["room"], _seat(2))
    assert not ok


def test_สร้างห้องใหม่ทิ้งห้องเก่าของเกมเดียวกัน():
    a = lobby.create("worms", 1, _seat(1))
    b = lobby.create("worms", 1, _seat(1))
    assert a["room"] != b["room"]
    assert lobby.load(a["room"]) is None       # ห้องเก่าไม่มีคนแล้ว = หายไป
    assert lobby.room_of("worms", 1) == b["room"]


def test_extra_เก็บของเฉพาะเกมได้():
    st = lobby.create("uno", 1, _seat(1), {"bet": 1000})
    assert lobby.load(st["room"])["extra"]["bet"] == 1000


def test_ห้องร้างโดนกวาดทิ้ง(monkeypatch):
    import time as _t
    st = lobby.create("worms", 1, _seat(1))
    # แกล้งทำเป็นว่าเวลาผ่านไปเกินอายุห้อง
    monkeypatch.setattr(lobby.time, "time", lambda: _t.time() + lobby.ROOM_TTL + 10)
    assert lobby.room_of("worms", 1) is None


def test_view_ไม่อยู่ห้องไหน():
    got = lobby.view("worms", 1)
    assert got["in_room"] is False


def test_view_บอกว่าใครเป็นเราและใครเป็นหัวห้อง():
    st = lobby.create("worms", 1, _seat(1, "เอ"))
    lobby.join("worms", 2, st["room"], _seat(2, "บี"))
    got = lobby.view("worms", 2)
    assert got["in_room"] is True
    assert got["code"] == st["room"]
    assert got["host"] is False               # คนที่ 2 ไม่ใช่หัวห้อง
    me = [s for s in got["seats"] if s["you"]]
    assert len(me) == 1 and me[0]["name"] == "บี"
```

- [ ] **Step 2: รันเทสยืนยันว่าแดง**

Run: `PYTHONIOENCODING=utf-8 python -m pytest tests/test_lobby.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'bot.lobby'`

- [ ] **Step 3: เขียน `bot/lobby.py`**

```python
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
```

- [ ] **Step 4: รันเทสยืนยันว่าเขียว**

Run: `PYTHONIOENCODING=utf-8 python -m pytest tests/test_lobby.py -q`
Expected: PASS ทั้ง 18 ข้อ

- [ ] **Step 5: กลับด้านเทส — ยืนยันว่าเทสจับ bug จริงได้**

แก้โค้ดให้พังทีละจุด แล้วดูว่าเทสแดงไหม เสร็จแล้วคืนไฟล์เดิมทุกครั้ง:

```bash
cp bot/lobby.py /tmp/lobby.bak
```

| จุดที่แกล้งทำพัง | แก้เป็น | เทสที่ต้องแดง |
|---|---|---|
| `PRIMARY KEY (user_id, game)` | `PRIMARY KEY (user_id)` | `test_คนเดียวอยู่ได้เกมละห้อง` |
| `st.get("game") != str(game)` | ตัดเงื่อนไขนี้ออก | `test_เข้าห้องเกมอื่นด้วยรหัสข้ามเกมไม่ได้` |
| `if len(st["seats"]) >= MAX_SEATS` | `> MAX_SEATS` | `test_ห้องเต็มเข้าไม่ได้` |
| `st["host"] = st["seats"][0]["uid"]` | ลบบรรทัดนี้ | `test_หัวห้องออกยกให้คนถัดไป` |
| `_sweep(conn)` ใน `room_of` | ลบออก | `test_ห้องร้างโดนกวาดทิ้ง` |

ถ้าจุดไหนเทสไม่แดง = เทสอ่อนเกินไป **ต้องเขียนเทสเพิ่มให้จับได้ก่อนไปต่อ**

คืนไฟล์: `cp /tmp/lobby.bak bot/lobby.py`

- [ ] **Step 6: รันเทสชุดเต็ม**

Run: `PYTHONIOENCODING=utf-8 python -m pytest -q`
Expected: PASS ทั้งหมด (ฐานเดิม 2665 + 18 ใหม่ = 2683)
ใช้เวลา ~12 นาที รันเป็น background ได้

- [ ] **Step 7: Commit**

```bash
git add bot/lobby.py tests/test_lobby.py
git commit -m "feat(lobby): ชั้นกลางห้องเล่นหลายคน ใช้ร่วมได้ทุกเกม

แยกเรื่อง 'ห้อง/รหัส/ที่นั่ง' ที่ทุกเกมเหมือนกันออกมาเป็นชั้นกลาง
ของเฉพาะเกม (ทีม/เงินเดิมพัน) อยู่ใน extra ที่ชั้นนี้ไม่แตะ

ต่างจาก rooms.py เดิม: ผูกกับเกมด้วย จึงอยู่หลายห้องพร้อมกันได้
(เล่น UNO อยู่แล้วเข้าห้องสนามรบได้ ของเดิมทำไม่ได้)

เทส 18 ข้อ · กลับด้านเทส 5 จุดจับได้ครบ

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

# งานที่ 2: ย้าย `rooms.py` มาใช้ชั้นกลาง

**⚠️ ความเสี่ยงสูงสุดของทั้งแผน** — สนามรบยังไม่เคยเทสกับคนจริง (ต้องรอ 2 คน)

**เกณฑ์ตัดสิน:** เทสสนามรบเดิมทุกข้อต้องผ่านเท่าเดิมเป๊ะ **ถ้าไม่ผ่าน = ถอยกลับทันที** ห้ามแก้เทสให้ผ่าน

**Files:**
- Modify: `bot/pvp/rooms.py` (ทั้งไฟล์)
- ห้ามแก้: `bot/pvp/match.py` · `license_server/web_api.py` (ถ้าต้องแก้ = ทำผิดทาง)

**Interfaces:**
- Consumes: ทุกอย่างจากงานที่ 1
- Produces: **ชื่อ public เดิมครบทุกตัว** — นับจากโค้ดจริงที่เรียกอยู่:

| ใครเรียก | ห้ามเปลี่ยนชื่อ |
|---|---|
| `match.py` | `load` `save` `leave` `room_of` `plan_ready` `TEAM_NAME` `TEAM_PLANS` |
| `web_api.py` | `create` `join` `leave` `set_plan` `set_team` `view` |

รวม 11 ฟังก์ชัน: `new_code` `room_of` `load` `save` `create` `join` `leave` `set_plan` `set_team` `plan_ready` `view`
รวม 4 ค่าคงที่: `MAX_SEATS` `ROOM_TTL` `TEAM_NAME` `TEAM_PLANS`

**สำคัญ:** ลายเซ็นเดิมไม่มี `game` — `rooms.create(uid, name, look)` ไม่ใช่ `create(game, uid, ...)`
เปลือกต้องเติม `"worms"` ให้เอง

- [ ] **Step 1: จดผลเทสสนามรบก่อนแก้ (เส้นฐาน)**

```bash
PYTHONIOENCODING=utf-8 python -m pytest tests/ -q -k "worms or pvp or room" 2>&1 | tail -3
```

จดตัวเลขไว้ — หลังแก้ต้องได้เท่านี้เป๊ะ

- [ ] **Step 2: เขียนเทสยืนยันว่าชื่อเดิมอยู่ครบ**

เพิ่มท้าย `tests/test_lobby.py`:

```python
# ── ย้าย rooms.py มาใช้ชั้นกลางแล้วต้องไม่มีอะไรพัง ──

def test_rooms_ยังมีชื่อเดิมครบ():
    """match.py กับ web_api.py เรียกชื่อพวกนี้อยู่ — เปลี่ยนชื่อ = พังทันที"""
    from bot.pvp import rooms
    for name in ("new_code", "room_of", "load", "save", "create", "join",
                 "leave", "set_plan", "set_team", "plan_ready", "view"):
        assert callable(getattr(rooms, name, None)), f"หายไป: {name}"
    for name in ("MAX_SEATS", "ROOM_TTL", "TEAM_NAME", "TEAM_PLANS"):
        assert getattr(rooms, name, None) is not None, f"หายไป: {name}"


def test_rooms_ลายเซ็นเดิมไม่มี_game():
    """ของเดิมเรียก rooms.create(uid, name, look) — เปลือกต้องเติม worms ให้เอง"""
    import inspect
    from bot.pvp import rooms
    assert list(inspect.signature(rooms.create).parameters) == ["uid", "name", "look"]
    assert list(inspect.signature(rooms.leave).parameters) == ["uid"]
    assert list(inspect.signature(rooms.room_of).parameters) == ["uid"]


def test_rooms_ใช้ชั้นกลางจริง():
    from bot.pvp import rooms
    st = rooms.create(1, "เอ", {})
    assert lobby.load(st["room"])["game"] == "worms"


def test_rooms_ห้องสนามรบไม่ชนกับ_uno():
    from bot.pvp import rooms
    w = rooms.create(1, "เอ", {})
    u = lobby.create("uno", 1, {"uid": "1", "name": "เอ"})
    assert rooms.room_of(1) == w["room"]
    assert lobby.room_of("uno", 1) == u["room"]
```

- [ ] **Step 3: รันเทสใหม่ยืนยันว่าแดง**

Run: `PYTHONIOENCODING=utf-8 python -m pytest tests/test_lobby.py -q -k rooms`
Expected: FAIL — `test_rooms_ใช้ชั้นกลางจริง` แดง (ยังใช้ตาราง `worms_rooms` เดิม)

- [ ] **Step 4: แก้ `rooms.py` เป็นเปลือกบาง**

เก็บส่วนทีมไว้ทั้งหมด (`TEAM_PLANS` `TEAM_NAME` `_rebalance` `set_plan` `set_team` `plan_ready` `_plans_view`) เปลี่ยนเฉพาะส่วนห้องให้เรียกชั้นกลาง:

```python
"""🎪 ห้องสนามรบผลัดเทิร์น — เปลือกบางบน bot/lobby.py

เจ้าของเกมเคาะ (09-02): ย้ายมาใช้ล็อบบี้กลางที่ทุกเกมใช้ร่วมกัน

⚠️ ไฟล์นี้เก็บ "ชื่อฟังก์ชันเดิมครบทุกตัว" ไว้โดยตั้งใจ
   match.py กับ web_api.py เรียกอยู่ 13 จุด — เปลี่ยนชื่อเมื่อไหร่พังทันที
   เรื่องห้อง/รหัส/ที่นั่ง = ส่งต่อให้ lobby.py
   เรื่องทีม (2-2-2 / 3v3) = ยังอยู่ที่นี่ เพราะเป็นของสนามรบล้วน ๆ
"""
import json  # noqa: F401  (เผื่อโค้ดเดิมที่ import จากที่นี่)
import time

from bot import lobby

GAME = "worms"

MAX_SEATS = lobby.MAX_SEATS
ROOM_TTL = lobby.ROOM_TTL
TEAM_PLANS = {           # แผนแบ่งทีมที่เลือกได้ — จำนวนคนต้องลงตัวพอดี
    "ffa": {"name": "🔥 ตัวใครตัวมัน", "teams": 0},
    "3v3": {"name": "⚔️ 3 ต่อ 3", "teams": 2, "size": 3},
    "2v2v2": {"name": "🎲 2-2-2", "teams": 3, "size": 2},
}
TEAM_NAME = ["🔴 ทีมแดง", "🔵 ทีมน้ำเงิน", "🟢 ทีมเขียว", "🟡 ทีมเหลือง",
             "🟣 ทีมม่วง", "🟠 ทีมส้ม"]

new_code = lobby.new_code
load = lobby.load
save = lobby.save


def room_of(uid):
    return lobby.room_of(GAME, uid)


def _seat(uid, name, look, team):
    return {"uid": str(uid), "name": str(name or "ผู้เล่น"), "look": look or {},
            "team": int(team), "ready": False}


def create(uid, name, look):
    """เปิดห้องใหม่ — คนเปิดเป็นหัวห้องและนั่งที่แรกทันที"""
    st = lobby.create(GAME, uid, _seat(uid, name, look, 0))
    st["plan"] = "ffa"
    return lobby.save(st["room"], st)


def join(uid, code, name, look):
    """เข้าห้องด้วยรหัส — คืน (ok, ห้อง|ข้อความผิดพลาด)"""
    st = lobby.load(str(code or "").strip().upper())
    team = (len(st["seats"]) % 2) if st else 0
    ok, got = lobby.join(GAME, uid, code, _seat(uid, name, look, team))
    return ok, got


def leave(uid):
    """ออกจากห้อง — หัวห้องออกก็ยกให้คนถัดไป ไม่มีคนเหลือก็ปิดห้อง"""
    st = lobby.leave(GAME, uid)
    if st:
        _rebalance(st)
        return lobby.save(st["room"], st)
    return None
```

ส่วน `set_plan` `set_team` `plan_ready` `_rebalance` `_plans_view` **ก๊อปมาจากไฟล์เดิมทั้งดุ้น** เปลี่ยนแค่ `room_of(uid)` (ซึ่งตอนนี้เรียกชั้นกลางให้แล้ว)

`view(uid)` ก๊อปจากเดิมเช่นกัน แต่เปลี่ยนบรรทัดแรกเป็น:
```python
def view(uid):
    """ห้องที่ตัวเองอยู่ พร้อมแสดงผลบนเว็บ"""
    code = room_of(uid)
    st = load(code) if code else None
    if not st:
        return {"in_room": False, "plans": _plans_view()}
    st.setdefault("plan", "ffa")          # ห้องที่สร้างผ่านชั้นกลางตรง ๆ
    # ...ที่เหลือเหมือนเดิมทุกบรรทัด
```

- [ ] **Step 5: รันเทสสนามรบ — ต้องเท่าเส้นฐานเป๊ะ**

```bash
PYTHONIOENCODING=utf-8 python -m pytest tests/ -q -k "worms or pvp or room" 2>&1 | tail -3
```
Expected: ตัวเลขเท่ากับ Step 1 เป๊ะ **ถ้าน้อยกว่า = ถอยกลับ ห้ามแก้เทสให้ผ่าน**

- [ ] **Step 6: รันเทสชุดเต็ม**

Run: `PYTHONIOENCODING=utf-8 python -m pytest -q`
Expected: PASS ทั้งหมด

- [ ] **Step 7: Commit**

```bash
git add bot/pvp/rooms.py tests/test_lobby.py
git commit -m "refactor(pvp): สนามรบย้ายมาใช้ล็อบบี้กลาง

rooms.py เหลือแต่เรื่องทีม (2-2-2 / 3v3) ที่เป็นของสนามรบล้วน ๆ
เรื่องห้อง/รหัส/ที่นั่งส่งต่อให้ bot/lobby.py

ชื่อ public เดิมครบทั้ง 11 ฟังก์ชัน 4 ค่าคงที่
match.py กับ web_api.py จึงไม่ต้องแก้สักบรรทัด

เทสสนามรบเดิมผ่านเท่าเดิมทุกข้อ = ย้ายสำเร็จ

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

# งานที่ 3: UNO เดิมพัน `bot/cards/uno_room.py`

**ความเสี่ยง:** ปานกลาง — แตะเงินจริง

**Files:**
- Create: `bot/cards/uno_room.py`
- Test: `tests/test_uno_money.py`

**Interfaces:**
- Consumes: `bot.lobby` (งานที่ 1) · `bot.cards.uno_engine` — `new_game(names, rng=None, start_cards=uno_engine.START_CARDS)` คืน state ที่มี `players[i]["hand"]` (ไพ่เป็น dict มี 2 คีย์: `{"suit": "fire", "value": "3"}`) · `play(st, index, chosen_suit=None, rng=None)` · `draw(st, ...)` · `passes(st, ...)` · `bot.models.player_model.get_player(uid) -> dict | None` และ `increment_player_field(uid, "cash", amount)`
- Produces: `open_table(uid, name, bet) -> tuple[bool, dict]` · `sit(uid, name, code) -> tuple[bool, dict]` · `stand(uid) -> dict | None` · `begin(uid) -> tuple[bool, dict]` · `view(uid) -> dict`

**กฎเหล็กที่งานนี้ต้องรักษา:** ทองรวมก่อน = ทองรวมหลัง ทุกกรณี

- [ ] **Step 1: เขียนเทสเงินให้แดงก่อน**

สร้าง `tests/test_uno_money.py` — เทสสำคัญที่สุดคือ "ทองรวมไม่เปลี่ยน":

```python
"""💰 UNO เดิมพัน — ทองรวมในระบบต้องเท่าเดิมเป๊ะทุกกรณี

เจ้าของเกมเคาะ (09-02): เล่นกับบอทไม่ได้เงิน · ที่ 1 กินเรียบ · ออกกลางคันเสียเงิน
"""
import pytest

from bot.cards import uno_room


@pytest.fixture(autouse=True)
def db(tmp_path, monkeypatch):
    import sqlite3

    from license_server import web_db

    path = tmp_path / "web.db"

    def _connect():
        conn = sqlite3.connect(str(path), timeout=5)
        conn.row_factory = sqlite3.Row
        conn.executescript(web_db._SCHEMA)
        return conn

    monkeypatch.setattr(web_db, "connect", _connect)
    yield


@pytest.fixture
def wallet(monkeypatch):
    """กระเป๋าเงินปลอม — นับยอดรวมได้ง่าย ไม่แตะฐานข้อมูลจริง"""
    money = {}

    def get_player(uid):
        return {"cash": money.get(str(uid), 0)}

    def inc(uid, field, amount=1):
        assert field == "cash"
        money[str(uid)] = money.get(str(uid), 0) + amount
        assert money[str(uid)] >= 0, "เงินติดลบ = บั๊ก"
        return True

    from bot.models import player_model
    monkeypatch.setattr(player_model, "get_player", get_player)
    monkeypatch.setattr(player_model, "increment_player_field", inc)
    money.total = lambda: sum(money.values())
    return money


def test_เข้าโต๊ะหักเงินทันที(wallet):
    wallet["1"] = 5000
    ok, _ = uno_room.open_table(1, "เอ", 1000)
    assert ok
    assert wallet["1"] == 4000


def test_เงินไม่พอเข้าโต๊ะไม่ได้(wallet):
    wallet["1"] = 500
    ok, got = uno_room.open_table(1, "เอ", 1000)
    assert not ok and "ไม่พอ" in got["error"]
    assert wallet["1"] == 500, "เข้าไม่ได้ต้องไม่หักเงิน"


def test_ทองรวมไม่เปลี่ยนตลอดเกม(wallet):
    """กฎเหล็ก — เงินย้ายมือ ไม่งอก ไม่หาย"""
    wallet["1"] = 5000
    wallet["2"] = 5000
    before = sum(wallet.values())

    ok, st = uno_room.open_table(1, "เอ", 1000)
    assert ok
    assert uno_room.sit(2, "บี", st["room"])[0]
    assert sum(wallet.values()) + 2000 == before, "เงินเข้ากองกลางแล้ว"

    uno_room.begin(1)
    uno_room._payout(uno_room._room(1), "1")      # จบเกม เอชนะ
    assert sum(wallet.values()) == before, "ทองรวมต้องเท่าเดิมเป๊ะ"


def test_ที่หนึ่งกินเรียบ(wallet):
    wallet["1"] = 5000
    wallet["2"] = 5000
    _, st = uno_room.open_table(1, "เอ", 1000)
    uno_room.sit(2, "บี", st["room"])
    uno_room.begin(1)
    uno_room._payout(uno_room._room(1), "1")
    assert wallet["1"] == 6000      # 4000 + กองกลาง 2000
    assert wallet["2"] == 4000


def test_ยุบโต๊ะก่อนเริ่มคืนเงินครบ(wallet):
    wallet["1"] = 5000
    wallet["2"] = 5000
    _, st = uno_room.open_table(1, "เอ", 1000)
    uno_room.sit(2, "บี", st["room"])
    uno_room.stand(2)
    uno_room.stand(1)
    assert wallet["1"] == 5000 and wallet["2"] == 5000, "ยังไม่เล่นต้องคืนครบ"


def test_ออกกลางเกมเสียเงิน(wallet):
    wallet["1"] = 5000
    wallet["2"] = 5000
    before = sum(wallet.values())
    _, st = uno_room.open_table(1, "เอ", 1000)
    uno_room.sit(2, "บี", st["room"])
    uno_room.begin(1)
    uno_room.stand(2)                    # บีหนีกลางเกม
    assert wallet["2"] == 4000, "ออกกลางเกมไม่คืนเงิน"
    uno_room._payout(uno_room._room(1), "1")
    assert wallet["1"] == 6000, "เอได้กองกลางทั้งหมด"
    assert sum(wallet.values()) == before


def test_จ่ายรางวัลซ้ำไม่ได้(wallet):
    """เน็ตกระตุกแล้วเบราว์เซอร์ยิงซ้ำ ห้ามได้เงินสองรอบ"""
    wallet["1"] = 5000
    wallet["2"] = 5000
    before = sum(wallet.values())
    _, st = uno_room.open_table(1, "เอ", 1000)
    uno_room.sit(2, "บี", st["room"])
    uno_room.begin(1)
    room = uno_room._room(1)
    uno_room._payout(room, "1")
    uno_room._payout(room, "1")
    uno_room._payout(room, "1")
    assert sum(wallet.values()) == before
    assert wallet["1"] == 6000, "จ่ายได้ครั้งเดียว"


def test_คนเดียวเริ่มเกมไม่ได้(wallet):
    wallet["1"] = 5000
    uno_room.open_table(1, "เอ", 1000)
    ok, got = uno_room.begin(1)
    assert not ok and "2 คน" in got["error"]


def test_เดิมพันติดลบไม่ได้(wallet):
    wallet["1"] = 5000
    assert not uno_room.open_table(1, "เอ", -100)[0]
    assert wallet["1"] == 5000


def test_เล่นซ้ำ_20_รอบทองรวมนิ่ง(wallet):
    """ฟอกทองไม่ได้ — เล่นกี่รอบยอดรวมก็เท่าเดิม"""
    wallet["1"] = 50000
    wallet["2"] = 50000
    before = sum(wallet.values())
    for i in range(20):
        _, st = uno_room.open_table(1, "เอ", 1000)
        uno_room.sit(2, "บี", st["room"])
        uno_room.begin(1)
        uno_room._payout(uno_room._room(1), "1" if i % 2 else "2")
        uno_room.stand(1)
        uno_room.stand(2)
    assert sum(wallet.values()) == before, "เล่น 20 รอบทองรวมต้องนิ่งสนิท"


def got_cards(v):
    """ดึงไพ่ทุกใบที่โผล่ในคำตอบของ view() — ไม่ว่าซ่อนอยู่ชั้นไหน"""
    out = []
    def walk(x):
        if isinstance(x, dict):
            if "suit" in x and "value" in x:
                out.append(x)
            for v in x.values():
                walk(v)
        elif isinstance(x, list):
            for v in x:
                walk(v)
    walk(v)
    return out


def test_view_ไม่หลุดไพ่คนอื่น(wallet):
    """🔒 ประตูเดียว — ไพ่ในมือคนอื่นห้ามหลุดลงเบราว์เซอร์แม้ใบเดียว"""
    import json
    wallet["1"] = 5000
    wallet["2"] = 5000
    _, st = uno_room.open_table(1, "เอ", 1000)
    uno_room.sit(2, "บี", st["room"])
    uno_room.begin(1)
    room = uno_room._room(1)
    # โครงจริงของ uno_engine: players[i]["hand"] — แต่ละใบเป็น dict ไม่ใช่ข้อความ
    game = room["extra"]["game"]
    seats = [s["uid"] for s in room["seats"]]
    others = [c for i, p in enumerate(game["players"])
              if seats[i] != "1" for c in p["hand"]]
    # ไพ่หนึ่งใบ = {"suit": ..., "value": ...} — นับจำนวนใบที่หลุดแทนเทียบข้อความ
    # (ไพ่ซ้ำกันได้ เทียบตรง ๆ จะฟ้องผิดเวลาไพ่ในมือเราชนกับของคนอื่น)
    import collections
    sent = collections.Counter(
        (c["suit"], c["value"]) for c in got_cards(uno_room.view(1)))
    mine = collections.Counter(
        (c["suit"], c["value"]) for c in game["players"][seats.index("1")]["hand"])
    assert sent == mine, "ส่งไพ่เกินมือตัวเอง = ไพ่คนอื่นหลุด"
    # จำนวนไพ่ทั้งหมดที่ส่งลงไป ต้องไม่เกินมือเรา
    assert len(others) > 0, "เทสนี้ต้องมีไพ่คนอื่นให้เทียบ ไม่งั้นเทสเปล่า
    # นับจำนวนไพ่ที่ส่งลงไป — ต้องเท่ามือเราเท่านั้น
```

- [ ] **Step 2: รันยืนยันว่าแดง**

Run: `PYTHONIOENCODING=utf-8 python -m pytest tests/test_uno_money.py -q`
Expected: FAIL — `No module named 'bot.cards.uno_room'`

- [ ] **Step 3: เขียน `bot/cards/uno_room.py`**

โครงที่ต้องมี (เขียนเต็มตอนลงมือ — ยึดตามเทสข้างบนเป็นสัญญา):

```python
"""💰 UNO เดิมพัน — โต๊ะหลายคนบนล็อบบี้กลาง

เจ้าของเกมเคาะ (09-02):
  - เล่นกับบอท "ไม่ได้เงิน" — ปิดช่องฟอกทองสนิท
  - ที่ 1 กินเรียบ · ออกกลางเกมเสียเงิน · ยุบก่อนเริ่มคืนครบ

⚠️ กฎเหล็ก: ทองรวมในระบบต้องเท่าเดิมเป๊ะทุกกรณี
   เงินขยับแค่ 2 จุด — ตอนเข้าโต๊ะ (หัก) กับตอนจบเกม (จ่าย)
"""
from bot import lobby
from bot.cards import uno_engine
from bot.models import player_model

GAME = "uno"
MIN_PLAYERS = 2


def _room(uid):
    code = lobby.room_of(GAME, uid)
    return lobby.load(code) if code else None


def open_table(uid, name, bet):
    """เปิดโต๊ะ — หักเงินทันทีตอนเข้า กันคนวางเงินแล้วไม่มีจ่าย"""
    bet = int(bet or 0)
    if bet < 0:
        return False, {"error": "❌ เดิมพันติดลบไม่ได้"}
    if bet and not _take(uid, bet):
        return False, {"error": "❌ เงินในกระเป๋าของคุณไม่พอ!"}
    st = lobby.create(GAME, uid, {"uid": str(uid), "name": name, "paid": bet},
                      {"bet": bet, "pot": bet, "paid_out": False})
    return True, lobby.save(st["room"], st)


def _take(uid, amount):
    """หักเงิน — คืน False ถ้าไม่พอ (เช็คก่อนหักเสมอ ห้ามติดลบ)"""
    p = player_model.get_player(uid)
    if not p or p.get("cash", 0) < amount:
        return False
    player_model.increment_player_field(uid, "cash", -amount)
    return True


def _payout(st, winner_uid):
    """จ่ายกองกลางให้ที่ 1 — จ่ายได้ครั้งเดียวเท่านั้น

    เน็ตกระตุกแล้วเบราว์เซอร์ยิงซ้ำ ต้องไม่ได้เงินสองรอบ
    """
    if not st or st["extra"].get("paid_out"):
        return
    st["extra"]["paid_out"] = True
    pot = st["extra"].get("pot", 0)
    if pot:
        player_model.increment_player_field(winner_uid, "cash", pot)
        st["extra"]["pot"] = 0
    lobby.save(st["room"], st)
```

`sit` `stand` `begin` `view` เขียนตามสัญญาในเทส:
- `sit` — หักเงินแล้วเรียก `lobby.join`
- `stand` — ยังไม่เริ่ม = คืนเงิน · เริ่มแล้ว = ไม่คืน (เงินค้างในกองกลาง)
- `begin` — ต้องมีคนจริง ≥ 2 · มีบอท → `bet` เป็น 0
- `view` — ต่อยอด `lobby.view` เติมไพ่ในมือ**ตัวเองเท่านั้น** + จำนวนใบของคนอื่น

- [ ] **Step 4: รันเทสยืนยันเขียว**

Run: `PYTHONIOENCODING=utf-8 python -m pytest tests/test_uno_money.py -q`

- [ ] **Step 5: กลับด้านเทส**

| แกล้งทำพัง | เทสที่ต้องแดง |
|---|---|
| `_payout` ตัด `if st["extra"].get("paid_out")` ออก | `test_จ่ายรางวัลซ้ำไม่ได้` |
| `stand` คืนเงินแม้เริ่มเกมแล้ว | `test_ออกกลางเกมเสียเงิน` |
| `_take` ไม่เช็คเงินพอ | `test_เงินไม่พอเข้าโต๊ะไม่ได้` |
| `view` ส่ง `hands` ทั้งก้อน | `test_view_ไม่หลุดไพ่คนอื่น` |

- [ ] **Step 6: รันชุดเต็ม + commit**

```bash
git add bot/cards/uno_room.py tests/test_uno_money.py
git commit -m "feat(uno): โต๊ะเดิมพันทองเล่นกับเพื่อน

เงินขยับแค่ 2 จุด: เข้าโต๊ะหัก · จบเกมจ่ายที่ 1
เล่นกับบอทไม่ได้เงิน = ฟอกทองไม่ได้

เทสคุมทองรวมก่อน=หลังทุกกรณี รวมออกกลางคันกับจ่ายซ้ำ

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

# งานที่ 4: หน้าล็อบบี้บนเว็บ

**ความเสี่ยง:** ไม่มี — ของใหม่ ไม่แตะหน้าเดิม

**Files:**
- Modify: `license_server/web_api.py` (เพิ่ม endpoint)
- Modify: `license_server/web_static/play.html` — เพิ่มปุ่มล็อบบี้**บนสุดหมวดออกผจญภัย** (บรรทัด 80 `<h3>ออกผจญภัย</h3>` ตามด้วย `<div class="g-grid">`) + หน้าเลือกโหมดใน `v-uno` (บรรทัด 932)
- Modify: `license_server/web_static/uno.js` `play.js` `play.css`

**ห้ามแตะ:** ปุ่มสนามรบ (`play.html:250`) และปุ่มไพ่รูน (`play.html:298`) — เจ้าของเกมสั่งให้อยู่ที่เดิมเข้าเล่นได้เหมือนเดิม

**Interfaces:**
- Consumes: `uno_room.open_table/sit/stand/begin/view` (งานที่ 3) · `lobby.view` (งานที่ 1)
- Produces: `POST /api/web/lobby` (action: `create|join|leave|start`) · `GET /api/web/lobby?game=uno`

- [ ] **Step 1: เทสว่า API ไม่หลุดความลับ**

เพิ่มใน `tests/test_uno_money.py` — คุมชั้น HTTP จริงอีกชั้น (แบบเดียวกับ `test_worms_props.py`):

```python
def test_http_ไม่หลุดไพ่คนอื่น(wallet):
    """ชั้นที่สอง — คุมที่คำตอบ HTTP จริง ไม่ใช่แค่ที่ฟังก์ชัน"""
    # เรียก endpoint จริงผ่าน TestClient แล้วเช็คว่าไพ่คนอื่นไม่โผล่
```

- [ ] **Step 2: เพิ่มปุ่มล็อบบี้บนสุดหมวดออกผจญภัย**

ใน `play.html` ใต้ `<h3>ออกผจญภัย</h3><div class="g-grid">` แทรกเป็นปุ่มแรก:

```html
<button class="g-tile hot" data-go="lobby">
  <span class="ic">🎪</span>ล็อบบี้ · ชวนเพื่อนเล่น<span class="sub">รวมทุกเกมที่เล่นกับเพื่อนได้</span></button>
```

- [ ] **Step 3: หน้าเลือกโหมดใน UNO**

เข้า `v-uno` แล้วเจอ 2 ปุ่มก่อนถึงโต๊ะ: `🤖 เล่นกับบอท` (ของเดิม) · `👥 เล่นกับเพื่อน` (ไปล็อบบี้)

⚠️ ระวัง `[hidden]` — CSS ที่มี `display:` ทับ `[hidden]{display:none}` เสมอ
ต้องเพิ่มคลาสใหม่เข้าบล็อกนี้ใน `play.css`:
```css
.uno-over[hidden], .uno-help[hidden], ... { display: none !important; }
```

- [ ] **Step 4-7: รันเทส · กลับด้าน · ชุดเต็ม · commit**

---

# งานที่ 5: DM คำเชิญ `bot/cogs/lobby_invite.py`

**ความเสี่ยง:** ไม่มี — cog ใหม่

**Files:**
- Create: `bot/cogs/lobby_invite.py`
- Test: `tests/test_lobby_invite.py`

**Interfaces:**
- Consumes: `bot.friends.are_friends(a_id, b_id) -> bool` · `bot.friends.list_of(uid)` · `bot.lobby.room_of`
- Produces: `send_invite(bot, from_uid, to_uid, game, code, bet) -> tuple[bool, str]`

ใช้แบบแผนจาก `bot/cogs/guild.py:53` (`GuildInviteView`) — ปุ่มยืนยันที่เช็คว่าคนกดคือคนถูกเชิญจริง

- [ ] **Step 1: เทส**

```python
def test_ชวนคนที่ไม่ใช่เพื่อนไม่ได้():
    """เช็คฝั่งเซิร์ฟเวอร์ — เบราว์เซอร์ส่ง uid อะไรมาก็เชื่อไม่ได้"""

def test_เพื่อนปิด_dm_บอกให้ส่งรหัสเอง():

def test_สแปมชวนโดนจำกัด():

def test_คนอื่นกดปุ่มคำเชิญของเราไม่ได้():
```

- [ ] **Step 2-7: ตามรอบเดิม**

---

## เช็คหลังทำครบทุกงาน

- [ ] เทสชุดเต็มผ่าน (ฐาน 2665 + ของใหม่)
- [ ] เปิดเว็บจริง กดปุ่มล็อบบี้เข้าได้
- [ ] ปุ่มสนามรบเดิมยังเข้าเล่นได้เหมือนเดิม
- [ ] ปุ่มไพ่รูนเดิมยังเข้าเล่นกับบอทได้เหมือนเดิม
- [ ] เปิด 2 เบราว์เซอร์ทดสอบเล่นกับเพื่อนจริง (ต้องมีคนที่ 2)
