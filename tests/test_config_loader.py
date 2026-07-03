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
