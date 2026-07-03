from fastapi import APIRouter
from panel import config_store

router = APIRouter()

@router.get("/api/config")
def get_config():
    return config_store.load()

@router.put("/api/config")
def put_config(data: dict):
    config_store.save(data)
    return {"ok": True}
