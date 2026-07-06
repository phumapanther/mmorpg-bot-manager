import json, os

from app_paths import get_app_root

_ROOT = get_app_root()
CONFIG_PATH = os.path.join(_ROOT, "config.json")
EXAMPLE_PATH = os.path.join(_ROOT, "config.example.json")

_cache = None

def _load_file(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)

def _merge_missing(target, defaults):
    for key, default_value in defaults.items():
        if key not in target:
            target[key] = default_value
        elif isinstance(target[key], dict) and isinstance(default_value, dict):
            _merge_missing(target[key], default_value)
    return target

def get_config():
    global _cache
    if _cache is not None:
        return _cache
    try:
        data = _load_file(CONFIG_PATH)
    except (FileNotFoundError, json.JSONDecodeError):
        data = None
    if data is not None:
        try:
            defaults = _load_file(EXAMPLE_PATH)
            data = _merge_missing(data, defaults)
        except (FileNotFoundError, json.JSONDecodeError):
            pass
        _cache = data
        return _cache
    try:
        _cache = _load_file(EXAMPLE_PATH)
        return _cache
    except (FileNotFoundError, json.JSONDecodeError):
        pass
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

def get_channel_mention(key):
    ch = get_config().get("channels", {}).get(key)
    return bool(ch.get("mention_player", False)) if ch else False

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

def get_skill_config(class_name, skill_name):
    return dict(get_config().get("skills", {}).get(class_name, {}).get(skill_name, {}))

def get_role_bonuses(bonus_type):
    entries = get_config().get("role_bonuses", [])
    result = []
    for e in entries:
        if e.get("bonus_type") == bonus_type and e.get("role_id") is not None:
            result.append({"role_id": int(e["role_id"]), "value": float(e.get("value", 1.0))})
    return result

def get_shop_items():
    items = get_config().get("shop_items", [])
    result = []
    for it in items:
        it2 = dict(it)
        if it2.get("role_id") is not None:
            it2["role_id"] = int(it2["role_id"])
        result.append(it2)
    return result

def get_item_config(item_id):
    return dict(get_config().get("item_catalog", {}).get("items", {}).get(item_id, {}))

def get_all_items():
    return dict(get_config().get("item_catalog", {}).get("items", {}))

def get_armor_stats(key):
    return dict(get_config().get("item_catalog", {}).get("armor_stats", {}).get(key, {}))

def get_weapon_stats(key):
    return dict(get_config().get("item_catalog", {}).get("weapon_stats", {}).get(key, {}))

def get_bag_stats(key):
    return dict(get_config().get("item_catalog", {}).get("bag_stats", {}).get(key, {}))

def get_crafting_recipe(item_id):
    return dict(get_config().get("item_catalog", {}).get("crafting_recipes", {}).get(item_id, {}))

def get_rank_rewards():
    entries = get_config().get("rank_rewards", {}).get("ranks", [])
    result = []
    for e in entries:
        e2 = dict(e)
        if e2.get("role_id") is not None:
            e2["role_id"] = int(e2["role_id"])
        result.append(e2)
    return result

def get_rank_reward_cooldown_hours():
    return float(get_config().get("rank_rewards", {}).get("cooldown_hours", 24))

def get_payment_config():
    return dict(get_config().get("payment", {}))

def get_gacha_price():
    return int(get_config().get("auto_trade_roles", {}).get("gacha_price", 10000000))

def get_gacha_pool_price():
    return int(get_config().get("auto_trade_roles", {}).get("gacha_pool_price", 20000000))

def get_token():
    return get_config().get("bot_token", "")

def get_license_key():
    return get_config().get("license_key", "")

def get_guild_id():
    return get_config().get("guild_id")
