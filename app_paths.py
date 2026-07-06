"""หาโฟลเดอร์ root ของแอปให้ถูกต้อง ทั้งตอนรันจาก source และตอนถูกแพ็กเป็น onefile exe (PyInstaller/Nuitka)

บั๊กที่แก้: PyInstaller onefile แตกไฟล์ทั้งหมดไปไว้ที่ temp dir ชั่วคราว (sys._MEIPASS) ตอนรัน แล้วลบทิ้งตอนปิดโปรแกรม
ถ้าคำนวณ root จาก __file__ เฉยๆ ตอน frozen จะได้ path ในเทมป์ที่หายไปทุกครั้ง ทำให้ config.json/game_data.db
ถูกสร้างในที่ที่หายทุกครั้งที่เปิดโปรแกรมใหม่ — ต้องใช้ตำแหน่งไฟล์ .exe จริง (sys.executable) แทนตอน frozen
"""
import os
import sys


def get_app_root():
    if getattr(sys, "frozen", False):
        return os.path.dirname(os.path.abspath(sys.executable))
    return os.path.dirname(os.path.abspath(__file__))
