# license_server/api_web/games/pvp.py
"""สนามรบผลัดเทิร์น (Worms) — แผนที่ + ซ้อมกับบอท + ห้องเล่นหลายคน (ย้ายจาก web_api.py 09-02)"""
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from license_server.api_web.deps import _user_lock, player_model_get, require_player

router = APIRouter()


@router.get("/pvp/worms/map")
def worms_map(request: Request, seed: int = 0, continent: str = "", players: int = 2):
    """แผนที่หนึ่งใบ — เมล็ดเดียวกันได้แผนที่เดียวกันเป๊ะ (แชร์รหัสแผนที่กับเพื่อนได้)"""
    require_player(request)
    import random as _r

    from bot.game_data import CONTINENTS
    from bot.pvp import terrain

    if continent not in CONTINENTS:
        continent = _r.choice(list(CONTINENTS))
    seed = int(seed) or _r.randrange(1, 10 ** 14)
    return terrain.view(seed, continent, max(2, min(8, int(players))))


class WormsBody(BaseModel):
    action: str = "walk"       # new | walk | jump | attack | end | timeout
    dir: int = 1               # -1 ซ้าย · 1 ขวา
    steps: int = 1
    seed: int = 0
    skill: str = ""            # สกิลที่ใช้ (ตอน attack)
    angle: float | None = None   # มุมเล็ง องศา · ไม่ส่งมาก็ใช้ค่าตั้งต้นตามชนิดท่า
    power: float = 70          # แรงยิง 10-100
    jump_power: float = 1      # แรงกระโดด 0-1 (กดค้างนานยิ่งไกล)
    lean: float = 0            # เอนตัวกลางอากาศ -1..1


@router.post("/pvp/worms/match")
def worms_match(body: WormsBody, request: Request):
    """🤖 ซ้อมกับบอท — ตำแหน่งทุกตัวตัดสินที่เซิร์ฟเวอร์ เบราว์เซอร์ส่งมาแค่ปุ่มที่กด"""
    uid = int(require_player(request)["uid"])
    from bot.pvp import match

    with _user_lock(uid):
        if body.action == "new":
            p = player_model_get(uid)
            from bot import fashion as _fashion
            look = {"race": p.get("race"), "cls": p.get("class_name"),
                    "armor": p.get("armor") or "None", "weapon": p.get("weapon") or "",
                    "fashion": _fashion.worn(p)}
            return match.view(uid, match.new_practice(uid, look, body.seed))
        if body.action == "surrender":
            ok, r = match.surrender(uid)
            if not ok:
                raise HTTPException(400, r["error"])
            return r
        if body.action == "quit":
            match.drop(uid)          # ทิ้งแมตช์ทิ้งไปเลย จะได้กลับมาเจอหน้าเริ่มเกม
            return match.view(uid)
        if body.action in ("end", "timeout"):
            # timeout = เบราว์เซอร์บอกว่านาฬิกาหมด แต่เซิร์ฟเวอร์เช็คเวลาเองอีกที
            # (ปรับนาฬิกาเครื่องตัวเองแล้วขอเทิร์นเพิ่มไม่ได้)
            ok, r = match.end_turn(uid, auto=body.action == "timeout")
        elif body.action == "attack":
            ok, r = match.attack(uid, body.skill, body.angle, body.power, body.dir)
        elif body.action in ("walk", "jump"):
            ok, r = match.move(uid, body.action, body.dir, body.steps,
                               body.jump_power, body.lean)
        else:
            raise HTTPException(400, "ไม่รู้จักคำสั่งนี้")
    if not ok:
        raise HTTPException(400, r["error"])
    return r


@router.get("/pvp/worms/match")
def worms_match_state(request: Request):
    uid = int(require_player(request)["uid"])
    from bot.pvp import match
    return match.view(uid)


class RoomBody(BaseModel):
    action: str = "view"       # view | create | join | leave | plan | team | start
    code: str = ""             # รหัสห้องตอน join
    plan: str = ""             # ffa | 3v3 | 2v2v2
    team: int = 0
    seed: int = 0


@router.post("/pvp/worms/room")
def worms_room(body: RoomBody, request: Request):
    """🎪 ห้องเล่นหลายคน — แยกขาดจากปุ่มซ้อมกับบอท

    🔒 ทุกคำสั่งผูกกับ uid ที่ล็อกอินอยู่เท่านั้น เบราว์เซอร์ระบุแทนคนอื่นไม่ได้
    """
    uid = int(require_player(request)["uid"])
    from bot.pvp import match, rooms

    def _look():
        p = player_model_get(uid)
        from bot import fashion as _fashion
        return {"race": p.get("race"), "cls": p.get("class_name"),
                "armor": p.get("armor") or "None", "weapon": p.get("weapon") or "",
                "fashion": _fashion.worn(p)}

    def _name():
        # ใช้ยศเป็นชื่อเรียกเหมือนหน้าโปรไฟล์เพื่อน (bot/friends.py) ไม่มีก็ใช้ไอดี
        p = player_model_get(uid)
        return p.get("rank") or f"ผู้เล่น {uid}"

    with _user_lock(uid):
        if body.action == "create":
            rooms.create(uid, _name(), _look())
        elif body.action == "join":
            ok, r = rooms.join(uid, body.code, _name(), _look())
            if not ok:
                raise HTTPException(400, r["error"])
        elif body.action == "leave":
            rooms.leave(uid)
        elif body.action == "plan":
            ok, r = rooms.set_plan(uid, body.plan)
            if not ok:
                raise HTTPException(400, r["error"])
        elif body.action == "team":
            ok, r = rooms.set_team(uid, body.team)
            if not ok:
                raise HTTPException(400, r["error"])
        elif body.action == "start":
            ok, r = match.start_room(uid, body.seed)
            if not ok:
                raise HTTPException(400, r["error"])
        elif body.action != "view":
            raise HTTPException(400, "ไม่รู้จักคำสั่งนี้")
        return rooms.view(uid)


@router.get("/pvp/worms/room")
def worms_room_state(request: Request):
    uid = int(require_player(request)["uid"])
    from bot.pvp import rooms
    return rooms.view(uid)
