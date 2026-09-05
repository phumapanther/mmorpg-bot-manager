"""⚔️ สกิลตามคลาส (เฟส 9)

เจ้าของเกมสั่ง 2026-09-04: ทุกคนมีปุ่มเหมือนกันหมดทั้งที่คลาสต่างกัน — ต้องแยก
ปุ่มที่ควรมี: **⚔️ โจมตี + 2 สกิลของคลาส + 🏃 หนี**
(ฮีลกับป้องกันไม่ต้องมีปุ่มกลาง เพราะเป็นสกิลของคลาสอยู่แล้ว)

⚠️ ชื่อสกิลกับตัวเลขทุกตัวมาจากเกมหลัก (`CLASS_SKILLS` + `get_skill_config`)
   ห้ามคิดเองหรือ hard-code ตัวเลข ไม่งั้นปรับที่ Panel แล้วสองโหมดไม่ตรงกัน
"""
import random
import sqlite3

import pytest

from bot import config_loader, mana
from bot.models import player_model
from bot.games.party import engine, room, skills


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
    # ⚠️ ตรึงให้เจอมอนเสมอ — ตั้งแต่เฟส 10b begin() สุ่มเหตุการณ์ได้หลายแบบ
    #    เทสชุดนี้ตรวจการต่อสู้ จึงต้องล็อกไว้ ไม่งั้นแดงแบบสุ่ม
    #    (เทสของเหตุการณ์อื่นอยู่ที่ test_party_events_roll.py)
    from bot.games.party import encounter as _enc
    monkeypatch.setattr(_enc, "roll_kind", lambda *a, **k: "monster")
    player_model.init_db()
    for uid in range(1, 7):
        player_model.get_player(uid)
    yield


class Dice:
    def __init__(self, *vals):
        self.vals = list(vals)

    def randint(self, a, b):
        # ⚠️ ค่าที่เตรียมไว้หมดแล้วคืน "ต่ำสุด" ไม่ใช่สูงสุด
        #    มอนแต่ละแรงค์ทอยไม่เท่ากัน (บอสถึง 5 ลูก) เตรียมไว้ 2 ค่าจึงไม่พอ
        #    คืนค่าสูงสุดทำให้ผลพลิกแบบสุ่ม เทสแดงทั้งที่โค้ดถูก (เจอ 3 รอบแล้ว)
        return self.vals.pop(0) if self.vals else a

    def choice(self, seq):
        return list(seq)[0]

    def random(self):
        return 0.5


def _battle(uids=(1, 2), cls="Warrior"):
    _, st = room.open_party(uids[0], "เอ")
    for u in uids[1:]:
        room.join_party(u, f"P{u}", st["room"])
    room.begin(uids[0])
    st = room._room(uids[0])
    b = st["extra"]["battle"]
    # ⚠️ มอนที่ไวกว่าอาจกวาดปาร์ตี้ร่วงตั้งแต่ยังไม่ทันเริ่ม — เติมเลือด
    #    **และล้างธงจบเกม** ไม่งั้นสั่งอะไรก็เจอ "สมรภูมินี้จบไปแล้ว" แบบสุ่ม ๆ
    b["over"], b["winner"] = False, None
    for u in b["units"].values():
        if u["side"] == "party":
            u["hp"] = u["hp_max"]
            u["class_name"] = cls
            u["cd"] = {}
    st["extra"]["battle"]["turn"] = st["extra"]["battle"]["order"].index("p1")
    return st


# ── ชุดสกิลตรงกับเกมหลัก ──

def test_ทุกคลาสมีสองสกิลตรงกับเกมหลัก():
    """⭐ ห้ามคิดชื่อสกิลเอง — เกมหลักประกาศไว้ที่ CLASS_SKILLS แล้ว"""
    from bot.views.profile_embed import CLASS_SKILLS
    for cls, names in CLASS_SKILLS.items():
        if cls == "Unknown":
            continue
        kit = skills.kit_for(cls)
        assert len(kit) == 2, f"{cls} มี {len(kit)} สกิล ควรมี 2"
        got = {skills.SPEC[k]["name"] for k in kit}
        assert got == set(names), f"{cls}: {got} ไม่ตรงกับเกมหลัก {set(names)}"


