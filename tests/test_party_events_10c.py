"""⚡ ภัยพิบัติ · 🚪 ดันเจี้ยน · 🧓 NPC (เฟส 10c)

เจ้าของเกมเคาะ 2026-09-05:
  - สถานะจากภัยพิบัติ **ติดเฉพาะการเดินทางนี้** ไม่ตามไปโหมดเดี่ยว
  - ดันเจี้ยน **นับเวฟละรอบ** (เข้าตอนรอบ 5 → เวฟ 10 คือรอบ 14)
  - **หนีกลางดันเจี้ยนได้ จบดันเจี้ยนเลย** ของที่ได้มาแล้วไม่ถูกริบ
"""
import random
import sqlite3

import pytest

from bot import game_modifiers, lobby
from bot.games.party import (disaster, dungeon, encounter, npc, room)
from bot.models import player_model


@pytest.fixture(autouse=True)
def db(tmp_path, monkeypatch):
    from license_server import web_db
    path = tmp_path / "web.db"

    def _connect():
        conn = sqlite3.connect(str(path), timeout=5)
        conn.row_factory = sqlite3.Row
        conn.executescript(web_db._SCHEMA)
        return conn

    monkeypatch.setattr(web_db, "connect", _connect)
    monkeypatch.setattr(player_model, "DB_NAME", str(tmp_path / "game.db"))
    player_model.init_db()
    for uid in range(1, 7):
        player_model.get_player(uid)
    yield


class Dice:
    """เต๋าปลอม — ทอยครั้งแรกได้ตามสั่ง หมดแล้วคืนค่าน้อยสุดเสมอ

    (คืนค่ามากสุดตอนหมดจะทำให้เทสผ่านเพราะโชคช่วย ไม่ใช่เพราะโค้ดถูก)
    """

    def __init__(self, *vals):
        self.vals = list(vals)

    def randint(self, lo, hi):
        return max(lo, min(hi, self.vals.pop(0))) if self.vals else lo

    def choice(self, seq):
        return seq[0]

    def random(self):
        return 0.0

    def choices(self, seq, weights=None, k=1):
        return [seq[0]] * k

    def sample(self, seq, k):
        return list(seq)[:k]


def _members(n=2, hp=100, hp_max=100):
    return [{"id": f"p{i}", "uid": str(i), "name": f"P{i}",
             "hp": hp, "hp_max": hp_max} for i in range(1, n + 1)]


def _party(uids=(1, 2)):
    _, st = room.open_party(uids[0], "เอ")
    for u in uids[1:]:
        room.join_party(u, f"P{u}", st["room"])
    return st["room"]


def _force(monkeypatch, kind):
    monkeypatch.setattr(encounter, "roll_kind", lambda *a, **k: kind)


# ═══════════════════════ ⚡ ภัยพิบัติ ═══════════════════════

def test_ทุกภัยติดสถานะที่มีดาเมจต่อรอบจริง():
    """⭐ ติดสถานะที่โหมดนี้ไม่มี hook รองรับ = ป้ายโชว์เฉย ๆ ไม่เจ็บสักนิด"""
    for k in disaster.KINDS:
        cfg = game_modifiers.STATUS_EFFECTS[k["status"]]
        assert cfg.get("step_damage"), f"{k['status']} ไม่มี step_damage"


def test_ทอยถึงเกณฑ์แล้วหลบพ้น():
    ev = disaster.start(_members(), Dice())
    ok, err = disaster.act(ev, "p1", "dodge", Dice(20))
    assert ok, err
    m = encounter.member(ev, "p1")
    assert m["choice"] == "dodged" and not m.get("dmg") and not m.get("status")


def test_ทอยไม่ถึงเกณฑ์เจ็บและติดสถานะ():
    ev = disaster.start(_members(), Dice())
    disaster.act(ev, "p1", "dodge", Dice(1))
    m = encounter.member(ev, "p1")
    assert m["choice"] == "hit"
    assert m["dmg"] > 0 and m["status"] == ev["status"]


def test_ทอยได้พอดีเกณฑ์ถือว่ารอด():
    """⭐ ตรึงขอบ — >= ไม่ใช่ > (พลาดตรงนี้คือเสียเลือดฟรีทั้งเกม)"""
    ev = disaster.start(_members(), Dice())
    disaster.act(ev, "p1", "dodge", Dice(int(disaster.DEFAULTS["save_need"])))
    assert encounter.member(ev, "p1")["choice"] == "dodged"


def test_ทอยแทนคนอื่นไม่ได้():
    ev = disaster.start(_members(), Dice())
    ok, err = disaster.act(ev, "p2", "dodge", Dice(20))
    assert not ok and "ยังไม่ถึงตา" in err


