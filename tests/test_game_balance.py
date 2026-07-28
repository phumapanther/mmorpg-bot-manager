"""กลุ่ม A: ค่าสมดุลทั้งหมดต้องอ่านจาก Panel ได้ และไม่มีค่าไหนพังถ้า config ว่าง"""
import json

from bot import config_loader


def test_balance_reader_fallback(monkeypatch):
    monkeypatch.setattr(config_loader, "get_config", lambda: {})       # config ว่างเปล่า
    assert config_loader.get_balance("guild.create_cost", 999) == 999   # ใช้ค่า fallback
    assert config_loader.get_balance_role_id("king_role_id") is None
    assert config_loader.get_monster_rank("Common") == {}


def test_config_has_all_balance_keys():
    cfg = json.load(open("config.example.json", encoding="utf-8"))
    b = cfg["game_balance"]
    assert set(b["roles"]) == {"king_role_id", "guild_divider_role_id", "guild_leader_role_id"}
    for section, keys in {
        "guild": ["create_cost", "rename_cost"],
        "guild_war": ["duration_min", "idle_warn_sec", "idle_grace_sec", "fight_cooldown_sec", "points", "chances"],
        "pvp": ["min_level", "reward_exp_base", "sanity_loss_base", "jail_base_min", "fine_base"],
        "bounty": ["base", "per_deficit", "cap", "hunt_sanity_reward"],
        "bestiary": ["continent_reward", "star_reward", "complete_reward"],
        "faction_war": ["gold_mult", "exp_mult"],
        "drops": ["normal_chance", "rare_chance", "respawn_hp_percent"],
        "events": ["travel_chance", "calm_chance"],
        "cooldowns": ["play_sec", "profile_sec", "adv_sec", "shop_sec"],
    }.items():
        for k in keys:
            assert k in b[section], f"game_balance.{section}.{k} หาย"
    assert set(cfg["monster_ranks"]) == {"Common", "Mini-Boss", "Main-Boss", "Secret", "Unbeatable"}


def test_panel_values_actually_apply(monkeypatch):
    """เปลี่ยนค่าใน config แล้วเกมต้องใช้ค่าใหม่จริง"""
    import bot.game_modifiers as gm
    import bot.views.game_views as gv
    import bot.cogs.guild_war as gw

    fake = {"game_balance": {"bounty": {"base": 1, "per_deficit": 2, "cap": 5},
                             "guild_war": {"duration_min": 1, "fight_cooldown_sec": 99,
                                           "chances": {"soldier": 10}, "points": {"soldier": 7}}},
            "monster_ranks": {"Common": {"hp_min": 5, "hp_max": 6, "gold_mult": 42}}}
    monkeypatch.setattr(config_loader, "get_config", lambda: fake)

    assert gm.bounty_for(-1) == 3 and gm.bounty_for(-99) == 5      # base+per, ชนเพดาน
    assert gw.war_duration() == 60 and gw.fight_cooldown() == 99
    soldier = next(e for e in gw.encounters() if e[0] == "soldier")
    assert soldier[1] == 10 and soldier[2] == 7                     # โอกาส/แต้มจาก Panel
    common = gv._rank_stats("Common")
    assert common["hp_range"] == (5, 6) and common["gold_mult"] == 42
