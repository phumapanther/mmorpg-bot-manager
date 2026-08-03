# tests/test_event_images.py
"""เทสโมดูลภาพอีเวนต์ — โฟกัส logic หาไฟล์/fallback (ไม่แตะเน็ต ไม่แตะ Discord จริง)"""
import bot.event_images as ei


def test_monster_slug():
    assert ei.monster_slug("🐉 มังกรน้ำแข็ง (Ice Dragon)") == "ice_dragon"
    assert ei.monster_slug("🟢 มอนสเตอร์ทั่วไป (Common)") == "common"
    assert ei.monster_slug("⚔️ อัศวินน้ำแข็งโบราณ (Ancient Ice Knight)") == "ancient_ice_knight"
    assert ei.monster_slug("🌈 จอมมารรุ้งสลับสี (Prismatic)") == "prismatic"
    assert ei.monster_slug("ไม่มีวงเล็บอังกฤษ") is None


def test_event_image_missing_returns_none(tmp_path, monkeypatch):
    monkeypatch.setattr(ei, "ASSETS_DIR", tmp_path)
    assert ei.event_image("village", "frozen") is None


def test_event_image_continent_first_then_fallback(tmp_path, monkeypatch):
    monkeypatch.setattr(ei, "ASSETS_DIR", tmp_path)
    (tmp_path / "village.png").write_bytes(b"png")
    f = ei.event_image("village", "frozen")          # ไม่มี frozen_village → fallback กลาง
    assert f is not None and f.filename == "village.png"
    (tmp_path / "frozen_village.png").write_bytes(b"png")
    f2 = ei.event_image("village", "frozen")         # มีของทวีป → ใช้ของทวีป
    assert f2.filename == "frozen_village.png"


def test_monster_image_fallback_rank(tmp_path, monkeypatch):
    monkeypatch.setattr(ei, "ASSETS_DIR", tmp_path)
    assert ei.monster_image("🐉 มังกรน้ำแข็ง (Ice Dragon)", "Main-Boss") is None
    (tmp_path / "monster_main_boss.png").write_bytes(b"png")
    f = ei.monster_image("🐉 มังกรน้ำแข็ง (Ice Dragon)", "Main-Boss")
    assert f.filename == "monster_main_boss.png"     # ไม่มีภาพเฉพาะตัว → ภาพแรงค์
    (tmp_path / "monster_ice_dragon.png").write_bytes(b"png")
    f2 = ei.monster_image("🐉 มังกรน้ำแข็ง (Ice Dragon)", "Main-Boss")
    assert f2.filename == "monster_ice_dragon.png"   # มีภาพเฉพาะตัว → ใช้ก่อน


def test_item_use_image_mapping(tmp_path, monkeypatch):
    monkeypatch.setattr(ei, "ASSETS_DIR", tmp_path)
    for name in ("item_wedding_ring", "item_monster_trap", "item_art_fire_ring",
                 "item_legend_weapon", "item_magic_bag", "respawn",
                 "mini_summon", "frozen_village"):
        (tmp_path / f"{name}.png").write_bytes(b"png")
    assert ei.item_use_image({"effect": "wedding_ring"}).filename == "item_wedding_ring.png"
    assert ei.item_use_image({"effect": "apply_status", "effect_value": "monster_trap"}).filename == "item_monster_trap.png"
    assert ei.item_use_image({"effect": "apply_status", "effect_value": "warm"}) is None  # ยาทั่วไป — ไม่มีภาพ
    assert ei.item_use_image({"effect": "equip_artifact", "effect_value": "art_fire_ring"}).filename == "item_art_fire_ring.png"
    assert ei.item_use_image({"effect": "revive"}).filename == "respawn.png"
    assert ei.item_use_image({"effect": "set_state", "effect_value": "mini_summon"}).filename == "mini_summon.png"
    assert ei.item_use_image({"effect": "set_state", "effect_value": "warp_village"}, continent="frozen").filename == "frozen_village.png"
    assert ei.item_use_image({"type": "weapon", "equip_key": "Legen_Weapon"}).filename == "item_legend_weapon.png"
    assert ei.item_use_image({"type": "weapon", "equip_key": "Iron_Weapon"}) is None
    assert ei.item_use_image({"type": "bag", "equip_key": "Magic_Bag"}).filename == "item_magic_bag.png"
    assert ei.item_use_image({"effect": "heal"}) is None


def test_file_kwargs():
    assert ei.file_kwargs(None) == {}

    class FakeFile:
        pass
    f = FakeFile()
    assert ei.file_kwargs(f) == {"file": f}
