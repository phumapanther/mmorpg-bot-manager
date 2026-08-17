"""🎁 กาชาแฟชั่น — จ่ายด้วยทอง เป็นทางเดียวที่จะได้แฟชั่น

ตู้กาชาเป็นจุดที่พังแล้วเจ็บที่สุดในเกม: หมุนแล้วไม่หักเงิน / หักเงินแล้วไม่ได้ของ /
สุ่มออกของที่ห้ามหลุด / กดรัวสองหน้าต่างแล้วได้ฟรี
เทสไฟล์นี้จึงคุมเรื่อง "เงินกับของต้องตรงกันเสมอ" เป็นหลัก
"""
import datetime
import json
import pathlib
import random
import re

import pytest

import bot.models.player_model as pm
from bot import fashion

UID = 8802
RICH = 10_000_000_000            # ทองเยอะพอหมุนได้เรื่อย ๆ


@pytest.fixture
def world(tmp_path, monkeypatch):
    monkeypatch.setattr(pm, "DB_NAME", str(tmp_path / "g.db"))
    pm.init_db()
    pm.get_player(UID)
    pm.update_player_fields(UID, {"cash": RICH, "capacity": 999, "level": 100})
    monkeypatch.setattr(fashion, "_starter_sets_free", lambda: False)
    return None


def _p():
    return pm.get_player(UID)


def _cash():
    return int(_p()["cash"])


def _gems():
    return int(_p()["fashion_gems"] or 0)


# ── เงินกับของต้องตรงกันเสมอ ──

def test_a_pull_costs_exactly_the_listed_price(world):
    before = _cash()
    ok, r = fashion.pull(UID, "single", random.Random(1))
    assert ok
    # ของที่ได้อาจถูกขายทิ้งเป็นทองคืนมาได้ (กระเป๋าเต็ม) — ที่นี่กระเป๋าว่าง จึงต้องหักเต็ม
    assert _cash() == before - fashion.GACHA_TIERS["single"]["price"]
    assert r["cash"] == _cash(), "ทองที่ตอบกลับไม่ตรงกับในดาต้าเบส"


def test_no_gold_no_pull(world):
    pm.update_player_field(UID, "cash", 5)
    ok, r = fashion.pull(UID, "single", random.Random(1))
    assert not ok and "ไม่พอ" in r["error"]
    assert _cash() == 5, "หมุนไม่สำเร็จแต่เงินหาย"
    assert _p()["fashion_owned"] == "[]", "หมุนไม่สำเร็จแต่ได้ของ"


def test_a_made_up_button_does_nothing(world):
    before = _cash()
    ok, _ = fashion.pull(UID, "ปุ่มปลอม", random.Random(1))
    assert not ok and _cash() == before


def test_ten_pull_gives_exactly_ten_results(world):
    ok, r = fashion.pull(UID, "ten", random.Random(7))
    assert ok
    rolls = [x for x in r["pulls"] if x["kind"] != "bonus"]
    assert len(rolls) == 10, f"ซื้อ 10 ครั้งแต่ได้ {len(rolls)} ครั้ง"


def test_ten_pull_always_pays_at_least_one_gem(world):
    """ต่อให้ดวงแย่ที่สุด ชุด 10 ครั้งต้องได้อัญมณีอย่างน้อย 1 เม็ด (เพดานความซวย)"""
    for seed in range(25):
        pm.update_player_fields(UID, {"cash": RICH, "fashion_gems": 0,
                                      "fashion_owned": "[]", "inventory": "[]"})
        ok, _ = fashion.pull(UID, "ten", random.Random(seed))
        assert ok and _gems() >= 1, f"เมล็ด {seed}: หมุน 10 ครั้งแล้วไม่ได้อัญมณีเลย"


def test_the_cheap_button_never_promises_a_gem(world):
    """ปุ่ม 1M ไม่มีการันตี ไม่งั้นปุ่มแพงไม่มีเหตุผลให้กด"""
    assert "free_gems" not in fashion.GACHA_TIERS["single"]


# ── ได้ซ้ำ → อัญมณี ──

