import json
import pytest
from panel import config_store

@pytest.fixture(autouse=True)
def _isolate_example_path(tmp_path, monkeypatch):
    empty_example = tmp_path / "_autouse_example.json"
    empty_example.write_text("{}", encoding="utf-8")
    monkeypatch.setattr(config_store, "EXAMPLE_PATH", str(empty_example))

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

def test_load_merges_missing_key_from_example(tmp_path, monkeypatch):
    cfg_path = tmp_path / "config.json"
    cfg_path.write_text(json.dumps({"channels": {"bank": {"channel_id": 999}}}), encoding="utf-8")
    monkeypatch.setattr(config_store, "CONFIG_PATH", str(cfg_path))
    ex_path = tmp_path / "example.json"
    ex_path.write_text(json.dumps({
        "channels": {"bank": {"channel_id": 111}, "levelup_announce": {"channel_id": None}},
        "shop_items": [{"name": "x"}],
    }), encoding="utf-8")
    monkeypatch.setattr(config_store, "EXAMPLE_PATH", str(ex_path))
    result = config_store.load()
    assert result["channels"]["bank"]["channel_id"] == 999
    assert result["channels"]["levelup_announce"]["channel_id"] is None
    assert result["shop_items"] == [{"name": "x"}]
