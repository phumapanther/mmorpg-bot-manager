"""💰 UNO เดิมพัน — โต๊ะหลายคนบนล็อบบี้กลาง

เจ้าของเกมเคาะ (09-02):
  - เล่นกับบอท "ไม่ได้เงิน" — ปิดช่องฟอกทองสนิท
  - ที่ 1 กินเรียบ · ออกกลางเกมเสียเงิน · ยุบก่อนเริ่มคืนครบ

⚠️ กฎเหล็ก: ทองรวมในระบบต้องเท่าเดิมเป๊ะทุกกรณี
   เงินขยับแค่ 2 จุด — ตอนเข้าโต๊ะ (หัก) กับตอนจบเกม (จ่าย)
"""
from bot import lobby
from bot.cards import uno_engine
from bot.models import player_model

GAME = "uno"
MIN_PLAYERS = 2


def _room(uid):
    code = lobby.room_of(GAME, uid)
    return lobby.load(code) if code else None


def open_table(uid, name, bet):
    """เปิดโต๊ะ — หักเงินทันทีตอนเข้า กันคนวางเงินแล้วไม่มีจ่าย"""
    bet = int(bet or 0)
    if bet < 0:
        return False, {"error": "❌ เดิมพันติดลบไม่ได้"}
    if bet and not _take(uid, bet):
        return False, {"error": "❌ เงินในกระเป๋าของคุณไม่พอ!"}
    st = lobby.create(GAME, uid, {"uid": str(uid), "name": name, "paid": bet},
                      {"bet": bet, "pot": bet, "paid_out": False})
    return True, lobby.save(st["room"], st)


def _take(uid, amount):
    """หักเงิน — คืน False ถ้าไม่พอ (เช็คก่อนหักเสมอ ห้ามติดลบ)"""
    p = player_model.get_player(uid)
    if not p or p.get("cash", 0) < amount:
        return False
    player_model.increment_player_field(uid, "cash", -amount)
    return True


def sit(uid, name, code):
    """เข้าห้องด้วยรหัส — หักเงินเดิมพันเท่ากับที่หัวห้องตั้งไว้ก่อนเข้า"""
    st = lobby.load(str(code or "").strip().upper())
    if not st or st.get("game") != GAME:
        return False, {"error": "❌ ไม่มีห้องรหัสนี้ — เช็ครหัสอีกทีนะ"}
    bet = st["extra"].get("bet", 0)
    already_in = any(s["uid"] == str(uid) for s in st["seats"])
    if bet and not already_in and not _take(uid, bet):
        return False, {"error": "❌ เงินในกระเป๋าของคุณไม่พอ!"}
    ok, got = lobby.join(GAME, uid, code, {"uid": str(uid), "name": name, "paid": bet})
    if not ok:
        if bet and not already_in:
            player_model.increment_player_field(uid, "cash", bet)   # เข้าไม่ได้ต้องคืนเงิน
        return False, got
    if bet and not already_in:
        got["extra"]["pot"] = got["extra"].get("pot", 0) + bet
        got = lobby.save(got["room"], got)
    return True, got


def stand(uid):
    """ออกจากห้อง — ยังไม่เริ่ม = คืนเงินที่จ่ายไป · เริ่มแล้ว = ไม่คืน (ค้างกองกลาง)"""
    code = lobby.room_of(GAME, uid)
    if not code:
        return None
    st = lobby.load(code)
    started = bool(st and st.get("started"))
    paid = 0
    if st:
        mine = next((s for s in st["seats"] if s["uid"] == str(uid)), None)
        paid = mine.get("paid", 0) if mine else 0
    result = lobby.leave(GAME, uid)
    if not started and paid:
        player_model.increment_player_field(uid, "cash", paid)
        if result:
            result["extra"]["pot"] = max(0, result["extra"].get("pot", 0) - paid)
            result = lobby.save(result["room"], result)
    return result


def begin(uid):
    """เริ่มเกม — ต้องมีคนจริง ≥ 2 คน · มีบอทร่วมโต๊ะ = ปิดเดิมพัน (กันฟอกทอง)"""
    st = _room(uid)
    if not st:
        return False, {"error": "ยังไม่ได้อยู่ห้องไหน"}
    if st["host"] != str(uid):
        return False, {"error": "เฉพาะหัวห้องเท่านั้นที่เริ่มเกมได้"}
    real_players = [s for s in st["seats"] if not s.get("bot")]
    if len(real_players) < MIN_PLAYERS:
        return False, {"error": f"ต้องมีคนจริงอย่างน้อย {MIN_PLAYERS} คนถึงจะเริ่มได้"}
    if any(s.get("bot") for s in st["seats"]):
        st["extra"]["bet"] = 0     # มีบอทในโต๊ะ → เดิมพันเป็น 0 อัตโนมัติ กันฟอกทอง

    names = [s["name"] for s in st["seats"]]
    game = uno_engine.new_game(names)
    st["extra"]["game"] = game
    st["started"] = True
    return True, lobby.save(st["room"], st)


def _payout(st, winner_uid):
    """จ่ายกองกลางให้ที่ 1 — จ่ายได้ครั้งเดียวเท่านั้น

    เน็ตกระตุกแล้วเบราว์เซอร์ยิงซ้ำ ต้องไม่ได้เงินสองรอบ
    """
    if not st or st["extra"].get("paid_out"):
        return
    st["extra"]["paid_out"] = True
    pot = st["extra"].get("pot", 0)
    if pot:
        player_model.increment_player_field(winner_uid, "cash", pot)
        st["extra"]["pot"] = 0
    lobby.save(st["room"], st)


def view(uid):
    """ห้อง UNO พร้อมแสดงผลบนเว็บ

    🔒 ประตูเดียว — ต่อยอดจาก lobby.view() เติมไพ่ในมือ "ตัวเองเท่านั้น"
       ห้ามส่งไพ่ในมือคนอื่นลงเบราว์เซอร์แม้ใบเดียว
    """
    out = lobby.view(GAME, uid)
    st = _room(uid)
    if not st:
        return out
    out["bet"] = st["extra"].get("bet", 0)
    out["pot"] = st["extra"].get("pot", 0)
    game = st["extra"].get("game")
    if not game:
        return out
    seats = [s["uid"] for s in st["seats"]]
    me = seats.index(str(uid)) if str(uid) in seats else None
    out["turn"] = game["turn"]
    out["dir"] = game["dir"]
    out["suit"] = game["suit"]
    top = game["pile"][-1] if game["pile"] else None
    # ไพ่บนสุดกอง = ข้อมูลสาธารณะ (ทุกคนเห็นบนโต๊ะจริงอยู่แล้ว) ไม่ใช่ของลับ
    # ส่งเป็น top_suit/top_value แยกคีย์ ไม่ใช่ dict {suit,value} เพื่อไม่ให้ปนกับ
    # ตัวตรวจ "ไพ่คนอื่นหลุด" ที่จับรูปทรงไพ่ล้วน ๆ (เทสยึดรูปทรงนี้เป็นสัญญา)
    out["top_suit"] = top["suit"] if top else None
    out["top_value"] = top["value"] if top else None
    out["over"] = bool(game.get("over"))
    out["winner"] = game.get("winner")
    for i, seat in enumerate(out["seats"]):
        hand = game["players"][i]["hand"]
        seat["cards"] = len(hand)
        seat["said_uno"] = game["players"][i]["said_uno"]
        if i == me:
            seat["hand"] = hand
    return out
