"""🎲 สุ่มเหตุการณ์ · หมู่บ้าน · หีบสมบัติ (เฟส 10b ขั้น 1-3)

เจ้าของเกมเคาะ 2026-09-05:
  - เหตุการณ์ที่ยังไม่ทำ **ตกเป็นเจอมอน** ไปก่อน
  - หมู่บ้าน **คิดค่านอนพักตามเกมหลัก** (2,000 ทอง ตั้งได้ที่ Panel)
  - หีบติดกับดัก **ทุกคนทอยเองสลับเทิร์น**
  - โหวตเสมอ = ข้าม
"""
import random
import sqlite3

import pytest

from bot import adventure_core
from bot.models import player_model
from bot.games.party import encounter, room, treasure, village


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


def _members(n=2, hp=50, hp_max=100):
    return [{"id": f"p{i}", "uid": str(i), "name": f"P{i}",
             "hp": hp, "hp_max": hp_max} for i in range(1, n + 1)]


# ── ตัวสุ่มเหตุการณ์ ──

def test_สุ่มได้เฉพาะชนิดที่ทำเสร็จแล้ว():
    """⭐ ยังไม่ได้ทำแล้วสุ่มออกมา = ผู้เล่นค้างอยู่กับจอว่าง"""
    for seed in range(60):
        got = encounter.roll_kind(1, random.Random(seed))
        assert got in encounter.READY, f"สุ่มได้ {got} ซึ่งยังไม่ได้ทำ"


def test_ชนิดที่ยังไม่ทำตกเป็นมอน():
    """dungeon/npc/trap ยังไม่ทำ — ต้องกลายเป็นมอน ไม่ใช่พัง"""
    assert "dungeon" not in encounter.READY
    assert "npc" not in encounter.READY
    assert encounter.FALLBACK == "monster"


def test_น้ำหนักมาจากเกมหลักไม่ใช่ตั้งใหม่():
    """เดินคนเดียวกับเดินเป็นปาร์ตี้ต้องเจอของแบบเดียวกัน"""
    import pathlib
    src = pathlib.Path("bot/games/party/encounter.py").read_text(encoding="utf-8")
    assert "adventure_core.event_weights" in src
    code = "\n".join(ln.split("#")[0] for ln in src.splitlines())
    assert "25" not in code and "[25," not in code, "ตั้งน้ำหนักเองในโค้ด"


def test_เจอครบทุกชนิดที่ทำแล้วถ้าสุ่มพอ():
    """ตกเป็นมอนหมดก็เท่ากับยังไม่มีเหตุการณ์อะไรเลย"""
    got = {encounter.roll_kind(1, random.Random(s)) for s in range(200)}
    assert {"monster", "village", "treasure"} <= got, f"เจอแค่ {got}"


