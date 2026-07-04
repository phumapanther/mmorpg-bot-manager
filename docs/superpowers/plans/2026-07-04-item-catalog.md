# Item Catalog & Extensible Item Effects Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move `ITEM_CONFIG`/`ARMOR_STATS`/`WEAPON_STATS`/`BAG_STATS`/`CRAFTING_RECIPES` out of hardcoded Python dicts into `config.json`, make `use_item`'s consumable/drop-item logic dispatch off a data-driven `effect` field instead of literal item IDs, fix two real bugs found while reading the code (heal-amount disconnected from config; new-player bag/capacity default mismatch), and add a Panel "Items" tab to edit all of it.

**Architecture:** `bot/config_loader.py` gains 6 read functions. Every file that currently does `from bot.views.profile_embed import ITEM_CONFIG` (etc.) removes that import; each function/method body that references the bare name `ITEM_CONFIG`/`ARMOR_STATS`/`WEAPON_STATS` gets ONE local-variable shadow line added at the top of that function (`ITEM_CONFIG = config_loader.get_all_items()`), so every existing `ITEM_CONFIG[...]`/`ITEM_CONFIG.get(...)` expression already in that function's body keeps working unchanged — this is a plain Python local-variable shadow, not a redesign, and mirrors the same "swap the data source, don't touch the formulas" approach already proven in the skill-config plan's Task 3 (`game_views.py` combat logic).

**Tech Stack:** Python 3.12, discord.py 2.x, FastAPI panel, pytest, vanilla JS panel frontend.

## Global Constraints

- Config is read at call time inside each function via `config_loader`, never held as a stale module-level constant.
- Every one of the 5 catalog default values in `config.example.json` must be byte-identical to what's CURRENTLY hardcoded in `bot/views/profile_embed.py` (except the 2 deliberate bug fixes named below) — a transcription error here silently changes game balance.
- Two deliberate bug fixes, not accidental changes: (1) heal potion's `effect_amount: 50` becomes a real config field instead of a hardcoded literal disconnected from `ITEM_CONFIG`; (2) `NEW_PLAYER_DEFAULTS["capacity"]` changes from `10` to `50` to match `BAG_STATS["Medium_Bag"]["capacity"]` (new players are supposed to start with a Medium bag's full capacity).
- `use_item`'s armor/weapon/bag auto-equip logic (already data-driven via `type`+`equip_key`) must NOT change at all — only the `type == "use"` and `type == "drop"` branches switch from literal-ID checks to `effect`-field dispatch.
- Keep `bot/` and `panel/` as separate packages with no cross-imports (existing architecture).

---

## File Structure

```
bot/
├── config_loader.py           # MODIFY: add get_item_config, get_all_items, get_armor_stats, get_weapon_stats, get_bag_stats, get_crafting_recipe
├── models/
│   └── player_model.py         # MODIFY: fix NEW_PLAYER_DEFAULTS["capacity"] 10 → 50
├── views/
│   ├── profile_embed.py        # MODIFY: delete the 5 module-level dicts; create_profile_embed reads via config_loader
│   └── game_views.py           # MODIFY: remove the dict import; add local shadow assignments in ~11 methods
├── cogs/
│   ├── player_commands.py      # MODIFY: use_item dispatches "use"/"drop" types via effect field; craft/recipes/drop/give read via config_loader
│   ├── admin_commands.py       # MODIFY: remove the dict import; add local shadow assignments in the affected commands
│   └── pvp_duel.py             # MODIFY: remove the dict import; add local shadow assignment
config.example.json             # MODIFY: add top-level "item_catalog" key (items/armor_stats/weapon_stats/bag_stats/crafting_recipes)
panel/static/
├── index.html                  # MODIFY: add "Items" tab button + section (5 sub-tables)
└── app.js                      # MODIFY: add render/save logic for the 5 sub-tables
tests/
└── test_config_loader.py       # MODIFY: add tests for the 6 new getters
```

---

### Task 1: config_loader — item/stat/recipe getters, config schema, and the two bug fixes

**Files:**
- Modify: `bot/config_loader.py`
- Modify: `config.example.json`
- Modify: `bot/models/player_model.py`
- Test: `tests/test_config_loader.py`

**Interfaces:**
- Produces:
  - `get_item_config(item_id: str) -> dict` — one item's full config dict, or `{}` if not found.
  - `get_all_items() -> dict[str, dict]` — the entire `item_catalog.items` mapping (item_id → item dict), for code that currently iterates `ITEM_CONFIG.items()`/`ITEM_CONFIG.keys()`.
  - `get_armor_stats(key: str) -> dict`, `get_weapon_stats(key: str) -> dict`, `get_bag_stats(key: str) -> dict` — one entry's stat dict, or `{}` if not found.
  - `get_crafting_recipe(item_id: str) -> dict` — `{"recipe": {ingredient_id: qty, ...}, "fail_rate": float}`, or `{}` if not found.

- [ ] **Step 1: Read `bot/views/profile_embed.py` in full first** to copy the CURRENT exact values of `ITEM_CONFIG` (28 entries), `ARMOR_STATS` (5), `WEAPON_STATS` (3), `BAG_STATS` (4), `CRAFTING_RECIPES` (11) verbatim into the new config section — do not retype from memory, copy-paste the real current values so nothing is mistyped.

- [ ] **Step 2: Add `"item_catalog"` to `config.example.json`**

Read the file first to find its current last key (should be `"shop_items"` after the skill-config plan) and insert this new top-level key after it, with a comma:

