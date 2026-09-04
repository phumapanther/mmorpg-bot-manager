"""🎭 ห้องปาร์ตี้ — นั่งบนล็อบบี้กลาง (bot/lobby.py)

⚠️ `lobby.MAX_SEATS = 6` เป็นค่าของสนามรบ แต่เจ้าของเกมเคาะว่าปาร์ตี้ 5 คน
   ชั้นนี้จึงต้องดักเอง **ห้ามไปแก้ค่าในล็อบบี้กลาง** — สนามรบใช้อยู่

ไฟล์นี้ไม่รู้จักกติกาการต่อสู้เลย รู้แค่ "ใครนั่งอยู่ในปาร์ตี้ไหน"
กติกาอยู่ที่ engine.py (เฟส 3)
"""
import random

from bot import lobby
from bot.games.party import engine, monsters

GAME = "party"
MAX_PARTY = 5          # เจ้าของเกมเคาะ 2026-09-03
MIN_TO_START = 2


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


def _players_of(st):
    """ดึงค่าสถานะจริงของผู้เล่นแต่ละคนมาลงสมรภูมิ

    ใช้ดาต้าจากเกมหลักทั้งหมด (ชุด · อาวุธ · เลเวล · ธาตุ) ตามที่เจ้าของเกมสั่ง
    ไม่มีตัวละครแยกสำหรับโหมดนี้
    """
    from bot import game_modifiers
    from bot.models import player_model

    out = []
    for seat in st["seats"]:
        p = player_model.get_player(int(seat["uid"])) or {}
        els = game_modifiers.resolve_player_elements([p.get("race") or ""])
        out.append({
            "uid": seat["uid"],
            "name": seat["name"],
            "level": int(p.get("level") or 1),
            "class_name": p.get("class_name"),
            "element": els[0] if els else None,
            "hp": int(p.get("hp") or 100),
            "max_hp": int(p.get("max_hp") or 100),
            "atk": int(p.get("level") or 1) + 8,
            "def": 2,
        })
    return out


def _spawn_battle(st):
    """เกิดมอนแล้วเริ่มสมรภูมิ

    ⚠️ มอนมาจาก adventure_core.spawn_monster ของเกมหลัก ไม่สร้างพันธุ์ใหม่
       (เจ้าของเกมสั่งให้ใช้ดาต้าเดิม) — monsters.spawn_group คุมจำนวนกับบอส
    """
    rng = random.Random()
    players = _players_of(st)
    mons = monsters.spawn_group(int(st["host"]), len(players), rng,
                                boss=bool(st["extra"].get("boss_raid")))
    engine.start_battle(st, players, mons, rng)
    _run_monsters(st, rng)      # มอนที่ไวกว่าผู้เล่นต้องได้เดินก่อน ไม่งั้นเกมค้าง


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
    lobby.save(st["room"], st)
    return True, {"events": evs}


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
            # engine.view คัดค่าลับของมอนออกให้แล้ว (ส่ง hp_pct ไม่ใช่ hp จริง)
            out["battle"] = engine.view(st, uid)
    return out
