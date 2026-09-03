# license_server/api_web/shop.py
"""ร้านค้า/ตลาด/คราฟ/กระเป๋า + ร้านยศ + กาชาแฟชั่น (ย้ายจาก web_api.py 09-02)"""
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from license_server import web_db
from license_server.api_web.deps import _game_conn, _money_now, _user_lock, require_player

router = APIRouter()


class UseBody(BaseModel):
    item_id: str


@router.post("/item/use")
def item_use(body: UseBody, request: Request):
    """ใช้ไอเทมจากกระเป๋า — เรียก apply_item_effect() ตัวเดียวกับปุ่ม 🧪 ในดิส"""
    uid = require_player(request)["uid"]
    from bot import adventure_core
    from core.services.items import apply_item_effect
    with _user_lock(uid):
        ok, msg = apply_item_effect(int(uid), str(body.item_id))
        # แวะกินยาระหว่างสู้ = ยังอยู่กับไฟต์นั้น ต่ออายุให้ ไม่งั้นกลับมาแล้วมอนหายไป
        adventure_core.touch_pending(int(uid))
    return {"ok": ok, "message": msg}


@router.get("/shop/items")
def shop_items(request: Request):
    """ของที่ร้านขาย — กรอง purchasable เหมือนหน้าร้านในดิสเป๊ะ"""
    require_player(request)
    from bot import config_loader
    from core.services.items import usable_kind
    out = [{"id": iid, "name": d.get("name", iid), "buy": int(d.get("buy", 0)),
            "sell": int(d.get("sell", 0)), "type": d.get("type", ""),
            "kind": usable_kind(d), "usable": bool(usable_kind(d))}
           for iid, d in config_loader.get_all_items().items()
           if d.get("purchasable", True)]
    out.sort(key=lambda x: x["buy"])
    return {"items": out}


class ShopBody(BaseModel):
    action: str
    item_id: str
    count: int = 1


@router.post("/shop")
def shop(body: ShopBody, request: Request):
    """ซื้อ/ขายไอเทมกับร้าน — buy_item_for()/sell_item_for() ตัวเดียวกับปุ่มร้านในดิส

    ซื้อได้ทีละหลายชิ้น (จำนวนถูกตรวจซ้ำใน buy_item_for เสมอ — เบราว์เซอร์ส่งอะไรมาก็ไม่เชื่อ)
    """
    uid = require_player(request)["uid"]
    if body.action not in ("buy", "sell"):
        raise HTTPException(400, "ไม่รู้จักคำสั่งนี้")

    from bot import adventure_core
    from core.services.items import buy_item_for, sell_item_for
    with _user_lock(uid):
        if body.action == "buy":
            ok, msg = buy_item_for(int(uid), body.item_id, body.count)
        else:
            ok, msg = sell_item_for(int(uid), body.item_id)
        adventure_core.touch_pending(int(uid))    # แวะซื้อของระหว่างสู้ = ยังอยู่กับไฟต์นั้น
    return {"ok": ok, "message": msg, "money": _money_now(uid)}


