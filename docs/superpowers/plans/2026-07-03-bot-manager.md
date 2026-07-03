# MMORPG Bot Manager Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn the hardcoded single-server Discord MMORPG bot into a distributable desktop program where a server owner configures channels, role permissions, and auto-trade roles through a local web panel, sets the token, and runs the bot — all from one double-clickable app.

**Architecture:** Two processes sharing one `config.json`. A FastAPI "panel" serves a local web UI, edits `config.json`, fetches the guild's real channels/roles from Discord REST to populate dropdowns, and controls the bot as a subprocess (start/stop/restart + live log). The bot (copied from the original project and refactored) reads all previously-hardcoded values from `config.json` via a central `config_loader`. Changes apply on bot restart.

**Tech Stack:** Python 3.12, discord.py 2.x (bot), FastAPI + uvicorn (panel), httpx (Discord REST), vanilla HTML/CSS/JS (UI), PyInstaller (packaging), pytest (tests).

## Global Constraints

- Original project `discord-mmorpg-bot` MUST NOT be modified. This is a separate new project at `mmorpg-bot-manager/`.
- All references to Discord objects are stored and compared by **ID** (channel_id, role_id), never by name.
- `config.json` is the single source of truth: panel writes it, bot reads it at startup only.
- Bot must run with `PYTHONIOENCODING=utf-8` (Thai/emoji in logs).
- Panel binds localhost only, default port `8770`. No auth in v1.
- v1 excludes: skill buff/nerf editor, multi-guild, live-reload, panel login.
- Keep files focused and small; one responsibility each.

---

## File Structure

```
mmorpg-bot-manager/
├── config.example.json         # default config shipped with app
├── config.json                 # runtime config (gitignored; created from example)
├── launcher.py                 # entry: start panel + open browser; --run-bot spawns bot
├── requirements.txt
├── .gitignore
├── build.spec                  # PyInstaller
├── bot/
│   ├── __init__.py
│   ├── config_loader.py        # NEW — reads/caches config.json
│   ├── main.py                 # refactored — token from config
│   ├── utils.py                # refactored — config-driven decorators
│   ├── models/player_model.py  # copied as-is
│   ├── controller/             # copied as-is
│   ├── views/game_views.py     # copied as-is
│   └── cogs/*.py               # copied; decorator args + role_shop refactored
├── panel/
│   ├── __init__.py
│   ├── server.py               # FastAPI app + mounts
│   ├── config_store.py         # load/save/validate config.json
│   ├── discord_fetch.py        # httpx Discord REST calls
│   ├── process_manager.py      # bot subprocess lifecycle + log buffer
│   ├── routes_config.py
│   ├── routes_discord.py
│   ├── routes_bot.py
│   └── static/{index.html,app.js,style.css}
└── tests/
    ├── test_config_loader.py
    ├── test_decorators.py
    ├── test_config_store.py
    ├── test_discord_fetch.py
    └── test_process_manager.py
```

---

## Phase 0 — Scaffold

### Task 1: Project scaffold + copy bot source

**Files:**
- Create: `mmorpg-bot-manager/requirements.txt`, `.gitignore`, `bot/__init__.py`, `panel/__init__.py`, `tests/__init__.py`
- Copy: bot source from original (cleaned set — exclude dead files)

**Interfaces:**
- Produces: `bot/` package importable; `config.example.json` present.

- [ ] **Step 1: Create requirements.txt**

```
discord.py>=2.3
python-dotenv>=1.0
fastapi>=0.110
uvicorn>=0.29
httpx>=0.27
pytest>=8.0
```

- [ ] **Step 2: Create .gitignore**

```
__pycache__/
*.pyc
config.json
game_data.db
build/
dist/
*.spec.bak
```

- [ ] **Step 3: Copy bot files from the original project**

Copy from `../discord-mmorpg-bot/` into `bot/`, keeping only the live files (skip already-dead `database.py`, `controller/db_managai.py`, `views/game_views_V0.*.py`):

