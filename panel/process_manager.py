import os, sys, subprocess, threading, collections

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# default: run the packaged/launcher bot; overridable in tests
BOT_CMD = [sys.executable, "-u", "-m", "bot.main"]

_proc = None
_log = collections.deque(maxlen=1000)
_lock = threading.Lock()

def _pump(pipe):
    for line in iter(pipe.readline, ""):
        _log.append(line.rstrip("\n"))
    pipe.close()

def start():
    global _proc
    with _lock:
        if _proc and _proc.poll() is None:
            return
        env = dict(os.environ, PYTHONIOENCODING="utf-8")
        _proc = subprocess.Popen(BOT_CMD, cwd=_ROOT, env=env,
                                 stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                 text=True, encoding="utf-8", bufsize=1)
        threading.Thread(target=_pump, args=(_proc.stdout,), daemon=True).start()

def stop():
    global _proc
    with _lock:
        if _proc and _proc.poll() is None:
            _proc.terminate()
            try:
                _proc.wait(timeout=8)
            except subprocess.TimeoutExpired:
                _proc.kill()
        _proc = None

def restart():
    stop(); start()

def status():
    running = _proc is not None and _proc.poll() is None
    return {"running": running, "pid": _proc.pid if running else None}

def get_log(max_lines=200):
    return list(_log)[-max_lines:]
