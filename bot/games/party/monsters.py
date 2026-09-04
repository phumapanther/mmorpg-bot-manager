"""🎭 มอนหลายตัว + บอสหลายเฟส — ตรรกะล้วน ไม่แตะ DB เอง

⚠️ **ใช้ `adventure_core.spawn_monster` ของเกมหลัก ห้ามสร้างมอนพันธุ์ใหม่**
   ไม่งั้นมอนธาตุเดียวกันในสองโหมดจะเลือด/ดาเมจไม่เท่ากัน ผู้เล่นงง
   (เจ้าของเกมสั่งไว้ 2026-09-03 — โหมดนี้ยืมดาต้าเกมหลักทั้งหมด)

⚠️ **บอสต้องเตือนก่อนออกท่าใหญ่ 1 ตาเสมอ** — ตายแบบไม่ทันตั้งตัวไม่สนุก
   บังคับด้วยโครงสร้าง ไม่ใช่ด้วยการเช็ค: ท่าใหญ่ยิงได้เฉพาะตอน `charging`
   ซึ่งตั้งได้ที่เดียวคือตาที่เตือน (ดู engine._boss_turn)
"""
import random

from bot import adventure_core

PHASES = ("normal", "rage", "desperate")

# เลือดเหลือกี่ส่วนถึงเปลี่ยนเฟส (แตะพอดี = เข้าเฟสใหม่แล้ว)
RAGE_AT = 0.70
DESPERATE_AT = 0.30

# ออกท่าใหญ่ทุกกี่ตา — 0 = ไม่ออก
# ยิ่งใกล้ตาย ยิ่งถี่ ผู้เล่นจะได้รู้สึกว่าต้องรีบจบ
BIG_MOVE_EVERY = {"normal": 0, "rage": 3, "desperate": 2}

BIG_MOVE_NAME = {"rage": "🔥 คลื่นเพลิงคลั่ง", "desperate": "💀 ลมหายใจสุดท้าย"}

# แรงค์ที่นับเป็นบอส (มาจาก adventure_core.MONSTER_RANKS)
BOSS_RANKS = ("Mini-Boss", "Main-Boss", "Secret", "Unbeatable")

GROUP_MIN, GROUP_MAX = 3, 5      # ปาร์ตี้ปกติเจอมอนกี่ตัว
MINION_MIN, MINION_MAX = 2, 4    # บอสเรดมีลูกน้องกี่ตัว


def boss_phase(hp, hp_max):
    """เลือดเท่านี้อยู่เฟสไหน — เลือดสูงสุด 0 ก็ไม่หารศูนย์"""
    if hp_max <= 0:
        return "normal"
    pct = float(hp) / float(hp_max)
    if pct > RAGE_AT:
        return "normal"
    if pct > DESPERATE_AT:
        return "rage"
    return "desperate"


def telegraph(boss):
    """ท่าใหญ่ที่บอสกำลังจะออก — `None` = ยังไม่ถึงเวลา

    ⚠️ engine ต้องเรียกตัวนี้ **ก่อน** ปล่อยท่าเสมอ 1 ตา
       คืน dict ที่ส่งขึ้นเบราว์เซอร์ได้ตรง ๆ (ชื่อท่า + โดนใคร)
    """
    ph = boss_phase(boss.get("hp") or 0, boss.get("hp_max") or 0)
    every = BIG_MOVE_EVERY.get(ph, 0)
    if not every or int(boss.get("since_big") or 0) < every:
        return None
    return {"move": BIG_MOVE_NAME.get(ph, "ท่าไม้ตาย"), "kind": "aoe",
            "targets": "all", "phase": ph}


def _power(m):
    """พลังโจมตี/เกราะจากแรงค์ — แรงค์สูงตีแรงกว่า

    เฟส 3 ตั้ง atk แบบตายตัว (6+i) ทำให้บอสตีเบาเท่ามอนทั่วไป
    ตรงนี้ผูกกับ dice_count ของเกมหลักแทน จะได้ไปทางเดียวกันเสมอ
    """
    dice = int((m.get("stats") or {}).get("dice_count") or 1)
    return 5 + dice * 3, max(0, dice - 1)


