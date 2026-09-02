"""🛒 ร้านขายยศ + กาชา (เว็บเกม เฟส 7)

จุดที่ต่างจากระบบอื่น: เว็บแจกยศ Discord เองไม่ได้ ต้องผ่านคิวให้บอทแจก
เงินถูกหักตั้งแต่ตอนกด ถ้าแจกไม่สำเร็จ "ต้องคืนเงินเสมอ" — นั่นคือสิ่งที่เทสชุดนี้คุม
"""
import pathlib
import random

import pytest

import bot.models.player_model as pm
from bot import config_loader, role_shop_core

DARK = [{"value": "d1", "label": "👹 ปีศาจน้อย", "role_id": 111, "price": 5_000_000},
        {"value": "d2", "label": "💀 เนโครแมนเซอร์", "role_id": 222, "price": 20_000_000},
        {"value": "d3", "label": "🔥 ราชาไฟ", "role_id": 333, "price": 20_000_000}]
LIGHT = [{"value": "l1", "label": "🕊️ นักบุญ", "role_id": 444, "price": 20_000_000}]


@pytest.fixture
def shop(monkeypatch):
    p = {"user_id": 1, "cash": 100_000_000}
    monkeypatch.setattr(pm, "get_player", lambda uid: dict(p))
    monkeypatch.setattr(pm, "increment_player_field",
                        lambda uid, f, v: p.__setitem__(f, p.get(f, 0) + v))
    monkeypatch.setattr(config_loader, "get_trade_roles",
                        lambda f: DARK if f == "dark" else LIGHT)
    monkeypatch.setattr(config_loader, "get_gacha_price", lambda: 10_000_000)
    monkeypatch.setattr(config_loader, "get_gacha_pool_price", lambda: 20_000_000)
    return p


# ── ตู้กาชา ───────────────────────────────────────────────────────────────────

def test_only_rare_roles_go_into_the_gacha_pool(shop):
    """ตู้คัดด้วยราคาตามที่ตั้งไว้ — ยศถูกต้องไม่หลุดเข้าตู้"""
    pool = {r["value"] for r in role_shop_core.gacha_pool("dark")}
    assert pool == {"d2", "d3"}, "ยศราคา 5 ล้านไม่ควรอยู่ในตู้"


def test_spinning_charges_the_spin_price_not_the_role_price(shop):
    ok, data = role_shop_core.prepare_gacha(1, "dark", rng=random.Random(0))
    assert ok and shop["cash"] == 90_000_000
    assert data["price"] == 10_000_000, "จ่ายค่าหมุน ไม่ใช่ราคายศ"
    assert data["kind"] == "gacha" and data["role_id"] in (222, 333)


def test_spinning_without_money_charges_nothing(shop):
    shop["cash"] = 1
    ok, data = role_shop_core.prepare_gacha(1, "dark")
    assert not ok and "ไม่พอ" in data["error"] and shop["cash"] == 1


def test_an_empty_gacha_cabinet_never_takes_your_money(shop, monkeypatch):
    """แอดมินยังไม่ได้ตั้งยศเข้าตู้ = ต้องไม่หักเงินแล้วปล่อยว่าง"""
    monkeypatch.setattr(config_loader, "get_gacha_pool_price", lambda: 999)
    ok, data = role_shop_core.prepare_gacha(1, "dark")
    assert not ok and shop["cash"] == 100_000_000


# ── ซื้อเจาะจง ────────────────────────────────────────────────────────────────

def test_buying_charges_exactly_the_listed_price(shop):
    ok, data = role_shop_core.prepare_buy(1, "dark", "d1")
    assert ok and shop["cash"] == 95_000_000 and data["role_id"] == 111


def test_buying_something_that_does_not_exist_charges_nothing(shop):
    ok, data = role_shop_core.prepare_buy(1, "dark", "ไม่มียศนี้")
    assert not ok and shop["cash"] == 100_000_000


def test_buying_across_factions_uses_the_right_list(shop):
    ok, data = role_shop_core.prepare_buy(1, "light", "l1")
    assert ok and data["role_id"] == 444
    assert not role_shop_core.prepare_buy(1, "dark", "l1")[0], "ยศฝ่ายแสงต้องไม่โผล่ในร้านมืด"


