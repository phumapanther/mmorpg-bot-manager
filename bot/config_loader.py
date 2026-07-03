import json, os

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
CONFIG_PATH = os.path.join(_ROOT, "config.json")
EXAMPLE_PATH = os.path.join(_ROOT, "config.example.json")

_cache = None

def _load_file(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)

def get_config():
    global _cache
    if _cache is not None:
        return _cache
    for path in (CONFIG_PATH, EXAMPLE_PATH):
        try:
            _cache = _load_file(path)
            return _cache
        except (FileNotFoundError, json.JSONDecodeError):
            continue
    _cache = {}
    return _cache

def reload_config():
    global _cache
    _cache = None

def get_channel_id(key):
    ch = get_config().get("channels", {}).get(key)
    if not ch:
        return None
    cid = ch.get("channel_id")
    return int(cid) if cid is not None else None

def get_role_ids(group):
    g = get_config().get("permission_groups", {}).get(group)
    if not g:
        return []
    return [int(r) for r in g.get("role_ids", [])]

def get_trade_roles(faction):
    roles = get_config().get("auto_trade_roles", {}).get(faction, [])
    result = []
    for r in roles:
        r2 = dict(r)
        if r2.get("role_id") is not None:
            r2["role_id"] = int(r2["role_id"])
        result.append(r2)
    return result

def get_gacha_price():
    return int(get_config().get("auto_trade_roles", {}).get("gacha_price", 10000000))

def get_gacha_pool_price():
    return int(get_config().get("auto_trade_roles", {}).get("gacha_pool_price", 20000000))

def get_token():
    return get_config().get("bot_token", "")

def get_guild_id():
    return get_config().get("guild_id")
