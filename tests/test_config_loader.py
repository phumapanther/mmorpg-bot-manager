import json
import pytest
from bot import config_loader

def _write(tmp_path, data):
    p = tmp_path / "config.json"
    p.write_text(json.dumps(data), encoding="utf-8")
    return p

@pytest.fixture(autouse=True)
def _isolate_example_path(tmp_path, monkeypatch):
    empty_example = tmp_path / "_autouse_example.json"
    empty_example.write_text("{}", encoding="utf-8")
    monkeypatch.setattr(config_loader, "EXAMPLE_PATH", str(empty_example))
    config_loader.reload_config()

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
    # Create temp example file for isolation (not the repo's real config.example.json)
    example = tmp_path / "config.example.json"
    example.write_text(json.dumps({"channels": {"bank": {"channel_id": 777}}}), encoding="utf-8")
    monkeypatch.setattr(config_loader, "EXAMPLE_PATH", str(example))
    config_loader.reload_config()
    assert config_loader.get_channel_id("bank") == 777  # fell back to example, not repo file

def test_get_channel_id_preserves_large_snowflake_string(tmp_path, monkeypatch):
    big_id = 1160575257892098109  # exceeds 2**53, would lose precision as a JS/JSON number
    cfg = {"channels": {"bank": {"label": "x", "channel_id": str(big_id)}}}
    monkeypatch.setattr(config_loader, "CONFIG_PATH", str(_write(tmp_path, cfg)))
    config_loader.reload_config()
    assert config_loader.get_channel_id("bank") == big_id

def test_get_role_ids_preserves_large_snowflake_strings(tmp_path, monkeypatch):
    big_ids = [1160575257892098109, 1510347144207401140]
    cfg = {"permission_groups": {"admin": {"role_ids": [str(x) for x in big_ids]}}}
    monkeypatch.setattr(config_loader, "CONFIG_PATH", str(_write(tmp_path, cfg)))
    config_loader.reload_config()
    assert config_loader.get_role_ids("admin") == big_ids

def test_get_trade_roles_preserves_large_snowflake_string(tmp_path, monkeypatch):
    big_id = 1160561278297837628
    cfg = {"auto_trade_roles": {"dark": [{"label": "x", "value": "x", "price": 1, "role_id": str(big_id), "emoji": ""}]}}
    monkeypatch.setattr(config_loader, "CONFIG_PATH", str(_write(tmp_path, cfg)))
    config_loader.reload_config()
    roles = config_loader.get_trade_roles("dark")
    assert roles[0]["role_id"] == big_id

def test_get_channel_mention_default_false(tmp_path, monkeypatch):
    cfg = {"channels": {"bank": {"channel_id": 1}}}
    monkeypatch.setattr(config_loader, "CONFIG_PATH", str(_write(tmp_path, cfg)))
    config_loader.reload_config()
    assert config_loader.get_channel_mention("bank") is False

def test_get_channel_mention_true(tmp_path, monkeypatch):
    cfg = {"channels": {"levelup_announce": {"channel_id": 1, "mention_player": True}}}
    monkeypatch.setattr(config_loader, "CONFIG_PATH", str(_write(tmp_path, cfg)))
    config_loader.reload_config()
    assert config_loader.get_channel_mention("levelup_announce") is True

def test_get_shop_items_coerces_role_id(tmp_path, monkeypatch):
    cfg = {"shop_items": [
        {"name": "A", "price": 100, "type": "rank_role", "role_id": "1160575257892098109"},
        {"name": "B", "price": 200, "type": "gacha_human"},
    ]}
    monkeypatch.setattr(config_loader, "CONFIG_PATH", str(_write(tmp_path, cfg)))
    config_loader.reload_config()
    items = config_loader.get_shop_items()
    assert items[0]["role_id"] == 1160575257892098109
    assert items[1].get("role_id") is None

def test_get_shop_items_empty_by_default(tmp_path, monkeypatch):
    monkeypatch.setattr(config_loader, "CONFIG_PATH", str(_write(tmp_path, {})))
    config_loader.reload_config()
    assert config_loader.get_shop_items() == []

def test_get_config_merges_missing_top_level_key(tmp_path, monkeypatch):
    cfg = {"channels": {"bank": {"channel_id": 999}}}
    example = {"channels": {"bank": {"channel_id": 111}}, "shop_items": [{"name": "x"}]}
    monkeypatch.setattr(config_loader, "CONFIG_PATH", str(_write(tmp_path, cfg)))
    ex_path = tmp_path / "example.json"
    ex_path.write_text(json.dumps(example), encoding="utf-8")
    monkeypatch.setattr(config_loader, "EXAMPLE_PATH", str(ex_path))
    config_loader.reload_config()
    result = config_loader.get_config()
    assert result["channels"]["bank"]["channel_id"] == 999  # existing value preserved, not overwritten
    assert result["shop_items"] == [{"name": "x"}]  # missing top-level key filled in from example

def test_get_config_merges_missing_nested_key(tmp_path, monkeypatch):
    cfg = {"channels": {"bank": {"channel_id": 999}}}
    example = {"channels": {"bank": {"channel_id": 111}, "levelup_announce": {"channel_id": None}}}
    monkeypatch.setattr(config_loader, "CONFIG_PATH", str(_write(tmp_path, cfg)))
    ex_path = tmp_path / "example.json"
    ex_path.write_text(json.dumps(example), encoding="utf-8")
    monkeypatch.setattr(config_loader, "EXAMPLE_PATH", str(ex_path))
    config_loader.reload_config()
    result = config_loader.get_config()
    assert result["channels"]["bank"]["channel_id"] == 999  # preserved
    assert result["channels"]["levelup_announce"]["channel_id"] is None  # missing nested key filled in

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
