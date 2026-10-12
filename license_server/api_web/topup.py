# license_server/api_web/topup.py
"""เติมเงินผ่านเว็บ (เงินทุกบาทต้องผ่านมือแอดมิน — ไม่มีอนุมัติอัตโนมัติ) (ย้ายจาก web_api.py 09-02)

⚠️ _slip_path ถูก player.py เรียกด้วย (เช็คว่ามีสลิปไหมตอนโชว์ประวัติเติมเงินในหน้าโปรไฟล์)
"""
import base64
import os
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from license_server import web_db
from license_server.api_web.deps import _game_conn, require_admin, require_player, verify

router = APIRouter()


class TopupBody(BaseModel):
    amount_thb: float


class DecideBody(BaseModel):
    note: str = ""


@router.get("/topup/rate")
def topup_rate():
    """เรทแลกทอง (public) — หน้า /topup โชว์ว่าเติมเท่าไหร่ได้กี่ทองก่อนกดสร้าง QR"""
    from bot import config_loader
    pay = config_loader.get_config().get("payment", {})
    return {"rate": float(pay.get("exchange_rate") or 0),
            "min_amount": float(pay.get("min_amount") or 0),
            "max_amount": float(pay.get("max_amount") or 0)}


@router.post("/topup")
def create_topup(body: TopupBody, request: Request):
    uid = require_player(request)["uid"]
    from bot import config_loader
    pay = config_loader.get_config().get("payment", {})
    pp = pay.get("promptpay", {})
    if not pp.get("enabled") or not pp.get("id"):
        raise HTTPException(400, "ยังไม่เปิดรับเติมเงินผ่านเว็บ (แอดมินยังไม่ตั้งค่า PromptPay)")
    amt = float(body.amount_thb)
    mn = float(pay.get("min_amount") or 0)
    mx = float(pay.get("max_amount") or 0)
    if amt <= 0 or (mn and amt < mn) or (mx and amt > mx):
        raise HTTPException(400, f"จำนวนเงินต้องอยู่ระหว่าง {mn:g} - {mx:g} บาท")
    gold = int(amt * float(pay.get("exchange_rate") or 0))
    if gold <= 0:
        raise HTTPException(400, "อัตราแลกเปลี่ยนยังไม่ถูกตั้งค่า — แจ้งแอดมิน")
    from bot.promptpay import build_qr_png
    qr = base64.b64encode(build_qr_png(pp["id"], amt).getvalue()).decode()
    # จดเครื่องที่ทำรายการ — หลัง cloudflared IP จริงอยู่ใน cf-connecting-ip (ตรงๆ = client.host)
    ip = (request.headers.get("cf-connecting-ip")
          or (request.headers.get("x-forwarded-for") or "").split(",")[0].strip()
          or (request.client.host if request.client else ""))
    ua = request.headers.get("user-agent", "")[:300]
    with web_db.connect() as conn:
        cur = conn.execute(
            "INSERT INTO topups(discord_id, amount_thb, gold, ip, user_agent) VALUES (?,?,?,?,?)",
            (uid, amt, gold, ip, ua))
    return {"id": cur.lastrowid, "gold": gold, "qr": qr,
            "promptpay_name": pp.get("name", ""), "promptpay_id": pp.get("id", "")}


@router.get("/topup/{topup_id}/qr")
def topup_qr(topup_id: int, request: Request):
    """เปิด QR ของรายการตัวเองซ้ำ — เฉพาะรายการที่ยังรอตรวจ (จบแล้วไม่ควรมีใครโอนเพิ่ม)"""
    uid = require_player(request)["uid"]
    with web_db.connect() as conn:
        row = conn.execute("SELECT * FROM topups WHERE id=? AND discord_id=?",
                           (topup_id, uid)).fetchone()
    if not row:
        raise HTTPException(404, "ไม่พบรายการนี้ของคุณ")
    if row["status"] != "pending":
        raise HTTPException(400, "รายการนี้ถูกตัดสินไปแล้ว — สร้างรายการใหม่ได้ที่หน้าเติมเกม")
    from bot import config_loader
    pp = config_loader.get_config().get("payment", {}).get("promptpay", {})
    if not pp.get("id"):
        raise HTTPException(400, "ระบบเติมเงินปิดอยู่")
    from bot.promptpay import build_qr_png
    qr = base64.b64encode(build_qr_png(pp["id"], row["amount_thb"]).getvalue()).decode()
    return {"id": row["id"], "gold": row["gold"], "amount_thb": row["amount_thb"], "qr": qr,
            "promptpay_name": pp.get("name", ""), "promptpay_id": pp.get("id", "")}


