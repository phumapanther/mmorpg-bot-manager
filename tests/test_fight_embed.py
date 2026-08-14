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


def test_embed_monster_thumbnail_every_turn():
    """ภาพมอนโชว์เป็น thumbnail ทุกเทิร์น — ไฟล์ถูกอัปโหลดแค่เทิร์นแรก attachment ค้างบนข้อความ"""
    for turn in (1, 2, 7):
        embed = gv.build_fight_embed(_view(), {"hp": 50, "max_hp": 50}, None, None, "", turn)
        assert embed.thumbnail.url == "attachment://monster.png"


# ── B7: หน้าตายสรุปชัด ──

def test_respawn_fee_tiers_from_config(monkeypatch):
    """ค่าชุบชีวิตอ่านจาก Panel และเลือก tier ตามเลเวลถูกต้อง"""
    from bot import config_loader
    tiers = config_loader.get_balance("death.respawn_fee_tiers")
    assert tiers and tiers[0][0] >= tiers[-1][0]          # เรียงจากเลเวลสูงลงต่ำ

    def fee_for(level):
        return next((int(f) for lv, f in tiers if level >= int(lv)), 0)

    assert fee_for(120) == 10000 and fee_for(95) == 5000
    assert fee_for(60) == 2500 and fee_for(25) == 1000
    assert fee_for(12) == 500 and fee_for(3) == 0          # ผู้เล่นใหม่ชุบฟรี


def test_death_screen_sections_exist():
    """หน้าตายต้องมีครบ 3 ส่วน: เสียอะไร / เหลืออะไร / ทำอะไรต่อ"""
    import pathlib
    src = pathlib.Path("bot/views/fight_ui.py").read_text(encoding="utf-8")   # O3: ย้ายมาไฟล์ UI กลาง
    assert "📉 สิ่งที่เสียไป" in src and "📊 สถานะปัจจุบัน" in src and "👉 ทำอะไรต่อดี" in src
    assert "ของในกระเป๋า **ปลอดภัยครบ**" in src           # บอกชัดว่าของไม่หาย



# ── O3+O4: ตายทางไหนก็จ่ายเท่ากัน + ค่าพักแรมตั้งได้ ──

def test_all_death_paths_share_one_logic():
    """ทั้ง RespawnView และ DeathRespawnView ต้องเรียก respawn_player ตัวเดียวกัน"""
    import pathlib, re
    src = pathlib.Path("bot/views/game_views.py").read_text(encoding="utf-8")
    assert src.count("respawn_player(self.user_id)") == 2, "ยังมีเส้นทางตายที่ไม่ได้ใช้ตรรกะกลาง"
    assert 'player.get("cash", 0) - 1000' not in src   # ไม่มีค่าชุบคงที่ 1,000 หลงเหลือ
    assert "force_respawn_fee" not in src              # เลิกใช้ค่าธรรมเนียมแยกของเส้นทางที่สอง


def test_respawn_player_uses_config(tmp_path, monkeypatch):
    import bot.views.game_views as gv
    from bot import config_loader
    saved = {}
    monkeypatch.setattr(gv.player_model, "get_player",
                        lambda uid: {"level": 95, "max_hp": 200, "cash": 50000, "dungeon_steps": 3})
    monkeypatch.setattr(gv.player_model, "update_player_fields", lambda uid, u: saved.update(u))
    monkeypatch.setattr(config_loader, "get_config", lambda: {"game_balance": {
        "drops": {"respawn_hp_percent": 50},
        "death": {"respawn_fee_tiers": [[90, 7777], [0, 0]]}}})

    embed, info = gv.respawn_player(1)
    assert info["fee"] == 7777 and info["hp"] == 100          # tier เลเวล 90+ / ฟื้น 50%
    assert saved["cash"] == 50000 - 7777 and saved["dungeon_steps"] == 0
    text = " ".join(f.value for f in embed.fields)
    assert "7,777" in text and "3 ชั้น" in text                # บอกค่าปรับ + ชั้นที่เสีย


def test_village_rest_cost_from_config():
    import json, pathlib
    cfg = json.load(open("config.example.json", encoding="utf-8"))
    assert cfg["game_balance"]["village"]["rest_cost"] == 2000
    assert "rest_cost_per_level" in cfg["game_balance"]["village"]
    # ค่าพักแรมย้ายไป adventure_core แล้ว (เว็บเกม เฟส 5.4) — พักแรมบนเว็บต้องคิดราคาเดียวกัน
    src = pathlib.Path("bot/adventure_core.py").read_text(encoding="utf-8")
    assert 'village.rest_cost' in src and 'player["cash"] < 2000' not in src