```bash
# run from mmorpg-bot-manager/
mkdir -p bot/models bot/controller bot/cogs bot/views
cp ../discord-mmorpg-bot/main.py bot/main.py
cp ../discord-mmorpg-bot/utils.py bot/utils.py
cp ../discord-mmorpg-bot/models/player_model.py bot/models/
cp ../discord-mmorpg-bot/controller/__init__.py bot/controller/
cp ../discord-mmorpg-bot/controller/bot_brain.py bot/controller/
cp ../discord-mmorpg-bot/controller/trainer.py bot/controller/
cp ../discord-mmorpg-bot/controller/db_manager.py bot/controller/
cp ../discord-mmorpg-bot/views/game_views.py bot/views/
cp ../discord-mmorpg-bot/views/profile_embed.py bot/views/
cp ../discord-mmorpg-bot/cogs/*.py bot/cogs/
touch bot/__init__.py panel/__init__.py tests/__init__.py
```

- [ ] **Step 4: Verify bot package compiles**

Run: `python -m compileall -q bot`
Expected: no output (all files compile)

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "chore: scaffold project and copy bot source"
```

---

## Phase 1 — Make the bot config-driven

### Task 2: config_loader + config.example.json

**Files:**
- Create: `bot/config_loader.py`, `config.example.json`, `tests/test_config_loader.py`

**Interfaces:**
- Produces:
  - `get_config() -> dict` — loads+caches config.json (falls back to config.example.json if missing/corrupt)
  - `get_channel_id(key: str) -> int | None`
  - `get_role_ids(group: str) -> list[int]`
  - `get_trade_roles(faction: str) -> list[dict]`
  - `get_gacha_price() -> int`, `get_gacha_pool_price() -> int`
  - `get_token() -> str`, `get_guild_id() -> int | None`
  - `reload_config() -> None` — clears cache (used by tests)

- [ ] **Step 1: Write config.example.json**

Use the schema from the spec §6. Seed `auto_trade_roles.dark`/`light` with the 20 roles from the original `role_shop.py` (copy the exact label/value/price/role_id/emoji lists). Set `bot_token: ""`, `guild_id: null`, `panel_port: 8770`, all `channel_id: null`, all `role_ids: []`.

- [ ] **Step 2: Write the failing tests**

```python
# tests/test_config_loader.py
import json, importlib
from bot import config_loader

def _write(tmp_path, data):
    p = tmp_path / "config.json"
    p.write_text(json.dumps(data), encoding="utf-8")
    return p

def test_get_channel_id_returns_int(tmp_path, monkeypatch):
    cfg = {"channels": {"bank": {"label": "x", "channel_id": 123}}}
    monkeypatch.setattr(config_loader, "CONFIG_PATH", str(_write(tmp_path, cfg)))
    config_loader.reload_config()
    assert config_loader.get_channel_id("bank") == 123

def test_missing_channel_key_returns_none(tmp_path, monkeypatch):
    monkeypatch.setattr(config_loader, "CONFIG_PATH", str(_write(tmp_path, {"channels": {}})))
    config_loader.reload_config()
    assert config_loader.get_channel_id("nope") is None

def test_get_role_ids(tmp_path, monkeypatch):
    cfg = {"permission_groups": {"admin": {"role_ids": [1, 2]}}}
    monkeypatch.setattr(config_loader, "CONFIG_PATH", str(_write(tmp_path, cfg)))
    config_loader.reload_config()
    assert config_loader.get_role_ids("admin") == [1, 2]

def test_corrupt_config_falls_back(tmp_path, monkeypatch):
    p = tmp_path / "config.json"
    p.write_text("{ broken", encoding="utf-8")
    monkeypatch.setattr(config_loader, "CONFIG_PATH", str(p))
    config_loader.reload_config()
    assert config_loader.get_channel_id("bank") is None  # falls back, no crash
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `pytest tests/test_config_loader.py -v`
Expected: FAIL (module attributes not defined)

- [ ] **Step 4: Implement config_loader.py**

```python
# bot/config_loader.py
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
    return ch.get("channel_id") if ch else None

def get_role_ids(group):
    g = get_config().get("permission_groups", {}).get(group)
    return list(g.get("role_ids", [])) if g else []

def get_trade_roles(faction):
    return list(get_config().get("auto_trade_roles", {}).get(faction, []))

def get_gacha_price():
    return int(get_config().get("auto_trade_roles", {}).get("gacha_price", 10000000))

def get_gacha_pool_price():
    return int(get_config().get("auto_trade_roles", {}).get("gacha_pool_price", 20000000))

def get_token():
    return get_config().get("bot_token", "")

def get_guild_id():
    return get_config().get("guild_id")
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/test_config_loader.py -v`
Expected: PASS (4 passed)

