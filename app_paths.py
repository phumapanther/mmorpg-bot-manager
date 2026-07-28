"""หาโฟลเดอร์ root ของแอปให้ถูกต้อง ทั้งตอนรันจาก source และตอนถูกแพ็กเป็น onefile exe (PyInstaller/Nuitka)

บั๊กที่แก้: PyInstaller onefile แตกไฟล์ทั้งหมดไปไว้ที่ temp dir ชั่วคราว (sys._MEIPASS) ตอนรัน แล้วลบทิ้งตอนปิดโปรแกรม
ถ้าคำนวณ root จาก __file__ เฉยๆ ตอน frozen จะได้ path ในเทมป์ที่หายไปทุกครั้ง ทำให้ config.json/game_data.db
ถูกสร้างในที่ที่หายทุกครั้งที่เปิดโปรแกรมใหม่ — ต้องใช้ตำแหน่งไฟล์ .exe จริง (sys.executable) แทนตอน frozen
"""
import os
import sys
import tempfile


def get_app_root():
    if getattr(sys, "frozen", False):
        return os.path.dirname(os.path.abspath(sys.executable))
    return os.path.dirname(os.path.abspath(__file__))


def get_shutdown_flag():
    """ธง 'ขอปิดบอท' ที่ panel วางไว้ให้บอทเห็น — ต้องอยู่นอกโฟลเดอร์ที่ถูกคลาวด์ซิงค์

    บั๊กที่แก้: โปรเจกต์อยู่ใน OneDrive ธงเป็นไฟล์ชั่วคราวที่สร้างแล้วลบใน 6 วินาที
    ถ้า OneDrive อัปโหลดทันก่อนลบ มันจะซิงค์ไฟล์กลับลงมาเองทีหลัง บอทหลักเห็นธงแล้ว
    ปิดตัวเองกลางอากาศทั้งที่ไม่มีใครสั่ง (บอทรองไม่โหลด cog นี้เลยไม่ดับตาม)
    เก็บไว้ในเทมป์ของเครื่องแทน — panel กับบอทรันเครื่องเดียวกันเสมอ จึงเห็นไฟล์เดียวกัน
    """
    return os.path.join(tempfile.gettempdir(), "mmorpg_bot_shutdown.flag")
