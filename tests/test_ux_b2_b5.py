"""B2 โปรไฟล์แบ่งหน้า + B5 กระเป๋าจัดกลุ่ม/ขายวัสดุ"""
import json
from types import SimpleNamespace

import bot.cogs.player_commands as pc
import bot.models.player_model as pm
from bot.views.menu_view import ProfilePageView
from bot.views.profile_embed import create_profile_embed

MEMBER = SimpleNamespace(id=1, display_name="T",
                         display_avatar=SimpleNamespace(url="https://x/a.png"), roles=[])
PLAYER = {"level": 5, "exp": 900, "race": "、🐉 • มังกร", "class_name": "Warrior"}


def test_profile_pages_split_content():
    status = create_profile_embed(MEMBER, PLAYER, page="status")
    equip = create_profile_embed(MEMBER, PLAYER, page="equip")
    prog = create_profile_embed(MEMBER, PLAYER, page="progress")
    names = lambda e: [f.name for f in e.fields]

    assert "🧬 ธาตุประจำตัว" in names(status) and "🔥 สกิลประจำคลาส" not in names(status)
    assert "⚔️ อาวุธที่ถือ" in names(equip) and "🔥 สกิลประจำคลาส" in names(equip)
    assert "📊 ประสบการณ์" in names(prog)
    for e in (status, equip, prog):
        assert len(e.fields) <= 10          # เดิม 15 ช่องรวด — ตอนนี้แต่ละหน้าอ่านสบาย
        assert "T" in e.title


def test_profile_page_buttons():
    v = ProfilePageView(MEMBER, current="equip")
    labels = [(b.label, b.disabled) for b in v.children]
    assert len(labels) == 3
    assert [d for lbl, d in labels if "อุปกรณ์" in lbl] == [True]     # หน้าปัจจุบันกดซ้ำไม่ได้


def _fake_inventory(monkeypatch, inv, items):
    saved = {}
    monkeypatch.setattr(pc.player_model, "get_player", lambda uid: {"inventory": inv, "cash": 100})
    monkeypatch.setattr(pc.player_model, "load_inventory", lambda raw: list(inv))
    monkeypatch.setattr(pc.player_model, "update_player_fields", lambda uid, u: saved.update(u))
    monkeypatch.setattr(pc.config_loader, "get_all_items", lambda: items)
    return saved


ITEMS = {
    "1": {"name": "💉 ยาฮีล", "type": "use", "effect": "heal", "sell": 100},
    "9": {"name": "🦴 เศษกระดูก", "type": "junk", "sell": 10},
    "12": {"name": "🪨 เศษหิน", "type": "junk", "sell": 5},
    "42": {"name": "🧤 ถุงมือ", "type": "use", "effect": "equip_artifact", "sell": 5000},
    "3": {"name": "🟫 เกราะหนัง", "type": "armor", "equip_key": "leather", "sell": 300},
}


def test_sell_all_junk_keeps_important_items(monkeypatch):
    saved = _fake_inventory(monkeypatch, ["1", "9", "9", "12", "42", "3"], ITEMS)
    sold, gold, msg = pc.sell_all_junk(1)
    assert sold == 3 and gold == 10 + 10 + 5           # ขายเฉพาะวัสดุ
    kept = json.loads(saved["inventory"])
    assert sorted(kept) == ["1", "3", "42"]            # ยา/เกราะ/อาร์ติแฟกต์ ปลอดภัย
    assert saved["cash"] == 100 + gold


def test_sell_all_junk_when_nothing(monkeypatch):
    _fake_inventory(monkeypatch, ["1", "42"], ITEMS)
    sold, gold, msg = pc.sell_all_junk(1)
    assert sold == 0 and gold == 0 and "ไม่มีวัสดุ" in msg


def test_bag_groups_by_type(monkeypatch):
    monkeypatch.setattr(pc.player_model, "load_inventory", lambda raw: ["1", "9", "42", "3"])
    monkeypatch.setattr(pc.config_loader, "get_all_items", lambda: ITEMS)
    embed = pc.build_bag_embed("T", "https://x/a.png", {"inventory": "", "cash": 0, "capacity": 50})
    names = " ".join(f.name for f in embed.fields)
    assert "💊 ของใช้" in names and "🏺 อาร์ติแฟกต์" in names
    assert "⚔️ อุปกรณ์สวมใส่" in names and "ขายหมดได้" in names


# ── B1: คราฟผ่านปุ่ม ──

RECIPE_ITEMS = dict(ITEMS, **{"7": {"name": "⚔️ อาวุธเหล็ก", "type": "weapon", "equip_key": "iron", "sell": 1}})
RECIPES = {"7": {"recipe": {"9": 2, "12": 1}, "fail_rate": 0}}


