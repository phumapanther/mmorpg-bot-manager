"""🏺 อาร์ติแฟกต์ทุกชิ้นต้องมีทางหามาได้จริง

อาร์ติแฟกต์ซื้อไม่ได้ ดรอปสุ่มไม่ได้ (ถูกกันออกจากกองสุ่มทั้งหมด)
ทางเดียวคืออีเวนต์พิเศษประจำทวีป/ธีม — ถ้าลืมผูกที่มา มันจะกลายเป็นของที่
"มีอยู่ในเกมแต่ไม่มีใครได้เลยตลอดกาล" (เคยเป็นแบบนั้นจริงกับ 💠 ปริซึมมานา)
"""
import pytest

from bot import config_loader, game_data as gd
from bot.adventure_core import is_random_rewardable

ITEMS = config_loader.get_all_items()
ARTIFACTS = {i for i, d in ITEMS.items() if d.get("effect") == "equip_artifact"}


def _event_item_ids():
    """{รหัสไอเทม: [คีย์อีเวนต์ที่ดรอป]} จากอีเวนต์พิเศษทั้งหมดในเกม"""
    out = {}

    def walk(o, where):
        if isinstance(o, dict):
            if "template" in o and "key" in o:
                where = o["key"]
            for k, v in o.items():
                if k in ("id", "id_pool"):
                    for x in (v if isinstance(v, list) else [v]):
                        out.setdefault(str(x), []).append(where)
                walk(v, where)
        elif isinstance(o, list):
            for v in o:
                walk(v, where)

    for name in dir(gd):
        if not name.startswith("_"):
            walk(getattr(gd, name), "?")
    return out


def test_there_are_artifacts_at_all():
    assert len(ARTIFACTS) >= 10, f"เจออาร์ติแฟกต์แค่ {len(ARTIFACTS)} ชิ้น — เช็คคอนฟิก"


def test_artifacts_cannot_be_bought_or_randomly_dropped():
    for i in ARTIFACTS:
        assert not ITEMS[i].get("purchasable", True), f"{ITEMS[i]['name']} ซื้อได้ — ไม่ควร"
        assert not is_random_rewardable(ITEMS[i]), f"{ITEMS[i]['name']} หลุดกองสุ่มได้"


def test_every_artifact_is_obtainable_somewhere():
    """ชิ้นไหนไม่มีอีเวนต์ผูกไว้ = ของตายในเกม ไม่มีใครได้เลย"""
    sources = _event_item_ids()
    orphans = {i: ITEMS[i]["name"] for i in ARTIFACTS if i not in sources}
    assert not orphans, f"อาร์ติแฟกต์ที่ไม่มีทางได้เลย: {orphans}"


def test_the_ocean_finally_has_its_own_special_event():
    """ทวีปทะเลเคยไม่มีอีเวนต์พิเศษเลยสักอัน"""
    sp = (gd.CONTINENTS["ocean"].get("mods") or {}).get("special_events") or []
    assert sp, "ทวีปมหาสมุทรยังไม่มีอีเวนต์พิเศษ"
    ids = {str(e.get("id")) for ev in sp for c in (ev.get("choices") or [])
           for e in (c.get("outcome", {}).get("items") or [])}
    assert ids & ARTIFACTS, "อีเวนต์ทะเลไม่ได้ดรอปอาร์ติแฟกต์"


def test_the_mana_prism_comes_from_the_ocean():
    prism = next((i for i, d in ITEMS.items() if "ปริซึมมานา" in d.get("name", "")), None)
    assert prism, "ไม่มี 💠 ปริซึมมานา ในตู้ไอเทม"
    assert "sunken_shrine" in _event_item_ids().get(prism, []), \
        "ปริซึมมานาไม่ได้ผูกกับอีเวนต์วิหารจมน้ำของทวีปทะเล"


@pytest.mark.parametrize("cont", ["frozen", "nether", "volcanic", "sylvan",
                                  "mechanized", "skyward", "ocean"])
def test_each_of_these_continents_has_its_own_artifact(cont):
    """ทวีปที่มีอีเวนต์พิเศษ ควรมีอาร์ติแฟกต์ประจำถิ่นเป็นรางวัลปลายทาง"""
    sp = (gd.CONTINENTS[cont].get("mods") or {}).get("special_events") or []
    ids = set()

    def collect(o):
        if isinstance(o, dict):
            for k, v in o.items():
                if k == "id":
                    ids.add(str(v))
                collect(v)
        elif isinstance(o, list):
            for v in o:
                collect(v)

    collect(sp)
    assert ids & ARTIFACTS, f"ทวีป {cont} ไม่มีอาร์ติแฟกต์เป็นรางวัล"


def _artifact_drops():
    """[(อีเวนต์, ชื่อของ, โอกาส%, ค่าใช้จ่าย)] ของทุกจุดที่ดรอปอาร์ติแฟกต์

    ค่าใช้จ่าย = ทองที่ต้องจ่ายในทางเลือกนั้น (0 = ได้ฟรี)
    """
    def walk(o, where, cost):
        if isinstance(o, dict):
            if "template" in o and "key" in o:
                where = o["key"]
            g = o.get("gold")
            if isinstance(g, (int, float)) and g < 0:
                cost = -int(g)
            elif isinstance(g, (list, tuple)) and g and max(g) < 0:
                cost = -int(max(g))
            if str(o.get("id")) in ARTIFACTS:
                yield where, ITEMS[str(o["id"])]["name"], int(o.get("chance", 100)), cost
            for v in o.values():
                yield from walk(v, where, cost)
        elif isinstance(o, list):
            for v in o:
                yield from walk(v, where, cost)

    return [d for name in dir(gd) if not name.startswith("_")
            for d in walk(getattr(gd, name), "?", 0)]


def test_free_artifact_drops_stay_rare():
    """อาร์ติแฟกต์เป็นของถาวรติดตัว ที่ได้ "ฟรี" ห้ามดรอปง่ายจนเก็บครบในวันเดียว"""
    drops = _artifact_drops()
    assert drops, "ไม่เจอการดรอปอาร์ติแฟกต์เลย"
    free = [d for d in drops if d[3] == 0]
    assert free, "ไม่มีอาร์ติแฟกต์ที่ได้ฟรีเลย — ควรมีบ้างเป็นรางวัลผจญภัย"
    for where, name, chance, _cost in free:
        assert chance <= 15, f"{name} ที่ {where} ดรอปฟรี {chance}% — ง่ายเกินไปสำหรับของถาวร"


def test_a_paid_gamble_must_actually_cost_something():
    """จ่ายเงินลุ้นได้เรทสูงกว่าปกติ — แต่ต้องแพงพอให้เป็นที่ทิ้งเงินจริง ไม่ใช่ลุ้นฟรี ๆ"""
    for where, name, chance, cost in _artifact_drops():
        if chance <= 15:
            continue
        assert cost >= 10_000, \
            f"{name} ที่ {where} ลุ้น {chance}% แต่จ่ายแค่ {cost:,} ทอง — ถูกเกินไป"
