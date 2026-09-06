"""🎭 ห้องปาร์ตี้ — นั่งบนล็อบบี้กลาง (bot/lobby.py)

⚠️ `lobby.MAX_SEATS = 6` เป็นค่าของสนามรบ แต่เจ้าของเกมเคาะว่าปาร์ตี้ 5 คน
   ชั้นนี้จึงต้องดักเอง **ห้ามไปแก้ค่าในล็อบบี้กลาง** — สนามรบใช้อยู่

ไฟล์นี้ไม่รู้จักกติกาการต่อสู้เลย รู้แค่ "ใครนั่งอยู่ในปาร์ตี้ไหน"
กติกาอยู่ที่ engine.py (เฟส 3)
"""
import random
import time

from bot import lobby
from bot.games.party import (disaster, dungeon, encounter, engine, events,
                             journey, monsters, npc, rewards, treasure, village)

# 🎲 เหตุการณ์ที่ไม่ใช่การต่อสู้ — ทุกโมดูลหน้าตาเหมือนกัน (start · options · act · bot_pick)
#    เพิ่มเหตุการณ์ใหม่ = เขียนโมดูลแล้วเติมบรรทัดเดียวตรงนี้ ไม่ต้องแก้ if/else ที่ไหนอีก
EVENT_MODS = {"village": village, "treasure": treasure,
              "trap": disaster, "npc": npc}      # "trap" = ภัยพิบัติ (ชื่อตามเกมหลัก)

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
        # ⚠️ สองเคสนี้ต้องแยกให้ขาด **นี่คือจุดที่พังง่ายที่สุด**
        #    "มีที่นั่งอยู่แล้ว" = เน็ตหลุดแล้วกลับมา → ผ่านเสมอ (สเปกข้อ 4 · เฟส 6)
        #    "ไม่มีที่นั่ง"      = คนใหม่ → ห้ามเข้าระหว่างเดินทาง (เจ้าของเกมเคาะข้อ 7)
        #    เผลอห้ามรวดเดียวเมื่อไหร่ = ทับฟีเจอร์กลับเข้าห้องของเฟส 6 ทันที
        if already:
            # 🔌 มีที่นั่งอยู่แล้ว = เน็ตหลุดแล้วกลับมา — ผ่านเลย ไม่ต้องผ่านล็อบบี้กลาง
            #
            # ⚠️ `lobby.join` บล็อกห้องที่ "เริ่มเล่นแล้ว" ไว้ทุกกรณี ซึ่งถูกสำหรับ UNO
            #    แต่กับปาร์ตี้แปลว่า **คนที่เน็ตหลุดกลางสมรภูมิกลับเข้ามาไม่ได้เลย**
            #    (เฟส 6 บอกว่าทำได้ แต่เทสตอนนั้นทดสอบแค่ตอนอยู่ในล็อบบี้ จับไม่ได้)
            return True, st
        if not already:
            if st.get("started"):
                rnd = int((st.get("extra") or {}).get("round") or 1)
                return False, {"error": f"🧭 ปาร์ตี้นี้ออกเดินทางไปแล้ว (รอบที่ {rnd}) "
                                        "— รอให้การเดินทางนี้จบก่อนนะ"}
            if len(st["seats"]) >= MAX_PARTY:
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
    # 🧭 รอบการเดินทาง — 1 เหตุการณ์ = 1 รอบ (เจ้าของเกมเคาะ 2026-09-04)
    #    ยิ่งรอบสูง มอนยิ่งแรง ทอง/EXP/ดรอปยิ่งดี · ตายยกทีมกลับมารอบ 1
    #    ห้องว่างหมดแล้วห้องถูกลบทิ้ง รอบจึงหายไปเอง ไม่ต้องล้างเพิ่ม
    st["extra"]["round"] = 1
    st["extra"]["score"] = {}  # ตารางอันดับเริ่มนับใหม่ทุกการเดินทาง
    st["extra"].pop("last_kind", None)
    st["extra"].pop("party_fx", None)      # สถานะติดลบมีอายุแค่การเดินทางเดียว
    dungeon.clear(st)
    _heal_full(st)             # ออกเดินทางครั้งใหม่ = ฟื้นเต็ม (เฉพาะที่นี่เท่านั้น)
    _next_encounter(st)
    return True, lobby.save(st["room"], st)


