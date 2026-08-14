"""🪤 กับดักมอนสเตอร์ — ก้าวถัดไปเจอมอนแน่นอน + มอนหนีไม่ได้ (โดยเฉพาะธาตุแสง)"""
import json
import pathlib

from bot import config_loader
from bot import game_modifiers as gm

SRC = pathlib.Path("bot/views/game_views.py").read_text(encoding="utf-8")
# ตรรกะเลือกเหตุการณ์ย้ายไป adventure_core แล้ว (เว็บเกม เฟส 5.1)
CORE = pathlib.Path("bot/adventure_core.py").read_text(encoding="utf-8")


def test_status_exists_with_the_right_flags():
    cfg = gm.STATUS_EFFECTS["monster_trap"]
    assert cfg["force_event"] == "monster"
    assert cfg["block_monster_flee"] is True
    assert cfg["no_tick"] is True, "ต้องไม่นับถอยหลังเอง ไม่งั้นหมดอายุก่อนเจอมอน"
    assert "monster_ward" in cfg["cleanse_on_apply"], "วางกับดักต้องล้างธูปไล่มอน"


def test_forced_event_lookup():
    assert gm.status_forced_event({"monster_trap": 1}) == ("monster", "monster_trap")
    assert gm.status_forced_event({"poison": 5}) == (None, None)
    assert gm.status_forced_event({}) == (None, None)


def test_trap_beats_travel_special_and_calm():
    """กับดักต้องตัดหน้าทุกอีเวนต์ในสาขาสุ่มปกติ ไม่งั้นวางแล้วยังเจออีเวนต์สงบ"""
    block = CORE[CORE.index("# [5] สุ่มปกติ"):]
    trap_at = block.index("status_forced_event")
    for other in ("roll_robbery", "roll_travel_chance", "roll_special_event",
                  "roll_calm_chance", "rng.choices"):
        assert trap_at < block.index(other), f"กับดักต้องถูกเช็คก่อน {other}"
    assert "if forced_event:" in block


def test_light_monsters_cannot_escape_a_trap():
    # การคำนวณเทิร์นย้ายไป adventure_core.fight_turn แล้ว (เว็บเกม เฟส 5.6)
    block = CORE[CORE.index('monster_flee = element_data.get'):]
    guard = block[:block.index("if monster_flee and")]
    assert 'has_status_flag(statuses, "block_monster_flee")' in guard
    assert "monster_flee = 0" in guard
    # ธาตุแสงต้องหนีได้จริงตอนไม่มีกับดัก ไม่งั้นเทสนี้ไม่มีความหมาย
    assert gm.ELEMENTS["light"]["monster_flee_chance"] > 0


def test_trap_is_consumed_only_on_a_win():
    assert 'if "monster_trap" in statuses:' in CORE
    assert 'statuses.pop("monster_trap", None)' in CORE
    win_block = CORE[CORE.index("db_updates[\"cash\"] = player.get") - 3000:CORE.index("db_updates[\"cash\"] = player.get")]
    assert "monster_trap" in win_block, "ต้องปลดกับดักในเส้นทางชนะเท่านั้น"


def test_item_is_in_the_shop():
    cfg = json.load(open("config.example.json", encoding="utf-8"))
    trap = next((i for i in cfg["item_catalog"]["items"].values()
                 if i.get("effect_value") == "monster_trap"), None)
    assert trap and trap["purchasable"] is True
    assert trap["effect"] == "apply_status"
    assert trap["buy"] > 0


def test_panel_can_edit_the_new_status():
    ov = json.load(open("config.example.json", encoding="utf-8"))["game_balance"]["status_overrides"]
    assert "monster_trap" in ov and ov["monster_trap"]["unit"] == "ก้าว"


def test_applying_trap_clears_the_ward():
    statuses = gm.apply_status({}, "monster_ward")
    statuses = gm.apply_status(statuses, "monster_trap")
    assert "monster_ward" not in statuses and "monster_trap" in statuses


def test_trap_survives_a_step_tick():
    """เดินหลายก้าวกว่าจะเจอมอน กับดักต้องยังอยู่"""
    statuses = gm.apply_status({}, "monster_trap")
    for _ in range(5):
        statuses, expired = gm.tick_statuses(statuses, "step")
        assert "monster_trap" in statuses and not expired


# ── เรทหนีตั้งใน Panel ได้ + ตารางคราฟในคู่มือ ──

def test_flee_rate_is_configurable_per_element(monkeypatch):
    from bot import config_loader
    monkeypatch.setattr(config_loader, "get_config",
                        lambda: {"game_balance": {"element_flee_chance": {"light": 0, "dark": 75}}})
    assert gm.element_flee_chance("light") == 0, "ตั้ง 0 = ธาตุแสงเลิกหนี"
    assert gm.element_flee_chance("dark") == 75, "เปิดให้ธาตุอื่นหนีได้"
    assert gm.get_element_data({}, "dark")["monster_flee_chance"] == 75


def test_flee_rate_survives_bad_input(monkeypatch):
    from bot import config_loader
    for junk in ("มาก", None, 999, -5):
        monkeypatch.setattr(config_loader, "get_config",
                            lambda: {"game_balance": {"element_flee_chance": {"light": junk}}})
        v = gm.element_flee_chance("light")
        assert 0 <= v <= 100, f"ค่า {junk!r} ทำให้เรทหนีเพี้ยน ({v})"


def test_config_has_every_element():
    cfg = json.load(open("config.example.json", encoding="utf-8"))["game_balance"]["element_flee_chance"]
    assert set(cfg) == set(gm.ELEMENTS)
    assert cfg["light"] == 40, "ค่าเริ่มต้นต้องเท่าของเดิมในโค้ด"


def test_codex_shows_the_effective_flee_rate(monkeypatch):
    from bot import config_loader
    from bot.cogs.player_commands import build_codex_embed
    monkeypatch.setattr(config_loader, "get_config",
                        lambda: {"game_balance": {"element_flee_chance": {"light": 7}}})
    text = " ".join(f.value for f in build_codex_embed("ธาตุ").fields)
    assert "หนีเก่ง 7%" in text, "คู่มือต้องบอกเลขที่ตั้งใน Panel ไม่ใช่เลขในโค้ด"


def test_craft_codex_page_highlights_hunting_gear():
    from bot.cogs.player_commands import build_codex_embed
    from bot.views.menu_view import CODEX_TOPICS
    embed = build_codex_embed("คราฟ")
    assert ("🔨 ตารางคราฟของ", "คราฟ") in CODEX_TOPICS
    hunt = embed.fields[0]
    assert "สายล่ามอน" in hunt.name
    for needed in ("ใบเชิญบอสไร้พ่าย", "กับดักมอนสเตอร์"):
        assert needed in hunt.value, f"หน้าคราฟต้องชูของสำคัญ: {needed}"
    body = " ".join(f.value for f in embed.fields)
    recipes = json.load(open("config.example.json", encoding="utf-8"))["item_catalog"]["crafting_recipes"]
    assert len(body.split("`" )) - 1 >= len(recipes), "ต้องแสดงทุกสูตร ไม่ตกหล่น"


def test_trap_is_craftable():
    recipes = json.load(open("config.example.json", encoding="utf-8"))["item_catalog"]["crafting_recipes"]
    assert "66" in recipes and recipes["66"]["recipe"], "กับดักต้องคราฟได้ ไม่งั้นคู่มือโกหก"