def test_ทอยซ้ำไม่ได้():
    ev = disaster.start(_members(1), Dice())
    disaster.act(ev, "p1", "dodge", Dice(20))
    ok, _ = disaster.act(ev, "p1", "dodge", Dice(1))
    assert not ok


def test_ทุกคนทอยครบแล้วเหตุการณ์จบ():
    ev = disaster.start(_members(2), Dice())
    disaster.act(ev, "p1", "dodge", Dice(20))
    assert not ev["over"], "คนเดียวทอยเสร็จก็จบแล้ว"
    disaster.act(ev, "p2", "dodge", Dice(20))
    assert ev["over"]


def test_ใช้ชื่อเหตุการณ์ของเกมหลัก():
    """⭐ ตั้งชื่อใหม่ = ตารางน้ำหนักที่ Panel ไม่ตรงกับที่ปาร์ตี้ใช้"""
    assert disaster.KIND == "trap"
    assert disaster.start(_members(), Dice())["kind"] == "trap"


# ── สถานะ: ติดเฉพาะการเดินทางนี้ ──

def test_สถานะไม่เขียนลงตัวละคร():
    """⭐ เจ้าของเกมเคาะ — ติดในปาร์ตี้แล้วต้องไม่ตามไปโหมดเดี่ยว"""
    st = {"extra": {}}
    disaster.afflict(st, "1", "poison")
    assert disaster.of(st, "1").get("poison")
    assert not game_modifiers.parse_statuses(player_model.get_player(1)), \
        "เขียนสถานะลงตัวละครจริง"


def test_ติดซ้ำเอาอันที่นานกว่า():
    st = {"extra": {}}
    disaster.afflict(st, "1", "poison", 3)
    disaster.afflict(st, "1", "poison", 9)
    assert disaster.of(st, "1")["poison"] == 9
    disaster.afflict(st, "1", "poison", 2)
    assert disaster.of(st, "1")["poison"] == 9, "ติดซ้ำแล้วเทิร์นหด"


def test_สถานะกัดกินแล้วนับถอยหลังจนหมด():
    st = {"extra": {}}
    disaster.afflict(st, "1", "poison", 2)
    assert disaster.tick_round(st, random.Random(1)), "ไม่กัดกินเลย"
    assert disaster.of(st, "1")["poison"] == 1
    disaster.tick_round(st, random.Random(1))
    assert not disaster.of(st, "1"), "หมดเทิร์นแล้วยังติดอยู่"


def test_หมู่บ้านกับ_npc_ล้างพิษได้ตามเกมหลัก():
    for where in ("village", "npc"):
        st = {"extra": {}}
        disaster.afflict(st, "1", "poison")
        assert disaster.cleanse(st, where), f"{where} ล้างไม่ได้"
        assert not disaster.of(st, "1")


def test_ล้างเฉพาะที่เกมหลักอนุญาต():
    """⭐ bleed ไม่มี cleanse_on — ล้างที่หมู่บ้านไม่ได้"""
    assert "cleanse_on" not in game_modifiers.STATUS_EFFECTS["bleed"]
    st = {"extra": {}}
    disaster.afflict(st, "1", "bleed")
    assert disaster.cleanse(st, "village") == []
    assert disaster.of(st, "1").get("bleed")


def test_ดันเจี้ยนล้างหนาวได้แต่ล้างพิษไม่ได้():
    st = {"extra": {}}
    disaster.afflict(st, "1", "frostbite")
    disaster.afflict(st, "1", "poison")
    disaster.cleanse(st, "dungeon")
    left = disaster.of(st, "1")
    assert "frostbite" not in left and "poison" in left


# ── ต่อเข้าห้องจริง ──

def test_ห้องเปิดฉากภัยพิบัติจริง(monkeypatch):
    """⭐ เขียนโมดูลไว้แต่ไม่มีใครเรียก = ผู้เล่นไม่มีวันเจอ"""
    _force(monkeypatch, "trap")
    _party()
    room.begin(1)
    got = room.view(1)
    assert got["event"]["kind"] == "trap"
    assert got["event"]["actions"], "ถึงตาแล้วแต่ไม่มีปุ่มให้กด"


def test_ภัยพิบัติหักเลือดในฐานข้อมูลจริง(monkeypatch):
    _force(monkeypatch, "trap")
    for u in (1, 2):
        player_model.update_player_fields(u, {"hp": 100, "max_hp": 100})
    _party()
    room.begin(1)
    st = room._room(1)
    ev = st["extra"]["event"]
    for who in ("p1", "p2"):
        disaster.act(ev, who, "dodge", Dice(1))
    room._ev_finish(st, ev)
    assert int(player_model.get_player(1)["hp"]) < 100, "ไม่หักเลือดจริง"
    assert disaster.of(st, "1"), "ไม่ติดสถานะ"