- [ ] **Step 6: Commit**

```bash
git add bot/config_loader.py config.example.json tests/test_config_loader.py
git commit -m "feat: config_loader reads config.json with example fallback"
```

---

### Task 3: Config-driven decorators in utils.py

**Files:**
- Modify: `bot/utils.py`
- Test: `tests/test_decorators.py`

**Interfaces:**
- Consumes: `config_loader.get_channel_id`, `get_role_ids`
- Produces:
  - `allowed_channel(feature_key: str)` — check passes if `ctx.channel.id == config_loader.get_channel_id(feature_key)`; if key unconfigured (None), allow (don't lock a server out of a feature it hasn't mapped yet)
  - `has_permission(group: str)` — passes if author is guild owner OR has a role whose id is in `get_role_ids(group)`
  - Keep existing `not_arrested()` unchanged.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_decorators.py
import types, asyncio, pytest
from bot import utils, config_loader

class FakeRole:
    def __init__(self, rid): self.id = rid

def make_ctx(channel_id, author_id, role_ids, owner_id):
    author = types.SimpleNamespace(id=author_id, roles=[FakeRole(r) for r in role_ids])
    guild = types.SimpleNamespace(owner_id=owner_id)
    sent = {}
    async def send(msg): sent["msg"] = msg
    return types.SimpleNamespace(channel=types.SimpleNamespace(id=channel_id),
                                 author=author, guild=guild, send=send), sent

def run_predicate(deco, ctx):
    # decorator returns commands.check(predicate); pull predicate out
    check = deco
    pred = check.predicate if hasattr(check, "predicate") else check.__closure__[0].cell_contents
    return asyncio.run(pred(ctx))

def test_allowed_channel_pass(monkeypatch):
    monkeypatch.setattr(config_loader, "get_channel_id", lambda k: 999)
    ctx, _ = make_ctx(channel_id=999, author_id=1, role_ids=[], owner_id=2)
    assert run_predicate(utils.allowed_channel("bank"), ctx) is True

def test_allowed_channel_unconfigured_allows(monkeypatch):
    monkeypatch.setattr(config_loader, "get_channel_id", lambda k: None)
    ctx, _ = make_ctx(channel_id=5, author_id=1, role_ids=[], owner_id=2)
    assert run_predicate(utils.allowed_channel("bank"), ctx) is True

def test_has_permission_owner_passes(monkeypatch):
    monkeypatch.setattr(config_loader, "get_role_ids", lambda g: [])
    ctx, _ = make_ctx(channel_id=1, author_id=7, role_ids=[], owner_id=7)
    assert run_predicate(utils.has_permission("admin"), ctx) is True

def test_has_permission_role_match(monkeypatch):
    monkeypatch.setattr(config_loader, "get_role_ids", lambda g: [55])
    ctx, _ = make_ctx(channel_id=1, author_id=7, role_ids=[55], owner_id=2)
    assert run_predicate(utils.has_permission("admin"), ctx) is True

def test_has_permission_denied(monkeypatch):
    monkeypatch.setattr(config_loader, "get_role_ids", lambda g: [55])
    ctx, _ = make_ctx(channel_id=1, author_id=7, role_ids=[10], owner_id=2)
    assert run_predicate(utils.has_permission("admin"), ctx) is False
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_decorators.py -v`
Expected: FAIL (`allowed_channel`/`has_permission` not defined)

- [ ] **Step 3: Implement the new decorators**

Add to `bot/utils.py` (keep `not_arrested`; the old `allowed_channels`/`has_role_or_owner` may be removed after Task 4 migrates callers):

```python
from bot import config_loader

def allowed_channel(feature_key):
    async def predicate(ctx):
        target = config_loader.get_channel_id(feature_key)
        if target is None:
            return True  # feature not mapped to a channel yet → don't block
        if ctx.channel.id != target:
            try:
                msg = await ctx.send(f"❌ **ผิดห้อง!** คำสั่งนี้ใช้ได้เฉพาะห้องที่แอดมินตั้งไว้เท่านั้นครับ")
                await asyncio.sleep(5)
                await msg.delete()
                await ctx.message.delete()
            except Exception:
                pass
            return False
        return True
    return commands.check(predicate)

