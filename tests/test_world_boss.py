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
