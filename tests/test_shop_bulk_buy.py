"""🛒 ซื้อทีละหลายชิ้น + 🧪 ยาฮีลหลายขนาด

จุดที่ต้องไม่พลาด: ซื้อหลายชิ้นต้องเป็น "ได้ทั้งกองหรือไม่ได้เลย"
ห้ามมีสภาพหักเงินไปแล้วแต่ของไม่ครบ หรือได้ของแต่เงินไม่ถูกหัก
"""
import json
import pathlib

import pytest

import bot.models.player_model as pm
from bot import config_loader
from bot.cogs.player_commands import MAX_BUY_AT_ONCE, buy_item_for
from tests import conftest

UID = 9001
API = conftest.web_api_source()
PLAY = conftest.play_js_source()
HTML = pathlib.Path("license_server/web_static/play.html").read_text(encoding="utf-8")
VIEWS = pathlib.Path("bot/views/game_views.py").read_text(encoding="utf-8")

POTION = "1"        # 💉 ยาฮีล — ของถูกที่สุดในร้าน ใช้ทดสอบสะดวก


@pytest.fixture
def world(tmp_path, monkeypatch):
    monkeypatch.setattr(pm, "DB_NAME", str(tmp_path / "s.db"))
    pm.init_db()
    pm.get_player(UID)
    pm.update_player_fields(UID, {"cash": 100000, "inventory": [], "capacity": 20})
    return int(config_loader.get_item_config(POTION)["buy"])


def _bag():
    return pm.load_inventory(pm.get_player(UID)["inventory"])


def test_buying_many_charges_for_many(world):
    price = world
    ok, msg = buy_item_for(UID, POTION, 10)
    assert ok and _bag().count(POTION) == 10
    assert pm.get_player(UID)["cash"] == 100000 - price * 10
    assert "×10" in msg, "ข้อความไม่ได้บอกว่าซื้อกี่ชิ้น"


def test_buying_one_still_works_the_old_way(world):
    price = world
    ok, msg = buy_item_for(UID, POTION)
    assert ok and _bag() == [POTION]
    assert pm.get_player(UID)["cash"] == 100000 - price
    assert "×" not in msg, "ซื้อชิ้นเดียวไม่ต้องมีป้ายจำนวน"


def test_not_enough_gold_buys_nothing_at_all(world):
    price = world
    pm.update_player_field(UID, "cash", price * 3)
    ok, msg = buy_item_for(UID, POTION, 10)
    assert not ok and _bag() == [], "ซื้อไม่สำเร็จแต่ของเข้ากระเป๋า"
    assert pm.get_player(UID)["cash"] == price * 3, "ซื้อไม่สำเร็จแต่เงินหาย"
    assert "10 ชิ้น" in msg and f"{price * 10:,}" in msg, "ต้องบอกยอดรวมที่ต้องใช้"


def test_a_full_bag_buys_nothing_at_all(world):
    pm.update_player_fields(UID, {"capacity": 5, "inventory": [POTION, POTION]})
    ok, msg = buy_item_for(UID, POTION, 10)
    assert not ok and len(_bag()) == 2
    assert pm.get_player(UID)["cash"] == 100000, "กระเป๋าไม่พอแต่เงินโดนหัก"
    assert "เหลือที่ว่าง 3 ช่อง" in msg, "ต้องบอกว่าเหลือที่ว่างเท่าไหร่"


def test_buying_exactly_the_remaining_room_is_allowed(world):
    pm.update_player_fields(UID, {"capacity": 5, "inventory": [POTION, POTION]})
    assert buy_item_for(UID, POTION, 3)[0], "เหลือ 3 ช่อง ซื้อ 3 ชิ้นต้องได้"
    assert len(_bag()) == 5


