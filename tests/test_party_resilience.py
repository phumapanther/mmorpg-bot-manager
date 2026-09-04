"""🎭 คนหลุด · บอทเล่นแทน · กลับเข้าห้อง · ชุบ (เฟส 6)

สเปกข้อ 4-5 (เจ้าของเกมเคาะ 2026-09-03):
  - คนหลุดกลางเกม → บอทเล่นแทน แล้วกลับเข้ามาคุมตัวเองต่อได้ จนกว่าปาร์ตี้จะยุบ
  - ตายแล้ว → นั่งดูเพื่อนเล่น จนกว่าจะโดนชุบด้วยสกิลหรือไอเทม

⚠️ ถ้าไม่มีตัวจับเวลา คน AFK คนเดียว **ค้างทั้งปาร์ตี้** — นี่คือเหตุผลของเฟสนี้
"""
import json
import pathlib
import random
import sqlite3
import time

import pytest

from bot import lobby
from bot.models import player_model
from bot.games.party import bot_ai, engine, room


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


def _battle(uids=(1, 2)):
    _, st = room.open_party(uids[0], "เอ")
    for u in uids[1:]:
        room.join_party(u, f"P{u}", st["room"])
    room.begin(uids[0])
    return room._room(uids[0])


def _unit(hp=100, hp_max=100, **kw):
    u = {"id": "p1", "uid": "1", "side": "party", "hp": hp, "hp_max": hp_max,
         "class_name": "Warrior", "alive": hp > 0}
    u.update(kw)
    return u


# ── บอทเลือกท่าเป็น ──

def test_บอทตีศัตรูที่ใกล้ตายก่อน():
    """เก็บให้ตายทีละตัวลดดาเมจที่ปาร์ตี้จะโดน — บอทโง่กว่านี้ไม่ได้"""
    foes = [_unit(hp=90, id="m1", side="monster"), _unit(hp=5, id="m2", side="monster")]
    act, tgt = bot_ai.choose(_unit(), [_unit()], foes, random.Random(1))
    assert (act, tgt) == ("attack", "m2")


def test_บอทฮีลเพื่อนที่เลือดวิกฤต():
    me = _unit(class_name="Cleric")
    hurt = _unit(hp=8, id="p2", uid="2")
    act, tgt = bot_ai.choose(me, [me, hurt], [_unit(id="m1", side="monster")],
                             random.Random(1))
    assert (act, tgt) == ("heal", "p2")


def test_บอทกวาดเมื่อศัตรูเยอะ():
    foes = [_unit(id=f"m{i}", side="monster") for i in range(1, 5)]
    act, _ = bot_ai.choose(_unit(), [_unit()], foes, random.Random(1))
    assert act == "aoe"


def test_บอทชุบเพื่อนที่ล้มก่อนอย่างอื่น():
    """คนตายนั่งดูอยู่ — ชุบสำคัญกว่าตี"""
    me = _unit(class_name="Cleric")
    dead = _unit(hp=0, id="p2", uid="2")
    act, tgt = bot_ai.choose(me, [me, dead], [_unit(id="m1", side="monster")],
                             random.Random(1))
    assert (act, tgt) == ("revive", "p2")


def test_บอทไม่สั่งท่าที่ตัวเองใช้ไม่ได้():
    """นักรบชุบไม่เป็น สั่งไปก็โดนเซิร์ฟปฏิเสธแล้วเกมค้าง"""
    me = _unit(class_name="Warrior")
    dead = _unit(hp=0, id="p2", uid="2")
    act, _ = bot_ai.choose(me, [me, dead], [_unit(id="m1", side="monster")],
                           random.Random(1))
    assert act != "revive"


def test_บอทสั่งท่าที่มีจริงเสมอ():
    """สั่งท่าแปลก = เกมค้างตลอดกาล ต้องกวาดหลายสถานการณ์"""
    rng = random.Random(3)
    for hp in (100, 40, 5):
        for n_foe in (1, 2, 4):
            for cls in ("Warrior", "Cleric", "Mage", None):
                me = _unit(hp=hp, class_name=cls)
                foes = [_unit(id=f"m{i}", side="monster") for i in range(1, n_foe + 1)]
                act, tgt = bot_ai.choose(me, [me], foes, rng)
                assert act in engine.ACTIONS, f"บอทสั่ง {act} ซึ่งไม่มีจริง"
                if engine.ACTIONS[act] not in ("self", "all", None):
                    assert tgt, f"ท่า {act} ต้องมีเป้า แต่บอทไม่เลือก"