def test_ภัยพิบัติหักเลือดครั้งเดียว(monkeypatch):
    """⭐ บั๊กตระกูลเดียวกับจ่ายรางวัลซ้ำ — poll ทุก 2 วิ"""
    _force(monkeypatch, "trap")
    _party()
    room.begin(1)
    st = room._room(1)
    ev = st["extra"]["event"]
    for who in ("p1", "p2"):
        disaster.act(ev, who, "dodge", Dice(1))
    room._ev_finish(st, ev)
    hp = int(player_model.get_player(1)["hp"])
    for _ in range(5):
        room._ev_finish(st, ev)
        room.view(1)
    assert int(player_model.get_player(1)["hp"]) == hp, "หักเลือดซ้ำ"


def test_หลบพ้นแล้วไม่โดนอะไรเลย(monkeypatch):
    _force(monkeypatch, "trap")
    player_model.update_player_fields(1, {"hp": 100, "max_hp": 100})
    _party()
    room.begin(1)
    st = room._room(1)
    ev = st["extra"]["event"]
    for who in ("p1", "p2"):
        disaster.act(ev, who, "dodge", Dice(20))
    room._ev_finish(st, ev)
    assert int(player_model.get_player(1)["hp"]) == 100
    assert not disaster.of(st, "1")


def test_สถานะกัดกินตอนขึ้นรอบใหม่(monkeypatch):
    """⭐ ต้องเดินทางต่อจริง — เรียก _fx_tick ตรง ๆ จะไม่จับกรณี "เขียนไว้แต่ไม่มีใครเรียก" """
    _force(monkeypatch, "trap")
    _party()
    room.begin(1)
    st = room._room(1)
    disaster.afflict(st, "1", "poison", 5)
    ev = st["extra"]["event"]
    for who in ("p1", "p2"):
        disaster.act(ev, who, "dodge", Dice(20))       # หลบพ้นทั้งคู่ ไม่มีดาเมจอื่นมาปน
    room._ev_finish(st, ev)
    lobby.save(st["room"], st)
    player_model.update_player_fields(1, {"hp": 100, "max_hp": 100})

    assert room.again(1)[0], "เหตุการณ์จบแล้วไปต่อไม่ได้"
    assert int(player_model.get_player(1)["hp"]) < 100, "ขึ้นรอบใหม่แล้วสถานะไม่กัด"
    assert room._room(1)["extra"].get("fx_log"), "ไม่บอกผู้เล่นว่าเสียเลือดเพราะอะไร"


def test_สถานะกัดไม่ถึงตาย(monkeypatch):
    _force(monkeypatch, "trap")
    _party()
    room.begin(1)
    st = room._room(1)
    disaster.afflict(st, "1", "poison", 99)
    player_model.update_player_fields(1, {"hp": 1, "max_hp": 100})
    for _ in range(10):
        room._fx_tick(st, random.Random(1))
    assert int(player_model.get_player(1)["hp"]) >= 1, "สถานะฆ่าคนได้ระหว่างเดิน"


def test_ออกเดินทางใหม่ล้างสถานะ(monkeypatch):
    _force(monkeypatch, "trap")
    _party()
    room.begin(1)
    st = room._room(1)
    disaster.afflict(st, "1", "poison", 9)
    lobby.save(st["room"], st)
    room.begin(1)
    assert not disaster.of(room._room(1), "1"), "สถานะข้ามการเดินทาง"


def test_view_ส่งสถานะของคนนั้นไปให้หน้าเว็บ(monkeypatch):
    _force(monkeypatch, "trap")
    _party()
    room.begin(1)
    st = room._room(1)
    disaster.afflict(st, "1", "poison", 9)
    lobby.save(st["room"], st)
    assert room.view(1)["fx"], "ไม่ส่งสถานะไปให้หน้าเว็บ"
    assert not room.view(2)["fx"], "ส่งสถานะของคนอื่นไปด้วย"


# ═══════════════════════ 🚪 ดันเจี้ยน ═══════════════════════

def test_เวฟท้ายเจอบอสแน่นอน():
    """⭐ ตรึงเลขดิบ — 10 เวฟ · เวฟ 8 เป็นต้นไปเป็นบอส"""
    assert dungeon.WAVES == 10 and dungeon.BOSS_FROM == 8
    assert not dungeon.is_boss(7)
    assert dungeon.is_boss(8) and dungeon.is_boss(10)


def test_เดินครบสิบเวฟแล้วออกเอง():
    st = {"extra": {}}
    dungeon.start(st)
    got = [dungeon.advance(st) for _ in range(dungeon.WAVES)]
    assert got == list(range(1, dungeon.WAVES + 1))
    assert dungeon.advance(st) is None, "เวฟ 11"
    assert not dungeon.active(st), "ครบแล้วยังไม่ออก"


