import sys, threading, time
import uvicorn

from bot.open_browser import open_url

def run_bot():
    from bot import main as bot_main
    import asyncio
    asyncio.run(bot_main.main())

def run_panel():
    from panel import config_store
    config_store.ensure_exists()
    port = config_store.load().get("panel_port", 8770)
    threading.Thread(
        target=lambda: (time.sleep(1.5), open_url(f"http://localhost:{port}")),
        daemon=True).start()
    uvicorn.run("panel.server:app", host="127.0.0.1", port=port, log_level="warning")

if __name__ == "__main__":
    if "--run-bot" in sys.argv:
        run_bot()
    else:
        run_panel()
