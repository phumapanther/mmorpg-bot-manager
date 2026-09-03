# license_server/api_web/bank.py
"""ธนาคาร + ทองคำแท่ง (ย้ายจาก web_api.py 09-02)"""
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from license_server.api_web.deps import _money_now, _user_lock, require_player

router = APIRouter()


class BankBody(BaseModel):
    action: str
    amount: int
    target_id: str = ""


@router.post("/bank")
def bank(body: BankBody, request: Request):
    """ฝาก/ถอน/โอน — เรียก bank_action() ตัวเดียวกับปุ่มธนาคารในดิส (ค่าธรรมเนียมคิดในนั้น)"""
    uid = require_player(request)["uid"]
    if body.action not in ("deposit", "withdraw", "transfer"):
        raise HTTPException(400, "ไม่รู้จักธุรกรรมนี้")
    if body.amount <= 0:
        raise HTTPException(400, "จำนวนเงินต้องมากกว่า 0")

    target = None
    if body.action == "transfer":
        if not str(body.target_id).isdigit():
            raise HTTPException(400, "ใส่ไอดี Discord ของผู้รับเป็นตัวเลข")
        target = int(body.target_id)

    from core.services.bank import bank_action
    with _user_lock(uid):
        ok, msg = bank_action(int(uid), body.action, body.amount, target_id=target)
    return {"ok": ok, "message": msg, "money": _money_now(uid)}


@router.get("/bank/fee")
def bank_fee_preview(amount: int, request: Request):
    """ดูค่าธรรมเนียมก่อนยืนยัน — คิดด้วย bank_fee() ตัวเดียวกับตอนทำจริง

    มีไว้ให้หน้ายืนยันบอกตัวเลขจริงได้ ไม่ต้องให้เบราว์เซอร์คำนวณเอง (จะเพี้ยนจากของจริง)
    """
    require_player(request)
    if amount <= 0:
        raise HTTPException(400, "จำนวนเงินต้องมากกว่า 0")
    from core.services.bank import bank_fee
    fee, pct = bank_fee(amount)
    return {"amount": amount, "fee": fee, "pct": pct, "net": amount - fee}


class BarBody(BaseModel):
    action: str
    item_id: str


@router.post("/goldbar")
def goldbar(body: BarBody, request: Request):
    """แลกซื้อ/ขายคืนทองคำแท่ง — เรียก gold_bars ตัวเดียวกับปุ่ม 🧈 ในดิส"""
    uid = require_player(request)["uid"]
    if body.action not in ("buy", "sell"):
        raise HTTPException(400, "ไม่รู้จักคำสั่งนี้")

    from bot import gold_bars
    with _user_lock(uid):
        fn = gold_bars.buy_bar if body.action == "buy" else gold_bars.sell_bar
        ok, msg = fn(int(uid), body.item_id)
    return {"ok": ok, "message": msg, "money": _money_now(uid)}


@router.get("/goldbar/prices")
def goldbar_prices():
    """ราคาซื้อ/ขายคืนของแท่งทองแต่ละขนาด — คิดค่าธรรมเนียมมาให้แล้ว"""
    from bot import config_loader, gold_bars
    pct = gold_bars.fee_pct()
    out = []
    for iid, face in gold_bars.bar_items().items():
        fee = face * pct // 100
        out.append({"id": iid, "name": config_loader.get_item_config(iid).get("name", iid),
                    "face": face, "buy": face + fee, "sell": face - fee})
    return {"fee_pct": pct, "bars": out}
