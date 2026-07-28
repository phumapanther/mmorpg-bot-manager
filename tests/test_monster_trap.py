"""🪤 กับดักมอนสเตอร์ — ก้าวถัดไปเจอมอนแน่นอน + มอนหนีไม่ได้ (โดยเฉพาะธาตุแสง)"""
import json
import pathlib

from bot import config_loader
from bot import game_modifiers as gm

SRC = pathlib.Path("bot/views/game_views.py").read_text(encoding="utf-8")


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
    block = SRC[SRC.index("# [Priority 5: สุ่มปกติ]"):SRC.index("summon_events = ")]
    trap_at = block.index("status_forced_event")
    for other in ("roll_travel_chance", "roll_special_event", "roll_calm_chance", "random.choices"):
        assert trap_at < block.index(other), f"กับดักต้องถูกเช็คก่อน {other}"
    assert "if forced_event:" in block and "elif game_modifiers.roll_travel_chance" in block


def test_light_monsters_cannot_escape_a_trap():
    block = SRC[SRC.index("monster_flee = self.element_data.get"):]
    guard = block[:block.index("if monster_flee and")]
    assert 'has_status_flag(self.statuses, "block_monster_flee")' in guard
    assert "monster_flee = 0" in guard
    # ธาตุแสงต้องหนีได้จริงตอนไม่มีกับดัก ไม่งั้นเทสนี้ไม่มีความหมาย
    assert gm.ELEMENTS["light"]["monster_flee_chance"] > 0


def test_trap_is_consumed_only_on_a_win():
    assert 'if "monster_trap" in self.statuses:' in SRC
    assert 'self.statuses.pop("monster_trap", None)' in SRC
    win_block = SRC[SRC.index("db_updates[\"cash\"] = player.get") - 3000:SRC.index("db_updates[\"cash\"] = player.get")]
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
