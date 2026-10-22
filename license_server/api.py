"""API ที่ให้ตัวบอทของลูกค้าเรียกมาเช็ค/ผูกคีย์ — ต้องเปิดโปรแกรมนี้ทิ้งไว้ (keygen_gui.py) บอทถึงจะสตาร์ทได้"""
import hmac
import os
import secrets

from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel

from license_server import db

_HERE = os.path.dirname(os.path.abspath(__file__))
_SECRET_PATH = os.path.join(_HERE, "admin_secret.txt")


def get_or_create_admin_secret():
    # บนคลาวด์ส่งค่าผ่าน env — ไม่ต้องฝากไฟล์ลงดิสก์ใน container
    env_secret = os.environ.get("ADMIN_SECRET", "").strip()
    if env_secret:
        return env_secret
    if os.path.exists(_SECRET_PATH):
        return open(_SECRET_PATH, encoding="utf-8").read().strip()
    secret = secrets.token_hex(16)
    with open(_SECRET_PATH, "w", encoding="utf-8") as f:
        f.write(secret)
    return secret


class RedeemRequest(BaseModel):
    key: str
    machine_id: str
    bot_token_hash: str = ""


def create_app():
    db.init_db()

    # 🧱 เว็บเกมเขียน game_data.db ด้วย จึงต้องรับผิดชอบสคีมาของตัวเองด้วย
    # เดิมมีแต่บอทที่งอกคอลัมน์ใหม่ตอนสตาร์ท — เพิ่มฟีเจอร์แล้วรีสตาร์ทแต่เว็บ
    # ผู้เล่นจะเจอ "Internal Server Error" จนกว่าจะรีสตาร์ทบอท (เจอจริงตอนกระดานทอยเต๋า)
    try:
        import bot.models.player_model as _pm
        _pm.init_db()
    except Exception as e:
        print(f"⚠️ [WEB] เตรียมสคีมา game_data.db ไม่สำเร็จ: {e}")

    app = FastAPI(title="License Server")

    # 🔑 ระบบแจกคีย์ไลเซนส์ — ใช้เฉพาะเครื่องผู้ขาย (keygen_gui) · เซิร์ฟเกม/NAS ปิดด้วย LICENSE_API=0
    # ปิดไว้ = ไม่เปิดช่อง mint คีย์/ดูคีย์/redeem ออกสู่ลิงก์สาธารณะ (อยู่นอก /api/web จึงไม่มี rate limit)
    if os.environ.get("LICENSE_API") != "0":
        @app.post("/redeem")
        def redeem(req: RedeemRequest):
            ok, reason = db.redeem_key(req.key.strip(), req.machine_id, req.bot_token_hash)
            if not ok:
                code = 404 if reason == "invalid_key" else 403
                raise HTTPException(code, reason)
            return {"ok": True}

        @app.get("/keys")
        def keys(x_admin_secret: str = Header(default="")):
            if not hmac.compare_digest(x_admin_secret, get_or_create_admin_secret()):
                raise HTTPException(401, "invalid admin secret")
            return db.list_keys()

        @app.post("/generate")
        def generate(note: str = "", x_admin_secret: str = Header(default="")):
            if not hmac.compare_digest(x_admin_secret, get_or_create_admin_secret()):
                raise HTTPException(401, "invalid admin secret")
            return {"key": db.generate_key(note)}

    # 🌐 เว็บไซต์เกม (ข่าว/ข้อมูลเกม/ล็อกอิน/เติมเงิน) — โฮสต์บนแอปเดียวกัน ลิงก์ tunnel เดียวกัน
    # ⚠️ ต้องอยู่ท้ายสุดเสมอ: Starlette จับเส้นทางตามลำดับ — mount "/" ก่อน route จะทับ /redeem (405)
    from fastapi.responses import FileResponse, JSONResponse
    from fastapi.staticfiles import StaticFiles

    from license_server import web_api
    app.include_router(web_api.router)

    web_static = os.path.join(_HERE, "web_static")
    assets_dir = os.path.join(os.path.dirname(_HERE), "assets")
    if os.path.isdir(web_static):
        # URL สวยไม่ต้องมี .html — หน้าเพจทั้งหมดชี้ไฟล์ตรงใน web_static
        for _page in ("news", "game", "topup", "me", "login", "admin", "play", "wold", "fxlab", "calendar"):
            def _serve(page=_page):
                return FileResponse(os.path.join(web_static, f"{page}.html"))
            app.get(f"/{_page}", include_in_schema=False)(_serve)
    # 🔄 หน้าเว็บ/สคริปต์/สไตล์ ต้องให้เบราว์เซอร์ถามเซิร์ฟเวอร์ทุกครั้งว่ามีของใหม่ไหม
    # (ไฟล์ไม่เปลี่ยน = ตอบ 304 ไม่โหลดซ้ำ จึงไม่เปลืองเน็ต แต่แก้โค้ดแล้วเห็นทันทีไม่ต้อง Ctrl+F5)
    # เคสจริง: แก้ play.js แล้วผู้ใช้ยังเห็นของเก่าจนเมนูไม่เปิด หาสาเหตุกันอยู่นาน
    # 🚦 จำกัดอัตราการยิง API — กันสคริปต์ยิงรัวฟาร์มของ และกันยิงถล่มจนล่ม
    # นับรายคนจาก session ไม่ใช่รายไอพี (บ้าน/มือถือเน็ตเดียวกันจะโดนหางเลขกันหมด)
    @app.middleware("http")
    async def _rate_limit(request, call_next):
        from license_server import rate_limit
        path = request.url.path
        if path.startswith("/api/web"):
            # นับรายคนจาก IP จริง (cf-connecting-ip หลัง tunnel) — ขาดข้อนี้ถูกเลี่ยงง่าย:
            # หลัง tunnel ทุกคำขอมาจาก IP เดียว (ตู้ tunnel) และคนร้ายสลับคุกกี้ทุกครั้งได้บัคเก็ตใหม่เรื่อย ๆ
            who = (request.headers.get("cf-connecting-ip")
                   or request.cookies.get("web_session")
                   or (request.client.host if request.client else "?"))
            ok, retry = rate_limit.check(who[:64], path, request.method)
            if not ok:
                return JSONResponse(
                    {"detail": f"⏳ ยิงคำสั่งถี่เกินไป — รออีก {retry} วินาทีแล้วลองใหม่"},
                    status_code=429, headers={"Retry-After": str(retry)})
        return await call_next(request)

    @app.middleware("http")
    async def _no_stale_pages(request, call_next):
        resp = await call_next(request)
        path = request.url.path
        if path.endswith((".html", ".js", ".css", ".json")) or "." not in path.rsplit("/", 1)[-1]:
            resp.headers["Cache-Control"] = "no-cache, must-revalidate"
        return resp

    # 🛠️ Panel ตั้งค่าบอท — ย้ายจาก localhost:8770 มาไว้ใต้ /manage บนลิงก์เดียวกัน
    # ⚠️ ทุก route ต้องผ่าน require_admin — panel แก้ token/ตั้งค่า/รูปได้ทั้งหมด เปิดดิบ ๆ = ยึดบอทได้
    from fastapi import Depends, Request
    from fastapi.responses import RedirectResponse

    from starlette.routing import Route as _StarRoute

    from license_server.api_web.deps import require_admin, verify
    from panel import routes_config, routes_discord, routes_images
    _admin = [Depends(require_admin)]
    # ลงทะเบียนทีละ route (include_router เวอร์ชันนี้ไม่ลง) — ใส่ prefix /manage + require_admin ทุกตัว
    for _src in (routes_config.router, routes_discord.router, routes_images.router):
        for _rt in _src.routes:
            if isinstance(_rt, _StarRoute):
                app.add_api_route("/manage" + _rt.path, _rt.endpoint,
                                  methods=list(_rt.methods or []), dependencies=_admin,
                                  include_in_schema=False)

    # บน NAS บอทรันเป็น task ใน serve.py (ไม่ใช่ subprocess ที่ panel คุม) — ปุ่ม start จะเปิดบอทซ้ำ
    # ชนโทเค็น จึงแทนด้วย stub ปลอดภัย: โชว์ว่ารันอยู่ · start/stop ไม่ทำอะไร (รีสตาร์ตผ่าน Container Manager)
    @app.get("/manage/api/bot/status", dependencies=_admin, include_in_schema=False)
    def _bot_status():
        return {"running": True, "pid": None}

    @app.get("/manage/api/bot/log", dependencies=_admin, include_in_schema=False)
    def _bot_log():
        return {"lines": ["บอทรันใน container — ดู log จริงที่ Container Manager → server_ai-game-1",
                          "รีสตาร์ตบอท: Container Manager → Project → server_ai → Action → Restart"]}

    for _verb in ("start", "stop", "restart"):
        app.add_api_route(f"/manage/api/bot/{_verb}", lambda: {"running": True, "pid": None},
                          methods=["POST"], dependencies=_admin, include_in_schema=False)

    _panel_static = os.path.join(os.path.dirname(_HERE), "panel", "static")

    @app.get("/manage", include_in_schema=False)
    def _panel_index(request: Request):
        data = verify(request.cookies.get("web_admin", ""))
        if not (data and data.get("role") == "admin"):
            return RedirectResponse("/admin", status_code=302)   # ยังไม่ล็อกอิน → ไปหน้าแอดมิน
        return FileResponse(os.path.join(_panel_static, "index.html"))

    # ไฟล์โค้ด (ไม่มีความลับ) — ข้อมูลลับอยู่หลัง /manage/api/* ที่ require_admin
    @app.get("/manage/app.js", include_in_schema=False)
    def _panel_js():
        return FileResponse(os.path.join(_panel_static, "app.js"), media_type="text/javascript")

    @app.get("/manage/style.css", include_in_schema=False)
    def _panel_css():
        return FileResponse(os.path.join(_panel_static, "style.css"), media_type="text/css")

    if os.path.isdir(assets_dir):
        app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")
    if os.path.isdir(web_static):
        app.mount("/", StaticFiles(directory=web_static, html=True), name="web")

    return app


app = create_app()