def test_นับเวฟละรอบ(monkeypatch):
    """⭐ เจ้าของเกมเคาะ — ทั้งดันเจี้ยนนับรอบเดียว = ที่ฟาร์มราคาถูก"""
    _force(monkeypatch, "dungeon")
    _party()
    room.begin(1)
    st = room._room(1)
    assert dungeon.wave(st) == 1 and st["extra"]["round"] == 1

    for expect in (2, 3):
        b = st["extra"]["battle"]
        b["over"], b["winner"] = True, "party"
        lobby.save(st["room"], st)
        assert room.again(1)[0]
        st = room._room(1)
        assert dungeon.wave(st) == expect, "เวฟไม่เดิน"
        assert st["extra"]["round"] == expect, "รอบไม่เดินตามเวฟ"


def test_อยู่ในดันเจี้ยนไม่สุ่มเหตุการณ์อื่น(monkeypatch):
    """⭐ มุดอยู่ครึ่งทางแล้วโผล่ไปหมู่บ้าน = ดันเจี้ยนไม่มีความหมาย"""
    _party()
    room.begin(1)
    st = room._room(1)
    dungeon.start(st)
    monkeypatch.setattr(encounter, "roll_kind",
                        lambda *a, **k: pytest.fail("ยังสุ่มทั้งที่อยู่ในดันเจี้ยน"))
    assert room._next_encounter(st) == "dungeon"
    assert st["extra"].get("battle") and not st["extra"].get("event")


def test_หนีกลางดันเจี้ยนแล้วจบดันเจี้ยน(monkeypatch):
    """⭐ เจ้าของเกมเคาะ — หนีได้ จบเลย ของที่ได้มาแล้วไม่ริบ"""
    _force(monkeypatch, "dungeon")
    _party()
    room.begin(1)
    st = room._room(1)
    assert dungeon.active(st)
    st["extra"]["battle"]["over"] = True
    st["extra"]["battle"]["winner"] = "flee"
    room.settle(st)
    assert not dungeon.active(st), "หนีแล้วยังอยู่ในดันเจี้ยน"


def test_ล้มยกทีมกลางดันเจี้ยนก็จบดันเจี้ยน(monkeypatch):
    _force(monkeypatch, "dungeon")
    _party()
    room.begin(1)
    st = room._room(1)
    b = st["extra"]["battle"]
    b["over"], b["winner"] = True, "monster"
    for u in b["units"].values():
        if u["side"] == "party":
            u["hp"] = 0
    room.settle(st)
    assert not dungeon.active(st)


def test_ชนะเวฟแล้วยังอยู่ในดันเจี้ยน(monkeypatch):
    """⭐ ชนะแล้วหลุดออกมาเอง = ไม่มีวันได้เจอบอสเวฟ 8"""
    _force(monkeypatch, "dungeon")
    _party()
    room.begin(1)
    st = room._room(1)
    b = st["extra"]["battle"]
    b["over"], b["winner"] = True, "party"
    room.settle(st)
    assert dungeon.active(st), "ชนะเวฟเดียวแล้วดันเจี้ยนจบ"


def test_เริ่มเดินทางใหม่ไม่ค้างอยู่ในดันเจี้ยน(monkeypatch):
    _force(monkeypatch, "dungeon")
    _party()
    room.begin(1)
    st = room._room(1)
    assert dungeon.active(st)
    _force(monkeypatch, "monster")      # การเดินทางใหม่สุ่มไม่ได้ดันเจี้ยน
    room.begin(1)
    assert not dungeon.active(room._room(1)), "ดันเจี้ยนค้างข้ามการเดินทาง"


def test_เข้าดันเจี้ยนแล้วหายหนาว(monkeypatch):
    _force(monkeypatch, "monster")      # ต้องเริ่มจาก "ยังไม่อยู่ในดันเจี้ยน"
    _party()
    room.begin(1)
    st = room._room(1)
    disaster.afflict(st, "1", "frostbite", 99)
    _force(monkeypatch, "dungeon")
    room._next_encounter(st)
    assert "frostbite" not in disaster.of(st, "1")


def test_view_บอกเวฟให้หน้าเว็บวาด(monkeypatch):
    _force(monkeypatch, "dungeon")
    _party()
    room.begin(1)
    got = room.view(1)
    assert got["dungeon"]["wave"] == 1 and got["dungeon"]["waves"] == 10
    assert "เวฟ 1/10" in got["battle"]["wave"]


def test_ไม่ได้อยู่ในดันเจี้ยนก็ไม่มีป้ายเวฟ(monkeypatch):
    _force(monkeypatch, "monster")
    _party()
    room.begin(1)
    got = room.view(1)
    assert got["dungeon"] is None and got["battle"]["wave"] is None


# ═══════════════════════ 🧓 NPC ═══════════════════════

