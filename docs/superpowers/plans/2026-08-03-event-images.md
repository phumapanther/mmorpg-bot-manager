# ภาพพิกเซลอาร์ตประกอบเหตุการณ์ — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** ทุกเหตุการณ์ในเกม (เดิน/มอน/เดินทาง/ธีม/ไอเทมพิเศษ/ตาย-เกิด) มีภาพพิกเซลอาร์ต 512×512 ≤ ~100KB แนบไปกับข้อความ โดยเจนล่วงหน้า ~172 ภาพเก็บใน `assets/events/`

**Architecture:** โมดูลใหม่ `bot/event_images.py` เป็นแหล่งเดียวของ logic หาไฟล์ภาพ (คืน `discord.File` หรือ `None` — ไม่มีไฟล์ = เกมทำงานแบบเดิม) สคริปต์ `scripts/gen_event_images.py` เจนภาพจาก Pollinations.ai โดย**สร้างรายชื่อภาพอัตโนมัติจากข้อมูลเกม** (CONTINENTS/WEEKLY_THEMES/config.example.json) กันหลุด sync จุดแนบภาพเป็นการแก้บางๆ ที่ call site เดิม

**Tech Stack:** Python 3.11+, discord.py 2.x, Pillow (มีแล้วจาก `qrcode[pil]`), stdlib `urllib` (ห้ามเพิ่ม dependency ใหม่), pytest

**Spec:** `docs/superpowers/specs/2026-08-03-event-images-design.md`

## Global Constraints

- ภาพทุกใบ: PNG 512×512 quantize 256 สี เป้า ≤ ~100KB (ผู้เล่นเน็ตช้าโหลดได้)
- ทุกจุดแนบภาพ: ไฟล์หาย → helper คืน `None` → **ไม่ส่ง kwarg `file`** — ข้อความออกเหมือนเดิม เกมห้ามพังเด็ดขาด
- สร้าง `discord.File` ใหม่ทุกครั้งที่ส่ง (discord.py ห้าม reuse File object)
- ภาพมอนในไฟต์แนบ**เฉพาะเทิร์นแรก** — เทิร์นถัดไปห้ามอัปโหลดซ้ำ
- ห้ามเพิ่ม dependency ใหม่ใน requirements.txt
- คอมมิตท้ายทุก Task; ก่อนเริ่ม Task 6 (แตะโค้ดเกม) ตั้ง tag `pre-event-images`
- รันเทสทั้งชุดด้วย `python -m pytest tests/ -q` จาก root repo

## รายการคีย์ภาพทั้งหมด (~172)

- **เดิน 63:** `<continent>_<event>.png` — continent ∈ {main, demon, frozen, nether, volcanic, sylvan, mechanized, skyward, ocean}, event ∈ {monster, village, treasure, dungeon, npc, trap, calm}
- **เรียกบอส 3:** `mini_summon.png`, `main_summon.png`, `unbeatable_summon.png`
- **special 10:** `blizzard_ambush, ancestral_feast, volcanic_eruption, poison_thicket, emp_field, ancient_excavation, falling_island, goddess_gamble, black_market_dealer, zombie_parasite` (.png)
- **ธีม 13:** `theme_<key>.png` — key ∈ {normal, faction_war, palette, royal_convoy, dragon_nesting, solar_eclipse, mana_meteor, absolute_zero, blood_moon, goddess_dice, masquerade, black_market, zombie}
- **ยานพาหนะ 4:** `vehicle_<key>.png` — key ∈ {airship, ship, portal, caravan}
- **มาถึงทวีป 9:** `arrival_<continent>.png`
- **มอน ~50:** `monster_<slug>.png` — slug จากชื่ออังกฤษในวงเล็บ lowercase แทนช่องว่าง/ขีดด้วย `_` เช่น `🐉 มังกรน้ำแข็ง (Ice Dragon)` → `monster_ice_dragon.png` — enumerate จาก `CONTINENTS[*]["mods"]["monster_pool"]` + `WEEKLY_THEMES[*]["mods"]["monster_pool"]` + แรงค์พื้นฐาน 5 (`MONSTER_RANKS` ใน game_views: Common/Mini-Boss/Main-Boss/Secret/Unbeatable → ชื่อมีวงเล็บอังกฤษอยู่แล้ว เช่น `monster_common.png`)
- **ไอเทม 18:** `item_wedding_ring, item_dye_profile, item_convoy_compass, item_monster_lure, item_monster_ward, item_monster_trap, item_legend_weapon, item_magic_bag` + `item_art_*` 10 ใบจาก config.example.json (effect `equip_artifact` → `item_<effect_value>.png` เช่น `item_art_fire_ring.png`)
- **ตาย/เกิด 2:** `death.png`, `respawn.png`

---

### Task 1: โมดูล `bot/event_images.py` + เทส

**Files:**
- Create: `bot/event_images.py`
- Test: `tests/test_event_images.py`

**Interfaces (Produces):**
- `ASSETS_DIR: Path` — ชี้ `<repo>/assets/events`
- `monster_slug(name: str) -> str | None` — `"🐉 มังกรน้ำแข็ง (Ice Dragon)"` → `"ice_dragon"`; ไม่มีวงเล็บอังกฤษ → `None`
- `event_image(key: str, continent: str | None = None) -> discord.File | None` — ลอง `<continent>_<key>.png` ก่อนแล้ว fallback `<key>.png`
- `monster_image(name: str, rank: str | None = None) -> discord.File | None` — ชื่อมอน → slug → ไฟล์; ไม่มีไฟล์ → fallback ภาพแรงค์ (`monster_<slug ของ MONSTER_RANKS[rank]["name"]>`); ไม่มีอีก → `None`
- `item_use_image(item_info: dict, continent: str | None = None) -> discord.File | None`
- `file_kwargs(f) -> dict` — `{"file": f}` ถ้า f ไม่ใช่ None, ไม่งั้น `{}` (ตัวช่วยให้ call site สั้น)

