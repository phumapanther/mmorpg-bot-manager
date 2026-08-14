"""🎲 กระดานทอยเต๋ารับของรายวัน (เว็บเกม เฟส 8)

นี่คือทางเข้าเงิน/ไอเทมใหม่ของเศรษฐกิจ เทสชุดนี้จึงเน้นสองเรื่องเป็นหลัก:
  1. โควตา 3 ครั้ง/วัน ต้องรั่วไม่ได้ (กดรัว/ยิงพร้อมกันก็ต้องไม่ได้ของเกิน)
  2. ของที่แจกต้องเล็กและผ่านปุ่มหรี่ทองรวมของ Panel เหมือนแหล่งอื่น
"""
import pathlib
import random

import pytest

import bot.models.player_model as pm
from bot import config_loader, dice_board, game_modifiers

ITEMS = {"1": {"name": "💉 ยาฮีล", "buy": 300},
         "2": {"name": "🛠️ ใบซ่อมแซม", "buy": 500},
         "29": {"name": "🔮 มานาคริสตัลบริสุทธิ์", "buy": 50000}}


@pytest.fixture
def hero(monkeypatch):
    p = {"user_id": 1, "level": 10, "cash": 0, "exp": 0, "max_hp": 500, "hp": 500,
         "inventory": "[]", "capacity": 10, "status_effects": "{}",
         "board_pos": 0, "board_rolls": 3, "board_date": dice_board._today()}
    monkeypatch.setattr(pm, "get_player", lambda uid: dict(p))
    monkeypatch.setattr(pm, "update_player_field", lambda uid, f, v: p.__setitem__(f, v))
    monkeypatch.setattr(pm, "update_player_fields", lambda uid, d: p.update(d))
    monkeypatch.setattr(pm, "increment_player_field",
                        lambda uid, f, v: p.__setitem__(f, p.get(f, 0) + v))
    monkeypatch.setattr(pm, "add_exp", lambda uid, e: p.__setitem__("exp", p["exp"] + e))
    monkeypatch.setattr(config_loader, "get_item_config", lambda i: ITEMS.get(str(i)))
    monkeypatch.setattr(config_loader, "get_balance", lambda k, d=None: d)
    return p


class Steps(random.Random):
    """คุมจำนวนก้าวที่ทอยได้"""

    def __init__(self, steps):
        super().__init__(0)
        self.steps = steps

    def randint(self, a, b):
        return self.steps if (a, b) == (1, 6) else super().randint(a, b)


# ── โควตา: ห้ามรั่วเด็ดขาด ───────────────────────────────────────────────────

def test_three_rolls_a_day_and_not_one_more(hero):
    for i in range(3):
        ok, r = dice_board.roll(1, rng=Steps(1))
        assert ok, f"ครั้งที่ {i+1} ทอยไม่ได้ทั้งที่ยังมีโควตา"
        assert r["rolls_left"] == 2 - i
    ok, r = dice_board.roll(1, rng=Steps(1))
    assert not ok and "ครบโควตา" in r["error"]


def test_spamming_the_button_never_gives_extra_loot(hero):
    """กดรัว 30 ครั้งต้องได้ของแค่ 3 ครั้ง — โควตาหักในจังหวะเดียวกับการทอย"""
    got = sum(1 for _ in range(30) if dice_board.roll(1, rng=Steps(2))[0])
    assert got == 3, f"ทอยผ่านไป {got} ครั้ง ทั้งที่โควตามี 3"
    assert hero["board_rolls"] == 0


def test_a_new_day_gives_the_quota_back(hero):
    hero.update(board_rolls=0, board_date="2020-01-01")
    assert dice_board.rolls_left(1) == 3
    assert dice_board.roll(1, rng=Steps(1))[0]


def test_the_quota_is_shared_with_discord():
    """ทอยบนเว็บกับใน !board ต้องหักโควตาก้อนเดียวกัน"""
    api = pathlib.Path("license_server/web_api.py").read_text(encoding="utf-8")
    cog = pathlib.Path("bot/cogs/dice_board_cmd.py").read_text(encoding="utf-8")
    assert "dice_board.roll(uid)" in api and "dice_board.roll(self.user_id)" in cog