```json
  "item_catalog": {
    "items": {
      "1": {"name": "💉 ยาฮีล", "buy": 300, "sell": 100, "type": "use", "effect": "heal", "effect_amount": 50},
      "2": {"name": "🛠️ ใบซ่อมแซม", "buy": 500, "sell": 150, "type": "use", "effect": "repair"},
      "3": {"name": "🟫 เกราะหนังเบา", "buy": 1000, "sell": 300, "type": "armor", "equip_key": "Leather_L"},
      "4": {"name": "🟫 เกราะหนังหนัก", "buy": 3000, "sell": 900, "type": "armor", "equip_key": "Leather_H"},
      "5": {"name": "⬜ เกราะเหล็กเบา", "buy": 8000, "sell": 2400, "type": "armor", "equip_key": "Steel_L"},
      "6": {"name": "⬜ เกราะเหล็กหนัก", "buy": 20000, "sell": 6000, "type": "armor", "equip_key": "Steel_H"},
      "7": {"name": "⚔️ อาวุธเหล็ก", "buy": 6000, "sell": 1800, "type": "weapon", "equip_key": "Iron_Weapon"},
      "8": {"name": "🗡️ อาวุธในตำนาน", "buy": 9999999, "sell": 1, "type": "weapon", "equip_key": "Legen_Weapon"},
      "9": {"name": "🦴 เศษกระดูก", "buy": 100, "sell": 10, "type": "junk", "purchasable": false},
      "10": {"name": "🕸️ ใยแมงมุม", "buy": 150, "sell": 15, "type": "junk", "purchasable": false},
      "11": {"name": "💎 เศษอัญมณีหมองหม่น", "buy": 500, "sell": 50, "type": "junk", "purchasable": false},
      "12": {"name": "🪨 เศษหิน", "buy": 50, "sell": 5, "type": "junk", "purchasable": false},
      "13": {"name": "🪵 เศษไม้", "buy": 30, "sell": 3, "type": "junk", "purchasable": false},
      "14": {"name": "🧪 ขวดสารเคมี", "buy": 200, "sell": 20, "type": "junk", "purchasable": false},
      "15": {"name": "🧵 เศษด้าย", "buy": 20, "sell": 2, "type": "junk", "purchasable": false},
      "16": {"name": "🪶 ขนนก", "buy": 40, "sell": 4, "type": "junk", "purchasable": false},
      "17": {"name": "🪙 เหรียญเก่า", "buy": 100, "sell": 10, "type": "junk", "purchasable": false},
      "18": {"name": "🧱 ก้อนอิฐ", "buy": 60, "sell": 6, "type": "junk", "purchasable": false},
      "19": {"name": "👜 กระเป๋ากลาง", "buy": 15000, "sell": 3000, "type": "bag", "equip_key": "Medium_Bag"},
      "20": {"name": "👜 กระเป๋าใหญ่", "buy": 40000, "sell": 8000, "type": "bag", "equip_key": "Large_Bag"},
      "21": {"name": "🌌 กระเป๋าเวทมนตร์", "buy": 9999999, "sell": 1, "type": "bag", "equip_key": "Magic_Bag"},
      "22": {"name": "📜ใบวาปเมือง", "buy": 500, "sell": 50, "type": "drop", "purchasable": false, "effect": "set_state", "effect_value": "warp_village"},
      "23": {"name": "🔑กุญแจวาปดันเจี้ยน", "buy": 2000, "sell": 200, "type": "drop", "purchasable": false, "effect": "set_state", "effect_value": "warp_dungeon"},
      "24": {"name": "📃ใบเชิญมินิบอส", "buy": 8000, "sell": 1, "type": "drop", "purchasable": false, "effect": "set_state", "effect_value": "mini_summon"},
      "25": {"name": "📃ใบเชิญบอสหลัก", "buy": 35000, "sell": 1, "type": "drop", "purchasable": false, "effect": "set_state", "effect_value": "main_summon"},
      "26": {"name": "📃ใบเชิญบอสไร้พ่าย", "buy": 80000, "sell": 1, "type": "drop", "purchasable": false, "effect": "set_state", "effect_value": "unbeatable_summon"},
      "27": {"name": "📡เรดาร์สแกนกล่องสมบัติ", "buy": 3000, "sell": 300, "type": "drop", "purchasable": false, "effect": "set_state", "effect_value": "scan_box"},
      "28": {"name": "💌ใบชุบชีวิต", "buy": 5000, "sell": 500, "type": "drop", "purchasable": false, "effect": "revive"}
    },
    "armor_stats": {
      "None":      {"name": "👕 เสื้อผ้าธรรมดา", "hp": 0,   "eva": 85, "dur": 100, "vis": 1},
      "Leather_L": {"name": "🟫 เกราะหนังเบา",   "hp": 20,  "eva": 70, "dur": 150, "vis": 3},
      "Leather_H": {"name": "🟫 เกราะหนังหนัก",  "hp": 30,  "eva": 60, "dur": 200, "vis": 5},
      "Steel_L":   {"name": "⬜ เกราะเหล็กเบา",  "hp": 50,  "eva": 40, "dur": 300, "vis": 7},
      "Steel_H":   {"name": "⬜ เกราะเหล็กหนัก", "hp": 100, "eva": 20, "dur": 500, "vis": 9}
    },
    "weapon_stats": {
      "Wooden_Weapon": {"name": "🪵 อาวุธไม้",     "atk": 10, "dur": 50},
      "Iron_Weapon":   {"name": "⚔️ อาวุธเหล็ก",   "atk": 30, "dur": 150},
      "Legen_Weapon":  {"name": "🗡️ อาวุธในตำนาน", "atk": 999, "dur": 1000}
    },
    "bag_stats": {
      "Small_Bag": {"name": "🎒 กระเป๋าเล็ก", "capacity": 10},
      "Medium_Bag": {"name": "🎒 กระเป๋ากลาง", "capacity": 50},
      "Large_Bag": {"name": "🎒 กระเป๋าใหญ่", "capacity": 100},
      "Magic_Bag": {"name": "🎒 กระเป๋าเวทมนตร์", "capacity": 0}
    },
    "crafting_recipes": {
      "1": {"recipe": {"9": 2, "12": 1}, "fail_rate": 0.1},
      "2": {"recipe": {"18": 1, "14": 1}, "fail_rate": 0.15},
      "3": {"recipe": {"15": 5, "10": 3}, "fail_rate": 0.25},
      "7": {"recipe": {"9": 5, "11": 1}, "fail_rate": 0.4},
      "22": {"recipe": {"9": 3, "12": 2}, "fail_rate": 0.05},
      "23": {"recipe": {"14": 2, "13": 3}, "fail_rate": 0.15},
      "24": {"recipe": {"11": 1, "14": 3, "3": 1}, "fail_rate": 0.25},
      "25": {"recipe": {"11": 3, "7": 1, "14": 5}, "fail_rate": 0.4},
      "26": {"recipe": {"11": 5, "6": 1, "27": 1}, "fail_rate": 0.6},
      "27": {"recipe": {"14": 3, "12": 5}, "fail_rate": 0.2},
      "28": {"recipe": {"9": 10, "11": 2}, "fail_rate": 0.3}
    }
  }
```

Verify: `python -c "import json; json.load(open('config.example.json', encoding='utf-8')); print('valid')"` → `valid`.

- [ ] **Step 3: Fix the bag/capacity default mismatch in `bot/models/player_model.py`**

Find in `NEW_PLAYER_DEFAULTS`:
```python
    "bag": "Medium_Bag",
    "capacity": 10,
```
Change to:
```python
    "bag": "Medium_Bag",
    "capacity": 50,
```
(This makes a new player's starting capacity match `Medium_Bag`'s real 50-item capacity, instead of silently giving them a Small-bag-sized 10.)

- [ ] **Step 4: Write the failing tests**

Append to `tests/test_config_loader.py` (reuse the existing `_write` helper):

```python
def test_get_item_config_and_get_all_items(tmp_path, monkeypatch):
    cfg = {"item_catalog": {"items": {
        "1": {"name": "Potion", "buy": 300, "sell": 100, "type": "use", "effect": "heal", "effect_amount": 50},
        "2": {"name": "Scroll", "buy": 500, "sell": 150, "type": "use", "effect": "repair"},
    }}}
    monkeypatch.setattr(config_loader, "CONFIG_PATH", str(_write(tmp_path, cfg)))
    config_loader.reload_config()
    assert config_loader.get_item_config("1") == cfg["item_catalog"]["items"]["1"]
    assert config_loader.get_item_config("nonexistent") == {}
    assert config_loader.get_all_items() == cfg["item_catalog"]["items"]

def test_get_armor_weapon_bag_stats(tmp_path, monkeypatch):
    cfg = {"item_catalog": {
        "armor_stats": {"Steel_H": {"name": "Heavy Steel", "hp": 100, "eva": 20, "dur": 500, "vis": 9}},
        "weapon_stats": {"Iron_Weapon": {"name": "Iron", "atk": 30, "dur": 150}},
        "bag_stats": {"Medium_Bag": {"name": "Medium", "capacity": 50}},
    }}
    monkeypatch.setattr(config_loader, "CONFIG_PATH", str(_write(tmp_path, cfg)))
    config_loader.reload_config()
    assert config_loader.get_armor_stats("Steel_H")["hp"] == 100
    assert config_loader.get_armor_stats("nonexistent") == {}
    assert config_loader.get_weapon_stats("Iron_Weapon")["atk"] == 30
    assert config_loader.get_bag_stats("Medium_Bag")["capacity"] == 50

def test_get_crafting_recipe(tmp_path, monkeypatch):
    cfg = {"item_catalog": {"crafting_recipes": {"1": {"recipe": {"9": 2, "12": 1}, "fail_rate": 0.1}}}}
    monkeypatch.setattr(config_loader, "CONFIG_PATH", str(_write(tmp_path, cfg)))
    config_loader.reload_config()
    assert config_loader.get_crafting_recipe("1") == {"recipe": {"9": 2, "12": 1}, "fail_rate": 0.1}
    assert config_loader.get_crafting_recipe("nonexistent") == {}
```

