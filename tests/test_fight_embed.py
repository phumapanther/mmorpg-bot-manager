"""B3: หน้าจอไฟต์แบบ embed — ครบข้อมูล อ่านง่าย ไม่เกินลิมิต Discord"""
from types import SimpleNamespace

import discord

import bot.views.game_views as gv


def test_hp_bar():
    assert gv.hp_bar(100, 100) == "█" * 10
    assert gv.hp_bar(0, 100) == "░" * 10
    assert gv.hp_bar(50, 100).count("█") == 5
    assert len(gv.hp_bar(7, 0)) == 10          # กันหารศูนย์


def _view(**kw):
    v = SimpleNamespace(monster_hp=312, monster_hp_max=500, monster_rank="Mini-Boss",
                        element="wood", m_stats={"name": "🌿 พืชกินคน"},
                        statuses={"spores": 2, "entangled": 3})
    v.__dict__.update(kw)
    return v


def test_embed_has_all_sections():
    embed = gv.build_fight_embed(
        _view(), {"hp": 240, "max_hp": 280},
        {"player": 19, "player_parts": ["`20` พื้นฐาน", "💨+1", "🍄-1"],
         "monster": 11, "monster_parts": ["`6` พื้นฐาน", "🌿+3", "🌱+2"]},
        "**`95`** ใส่ศัตรู · (19 เต๋า +0 ดาบ) ×5",
        "✨ Heal +115 HP\n😡 บอสคลั่ง +4",
        3)
    text = "\n".join(f.name + f.value for f in embed.fields)
    assert "เทิร์น 3" in embed.title and embed.color.value == gv.ELEMENT_COLORS["wood"]
    assert "312/500" in text and "240/280" in text          # เลือดสองฝ่าย
    assert "มินิบอส" in text                                  # ป้ายแรงค์
    assert "💨+1" in text and "🌱+2" in text                  # ที่มาแต้มเต๋าทั้งสองฝั่ง
    assert "ชนะเต๋า" in text                                  # ผลแพ้ชนะชัดเจน
    assert "Heal +115" in text and "บอสคลั่ง" in text          # เหตุการณ์ครบไม่ตัดทิ้ง
    assert "สปอร์" in text or "เห็ด" in text                   # สถานะติดตัว
    for f in embed.fields:
        assert len(str(f.value)) <= 1024                     # ไม่ชนลิมิต Discord


def test_embed_survives_long_event_log():
    long_log = "\n".join(f"เหตุการณ์ที่ {i} เกิดขึ้นในสนามรบอันดุเดือด" for i in range(60))
    embed = gv.build_fight_embed(_view(), {"hp": 1, "max_hp": 100}, None, None, long_log, 9)
    for f in embed.fields:
        assert len(str(f.value)) <= 1024
    assert len(embed.fields) <= 25


def test_embed_without_optional_parts():
    embed = gv.build_fight_embed(_view(statuses={}), {"hp": 50, "max_hp": 50}, None, None, "", 1)
    assert isinstance(embed, discord.Embed) and len(embed.fields) == 1   # เหลือแค่แถบเลือด
