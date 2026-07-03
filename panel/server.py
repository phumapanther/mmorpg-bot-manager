from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
import os
from panel import config_store, routes_config

app = FastAPI(title="MMORPG Bot Manager")
config_store.ensure_exists()
app.include_router(routes_config.router)
# routes_discord and routes_bot mounted in later tasks
_static = os.path.join(os.path.dirname(__file__), "static")
app.mount("/", StaticFiles(directory=_static, html=True), name="static")
