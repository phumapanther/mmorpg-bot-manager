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

    return app


app = create_app()
