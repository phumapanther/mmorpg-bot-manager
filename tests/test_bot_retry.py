"""เน็ต/DNS ล่มตอนสตาร์ท ต้องลองใหม่เอง ไม่ใช่ทั้งโปรเซสตาย (เคสจริง 2026-08-10)

โทเค็นผิด/intents ไม่เปิด = หยุดเลย ลองใหม่กี่รอบก็ไม่ติด ต้องรอคนแก้
"""
import asyncio
import socket

import aiohttp
import discord
import pytest

from bot import main as bot_main


def _run(coro, monkeypatch):
    """รันโดยไม่ต้องรอ sleep จริง — เก็บเวลาที่สั่งรอไว้ตรวจ backoff"""
    slept = []

    async def fake_sleep(sec):
        slept.append(sec)
    monkeypatch.setattr(bot_main.asyncio, "sleep", fake_sleep)
    asyncio.run(coro())
    return slept


def _factory(monkeypatch, errors):
    """create_bot ปลอม: โยน error ตามคิว หมดคิวแล้วถือว่าเปิดสำเร็จ"""
    calls = []

    def create_bot(bot_type):
        async def start(token):
            calls.append((bot_type, token))
            if errors:
                raise errors.pop(0)
        return start
    monkeypatch.setattr(bot_main, "create_bot", create_bot)
    return calls


def test_retries_on_dns_failure_then_succeeds(monkeypatch):
    # gaierror = ต้นเหตุจริงที่ทำบอทตาย (DNS resolve discord.com ไม่ได้) + ฝั่ง aiohttp
    calls = _factory(monkeypatch, [socket.gaierror(11001, "getaddrinfo failed"),
                                   aiohttp.ClientError("connection reset")])
    slept = _run(lambda: bot_main.run_with_retry("game", "tok", "GAME"), monkeypatch)
    assert len(calls) == 3                       # ล้ม 2 ครั้ง แล้วติดรอบที่ 3
    assert slept == [15, 30]                     # ถอยหลังเพิ่มเป็นเท่าตัว


def test_backoff_capped(monkeypatch):
    _factory(monkeypatch, [OSError("boom")] * 8)
    slept = _run(lambda: bot_main.run_with_retry("game", "tok", "GAME"), monkeypatch)
    assert max(slept) == bot_main.RETRY_DELAY_MAX
    assert slept == [15, 30, 60, 120, 240, 300, 300, 300]


@pytest.mark.parametrize("err", [
    discord.LoginFailure("bad token"),
    discord.PrivilegedIntentsRequired(shard_id=None),
    ValueError("อะไรก็ไม่รู้"),
])
def test_gives_up_without_retry(monkeypatch, err):
    calls = _factory(monkeypatch, [err])
    slept = _run(lambda: bot_main.run_with_retry("game", "tok", "GAME"), monkeypatch)
    assert len(calls) == 1 and slept == []       # เรียกครั้งเดียว ไม่รอ ไม่วน


def test_creates_fresh_bot_each_attempt(monkeypatch):
    """discord.py ปิด Client แล้วเปิดตัวเดิมซ้ำไม่ได้ — ต้องเรียก create_bot ใหม่ทุกรอบ"""
    made = []

    def create_bot(bot_type):
        made.append(bot_type)

        async def start(token):
            if len(made) < 3:
                raise OSError("เน็ตหลุด")
        return start
    monkeypatch.setattr(bot_main, "create_bot", create_bot)
    _run(lambda: bot_main.run_with_retry("guest", "tok", "Guest Bot"), monkeypatch)
    assert made == ["guest", "guest", "guest"]
