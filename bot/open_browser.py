"""เปิดลิงก์ด้วย Microsoft Edge — ใช้ร่วมกันทั้ง Panel และเว็บไซต์เกม

หา msedge.exe จากที่ติดตั้งมาตรฐาน ไม่เจอ (เครื่องอื่น/ลงที่อื่น) = ตกกลับเบราว์เซอร์เริ่มต้น
เกมต้องไม่พังเพราะไม่มี Edge
"""
import os
import webbrowser

EDGE_PATHS = [
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
]


def _edge():
    for path in EDGE_PATHS:
        if os.path.isfile(path):
            return path
    return None


def open_url(url):
    """เปิด url ใน Edge — คืน True ถ้าเปิดด้วย Edge สำเร็จ, False = ใช้เบราว์เซอร์เริ่มต้นแทน"""
    path = _edge()
    if path:
        try:
            webbrowser.get(f'"{path}" %s').open(url)
            return True
        except webbrowser.Error as e:
            print(f"⚠️ [Browser] เปิด Edge ไม่ได้ ({e}) — ใช้เบราว์เซอร์เริ่มต้นแทน")
    webbrowser.open(url)
    return False