@pytest.mark.parametrize("bad", [0, -5, "abc", None])
def test_a_junk_count_never_costs_more_than_one(world, bad):
    """เลขแปลก ๆ ต้องไม่กลายเป็นซื้อกองใหญ่ — อย่างมากคือ 1 ชิ้น หรือปฏิเสธไปเลย"""
    price = world
    ok, _msg = buy_item_for(UID, POTION, bad)
    spent = 100000 - pm.get_player(UID)["cash"]
    assert spent <= price, f"count={bad!r} แล้วโดนหัก {spent}"
    assert len(_bag()) <= 1


def test_the_count_is_capped(world):
    ok, _ = buy_item_for(UID, POTION, 10 ** 9)
    assert len(_bag()) <= MAX_BUY_AT_ONCE, "จำนวนไม่ถูกจำกัด กระเป๋า/เงินหายรวดเดียวได้"


def test_the_web_passes_the_count_through_to_the_shared_rule():
    assert "count: int = 1" in API, "API ไม่รับจำนวน"
    assert "buy_item_for(int(uid), body.item_id, body.count)" in API
    assert "count: count" in PLAY, "หน้าเว็บไม่ได้ส่งจำนวนไป"
    block = PLAY[PLAY.index("async function shopAction("):]
    assert "askNumber(" in block[:1400], "ซื้อของบนเว็บต้องถามจำนวนก่อน"


def test_discord_can_also_buy_many():
    """ดิสต้องซื้อหลายชิ้นได้ด้วย ไม่งั้นสองแพลตฟอร์มเล่นไม่เหมือนกัน"""
    assert "class BuyCountModal" in VIEWS, "ดิสยังไม่มีช่องกรอกจำนวน"
    assert "buy_item_for(self.user_id, item_id, count)" in VIEWS


# ── 🧪 ยาฮีลหลายขนาด ──

def test_there_is_a_bigger_potion_than_the_basic_one():
    heals = sorted((int(v["effect_amount"]), int(v["buy"]), k, v["name"])
                   for k, v in config_loader.get_all_items().items()
                   if v.get("effect") == "heal")
    assert len(heals) >= 2, "มียาฮีลขนาดเดียว — ผู้เล่นขอยาที่แรงกว่าปกติ"
    small, big = heals[0], heals[-1]
    assert big[0] > small[0] * 2, "ยาใหญ่ต้องฮีลแรงกว่ายาปกติชัดเจน"
    assert big[1] > small[1], "ยาที่ฮีลแรงกว่าต้องแพงกว่า"


def test_bigger_potions_are_worth_the_bag_slot():
    """ซื้อยาใหญ่แล้วต้องคุ้มกว่าซื้อยาเล็กหลายขวด ไม่งั้นไม่มีใครซื้อ"""
    heals = sorted((int(v["effect_amount"]), int(v["buy"]))
                   for k, v in config_loader.get_all_items().items()
                   if v.get("effect") == "heal")
    rates = [buy / amt for amt, buy in heals]
    assert rates == sorted(rates, reverse=True) or rates[-1] <= rates[0], \
        f"ยาใหญ่แพงต่อ HP กว่ายาเล็ก: {rates}"


def test_every_heal_potion_can_be_bought_and_used():
    for k, v in config_loader.get_all_items().items():
        if v.get("effect") != "heal":
            continue
        assert v.get("purchasable", True), f"{v['name']} ซื้อไม่ได้"
        assert v.get("type") == "use", f"{v['name']} กดใช้ไม่ได้"
        assert int(v["buy"]) > int(v["sell"]), f"{v['name']} ซื้อถูกกว่าขาย = ปั๊มเงิน"


def test_the_shipped_config_has_them_too():
    ex = json.loads(pathlib.Path("config.example.json").read_text(encoding="utf-8"))
    heals = [v for v in ex["item_catalog"]["items"].values() if v.get("effect") == "heal"]
    assert len(heals) >= 2, "แม่แบบ config ยังมียาฮีลขนาดเดียว"


# ── ป้ายบนปุ่ม ──

def test_the_adventure_tile_no_longer_says_it_is_a_demo():
    for stale in ("ทดลองฉาก", "เฟส 4", "เฟส 5"):
        assert stale not in HTML, f"ยังมีป้ายค้างจากตอนพัฒนา: {stale}"
