# license_server/api_web/games/uno.py
"""ศึกไพ่รูน — ซ้อมกับบอท + โต๊ะเดิมพันกับเพื่อน (ย้ายจาก web_api.py 09-02)"""
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from license_server.api_web.deps import _user_lock, player_model_get, require_player

router = APIRouter()


class UnoBody(BaseModel):
    action: str = "view"       # start | play | draw | take | pass | uno | quit
    index: int = 0             # ไพ่ใบที่เท่าไหร่ในมือ
    suit: str = ""             # สีที่เลือกตอนวางไวลด์
    bots: int = 1


@router.post("/uno")
def uno(body: UnoBody, request: Request):
    """🎴 ศึกไพ่รูน — ซ้อมกับบอท

    🔒 เบราว์เซอร์ส่งมาแค่ "กดอะไร" — กติกาทั้งหมดตัดสินที่เซิร์ฟเวอร์
       ไพ่ในมือคนอื่นไม่เคยถูกส่งลงมา (uno_table.view คัดออกให้แล้ว)
    """
    uid = int(require_player(request)["uid"])
    from bot.cards import uno_table

    with _user_lock(uid):
        if body.action == "start":
            return {"ok": True, "table": uno_table.view(uid, uno_table.start(uid, bots=body.bots))}
        if body.action == "quit":
            uno_table.clear(uid)
            return {"ok": True, "table": {"playing": False}}
        if body.action == "view":
            return {"ok": True, "table": uno_table.view(uid)}

        if body.action == "play":
            ok, r = uno_table.play(uid, body.index, suit=body.suit or None)
        elif body.action == "draw":
            ok, r = uno_table.draw(uid)
        elif body.action == "take":
            ok, r = uno_table.take_stack(uid)
        elif body.action == "pass":
            ok, r = uno_table.passes(uid)
        elif body.action == "uno":
            ok, r = uno_table.say_uno(uid)
        else:
            raise HTTPException(400, "ไม่รู้จักคำสั่งนี้")
    if not ok:
        raise HTTPException(400, r["error"])
    return {"ok": True, **r}


@router.get("/uno")
def uno_current(request: Request):
    """โต๊ะที่ค้างอยู่ (ถ้ามี) — เปิดหน้าเว็บมาเจอโต๊ะเดิม"""
    uid = int(require_player(request)["uid"])
    from bot.cards import uno_table
    return {"ok": True, "table": uno_table.view(uid)}


class UnoRoomBody(BaseModel):
    action: str = "view"       # view | create | join | leave | start | play | draw | take_stack | pass | say_uno
    code: str = ""             # รหัสห้องตอน join
    bet: int = 0                # เดิมพันตอน create
    index: int = 0              # ไพ่ใบที่เท่าไหร่ในมือ ตอน play
    suit: str = ""              # สีที่เลือกตอนวางไวลด์


@router.post("/uno/room")
def uno_room_do(body: UnoRoomBody, request: Request):
    """🎴 โต๊ะ UNO เดิมพัน — ชวนเพื่อนเล่น แยกขาดจากปุ่มซ้อมกับบอท

    🔒 ทุกคำสั่งผูกกับ uid ที่ล็อกอินอยู่เท่านั้น เบราว์เซอร์ระบุแทนคนอื่นไม่ได้
    ตอบกลับด้วย uno_room.view(uid) เท่านั้น — ไม่ส่ง state ดิบ
    """
    uid = int(require_player(request)["uid"])
    from bot.cards import uno_room

    def _name():
        p = player_model_get(uid)
        return p.get("rank") or f"ผู้เล่น {uid}"

    with _user_lock(uid):
        if body.action == "create":
            ok, r = uno_room.open_table(uid, _name(), body.bet)
            if not ok:
                raise HTTPException(400, r["error"])
        elif body.action == "join":
            ok, r = uno_room.sit(uid, _name(), body.code)
            if not ok:
                raise HTTPException(400, r["error"])
        elif body.action == "leave":
            uno_room.stand(uid)
        elif body.action == "start":
            ok, r = uno_room.begin(uid)
            if not ok:
                raise HTTPException(400, r["error"])
        elif body.action == "play":
            ok, r = uno_room.play(uid, body.index, suit=body.suit or None)
            if not ok:
                raise HTTPException(400, r["error"])
        elif body.action == "draw":
            ok, r = uno_room.draw(uid)
            if not ok:
                raise HTTPException(400, r["error"])
        elif body.action == "take_stack":
            ok, r = uno_room.take_stack(uid)
            if not ok:
                raise HTTPException(400, r["error"])
        elif body.action == "pass":
            ok, r = uno_room.passes(uid)
            if not ok:
                raise HTTPException(400, r["error"])
        elif body.action == "say_uno":
            ok, r = uno_room.say_uno(uid)
            if not ok:
                raise HTTPException(400, r["error"])
        elif body.action != "view":
            raise HTTPException(400, "ไม่รู้จักคำสั่งนี้")
        return uno_room.view(uid)


@router.get("/uno/room")
def uno_room_state(request: Request):
    uid = int(require_player(request)["uid"])
    from bot.cards import uno_room
    return uno_room.view(uid)
