"""ภาษีรวยรายสัปดาห์: เกณฑ์สัดส่วนที่ถือของเซิร์ฟ + เงินเข้าคลังกลาง + แจกออกจากคลัง"""
import bot.models.player_model as pm
from bot import config_loader, weekly_tax


def _no_panel(monkeypatch):
    monkeypatch.setattr(config_loader, "get_balance", lambda k, d=None: d)


def _fresh_db(tmp_path, monkeypatch):
    monkeypatch.setattr(pm, "DB_NAME", str(tmp_path / "tax.db"))
    pm.init_db()


def _set_wealth(uid, cash, bank):
    pm.get_player(uid)                      # สร้างตัวละคร (ค่าเริ่มต้น) ก่อนเซ็ตเงินตรงๆ
    pm.update_player_field(uid, "cash", cash)
    pm.update_player_field(uid, "bank", bank)


def test_tax_pct_tiers(monkeypatch):
    _no_panel(monkeypatch)
    assert weekly_tax.tax_pct(95) == 99
    assert weekly_tax.tax_pct(90) == 99
    assert weekly_tax.tax_pct(80) == 75
    assert weekly_tax.tax_pct(60) == 50
    assert weekly_tax.tax_pct(49.9) == 0


def test_collect_taxes_only_whale(tmp_path, monkeypatch):
    _no_panel(monkeypatch)
    _fresh_db(tmp_path, monkeypatch)
    _set_wealth(1, 0, 1_000_000_000)   # ถือ ~90% ของเซิร์ฟ
    _set_wealth(2, 0, 100_000_000)     # ~9% — ไม่โดน
    _set_wealth(3, 5_000_000, 5_000_000)  # ~0.9% — ไม่โดน

    taxed = weekly_tax.collect("2026-W32")
    assert [t[0] for t in taxed] == [1]
    uid, wealth, share, pct, take = taxed[0]
    assert wealth == 1_000_000_000 and pct == 99 and take == 990_000_000
    assert share >= 90
    # เงินถูกหักจริง + เข้าคลังครบ
    assert pm.get_player(1)["bank"] == 10_000_000
    assert pm.get_player(2)["bank"] == 100_000_000
    assert weekly_tax.balance() == 990_000_000


def test_collect_disabled_wealth_spread(tmp_path, monkeypatch):
    """เงินกระจายไม่มีใครถือถึงครึ่งเซิร์ฟ = ไม่มีใครโดน"""
    _no_panel(monkeypatch)
    _fresh_db(tmp_path, monkeypatch)
    for uid in range(1, 5):
        _set_wealth(uid, 0, 100_000_000)
    assert weekly_tax.collect("2026-W32") == []
    assert weekly_tax.balance() == 0


def test_tax_hits_cash_when_bank_short(tmp_path, monkeypatch):
    """ธนาคารไม่พอยอดภาษี → หักส่วนที่เหลือจากเงินติดตัว"""
    _no_panel(monkeypatch)
    _fresh_db(tmp_path, monkeypatch)
    _set_wealth(1, 900_000_000, 100_000_000)   # คนเดียวในเซิร์ฟ = ถือ 100%
    taxed = weekly_tax.collect("2026-W32")
    assert taxed[0][4] == 990_000_000
    p = pm.get_player(1)
    assert p["bank"] == 0 and p["cash"] == 10_000_000


def test_treasury_give_flow(tmp_path, monkeypatch):
    _no_panel(monkeypatch)
    _fresh_db(tmp_path, monkeypatch)
    weekly_tax.add(500_000, week="2026-W32", user_id=1, note="ภาษีรวย")
    weekly_tax.add(-200_000, user_id=2, note="แอดมินแจกจากคลัง")
    assert weekly_tax.balance() == 300_000
    log = weekly_tax.recent_log(5)
    assert len(log) == 2 and log[0][2] == -200_000 and log[1][2] == 500_000
