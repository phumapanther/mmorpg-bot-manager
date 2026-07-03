import httpx
from panel import discord_fetch

def test_list_channels_filters_text(monkeypatch):
    payload = [{"id": "1", "name": "general", "type": 0},
               {"id": "2", "name": "voice", "type": 2}]
    def fake_get(url, headers, params=None, timeout=None):
        return httpx.Response(200, json=payload, request=httpx.Request("GET", url))
    monkeypatch.setattr(discord_fetch.httpx, "get", fake_get)
    chans = discord_fetch.list_channels("tok", 123)
    assert [c["id"] for c in chans] == ["1"]  # only text (type 0)

def test_list_channels_sorted_by_position(monkeypatch):
    payload = [
        {"id": "2", "name": "second", "type": 0, "position": 3},
        {"id": "1", "name": "first", "type": 0, "position": 1},
        {"id": "3", "name": "voice", "type": 2, "position": 2},
    ]
    def fake_get(url, headers, params=None, timeout=None):
        return httpx.Response(200, json=payload, request=httpx.Request("GET", url))
    monkeypatch.setattr(discord_fetch.httpx, "get", fake_get)
    chans = discord_fetch.list_channels("tok", 123)
    assert [c["id"] for c in chans] == ["1", "2"]

def test_list_roles_sorted_by_position_desc(monkeypatch):
    payload = [
        {"id": "1", "name": "everyone", "position": 0},
        {"id": "3", "name": "admin", "position": 5},
        {"id": "2", "name": "mod", "position": 2},
    ]
    def fake_get(url, headers, params=None, timeout=None):
        return httpx.Response(200, json=payload, request=httpx.Request("GET", url))
    monkeypatch.setattr(discord_fetch.httpx, "get", fake_get)
    roles = discord_fetch.list_roles("tok", 123)
    assert [r["id"] for r in roles] == ["3", "2", "1"]
