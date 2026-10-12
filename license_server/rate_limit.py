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
    "auth": (10, 300),      # **ขอ**โค้ดล็อกอิน — คุมแน่น กันคนกดปั๊มโค้ดรัว ๆ
    # ลองรหัสแอดมิน — บอทยิงรัว ๆ ผ่านลิงก์สาธารณะโดนบล็อก แต่เจ้าของพิมพ์ผิดหลายครั้งยังลองได้
    # (กันเดารหัสจริงอยู่ที่บังคับรหัส ≥24 ตัวตอนสตาร์ท serve.py — เดาไม่มีวันเจอ ลิมิตนี้แค่กันสแปม)
    "adminlogin": (20, 300),
    # 🔑 **ถามสถานะ**โค้ดของตัวเอง — คนละเรื่องกับการขอโค้ด
    #
    # ⚠️ เคยรวมอยู่กลุ่ม auth แล้วล็อกอินพังจริง: หน้าล็อกอินหมุนถามทุก 2.5 วิ
    #    เพื่อรอผู้ใช้ไปพิมพ์โค้ดในดิส แต่โควตา 10 ครั้ง/5 นาที หมดใน 25 วินาที
    #    ผู้ใช้ยังพิมพ์ในดิสไม่ทันด้วยซ้ำ หน้าเว็บก็ค้างไปแล้ว
    # กันเดาโค้ดยังอยู่: โค้ด 6 หลักจาก 32 ตัวอักษร = 1,073 ล้านแบบ
    # ที่ 80 ครั้ง/นาที ต้องเดา 26 ปีถึงจะครบ — ปลอดภัยเหลือเฟือ
    "poll": (400, 300),
    # 🪱 สนามรบ PVP — กดค้างเดินคือยิงคำสั่งรัวโดยธรรมชาติ ไม่ใช่พฤติกรรมสคริปต์
    # ฟาร์มของไม่ได้อยู่แล้วเพราะมินิเกมแยกขาดจากเกมหลัก ไม่มีรางวัลไหลกลับเลย
    # จึงเหลือเหตุผลเดียวคือกันยิงถล่มจนล่ม → ปล่อยกว้างแต่ยังมีเพดาน
    "arena": (200, 60),
}

# เส้นทางไหนอยู่กลุ่มไหน (เทียบแบบขึ้นต้นด้วย เอาที่ยาวสุดก่อน)
ROUTES = {
    "/api/web/admin/login": "adminlogin",  # ต้องมาก่อน /api/web/login (เทียบตัวยาวสุดก่อน)
    "/api/web/login/status": "poll",     # ต้องมาก่อน /api/web/login (เทียบตัวยาวสุดก่อน)
    "/api/web/pvp": "arena",
    "/api/web/login": "auth",
    "/api/web/bank": "money",
    "/api/web/casino": "money",
    "/api/web/blackjack": "money",
    # UNO เดิมพันทองจริงตั้งแต่ 09-02 (โต๊ะเล่นกับเพื่อน) ต้องคุมแน่นเท่าคาสิโนอื่น
    "/api/web/uno": "money",
    "/api/web/party": "money",     # เฟส 5 จ่ายทองจริงแล้ว
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
        # GET ส่วนใหญ่เป็นการอ่านเฉย ๆ ยกเว้นเส้นทางล็อกอินที่ต้องคุมเป็นพิเศษ
        for prefix in sorted(ROUTES, key=len, reverse=True):
            if path.startswith(prefix) and ROUTES[prefix] in ("auth", "poll"):
                return ROUTES[prefix]
        return "read"
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