def _round_over(st):
    """รอบนี้จบหรือยัง — เป็นได้ทั้งสมรภูมิและเหตุการณ์อื่น"""
    ev = st["extra"].get("event")
    if ev:
        return bool(ev.get("over"))
    b = st["extra"].get("battle")
    return bool(b and b.get("over"))


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
    if not _round_over(st):
        return False, {"error": "รอบนี้ยังไม่จบ"}

    # ⚠️ เคยมีเกณฑ์ "เลือดต่ำกว่า 25% ห้ามเดินต่อ" — **ถอดออกแล้ว**
    #    สเปกเสริม 2026-09-04 บอกว่าคนที่ล้มฟื้นมา 1% แล้วเดินทางต่อได้เลย
    #    เกณฑ์เดิมจะบล็อกทันทีทุกครั้ง ขัดกันตรง ๆ (เจ้าของเกมเคาะให้สเปกใหม่ชนะ)
    #    ความเสี่ยงตอนนี้อยู่ที่ "ตายยกทีมแล้วเสียของ" แทน ดู settle()
    if st["extra"].get("wiped"):
        return False, {"error": "💀 ปาร์ตี้ล้มยกทีม — ต้องกด \"เริ่มออกเดินทางใหม่\" ก่อน"}

    st["extra"].pop("battle", None)
    st["extra"].pop("reward", None)
    st["extra"]["paid"] = False
    st["extra"]["round"] = int(st["extra"].get("round") or 1) + 1
    _next_encounter(st)
    return True, lobby.save(st["room"], st)


def restart(uid):
    """เริ่มออกเดินทางใหม่หลังตายยกทีม — เฉพาะหัวห้อง

    รอบถูกรีเซ็ตเป็น 1 ตั้งแต่ตอน settle แล้ว ตรงนี้แค่ล้างธงกับเปิดสมรภูมิใหม่
    """
    st = _room(uid)
    if not st:
        return False, {"error": "ยังไม่ได้อยู่ปาร์ตี้ไหน"}
    if st["host"] != str(uid):
        return False, {"error": "เฉพาะหัวห้องเท่านั้นที่เริ่มออกเดินทางใหม่ได้"}
    if not st["extra"].get("wiped"):
        return False, {"error": "ปาร์ตี้ยังไม่ได้ล้มยกทีม"}

    # 💚 ฟื้นครึ่งเลือดตรงนี้ ไม่ใช่ตอนจบสมรภูมิ — จอจะได้แสดง "แพ้" ให้เห็นก่อน
    from bot.models import player_model
    for seat in st["seats"]:
        try:
            uid = int(seat["uid"])
            p = player_model.get_player(uid) or {}
            player_model.update_player_field(
                uid, "hp", journey.respawn_hp(gear_stats(p)[1]))
        except Exception as e:
            print(f"⚠️ [party] ฟื้นครึ่งเลือดไม่ได้ uid={seat.get('uid')}: {e}")

    st["extra"]["wiped"] = False
    st["extra"]["score"] = {}
    st["extra"].pop("penalty", None)
    st["extra"].pop("battle", None)
    st["extra"].pop("reward", None)
    st["extra"]["paid"] = False
    st["extra"]["round"] = 1
    st["extra"].pop("last_kind", None)
    st["extra"].pop("party_fx", None)
    dungeon.clear(st)
    _next_encounter(st)
    return True, lobby.save(st["room"], st)