def test_บอทไม่หนี():
    """หนีคือจบเกมให้ทั้งปาร์ตี้ — คนหลุดคนเดียวห้ามตัดสินใจแทนทุกคน

    ⚠️ ต้องกวาดทุกทางแยกจริง ๆ ฉบับแรกเทสแต่ตอนเลือดวิกฤต (hp=3)
       ซึ่งเข้าทางฮีลตลอด ไม่เคยไปถึงบรรทัดที่คืนท่าโจมตีเลย
       ย้อนเทสใส่ flee ตรงนั้นแล้วเทสยังเขียว (2026-09-04)
    """
    rng = random.Random(5)
    seen = set()
    for hp in (100, 80, 40, 20, 3):
        for n_foe in (1, 2, 3, 5):
            for n_dead in (0, 1):
                for cls in ("Warrior", "Cleric"):
                    me = _unit(hp=hp, class_name=cls)
                    allies = [me] + [_unit(hp=0, id="p2", uid="2")] * n_dead
                    foes = [_unit(id=f"m{i}", side="monster")
                            for i in range(1, n_foe + 1)]
                    act, _ = bot_ai.choose(me, allies, foes, rng)
                    assert act != "flee", f"บอทกดหนีตอน hp={hp} ศัตรู={n_foe}"
                    seen.add(act)
    assert {"attack", "heal", "aoe"} <= seen,         f"เทสไม่ได้แตะทุกทางแยก แตะแค่ {seen}"


def test_ในโค้ดบอทไม่มีคำว่า_flee_เลย():
    """กันไว้อีกชั้น — เผลอเพิ่มทางแยกใหม่ที่คืน flee เทสข้างบนอาจไม่ครอบคลุม"""
    src = pathlib.Path("bot/games/party/bot_ai.py").read_text(encoding="utf-8")
    code = chr(10).join(ln.split("#")[0] for ln in src.splitlines())
    assert '"flee"' not in code and "'flee'" not in code


# ── หมดเวลาแล้วบอทเล่นแทน ──

def test_ยังไม่หมดเวลาบอทไม่แย่งเล่น():
    st = _battle()
    b = st["extra"]["battle"]
    who = engine.current_actor(st)
    assert engine.timeout_act(st, random.Random(1), now=b["turn_at"] + 5) == []
    assert engine.current_actor(st) == who, "ยังไม่ถึงเวลา ห้ามเล่นแทน"


def test_หมดเวลาแล้วบอทเล่นแทนไม่ค้าง():
    """⭐ เหตุผลทั้งหมดของเฟสนี้ — คน AFK คนเดียวห้ามค้างทั้งปาร์ตี้"""
    st = _battle()
    b = st["extra"]["battle"]
    who = engine.current_actor(st)
    evs = engine.timeout_act(st, random.Random(1), now=b["turn_at"] + engine.TURN_SECONDS + 1)
    assert evs, "หมดเวลาแล้วแต่ไม่มีอะไรเกิดขึ้น"
    assert b["over"] or engine.current_actor(st) != who, "เล่นแทนแล้วแต่ตาไม่เดิน"


def test_บอทเล่นแทนไม่ได้ถ้าเป็นตาของมอน():
    st = _battle()
    b = st["extra"]["battle"]
    mon = [u for u in b["units"].values() if u["side"] == "monster"][0]
    b["turn"] = b["order"].index(mon["id"])
    assert engine.timeout_act(st, random.Random(1), now=b["turn_at"] + 9999) == []


def test_ทั้งปาร์ตี้_afk_เกมยังเดินจนจบ():
    """ทุกคนหลุดหมด บอทต้องเล่นจนจบ ไม่ใช่วนไม่รู้จบ"""
    st = _battle()
    rng = random.Random(2)
    for _ in range(400):
        b = st["extra"]["battle"]
        if b["over"]:
            break
        engine.timeout_act(st, rng, now=b["turn_at"] + engine.TURN_SECONDS + 1)
        room._run_monsters(st, rng)
    assert st["extra"]["battle"]["over"], "บอทเล่นแทนแล้วเกมยังไม่จบ = ค้าง"


def test_นาฬิกาเริ่มใหม่ทุกตา():
    """ไม่รีเซ็ต = คนถัดไปโดนบอทแย่งเล่นทันทีทั้งที่เพิ่งถึงตา"""
    st = _battle()
    b = st["extra"]["battle"]
    t0 = b["turn_at"]
    who = engine.current_actor(st)
    foes = [u["id"] for u in b["units"].values() if u["side"] == "monster"]
    engine.act(st, int(who[1:]), "attack", foes[0], random.Random(1))
    assert b["turn_at"] > t0, "เดินตาแล้วนาฬิกาไม่เริ่มใหม่"


# ── ชุบ ──