- [ ] **Step 5: Run tests to verify they fail**

Run: `python -m pytest tests/test_config_loader.py -k "item_config or armor_weapon_bag or crafting_recipe" -v`
Expected: FAIL (functions not defined)

- [ ] **Step 6: Implement the 6 functions**

Add to `bot/config_loader.py`, near the other getters:

```python
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
```

- [ ] **Step 7: Run tests to verify they pass**

Run: `python -m pytest tests/test_config_loader.py -v`
Expected: PASS (all tests in the file)

Run: `python -m pytest -v` (whole suite)
Expected: PASS (previous count + 3 new)

- [ ] **Step 8: Commit**

```bash
git add bot/config_loader.py config.example.json bot/models/player_model.py tests/test_config_loader.py
git commit -m "feat: add item catalog config getters + schema; fix heal-amount and bag-capacity default bugs"
```

---

### Task 2: profile_embed.py — delete the 5 dicts, read via config_loader

**Files:**
- Modify: `bot/views/profile_embed.py`

**Interfaces:**
- Consumes: `config_loader.get_armor_stats`, `get_weapon_stats` (from Task 1)

- [ ] **Step 1: Read the current file in full** to get the exact current content of `create_profile_embed` (it reads `ARMOR_STATS`/`WEAPON_STATS` at the top of the function via `armor_info = ARMOR_STATS.get(armor_key, ARMOR_STATS["None"])` and `weapon_info = WEAPON_STATS.get(weapon_key, WEAPON_STATS["Wooden_Weapon"])`).

- [ ] **Step 2: Add `from bot import config_loader` import at the top of the file.**

- [ ] **Step 3: Replace the two lookup lines inside `create_profile_embed`:**

