# license_server/web_api.py
"""ย้ายไปอยู่ license_server/api_web/ แล้ว (รื้อโครงสร้าง 09-02 ขั้นที่ 4)

โค้ดจริงทั้งหมด (route/ตัวช่วย/ค่าคงที่) อยู่ใน license_server/api_web/ แบ่งเป็น
controller ตามหมวด — ไฟล์นี้เหลือเป็นสะพานให้ของเก่าที่ยัง import
`from license_server import web_api` หรือเรียก `web_api.sign(...)`,
`web_api.router` ตรง ๆ ยังใช้งานได้เหมือนเดิมทุกอย่าง
"""
from license_server.api_web import *          # noqa: F401,F403
from license_server.api_web import router     # noqa: F401  ← api.py ใช้ตัวนี้

# ── re-export ชื่อที่ทดสอบ/โค้ดเก่าเรียกผ่าน web_api.<name> ตรง ๆ ──
# (import * ข้างบนดึงเฉพาะ router เข้ามา ไม่ได้ดึงของจาก submodule ย่อยให้อัตโนมัติ)
from license_server.api_web.deps import (  # noqa: F401
    GAME_DB_PATH, _ADMIN_TTL, _SESSION_TTL, _game_conn, _key, _money_now,
    _set_cookie, _user_lock, player_model_get, require_admin, require_player, sign, verify,
)
from license_server.api_web.auth import _CODE_CHARS, _CODE_RE, _CODE_TTL, _TICKET_RE  # noqa: F401
from license_server.api_web.topup import _slip_path  # noqa: F401
from license_server.api_web.adventure import _finish_special  # noqa: F401
from license_server.api_web.player import _dur_pct  # noqa: F401