def _give(uid, item_id):
    p = player_model.get_player(uid) or {}
    inv = player_model.load_inventory(p.get("inventory", ""))
    inv.append(str(item_id))
    player_model.update_player_field(uid, "inventory", json.dumps(inv))


def _revive_item_id():
    from bot import config_loader
    for i, d in config_loader.get_all_items().items():
        if str(d.get("effect", "")) == "revive":
            return str(i)
    pytest.skip("เกมนี้ไม่มีไอเทมชุบชีวิต")


def test_นักบวชชุบเพื่อนได้():
    st = _battle()
    b = st["extra"]["battle"]
    b["units"]["p1"]["class_name"] = "Cleric"
    b["units"]["p2"]["hp"] = 0
    b["turn"] = b["order"].index("p1")
    ok, r = engine.act(st, 1, "revive", "p2", random.Random(1))
    assert ok, r
    assert b["units"]["p2"]["hp"] > 0, "ชุบแล้วยังไม่ฟื้น"


def test_ชุบแล้วเล่นต่อได้จริง():
    """ฟื้นแล้วแต่สั่งอะไรไม่ได้ = ชุบไปก็เท่านั้น"""
    st = _battle()
    b = st["extra"]["battle"]
    b["units"]["p1"]["class_name"] = "Cleric"
    b["units"]["p2"]["hp"] = 0
    b["turn"] = b["order"].index("p1")
    engine.act(st, 1, "revive", "p2", random.Random(1))
    b["turn"] = b["order"].index("p2")
    foes = [u["id"] for u in b["units"].values()
            if u["side"] == "monster" and u["hp"] > 0]
    ok, r = engine.act(st, 2, "attack", foes[0], random.Random(1))
    assert ok, r


def test_นักรบชุบไม่ได้ถ้าไม่มีไอเทม():
    st = _battle()
    b = st["extra"]["battle"]
    b["units"]["p1"]["class_name"] = "Warrior"
    b["units"]["p2"]["hp"] = 0
    b["turn"] = b["order"].index("p1")
    ok, r = engine.act(st, 1, "revive", "p2", random.Random(1))
    assert not ok and "ชุบ" in r["error"]


def test_มีใบชุบชีวิตก็ชุบได้แม้ไม่ใช่นักบวช():
    item = _revive_item_id()
    _give(1, item)
    st = _battle()
    b = st["extra"]["battle"]
    b["units"]["p1"]["class_name"] = "Warrior"
    b["units"]["p2"]["hp"] = 0
    b["turn"] = b["order"].index("p1")
    ok, r = engine.act(st, 1, "revive", "p2", random.Random(1))
    assert ok, r


def test_ใบชุบชีวิตหายไปจากกระเป๋าหลังใช้():
    """ไม่หัก = ใบเดียวชุบได้ไม่จำกัด"""
    item = _revive_item_id()
    _give(1, item)
    st = _battle()
    b = st["extra"]["battle"]
    b["units"]["p1"]["class_name"] = "Warrior"
    b["units"]["p2"]["hp"] = 0
    b["turn"] = b["order"].index("p1")
    engine.act(st, 1, "revive", "p2", random.Random(1))
    inv = player_model.load_inventory(
        (player_model.get_player(1) or {}).get("inventory", ""))
    assert item not in inv, "ใช้ใบชุบชีวิตแล้วแต่ยังอยู่ในกระเป๋า"


def test_ชุบคนที่ยังไม่ตายไม่ได้():
    st = _battle()
    b = st["extra"]["battle"]
    b["units"]["p1"]["class_name"] = "Cleric"
    b["turn"] = b["order"].index("p1")
    ok, _ = engine.act(st, 1, "revive", "p2", random.Random(1))
    assert not ok


def test_ชุบมอนไม่ได้():
    st = _battle()
    b = st["extra"]["battle"]
    b["units"]["p1"]["class_name"] = "Cleric"
    mon = [u for u in b["units"].values() if u["side"] == "monster"][0]
    mon["hp"] = 0
    b["turn"] = b["order"].index("p1")
    ok, _ = engine.act(st, 1, "revive", mon["id"], random.Random(1))
    assert not ok


# ── คนตายนั่งดู ──

def test_คนล้มสั่งอะไรไม่ได้แต่ยังเห็นสนาม():
    st = _battle()
    b = st["extra"]["battle"]
    b["units"]["p2"]["hp"] = 0
    b["turn"] = b["order"].index("p2")
    ok, r = engine.act(st, 2, "attack", "m1", random.Random(1))
    assert not ok and "ชุบ" in r["error"]
    assert engine.view(st, 2)["in_battle"], "ล้มแล้วต้องยังดูเพื่อนเล่นได้"


