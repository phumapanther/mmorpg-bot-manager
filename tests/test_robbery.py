"""ระบบโจรปล้น: เรทตามความรวย + บัตรประกันคุ้มครองตามเพดาน + ยอดเหลือหลังปล้นธนาคาร"""
import random

from bot import config_loader, robbery


def _no_panel(monkeypatch):
    """บังคับใช้ค่า default ในโค้ด — กันค่าที่ตั้งใน config เครื่องจริงรั่วเข้าเทส"""
    monkeypatch.setattr(config_loader, "get_balance", lambda k, d=None: d)


def test_chance_tiers(monkeypatch):
    _no_panel(monkeypatch)
    assert robbery.robbery_chance(500_000) == 0
    assert robbery.robbery_chance(1_000_000) == 10
    assert robbery.robbery_chance(9_999_999) == 10
    assert robbery.robbery_chance(10_000_000) == 25
    assert robbery.robbery_chance(100_000_000) == 50
    assert robbery.robbery_chance(1_000_000_000) == 100


def test_mug_win_tiers(monkeypatch):
    _no_panel(monkeypatch)
    assert robbery.mug_win_chance(2_000_000) == 50
    assert robbery.mug_win_chance(10_000_000) == 35
    assert robbery.mug_win_chance(100_000_000) == 20
    assert robbery.mug_win_chance(1_000_000_000) == 10


def test_bank_rob_left(monkeypatch):
    _no_panel(monkeypatch)
    assert robbery.bank_rob_left(1_000_000_000) == 10_000
    assert robbery.bank_rob_left(100_000_000) == 100_000
    assert robbery.bank_rob_left(10_000_000) == 1_000_000
    assert robbery.bank_rob_left(4_000_000) == 2_000_000   # 1-10 ล้าน หัก 50%


def test_insured_caps(monkeypatch):
    _no_panel(monkeypatch)
    assert robbery.insured({"insurance_1m": 5}, 9_999_999) is True
    assert robbery.insured({"insurance_1m": 5}, 10_000_000) is False    # รวยเกินเพดานบัตร
    assert robbery.insured({"insurance_10m": 5}, 99_999_999) is True
    assert robbery.insured({"insurance_10m": 5}, 100_000_000) is False
    assert robbery.insured({"insurance_1b": 5}, 5_000_000_000) is True  # ไม่จำกัด
    assert robbery.insured({"poison": 5}, 2_000_000) is False           # สถานะอื่นไม่ใช่ประกัน
    assert robbery.insured({}, 2_000_000) is False


def test_roll_robbery(monkeypatch):
    _no_panel(monkeypatch)
    rng = random.Random(24)
    # จนกว่าเกณฑ์ = ไม่โดนเลย
    assert all(robbery.roll_robbery(500_000, 500_000, {}, rng) is None for _ in range(200))
    # พันล้านโดนทุกก้าว — ฝั่งไหนเกินล้านโดนฝั่งนั้น
    assert robbery.roll_robbery(0, 2_000_000_000, {}, rng) == "bank_robbery"
    assert robbery.roll_robbery(2_000_000_000, 0, {}, rng) == "mugging"
    # มีบัตรที่คุ้มครองอยู่ = รอดแน่นอน
    assert robbery.roll_robbery(0, 2_000_000_000, {"insurance_1b": 3}, rng) is None
    # เข้าเงื่อนไขทั้งคู่ → สุ่มได้ทั้งสองแบบ
    kinds = {robbery.roll_robbery(2_000_000, 2_000_000_000, {}, rng) for _ in range(50)}
    assert kinds == {"bank_robbery", "mugging"}