def _budget(group, party_size):
    """งบสมรภูมิ — มอนทั้ง**กลุ่มรวมกัน**ต้องแรงราว ๆ "มอนเดี่ยว × จำนวนคน"

    ⚠️ วัดจริง 2026-09-04 (40 สมรภูมิต่อช่อง): ไม่คุมงบแล้วปาร์ตี้ 2 คน
       **ชนะ 1 ใน 40** เพราะเจอมอน 3 ตัวเต็มสเปกโหมดเดี่ยว
       จำนวนตัวมีไว้ให้ภาพสนามดูเป็นกลุ่ม **ไม่ใช่ให้ยากขึ้นตามจำนวน**
       คุมงบแล้วได้ 15/40 (บอทโง่ ๆ ที่เอาแต่ตีกับฮีลตัวเอง)

    บอสเรดไม่ต้องคูณเพิ่ม — แรงค์บอสดันค่าเฉลี่ยของกลุ่มขึ้นเองอยู่แล้ว
    เคยใส่ ×1.3 ทับไปอีกชั้น ผลคือปาร์ตี้ 2 คน**ชนะ 0 ใน 40** (คูณซ้ำซ้อน)
    """
    if not group:
        return group
    k = float(party_size) / len(group)
    for m in group:
        m["hp"] = m["hp_max"] = max(1, int(m["hp_max"] * k))
        m["atk"] = max(1, int(m["atk"] * k))
    return group


def _one(uid, rng):
    """มอนหนึ่งตัวจากเกมหลัก + ค่าที่โหมดปาร์ตี้ต้องใช้เพิ่ม"""
    m = adventure_core.spawn_monster(uid, rng=rng)
    m["atk"], m["def"] = _power(m)
    m["name"] = (m.get("stats") or {}).get("name") or "มอนสเตอร์"
    return m


def boss_rank_for(level, rng):
    """แรงค์บอสที่เลเวลนี้ควรเจอ — สุ่มด้วย **ตารางน้ำหนักของเกมหลัก**

    ⚠️ เดิมบังคับเป็น Mini-Boss ทุกเลเวล วัดจริง 2026-09-04 แล้วเพี้ยนสองทาง:
       เลเวล 60 ล่าบอสชนะ 30/30 (ง่ายจนไม่มีความหมาย)
       เลเวล 1 ชนะ 0/30 (แต่อันนี้ตรงกับเกมหลัก — เลเวลต่ำเจอบอสก็ควรหนี)
       สุ่มตามเลเวลแล้วเลเวลสูงจะเจอ Main-Boss/Secret ขึ้นไปเอง
    """
    keys = list(adventure_core.MONSTER_RANKS)
    w = adventure_core.spawn_weights_for(int(level or 1), keys)
    pool = [(k, x) for k, x in zip(keys, w) if k in BOSS_RANKS and x > 0]
    if not pool:
        return BOSS_RANKS[0]
    return rng.choices([k for k, _ in pool], weights=[x for _, x in pool], k=1)[0]


def _promote(m, rng, level=1):
    """ดันมอนธรรมดาให้เป็นบอส — ใช้สเปกแรงค์ของเกมหลัก ไม่ตั้งตัวเลขเอง

    `spawn_monster` สุ่มแรงค์ตามเลเวลผู้เล่น บอสเรดจึงอาจได้มอนทั่วไปมา
    ตอนนั้นต้องยกแรงค์ให้ ไม่ใช่คูณเลขมั่ว ๆ
    """
    if m.get("rank") in BOSS_RANKS:
        return m
    rank = boss_rank_for(level, rng)
    stats = dict(adventure_core.MONSTER_RANKS[rank])
    lo, hi = stats["hp_range"]
    m["rank"] = rank
    m["stats"] = stats
    m["name"] = stats["name"]
    m["hp"] = m["hp_max"] = rng.randint(int(lo), int(hi))
    m["atk"], m["def"] = _power(m)
    return m


def spawn_group(uid, party_size, rng=None, boss=False, level=1):
    """กลุ่มมอนสำหรับหนึ่งสมรภูมิ — คืนลิสต์ที่ engine เอาไปใช้ได้เลย

    ปาร์ตี้ปกติ: 3-5 ตัว ตามจำนวนคน
    บอสเรด: บอส 1 + ลูกน้อง 2-4 — **แรงค์บอสสุ่มตามเลเวลปาร์ตี้**
            (ยากกว่าเพราะแรงค์ ไม่ใช่เพราะคูณตัวเลขเพิ่ม)

    ความแรงรวมคุมด้วย `_budget` ไม่ใช่ปล่อยตามจำนวนตัว

    id ต่อให้ที่นี่ที่เดียว (`m1`, `m2`, ...) — ซ้ำกันเมื่อไหร่
    ตีตัวหนึ่งแล้วอีกตัวเลือดลด และ renderer วาดทับกัน
    """
    rng = rng or random.Random()
    size = max(1, int(party_size or 1))

    if boss:
        n_minion = min(MINION_MAX, max(MINION_MIN, size))
        group = [_promote(_one(uid, rng), rng, level)]
        group[0]["boss"] = True
        group += [_one(uid, rng) for _ in range(n_minion)]
    else:
        group = [_one(uid, rng)
                 for _ in range(min(GROUP_MAX, max(GROUP_MIN, size + 1)))]

    _budget(group, size)
    for i, m in enumerate(group):
        m["id"] = f"m{i + 1}"
        m.setdefault("boss", False)
        m["since_big"] = 0
        m["charging"] = False
    return group
