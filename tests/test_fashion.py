"""👗 แฟชั่น — เปลี่ยนแค่หน้าตา ห้ามแตะค่าต่อสู้แม้แต่นิดเดียว

ถ้าแฟชั่นบวกค่าได้เมื่อไหร่ กาชาแฟชั่นจะกลายเป็นการขายพลังด้วยเงินทันที
เทสไฟล์นี้จึงคุมข้อนั้นเป็นหลัก
"""
import json
import pathlib
import re

import pytest

import bot.models.player_model as pm
from bot import fashion
from tests import conftest

UID = 8801
SPRITE = pathlib.Path("license_server/web_static/sprite.js").read_text(encoding="utf-8")
API = conftest.web_api_source()


@pytest.fixture
def world(tmp_path, monkeypatch):
    monkeypatch.setattr(pm, "DB_NAME", str(tmp_path / "f.db"))
    pm.init_db()
    pm.get_player(UID)
    pm.update_player_fields(UID, {"armor": "Steel_H", "armor_dur": 80,
                                  "weapon": "Iron_Weapon", "weapon_dur": 100,
                                  "hp": 300, "max_hp": 400, "level": 30,
                                  # ได้มาจากกาชาแล้ว — เทสชุดนี้สนใจเรื่องใส่/ถอด ไม่ใช่ที่มา
                                  "fashion_owned": json.dumps(sorted(fashion.CATALOG))})
    return None


# ── กติกาเหล็ก: ห้ามกระทบค่าต่อสู้ ──

COMBAT_FIELDS = ("armor", "armor_dur", "weapon", "weapon_dur", "hp", "max_hp",
                 "level", "exp", "cash", "bank", "artifact_slots", "pet", "status_effects")


def _snapshot():
    p = pm.get_player(UID)
    return {k: p.get(k) for k in COMBAT_FIELDS}


def test_wearing_fashion_changes_nothing_that_matters(world):
    before = _snapshot()
    for key in fashion.CATALOG:
        assert fashion.wear(UID, key)[0]
    assert _snapshot() == before, "ใส่แฟชั่นแล้วค่าต่อสู้เปลี่ยน — กลายเป็นขายพลัง"


def test_taking_fashion_off_changes_nothing_either(world):
    for key in fashion.CATALOG:
        fashion.wear(UID, key)
    before = _snapshot()
    for slot in fashion.SLOTS:
        fashion.take_off(UID, slot)
    assert _snapshot() == before


def test_the_real_gear_is_still_the_real_gear(world):
    """ใส่ชุดแฟชั่นทับ แต่เกราะเหล็กที่ใส่อยู่ต้องยังเป็นเกราะเหล็ก"""
    fashion.wear(UID, "dark_cloak")
    p = pm.get_player(UID)
    assert p["armor"] == "Steel_H" and p["armor_dur"] == 80
    assert p["weapon"] == "Iron_Weapon"


def test_the_dice_roll_is_untouched(world, monkeypatch):
    """ทอยเต๋าด้วยเมล็ดเดียวกัน ใส่แฟชั่นหรือไม่ใส่ต้องได้ผลเท่ากันเป๊ะ"""
    import random

    from bot import adventure_core as ac

    def roll():
        rng = random.Random(1234)
        p = pm.get_player(UID)
        return [ac.roll_player_die(rng, False) for _ in range(20)], ac.player_dice_count(p)

    plain = roll()
    for key in fashion.CATALOG:
        fashion.wear(UID, key)
    assert roll() == plain, "ใส่แฟชั่นแล้วเต๋าเปลี่ยน"


# ── มีของจริงถึงใส่ได้ ──

def test_you_cannot_wear_what_you_do_not_own(world, monkeypatch):
    monkeypatch.setattr(fashion, "_starter_sets_free", lambda: False)
    pm.update_player_field(UID, "fashion_owned", "[]")
    ok, msg = fashion.wear(UID, "light_knight")
    assert not ok and "ยังไม่มี" in msg


def test_owning_it_lets_you_wear_it(world, monkeypatch):
    monkeypatch.setattr(fashion, "_starter_sets_free", lambda: False)
    pm.update_player_field(UID, "fashion_owned", json.dumps(["light_knight"]))
    assert fashion.wear(UID, "light_knight")[0]
    assert not fashion.wear(UID, "dark_cloak")[0], "มีชิ้นเดียวแต่ใส่ชิ้นอื่นได้"


def test_a_made_up_key_is_refused(world):
    assert not fashion.wear(UID, "ไม่มีจริง")[0]
    assert not fashion.wear(UID, "")[0]