- [ ] **Step 1: เขียนเทส (ยังไม่มีโมดูล — ต้อง fail)**

```python
# tests/test_event_images.py
"""เทสโมดูลภาพอีเวนต์ — โฟกัส logic หาไฟล์/fallback (ไม่แตะเน็ต ไม่แตะ Discord จริง)"""
import bot.event_images as ei


def test_monster_slug():
    assert ei.monster_slug("🐉 มังกรน้ำแข็ง (Ice Dragon)") == "ice_dragon"
    assert ei.monster_slug("🟢 มอนสเตอร์ทั่วไป (Common)") == "common"
    assert ei.monster_slug("⚔️ อัศวินน้ำแข็งโบราณ (Ancient Ice Knight)") == "ancient_ice_knight"
    assert ei.monster_slug("🌈 จอมมารรุ้งสลับสี (Prismatic)") == "prismatic"
    assert ei.monster_slug("ไม่มีวงเล็บอังกฤษ") is None


def test_event_image_missing_returns_none(tmp_path, monkeypatch):
    monkeypatch.setattr(ei, "ASSETS_DIR", tmp_path)
    assert ei.event_image("village", "frozen") is None


def test_event_image_continent_first_then_fallback(tmp_path, monkeypatch):
    monkeypatch.setattr(ei, "ASSETS_DIR", tmp_path)
    (tmp_path / "village.png").write_bytes(b"png")
    f = ei.event_image("village", "frozen")          # ไม่มี frozen_village → fallback กลาง
    assert f is not None and f.filename == "village.png"
    (tmp_path / "frozen_village.png").write_bytes(b"png")
    f2 = ei.event_image("village", "frozen")         # มีของทวีป → ใช้ของทวีป
    assert f2.filename == "frozen_village.png"


def test_monster_image_fallback_rank(tmp_path, monkeypatch):
    monkeypatch.setattr(ei, "ASSETS_DIR", tmp_path)
    assert ei.monster_image("🐉 มังกรน้ำแข็ง (Ice Dragon)", "Main-Boss") is None
    (tmp_path / "monster_main_boss.png").write_bytes(b"png")
    f = ei.monster_image("🐉 มังกรน้ำแข็ง (Ice Dragon)", "Main-Boss")
    assert f.filename == "monster_main_boss.png"     # ไม่มีภาพเฉพาะตัว → ภาพแรงค์
    (tmp_path / "monster_ice_dragon.png").write_bytes(b"png")
    f2 = ei.monster_image("🐉 มังกรน้ำแข็ง (Ice Dragon)", "Main-Boss")
    assert f2.filename == "monster_ice_dragon.png"   # มีภาพเฉพาะตัว → ใช้ก่อน


def test_item_use_image_mapping(tmp_path, monkeypatch):
    monkeypatch.setattr(ei, "ASSETS_DIR", tmp_path)
    for name in ("item_wedding_ring", "item_monster_trap", "item_art_fire_ring",
                 "item_legend_weapon", "item_magic_bag", "respawn",
                 "mini_summon", "frozen_village"):
        (tmp_path / f"{name}.png").write_bytes(b"png")
    assert ei.item_use_image({"effect": "wedding_ring"}).filename == "item_wedding_ring.png"
    assert ei.item_use_image({"effect": "apply_status", "effect_value": "monster_trap"}).filename == "item_monster_trap.png"
    assert ei.item_use_image({"effect": "apply_status", "effect_value": "warm"}) is None  # ยาทั่วไป — ไม่มีภาพ
    assert ei.item_use_image({"effect": "equip_artifact", "effect_value": "art_fire_ring"}).filename == "item_art_fire_ring.png"
    assert ei.item_use_image({"effect": "revive"}).filename == "respawn.png"
    assert ei.item_use_image({"effect": "set_state", "effect_value": "mini_summon"}).filename == "mini_summon.png"
    assert ei.item_use_image({"effect": "set_state", "effect_value": "warp_village"}, continent="frozen").filename == "frozen_village.png"
    assert ei.item_use_image({"type": "weapon", "equip_key": "Legen_Weapon"}).filename == "item_legend_weapon.png"
    assert ei.item_use_image({"type": "weapon", "equip_key": "Iron_Weapon"}) is None
    assert ei.item_use_image({"type": "bag", "equip_key": "Magic_Bag"}).filename == "item_magic_bag.png"
    assert ei.item_use_image({"effect": "heal"}) is None


def test_file_kwargs():
    assert ei.file_kwargs(None) == {}
    class FakeFile: pass
    f = FakeFile()
    assert ei.file_kwargs(f) == {"file": f}
```

- [ ] **Step 2: รันเทสให้เห็นว่า fail** — `python -m pytest tests/test_event_images.py -q` คาดหวัง: `ModuleNotFoundError: bot.event_images`

- [ ] **Step 3: เขียนโมดูล**