def test_คุยแล้วผลมาจากเกมหลัก(monkeypatch):
    """⭐ สุ่มผลเอง = ปรับที่ Panel แล้วสองโหมดไม่ตรงกัน"""
    called = {}

    def fake(uid, rng=None):
        called["uid"] = uid
        return {"text": "ทักทาย"}

    monkeypatch.setattr("bot.adventure_core.npc_talk", fake)
    ev = npc.start(_members(), Dice())
    ok, err = npc.act(ev, "p1", "talk", Dice())
    assert ok, err
    assert called["uid"] == 1
    assert any("ทักทาย" in t for t in ev["log"])


def test_ซื้อของผ่านตัวกลางเดียวกับร้านค้า(monkeypatch):
    got = {}

    def fake(uid, item_id, count=1):
        got["args"] = (uid, item_id, count)
        return True, "ซื้อแล้ว"

    monkeypatch.setattr("core.services.items.buy_item_for", fake)
    ev = npc.start(_members(), Dice())
    if not ev["stock"]:
        pytest.skip("คอนฟิกไม่มีของขาย")
    key = ev["stock"][0]["id"]
    ok, err = npc.act(ev, "p1", f"buy:{key}", Dice())
    assert ok, err
    assert got["args"] == (1, key, 1)


def test_ซื้อของที่ไม่ได้อยู่ในเป้ไม่ได้(monkeypatch):
    """🔒 กันคนยิง API ตรง ๆ ซื้อของนอกร้าน"""
    monkeypatch.setattr("core.services.items.buy_item_for",
                        lambda *a, **k: pytest.fail("ปล่อยให้ซื้อของนอกเป้"))
    ev = npc.start(_members(), Dice())
    ok, _ = npc.act(ev, "p1", "buy:ของที่ไม่มีจริง", Dice())
    assert ok, "ควรบอกว่าไม่มีของแล้วให้เลือกใหม่"
    assert not encounter.member(ev, "p1")["done"], "ซื้อพลาดแล้วปิดตาเลย"


def test_ซื้อไม่สำเร็จยังเลือกใหม่ได้(monkeypatch):
    monkeypatch.setattr("core.services.items.buy_item_for",
                        lambda *a, **k: (False, "เงินไม่พอ"))
    ev = npc.start(_members(), Dice())
    if not ev["stock"]:
        pytest.skip("คอนฟิกไม่มีของขาย")
    npc.act(ev, "p1", f"buy:{ev['stock'][0]['id']}", Dice())
    assert not encounter.member(ev, "p1")["done"]
    assert npc.act(ev, "p1", "bye", Dice())[0]


def test_ลาไปแล้วจบตาของคนนั้น():
    ev = npc.start(_members(), Dice())
    npc.act(ev, "p1", "bye", Dice())
    assert encounter.member(ev, "p1")["done"]
    assert encounter.current(ev) == "p2"


def test_บอทคุยเฉยไม่ใช้เงินคนอื่น():
    """⭐ บอทกดซื้อแทน = คน AFK กลับมาเงินหาย"""
    ev = npc.start(_members(), Dice())
    assert npc.bot_pick(ev, "p1") == "talk"


def test_ห้องเปิดฉาก_npc_จริง(monkeypatch):
    _force(monkeypatch, "npc")
    _party()
    room.begin(1)
    got = room.view(1)
    assert got["event"]["kind"] == "npc"
    assert got["event"]["actions"], "ถึงตาแล้วแต่ไม่มีปุ่ม"


def test_npc_ล้างสถานะให้ตอนจบเหตุการณ์(monkeypatch):
    monkeypatch.setattr("bot.adventure_core.npc_talk",
                        lambda uid, rng=None: {"text": "ทักทาย"})
    _force(monkeypatch, "npc")
    _party()
    room.begin(1)
    st = room._room(1)
    disaster.afflict(st, "1", "poison", 9)
    ev = st["extra"]["event"]
    for who in ("p1", "p2"):
        npc.act(ev, who, "talk", Dice())
    room._ev_finish(st, ev)
    assert ev["over"], "ทุกคนเลือกครบแล้วยังไม่จบ"
    assert not disaster.of(st, "1"), "NPC ไม่ล้างสถานะให้"


def test_npc_จบแล้วออกเดินทางต่อได้(monkeypatch):
    monkeypatch.setattr("bot.adventure_core.npc_talk",
                        lambda uid, rng=None: {"text": "ทักทาย"})
    _force(monkeypatch, "npc")
    _party()
    room.begin(1)
    room.act(1, "talk")
    room.act(2, "talk")
    ok, _ = room.again(1)
    assert ok
    assert room.view(1)["round"] == 2


# ═══════════════ ต่อสายครบทุกเหตุการณ์แล้วหรือยัง ═══════════════