def test_each_slot_holds_one_piece(world):
    """ใส่ชุดใหม่ทับชุดเดิมในช่องเดียวกัน ไม่ใช่ใส่ซ้อนกัน"""
    fashion.wear(UID, "light_knight")
    fashion.wear(UID, "dark_cloak")
    assert fashion.worn(pm.get_player(UID))["outfit"] == "dark_cloak"


def test_slots_are_independent(world):
    """ชุดสายแสง + อาวุธสายมืด = ใส่ปนกันได้ตามใจ"""
    fashion.wear(UID, "light_knight")
    fashion.wear(UID, "dark_scythe")
    on = fashion.worn(pm.get_player(UID))
    assert on["outfit"] == "light_knight" and on["weapon"] == "dark_scythe"


def test_junk_in_the_database_never_breaks_the_wardrobe(world):
    for junk in ('{"outfit": "ของปลอม"}', "ไม่ใช่ json", "", '{"outfit": "light_blade"}'):
        pm.update_player_field(UID, "fashion", junk)
        on = fashion.worn(pm.get_player(UID))
        assert set(on) == set(fashion.SLOTS), f"ข้อมูลเสีย {junk!r} แล้วตู้พัง"
        assert not on["outfit"], "รหัสผิดช่อง/ไม่มีจริง ต้องถือว่าไม่ได้ใส่"


# ── ตัววาดต้องมีของครบตามตู้ ──

def test_every_catalog_entry_has_something_to_draw():
    """รหัสในตู้ต้องมีตารางสีใน sprite.js ไม่งั้นใส่แล้วตัวละครหาย"""
    tables = {"outfit": "FASHION_OUTFIT", "weapon": "FASHION_WEAPON", "aura": "FASHION_AURA"}
    for slot, name in tables.items():
        block = SPRITE[SPRITE.index(f"const {name} = {{"):]
        block = block[:block.index("\n};")]
        keys = set(re.findall(r"^\s{2}(\w+):", block, re.M))
        want = {k for k, v in fashion.CATALOG.items() if v["slot"] == slot}
        assert want <= keys, f"{name} ขาด: {sorted(want - keys)}"


def test_the_painter_never_reads_real_gear_stats():
    """ตัววาดต้องแตะแค่ 'หน้าตา' — ห้ามไปอ่านค่าป้องกัน/ดาเมจมาคำนวณอะไร"""
    fn = SPRITE[SPRITE.index("function drawCharacter("):SPRITE.index("function drawWeapon(")]
    for banned in ("hp", "damage", "defense", "dur"):
        assert banned not in fn.lower().replace("drawcharacter", ""), \
            f"ตัววาดไปยุ่งกับค่า {banned}"


def test_fashion_rides_along_with_the_character_everywhere():
    """ทุกที่ที่วาดตัวละครต้องเห็นแฟชั่น — ส่งไปกับ CHAR ก้อนเดียว"""
    play = pathlib.Path("license_server/web_static/play.js").read_text(encoding="utf-8")
    assert "fashion: g.fashion || {}" in play, "ตัวละครหลักไม่ได้พกแฟชั่นไปด้วย"
    assert '"fashion": _fashion.worn(p)' in API, "API ไม่ได้ส่งแฟชั่นที่ใส่อยู่มา"


# ── ที่มาของแฟชั่น ──

def test_fashion_comes_from_gacha_only():
    """ไม่มีร้านขายตรง — เจ้าของเกมเคาะว่าได้จากกาชาเท่านั้น"""
    html = pathlib.Path("license_server/web_static/play.html").read_text(encoding="utf-8")
    assert "ร้านแฟชั่น" not in html
    assert "กาชาแฟชั่น" in html


def test_the_starter_giveaway_can_be_switched_off(world, monkeypatch):
    """เคยแจกให้ลองใส่ตอนกาชายังไม่เสร็จ — กาชาเปิดแล้วสวิตช์นี้ต้องปิดของฟรีได้จริง"""
    pm.update_player_field(UID, "fashion_owned", "[]")
    monkeypatch.setattr(fashion, "_starter_sets_free", lambda: True)
    assert fashion.owned(pm.get_player(UID)) == set(fashion.CATALOG)
    monkeypatch.setattr(fashion, "_starter_sets_free", lambda: False)
    assert fashion.owned(pm.get_player(UID)) == set()


def test_both_launch_themes_are_complete():
    """สายแสงกับสายมืดต้องมีครบทุกช่อง ไม่ใช่มีแต่ชุดไม่มีอาวุธ"""
    for theme in ("light", "dark"):
        got = {v["slot"] for v in fashion.CATALOG.values() if v["theme"] == theme}
        assert got == set(fashion.SLOTS), f"สาย {theme} ขาดช่อง: {set(fashion.SLOTS) - got}"
