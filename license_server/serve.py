"""รันบอท + เว็บเกม พร้อมกันบนคลาวด์ — ไม่มีหน้าต่าง GUI (Oracle Cloud 24 ชม.)

ต่างจาก keygen_gui.py ตรงที่:
  - ไม่มี tkinter (เครื่องคลาวด์ไม่มีจอ)
  - ไม่มี cloudflared (ใช้โดเมนจริงผ่าน Caddy แทน)
  - ค่าลับอ่านจาก env var (ไม่มี config.json บนคลาวด์)

รัน: python -m license_server.serve
"""
import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# คอนโซล Windows เป็น cp874 — print อีโมจิแล้วโปรแกรมตายทั้งตัว
# (Docker เป็น UTF-8 อยู่แล้ว แต่กันไว้เผื่อรันเทสในเครื่อง)
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")

PORT = int(os.environ.get("PORT", "8790"))
RUN_BOT = os.environ.get("RUN_BOT", "1") != "0"


def _ensure_dirs():
    """สร้างโฟลเดอร์ของฐานข้อมูลก่อน — sqlite ไม่สร้างโฟลเดอร์ให้เอง

    volume ที่เพิ่ง mount รอบแรกเป็นโฟลเดอร์เปล่า ขาดข้อนี้จะ crash ตอนบูตครั้งแรก
    """
    for key in ("GAME_DB_PATH", "WEB_DB_PATH", "LICENSE_DB_PATH"):
        path = os.environ.get(key)
        if path:
            os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    upload = os.environ.get("UPLOAD_DIR")
    if upload:
        os.makedirs(upload, exist_ok=True)


async def _serve_web():
    import uvicorn

    from license_server.api import create_app

    config = uvicorn.Config(create_app(), host="0.0.0.0", port=PORT,
                            log_level="info", access_log=False)
    await uvicorn.Server(config).serve()


async def _serve_bot():
    """บอทล้มต้องไม่ลากเว็บตายไปด้วย — เว็บเกมยังต้องเล่นได้แม้ Discord มีปัญหา"""
    from bot import main as bot_main

    try:
        await bot_main.main()
    except asyncio.CancelledError:
        raise
    except Exception as e:
        print(f"❌ บอทหยุดทำงาน: {type(e).__name__}: {e}", flush=True)
        print("   เว็บเกมยังเปิดอยู่ — แก้แล้วรีสตาร์ท container", flush=True)


async def main():
    _ensure_dirs()
    tasks = [_serve_web()]
    if RUN_BOT:
        tasks.append(_serve_bot())
    else:
        print("⏸️ ปิดบอทไว้ (RUN_BOT=0) — เปิดแค่เว็บ", flush=True)
    print(f"🚀 เริ่มระบบ พอร์ต {PORT}", flush=True)
    await asyncio.gather(*tasks)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n🛑 ปิดระบบเรียบร้อย", flush=True)
