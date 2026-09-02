"""เทสกฎการทาย — ฟังก์ชันล้วน ไม่มี state

⚠️ ไฟล์นี้ import แบบ absolute (`from templates.minigame.core import ...`)
   เพราะเทสอยู่นอกโฟลเดอร์ core/ — ตอนก๊อปไปใช้จริงต้องแก้บรรทัด import
   เป็น `from bot.games.<หมวด>.<ชื่อเกม> import rules as R` (ดู
   templates/README.md ขั้นตอนก๊อปเทมเพลต)
"""
from templates.minigame.core import rules as R


def test_ทายถูกได้ผล_correct():
    assert R.feedback(5, 5) == "correct"


def test_ทายสูงเกินได้ผล_lower():
    assert R.feedback(3, 7) == "lower"      # เลขลับ (3) ต่ำกว่าที่ทาย (7) = ทายสูงไป


def test_ทายต่ำเกินได้ผล_higher():
    assert R.feedback(9, 2) == "higher"     # เลขลับ (9) สูงกว่าที่ทาย (2) = ทายต่ำไป


def test_ทายเลขนอกช่วงไม่ผ่าน():
    assert not R.valid_guess(0)
    assert not R.valid_guess(11)
    assert not R.valid_guess("มั่ว")
    assert not R.valid_guess(None)


def test_ทายเลขในช่วงผ่าน():
    assert R.valid_guess(1)
    assert R.valid_guess(10)
    assert R.valid_guess("5")     # เบราว์เซอร์ส่งมาเป็น string ก็ต้องรับได้
