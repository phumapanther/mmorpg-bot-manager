"""💰 UNO เดิมพัน — โต๊ะหลายคนบนล็อบบี้กลาง

เจ้าของเกมเคาะ (09-02):
  - เล่นกับบอท "ไม่ได้เงิน" — ปิดช่องฟอกทองสนิท
  - ที่ 1 กินเรียบ · ออกกลางเกมเสียเงิน · ยุบก่อนเริ่มคืนครบ

⚠️ กฎเหล็ก: ทองรวมในระบบต้องเท่าเดิมเป๊ะทุกกรณี
   เงินขยับแค่ 2 จุด — ตอนเข้าโต๊ะ (หัก) กับตอนจบเกม (จ่าย)
"""
from bot import lobby
from bot.cards import uno_deck
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
        # เกมเริ่มแล้วและนี่คือคนสุดท้ายที่เหลือ — ไม่มีคู่แข่งให้ชนะแล้ว
        # ต้องจ่าย pot คืนให้เขา *ก่อน* lobby.leave() ลบห้องทิ้ง ไม่งั้นเงินหายถาวร
        if started and len(st["seats"]) == 1:
            _payout(st, str(uid))
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


def _act(uid, fn):
    """ทำท่าหนึ่งของคนจริงในห้อง — ประตูเดียวคุมทุกท่า คืน (ok, ผล)

    ต่างจาก uno_table._act ตรงที่ห้องนี้มีคนจริงหลายคน — ต้องเช็คว่า
    คนที่ส่งคำสั่งมาเป็นเจ้าของตาปัจจุบันจริงไหม ไม่งั้นคนอื่นสั่งแทนกันได้
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
    me = seats.index(str(uid))
    if game["turn"] != me:
        return False, {"error": "ยังไม่ถึงตาคุณ"}
    if me in game.get("finished", []):
        return False, {"error": "คุณทิ้งไพ่หมดแล้ว — นั่งดูเพื่อนเล่นจนจบ"}

    ok, r = fn(game)
    if not ok:
        return False, r
    lobby.save(st["room"], st)
    if game.get("over"):
        winner_uid = seats[game["winner"]]
        _payout(st, winner_uid)
    return True, {**r, "table": view(uid)}


def play(uid, index, suit=None, rng=None):
    return _act(uid, lambda game: uno_engine.play(game, int(index), chosen_suit=suit, rng=rng))


def draw(uid, rng=None):
    return _act(uid, lambda game: uno_engine.draw(game, rng))


def take_stack(uid, rng=None):
    return _act(uid, lambda game: uno_engine.take_stack(game, rng))


def passes(uid, rng=None):
    return _act(uid, lambda game: uno_engine.passes(game))


def say_uno(uid):
    """ร้อง UNO — ไม่ต้องรอตาตัวเอง (กฎเดียวกับโหมดบอท)"""
    st = _room(uid)
    if not st:
        return False, {"error": "ยังไม่ได้อยู่ห้องไหน"}
    game = st["extra"].get("game")
    if not game:
        return False, {"error": "เกมยังไม่เริ่ม"}
    seats = [s["uid"] for s in st["seats"]]
    if str(uid) not in seats:
        return False, {"error": "คุณไม่ได้อยู่ห้องนี้"}
    ok, r = uno_engine.say_uno(game, seats.index(str(uid)))
    if not ok:
        return False, r
    lobby.save(st["room"], st)
    return True, {**r, "table": view(uid)}


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
    # ไพ่บนสุดกอง = ข้อมูลสาธารณะ ทุกคนเห็นบนโต๊ะจริงอยู่แล้ว ไม่ใช่ของลับ
    # ส่งรูปทรงเดียวกับไพ่ในมือ {"suit","value"} ให้หน้าเว็บ render ด้วยโค้ดเดียวกันได้
    out["top"] = game["pile"][-1] if game["pile"] else None
    out["over"] = bool(game.get("over"))
    out["winner"] = game.get("winner")
    # ⚠️ ไพ่ในมือตัวเองส่งผ่าน out["hand"] ที่เดียว (รูปทรงเดียวกับ uno_table.view())
    #    เคยใส่ซ้ำที่ seat["hand"] ด้วย — got_cards() เดินนับสองครั้งจนดูเหมือนไพ่หลุด
    for i, seat in enumerate(out["seats"]):
        seat["cards"] = len(game["players"][i]["hand"])
        seat["said_uno"] = game["players"][i]["said_uno"]

    # 🔁 ต่อยอดรูปทรงเดียวกับ uno_table.view() — หน้าเว็บใช้โค้ดวาดไพ่ตัวเดียวกันได้เลย
    #    (โหมดบอทมีแค่คนจริงคนเดียว ที่นี่มีหลายคน — me เป็น None ถ้าเรานั่งดูอยู่นอกที่)
    out["playing"] = True
    # unoSeats() ในหน้าเว็บวาดที่นั่งคนอื่นจาก "players" (รูปทรงเดียวกับโหมดบอท)
    # ต่างจาก out["seats"] ของล็อบบี้กลาง (มี uid/host) — คนละหน้าที่กัน
    out["players"] = [{"name": p["name"], "cards": len(p["hand"]),
                        "you": i == me, "said_uno": p["said_uno"]}
                       for i, p in enumerate(game["players"])]
    out["hand"] = game["players"][me]["hand"] if me is not None else []
    out["playable"] = ([i for i, c in enumerate(game["players"][me]["hand"])
                         if c in uno_engine.playable_now(game, me)]
                        if me is not None and game["turn"] == me else [])
    out["top_label"] = uno_deck.label(out["top"]) if out["top"] else None
    out["suits"] = {k: v["label"] for k, v in uno_deck.SUITS.items()}
    out["my_turn"] = (me is not None and game["turn"] == me and not game.get("over")
                       and me not in game.get("finished", []))
    out["stack"] = game["stack"]
    out["stack_kind"] = game["stack_kind"]
    out["must_answer"] = (uno_engine.must_answer_stack(game)
                           and me is not None and game["turn"] == me)
    out["drew"] = game["drew"]
    out["deck_left"] = len(game["deck"])
    out["finished"] = [{"name": game["players"][i]["name"], "place": k + 1,
                         "you": i == me,
                         "left": sum(uno_deck.points(c) for c in game["players"][i]["hand"])}
                        for k, i in enumerate(game.get("finished", []))]
    out["my_place"] = (game["finished"].index(me) + 1
                        if me is not None and me in game.get("finished", []) else 0)
    out["winner_name"] = (game["players"][game["winner"]]["name"]
                           if game.get("winner") is not None else "")
    out["score"] = uno_engine.score(game)
    out["log"] = game["log"][-12:]
    return out