```python
# bot/event_images.py
"""ภาพพิกเซลอาร์ตประกอบเหตุการณ์ — แหล่งเดียวของ logic หาไฟล์ภาพใน assets/events/

ทุกฟังก์ชันคืน discord.File หรือ None — ไม่มีไฟล์ = ผู้เรียกไม่แนบภาพ เกมทำงานแบบเดิม
(สเปค: docs/superpowers/specs/2026-08-03-event-images-design.md)
"""
import re
from pathlib import Path

import discord

ASSETS_DIR = Path(__file__).resolve().parent.parent / "assets" / "events"

# ไอเทมติดสถานะที่เห็นผลตอนเดิน — มีภาพตอนใช้สำเร็จ (ยาบัฟไฟต์ทั่วไปไม่ใส่ กันแชทรก)
_WALK_STATUS_ITEMS = {"convoy_compass", "monster_lure", "monster_ward", "monster_trap"}
# ใบวาปบังคับเหตุการณ์ → ใช้ภาพอีเวนต์ของทวีปปัจจุบันซ้ำ
_WARP_EVENT = {"warp_village": "village", "warp_dungeon": "dungeon", "scan_box": "treasure"}
_SUMMONS = {"mini_summon", "main_summon", "unbeatable_summon"}
# อุปกรณ์ระดับตำนาน 2 ชิ้น (สเปคระบุเฉพาะ 2 ตัวนี้)
_LEGENDARY_EQUIP = {"Legen_Weapon": "item_legend_weapon", "Magic_Bag": "item_magic_bag"}


def _file(stem):
    p = ASSETS_DIR / f"{stem}.png"
    if p.is_file():
        return discord.File(str(p), filename=f"{stem}.png")
    return None


def monster_slug(name):
    """'🐉 มังกรน้ำแข็ง (Ice Dragon)' → 'ice_dragon' — ไม่มีวงเล็บอังกฤษ → None"""
    m = re.search(r"\(([A-Za-z0-9' \-]+)\)", name or "")
    if not m:
        return None
    return re.sub(r"[^a-z0-9]+", "_", m.group(1).lower()).strip("_")


def event_image(key, continent=None):
    """ภาพอีเวนต์ — ลองภาพเฉพาะทวีปก่อน แล้ว fallback ภาพกลาง"""
    if continent:
        f = _file(f"{continent}_{key}")
        if f:
            return f
    return _file(key)


def monster_image(name, rank=None):
    """ภาพมอนรายตัว — ไม่มีภาพเฉพาะตัว → fallback ภาพแรงค์ → None"""
    slug = monster_slug(name)
    if slug:
        f = _file(f"monster_{slug}")
        if f:
            return f
    if rank:
        # ชื่อแรงค์ใน MONSTER_RANKS มีวงเล็บอังกฤษ (Common/Mini-Boss/...) — slug ตรงกันเสมอ
        f = _file(f"monster_{re.sub(r'[^a-z0-9]+', '_', rank.lower()).strip('_')}")
        if f:
            return f
    return None


def item_use_image(item_info, continent=None):
    """ภาพตอนใช้/สวมไอเทมพิเศษสำเร็จ — effect นอกลิสต์คืน None (ยาทั่วไปไม่มีภาพ)"""
    eff = (item_info or {}).get("effect")
    val = (item_info or {}).get("effect_value")
    if eff == "wedding_ring":
        return _file("item_wedding_ring")
    if eff == "dye_profile":
        return _file("item_dye_profile")
    if eff == "revive":
        return _file("respawn")
    if eff == "equip_artifact" and val:
        return _file(f"item_{val}")
    if eff == "apply_status" and val in _WALK_STATUS_ITEMS:
        return _file(f"item_{val}")
    if eff == "set_state":
        if val in _SUMMONS:
            return _file(val)
        if val in _WARP_EVENT:
            return event_image(_WARP_EVENT[val], continent)
        return None
    if item_info.get("equip_key") in _LEGENDARY_EQUIP:
        return _file(_LEGENDARY_EQUIP[item_info["equip_key"]])
    return None


def file_kwargs(f):
    """แปลง File|None → kwargs สำหรับ send/followup — ไม่มีภาพ = ไม่ส่ง kwarg"""
    return {"file": f} if f else {}
```

- [ ] **Step 4: รันเทสให้ผ่าน** — `python -m pytest tests/test_event_images.py -q` คาดหวัง: ผ่านทุกข้อ
- [ ] **Step 5: Commit** — `git add bot/event_images.py tests/test_event_images.py && git commit -m "feat: โมดูลภาพอีเวนต์ event_images (หาไฟล์+fallback ครบ ยังไม่มีภาพจริง)"`

---

### Task 2: สคริปต์เจนภาพ `scripts/gen_event_images.py`

**Files:**
- Create: `scripts/gen_event_images.py`
- Modify: `tests/test_event_images.py` (เพิ่มเทส build_prompts)

**Interfaces:**
- Consumes: `bot.event_images.monster_slug`, `bot.game_data.CONTINENTS/WEEKLY_THEMES`, `config.example.json`
- Produces: `build_prompts() -> dict[str, str]` (stem → prompt อังกฤษ) และ CLI: `python scripts/gen_event_images.py [--only PREFIX] [--seed N] [--list]`

- [ ] **Step 1: เขียนเทสก่อน (เพิ่มท้าย tests/test_event_images.py)**

