"""API ที่ให้ตัวบอทของลูกค้าเรียกมาเช็ค/ผูกคีย์ — ต้องเปิดโปรแกรมนี้ทิ้งไว้ (keygen_gui.py) บอทถึงจะสตาร์ทได้"""
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

    @app.post("/redeem")
    def redeem(req: RedeemRequest):
        ok, reason = db.redeem_key(req.key.strip(), req.machine_id, req.bot_token_hash)
        if not ok:
            code = 404 if reason == "invalid_key" else 403
            raise HTTPException(code, reason)
        return {"ok": True}

    @app.get("/keys")
    def keys(x_admin_secret: str = Header(default="")):
        if x_admin_secret != get_or_create_admin_secret():
            raise HTTPException(401, "invalid admin secret")
        return db.list_keys()

    @app.post("/generate")
    def generate(note: str = "", x_admin_secret: str = Header(default="")):
        if x_admin_secret != get_or_create_admin_secret():
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
        for _page in ("news", "game", "topup", "me", "login", "admin", "play"):
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
            who = (request.cookies.get("web_session")
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
        if path.endswith((".html", ".js", ".css")) or "." not in path.rsplit("/", 1)[-1]:
            resp.headers["Cache-Control"] = "no-cache, must-revalidate"
        return resp

    if os.path.isdir(assets_dir):
        app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")
    if os.path.isdir(web_static):
        app.mount("/", StaticFiles(directory=web_static, html=True), name="web")

    return app


app = create_app()