def test_ทุกชนิดที่สุ่มได้มีคนรับ():
    """⭐ สุ่มออกมาแล้วไม่มีโมดูลรับ = KeyError กลางการเดินทาง"""
    handled = set(room.EVENT_MODS) | {"monster", "dungeon"}
    assert set(encounter.READY) <= handled, \
        f"ไม่มีคนรับ: {set(encounter.READY) - handled}"


def test_ทุกโมดูลเหตุการณ์หน้าตาเหมือนกัน():
    """⭐ room เรียกแบบเดียวกันหมด — โมดูลไหนเซ็นต่างก็ระเบิดตอนสุ่มเจอ"""
    import inspect
    for kind, mod in room.EVENT_MODS.items():
        for fn, need in (("start", ("members", "rng")),
                         ("options", ("ev", "unit_id", "is_host")),
                         ("act", ("ev", "unit_id", "action", "rng", "is_host")),
                         ("bot_pick", ("ev", "unit_id"))):
            args = list(inspect.signature(getattr(mod, fn)).parameters)
            assert args == list(need), f"{kind}.{fn} รับ {args}"


# ═══════════ ทางเข้าฝั่งเว็บ: กดปุ่มในเหตุการณ์แล้วถึงเซิร์ฟเวอร์จริงไหม ═══════════
#
# ⭐ 10b เขียนหมู่บ้าน/หีบเสร็จ แต่ API รับแค่ `engine.ACTIONS` — ปุ่ม "พักผ่อน"
#    บนเว็บจึงตอบ 400 มาตลอด เทสชั้น room.act จับไม่ได้เพราะข้ามชั้น API ไปเลย
#    (เจอตอนต่อสาย 10c) เทสข้างล่างยิงผ่าน HTTP จริงเพื่อกันซ้ำ

def _client(monkeypatch, uid=1):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from license_server import web_api
    from license_server.api_web.games import party as web_party
    # ต้อง patch ที่ party.py ตรง ๆ — มันทำ from ... import require_player ตอน import
    monkeypatch.setattr(web_party, "require_player", lambda r: {"uid": uid})
    monkeypatch.setattr(web_party, "player_model_get",
                        lambda u: player_model.get_player(int(u)) or {})
    app = FastAPI()
    app.include_router(web_api.router)
    return TestClient(app)


def _post(client, **body):
    return client.post("/api/web/party/room", json=body)


def test_ปุ่มในเหตุการณ์ยิงผ่าน_api_ได้(monkeypatch):
    """⭐ ปุ่มโผล่บนจอแต่กดแล้ว 400 = เหตุการณ์เล่นไม่ได้เลยทั้งชุด"""
    _force(monkeypatch, "trap")
    _party()
    room.begin(1)
    r = _post(_client(monkeypatch), action="dodge")
    assert r.status_code == 200, r.text
    assert r.json()["room"]["event"]["members"][0]["done"] is True


def test_ปุ่มหมู่บ้านยิงผ่าน_api_ได้(monkeypatch):
    _force(monkeypatch, "village")
    _party()
    room.begin(1)
    r = _post(_client(monkeypatch), action="walk")
    assert r.status_code == 200, r.text


def test_ปุ่มซื้อของ_npc_ยิงผ่าน_api_ได้(monkeypatch):
    """⭐ คำสั่งแบบ buy:<id> สร้างตอนรัน — ลิสต์คำสั่งตายตัวจะพลาดข้อนี้"""
    monkeypatch.setattr("core.services.items.buy_item_for",
                        lambda *a, **k: (True, "ซื้อแล้ว"))
    _force(monkeypatch, "npc")
    _party()
    room.begin(1)
    st = room._room(1)
    if not st["extra"]["event"]["stock"]:
        pytest.skip("คอนฟิกไม่มีของขาย")
    key = st["extra"]["event"]["stock"][0]["id"]
    r = _post(_client(monkeypatch), action=f"buy:{key}")
    assert r.status_code == 200, r.text


def test_ปุ่มลา_npc_ไม่ทำให้หลุดออกจากปาร์ตี้(monkeypatch):
    """⭐ ถ้า NPC ใช้คีย์ "leave" จะชนกับคำสั่งออกจากปาร์ตี้ของ API"""
    _force(monkeypatch, "npc")
    _party()
    room.begin(1)
    acts = [a["key"] for a in room.view(1)["event"]["actions"]]
    assert "leave" not in acts, "ชื่อคำสั่งชนกับ \"ออกจากปาร์ตี้\""
    r = _post(_client(monkeypatch), action="bye")
    assert r.status_code == 200, r.text
    assert r.json()["room"]["in_room"], "กดลา NPC แล้วหลุดออกจากปาร์ตี้"


