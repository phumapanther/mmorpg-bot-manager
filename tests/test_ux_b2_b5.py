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
