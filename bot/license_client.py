"""เช็คไลเซนส์กับ License Server ทุกครั้งที่บอทสตาร์ท — ปิด License Server (keygen_gui.py) เมื่อไหร่ บอทจะสตาร์ทไม่ได้

จุดที่ต้องแก้เวลาลิงก์ License Server เปลี่ยน (เช่น tunnel รีสตาร์ทแล้วได้ลิงก์ใหม่):
แก้ไฟล์ "LICENSE_SERVER_URL.txt" ที่ root ของโปรเจ็ค (ไฟล์ข้อความธรรมดา บรรทัดเดียว ไม่ต้องแตะโค้ด)
แล้ว build ใหม่ (pyinstaller build.spec + python make_installer_zip.py) ส่ง zip ใหม่ให้ลูกค้ากด Install.bat ทับ

ponytail: ต้อง "ฝัง" ค่านี้เข้าไปในตัว exe ตอน build เท่านั้น (อ่านจากไฟล์ที่ bundle มาด้วย ไม่ใช่จาก config.json
ที่อยู่ข้างๆ exe) — ถ้าให้ลูกค้าแก้ไฟล์นี้ได้เอง ผู้ซื้อจะชี้ไปเซิร์ฟเวอร์ปลอมของตัวเองแล้วบายพาสการเช็คได้ทันที
"""
import hashlib
import os
import platform
import uuid

import httpx

_HERE = os.path.dirname(os.path.abspath(__file__))
_URL_FILE = os.path.join(os.path.dirname(_HERE), "LICENSE_SERVER_URL.txt")

try:
    with open(_URL_FILE, encoding="utf-8") as _f:
        LICENSE_SERVER_URL = _f.read().strip()
except FileNotFoundError:
    LICENSE_SERVER_URL = "http://YOUR-LICENSE-SERVER-ADDRESS:8790"


def get_machine_id():
    raw = f"{uuid.getnode()}:{platform.node()}:{platform.machine()}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:32]


def check_license(license_key, bot_token):
    """เรียก License Server เพื่อผูก/ยืนยันคีย์กับเครื่องนี้ — คืน (ok: bool, message: str)

    ponytail: ถ้ายังไม่ได้แก้ LICENSE_SERVER_URL จาก placeholder (เช่น ตอน dev/ทดสอบเอง)
    ข้ามการเช็คไปเลย ไม่งั้นจะสตาร์ทบอทตัวเองไม่ได้เลยจนกว่าจะตั้ง License Server จริงก่อน —
    การบังคับเช็คจะเริ่มมีผลก็ต่อเมื่อแก้ค่านี้เป็นที่อยู่เซิร์ฟเวอร์จริงก่อน build แจกลูกค้าแล้วเท่านั้น
    """
    if "YOUR-LICENSE-SERVER-ADDRESS" in LICENSE_SERVER_URL:
        return True, "ℹ️ ยังไม่ได้ตั้งค่า License Server (โหมด dev) — ข้ามการเช็คคีย์"

    if not license_key:
        return False, "⚠️ ยังไม่ได้ใส่ License Key — เปิดหน้า Panel แท็บ Setup แล้วกรอกคีย์ก่อนสตาร์ทบอท"

    machine_id = get_machine_id()
    bot_token_hash = hashlib.sha256(bot_token.encode("utf-8")).hexdigest() if bot_token else ""

    # เครื่องที่รัน License Server เองอยู่แล้ว (มีโฟลเดอร์ license_server = เครื่องเจ้าของเกม):
    # tunnel ล่ม/ลิงก์ในไฟล์เก่า ก็ยังเช็คผ่าน localhost ได้เสมอ — เครื่องลูกค้าไม่มีโฟลเดอร์นี้ จึงไม่มีทางบายพาส
    urls = [LICENSE_SERVER_URL]
    if os.path.isdir(os.path.join(os.path.dirname(_HERE), "license_server")):
        urls.append("http://localhost:8790")

    resp = None
    for base in urls:
        try:
            resp = httpx.post(
                f"{base}/redeem",
                json={"key": license_key.strip(), "machine_id": machine_id, "bot_token_hash": bot_token_hash},
                timeout=8,
            )
            break
        except httpx.HTTPError:
            continue
    if resp is None:
        return False, "⚠️ ติดต่อ License Server ไม่ได้ — ต้องเปิดโปรแกรม License Server/KeyGen ทิ้งไว้ก่อนสตาร์ทบอท"

    if resp.status_code == 200:
        return True, "✅ ยืนยัน License Key สำเร็จ"
    if resp.status_code == 404:
        return False, "❌ License Key ไม่ถูกต้อง"
    if resp.status_code == 403:
        return False, "❌ License Key นี้ถูกใช้งานกับเครื่องอื่นไปแล้ว (1 คีย์ใช้ได้ 1 เครื่องเท่านั้น)"
    return False, f"⚠️ License Server ตอบกลับผิดปกติ (HTTP {resp.status_code})"