def test_ออกจากปาร์ตี้กลางเหตุการณ์ยังได้(monkeypatch):
    """⭐ เหตุการณ์กินคำสั่งไปหมดก็ออกจากห้องไม่ได้ ติดอยู่ในเกมถาวร"""
    _force(monkeypatch, "village")
    _party()
    room.begin(1)
    r = _post(_client(monkeypatch), action="leave")
    assert r.status_code == 200, r.text
    assert not r.json()["room"]["in_room"], "ออกจากปาร์ตี้ไม่ได้"


def test_คำสั่งต่อสู้ตอนอยู่ในเหตุการณ์ยังถูกปฏิเสธ(monkeypatch):
    """🔒 ส่งต่อให้ room.act ไม่ได้แปลว่าปล่อยผ่านทุกอย่าง"""
    _force(monkeypatch, "trap")
    _party()
    room.begin(1)
    assert _post(_client(monkeypatch), action="attack").status_code == 400


def test_คำสั่งต่อสู้ยังยิงผ่าน_api_พร้อมเป้าหมายได้(monkeypatch):
    """⭐ ทางแยก in_event ต้องไม่กินคำสั่งของสมรภูมิ — ไม่งั้นเล็งเป้าไม่ได้ทั้งเกม"""
    _force(monkeypatch, "monster")
    _party()
    room.begin(1)
    st = room._room(1)
    b = st["extra"]["battle"]
    me = next(u for u in b["units"].values()
              if u["side"] == "party" and u.get("uid") == "1")
    b["turn"] = b["order"].index(me["id"])
    foe = next(u["id"] for u in b["units"].values() if u["side"] == "monster")
    lobby.save(st["room"], st)

    r = _post(_client(monkeypatch), action="attack", target=foe)
    assert r.status_code == 200, r.text
    assert r.json()["events"], "ตีแล้วไม่มีเหตุการณ์อะไรกลับมาเลย"


def test_ติ๊กล่าบอสแล้วมุดดันเจี้ยนก็ยังเจอบอส(monkeypatch):
    """⭐ เวฟ 1-7 เขียนทับด้วย boss=False = โหมดล่าบอสหายไปกลางดันเจี้ยน"""
    seen = []
    from bot.games.party import monsters
    real = monsters.spawn_group
    monkeypatch.setattr(monsters, "spawn_group",
                        lambda *a, **k: (seen.append(k.get("boss")), real(*a, **k))[1])
    _force(monkeypatch, "dungeon")
    _party()
    room.begin(1, boss_raid=True)
    st = room._room(1)
    assert dungeon.wave(st) == 1, "ไม่ได้อยู่เวฟ 1"
    assert seen and seen[-1] is True, f"เวฟ 1 ของปาร์ตี้ล่าบอสได้ boss={seen}"

    # เวฟถัดไปเดินผ่านอีกทางเข้าหนึ่ง (dungeon.active) — ต้องคง boss ไว้เหมือนกัน
    b = st["extra"]["battle"]
    b["over"], b["winner"] = True, "party"
    lobby.save(st["room"], st)
    assert room.again(1)[0]
    assert dungeon.wave(room._room(1)) == 2, "เวฟไม่เดิน"
    assert seen[-1] is True, f"เวฟ 2 ของปาร์ตี้ล่าบอสได้ boss={seen}"


# ═══════════ 🖼️ พื้นหลังเหตุการณ์ต้องมีจริง ═══════════
#
# ⭐ 10b ต่อ URL เป็น `/assets/events/<kind>.png` แต่ในโฟลเดอร์มีแต่
#    `main_village.png` / `frozen_village.png` ราย "ทวีป" — ได้ 404 เงียบทุกครั้ง

def test_ทุกเหตุการณ์มีภาพพื้นหลังจริง():
    from bot import event_images
    for kind in encounter.READY:
        url = event_images.web_url(kind)
        assert url, f"ไม่มีภาพของ {kind}"
        stem = url.rsplit("/", 1)[-1]
        assert (event_images.ASSETS_DIR / stem).is_file(), f"{url} ไม่มีไฟล์จริง"


def test_ภาพประจำทวีปมาก่อนภาพกลาง():
    from bot import event_images
    assert event_images.web_url("village", "frozen").endswith("frozen_village.png")
    assert event_images.web_url("village", "ทวีปที่ไม่มีภาพ").endswith("main_village.png")


def test_ไม่มีภาพก็ไม่พัง():
    from bot import event_images
    assert event_images.web_url("เหตุการณ์ที่ไม่มีจริง") is None


def test_view_ส่ง_url_ภาพที่มีไฟล์จริง(monkeypatch):
    """⭐ ส่งชื่อ kind เปล่า ๆ ไปให้หน้าเว็บต่อ URL เอง = พื้นหลังหายทั้งหมด"""
    from bot import event_images
    _force(monkeypatch, "village")
    _party()
    room.begin(1)
    url = room.view(1)["event"]["art_url"]
    assert url, "ไม่ส่ง url ภาพไปให้หน้าเว็บ"
    assert (event_images.ASSETS_DIR / url.rsplit("/", 1)[-1]).is_file(), \
        f"ส่ง {url} ที่ไม่มีไฟล์จริง"


