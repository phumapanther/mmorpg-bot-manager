import os, sys, subprocess, threading, collections

from app_paths import get_app_root, get_shutdown_flag

_ROOT = get_app_root()
# default: run the packaged/launcher bot; overridable in tests
if getattr(sys, "frozen", False):
    BOT_CMD = [sys.executable, "--run-bot"]
else:
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
            # ขอปิดแบบสุภาพก่อน: วางไฟล์ธงให้บอทประกาศ 🔴 ในห้อง server_status แล้วปิดตัวเอง
            flag = get_shutdown_flag()
            try:
                open(flag, "w").close()
                _proc.wait(timeout=6)
            except (subprocess.TimeoutExpired, OSError):
                _proc.terminate()  # บอทไม่ตอบ (ค้าง/ยังไม่ ready) → จัดการแบบเดิม
                try:
                    _proc.wait(timeout=8)
                except subprocess.TimeoutExpired:
                    _proc.kill()
                    _proc.wait()
            finally:
                try:
                    if os.path.exists(flag):
                        os.remove(flag)
                except OSError:
                    pass
        _proc = None

def restart():
    stop(); start()

def status():
    p = _proc
    running = p is not None and p.poll() is None
    return {"running": running, "pid": p.pid if running else None}

def get_log(max_lines=200):
    return list(_log)[-max_lines:]
