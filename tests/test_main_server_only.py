"""P8-① ชั้นแยกเซิร์ฟหลัก/เซิร์ฟรอง"""
import asyncio
from types import SimpleNamespace

from bot import config_loader, utils


def _ctx(guild_id, sent):
    async def send(msg=None, **kw):
        sent.append(msg)
    return SimpleNamespace(guild=SimpleNamespace(id=guild_id), send=send)


def test_is_main_server_default_true(monkeypatch):
    monkeypatch.setattr(config_loader, "get_main_guild_id", lambda: None)
    assert utils.is_main_server(SimpleNamespace(guild=SimpleNamespace(id=123))) is True


def test_is_main_server_match(monkeypatch):
    monkeypatch.setattr(config_loader, "get_main_guild_id", lambda: 999)
    assert utils.is_main_server(SimpleNamespace(guild=SimpleNamespace(id=999))) is True
    assert utils.is_main_server(SimpleNamespace(guild=SimpleNamespace(id=111))) is False


def test_main_server_only_blocks_with_invite(monkeypatch):
    monkeypatch.setattr(config_loader, "get_main_guild_id", lambda: 999)
    monkeypatch.setattr(config_loader, "get_main_server_invite", lambda: "https://discord.gg/test")
    predicate = utils.main_server_only().predicate
    sent = []
    assert asyncio.run(predicate(_ctx(999, sent))) is True and sent == []
    assert asyncio.run(predicate(_ctx(111, sent))) is False
    assert "เซิร์ฟหลัก" in sent[0] and "discord.gg/test" in sent[0]


def test_config_keys_exist():
    import json
    cfg = json.load(open("config.example.json", encoding="utf-8"))
    assert "guest_bot_token" in cfg and cfg["guest_bot_token"] == ""
    assert "main_guild_id" in cfg and cfg["main_guild_id"] is None
    assert cfg["main_server_invite"].startswith("https://discord.gg/")


def test_locked_cogs_have_main_server_gate():
    """cog ที่ต้องล็อกไว้เซิร์ฟหลัก ต้องมีด่านเช็คจริง (กันเผลอลบตอน refactor)"""
    import pathlib
    must_gate = ["casino", "blackjack", "role_shop", "payment", "pvp_duel", "world_boss",
                 "world_admin", "private_room", "owner_announce", "guild", "guild_war",
                 "admin_commands"]
    for name in must_gate:
        src = pathlib.Path(f"bot/cogs/{name}.py").read_text(encoding="utf-8")
        assert ("main_server_gate(ctx)" in src or "is_main_server(ctx)" in src), f"{name} ไม่มีด่านเซิร์ฟหลัก!"


def test_adventure_commands_stay_open():
    """คำสั่งเล่นผจญภัยต้องไม่ถูกล็อก (guest ต้องใช้ได้)"""
    import pathlib
    gc = pathlib.Path("bot/cogs/game_commands.py").read_text(encoding="utf-8")
    assert "async def cog_check" not in gc          # ไม่ล็อกทั้ง cog (มี !play/!menu)
    assert "@main_server_only()" in gc              # แต่ล็อก !shop
    adv = pathlib.Path("bot/cogs/adventure_zone.py").read_text(encoding="utf-8")
    assert "is_main_server" not in adv              # !adv เปิดให้เซิร์ฟรอง


def test_panel_ui_has_multi_server_fields():
    """หน้า Panel ต้องมีช่องกรอกครบ 3 ค่าของโหมดหลายเซิร์ฟ + โค้ดอ่าน/เขียนถูก key"""
    import pathlib
    html = pathlib.Path("panel/static/index.html").read_text(encoding="utf-8")
    js = pathlib.Path("panel/static/app.js").read_text(encoding="utf-8")
    for el in ("guestTokenInput", "mainGuildIdInput", "mainInviteInput"):
        assert f'id="{el}"' in html, f"ไม่มีช่อง {el} ในหน้า Panel"
        assert el in js, f"app.js ไม่ได้อ่าน/เขียน {el}"
    for key in ("guest_bot_token", "main_guild_id", "main_server_invite"):
        assert f"state.config.{key}" in js


