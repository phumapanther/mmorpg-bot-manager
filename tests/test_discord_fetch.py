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
