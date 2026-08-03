# scripts/gen_event_images.py
"""เจนภาพพิกเซลอาร์ตประกอบเหตุการณ์จาก Pollinations.ai → assets/events/*.png

รันมือจาก root repo:  python scripts/gen_event_images.py [--only PREFIX] [--seed N] [--list]
- ข้ามไฟล์ที่มีอยู่แล้ว — ภาพไหนไม่สวย ลบไฟล์แล้วรันใหม่ (เปลี่ยน --seed ให้ได้ภาพใหม่)
- ต้องต่อเน็ต; บอทไม่เรียกไฟล์นี้ตอนรัน
"""
import argparse
import io
import json
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
PIXEL_GRID = 128   # บังคับเม็ดพิกเซลจริง: ย่อเหลือกริดนี้แล้วขยายกลับแบบ NEAREST (เลขน้อย = เม็ดหยาบขึ้น)
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
    "normal":         "peaceful sunny fantasy kingdom, doves and calm sky",
    "faction_war":    "epic war between human knights and demon army, battle banners",
    "palette":        "colorful rainbow slimes and monsters in many bright colors",
    "royal_convoy":   "crashed royal treasure convoy, gold coins scattered on the road",
    "dragon_nesting": "dragons nesting on mountain peaks with glowing eggs",
    "solar_eclipse":  "ominous solar eclipse darkening a fantasy land",
    "mana_meteor":    "glowing blue mana meteors falling from the night sky",
    "absolute_zero":  "entire land flash-frozen in deep blue ice",
    "blood_moon":     "huge red blood moon over howling wolves",
    "goddess_dice":   "giant glowing dice floating in the sky over a fantasy land",
    "masquerade":     "mysterious masquerade ball with masked figures",
    "black_market":   "night black market bazaar with shady hooded merchants",
    "zombie":         "zombie apocalypse outbreak in a fantasy town, green haze",
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
              "มอนสเตอร์ลับ (Secret)", "ไร้พ่าย (Unbeatable)"):
        names[n] = True
    return list(names)


def build_prompts():
    prompts = {}
    for c, flavor in CONTINENT_FLAVOR.items():
        for e, scene in EVENT_SCENE.items():
            prompts[f"{c}_{e}"] = f"{scene}, in {flavor}, {STYLE}"
        prompts[f"arrival_{c}"] = f"{ARRIVAL_SCENE.format(flavor=flavor)}, {STYLE}"
    for k, scene in VEHICLES.items():
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
    for art_key, _thai_name in _artifact_items().items():
        eng = art_key.removeprefix("art_").replace("_", " ")
        prompts[f"item_{art_key}"] = (
            f"legendary magical artifact {eng} on display pedestal, glowing aura, {STYLE}")
    return prompts


def generate(stem, prompt, seed):
    from PIL import Image
    url = URL.format(prompt=urllib.parse.quote(prompt), seed=seed)
    # Pollinations บล็อก UA ของ Python-urllib (403) — ต้องส่ง UA แบบเบราว์เซอร์
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"})
    data = urllib.request.urlopen(req, timeout=120).read()
    img = Image.open(io.BytesIO(data)).convert("RGB")
    # โมเดลชอบวาดเนียนเกิน — บังคับพิกเซลจริง: ย่อ→ขยาย NEAREST แล้วลดสี (ได้ลุคเรโทร + ไฟล์เล็ก)
    img = img.resize((PIXEL_GRID, PIXEL_GRID), Image.LANCZOS)
    img = img.resize((512, 512), Image.NEAREST)
    img = img.quantize(colors=128)
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
                print(f"[{i}/{len(todo)}] ✅ {stem}.png ({size // 1024}KB)", flush=True)
                break
            except Exception as e:   # ponytail: retry 3 ครั้งพอ — รันซ้ำได้เพราะข้ามไฟล์ที่มีแล้ว
                print(f"[{i}/{len(todo)}] ⚠️ {stem} ครั้งที่ {attempt}: {e}", flush=True)
                time.sleep(5 * attempt)
        time.sleep(1)   # ถนอมบริการฟรี


if __name__ == "__main__":
    main()
