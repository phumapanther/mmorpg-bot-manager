# Skill Buff/Nerf Config Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move the 8 class-skill buffs/nerfs and 4 role-bound passive bonuses out of hardcoded Python into `config.json`, editable via a new Panel "Skills" tab, and fix the pre-existing bug where World Boss fights never actually apply skill effects.

**Architecture:** `bot/config_loader.py` gains two read functions (`get_skill_config`, `get_role_bonuses`) that both `bot/views/game_views.py` and `bot/cogs/world_boss.py` call at combat-resolution time (not cached at import) — the same "read at call time" pattern already used by `role_shop.py`. `bot/cogs/voice_chat_tracker.py`'s three hardcoded role-name checks become one small reusable helper that looks up role IDs against `get_role_bonuses(bonus_type)`. The Panel gets a new tab: 8 Thai-labeled skill cards + an editable role-bonus list (same add/delete/hide-selected pattern already used for Auto-trade/Shop).

**Tech Stack:** Python 3.12, discord.py 2.x, FastAPI panel, pytest, vanilla JS panel frontend (existing `panel/static/app.js` conventions).

## Global Constraints

- Never overwrite existing `config.json` values — this project's config-loading functions already merge missing keys from `config.example.json` without touching present ones (see `bot/config_loader.py`/`panel/config_store.py` `_merge_missing`); new config keys added here must follow the same shape so that merge continues to work automatically.
- `role_bonuses` entries default to `role_id: null` (the real Discord role IDs for "ทีมงาน"/"นักกวี"/"ผู้ส่งสาร" are not known ahead of time — an admin must set them via the Panel after upgrading, same pattern as `shop_items`'s `rank_role` entries and `auto_trade_roles`).
- Config is read at call time inside combat/event functions, never cached at import time (matches `bot/cogs/role_shop.py`'s existing convention).
- All Discord role/channel references are IDs, never names (project-wide rule already established).
- Keep `bot/` and `panel/` as separate packages with no cross-imports (existing architecture — small helpers may be duplicated between them if ever needed, though this plan doesn't require that).

---

## File Structure

```
bot/
├── config_loader.py          # MODIFY: add get_skill_config, get_role_bonuses
├── views/
│   └── game_views.py          # MODIFY: process_turn reads config_loader instead of module-level SKILL_CONFIG; delete the dead SKILL_CONFIG dict
│   └── profile_embed.py        # MODIFY: delete dead TEAMWORK_CLASSES + stale comment block
├── cogs/
│   ├── world_boss.py           # MODIFY: fix skill-schema bug (chance formula, backstab/fireball/heal field names)
│   └── voice_chat_tracker.py   # MODIFY: replace 3 hardcoded role-name checks with a shared config-driven helper
config.example.json             # MODIFY: add "skills" and "role_bonuses" top-level keys
panel/static/
├── index.html                  # MODIFY: add "Skills" tab button + section
└── app.js                      # MODIFY: add skill-card rendering + role-bonus list editor
tests/
├── test_config_loader.py       # MODIFY: add tests for get_skill_config, get_role_bonuses
├── test_world_boss.py          # CREATE: tests for the fixed skill-chance formula
└── test_voice_chat_tracker.py  # CREATE: tests for the shared role-bonus-stacking helper
```

---

### Task 1: config_loader — `get_skill_config` + `get_role_bonuses`, plus config schema

**Files:**
- Modify: `bot/config_loader.py`
- Modify: `config.example.json`
- Test: `tests/test_config_loader.py`

**Interfaces:**
- Produces:
  - `get_skill_config(class_name: str, skill_name: str) -> dict` — returns the skill's field dict (e.g. `{"chance_base": 80, "chance_lvl_scale": 1, "damage_multiplier": 2}`), or `{}` if the class/skill isn't in config.
  - `get_role_bonuses(bonus_type: str) -> list[dict]` — returns `[{"role_id": int, "value": float}, ...]` for every `config.json` `role_bonuses` entry whose `bonus_type` matches and whose `role_id` is not `None`. `role_id` is coerced to `int`; `value` is coerced to `float`.

- [ ] **Step 1: Add the "skills" section to `config.example.json`**

Read the file first to find its current end (top-level keys currently end with `auto_trade_roles`). Insert a new top-level `"skills"` key after `auto_trade_roles`, using the EXACT values currently hardcoded in `bot/views/game_views.py`'s `SKILL_CONFIG` (lines 12-58 of that file):

```json
  "skills": {
    "Warrior": {
      "heavy_strike": {"chance_base": 80, "chance_lvl_scale": 1, "damage_multiplier": 2},
      "shield_bash":  {"duration": 3, "reduction_base": 0.50, "reduction_lvl_scale": 0.005}
    },
    "Mage": {
      "fireball":  {"duration": 2, "burn_base": 0.05, "burn_lvl_scale": 0.002},
      "frostbolt": {"duration_base": 1, "duration_lvl_scale": 0.05, "damage_reduce": 0.75}
    },
    "Rogue": {
      "backstab": {"chance_base": 50, "chance_lvl_scale": 0.5, "damage_reflect_mult": 1.5},
      "evasion":  {"chance_base": 100, "chance_lvl_scale": 0.0}
    },
    "Cleric": {
      "heal":      {"heal_percent_base": 0.40, "heal_lvl_scale": 0.01},
      "holy_aura": {"chance_base": 50, "chance_lvl_scale": 1}
    }
  },
```

- [ ] **Step 2: Add the "role_bonuses" section to `config.example.json`**

Add right after `"skills"`, before the file's closing `}`. This covers all 4 role-gated bonuses currently hardcoded by role NAME in `bot/cogs/voice_chat_tracker.py` (staff "ทีมงาน" affects TWO separate mechanics — voice EXP and chat event-counter — so it needs two entries):

```json
  "role_bonuses": [
    {"label": "ทีมงาน (Staff) — โบนัส EXP ห้องเสียง", "role_id": null, "bonus_type": "voice_exp_multiplier", "value": 1.2},
    {"label": "นักกวี (Poet) — โบนัส EXP ห้องเสียง", "role_id": null, "bonus_type": "voice_exp_multiplier", "value": 1.5},
    {"label": "ทีมงาน (Staff) — โบนัสสถิติแชทกิจกรรม", "role_id": null, "bonus_type": "chat_event_multiplier", "value": 2.0},
    {"label": "ผู้ส่งสาร (Messenger) — โบนัสเงินแชท", "role_id": null, "bonus_type": "chat_gold_multiplier", "value": 3.0}
  ]
```

Double-check the JSON is valid afterward: `python -c "import json; json.load(open('config.example.json', encoding='utf-8')); print('valid')"` → expect `valid`.

- [ ] **Step 2: Write the failing tests**

Append to `tests/test_config_loader.py` (reuse the existing `_write` helper already defined in the file):

```python
def test_get_skill_config_returns_fields(tmp_path, monkeypatch):
    cfg = {"skills": {"Warrior": {"heavy_strike": {"chance_base": 80, "damage_multiplier": 2}}}}
    monkeypatch.setattr(config_loader, "CONFIG_PATH", str(_write(tmp_path, cfg)))
    config_loader.reload_config()
    result = config_loader.get_skill_config("Warrior", "heavy_strike")
    assert result == {"chance_base": 80, "damage_multiplier": 2}

def test_get_skill_config_missing_returns_empty_dict(tmp_path, monkeypatch):
    monkeypatch.setattr(config_loader, "CONFIG_PATH", str(_write(tmp_path, {"skills": {}})))
    config_loader.reload_config()
    assert config_loader.get_skill_config("Warrior", "nonexistent") == {}
    assert config_loader.get_skill_config("NoSuchClass", "heavy_strike") == {}

def test_get_role_bonuses_filters_by_type_and_coerces(tmp_path, monkeypatch):
    cfg = {"role_bonuses": [
        {"label": "a", "role_id": "111", "bonus_type": "voice_exp_multiplier", "value": 1.2},
        {"label": "b", "role_id": "222", "bonus_type": "chat_gold_multiplier", "value": 3},
        {"label": "c", "role_id": None, "bonus_type": "voice_exp_multiplier", "value": 1.5},
    ]}
    monkeypatch.setattr(config_loader, "CONFIG_PATH", str(_write(tmp_path, cfg)))
    config_loader.reload_config()
    result = config_loader.get_role_bonuses("voice_exp_multiplier")
    assert result == [{"role_id": 111, "value": 1.2}]  # unset role_id (None) excluded

def test_get_role_bonuses_no_match_returns_empty_list(tmp_path, monkeypatch):
    monkeypatch.setattr(config_loader, "CONFIG_PATH", str(_write(tmp_path, {"role_bonuses": []})))
    config_loader.reload_config()
    assert config_loader.get_role_bonuses("voice_exp_multiplier") == []
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `python -m pytest tests/test_config_loader.py -k "skill_config or role_bonuses" -v`
Expected: FAIL with `AttributeError` (functions not defined)

- [ ] **Step 4: Implement the two functions**

Add to `bot/config_loader.py`, near `get_trade_roles` (same file, same style):

```python
def get_skill_config(class_name, skill_name):
    return dict(get_config().get("skills", {}).get(class_name, {}).get(skill_name, {}))

def get_role_bonuses(bonus_type):
    entries = get_config().get("role_bonuses", [])
    result = []
    for e in entries:
        if e.get("bonus_type") == bonus_type and e.get("role_id") is not None:
            result.append({"role_id": int(e["role_id"]), "value": float(e.get("value", 1.0))})
    return result
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `python -m pytest tests/test_config_loader.py -v`
Expected: PASS (all tests in the file, existing + 4 new)

- [ ] **Step 6: Commit**

```bash
git add bot/config_loader.py config.example.json tests/test_config_loader.py
git commit -m "feat: add get_skill_config/get_role_bonuses + skills/role_bonuses config schema"
```

---

### Task 2: World Boss — fix skill-consumption bug

**Files:**
- Modify: `bot/cogs/world_boss.py`
- Test: Create `tests/test_world_boss.py`

**Interfaces:**
- Consumes: `config_loader.get_skill_config(class_name, skill_name) -> dict` (from Task 1)
- Produces: `BossView.get_random_skill(self, class_name, p_lvl) -> (skill_name_or_None, config_dict_or_None)` — signature now takes `p_lvl` (previously just `class_name`); later tasks/manual testing rely on this new signature.

This is the actual bug fix: `bot/cogs/world_boss.py` currently reads `config.get("chance", 0)` — a key that has never existed in the skill config (real keys are `chance_base`/`chance_lvl_scale`) — so `chance` is always `0` and no skill has ever procced in a World Boss fight. Separately, `attack()`'s per-skill branches reference `skill_data["damage_multiplier"]` for `backstab` (wrong key — backstab's real field is `damage_reflect_mult`; this would raise `KeyError` and crash the whole attack once skills start procing), and `skill_data["burn_damage"]`/`skill_data["heal_amount"]` for `fireball`/`heal` (neither key exists — the real fields are `burn_base`+`burn_lvl_scale` and `heal_percent_base`+`heal_lvl_scale`, which need to be turned into an actual damage/heal number, same formula `bot/views/game_views.py` already uses for the regular monster-fight flow).

- [ ] **Step 1: Write the failing tests**

Create `tests/test_world_boss.py`:

```python
import sys
sys.path.insert(0, ".")  # no-op if already on path; keeps import consistent with other test files
from unittest.mock import patch
from bot.cogs.world_boss import BossView

def _make_view():
    return BossView({"name": "Test Boss", "hp": 500, "max_hp": 500, "dice_count": 1, "dice_sides": 6, "exp": 10, "gold": 10})

def test_get_random_skill_uses_chance_base_and_lvl_scale():
    view = _make_view()
    fake_config = {"Warrior": {"heavy_strike": {"chance_base": 100, "chance_lvl_scale": 0, "damage_multiplier": 2}}}
    with patch("bot.cogs.world_boss.SKILL_CONFIG", fake_config), \
         patch("bot.cogs.world_boss.random.randint", return_value=1), \
         patch("bot.cogs.world_boss.random.choice", return_value="heavy_strike"):
        skill, data = view.get_random_skill("Warrior", p_lvl=1)
    assert skill == "heavy_strike"
    assert data == {"chance_base": 100, "chance_lvl_scale": 0, "damage_multiplier": 2}  # proc'd because roll(1) <= chance(100)

def test_get_random_skill_fails_when_roll_above_chance():
    view = _make_view()
    fake_config = {"Warrior": {"heavy_strike": {"chance_base": 10, "chance_lvl_scale": 0, "damage_multiplier": 2}}}
    with patch("bot.cogs.world_boss.SKILL_CONFIG", fake_config), \
         patch("bot.cogs.world_boss.random.randint", return_value=50), \
         patch("bot.cogs.world_boss.random.choice", return_value="heavy_strike"):
        skill, data = view.get_random_skill("Warrior", p_lvl=1)
    assert skill == "heavy_strike"
    assert data is None  # roll(50) > chance(10) -> skill attempted but missed

def test_get_random_skill_chance_scales_with_level():
    view = _make_view()
    fake_config = {"Rogue": {"backstab": {"chance_base": 50, "chance_lvl_scale": 2, "damage_reflect_mult": 1.5}}}
    with patch("bot.cogs.world_boss.SKILL_CONFIG", fake_config), \
         patch("bot.cogs.world_boss.random.randint", return_value=70), \
         patch("bot.cogs.world_boss.random.choice", return_value="backstab"):
        skill, data = view.get_random_skill("Rogue", p_lvl=10)  # chance = 50 + 10*2 = 70, roll(70) <= 70 -> proc
    assert data is not None

def test_get_random_skill_unknown_class_returns_none():
    view = _make_view()
    skill, data = view.get_random_skill("NoSuchClass", p_lvl=1)
    assert skill is None and data is None
```

Note: this patches the module-level `SKILL_CONFIG` name inside `bot.cogs.world_boss` — Step 4 keeps a module-level `SKILL_CONFIG` reference in `world_boss.py` populated from `config_loader.get_skill_config` results at call time inside `get_random_skill` itself (see implementation below), so patching `bot.cogs.world_boss.SKILL_CONFIG` directly is how the test substitutes config values without touching the real `config.json`/`config.example.json`.

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_world_boss.py -v`
Expected: FAIL (`get_random_skill()` doesn't accept `p_lvl` yet; `chance_base` not read yet)

- [ ] **Step 3: Fix `bot/cogs/world_boss.py`**

Change the import line (remove the now-unnecessary `SKILL_CONFIG` import from `game_views`, since world_boss builds its own view via `config_loader`):

Replace:
```python
import bot.models.player_model as player_model
from bot.views.game_views import SKILL_CONFIG
```
with:
```python
import bot.models.player_model as player_model
from bot import config_loader

SKILL_CONFIG = {
    "Warrior": ["heavy_strike", "shield_bash"],
    "Mage": ["fireball", "frostbolt"],
    "Rogue": ["backstab", "evasion"],
    "Cleric": ["heal", "holy_aura"],
}
```
(`SKILL_CONFIG` here is now just the fixed list of skill NAMES per class — used only to pick which skill name to randomly try — not the numeric values, which now always come from `config_loader.get_skill_config` at call time. This keeps a module-level name for the test to patch while making the real numeric values config-driven.)

Replace `get_random_skill`:
```python
    def get_random_skill(self, class_name):
        try:
            if class_name not in SKILL_CONFIG:
                print(f"[LOG] [SKILL] ไม่พบค่าคอนฟิกสำหรับคลาส: {class_name} (ข้ามระบบสกิล)")
                return None, None
            
            skills = list(SKILL_CONFIG[class_name].keys())
            chosen_skill = random.choice(skills)
            config = SKILL_CONFIG[class_name][chosen_skill]
            
            roll = random.randint(1, 100)
            chance = config.get("chance", 0)
            
            if roll <= chance:
                print(f"[LOG] [SKILL] คลาส {class_name} ทอยเต๋าสกิลได้ {roll}/{chance} -> [สุ่มติดสกิล: {chosen_skill}]")
                return chosen_skill, config
            else:
                print(f"[LOG] [SKILL] คลาส {class_name} ทอยเต๋าสกิลได้ {roll}/{chance} -> [สกิลวืด/ไม่ติด: {chosen_skill}]")
                return chosen_skill, None 
        except Exception as e:
            print(f"[ERROR] [get_random_skill] เกิดข้อผิดพลาด: {e}")
            return None, None
```
with:
```python
    def get_random_skill(self, class_name, p_lvl):
        try:
            if class_name not in SKILL_CONFIG:
                print(f"[LOG] [SKILL] ไม่พบค่าคอนฟิกสำหรับคลาส: {class_name} (ข้ามระบบสกิล)")
                return None, None
            
            skills = SKILL_CONFIG[class_name]
            chosen_skill = random.choice(skills)
            config = config_loader.get_skill_config(class_name, chosen_skill)
            
            roll = random.randint(1, 100)
            chance = config.get("chance_base", 0) + (p_lvl * config.get("chance_lvl_scale", 0))
            
            if roll <= chance:
                print(f"[LOG] [SKILL] คลาส {class_name} ทอยเต๋าสกิลได้ {roll}/{chance} -> [สุ่มติดสกิล: {chosen_skill}]")
                return chosen_skill, config
            else:
                print(f"[LOG] [SKILL] คลาส {class_name} ทอยเต๋าสกิลได้ {roll}/{chance} -> [สกิลวืด/ไม่ติด: {chosen_skill}]")
                return chosen_skill, None 
        except Exception as e:
            print(f"[ERROR] [get_random_skill] เกิดข้อผิดพลาด: {e}")
            return None, None
```

In `attack()`, fetch the player's level before calling `get_random_skill`. Find:
```python
            # 2. หาวิชคลาสของผู้เล่นจากบทบาท (Roles)
            user_roles = [r.name for r in user.roles]
            player_class = "None"
            for c in ["Warrior", "Mage", "Rogue", "Cleric"]:
                if c in user_roles:
                    player_class = c
                    break
            print(f"[LOG] [CLASS_CHECK] ตรวจพบการทำงานคลาสของ {user.display_name} -> [{player_class}]")
```
Add right after it:
```python
            player_data = player_model.get_player(user_id)
            p_lvl = player_data.get("level", 1) if player_data else 1
```

Find:
```python
            # 4. สุ่มและคำนวณสกิล
            skill_used, skill_data = self.get_random_skill(player_class)
```
Replace with:
```python
            # 4. สุ่มและคำนวณสกิล
            skill_used, skill_data = self.get_random_skill(player_class, p_lvl)
```

Find the per-skill effect branches:
```python
                    if skill_used == "heavy_strike":
                        final_dmg = int(final_dmg * skill_data["damage_multiplier"])
                        combat_log += f"✨ **Heavy Strike สำเร็จ!** ดาเมจทวีคูณเป็น **{final_dmg}** หน่วย!\n"
                    elif skill_used == "backstab":
                        final_dmg = int(final_dmg * skill_data["damage_multiplier"])
                        combat_log += f"🗡️ **Backstab สำเร็จ!** แอบแทงข้างหลัง ดาเมจคริติคอล **{final_dmg}** หน่วย!\n"
                    elif skill_used == "fireball":
                        final_dmg += skill_data["burn_damage"]
                        combat_log += f"🔥 **Fireball เข้าเป้า!** เผาไหม้บอสเพิ่มอีก {skill_data['burn_damage']} ดาเมจ! รวมเป็น **{final_dmg}**\n"
                    elif skill_used == "heal":
                        heal_amt = skill_data["heal_amount"]
                        combat_log += f"✨ **Heal ทำงาน!** คุณฟื้นฟูเลือดตัวเอง **+{heal_amt} HP** และตีบอสไป **{final_dmg}** ดาเมจ!\n"
                    elif skill_used in ["shield_bash", "frostbolt", "holy_aura", "evasion"]:
                        combat_log += f"🛡️ ร่ายสกิล **{skill_used}** ป้องกันการโจมตีสวนกลับของบอสในตาต่อไป!\n"
```
Replace with (fixes `backstab`'s field name; computes real `burn_damage`/`heal_amt` from the actual config fields instead of the nonexistent keys):
```python
                    if skill_used == "heavy_strike":
                        final_dmg = int(final_dmg * skill_data["damage_multiplier"])
                        combat_log += f"✨ **Heavy Strike สำเร็จ!** ดาเมจทวีคูณเป็น **{final_dmg}** หน่วย!\n"
                    elif skill_used == "backstab":
                        final_dmg = int(final_dmg * skill_data["damage_reflect_mult"])
                        combat_log += f"🗡️ **Backstab สำเร็จ!** แอบแทงข้างหลัง ดาเมจคริติคอล **{final_dmg}** หน่วย!\n"
                    elif skill_used == "fireball":
                        burn_percent = skill_data["burn_base"] + (p_lvl * skill_data["burn_lvl_scale"])
                        burn_damage = int(self.boss["max_hp"] * burn_percent)
                        final_dmg += burn_damage
                        combat_log += f"🔥 **Fireball เข้าเป้า!** เผาไหม้บอสเพิ่มอีก {burn_damage} ดาเมจ! รวมเป็น **{final_dmg}**\n"
                    elif skill_used == "heal":
                        heal_percent = skill_data["heal_percent_base"] + (p_lvl * skill_data["heal_lvl_scale"])
                        heal_amt = int(player_data.get("max_hp", 100) * heal_percent) if player_data else 0
                        combat_log += f"✨ **Heal ทำงาน!** คุณฟื้นฟูเลือดตัวเอง **+{heal_amt} HP** และตีบอสไป **{final_dmg}** ดาเมจ!\n"
                    elif skill_used in ["shield_bash", "frostbolt", "holy_aura", "evasion"]:
                        combat_log += f"🛡️ ร่ายสกิล **{skill_used}** ป้องกันการโจมตีสวนกลับของบอสในตาต่อไป!\n"
```

Do not add an actual database write for the heal amount — this matches the pre-existing behavior (the original code also only displayed a heal message without persisting HP in World Boss fights; fixing the displayed number's source is in scope, adding a new persistence mechanic is not).

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_world_boss.py -v`
Expected: PASS (4 passed)

- [ ] **Step 5: Verify no other breakage**

Run: `python -m pytest -v`
Expected: all tests pass (previous count + 4 + the 4 from Task 1 = previous + 8)

Run: `python -c "import bot.cogs.world_boss; print('OK')"`
Expected: `OK`, no import error

- [ ] **Step 6: Commit**

```bash
git add bot/cogs/world_boss.py tests/test_world_boss.py
git commit -m "fix: World Boss now correctly reads chance_base/chance_lvl_scale and per-skill fields, so skills actually proc"
```

---

### Task 3: game_views.py — read skills from config, delete dead constant

**Files:**
- Modify: `bot/views/game_views.py`

**Interfaces:**
- Consumes: `config_loader.get_skill_config(class_name, skill_name) -> dict` (from Task 1)

This task has no dedicated automated test: `MonsterEventView.process_turn` is a ~300-line async method taking a live `discord.Interaction`, and this project has no existing test coverage of `game_views.py`'s combat logic (mocking a full Interaction/Member/Guild chain here would be disproportionate to the rest of this plan's testing style). Verification is via `compileall` + a manual playtest at the end of this plan (see Task 6's manual verification step), plus the structural greps below.

- [ ] **Step 1: Add the config_loader import**

At the top of `bot/views/game_views.py`, add:
```python
from bot import config_loader
```

- [ ] **Step 2: Delete the dead `SKILL_CONFIG` dict**

Delete lines 9-58 (the entire `# 📊 [SKILL BALANCE CONFIG] ...` comment block and the `SKILL_CONFIG = {...}` dict definition shown in the Task 2 read-through above) — every value in it is being replaced by calls to `config_loader.get_skill_config`.

- [ ] **Step 3: Replace every `SKILL_CONFIG[...]` reference inside `process_turn` with `config_loader.get_skill_config(...)` calls**

Find each of these exact lines (all inside `MonsterEventView.process_turn`) and replace as shown:

```python
                    w_cfg = SKILL_CONFIG["Warrior"]["heavy_strike"]
```
→
```python
                    w_cfg = config_loader.get_skill_config("Warrior", "heavy_strike")
```

```python
                    r_cfg = SKILL_CONFIG["Rogue"]["evasion"]
```
→
```python
                    r_cfg = config_loader.get_skill_config("Rogue", "evasion")
```

```python
                    c_cfg = SKILL_CONFIG["Cleric"]["heal"]
```
→
```python
                    c_cfg = config_loader.get_skill_config("Cleric", "heal")
```

```python
                if skill_used == "skill_shield_bash": 
                    self.active_buffs["shield_bash"] = SKILL_CONFIG["Warrior"]["shield_bash"]["duration"]
                elif skill_used == "skill_fireball": 
                    self.active_buffs["fireball"] = SKILL_CONFIG["Mage"]["fireball"]["duration"]
                elif skill_used == "skill_frostbolt": 
                    f_cfg = SKILL_CONFIG["Mage"]["frostbolt"]
                    self.active_buffs["frostbolt"] = f_cfg["duration_base"] + int(p_lvl * f_cfg["duration_lvl_scale"])
                elif skill_used == "skill_holy_aura": 
                    self.active_buffs["holy_aura"] = 3
                elif skill_used == "skill_backstab":
                    r_b_cfg = SKILL_CONFIG["Rogue"]["backstab"]
                    if random.randint(1, 100) <= (r_b_cfg["chance_base"] + (p_lvl * r_b_cfg["chance_lvl_scale"])): 
                        self.active_buffs["backstab"] = 1
```
→
```python
                if skill_used == "skill_shield_bash": 
                    self.active_buffs["shield_bash"] = config_loader.get_skill_config("Warrior", "shield_bash")["duration"]
                elif skill_used == "skill_fireball": 
                    self.active_buffs["fireball"] = config_loader.get_skill_config("Mage", "fireball")["duration"]
                elif skill_used == "skill_frostbolt": 
                    f_cfg = config_loader.get_skill_config("Mage", "frostbolt")
                    self.active_buffs["frostbolt"] = f_cfg["duration_base"] + int(p_lvl * f_cfg["duration_lvl_scale"])
                elif skill_used == "skill_holy_aura": 
                    self.active_buffs["holy_aura"] = 3
                elif skill_used == "skill_backstab":
                    r_b_cfg = config_loader.get_skill_config("Rogue", "backstab")
                    if random.randint(1, 100) <= (r_b_cfg["chance_base"] + (p_lvl * r_b_cfg["chance_lvl_scale"])): 
                        self.active_buffs["backstab"] = 1
```

```python
                    m_cfg = SKILL_CONFIG["Mage"]["fireball"]
                    burn_percent = m_cfg["burn_base"] + (p_lvl * m_cfg["burn_lvl_scale"])
```
→
```python
                    m_cfg = config_loader.get_skill_config("Mage", "fireball")
                    burn_percent = m_cfg["burn_base"] + (p_lvl * m_cfg["burn_lvl_scale"])
```

```python
                    if self.active_buffs.get("frostbolt", 0) > 0:
                        f_reduce = SKILL_CONFIG["Mage"]["frostbolt"]["damage_reduce"]
                        damage_to_player = int(damage_to_player * (1 - f_reduce))
                        combat_log += f"❄️ *น้ำแข็งเกาะ:* บอสติดแช่แข็ง พลังโจมตีลดลง {int(f_reduce*100)}%! (โดนดาเมจเบา ๆ `- {damage_to_player}`)\n"
                        
                    elif self.active_buffs.get("holy_aura", 0) > 0 and random.randint(1, 100) <= (SKILL_CONFIG["Cleric"]["holy_aura"]["chance_base"] + (p_lvl * SKILL_CONFIG["Cleric"]["holy_aura"]["chance_lvl_scale"])):
                        damage_to_player = 0
                        combat_log += "✨ *Holy Aura ทำงาน:* ร่างกายส่องแสงบล็อคพลังโจมตีของบอสกลายเป็น 0!\n"
                        
                    elif self.active_buffs.get("backstab", 0) > 0:
                        damage_to_player = int(damage_to_player * 0.2)
                        rogue_reflect = int(player_roll * 5 * SKILL_CONFIG["Rogue"]["backstab"]["damage_reflect_mult"])
                        self.monster_hp = max(0, self.monster_hp - rogue_reflect)
                        combat_log += f"🗡️ *Backstab คุมเชิง:* ดาเมจสวนกลับลดลง 80% (โดนแค่ `- {damage_to_player}`) พร้อมวาร์ปตลบหลังแทงบอสสวนกลับหงายหลังฟาด `- {rogue_reflect}` หน่วย! (บอสเหลือ HP: {self.monster_hp})\n"
                        
                    elif self.active_buffs.get("shield_bash", 0) > 0:
                        s_b_cfg = SKILL_CONFIG["Warrior"]["shield_bash"]
                        reduction = s_b_cfg["reduction_base"] + (p_lvl * s_b_cfg["reduction_lvl_scale"])
                        damage_to_player = int(damage_to_player * (1 - min(0.9, reduction)))
                        combat_log += f"🛡️ *Shield Bash บล็อก:* ดาเมจลดลงครอบคลุมเกราะ (โดนแค่ `- {damage_to_player}`)\n"
```
→
```python
                    if self.active_buffs.get("frostbolt", 0) > 0:
                        f_reduce = config_loader.get_skill_config("Mage", "frostbolt")["damage_reduce"]
                        damage_to_player = int(damage_to_player * (1 - f_reduce))
                        combat_log += f"❄️ *น้ำแข็งเกาะ:* บอสติดแช่แข็ง พลังโจมตีลดลง {int(f_reduce*100)}%! (โดนดาเมจเบา ๆ `- {damage_to_player}`)\n"
                        
                    elif self.active_buffs.get("holy_aura", 0) > 0 and random.randint(1, 100) <= _holy_aura_chance(p_lvl):
                        damage_to_player = 0
                        combat_log += "✨ *Holy Aura ทำงาน:* ร่างกายส่องแสงบล็อคพลังโจมตีของบอสกลายเป็น 0!\n"
                        
                    elif self.active_buffs.get("backstab", 0) > 0:
                        damage_to_player = int(damage_to_player * 0.2)
                        rogue_reflect = int(player_roll * 5 * config_loader.get_skill_config("Rogue", "backstab")["damage_reflect_mult"])
                        self.monster_hp = max(0, self.monster_hp - rogue_reflect)
                        combat_log += f"🗡️ *Backstab คุมเชิง:* ดาเมจสวนกลับลดลง 80% (โดนแค่ `- {damage_to_player}`) พร้อมวาร์ปตลบหลังแทงบอสสวนกลับหงายหลังฟาด `- {rogue_reflect}` หน่วย! (บอสเหลือ HP: {self.monster_hp})\n"
                        
                    elif self.active_buffs.get("shield_bash", 0) > 0:
                        s_b_cfg = config_loader.get_skill_config("Warrior", "shield_bash")
                        reduction = s_b_cfg["reduction_base"] + (p_lvl * s_b_cfg["reduction_lvl_scale"])
                        damage_to_player = int(damage_to_player * (1 - min(0.9, reduction)))
                        combat_log += f"🛡️ *Shield Bash บล็อก:* ดาเมจลดลงครอบคลุมเกราะ (โดนแค่ `- {damage_to_player}`)\n"
```
(`_holy_aura_chance(p_lvl)` is a tiny module-level helper added in the next step, since the original single-line expression referenced `SKILL_CONFIG["Cleric"]["holy_aura"]` twice inline — pulling it into one helper avoids calling `config_loader.get_skill_config` twice for the same lookup on one line.)

Add this helper near the top of `bot/views/game_views.py`, right after the `config_loader` import:
```python
def _holy_aura_chance(p_lvl):
    cfg = config_loader.get_skill_config("Cleric", "holy_aura")
    return cfg["chance_base"] + (p_lvl * cfg["chance_lvl_scale"])
```

- [ ] **Step 4: Verify no `SKILL_CONFIG` references remain and the file still compiles**

Run: `grep -n "SKILL_CONFIG" bot/views/game_views.py`
Expected: no matches

Run: `python -m compileall -q bot/views/game_views.py`
Expected: no output

Run: `python -c "import bot.views.game_views; print('OK')"`
Expected: `OK`

- [ ] **Step 5: Run full test suite to confirm nothing else broke**

Run: `python -m pytest -v`
Expected: all pass (same count as end of Task 2 — this task adds no new tests, per the scoping note above)

- [ ] **Step 6: Commit**

```bash
git add bot/views/game_views.py
git commit -m "refactor: game_views combat reads skill values from config_loader; delete dead SKILL_CONFIG constant"
```

---

### Task 4: voice_chat_tracker.py — role bonuses become config-driven

**Files:**
- Modify: `bot/cogs/voice_chat_tracker.py`
- Test: Create `tests/test_voice_chat_tracker.py`

**Interfaces:**
- Consumes: `config_loader.get_role_bonuses(bonus_type) -> list[dict]` (from Task 1)
- Produces: `bot.cogs.voice_chat_tracker._stacked_multiplier(role_ids_held: set[int], bonus_type: str) -> float` — a module-level helper, reused across 3 call sites in this file. `role_ids_held` is a set of Discord role IDs (ints) the member currently holds.

This replaces three hardcoded role-NAME checks (`"ทีมงาน"`, `"꒰ EN ꒱ นักกวี 𝄞⋆"`, `"꒰ PR ꒱ ผู้ส่งสาร"`) with ID-based lookups against `role_bonuses` from config. If a player holds multiple roles that both match the same `bonus_type`, their values multiply together (matches the current stacking behavior of the two independent `if` checks for voice EXP).

- [ ] **Step 1: Write the failing test**

Create `tests/test_voice_chat_tracker.py`:

```python
from unittest.mock import patch
from bot.cogs import voice_chat_tracker

def test_stacked_multiplier_no_match_returns_one():
    with patch("bot.cogs.voice_chat_tracker.config_loader.get_role_bonuses", return_value=[]):
        assert voice_chat_tracker._stacked_multiplier({111, 222}, "voice_exp_multiplier") == 1.0

def test_stacked_multiplier_single_match():
    bonuses = [{"role_id": 111, "value": 1.5}]
    with patch("bot.cogs.voice_chat_tracker.config_loader.get_role_bonuses", return_value=bonuses):
        assert voice_chat_tracker._stacked_multiplier({111, 222}, "voice_exp_multiplier") == 1.5

def test_stacked_multiplier_stacks_multiple_matches():
    bonuses = [{"role_id": 111, "value": 1.2}, {"role_id": 222, "value": 1.5}]
    with patch("bot.cogs.voice_chat_tracker.config_loader.get_role_bonuses", return_value=bonuses):
        result = voice_chat_tracker._stacked_multiplier({111, 222}, "voice_exp_multiplier")
    assert abs(result - 1.8) < 1e-9  # 1.2 * 1.5

def test_stacked_multiplier_ignores_roles_player_does_not_have():
    bonuses = [{"role_id": 999, "value": 5.0}]
    with patch("bot.cogs.voice_chat_tracker.config_loader.get_role_bonuses", return_value=bonuses):
        assert voice_chat_tracker._stacked_multiplier({111, 222}, "voice_exp_multiplier") == 1.0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_voice_chat_tracker.py -v`
Expected: FAIL (`_stacked_multiplier` not defined / `config_loader` not imported)

- [ ] **Step 3: Implement the helper and wire it into both call sites**

Add near the top of `bot/cogs/voice_chat_tracker.py` (alongside the existing `import bot.models.player_model as player_model`):
```python
from bot import config_loader
```

Add this module-level function (outside the `VoiceChatTracker` class, anywhere before it):
```python
def _stacked_multiplier(role_ids_held, bonus_type):
    multiplier = 1.0
    for bonus in config_loader.get_role_bonuses(bonus_type):
        if bonus["role_id"] in role_ids_held:
            multiplier *= bonus["value"]
    return multiplier
```

In `voice_exp_tracker`, find:
```python
                    # 1. เช็กยศจาก member object
                    roles = [role.name for role in member.roles]

                    # 2. ตั้งค่าตัวคูณพื้นฐานตามเลเวล
                    multiplier = 0.5
                    if p_lvl >= 80: multiplier = 0.5   # เลเวลสูงเก็บช้าลง
                    elif p_lvl >= 40: multiplier = 0.8
                    elif p_lvl >= 20: multiplier = 1.0
                    else: multiplier = 1.5

                    # 3. เพิ่มโบนัสให้นักกวี (ได้รับ EXP เพิ่ม x4 จากโบนัสห้องเสียง)
                    # ถ้าเป็นนักกวี ให้คูณเพิ่มอีก 4 เท่าจากค่าเดิมที่คำนวณได้
                    if "ทีมงาน" in roles:
                        multiplier = multiplier * 1.2
                        print(f"🛠️ [Voice Reward] คุณ {member.name} (ทีมงาน) ได้รับโบนัส EXP ห้องเสียง x2!")

                    # 3. เพิ่มโบนัสให้นักกวี (คูณ 4)
                    if "꒰ EN ꒱ นักกวี 𝄞⋆" in roles:
                        multiplier = multiplier * 1.5
                        print(f"✨ [Voice Reward] คุณ {member.name} (นักกวี) ได้รับโบนัส EXP ห้องเสียง x4!")
```
Replace with:
```python
                    # 1. เช็กยศจาก member object (ตั้งค่าโบนัสได้ที่ Panel แท็บ Skills)
                    role_ids_held = {role.id for role in member.roles}

                    # 2. ตั้งค่าตัวคูณพื้นฐานตามเลเวล
                    multiplier = 0.5
                    if p_lvl >= 80: multiplier = 0.5   # เลเวลสูงเก็บช้าลง
                    elif p_lvl >= 40: multiplier = 0.8
                    elif p_lvl >= 20: multiplier = 1.0
                    else: multiplier = 1.5

                    # 3. โบนัสยศพิเศษ (ตั้งค่าได้ที่ Panel แท็บ Skills)
                    role_bonus = _stacked_multiplier(role_ids_held, "voice_exp_multiplier")
                    if role_bonus != 1.0:
                        multiplier *= role_bonus
                        print(f"✨ [Voice Reward] คุณ {member.name} ได้รับโบนัส EXP ห้องเสียง x{role_bonus}!")
```

In `on_message`, find:
```python
        # 1. จัดการยศเพื่อคำนวณโบนัส
        roles = [role.name for role in message.author.roles]
        
        # 📈 เก็บสถิติ (ทีมงานได้ event_text * 2)
        event_bonus = 2 if "ทีมงาน" in roles else 1
        current_total = player.get("total_text", 0)
        current_event = player.get("event_text", 0)
        
        player_model.update_player_field(user_id, "total_text", current_total + 1)
        player_model.update_player_field(user_id, "event_text", current_event + event_bonus)

        current_time = time.time()
        
        # ⏱️ ระบบ Cooldown 10 วิ
        if user_id in self.chat_cooldowns:
            if current_time - self.chat_cooldowns[user_id] < 10: 
                return
                
        # 💰 คำนวณเงิน (ผู้ส่งสารได้เงิน * 3)
        gold_multi = 3 if "꒰ PR ꒱ ผู้ส่งสาร" in roles else 1
        gained_gold = random.randint(10, 300) * gold_multi
```
Replace with:
```python
        # 1. จัดการยศเพื่อคำนวณโบนัส (ตั้งค่าได้ที่ Panel แท็บ Skills)
        role_ids_held = {role.id for role in message.author.roles}
        
        # 📈 เก็บสถิติ (โบนัสตัวคูณสถิติแชทกิจกรรมตามยศ)
        event_bonus = int(round(_stacked_multiplier(role_ids_held, "chat_event_multiplier")))
        current_total = player.get("total_text", 0)
        current_event = player.get("event_text", 0)
        
        player_model.update_player_field(user_id, "total_text", current_total + 1)
        player_model.update_player_field(user_id, "event_text", current_event + event_bonus)

        current_time = time.time()
        
        # ⏱️ ระบบ Cooldown 10 วิ
        if user_id in self.chat_cooldowns:
            if current_time - self.chat_cooldowns[user_id] < 10: 
                return
                
        # 💰 คำนวณเงิน (โบนัสตัวคูณเงินตามยศ)
        gold_multi = _stacked_multiplier(role_ids_held, "chat_gold_multiplier")
        gained_gold = int(random.randint(10, 300) * gold_multi)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_voice_chat_tracker.py -v`
Expected: PASS (4 passed)

- [ ] **Step 5: Verify no leftover hardcoded role-name checks and the file still compiles**

Run: `grep -n "ทีมงาน\|นักกวี\|ผู้ส่งสาร" bot/cogs/voice_chat_tracker.py`
Expected: no matches

Run: `python -c "import bot.cogs.voice_chat_tracker; print('OK')"`
Expected: `OK`

Run: `python -m pytest -v`
Expected: all pass (previous count + 4)

- [ ] **Step 6: Commit**

```bash
git add bot/cogs/voice_chat_tracker.py tests/test_voice_chat_tracker.py
git commit -m "refactor: voice/chat role bonuses are config-driven (role ID, not role name), stacking supported"
```

---

### Task 5: profile_embed.py — delete dead TEAMWORK_CLASSES

**Files:**
- Modify: `bot/views/profile_embed.py`

**Interfaces:** none (pure deletion, no other file imports `TEAMWORK_CLASSES` — already confirmed via repo-wide grep during design).

- [ ] **Step 1: Delete the dead list and its stale comment block**

Find and delete these lines from `bot/views/profile_embed.py`:
```python
TEAMWORK_CLASSES = ["꒰ PL ꒱ อัศวิน ⚔️", "꒰ DT ꒱ นักบวช .⋆♱", "꒰ PR ꒱ ผู้ส่งสาร", "꒰ EN ꒱ นักกวี 𝄞⋆"]
# บัพพาสซีพทีมงาน 
# (any further stale comment lines describing Knight/Priest/Messenger/Poet bonuses that sit directly below this list)
# ผู้ส่งสาร เพิ่มโอกาสหลบหลีก 15% และเพิ่ม gold ที่ได้รับจากการพิมแชท 100%
# นักกวี เพิ่มโอกาสหลบหลีก 15% และเพิ่ม EXP ที่ได้รับจากการพูดคุยในห้องเสียงอีก 100%
```
(Read the file first to see the exact current line range and any adjacent blank lines/comments describing Knight/Priest, and remove the whole stale block cleanly — leave surrounding unrelated code untouched.)

- [ ] **Step 2: Verify**

Run: `grep -rn "TEAMWORK_CLASSES" bot/`
Expected: no matches

Run: `python -c "import bot.views.profile_embed; print('OK')"`
Expected: `OK`

Run: `python -m pytest -v`
Expected: all pass (same count as end of Task 4 — no tests added/removed)

- [ ] **Step 3: Commit**

```bash
git add bot/views/profile_embed.py
git commit -m "chore: remove dead TEAMWORK_CLASSES list and stale comment describing never-built bonuses"
```

---

### Task 6: Panel — "Skills" tab UI

**Files:**
- Modify: `panel/static/index.html`
- Modify: `panel/static/app.js`

**Interfaces:**
- Consumes: `GET /api/config` / `PUT /api/config` (existing), specifically the `skills` and `role_bonuses` keys added in Task 1. Reuses `state.roles` (already fetched by `onGuildChange()`).

No automated test (pure frontend, matches this project's existing pattern for UI-only tasks). Verify via headless curl checks; full click-through testing is a manual step for the user.

- [ ] **Step 1: Add the tab button and section shell to `panel/static/index.html`**

Find:
```html
  <button class="tab-btn" data-tab="shop">Shop</button>
```
Add right after it:
```html
  <button class="tab-btn" data-tab="skills">Skills</button>
```

Find the `<section id="tab-shop" ...>...</section>` block and add this new section right after it (before `<script src="app.js"></script>`):
```html
<section id="tab-skills" class="tab-panel">
  <h2>Skills</h2>
  <div id="skillCards"></div>
  <h3>โบนัสยศพิเศษ</h3>
  <table id="roleBonusTable">
    <thead><tr><th>ชื่อ</th><th>ยศ</th><th>ประเภทบัพ</th><th>ค่าตัวคูณ</th><th></th></tr></thead>
    <tbody></tbody>
  </table>
  <button id="roleBonusAddBtn" type="button">+ เพิ่มแถว</button>
  <button id="skillsSaveBtn" class="save-btn">บันทึก</button>
</section>
```

- [ ] **Step 2: Add the skill-card rendering + role-bonus editor to `panel/static/app.js`**

Add this new section after the existing "shop tab" section (after `shopSave()`, before `// ---------- tabs ----------`):

```js
// ---------- skills tab ----------

const SKILL_FIELD_LABELS = {
  chance_base: "โอกาสติดสกิลพื้นฐาน (%)",
  chance_lvl_scale: "โอกาสเพิ่มต่อเลเวล (%)",
  damage_multiplier: "ตัวคูณดาเมจ",
  duration: "ระยะเวลาบัพ (เทิร์น)",
  reduction_base: "% ลดดาเมจพื้นฐาน",
  reduction_lvl_scale: "% ลดดาเมจเพิ่มต่อเลเวล",
  burn_base: "% ดาเมจเผาไหม้พื้นฐาน (จาก HP บอส)",
  burn_lvl_scale: "% ดาเมจเผาไหม้เพิ่มต่อเลเวล",
  duration_base: "ระยะเวลาพื้นฐาน (เทิร์น)",
  duration_lvl_scale: "ระยะเวลาเพิ่มต่อเลเวล",
  damage_reduce: "% หักล้างดาเมจ",
  damage_reflect_mult: "ตัวคูณดาเมจสะท้อนกลับ",
  heal_percent_base: "% ฮีลพื้นฐาน (จาก Max HP)",
  heal_lvl_scale: "% ฮีลเพิ่มต่อเลเวล",
};

const SKILL_LABELS = {
  Warrior: { heavy_strike: "เจาะเกราะสุดพลัง (heavy_strike)", shield_bash: "โล่กระแทก (shield_bash)" },
  Mage: { fireball: "ลูกไฟ (fireball)", frostbolt: "ธนูน้ำแข็ง (frostbolt)" },
  Rogue: { backstab: "แทงข้างหลัง (backstab)", evasion: "หลบหลีก (evasion)" },
  Cleric: { heal: "รักษา (heal)", holy_aura: "ออร่าศักดิ์สิทธิ์ (holy_aura)" },
};

const ROLE_BONUS_TYPES = [
  { value: "voice_exp_multiplier", label: "ตัวคูณ EXP ห้องเสียง" },
  { value: "chat_event_multiplier", label: "ตัวคูณสถิติแชทกิจกรรม" },
  { value: "chat_gold_multiplier", label: "ตัวคูณเงินแชท" },
];

function renderSkillCards() {
  const root = document.getElementById("skillCards");
  root.innerHTML = "";
  const skills = state.config.skills || {};
  for (const className of Object.keys(SKILL_LABELS)) {
    const classSkills = skills[className] || {};
    const classHeader = document.createElement("h3");
    classHeader.textContent = className;
    root.appendChild(classHeader);
    for (const skillKey of Object.keys(SKILL_LABELS[className])) {
      const fields = classSkills[skillKey] || {};
      const card = document.createElement("div");
      card.className = "skill-card";
      card.dataset.class = className;
      card.dataset.skill = skillKey;
      const title = document.createElement("strong");
      title.textContent = SKILL_LABELS[className][skillKey];
      card.appendChild(title);
      for (const fieldKey of Object.keys(fields)) {
        const row = document.createElement("div");
        row.className = "field";
        const label = document.createElement("label");
        label.textContent = SKILL_FIELD_LABELS[fieldKey] || fieldKey;
        const input = document.createElement("input");
        input.type = "number";
        input.step = "any";
        input.className = "skill-field";
        input.dataset.field = fieldKey;
        input.value = fields[fieldKey];
        row.appendChild(label);
        row.appendChild(input);
        card.appendChild(row);
      }
      root.appendChild(card);
    }
  }
}

function refreshRoleBonusOptions() {
  const selects = Array.from(document.querySelectorAll("#roleBonusTable select.bonus-role"));
  const currentValues = selects.map((sel) => sel.value);
  selects.forEach((sel, i) => {
    const used = new Set(currentValues.filter((v, j) => j !== i && v));
    Array.from(sel.options).forEach((opt) => {
      if (!opt.value) return;
      opt.hidden = used.has(opt.value) && opt.value !== sel.value;
    });
  });
}

function roleBonusRoleSelectHtml(selectedId) {
  const sel = document.createElement("select");
  sel.className = "bonus-role";
  sel.innerHTML = '<option value="">-- ไม่ระบุ --</option>';
  for (const r of state.roles) {
    const opt = document.createElement("option");
    opt.value = r.id;
    opt.textContent = r.name;
    sel.appendChild(opt);
  }
  if (selectedId != null) sel.value = String(selectedId);
  sel.addEventListener("change", refreshRoleBonusOptions);
  return sel;
}

function roleBonusTypeSelectHtml(selectedType) {
  const sel = document.createElement("select");
  sel.className = "bonus-type";
  for (const t of ROLE_BONUS_TYPES) {
    const opt = document.createElement("option");
    opt.value = t.value;
    opt.textContent = t.label;
    sel.appendChild(opt);
  }
  sel.value = selectedType || ROLE_BONUS_TYPES[0].value;
  return sel;
}

function renderRoleBonuses() {
  const tbody = document.querySelector("#roleBonusTable tbody");
  tbody.innerHTML = "";
  const bonuses = state.config.role_bonuses || [];
  bonuses.forEach((item, idx) => {
    const tr = document.createElement("tr");
    tr.dataset.idx = idx;

    const tdLabel = document.createElement("td");
    const labelInput = document.createElement("input");
    labelInput.type = "text";
    labelInput.className = "bonus-label";
    labelInput.value = item.label || "";
    tdLabel.appendChild(labelInput);
    tr.appendChild(tdLabel);

    const tdRole = document.createElement("td");
    const roleSel = roleBonusRoleSelectHtml(item.role_id);
    tdRole.appendChild(roleSel);
    tr.appendChild(tdRole);

    const tdType = document.createElement("td");
    const typeSel = roleBonusTypeSelectHtml(item.bonus_type);
    tdType.appendChild(typeSel);
    tr.appendChild(tdType);

    const tdValue = document.createElement("td");
    const valueInput = document.createElement("input");
    valueInput.type = "number";
    valueInput.step = "any";
    valueInput.className = "bonus-value";
    valueInput.value = item.value != null ? item.value : 1.0;
    tdValue.appendChild(valueInput);
    tr.appendChild(tdValue);

    const tdDel = document.createElement("td");
    const delBtn = document.createElement("button");
    delBtn.type = "button";
    delBtn.textContent = "ลบ";
    delBtn.onclick = () => {
      state.config.role_bonuses.splice(idx, 1);
      renderRoleBonuses();
    };
    tdDel.appendChild(delBtn);
    tr.appendChild(tdDel);

    tbody.appendChild(tr);
  });
  refreshRoleBonusOptions();
}

function renderSkillsTab() {
  renderSkillCards();
  renderRoleBonuses();
}

function addRoleBonusRow() {
  if (!state.config.role_bonuses) state.config.role_bonuses = [];
  state.config.role_bonuses.push({ label: "โบนัสใหม่", role_id: null, bonus_type: ROLE_BONUS_TYPES[0].value, value: 1.0 });
  renderRoleBonuses();
}

async function skillsSave() {
  const skills = state.config.skills || {};
  document.querySelectorAll("#skillCards .skill-card").forEach((card) => {
    const className = card.dataset.class;
    const skillKey = card.dataset.skill;
    const fields = {};
    card.querySelectorAll(".skill-field").forEach((input) => {
      fields[input.dataset.field] = parseFloat(input.value);
    });
    if (!skills[className]) skills[className] = {};
    skills[className][skillKey] = fields;
  });
  state.config.skills = skills;

  const tbody = document.querySelector("#roleBonusTable tbody");
  const bonuses = [];
  tbody.querySelectorAll("tr").forEach((tr) => {
    const label = tr.querySelector(".bonus-label").value;
    const role_id = tr.querySelector(".bonus-role").value || null;
    const bonus_type = tr.querySelector(".bonus-type").value;
    const value = parseFloat(tr.querySelector(".bonus-value").value) || 1.0;
    bonuses.push({ label, role_id, bonus_type, value });
  });
  state.config.role_bonuses = bonuses;

  await saveConfig();
}
```

- [ ] **Step 3: Wire up event listeners and render calls in `init()` / `onGuildChange()`**

In `init()`, find:
```js
  document.getElementById("darkAddBtn").addEventListener("click", () => addTradeRow("dark"));
  document.getElementById("lightAddBtn").addEventListener("click", () => addTradeRow("light"));
  document.getElementById("tradeSaveBtn").addEventListener("click", tradeSave);

  document.getElementById("shopAddBtn").addEventListener("click", addShopRow);
  document.getElementById("shopSaveBtn").addEventListener("click", shopSave);
```
Add right after:
```js
  document.getElementById("roleBonusAddBtn").addEventListener("click", addRoleBonusRow);
  document.getElementById("skillsSaveBtn").addEventListener("click", skillsSave);
```

Find every occurrence of the render sequence (three occurrences in the file — two inside `onGuildChange()`, one inside `init()` — read the file first to find their exact current indentation, matching the style already used for `renderShop()` which was added the same way in a previous task):
```js
    renderChannels();
    renderPermissions();
    renderTrade();
    renderShop();
```
and
```js
  renderChannels();
  renderPermissions();
  renderTrade();
  renderShop();
```
Add `renderSkillsTab();` as a new line immediately after each `renderShop();` line, at each of the 3 call sites, matching that call site's existing indentation exactly.

- [ ] **Step 4: Verify**

Run: `python -c "import panel.server; print('OK')"`
Expected: `OK`

Start the server, confirm the new tab/content is served, then stop it:
```bash
python -m uvicorn panel.server:app --port 8770 &
sleep 1
curl -s http://localhost:8770/ | grep -c "tab-skills"
curl -s http://localhost:8770/app.js | grep -c "renderSkillsTab"
```
Both counts should be `> 0`. Kill the background uvicorn process afterward.

Run: `python -m pytest -v`
Expected: all pass (same count as end of Task 5 — this task adds no Python tests)

- [ ] **Step 5: Commit**

```bash
git add panel/static/index.html panel/static/app.js
git commit -m "feat: add Skills tab to panel UI (8 skill cards + role-bonus editor)"
```

---

## Self-Review Notes

- **Spec coverage:** 8 skills configurable (Task 1 schema + Task 3 consumption) ✅; World Boss bug fix (Task 2) ✅; role bonuses ID-based + configurable (Task 1 schema + Task 4 consumption) ✅ — plus the extra "ทีมงาน chat_event_multiplier" mechanic found during precise code reading, folded in since it's the exact same function being touched; TEAMWORK_CLASSES cleanup (Task 5) ✅; Panel UI (Task 6) ✅.
- **Deferred per spec, confirmed not in any task:** armor%/enrage table/durability costs, Knight/Priest bonuses, all other game-balance categories (monsters, drops, EXP/gold rates broadly) — correct, none appear above.
- **Placeholder scan:** no TBD/TODO; every step has literal code or exact commands.
- **Type consistency:** `get_skill_config`/`get_role_bonuses` names and return shapes are identical everywhere they're referenced (Task 1 defines them, Tasks 2-4 consume them, Task 6's UI writes back the same field names). `_stacked_multiplier` signature consistent between its definition (Task 4) and its 2 call sites (Task 4) and its tests (Task 4).
- **Known deviation from the approved design doc, made during precise code-reading (per user's standing instruction to decide autonomously when the plan requires a judgment call the design doc didn't anticipate):** the design doc listed only `voice_exp_multiplier`/`chat_gold_multiplier` as the 2 fixed `bonus_type` values; reading the actual code surfaced a third mechanic (staff role also doubles the `event_text` chat-stat counter, `chat_event_multiplier`) living in the exact same `on_message` handler being edited for the gold-multiplier fix. Included it in Task 1's schema and Task 4's implementation rather than leaving one more hardcoded-by-name check sitting untouched right next to the ones being fixed.
