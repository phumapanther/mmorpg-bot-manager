"""🛒 ตลาดผู้เล่น + 🗺️ สรุปทุกทวีป บนเว็บ

ตลาดแตะเงินกับของจริง เทสชุดนี้จึงคุม "ทางโกง" เป็นหลัก ไม่ใช่แค่ว่าหน้าโหลดขึ้น
"""
import pathlib
import re

import pytest

import bot.models.player_model as pm
from bot import market
from tests import conftest

API = conftest.web_api_source()
PLAY = conftest.play_js_source()
HTML = pathlib.Path("license_server/web_static/play.html").read_text(encoding="utf-8")

SELLER, BUYER = 101, 202


@pytest.fixture
def world(tmp_path, monkeypatch):
    monkeypatch.setattr(pm, "DB_NAME", str(tmp_path / "m.db"))
    pm.init_db()
    for uid in (SELLER, BUYER):
        pm.get_player(uid)
    pm.update_player_fields(SELLER, {"inventory": ["1", "1"], "cash": 0, "bank": 0, "capacity": 20})
    pm.update_player_fields(BUYER, {"inventory": [], "cash": 100000, "bank": 0, "capacity": 20})
    return None


# ── ทางโกงที่ต้องปิดให้หมด ──

def test_you_cannot_sell_what_you_do_not_have(world):
    ok, msg = market.list_item(SELLER, "9999", 500)
    assert not ok and "ไม่มีไอเทม" in msg


def test_listing_takes_the_item_out_of_the_bag_immediately(world):
    """ถ้าของยังอยู่ในกระเป๋าระหว่างประกาศขาย = ขายแล้วยังใช้ได้ = ปั๊มของ"""
    ok, _ = market.list_item(SELLER, "1", 500)
    assert ok
    assert pm.load_inventory(pm.get_player(SELLER)["inventory"]).count("1") == 1


def test_you_cannot_buy_your_own_listing(world):
    market.list_item(SELLER, "1", 500)
    lid = market.my_listings(SELLER)[0][0]
    ok, msg = market.buy_listing(SELLER, lid)
    assert not ok and "ของตัวเอง" in msg


def test_a_listing_can_only_be_sold_once(world):
    """สองคนกดซื้อพร้อมกัน คนที่สองต้องไม่ได้ของและไม่เสียเงิน"""
    market.list_item(SELLER, "1", 500)
    lid = market.my_listings(SELLER)[0][0]
    assert market.buy_listing(BUYER, lid)[0]
    cash_after = pm.get_player(BUYER)["cash"]
    ok, msg = market.buy_listing(BUYER, lid)
    assert not ok and pm.get_player(BUYER)["cash"] == cash_after, "ซื้อซ้ำแล้วโดนหักเงินอีกรอบ"


def test_only_the_owner_can_cancel(world):
    market.list_item(SELLER, "1", 500)
    lid = market.my_listings(SELLER)[0][0]
    ok, msg = market.cancel_listing(BUYER, lid)
    assert not ok and "ของตัวเอง" in msg


def test_cancelling_always_returns_the_item(world):
    market.list_item(SELLER, "1", 500)
    lid = market.my_listings(SELLER)[0][0]
    assert market.cancel_listing(SELLER, lid)[0]
    assert pm.load_inventory(pm.get_player(SELLER)["inventory"]).count("1") == 2


def test_the_money_lands_where_it_should(world, monkeypatch):
    """ผู้ซื้อจ่ายจากเงินสด · ผู้ขายรับเข้าธนาคาร (ตายแล้วไม่หาย) · หักภาษีจากผู้ขายเท่านั้น"""
    from bot import config_loader
    monkeypatch.setattr(config_loader, "get_config",
                        lambda: {"market": {"enabled": True, "tax_percent": 10, "min_price": 1}})
    market.list_item(SELLER, "1", 1000)
    lid = market.my_listings(SELLER)[0][0]
    assert market.buy_listing(BUYER, lid)[0]
    assert pm.get_player(BUYER)["cash"] == 99000, "หักเงินผู้ซื้อไม่ตรงราคา"
    assert pm.get_player(SELLER)["bank"] == 900, "ผู้ขายควรได้ราคาหักภาษี 10%"
    assert pm.get_player(SELLER)["cash"] == 0, "เงินขายต้องเข้าธนาคาร ไม่ใช่เงินสด"