def test_panel_can_retune_the_quota(hero, monkeypatch):
    monkeypatch.setattr(config_loader, "get_balance",
                        lambda k, d=None: 1 if k == "dice_board.rolls_per_day" else d)
    hero.update(board_rolls=1, board_date=dice_board._today())
    assert dice_board.roll(1, rng=Steps(1))[0]
    assert not dice_board.roll(1, rng=Steps(1))[0]


# ── เดินกระดาน ───────────────────────────────────────────────────────────────

def test_the_pawn_wraps_around_and_pays_a_lap_bonus(hero):
    hero["board_pos"] = dice_board.BOARD_SIZE - 2
    ok, r = dice_board.roll(1, rng=Steps(4))
    assert ok and r["lapped"] and r["to"] == 2
    assert r["lap_bonus"] > 0 and hero["cash"] >= r["lap_bonus"]


def test_no_lap_bonus_without_completing_a_lap(hero):
    hero["board_pos"] = 0
    ok, r = dice_board.roll(1, rng=Steps(3))
    assert ok and not r["lapped"] and "lap_bonus" not in r


def test_the_pawn_position_survives_between_rolls(hero):
    dice_board.roll(1, rng=Steps(5))
    assert hero["board_pos"] == 5
    dice_board.roll(1, rng=Steps(3))
    assert hero["board_pos"] == 8


# ── ของที่แจก ────────────────────────────────────────────────────────────────

def test_every_tile_actually_pays_something_it_promises(hero):
    """ไล่ยืนหมากทีละช่องทั้งกระดาน — ทุกช่องต้องจ่ายของตรงชนิดที่ประกาศไว้"""
    tiles = dice_board.board("normal")
    for i, tile in enumerate(tiles):
        if tile["kind"] in ("none", "lap"):
            continue
        hero.update(board_pos=(i - 1) % dice_board.BOARD_SIZE, board_rolls=3,
                    cash=0, exp=0, inventory="[]", status_effects="{}",
                    board_date=dice_board._today())
        ok, r = dice_board.roll(1, rng=Steps(1))
        assert ok and r["to"] == i
        if tile["kind"] == "gold":
            assert r.get("gold", 0) > 0, f"ช่อง {i} {tile['label']} ไม่จ่ายทอง"
        elif tile["kind"] == "exp":
            assert r.get("exp", 0) > 0, f"ช่อง {i} {tile['label']} ไม่จ่าย EXP"
        elif tile["kind"] == "item":
            assert r.get("item"), f"ช่อง {i} {tile['label']} ไม่ให้ไอเทม"
        elif tile["kind"] == "buff":
            assert r.get("buff"), f"ช่อง {i} {tile['label']} ไม่ติดบัฟ"


def test_a_full_bag_does_not_swallow_the_item(hero):
    tiles = dice_board.board("normal")
    idx = next(i for i, t in enumerate(tiles) if t["kind"] == "item")
    hero.update(board_pos=(idx - 1) % dice_board.BOARD_SIZE,
                inventory='["1","1","1","1","1","1","1","1","1","1"]', capacity=10)
    ok, r = dice_board.roll(1, rng=Steps(1))
    assert ok and r.get("bag_full") and "กระเป๋าเต็ม" in r["text"]


def test_board_rewards_obey_the_global_gold_knob(hero, monkeypatch):
    """ปุ่มหรี่ทองรวมของ Panel ต้องคุมกระดานด้วย ไม่งั้นเป็นรูรั่วใหม่"""
    monkeypatch.setattr(config_loader, "get_balance",
                        lambda k, d=None: 0.0 if k == "reward.gold_mult" else d)
    tiles = dice_board.board("normal")
    idx = next(i for i, t in enumerate(tiles) if t["kind"] == "gold")
    hero["board_pos"] = (idx - 1) % dice_board.BOARD_SIZE
    ok, r = dice_board.roll(1, rng=Steps(1))
    assert ok and r["gold"] <= 1, "ตั้งตัวคูณ 0 แล้วทองต้องแทบไม่ออก"


def test_the_payouts_stay_small(hero):
    """ของรางวัลตั้งใจให้จิปาถะ — กันเผลอตั้งเลขหลุดจนกลายเป็นแหล่งรวยใหม่"""
    for tile in dice_board.board("normal"):
        if tile["kind"] == "gold":
            assert tile["amount"][1] <= 2000, f"{tile['label']} จ่ายทองเยอะเกินสำหรับกระดาน"
        if tile["kind"] == "exp":
            assert tile["amount"][1] <= 300, f"{tile['label']} จ่าย EXP เยอะเกิน"