def test_คนล้มไม่ได้เทิร์นแต่ไม่ถูกลบออกจากสนาม():
    st = _battle()
    b = st["extra"]["battle"]
    b["units"]["p2"]["hp"] = 0
    assert engine.current_actor(st) != "p2"
    assert any(u["id"] == "p2" for u in engine.view(st, 1)["units"])


# ── หลุดแล้วกลับเข้ามา ──

def test_หลุดแล้วกลับเข้ามาคุมตัวเองต่อได้():
    """หลุด = เลิก poll เฉย ๆ ที่นั่งยังอยู่ กลับมาต้องสั่งได้เหมือนเดิม"""
    st = _battle()
    b = st["extra"]["battle"]
    lobby.save(st["room"], st)
    got = room.view(2)
    assert got["in_room"] and got["battle"]["in_battle"]

    b["turn"] = b["order"].index("p2")
    lobby.save(st["room"], st)
    foes = [u["id"] for u in b["units"].values()
            if u["side"] == "monster" and u["hp"] > 0]
    ok, _ = room.act(2, "attack", foes[0])
    assert ok, "กลับเข้ามาแล้วสั่งไม่ได้"


def test_ปาร์ตี้ยุบแล้วกลับเข้าไม่ได้():
    _, st0 = room.open_party(1, "เอ")
    code = st0["room"]
    room.join_party(2, "บี", code)
    room.begin(1)
    room.leave_party(1)
    room.leave_party(2)                 # คนสุดท้ายออก = ห้องหาย
    ok, r = room.join_party(2, "บี", code)
    assert not ok and "error" in r


def test_บอทเล่นแทนแล้วคนกลับมาไม่โดนแย่งอีก():
    """กลับมาแล้วยังโดนบอทเล่นแทนทันที = เล่นไม่ได้เลย"""
    st = _battle()
    b = st["extra"]["battle"]
    engine.timeout_act(st, random.Random(1), now=b["turn_at"] + engine.TURN_SECONDS + 1)
    b["turn"] = b["order"].index("p2")          # บังคับให้เป็นตาผู้เล่น ไม่ต้องพึ่งดวง
    b["turn_at"] = time.time()
    assert engine.timeout_act(st, random.Random(1), now=b["turn_at"] + 1) == [],         "เพิ่งกลับมาก็โดนบอทแย่งเล่นอีก = เล่นไม่ได้เลย"


# ── หน้าเว็บ ──

def test_view_บอกเวลาที่เหลือให้หน้าเว็บนับถอยหลัง():
    st = _battle()
    got = engine.view(st, 1)
    assert "turn_left" in got, "หน้าเว็บไม่รู้ว่าเหลือเวลาเท่าไหร่"
    assert 0 <= got["turn_left"] <= engine.TURN_SECONDS


def test_view_บอกว่าเราชุบได้ไหม():
    """ปุ่มชุบต้องเทาไว้ถ้าใช้ไม่ได้ ไม่ใช่ให้กดแล้วค่อยด่า"""
    st = _battle()
    st["extra"]["battle"]["units"]["p1"]["class_name"] = "Cleric"
    me = [u for u in engine.view(st, 1)["units"] if u.get("you")][0]
    assert me.get("can_revive") is True
    st["extra"]["battle"]["units"]["p1"]["class_name"] = "Warrior"
    me = [u for u in engine.view(st, 1)["units"] if u.get("you")][0]
    assert me.get("can_revive") is False


# ── ท่าที่ไม่ต้องเล็ง ──

def test_กวาดได้โดยไม่ต้องเล็งเป้า():
    """🐛 บั๊กจริงจากเฟส 3: เบราว์เซอร์ส่ง aoe มาแบบไม่มีเป้า แต่ _check บังคับ
       ให้มีเป้า ปุ่ม 💥 จึงตอบ "ไม่มีเป้าหมายนี้ในสมรภูมิ" มาตลอด
       (เจอตอนเขียนบอทเฟส 6 — เทสอ่าน JS จับไม่ได้ ต้องยิงเข้าเซิร์ฟจริง)
    """
    st = _battle()
    b = st["extra"]["battle"]
    who = engine.current_actor(st)
    if b["units"][who]["side"] != "party":
        b["turn"] = b["order"].index("p1")
        who = "p1"
    ok, r = engine.act(st, int(who[1:]), "aoe", None, random.Random(1))
    assert ok, f"กวาดโดยไม่เล็งไม่ได้: {r}"
    assert any(e["t"] == "aoe" for e in r["events"])


def test_ป้องกันกับหนีก็ไม่ต้องเล็ง():
    st = _battle()
    b = st["extra"]["battle"]
    b["turn"] = b["order"].index("p1")
    ok, r = engine.act(st, 1, "defend", None, random.Random(1))
    assert ok, r
