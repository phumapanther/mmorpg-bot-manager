from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
import os
from panel import config_store, routes_config, routes_discord, routes_bot, routes_images

app = FastAPI(title="MMORPG Bot Manager")
config_store.ensure_exists()
app.include_router(routes_config.router)
app.include_router(routes_discord.router)
app.include_router(routes_bot.router)
app.include_router(routes_images.router)
_static = os.path.join(os.path.dirname(__file__), "static")


@app.middleware("http")
async def _no_cache(request, call_next):
    """ห้ามเบราว์เซอร์ cache หน้า Panel — อัปเดตแล้วต้องเห็นของใหม่ทันที ไม่ต้อง Ctrl+F5"""
    response = await call_next(request)
    if request.url.path.endswith((".html", ".js", ".css")) or request.url.path == "/":
        response.headers["Cache-Control"] = "no-store, must-revalidate"
    return response


app.mount("/", StaticFiles(directory=_static, html=True), name="static")