def _heal_full(st):
    """ฟื้นเลือดทุกคนเต็มก่อนออกเดินทาง

    ⚠️ เจ้าของเกมเคาะ 2026-09-04 — **รู้ตัวว่าเป็นก๊อกฮีลฟรี**
       (ออกจากห้องแล้วเปิดใหม่ = ฟื้นเต็มโดยไม่ต้องจ่ายค่านอนพัก 2,000 ทอง)
       เลือกแบบนี้เพราะยังไม่มีเหตุการณ์หมู่บ้าน (10b) ปาร์ตี้ที่ไม่มีนักบวช
       เลือดเหลือ 1 จะตันถาวร เล่นต่อไม่ได้เลย

    ⚠️ เรียกเฉพาะตอน `begin()` (ออกเดินทางครั้งใหม่จากล็อบบี้) เท่านั้น
       **ห้ามเรียกใน `again()` หรือ `restart()`** ไม่งั้นทับกฎ
       "เดินทางต่อโดยเลือดติดตัว" กับ "ตายยกทีมฟื้นแค่ 50%" ทั้งสองข้อ

    ⚠️ ต้องเติม **เม็ดคริสตัลด้วย** ไม่ใช่แค่เลือด — ออกเดินทางใหม่ทั้งที
       แต่ออกท่าไม่ได้เลยก็ไม่ต่างจากตัน (เจ้าของเกมเจอตอนเทสด้วยมือ 2026-09-04)
    """
    from bot import mana as _mana
    from bot.models import player_model
    for seat in st["seats"]:
        try:
            uid = int(seat["uid"])
            p = player_model.get_player(uid) or {}
            player_model.update_player_field(uid, "hp", gear_stats(p)[1])
            _mana.refill(uid)
        except Exception as e:
            print(f"⚠️ [party] ฟื้นเลือด/เม็ดไม่ได้ uid={seat.get('uid')}: {e}")


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


def _next_encounter(st, rng=None):
    """รอบนี้เจออะไร — สุ่มแล้วเปิดฉากให้เลย

    ⚠️ ทางเดียวที่รอบใหม่จะเริ่ม ทั้งตอน begin / again / restart
       เหตุการณ์ที่ยังไม่ได้ทำจะตกเป็น "เจอมอน" ให้เอง (ดู encounter.READY)
    """
    rng = rng or random.Random()
    st["extra"].pop("event", None)
    st["extra"].pop("battle", None)
    _fx_tick(st, rng)          # สถานะจากภัยพิบัติกัดกินหนึ่งครั้งต่อรอบ

    # 🚪 อยู่กลางดันเจี้ยน = ไม่ต้องสุ่ม เวฟถัดไปมาเลย (นับเวฟละรอบ)
    if dungeon.active(st):
        w = dungeon.advance(st)
        if w:
            st["extra"]["last_kind"] = "dungeon"
            # ⚠️ or ไม่ใช่ = — ปาร์ตี้ที่ติ๊ก "ล่าบอส" ไว้ต้องเจอบอสทุกเวฟเหมือนเดิม
            #    เขียนทับด้วย False จะกลายเป็นว่ามุดดันเจี้ยนแล้วโหมดล่าบอสหายไป
            _spawn_battle(st, boss=dungeon.is_boss(w)
                          or bool(st["extra"].get("boss_raid")))
            return "dungeon"

    kind = encounter.roll_kind(int(st["extra"].get("round") or 1), rng,
                               last=st["extra"].get("last_kind"))
    st["extra"]["last_kind"] = kind
    if kind == "dungeon":
        dungeon.start(st)
        disaster.cleanse(st, "dungeon")     # ในดันเจี้ยนอุ่น — ตามที่เกมหลักกำหนด
        _spawn_battle(st, boss=dungeon.is_boss(dungeon.advance(st))
                      or bool(st["extra"].get("boss_raid")))
        return kind
    if kind == "monster":
        _spawn_battle(st)
        return kind

    members = [{"id": f"p{p['uid']}", "uid": p["uid"], "name": p["name"],
                "hp": p["hp"], "hp_max": p["max_hp"]} for p in _players_of(st)]
    ev = EVENT_MODS[kind].start(members, rng)
    ev["turn_at"] = time.time()
    st["extra"]["event"] = ev
    return kind


def _fx_tick(st, rng=None):
    """สถานะติดลบกัดกินตอนขึ้นรอบใหม่ — หักเลือดจริงแล้วเก็บข้อความไว้เล่า

    ⚠️ หักไม่ถึงตาย เหลืออย่างน้อย 1 เสมอ (ตายระหว่างเดินไม่มีในสเปก)
    """
    from bot.models import player_model
    lines = []
    for uid, key, dmg in disaster.tick_round(st, rng):
        try:
            pl = player_model.get_player(int(uid)) or {}
            player_model.update_player_field(
                int(uid), "hp", max(1, int(pl.get("hp") or 1) - int(dmg)))
            lines.append(f"{pl.get('name') or uid} เสีย {dmg:,} เลือดจาก"
                         f"{disaster.label(key)}")
        except Exception as e:
            print(f"⚠️ [party] หักเลือดสถานะไม่ได้ uid={uid}: {e}")
    if lines:
        st["extra"]["fx_log"] = lines
    else:
        st["extra"].pop("fx_log", None)
    return lines


