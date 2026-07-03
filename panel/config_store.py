import json, os, shutil, tempfile

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
CONFIG_PATH = os.path.join(_ROOT, "config.json")
EXAMPLE_PATH = os.path.join(_ROOT, "config.example.json")

def ensure_exists():
    if not os.path.exists(CONFIG_PATH) and os.path.exists(EXAMPLE_PATH):
        shutil.copyfile(EXAMPLE_PATH, CONFIG_PATH)

def load():
    with open(CONFIG_PATH, encoding="utf-8") as f:
        return json.load(f)

def save(data):
    d = os.path.dirname(CONFIG_PATH)
    fd, tmp = tempfile.mkstemp(dir=d, suffix=".tmp")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, CONFIG_PATH)
