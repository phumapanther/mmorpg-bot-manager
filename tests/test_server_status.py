"""แจ้งเตือนเปิด-ปิดเซิร์ฟ: config + การจับมือผ่านไฟล์ธง"""
import asyncio
import json
import subprocess
import time
from types import SimpleNamespace

import panel.process_manager as pmgr


def test_server_status_channel_in_config():
    ch = json.load(open("config.example.json", encoding="utf-8"))["channels"]
    assert ch["server_status"]["channel_id"] is None
    assert "เปิด-ปิดเซิร์ฟ" in ch["server_status"]["label"]


def test_flag_lives_outside_the_synced_project_folder():
    """ธงต้องไม่อยู่ในโฟลเดอร์โปรเจกต์ — OneDrive ซิงค์ไฟล์กลับมาเองแล้วบอทหลักดับกลางอากาศ
    และ panel กับบอทต้องชี้ path เดียวกันเสมอ (คนละ path = ปุ่ม Stop ไม่ทำงาน)"""
    import bot.cogs.server_status as ss
    from app_paths import get_app_root, get_shutdown_flag
    assert ss.SHUTDOWN_FLAG == get_shutdown_flag()
    assert not ss.SHUTDOWN_FLAG.startswith(get_app_root())


def test_stale_flag_is_ignored(tmp_path, monkeypatch):
    """ธงเก่า (ไฟล์ค้าง/ถูกซิงค์กลับมา) ต้องถูกทิ้ง ไม่ใช่สั่งปิดบอท

    ⚠️ ต้อง patch ที่โมดูลจริง (bot.apps.bot_worker.server_status) ไม่ใช่ที่สะพาน
    bot.cogs.server_status — ฟังก์ชันมองตัวแปร global ของไฟล์ที่นิยามจริง
    """
    import bot.apps.bot_worker.server_status as ss
    flag = tmp_path / "stale.flag"
    flag.write_text("")
    monkeypatch.setattr(ss, "SHUTDOWN_FLAG", str(flag))
    monkeypatch.setattr(ss.os.path, "getmtime", lambda p: time.time() - 999)

    closed = []
    cog = ss.ServerStatus.__new__(ss.ServerStatus)          # ข้าม __init__ (มันสตาร์ท loop)
    cog.bot = SimpleNamespace(close=lambda: closed.append(1), get_channel=lambda cid: None)
    asyncio.run(ss.ServerStatus.watch_shutdown.coro(cog))

    assert not closed, "ธงเก่าห้ามทำให้บอทปิดตัวเอง"
    assert not flag.exists(), "ธงเก่าต้องถูกเก็บกวาดทิ้ง"


def test_panel_stop_writes_flag_and_waits(tmp_path, monkeypatch):
    """stop() ต้องวางธงก่อน แล้วรอบอทปิดเอง — บอทตอบทัน = ไม่โดน terminate"""
    flag = tmp_path / "shutdown.flag"
    monkeypatch.setattr(pmgr, "get_shutdown_flag", lambda: str(flag))
    events = []

    def wait(timeout=None):
        # จำลองบอทเห็นธงแล้วปิดตัวเองทันเวลา
        events.append(("wait", flag.exists()))
        return 0

    fake = SimpleNamespace(poll=lambda: None, wait=wait,
                           terminate=lambda: events.append(("terminate", None)),
                           kill=lambda: events.append(("kill", None)))
    monkeypatch.setattr(pmgr, "_proc", fake)
    pmgr.stop()
    assert events == [("wait", True)]     # ธงถูกวางก่อนรอ และไม่มีการฆ่า
    assert not flag.exists()              # ธงถูกเก็บกวาด


def test_panel_stop_falls_back_to_terminate(tmp_path, monkeypatch):
    """บอทไม่ตอบใน 6 วิ → terminate ตามเดิม"""
    monkeypatch.setattr(pmgr, "get_shutdown_flag", lambda: str(tmp_path / "shutdown.flag"))
    events = []
    calls = {"n": 0}

    def wait(timeout=None):
        calls["n"] += 1
        if calls["n"] == 1:
            raise subprocess.TimeoutExpired(cmd="bot", timeout=timeout)
        return 0

    fake = SimpleNamespace(poll=lambda: None, wait=wait,
                           terminate=lambda: events.append("terminate"),
                           kill=lambda: events.append("kill"))
    monkeypatch.setattr(pmgr, "_proc", fake)
    pmgr.stop()
    assert events == ["terminate"]