```python
def test_build_prompts_covers_everything():
    """ตาราง prompt ต้องครอบคลุมคีย์ภาพทุกใบที่เกมใช้ — กันเพิ่มทวีป/มอน/ธีมแล้วลืมเจนภาพ"""
    import importlib.util, pathlib
    spec = importlib.util.spec_from_file_location(
        "gen_event_images", pathlib.Path("scripts/gen_event_images.py"))
    gen = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(gen)
    prompts = gen.build_prompts()

    from bot.game_data import CONTINENTS, WEEKLY_THEMES
    from bot.views.game_views import MONSTER_RANKS
    events = ["monster", "village", "treasure", "dungeon", "npc", "trap", "calm"]
    for c in CONTINENTS:
        for e in events:
            assert f"{c}_{e}" in prompts
        assert f"arrival_{c}" in prompts
    for t in WEEKLY_THEMES:
        assert f"theme_{t['key']}" in prompts
    for r in MONSTER_RANKS.values():
        assert f"monster_{ei.monster_slug(r['name'])}" in prompts
    pools = [c["mods"].get("monster_pool", {}) for c in CONTINENTS.values()]
    pools += [t.get("mods", {}).get("monster_pool", {}) for t in WEEKLY_THEMES]
    for pool in pools:
        for names in pool.values():
            for n in names:
                assert f"monster_{ei.monster_slug(n)}" in prompts, n
    for k in ("mini_summon", "main_summon", "unbeatable_summon", "death", "respawn",
              "vehicle_airship", "vehicle_ship", "vehicle_portal", "vehicle_caravan",
              "item_wedding_ring", "item_dye_profile", "item_convoy_compass",
              "item_monster_lure", "item_monster_ward", "item_monster_trap",
              "item_legend_weapon", "item_magic_bag",
              "blizzard_ambush", "ancestral_feast", "volcanic_eruption", "poison_thicket",
              "emp_field", "ancient_excavation", "falling_island", "goddess_gamble",
              "black_market_dealer", "zombie_parasite"):
        assert k in prompts
    import json
    items = json.loads(pathlib.Path("config.example.json").read_text(encoding="utf-8"))
    arts = [v["effect_value"] for v in _iter_items(items) if v.get("effect") == "equip_artifact"]
    assert len(arts) >= 10
    for a in arts:
        assert f"item_{a}" in prompts
    for p in prompts.values():   # ทุก prompt ลงท้ายสไตล์เดียวกัน
        assert p.endswith(gen.STYLE)


def _iter_items(cfg):
    """หา dict ไอเทม (ตาราง id→item ที่มี 'name') ใน config — โครงสร้างซ้อนตรงไหนก็เจอ"""
    if isinstance(cfg, dict):
        if all(isinstance(v, dict) and "name" in v for v in cfg.values()) and cfg:
            yield from cfg.values()
        else:
            for v in cfg.values():
                yield from _iter_items(v)
```

- [ ] **Step 2: รันเทสให้ fail** — `python -m pytest tests/test_event_images.py::test_build_prompts_covers_everything -q` คาดหวัง: FAIL (ไม่มีไฟล์สคริปต์)

- [ ] **Step 3: เขียนสคริปต์**

โครงหลัก (เขียนเต็มตามนี้ — ตาราง scene ภาษาอังกฤษเขียนจากเนื้อเรื่อง/intro ภาษาไทยของแต่ละเหตุการณ์ใน `bot/game_data.py` และชื่อไอเทมใน `config.example.json`):

