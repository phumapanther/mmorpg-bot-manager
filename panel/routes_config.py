import os

from fastapi import APIRouter
from panel import config_store

router = APIRouter()

_VERSION_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "VERSION")

@router.get("/api/version")
def get_version():
    try:
        with open(_VERSION_PATH, encoding="utf-8") as f:
            return {"version": f.read().strip()}
    except FileNotFoundError:
        return {"version": "unknown"}

@router.get("/api/config")
def get_config():
    return config_store.load()

@router.put("/api/config")
def put_config(data: dict):
    config_store.save(data)
    return {"ok": True}
