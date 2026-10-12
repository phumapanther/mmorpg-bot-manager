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
# NAS: ลิงก์เว็บสุ่มจาก Cloudflare Quick Tunnel — ตั้งค่านี้แล้วจะคอยจับลิงก์ใหม่ให้บอทแจก (docker-compose.nas.yml)
TUNNEL_METRICS_URL = os.environ.get("TUNNEL_METRICS_URL", "").strip()


# .env.example ใส่ค่าตัวอย่างไว้ — ถ้าลืมแก้แล้วเปิดสู่เน็ต รหัสหลังบ้านจะเป็นค่าที่ใครก็เดาได้
_ADMIN_SECRET_PLACEHOLDER = "ตั้งรหัสยาวๆสำหรับเข้าหลังบ้าน"


def _check_admin_secret():
    """บนเซิร์ฟสาธารณะ (NAS/คลาวด์) รหัสแอดมินเซ็นคุกกี้ session ทุกใบด้วย — อ่อนเมื่อไหร่ ปลอมสิทธิ์ได้ทันที
    จึงบังคับให้ตั้งจริง ≥24 ตัว ก่อนเปิดระบบ · รันในเครื่องตัวเอง (keygen_gui) ไม่ผ่านทางนี้ ไม่กระทบ
    """
    secret = os.environ.get("ADMIN_SECRET", "").strip()
    if not secret or secret == _ADMIN_SECRET_PLACEHOLDER or len(secret) < 24:
        print("❌ ADMIN_SECRET ยังไม่ปลอดภัย — ต้องตั้งใน .env ให้ยาว ≥24 ตัว (สร้างด้วย: openssl rand -hex 24)",
              flush=True)
        print("   รหัสนี้ใช้เซ็นคุกกี้ล็อกอินทุกใบ ถ้าอ่อนคนอื่นปลอมเป็นแอดมิน/ผู้เล่นได้ทันที", flush=True)
        sys.exit(1)


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
    _check_admin_secret()
    _ensure_dirs()
    tasks = [_serve_web()]
    if RUN_BOT:
        tasks.append(_serve_bot())
    else:
        print("⏸️ ปิดบอทไว้ (RUN_BOT=0) — เปิดแค่เว็บ", flush=True)
    if TUNNEL_METRICS_URL:
        from license_server.tunnel_url import watch_tunnel
        tasks.append(watch_tunnel(TUNNEL_METRICS_URL))
    print(f"🚀 เริ่มระบบ พอร์ต {PORT}", flush=True)
    await asyncio.gather(*tasks)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n🛑 ปิดระบบเรียบร้อย", flush=True)
