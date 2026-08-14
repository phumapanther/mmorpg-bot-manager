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


def test_the_premium_price_shown_is_the_price_charged():
    """เคยพลาด: หน้าเว็บอ่านคีย์ที่ไม่มีจริง เลยโชว์ 'ราคา 0 ทอง' ทั้งที่หักจริง 5 ล้าน
    ตัวที่โชว์กับตัวที่หักต้องอ่านจากฟังก์ชันเดียวกันเสมอ"""
    from bot import season
    import inspect
    charge = inspect.getsource(season.buy_premium)
    assert "premium_price()" in charge, "ตัวหักเงินไม่ได้ใช้ premium_price()"
    assert "season.premium_price()" in API, "API ไม่ได้ใช้ premium_price() ตัวเดียวกัน"
    assert season.premium_price() > 0, "ราคาต้องอ่านออก ไม่ใช่ 0"


def test_the_price_is_visible_before_you_click():
    """ราคาต้องอยู่บนปุ่มตั้งแต่แรก ไม่ใช่ไปเห็นตอนป็อปอัพเด้ง"""
    block = JS[JS.index("async function fillSeason("):]
    assert "d.premium_price" in block[:1800]
    assert "buy.innerHTML" in block[:1800], "ปุ่มไม่ได้อัปเดตข้อความให้มีราคา"


def test_a_closed_season_disables_the_button():
    block = JS[JS.index("async function fillSeason("):]
    assert "!d.enabled" in block[:1800], "ซีซั่นปิดอยู่ต้องกดซื้อไม่ได้"


# ── 🎲 สรุปเต๋า + ความทนทาน (คำถามจากผู้เล่นจริง 2026-08-14) ──────────────────

def test_the_dice_summary_is_computed_on_the_server():
    """ผู้เล่นถามว่าทำไมไม่เคยทอยเกิน 20 — คำตอบต้องมาจากเซิร์ฟเวอร์ ไม่ให้เบราว์เซอร์คิดเอง"""
    assert "def _dice_view(" in API
    for field in ("dice_count", "normal_cap", "skill_cap", "bonus_total"):
        assert f'"{field}"' in API, f"สรุปเต๋าไม่มี {field}"
    assert "prDice" in JS and "normal_cap" in JS


def test_the_dice_count_grows_with_level_and_pets():
    """เดิมทุกคนทอยลูกเดียวตายตัว — ตอนนี้ +1 ลูกทุก 25 เลเวล และสัตว์เลี้ยงเพิ่มอีก"""
    from bot import adventure_core
    assert adventure_core.player_dice_count({"level": 1, "pet": ""})[0] == 1
    assert adventure_core.player_dice_count({"level": 24, "pet": ""})[0] == 1
    assert adventure_core.player_dice_count({"level": 25, "pet": ""})[0] == 2
    assert adventure_core.player_dice_count({"level": 100, "pet": ""})[0] == 5
    with_pet = adventure_core.player_dice_count({"level": 25, "pet": "wolfpup"})
    assert with_pet[0] == 4 and with_pet[2] == 2, "หมาป่าต้องเพิ่ม 2 ลูก"


def test_pet_dice_are_small_so_points_do_not_inflate():
    """เต๋าสัตว์เลี้ยงลูกละ 1-6 เท่านั้น ไม่ใช่เต็มช่วงเหมือนเต๋าตัวเอง"""
    core = pathlib.Path("bot/adventure_core.py").read_text(encoding="utf-8")
    assert 'config_loader.get_balance("dice.pet_die_max", 6)' in core
    assert "rng.randint(1, pet_die_max) for _ in range(pet_dice)" in core

    import json
    cfg = json.load(open("config.example.json", encoding="utf-8"))
    assert cfg["game_balance"]["dice"]["pet_die_max"] == 6