def _craft_env(monkeypatch, inv):
    saved = {}
    monkeypatch.setattr(pc.player_model, "get_player",
                        lambda uid: {"inventory": list(inv), "capacity": 50, "cash": 0})
    monkeypatch.setattr(pc.player_model, "load_inventory", lambda raw: list(raw) if isinstance(raw, list) else list(inv))
    monkeypatch.setattr(pc.player_model, "update_player_field",
                        lambda uid, f, v: saved.__setitem__(f, v))
    monkeypatch.setattr(pc.config_loader, "get_crafting_recipe", lambda i: RECIPES.get(str(i), {}))
    monkeypatch.setattr(pc.config_loader, "get_item_config", lambda i: RECIPE_ITEMS.get(str(i), {}))
    monkeypatch.setattr(pc.config_loader, "get_config",
                        lambda: {"item_catalog": {"crafting_recipes": RECIPES}})
    return saved


def test_craft_for_success(monkeypatch):
    saved = _craft_env(monkeypatch, ["9", "9", "12"])
    ok, msg = pc.craft_for(1, "7")
    assert ok and "คราฟสำเร็จ" in msg
    assert json.loads(saved["inventory"]) == ["7"]        # วัตถุดิบถูกหัก ของใหม่เข้ากระเป๋า


def test_craft_for_missing_material(monkeypatch):
    _craft_env(monkeypatch, ["9"])
    ok, msg = pc.craft_for(1, "7")
    assert not ok and "วัตถุดิบไม่พอ" in msg


def test_craftable_now_lists_only_ready(monkeypatch):
    _craft_env(monkeypatch, ["9", "9", "12"])
    ready = pc.craftable_now(1)
    assert [r[0] for r in ready] == ["7"] and "×2" in ready[0][2]
    _craft_env(monkeypatch, ["9"])
    assert pc.craftable_now(1) == []


# ── B6: แยกไฟล์แล้วต้องใช้งานเหมือนเดิมทุกจุด ──

def test_b6_data_module_reexport():
    """ย้าย data ออกไป game_data แล้ว game_modifiers ต้องยังเข้าถึงได้เหมือนเดิม"""
    import bot.game_data as gd
    import bot.game_modifiers as gm
    assert gm.CONTINENTS is gd.CONTINENTS
    assert gm.STATUS_EFFECTS is gd.STATUS_EFFECTS and gm.WEEKLY_THEMES is gd.WEEKLY_THEMES
    assert len(gm.CONTINENTS) == 9 and len(gm.WEEKLY_THEMES) == 13


def test_b6_fight_ui_module():
    """ย้าย UI ไฟต์ออกไป fight_ui แล้ว game_views ต้องยังเรียกได้เหมือนเดิม"""
    import bot.views.fight_ui as ui
    import bot.views.game_views as gv
    assert gv.hp_bar is ui.hp_bar and gv.build_fight_embed is ui.build_fight_embed
    assert gv.ELEMENT_COLORS is ui.ELEMENT_COLORS


def test_b6_files_got_smaller():
    """กันถอยหลัง: ไฟล์ตรรกะหลักต้องไม่บวมกลับ"""
    import pathlib
    assert len(pathlib.Path("bot/game_modifiers.py").read_text(encoding="utf-8").splitlines()) < 900
    assert len(pathlib.Path("bot/views/fight_ui.py").read_text(encoding="utf-8").splitlines()) < 200


# ── B1 รอบสอง: คำสั่งที่พิมพ์เองต้องได้ปุ่มเหมือนกดจากเมนู ──

def test_typed_commands_attach_views():
    """!bank / !bag พิมพ์เองต้องมีปุ่มติดมาด้วย (เดิมมีเฉพาะตอนกดจากเมนู)"""
    import pathlib
    src = pathlib.Path("bot/apps/bot_game/player_commands.py").read_text(encoding="utf-8")
    assert "view=BankActionView()" in src, "!bank ไม่มีปุ่มฝาก/ถอน/โอน"
    assert "view=BagActionView(ctx.author.id)" in src, "!bag ไม่มีปุ่มคราฟ/ทิ้ง/ขาย"


def test_bag_has_three_action_buttons():
    from bot.views.menu_view import BagActionView
    labels = [b.label for b in BagActionView(1).children]
    assert any("คราฟ" in l for l in labels) and any("ทิ้ง" in l for l in labels) \
        and any("ขายวัสดุ" in l for l in labels)


def test_drop_item_for(monkeypatch):
    saved = {}
    monkeypatch.setattr(pc.player_model, "get_player", lambda uid: {"inventory": ["9", "9", "1"]})
    monkeypatch.setattr(pc.player_model, "load_inventory", lambda raw: ["9", "9", "1"])
    monkeypatch.setattr(pc.player_model, "update_player_field", lambda uid, f, v: saved.__setitem__(f, v))
    monkeypatch.setattr(pc.config_loader, "get_item_config", lambda i: ITEMS.get(str(i), {}))

    ok, msg = pc.drop_item_for(1, "9", 1)
    assert ok and json.loads(saved["inventory"]) == ["9", "1"]
    ok2, msg2 = pc.drop_item_for(1, "77", 1)          # ไม่มีของชิ้นนี้
    assert not ok2 and "ไม่มีไอเทม" in msg2
