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
