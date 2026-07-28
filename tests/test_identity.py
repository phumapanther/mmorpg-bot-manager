"""P8-④ เผ่า/คลาส: ยศมาก่อน → ไม่มียศใช้ DB → ไม่มีทั้งคู่สุ่มให้"""
import asyncio
import random
from types import SimpleNamespace

import bot.identity as identity
import bot.models.player_model as pm
from bot.views.profile_embed import GAME_CLASSES, GAME_RACES, MONSTER_RACES

DRAGON = GAME_RACES[4]      # 、🐉 • มังกร
LICH = MONSTER_RACES[6]     # • Lich


def _roles(*names):
    return [SimpleNamespace(name=n) for n in names]


def test_detect_and_roll():
    assert identity.detect_from_roles([DRAGON, "Warrior"]) == (DRAGON, "Warrior")
    assert identity.detect_from_roles(["สุ่มมั่ว"]) == (None, None)
    race, cls = identity.roll_identity(random.Random(1))
    assert race in identity.ALL_RACES and cls in GAME_CLASSES


def test_effective_names_priority():
    db = {"race": LICH, "class_name": "Mage"}
    # มียศจริง → ยศชนะ DB
    names = identity.effective_role_names(_roles(DRAGON, "Warrior"), db)
    assert DRAGON in names and LICH not in names
    # ไม่มียศ → ใช้ DB
    names2 = identity.effective_role_names([], db)
    assert LICH in names2 and "Mage" in names2
    # ไม่มีทั้งคู่ → ว่าง
    assert identity.effective_role_names([], {}) == []


def _fake_db(monkeypatch, player):
    saved = {}
    monkeypatch.setattr(pm, "update_player_fields", lambda uid, updates: saved.update(updates))
    return saved


def test_roles_sync_into_db(monkeypatch):
    saved = _fake_db(monkeypatch, {})
    member = SimpleNamespace(id=1, roles=_roles(DRAGON, "Warrior"), guild=SimpleNamespace(roles=[]))
    msg = asyncio.run(identity.ensure_identity(member, {"race": "", "class_name": ""}, True))
    assert msg is None                                    # มียศแล้วไม่ต้องประกาศอะไร
    assert saved == {"race": DRAGON, "class_name": "Warrior"}


def test_secondary_server_rolls_and_saves(monkeypatch):
    saved = _fake_db(monkeypatch, {})
    member = SimpleNamespace(id=1, roles=[], guild=SimpleNamespace(roles=[]))
    msg = asyncio.run(identity.ensure_identity(member, {}, False))
    assert saved["race"] in identity.ALL_RACES and saved["class_name"] in GAME_CLASSES
    assert "โชคชะตา" in msg and "เซิร์ฟหลัก" in msg
    # มีค่าใน DB แล้ว = ไม่สุ่มซ้ำ
    saved.clear()
    assert asyncio.run(identity.ensure_identity(member, {"race": LICH, "class_name": "Mage"}, False)) is None
    assert saved == {}


def test_main_server_rolls_and_gives_roles(monkeypatch):
    saved = _fake_db(monkeypatch, {})
    given = []

    async def add_roles(role, reason=None):
        given.append(role.name)

    guild_roles = [SimpleNamespace(name=r) for r in identity.ALL_RACES + GAME_CLASSES]
    member = SimpleNamespace(id=1, roles=[], guild=SimpleNamespace(roles=guild_roles), add_roles=add_roles)
    msg = asyncio.run(identity.ensure_identity(member, {"race": LICH, "class_name": "Mage"}, True))
    # เข้าเซิร์ฟหลักครั้งแรก = สุ่มใหม่ + แจกยศจริง (ตามสเปก)
    assert saved["race"] in identity.ALL_RACES and len(given) == 2
    assert "พิธีกำเนิด" in msg and "ได้รับยศจริง" in msg
