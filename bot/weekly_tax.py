"""ภาษีรวยรายสัปดาห์ + คลังกลาง (spec 2026-08-06)

เกณฑ์: สัดส่วนเงินรวม (ติดตัว+ธนาคาร) ของคนนั้นเทียบทั้งเซิร์ฟ
ถือ ≥90% หัก 99% | ≥75% หัก 75% | ≥50% หัก 50% — % ปรับได้ที่ Panel, เปิด/ปิดได้ (weekly_tax.enabled)
เงินภาษีเข้าคลังกลาง (ตาราง treasury ใน game_data.db) พร้อม log ทุกยอดเข้า-ออก
"""
import sqlite3
import time

import bot.models.player_model as player_model
from bot import config_loader

# (เกณฑ์สัดส่วน %, คีย์ Panel, % หัก default) — เรียงจากรวยสุดลงมา เกณฑ์ตายตัวตามสเปค
_TIERS = [(90, "share_90_pct", 99), (75, "share_75_pct", 75), (50, "share_50_pct", 50)]


def _connect():
    conn = sqlite3.connect(player_model.DB_NAME)
    conn.execute("CREATE TABLE IF NOT EXISTS treasury "
                 "(id INTEGER PRIMARY KEY CHECK (id = 1), balance INTEGER NOT NULL DEFAULT 0)")
    conn.execute("""CREATE TABLE IF NOT EXISTS treasury_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        week TEXT, user_id INTEGER,
        amount INTEGER NOT NULL,
        note TEXT,
        created_at REAL NOT NULL)""")
    conn.execute("INSERT OR IGNORE INTO treasury (id, balance) VALUES (1, 0)")
    return conn


def enabled():
    try:
        return bool(int(config_loader.get_balance("weekly_tax.enabled", 1) or 0))
    except (TypeError, ValueError):
        return True


def balance():
    conn = _connect()
    try:
        return int(conn.execute("SELECT balance FROM treasury WHERE id = 1").fetchone()[0])
    finally:
        conn.close()


def add(amount, week="", user_id=None, note=""):
    """บวกเงินเข้าคลัง (จำนวนติดลบ = จ่ายออก) พร้อมจด log"""
    conn = _connect()
    try:
        conn.execute("UPDATE treasury SET balance = balance + ? WHERE id = 1", (int(amount),))
        conn.execute("INSERT INTO treasury_log (week, user_id, amount, note, created_at) "
                     "VALUES (?,?,?,?,?)", (week, user_id, int(amount), note, time.time()))
        conn.commit()
    finally:
        conn.close()


def recent_log(limit=10):
    """รายการเข้า-ออกคลังล่าสุด [(week, user_id, amount, note, created_at), ...]"""
    conn = _connect()
    try:
        return conn.execute("SELECT week, user_id, amount, note, created_at FROM treasury_log "
                            "ORDER BY id DESC LIMIT ?", (int(limit),)).fetchall()
    finally:
        conn.close()


def tax_pct(share_pct):
    """% ภาษีของคนที่ถือ share_pct% ของเงินทั้งเซิร์ฟ"""
    for threshold, key, default in _TIERS:
        if share_pct >= threshold:
            try:
                return max(0, min(100, int(config_loader.get_balance(f"weekly_tax.{key}", default) or 0)))
            except (TypeError, ValueError):
                return default
    return 0


def collect(week):
    """เก็บภาษีทั้งเซิร์ฟหนึ่งรอบ — คืน [(uid, wealth, share%, tax%, ยอดเก็บ), ...] เรียงยอดมากไปน้อย"""
    conn = sqlite3.connect(player_model.DB_NAME)
    try:
        rows = conn.execute("SELECT user_id, COALESCE(cash, 0), COALESCE(bank, 0) FROM players").fetchall()
    finally:
        conn.close()
    total = sum(c + b for _, c, b in rows)
    if total <= 0:
        return []

    taxed = []
    for uid, cash, bank in rows:
        wealth = cash + bank
        if wealth <= 0:
            continue
        share = wealth * 100.0 / total
        pct = tax_pct(share)
        if pct <= 0:
            continue
        take = wealth * pct // 100
        take_bank = min(bank, take)          # หักจากธนาคารก่อน เหลือค่อยหักเงินติดตัว
        player_model.update_player_field(uid, "bank", bank - take_bank)
        if take - take_bank:
            player_model.update_player_field(uid, "cash", cash - (take - take_bank))
        add(take, week=week, user_id=uid, note=f"ภาษีรวย {pct}% (ถือ {share:.1f}% ของเซิร์ฟ)")
        taxed.append((uid, wealth, share, pct, take))
        print(f"[LOG] [WEEKLY_TAX] 🏛️ {uid} ถือ {share:.1f}% ของเซิร์ฟ → เก็บ {pct}% = {take:,} ทอง")
    return sorted(taxed, key=lambda t: t[4], reverse=True)
