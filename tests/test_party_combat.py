"""🎭 การคำนวณดาเมจในโหมดปาร์ตี้

⚠️ ตัวเลขสมดุลตั้งได้ใน Panel — เทสนี้คุม "ความสัมพันธ์" ไม่ใช่ตัวเลขตายตัว
   (เช่น "ทอยสูงต้องแรงกว่าทอยต่ำ" ไม่ใช่ "ทอย 20 ต้องได้ 137 พอดี")
   ไม่งั้นปรับสมดุลทีไรเทสแดงทุกที
"""
import pytest

from bot.games.party import combat


def _unit(uid="p1", level=10, element="fire", atk=10, defense=0, alive=True):
    return {"id": uid, "level": level, "element": element,
            "atk": atk, "def": defense, "hp": 100 if alive else 0, "hp_max": 100}


# ── ดาเมจพื้นฐาน ──

def test_ทอยสูงแรงกว่าทอยต่ำ():
    a, d = _unit(), _unit("m1", element="water")
    lo, _ = combat.damage(a, d, "attack", roll=3)
    hi, _ = combat.damage(a, d, "attack", roll=19)
    assert hi > lo


def test_ดาเมจไม่ติดลบ():
    """เกราะหนากว่าพลังโจมตี ต้องได้ 0 ไม่ใช่ติดลบ (ไม่งั้นตีแล้วศัตรูเลือดขึ้น)"""
    weak = _unit(atk=1, level=1)
    tank = _unit("m1", defense=9999)
    dmg, _ = combat.damage(weak, tank, "attack", roll=1)
    assert dmg >= 0


def test_ดาเมจเป็นจำนวนเต็ม():
    """ตัวคูณธาตุทำให้เป็นทศนิยม ต้องปัดก่อนส่งให้ renderer"""
    dmg, _ = combat.damage(_unit(), _unit("m1", element="wood"), "attack", roll=15)
    assert isinstance(dmg, int)


def test_เลเวลสูงตีแรงกว่า():
    lo, _ = combat.damage(_unit(level=1), _unit("m1"), "attack", roll=15)
    hi, _ = combat.damage(_unit(level=99), _unit("m1"), "attack", roll=15)
    assert hi > lo


def test_เกราะหนาโดนน้อยกว่า():
    soft, _ = combat.damage(_unit(), _unit("m1", defense=0), "attack", roll=15)
    hard, _ = combat.damage(_unit(), _unit("m1", defense=20), "attack", roll=15)
    assert hard < soft


# ── ธาตุ (ต่อยอดจาก rules.py) ──

def test_ธาตุได้เปรียบแรงกว่า():
    """fire ข่ม wood — ต้องแรงกว่าตีใส่ธาตุที่ไม่เกี่ยวกัน"""
    adv, _ = combat.damage(_unit(element="fire"), _unit("m1", element="wood"), "attack", roll=15)
    neu, _ = combat.damage(_unit(element="fire"), _unit("m1", element="light"), "attack", roll=15)
    assert adv > neu


def test_ธาตุเสียเปรียบอ่อนกว่า():
    dis, _ = combat.damage(_unit(element="wood"), _unit("m1", element="fire"), "attack", roll=15)
    neu, _ = combat.damage(_unit(element="wood"), _unit("m1", element="light"), "attack", roll=15)
    assert dis < neu


# ── คริติคอล ──

def test_ทอยสูงสุดคริติคอล():
    _, crit = combat.damage(_unit(), _unit("m1"), "attack", roll=20)
    assert crit is True


def test_ทอยธรรมดาไม่คริติคอล():
    _, crit = combat.damage(_unit(), _unit("m1"), "attack", roll=10)
    assert crit is False


def test_คริติคอลแรงกว่าไม่คริ():
    normal, _ = combat.damage(_unit(), _unit("m1"), "attack", roll=19)
    crit, is_c = combat.damage(_unit(), _unit("m1"), "attack", roll=20)
    assert is_c and crit > normal


# ── คำสั่งแต่ละแบบ ──

def test_สกิลแรงกว่าโจมตีปกติ():
    """แลกกับเต๋าที่เสี่ยงกว่า (roll_player_die ให้สกิลทอยเต็มช่วง 1-20)"""
    atk, _ = combat.damage(_unit(), _unit("m1"), "attack", roll=15)
    skill, _ = combat.damage(_unit(), _unit("m1"), "skill", roll=15)
    assert skill > atk


def test_ป้องกันลดดาเมจที่จะโดน():
    d = _unit("m1")
    normal = combat.incoming(_unit(), d, 100, defending=False)
    guard = combat.incoming(_unit(), d, 100, defending=True)
    assert guard < normal


def test_ป้องกันไม่ทำให้ดาเมจติดลบ():
    assert combat.incoming(_unit(), _unit("m1"), 1, defending=True) >= 0


# ── AoE ──

def test_aoe_โดนทุกเป้า():
    targets = [_unit("m1"), _unit("m2"), _unit("m3")]
    dmgs = combat.splash(_unit(), targets, "skill", roll=15)
    assert len(dmgs) == 3
    assert all(d >= 0 for d in dmgs)


def test_aoe_แต่ละตัวอ่อนกว่าตีเดี่ยว():
    """ไม่งั้น AoE จะดีกว่าตีเดี่ยวทุกกรณี ไม่มีเหตุผลให้เลือกตีเดี่ยว"""
    t = _unit("m1")
    single, _ = combat.damage(_unit(), t, "skill", roll=15)
    aoe = combat.splash(_unit(), [t, _unit("m2")], "skill", roll=15)
    assert aoe[0] < single


def test_aoe_เป้าเดียวก็ยังทำงาน():
    """ลูกน้องตายหมดเหลือบอสตัวเดียว AoE ต้องไม่พัง"""
    assert len(combat.splash(_unit(), [_unit("m1")], "skill", roll=15)) == 1


def test_aoe_ไม่มีเป้าไม่พัง():
    assert combat.splash(_unit(), [], "skill", roll=15) == []