def test_a_duplicate_becomes_a_gem_not_a_second_copy(world):
    pm.update_player_field(UID, "fashion_owned", json.dumps(sorted(fashion.CATALOG)))
    got_dup = False
    for seed in range(60):
        pm.update_player_fields(UID, {"cash": RICH, "fashion_gems": 0})
        ok, r = fashion.pull(UID, "lucky", random.Random(seed))
        dups = [x for x in r["pulls"] if x["kind"] == "dup"]
        if dups:
            got_dup = True
            assert _gems() == len(dups), "ได้ซ้ำแล้วอัญมณีไม่เพิ่มตามจำนวน"
            owned = json.loads(_p()["fashion_owned"])
            assert len(owned) == len(set(owned)) == len(fashion.CATALOG), "ของซ้ำถูกยัดเข้าตู้"
    assert got_dup, "หมุน 60 รอบด้วยตู้เต็มแล้วยังไม่เจอของซ้ำเลย — เรทเพี้ยน"


def test_owned_fashion_survives_more_pulls(world):
    """หมุนต่ออีกหลายรอบ ของที่มีอยู่แล้วต้องไม่หายไปไหน"""
    keys = set()
    for seed in range(40):
        pm.update_player_field(UID, "cash", RICH)
        fashion.pull(UID, "lucky", random.Random(seed))
        now = set(json.loads(_p()["fashion_owned"]))
        assert keys <= now, f"ของหายไป: {sorted(keys - now)}"
        keys = now


# ── ของที่ห้ามหลุดออกจากตู้ ──

def test_the_gacha_never_prints_forbidden_items(world):
    """สว่านเจาะช่อง/ทองคำแท่ง/แหวนแต่งงาน ห้ามหลุดจากกาชา (กฎเดียวกับหีบสมบัติ)"""
    from bot.adventure_core import is_random_rewardable
    from bot import config_loader

    items = config_loader.get_all_items()
    seen = set()
    for seed in range(120):
        pm.update_player_fields(UID, {"cash": RICH, "inventory": "[]"})
        ok, r = fashion.pull(UID, "ten", random.Random(seed))
        seen |= {x["item"] for x in r["pulls"] if x.get("item")}
    bad = [items[i]["name"] for i in seen
           if not is_random_rewardable(items[i]) and items[i].get("effect") != "equip_artifact"]
    assert not bad, f"ของต้องห้ามหลุดจากกาชา: {sorted(set(bad))}"


def test_the_gacha_cannot_mint_crypto(world):
    """กาชา + ถอนเป็นเงินจริง = เข้าใกล้การพนัน — ห้ามชนกันเด็ดขาด"""
    src = pathlib.Path("bot/fashion.py").read_text(encoding="utf-8")
    for banned in ("coin", "crypto", "withdraw", "bar_value"):
        assert banned not in src.lower().replace("# ", ""), \
            f"fashion.py ไปยุ่งกับ {banned} — ตู้กาชาห้ามออกของที่ถอนเป็นเงินจริงได้"


def test_a_full_bag_pays_gold_instead_of_swallowing_the_prize(world):
    """กระเป๋าเต็มแล้วยังหมุนได้ แต่ต้องได้ทองคืน ไม่ใช่จ่ายเงินแล้วของหายเฉย ๆ"""
    pm.update_player_fields(UID, {"capacity": 1, "inventory": json.dumps(["1"])})
    for seed in range(30):
        pm.update_player_field(UID, "cash", RICH)
        ok, r = fashion.pull(UID, "ten", random.Random(seed))
        sold = [x for x in r["pulls"] if x["kind"] == "sold"]
        if sold:
            assert _cash() > RICH - fashion.GACHA_TIERS["ten"]["price"], "ของล้นกระเป๋าแต่ไม่ได้ทองคืน"
            assert len(pm.load_inventory(_p()["inventory"])) == 1, "กระเป๋าเต็มแล้วยังยัดของเข้าไปอีก"
            return
    pytest.fail("กระเป๋าเต็ม 30 รอบแล้วไม่มีของล้นเลย — เทสอ่านผลผิด")


# ── 💎 แลกอัญมณี ──

def test_ten_gems_buy_one_piece(world):
    need = fashion.GEMS_PER_EXCHANGE
    pm.update_player_field(UID, "fashion_gems", need)
    ok, msg = fashion.exchange(UID, "light_knight")
    assert ok, msg
    assert _gems() == 0
    assert "light_knight" in fashion.owned(_p())


def test_nine_gems_buy_nothing(world):
    pm.update_player_field(UID, "fashion_gems", fashion.GEMS_PER_EXCHANGE - 1)
    ok, msg = fashion.exchange(UID, "light_knight")
    assert not ok and "ไม่พอ" in msg
    assert _gems() == fashion.GEMS_PER_EXCHANGE - 1, "แลกไม่สำเร็จแต่อัญมณีหาย"
    assert not fashion.owned(_p())


