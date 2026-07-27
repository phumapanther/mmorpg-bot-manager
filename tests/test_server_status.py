"""แจ้งเตือนเปิด-ปิดเซิร์ฟ: config + การจับมือผ่านไฟล์ธง"""
import json
import subprocess
from types import SimpleNamespace

import panel.process_manager as pmgr


def test_server_status_channel_in_config():
    ch = json.load(open("config.example.json", encoding="utf-8"))["channels"]
    assert ch["server_status"]["channel_id"] is None
    assert "เปิด-ปิดเซิร์ฟ" in ch["server_status"]["label"]


def test_cog_importable_and_flag_path():
    import bot.cogs.server_status as ss
    assert ss.SHUTDOWN_FLAG.endswith("shutdown_request.flag")


def test_panel_stop_writes_flag_and_waits(tmp_path, monkeypatch):
    """stop() ต้องวางธงก่อน แล้วรอบอทปิดเอง — บอทตอบทัน = ไม่โดน terminate"""
    monkeypatch.setattr(pmgr, "_ROOT", str(tmp_path))
    events = []

    def wait(timeout=None):
        # จำลองบอทเห็นธงแล้วปิดตัวเองทันเวลา
        events.append(("wait", (tmp_path / "shutdown_request.flag").exists()))
        return 0

    fake = SimpleNamespace(poll=lambda: None, wait=wait,
                           terminate=lambda: events.append(("terminate", None)),
                           kill=lambda: events.append(("kill", None)))
    monkeypatch.setattr(pmgr, "_proc", fake)
    pmgr.stop()
    assert events == [("wait", True)]                       # ธงถูกวางก่อนรอ และไม่มีการฆ่า
    assert not (tmp_path / "shutdown_request.flag").exists()  # ธงถูกเก็บกวาด


def test_panel_stop_falls_back_to_terminate(tmp_path, monkeypatch):
    """บอทไม่ตอบใน 6 วิ → terminate ตามเดิม"""
    monkeypatch.setattr(pmgr, "_ROOT", str(tmp_path))
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