Find:
```python
    armor_info = ARMOR_STATS.get(armor_key, ARMOR_STATS["None"])
    weapon_info = WEAPON_STATS.get(weapon_key, WEAPON_STATS["Wooden_Weapon"])
```
Replace with:
```python
    armor_info = config_loader.get_armor_stats(armor_key) or config_loader.get_armor_stats("None")
    weapon_info = config_loader.get_weapon_stats(weapon_key) or config_loader.get_weapon_stats("Wooden_Weapon")
```
(`get_armor_stats`/`get_weapon_stats` return `{}` — falsy — when the key isn't found, so `or` correctly falls back to the default key, matching the original `.get(key, default_dict)` semantics.)

- [ ] **Step 4: Delete the 5 module-level dicts** — `ARMOR_STATS`, `WEAPON_STATS`, `BAG_STATS`, `ITEM_CONFIG`, `CRAFTING_RECIPES` (including their comment headers). Leave `GAME_RACES`, `MONSTER_RACES`, `GAME_CLASSES`, `CLASS_SKILLS`, and the `create_profile_embed` function itself untouched otherwise.

- [ ] **Step 5: Verify**

Run: `grep -n "^ARMOR_STATS\|^WEAPON_STATS\|^BAG_STATS\|^ITEM_CONFIG\|^CRAFTING_RECIPES" bot/views/profile_embed.py`
Expected: no matches (all 5 module-level dict definitions gone)

Run: `python -c "import bot.views.profile_embed; print('OK')"`
Expected: `OK` (this will only succeed once Tasks 3-6 also stop importing the deleted names — if this task is done standalone before those, expect import errors in OTHER files, not this one; this file itself must still import cleanly on its own)

Run: `python -m compileall -q bot/views/profile_embed.py`
Expected: no output

- [ ] **Step 6: Commit**

```bash
git add bot/views/profile_embed.py
git commit -m "refactor: profile_embed reads armor/weapon stats from config_loader; delete the 5 dead module dicts"
```

(Note: this commit will temporarily break `bot.views.game_views`, `bot.cogs.player_commands`, `bot.cogs.admin_commands`, `bot.cogs.pvp_duel` — all of which still import the now-deleted names. That's expected and fixed by Tasks 3-6, which MUST land before running the full test suite / importing the whole `bot` package again.)

---

### Task 3: player_commands.py — effect-based `use_item` dispatch + other reads via config_loader

**Files:**
- Modify: `bot/cogs/player_commands.py`

**Interfaces:**
- Consumes: `config_loader.get_item_config`, `get_all_items`, `get_armor_stats`, `get_weapon_stats`, `get_bag_stats`, `get_crafting_recipe` (from Task 1)

- [ ] **Step 1: Read the current file in full** to find the exact current import line (`from bot.views.profile_embed import ...` — confirm which of the 5 names it imports) and the exact current bodies of `use_item`, `drop_item`, `give_item_to_player`, and the `craft`/`recipes` commands (search for `ITEM_CONFIG`/`ARMOR_STATS`/`WEAPON_STATS`/`BAG_STATS`/`CRAFTING_RECIPES` throughout the file to find every reference).

- [ ] **Step 2: Replace the import.** Remove `from bot.views.profile_embed import ITEM_CONFIG` (and any other profile_embed dict imports in this file) and add `from bot import config_loader`.

- [ ] **Step 3: In `use_item`, add local shadow assignments at the very top of the function body** (right after `player = player_model.get_player(user_id)` and its `if not player` guard):
```python
        ITEM_CONFIG = config_loader.get_all_items()
        ARMOR_STATS = {}  # filled lazily below only where needed
        WEAPON_STATS = {}
```
Actually, simplify: since `use_item` only looks up ONE armor/weapon key at a time (the player's currently-equipped gear), don't shadow whole stat dicts — replace those specific lookups directly:

Find:
```python
            armor_info_stats = ARMOR_STATS.get(armor_key, ARMOR_STATS.get("None", {}))
```
Replace with:
```python
            armor_info_stats = config_loader.get_armor_stats(armor_key) or config_loader.get_armor_stats("None")
```

Find (repair-scroll branch):
```python
            armor_info_stats = ARMOR_STATS.get(armor_key, {})
            ...
            weapon_info_stats = WEAPON_STATS.get(weapon_key, {})
```
Replace with:
```python
            armor_info_stats = config_loader.get_armor_stats(armor_key)
            ...
            weapon_info_stats = config_loader.get_weapon_stats(weapon_key)
```
(keep everything else in that branch, including the surrounding `max_armor_dur = armor_info_stats.get("dur", 100)` etc., exactly as-is — only the two source lines change)

Find (armor-equip branch):
```python
            armor_stats = ARMOR_STATS.get(equip_key, {})
```
Replace with:
```python
            armor_stats = config_loader.get_armor_stats(equip_key)
```

Find (weapon-equip branch):
```python
            weapon_stats = WEAPON_STATS.get(equip_key, {})
```
Replace with:
```python
            weapon_stats = config_loader.get_weapon_stats(equip_key)
```

Find (bag-equip branch):
```python
            bag_status = BAG_STATS.get(equip_key, {})
```
Replace with:
```python
            bag_status = config_loader.get_bag_stats(equip_key)
```

Find, near the top of `use_item`, right after `item_type = item_info.get("type", "unknown")`:
```python
        item_info = ITEM_CONFIG[item_id]
        item_name = item_info["name"]
        item_type = item_info.get("type", "unknown")
```
Replace `ITEM_CONFIG[item_id]` with `config_loader.get_item_config(item_id)`:
```python
        item_info = config_loader.get_item_config(item_id)
        item_name = item_info["name"]
        item_type = item_info.get("type", "unknown")
```
(the `if item_id not in ITEM_CONFIG:` guard just above this, which currently sends "❌ ไม่มีข้อมูลไอเทมนี้ในระบบเซิร์ฟเวอร์!" if missing, must become `if not config_loader.get_item_config(item_id):` — same guard, config-driven)

- [ ] **Step 4: Replace the `type == "use"` literal-ID branches with `effect`-based dispatch.**

Find the whole heal-potion branch:
```python
        # 🧪 กรณี: ใช้ยาฮีล
        if item_id == "1":
            heal_amount = 50 
```
Replace the condition and the hardcoded amount:
```python
        # 🧪 กรณี: ใช้ยาฮีล (ตั้งค่าได้ผ่าน effect: "heal" + effect_amount)
        if item_info.get("effect") == "heal":
            heal_amount = item_info.get("effect_amount", 50)
```
Leave the rest of that branch's body (the HP calculation, the `player_model.update_player_field` call, the message) completely unchanged.

Find the repair-scroll branch's condition:
```python
        # 🛠️ กรณี: ใช้ใบซ่อมแซม
        elif item_id == "2":
```
Replace with:
```python
        # 🛠️ กรณี: ใช้ใบซ่อมแซม (ตั้งค่าได้ผ่าน effect: "repair")
        elif item_info.get("effect") == "repair":
```
Leave the rest of that branch unchanged.

- [ ] **Step 5: Replace the `type == "drop"` branch's literal-ID special case and `drop_map` with `effect`-based dispatch.**

Find:
```python
        elif item_type == "drop":
            # 1. เช็กเคสพิเศษ: ใบชุบชีวิต (28) ต้องเช็กว่าตายไหม
            if item_id == "28":
```
Replace the condition:
```python
        elif item_type == "drop":
            # 1. เช็กเคสพิเศษ: ไอเทมชุบชีวิต ต้องเช็กว่าตายไหม (ตั้งค่าได้ผ่าน effect: "revive")
            if item_info.get("effect") == "revive":
```
Leave that branch's body unchanged (the death-state check, the HP/state restore, the message).

Find:
```python
            # 2. เคสไอเทม Drop อื่นๆ (ต้องเป็น idle เท่านั้น)
            else:
                if player.get("current_state") != "idle":
                    return await ctx.send("❌ คุณไม่สามารถใช้ไอเทมนี้ได้ในขณะที่กำลังทำกิจกรรมอื่นอยู่ (ต้องอยู่ในสถานะว่างก่อนกดปุ่ม 🧭 เริ่มออกเดินทาง)!")

                drop_map = {
                    "22": "warp_village",
                    "23": "warp_dungeon",
                    "24": "mini_summon",
                    "25": "main_summon",
                    "26": "unbeatable_summon",
                    "27": "scan_box"
                }
                
                new_state = drop_map.get(item_id)
                if new_state:
```
Replace with:
```python
            # 2. เคสไอเทมตั้งค่า last_event อื่นๆ (ต้องเป็น idle เท่านั้น) — ตั้งค่าได้ผ่าน effect: "set_state" + effect_value
            elif item_info.get("effect") == "set_state":
                if player.get("current_state") != "idle":
                    return await ctx.send("❌ คุณไม่สามารถใช้ไอเทมนี้ได้ในขณะที่กำลังทำกิจกรรมอื่นอยู่ (ต้องอยู่ในสถานะว่างก่อนกดปุ่ม 🧭 เริ่มออกเดินทาง)!")

                new_state = item_info.get("effect_value")
                if new_state:
```
(Changed the plain `else:` to `elif item_info.get("effect") == "set_state":` so an item with `type: "drop"` but no recognized `effect` correctly falls through to the final catch-all `else: return await ctx.send(f"❌ ไอเทม {item_name} ยังไม่สามารถกดใช้งานได้ในตอนนี้")` at the bottom of the whole if/elif chain, instead of silently doing nothing.)

Leave the innermost `if new_state: ... else: await ctx.send("❌ ไอเทมนี้ยังไม่ถูกตั้งค่าการใช้งาน!")` unchanged.

- [ ] **Step 6: Find and fix the `craft`/`recipes` commands.** Read their current bodies (search for `CRAFTING_RECIPES` in the file) and replace every `CRAFTING_RECIPES[...]`/`CRAFTING_RECIPES.get(...)` with the equivalent `config_loader.get_crafting_recipe(...)` call, and every bare `ITEM_CONFIG[...]`/`ITEM_CONFIG.get(...)`/`ITEM_CONFIG.items()` reference elsewhere in the file (in `drop_item`, `give_item_to_player`, and anywhere else it appears) with `config_loader.get_item_config(...)` (for single lookups) or `config_loader.get_all_items()` (for anything that currently does `ITEM_CONFIG.items()`/`.keys()`/full-dict membership checks like `item_id in ITEM_CONFIG`, which becomes `item_id in config_loader.get_all_items()`).

- [ ] **Step 7: Verify**

Run: `grep -n "ITEM_CONFIG\[\|ITEM_CONFIG\.\|ARMOR_STATS\[\|ARMOR_STATS\.\|WEAPON_STATS\[\|WEAPON_STATS\.\|BAG_STATS\[\|BAG_STATS\.\|CRAFTING_RECIPES\[\|CRAFTING_RECIPES\." bot/cogs/player_commands.py`
Expected: no matches (every bare-dict reference converted)

Run: `grep -n "from bot.views.profile_embed import" bot/cogs/player_commands.py`
Expected: either no match, or a match that no longer lists `ITEM_CONFIG`/`ARMOR_STATS`/`WEAPON_STATS`/`BAG_STATS`/`CRAFTING_RECIPES` (it's fine if it still imports unrelated names like `create_profile_embed` if this file uses that too — check first).

Run: `python -c "import bot.cogs.player_commands; print('OK')"`
Expected: `OK`

- [ ] **Step 8: Commit**

```bash
git add bot/cogs/player_commands.py
git commit -m "refactor: use_item dispatches use/drop effects via config-driven effect field instead of literal item IDs"
```

---

### Task 4: admin_commands.py — switch to config_loader

**Files:**
- Modify: `bot/cogs/admin_commands.py`

**Interfaces:**
- Consumes: `config_loader.get_item_config`, `get_armor_stats` (from Task 1)

- [ ] **Step 1: Read the current file in full** to find the exact import line and every reference to `ITEM_CONFIG`/`ARMOR_STATS`/`WEAPON_STATS` (the brief's earlier repo-wide grep found `ARMOR_STATS.get(armor_key, {}).get("hp", 0)` appearing twice, and `ITEM_CONFIG[item_id]`/`item_id not in ITEM_CONFIG` appearing in what look like 4 similar admin commands — likely `!heal`/`!rv` and `!spawn`/`!give`/`!remove`-style commands; confirm the exact command names and surrounding code by reading the file, don't guess from line numbers alone since they'll shift as you edit).

- [ ] **Step 2: Replace the import.** Remove `ARMOR_STATS`, `WEAPON_STATS`, `ITEM_CONFIG` from the `from bot.views.profile_embed import ...` line (keep `GAME_CLASSES` if the file still uses it — check first) and add `from bot import config_loader`.

- [ ] **Step 3: Replace every bare-dict reference:**
- `ARMOR_STATS.get(armor_key, {}).get("hp", 0)` → `config_loader.get_armor_stats(armor_key).get("hp", 0)` (both occurrences)
- `item_id not in ITEM_CONFIG` → `not config_loader.get_item_config(item_id)`
- `ITEM_CONFIG[item_id]["name"]` → `config_loader.get_item_config(item_id)["name"]`

- [ ] **Step 4: Verify**

Run: `grep -n "ITEM_CONFIG\[\|ITEM_CONFIG\.\|ARMOR_STATS\[\|ARMOR_STATS\.\|WEAPON_STATS\[\|WEAPON_STATS\." bot/cogs/admin_commands.py`
Expected: no matches

Run: `python -c "import bot.cogs.admin_commands; print('OK')"`
Expected: `OK`

- [ ] **Step 5: Commit**

```bash
git add bot/cogs/admin_commands.py
git commit -m "refactor: admin_commands reads item/armor config via config_loader"
```

---

### Task 5: pvp_duel.py — switch to config_loader

**Files:**
- Modify: `bot/cogs/pvp_duel.py`

**Interfaces:**
- Consumes: `config_loader.get_armor_stats`, `get_weapon_stats` (from Task 1)

- [ ] **Step 1: Read the current file in full.** Find the exact import line `from bot.views.profile_embed import ARMOR_STATS ,WEAPON_STATS` and its two usages:
```python
            armor = ARMOR_STATS.get(armor_key, ARMOR_STATS["None"])
            weapon = WEAPON_STATS.get(weapon_key, {"name": "✊ มือเปล่า", "atk": 5})
```

- [ ] **Step 2: Replace the import** with `from bot import config_loader`.

- [ ] **Step 3: Replace the two usages:**
```python
            armor = config_loader.get_armor_stats(armor_key) or config_loader.get_armor_stats("None")
            weapon = config_loader.get_weapon_stats(weapon_key) or {"name": "✊ มือเปล่า", "atk": 5}
```

- [ ] **Step 4: Verify**

Run: `grep -n "ARMOR_STATS\|WEAPON_STATS" bot/cogs/pvp_duel.py`
Expected: no matches

Run: `python -c "import bot.cogs.pvp_duel; print('OK')"`
Expected: `OK`

- [ ] **Step 5: Commit**

```bash
git add bot/cogs/pvp_duel.py
git commit -m "refactor: pvp_duel reads armor/weapon stats via config_loader"
```

---

### Task 6: game_views.py — switch to config_loader (11 insertion points)

**Files:**
- Modify: `bot/views/game_views.py`

**Interfaces:**
- Consumes: `config_loader.get_all_items`, `get_armor_stats`, `get_weapon_stats` (from Task 1)

This file has the most call sites (~25 individual `ITEM_CONFIG[...]`/`ARMOR_STATS[...]`/`WEAPON_STATS[...]` expressions spread across many different View classes/methods). Rather than rewriting each expression individually, add ONE local-variable shadow line at the top of each function/method body that uses one of these names — this makes every EXISTING expression in that function's body keep working unchanged, because Python resolves the bare name to the new local variable instead of the (now-removed) module-level import.

- [ ] **Step 1: Read the current file in full first.** Confirm the current top-of-file import line (`from bot.views.profile_embed import ARMOR_STATS, GAME_CLASSES ,WEAPON_STATS,ITEM_CONFIG`) and locate each of the following 11 methods by name (use the class/method names below as search anchors — line numbers will have shifted since the skill-config plan's earlier edits to this same file):

| Class | Method | Shadow line(s) to add as the FIRST executable statement inside the method body (after any docstring, before first use of the name) |
|---|---|---|
| `MonsterEventView` | `process_turn` | `ITEM_CONFIG = config_loader.get_all_items()` — this method already has `config_loader` imported (from the skill-config plan) and already fetches `player = player_model.get_player(...)` near its top; add the shadow line right after that, alongside the existing `w_stat = WEAPON_STATS.get(...)`/`a_stat = ARMOR_STATS.get(...)` lines — replace THOSE two lines directly instead of shadowing (see Step 2 below), and only add the `ITEM_CONFIG` shadow for the later `ITEM_CONFIG.get(...)` uses further down in the same method (the item-drop-weighting section). |
| `VillageEventView` | `rest` | `ARMOR_STATS = {"None": config_loader.get_armor_stats("None")}` is NOT enough if the method looks up multiple keys — read the method first: if it only ever looks up ONE key, replace that specific `ARMOR_STATS.get(...)`/`ARMOR_STATS[...]` expression directly with `config_loader.get_armor_stats(...)` instead of shadowing the whole name (prefer a direct single-expression replacement over a shadow wherever the method only touches the dict once or twice — only use the shadow-the-whole-name approach in methods that reference the dict 3+ times, to keep the diff readable). |
| `ShopEventView` | `buy_menu` | `ITEM_CONFIG = config_loader.get_all_items()` |
| `BuySelectView` | `__init__` | `ITEM_CONFIG = config_loader.get_all_items()` |
| `BuySelectView` | `buy_callback` | `ITEM_CONFIG = config_loader.get_all_items()` |
| `SellSelectView` | `__init__` | `ITEM_CONFIG = config_loader.get_all_items()` |
| `SellSelectView` | `sell_callback` | `ITEM_CONFIG = config_loader.get_all_items()` |
| `TreasureEventView` | `open_box` | `ITEM_CONFIG = config_loader.get_all_items()` |
| `NpcEventView` | `talk` | `ITEM_CONFIG = config_loader.get_all_items()` |
| `NpcEventView` | `quest_btn` | `ITEM_CONFIG = config_loader.get_all_items()` |
| `TrapEventView` | `dodge` | this method references `ARMOR_STATS` twice for the SAME lookup pattern (`ARMOR_STATS.get(armor_key)` then a fallback to `ARMOR_STATS["None"]`) — replace both directly with `config_loader.get_armor_stats(armor_key)` / `config_loader.get_armor_stats("None")` rather than shadowing. |

Apply the rule from the table: for methods marked "shadow the whole name" (most of them, since they reference `ITEM_CONFIG` 2+ times each with different keys/iteration), add the ONE shadow line as the very first statement of the method body (right after `async def method_name(self, ...):` and past any existing docstring/comment, before the first line of real code). For `rest` and `dodge`, replace the specific 1-2 expressions directly instead (no shadow needed there since it's cheaper and clearer for a single/double lookup).

- [ ] **Step 2: In `process_turn` specifically**, replace the two WEAPON_STATS/ARMOR_STATS lines directly (do not shadow, since `config_loader` calls fit cleanly here and this method already imports `config_loader`):

Find:
```python
            w_stat = WEAPON_STATS.get(w_id, WEAPON_STATS.get("Wooden_Weapon", {"atk": 1}))
            a_stat = ARMOR_STATS.get(a_id, ARMOR_STATS.get("None", {"hp": 0}))
```
Replace with:
```python
            w_stat = config_loader.get_weapon_stats(w_id) or config_loader.get_weapon_stats("Wooden_Weapon") or {"atk": 1}
            a_stat = config_loader.get_armor_stats(a_id) or config_loader.get_armor_stats("None") or {"hp": 0}
```
Then, for the LATER `ITEM_CONFIG.get(...)` uses further down in this same method (the monster-kill item-drop weighting section — search for `ITEM_CONFIG.get(i, {}).get("buy"` and `ITEM_CONFIG.get(dropped_item_id`), add `ITEM_CONFIG = config_loader.get_all_items()` as a local variable assigned once, right before the first of those two lines (inside the same `try:` block where the drop logic lives) — this local shadow only needs to cover the remainder of the method from that point on; Python allows assigning it anywhere before first use within the function, it doesn't have to be at the very top when the earlier code in the same function doesn't reference the name at all.

- [ ] **Step 3: Remove the dead import.** Change the top-of-file line:
```python
from bot.views.profile_embed import ARMOR_STATS, GAME_CLASSES ,WEAPON_STATS,ITEM_CONFIG
```
to:
```python
from bot.views.profile_embed import GAME_CLASSES
```
(keep `GAME_CLASSES` since it's a genuinely-used constant unrelated to this task's scope — confirm this file still uses `GAME_CLASSES` somewhere before keeping the import; if it turns out unused, drop it too, but don't assume — check.)

- [ ] **Step 4: Verify**

Run: `grep -n "^from bot.views.profile_embed" bot/views/game_views.py`
Expected: shows the updated import with the 4 catalog names removed.

Run: `grep -cn "ITEM_CONFIG\|ARMOR_STATS\|WEAPON_STATS" bot/views/game_views.py`
Expected: a nonzero count is FINE (these are now local variables/config_loader calls, not the old import) — the important check is the next one:

Run: `python -c "import bot.views.game_views; print('OK')"`
Expected: `OK` — this is the real proof no name resolves to something undefined. If this fails with a `NameError`, some usage was missed; find it via `grep -n "ITEM_CONFIG\|ARMOR_STATS\|WEAPON_STATS" bot/views/game_views.py` and confirm every remaining occurrence is either a local shadow assignment, a `config_loader.get_...` call, or a local variable derived from one of those — not a bare reference to the deleted import.

Run: `python -m compileall -q bot/views/game_views.py`
Expected: no output

Run: `python -m pytest -v` (whole suite — this is the first task where the whole `bot` package should import cleanly again after Task 2's temporary breakage, ASSUMING Tasks 3-5 already landed first)
Expected: PASS (same count as Task 1's end — this task adds no new tests)

- [ ] **Step 5: Commit**

```bash
git add bot/views/game_views.py
git commit -m "refactor: game_views reads item/armor/weapon config via config_loader (11 call sites across 8 View classes)"
```

---

### Task 7: Panel — "Items" tab UI (5 sub-tables)

**Files:**
- Modify: `panel/static/index.html`
- Modify: `panel/static/app.js`

**Interfaces:**
- Consumes: `GET /api/config` / `PUT /api/config` (existing), specifically the new `item_catalog` key added in Task 1.

No automated test (pure frontend, matches this project's established pattern). Verify via headless curl checks.

- [ ] **Step 1: Read `panel/static/index.html` and `panel/static/app.js` in full first** to find the current exact tab list, section list, and the `init()` function's wiring (the most recently added tab is "Skills" from the prior plan — follow that exact same structural pattern: tab button, section, render function, save function, add-row function where needed, wiring in `init()`/`onGuildChange()`).

- [ ] **Step 2: Add the tab button** right after the existing Skills tab button:
```html
  <button class="tab-btn" data-tab="items">Items</button>
```

- [ ] **Step 3: Add the section** (after the Skills tab's section, before `<script src="app.js"></script>`):
```html
<section id="tab-items" class="tab-panel">
  <h2>Items</h2>

  <h3>Items</h3>
  <table id="itemsTable">
    <thead><tr><th>ID</th><th>ชื่อ</th><th>ราคาซื้อ</th><th>ราคาขาย</th><th>ประเภท</th><th>ซื้อได้</th><th>อุปกรณ์/เอฟเฟกต์</th><th></th></tr></thead>
    <tbody></tbody>
  </table>
  <button id="itemAddBtn" type="button">+ เพิ่มไอเทม</button>

  <h3>Armor Stats</h3>
  <table id="armorStatsTable">
    <thead><tr><th>Key</th><th>ชื่อ</th><th>HP</th><th>หลบหลีก(%)</th><th>ความทนทาน</th><th>การมองเห็น</th><th></th></tr></thead>
    <tbody></tbody>
  </table>
  <button id="armorStatAddBtn" type="button">+ เพิ่ม</button>

  <h3>Weapon Stats</h3>
  <table id="weaponStatsTable">
    <thead><tr><th>Key</th><th>ชื่อ</th><th>โจมตี</th><th>ความทนทาน</th><th></th></tr></thead>
    <tbody></tbody>
  </table>
  <button id="weaponStatAddBtn" type="button">+ เพิ่ม</button>

  <h3>Bag Stats</h3>
  <table id="bagStatsTable">
    <thead><tr><th>Key</th><th>ชื่อ</th><th>ความจุ (0=ไม่จำกัด)</th><th></th></tr></thead>
    <tbody></tbody>
  </table>
  <button id="bagStatAddBtn" type="button">+ เพิ่ม</button>

  <h3>Crafting Recipes</h3>
  <table id="recipesTable">
    <thead><tr><th>ไอเทมที่คราฟต์ (ID)</th><th>วัตถุดิบ (รูปแบบ id:จำนวน,id:จำนวน)</th><th>โอกาสล้มเหลว (0-1)</th><th></th></tr></thead>
    <tbody></tbody>
  </table>
  <button id="recipeAddBtn" type="button">+ เพิ่มสูตร</button>

  <button id="itemsSaveBtn" class="save-btn">บันทึก</button>
</section>
```

- [ ] **Step 4: Add the render/collect/save logic to `panel/static/app.js`** (append after the Skills-tab section, before `// ---------- tabs ----------`):

```js
// ---------- items tab ----------

const ITEM_TYPES = [
  { value: "use", label: "ใช้ได้ (Consumable)" },
  { value: "armor", label: "เกราะ" },
  { value: "weapon", label: "อาวุธ" },
  { value: "bag", label: "กระเป๋า" },
  { value: "junk", label: "ของเก็บ (Junk)" },
  { value: "drop", label: "ดรอปพิเศษ" },
];

const ITEM_EFFECTS = [
  { value: "", label: "-- ไม่มี --" },
  { value: "heal", label: "ฟื้น HP (heal)" },
  { value: "repair", label: "ซ่อมอุปกรณ์ (repair)" },
  { value: "revive", label: "ชุบชีวิต (revive)" },
  { value: "set_state", label: "ตั้งค่าเหตุการณ์ (set_state)" },
];

function renderItemsCatalog() {
  const cat = state.config.item_catalog || {};
  renderItemsTable(cat.items || {});
  renderKvStatsTable(cat.armor_stats || {}, "armorStatsTable", ["hp", "eva", "dur", "vis"]);
  renderKvStatsTable(cat.weapon_stats || {}, "weaponStatsTable", ["atk", "dur"]);
  renderKvStatsTable(cat.bag_stats || {}, "bagStatsTable", ["capacity"]);
  renderRecipesTable(cat.crafting_recipes || {});
}

function renderItemsTable(items) {
  const tbody = document.querySelector("#itemsTable tbody");
  tbody.innerHTML = "";
  Object.keys(items).forEach((id) => {
    const item = items[id];
    const tr = document.createElement("tr");
    tr.dataset.id = id;

    const tdId = document.createElement("td");
    tdId.textContent = id;
    tr.appendChild(tdId);

    const tdName = document.createElement("td");
    const nameInput = document.createElement("input");
    nameInput.type = "text";
    nameInput.className = "item-name";
    nameInput.value = item.name || "";
    tdName.appendChild(nameInput);
    tr.appendChild(tdName);

    const tdBuy = document.createElement("td");
    const buyInput = document.createElement("input");
    buyInput.type = "number";
    buyInput.className = "item-buy";
    buyInput.value = item.buy != null ? item.buy : 0;
    tdBuy.appendChild(buyInput);
    tr.appendChild(tdBuy);

    const tdSell = document.createElement("td");
    const sellInput = document.createElement("input");
    sellInput.type = "number";
    sellInput.className = "item-sell";
    sellInput.value = item.sell != null ? item.sell : 0;
    tdSell.appendChild(sellInput);
    tr.appendChild(tdSell);

    const tdType = document.createElement("td");
    const typeSel = document.createElement("select");
    typeSel.className = "item-type";
    for (const t of ITEM_TYPES) {
      const opt = document.createElement("option");
      opt.value = t.value;
      opt.textContent = t.label;
      typeSel.appendChild(opt);
    }
    typeSel.value = item.type || "use";
    tdType.appendChild(typeSel);
    tr.appendChild(tdType);

    const tdPurchasable = document.createElement("td");
    const purchasableCb = document.createElement("input");
    purchasableCb.type = "checkbox";
    purchasableCb.className = "item-purchasable";
    purchasableCb.checked = item.purchasable !== false;
    tdPurchasable.appendChild(purchasableCb);
    tr.appendChild(tdPurchasable);

    const tdExtra = document.createElement("td");
    const equipKeyInput = document.createElement("input");
    equipKeyInput.type = "text";
    equipKeyInput.className = "item-equip-key";
    equipKeyInput.placeholder = "equip_key (armor/weapon/bag)";
    equipKeyInput.value = item.equip_key || "";
    const effectSel = document.createElement("select");
    effectSel.className = "item-effect";
    for (const e of ITEM_EFFECTS) {
      const opt = document.createElement("option");
      opt.value = e.value;
      opt.textContent = e.label;
      effectSel.appendChild(opt);
    }
    effectSel.value = item.effect || "";
    const effectValInput = document.createElement("input");
    effectValInput.type = "text";
    effectValInput.className = "item-effect-value";
    effectValInput.placeholder = "effect_amount / effect_value";
    effectValInput.value = item.effect_amount != null ? item.effect_amount : (item.effect_value || "");
    tdExtra.appendChild(equipKeyInput);
    tdExtra.appendChild(effectSel);
    tdExtra.appendChild(effectValInput);
    tr.appendChild(tdExtra);

    const tdDel = document.createElement("td");
    const delBtn = document.createElement("button");
    delBtn.type = "button";
    delBtn.textContent = "ลบ";
    delBtn.onclick = () => {
      delete state.config.item_catalog.items[id];
      renderItemsCatalog();
    };
    tdDel.appendChild(delBtn);
    tr.appendChild(tdDel);

    tbody.appendChild(tr);
  });
}

function addNewItem() {
  if (!state.config.item_catalog) state.config.item_catalog = {};
  if (!state.config.item_catalog.items) state.config.item_catalog.items = {};
  const items = state.config.item_catalog.items;
  let n = 1;
  while (items[String(n)]) n++;
  items[String(n)] = { name: "ไอเทมใหม่", buy: 0, sell: 0, type: "use", purchasable: true };
  renderItemsCatalog();
}

function renderKvStatsTable(statsObj, tableId, fieldNames) {
  const tbody = document.querySelector(`#${tableId} tbody`);
  tbody.innerHTML = "";
  Object.keys(statsObj).forEach((key) => {
    const entry = statsObj[key];
    const tr = document.createElement("tr");
    tr.dataset.key = key;

    const tdKey = document.createElement("td");
    const keyInput = document.createElement("input");
    keyInput.type = "text";
    keyInput.className = "stat-key";
    keyInput.value = key;
    tdKey.appendChild(keyInput);
    tr.appendChild(tdKey);

    const tdName = document.createElement("td");
    const nameInput = document.createElement("input");
    nameInput.type = "text";
    nameInput.className = "stat-name";
    nameInput.value = entry.name || "";
    tdName.appendChild(nameInput);
    tr.appendChild(tdName);

    for (const field of fieldNames) {
      const td = document.createElement("td");
      const input = document.createElement("input");
      input.type = "number";
      input.className = "stat-field";
      input.dataset.field = field;
      input.value = entry[field] != null ? entry[field] : 0;
      td.appendChild(input);
      tr.appendChild(td);
    }

    const tdDel = document.createElement("td");
    const delBtn = document.createElement("button");
    delBtn.type = "button";
    delBtn.textContent = "ลบ";
    delBtn.onclick = () => {
      delete statsObj[key];
      renderItemsCatalog();
    };
    tdDel.appendChild(delBtn);
    tr.appendChild(tdDel);

    tbody.appendChild(tr);
  });
}

function addStatRow(catalogField, tableId, fieldNames) {
  if (!state.config.item_catalog) state.config.item_catalog = {};
  if (!state.config.item_catalog[catalogField]) state.config.item_catalog[catalogField] = {};
  const statsObj = state.config.item_catalog[catalogField];
  let n = 1;
  while (statsObj["new_" + n]) n++;
  const entry = { name: "ใหม่" };
  for (const f of fieldNames) entry[f] = 0;
  statsObj["new_" + n] = entry;
  renderItemsCatalog();
}

function renderRecipesTable(recipes) {
  const tbody = document.querySelector("#recipesTable tbody");
  tbody.innerHTML = "";
  Object.keys(recipes).forEach((itemId) => {
    const r = recipes[itemId];
    const tr = document.createElement("tr");
    tr.dataset.itemId = itemId;

    const tdItem = document.createElement("td");
    const itemIdInput = document.createElement("input");
    itemIdInput.type = "text";
    itemIdInput.className = "recipe-item-id";
    itemIdInput.value = itemId;
    tdItem.appendChild(itemIdInput);
    tr.appendChild(tdItem);

    const tdIngredients = document.createElement("td");
    const ingredientsInput = document.createElement("input");
    ingredientsInput.type = "text";
    ingredientsInput.className = "recipe-ingredients";
    ingredientsInput.value = Object.entries(r.recipe || {}).map(([id, qty]) => `${id}:${qty}`).join(",");
    tdIngredients.appendChild(ingredientsInput);
    tr.appendChild(tdIngredients);

    const tdFail = document.createElement("td");
    const failInput = document.createElement("input");
    failInput.type = "number";
    failInput.step = "any";
    failInput.className = "recipe-fail-rate";
    failInput.value = r.fail_rate != null ? r.fail_rate : 0;
    tdFail.appendChild(failInput);
    tr.appendChild(tdFail);

    const tdDel = document.createElement("td");
    const delBtn = document.createElement("button");
    delBtn.type = "button";
    delBtn.textContent = "ลบ";
    delBtn.onclick = () => {
      delete state.config.item_catalog.crafting_recipes[itemId];
      renderItemsCatalog();
    };
    tdDel.appendChild(delBtn);
    tr.appendChild(tdDel);

    tbody.appendChild(tr);
  });
}

function addRecipeRow() {
  if (!state.config.item_catalog) state.config.item_catalog = {};
  if (!state.config.item_catalog.crafting_recipes) state.config.item_catalog.crafting_recipes = {};
  const recipes = state.config.item_catalog.crafting_recipes;
  let n = 1;
  while (recipes["new_" + n]) n++;
  recipes["new_" + n] = { recipe: {}, fail_rate: 0.1 };
  renderItemsCatalog();
}

function parseIngredients(text) {
  const result = {};
  text.split(",").map((s) => s.trim()).filter(Boolean).forEach((pair) => {
    const [id, qty] = pair.split(":").map((s) => s.trim());
    if (id) result[id] = parseInt(qty, 10) || 1;
  });
  return result;
}

async function itemsSave() {
  const items = {};
  document.querySelectorAll("#itemsTable tbody tr").forEach((tr) => {
    const id = tr.dataset.id;
    const type = tr.querySelector(".item-type").value;
    const effect = tr.querySelector(".item-effect").value;
    const extraVal = tr.querySelector(".item-effect-value").value;
    const entry = {
      name: tr.querySelector(".item-name").value,
      buy: parseInt(tr.querySelector(".item-buy").value, 10) || 0,
      sell: parseInt(tr.querySelector(".item-sell").value, 10) || 0,
      type,
      purchasable: tr.querySelector(".item-purchasable").checked,
    };
    const equipKey = tr.querySelector(".item-equip-key").value.trim();
    if (["armor", "weapon", "bag"].includes(type) && equipKey) entry.equip_key = equipKey;
    if (effect) {
      entry.effect = effect;
      if (effect === "heal") entry.effect_amount = parseInt(extraVal, 10) || 0;
      if (effect === "set_state") entry.effect_value = extraVal;
    }
    items[id] = entry;
  });

  function collectStats(tableId, fieldNames) {
    const out = {};
    document.querySelectorAll(`#${tableId} tbody tr`).forEach((tr) => {
      const key = tr.querySelector(".stat-key").value.trim();
      if (!key) return;
      const entry = { name: tr.querySelector(".stat-name").value };
      tr.querySelectorAll(".stat-field").forEach((input) => {
        const parsed = parseFloat(input.value);
        entry[input.dataset.field] = isNaN(parsed) ? 0 : parsed;
      });
      out[key] = entry;
    });
    return out;
  }

  const armor_stats = collectStats("armorStatsTable", ["hp", "eva", "dur", "vis"]);
  const weapon_stats = collectStats("weaponStatsTable", ["atk", "dur"]);
  const bag_stats = collectStats("bagStatsTable", ["capacity"]);

  const crafting_recipes = {};
  document.querySelectorAll("#recipesTable tbody tr").forEach((tr) => {
    const itemId = tr.querySelector(".recipe-item-id").value.trim();
    if (!itemId) return;
    const fail = parseFloat(tr.querySelector(".recipe-fail-rate").value);
    crafting_recipes[itemId] = {
      recipe: parseIngredients(tr.querySelector(".recipe-ingredients").value),
      fail_rate: isNaN(fail) ? 0 : fail,
    };
  });

  state.config.item_catalog = { items, armor_stats, weapon_stats, bag_stats, crafting_recipes };
  await saveConfig();
}
```

- [ ] **Step 5: Wire up event listeners** — in `init()`, find the Skills-tab wiring (from the prior plan, e.g. `document.getElementById("shopAddBtn").addEventListener(...)` / `skillsSaveBtn` lines) and add right after:
```js
  document.getElementById("itemAddBtn").addEventListener("click", addNewItem);
  document.getElementById("armorStatAddBtn").addEventListener("click", () => addStatRow("armor_stats", "armorStatsTable", ["hp", "eva", "dur", "vis"]));
  document.getElementById("weaponStatAddBtn").addEventListener("click", () => addStatRow("weapon_stats", "weaponStatsTable", ["atk", "dur"]));
  document.getElementById("bagStatAddBtn").addEventListener("click", () => addStatRow("bag_stats", "bagStatsTable", ["capacity"]));
  document.getElementById("recipeAddBtn").addEventListener("click", addRecipeRow);
  document.getElementById("itemsSaveBtn").addEventListener("click", itemsSave);
```

- [ ] **Step 6: Add `renderItemsCatalog();` to all 3 existing render-call sites** (the two inside `onGuildChange()` and the one inside `init()`, immediately after each site's `renderSkillsTab();` line, matching each site's exact indentation — same approach used for adding Skills after Shop in the prior plan).

Note: unlike Channels/Auto-trade/Shop/Skills, the Items tab does NOT need `state.roles`/`state.channels` (it's pure catalog data, no Discord role/channel pickers) — so it's safe to render it even before a guild is selected; still wire it at the same 3 call sites for consistency with every other tab.

- [ ] **Step 7: Verify**

Run: `python -c "import panel.server; print('OK')"`
Expected: `OK`

Run:
```bash
python -m uvicorn panel.server:app --port 8770 &
sleep 1
curl -s http://localhost:8770/ | grep -c "tab-items"
curl -s http://localhost:8770/app.js | grep -c "renderItemsCatalog"
```
Both counts should be `> 0`. Kill the background uvicorn process afterward.

Run: `python -m pytest -v`
Expected: PASS (same count as Task 1's end — pure frontend task, no Python tests added)

- [ ] **Step 8: Commit**

```bash
git add panel/static/index.html panel/static/app.js
git commit -m "feat: add Items tab to panel UI (items/armor/weapon/bag stats + crafting recipes)"
```

---

## Self-Review Notes

- **Spec coverage:** item catalog config-ified (Task 1+2+3+4+5+6) ✅; extensible `effect` field replacing literal-ID dispatch (Task 1 schema + Task 3 `use_item`) ✅; heal-amount bug fix (Task 1+3) ✅; bag/capacity default bug fix (Task 1) ✅; Panel UI (Task 7) ✅.
- **Deferred, confirmed not in any task:** loot-table/drop-chance restructuring (hard, next phase), monster/EXP/gold rates (next phase).
- **Placeholder scan:** Task 6's table-driven instructions ("shadow the whole name" vs "replace directly") describe a complete, unambiguous algorithm per method rather than exhaustive line-level diffs for all ~25 call sites — this is a deliberate scoping choice given the volume of near-identical mechanical edits (same pattern successfully used for Task 4 of the prior skill-config plan, which used a mapping table rather than per-line diffs for ~15 decorator call-sites with zero review findings). Every OTHER task in this plan has full literal before/after code.
- **Type consistency:** `get_item_config`/`get_all_items`/`get_armor_stats`/`get_weapon_stats`/`get_bag_stats`/`get_crafting_recipe` names and return shapes are identical everywhere they're referenced across Tasks 2-7.
- **Ordering constraint:** Task 2 (profile_embed.py) MUST land before Tasks 3-6 run their own verification's full-suite pytest step, since deleting the dict definitions temporarily breaks every other file's import until each of Tasks 3-6 also lands — execute in the numbered order given (1→2→3→4→5→6→7), not in parallel, and don't treat Task 2's "expected breakage" note as a signal to skip its own file-local verification.
