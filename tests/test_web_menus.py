"""📚 เมนูสะสม/รางวัลที่ยกจากดิสขึ้นเว็บ

หลักการเดียวกับทุกเมนู: ตรรกะอยู่ในโมดูลกลาง เว็บแค่แปลงเป็น JSON
เทสชุดนี้คุมว่า (1) ทุกปุ่มบนหน้าเว็บมีแผงรองรับจริง (2) เว็บไม่คิดกฎเกมเอง
"""
import pathlib
import re

HTML = pathlib.Path("license_server/web_static/play.html").read_text(encoding="utf-8")
JS = pathlib.Path("license_server/web_static/play.js").read_text(encoding="utf-8")
API = pathlib.Path("license_server/web_api.py").read_text(encoding="utf-8")

MENUS = {"pets": "fillPets", "daily": "fillDaily", "achv": "fillAchv",
         "books": "fillBooks", "season": "fillSeason", "partner": "fillPartner"}


def test_every_menu_button_opens_a_panel_that_exists():
    """กดปุ่มแล้วต้องมีแผงให้เปิด ไม่ใช่หน้าว่าง"""
    for go in set(re.findall(r'data-go="(\w+)"', HTML)):
        assert f'id="v-{go}"' in HTML, f'ปุ่ม {go} ไม่มีแผง v-{go} รองรับ'


def test_every_new_panel_loads_its_data():
    for panel, fn in MENUS.items():
        assert f'id="v-{panel}"' in HTML, f"ไม่มีแผง {panel}"
        assert f"if (id === '{panel}') {fn}(" in JS, f"เปิดแผง {panel} แล้วไม่โหลดข้อมูล"
        assert f"async function {fn}(" in JS


def test_the_web_reads_from_the_same_modules_as_discord():
    """ห้ามคำนวณกฎเกมในเว็บเอง — ต้องเรียกโมดูลเดียวกับคำสั่งในดิส"""
    for mod in ("pets", "daily", "achievements", "season", "partner"):
        assert f"from bot import {mod}" in API or f"from bot import config_loader, {mod}" in API \
            or f", {mod}" in API, f"API ไม่ได้เรียกโมดูล {mod}"


def test_actions_that_spend_gold_ask_first():
    """ซื้อสายพรีเมียมเป็นการจ่ายทองก้อน ต้องเด้งยืนยันก่อนเสมอ"""
    block = JS[JS.index("async function fillSeason("):]
    assert "confirmAction(" in block[:2200], "ปุ่มซื้อสายพรีเมียมไม่ได้ถามยืนยัน"


def test_pet_equip_goes_through_the_shared_rule():
    """ติดสัตว์เลี้ยงที่ยังไม่ได้จับต้องไม่ได้ — กฎอยู่ใน pets.set_active"""
    assert "pets.set_active(uid, body.key)" in API


def test_marriage_stays_in_discord_and_says_so():
    """ขอแต่งงานต้องแท็กอีกฝ่าย เว็บทำไม่ได้ — ต้องบอกผู้เล่นให้ชัด ไม่ใช่ปุ่มตาย"""
    panel = HTML[HTML.index('id="v-partner"'):]
    assert "!marry" in panel[:900], "หน้าคู่หูต้องบอกว่าขอแต่งงานทำที่ไหน"
    assert "marry" not in JS, "เว็บต้องไม่พยายามขอแต่งงานเอง"


def test_no_menu_button_is_left_marked_as_coming_later_without_reason():
    """ปุ่มที่ยังไม่ทำต้องเหลือเฉพาะของที่ยังไม่มีระบบจริง"""
    soon = re.findall(r'<button class="g-tile soon">.*?<span class="ic">[^<]*</span>([^<]+)<',
                      HTML, re.S)
    left = {s.strip() for s in soon}
    assert left <= {"เดินต่อ ×5", "สรุปทุกทวีป", "ตลาดผู้เล่น", "ไปต่างโลก"}, \
        f"ยังมีปุ่มค้างที่ควรทำได้แล้ว: {left}"
