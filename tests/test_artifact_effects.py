"""อาร์ติแฟกต์ต้องทำงานตามที่คำอธิบายบอก — เคสที่ผู้เล่นรายงาน 2026-08-01"""
import discord
import pytest

from bot import config_loader
from bot import game_modifiers as gm

CLOAK = "art_sylvan_cloak"
AMULET = "art_nether_amulet"
MONOCLE = "art_masquerade_monocle"


# ── 🧥 เสื้อคลุมเปลือกไม้: "ราก" มี 2 กลไก ต้องกันทั้งคู่ ──

def test_cloak_blocks_the_dice_lock_root():
    assert gm.has_status_flag({CLOAK: 1}, "block_root") is True
    assert gm.ELEMENTS["wood"]["root_chance"] > 0, "ถ้าธาตุไม้เลิกล็อกเต๋า เทสนี้ไม่มีความหมาย"


def test_cloak_also_blocks_the_entangle_status():
    """บั๊กที่ผู้เล่นเจอ: มอนธาตุไม้ตีติด 🌱 รากไม้พันธนาการ แล้วเสื้อคลุมกันไม่ได้"""
    after = gm.apply_status({CLOAK: 1}, "entangled")
    assert "entangled" not in after, "เสื้อคลุมต้องกันรากพันธนาการด้วย ไม่ใช่แค่ล็อกเต๋า"
    assert gm.ELEMENTS["wood"]["on_hit_status"]["key"] == "entangled", \
        "ถ้ามอนไม้เลิกตีติดราก เทสนี้ไม่มีความหมาย"


def test_wearing_the_cloak_shakes_off_an_active_root():
    rooted = {"entangled": 3}
    assert "entangled" not in gm.apply_status(rooted, CLOAK)


def test_cloak_still_softens_step_damage():
    import random
    total, _ = gm.roll_step_damage({"poison": 10, CLOAK: 1}, rng=random.Random(1))
    plain, _ = gm.roll_step_damage({"poison": 10}, rng=random.Random(1))
    assert total < plain, "ผลลดเลือดไหลเดิมต้องไม่หายไป"


# ── 📿 สร้อยเนเธอร์ + 🎭 แว่นหน้ากาก: ทำงานถูก แต่มีเงื่อนไข ──

def test_amulet_converts_drain_where_drain_exists():
    pct = max((gm.STATUS_EFFECTS[k].get("hp_drain_heal", 0) for k in {AMULET: 1}), default=0)
    assert pct > 0
    drains = [k for k, c in gm.CONTINENTS.items() if (c.get("mods") or {}).get("combat_hp_drain")]
    assert drains, "ไม่มีทวีปไหนมี Life Drain เลย = สร้อยไร้ประโยชน์ถาวร"


def test_monocle_flag_and_its_only_use_site():
    assert gm.has_status_flag({MONOCLE: 1}, "free_inspect") is True
    masq = [t for t in gm.WEEKLY_THEMES if (t.get("mods") or {}).get("masquerade")]
    assert masq, "ไม่มีธีมหน้ากากแล้ว = แว่นไร้ที่ใช้"


@pytest.mark.parametrize("key", [AMULET, MONOCLE])
def test_conditional_artifacts_say_their_condition(key):
    """ของที่ใช้ได้เฉพาะบางที่ ต้องเขียนเงื่อนไขในคำอธิบาย ไม่งั้นผู้เล่นคิดว่าพัง"""
    desc = gm.STATUS_EFFECTS[key]["desc"]
    assert any(w in desc for w in ("เฉพาะ", "อยู่ทวีป")), \
        f"{gm.STATUS_EFFECTS[key]['label']} ใช้ได้เฉพาะบางสถานการณ์ แต่คำอธิบายไม่บอก: {desc}"


# ── ปุ่มเมนูต้องไม่พังเงียบ ──

def test_menu_view_reports_errors():
    from bot.views.menu_view import GameMenuView
    assert "on_error" in vars(GameMenuView), \
        "GameMenuView ต้องมี on_error ไม่งั้นปุ่มพังแล้วขึ้นแค่ 'interaction failed' ตามหาสาเหตุไม่ได้"


def test_every_menu_button_is_persistent():
    from bot.views.menu_view import GameMenuView
    v = GameMenuView()
    assert v.is_persistent(), "เมนูต้อง persistent ไม่งั้นปุ่มตายหลังบอทรีสตาร์ท"
    for b in v.children:
        assert getattr(b, "custom_id", None), f"ปุ่ม {b.label} ไม่มี custom_id — add_view จะพังทั้งชุด"