```python
# scripts/gen_event_images.py
"""เจนภาพพิกเซลอาร์ตประกอบเหตุการณ์จาก Pollinations.ai → assets/events/*.png

รันมือจาก root repo:  python scripts/gen_event_images.py [--only PREFIX] [--seed N] [--list]
- ข้ามไฟล์ที่มีอยู่แล้ว — ภาพไหนไม่สวย ลบไฟล์แล้วรันใหม่ (เปลี่ยน --seed ให้ได้ภาพใหม่)
- ต้องต่อเน็ต; บอทไม่เรียกไฟล์นี้ตอนรัน
"""
import argparse
import io
import json
import re
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from bot.event_images import ASSETS_DIR, monster_slug          # noqa: E402
from bot.game_data import CONTINENTS, WEEKLY_THEMES            # noqa: E402

STYLE = "pixel art, 16-bit retro fantasy game style, vibrant colors"
URL = "https://image.pollinations.ai/prompt/{prompt}?width=512&height=512&nologo=true&seed={seed}"

# บรรยากาศประจำทวีป (จาก arrival_text/ธีมทวีปใน game_data)
CONTINENT_FLAVOR = {
    "main":       "medieval fantasy kingdom, green plains and castle town",
    "demon":      "demon realm, blood-red sky, dark ominous land",
    "frozen":     "frozen tundra, snowstorm, ice cliffs",
    "nether":     "haunted netherworld, purple mist, wandering spirits",
    "volcanic":   "volcanic wasteland, lava rivers, ash rain",
    "sylvan":     "deep enchanted living forest, giant mossy trees",
    "mechanized": "ancient steampunk clockwork city, gears and steam",
    "skyward":    "floating sky islands above the clouds, bright sunlight",
    "ocean":      "tropical pirate ocean, coral coast, treasure seas",
}
# ฉากของอีเวนต์เดินแต่ละแบบ (ผสมกับ flavor ทวีป)
EVENT_SCENE = {
    "monster":  "huge mysterious monster shadow with glowing eyes lurking on the path",
    "village":  "cozy small fantasy village with warm lights and villagers",
    "treasure": "ancient ornate treasure chest with glowing runes",
    "dungeon":  "dark dungeon cave entrance with stone steps leading underground",
    "npc":      "old hooded traveler sitting by a campfire at night",
    "trap":     "hidden rope trap and spikes triggered on a forest path",
    "calm":     "peaceful scenic empty road, calm atmosphere, no danger",
}
ARRIVAL_SCENE = "wide beautiful landscape vista of {flavor}, adventurer arriving"

VEHICLES = {
    "airship": "fantasy merchant airship with balloons flying through clouds",
    "ship":    "wooden sailing ship crossing a stormy sea",
    "portal":  "mysterious glowing magic portal gate in ancient ruins",
    "caravan": "horse-drawn traveler caravan wagons on a long road",
}
SPECIALS = {
    "blizzard_ambush":     "giant shadow approaching through a heavy blizzard whiteout",
    "ancestral_feast":     "hundreds of candles and friendly ancestor spirits feast at night",
    "volcanic_eruption":   "volcano erupting, burning rocks raining from the sky",
    "poison_thicket":      "dense thorn thicket dripping with purple poison sap",
    "emp_field":           "crackling blue electric energy field over scrap metal",
    "ancient_excavation":  "ancient excavation site with half-buried golden relics",
    "falling_island":      "floating island crumbling and falling from the sky",
    "goddess_gamble":      "playful goddess at a floating dice gambling table in the sky",
    "black_market_dealer": "shady hooded dealer opening coat full of glowing wares in an alley",
    "zombie_parasite":     "zombie horde with glowing parasite spores in a ruined street",
}
THEMES = {
    "normal":        "peaceful sunny fantasy kingdom, doves and calm sky",
    "faction_war":   "epic war between human knights and demon army, battle banners",
    "palette":       "colorful rainbow slimes and monsters in many bright colors",
    "royal_convoy":  "crashed royal treasure convoy, gold coins scattered on the road",
    "dragon_nesting":"dragons nesting on mountain peaks with glowing eggs",
    "solar_eclipse": "ominous solar eclipse darkening a fantasy land",
    "mana_meteor":   "glowing blue mana meteors falling from the night sky",
    "absolute_zero": "entire land flash-frozen in deep blue ice",
    "blood_moon":    "huge red blood moon over howling wolves",
    "goddess_dice":  "giant glowing dice floating in the sky over a fantasy land",
    "masquerade":    "mysterious masquerade ball with masked figures",
    "black_market":  "night black market bazaar with shady hooded merchants",
    "zombie":        "zombie apocalypse outbreak in a fantasy town, green haze",
}
ITEMS = {
    "item_wedding_ring":   "fantasy wedding ceremony, two adventurers exchanging golden rings, confetti",
    "item_dye_profile":    "magic paint bucket splashing rainbow colors on an adventurer",
    "item_convoy_compass": "ornate golden royal compass glowing and pointing the way",
    "item_monster_lure":   "raw meat bait on the ground with scent trails and monster eyes in the dark",
    "item_monster_ward":   "sacred incense sticks with holy smoke keeping monster shadows away",
    "item_monster_trap":   "big iron monster trap being set on a forest path",
    "item_legend_weapon":  "legendary glowing sword on a stone altar with light rays",
    "item_magic_bag":      "magical dimensional bag with galaxy portal opening inside",
}
EXTRAS = {
    "mini_summon":       "summoning scroll glowing, dark ritual circle calling a mini boss",
    "main_summon":       "large summoning ritual circle with lightning calling a mighty boss",
    "unbeatable_summon": "forbidden summoning ritual, colossal terrifying silhouette appearing",
    "death":             "adventurer ghost spirit floating over their fallen body, gray world",
    "respawn":           "warm holy light beam reviving an adventurer, sparkles of life",
}


def _artifact_items():
    cfg = json.loads((ROOT / "config.example.json").read_text(encoding="utf-8"))
    found = {}
    def walk(node):
        if isinstance(node, dict):
            for v in node.values():
                if isinstance(v, dict) and v.get("effect") == "equip_artifact" and v.get("effect_value"):
                    found[v["effect_value"]] = v.get("name", v["effect_value"])
                else:
                    walk(v)
    walk(cfg)
    return found


def _monster_names():
    names = {}
    pools = [c["mods"].get("monster_pool", {}) for c in CONTINENTS.values()]
    pools += [t.get("mods", {}).get("monster_pool", {}) for t in WEEKLY_THEMES]
    for pool in pools:
        for lst in pool.values():
            for n in lst:
                names[n] = True
    # แรงค์พื้นฐาน — hardcode กัน import discord (game_views) ในสคริปต์
    for n in ("มอนสเตอร์ทั่วไป (Common)", "มินิบอส (Mini-Boss)", "บอสหลัก (Main-Boss)",
              "มอนลับ (Secret)", "บอสไร้พ่าย (Unbeatable)"):
        names[n] = True
    return list(names)


def build_prompts():
    prompts = {}
    for c, flavor in CONTINENT_FLAVOR.items():
        for e, scene in EVENT_SCENE.items():
            prompts[f"{c}_{e}"] = f"{scene}, in {flavor}, {STYLE}"
        prompts[f"arrival_{c}"] = f"{ARRIVAL_SCENE.format(flavor=flavor)}, {STYLE}"
    for k, scene in {**VEHICLES}.items():
        prompts[f"vehicle_{k}"] = f"{scene}, {STYLE}"
    for table, prefix in ((SPECIALS, ""), (THEMES, "theme_"), (ITEMS, ""), (EXTRAS, "")):
        for k, scene in table.items():
            prompts[f"{prefix}{k}"] = f"{scene}, {STYLE}"
    for name in _monster_names():
        slug = monster_slug(name)
        if not slug:
            print(f"⚠️ ข้ามมอนไม่มีชื่ออังกฤษ: {name}")
            continue
        eng = slug.replace("_", " ")
        prompts[f"monster_{slug}"] = (
            f"fantasy RPG monster portrait of a {eng}, full body, battle pose, {STYLE}")
    for art_key, thai_name in _artifact_items().items():
        eng = art_key.removeprefix("art_").replace("_", " ")
        prompts[f"item_{art_key}"] = (
            f"legendary magical artifact {eng} on display pedestal, glowing aura, {STYLE}")
    return prompts


def generate(stem, prompt, seed):
    from PIL import Image
    url = URL.format(prompt=urllib.parse.quote(prompt), seed=seed)
    data = urllib.request.urlopen(url, timeout=120).read()
    img = Image.open(io.BytesIO(data)).convert("RGB")
    if img.size != (512, 512):
        img = img.resize((512, 512))
    img = img.quantize(colors=256)   # PNG 256 สี — พิกเซลอาร์ตแทบไม่เสีย ขนาดตก ~20-60KB
    out = ASSETS_DIR / f"{stem}.png"
    img.save(out, optimize=True)
    return out.stat().st_size


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", default="", help="เจนเฉพาะ stem ที่ขึ้นต้นด้วยคำนี้ (คั่นหลายคำด้วย ,)")
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--list", action="store_true", help="แค่โชว์รายชื่อ+จำนวน ไม่เจน")
    args = ap.parse_args()
    ASSETS_DIR.mkdir(parents=True, exist_ok=True)
    prompts = build_prompts()
    prefixes = [p for p in args.only.split(",") if p]
    todo = {k: v for k, v in sorted(prompts.items())
            if (not prefixes or any(k.startswith(p) for p in prefixes))
            and not (ASSETS_DIR / f"{k}.png").exists()}
    print(f"ทั้งหมด {len(prompts)} ภาพ | ยังไม่มีไฟล์ {len(todo)} ภาพ")
    if args.list:
        for k in todo:
            print(" -", k)
        return
    for i, (stem, prompt) in enumerate(todo.items(), 1):
        for attempt in (1, 2, 3):
            try:
                size = generate(stem, prompt, args.seed)
                print(f"[{i}/{len(todo)}] ✅ {stem}.png ({size//1024}KB)")
                break
            except Exception as e:                       # ponytail: retry 3 ครั้งพอ — รันซ้ำได้เพราะข้ามไฟล์ที่มีแล้ว
                print(f"[{i}/{len(todo)}] ⚠️ {stem} ครั้งที่ {attempt}: {e}")
                time.sleep(5 * attempt)
        time.sleep(1)   # ถนอมบริการฟรี


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: รันเทสให้ผ่าน** — `python -m pytest tests/test_event_images.py -q` คาดหวัง: ผ่านทุกข้อ (รวม coverage)
- [ ] **Step 5: ลองรัน `python scripts/gen_event_images.py --list`** — คาดหวัง: โชว์ ~172 รายการ ไม่ error
- [ ] **Step 6: Commit** — `git add scripts/gen_event_images.py tests/test_event_images.py && git commit -m "feat: สคริปต์เจนภาพอีเวนต์ (enumerate จากข้อมูลเกมอัตโนมัติ)"`

---

### Task 3: เจนชุดตัวอย่างให้ผู้ใช้คัดสไตล์ 🚧 USER GATE

- [ ] **Step 1: เจนชุดตัวแทน 12 ภาพ**

```bash
python scripts/gen_event_images.py --only main_village,main_monster,frozen_treasure,demon_trap,sylvan_calm,arrival_ocean,vehicle_airship,theme_blood_moon,monster_ice_dragon,monster_common,item_wedding_ring,death
```

- [ ] **Step 2: เปิดภาพให้ผู้ใช้ดู (Read ทีละไฟล์ใน `assets/events/`) แล้วถามว่าสไตล์ผ่านไหม**
- [ ] **Step 3: ถ้าไม่ผ่าน — ปรับ STYLE/scene ตามฟีดแบ็ก ลบไฟล์ เจนใหม่ วนจนผู้ใช้พอใจ**
- [ ] **Step 4: Commit ภาพชุดแรก** — `git add assets/events && git commit -m "assets: ภาพอีเวนต์ชุดตัวอย่าง (ผู้ใช้คัดสไตล์ผ่านแล้ว)"`

### Task 4: เจนครบทุกภาพ + ผู้ใช้คัด 🚧 USER GATE

- [ ] **Step 1: เจนที่เหลือทั้งหมด** — `python scripts/gen_event_images.py` (~30-45 นาที — รัน background แจ้งความคืบหน้า; ล่มตรงไหนรันซ้ำได้ ข้ามของที่มีแล้ว)
- [ ] **Step 2: เช็คขนาดไฟล์** — PowerShell: `Get-ChildItem assets/events | Sort Length -desc | Select -First 5 Name,Length` คาดหวัง: ทุกไฟล์ < ~150KB
- [ ] **Step 3: ให้ผู้ใช้ไล่ดูภาพ (แนะนำเปิดโฟลเดอร์ใน Explorer) — ใบไหนไม่ผ่าน ลบไฟล์ แล้วรัน `python scripts/gen_event_images.py --seed <เลขใหม่>` เจนเฉพาะที่หายไป วนจนพอใจ**
- [ ] **Step 4: Commit** — `git add assets/events && git commit -m "assets: ภาพอีเวนต์ครบชุด ~172 ภาพ (คัดแล้ว)"`

### Task 5: เทสความครบ + เช็ค packaging

**Files:** Modify: `tests/test_event_images.py`, ตรวจ `make_installer_zip.py` / `build_nuitka.py`

- [ ] **Step 1: เพิ่มเทสไฟล์ภาพครบ (ตอนนี้ภาพมีจริงแล้ว — เทสนี้ล็อกไม่ให้หาย)**

```python
def test_all_images_exist_on_disk():
    """ทุกคีย์ใน build_prompts ต้องมีไฟล์จริง — กันลืมเจน/ลืม commit/เผลอลบ"""
    import importlib.util, pathlib
    spec = importlib.util.spec_from_file_location(
        "gen_event_images", pathlib.Path("scripts/gen_event_images.py"))
    gen = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(gen)
    missing = [k for k in gen.build_prompts() if not (ei.ASSETS_DIR / f"{k}.png").is_file()]
    assert not missing, f"ภาพหาย {len(missing)} ใบ: {missing[:10]}"