def test_คลาสที่ไม่รู้จักไม่มีสกิล():
    """ยังไม่ได้รับยศคลาส = ตีกับหนีเท่านั้น ไม่ใช่พังทั้งเกม"""
    assert skills.kit_for(None) == []
    assert skills.kit_for("ยศมั่ว") == []


def test_ทุกสกิลอ่านตัวเลขจากคอนฟิกเกมหลัก():
    """ปรับที่ Panel แล้วต้องมีผลกับโหมดนี้ด้วย"""
    for key, spec in skills.SPEC.items():
        cfg = config_loader.get_skill_config(spec["cls"], key)
        assert cfg, f"{key} ไม่มีคอนฟิกในเกมหลัก — ชื่อคีย์อาจสะกดไม่ตรง"


def test_ไม่มีตัวเลขสมดุลฝังในโค้ด():
    """เลขต้องมาจากคอนฟิก ไม่ใช่เขียนทับไว้ในไฟล์"""
    import pathlib
    src = pathlib.Path("bot/games/party/skills.py").read_text(encoding="utf-8")
    body = "\n".join(ln.split("#")[0] for ln in src.splitlines())
    for bad in ("0.6", "1.5", "2.0", "0.4"):
        assert f"= {bad}" not in body, f"มีเลขสมดุล {bad} ฝังในโค้ด ควรอ่านจากคอนฟิก"


# ── คำสั่งที่เซิร์ฟเวอร์ยอมรับ ──

def test_คำสั่งกลางเหลือแค่ตีกับหนี():
    """เจ้าของเกมสั่ง: ฮีล/ป้องกัน/กวาด ไม่ต้องมีปุ่มกลางแล้ว

    ⚠️ "heal" ยังอยู่ใน ACTIONS แต่คนละความหมาย — ตอนนี้เป็น ✨ Heal ของ Cleric
       ที่คลาสอื่นใช้ไม่ได้ ไม่ใช่ปุ่มกลางที่ทุกคนกดได้เหมือนเดิม
    """
    for gone in ("aoe", "defend", "skill"):
        assert gone not in engine.ACTIONS, f"ยังมีคำสั่งกลาง {gone} อยู่"
    assert "attack" in engine.ACTIONS and "flee" in engine.ACTIONS
    assert skills.SPEC["heal"]["cls"] == "Cleric", "ฮีลต้องเป็นของ Cleric เท่านั้น"
    assert "heal" not in skills.kit_for("Warrior")


def test_สกิลทุกตัวเป็นคำสั่งที่สั่งได้():
    for key in skills.SPEC:
        assert key in engine.ACTIONS, f"สั่ง {key} ไม่ได้"


def test_ใช้สกิลของคลาสอื่นไม่ได้():
    """⭐ กันคนยิง API ตรง ๆ ใช้ท่าที่ตัวเองไม่มี"""
    st = _battle(cls="Warrior")
    ok, r = engine.act(st, 1, "fireball", "m1", random.Random(1))
    assert not ok and "คลาส" in r["error"]


def test_ใช้สกิลของคลาสตัวเองได้():
    st = _battle(cls="Mage")
    foes = [u["id"] for u in st["extra"]["battle"]["units"].values()
            if u["side"] == "monster" and u["hp"] > 0]
    ok, r = engine.act(st, 1, "frostbolt", foes[0], random.Random(1))
    assert ok, r


# ── คูลดาวน์ ──

def test_ใช้สกิลแล้วติดคูลดาวน์():
    st = _battle(cls="Warrior")
    b = st["extra"]["battle"]
    foes = [u["id"] for u in b["units"].values() if u["side"] == "monster"][0]
    engine.act(st, 1, "heavy_strike", foes, random.Random(1))
    assert b["units"]["p1"]["cd"].get("heavy_strike", 0) > 0


