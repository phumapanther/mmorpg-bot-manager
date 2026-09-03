"""🎭 ห้องปาร์ตี้ — นั่งบนล็อบบี้กลาง (bot/lobby.py)

⚠️ `lobby.MAX_SEATS = 6` เป็นค่าของสนามรบ แต่เจ้าของเกมเคาะว่าปาร์ตี้ 5 คน
   ชั้นนี้จึงต้องดักเอง **ห้ามไปแก้ค่าในล็อบบี้กลาง** — สนามรบใช้อยู่

ไฟล์นี้ไม่รู้จักกติกาการต่อสู้เลย รู้แค่ "ใครนั่งอยู่ในปาร์ตี้ไหน"
กติกาอยู่ที่ engine.py (เฟส 3)
"""
from bot import lobby

GAME = "party"
MAX_PARTY = 5          # เจ้าของเกมเคาะ 2026-09-03
MIN_TO_START = 2


def _room(uid):
    code = lobby.room_of(GAME, uid)
    return lobby.load(code) if code else None


def _seat(uid, name):
    return {"uid": str(uid), "name": str(name or "ผู้เล่น")}


def open_party(uid, name):
    """เปิดปาร์ตี้ใหม่ — คนเปิดเป็นหัวห้องและนั่งที่แรกทันที"""
    st = lobby.create(GAME, uid, _seat(uid, name), {"phase": "lobby"})
    return True, st


def join_party(uid, name, code):
    """เข้าปาร์ตี้ด้วยรหัส — คืน (ok, ห้อง|ข้อความผิดพลาด)

    คนที่มีที่นั่งอยู่แล้วกลับเข้ามาได้เสมอ แม้ปาร์ตี้จะเต็ม
    (สเปกข้อ 4: หลุดแล้วกลับเข้ามาได้จนกว่าปาร์ตี้จะยุบ)
    """
    st = lobby.load(str(code or "").strip().upper())
    if st and st.get("game") == GAME:
        already = any(s["uid"] == str(uid) for s in st["seats"])
        if not already and len(st["seats"]) >= MAX_PARTY:
            return False, {"error": f"🚪 ปาร์ตี้เต็มแล้ว (สูงสุด {MAX_PARTY} คน)"}
    return lobby.join(GAME, uid, code, _seat(uid, name))


def leave_party(uid):
    """ออกจากปาร์ตี้ — หัวห้องออกก็ยกให้คนถัดไป (ล็อบบี้กลางจัดการให้)"""
    return lobby.leave(GAME, uid)


def begin(uid):
    """หัวห้องกดเริ่ม — ต้องมีอย่างน้อย 2 คน"""
    st = _room(uid)
    if not st:
        return False, {"error": "ยังไม่ได้อยู่ปาร์ตี้ไหน"}
    if st["host"] != str(uid):
        return False, {"error": "เฉพาะหัวห้องเท่านั้นที่เริ่มได้"}
    if len(st["seats"]) < MIN_TO_START:
        return False, {"error": f"ต้องมีอย่างน้อย {MIN_TO_START} คนถึงจะเริ่มได้"}
    st["started"] = True
    st["extra"]["phase"] = "battle"
    return True, lobby.save(st["room"], st)


def view(uid):
    """🔒 ประตูเดียวก่อนส่งขึ้นเบราว์เซอร์

    ตอนนี้ยังไม่มีของลับให้ซ่อน (ยังไม่มีสมรภูมิ) แต่ทุกอย่างต้องผ่านที่นี่
    ตั้งแต่แรก — เฟส 3 จะมีค่าลับของมอนมาเพิ่ม
    """
    out = lobby.view(GAME, uid)
    st = _room(uid)
    if st:
        out["max"] = MAX_PARTY                       # ทับค่า 6 ของล็อบบี้กลาง
        out["phase"] = st["extra"].get("phase", "lobby")
    return out
