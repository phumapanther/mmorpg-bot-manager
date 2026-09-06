"""🎲 สุ่มเหตุการณ์ + โครงสถานะกลางของเหตุการณ์ที่ไม่ใช่การต่อสู้ (เฟส 10b)

⚠️ **น้ำหนักการสุ่มยืมจากเกมหลัก** (`adventure_core.event_weights`) ห้ามตั้งใหม่
   ไม่งั้นเดินทางคนเดียวกับเดินทางเป็นปาร์ตี้เจอของไม่เหมือนกัน ผู้เล่นงง

⚠️ เหตุการณ์ที่ยังไม่ได้ทำ **ตกเป็น "เจอมอน" ไปก่อน** (เจ้าของเกมเคาะ 2026-09-05)
   เกมจะเล่นได้ต่อเนื่องระหว่างที่ 10c ยังไม่เสร็จ พอทำเสร็จก็เติมชื่อใน READY
   แล้วมันจะโผล่มาเองทันที ไม่ต้องแก้ตัวสุ่ม

โครงสถานะกลาง `extra["event"]` — ทุกเหตุการณ์ใช้ร่วมกันเพื่อให้หน้าเว็บวาดแบบเดียว
    kind      ชนิด (village · treasure · ...)
    turn_of   ใครถึงตา (None = ไม่ต้องสลับเทิร์น)
    order     ลำดับเทิร์น
    members   [{id, uid, name, hp, hp_max, done, choice}]
    actions   ปุ่มที่กดได้ตอนนี้ [{key, name, hint}]
    log       ข้อความเล่าเรื่อง (เก่าอยู่บนสุด)
    over      จบเหตุการณ์นี้แล้วไหม
    art       ชื่อภาพพื้นหลัง (ใช้ของเกมหลักที่ /assets/events/)
"""
import random

from bot import adventure_core

# ชนิดที่ทำเสร็จแล้วจริง ๆ — ครบทุกชนิดของเกมหลักแล้วตั้งแต่ 10c (2026-09-05)
# ยังเก็บด่านนี้ไว้: Panel เพิ่มชื่ออีเวนต์ใหม่เมื่อไหร่ ปาร์ตี้จะตกเป็น "เจอมอน"
# แทนที่จะระเบิด KeyError กลางการเดินทาง
READY = ("monster", "village", "treasure", "dungeon", "npc", "trap")

FALLBACK = "monster"


def roll_kind(rnd=1, rng=None, last=None):
    """สุ่มว่ารอบนี้เจออะไร — คืนชื่อชนิดที่ทำเสร็จแล้วเสมอ

    ใช้ตารางน้ำหนักของเกมหลัก แล้วเอาผลที่ยังไม่ได้ทำมาตกเป็น "เจอมอน"
    """
    rng = rng or random.Random()
    keys = list(adventure_core.EVENT_LIST)
    try:
        weights = adventure_core.event_weights(last or "none")
    except Exception as e:
        print(f"⚠️ [party] อ่านน้ำหนักอีเวนต์ไม่ได้: {e}")
        return FALLBACK
    if len(weights) != len(keys) or not any(weights):
        return FALLBACK
    got = rng.choices(keys, weights=weights, k=1)[0]
    return got if got in READY else FALLBACK


def new_state(kind, members, art=None):
    """โครงสถานะเปล่าของเหตุการณ์ — ทุกเหตุการณ์เริ่มจากตรงนี้"""
    rows = [{
        "id": m["id"], "uid": m.get("uid"), "name": m.get("name") or "ผู้เล่น",
        "hp": int(m.get("hp") or 0), "hp_max": int(m.get("hp_max") or 1),
        "done": False, "choice": None,
    } for m in members]
    return {
        "kind": kind,
        "order": [r["id"] for r in rows],
        "turn": 0,
        "members": rows,
        "log": [],
        "over": False,
        "art": art or kind,
        "turn_at": 0.0,
    }


def current(ev):
    """ใครถึงตาตอนนี้ — คนที่เลือกไปแล้วถูกข้ามให้อัตโนมัติ"""
    order = ev.get("order") or []
    if not order or ev.get("over"):
        return None
    by = {m["id"]: m for m in ev["members"]}
    n = len(order)
    for step in range(n):
        who = order[(int(ev.get("turn") or 0) + step) % n]
        if not (by.get(who) or {}).get("done"):
            ev["turn"] = (int(ev.get("turn") or 0) + step) % n
            return who
    return None


def member(ev, unit_id):
    for m in ev.get("members") or []:
        if m["id"] == unit_id:
            return m
    return None


def say(ev, text):
    """เติมข้อความเล่าเรื่อง — เก็บไว้ไม่เกิน 12 บรรทัด กันสถานะบวม"""
    ev.setdefault("log", []).append(str(text))
    ev["log"] = ev["log"][-12:]
    return ev


def all_done(ev):
    return all(m.get("done") for m in ev.get("members") or [])