def test_you_cannot_buy_what_you_already_own(world):
    pm.update_player_fields(UID, {"fashion_gems": 99,
                                  "fashion_owned": json.dumps(["light_knight"])})
    ok, msg = fashion.exchange(UID, "light_knight")
    assert not ok and "อยู่แล้ว" in msg
    assert _gems() == 99


def test_gems_work_across_banners(world):
    """แลกของตู้เก่าที่พลาดไปได้ด้วย ไม่งั้นคนเข้าไม่ทันตู้เก่าไม่มีทางตามเก็บ"""
    feat = fashion.banner()
    other = next(k for k in fashion.CATALOG if k != feat)
    pm.update_player_field(UID, "fashion_gems", 99)
    assert fashion.exchange(UID, other)[0], "แลกได้แต่ของหน้าตู้รอบนี้"


def test_a_made_up_key_cannot_be_exchanged(world):
    pm.update_player_field(UID, "fashion_gems", 99)
    assert not fashion.exchange(UID, "ของปลอม")[0]
    assert _gems() == 99


# ── หน้าตู้ ──

def test_the_banner_rotates_and_covers_the_whole_catalog():
    """ของหน้าตู้ต้องเวียนครบทุกชิ้น ไม่งั้นบางชิ้นไม่มีวันขึ้นหน้าตู้"""
    d = datetime.date(2026, 1, 1)
    seen = {fashion.banner(d + datetime.timedelta(days=7 * w)) for w in range(len(fashion.CATALOG))}
    assert seen == set(fashion.CATALOG), f"ชิ้นที่ไม่มีวันขึ้นหน้าตู้: {sorted(set(fashion.CATALOG) - seen)}"


def test_the_banner_holds_still_for_a_whole_week():
    """ตู้เปลี่ยนวันจันทร์ ไม่ใช่เปลี่ยนกลางสัปดาห์ให้คนงง"""
    d = datetime.date(2026, 3, 2)             # วันจันทร์
    week = {fashion.banner(d + datetime.timedelta(days=i)) for i in range(7)}
    assert len(week) == 1, "ของหน้าตู้เปลี่ยนกลางสัปดาห์"


def test_the_expensive_button_is_actually_better(world):
    """1M กับ 10M ต้องต่างกันจริง ไม่งั้นปุ่มแพงไม่มีเหตุผลให้กด"""
    low = fashion._odds("low")
    high = fashion._odds("high")
    cheap = low["fashion"] + low["featured"]
    rich = high["fashion"] + high["featured"]
    ratio = rich / cheap
    per_gold_cheap = cheap / fashion.GACHA_TIERS["single"]["price"]
    per_gold_rich = rich / fashion.GACHA_TIERS["lucky"]["price"]
    assert ratio > 10, f"ปุ่ม 10M เรทดีกว่าแค่ {ratio:.1f} เท่า — แพงกว่า 10 เท่าแต่ไม่คุ้ม"
    assert per_gold_rich > per_gold_cheap, "จ่ายแพงกว่าแล้วได้แฟชั่นต่อทองน้อยลง"
    assert cheap > 0, "ปุ่มถูกไม่มีทางได้แฟชั่นเลย = ปุ่มหลอก"


def test_the_view_tells_the_player_the_real_odds(world):
    v = fashion.gacha_view(UID)
    assert v["featured"]["key"] == fashion.banner()
    assert {t["key"] for t in v["tiers"]} == set(fashion.GACHA_TIERS)
    for t in v["tiers"]:
        assert sum(t["odds"].values()) < 100, "เรทรวมเกิน 100% — ไม่เหลือช่องของธรรมดา"
        assert t["price"] > 0
    assert v["gems_per_exchange"] == fashion.GEMS_PER_EXCHANGE


def test_the_view_only_offers_what_you_do_not_own(world):
    pm.update_player_field(UID, "fashion_owned", json.dumps(["light_knight"]))
    keys = {i["key"] for i in fashion.gacha_view(UID)["exchangeable"]}
    assert "light_knight" not in keys and keys == set(fashion.CATALOG) - {"light_knight"}


# ── ราคาปรับได้จากคอนฟิก ──

def test_prices_and_odds_are_tunable(world, monkeypatch):
    from bot import config_loader

    def fake(key, default=None):
        return {"fashion.gacha.single": {"price": 42}}.get(key, default)

    monkeypatch.setattr(config_loader, "get_balance", fake)
    assert fashion._tier("single")["price"] == 42
    before = _cash()
    assert fashion.pull(UID, "single", random.Random(1))[0]
    assert _cash() <= before - 42, "ตั้งราคาใหม่แล้วยังหักราคาเดิม"


