"""🧬 สมุดธาตุ — ทวีป × แรงค์ × ธาตุ + รางวัล 3 ชั้น (แรงค์ → ทวีป → ทั้งเล่ม)"""
import json
import sqlite3

import pytest

import bot.models.player_model as pm
from bot import config_loader
from bot import game_modifiers as gm

ELS = list(gm.ELEMENTS)
RANKS = gm.ELEMENT_BOOK_RANKS


@pytest.fixture
def db(tmp_path, monkeypatch):
    path = str(tmp_path / "t.db")
    monkeypatch.setattr(pm, "DB_NAME", path)
    sqlite3.connect(path).close()
    return path


def _fill(uid, continent, ranks=RANKS, elements=ELS):
    for r in ranks:
        for e in elements:
            pm.record_element_kill(uid, continent, r, e)


# ── ตัวสมุด ──

def test_records_each_element_separately(db):
    pm.record_element_kill(1, "main", "Common", "fire")
    pm.record_element_kill(1, "main", "Common", "fire")
    pm.record_element_kill(1, "main", "Common", "water")
    book = pm.get_element_book(1)
    assert book[("main", "Common", "fire")] == 2 and book[("main", "Common", "water")] == 1


def test_monster_without_element_is_skipped(db):
    pm.record_element_kill(1, "main", "Common", None)
    pm.record_element_kill(1, "main", "Common", "")
    assert pm.get_element_book(1) == {}


def test_rank_and_continent_completion(db):
    _fill(1, "main", ranks=["Common"])
    book = pm.get_element_book(1)
    assert gm.element_rank_done(book, "main", "Common")
    assert not gm.element_rank_done(book, "main", "Secret")
    assert not gm.element_continent_done(book, "main")

    _fill(1, "main")
    book = pm.get_element_book(1)
    assert gm.element_continent_done(book, "main")
    assert gm.element_progress(book, "main") == (35, 35)
    assert not gm.element_book_complete(book)


def test_full_book_needs_every_continent(db):
    for c in gm.CONTINENTS:
        _fill(1, c)
    assert gm.element_book_complete(pm.get_element_book(1))


def test_grid_size_is_five_ranks_by_seven_elements():
    assert len(RANKS) == 5 and "Unbeatable" in RANKS
    assert len(ELS) == 7
    assert gm.element_progress({}, "main") == (0, 35)


def test_every_continent_can_actually_spawn_every_element():
    """กันช่องตาย: ถ้าทวีปไหนมีธาตุน้ำหนัก 0 ผู้เล่นจะเก็บไม่ครบตลอดชาติ"""
    for key, c in gm.CONTINENTS.items():
        w = {**gm.DEFAULT_ELEMENT_WEIGHTS, **((c.get("mods") or {}).get("element_weights") or {})}
        dead = [e for e in ELS if w.get(e, 0) <= 0]
        assert not dead, f"ทวีป {key} ไม่มีทางเจอธาตุ {dead}"


# ── รางวัล ──

class _Book:
    """ตัวเรียก record_element_book ที่ย้ายไป adventure_core แล้ว (เว็บเกม เฟส 5.6c)"""

    def __init__(self, rank, element):
        self.rank, self.element = rank, element

    def _record_element_book(self, cont, upd):
        from bot import adventure_core
        return adventure_core.record_element_book(1, cont, self.rank, self.element, upd)


def _view(db, monkeypatch, cont="main", rank="Common", element="fire"):
    monkeypatch.setattr(pm, "get_player", lambda uid: {"inventory": "[]"})
    return _Book(rank, element)


def test_rank_completion_pays_gold_once(db, monkeypatch):
    _fill(1, "main", ranks=["Common"], elements=ELS[:-1])      # ขาดธาตุสุดท้าย
    v = _view(db, monkeypatch, element=ELS[-1])
    upd = {}
    msg = v._record_element_book("main", upd)
    gold = int((config_loader.get_balance("bestiary.element_rank_rewards", {}) or {})["Common"])
    assert upd["cash"] == gold and "สมุดธาตุครบชุด" in msg

    upd2 = {}
    assert "สมุดธาตุครบชุด" not in v._record_element_book("main", upd2), "รับซ้ำไม่ได้"
    assert upd2.get("cash", 0) == 0


def test_continent_completion_gives_that_continents_artifact(db, monkeypatch):
    _fill(1, "sylvan")
    for r in RANKS:                                            # ถอนช่องสุดท้ายออกให้เหลือไว้ยิงเอง
        pass
    conn = sqlite3.connect(db)
    conn.execute("DELETE FROM bestiary_elements WHERE rank = ? AND element = ?", ("Unbeatable", ELS[-1]))
    conn.commit()
    conn.close()

    v = _view(db, monkeypatch, rank="Unbeatable", element=ELS[-1])
    upd = {}
    msg = v._record_element_book("sylvan", upd)
    art = str((config_loader.get_balance("bestiary.continent_artifacts", {}) or {})["sylvan"])
    assert art in json.loads(upd["inventory"]), "ต้องได้อาร์ติแฟกต์ของทวีปนั้น"
    assert "ครบทั้งทวีป" in msg


def test_artifact_map_covers_every_continent_without_duplicates():
    arts = config_loader.get_balance("bestiary.continent_artifacts", {}) or {}
    assert set(arts) == set(gm.CONTINENTS), "ทวีปที่ไม่มีอาร์ติแฟกต์ = เก็บครบแล้วไม่ได้อะไร"
    assert len(set(arts.values())) == len(arts), "อาร์ติแฟกต์ซ้ำระหว่างทวีป"
    for cont, iid in arts.items():
        item = config_loader.get_item_config(str(iid))
        assert item.get("effect") == "equip_artifact", f"{cont} ชี้ไปไอเทมที่ไม่ใช่อาร์ติแฟกต์"


def test_full_book_grants_the_top_pet(db, monkeypatch):
    from bot import pets
    for c in gm.CONTINENTS:
        _fill(1, c)
    conn = sqlite3.connect(db)
    conn.execute("DELETE FROM bestiary_elements WHERE continent = ? AND rank = ? AND element = ?",
                 ("ocean", "Unbeatable", ELS[-1]))
    conn.commit()
    conn.close()

    v = _view(db, monkeypatch, rank="Unbeatable", element=ELS[-1])
    msg = v._record_element_book("ocean", {})
    pet_key = config_loader.get_balance("bestiary.element_complete_pet")
    assert pet_key in pets.owned(1), "ต้องได้สัตว์เลี้ยงขั้นสูงสุด"
    assert "ทั้ง 9 ทวีป" in msg

    top = max(pets.all_pets(), key=lambda p: int(p.get("dice", 0)))
    assert top["key"] == pet_key, "รางวัลต้องเป็นสัตว์เลี้ยงที่แรงที่สุดจริง"


def test_broken_element_book_never_kills_the_fight(db, monkeypatch):
    v = _view(db, monkeypatch)
    monkeypatch.setattr(pm, "record_element_kill", lambda *a: 1 / 0)
    import pathlib
    src = pathlib.Path("bot/adventure_core.py").read_text(encoding="utf-8")
    block = src[src.index("# 📕 สมุดสะสมมอน (Bestiary)"):]
    assert "try:" in block[:120], "ต้องอยู่ใน try/except เดิมของสมุดล่า"


def test_wired_into_the_win_path():
    import pathlib
    src = pathlib.Path("bot/adventure_core.py").read_text(encoding="utf-8")
    assert "record_element_book(user_id, cont_key, monster_rank, element, db_updates)" in src