# สลิปหลักฐานโอน — เก็บเป็นไฟล์ตามเลขรายการ (ไม่ต้องแก้ schema): web_uploads/slip_<id>.jpg
UPLOAD_DIR = Path(os.environ.get("UPLOAD_DIR") or (Path(__file__).resolve().parent.parent / "web_uploads"))
_SLIP_MAX = 5 * 1024 * 1024


def _slip_path(topup_id):
    return UPLOAD_DIR / f"slip_{int(topup_id)}.jpg"


@router.post("/topup/{topup_id}/slip")
async def upload_slip(topup_id: int, request: Request):
    from PIL import Image
    import io
    uid = require_player(request)["uid"]
    with web_db.connect() as conn:
        row = conn.execute("SELECT * FROM topups WHERE id=? AND discord_id=?",
                           (topup_id, uid)).fetchone()
    if not row:
        raise HTTPException(404, "ไม่พบรายการนี้ของคุณ")
    if row["status"] != "pending":
        raise HTTPException(400, "รายการนี้ถูกตัดสินไปแล้ว")
    # กันระเบิดภาพ (ไฟล์ 5MB คลายเป็นหลายร้อย MB) — container จำกัดแรม 512MB โดน OOM ลากบอท+เว็บตายพร้อมกัน
    # 1) เช็ค Content-Length ก่อนอ่าน body · 2) จำกัดจำนวนพิกเซลที่ยอม decode
    clen = request.headers.get("content-length")
    if clen and clen.isdigit() and int(clen) > _SLIP_MAX:
        raise HTTPException(400, "ไฟล์ใหญ่เกิน 5MB")
    Image.MAX_IMAGE_PIXELS = 25_000_000       # ~25 ล้านพิกเซล (เกินนี้ถือว่าผิดปกติ ไม่ใช่สลิปโอนเงิน)
    data = await request.body()
    if len(data) > _SLIP_MAX:
        raise HTTPException(400, "ไฟล์ใหญ่เกิน 5MB")
    try:
        img = Image.open(io.BytesIO(data))
        img.load()
    except Exception:
        raise HTTPException(400, "ไฟล์นี้เปิดเป็นรูปภาพไม่ได้ หรือใหญ่ผิดปกติ (รองรับ png/jpg/webp)")
    img = img.convert("RGB")
    img.thumbnail((1280, 1280))   # ย่อรูปสลิปใหญ่ๆ ให้พอดี ประหยัดที่
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    img.save(_slip_path(topup_id), format="JPEG", quality=85)
    return {"ok": True}


@router.get("/topup/{topup_id}/slip")
def get_slip(topup_id: int, request: Request):
    from fastapi.responses import FileResponse
    p = _slip_path(topup_id)
    if not p.is_file():
        raise HTTPException(404, "ยังไม่มีสลิปของรายการนี้")
    # แอดมินเปิดได้ทุกใบ — ผู้เล่นเปิดได้เฉพาะรายการตัวเอง
    # ⚠️ ต้องเช็ค role==admin ไม่ใช่แค่ลายเซ็นถูก: cookie ผู้เล่นเซ็นด้วยกุญแจเดียวกัน
    #    ถ้าเช็คแค่ verify() ผู้เล่นเอา web_session มาใส่ช่อง web_admin แล้วเปิดสลิปคนอื่นได้ (IDOR)
    _adm = verify(request.cookies.get("web_admin", ""))
    if not (_adm and _adm.get("role") == "admin"):
        uid = require_player(request)["uid"]
        with web_db.connect() as conn:
            row = conn.execute("SELECT id FROM topups WHERE id=? AND discord_id=?",
                               (topup_id, uid)).fetchone()
        if not row:
            raise HTTPException(404, "ไม่พบรายการนี้ของคุณ")
    return FileResponse(str(p), media_type="image/jpeg")