def test_a_full_bag_blocks_the_purchase(world):
    market.list_item(SELLER, "1", 500)
    lid = market.my_listings(SELLER)[0][0]
    pm.update_player_fields(BUYER, {"capacity": 1, "inventory": ["1"]})
    ok, msg = market.buy_listing(BUYER, lid)
    assert not ok and "กระเป๋าเต็ม" in msg
    assert pm.get_player(BUYER)["cash"] == 100000, "ซื้อไม่สำเร็จแต่เงินหาย"


# ── เว็บต้องไม่แตะเงิน/ของเอง ──

def test_the_web_only_calls_the_shared_market_module():
    block = API[API.index("def market_action("):API.index("def market_action(") + 1400]
    for fn in ("market.list_item(", "market.cancel_listing(", "market.buy_listing("):
        assert fn in block, f"เว็บไม่ได้เรียก {fn}"
    for danger in ("UPDATE players", "cash =", "inventory ="):
        assert danger not in block, f"เว็บแตะข้อมูลเอง: {danger}"
    assert "_user_lock(uid)" in block, "ไม่ได้ล็อกผู้ใช้ระหว่างทำรายการ"


def test_the_web_never_leaks_who_the_seller_is():
    """หน้าเว็บไม่มีเหตุผลต้องรู้ไอดี Discord ของคนอื่น"""
    block = API[API.index("def market_list("):API.index("class MarketBody")]
    assert '"seller_id"' not in block and "seller_id" not in PLAY
    assert '"mine": sid == uid' in block, "ต้องบอกแค่ว่าเป็นแผงของเราไหม"


def test_selling_asks_for_a_price_before_doing_anything():
    fn = PLAY[PLAY.index("async function marketSell("):]
    assert "askNumber(" in fn[:900], "ลงขายต้องถามราคาก่อน"
    assert "ของจะออกจากกระเป๋าทันที" in fn[:900], "ต้องเตือนว่าของออกจากกระเป๋าทันที"


def test_buying_and_cancelling_ask_first():
    for fn in ("marketBuy", "marketCancel"):
        block = PLAY[PLAY.index(f"async function {fn}("):]
        assert "confirmAction(" in block[:700], f"{fn} ไม่ได้ถามยืนยัน"


# ── 🗺️ สรุปทุกทวีป ──

def test_the_atlas_covers_every_continent_in_the_game():
    from bot.game_data import CONTINENTS
    block = API[API.index("def continents_summary("):API.index('@router.get("/codex")')]
    assert "for key, c in CONTINENTS.items()" in block, "ต้องไล่จากทวีปจริงทั้งหมด ไม่ใช่ลิสต์ที่พิมพ์เอง"
    assert len(CONTINENTS) == 9
    for field in ("elements", "monsters", "specials", "mult", "killed"):
        assert f'"{field}"' in block, f"สรุปทวีปไม่มี {field}"


def test_the_atlas_reads_the_numbers_actually_used_in_play():
    """ตัวคูณที่โชว์ต้องมาจาก mods ชุดเดียวกับตอนเดินจริง ไม่ใช่พิมพ์ค่าไว้เอง"""
    block = API[API.index("def continents_summary("):API.index('@router.get("/codex")')]
    for k in ("monster_hp_mult", "monster_gold_mult", "monster_exp_mult"):
        assert k in block, f"ไม่ได้อ่าน {k} จาก mods"


# ── ปุ่มเมนู ──

