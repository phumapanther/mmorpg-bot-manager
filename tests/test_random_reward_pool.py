"""🚫 ของที่ต้องหามาด้วยวิธีของมันเอง ห้ามหลุดออกมาเป็นของรางวัลสุ่ม

ผู้เล่นเจอว่าได้ 💠 สว่านเจาะรูอาร์ติแฟกต์ จากที่อื่นนอกจากบอสไร้พ่าย

ต้นเหตุ: NPC แลกของเลือกของรางวัลด้วย rng.choice() = สุ่มเท่า ๆ กันทุกชิ้น
และใช้ "ราคาขาย" เป็นค่าประเมิน — สว่านขายได้ 1 ทอง เลยติดโผของทุกดีล
ได้จากแลก NPC ราว 1.4% ต่อครั้ง ทั้งที่ควรได้จากบอสไร้พ่ายเท่านั้น
"""
import pytest

from bot import config_loader
from bot.adventure_core import NO_RANDOM_REWARD, _item_value, is_random_rewardable

ITEMS = config_loader.get_all_items()
DRILL = "67"


def _by_effect(effect):
    return [i for i, d in ITEMS.items() if d.get("effect") == effect]


def test_the_drill_is_boss_only():
    assert not is_random_rewardable(ITEMS[DRILL]), "สว่านเจาะรูยังหลุดเป็นของรางวัลสุ่มได้"


def test_artifacts_stay_a_collection_reward():
    """อาร์ติแฟกต์ได้จากการเก็บสมุดธาตุครบทวีป ไม่ใช่ของแถมจาก NPC"""
    arts = _by_effect("equip_artifact")
    assert arts, "ไม่มีอาร์ติแฟกต์ในตู้ไอเทม — เช็คคอนฟิก"
    for i in arts:
        assert not is_random_rewardable(ITEMS[i]), f"อาร์ติแฟกต์ {ITEMS[i]['name']} ยังหลุดได้"


def test_gold_bars_can_never_drop():
    """ทองคำแท่งหลุดจากหีบ/NPC = ฟอกเงิน หีบใบเดียวได้พันล้าน"""
    bars = [i for i, d in ITEMS.items() if d.get("bar_value")]
    assert bars, "ไม่มีทองคำแท่งในตู้ไอเทม — เช็คคอนฟิก"
    for i in bars:
        assert not is_random_rewardable(ITEMS[i]), f"{ITEMS[i]['name']} ยังหลุดเป็นของรางวัลได้"


def test_ordinary_loot_still_drops():
    """กันของเทพอย่างเดียว ของธรรมดาต้องยังออกได้ปกติ ไม่งั้นหีบว่างเปล่า"""
    ok = [i for i, d in ITEMS.items() if is_random_rewardable(d)]
    assert len(ok) > 50, f"กันเยอะเกินไป เหลือของให้สุ่มแค่ {len(ok)} ชิ้น"
    assert "1" in ok, "ยาฮีลต้องยังดรอปได้"


def test_a_cheap_sell_price_can_no_longer_smuggle_things_in():
    """ช่องโหว่เดิม: ของแพงที่ตั้ง 'ขายได้ 1 ทอง' (กันคนขายทิ้ง) กลายเป็นของถูกในสายตาระบบ
    เลยติดโผของแถมของทุกดีล — เคสจริงคือ 🗡️ อาวุธในตำนาน ซื้อ 10 ล้าน ขาย 1

    กติกาที่ต้องคงไว้: ค่าประเมินห้ามต่ำกว่า 1/10 ของราคาซื้อ ไม่ว่าจะตั้งราคาขายไว้เท่าไหร่
    """
    cheap_sell = [i for i, d in ITEMS.items()
                  if int(d.get("buy", 0)) >= 100_000 and int(d.get("sell", 0)) <= 10]
    assert cheap_sell, "ไม่มีของราคาแพงแต่ตั้งขายถูก — เทสนี้ไม่ได้ทดสอบอะไรเลย"
    for i in cheap_sell:
        d, val = ITEMS[i], _item_value(ITEMS, i)
        assert val >= int(d["buy"]) // 10, \
            f"{d['name']} ซื้อ {int(d['buy']):,} แต่ค่าประเมินแค่ {val:,} — ยังแลกได้ในราคาถูก"


def test_the_value_floor_covers_every_item():
    """ไล่ทั้งตู้ — ห้ามมีของชิ้นไหนถูกตีค่าต่ำกว่า 1/10 ของราคาซื้อ"""
    for i, d in ITEMS.items():
        buy = int(d.get("buy", 0) or 0)
        if buy <= 0:
            continue
        assert _item_value(ITEMS, i) >= buy // 10, f"{d['name']} ถูกตีค่าต่ำเกินจริง"


@pytest.mark.parametrize("val", [500, 5_000, 50_000, 500_000, 10_000_000])
def test_no_npc_trade_can_ever_pay_out_a_forbidden_item(val):
    """ไล่ทุกระดับมูลค่าดีล — ของต้องห้ามต้องไม่อยู่ในกองของรางวัลเลยสักระดับ"""
    valid = [i for i, d in ITEMS.items()
             if is_random_rewardable(d) and 0 < _item_value(ITEMS, i) <= val]
    for i in valid:
        assert ITEMS[i].get("effect") not in NO_RANDOM_REWARD
        assert not ITEMS[i].get("bar_value")


def test_every_random_pick_uses_the_filter():
    """มีสามที่ที่สุ่มของให้ผู้เล่น — ต้องกรองครบทุกที่ ไม่ใช่แค่ที่ผู้เล่นบังเอิญเจอ"""
    import pathlib
    import re
    src = pathlib.Path("bot/adventure_core.py").read_text(encoding="utf-8")
    picks = re.findall(r"^\s*(ids|valid) = \[.*", src, re.M)
    assert len(picks) >= 3, f"เจอจุดสุ่มแค่ {len(picks)} จุด — เช็คว่าเปลี่ยนโครงไปหรือเปล่า"
    for line in re.findall(r"^\s*(?:ids|valid) = \[[^\]]*\]", src, re.M | re.S):
        assert "is_random_rewardable" in line, f"จุดสุ่มนี้ไม่ได้กรอง: {line.strip()[:70]}"