def has_permission(group):
    async def predicate(ctx):
        if ctx.author.id == ctx.guild.owner_id:
            return True
        allowed = set(config_loader.get_role_ids(group))
        if any(r.id in allowed for r in ctx.author.roles):
            return True
        await ctx.send("❌ คุณไม่มีสิทธิ์ใช้คำสั่งนี้ (ติดต่อแอดมินเพื่อขอสิทธิ์)")
        return False
    return commands.check(predicate)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_decorators.py -v`
Expected: PASS (5 passed)

- [ ] **Step 5: Commit**

```bash
git add bot/utils.py tests/test_decorators.py
git commit -m "feat: config-driven allowed_channel and has_permission decorators"
```

---

### Task 4: Migrate all cog decorator call-sites

**Files:**
- Modify: every `bot/cogs/*.py` using `allowed_channels(...)` or `has_role_or_owner(...)`

**Interfaces:**
- Consumes: `utils.allowed_channel`, `utils.has_permission`

Apply this exact mapping. Replace the decorator and update the import line (`from utils import ...` becomes `from bot.utils import ...`; also change `import models.player_model` → `from bot import ... ` per Task 6 note — but for THIS task only touch the decorator lines and the `utils` import symbols).

**Channel name → feature key:**

| old `allowed_channels([...])` name | new `allowed_channel("key")` |
|---|---|
| `🏦ธนาคารกลาง🏦` | `bank` |
| `⚒-แชทลานประลอง-⚒` | `arena` |
| `💸ซื้อยศออโต้💸` | `role_shop` |
| `🪪เช็คโปรไฟล์🪪` | `profile` |
| `⚔-เริ่มเกม-⚔` | `adventure` |
| `📃สัญญาเช่า📃` | `rent` |
| `🚨ห้องแจ้งความ🚨` | `police` |
| `🎲-hilo-🎲` | `casino_hilo` |
| `🎰-slots-🎰` | `casino_slots` |
| `🃏blackjack🃏` | `casino_bj` |

**Role name → permission group:**

| old `has_role_or_owner("...")` | new `has_permission("group")` |
|---|---|
| `คนบ้า` | `admin` |
| `꒰ PL ꒱ อัศวิน ⚔️` | `police` |
| `꒰ DT ꒱ นักบวช .⋆♱` | `priest` |

- [ ] **Step 1: Update the import symbols in each affected cog**

In each cog file, change `from utils import ...` to import the new names, e.g.:
`from bot.utils import not_arrested, allowed_channel, has_permission`
(drop `allowed_channels`, `has_role_or_owner`).

- [ ] **Step 2: Replace every decorator call-site per the tables above**

Files/lines to edit (from the codebase grep): `admin_commands.py`, `player_commands.py`, `game_commands.py`, `casino.py`, `blackjack.py`, `world_boss.py`, `pvp_duel.py`, `private_room.py`, `adventure_zone.py`, `role_shop.py`. Every `@allowed_channels([X])` → `@allowed_channel("key")`; every `@has_role_or_owner("Y")` → `@has_permission("group")`.

- [ ] **Step 3: Remove the now-dead old decorators from utils.py**

Delete `allowed_channels(channel_names)` and `has_role_or_owner(role_name)` from `bot/utils.py`.

- [ ] **Step 4: Verify no stragglers remain**

Run: `grep -rn "allowed_channels\|has_role_or_owner" bot/`
Expected: no matches.

- [ ] **Step 5: Verify bot package compiles**

Run: `python -m compileall -q bot`
Expected: no output.

- [ ] **Step 6: Commit**

```bash
git add bot/
git commit -m "refactor: migrate cogs to config-driven decorators"
```

---

### Task 5: Refactor role_shop.py to read config

**Files:**
- Modify: `bot/cogs/role_shop.py`

**Interfaces:**
- Consumes: `config_loader.get_trade_roles`, `get_gacha_price`, `get_gacha_pool_price`

- [ ] **Step 1: Replace the module-level DARK_ROLES/LIGHT_ROLES constants with config reads**

Delete the hardcoded `DARK_ROLES` and `LIGHT_ROLES` lists. At the top add:
`from bot import config_loader`. Replace every use of `DARK_ROLES` with `config_loader.get_trade_roles("dark")` and `LIGHT_ROLES` with `config_loader.get_trade_roles("light")`. In the Select `__init__` methods and gacha handlers, call these at construction/call time (not import time) so edited config is picked up on the next bot start.

- [ ] **Step 2: Replace hardcoded gacha prices**

In `process_role_gacha`: `GACHA_PRICE = config_loader.get_gacha_price()`, and the pool filter `r["price"] == 20000000` → `r["price"] == config_loader.get_gacha_pool_price()`.

- [ ] **Step 3: Verify compile**

Run: `python -m compileall -q bot/cogs/role_shop.py`
Expected: no output.

- [ ] **Step 4: Commit**

```bash
git add bot/cogs/role_shop.py
git commit -m "refactor: role_shop reads auto-trade roles from config"
```

---

### Task 6: Token from config + package-relative imports

**Files:**
- Modify: `bot/main.py`; every `bot/**/*.py` with absolute intra-project imports

**Interfaces:**
- Consumes: `config_loader.get_token`
- Produces: `bot/main.py` runnable as `python -m bot.main` from project root.

- [ ] **Step 1: Load token from config in main.py**

Replace the `.env`/`os.getenv("ARTHUR_TOKEN")` token source with:
```python
from bot import config_loader
TOKEN_GAME = config_loader.get_token()
```
Keep the single-bot "game" launch (current bypass behavior). If `TOKEN_GAME` is empty, print a clear message: `"⚠️ ยังไม่ได้ตั้ง token — เปิดหน้า Panel แล้วใส่ token ก่อน"` and return.

- [ ] **Step 2: Fix intra-project imports to package form**

Change `import models.player_model as player_model` → `from bot import models` won't work with existing usage; instead use `import bot.models.player_model as player_model`. Apply consistently: `from bot.utils import ...`, `from bot.views.game_views import ...`, `from bot import config_loader`, `from bot.controller import ...`. Update `controller/*.py` sys.path hacks to plain package imports.

- [ ] **Step 3: Smoke-test import**

Run: `python -c "import bot.main"`
Expected: no ImportError (may print the "no token" message only if it executes main, which it won't on import).

- [ ] **Step 4: Manual run check with a test config**

Copy `config.example.json` → `config.json`, paste a real token + guild_id, then:
Run: `PYTHONIOENCODING=utf-8 python -m bot.main`
Expected: log shows all cogs load and `🟢 SYSTEM ONLINE`. Ctrl+C to stop.

- [ ] **Step 5: Commit**

```bash
git add bot/
git commit -m "refactor: bot loads token from config, package-relative imports"
```

---

## Phase 2 — Panel backend

### Task 7: config_store + config routes

**Files:**
- Create: `panel/config_store.py`, `panel/routes_config.py`, `panel/server.py`
- Test: `tests/test_config_store.py`

**Interfaces:**
- Produces:
  - `config_store.load() -> dict`, `config_store.save(data: dict) -> None` (writes `config.json` atomically), `config_store.ensure_exists() -> None` (copy from example if missing)
  - FastAPI app `panel.server:app` with `GET /api/config`, `PUT /api/config`

- [ ] **Step 1: Write failing tests for config_store**

```python
# tests/test_config_store.py
import json
from panel import config_store

def test_save_then_load(tmp_path, monkeypatch):
    monkeypatch.setattr(config_store, "CONFIG_PATH", str(tmp_path / "config.json"))
    config_store.save({"bot_token": "abc"})
    assert config_store.load()["bot_token"] == "abc"

def test_ensure_exists_copies_example(tmp_path, monkeypatch):
    ex = tmp_path / "config.example.json"; ex.write_text('{"panel_port": 8770}', encoding="utf-8")
    monkeypatch.setattr(config_store, "CONFIG_PATH", str(tmp_path / "config.json"))
    monkeypatch.setattr(config_store, "EXAMPLE_PATH", str(ex))
    config_store.ensure_exists()
    assert config_store.load()["panel_port"] == 8770
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_config_store.py -v`
Expected: FAIL (module not found)

- [ ] **Step 3: Implement config_store.py**

```python
# panel/config_store.py
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
```

- [ ] **Step 4: Implement routes_config.py and server.py**

```python
# panel/routes_config.py
from fastapi import APIRouter
from panel import config_store

router = APIRouter()

@router.get("/api/config")
def get_config():
    return config_store.load()

@router.put("/api/config")
def put_config(data: dict):
    config_store.save(data)
    return {"ok": True}
```

```python
# panel/server.py
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
```

- [ ] **Step 5: Run config_store tests**

Run: `pytest tests/test_config_store.py -v`
Expected: PASS (2 passed)

- [ ] **Step 6: Commit**

```bash
git add panel/config_store.py panel/routes_config.py panel/server.py tests/test_config_store.py
git commit -m "feat: panel config store + GET/PUT config routes"
```

---

### Task 8: discord_fetch + discord routes

**Files:**
- Create: `panel/discord_fetch.py`, `panel/routes_discord.py`
- Test: `tests/test_discord_fetch.py`
- Modify: `panel/server.py` (mount router)

**Interfaces:**
- Produces:
  - `discord_fetch.list_guilds(token) -> list[dict]` (id, name)
  - `discord_fetch.list_channels(token, guild_id) -> list[dict]` (id, name, type)
  - `discord_fetch.list_roles(token, guild_id) -> list[dict]` (id, name)
  - Routes `GET /api/discord/guilds`, `/channels?guild_id=`, `/roles?guild_id=` (token read from saved config)

- [ ] **Step 1: Write failing tests (mock httpx)**

```python
# tests/test_discord_fetch.py
import httpx
from panel import discord_fetch

def test_list_channels_filters_text(monkeypatch):
    payload = [{"id": "1", "name": "general", "type": 0},
               {"id": "2", "name": "voice", "type": 2}]
    def fake_get(url, headers, params=None, timeout=None):
        return httpx.Response(200, json=payload, request=httpx.Request("GET", url))
    monkeypatch.setattr(discord_fetch.httpx, "get", fake_get)
    chans = discord_fetch.list_channels("tok", 123)
    assert [c["id"] for c in chans] == ["1"]  # only text (type 0)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_discord_fetch.py -v`
Expected: FAIL (module not found)

- [ ] **Step 3: Implement discord_fetch.py**

```python
# panel/discord_fetch.py
import httpx

BASE = "https://discord.com/api/v10"

def _headers(token):
    return {"Authorization": f"Bot {token}"}

def list_guilds(token):
    r = httpx.get(f"{BASE}/users/@me/guilds", headers=_headers(token), timeout=10)
    r.raise_for_status()
    return [{"id": g["id"], "name": g["name"]} for g in r.json()]

def list_channels(token, guild_id):
    r = httpx.get(f"{BASE}/guilds/{guild_id}/channels", headers=_headers(token), timeout=10)
    r.raise_for_status()
    return [{"id": c["id"], "name": c["name"], "type": c["type"]}
            for c in r.json() if c["type"] == 0]

def list_roles(token, guild_id):
    r = httpx.get(f"{BASE}/guilds/{guild_id}/roles", headers=_headers(token), timeout=10)
    r.raise_for_status()
    return [{"id": r_["id"], "name": r_["name"]} for r_ in r.json()]
```

- [ ] **Step 4: Implement routes_discord.py**

```python
# panel/routes_discord.py
from fastapi import APIRouter, HTTPException
import httpx
from panel import config_store, discord_fetch

router = APIRouter(prefix="/api/discord")

def _token():
    tok = config_store.load().get("bot_token", "")
    if not tok:
        raise HTTPException(400, "ยังไม่ได้ตั้ง token")
    return tok

@router.get("/guilds")
def guilds():
    try:
        return discord_fetch.list_guilds(_token())
    except httpx.HTTPStatusError as e:
        raise HTTPException(e.response.status_code, "token ไม่ถูกต้องหรือหมดสิทธิ์")

@router.get("/channels")
def channels(guild_id: int):
    return discord_fetch.list_channels(_token(), guild_id)

@router.get("/roles")
def roles(guild_id: int):
    return discord_fetch.list_roles(_token(), guild_id)
```

- [ ] **Step 5: Mount router in server.py**

Add `from panel import routes_discord` and `app.include_router(routes_discord.router)` **before** the `app.mount("/", StaticFiles...)` line (static mount must stay last).

- [ ] **Step 6: Run test to verify it passes**

Run: `pytest tests/test_discord_fetch.py -v`
Expected: PASS (1 passed)

- [ ] **Step 7: Commit**

```bash
git add panel/discord_fetch.py panel/routes_discord.py panel/server.py tests/test_discord_fetch.py
git commit -m "feat: panel fetches guilds/channels/roles from Discord REST"
```

---

### Task 9: process_manager + bot routes

**Files:**
- Create: `panel/process_manager.py`, `panel/routes_bot.py`
- Test: `tests/test_process_manager.py`
- Modify: `panel/server.py` (mount router)

**Interfaces:**
- Produces:
  - `process_manager.start() -> None`, `stop() -> None`, `restart() -> None`
  - `process_manager.status() -> dict` (`{"running": bool, "pid": int | None}`)
  - `process_manager.get_log(max_lines=200) -> list[str]`
  - Routes `POST /api/bot/start|stop|restart`, `GET /api/bot/status`, `GET /api/bot/log`

- [ ] **Step 1: Write failing test (start a trivial process)**

```python
# tests/test_process_manager.py
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_process_manager.py -v`
Expected: FAIL (module not found)

- [ ] **Step 3: Implement process_manager.py**

```python
# panel/process_manager.py
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
```

- [ ] **Step 4: Implement routes_bot.py**

```python
# panel/routes_bot.py
from fastapi import APIRouter
from panel import process_manager

router = APIRouter(prefix="/api/bot")

@router.post("/start")
def start(): process_manager.start(); return process_manager.status()

@router.post("/stop")
def stop(): process_manager.stop(); return process_manager.status()

@router.post("/restart")
def restart(): process_manager.restart(); return process_manager.status()

@router.get("/status")
def status(): return process_manager.status()

@router.get("/log")
def log(): return {"lines": process_manager.get_log()}
```

- [ ] **Step 5: Mount router in server.py**

Add `from panel import routes_bot` and `app.include_router(routes_bot.router)` before the static mount.

- [ ] **Step 6: Run test to verify it passes**

Run: `pytest tests/test_process_manager.py -v`
Expected: PASS (1 passed)

- [ ] **Step 7: Commit**

```bash
git add panel/process_manager.py panel/routes_bot.py panel/server.py tests/test_process_manager.py
git commit -m "feat: panel controls bot subprocess with live log buffer"
```

---

## Phase 3 — Panel frontend

### Task 10: Static UI (5 tabs)

**Files:**
- Create: `panel/static/index.html`, `panel/static/app.js`, `panel/static/style.css`

**Interfaces:**
- Consumes: all `/api/*` routes above.

- [ ] **Step 1: Build index.html with 5 tabs**

Single page, tab buttons: Setup, Dashboard, Channels, Permissions, Auto-trade. Each tab a `<section>`. Include `<script src="app.js">` and `<link href="style.css">`. Setup: token input + "ตรวจสอบ" button + guild `<select>`. Dashboard: status dot, Start/Stop/Restart buttons, `<pre id="log">`. Channels: table filled by JS (one row per key in config.channels, each with a channel `<select>`). Permissions: 3 groups, each a multi-select of roles. Auto-trade: two editable tables (dark/light).

- [ ] **Step 2: Build app.js**

Real functions (no placeholders):
- `loadConfig()` → GET /api/config, cache in `state.config`
- `saveConfig()` → PUT /api/config with `state.config`, toast "บันทึกแล้ว — กด Restart บอทเพื่อให้มีผล"
- `verifyToken()` → PUT token then GET /api/discord/guilds, fill guild select; on 400/401 show error
- `onGuildChange()` → GET channels+roles, populate all dropdowns, tick current selections from config
- `renderChannels()`, `renderPermissions()`, `renderTrade()` build the tables from `state.config` + fetched lists
- Dashboard: `startBot/stopBot/restartBot` POST, `pollStatus()` + `pollLog()` on `setInterval(1500)` updating the status dot and `<pre>`
- Wire each tab's "บันทึก" button to write back into `state.config` then `saveConfig()`

- [ ] **Step 3: Build style.css**

Minimal dark theme: tab bar, tables, status dot (green/red), log `<pre>` monospace scroll box. No framework, no external fonts (CSP-free for packaging).

- [ ] **Step 4: Manual smoke test**

Run: `python -m uvicorn panel.server:app --port 8770`
Open `http://localhost:8770`. Verify: tabs switch, token verify lists guilds, selecting a guild fills channel/role dropdowns, saving persists to config.json, Start shows log + green dot, Stop → red dot.

- [ ] **Step 5: Commit**

```bash
git add panel/static/
git commit -m "feat: panel web UI with 5 config tabs and live dashboard"
```

---

## Phase 4 — Launcher & packaging

### Task 11: launcher.py (start panel + open browser; --run-bot)

**Files:**
- Create: `launcher.py`

**Interfaces:**
- `python launcher.py` → serves panel + opens browser
- `python launcher.py --run-bot` → runs the bot (used by process_manager in packaged mode)

- [ ] **Step 1: Implement launcher.py**

```python
# launcher.py
import sys, threading, time, webbrowser
import uvicorn

def run_bot():
    from bot import main as bot_main
    import asyncio
    asyncio.run(bot_main.main())

def run_panel():
    from panel import config_store
    config_store.ensure_exists()
    port = config_store.load().get("panel_port", 8770)
    threading.Thread(
        target=lambda: (time.sleep(1.5), webbrowser.open(f"http://localhost:{port}")),
        daemon=True).start()
    uvicorn.run("panel.server:app", host="127.0.0.1", port=port, log_level="warning")

if __name__ == "__main__":
    if "--run-bot" in sys.argv:
        run_bot()
    else:
        run_panel()
```

- [ ] **Step 2: Point process_manager at the launcher when frozen**

In `panel/process_manager.py`, change `BOT_CMD` selection:
```python
import sys
if getattr(sys, "frozen", False):
    BOT_CMD = [sys.executable, "--run-bot"]        # packaged exe re-invokes itself
else:
    BOT_CMD = [sys.executable, "-u", "-m", "bot.main"]
```

- [ ] **Step 3: Manual test**

Run: `python launcher.py`
Expected: browser opens to the panel; from Dashboard, Start launches the bot and log streams.

- [ ] **Step 4: Commit**

```bash
git add launcher.py panel/process_manager.py
git commit -m "feat: launcher serves panel, opens browser, --run-bot entry"
```

---

### Task 12: PyInstaller packaging

**Files:**
- Create: `build.spec`

**Interfaces:** produces `dist/BotManager.exe`

- [ ] **Step 1: Write build.spec**

One-file spec bundling `panel/static`, `config.example.json`, and discord.py data. Collect `discord`, `fastapi`, `uvicorn` hidden imports. `datas=[('panel/static','panel/static'), ('config.example.json','.')]`. `console=True` (so bot log is visible if launched from terminal; the browser UI is primary).

- [ ] **Step 2: Build**

Run: `pyinstaller build.spec`
Expected: `dist/BotManager.exe` produced, no missing-module errors.

- [ ] **Step 3: Manual test the exe on a clean path**

Copy `dist/BotManager.exe` + `config.example.json` to an empty folder, double-click. Expected: `config.json` created, browser opens, set token → verify → configure → Start → bot online. Confirms subprocess self-invocation (`--run-bot`) works when frozen.

- [ ] **Step 4: Commit**

```bash
git add build.spec
git commit -m "build: PyInstaller one-file packaging"
```

---

## Self-Review Notes

- **Spec coverage:** control panel (T7,T9,T10,T11), channel routing (T2,T3,T4,T10), role→group perms (T2,T3,T4,T10), auto-trade (T2,T5,T10), token+run/stop/log (T6,T9,T10,T11), dropdowns from Discord (T8,T10), .exe+auto-open (T11,T12), ID-not-name (T2,T3,T8), error handling (T8 token errors, T7 fallback, T9 crash via status) — all mapped.
- **Deferred per spec:** skill buff/nerf, multi-guild, live-reload, panel auth — not in tasks (correct).
- **Type consistency:** `get_channel_id/get_role_ids/get_trade_roles` names identical across T2→T3→T5; `BOT_CMD`, `status()`, `get_log()` consistent T9→T11.
- **Known manual-only checks:** UI (T10), packaging (T12), full bot run (T6.4) are manual — inherent to GUI/packaging work.