```

- [ ] **Step 2: รันเทสให้ผ่าน** — `python -m pytest tests/test_event_images.py -q`
- [ ] **Step 3: ตรวจว่าตัวแพ็ค (make_installer_zip.py / build_nuitka.py) รวมโฟลเดอร์ `assets/` ไปด้วย — ถ้าไม่รวม เพิ่มเข้าไป (ไม่งั้นเครื่องลูกค้าไม่มีภาพ)**
- [ ] **Step 4: Commit** — `git commit -am "test: ล็อกภาพอีเวนต์ครบชุด + แพ็ค assets ลง installer"`

---

### Task 6: แนบภาพใน walk_step (อีเวนต์เดิน + special + summon)

**Files:** Modify: `bot/views/game_views.py` (walk_step ~2829-2935)

**Interfaces (Consumes):** `event_image(key, continent)`, `file_kwargs(f)` จาก `bot.event_images`

ก่อนเริ่ม: `git tag pre-event-images`

- [ ] **Step 1: import ใน game_views.py** — `from bot.event_images import event_image, monster_image, item_use_image, file_kwargs` (บนสุดไฟล์ ใกล้ import อื่นของ bot)
- [ ] **Step 2: หา continent ปัจจุบันใน walk_step** — ใน walk_step มี `mods` จาก game_modifiers อยู่แล้ว; ใช้ `cur_continent = player.get("continent", "main")` (ดูชื่อ field จริงจาก player_model — grep `"continent"` ใน bot/models/player_model.py ก่อน ถ้าชื่ออื่นใช้ตามนั้น)
- [ ] **Step 3: แก้ทีละ branch — pattern เดียวกันทุกจุด** ตัวอย่าง branch village (บรรทัด ~2853):

```python
sent_msg = await interaction.followup.send(
    content=f"🏡 คุณเดินทางมาพบ **'หมู่บ้านอุ่นใจ'** เลือกแอคชั่นของคุณ:{cleanse_note}",
    view=next_view, wait=True,
    **file_kwargs(event_image("village", cur_continent)))