def test_อ่านน้ำหนักไม่ได้ก็ไม่พัง(monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("คอนฟิกพัง")
    monkeypatch.setattr(adventure_core, "event_weights", boom)
    assert encounter.roll_kind(1, random.Random(1)) == "monster"


# ── โครงสถานะกลาง ──

def test_โครงสถานะมีครบทุกช่องที่หน้าเว็บต้องใช้():
    ev = encounter.new_state("village", _members())
    for key in ("kind", "order", "turn", "members", "log", "over", "art"):
        assert key in ev, f"ขาดช่อง {key}"
    assert [m["id"] for m in ev["members"]] == ["p1", "p2"]


def test_ข้ามคนที่เลือกไปแล้ว():
    ev = encounter.new_state("village", _members(3))
    encounter.member(ev, "p1")["done"] = True
    assert encounter.current(ev) == "p2"


def test_ทุกคนเลือกครบแล้วไม่มีใครถึงตา():
    ev = encounter.new_state("village", _members(2))
    for m in ev["members"]:
        m["done"] = True
    assert encounter.current(ev) is None
    assert encounter.all_done(ev)


def test_ข้อความเล่าเรื่องไม่บวมไม่จำกัด():
    """สถานะถูกเซฟลง DB ทุกครั้ง ปล่อยให้โตเรื่อย ๆ ไม่ได้"""
    ev = encounter.new_state("village", _members())
    for i in range(50):
        encounter.say(ev, f"บรรทัด {i}")
    assert len(ev["log"]) <= 12


# ── 🏡 หมู่บ้าน ──

def test_พักแล้วฟื้นเต็มและเสียเงิน():
    player_model.update_player_fields(1, {"cash": 999999, "hp": 10, "max_hp": 100})
    ev = village.start(_members(1, hp=10))
    before = int(player_model.get_player(1)["cash"])
    ok, err = village.act(ev, "p1", "rest")
    assert ok, err
    p = player_model.get_player(1)
    assert int(p["hp"]) == 100, "พักแล้วเลือดไม่เต็ม"
    assert int(p["cash"]) < before, "พักแล้วไม่เสียเงิน"


def test_ค่าพักใช้สูตรเกมหลัก():
    p = player_model.get_player(1)
    assert village.cost_for(1) == int(adventure_core.rest_cost(p))


def test_เงินไม่พอพักไม่ได้():
    """เงินไม่พอแล้วยังฟื้นได้ = ค่าพักไม่มีความหมาย"""
    player_model.update_player_fields(1, {"cash": 0, "hp": 10, "max_hp": 100})
    ev = village.start(_members(1, hp=10))
    ok, _ = village.act(ev, "p1", "rest")
    assert ok, "ต้องผ่านแต่ไม่ได้ฟื้น ไม่ใช่กดไม่ได้เลย"
    assert int(player_model.get_player(1)["hp"]) == 10, "เงินไม่พอแต่ยังฟื้น"
    assert any("เงินไม่พอ" in t for t in ev["log"])


def test_พักแล้วเม็ดคริสตัลเต็มด้วย():
    from bot import mana
    player_model.update_player_fields(1, {"cash": 999999, "hp": 10})
    mana.spend(1, 99)
    ev = village.start(_members(1, hp=10))
    village.act(ev, "p1", "rest")
    assert mana.get(1) > 0


def test_เดินต่อไม่เสียเงินไม่ฟื้น():
    player_model.update_player_fields(1, {"cash": 999999, "hp": 10, "max_hp": 100})
    ev = village.start(_members(1, hp=10))
    before = int(player_model.get_player(1)["cash"])
    village.act(ev, "p1", "walk")
    p = player_model.get_player(1)
    assert int(p["cash"]) == before and int(p["hp"]) == 10


def test_สลับเทิร์นทีละคน():
    """สเปกข้อ 3.2 — ไม่ใช่กดพร้อมกันรวดเดียว"""
    for uid in (1, 2):
        player_model.update_player_fields(uid, {"cash": 999999, "hp": 10})
    ev = village.start(_members(2, hp=10))
    assert encounter.current(ev) == "p1"
    ok, _ = village.act(ev, "p2", "rest")
    assert not ok, "คนที่ยังไม่ถึงตากดได้"
    village.act(ev, "p1", "rest")
    assert encounter.current(ev) == "p2"


def test_ปุ่มบอกราคาไปด้วย():
    """กดแล้วค่อยรู้ว่าเสียเท่าไหร่คือ UX แย่"""
    ev = village.start(_members(1))
    names = " ".join(o["name"] for o in village.options(ev, "p1"))
    assert "ทอง" in names


def test_บอทพักให้เมื่อเลือดไม่เต็มและเงินพอ():
    player_model.update_player_fields(1, {"cash": 999999, "hp": 10, "max_hp": 100})
    ev = village.start(_members(1, hp=10))
    assert village.bot_pick(ev, "p1") == "rest"


def test_บอทไม่พักเมื่อเลือดเต็ม():
    player_model.update_player_fields(1, {"cash": 999999, "hp": 100, "max_hp": 100})
    ev = village.start(_members(1, hp=100, hp_max=100))
    assert village.bot_pick(ev, "p1") == "walk"


def test_บอทไม่พักเมื่อเงินไม่พอ():
    player_model.update_player_fields(1, {"cash": 0, "hp": 10, "max_hp": 100})
    ev = village.start(_members(1, hp=10))
    assert village.bot_pick(ev, "p1") == "walk"


# ── 📦 หีบสมบัติ ──

class Dice:
    def __init__(self, *vals):
        self.vals = list(vals)

    def randint(self, a, b):
        return self.vals.pop(0) if self.vals else a

    def choice(self, seq):
        return list(seq)[0]

    def random(self):
        return 0.5


def test_เฉพาะหัวห้องเลือกวิธีได้():
    """⭐ กันคนยิง API ตรง ๆ เปิดหีบแทนหัวห้อง"""
    ev = treasure.start(_members(2))
    ok, err = treasure.act(ev, "p2", "open", Dice(99), is_host=False)
    assert not ok and "หัวห้อง" in err


def test_ลูกทีมไม่มีปุ่มตอนรอหัวห้อง():
    ev = treasure.start(_members(2))
    assert treasure.options(ev, "p2", is_host=False) == []
    assert treasure.options(ev, "p1", is_host=True)


def test_หัวห้องข้ามได้เลย():
    ev = treasure.start(_members(2))
    ok, _ = treasure.act(ev, "p1", "skip", Dice(), is_host=True)
    assert ok and ev["over"]


def test_เปิดเลยแล้วไม่ติดกับดักได้รางวัล():
    ev = treasure.start(_members(2))
    treasure.act(ev, "p1", "open", Dice(99), is_host=True)   # 99 > 50 = ไม่ติดกับดัก
    assert ev["over"] and ev.get("prize") is True


def test_เปิดเลยแล้วติดกับดักต้องทอยหลบ():
    ev = treasure.start(_members(2))
    treasure.act(ev, "p1", "open", Dice(1), is_host=True)    # 1 <= 50 = ติดกับดัก
    assert not ev["over"]
    assert ev["stage"] == treasure.PHASE_SAVE
    assert encounter.current(ev) == "p1", "ต้องเริ่มทอยจากคนแรก"


def test_ทุกคนทอยหลบเองสลับเทิร์น():
    """สเปกข้อ 3.3 — ไม่ใช่ทอยรวดเดียวทั้งทีม"""
    ev = treasure.start(_members(3))
    treasure.act(ev, "p1", "open", Dice(1), is_host=True)
    ok, _ = treasure.act(ev, "p2", "save", Dice(15))
    assert not ok, "คนที่ยังไม่ถึงตาทอยได้"
    treasure.act(ev, "p1", "save", Dice(15))
    assert encounter.current(ev) == "p2"


def test_ทอยถึงเกณฑ์หลบพ้น():
    ev = treasure.start(_members(1))
    treasure.act(ev, "p1", "open", Dice(1), is_host=True)
    treasure.act(ev, "p1", "save", Dice(20))
    m = encounter.member(ev, "p1")
    assert m["choice"] == "dodged" and not m.get("dmg")


def test_ทอยไม่ถึงเสีย_20_เปอร์เซ็นต์():
    ev = treasure.start(_members(1, hp=100, hp_max=100))
    treasure.act(ev, "p1", "open", Dice(1), is_host=True)
    treasure.act(ev, "p1", "save", Dice(1))
    m = encounter.member(ev, "p1")
    assert m["choice"] == "hit" and m["dmg"] == 20, f"ควรเสีย 20 ได้ {m.get('dmg')}"


def test_ทอยครบทุกคนแล้วจบเหตุการณ์():
    ev = treasure.start(_members(2))
    treasure.act(ev, "p1", "open", Dice(1), is_host=True)
    treasure.act(ev, "p1", "save", Dice(20))
    assert not ev["over"]
    treasure.act(ev, "p2", "save", Dice(20))
    assert ev["over"]


def test_โหวตเปิดชนะแล้วเปิดหีบ():
    ev = treasure.start(_members(2))
    treasure.act(ev, "p1", "vote", Dice(), is_host=True)
    treasure.act(ev, "p1", "yes", Dice())
    treasure.act(ev, "p2", "yes", Dice(99))
    assert ev.get("prize") is True


def test_โหวตเสมอถือว่าข้าม():
    """⭐ เจ้าของเกมเคาะข้อ 12 — ปลอดภัยไว้ก่อน"""
    ev = treasure.start(_members(2))
    treasure.act(ev, "p1", "vote", Dice(), is_host=True)
    treasure.act(ev, "p1", "yes", Dice())
    treasure.act(ev, "p2", "no", Dice())
    assert ev["over"] and not ev.get("prize")
    assert any("เสมอ" in t for t in ev["log"])


def test_โหวตข้ามชนะก็ข้าม():
    ev = treasure.start(_members(3))
    treasure.act(ev, "p1", "vote", Dice(), is_host=True)
    for who in ("p1", "p2", "p3"):
        treasure.act(ev, who, "no", Dice())
    assert ev["over"] and not ev.get("prize")


def test_เลือดน้อยทอยหลบเสียเปรียบ():
    """ใช้เต๋าตัวเดียวกับการต่อสู้ — คนที่ฟื้นมา 1% จึงเสี่ยงกว่า (เคาะข้อ 10)"""
    from bot.games.party import contest
    weak = {"side": "party", "hp": 5, "hp_max": 100, "level": 1, "fx": {}}
    assert contest.frail_penalty(weak) < 0


def test_บอทโหวตข้ามและทอยให้():
    ev = treasure.start(_members(2))
    treasure.act(ev, "p1", "vote", Dice(), is_host=True)
    assert treasure.bot_pick(ev, "p1") == "no"
    ev["stage"] = treasure.PHASE_SAVE
    assert treasure.bot_pick(ev, "p1") == "save"


def test_ตัวเลขหีบตรงกับสเปก():
    """⭐ ตรึงเลขดิบ — 50% กับดัก · ทอย 10 ขึ้นไปรอด · เสีย 20%"""
    assert treasure.DEFAULTS["trap_chance"] == 50
    assert treasure.DEFAULTS["save_need"] == 10
    assert treasure.DEFAULTS["trap_dmg_pct"] == 0.20


# ── ต่อเข้าห้องจริงแล้วหรือยัง ──

def _party(uids=(1, 2)):
    _, st = room.open_party(uids[0], "เอ")
    for u in uids[1:]:
        room.join_party(u, f"P{u}", st["room"])
    return st["room"]


def _force(monkeypatch, kind):
    monkeypatch.setattr(encounter, "roll_kind", lambda *a, **k: kind)


def test_สุ่มได้หมู่บ้านแล้วห้องเปิดฉากหมู่บ้านจริง(monkeypatch):
    """⭐ เขียนโมดูลไว้แต่ไม่มีใครเรียก = ผู้เล่นยังเจอมอนอย่างเดียวเหมือนเดิม"""
    _force(monkeypatch, "village")
    _party()
    room.begin(1)
    got = room.view(1)
    assert got.get("event"), "ไม่ได้เปิดฉากเหตุการณ์เลย"
    assert got["event"]["kind"] == "village"
    assert not got.get("battle"), "ยังเปิดสมรภูมิซ้อนอยู่"


def test_สุ่มได้หีบแล้วห้องเปิดฉากหีบจริง(monkeypatch):
    _force(monkeypatch, "treasure")
    _party()
    room.begin(1)
    got = room.view(1)
    assert got["event"]["kind"] == "treasure"


def test_สุ่มได้มอนก็ยังเป็นสมรภูมิเหมือนเดิม(monkeypatch):
    _force(monkeypatch, "monster")
    _party()
    room.begin(1)
    got = room.view(1)
    assert got.get("battle") and not got.get("event")


def test_view_ส่งข้อมูลครบให้หน้าเว็บวาด(monkeypatch):
    _force(monkeypatch, "village")
    _party()
    room.begin(1)
    ev = room.view(1)["event"]
    for key in ("kind", "art", "turn_of", "turn_left", "members",
                "log", "over", "actions", "round"):
        assert key in ev, f"ขาดช่อง {key}"
    me = [m for m in ev["members"] if m.get("you")]
    assert len(me) == 1, "ไม่บอกว่าคนไหนคือเรา"


def test_สั่งเหตุการณ์ผ่าน_room_act_ได้(monkeypatch):
    _force(monkeypatch, "village")
    player_model.update_player_fields(1, {"cash": 999999, "hp": 10})
    _party()
    room.begin(1)
    ok, r = room.act(1, "walk")
    assert ok, r
    assert room.view(1)["event"]["members"][0]["done"] is True


def test_สั่งท่าต่อสู้ตอนอยู่ในเหตุการณ์ไม่ได้(monkeypatch):
    """🔒 กันคนยิง API ตรง ๆ ใช้คำสั่งผิดฉาก"""
    _force(monkeypatch, "village")
    _party()
    room.begin(1)
    ok, r = room.act(1, "attack", "m1")
    assert not ok


def test_เหตุการณ์จบแล้วไปต่อได้(monkeypatch):
    """1 เหตุการณ์ = 1 รอบ — หมู่บ้านก็ต้องนับรอบ"""
    _force(monkeypatch, "village")
    _party()
    room.begin(1)
    room.act(1, "walk")
    room.act(2, "walk")
    assert room.view(1)["event"]["over"] is True

    ok, _ = room.again(1)
    assert ok, "เหตุการณ์จบแล้วแต่ไปต่อไม่ได้"
    assert room.view(1)["round"] == 2


def test_เหตุการณ์ยังไม่จบไปต่อไม่ได้(monkeypatch):
    _force(monkeypatch, "village")
    _party()
    room.begin(1)
    ok, r = room.again(1)
    assert not ok and "ยังไม่จบ" in r["error"]


def test_หัวห้องเท่านั้นที่เห็นปุ่มเลือกวิธีเปิดหีบ(monkeypatch):
    _force(monkeypatch, "treasure")
    _party()
    room.begin(1)
    assert room.view(1)["event"]["actions"], "หัวห้องไม่มีปุ่ม"
    assert room.view(2)["event"]["actions"] == [], "ลูกทีมมีปุ่มทั้งที่ยังไม่ถึงตา"


def test_กับดักหักเลือดในฐานข้อมูลจริง(monkeypatch):
    """เสียเลือดแค่ในหน้าจอแต่ตัวละครจริงไม่โดน = กับดักไม่มีความหมาย"""
    _force(monkeypatch, "treasure")
    player_model.update_player_fields(1, {"hp": 100, "max_hp": 100})
    player_model.update_player_fields(2, {"hp": 100, "max_hp": 100})
    _party()
    room.begin(1)
    st = room._room(1)
    ev = st["extra"]["event"]
    treasure.act(ev, "p1", "open", Dice(1), is_host=True)      # ติดกับดัก
    for who in ("p1", "p2"):
        treasure.act(ev, who, "save", Dice(1))                 # ทอยไม่ผ่านทั้งคู่
    room._ev_finish(st, ev)
    assert int(player_model.get_player(1)["hp"]) < 100, "กับดักไม่หักเลือดจริง"


def test_เปิดหีบได้รางวัลแล้วได้ทองจริง(monkeypatch):
    _force(monkeypatch, "treasure")
    _party()
    room.begin(1)
    st = room._room(1)
    ev = st["extra"]["event"]
    before = int(player_model.get_player(1)["cash"])
    treasure.act(ev, "p1", "open", Dice(99), is_host=True)     # ไม่ติดกับดัก
    room._ev_finish(st, ev)
    assert int(player_model.get_player(1)["cash"]) > before, "ได้รางวัลแต่ไม่ได้ทอง"


def test_จ่ายรางวัลหีบครั้งเดียว(monkeypatch):
    """⭐ บั๊กตระกูลเดียวกับจ่ายรางวัลซ้ำตอนสู้"""
    _force(monkeypatch, "treasure")
    _party()
    room.begin(1)
    st = room._room(1)
    ev = st["extra"]["event"]
    treasure.act(ev, "p1", "open", Dice(99), is_host=True)
    room._ev_finish(st, ev)
    got = int(player_model.get_player(1)["cash"])
    for _ in range(5):
        room._ev_finish(st, ev)
        room.view(1)
    assert int(player_model.get_player(1)["cash"]) == got, "จ่ายรางวัลหีบซ้ำ"
