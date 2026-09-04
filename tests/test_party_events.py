"""🎭 เหตุการณ์ที่แกนส่งให้ renderer — นี่คือ "สัญญา" ระหว่างแกนกับภาพ

เปลี่ยนรูปแบบตรงนี้ = renderer ทุกตัวพัง ต้องมีเทสคุมให้แน่น
(นี่คือสิ่งที่ทำให้ "เปลี่ยนกราฟิกได้ง่าย" ตามที่เจ้าของเกมสั่ง)
"""
import json

import pytest

from bot.games.party import events

ALL_MAKERS = [
    ("turn_start", lambda: events.turn_start("p1")),
    ("dice", lambda: events.dice("p1", [17, 4])),
    ("attack", lambda: events.attack("p1", "m2", 120, "fire")),
    ("aoe", lambda: events.aoe("p3", ["m1", "m2"], [40, 35], "water")),
    ("heal", lambda: events.heal("p2", "p4", 80)),
    ("die", lambda: events.die("m2")),
    ("phase", lambda: events.phase("boss", "rage")),
    ("miss", lambda: events.miss("p1", "m2")),
    ("telegraph", lambda: events.telegraph("m1", "🔥 คลื่นเพลิงคลั่ง", ["p1", "p2"])),
]


@pytest.mark.parametrize("name,make", ALL_MAKERS)
def test_เหตุการณ์ทุกชนิดมีคีย์_t(name, make):
    """renderer ดูคีย์ t ตัวเดียวว่าจะวาดอะไร"""
    assert make()["t"] == name


@pytest.mark.parametrize("name,make", ALL_MAKERS)
def test_เหตุการณ์ทุกชนิดส่งเป็น_json_ได้(name, make):
    """ต้องส่งขึ้นเบราว์เซอร์ได้ — ห้ามมี object แปลก ๆ ปน"""
    e = make()
    assert json.loads(json.dumps(e, ensure_ascii=False)) == e


def test_โจมตีเก็บครบทุกอย่างที่ต้องวาด():
    e = events.attack("p1", "m2", 120, "fire", crit=True)
    assert e["from"] == "p1" and e["to"] == "m2"
    assert e["dmg"] == 120 and e["element"] == "fire"
    assert e["crit"] is True


def test_โจมตีไม่คริติคอลก็ต้องบอก():
    """renderer ต้องรู้เสมอ ไม่ใช่เดาจากการที่คีย์หายไป"""
    assert events.attack("p1", "m2", 10, "fire")["crit"] is False


def test_ดาเมจเป็นจำนวนเต็มเสมอ():
    """ทศนิยมจากตัวคูณธาตุต้องปัดก่อนส่ง ไม่งั้นจอโชว์ 34.99999"""
    assert events.attack("p1", "m2", 34.7, "fire")["dmg"] == 34
    assert isinstance(events.heal("p1", "p2", 12.9)["amount"], int)


def test_ทอยเต๋าเก็บทุกลูกกับผลรวม():
    e = events.dice("p1", [17, 4])
    assert e["rolls"] == [17, 4] and e["total"] == 21


def test_aoe_จำนวนเป้ากับดาเมจต้องเท่ากัน():
    """ไม่เท่ากัน = บั๊ก renderer จะวาดเลขผิดตัว ต้องดักที่ต้นทาง"""
    with pytest.raises(ValueError):
        events.aoe("p1", ["m1", "m2"], [10], "fire")


def test_aoe_เก็บเป้ากับดาเมจเรียงตรงกัน():
    e = events.aoe("p1", ["m1", "m2"], [40, 35], "fire")
    assert e["targets"] == ["m1", "m2"] and e["dmgs"] == [40, 35]


def test_เหตุการณ์เป็น_dict_ธรรมดาแก้ต่อได้():
    """renderer บางตัวอาจอยากเติมคีย์เอง — ต้องไม่ frozen"""
    e = events.attack("p1", "m2", 10, "fire")
    e["extra"] = 1
    assert e["extra"] == 1


def test_รายชื่อชนิดเหตุการณ์ครบตามที่ประกาศ():
    """เพิ่มชนิดใหม่ต้องประกาศใน EVENT_TYPES ด้วย ไม่งั้น renderer ไม่รู้ว่าต้องรองรับอะไร"""
    made = {make()["t"] for _, make in ALL_MAKERS}
    assert made == set(events.EVENT_TYPES)


def test_เตือนท่าใหญ่บอกทั้งชื่อท่าและคนที่จะโดน():
    """ป้ายเตือนต้องบอกครบ ไม่งั้นผู้เล่นตัดสินใจไม่ได้ว่าจะกันหรือจะฮีล"""
    e = events.telegraph("m1", "🔥 คลื่นเพลิงคลั่ง", ["p1", "p2"])
    assert e["move"] and e["targets"] == ["p1", "p2"]