@router.get("/market")
def market_list(request: Request):
    """🏪 ตลาดผู้เล่น — แผงขายที่เปิดอยู่ + ของเราที่ฝากขายไว้ + ของในกระเป๋าที่ลงขายได้

    ไม่ส่งไอดีคนขายออกไป (บอกแค่ว่า "ของคุณ" ไหม) — หน้าเว็บไม่มีเหตุผลต้องรู้ว่าใครเป็นใคร
    """
    uid = int(require_player(request)["uid"])
    from bot import config_loader, market
    from core.services.items import usable_kind
    from bot.models.player_model import get_player, load_inventory

    items = config_loader.get_all_items()
    name = lambda i: items.get(str(i), {}).get("name", f"ไอเทม {i}")

    listings = [{"id": lid, "item_id": str(iid), "name": name(iid), "price": int(price),
                 "mine": sid == uid}
                for lid, sid, iid, price in market.open_listings()]
    mine = [{"id": lid, "item_id": str(iid), "name": name(iid), "price": int(price)}
            for lid, iid, price in market.my_listings(uid)]

    # ของในกระเป๋าที่ลงขายได้ — รวมชิ้นซ้ำเป็นแถวเดียวเหมือนหน้ากระเป๋า
    counts = {}
    for i in load_inventory((get_player(uid) or {}).get("inventory", "")):
        counts[str(i)] = counts.get(str(i), 0) + 1
    bag = [{"id": i, "name": name(i), "count": n, "kind": usable_kind(items.get(i, {})),
            "sell": int(items.get(i, {}).get("sell", 0))}
           for i, n in sorted(counts.items(), key=lambda kv: name(kv[0]))]

    cfg = config_loader.get_config().get("market", {})
    return {"enabled": bool(cfg.get("enabled", True)),
            "tax_percent": int(cfg.get("tax_percent", 0) or 0),
            "min_price": int(cfg.get("min_price", 1) or 1),
            "max_price": int(cfg.get("max_price", 10**12) or 10**12),
            "max_listings": int(cfg.get("max_listings_per_player", 5) or 5),
            "listings": listings, "mine": mine, "bag": bag}


class MarketBody(BaseModel):
    action: str
    listing_id: int = 0
    item_id: str = ""
    price: int = 0


@router.post("/market")
def market_action(body: MarketBody, request: Request):
    """ลงขาย / ยกเลิก / ซื้อ — market.py ตัวเดียวกับ !market ในดิส

    เงินกับของทั้งหมดขยับใน transaction เดียวฝั่ง market.py — เว็บไม่แตะเองสักบรรทัด
    (ปิดการขายด้วย compare-and-swap แล้ว สองคนกดซื้อพร้อมกันคนที่สองจะถูกปฏิเสธ)
    """
    uid = int(require_player(request)["uid"])
    if body.action not in ("list", "cancel", "buy"):
        raise HTTPException(400, "ไม่รู้จักคำสั่งนี้")

    from bot import market
    with _user_lock(uid):
        if body.action == "list":
            ok, msg = market.list_item(uid, body.item_id, body.price)
        elif body.action == "cancel":
            ok, msg = market.cancel_listing(uid, body.listing_id)
        else:
            ok, msg = market.buy_listing(uid, body.listing_id)
    if not ok:
        raise HTTPException(400, msg)
    return {"ok": True, "message": msg, "money": _money_now(uid)}


@router.get("/craft/list")
def craft_list(request: Request):
    """สูตรที่วัตถุดิบครบพร้อมคราฟตอนนี้ — craftable_now() ตัวเดียวกับปุ่ม 🔨 ในดิส"""
    uid = require_player(request)["uid"]
    from core.services.crafting import craftable_now
    rows = craftable_now(int(uid))
    return {"recipes": [{"id": i, "name": n, "materials": m} for i, n, m in rows]}


class CraftBody(BaseModel):
    item_id: str


@router.post("/craft")
def craft(body: CraftBody, request: Request):
    """คราฟของ — craft_for() ตัวเดียวกับในดิส (มีโอกาสล้มเหลวตามสูตร)"""
    uid = require_player(request)["uid"]
    from bot import adventure_core
    from core.services.crafting import craft_for
    with _user_lock(uid):
        ok, msg = craft_for(int(uid), str(body.item_id))
        adventure_core.touch_pending(int(uid))    # แวะคราฟระหว่างสู้ = ยังอยู่กับไฟต์นั้น
    return {"ok": ok, "message": msg}


@router.post("/bag/sell-junk")
def sell_junk(request: Request):
    """เทขายวัสดุ/ของขยะทั้งกระเป๋า — sell_all_junk() ตัวเดียวกับปุ่ม 🧱 ในดิส"""
    uid = require_player(request)["uid"]
    from core.services.items import sell_all_junk
    with _user_lock(uid):
        sold, gold, msg = sell_all_junk(int(uid))
    return {"ok": sold > 0, "sold": sold, "gold": gold, "message": msg,
            "money": _money_now(uid)}


