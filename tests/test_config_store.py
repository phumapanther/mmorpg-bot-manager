import json
from panel import config_store

def test_save_then_load(tmp_path, monkeypatch):
    monkeypatch.setattr(config_store, "CONFIG_PATH", str(tmp_path / "config.json"))
    config_store.save({"bot_token": "abc"})
    assert config_store.load()["bot_token"] == "abc"

def test_ensure_exists_copies_example(tmp_path, monkeypatch):
    ex = tmp_path / "config.example.json"; ex.write_text('{"panel_port": 8770}', encoding="utf-8")
    monkeypatch.setattr(config_store, "CONFIG_PATH", str(tmp_path / "config.json"))
    monkeypatch.setattr(config_store, "EXAMPLE_PATH", str(ex))
    config_store.ensure_exists()
    assert config_store.load()["panel_port"] == 8770
