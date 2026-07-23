"""ทดสอบ U1: ธาตุประจำตัวผู้เล่นจากยศเผ่า + ตารางแพ้ทาง + dual-race"""
from bot import game_modifiers as gm


def test_resolve_from_real_role_names():
    # ชื่อยศจริงมีสัญลักษณ์/ช่องว่างแปลก — ต้อง match ด้วยคำสำคัญได้
    assert gm.resolve_player_elements(["、👲🏻 • มนุษย์"]) == ["light", "wind"]
    assert gm.resolve_player_elements(["、 🧝🏻‍♂️ • เอลฟ์"]) == ["wood"]
    assert gm.resolve_player_elements(["• Lich 🧙🏽‍♂️"]) == ["dark"]
    assert gm.resolve_player_elements(["•  Slime 🪼⋆"]) == ["water"]
    # dual-race: มังกร + เงือก = ไฟ + น้ำ
    assert gm.resolve_player_elements(["、🐉 • มังกร", "、🧜🏼‍♀️ • เงือก"]) == ["fire", "water"]
    # ไม่มียศเผ่า = ไม่มีธาตุ
    assert gm.resolve_player_elements(["นักผจญภัยแรงค์ F", "Warrior"]) == []


def test_attack_advantage_and_dual_cap():
    # ไฟข่มไม้ ×1.5
    assert gm.player_attack_element_mult(["fire"], "wood") == 1.5
    assert gm.player_attack_element_mult(["fire"], "water") == 1.0
    # สองธาตุได้เปรียบซ้อน (ไม้+ลม ข่มดิน) = ×2.0 cap
    assert gm.player_attack_element_mult(["wood", "wind"], "earth") == 2.0
    # แสงข่มมืด / มืดข่มแสง
    assert gm.player_attack_element_mult(["light"], "dark") == 1.5
    assert gm.player_attack_element_mult(["dark"], "light") == 1.5
    # ไม่มีธาตุ/มอนไม่มีธาตุ = กลาง
    assert gm.player_attack_element_mult([], "wood") == 1.0
    assert gm.player_attack_element_mult(["fire"], None) == 1.0


def test_defense_resist_and_lightdark():
    # ไฟทนน้ำ ×0.75 (ตามสเปกฝั่งรับ)
    assert gm.player_defense_element_mult(["fire"], "water") == 0.75
    assert gm.player_defense_element_mult(["wind"], "fire") == 0.75
    # ถือธาตุคู่ปรับแสง↔มืด → รับแรงขึ้น ×1.5
    assert gm.player_defense_element_mult(["light"], "dark") == 1.5
    assert gm.player_defense_element_mult(["dark"], "light") == 1.5
    # เป็นกลาง
    assert gm.player_defense_element_mult(["earth"], "fire") == 1.0
    assert gm.player_defense_element_mult([], "fire") == 1.0


def test_matrix_integrity():
    valid = set(gm.ELEMENTS)
    for source, targets in {**gm.ELEMENT_ADVANTAGE, **gm.ELEMENT_RESIST}.items():
        assert source in valid
        assert set(targets) <= valid
    for elems in gm.RACE_ELEMENTS.values():
        assert set(elems) <= valid
