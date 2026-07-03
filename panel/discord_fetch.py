import httpx

BASE = "https://discord.com/api/v10"

def _headers(token):
    return {"Authorization": f"Bot {token}"}

def list_guilds(token):
    r = httpx.get(f"{BASE}/users/@me/guilds", headers=_headers(token), timeout=10)
    r.raise_for_status()
    return [{"id": g["id"], "name": g["name"]} for g in r.json()]

def list_channels(token, guild_id):
    r = httpx.get(f"{BASE}/guilds/{guild_id}/channels", headers=_headers(token), timeout=10)
    r.raise_for_status()
    return [{"id": c["id"], "name": c["name"], "type": c["type"]}
            for c in r.json() if c["type"] == 0]

def list_roles(token, guild_id):
    r = httpx.get(f"{BASE}/guilds/{guild_id}/roles", headers=_headers(token), timeout=10)
    r.raise_for_status()
    return [{"id": r_["id"], "name": r_["name"]} for r_ in r.json()]