def test_the_web_route_is_wired(world):
    api = pathlib.Path("license_server/web_api.py").read_text(encoding="utf-8")
    assert '@router.post("/fashion/gacha")' in api, "ไม่มีปุ่มหมุนฝั่งเว็บ"
    route = api[api.index('@router.post("/fashion/gacha")'):]
    route = route[:route.index("\n\n\n")] if "\n\n\n" in route else route
    assert "_user_lock" in route, "หมุนกาชาไม่ได้ล็อกผู้เล่น — กดรัวสองจอได้ของฟรี"


# ── หน้าเว็บต้องต่อสายครบ ──

WEB = pathlib.Path("license_server/web_static")


def test_the_gacha_tile_is_no_longer_a_teaser():
    """ปุ่มกาชาแฟชั่นต้องกดได้จริงแล้ว ไม่ใช่ป้าย 'เร็ว ๆ นี้'"""
    html = (WEB / "play.html").read_text(encoding="utf-8")
    tile = html[html.index("กาชาแฟชั่น") - 400:html.index("กาชาแฟชั่น")]
    assert 'data-go="fgacha"' in tile, "ปุ่มกาชาแฟชั่นยังไม่พาไปไหน"
    assert "disabled" not in tile.rsplit("<button", 1)[-1], "ปุ่มกาชาแฟชั่นยังกดไม่ได้"
    assert '<div class="g-panelview" id="v-fgacha">' in html, "ไม่มีหน้าตู้กาชา"


def test_the_panel_loads_itself_when_opened():
    play = (WEB / "play.js").read_text(encoding="utf-8")
    assert "if (id === 'fgacha') fillGacha()" in play, "เปิดหน้าตู้แล้วไม่โหลดข้อมูล"
    for el in ("fgTiers", "fgResult", "fgExchange", "fgFeatName", "fgGems"):
        assert el in play and el in (WEB / "play.html").read_text(encoding="utf-8"), \
            f"อ้างถึง #{el} แต่ไม่มีในหน้าเว็บ (หรือกลับกัน)"


def test_the_browser_never_decides_what_you_won():
    """กติกาเหล็ก: เบราว์เซอร์ห้ามมีเรทหรือสุ่มเอง — ผลมาจากเซิร์ฟเวอร์อย่างเดียว"""
    play = (WEB / "play.js").read_text(encoding="utf-8")
    fn = play[play.index("async function fgPull("):]
    fn = fn[:fn.index("\n}\n")]
    assert "Math.random" not in fn, "เบราว์เซอร์สุ่มผลกาชาเอง"
    assert "/api/web/fashion/gacha" in fn, "ไม่ได้ถามเซิร์ฟเวอร์"


def test_every_result_kind_has_a_card_to_show():
    """ผลชนิดใหม่ที่ไม่มีป้าย = ผู้เล่นเห็นการ์ดเปล่า"""
    play = (WEB / "play.js").read_text(encoding="utf-8")
    block = play[play.index("const FG_KIND"):]
    block = block[:block.index("\n};")]
    shown = set(re.findall(r"^\s{2}(\w+):", block, re.M))
    assert {"featured", "fashion", "dup", "artifact", "junk", "sold", "bonus"} <= shown, \
        f"ผลที่ยังไม่มีการ์ด: {sorted({'featured','fashion','dup','artifact','junk','sold','bonus'} - shown)}"


def test_the_result_cards_have_styling():
    css = (WEB / "play.css").read_text(encoding="utf-8")
    for cls in (".fg-card", ".fg-card.feat", ".fg-banner", ".fg-gems"):
        assert cls in css, f"ไม่มีสไตล์ของ {cls}"


# ── ยิงผ่าน HTTP จริง ──

@pytest.fixture
def web(tmp_path, monkeypatch):
    import time

    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from license_server import web_api

    monkeypatch.setattr(pm, "DB_NAME", str(tmp_path / "w.db"))
    pm.init_db()
    pm.get_player(UID)
    pm.update_player_fields(UID, {"cash": RICH, "capacity": 99, "inventory": "[]"})
    monkeypatch.setattr(fashion, "_starter_sets_free", lambda: False)
    monkeypatch.setattr(web_api, "GAME_DB_PATH", tmp_path / "w.db")
    app = FastAPI()
    app.include_router(web_api.router)
    c = TestClient(app)
    c.cookies.set("web_session", web_api.sign({"uid": str(UID), "exp": time.time() + 3600}))
    return c