@router.get("/admin/topups")
def list_topups(request: Request, status: str = "pending", q: str = ""):
    """log เติมเงิน — status=all ดูทุกสถานะ, q ค้นหาด้วยเศษ discord_id หรือเลขรายการ"""
    require_admin(request)
    sql = "SELECT * FROM topups"
    where, args = [], []
    if status != "all":
        where.append("status=?")
        args.append(status)
    if q.strip():
        where.append("(discord_id LIKE ? OR CAST(id AS TEXT)=?)")
        args += [f"%{q.strip()}%", q.strip()]
    if where:
        sql += " WHERE " + " AND ".join(where)
    with web_db.connect() as conn:
        rows = conn.execute(sql + " ORDER BY id DESC LIMIT 300", args).fetchall()
        s = conn.execute(
            "SELECT COUNT(*) AS count, "
            "COALESCE(SUM(CASE WHEN status='approved' THEN amount_thb END), 0) AS approved_thb, "
            "COALESCE(SUM(CASE WHEN status='approved' THEN gold END), 0) AS approved_gold "
            "FROM topups").fetchone()
    return {"topups": [dict(r) | {"has_slip": _slip_path(r["id"]).is_file()} for r in rows],
            "summary": dict(s)}


def _decide_topup(topup_id, new_status, note):
    """CAS เปลี่ยนสถานะจาก pending — คืนแถวเดิม; ถูกตัดสินไปแล้ว → 409 (กันอนุมัติ/ทองเข้าซ้ำ)"""
    with web_db.connect() as conn:
        row = conn.execute("SELECT * FROM topups WHERE id=?", (topup_id,)).fetchone()
        if not row:
            raise HTTPException(404, "ไม่พบรายการนี้")
        cur = conn.execute(
            "UPDATE topups SET status=?, decided_at=datetime('now','localtime'), "
            "decided_by='admin', note=? WHERE id=? AND status='pending'",
            (new_status, note, topup_id))
        if cur.rowcount == 0:
            raise HTTPException(409, f"รายการนี้ถูกตัดสินไปแล้ว (สถานะ: {row['status']})")
    return row


@router.post("/admin/topups/{topup_id}/approve")
def approve_topup(topup_id: int, body: DecideBody, request: Request):
    require_admin(request)
    row = _decide_topup(topup_id, "approved", body.note)
    # เพิ่มทองเข้าธนาคารผู้เล่น — จุดเดียวที่เว็บเขียน game_data.db
    gconn = _game_conn(readonly=False)
    try:
        with gconn:
            cur = gconn.execute("UPDATE players SET bank = bank + ? WHERE user_id=?",
                                (row["gold"], int(row["discord_id"])))
        if cur.rowcount == 0:
            # ผู้เล่นหายจากเกม — คืนสถานะ pending ให้แอดมินตามเรื่องต่อ (ทองยังไม่เข้า)
            with web_db.connect() as conn:
                conn.execute("UPDATE topups SET status='pending', decided_at=NULL WHERE id=?",
                             (topup_id,))
            raise HTTPException(400, "ไม่พบผู้เล่นนี้ในเกม — ทองยังไม่ถูกเพิ่ม รายการกลับเป็นรอตรวจ")
    finally:
        gconn.close()
    return {"ok": True, "gold": row["gold"]}


@router.post("/admin/topups/{topup_id}/reject")
def reject_topup(topup_id: int, body: DecideBody, request: Request):
    require_admin(request)
    _decide_topup(topup_id, "rejected", body.note)
    return {"ok": True}
