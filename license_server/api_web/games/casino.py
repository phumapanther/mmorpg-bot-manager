# license_server/api_web/games/casino.py
"""ไฮโล/สล็อต + แบล็กแจ็ค บนเว็บ (ย้ายจาก web_api.py 09-02)"""
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from license_server.api_web.deps import _money_now, _user_lock, require_player

router = APIRouter()


class CasinoBody(BaseModel):
    game: str
    bet: int
    choice: str = ""


@router.post("/casino")
def casino(body: CasinoBody, request: Request):
    """เล่นคาสิโนหนึ่งตา — casino_core ตัวเดียวกับปุ่ม !hilo / !slots ในดิส

    ผลออกที่เซิร์ฟเวอร์ทั้งหมดรวมถึงระบบเจ้ามือตุกติก เบราว์เซอร์แค่เอาไปเล่นอนิเมชัน
    """
    uid = require_player(request)["uid"]
    if body.game not in ("hilo", "slots"):
        raise HTTPException(400, "ไม่รู้จักเกมนี้")
    if body.bet <= 0:
        raise HTTPException(400, "เดิมพันต้องมากกว่า 0")

    from bot import casino_core
    with _user_lock(uid):
        if body.game == "hilo":
            ok, out = casino_core.play_hilo(int(uid), body.choice, body.bet)
        else:
            ok, out = casino_core.play_slots(int(uid), body.bet)
    return {"ok": ok, "result": out, "money": _money_now(uid)}


class BjBody(BaseModel):
    action: str
    bet: int = 0


@router.post("/blackjack")
def blackjack(body: BjBody, request: Request):
    """แบล็กแจ็ค 24 — blackjack_core ตัวเดียวกับปุ่มในดิส

    สถานะโต๊ะอยู่ใน DB เปิดมือในดิสแล้วมาเล่นต่อที่นี่ได้เลย
    """
    uid = require_player(request)["uid"]
    if body.action not in ("start", "hit", "stand"):
        raise HTTPException(400, "ไม่รู้จักคำสั่งนี้")

    from bot import blackjack_core
    with _user_lock(uid):
        if body.action == "start":
            if body.bet <= 0:
                raise HTTPException(400, "เดิมพันต้องมากกว่า 0")
            ok, out = blackjack_core.start(int(uid), body.bet)
        elif body.action == "hit":
            ok, out = blackjack_core.hit(int(uid))
        else:
            ok, out = blackjack_core.stand(int(uid))
    return {"ok": ok, "game": out, "money": _money_now(uid)}


@router.get("/blackjack")
def blackjack_current(request: Request):
    """โต๊ะที่ค้างอยู่ (ถ้ามี) — เปิดหน้าเว็บมาเจอมือที่เปิดค้างไว้ในดิสได้"""
    uid = require_player(request)["uid"]
    from bot import blackjack_core
    state = blackjack_core.load_game(int(uid))
    if not state:
        return {"playing": False}
    return {"playing": True, "game": blackjack_core._view(state)}
