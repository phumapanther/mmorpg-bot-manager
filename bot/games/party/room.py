"""🎭 ห้องปาร์ตี้ — นั่งบนล็อบบี้กลาง (bot/lobby.py)

⚠️ `lobby.MAX_SEATS = 6` เป็นค่าของสนามรบ แต่เจ้าของเกมเคาะว่าปาร์ตี้ 5 คน
   ชั้นนี้จึงต้องดักเอง **ห้ามไปแก้ค่าในล็อบบี้กลาง** — สนามรบใช้อยู่

ไฟล์นี้ไม่รู้จักกติกาการต่อสู้เลย รู้แค่ "ใครนั่งอยู่ในปาร์ตี้ไหน"
กติกาอยู่ที่ engine.py (เฟส 3)
"""
import random

from bot import lobby
from bot.games.party import engine, monsters, rewards

GAME = "party"
MAX_PARTY = 5          # เจ้าของเกมเคาะ 2026-09-03
MIN_TO_START = 2
REST_AT = 0.25         # เลือดต่ำกว่านี้ต้องไปพักก่อน ถึงจะออกเดินทางต่อได้


def _room(uid):
    code = lobby.room_of(GAME, uid)
    return lobby.load(code) if code else None


def _seat(uid, name):
    return {"uid": str(uid), "name": str(name or "ผู้เล่น")}


def open_party(uid, name):
    """เปิดปาร์ตี้ใหม่ — คนเปิดเป็นหัวห้องและนั่งที่แรกทันที"""
    st = lobby.create(GAME, uid, _seat(uid, name), {"phase": "lobby"})
    return True, st


def join_party(uid, name, code):
    """เข้าปาร์ตี้ด้วยรหัส — คืน (ok, ห้อง|ข้อความผิดพลาด)

    คนที่มีที่นั่งอยู่แล้วกลับเข้ามาได้เสมอ แม้ปาร์ตี้จะเต็ม
    (สเปกข้อ 4: หลุดแล้วกลับเข้ามาได้จนกว่าปาร์ตี้จะยุบ)
    """
    st = lobby.load(str(code or "").strip().upper())
    if st and st.get("game") == GAME:
        already = any(s["uid"] == str(uid) for s in st["seats"])
        if not already and len(st["seats"]) >= MAX_PARTY:
            return False, {"error": f"🚪 ปาร์ตี้เต็มแล้ว (สูงสุด {MAX_PARTY} คน)"}
    return lobby.join(GAME, uid, code, _seat(uid, name))


def leave_party(uid):
    """ออกจากปาร์ตี้ — หัวห้องออกก็ยกให้คนถัดไป (ล็อบบี้กลางจัดการให้)"""
    return lobby.leave(GAME, uid)


def begin(uid, boss_raid=False):
    """หัวห้องกดเริ่ม — ต้องมีอย่างน้อย 2 คน

    boss_raid=True → เจอบอส 1 ตัว + ลูกน้อง แทนมอนธรรมดาทั้งกลุ่ม
    """
    st = _room(uid)
    if not st:
        return False, {"error": "ยังไม่ได้อยู่ปาร์ตี้ไหน"}
    if st["host"] != str(uid):
        return False, {"error": "เฉพาะหัวห้องเท่านั้นที่เริ่มได้"}
    if len(st["seats"]) < MIN_TO_START:
        return False, {"error": f"ต้องมีอย่างน้อย {MIN_TO_START} คนถึงจะเริ่มได้"}
    st["started"] = True
    st["extra"]["phase"] = "battle"
    st["extra"]["boss_raid"] = bool(boss_raid)
    _spawn_battle(st)
    return True, lobby.save(st["room"], st)