def test_หน้าเว็บไม่ต่อ_url_ภาพเอง():
    import pathlib
    js = pathlib.Path("license_server/web_static/games/party/lobby.js").read_text(
        encoding="utf-8")
    assert "/assets/events/${" not in js, "หน้าเว็บยังต่อ URL ภาพเอง"
    assert "ev.art_url" in js, "ไม่ได้ใช้ url ที่เซิร์ฟเวอร์ส่งมา"


def test_ภัยพิบัติกำหนดอายุสถานะเอง(monkeypatch):
    """⭐ frostbite ของเกมหลักตั้งไว้ 999 รอบ — เอามาใช้ตรง ๆ คือเลือดไหลตลอดการเดินทาง

    ธีมนั้นเสกใส่ซ้ำทุกก้าวอยู่แล้ว ความหนาวเป็นสภาพแวดล้อม ไม่ใช่บาดแผลจากภัยหนเดียว
    """
    assert game_modifiers.STATUS_EFFECTS["frostbite"]["default_turns"] > 100
    assert disaster.DEFAULTS["status_turns"] == 5

    _force(monkeypatch, "trap")
    _party()
    room.begin(1)
    st = room._room(1)
    ev = st["extra"]["event"]
    ev["status"] = "frostbite"          # บังคับให้เจอพายุหิมะ
    for who in ("p1", "p2"):
        disaster.act(ev, who, "dodge", Dice(1))
    room._ev_finish(st, ev)
    assert disaster.of(st, "1")["frostbite"] == 5, \
        f"ติดหนาว {disaster.of(st, '1')} รอบ"


def test_คอนฟิกไอเทมพังก็ยังคุยกับ_npc_ได้(monkeypatch):
    """⭐ ราคาพิมพ์เป็นตัวหนังสือที่ Panel แล้วปาร์ตี้ค้างทั้งห้อง = ไม่คุ้มกัน"""
    monkeypatch.setattr("bot.config_loader.get_all_items",
                        lambda: {"x": {"name": "ของ", "buy": "แพงมาก"}})
    ev = npc.start(_members(), Dice())
    assert ev["stock"] == [], "คอนฟิกพังแต่ยังยัดของเข้าเป้"
    assert [a["key"] for a in npc.options(ev, "p1")] == ["talk", "bye"]


def test_หา_url_ภาพได้โดยไม่มี_discord():
    """⭐ แกนปาร์ตี้ต้องรันบนโฮสต์เว็บที่ไม่ได้ติดตั้ง discord (กฎเดียวกับ test_party_layering)

    `room._art_url` เรียก `event_images` ซึ่งเคย `import discord` ตรง ๆ ที่หัวไฟล์
    → เทสชั้น layering จับไม่ได้เพราะมัน import แบบ lazy ในฟังก์ชัน แต่ของจริงพังตอนรัน
    """
    import subprocess
    import sys
    code = (
        "import sys\n"
        "class Block:\n"
        "    def find_module(self, name, path=None):\n"
        "        if name == 'discord' or name.startswith('discord.'): return self\n"
        "    def load_module(self, name): raise ImportError('discord ถูกบล็อก')\n"
        "sys.meta_path.insert(0, Block())\n"
        "from bot import event_images\n"
        "assert event_images.web_url('village'), 'หาภาพไม่เจอ'\n"
        "print('OK')\n"
    )
    r = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True)
    assert "OK" in r.stdout, f"ไม่มี discord แล้วหา url ภาพไม่ได้:\n{r.stderr[-400:]}"


def test_แถบเลือดบนจอลดตามภัยพิบัติ(monkeypatch):
    """⭐ หักแต่ในฐานข้อมูล แถบเลือดบนจอไม่ขยับ = ผู้เล่นไม่รู้ว่าเจ็บ"""
    _force(monkeypatch, "trap")
    for u in (1, 2):
        player_model.update_player_fields(u, {"hp": 100, "max_hp": 100})
    _party()
    room.begin(1)
    st = room._room(1)
    ev = st["extra"]["event"]
    before = encounter.member(ev, "p1")["hp"]
    for who in ("p1", "p2"):
        disaster.act(ev, who, "dodge", Dice(1))
    room._ev_finish(st, ev)
    assert encounter.member(ev, "p1")["hp"] < before, "แถบเลือดบนจอไม่ลด"
    assert encounter.member(ev, "p1")["hp"] == int(player_model.get_player(1)["hp"]), \
        "เลือดบนจอไม่ตรงกับตัวละครจริง"