def test_adventure_room_only_gate(monkeypatch):
    """คำสั่งที่ไม่ได้ฟิกห้อง: เซิร์ฟหลักต้องอยู่ในมิติส่วนตัวของตัวเอง / เซิร์ฟรองผ่าน"""
    import asyncio
    monkeypatch.setattr(config_loader, "get_main_guild_id", lambda: 999)
    predicate = utils.adventure_room_only().predicate
    sent = []

    async def send(msg=None, **kw):
        sent.append(msg)

    def ctx(guild_id, channel_name, author="panther"):
        return SimpleNamespace(guild=SimpleNamespace(id=guild_id),
                               channel=SimpleNamespace(name=channel_name),
                               author=SimpleNamespace(name=author, mention=f"@{author}"),
                               send=send)

    assert asyncio.run(predicate(ctx(999, "🌌มิติส่วนตัว-panther"))) is True     # ห้องตัวเอง
    assert asyncio.run(predicate(ctx(999, "แชทโลก"))) is False                   # ห้องทั่วไป
    assert "มิติส่วนตัว" in sent[-1]
    assert asyncio.run(predicate(ctx(999, "🌌มิติส่วนตัว-someone"))) is False     # ห้องคนอื่น
    assert asyncio.run(predicate(ctx(111, "แชทอะไรก็ได้"))) is True               # เซิร์ฟรองผ่าน


def test_all_player_commands_have_a_room_gate():
    """กันลืม: ทุกคำสั่งผู้เล่นต้องมีด่านห้องอย่างใดอย่างหนึ่ง (config หรือมิติส่วนตัว)"""
    import pathlib, re
    for f in ("player_commands", "game_commands"):
        src = pathlib.Path(f"bot/cogs/{f}.py").read_text(encoding="utf-8")
        for m in re.finditer(r'((?:^    @[^\n]*\n)+)    async def \w+', src, re.M):
            block = m.group(1)
            name = re.search(r'command\(name="([^"]+)"', block)
            if not name or name.group(1) == "play":   # !play มีเช็คมิติในตัว
                continue
            assert ("allowed_channel" in block or "adventure_room_only" in block), \
                f"!{name.group(1)} ยังไม่มีด่านห้อง"


def test_gate_explains_instead_of_silent(monkeypatch):
    """cog_check ต้องไม่บล็อกเงียบ — ผู้เล่นต้องได้ข้อความบอกเหตุผล"""
    import asyncio
    monkeypatch.setattr(config_loader, "get_main_guild_id", lambda: 999)
    monkeypatch.setattr(config_loader, "get_main_server_invite", lambda: "https://discord.gg/x")
    sent = []

    async def send(msg=None, **kw):
        sent.append(msg)

    ctx = SimpleNamespace(guild=SimpleNamespace(id=111), send=send)
    assert asyncio.run(utils.main_server_gate(ctx)) is False
    assert "เซิร์ฟหลัก" in sent[0] and "discord.gg/x" in sent[0]
    assert asyncio.run(utils.main_server_gate(SimpleNamespace(guild=SimpleNamespace(id=999), send=send))) is True


def test_no_cog_blocks_silently():
    """กันลืม: cog ที่ล็อกเซิร์ฟหลักต้องใช้ main_server_gate (ไม่ใช่ return is_main_server เฉย ๆ)"""
    import pathlib
    for f in pathlib.Path("bot/cogs").glob("*.py"):
        src = f.read_text(encoding="utf-8")
        assert "return is_main_server(ctx)" not in src, f"{f.name} บล็อกเงียบ — ใช้ main_server_gate แทน"


def test_snowflake_ids_never_converted_to_js_number():
    """บั๊กจริง 2026-07-28: Number() ใน JS ปัดไอดี Discord (>2^53) ทิ้งหลักท้าย
    เช่น 1138420073900560515 → 1138420073900560500 ทำให้เซิร์ฟหลักกลายเป็นเซิร์ฟรอง"""
    import pathlib, re
    js = pathlib.Path("panel/static/app.js").read_text(encoding="utf-8")
    for line in js.splitlines():
        if "Number(" not in line:
            continue
        assert "guild_id" not in line and "role" not in line.lower(), \
            f"ห้ามแปลงไอดี Discord เป็น Number: {line.strip()}"


def test_main_guild_id_accepts_string(monkeypatch):
    """เก็บเป็น string แล้ว get_main_guild_id ต้องยังคืน int ที่ถูกต้อง"""
    from bot import config_loader
    monkeypatch.setattr(config_loader, "get_config",
                        lambda: {"main_guild_id": "1138420073900560515"})
    assert config_loader.get_main_guild_id() == 1138420073900560515
