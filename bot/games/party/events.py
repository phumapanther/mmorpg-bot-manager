"""🎭 เหตุการณ์ที่แกนส่งให้ renderer วาด

⚠️ **นี่คือ "สัญญา" ระหว่างแกน Python กับ renderer ทุกตัว**
   แก้รูปแบบตรงนี้ = renderer ทุกตัวพัง — แก้แล้วต้องไล่แก้ทุก renderer ด้วย
   เพิ่มชนิดใหม่ต้องใส่ใน EVENT_TYPES ด้วย (มีเทสคุม)

หลักการ: เซิร์ฟเวอร์บอกว่า **"เกิดอะไรขึ้น"** ไม่บอกว่า **"วาดยังไง"**
         renderer อ่านรายการนี้แล้วตีความเป็นภาพเอง
         → เปลี่ยนกราฟิก = เขียน renderer ใหม่ ไม่ต้องแตะแกนเลย
         (นี่คือเงื่อนไขที่เจ้าของเกมสั่งไว้ 2026-09-03)

ทุกฟังก์ชันคืน dict ธรรมดาที่ json.dumps ได้ — ห้ามใส่ object แปลก ๆ
"""

# ชนิดเหตุการณ์ทั้งหมดที่ renderer ต้องรองรับ
EVENT_TYPES = (
    "turn_start",   # ถึงตาใคร
    "dice",         # ทอยเต๋า
    "attack",       # โจมตีเป้าเดียว
    "aoe",          # โจมตีหลายเป้า
    "heal",         # ฮีล / ชุบ
    "miss",         # พลาด
    "die",          # ล้ม
    "phase",        # บอสเปลี่ยนเฟส
)


def turn_start(who):
    """ถึงตาของ who แล้ว — renderer เอาไปเลื่อนแถบคิวกับโฟกัสกล้อง"""
    return {"t": "turn_start", "who": who}


def dice(who, rolls):
    """ทอยเต๋า — ส่งทุกลูกไปด้วยเพื่อให้ renderer เล่นอนิเมชันทีละลูกได้"""
    rolls = [int(r) for r in rolls]
    return {"t": "dice", "who": who, "rolls": rolls, "total": sum(rolls)}


def attack(frm, to, dmg, element, crit=False):
    """โจมตีเป้าเดียว — crit ส่งเสมอ (True/False) ไม่ให้ renderer ต้องเดา"""
    return {"t": "attack", "from": frm, "to": to,
            "dmg": int(dmg), "element": element, "crit": bool(crit)}


def aoe(frm, targets, dmgs, element):
    """โจมตีหลายเป้าพร้อมกัน — จำนวนเป้ากับดาเมจต้องเท่ากันและเรียงตรงกัน"""
    targets = list(targets)
    dmgs = [int(d) for d in dmgs]
    if len(targets) != len(dmgs):
        raise ValueError(
            f"เป้า {len(targets)} ตัว แต่ดาเมจ {len(dmgs)} ค่า — ไม่ตรงกัน "
            "renderer จะวาดเลขผิดตัว")
    return {"t": "aoe", "from": frm, "targets": targets,
            "dmgs": dmgs, "element": element}


def heal(frm, to, amount):
    """ฮีลหรือชุบเพื่อน"""
    return {"t": "heal", "from": frm, "to": to, "amount": int(amount)}


def miss(frm, to):
    """พลาด — ต้องมีชนิดของตัวเอง ไม่ใช่ส่ง attack ที่ dmg=0
    (renderer จะได้เล่นอนิเมชันหลบแทนอนิเมชันโดนตี)"""
    return {"t": "miss", "from": frm, "to": to}


def die(who):
    """ล้ม — ผู้เล่นที่ล้มยังอยู่ในสมรภูมิ รอเพื่อนชุบ (สเปกข้อ 5)"""
    return {"t": "die", "who": who}


def phase(who, phase_name):
    """บอสเปลี่ยนเฟส — renderer เอาไปเล่นอนิเมชันพิเศษ
    phase_name: "normal" / "rage" / "desperate" """
    return {"t": "phase", "who": who, "phase": phase_name}