def test_the_three_buttons_are_wired_up():
    for panel, fn in (("atlas", "fillAtlas"), ("market", "fillMarket")):
        assert f'id="v-{panel}"' in HTML, f"ไม่มีแผง {panel}"
        assert f'data-go="{panel}"' in HTML, f"ไม่มีปุ่มเปิดแผง {panel}"
        assert f"if (id === '{panel}') {fn}(" in PLAY
    assert "advWalk(5)" in PLAY, "ไม่มีปุ่มเดินเร็ว ×5 บนเว็บ"


# ปุ่ม "เร็ว ๆ นี้" — โชว์ให้ผู้เล่นเห็นว่ากำลังจะมีอะไร แต่กดไม่ได้
# รายชื่อตรงกับ docs/plan-2026-08-15-future-systems.md
PLANNED_SOON = {
    "ครอบครัว", "เหรียญ",                                 # ระบบใหม่ที่วางแผนไว้
    "สะสมแฟชั่น",                                         # แฟชั่นแทรกเข้าหมวดเดิม (กาชาเปิดแล้ว)
    "ดวล 1v1", "ศึกกิลด์",                                # หมวด PVP (ซ้อมกับบอทเปิดแล้ว)
    "ไปต่างโลก",                                          # ยังไม่มีระบบในดิสเลย
}


def _soon_tiles():
    """ชื่อปุ่มที่ติดป้าย "เร็ว ๆ นี้" ทั้งหมด

    ⚠️ regex ต้องเผื่อ attribute หลัง class — ของเดิมจับ `class="g-tile soon">` เป๊ะ ๆ
    พอเพิ่ม disabled เข้าไปเลยจับไม่ได้สักปุ่ม เทสผ่านทั้งที่ไม่ได้ตรวจอะไรเลย
    """
    # \s+ กันไว้เพราะ IDE จัดรูปแบบใหม่แยก <button กับ class="..." ไปคนละบรรทัดได้
    return {s.strip() for s in re.findall(
        r'<button\s+class="g-tile soon"[^>]*>.*?<span class="ic">[^<]*</span>([^<]+)<', HTML, re.S)}


def test_only_the_unbuilt_button_is_left_marked_as_coming_later():
    """ปุ่มที่ติดป้ายต้องเป็นระบบที่วางแผนไว้จริง ไม่ใช่ของที่ทำเสร็จแล้วลืมเปิด"""
    tiles = _soon_tiles()
    assert tiles, "ไม่เจอปุ่มเร็ว ๆ นี้เลย — regex อ่านไม่ออกหรือเปล่า?"
    extra = tiles - PLANNED_SOON
    assert not extra, f"ปุ่มที่ติดป้ายเร็ว ๆ นี้แต่ไม่มีในแผน: {sorted(extra)}"


def test_the_teaser_buttons_really_cannot_be_clicked():
    """โชว์ให้เห็นว่ากำลังจะมี แต่ต้องกดไม่ได้จริง ไม่ใช่กดแล้วเงียบให้ผู้เล่นงง"""
    found = re.findall(r'<button\s+class="g-tile soon"([^>]*)>', HTML)
    assert len(found) == len(PLANNED_SOON), \
        f"เจอปุ่มเร็ว ๆ นี้ {len(found)} ปุ่ม แต่ในแผนมี {len(PLANNED_SOON)}"
    for attrs in found:
        assert "disabled" in attrs, f"ปุ่มเร็ว ๆ นี้ยังกดได้อยู่: {attrs.strip()[:70]}"
        assert "data-go" not in attrs, "ปุ่มเร็ว ๆ นี้ไม่ควรชี้ไปแผงไหน"
        assert "title=" in attrs, "ควรบอกด้วยว่าระบบนี้จะทำอะไรได้"