def test_dice_count_has_a_ceiling(monkeypatch):
    """กันเต๋าเฟ้อจนไร้ความหมาย — ต้องมีเพดานจำนวนลูก"""
    from bot import adventure_core, config_loader
    monkeypatch.setattr(config_loader, "get_balance",
                        lambda k, d=None: {"dice.level_per_die": 1, "dice.max_dice": 8}.get(k, d))
    assert adventure_core.player_dice_count({"level": 9999, "pet": "dragonling"})[0] == 8


def test_both_platforms_share_the_dice_count_rule():
    """ดิสกับเว็บใช้ roll_combat ตัวเดียวกัน จำนวนเต๋าจึงต้องตรงกันเสมอ"""
    core = pathlib.Path("bot/adventure_core.py").read_text(encoding="utf-8")
    assert "my_dice, lvl_dice, pet_dice = player_dice_count(player)" in core
    gv = pathlib.Path("bot/views/game_views.py").read_text(encoding="utf-8")
    assert "adventure_core.fight_turn(" in gv, "ดิสต้องเรียกเส้นทางเดียวกัน"


def test_max_hp_shown_includes_the_armor_bonus():
    """เคยโชว์ '380 / 280' เพราะ HP รวมโบนัสเกราะแต่ตัวหารไม่รวม อ่านแล้วงง"""
    block = API[API.index('"vitals": {'):API.index('"money": {')]
    assert 'armor.get("hp", 0)' in block, "HP เต็มต้องรวมโบนัสเกราะ"
    assert 'p.get("armor_dur", 0) > 0' in block, "เกราะพังแล้วต้องไม่นับโบนัส"


def test_durability_is_shown_as_a_percent_in_both_places():
    """ผู้เล่นขอ % ความพังของเกราะ/อาวุธทั้งหน้าโปรไฟล์และหน้าผจญภัย"""
    assert "ความทนทาน ${pct}%" in JS, "หน้าโปรไฟล์ยังไม่โชว์ %"
    assert "${pct}%</b>" in JS, "หน้าผจญภัยยังไม่โชว์ %"
    assert "พังแล้ว! ไม่ได้โบนัส" in JS, "เกราะพังต้องบอกว่าเสียโบนัสไปแล้ว"


def test_durability_percent_is_relative_to_each_items_own_maximum():
    """เคยโชว์ 'เกราะ 367%' เพราะเอาเลขความทนทานดิบไปติด % ตรง ๆ
    ของเต็มต่างกันตามชิ้น (อาวุธไม้ 50 · เหล็ก 150 · ตำนาน 1000 · เกราะเหล็กหนัก 500)"""
    from license_server.web_api import _dur_pct
    assert _dur_pct(367, 500) == 73
    assert _dur_pct(106, 150) == 71
    assert _dur_pct(45, 50) == 90
    assert _dur_pct(0, 500) == 0
    assert _dur_pct(999, 100) == 100, "ค่าเกินของเต็มต้องตัดที่ 100 ไม่ใช่ปล่อยทะลุ"
    assert _dur_pct(None, 100) is None


def test_the_api_sends_the_maximum_so_the_page_can_do_the_maths():
    assert '"dur_max"' in API and '"dur_pct"' in API
    assert "o.dur_pct" in JS, "หน้าเว็บต้องใช้ % ที่เซิร์ฟเวอร์คิดให้ ไม่คิดเอง"
    assert "${o.dur}%" not in JS, "ยังมีที่เอาเลขดิบไปติด % ตรง ๆ อยู่"


def test_the_dice_cap_trims_pet_dice_not_your_own():
    """เต๋าที่ปั้นมาเองจากเลเวลต้องไม่โดนเพดานกิน — ตัดของสัตว์เลี้ยงก่อนเสมอ"""
    from bot import adventure_core
    total, lvl, pet = adventure_core.player_dice_count({"level": 100, "pet": "dragonling"})
    assert total == 8 and total - pet == 1 + lvl, \
        f"Lv100 ควรได้เต๋าตัวเอง {1+lvl} ลูกครบ แต่ได้ {total-pet}"