def in_event(uid):
    """ตอนนี้ปาร์ตี้ของคนนี้อยู่ในเหตุการณ์ (ไม่ใช่สมรภูมิ) หรือเปล่า

    ชั้น API ใช้ตัดสินว่าจะส่งคำสั่งต่อให้ `act()` ไหม — **ไม่ได้ตรวจว่าสั่งได้จริง**
    ด่านนั้นคือ `_ev_act` (ถึงตาจริงไหม · ของอยู่ในเป้จริงไหม) ที่เดียวเหมือนเดิม
    """
    st = _room(uid)
    return bool(st and (st.get("extra") or {}).get("event"))


def _art_url(st, ev):
    """ภาพพื้นหลังของเหตุการณ์ — ลองภาพประจำทวีปของหัวห้องก่อน"""
    from bot import event_images
    from bot.models import player_model
    try:
        p = player_model.get_player(int(st["host"])) or {}
        cont = p.get("continent") or None
    except Exception as e:
        print(f"⚠️ [party] อ่านทวีปหัวห้องไม่ได้: {e}")
        cont = None
    return event_images.web_url(ev.get("art") or ev["kind"], cont)


def _ev_actions(st, ev, uid):
    """ปุ่มที่คนนี้กดได้ตอนนี้ — แต่ละเหตุการณ์ตอบเอง"""
    me = f"p{uid}"
    if ev.get("over") or encounter.current(ev) not in (me, None):
        if ev["kind"] != "treasure" or ev.get("stage") != treasure.PHASE_CHOOSE:
            return []
    return EVENT_MODS[ev["kind"]].options(ev, me, is_host=(st["host"] == str(uid)))


def _ev_act(st, ev, uid, action, rng):
    """สั่งหนึ่งอย่างในเหตุการณ์ — คืน (ok, ผล|ข้อความผิดพลาด)"""
    me = f"p{uid}"
    ok, err = EVENT_MODS[ev["kind"]].act(ev, me, action, rng,
                                         is_host=(st["host"] == str(uid)))
    if not ok:
        return False, {"error": err or "สั่งไม่ได้"}
    ev["turn_at"] = time.time()
    _ev_finish(st, ev)
    return True, {"events": []}


def _ev_finish(st, ev):
    """เช็คว่าเหตุการณ์จบหรือยัง แล้วเก็บผลเข้าตัวละครจริง"""
    if ev["kind"] in ("village", "npc", disaster.KIND) and encounter.all_done(ev):
        ev["over"] = True
    if not ev.get("over") or ev.get("paid"):
        return
    ev["paid"] = True
    if ev["kind"] == "treasure":
        _treasure_payout(st, ev)
    elif ev["kind"] == disaster.KIND:
        _disaster_payout(st, ev)
    elif ev["kind"] in ("village", "npc"):
        # 🧼 หมู่บ้าน/NPC ล้างสถานะให้ — เกมหลักเป็นคนบอกว่าล้างอะไรได้ (cleanse_on)
        gone = disaster.cleanse(st, ev["kind"])
        if gone:
            encounter.say(ev, "🧼 หายจาก " + " · ".join(sorted(set(gone))))


def _disaster_payout(st, ev):
    """เก็บผลภัยพิบัติเข้าตัวละครจริง — หักเลือดและติดสถานะของการเดินทางนี้

    ⚠️ สถานะลงที่ห้อง **ไม่ลงตัวละคร** — ติดเฉพาะการเดินทางนี้
       (เจ้าของเกมเคาะ 2026-09-05) ไปโหมดเดี่ยวแล้วต้องไม่ติดตามไป
    """
    from bot.models import player_model
    for m in ev["members"]:
        if not m.get("uid") or m.get("choice") != "hit":
            continue
        try:
            uid = int(m["uid"])
            pl = player_model.get_player(uid) or {}
            left = max(1, int(pl.get("hp") or 1) - int(m.get("dmg") or 0))
            player_model.update_player_field(uid, "hp", left)
            m["hp"] = left          # แถบเลือดบนจอเหตุการณ์อ่านค่านี้ ไม่ได้อ่านฐานข้อมูล
        except Exception as e:
            print(f"⚠️ [party] หักเลือดภัยพิบัติไม่ได้ uid={m.get('uid')}: {e}")
        if m.get("status"):
            disaster.afflict(st, m["uid"], m["status"], m.get("turns"))