@router.get("/bag/junk-preview")
def junk_preview(request: Request):
    """ดูก่อนยืนยันว่าจะขายอะไรไปบ้าง ได้เงินเท่าไหร่

    ใช้เกณฑ์ 'ของขยะ' ชุดเดียวกับ sell_all_junk() — ของกดใช้ได้/อุปกรณ์/ทองคำแท่ง ปลอดภัยเสมอ
    """
    uid = require_player(request)["uid"]
    from bot import config_loader
    from bot.models.player_model import load_inventory

    conn = _game_conn()
    try:
        row = conn.execute("SELECT inventory FROM players WHERE user_id=?", (int(uid),)).fetchone()
    finally:
        conn.close()
    if not row:
        return {"items": [], "gold": 0, "count": 0}

    items = config_loader.get_all_items()
    counts = {}
    for iid in load_inventory(row["inventory"]):
        counts[str(iid)] = counts.get(str(iid), 0) + 1

    out, gold = [], 0
    for iid, n in counts.items():
        d = items.get(iid, {})
        is_junk = (d and not d.get("effect") and not d.get("equip_key")
                   and d.get("type") != "use" and not d.get("bar_value"))
        if not is_junk:
            continue
        each = int(d.get("sell", 0))
        gold += each * n
        out.append({"id": iid, "name": d.get("name", iid), "count": n, "each": each})
    out.sort(key=lambda x: -x["each"] * x["count"])
    return {"items": out, "gold": gold, "count": sum(i["count"] for i in out)}


class DropBody(BaseModel):
    item_id: str
    amount: int = 1


@router.post("/item/drop")
def item_drop(body: DropBody, request: Request):
    """ทิ้งไอเทม — เรียก drop_item_for() ตัวเดียวกับปุ่ม 🗑️ ในดิส (ของหายถาวร)"""
    uid = require_player(request)["uid"]
    if body.amount <= 0:
        raise HTTPException(400, "จำนวนต้องมากกว่า 0")
    from core.services.items import drop_item_for
    with _user_lock(uid):
        ok, msg = drop_item_for(int(uid), str(body.item_id), body.amount)
    return {"ok": ok, "message": msg}


# ─────────────────────────────────────────────────────────────────────────────
# 🛒 ร้านขายยศ + กาชา (เว็บเกม เฟส 7.4)
# เว็บแจกยศ Discord เองไม่ได้ — หักเงินแล้วโยนเข้า role_grant_queue ให้บอทมาแจก
# แจกไม่สำเร็จบอทจะคืนเงินให้เอง (ดู bot/cogs/role_grant_worker.py)
# ─────────────────────────────────────────────────────────────────────────────

_FACTIONS = ("dark", "light")

BOT_OFFLINE = ("🔌 บอทดิสคอร์ดออฟไลน์อยู่ตอนนี้ — ยศต้องให้บอทเป็นคนมอบ "
               "ถ้าซื้อตอนนี้เงินจะหักไปแล้วยศไม่มา ลองใหม่อีกครั้งเมื่อบอทกลับมา")


@router.get("/roleshop")
def roleshop(faction: str, request: Request):
    """รายการยศ + ราคา + ตู้กาชาของฝ่ายนั้น (อ่านอย่างเดียว)"""
    uid = int(require_player(request)["uid"])
    if faction not in _FACTIONS:
        raise HTTPException(400, "ฝ่ายต้องเป็น dark หรือ light")
    from bot import role_shop_core
    return role_shop_core.shop_view(faction, uid) | {"bot_online": web_db.bot_alive()}


class RoleBuyBody(BaseModel):
    faction: str
    value: str = ""
    action: str = "buy"          # buy = ซื้อเจาะจง | gacha = หมุนตู้


def _queue_grant(uid, data):
    with web_db.connect() as conn:
        cur = conn.execute(
            "INSERT INTO role_grant_queue(discord_id, role_id, label, price, kind) "
            "VALUES (?,?,?,?,?)",
            (str(uid), int(data["role_id"]), data["label"], int(data["price"]), data["kind"]))
    return cur.lastrowid


