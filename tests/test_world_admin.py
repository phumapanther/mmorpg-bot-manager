"""ทดสอบชุดคำสั่งแอดมินควบคุมโลก — ส่วน override/persist (ตัวคำสั่ง Discord ทดสอบ manual)"""
import bot.models.player_model as player_model
from bot import game_modifiers as gm
from bot.cogs import weekly_event as we
from bot.cogs import world_admin as wa


def test_theme_override_forces_theme(monkeypatch):
    monkeypatch.setattr(gm, "THEME_OVERRIDE", "zombie")
    assert gm.get_weekly_theme()["key"] == "zombie"
    # ปลดล็อก → กลับสู่การสุ่มปกติ (ธีมใดก็ได้ใน pool)
    monkeypatch.setattr(gm, "THEME_OVERRIDE", None)
    assert gm.get_weekly_theme()["key"] in {t["key"] for t in gm.WEEKLY_THEMES}
    # key ที่ไม่มีจริง = เมิน override สุ่มตามปกติ (กันค่าเก่าค้างหลังลบธีม)
    monkeypatch.setattr(gm, "THEME_OVERRIDE", "deleted_theme")
    assert gm.get_weekly_theme() is not None


def test_get_theme_by_key():
    assert gm.get_theme_by_key("normal")["key"] == "normal"
    assert gm.get_theme_by_key("no_such") is None


def test_load_theme_override_persists_via_db(tmp_path, monkeypatch):
    monkeypatch.setattr(player_model, "DB_NAME", str(tmp_path / "state.db"))
    monkeypatch.setattr(gm, "THEME_OVERRIDE", None)
    we.set_state("theme_override", "palette")
    wa.load_theme_override()
    assert gm.THEME_OVERRIDE == "palette"
    # ค่าว่าง (หลัง !settheme auto) = None
    we.set_state("theme_override", "")
    wa.load_theme_override()
    assert gm.THEME_OVERRIDE is None
