"""O6: รวมอันดับ 4 หมวดเป็น !top หน้าเดียว"""
import sqlite3
from types import SimpleNamespace

import bot.cogs.player_commands as pc
import bot.models.player_model as pm


def _db(tmp_path, monkeypatch):
    monkeypatch.setattr(pm, "DB_NAME", str(tmp_path / "t.db"))
    conn = sqlite3.connect(pm.DB_NAME)
    conn.execute("""CREATE TABLE players (user_id INTEGER PRIMARY KEY, cash INT, bank INT,
                    level INT, exp INT, total_text INT, total_online_time INT)""")
    conn.executemany("INSERT INTO players VALUES (?,?,?,?,?,?,?)", [
        (1, 500, 500, 10, 0, 50, 7200),      # รวย 1000
        (2, 100, 5000, 99, 0, 10, 100),      # รวยสุด 5100 + เลเวลสุด
        (3, 0, 0, 1, 0, 999, 60),            # แชทเยอะสุด
    ])
    conn.commit()
    conn.close()


def test_leaderboard_all_kinds(tmp_path, monkeypatch):
    _db(tmp_path, monkeypatch)
    assert [u for u, _ in pm.get_leaderboard("rich")][0] == 2
    assert [u for u, _ in pm.get_leaderboard("level")][0] == 2
    assert [u for u, _ in pm.get_leaderboard("text")][0] == 3
    assert [u for u, _ in pm.get_leaderboard("time")][0] == 1
    assert pm.get_leaderboard("ไม่มีหมวดนี้") == []


def test_my_rank(tmp_path, monkeypatch):
    _db(tmp_path, monkeypatch)
    rank, value, total = pm.get_my_rank(1, "rich")
    assert rank == 2 and value == 1000 and total == 3
    assert pm.get_my_rank(999, "rich") is None      # ไม่มีตัวละคร


def test_top_embed_marks_viewer(tmp_path, monkeypatch):
    _db(tmp_path, monkeypatch)
    embed = pc.build_top_embed("rich", viewer_id=1)
    assert "🥇" in embed.description and "<@2>" in embed.description
    assert "⬅️ **คุณ**" in embed.description                 # ไฮไลต์แถวตัวเอง
    assert "อันดับของคุณ" in embed.fields[0].name and "2" in embed.fields[0].value


def test_top_view_and_aliases():
    from bot.views.menu_view import TopBoardView
    assert len(TopBoardView(1).children) == 5      # 4 หมวดเดิม + 🗓️ สัปดาห์นี้ (C3)
    cmd = pc.PlayerCommands.top_board
    assert set(cmd.aliases) >= {"rich", "toplvl", "toptext", "toptime"}   # คำสั่งเดิมยังใช้ได้
