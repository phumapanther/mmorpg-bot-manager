"""คู่มือต้องตรงกับเกมปัจจุบันเสมอ — กันเพิ่มฟีเจอร์แล้วลืมอัปเดตคู่มือ

เคสจริง (2026-08-01): หน้า "วิธีเล่น" ยังเขียนว่าอาร์ติแฟกต์ "มีช่องเดียว สวมทับแล้ว
ของเก่าถูกทำลายถาวร" ทั้งที่เปลี่ยนเป็นระบบช่อง 5 ช่อง + ถอดได้ไปแล้ว
"""
import json
import pathlib
import re

import pytest

from bot import config_loader
from bot import game_modifiers as gm
from bot.cogs.player_commands import build_codex_embed, _item_effect_desc
from bot.views.menu_view import CODEX_TOPICS

ITEMS = config_loader.get_all_items()


def _page_text(topic):
    e = build_codex_embed(topic)
    return (e.description or "") + " ".join(f.name + f.value for f in e.fields) + (e.footer.text or "")


ALL_TEXT = " ".join(_page_text(v) for _lbl, v in CODEX_TOPICS)


# ── ครบถ้วน ──

def test_every_item_effect_has_a_description():
    """ไอเทมที่มี effect ต้องอธิบายผลได้ ไม่งั้นหน้า 'ไอเทม' โชว์ช่องว่าง"""
    blank = [f"{i} {it['name']} (effect={it['effect']})"
             for i, it in ITEMS.items() if it.get("effect") and not _item_effect_desc(it)]
    assert not blank, "ไอเทมที่คู่มืออธิบายผลไม่ได้:\n  " + "\n  ".join(blank)


def test_every_status_and_item_appears_somewhere():
    for key, cfg in gm.STATUS_EFFECTS.items():
        if cfg.get("artifact"):
            continue
        assert cfg["label"] in ALL_TEXT, f"สถานะ {cfg['label']} ไม่ถูกพูดถึงในคู่มือเลย"
    for iid, it in ITEMS.items():
        assert it["name"] in ALL_TEXT, f"ไอเทม {iid} {it['name']} ไม่อยู่ในคู่มือ"


@pytest.mark.parametrize("cmd", ["!daily", "!season", "!top", "!ach", "!pet",
                                 "!market", "!marry", "!bestiary", "!guild", "!bounty"])
def test_every_player_system_is_mentioned(cmd):
    assert cmd in ALL_TEXT, f"คู่มือไม่ได้พูดถึง {cmd} เลย"


# ── ไม่ล้าสมัย ──

def test_no_page_still_claims_the_old_single_artifact_slot():
    stale = ["มีช่องเดียว", "สวมทับแล้วของเก่าถูกทำลาย", "สวมทับ = ของเก่า"]
    for phrase in stale:
        assert phrase not in ALL_TEXT, (
            f"คู่มือยังเขียนกติกาเก่าอยู่: '{phrase}' — ตอนนี้เป็นระบบช่อง เจาะเพิ่มได้/ถอดได้")


def test_artifact_slot_cap_matches_config():
    cap = int(config_loader.get_balance("artifact.max_slots", 5))
    assert f"{cap} ช่อง" in _page_text("อาร์ติแฟกต์"), "เพดานช่องในคู่มือไม่ตรงกับ config"


def test_how_to_play_covers_the_daily_loop():
    """หน้าแรกที่ผู้เล่นใหม่อ่าน ต้องบอกระบบที่ทำให้กลับมาเล่นทุกวัน"""
    text = _page_text("วิธีเล่น")
    for needed in ("!daily", "!season", "!top", "!market", "⏩", "อาร์ติแฟกต์"):
        assert needed in text, f"หน้า 'วิธีเล่น' ไม่ได้พูดถึง {needed}"


def test_menu_and_index_agree():
    index = build_codex_embed("").description
    for _label, value in CODEX_TOPICS:
        assert f"`!codex {value}`" in index, f"สารบัญขาดหัวข้อ {value}"
        assert build_codex_embed(value).fields, f"หัวข้อ {value} เปิดแล้วว่าง"


def test_pages_fit_discord_limits():
    for _label, value in CODEX_TOPICS:
        e = build_codex_embed(value)
        assert len(e) <= 6000, f"หน้า {value} ยาวเกิน 6000"
        assert len(e.fields) <= 25, f"หน้า {value} เกิน 25 ช่อง"
        for f in e.fields:
            assert len(str(f.value)) <= 1024, f"หน้า {value} ช่อง {f.name} ยาวเกิน 1024"
