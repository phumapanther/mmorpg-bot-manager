# license_server/api_web/games/party.py
"""🎭 ชวนเพื่อนเดินทาง — ล็อบบี้ปาร์ตี้ (เฟส 2)

สเปก: docs/superpowers/specs/2026-09-03-party-rpg-design.md
เฟสนี้ทำแค่ห้อง ยังไม่มีการต่อสู้ (เฟส 3)
"""
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from license_server.api_web.deps import _user_lock, player_model_get, require_player

router = APIRouter()


class PartyBody(BaseModel):
    action: str = "view"       # create|join|leave|start|again|restart|view
    #                          + คำสั่งในสมรภูมิ (attack|revive|flee|<สกิล>)
    #                          + คำสั่งในเหตุการณ์ (rest|walk|open|dodge|talk|buy:<id>|...)
    code: str = ""             # รหัสห้องตอน join
    target: str = ""           # เป้าหมายตอนสั่งท่า (เช่น "m2" หรือ "p3")
    boss_raid: bool = False    # หัวห้องติ๊กก่อนกดเริ่ม = เจอบอสแทนมอนธรรมดา
    # ⚠️ ห้ามเพิ่ม uid/host ที่นี่เด็ดขาด — ต้องมาจาก session เท่านั้น
    #    (ไม่งั้นคนยิง API ตรง ๆ ปลอมเป็นคนอื่นได้ · คำเชิญ UNO เคยพลาดข้อนี้)


def _name_of(uid):
    """ชื่อที่โชว์ในปาร์ตี้ — เอาจากตัวละครในเกม ไม่ให้เบราว์เซอร์ส่งมาเอง"""
    p = player_model_get(uid) or {}
    return p.get("title") or p.get("remark") or f"ผู้เล่น {uid}"


@router.post("/party/room")
def party_room(body: PartyBody, request: Request):
    """🎭 ห้องปาร์ตี้ — สร้าง / เข้า / ออก / เริ่ม

    🔒 uid มาจาก session เท่านั้น · ตอบด้วย room.view(uid) เท่านั้น
       (ห้ามส่ง state ดิบ — เฟส 3 จะมีค่าลับของมอนอยู่ในนั้น)
    """
    uid = int(require_player(request)["uid"])
    from bot.games.party import room

    with _user_lock(uid):
        if body.action == "create":
            room.open_party(uid, _name_of(uid))
            return {"ok": True, "room": room.view(uid)}

        if body.action == "join":
            ok, r = room.join_party(uid, _name_of(uid), body.code)
            if not ok:
                raise HTTPException(400, r.get("error", "เข้าปาร์ตี้ไม่ได้"))
            return {"ok": True, "room": room.view(uid)}

        if body.action == "leave":
            room.leave_party(uid)
            return {"ok": True, "room": room.view(uid)}

        if body.action == "start":
            ok, r = room.begin(uid, body.boss_raid)
            if not ok:
                raise HTTPException(400, r.get("error", "เริ่มไม่ได้"))
            return {"ok": True, "room": room.view(uid)}

        if body.action == "again":
            ok, r = room.again(uid)
            if not ok:
                raise HTTPException(400, r.get("error", "ออกเดินทางต่อไม่ได้"))
            return {"ok": True, "room": room.view(uid)}

        if body.action == "restart":
            ok, r = room.restart(uid)
            if not ok:
                raise HTTPException(400, r.get("error", "เริ่มใหม่ไม่ได้"))
            return {"ok": True, "room": room.view(uid)}

        if body.action == "view":
            return {"ok": True, "room": room.view(uid)}

        # ── คำสั่งในเหตุการณ์ที่ไม่ใช่การต่อสู้ (เฟส 10b-10c) ──
        #
        # 🔒 อยู่ในเหตุการณ์ = ส่งต่อให้ room.act ตัดสินทั้งดุ้น เพราะโมดูลเหตุการณ์
        #    เป็นด่านเดียวที่รู้ว่าถึงตาจริงไหม · ของอยู่ในเป้จริงไหม
        #    ทำลิสต์คำสั่งซ้ำที่นี่จะพลาดคำสั่งแบบ "buy:<id>" ที่สร้างตอนรันทันที
        #
        # ⚠️ ต้องอยู่ **หลัง** create/join/leave/start/again/restart
        #    ไม่งั้นชื่อคำสั่งที่ซ้ำกันจะถูกเหตุการณ์กินไปหมด
        if room.in_event(uid):
            ok, r = room.act(uid, body.action)
            if not ok:
                raise HTTPException(400, r.get("error", "สั่งไม่ได้"))
            return {"ok": True, "room": room.view(uid),
                    "events": r.get("events", [])}

        # ── คำสั่งในสมรภูมิ (เฟส 3) ──
        # 🔒 engine._check() เป็นด่านเดียวที่ตัดสินว่าสั่งได้ไหม
        #    (ถึงตาจริงไหม · ล้มแล้วหรือยัง · เล็งถูกฝั่งไหม)
        from bot.games.party import engine

        if body.action in engine.ACTIONS:
            ok, r = room.act(uid, body.action, body.target or None)
            if not ok:
                raise HTTPException(400, r.get("error", "สั่งไม่ได้"))
            return {"ok": True, "room": room.view(uid),
                    "events": r.get("events", [])}

    raise HTTPException(400, "คำสั่งไม่ถูกต้อง")


@router.get("/party/room")
def party_room_state(request: Request):
    """สถานะห้องตอนนี้ — หน้าเว็บเรียกซ้ำทุก 2 วิ เพื่อเห็นคนเข้า/ออก"""
    uid = int(require_player(request)["uid"])
    from bot.games.party import room

    return {"ok": True, "room": room.view(uid)}