@router.post("/roleshop")
def roleshop_buy(body: RoleBuyBody, request: Request):
    """ซื้อยศ / หมุนกาชา — ตรรกะเดียวกับปุ่มใน !darkshop / !lightshop"""
    uid = int(require_player(request)["uid"])
    if body.faction not in _FACTIONS:
        raise HTTPException(400, "ฝ่ายต้องเป็น dark หรือ light")
    # บอทดับ = ไม่มีใครแจกยศ ต้องกันตั้งแต่ก่อนหักเงิน ไม่ใช่หักแล้วค่อยไปค้างในคิว
    if not web_db.bot_alive():
        raise HTTPException(503, BOT_OFFLINE)
    from bot import role_shop_core

    with _user_lock(uid):
        if body.action == "gacha":
            ok, data = role_shop_core.prepare_gacha(uid, body.faction)
        elif body.action == "buy":
            ok, data = role_shop_core.prepare_buy(uid, body.faction, body.value)
        else:
            raise HTTPException(400, "ไม่รู้จักแอคชั่นนี้")
        if not ok:
            raise HTTPException(400, data["error"])
        ticket = _queue_grant(uid, data)

    return {"ok": True, "ticket": ticket, "kind": data["kind"], "label": data["label"],
            "price": data["price"], "money": _money_now(uid),
            "text": ("🎲 หมุนกาชาแล้ว! บอทกำลังนำยศไปมอบให้ในดิสคอร์ด"
                     if data["kind"] == "gacha" else
                     "🎉 ซื้อสำเร็จ! บอทกำลังนำยศไปมอบให้ในดิสคอร์ด")}


@router.get("/roleshop/ticket/{ticket_id}")
def roleshop_ticket(ticket_id: int, request: Request):
    """เช็คว่าบอทแจกยศให้แล้วหรือยัง — หน้าเว็บถามซ้ำจนกว่าจะไม่ pending"""
    uid = str(require_player(request)["uid"])
    with web_db.connect() as conn:
        row = conn.execute("SELECT * FROM role_grant_queue WHERE id=? AND discord_id=?",
                           (ticket_id, uid)).fetchone()
    if not row:
        raise HTTPException(404, "ไม่พบรายการนี้")
    return {"status": row["status"], "label": row["label"], "kind": row["kind"],
            "note": row["note"] or "", "money": _money_now(int(uid))}


@router.get("/fashion/gacha")
def fashion_gacha(request: Request):
    """🎁 หน้าตู้กาชาแฟชั่น — ปุ่มหมุน เรท ของหน้าตู้ อัญมณีที่มี"""
    uid = int(require_player(request)["uid"])
    from bot import fashion
    return fashion.gacha_view(uid)


class GachaBody(BaseModel):
    action: str = "pull"   # pull | exchange
    tier: str = ""         # ปุ่มหมุน (ตอน pull)
    key: str = ""          # รหัสแฟชั่นที่จะแลก (ตอน exchange)


@router.post("/fashion/gacha")
def fashion_gacha_go(body: GachaBody, request: Request):
    """หมุนกาชา / แลกอัญมณี — หักทองกับสุ่มอยู่ใต้ล็อกเดียวกัน กดรัวสองจอไม่ได้ของฟรี"""
    uid = int(require_player(request)["uid"])
    from bot import fashion
    with _user_lock(uid):
        if body.action == "exchange":
            ok, msg = fashion.exchange(uid, body.key)
            if not ok:
                raise HTTPException(400, msg)
            return {"ok": True, "message": msg} | fashion.gacha_view(uid)
        if body.action != "pull":
            raise HTTPException(400, "ไม่รู้จักคำสั่งนี้")
        ok, r = fashion.pull(uid, body.tier)
    if not ok:
        raise HTTPException(400, r["error"])
    return r | {"money": _money_now(uid)}
