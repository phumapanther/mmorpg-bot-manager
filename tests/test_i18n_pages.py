"""🌐 หน้าเว็บผู้เล่น — ข้อความไทยทุกจุดต้องติดป้าย data-i18n* หรือห่อ tr() แล้ว

ลืมติดป้าย = ผู้เล่นต่างชาติเห็นภาษาไทยโผล่กลางหน้า โดยไม่มีอะไรเตือนเลย
กฎการติดป้ายอยู่ใน docs/superpowers/plans/2026-10-05-i18n-chunk1-web.md หัวข้อ "วิธีติดป้ายหน้า HTML"
"""
import pathlib

import pytest

from scripts import i18n_extract as X

WEB = pathlib.Path("license_server/web_static")
# หน้าที่แปลเสร็จแล้ว — เพิ่มทีละหน้า (แผนก้อน 1 Task 5-7)
DONE_PAGES = ["index.html", "login.html", "me.html", "news.html", "topup.html", "game.html"]


@pytest.mark.parametrize("page", DONE_PAGES)
def test_ข้อความไทยในหน้าติดป้ายครบ(page):
    _keys, problems = X.scan_html((WEB / page).read_text(encoding="utf-8"), page)
    assert not problems, "\n".join(problems)
