"""ประกอบไฟล์ทั้งหมดเป็นชุดติดตั้ง (BotManager-Setup.zip) — รันหลัง build.spec/build_nuitka.py เสร็จแล้ว

รัน: python make_installer_zip.py
ผลลัพธ์: dist/BotManager-Setup.zip (แตกแล้วดับเบิลคลิก Install.bat เพื่อติดตั้ง)
"""
import os
import shutil
import zipfile

ROOT = os.path.dirname(os.path.abspath(__file__))
STAGE_DIR = os.path.join(ROOT, "dist", "BotManager-Setup")
ZIP_PATH = os.path.join(ROOT, "dist", "BotManager-Setup.zip")

FILES = [
    (os.path.join(ROOT, "dist", "BotManager.exe"), "BotManager.exe"),
    (os.path.join(ROOT, "config.example.json"), "config.example.json"),
    (os.path.join(ROOT, "installer", "Install.bat"), "Install.bat"),
    (os.path.join(ROOT, "installer", "install.ps1"), "install.ps1"),
    (os.path.join(ROOT, "installer", "uninstall.ps1"), "uninstall.ps1"),
]


def main():
    if not os.path.exists(FILES[0][0]):
        raise SystemExit("ไม่พบ dist/BotManager.exe — รัน `pyinstaller build.spec` หรือ `python build_nuitka.py` ก่อน")

    if os.path.exists(STAGE_DIR):
        shutil.rmtree(STAGE_DIR)
    os.makedirs(STAGE_DIR)

    for src, name in FILES:
        shutil.copy2(src, os.path.join(STAGE_DIR, name))

    if os.path.exists(ZIP_PATH):
        os.remove(ZIP_PATH)
    with zipfile.ZipFile(ZIP_PATH, "w", zipfile.ZIP_DEFLATED) as z:
        for _, name in FILES:
            z.write(os.path.join(STAGE_DIR, name), name)

    version_path = os.path.join(ROOT, "VERSION")
    version = open(version_path, encoding="utf-8").read().strip() if os.path.exists(version_path) else "unknown"
    print(f"เสร็จแล้ว: {ZIP_PATH} (เวอร์ชัน {version})")


if __name__ == "__main__":
    main()