def again(uid):
    """จบสมรภูมิแล้วออกเดินทางต่อกับปาร์ตี้เดิม — เฉพาะหัวห้อง

    ⚠️ ต้องล้าง `paid` กับ `reward` ของเก่าให้หมด ไม่งั้นรอบใหม่ไม่จ่ายรางวัล
       (settle เห็นธง paid ค้างอยู่ก็ข้ามไปเลย)
    """
    st = _room(uid)
    if not st:
        return False, {"error": "ยังไม่ได้อยู่ปาร์ตี้ไหน"}
    if st["host"] != str(uid):
        return False, {"error": "เฉพาะหัวห้องเท่านั้นที่พาออกเดินทางต่อได้"}
    b = st["extra"].get("battle")
    if not b or not b.get("over"):
        return False, {"error": "สมรภูมิยังไม่จบ"}

    # ⚠️ เลือดติดตัวข้ามรอบ (ดู _carry_hp) — ออกเดินทางต่อทั้งที่เลือดแดง
    #    คือแพ้ฟรีตั้งแต่ตายังไม่ทันเดิน ต้องกันไว้ ไม่ใช่ปล่อยให้กดแล้วงง
    weak = [p for p in _players_of(st) if p["hp"] < p["max_hp"] * REST_AT]
    if weak:
        who = " · ".join(p["name"] for p in weak)
        return False, {"error": f"🩸 เลือดน้อยเกินไป ({who}) — "
                                "ไปพักที่เมืองก่อนค่อยออกเดินทางต่อ"}

    st["extra"].pop("battle", None)
    st["extra"].pop("reward", None)
    st["extra"]["paid"] = False
    _spawn_battle(st)
    return True, lobby.save(st["room"], st)


def _players_of(st):
    """ดึงค่าสถานะจริงของผู้เล่นแต่ละคนมาลงสมรภูมิ

    ใช้ดาต้าจากเกมหลักทั้งหมด (ชุด · อาวุธ · เลเวล · ธาตุ) ตามที่เจ้าของเกมสั่ง
    ไม่มีตัวละครแยกสำหรับโหมดนี้
    """
    from bot import config_loader, game_modifiers
    from bot.models import player_model

    out = []
    for seat in st["seats"]:
        p = player_model.get_player(int(seat["uid"])) or {}
        els = game_modifiers.resolve_player_elements([p.get("race") or ""])
        atk, max_hp = gear_stats(p)
        out.append({
            "uid": seat["uid"],
            "name": seat["name"],
            "level": int(p.get("level") or 1),
            "class_name": p.get("class_name"),
            "element": els[0] if els else None,
            "hp": min(int(p.get("hp") or 100), max_hp),
            "max_hp": max_hp,
            "atk": atk,
            "def": 2,
        })
    return out


def gear_stats(p):
    """พลังโจมตีกับเลือดสูงสุด **ตามสูตรเกมหลักเป๊ะ ๆ** — คืน (atk, max_hp)

    ⚠️ เลือดสูงสุดจริง = max_hp ในฐานข้อมูล **บวกโบนัสจากชุด**
       เฟส 2-7 อ่านแต่ max_hp ดิบ คนใส่ชุดดีเลยขึ้น "320/220"
       (เจ้าของเกมเจอตอนเทสด้วยมือ 2026-09-04) ที่แย่กว่านั้นคือ
       ฮีลใช้ min(hp_max, ...) → ฮีลแล้วเลือด **ลด** จาก 320 เหลือ 220

    ⚠️ ชุด/อาวุธพังแล้ว (dur = 0) ไม่ให้ค่าอะไรเลย — เหมือนเกมหลัก
    """
    from bot import config_loader

    w = config_loader.get_weapon_stats(p.get("weapon") or "Wooden_Weapon") or {}
    a = config_loader.get_armor_stats(p.get("armor") or "None") or {}
    atk = int(w.get("atk", 0) or 0) if int(p.get("weapon_dur") or 0) > 0 else 0
    hp_bonus = int(a.get("hp", 0) or 0) if int(p.get("armor_dur") or 0) > 0 else 0
    return max(1, atk), max(1, int(p.get("max_hp") or 100) + hp_bonus)