def _treasure_payout(st, ev):
    """เก็บผลหีบเข้าตัวละครจริง — ดาเมจกับดัก และรางวัลถ้าได้"""
    from bot.models import player_model
    for m in ev["members"]:
        if not m.get("dmg") or not m.get("uid"):
            continue
        try:
            uid = int(m["uid"])
            p = player_model.get_player(uid) or {}
            left = max(1, int(p.get("hp") or 1) - int(m["dmg"]))
            player_model.update_player_field(uid, "hp", left)
            m["hp"] = left          # แถบเลือดบนจอเหตุการณ์อ่านค่านี้ ไม่ได้อ่านฐานข้อมูล
        except Exception as e:
            print(f"⚠️ [party] หักเลือดกับดักไม่ได้ uid={m.get('uid')}: {e}")

    if not ev.get("prize"):
        return
    mons = [{"rank": "Mini-Boss", "stats": {"gold_mult": 5, "exp_reward": 30}}]
    uids = [m["uid"] for m in ev["members"] if m.get("uid")]
    got = rewards.pay(uids, mons, random.Random(),
                      rnd=int(st["extra"].get("round") or 1))
    ev["reward"] = got
    encounter.say(ev, "🎁 แบ่งของในหีบกันเรียบร้อย")


def _ev_tick(st, ev):
    """หมดเวลาแล้วบอทเลือกแทน — เหตุการณ์ก็ต้องไม่ค้างเหมือนตอนสู้"""
    if ev.get("over"):
        return False
    who = encounter.current(ev)
    if not who:
        if ev["kind"] == "treasure" and ev.get("stage") == treasure.PHASE_CHOOSE:
            return False        # รอหัวห้อง ไม่มีคิวเทิร์น
        _ev_finish(st, ev)
        return True
    if time.time() - float(ev.get("turn_at") or 0) < engine.TURN_SECONDS:
        return False
    pick = EVENT_MODS[ev["kind"]].bot_pick(ev, who)
    uid = int(who[1:])
    ok, _ = _ev_act(st, ev, uid, pick, random.Random())
    return bool(ok)


