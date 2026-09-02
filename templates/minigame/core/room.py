"""🏠 ห้องทายเลขหลายคน — ขั้น 5 ของเกมทายเลข 1-10 บนล็อบบี้กลาง

ใช้ bot/lobby.py (ล็อบบี้กลางที่ทุกเกมใช้ร่วมกันได้) — ไฟล์นี้แค่ต่อยอด
"ห้อง" ให้เข้าใจกติกาเกมทายเลข ไม่ได้คุมเรื่องที่นั่ง/รหัสห้องเอง

⚠️ ตัวอย่างนี้ไม่แตะเงิน — ถ้าเกมของคุณมีเดิมพัน อ่านกฎเหล็ก #3 ใน
   templates/minigame/README.md ก่อนเพิ่มโค้ดหักเงิน/จ่ายเงิน
   ตัวอย่างจริงที่แตะเงิน: bot/games/casino/uno/room.py
"""
from bot import lobby

from . import engine as E

GAME = "template_guessnum"    # 🔁 เปลี่ยนเป็นชื่อเกมของคุณตอนก๊อปไปใช้จริง
MIN_PLAYERS = 2


def _room(uid):
    code = lobby.room_of(GAME, uid)
    return lobby.load(code) if code else None


def open_room(uid, name):
    """เปิดห้องใหม่ — คนเปิดเป็นหัวห้องและนั่งที่แรกทันที"""
    st = lobby.create(GAME, uid, {"uid": str(uid), "name": name}, {"game": None})
    return lobby.save(st["room"], st)


def sit(uid, name, code):
    """เข้าห้องด้วยรหัส — คืน (ok, ห้อง|ข้อความผิดพลาด)"""
    return lobby.join(GAME, uid, code, {"uid": str(uid), "name": name})


def stand(uid):
    """ออกจากห้อง — หัวห้องออกก็ยกให้คนถัดไป ไม่มีคนเหลือก็ปิดห้อง"""
    return lobby.leave(GAME, uid)


def begin(uid):
    """เริ่มเกม — ต้องมีคนอย่างน้อย MIN_PLAYERS คน"""
    st = _room(uid)
    if not st:
        return False, {"error": "ยังไม่ได้อยู่ห้องไหน"}
    if st["host"] != str(uid):
        return False, {"error": "เฉพาะหัวห้องเท่านั้นที่เริ่มเกมได้"}
    if len(st["seats"]) < MIN_PLAYERS:
        return False, {"error": f"ต้องมีคนอย่างน้อย {MIN_PLAYERS} คนถึงจะเริ่มได้"}

    names = [s["name"] for s in st["seats"]]
    st["extra"]["game"] = E.new_game(names)
    st["started"] = True
    return True, lobby.save(st["room"], st)


def _act(uid, fn):
    """ทำท่าหนึ่งของคนจริงในห้อง — ประตูเดียวคุมทุกท่า คืน (ok, ผล)

    เช็คว่าคนที่ส่งคำสั่งมาเป็นเจ้าของตาปัจจุบันจริงไหม ไม่งั้นคนอื่นสั่งแทนกันได้
    """
    st = _room(uid)
    if not st:
        return False, {"error": "ยังไม่ได้อยู่ห้องไหน"}
    if not st.get("started"):
        return False, {"error": "เกมยังไม่เริ่ม"}
    game = st["extra"].get("game")
    if not game:
        return False, {"error": "เกมยังไม่เริ่ม"}
    if game.get("over"):
        return False, {"error": "เกมนี้จบแล้ว"}
    seats = [s["uid"] for s in st["seats"]]
    if str(uid) not in seats:
        return False, {"error": "คุณไม่ได้อยู่ห้องนี้"}
    if game["turn"] != seats.index(str(uid)):
        return False, {"error": "ยังไม่ถึงตาคุณ"}

    ok, r = fn(game)
    if not ok:
        return False, r
    lobby.save(st["room"], st)
    return True, {**r, "room": view(uid)}


def guess(uid, number):
    return _act(uid, lambda game: E.guess(game, number))


# ── 🔒 ประตูเดียวก่อนส่งขึ้นเว็บ ──

def view(uid):
    """ห้องทายเลขพร้อมแสดงผลบนเว็บ — คัด secret ออกจนกว่าเกมจะจบ

    ต่อยอดจาก lobby.view() ที่คุมแค่ "ใครนั่งห้องไหน" — เกมเติมกติกาเฉพาะตัวเอง
    """
    out = lobby.view(GAME, uid)
    st = _room(uid)
    if not st:
        return out
    game = st["extra"].get("game")
    if not game:
        return out
    seats = [s["uid"] for s in st["seats"]]
    me = seats.index(str(uid)) if str(uid) in seats else None

    out["turn"] = game["turn"]
    out["over"] = bool(game.get("over"))
    out["winner"] = game.get("winner")
    out["my_turn"] = me is not None and game["turn"] == me and not game.get("over")
    out["log"] = game["log"][-12:]
    out["players"] = [{"name": p["name"], "guesses": len(p["guesses"]), "you": i == me}
                       for i, p in enumerate(game["players"])]
    if game.get("over"):
        out["secret"] = game["secret"]     # ✅ เฉลยได้ก็ต่อเมื่อเกมจบแล้วเท่านั้น
    return out
