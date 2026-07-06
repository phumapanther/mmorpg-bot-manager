import json, os, shutil, tempfile

from app_paths import get_app_root

_ROOT = get_app_root()
CONFIG_PATH = os.path.join(_ROOT, "config.json")
EXAMPLE_PATH = os.path.join(_ROOT, "config.example.json")

def ensure_exists():
    if not os.path.exists(CONFIG_PATH) and os.path.exists(EXAMPLE_PATH):
        shutil.copyfile(EXAMPLE_PATH, CONFIG_PATH)

def _merge_missing(target, defaults):
    for key, default_value in defaults.items():
        if key not in target:
            target[key] = default_value
        elif isinstance(target[key], dict) and isinstance(default_value, dict):
            _merge_missing(target[key], default_value)
    return target

def load():
    with open(CONFIG_PATH, encoding="utf-8") as f:
        data = json.load(f)
    try:
        with open(EXAMPLE_PATH, encoding="utf-8") as f:
            defaults = json.load(f)
        data = _merge_missing(data, defaults)
    except (FileNotFoundError, json.JSONDecodeError):
        pass
    return data

def save(data):
    d = os.path.dirname(CONFIG_PATH)
    fd, tmp = tempfile.mkstemp(dir=d, suffix=".tmp")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, CONFIG_PATH)