def test_ยังติดคูลดาวน์ใช้ซ้ำไม่ได้():
    st = _battle(cls="Warrior")
    b = st["extra"]["battle"]
    b["units"]["p1"]["cd"] = {"heavy_strike": 2}
    foes = [u["id"] for u in b["units"].values() if u["side"] == "monster"][0]
    ok, r = engine.act(st, 1, "heavy_strike", foes, random.Random(1))
    assert not ok and "รอ" in r["error"]


def test_คูลดาวน์ลดลงทุกตาของเจ้าตัว():
    st = _battle(cls="Warrior")
    b = st["extra"]["battle"]
    b["units"]["p1"]["cd"] = {"heavy_strike": 2}
    foes = [u["id"] for u in b["units"].values() if u["side"] == "monster"][0]
    engine.act(st, 1, "attack", foes, random.Random(1))
    assert b["units"]["p1"]["cd"].get("heavy_strike") == 1


def test_คูลดาวน์คนละสกิลไม่ปนกัน():
    st = _battle(cls="Mage")
    b = st["extra"]["battle"]
    foes = [u["id"] for u in b["units"].values() if u["side"] == "monster"][0]
    engine.act(st, 1, "frostbolt", foes, random.Random(1))
    assert b["units"]["p1"]["cd"].get("fireball", 0) == 0, "กดท่าหนึ่งแล้วอีกท่าติดด้วย"


# ── มานา ──

def test_ออกท่าแล้วทอยชนะไม่เสียมานา():
    """⚠️ กฎเกมหลักเป๊ะ ๆ — ทอยชนะถือว่าคุ้มค่าท่า ไม่หักเม็ด"""
    st = _battle(cls="Warrior")
    b = st["extra"]["battle"]
    tgt = [u for u in b["units"].values() if u["side"] == "monster"][0]
    tgt["stats"] = {"dice_count": 1}      # ตรึงจำนวนลูกเต๋า ไม่งั้นเต๋าปลอมหมดก่อน
    before = mana.get(1)
    engine.act(st, 1, "heavy_strike", tgt["id"], Dice(19, 2))
    assert mana.get(1) == before, "ทอยชนะแล้วยังเสียมานา"


def test_ออกท่าแล้วทอยแพ้เสียมานา():
    st = _battle(cls="Warrior")
    b = st["extra"]["battle"]
    tgt = [u for u in b["units"].values() if u["side"] == "monster"][0]
    tgt["stats"] = {"dice_count": 1}      # ตรึงจำนวนลูกเต๋า ไม่งั้นเต๋าปลอมหมดก่อน
    before = mana.get(1)
    engine.act(st, 1, "heavy_strike", tgt["id"], Dice(2, 20))
    assert mana.get(1) == before - 1, "ทอยแพ้แล้วไม่เสียมานา"


def test_มานาหมดออกท่าไม่ได้():
    st = _battle(cls="Warrior")
    b = st["extra"]["battle"]
    mana.spend(1, 99)
    foes = [u["id"] for u in b["units"].values() if u["side"] == "monster"][0]
    ok, r = engine.act(st, 1, "heavy_strike", foes, random.Random(1))
    assert not ok and "คริสตัล" in r["error"]


def test_มานาหมดยังตีปกติได้():
    """ตีปกติไม่กินมานา ไม่งั้นมานาหมดแล้วทำอะไรไม่ได้เลย"""
    st = _battle(cls="Warrior")
    mana.spend(1, 99)
    foes = [u["id"] for u in st["extra"]["battle"]["units"].values()
            if u["side"] == "monster"][0]
    ok, r = engine.act(st, 1, "attack", foes["id"] if isinstance(foes, dict) else foes,
                       random.Random(1))
    assert ok, r


# ── ผลของแต่ละสกิล ──

def _unit_mon():
    return {"id": "m9", "side": "monster", "hp": 500, "hp_max": 500, "atk": 40,
            "def": 0, "defending": False, "fx": {}, "element": None,
            "name": "m", "level": 1, "stats": {"dice_count": 1}}


