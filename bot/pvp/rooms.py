"""🎪 ห้องสนามรบผลัดเทิร์น — เปลือกบางบน bot/lobby.py

เจ้าของเกมเคาะ (09-02): ย้ายมาใช้ล็อบบี้กลางที่ทุกเกมใช้ร่วมกัน

⚠️ ไฟล์นี้เก็บ "ชื่อฟังก์ชันเดิมครบทุกตัว" ไว้โดยตั้งใจ
   match.py กับ web_api.py เรียกอยู่หลายจุด — เปลี่ยนชื่อเมื่อไหร่พังทันที
   เรื่องห้อง/รหัส/ที่นั่ง = ส่งต่อให้ lobby.py
   เรื่องทีม (2-2-2 / 3v3) = ยังอยู่ที่นี่ เพราะเป็นของสนามรบล้วน ๆ
"""
import json  # noqa: F401  (เผื่อโค้ดเดิมที่ import จากที่นี่)
import time  # noqa: F401  (เผื่อโค้ดเดิมที่ import จากที่นี่)

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
    st.setdefault("plan", "ffa")          # ห้องที่สร้างผ่านชั้นกลางตรง ๆ ไม่มีคีย์ plan
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
