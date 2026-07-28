"""O2 ปุ่มไอเทมกลางไฟต์ · O7 ปุ่มลัดในหมู่บ้าน · O8 ล็อกห้องกิลด์วอร์"""
import json

import bot.views.game_views as gv


def test_o2_quick_item_button_in_fight():
    labels = [b.label for b in gv.MonsterEventView(1, [], monster_rank="Common", monster_hp=10).children]
    assert any("ใช้ไอเทม" in l for l in labels), "ไม่มีปุ่มใช้ไอเทมกลางไฟต์"
    assert any("สู้ต่อ" in l for l in labels) and any("หนี" in l for l in labels)   # ของเดิมยังอยู่


def test_o7_village_shortcuts():
    labels = [b.label for b in gv.VillageEventView(1).children]
    for want in ("พักแรม", "ร้านค้า", "ธนาคาร", "โปรไฟล์", "ออกเดินทางต่อ"):
        assert any(want in l for l in labels), f"หมู่บ้านไม่มีปุ่ม {want}"
    assert len(labels) <= 25          # ลิมิต Discord


def test_o8_warguild_channel_locked():
    import pathlib
    src = pathlib.Path("bot/cogs/guild_war.py").read_text(encoding="utf-8")
    assert 'allowed_channel("guild_war")' in src
    cfg = json.load(open("config.example.json", encoding="utf-8"))
    assert cfg["channels"]["guild_war"]["channel_id"] is None      # ไม่ตั้ง = ใช้ได้ทุกห้อง (ของเดิมไม่พัง)
