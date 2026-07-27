"""บั๊กเฟส D: ร้านค้าปุ่มชนลิมิต 25 → เปลี่ยนเป็น Select ต้องโชว์ของครบ + ปุ่มกลับไม่หลุด"""
import discord

import bot.views.game_views as gv
from bot import config_loader


def test_buy_view_shows_all_items_and_back():
    v = gv.BuySelectView(user_id=1)
    selects = [c for c in v.children if isinstance(c, discord.ui.Select)]
    buttons = [c for c in v.children if isinstance(c, discord.ui.Button)]
    purchasable = [k for k, d in config_loader.get_all_items().items() if d.get("purchasable", True)]
    assert sum(len(s.options) for s in selects) == len(purchasable)   # ครบทุกชิ้น (ตอนนี้ 30)
    assert len(purchasable) > 25                                       # เคสที่เคยพังจริง
    assert len(buttons) == 1                                           # ปุ่มกลับอยู่
    assert len(v.children) <= 25


def test_sell_view_shows_all_unique_items_and_back(monkeypatch):
    all_ids = [k for k in config_loader.get_all_items()][:30]
    monkeypatch.setattr(gv.player_model, "get_player",
                        lambda uid: {"inventory": ",".join(all_ids), "cash": 0})
    v = gv.SellSelectView(user_id=1)
    selects = [c for c in v.children if isinstance(c, discord.ui.Select)]
    buttons = [c for c in v.children if isinstance(c, discord.ui.Button)]
    assert sum(len(s.options) for s in selects) == 30
    assert len(buttons) == 1
