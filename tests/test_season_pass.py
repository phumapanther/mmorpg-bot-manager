"""C2: Season Pass รายเดือน — สายฟรี/พรีเมียม, รับรางวัลครั้งเดียว, เปลี่ยนซีซั่นเอง"""
import datetime
import json

import pytest

import bot.models.player_model as pm
from bot import config_loader, season

CFG = {"season_pass": {"enabled": True, "price_gold": 5000000, "tiers": [
    {"points": 100, "free": {"gold": 1000}, "premium": {"gold": 5000}},
    {"points": 500, "free": {"gold": 2000}, "premium": {"gold": 9000}},
]}}


@pytest.fixture
def world(tmp_path, monkeypatch):
    monkeypatch.setattr(pm, "DB_NAME", str(tmp_path / "t.db"))
    monkeypatch.setattr(config_loader, "get_config", lambda: CFG)
    state = {"cash": 6000000, "bank": 0, "inventory": "[]"}
    monkeypatch.setattr(pm, "get_player", lambda uid: dict(state))
    monkeypatch.setattr(pm, "update_player_field", lambda uid, f, v: state.__setitem__(f, v))
    monkeypatch.setattr(pm, "add_exp", lambda uid, exp: None)
    return state


def test_season_key_is_the_month():
    assert pm.season_key(datetime.date(2026, 7, 28)) == "2026-07"
    assert pm.season_key(datetime.date(2026, 8, 1)) == "2026-08"   # เดือนใหม่ = ซีซั่นใหม่เอง


def test_points_reset_between_seasons(world):
    pm.add_season_points(1, 300, season="2026-07")
    assert pm.get_season_points(1, "2026-07") == 300
    assert pm.get_season_points(1, "2026-08") == 0


def test_free_track_only_without_premium(world):
    pm.add_season_points(1, 600)
    msg = season.claim_all(1)
    assert world["bank"] == 1000 + 2000                 # ได้เฉพาะสายฟรีสองขั้น
    assert "พรีเมียม" not in msg

    assert "ยังไม่มีรางวัล" in season.claim_all(1)      # รับซ้ำไม่ได้
    assert world["bank"] == 3000


def test_premium_unlocks_the_second_track(world):
    pm.add_season_points(1, 600)
    season.claim_all(1)                                 # เก็บสายฟรีไปก่อน
    ok, _msg = season.buy_premium(1)
    assert ok and world["cash"] == 6000000 - 5000000

    season.claim_all(1)
    assert world["bank"] == 3000 + 5000 + 9000          # ย้อนเก็บสายพรีเมียมของขั้นที่ปลดไว้แล้วได้


def test_locked_tier_pays_nothing(world):
    pm.add_season_points(1, 99)
    season.claim_all(1)
    assert world["bank"] == 0


def test_buy_requires_enough_cash(world):
    world["cash"] = 10
    ok, msg = season.buy_premium(1)
    assert not ok and "!payment" in msg                 # ชี้ทางไปเติมเงินระบบเดิม
    assert not season.is_premium(1)


def test_admin_grant_is_idempotent(world):
    assert season.grant_premium(1) is True
    assert season.grant_premium(1) is False
    assert season.is_premium(1)


def test_premium_is_per_season(world):
    season.grant_premium(1, season="2026-07")
    assert season.is_premium(1, "2026-07")
    assert not season.is_premium(1, "2026-08")          # ซีซั่นใหม่ต้องซื้อใหม่ = รายได้ต่อเนื่อง


def test_embed_shows_both_tracks(world):
    pm.add_season_points(1, 150)
    embed = season.build_season_embed(1, "T")
    text = "\n".join(f.name + f.value for f in embed.fields)
    assert "🆓" in text and "⭐" in text
    assert "กดรับได้" in text and "ต้องเปิดพรีเมียม" in text and "ยังไม่ถึง" in text


def test_config_tiers_sorted():
    tiers = json.load(open("config.example.json", encoding="utf-8"))["season_pass"]["tiers"]
    pts = [t["points"] for t in tiers]
    assert pts == sorted(pts), "ขั้นต้องเรียงจากน้อยไปมาก (claim_all หยุดที่ขั้นแรกที่ยังไม่ถึง)"


def test_points_come_from_add_exp():
    import pathlib
    src = pathlib.Path("bot/models/player_model.py").read_text(encoding="utf-8")
    add_exp = src[src.index("def add_exp("):src.index("def add_exp(") + 800]
    assert "add_season_points" in add_exp and "add_weekly_points" in add_exp