def _dummy():
    return {"id": "x", "side": "monster", "hp": 90000, "hp_max": 90000, "def": 0,
            "defending": False, "fx": {}, "element": None, "name": "x", "level": 1}


def _hit_with(me, key, dice):
    """ตีหนึ่งครั้งด้วยท่านี้ — คืนดาเมจที่ทำได้"""
    t = _dummy()
    if key == "attack":
        engine.strike(dict(me), t, "attack", dice)
    else:
        skills.use(dict(me), t, key, [me], [t], dice)
    return 90000 - t["hp"]


def test_ท่าโจมตีแรงกว่าตีปกติ():
    st = _battle(cls="Warrior")
    me = st["extra"]["battle"]["units"]["p1"]
    assert _hit_with(me, "heavy_strike", Dice(19, 2)) > _hit_with(me, "attack", Dice(19, 2))


def test_heavy_strike_แรงกว่าท่าโจมตีธรรมดาของคลาสเดียวกัน():
    """⭐ เทียบกับ **ท่าอื่น** ไม่ใช่ตีปกติ

    ⚠️ ฉบับแรกเทียบกับตีปกติ ซึ่งผ่านเพราะ "ตัวคูณสกิลกลาง" (skill_mult)
       ไม่ใช่เพราะ damage_multiplier ของ Heavy Strike เอง
       ย้อนเทสตั้งตัวคูณเป็น 1.0 แล้วเทสยังเขียว (2026-09-04)
       shield_bash ใช้เงื่อนไขเดียวกันหมดยกเว้นไม่มีตัวคูณ จึงเป็นตัวเทียบที่ถูก
    """
    st = _battle(cls="Warrior")
    me = st["extra"]["battle"]["units"]["p1"]
    heavy = _hit_with(me, "heavy_strike", Dice(19, 2))
    plain = _hit_with(me, "shield_bash", Dice(19, 2))
    assert heavy > plain, f"Heavy Strike ทำ {heavy} เท่ากับท่าไม่มีตัวคูณ ({plain})"


def test_backstab_แรงกว่าท่าไม่มีตัวคูณ():
    st = _battle(cls="Rogue")
    me = st["extra"]["battle"]["units"]["p1"]
    me["class_name"] = "Warrior"          # ยืม shield_bash มาเป็นตัวเทียบ
    plain = _hit_with(me, "shield_bash", Dice(19, 2))
    me["class_name"] = "Rogue"
    assert _hit_with(me, "backstab", Dice(19, 2)) > plain


def test_fireball_โดนศัตรูทุกตัว():
    st = _battle(cls="Mage")
    b = st["extra"]["battle"]
    foes = [u for u in b["units"].values() if u["side"] == "monster"]
    ok, r = engine.act(st, 1, "fireball", None, Dice(*([19, 2] * 10)))
    assert ok, r
    hit = [e for e in r["events"] if e["t"] == "aoe"]
    assert hit and len(hit[0]["targets"]) == len(foes)


def test_frostbolt_ทำให้เป้าช้าลง():
    st = _battle(cls="Mage")
    b = st["extra"]["battle"]
    tgt = [u for u in b["units"].values() if u["side"] == "monster"][0]
    engine.act(st, 1, "frostbolt", tgt["id"], Dice(19, 2))
    assert int(tgt["fx"].get("slow") or 0) > 0, "โดน Frostbolt แล้วไม่ติดสถานะช้า"


def test_shield_bash_ยกโล่รับให้ตัวเอง():
    """เกมหลักบอกว่าเป็นท่าลดดาเมจ (reduction_base) — ต้องคงคาแรกเตอร์เดิม
    เจ้าของเกมบอกว่าไม่ต้องมีปุ่ม "ป้องกัน" กลาง เพราะคลาสมีท่านี้อยู่แล้ว"""
    st = _battle(cls="Warrior")
    b = st["extra"]["battle"]
    tgt = [u for u in b["units"].values() if u["side"] == "monster"][0]
    engine.act(st, 1, "shield_bash", tgt["id"], Dice(19, 2))
    assert int(b["units"]["p1"]["fx"].get("ward") or 0) > 0, "ยกโล่แล้วไม่ติดบัฟ"


