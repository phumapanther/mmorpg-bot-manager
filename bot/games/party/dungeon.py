"""🚪 ดันเจี้ยน — สู้ต่อเนื่อง 10 เวฟ (เฟส 10c)

สเปกข้อ 3.5: เข้าไปแล้วสู้ทีละเวฟจนครบ 10 · เวฟท้าย ๆ เจอบอส

⚠️ **ไม่มีระบบต่อสู้ของตัวเอง** — ใช้สมรภูมิตัวเดิม (`engine` + `monsters`)
   ไฟล์นี้รู้แค่ "ตอนนี้เวฟที่เท่าไหร่ · เวฟนี้ต้องเจอบอสไหม · จบหรือยัง"

⚠️ **นับเวฟละรอบ** (เจ้าของเกมเคาะ 2026-09-05) — เข้าดันเจี้ยนตอนรอบ 5
   เวฟ 10 คือรอบ 14 มอนแรงขึ้นเรื่อย ๆ ระหว่างมุด ทองก็ขึ้นตาม
   ทางเลือกอีกทางคือ "ทั้งดันเจี้ยนนับรอบเดียว" ซึ่งจะกลายเป็นที่ฟาร์มราคาถูก

⚠️ **หนีกลางดันเจี้ยนได้ จบดันเจี้ยนทันที** (เจ้าของเกมเคาะ 2026-09-05)
   ของที่เก็บได้จากเวฟก่อนหน้าไม่ถูกริบ — จ่ายไปตั้งแต่จบเวฟนั้นแล้ว
   ตายยกทีมก็จบเหมือนกัน (ดู `room.settle`)
"""
WAVES = 10          # สู้กี่เวฟถึงจะผ่าน
BOSS_FROM = 8       # เวฟนี้เป็นต้นไปเจอบอสแน่นอน


def start(st):
    """เปิดปากดันเจี้ยน — เวฟแรกจะถูกนับตอน `advance()`"""
    st.setdefault("extra", {})["dungeon"] = {"wave": 0, "waves": WAVES}


def active(st):
    return bool((st.get("extra") or {}).get("dungeon"))


def wave(st):
    """เวฟที่กำลังสู้อยู่ (0 = ยังไม่เริ่ม)"""
    return int(((st.get("extra") or {}).get("dungeon") or {}).get("wave") or 0)


def advance(st):
    """ก้าวเข้าเวฟถัดไป — คืนเลขเวฟ หรือ None ถ้าครบแล้ว (และปิดดันเจี้ยนให้)"""
    d = (st.get("extra") or {}).get("dungeon")
    if not d:
        return None
    nxt = int(d.get("wave") or 0) + 1
    if nxt > int(d.get("waves") or WAVES):
        clear(st)
        return None
    d["wave"] = nxt
    return nxt


def is_boss(n):
    return int(n or 0) >= BOSS_FROM


def clear(st):
    """ออกจากดันเจี้ยน — ผ่านครบ · หนี · หรือล้มยกทีม"""
    (st.get("extra") or {}).pop("dungeon", None)


def view(st):
    """ก้อนเล็ก ๆ ให้หน้าเว็บวาดป้าย "เวฟ 3/10" — ไม่ได้อยู่ในดันเจี้ยนก็ None"""
    d = (st.get("extra") or {}).get("dungeon")
    if not d or not int(d.get("wave") or 0):
        return None
    return {"wave": int(d["wave"]), "waves": int(d.get("waves") or WAVES),
            "boss": is_boss(d["wave"])}