# ── สรุปสถานะทั้งใบ (season_view) — ดิสกับเว็บอ่านตัวเดียวกัน ──

CFG_ITEM = {"season_pass": {"enabled": True, "price_gold": 5000000, "tiers": [
    {"points": 100, "free": {"gold": 1000}, "premium": {"gold": 5000, "item": "1"}},
    {"points": 500, "free": {"gold": 2000, "item": "1"}, "premium": {"gold": 9000}},
]}}


def test_view_marks_every_slot_the_same_way_the_embed_does(world):
    pm.add_season_points(1, 150)                       # ถึงขั้น 1 ยังไม่ถึงขั้น 2
    v = season.season_view(1)
    assert v["tiers_done"] == 1 and v["tiers_total"] == 2
    assert v["next"] == {"index": 1, "points": 500, "need_more": 350}

    slot = {(t["index"], k["track"]): k["status"] for t in v["tiers"] for k in t["tracks"]}
    assert slot[(0, "free")] == "ready"               # ถึงแล้ว ยังไม่รับ
    assert slot[(0, "premium")] == "need_premium"     # ถึงแล้วแต่ยังไม่ได้ซื้อสาย
    assert slot[(1, "free")] == "locked"              # แต้มยังไม่ถึง
    assert v["claimable"] == 1                        # กดรับได้แค่ช่องเดียวตอนนี้

    season.claim_all(1)
    v = season.season_view(1)
    assert v["tiers"][0]["tracks"][0]["status"] == "claimed"
    assert v["claimable"] == 0                        # รับหมดแล้วต้องไม่เหลือค้าง


def test_view_spells_out_the_item_you_will_get(world, monkeypatch):
    """เดิมเว็บโชว์แค่คำว่า 'ไอเทม' — ต้องบอกชื่อของจริงถึงจะรู้ว่าคุ้มไหม"""
    monkeypatch.setattr(config_loader, "get_config", lambda: CFG_ITEM)
    pm.add_season_points(1, 600)
    v = season.season_view(1)
    free2 = v["tiers"][1]["tracks"][0]
    assert free2["item"] and free2["item"]["name"], "ไม่ได้แปลงรหัสไอเทมเป็นชื่อ"
    assert free2["item"]["name"] in free2["text"], "ข้อความสรุปไม่มีชื่อของ"
    assert "1" != free2["text"], "ยังโชว์เป็นรหัสไอเทมดิบอยู่"


def test_premium_slots_open_up_after_buying(world):
    pm.add_season_points(1, 600)
    assert all(k["status"] != "ready"
               for t in season.season_view(1)["tiers"] for k in t["tracks"]
               if k["track"] == "premium")
    season.grant_premium(1)
    prem = [k for t in season.season_view(1)["tiers"] for k in t["tracks"]
            if k["track"] == "premium"]
    assert all(k["status"] == "ready" for k in prem), "ซื้อสายแล้วช่องพรีเมียมต้องกดรับได้"


def test_the_embed_is_built_from_the_same_view():
    """ห้ามคำนวณสถานะช่องซ้ำสองที่ — เคยพลาดจนเว็บโชว์ไม่ตรงกับดิส"""
    import inspect
    src = inspect.getsource(season.build_season_embed)
    assert "season_view(" in src, "เอมเบดในดิสไม่ได้อ่านจาก season_view()"
    assert "claimed" not in src, "เอมเบดยังคำนวณเองว่าช่องไหนรับแล้ว"


def test_the_web_serves_the_view_untouched():
    api = __import__("pathlib").Path("license_server/web_api.py").read_text(encoding="utf-8")
    assert "return season.season_view(uid)" in api, "เว็บไม่ได้ส่ง season_view ตรง ๆ"


def test_the_menu_has_one_season_button_not_two():
    """เดิมมีปุ่ม 'ซีซั่นพาส' กับ 'สายพรีเมียม' แยกกัน ทั้งที่กดแล้วไปหน้าเดียวกัน"""
    html = __import__("pathlib").Path("license_server/web_static/play.html").read_text(encoding="utf-8")
    # data-go มีเฉพาะบนปุ่มเมนู นับทั้งไฟล์ได้เลย
    assert html.count('data-go="season"') == 1, "ยังมีปุ่มซีซั่นพาสซ้ำกันอยู่"
