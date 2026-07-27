"""P6 กิลด์: ชั้น DB — สร้าง/ซ้ำ/สมาชิกเดียวต่อคน/คลังห้ามติดลบ/ยุบ"""
import bot.models.player_model as pm


def _db(tmp_path, monkeypatch):
    monkeypatch.setattr(pm, "DB_NAME", str(tmp_path / "t.db"))


def test_create_and_lookup(tmp_path, monkeypatch):
    _db(tmp_path, monkeypatch)
    gid = pm.create_guild("มังกรทมิฬ", "🐲", leader_id=1, role_id=10, channel_id=20)
    assert gid is not None
    g = pm.get_guild_of(1)
    assert g["name"] == "มังกรทมิฬ" and g["leader_id"] == 1 and g["treasury"] == 0
    assert pm.get_guild_by_name("มังกรทมิฬ")["guild_id"] == gid
    assert pm.get_guild_members(gid) == [1]


def test_duplicate_name_and_leader(tmp_path, monkeypatch):
    _db(tmp_path, monkeypatch)
    assert pm.create_guild("A", "🏰", 1, 10, 20) is not None
    assert pm.create_guild("A", "🏰", 2, 11, 21) is None      # ชื่อซ้ำ
    assert pm.create_guild("B", "🏰", 1, 12, 22) is None      # หัวหน้าซ้ำ (ยังอยู่กิลด์ A)


def test_one_guild_per_player(tmp_path, monkeypatch):
    _db(tmp_path, monkeypatch)
    g1 = pm.create_guild("A", "🏰", 1, 10, 20)
    g2 = pm.create_guild("B", "🗡️", 2, 11, 21)
    assert pm.add_guild_member(3, g1) is True
    assert pm.add_guild_member(3, g2) is False                # อยู่ได้กิลด์เดียว
    pm.remove_guild_member(3)
    assert pm.add_guild_member(3, g2) is True                 # ออกแล้วย้ายได้


def test_treasury_never_negative(tmp_path, monkeypatch):
    _db(tmp_path, monkeypatch)
    gid = pm.create_guild("A", "🏰", 1, 10, 20)
    assert pm.guild_add_treasury(gid, 500) == 500
    assert pm.guild_add_treasury(gid, -200) == 300
    assert pm.guild_add_treasury(gid, -999) is None           # ถอนเกิน = ปฏิเสธ ยอดไม่ขยับ
    assert pm.get_guild_of(1)["treasury"] == 300


def test_delete_guild(tmp_path, monkeypatch):
    _db(tmp_path, monkeypatch)
    gid = pm.create_guild("A", "🏰", 1, 10, 20)
    pm.add_guild_member(2, gid)
    pm.delete_guild(gid)
    assert pm.get_guild_of(1) is None and pm.get_guild_of(2) is None
    assert pm.create_guild("A", "🏰", 1, 10, 20) is not None  # ชื่อ/หัวหน้าว่างให้ใช้ใหม่