def test_the_whole_loop_works_over_http(web):
    """เปิดหน้าตู้ → หมุน → ทองลด → ของเข้าตู้ ครบวงในทางที่ผู้เล่นใช้จริง"""
    view = web.get("/api/web/fashion/gacha").json()
    assert view["featured"]["key"] in fashion.CATALOG
    assert view["cash"] == RICH

    r = web.post("/api/web/fashion/gacha", json={"action": "pull", "tier": "ten"})
    assert r.status_code == 200, r.text
    d = r.json()
    assert len([x for x in d["pulls"] if x["kind"] != "bonus"]) == 10
    assert d["cash"] == RICH - fashion.GACHA_TIERS["ten"]["price"] + \
        sum(x.get("gold", 0) for x in d["pulls"])
    assert d["money"]["cash"] == d["cash"], "ยอดทองบนแถบบนกับในผลไม่ตรงกัน"


def test_http_refuses_a_pull_you_cannot_afford(web):
    pm.update_player_field(UID, "cash", 100)
    r = web.post("/api/web/fashion/gacha", json={"action": "pull", "tier": "ten"})
    assert r.status_code == 400
    assert int(pm.get_player(UID)["cash"]) == 100, "หมุนไม่ผ่านแต่เงินหาย"


def test_http_exchange_needs_the_gems(web):
    r = web.post("/api/web/fashion/gacha", json={"action": "exchange", "key": "light_knight"})
    assert r.status_code == 400
    pm.update_player_field(UID, "fashion_gems", fashion.GEMS_PER_EXCHANGE)
    r = web.post("/api/web/fashion/gacha", json={"action": "exchange", "key": "light_knight"})
    assert r.status_code == 200, r.text
    assert r.json()["gems"] == 0
    assert "light_knight" in fashion.owned(pm.get_player(UID))


def test_a_stranger_cannot_pull(web):
    web.cookies.clear()
    assert web.post("/api/web/fashion/gacha",
                    json={"action": "pull", "tier": "ten"}).status_code in (401, 403)


def test_the_gacha_prize_can_actually_be_worn(web):
    """ได้ของจากกาชาแล้วต้องใส่ได้จริงทันที ไม่ใช่ขึ้นว่า 'ยังไม่มี'"""
    for _ in range(40):
        pm.update_player_field(UID, "cash", RICH)
        got = web.post("/api/web/fashion/gacha",
                       json={"action": "pull", "tier": "ten"}).json()["got_fashion"]
        if got:
            key = got[0]["key"]
            r = web.post("/api/web/me/fashion", json={"action": "wear", "key": key})
            assert r.status_code == 200, r.text
            assert r.json()["worn"][fashion.CATALOG[key]["slot"]] == key
            return
    pytest.fail("หมุน 400 ครั้งแล้วไม่ได้แฟชั่นสักชิ้น — เรทเพี้ยน")


def test_a_button_you_cannot_afford_still_says_why(web):
    """กดแล้วเงียบคือบั๊ก — ต้องกดได้และได้ข้อความบอกว่าทองไม่พอ"""
    play = (WEB / "play.js").read_text(encoding="utf-8")
    block = play[play.index("document.getElementById('fgTiers').innerHTML"):]
    block = block[:block.index("}).join('');")]
    assert "disabled" not in block, "ปุ่มหมุนถูกปิดตายเมื่อทองไม่พอ — กดแล้วไม่มีอะไรเกิดขึ้น"
    assert "ขาดอีก" in block, "ไม่ได้บอกว่าขาดอีกเท่าไหร่"

    pm.update_player_field(UID, "cash", 5)
    r = web.post("/api/web/fashion/gacha", json={"action": "pull", "tier": "single"})
    assert r.status_code == 400
    assert "ไม่พอ" in r.json()["detail"], f"ข้อความไม่ได้บอกว่าทองไม่พอ: {r.text}"
    assert "5" in r.json()["detail"], "ไม่ได้บอกว่าตอนนี้มีเท่าไหร่"


def test_the_exchange_button_also_speaks_up(web):
    play = (WEB / "play.js").read_text(encoding="utf-8")
    block = play[play.index("document.getElementById('fgExchange').innerHTML"):]
    block = block[:block.index("document.getElementById('fgExchange').querySelectorAll")]
    assert "disabled" not in block, "ปุ่มแลกถูกปิดตายเมื่ออัญมณีไม่พอ"

    r = web.post("/api/web/fashion/gacha", json={"action": "exchange", "key": "light_knight"})
    assert r.status_code == 400 and "ไม่พอ" in r.json()["detail"]
