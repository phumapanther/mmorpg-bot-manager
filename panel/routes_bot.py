from fastapi import APIRouter
from panel import process_manager

router = APIRouter(prefix="/api/bot")

@router.post("/start")
def start(): process_manager.start(); return process_manager.status()

@router.post("/stop")
def stop(): process_manager.stop(); return process_manager.status()

@router.post("/restart")
def restart(): process_manager.restart(); return process_manager.status()

@router.get("/status")
def status(): return process_manager.status()

@router.get("/log")
def log(): return {"lines": process_manager.get_log()}