def test_refund_puts_the_money_back(shop):
    role_shop_core.prepare_buy(1, "dark", "d1")
    role_shop_core.refund(1, 5_000_000)
    assert shop["cash"] == 100_000_000


# ── หน้าร้านพร้อมแสดงผล ───────────────────────────────────────────────────────

def test_shop_view_is_ready_to_render(shop):
    v = role_shop_core.shop_view("dark", 1)
    assert [r["label"] for r in v["roles"]] == [r["label"] for r in DARK]
    assert v["gacha"]["price"] == 10_000_000 and v["gacha"]["pool_size"] == 2
    assert v["cash"] == 100_000_000


# ── สะพานแจกยศ (คิว) ─────────────────────────────────────────────────────────

def test_the_queue_table_carries_everything_needed_for_a_refund():
    """ถ้าคิวไม่เก็บราคาไว้ ตอนแจกพลาดจะคืนเงินไม่ได้"""
    schema = pathlib.Path("license_server/web_db.py").read_text(encoding="utf-8")
    block = schema[schema.index("role_grant_queue"):schema.index("idx_grant_pending")]
    for col in ("discord_id", "role_id", "label", "price", "kind", "status"):
        assert col in block, f"คิวไม่มีคอลัมน์ {col}"


def test_the_worker_refunds_on_every_failure_path():
    """ทุกทางที่แจกยศไม่สำเร็จต้องคืนเงิน — ไม่งั้นผู้เล่นเสียเงินฟรี"""
    src = pathlib.Path("bot/apps/bot_worker/role_grant_worker.py").read_text(encoding="utf-8")
    body = src[src.index("async def _grant("):src.index("@drain.before_loop")]
    fails = body.count('return "refunded"')
    assert fails >= 3, f"ทางที่คืนเงินมีแค่ {fails} จุด — ควรครอบคลุมทุกกรณีพัง"
    assert body.count("role_shop_core.refund(uid, price)") >= fails


def test_a_duplicate_gacha_is_salt_not_a_refund():
    """กาชาได้ของซ้ำคือความเสี่ยงที่ผู้เล่นรับไปแล้ว — ห้ามคืนเงิน
    แต่ 'ซื้อเจาะจง' แล้วซ้ำต้องคืน เพราะตั้งใจซื้อของที่ยังไม่มี"""
    src = pathlib.Path("bot/apps/bot_worker/role_grant_worker.py").read_text(encoding="utf-8")
    dup = src[src.index("if role_obj in member.roles:"):src.index("await member.add_roles")]
    assert 'if kind == "gacha"' in dup and 'return "duplicate"' in dup
    assert "role_shop_core.refund" in dup, "ซื้อเจาะจงแล้วซ้ำต้องคืนเงิน"


def test_both_platforms_share_the_same_money_logic():
    cog = pathlib.Path("bot/cogs/role_shop.py").read_text(encoding="utf-8")
    api = pathlib.Path("license_server/web_api.py").read_text(encoding="utf-8")
    for fn in ("prepare_buy", "prepare_gacha"):
        assert f"role_shop_core.{fn}(" in cog, f"ดิสยังไม่ได้เรียก {fn}"
        assert f"role_shop_core.{fn}(" in api, f"เว็บยังไม่ได้เรียก {fn}"


def test_the_web_never_tries_to_grant_roles_itself():
    """เว็บแจกยศ Discord ไม่ได้ — ต้องผ่านคิวเท่านั้น"""
    api = pathlib.Path("license_server/web_api.py").read_text(encoding="utf-8")
    block = api[api.index("def roleshop_buy("):]
    assert "_queue_grant(uid, data)" in block
    assert "add_roles" not in block


def test_the_gacha_page_waits_for_the_bot_before_celebrating():
    """ยศยังไม่ถึงมือจนกว่าบอทจะแจก — หน้าเว็บต้องรอผลจริงก่อนขึ้นแจ็คพอต"""
    js = pathlib.Path("license_server/web_static/play.js").read_text(encoding="utf-8")
    assert "waitTicket(res.ticket)" in js
    assert "แจ็คพอตแตก" in js and "เกลือ" in js