def test_ยกโล่แล้วรับดาเมจน้อยลงจริง():
    """ติดบัฟแต่ไม่ลดดาเมจ = เสียตาเปล่า"""
    st = _battle(cls="Warrior")
    me = _unit_mon()
    plain = dict(st["extra"]["battle"]["units"]["p1"], hp=9000, hp_max=9000, fx={})
    warded = dict(plain, fx={"ward": 3})
    engine.strike(me, plain, "attack", Dice(19, 2))
    engine.strike(me, warded, "attack", Dice(19, 2))
    assert 9000 - warded["hp"] < 9000 - plain["hp"], "ยกโล่แล้วเจ็บเท่าเดิม"


def test_evasion_ทำให้ตัวเองหลบได้():
    st = _battle(cls="Rogue")
    ok, r = engine.act(st, 1, "evasion", None, random.Random(1))
    assert ok, r
    assert int(st["extra"]["battle"]["units"]["p1"]["fx"].get("evade") or 0) > 0


def test_holy_aura_คุ้มทั้งปาร์ตี้():
    """ของ Cleric — ทั้งปาร์ตี้รับดาเมจน้อยลง ไม่ใช่แค่ตัวเอง"""
    st = _battle(uids=(1, 2, 3), cls="Cleric")
    ok, r = engine.act(st, 1, "holy_aura", None, random.Random(1))
    assert ok, r
    for u in st["extra"]["battle"]["units"].values():
        if u["side"] == "party":
            assert int(u["fx"].get("aura") or 0) > 0, f"{u['id']} ไม่ได้ออร่า"


def test_heal_ฟื้นเลือดเพื่อน():
    st = _battle(uids=(1, 2), cls="Cleric")
    b = st["extra"]["battle"]
    b["units"]["p2"]["hp"] = 10
    ok, r = engine.act(st, 1, "heal", "p2", random.Random(1))
    assert ok, r
    assert b["units"]["p2"]["hp"] > 10


def test_heal_ชุบเพื่อนที่ล้มได้():
    """สเปกข้อ 5: ตายแล้วนั่งดูจนโดนชุบ — Heal ของ Cleric คือทางนั้น"""
    st = _battle(uids=(1, 2), cls="Cleric")
    b = st["extra"]["battle"]
    b["units"]["p2"]["hp"] = 0
    ok, r = engine.act(st, 1, "heal", "p2", random.Random(1))
    assert ok, r
    assert b["units"]["p2"]["hp"] > 0, "ฮีลคนที่ล้มแล้วไม่ฟื้น"


def test_backstab_มีโอกาสคริสูงกว่าปกติ():
    import pathlib
    src = pathlib.Path("bot/games/party/skills.py").read_text(encoding="utf-8")
    assert "backstab" in src


# ── หน้าเว็บต้องรู้ว่าตัวเองมีอะไร ──

def test_view_บอกชุดสกิลของเราเอง():
    st = _battle(cls="Rogue")
    me = [u for u in engine.view(st, 1)["units"] if u.get("you")][0]
    assert [s["key"] for s in me["skills"]] == skills.kit_for("Rogue")
    assert all(s.get("name") for s in me["skills"])


def test_view_บอกคูลดาวน์กับมานา():
    st = _battle(cls="Warrior")
    st["extra"]["battle"]["units"]["p1"]["cd"] = {"heavy_strike": 2}
    got = engine.view(st, 1)
    me = [u for u in got["units"] if u.get("you")][0]
    cd = {s["key"]: s["cd"] for s in me["skills"]}
    assert cd["heavy_strike"] == 2
    assert "mana" in me and "mana_max" in me


def test_view_ไม่บอกชุดสกิลของคนอื่น():
    """🔒 ประตูเดียว — รู้ท่าเพื่อนไม่เป็นไร แต่ไม่ควรหลุดของมอน"""
    st = _battle(cls="Warrior")
    for u in engine.view(st, 1)["units"]:
        if u["side"] == "monster":
            assert "skills" not in u
