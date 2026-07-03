import sys, time
from panel import process_manager

def test_start_stop(monkeypatch):
    # run a short-lived python that prints, instead of the real bot
    monkeypatch.setattr(process_manager, "BOT_CMD",
                        [sys.executable, "-u", "-c", "import time;print('hi');time.sleep(30)"])
    process_manager.start()
    time.sleep(1)
    assert process_manager.status()["running"] is True
    process_manager.stop()
    time.sleep(1)
    assert process_manager.status()["running"] is False
