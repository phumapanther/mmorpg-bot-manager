"""🎭 กติกาปาร์ตี้เทิร์นเบส — ตรรกะล้วน ไม่มี I/O เทสง่ายสุด

⚠️ ธาตุ **ไม่ได้ตั้งตารางใหม่** — ใช้ ELEMENT_ADVANTAGE ของเกมหลัก
   ไม่งั้นธาตุในโหมดปาร์ตี้กับโหมดเดี่ยวไม่ตรงกัน ผู้เล่นจะงง
"""
import pytest

from bot.game_modifiers import ELEMENT_ADVANTAGE
from bot.games.party import rules


# ── ธาตุ ──

def test_ใช้ตารางธาตุตัวเดียวกับเกมหลัก():
    """ถ้าใครเผลอก๊อปตารางมาไว้ในไฟล์นี้ เทสนี้จะจับได้"""
    import inspect
    src = inspect.getsource(rules)
    assert "ELEMENT_ADVANTAGE" in src, "ต้องอ้างตารางของเกมหลัก ไม่ใช่ตั้งใหม่"
    assert '"wood"' not in src.split("import")[-1] or "STRONG" not in src, \
        "อย่าก๊อปตารางธาตุมาไว้ที่นี่ — ใช้ของ game_modifiers"


@pytest.mark.parametrize("attacker,target", list(
    (a, t) for a, ts in ELEMENT_ADVANTAGE.items() for t in ts))
def test_ธาตุที่ข่มได้ดาเมจมากกว่า(attacker, target):
    """ไล่ทุกคู่ในตารางจริง — เพิ่ม/ลดธาตุในเกมหลักแล้วเทสนี้ตามเอง"""
    assert rules.element_multiplier(attacker, target) > 1.0


def _beats(a, b):
    return b in ELEMENT_ADVANTAGE.get(a, [])


# ⚠️ light กับ dark ข่มกันเอง 2 ทาง (เจอตอนรันจริง) — คู่แบบนั้นทั้งคู่ได้เปรียบ
#    ตัดออกจากเทสเสียเปรียบ ไม่งั้นเทสขัดกับตารางจริงของเกม
@pytest.mark.parametrize("attacker,target", [
    (t, a) for a, ts in ELEMENT_ADVANTAGE.items() for t in ts
    if not _beats(t, a)])
def test_ธาตุที่โดนข่มได้ดาเมจน้อยกว่า(attacker, target):
    assert rules.element_multiplier(attacker, target) < 1.0


@pytest.mark.parametrize("a,b", [
    (a, t) for a, ts in ELEMENT_ADVANTAGE.items() for t in ts if _beats(t, a)])
def test_ธาตุที่ข่มกันเอง_2_ทางได้เปรียบทั้งคู่(a, b):
    """light/dark ข่มกันเอง — ฝ่ายที่ตีก่อนได้เปรียบ ไม่ใช่หักล้างเป็น 1.0"""
    assert rules.element_multiplier(a, b) > 1.0
    assert rules.element_multiplier(b, a) > 1.0


def test_ธาตุเดียวกันไม่ได้ไม่เสีย():
    assert rules.element_multiplier("fire", "fire") == 1.0


def test_สองธาตุข่มเป้าเดียวกันได้แรงกว่าธาตุเดียว():
    """เกมหลักให้ผู้เล่นถือได้หลายธาตุ (ยศเผ่าหลายอัน) — ต้องได้เปรียบมากขึ้น"""
    one = rules.element_multiplier(["water"], "fire")
    two = rules.element_multiplier(["water", "water"], "fire")
    assert two >= one


def test_ไม่มีธาตุไม่พัง():
    """ผู้เล่นที่ยังไม่มียศเผ่าจะไม่มีธาตุ — ต้องไม่ crash"""
    assert rules.element_multiplier(None, "fire") == 1.0
    assert rules.element_multiplier("fire", None) == 1.0
    assert rules.element_multiplier([], "fire") == 1.0


def test_ธาตุที่ไม่รู้จักไม่พัง():
    assert rules.element_multiplier("ไม่มีธาตุนี้", "fire") == 1.0


def test_รับได้ทั้งข้อความเดียวและรายการ():
    """ผู้เล่นส่งรายการธาตุ มอนส่งธาตุเดียว — ต้องรับได้ทั้งคู่"""
    assert rules.element_multiplier("water", "fire") == \
        rules.element_multiplier(["water"], "fire")


# ── การเล็งเป้า ──

@pytest.mark.parametrize("kind,actor,target,ok", [
    ("single", "party", "monster", True),    # ตีมอน
    ("single", "party", "party", False),     # ตีเพื่อนไม่ได้
    ("all", "party", "monster", True),       # AoE ใส่มอนทุกตัว
    ("ally", "party", "party", True),        # ฮีล/ชุบเพื่อน
    ("ally", "party", "monster", False),     # ฮีลมอนไม่ได้
    ("self", "party", "party", True),        # บัฟตัวเอง
    ("single", "monster", "party", True),    # มอนตีเรา
    ("all", "monster", "party", True),       # มอนใช้ AoE ใส่ปาร์ตี้
])
def test_เล็งเป้าถูกฝั่ง(kind, actor, target, ok):
    assert rules.can_target(kind, actor, target) is ok


def test_ชนิดการเล็งที่ไม่รู้จักถือว่าเล็งไม่ได้():
    """กันคนยิง API ส่ง kind มั่ว ๆ มา — เซิร์ฟเวอร์ต้องปฏิเสธ"""
    assert rules.can_target("ทำลายล้างจักรวาล", "party", "monster") is False
    assert rules.can_target(None, "party", "monster") is False


def test_ชนิดการเล็งที่รองรับครบตามสเปก():
    """เพิ่ม/ลดต้องตั้งใจ ไม่ใช่หลุดมาเอง — ชนิดที่ไม่รู้จักต้องเล็งไม่ได้เลย

    สเปกแรกมี 4 แบบ · "fallen" เพิ่มตอนเฟส 6 (ท่าชุบเล็งคนที่ล้มแล้ว)
    · "ally_any" เพิ่มตอนเฟส 9 (✨ Heal ของ Cleric เล็งได้ทั้งคนยืนและคนล้ม)
    """
    assert set(rules.TARGET_KINDS) == {"single", "all", "ally", "self",
                                       "fallen", "ally_any"}
    assert not rules.can_target("ชนิดมั่ว", "party", "monster")
