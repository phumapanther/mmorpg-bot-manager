"""ค่าตั้งต้นร่วมของเทสทั้งชุด"""
import pytest


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