def _spawn_battle(st, boss=None):
    """เกิดมอนแล้วเริ่มสมรภูมิ

    ⚠️ มอนมาจาก adventure_core.spawn_monster ของเกมหลัก ไม่สร้างพันธุ์ใหม่
       (เจ้าของเกมสั่งให้ใช้ดาต้าเดิม) — monsters.spawn_group คุมจำนวนกับบอส
    """
    rng = random.Random()
    players = _players_of(st)
    lv = max(1, sum(int(p.get("level") or 1) for p in players) // max(1, len(players)))
    if boss is None:
        boss = bool(st["extra"].get("boss_raid"))
    mons = monsters.spawn_group(int(st["host"]), len(players), rng,
                                boss=bool(boss), level=lv,
                                rnd=int(st["extra"].get("round") or 1))
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

    ev = st["extra"].get("event")
    if ev:
        ok, r = _ev_act(st, ev, uid, action, random.Random())
        if ok:
            lobby.save(st["room"], st)
        return ok, r

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


def _bank_score(st, b):
    """รวมดาเมจของสมรภูมินี้เข้าตารางสะสมของทั้งการเดินทาง

    ⚠️ สะสมข้ามรอบ ไม่ใช่ต่อสมรภูมิ — ตารางอันดับโชว์ตอนจบการเดินทาง
       จึงต้องนับตั้งแต่รอบ 1 ถึงรอบที่ล้ม
    """
    score = st["extra"].setdefault("score", {})
    for u in b["units"].values():
        if u["side"] != "party" or not u.get("uid"):
            continue
        got = int(u.get("dmg_done") or 0)
        if not got:
            continue
        row = score.setdefault(u["uid"], {"name": u.get("name") or "ผู้เล่น", "dmg": 0})
        row["dmg"] = int(row.get("dmg") or 0) + got
        row["name"] = u.get("name") or row["name"]
        u["dmg_done"] = 0          # ย้ายเข้าตารางแล้ว กันนับซ้ำตอน poll รอบถัดไป


def _score_board(st):
    """ตารางอันดับดาเมจ เรียงมากไปน้อย — ส่งขึ้นจอได้เลย"""
    rows = list((st["extra"].get("score") or {}).values())
    return sorted(rows, key=lambda r: -int(r.get("dmg") or 0))


def _punish(b):
    """โทษตอนตายยกทีม — เสียเงินสด เสีย EXP และอาจตกเลเวล

    เจ้าของเกมสั่ง 2026-09-04: "แพ้ต้องเสียตัง เสีย EXP และเลเวล"
    ⚠️ เงินใน **ธนาคารปลอดภัย** เสียเฉพาะเงินสดที่พกติดตัว
       (เข้ากับระบบธนาคาร/โจรปล้นที่มีอยู่ — ฝากก่อนออกเดินทางคือการเล่นที่ฉลาด)
    ⚠️ settle() กันเรียกซ้ำด้วยธง paid อยู่แล้ว โทษจึงถูกหักครั้งเดียว
    """
    from bot.models import player_model

    out = {}
    for u in b["units"].values():
        if u["side"] != "party" or not u.get("uid"):
            continue
        try:
            uid = int(u["uid"])
            p = player_model.get_player(uid) or {}
            pen = journey.wipe_penalty(p)
            player_model.update_player_fields(uid, {
                "cash": pen["cash"], "exp": pen["exp"],
                "level": pen["level"], "max_hp": pen["max_hp"]})
            # ⚠️ `pen["max_hp"]` เป็นค่า **ดิบ** ในฐานข้อมูล ยังไม่รวมโบนัสชุด
            #    เอาไปทับ u["hp_max"] ตรง ๆ ไม่ได้ เพราะของหน่วยรวมชุดแล้ว
            #    (เจ้าของเกมเห็น "170/240" ทั้งที่ควรเป็น 170/340 — 2026-09-04)
            fresh = dict(player_model.get_player(uid) or {})
            u["hp_max"] = gear_stats(fresh)[1]
            u["hp"] = min(u["hp"], u["hp_max"])
            out[u["uid"]] = {"gold": pen["gold_lost"], "exp": pen["exp_lost"],
                             "level": pen["level_lost"]}
        except Exception as e:
            print(f"⚠️ [party] หักโทษไม่ได้ uid={u.get('uid')}: {e}")
    return out


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

    # 💀 ปิดฉาก — journey เป็นที่เดียวที่ตัดสินว่าฟื้นยังไง
    #    รอด ≥1 คน → คนที่ล้มฟื้นมา 1% เดินทางต่อได้
    #    ล้มยกทีม  → ฟื้นมา 50% แต่รอบกลับไป 1 และเสียของ
    _bank_score(st, b)          # เก็บดาเมจของรอบนี้เข้าตารางสะสมก่อนปิดฉาก
    ending, revived = journey.close_out(list(b["units"].values()))
    if revived:
        # ต่อท้ายชุดเหตุการณ์เดิม — จอจะเล่น "ตาย" ให้จบก่อนแล้วค่อย "ฟื้น"
        _record(st, list(b.get("recent") or [])
                + [events.heal(i, i, hp) for i, hp in revived])
    st["extra"]["wiped"] = (ending == "wipe")
    if ending == "wipe":
        st["extra"]["round"] = 1
        st["extra"]["penalty"] = _punish(b)

    _carry_hp(b)                        # เลือดที่เหลือติดตัวกลับไปเกมหลัก
    if b.get("winner") != "party" and dungeon.active(st):
        dungeon.clear(st)               # หนีหรือล้มยกทีม = จบดันเจี้ยน ของที่ได้ไม่ถูกริบ
    if b.get("winner") != "party":
        st["extra"]["reward"] = None
        lobby.save(st["room"], st)
        return None

    mons = [u for u in b["units"].values() if u["side"] == "monster"]
    uids = [u["uid"] for u in b["units"].values() if u["side"] == "party"]
    st["extra"]["reward"] = rewards.pay(
        uids, mons, random.Random(), rnd=int(st["extra"].get("round") or 1))
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
        if st["extra"].get("round"):
            out["round"] = int(st["extra"]["round"])
        out["dungeon"] = dungeon.view(st)
        out["fx"] = {k: disaster.label(k) for k in disaster.of(st, uid)}
        if st["extra"].get("fx_log"):
            out["fx_log"] = list(st["extra"]["fx_log"])
        ev = st["extra"].get("event")
        if ev:
            if _ev_tick(st, ev):
                lobby.save(st["room"], st)
            out["event"] = {
                "kind": ev["kind"],
                "art": ev.get("art") or ev["kind"],
                # 🖼️ ต่อ URL ที่นี่ที่เดียว — ชื่อไฟล์ภาพมีคำนำหน้าทวีป
                #    หน้าเว็บเดาเองแล้วได้ 404 (ดู event_images.web_url)
                "art_url": _art_url(st, ev),
                "stage": ev.get("stage"),
                "turn_of": encounter.current(ev),
                "turn_left": max(0, int(engine.TURN_SECONDS
                                        - (time.time() - float(ev.get("turn_at") or 0)))),
                "members": [{k: m.get(k) for k in
                             ("id", "name", "hp", "hp_max", "done", "choice", "roll", "dmg")}
                            | {"you": m.get("uid") == str(uid)}
                            for m in ev["members"]],
                "log": list(ev.get("log") or []),
                "over": bool(ev.get("over")),
                "actions": _ev_actions(st, ev, uid),
                "round": int(st["extra"].get("round") or 1),
                "reward": ev.get("reward"),
            }
        elif st["extra"].get("battle"):
            # ⏱️ คนที่ยังเปิดจออยู่เป็นคนเดินนาฬิกาให้ — หมดเวลาแล้วบอทเล่นแทน
            #    (ไม่มีตรงนี้ คน AFK คนเดียวค้างทั้งปาร์ตี้ ไม่มีใครปลด)
            #    ทุกคนหลุดหมดก็ไม่มีใคร poll = ไม่มีอะไรต้องเดิน
            if _tick(st):
                lobby.save(st["room"], st)
            # ⚠️ ต้อง settle **ก่อน** ถ่ายภาพส่งขึ้นจอ
            #    settle เป็นคนฟื้นเลือดคนที่ล้ม (1% / 50%) ถ่ายภาพก่อนแล้ว
            #    จอจะยังเห็นเลือด 0 ทั้งที่ฟื้นไปแล้ว
            #    (เจ้าของเกมเห็น "0/480" ตอนเทสด้วยมือ 2026-09-04)
            settle(st)                  # จบตอนตามอนก็ต้องได้รางวัล ไม่ต้องรอกดอะไร
            # engine.view คัดค่าลับของมอนออกให้แล้ว (ส่ง hp_pct ไม่ใช่ hp จริง)
            out["battle"] = engine.view(st, uid)
            # renderer รับแค่ก้อน battle — ยัดรอบกับตารางอันดับเข้าไปด้วย
            out["battle"]["round"] = int(st["extra"].get("round") or 1)
            # 🚪 ป้ายเวฟดันเจี้ยน — ประกอบข้อความที่นี่ที่เดียว renderer ทั้งสองตัว
            #    จะได้ไม่ต้องรู้กติกาเวฟ (วาดตัวหนังสือที่ส่งไปให้เฉย ๆ)
            d = dungeon.view(st)
            out["battle"]["wave"] = (
                f"🚪 เวฟ {d['wave']}/{d['waves']}" + (" 👑" if d["boss"] else "")
            ) if d else None
            out["battle"]["score"] = _score_board(st)
            out["reward"] = st["extra"].get("reward")
            out["wiped"] = bool(st["extra"].get("wiped"))
            if st["extra"].get("penalty"):
                out["penalty"] = (st["extra"]["penalty"] or {}).get(str(uid))
    return out
