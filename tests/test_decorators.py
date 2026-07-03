import types, asyncio, pytest
from bot import utils, config_loader

class FakeRole:
    def __init__(self, rid): self.id = rid

def make_ctx(channel_id, author_id, role_ids, owner_id):
    author = types.SimpleNamespace(id=author_id, roles=[FakeRole(r) for r in role_ids])
    guild = types.SimpleNamespace(owner_id=owner_id)
    sent = {}
    async def send(msg): sent["msg"] = msg
    return types.SimpleNamespace(channel=types.SimpleNamespace(id=channel_id),
                                 author=author, guild=guild, send=send), sent

def run_predicate(deco, ctx):
    # decorator returns commands.check(predicate); pull predicate out
    check = deco
    pred = check.predicate if hasattr(check, "predicate") else check.__closure__[0].cell_contents
    return asyncio.run(pred(ctx))

def test_allowed_channel_pass(monkeypatch):
    monkeypatch.setattr(config_loader, "get_channel_id", lambda k: 999)
    ctx, _ = make_ctx(channel_id=999, author_id=1, role_ids=[], owner_id=2)
    assert run_predicate(utils.allowed_channel("bank"), ctx) is True

def test_allowed_channel_unconfigured_allows(monkeypatch):
    monkeypatch.setattr(config_loader, "get_channel_id", lambda k: None)
    ctx, _ = make_ctx(channel_id=5, author_id=1, role_ids=[], owner_id=2)
    assert run_predicate(utils.allowed_channel("bank"), ctx) is True

def test_has_permission_owner_passes(monkeypatch):
    monkeypatch.setattr(config_loader, "get_role_ids", lambda g: [])
    ctx, _ = make_ctx(channel_id=1, author_id=7, role_ids=[], owner_id=7)
    assert run_predicate(utils.has_permission("admin"), ctx) is True

def test_has_permission_role_match(monkeypatch):
    monkeypatch.setattr(config_loader, "get_role_ids", lambda g: [55])
    ctx, _ = make_ctx(channel_id=1, author_id=7, role_ids=[55], owner_id=2)
    assert run_predicate(utils.has_permission("admin"), ctx) is True

def test_has_permission_denied(monkeypatch):
    monkeypatch.setattr(config_loader, "get_role_ids", lambda g: [55])
    ctx, _ = make_ctx(channel_id=1, author_id=7, role_ids=[10], owner_id=2)
    assert run_predicate(utils.has_permission("admin"), ctx) is False
