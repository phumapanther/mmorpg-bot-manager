"""แพ็กเป็น .exe ด้วย Nuitka แทน PyInstaller

ทำไมต้อง Nuitka: PyInstaller (build.spec) แค่ห่อ Python bytecode (.pyc) ไว้ในไฟล์เดียว
ซึ่งมีเครื่องมือ decompile (เช่น decompyle3) แกะกลับเป็นซอร์สที่อ่านได้เกือบเป๊ะ — ไม่ตรงกับ
requirement ที่ห้ามให้ผู้ซื้อดูซอร์สโค้ด Nuitka คอมไพล์ Python เป็นภาษา C แล้วคอมไพล์ต่อเป็นไบนารีเครื่องจริง
จึงไม่มี bytecode ให้แกะ (ยกระดับการป้องกันขึ้นมาก แต่ไม่มีอะไร "แกะไม่ได้ 100%" — วิศวกรย้อนกลับที่เก่งพอ
ยังไล่ตาม disassembly ของไบนารีได้เสมอ)

ก่อนรัน: ต้องมี C compiler (Visual Studio Build Tools หรือ MinGW-w64) ติดตั้งไว้แล้ว — Nuitka
เองไม่ได้ติดตั้ง compiler ให้ (ถ้ายังไม่มีจะรันสคริปต์นี้ไม่ผ่าน ให้ติดตั้งก่อน)

รัน: python build_nuitka.py
"""
import subprocess
import sys

CMD = [
    sys.executable, "-m", "nuitka",
    "--onefile",
    "--standalone",
    "--assume-yes-for-downloads",
    "--include-package=bot",
    "--include-package=panel",
    # ponytail: ห้ามใส่ --include-package=license_server ตรงนี้ — นั่นคือโปรแกรมฝั่งผู้ขาย/แอดมิน
    # (เจนคีย์ + เก็บ licenses.db) ต้องอยู่แค่เครื่องผู้ขายเท่านั้น ห้ามติดไปกับ exe ที่แจกลูกค้า
    "--include-data-dir=panel/static=panel/static",
    "--include-data-files=config.example.json=config.example.json",
    "--include-data-files=VERSION=VERSION",
    "--include-data-files=LICENSE_SERVER_URL.txt=LICENSE_SERVER_URL.txt",
    "--output-dir=dist_nuitka",
    "--output-filename=BotManager.exe",
    "--company-name=YourCompany",
    "--product-name=BotManager",
    "launcher.py",
]

if __name__ == "__main__":
    print("กำลังคอมไพล์ด้วย Nuitka (ใช้เวลาหลายนาที ครั้งแรกอาจโหลดตัวช่วยคอมไพล์เพิ่ม)...")
    subprocess.run(CMD, check=True)
    print("เสร็จแล้ว: dist_nuitka/BotManager.exe")
