"""ค่าตั้งต้นร่วมของเทสทั้งชุด"""
import functools
import pathlib

import pytest

_ROOT = pathlib.Path(__file__).resolve().parent.parent
_WEB = _ROOT / "license_server" / "web_static"


def web_api_source():
    """รวมซอร์สทั้งหมดของ API เว็บ (web_api.py สะพาน + license_server/api_web/**)

    ระหว่างรื้อโครงสร้าง (09-02 ขั้นที่ 4) โค้ดที่เคยอยู่ไฟล์เดียว web_api.py
    ถูกย้ายกระจายไปหลายไฟล์ใน api_web/ — เทสเก่าที่เคยอ่าน web_api.py แล้วค้นหาข้อความ
    (เช่น `"def continents_summary(" in API`) ต้องเปลี่ยนมาเรียกฟังก์ชันนี้แทน
    ไม่งั้นจะหาข้อความไม่เจอเพราะย้ายไฟล์ไปแล้ว ทั้งที่โค้ดจริงยังอยู่ครบ
    """
    parts = [(_ROOT / "license_server" / "web_api.py").read_text(encoding="utf-8")]
    api_web_dir = _ROOT / "license_server" / "api_web"
    if api_web_dir.is_dir():
        for f in sorted(api_web_dir.rglob("*.py")):
            parts.append(f.read_text(encoding="utf-8"))
    return "\n".join(parts)


@functools.lru_cache(maxsize=1)
def play_js_source():
    """ซอร์สหน้าเล่นเกมทั้งหมดรวมกัน — หลังผ่า play.js ออกเป็นหลายไฟล์ (09-02 ขั้นที่ 5)

    เทสที่เคยอ่าน play.js ไฟล์เดียวให้เรียกตัวนี้แทน จะได้ไม่พังตอนย้ายฟังก์ชัน
    wm* ไปไฟล์ games/worms_ui.js (หรือร้านค้าไป shop_ui.js) — ลิสต์ parts ด้านล่าง
    เช็ค exists() ทีละไฟล์ เผื่อยังไม่มีไฟล์ใหม่ (ระหว่างก้อนคอมมิตแรก ๆ)
    """
    parts = ["play.js", "games/worms_ui.js", "shop_ui.js"]
    return "\n".join(
        (_WEB / p).read_text(encoding="utf-8") for p in parts if (_WEB / p).exists()
    )


@pytest.fixture(autouse=True)
def _fresh_rate_limiter():
    """ล้างตัวนับจำกัดอัตราก่อนทุกเทส

    ตัวนับเป็นสถานะระดับโมดูล (ตั้งใจให้เป็นแบบนั้น — เซิร์ฟเดียวไม่ต้องพึ่ง Redis)
    ถ้าไม่ล้าง เทสที่ขอโค้ดล็อกอินหลายสิบตัวจะไปกินโควตากันเอง แล้วพังทั้งที่โค้ดถูก
    """
    try:
        from license_server import rate_limit
    except Exception:
        yield
        return
    rate_limit.reset()
    yield
    rate_limit.reset()
