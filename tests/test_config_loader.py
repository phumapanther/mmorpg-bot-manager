import json
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
