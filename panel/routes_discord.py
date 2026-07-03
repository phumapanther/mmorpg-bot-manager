from fastapi import APIRouter, HTTPException
import httpx
from panel import config_store, discord_fetch

router = APIRouter(prefix="/api/discord")

def _token():
    tok = config_store.load().get("bot_token", "")
    if not tok:
        raise HTTPException(400, "ยังไม่ได้ตั้ง token")
    return tok

@router.get("/guilds")
def guilds():
    try:
        return discord_fetch.list_guilds(_token())
    except httpx.HTTPStatusError as e:
        raise HTTPException(e.response.status_code, "token ไม่ถูกต้องหรือหมดสิทธิ์")

@router.get("/channels")
def channels(guild_id: int):
    return discord_fetch.list_channels(_token(), guild_id)

@router.get("/roles")
def roles(guild_id: int):
    return discord_fetch.list_roles(_token(), guild_id)