```

ทำเหมือนกันกับ: `monster` (คีย์ `"monster"` — **ยกเว้น** ถ้า `last_evt in summon_events` ให้ใช้ `event_image(last_evt)` ภาพบอส), `treasure`, `npc`, `dungeon`, `trap`, `calm` (แนบเฉพาะข้อความสุดท้าย ไม่แนบระหว่างเดินรวด), และ branch `special` ใช้ `event_image(special_event["key"])` ทุกจุดที่ `followup.send` ของ special (รวม instant/dice/choice — ดูทุก send ใน branch)
- [ ] **Step 4: รันเทสเดิมทั้งชุด** — `python -m pytest tests/ -q` คาดหวัง: ผ่านเท่าเดิม (เทสเดินเกมเดิมต้องไม่พัง — mock followup.send รับ **kwargs อยู่แล้ว; ถ้าเทสไหน mock แบบเข้มงวดค่อยแก้เทสนั้นให้รับ file)
- [ ] **Step 5: Commit** — `git commit -am "feat: แนบภาพอีเวนต์เดิน+special+summon ใน walk_step"`

---

### Task 7: ภาพมอนในไฟต์ (เทิร์นแรก) — fight embed

**Files:** Modify: `bot/views/fight_ui.py` (`build_fight_embed` ~21), `bot/views/game_views.py` (จุดส่ง fight embed ครั้งแรก)

- [ ] **Step 1: อ่าน `build_fight_embed` + หาจุดที่ fight embed ถูกส่งครั้งแรก** (turn 1 — grep `build_fight_embed(` ใน game_views.py)
- [ ] **Step 2: ใน build_fight_embed เพิ่ม thumbnail เมื่อ turn แรก:**

```python
if turn == 1:
    embed.set_thumbnail(url="attachment://monster.png")
```

- [ ] **Step 3: ที่จุดส่ง embed เทิร์นแรก แนบไฟล์:** (ELEMENT_COLORS มีอยู่แล้ว — สีธาตุไม่ต้องทำเพิ่ม)

```python
f = monster_image(view.m_stats.get("name", ""), getattr(view, "monster_rank", None))
if f:
    f.filename = "monster.png"          # ให้ตรง attachment:// เสมอ ไม่ว่ามอนไหน
# ส่งด้วย **file_kwargs(f) — ถ้าเป็น edit ใช้ attachments=[f] แทน (ดู API ของจุดนั้น)
```

หมายเหตุ: ถ้าจุดแรกเป็น `interaction.response.edit_message` ให้ใช้ `attachments=[f]` (ว่าง = ไม่ใส่ param); เทิร์นถัดไป**ห้าม**ส่ง attachments ใหม่ (ปล่อยของเดิมค้าง — thumbnail ยังแสดง)
- [ ] **Step 4: รันเทส** — `python -m pytest tests/test_fight_embed.py tests/ -q` คาดหวัง: ผ่าน (test_fight_embed อาจต้องเพิ่ม assert thumbnail เทิร์น 1 — เพิ่มเทสใหม่ 1 ตัว: build embed turn=1 → `embed.thumbnail.url == "attachment://monster.png"`, turn=2 → ไม่มี)
- [ ] **Step 5: Commit** — `git commit -am "feat: ภาพมอนรายตัวในไฟต์ (เทิร์นแรก ไม่อัปโหลดซ้ำ)"`

---

### Task 8: ภาพยานพาหนะ + มาถึงทวีป

**Files:** Modify: `bot/views/game_views.py` (~2534-2600 travel encounter + arrival), `bot/cogs/player_commands.py` (~354 arrival)

- [ ] **Step 1: จุดเจอยานพาหนะ** (view ที่รับ `encounter` ~2546 — หา send ของข้อความชวนขึ้นยาน): แนบ `**file_kwargs(event_image(f"vehicle_{self.encounter['vehicle']}"))`
- [ ] **Step 2: จุด arrival 2 ที่** (game_views ~2597 เป็น embed → `embed.set_image(url=f"attachment://arrival_{dest}.png")` + แนบไฟล์; player_commands ~354 เป็นข้อความ → `**file_kwargs(event_image(f"arrival_{dest}"))` — ดูตัวแปรชื่อทวีปปลายทางจริงในแต่ละจุด)
- [ ] **Step 3: รันเทส** — `python -m pytest tests/ -q`
- [ ] **Step 4: Commit** — `git commit -am "feat: ภาพยานพาหนะ+มาถึงทวีป"`

---

### Task 9: ภาพประกาศธีมสัปดาห์

**Files:** Modify: `bot/cogs/weekly_event.py` (`build_announce_embed` ~86 + จุด `channel.send(embed=...)` ~125)

- [ ] **Step 1: ใน build_announce_embed:** `embed.set_image(url=f"attachment://theme_{theme['key']}.png")` เฉพาะเมื่อไฟล์มี (เช็คผ่าน `event_image(f"theme_{theme['key']}")` ก่อน)
- [ ] **Step 2: จุดส่ง:** `await channel.send(embed=build_announce_embed(theme), **file_kwargs(event_image(f"theme_{theme['key']}")))`
   ระวัง: ต้องสร้าง File คนละ object กับที่เช็คใน embed (สร้างใหม่ตอน send)
- [ ] **Step 3: รันเทส** — `python -m pytest tests/test_weekly_event.py tests/ -q`
- [ ] **Step 4: Commit** — `git commit -am "feat: ภาพธีมในประกาศธีมสัปดาห์"`

---

### Task 10: ภาพใช้ไอเทมพิเศษ + แต่งงาน + ตาย/เกิดใหม่

**Files:** Modify: `bot/cogs/player_commands.py` (!use ~1391 + จุดส่งผล marry), `bot/views/menu_view.py` (~558 ปุ่มใช้ของ), `bot/views/game_views.py` (RespawnView ~2117-2136 + จุดส่ง RespawnView ทุกจุด), `bot/views/fight_ui.py` (embed ฟื้นคืนสติ ~69)

- [ ] **Step 1: จุดใช้ไอเทม 2 call site** (`use_item` คืน `(success, msg)` — ไม่แก้ signature): หลัง success ที่ผู้เรียกส่ง msg ให้เพิ่ม

```python
item_info = config_loader.get_item_config(item_id)   # หรือ ITEM_CONFIG ตามที่ไฟล์นั้นใช้อยู่
img = item_use_image(item_info, player.get("continent", "main")) if success else None
await ctx.send(msg, **file_kwargs(img))              # รูปแบบตาม call site จริง
```

- [ ] **Step 2: แต่งงานสำเร็จ** — grep `partner.marry(` หาจุดที่ส่งข้อความ "เป็นคู่หูกันแล้ว" (partner.py:126 เป็นคนสร้างข้อความ ผู้ส่งอยู่ cog/view) → แนบ `event_image("item_wedding_ring")`
- [ ] **Step 3: ตาย** — ทุกจุดที่ส่ง/แก้ข้อความพร้อม `RespawnView(...)` (grep `RespawnView(` ใน game_views.py ~7 จุด + DeathRespawnView): จุดที่เป็น `followup.send` เพิ่ม `**file_kwargs(event_image("death"))`; จุดที่เป็น `edit_message` เพิ่ม `attachments=[f]` เมื่อ f ไม่ None (สร้างตัวแปรก่อน)
- [ ] **Step 4: เกิดใหม่** — `RespawnView.respawn` (~2129) + embed ปาฏิหาริย์ fight_ui (~69): แนบ `event_image("respawn")` (embed → `set_image(url="attachment://respawn.png")` + แนบไฟล์)
- [ ] **Step 5: รันเทสทั้งชุด** — `python -m pytest tests/ -q` คาดหวัง: ผ่านหมด
- [ ] **Step 6: Commit** — `git commit -am "feat: ภาพใช้ไอเทมพิเศษ/แต่งงาน/ตาย/เกิดใหม่"`

---

### Task 11: ปิดงาน — เทสรวม + checklist เทสจริง

- [ ] **Step 1: รันเทสทั้งโปรเจ็ค** — `python -m pytest tests/ -q` ต้องเขียวหมด
- [ ] **Step 2: เพิ่มหัวข้อเทสจริงใน `docs/live-test-checklist.md`** — รายการ: เดินเจอครบ 7 อีเวนต์เห็นภาพตรงทวีป, สู้มอนเห็นภาพมอนเทิร์นแรกเทิร์นสองไม่อัปซ้ำ, ใช้ใบเชิญบอส/กับดัก/เข็มทิศเห็นภาพ, ตาย-เกิดใหม่เห็นภาพ, เปลี่ยนทวีปเห็นภาพยาน+ภาพทวีป, ประกาศธีมจันทร์เห็นภาพ, แต่งงานเห็นภาพ, **เน็ตช้า: ภาพไม่ทำให้ปุ่มหน่วงเกินรับได้**
- [ ] **Step 3: Commit สุดท้าย** — `git commit -am "docs: checklist เทสจริงภาพอีเวนต์"`

---

## Self-Review Notes

- Spec coverage: เดิน 63 ✓(T3-4,6) มอน ✓(T7) ยาน+ทวีป ✓(T8) ธีม ✓(T9) ไอเทม+ใบวาป(ใช้ภาพซ้ำใน item_use_image)+แต่งงาน+ตาย/เกิด ✓(T10) ขนาดไฟล์ ✓(T2 quantize + T4 เช็ค) fallback ✓(T1) ครบไฟล์ ✓(T5)
- จุดเสี่ยงที่ executor ต้องดูของจริง: ชื่อ field ทวีปใน player (T6), รูปแบบ send/edit แต่ละจุด (T7,T10) — แผนสั่ง grep ก่อนแก้แล้ว
- Faction war champion / world boss ไม่มีภาพเฉพาะ → fallback ภาพแรงค์ (ตามสเปค — ไม่บล็อก)