# ── ธีมสัปดาห์ ────────────────────────────────────────────────────────────────

def test_the_board_changes_with_the_weekly_theme():
    base = dice_board.board("normal")
    assert any(dice_board.board(k) != base for k in dice_board._THEME_TILES), \
        "ทุกธีมได้กระดานหน้าตาเดียวกันหมด"


def test_every_theme_board_is_still_the_right_size_and_valid():
    from bot.game_data import WEEKLY_THEMES
    kinds = {"gold", "exp", "item", "buff", "none", "lap"}
    for t in list(WEEKLY_THEMES) + [{"key": "ธีมที่ยังไม่มี"}]:
        b = dice_board.board(t["key"])
        assert len(b) == dice_board.BOARD_SIZE, f"กระดานธีม {t['key']} ขนาดเพี้ยน"
        assert b[0]["kind"] == "lap", "ช่องแรกต้องเป็นจุดเริ่มเสมอ"
        for tile in b:
            assert tile["kind"] in kinds, f"ธีม {t['key']} มีช่องชนิดไม่รู้จัก: {tile['kind']}"


def test_theme_tiles_only_use_items_and_buffs_that_exist():
    """ตั้งช่องธีมชี้ไปที่ของที่ไม่มีจริง = ตกช่องนั้นแล้วได้ข้อความว่างเปล่า"""
    items = config_loader.get_all_items()
    for key, tiles in dice_board._THEME_TILES.items():
        for idx, tile in tiles.items():
            if tile["kind"] == "item":
                assert str(tile["item"]) in items, f"ธีม {key} ช่อง {idx} ชี้ไอเทมที่ไม่มี"
            if tile["kind"] == "buff":
                assert tile["status"] in game_modifiers.STATUS_EFFECTS, \
                    f"ธีม {key} ช่อง {idx} ชี้สถานะที่ไม่มี"


def test_base_board_only_uses_items_and_buffs_that_exist():
    items = config_loader.get_all_items()
    for tile in dice_board._BASE:
        if tile["kind"] == "item":
            assert str(tile["item"]) in items, f"{tile['label']} ชี้ไอเทมที่ไม่มีจริง"
        if tile["kind"] == "buff":
            assert tile["status"] in game_modifiers.STATUS_EFFECTS


def test_new_players_start_at_the_first_square():
    assert pm.NEW_PLAYER_DEFAULTS.get("board_pos") == 0
    assert "board_rolls" in pm.NEW_PLAYER_DEFAULTS and "board_date" in pm.NEW_PLAYER_DEFAULTS


def test_the_web_page_draws_the_board_from_the_server():
    """เบราว์เซอร์ต้องไม่มีกระดานฝังไว้เอง ไม่งั้นธีมเปลี่ยนแล้วหน้าเว็บไม่ตาม"""
    js = pathlib.Path("license_server/web_static/play.js").read_text(encoding="utf-8")
    assert "api('GET', '/api/web/board')" in js and "paintBoard(" in js
    assert "const TILES = [" not in js, "ยังมีกระดานตัวอย่างฝังอยู่ในหน้าเว็บ"
    assert "hopTo(" in js, "หมากต้องเดินทีละช่องให้เห็น ไม่ใช่วาร์ป"


def test_the_roll_button_locks_when_the_quota_is_gone():
    js = pathlib.Path("license_server/web_static/play.js").read_text(encoding="utf-8")
    assert "btn.disabled = st.rolls_left <= 0" in js


def test_the_web_server_prepares_its_own_schema():
    """เว็บเขียน game_data.db ด้วย จึงต้องงอกคอลัมน์ใหม่เองได้
    เดิมมีแต่บอทที่ทำ — เพิ่มฟีเจอร์แล้วรีสตาร์ทแต่เว็บ ผู้เล่นเจอ 500 (เจอจริงตอนกระดาน)"""
    api = pathlib.Path("license_server/api.py").read_text(encoding="utf-8")
    block = api[api.index("def create_app():"):api.index("app = FastAPI(")]
    assert "player_model" in block and "init_db()" in block