def test_every_planned_system_has_a_teaser_button():
    """ผู้เล่นควรเห็นครบว่ากำลังจะมีอะไรบ้าง — ขาดปุ่มไหนแปลว่าลืมใส่"""
    missing = PLANNED_SOON - _soon_tiles()
    assert not missing, f"ระบบที่วางแผนไว้แต่ยังไม่มีปุ่มโชว์: {sorted(missing)}"


def test_the_wardrobe_is_open_for_business():
    """👗 แฟชั่นเปิดใช้งานแล้ว — ต้องไม่ติดป้าย "เร็ว ๆ นี้" อีก"""
    assert 'data-go="fashion"' in HTML, "ไม่มีปุ่มเปิดตู้เสื้อผ้า"
    assert 'id="v-fashion"' in HTML, "ไม่มีแผงตู้เสื้อผ้า"
    assert 'data-go="fgacha"' in HTML, "ไม่มีปุ่มเปิดตู้กาชาแฟชั่น"
    assert 'id="v-fgacha"' in HTML, "ไม่มีแผงตู้กาชาแฟชั่น"
    assert "แฟชั่น" not in _soon_tiles(), "ตู้เสื้อผ้าใช้งานได้แล้วแต่ยังติดป้ายเร็ว ๆ นี้"
    assert "if (id === 'fashion') fillFashion(" in PLAY


def test_fashion_buttons_sit_in_the_right_sections():
    """แฟชั่นแทรกเข้าหมวดที่มันควรอยู่ ไม่ใช่กองรวมกันที่เดียว
    กาชา/ร้าน -> หมวดร้านค้า · คอลเลกชัน -> หมวดสะสม"""
    shop = HTML[HTML.index("<h3>ร้านค้า</h3>"):HTML.index("<h3>รางวัล</h3>")]
    assert "กาชาแฟชั่น" in shop, "กาชาแฟชั่นไม่ได้อยู่หมวดร้านค้า"
    assert "ร้านแฟชั่น" not in HTML, "แฟชั่นได้จากกาชาเท่านั้น ไม่ควรมีร้านขายตรง"

    books = HTML[HTML.index("<h3>คู่มือ · สมุดสะสม</h3>"):]
    assert "สะสมแฟชั่น" in books, "คอลเลกชันแฟชั่นไม่ได้อยู่หมวดสะสม"


def test_the_shop_section_is_not_just_for_roles_anymore():
    """เดิมชื่อ "ร้านค้ายศ" — พอมีร้านแฟชั่นด้วยแล้วชื่อเดิมทำให้เข้าใจผิด"""
    assert "<h3>ร้านค้ายศ</h3>" not in HTML, "ยังใช้ชื่อหมวดเดิมที่แคบเกินไป"
    assert "<h3>ร้านค้า</h3>" in HTML


def test_pet_evolution_is_announced_inside_the_pets_panel():
    """อีโวไม่ต้องมีปุ่มของตัวเอง — ไปบอกในแผงสัตว์เลี้ยงเลย
    คนที่เปิดแผงนี้คือคนที่สนใจสัตว์เลี้ยงอยู่แล้ว ตรงกลุ่มกว่าและเมนูหลักไม่รก"""
    panel = HTML[HTML.index('id="v-pets"'):HTML.index('id="v-daily"')]
    # เช็คหัวข้อตัวหนาโดยเฉพาะ ไม่ใช่แค่คำว่า "อีโว" ลอย ๆ
    # (คำนั้นโผล่ในวงเล็บอธิบายด้วย เช็คหลวม ๆ แล้วลบหัวข้อทิ้งก็ยังผ่าน)
    assert "<b>🧬 อีโวสัตว์เลี้ยง</b>" in panel, "แผงสัตว์เลี้ยงไม่ได้ประกาศระบบอีโว"
    assert 'class="tag-soon"' in panel, "ไม่ได้ติดป้ายว่ายังไม่เปิด"
    assert "อีโวสัตว์เลี้ยง" not in _soon_tiles(), "ไม่ควรมีปุ่มอีโวแยกในเมนูหลักแล้ว"
