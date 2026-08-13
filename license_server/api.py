"""API ที่ให้ตัวบอทของลูกค้าเรียกมาเช็ค/ผูกคีย์ — ต้องเปิดโปรแกรมนี้ทิ้งไว้ (keygen_gui.py) บอทถึงจะสตาร์ทได้"""
import os
import secrets

from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel

from license_server import db

_HERE = os.path.dirname(os.path.abspath(__file__))
_SECRET_PATH = os.path.join(_HERE, "admin_secret.txt")


def get_or_create_admin_secret():
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
    from fastapi.responses import FileResponse
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
    if os.path.isdir(assets_dir):
        app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")
    if os.path.isdir(web_static):
        app.mount("/", StaticFiles(directory=web_static, html=True), name="web")

    return app


app = create_app()
