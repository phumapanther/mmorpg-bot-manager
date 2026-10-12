"""🌐 จับลิงก์ Cloudflare Quick Tunnel บนเครื่องที่ไม่มีหน้าต่าง GUI (NAS / คลาวด์)

ที่บ้าน keygen_gui จับลิงก์สุ่มใหม่จาก cloudflared แล้วเขียน LICENSE_SERVER_URL.txt ให้
บน NAS ไม่มีหน้าต่าง → ถามช่อง /quicktunnel ของ cloudflared เอง (ตอบ {"hostname":"..."})
แล้วเขียนไฟล์เดียวกัน · บอทอ่านไฟล์นี้ใหม่ทุกครั้งที่แจกลิงก์ (web_link.website_url)
"""
import asyncio
import json
import os
import re
import urllib.request

# cloudflared ตอบแค่ชื่อโฮสต์ — รับเฉพาะ *.trycloudflare.com กันค่าแปลกถูกเขียนเป็นลิงก์แจกผู้เล่น
_HOST = re.compile(r"[a-z0-9-]+\.trycloudflare\.com")


def url_file():
    """ไฟล์เดียวกับที่บอทอ่าน (bot/apps/bot_game/web_link.py: URL_FILE)"""
    from app_paths import get_app_root
    return os.path.join(get_app_root(), "LICENSE_SERVER_URL.txt")


def save_tunnel_url(hostname, path=None):
    """เขียน https://<hostname> ลงไฟล์ลิงก์ — คืน True เมื่อเขียนลิงก์ใหม่จริง"""
    hostname = hostname.strip() if isinstance(hostname, str) else ""
    if not _HOST.fullmatch(hostname):
        return False
    url = f"https://{hostname}"
    path = path or url_file()
    try:
        with open(path, encoding="utf-8") as f:
            if f.read().strip() == url:
                return False
    except OSError:
        pass
    # เขียนแบบ atomic: บอทที่ !web/!login อ่านตอนไฟล์ถูก truncate จะได้ลิงก์ว่าง — เขียน tmp แล้ว replace
    tmp = f"{path}.tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(url + "\n")
    os.replace(tmp, path)
    return True


def _fetch(url):
    # ไม่ผ่าน proxy ใด ๆ — http_proxy ใน .env (env_file) ต้องไม่ถูกเอามาใช้กับ tunnel ภายใน
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    with opener.open(url, timeout=5) as r:
        return r.read()


def poll_once(metrics_url, path=None):
    """ถาม cloudflared หนึ่งครั้ง — tunnel ยังไม่ขึ้น/ตอบแปลก คืน False เงียบๆ รอบหน้าลองใหม่"""
    try:
        hostname = json.loads(_fetch(metrics_url)).get("hostname")
    except (OSError, ValueError, AttributeError):
        return False
    return save_tunnel_url(hostname, path)


async def watch_tunnel(metrics_url, every=30, warmup=5):
    """วนถามตลอดอายุโปรแกรม — cloudflared รีสตาร์ตเมื่อไหร่ ลิงก์ใหม่เข้าไฟล์ภายในครึ่งนาที

    ลิงก์เว็บเป็นแค่ความสะดวก — ห้าม error ที่นี่ลากบอท/เว็บตายทั้งคู่ (escape asyncio.gather)
    ตอนเพิ่งบูต tunnel ยังไม่ขึ้น → ถามถี่ทุก warmup วิ จนได้ลิงก์แรก แล้วค่อยลดเหลือ every
    """
    got_first = False
    while True:
        try:
            if await asyncio.to_thread(poll_once, metrics_url):
                got_first = True
                with open(url_file(), encoding="utf-8") as f:
                    print(f"🌐 ลิงก์เว็บใหม่: {f.read().strip()}", flush=True)
        except Exception as e:                       # noqa: BLE001 — กันทุกอย่าง ไม่ให้ลากระบบตาย
            print(f"⚠️ จับลิงก์ tunnel ไม่สำเร็จ (ข้ามรอบนี้): {type(e).__name__}: {e}", flush=True)
        await asyncio.sleep(every if got_first else warmup)