def _spawn_battle(st):
    """เกิดมอนแล้วเริ่มสมรภูมิ

    ⚠️ มอนมาจาก adventure_core.spawn_monster ของเกมหลัก ไม่สร้างพันธุ์ใหม่
       (เจ้าของเกมสั่งให้ใช้ดาต้าเดิม) — monsters.spawn_group คุมจำนวนกับบอส
    """
    rng = random.Random()
    players = _players_of(st)
    lv = max(1, sum(int(p.get("level") or 1) for p in players) // max(1, len(players)))
    mons = monsters.spawn_group(int(st["host"]), len(players), rng,
                                boss=bool(st["extra"].get("boss_raid")), level=lv)
    engine.start_battle(st, players, mons, rng)
    # มอนที่ไวกว่าผู้เล่นต้องได้เดินก่อน ไม่งั้นเกมค้าง
    _record(st, _run_monsters(st, rng))


def _record(st, evs):
    """เก็บเหตุการณ์ล่าสุดไว้ให้คนที่ยังไม่ได้กดอะไรเห็นด้วย

    ⚠️ ไม่มีตรงนี้ คนที่นั่งรอจะเห็นแค่เลือดเปลี่ยนวูบ ไม่รู้ว่าใครทำอะไร
       (เจอตอนเทสด้วยมือ 2026-09-04)
    """
    if not evs:
        return
    b = st["extra"]["battle"]
    b["seq"] = int(b.get("seq") or 0) + 1
    b["recent"] = list(evs)[-40:]


def _run_monsters(st, rng):
    """ให้มอนเดินจนกว่าจะถึงตาผู้เล่น (หรือเกมจบ)

    ⚠️ ต้องเรียกทั้งตอนเริ่มสมรภูมิและหลังผู้เล่นสั่งเสร็จ
       เพราะคิวเทิร์นเรียงตามความไว — **มอนอาจได้ไปก่อนผู้เล่น**
       ถ้าไม่เดินให้ตั้งแต่เริ่ม เกมจะค้างรอมอนที่ไม่มีใครสั่ง (เจอตอนเทสจริง)
    """
    b = st["extra"]["battle"]
    evs = []
    guard = 0
    while not b["over"] and guard < 30:
        who = engine.current_actor(st)
        if b["units"][who]["side"] != "monster":
            break
        evs += engine.monster_turn(st, rng)
        guard += 1
    return evs


def act(uid, action, target=None):
    """ผู้เล่นสั่งท่าในสมรภูมิ — บันทึกผลลงห้องทุกครั้ง

    หลังผู้เล่นเดินเสร็จ ถ้าถึงตามอนก็ให้มอนเดินต่อทันที
    (ไม่ต้องรอ poll รอบถัดไป — ผู้เล่นจะได้เห็นผลรวดเดียว)
    """
    st = _room(uid)
    if not st:
        return False, {"error": "ยังไม่ได้อยู่ปาร์ตี้ไหน"}
    if not st.get("extra", {}).get("battle"):
        return False, {"error": "ยังไม่ได้เริ่มสมรภูมิ"}

    rng = random.Random()
    ok, r = engine.act(st, uid, action, target, rng)
    if not ok:
        return False, r

    evs = list(r["events"]) + _run_monsters(st, rng)
    _record(st, evs)
    settle(st)                          # จบแล้วจ่ายทันที (กันจ่ายซ้ำอยู่ในนั้น)
    lobby.save(st["room"], st)
    return True, {"events": evs}


def _tick(st):
    """เดินเวลาให้สมรภูมิ — คืน True ถ้ามีอะไรเปลี่ยนจนต้องเซฟ

    หมดเวลาผู้เล่น → บอทเล่นแทน แล้วปล่อยมอนเดินต่อจนถึงตาคนถัดไป
    """
    rng = random.Random()
    evs = engine.timeout_act(st, rng)
    if not evs:
        return False
    _record(st, evs + _run_monsters(st, rng))
    settle(st)
    return True


def _carry_hp(b):
    """เลือดที่เหลือหลังสมรภูมิ เขียนกลับเข้าตัวละครจริง

    ⚠️ ไม่เขียนกลับ = สู้ปาร์ตี้ไม่มีต้นทุนอะไรเลย เลือดเต็มทุกรอบ
       พอมีปุ่ม "ออกเดินทางอีกครั้ง" ก็กลายเป็นก๊อกทองไม่รู้จบ
    ⚠️ ไม่ให้ต่ำกว่า 1 — ล้มในโหมดนี้ไม่ควรทำให้ตัวละครหลักตายไปด้วย
       (โหมดนี้เป็นของแถม ไม่ควรมีโทษหนักกว่าเกมหลัก)
    """
    from bot.models import player_model
    for u in b["units"].values():
        if u["side"] != "party" or not u.get("uid"):
            continue
        try:
            player_model.update_player_field(
                int(u["uid"]), "hp", max(1, int(u["hp"])))
        except Exception as e:
            print(f"⚠️ [party] เขียนเลือดกลับไม่ได้ uid={u.get('uid')}: {e}")


def settle(st):
    """จ่ายรางวัลตอนจบสมรภูมิ — **จ่ายได้ครั้งเดียวเท่านั้น**

    ⚠️ ธง `paid` คือด่านกันพิมพ์เงิน หน้าเว็บ poll ทุก 2 วิ และ act() ก็เรียกซ้ำ
       ไม่มีธงนี้ = ทองงอกทุกครั้งที่รีเฟรช (ล็อบบี้ UNO เคยเจอบั๊กทำนองนี้)

    จ่ายเฉพาะตอน **ปาร์ตี้ชนะ** — แพ้หรือหนีไม่ได้อะไร
    (ไม่งั้นฟาร์มด้วยการเปิดห้องแล้วกดหนีรัว ๆ ได้)
    """
    b = st.get("extra", {}).get("battle")
    if not b or not b.get("over") or st["extra"].get("paid"):
        return st["extra"].get("reward")
    st["extra"]["paid"] = True          # ตั้งก่อนจ่าย กันเรียกซ้อนกัน
    _carry_hp(b)                        # เลือดที่เหลือติดตัวกลับไปเกมหลัก
    if b.get("winner") != "party":
        st["extra"]["reward"] = None
        lobby.save(st["room"], st)
        return None

    mons = [u for u in b["units"].values() if u["side"] == "monster"]
    uids = [u["uid"] for u in b["units"].values() if u["side"] == "party"]
    st["extra"]["reward"] = rewards.pay(uids, mons, random.Random())
    lobby.save(st["room"], st)
    return st["extra"]["reward"]


def view(uid):
    """🔒 ประตูเดียวก่อนส่งขึ้นเบราว์เซอร์

    ตอนนี้ยังไม่มีของลับให้ซ่อน (ยังไม่มีสมรภูมิ) แต่ทุกอย่างต้องผ่านที่นี่
    ตั้งแต่แรก — เฟส 3 จะมีค่าลับของมอนมาเพิ่ม
    """
    out = lobby.view(GAME, uid)
    st = _room(uid)
    if st:
        out["max"] = MAX_PARTY                       # ทับค่า 6 ของล็อบบี้กลาง
        out["phase"] = st["extra"].get("phase", "lobby")
        if st["extra"].get("battle"):
            # ⏱️ คนที่ยังเปิดจออยู่เป็นคนเดินนาฬิกาให้ — หมดเวลาแล้วบอทเล่นแทน
            #    (ไม่มีตรงนี้ คน AFK คนเดียวค้างทั้งปาร์ตี้ ไม่มีใครปลด)
            #    ทุกคนหลุดหมดก็ไม่มีใคร poll = ไม่มีอะไรต้องเดิน
            if _tick(st):
                lobby.save(st["room"], st)
            # engine.view คัดค่าลับของมอนออกให้แล้ว (ส่ง hp_pct ไม่ใช่ hp จริง)
            out["battle"] = engine.view(st, uid)
            settle(st)                  # จบตอนตามอนก็ต้องได้รางวัล ไม่ต้องรอกดอะไร
            out["reward"] = st["extra"].get("reward")
    return out
