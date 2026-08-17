"""🚦 จำกัดอัตราการยิง API (เว็บเกม เฟส 6)

กันสองอย่าง:
  1. สคริปต์ยิงรัวเพื่อฟาร์มของ (เดินทาง/ทอยเต๋า/กาชา)
  2. ยิงถล่มจนเซิร์ฟเวอร์ล่ม

นับแยกรายคน (ตาม session cookie) — ไม่ใช่รายไอพี เพราะบ้านเดียวกัน/มือถือเน็ตเดียวกัน
จะโดนหางเลขกันหมด ไม่มี session ค่อยตกไปนับตามไอพี

หน้าต่างเลื่อน (sliding window) เก็บในหน่วยความจำ — เซิร์ฟเดียวก็พอ
ถ้าวันหนึ่งรันหลายเครื่องค่อยย้ายไป Redis (ponytail: ยังไม่ถึงจุดนั้น)
"""
import threading
import time

# กลุ่มเส้นทาง -> (จำนวนครั้ง, ในกี่วินาที)
# เขียน DB/แจกของ = คุมแน่น · อ่านอย่างเดียว = ปล่อยกว้าง
LIMITS = {
    "write": (30, 60),      # เดินทาง สู้ ทอยเต๋า ซื้อของ ฯลฯ
    "money": (12, 60),      # ธนาคาร คาสิโน กาชา ร้านยศ — ของที่แตะเงินก้อน
    "read": (240, 60),      # โหลดข้อมูลหน้าจอ
    "auth": (10, 300),      # ขอโค้ดล็อกอิน (กันสุ่มโค้ดคนอื่น)
    # 🪱 สนามรบ PVP — กดค้างเดินคือยิงคำสั่งรัวโดยธรรมชาติ ไม่ใช่พฤติกรรมสคริปต์
    # ฟาร์มของไม่ได้อยู่แล้วเพราะมินิเกมแยกขาดจากเกมหลัก ไม่มีรางวัลไหลกลับเลย
    # จึงเหลือเหตุผลเดียวคือกันยิงถล่มจนล่ม → ปล่อยกว้างแต่ยังมีเพดาน
    "arena": (200, 60),
}

# เส้นทางไหนอยู่กลุ่มไหน (เทียบแบบขึ้นต้นด้วย เอาที่ยาวสุดก่อน)
ROUTES = {
    "/api/web/pvp": "arena",
    "/api/web/login": "auth",
    "/api/web/bank": "money",
    "/api/web/casino": "money",
    "/api/web/blackjack": "money",
    "/api/web/goldbar": "money",
    "/api/web/roleshop": "money",
    "/api/web/topup": "money",
    "/api/web/adventure": "write",
    "/api/web/board": "write",
    "/api/web/item": "write",
    "/api/web/craft": "write",
    "/api/web/shop": "write",
    "/api/web/bag": "write",
}

_hits = {}                  # (คีย์ผู้ใช้, กลุ่ม) -> [เวลาที่ยิง...]
_lock = threading.Lock()
_last_sweep = [0.0]


def group_for(path, method):
    """เส้นทางนี้อยู่กลุ่มไหน — GET ทั้งหมดถือเป็นอ่านอย่างเดียว"""
    if not path.startswith("/api/web"):
        return None
    if method == "GET":
        return "auth" if path.startswith("/api/web/login") else "read"
    for prefix in sorted(ROUTES, key=len, reverse=True):
        if path.startswith(prefix):
            return ROUTES[prefix]
    return "write"


def _sweep(now):
    """ทิ้งรอยเก่าทุก 5 นาที — กันหน่วยความจำโตไม่หยุดตอนคนเข้าเยอะ"""
    if now - _last_sweep[0] < 300:
        return
    _last_sweep[0] = now
    longest = max(w for _, w in LIMITS.values())
    for key in [k for k, v in _hits.items() if not v or now - v[-1] > longest]:
        _hits.pop(key, None)


def check(user_key, path, method, now=None):
    """คืน (ผ่านไหม, ต้องรออีกกี่วินาที) — ไม่ผ่านเมื่อยิงถี่เกินโควตาของกลุ่มนั้น"""
    group = group_for(path, method)
    if not group:
        return True, 0
    limit, window = LIMITS[group]
    now = now if now is not None else time.time()

    with _lock:
        _sweep(now)
        key = (user_key, group)
        hits = [t for t in _hits.get(key, ()) if now - t < window]
        if len(hits) >= limit:
            _hits[key] = hits
            return False, max(1, int(window - (now - hits[0])) + 1)
        hits.append(now)
        _hits[key] = hits
    return True, 0


def reset():
    """ล้างตัวนับ (ใช้ในเทส)"""
    with _lock:
        _hits.clear()
        _last_sweep[0] = 0.0
