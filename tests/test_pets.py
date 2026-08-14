"""C4: สัตว์เลี้ยง — จับจากมอนที่ล้ม ติดได้ทีละตัว หนุนเต๋าตอนสู้"""
import json

import pytest

import bot.models.player_model as pm
from bot import config_loader, pets

CFG = {"pets": {
    "tame_chance": {"Common": 100, "Mini-Boss": 0},
    "list": [
        {"key": "slime", "name": "🟢 สไลม์", "from_rank": "Common", "dice": 1},
        {"key": "bat", "name": "🦇 ค้างคาว", "from_rank": "Common", "dice": 1},
        {"key": "wolf", "name": "🐺 หมาป่า", "from_rank": "Mini-Boss", "dice": 2},
    ]}}


@pytest.fixture
def world(tmp_path, monkeypatch):
    monkeypatch.setattr(pm, "DB_NAME", str(tmp_path / "t.db"))
    monkeypatch.setattr(config_loader, "get_config", lambda: CFG)
    state = {"pet": ""}
    monkeypatch.setattr(pm, "get_player", lambda uid: dict(state))
    monkeypatch.setattr(pm, "update_player_field", lambda uid, f, v: state.__setitem__(f, v))
    return state


def test_bonus_only_when_a_pet_is_equipped(world):
    assert pets.roll_bonus({"pet": ""}) == 0
    assert pets.roll_bonus({"pet": "wolf"}) == 2
    assert pets.roll_bonus({"pet": "ไม่มีตัวนี้"}) == 0     # คีย์เพี้ยนต้องไม่พังไฟต์


def test_tame_grants_and_auto_equips_the_first_one(world):
    pet = pets.try_tame(1, "Common")
    assert pet and pet["key"] in ("slime", "bat")
    assert world["pet"] == pet["key"], "ตัวแรกต้องติดให้อัตโนมัติ"
    assert "จับมาเลี้ยงได้" in pets.tame_message(pet)


def test_second_pet_does_not_steal_the_active_slot(world):
    first = pets.try_tame(1, "Common")
    second = pets.try_tame(1, "Common")
    assert second and second["key"] != first["key"]        # ตัวที่มีแล้วไม่ออกซ้ำ
    assert world["pet"] == first["key"], "ตัวที่ติดอยู่ต้องไม่ถูกเปลี่ยนเอง"


def test_pool_exhausted_returns_none(world):
    pets.try_tame(1, "Common")
    pets.try_tame(1, "Common")
    assert pets.try_tame(1, "Common") is None              # เก็บครบแรงค์นี้แล้ว
    assert pets.tame_message(None) == ""


def test_zero_chance_rank_never_tames(world):
    assert pets.try_tame(1, "Mini-Boss") is None
    assert pets.owned(1) == set()


def test_cannot_equip_what_you_dont_own(world):
    ok, msg = pets.set_active(1, "wolf")
    assert not ok and "ยังไม่มี" in msg and world["pet"] == ""

    pets.try_tame(1, "Common")
    ok, _ = pets.set_active(1, "")                         # ปล่อยออกได้เสมอ
    assert ok and world["pet"] == ""


def test_embed_marks_owned_and_locked(world):
    pets.try_tame(1, "Common")
    embed = pets.build_pet_embed(1, "T")
    text = "\n".join(f.name + f.value for f in embed.fields)
    assert "✅ **มีแล้ว**" in text and "🔒" in text


def test_wired_into_the_fight():
    import pathlib
    src = pathlib.Path("bot/views/game_views.py").read_text(encoding="utf-8")
    # การทอยเต๋าย้ายไป adventure_core แล้ว (เว็บเกม เฟส 5.2) — โบนัสสัตว์เลี้ยงตามไปด้วย
    core = pathlib.Path("bot/adventure_core.py").read_text(encoding="utf-8")
    assert "_pets.roll_bonus(player)" in core, "โบนัสเต๋าต้องเข้าไปในการทอยจริง"
    assert 'parts.append(f"🐾' in core, "ต้องโชว์ที่มาของแต้มในหน้าจอไฟต์"
    assert "_pets.try_tame(self.user_id, self.monster_rank)" in src


def test_config_pets_valid():
    cfg = json.load(open("config.example.json", encoding="utf-8"))["pets"]
    keys = [p["key"] for p in cfg["list"]]
    assert len(keys) == len(set(keys)), "คีย์ซ้ำ = จับได้ตัวเดียวแต่ขึ้นสองช่อง"
    ranks = {p["from_rank"] for p in cfg["list"]}
    assert ranks <= set(cfg["tame_chance"]), "มีสัตว์เลี้ยงที่ไม่มีทางจับได้ (แรงค์ไม่มีโอกาสตั้งไว้)"
    assert "pet" in pm.NEW_PLAYER_DEFAULTS
