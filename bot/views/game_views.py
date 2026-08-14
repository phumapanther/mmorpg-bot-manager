import discord
from discord.ui import View
import random
import bot.models.player_model as player_model
from bot.views.profile_embed import GAME_CLASSES
import traceback # เอาไว้ดูว่า Error บรรทัดไหน
import json
from bot import config_loader
from bot import game_modifiers
from bot import robbery
from bot import adventure_core
from bot.adventure_core import (_roll_amount,  # noqa: F401 — ย้ายไป core แล้ว
                                _holy_aura_chance, _rank_stats, _random_enemy_champion,
                                execute_special_outcome, resolve_instant_special,
                                EVENT_WEIGHTS, EVENT_LIST, event_weights,
                                DEFAULT_SPAWN_WEIGHTS, MONSTER_RANKS, spawn_weights_for)
from bot.views.fight_ui import (ELEMENT_COLORS, RANK_BADGES, build_fight_embed,  # noqa: F401 (B6)
                                build_respawn_embed, hp_bar)
from bot.event_images import event_image, monster_image, item_use_image, file_kwargs  # noqa: F401

# ==========================================================
# 🎮 INTERACTIVE VIEWS
# ==========================================================


def respawn_player(user_id):
    """💀 O3: ชุบชีวิตผู้เล่น — ตรรกะเดียวใช้ทุกเส้นทางตาย (ค่าธรรมเนียม/หน้าจอตรงกันเสมอ)
    คืน (embed, ข้อมูลสรุป) — ค่าธรรมเนียมตามเลเวลจาก Panel"""
    player = player_model.get_player(user_id)
    if not player:
        return None, None
    level = player.get("level", 0)
    max_hp = player.get("max_hp", 100)
    hp_pct = int(config_loader.get_balance("drops.respawn_hp_percent", 30))
    respawn_hp = max(1, int(max_hp * hp_pct / 100))
    tiers = config_loader.get_balance("death.respawn_fee_tiers",
                                      [[100, 10000], [90, 5000], [50, 2500], [20, 1000], [10, 500], [0, 0]])
    fee = next((int(f) for lv, f in tiers if level >= int(lv)), 0)
    new_cash = player.get("cash", 0) - fee
    lost_steps = player.get("dungeon_steps", 0)
    player_model.update_player_fields(user_id, {
        "hp": respawn_hp, "cash": new_cash,
        "current_state": "village", "last_event": "village", "dungeon_steps": 0})
    embed = build_respawn_embed(player, respawn_hp, max_hp, fee, new_cash, lost_steps, hp_pct)
    return embed, {"fee": fee, "hp": respawn_hp, "cash": new_cash}


TAIL_CONTINUE = "\n----------------------------------------\nคุณต้องการไปต่อหรือไม่?"


class MenuButton(discord.ui.Button):
    """🕹️ เมนูลัดเทียบเท่า !menu — แปะท้ายทุกหน้าอีเวนต์ ผู้เล่นไม่ต้องพิมพ์คำสั่ง"""
    def __init__(self):
        super().__init__(label="🕹️ เมนู", style=discord.ButtonStyle.secondary)

    async def callback(self, interaction: discord.Interaction):
        # import ในฟังก์ชันกันวงจร import (menu_view → player_commands → game_views)
        from bot.views.menu_view import GameMenuView
        await interaction.response.send_message("🕹️ **เมนูผู้เล่น**", view=GameMenuView(), ephemeral=True)


class ActionView(View):
    """ฐานของ view อีเวนต์เกมทุกตัว — สืบทอดแล้วได้ปุ่มเมนูลัดต่อท้ายอัตโนมัติ"""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.add_item(MenuButton())

    async def on_error(self, interaction: discord.Interaction, error: Exception, item: discord.ui.Item):
        """ปุ่มพังห้ามเงียบ — บอกผู้เล่นว่าเกิดอะไร แล้วพ่นสาเหตุลงคอนโซลให้ตามแก้ได้"""
        traceback.print_exception(type(error), error, error.__traceback__)
        msg = (f"⚠️ ปุ่ม **{getattr(item, 'label', '?')}** ขัดข้อง (`{type(error).__name__}`)\n"
               "รบกวนเรียกหน้าต่างใหม่ด้วย `!play` นะครับ")
        try:
            if interaction.response.is_done():
                await interaction.followup.send(msg, ephemeral=True)
            else:
                await interaction.response.send_message(msg, ephemeral=True)
        except Exception:
            pass

    async def on_timeout(self):
        """หน้าต่างหมดอายุต้องเห็นได้ — ปิดปุ่มพร้อมบอกเหตุผล ไม่ปล่อยให้กดแล้วเงียบ"""
        for child in self.children:
            child.disabled = True
        if getattr(self, "message", None):
            try:
                await self.message.edit(content="⏰ **หน้าต่างนี้หมดอายุแล้ว** — พิมพ์ `!play` เพื่อเรียกหน้าใหม่นะครับ",
                                        view=self)
            except Exception:
                pass


class MonsterEventView(ActionView):
    def __init__(self, user_id, member_roles, monster_rank=None, monster_hp=None, active_buffs=None, turn_count=1, monster_name=None, element=None, fight_statuses=None, infused=False, faction_war_side=None, fight_grace=None, monster_hp_max=None):
        super().__init__(timeout=60)
        self.user_id = user_id
        self.member_roles = member_roles
        self.active_buffs = active_buffs if active_buffs else {}
        self.turn_count = turn_count
        
        if monster_rank is None:
            # เกิดมอนใหม่ — ตรรกะอยู่ใน adventure_core (ใช้ร่วมกับหน้าไฟต์บนเว็บ)
            m = adventure_core.spawn_monster(user_id, member_roles)
            self.mods = game_modifiers.get_active_modifiers(player_model.get_player(user_id))
            self.monster_rank = m["rank"]
            self.m_stats = m["stats"]
            self.monster_hp = m["hp"]
            self.monster_hp_max = m["hp_max"]
            self.element = m["element"]
            self.element_data = game_modifiers.get_element_data(self.mods, self.element)
            self.statuses = m["statuses"]
            self.fight_grace = set(m["fight_grace"])
            self.infused = m["infused"]
            self.faction_war_side = m["faction_side"]

        else:
            self.monster_rank = monster_rank
            self.m_stats = _rank_stats(self.monster_rank)
            self.monster_hp = monster_hp
            player = player_model.get_player(user_id)
            self.mods = game_modifiers.get_active_modifiers(player)
            if monster_name:
                # รับชื่อธีมต่อจากเทิร์นก่อน ไม่สุ่มใหม่กลางไฟต์
                self.m_stats["name"] = monster_name
            # รับธาตุต่อจากเทิร์นก่อน (ไม่สุ่มใหม่) — ไม่มี = ไม่มีเอฟเฟกต์ธาตุ
            self.element = element
            self.element_data = game_modifiers.get_element_data(self.mods, self.element)
            # รับสแนปช็อตสถานะต่อจากเทิร์นก่อน (สถานะแบบ fight ถูก tick ไปแล้วตอนไฟต์เริ่ม)
            self.statuses = fight_statuses if fight_statuses is not None else game_modifiers.parse_statuses(player)
            self.infused = infused
            self.faction_war_side = faction_war_side  # ธงแชมเปี้ยนส่งต่อข้ามเทิร์น
            self.monster_hp_max = monster_hp_max or monster_hp
            self.fight_grace = set(fight_grace or ())
            self._resync_statuses(player)  # รักษา/บัฟระหว่างเทิร์น → สะท้อนทันที (รวมปลดล็อกปุ่มสกิลจาก EMP)

        # 🧬 P8: ชื่อยศที่มีผลจริง — เซิร์ฟหลักใช้ยศจริง / เซิร์ฟรองใช้ค่าจาก DB
        from bot import identity
        self.effective_roles = identity.effective_role_names(
            self.member_roles, player_model.get_player(self.user_id))

        self.player_class = "Unknown"
        for name in self.effective_roles:
            if name in GAME_CLASSES:
                self.player_class = name
                break

        # ⚔️ ธาตุประจำตัวผู้เล่นจากยศเผ่า (dual-race ได้หลายธาตุ)
        self.player_elements = game_modifiers.resolve_player_elements(self.effective_roles)

        self.add_skill_buttons()

    def _resync_statuses(self, player):
        """ซิงก์สแนปช็อตไฟต์กับ DB สด (บั๊กเฟส D #2-#3):
        - สถานะที่ถูก "รักษากลางไฟต์" (มีดตัดเถา/ครีมว่านเย็น/ชา/สายดิน/เทียน ฯลฯ) หลุดจากไฟต์ทันที
        - บัฟที่ "เพิ่งกดใช้กลางไฟต์" (ชิป EMP/น้ำมนต์/เต๋าถ่วง ฯลฯ) มีผลทันที
        - ยกเว้น fight_grace: สถานะที่หมดอายุด้วย tick ต้นไฟต์ ยังคุ้มครองจนจบไฟต์ตามดีไซน์เดิม"""
        fresh = game_modifiers.parse_statuses(player)
        grace = getattr(self, "fight_grace", set()) or set()
        synced = {k: v for k, v in self.statuses.items() if k in fresh or k in grace}
        for k, v in fresh.items():
            synced.setdefault(k, v)
        self.statuses = synced

    def add_skill_buttons(self):
        # ⚡ สถานะ EMP: ปิดปุ่มสกิลทั้งไฟต์ (เหลือปุ่มโจมตี/หนีปกติ)
        if game_modifiers.has_status_flag(self.statuses, "disable_skills"):
            return

        skills_map = {
            "Warrior": [("🛡️ Shield Bash", "skill_shield_bash"), ("⚔️ Heavy Strike", "skill_heavy_strike")],
            "Mage":    [("🔥 Fireball", "skill_fireball"),       ("❄️ Frostbolt", "skill_frostbolt")],
            "Rogue":   [("🗡️ Backstab", "skill_backstab"),       ("💨 Evasion", "skill_evasion")],
            "Cleric":  [("✨ Heal", "skill_heal"),               ("🛡️ Holy Aura", "skill_holy_aura")]
        }

        if self.player_class in skills_map:
            for label, custom_id in skills_map[self.player_class]:
                btn = discord.ui.Button(label=label, style=discord.ButtonStyle.primary, custom_id=custom_id, row=1)
                btn.callback = self.skill_callback 
                self.add_item(btn)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("❌ นี่ไม่ใช่การต่อสู้ของคุณ! พิมพ์ `!play` เพื่อเปิดบอร์ดตัวเองนะจ๊ะ", ephemeral=True)
            return False
        return True

    async def process_turn(self, interaction: discord.Interaction, skill_used=None):
        try:
            player = player_model.get_player(self.user_id)
            if not player:
                return await interaction.response.send_message("❌ ไม่พบข้อมูลตัวละครของคุณในระบบ!", ephemeral=True)

            # 🔄 ซิงก์สถานะกับ DB สดก่อนคำนวณเทิร์น — ไอเทมรักษา/บัฟที่กดใช้ระหว่างรอเทิร์นมีผลทันที
            self._resync_statuses(player)

            # 🎲 คำนวณทั้งเทิร์น — ตรรกะอยู่ใน adventure_core (ใช้ร่วมกับหน้าไฟต์บนเว็บ)
            _f = {"rank": self.monster_rank, "stats": self.m_stats, "hp": self.monster_hp,
                  "hp_max": self.monster_hp_max, "element": self.element,
                  "statuses": self.statuses, "fight_grace": list(self.fight_grace),
                  "infused": self.infused, "faction_side": self.faction_war_side,
                  "turn": self.turn_count, "buffs": self.active_buffs}
            t = adventure_core.fight_turn(self.user_id, _f, self.member_roles, skill_used)

            if t["outcome"] == "no_player":
                return await interaction.response.send_message(t["text"], ephemeral=True)

            # จบไฟต์ทันที: มอนธาตุแสงเผ่นหนี / Evasion สำเร็จ
            if t["outcome"] in ("monster_fled", "player_fled"):
                self.stop()
                _msg = t["text"] + TAIL_CONTINUE
                if not interaction.response.is_done():
                    return await interaction.response.edit_message(content=_msg, view=AdventureView(author_id=self.user_id))
                return await interaction.followup.edit_message(message_id=interaction.message.id,
                                                               content=_msg, view=AdventureView(author_id=self.user_id))

            player = t["player"]
            p_lvl = player.get("level", 1)
            self.monster_hp = t["monster_hp"]
            self.statuses = t["fight"]["statuses"]
            self.active_buffs = t["fight"]["buffs"]
            self.m_stats = t["fight"]["stats"]
            skill_log, combat_log = t["skill_log"], t["combat_log"]
            damage_line = t["damage_line"]
            db_updates = dict(t["db_updates"])
            player_roll, monster_roll = t["player_roll"], t["monster_roll"]
            roll_parts, mon_parts = t["player_parts"], t["monster_parts"]
            damage_to_monster, damage_to_player = t["damage_to_monster"], t["damage_to_player"]

            # =================================================================
            # 🏆 กรณี: ผู้เล่นชนะ (บอสตาย)
            # =================================================================
            if self.monster_hp <= 0:
                # 🏆 จ่ายรางวัล — ตรรกะอยู่ใน adventure_core (ใช้ร่วมกับหน้าไฟต์บนเว็บ)
                v = adventure_core.fight_victory(self.user_id, t["fight"], self.member_roles)
                reward, gained_exp = v["reward"], v["exp"]
                current_level, current_exp = v["level"], v["current_exp"]
                is_lv_up, rank_msg = v["level_up"], v["rank_msg"]
                dropped_item_msg, battle_end_log = v["drops"], v["battle_end_log"]
                combat_log += v["combat_log"]
                self.statuses = v["statuses"]
                next_view = AdventureView(author_id=self.user_id)

                # ยศแรงค์ให้ได้เฉพาะฝั่งดิส (เว็บให้ยศเองไม่ได้ — บอทจะซิงก์ให้ตอนเข้าเซิร์ฟ)
                if v["promoted_rank"]:
                    try:
                        guild, member = interaction.guild, interaction.user
                        if guild and isinstance(member, discord.Member):
                            role = discord.utils.get(guild.roles, name=f"นักผจญภัยแรงค์ {v['promoted_rank']}")
                            if role:
                                await member.add_roles(role)
                    except Exception as e:
                        print(f"⚠️ [RANK] ให้ยศแรงค์ใหม่ไม่สำเร็จ: {e}")

                # -----------------------------------------------------------------
                # 📩 จบการทำงาน (ส่งข้อความชนะแบบต้นฉบับ 100%)
                # -----------------------------------------------------------------
                try:
                    lv_up_msg = f"\n✨🎉 **LEVEL UP!! คุณเลเวลเพิ่มขึ้นเป็น Lv.{current_level}** พลังชีวิตสูงสุดเพิ่มขึ้น เลือดฟื้นฟูเต็มเปี่ยม! ✨🎉" if is_lv_up else ""
                    required_xp_display = (current_level ** 2) * 70
                    
                    # 🏅 B3/B4: หน้าชนะแบบ embed + แถบ EXP บอกความคืบหน้าเลเวล
                    exp_bar = hp_bar(current_exp, required_xp_display, 12)
                    left = max(0, required_xp_display - current_exp)
                    near = f"  *(อีก ~{max(1, round(left / max(1, gained_exp)))} ตัวเลเวลอัป)*" if gained_exp else ""
                    win_embed = discord.Embed(
                        title=f"🏅 โค่น {self.m_stats.get('name', 'มอนสเตอร์')} สำเร็จ!",
                        color=ELEMENT_COLORS.get(getattr(self, "element", None), 0x2ecc71),
                        description=f"💰 **+{reward:,}** ทอง   🔷 **+{gained_exp:,}** EXP")
                    win_embed.add_field(name="📊 ความคืบหน้าเลเวล",
                        value=f"`{exp_bar}` `{current_exp:,}/{required_xp_display:,}` XP{near}", inline=False)
                    _extra = f"{lv_up_msg}{rank_msg}{dropped_item_msg}{battle_end_log}".strip()
                    if _extra:
                        win_embed.add_field(name="✨ เพิ่มเติม", value=_extra[:1024], inline=False)
                    _log = f"{skill_log}{combat_log}".strip()
                    if _log:
                        win_embed.add_field(name="📜 เทิร์นสุดท้าย", value=_log[-1024:], inline=False)
                    final_content = None
                    
                    if not interaction.response.is_done():
                        await interaction.response.edit_message(content=None, embed=win_embed, view=next_view)
                    else:
                        await interaction.followup.edit_message(message_id=interaction.message.id, content=None, embed=win_embed, view=next_view)
                
                except discord.NotFound:
                    print("⚠️ [WARNING] สู้จบนานเกินไป Interaction หมดอายุ กำลังส่งเป็นข้อความธรรมดาแทน...")
                    try:
                        await interaction.channel.send(content=f"<@{self.user_id}> {final_content}", view=next_view)
                    except Exception as e:
                        print(f"❌ [ERROR] ไม่สามารถส่งข้อความแทนได้: {e}")
                except Exception as e:
                    print(f"❌ [ERROR] ไม่สามารถแก้ไขข้อความตอนจบได้: {e}")

            # =================================================================
            # 💀 กรณี: ผู้เล่นแพ้ (เลือดหมด)
            # =================================================================
            elif db_updates.get("hp", player.get("hp", 0)) <= 0:
                try:
                    db_updates["current_state"] = "dead"
                    player_model.update_player_fields(self.user_id, db_updates)
                    
                    fail_msg = f"{skill_log}{combat_log}💀 **คุณหมดสติลงกลางสนามรบเนื่องจากทนความโกรธของบอสไม่ไหว...**"
                    death_kw = {"attachments": [f]} if (f := event_image("death")) else {}
                    if not interaction.response.is_done():
                        await interaction.response.edit_message(content=fail_msg, view=RespawnView(self.user_id), **death_kw)
                    else:
                        await interaction.followup.edit_message(message_id=interaction.message.id, content=fail_msg, view=RespawnView(self.user_id), **death_kw)
                except Exception as e:
                    print(f"❌ [ERROR] การแจ้งเตือนความตายพัง: {e}")

            # =================================================================
            # 🔄 กรณี: ยังไม่มีใครตาย (ไปเทิร์นถัดไป)
            # =================================================================
            else:
                try:
                    player_model.update_player_fields(self.user_id, db_updates)
                    next_turn = self.turn_count + 1
                    
                    # 🖼️ B3: หน้าจอไฟต์แบบ embed — ข้อมูลครบเหมือนเดิม แต่จัดกลุ่มให้อ่านง่าย
                    fresh_player = player_model.get_player(self.user_id) or player
                    fight_embed = build_fight_embed(
                        self, fresh_player,
                        {"player": player_roll, "player_parts": roll_parts,
                         "monster": monster_roll, "monster_parts": mon_parts},
                        locals().get("damage_line"), f"{skill_log}{combat_log}", self.turn_count)
                    next_msg = None

                    # 🖼️ เทิร์นแรก: อัปโหลดภาพมอนแทนภาพเงาปริศนา (เทิร์นถัดไปไม่อัปซ้ำ — attachment เดิมค้างอยู่)
                    img_kwargs = {}
                    if self.turn_count == 1:
                        mon_f = monster_image(self.m_stats.get("name", ""), self.monster_rank)
                        if mon_f:
                            mon_f.filename = "monster.png"   # ให้ตรง attachment://monster.png ใน embed เสมอ
                            img_kwargs = {"attachments": [mon_f]}

                    if not interaction.response.is_done():
                        await interaction.response.edit_message(content=None, embed=fight_embed, view=MonsterEventView(self.user_id, self.member_roles, self.monster_rank, self.monster_hp, self.active_buffs, turn_count=next_turn, monster_name=self.m_stats.get("name"), element=self.element, fight_statuses=self.statuses, infused=getattr(self, "infused", False), faction_war_side=getattr(self, "faction_war_side", None), fight_grace=getattr(self, "fight_grace", None), monster_hp_max=getattr(self, "monster_hp_max", None)), **img_kwargs)
                    else:
                        await interaction.followup.edit_message(message_id=interaction.message.id, content=None, embed=fight_embed, view=MonsterEventView(self.user_id, self.member_roles, self.monster_rank, self.monster_hp, self.active_buffs, turn_count=next_turn, monster_name=self.m_stats.get("name"), element=self.element, fight_statuses=self.statuses, infused=getattr(self, "infused", False), faction_war_side=getattr(self, "faction_war_side", None), fight_grace=getattr(self, "fight_grace", None), monster_hp_max=getattr(self, "monster_hp_max", None)), **img_kwargs)
                except Exception as e:
                    print(f"❌ [ERROR] การไปเทิร์นถัดไปพัง: {e}")

        # 🚨 CATCH-ALL: ดักจับ Error ขั้นรุนแรง 🚨
        except Exception as global_e:
            print(f"💥 [CRITICAL ERROR] ฟังก์ชัน process_turn ล่มสลาย!: {global_e}")
            traceback.print_exc() 
            
            try:
                error_msg = f"❌ **เกิดข้อผิดพลาดร้ายแรงระหว่างการต่อสู้!**\nระบบขัดข้องชั่วคราว โปรดแคปจอแจ้งแอดมิน: `{str(global_e)}`"
                if not interaction.response.is_done():
                    await interaction.response.send_message(error_msg, ephemeral=True)
                else:
                    await interaction.followup.send(error_msg, ephemeral=True)
            except Exception: pass

    @discord.ui.button(label="⚔️ สู้ต่อ (ทอยเต๋าปกติ)", style=discord.ButtonStyle.danger, row=0)
    async def fight_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.process_turn(interaction)

    # 🌱 สถานะรากพันธนาการ (no_flee): บล็อกการหนีจนกว่าสถานะจะหมด — เช็คในตัว callback ด้านล่าง
    @discord.ui.button(label="🧪 ใช้ไอเทม", style=discord.ButtonStyle.success, row=0)
    async def quick_item(self, interaction: discord.Interaction, button: discord.ui.Button):
        """O2: กินยา/ใช้ของกลางไฟต์ได้เลย (เดิมต้องผ่านปุ่มเมนูก่อน = คลิกมากกว่า)"""
        from bot.views.menu_view import ItemUseView
        player = player_model.get_player(self.user_id)
        inv = player_model.load_inventory((player or {}).get("inventory", ""))
        if not inv:
            return await interaction.response.send_message("🎒 กระเป๋าว่างเปล่า ไม่มีของให้ใช้!", ephemeral=True)
        await interaction.response.send_message(
            "🧪 เลือกไอเทมที่จะใช้ *(ใช้แล้วกดสู้ต่อได้เลย ผลมีทันที)*:",
            view=ItemUseView(inv), ephemeral=True)

    @discord.ui.button(label="🏃 วิ่งหนี!", style=discord.ButtonStyle.secondary, row=0)
    async def flee(self, interaction: discord.Interaction, button: discord.ui.Button):
        # 🌱 สถานะรากพันธนาการ: หนีไม่ได้จนกว่าสถานะจะหมด
        # (บั๊กเฟส D #2: ซิงก์กับ DB สดก่อนเช็ค — ใช้ 🗡️ มีดตัดเถากลางไฟต์แล้วต้องหนีได้ทันที)
        player = player_model.get_player(self.user_id)
        if player:
            self._resync_statuses(player)
        if game_modifiers.has_status_flag(self.statuses, "no_flee"):
            root_turns = next((v for k, v in self.statuses.items()
                               if game_modifiers.STATUS_EFFECTS[k].get("no_flee")), "?")
            return await interaction.response.send_message(
                f"🌱 **รากไม้รัดขาแน่น!** (สถานะพันธนาการเหลือ `{root_turns}` ก้าว) คุณดิ้นเท่าไหร่ก็หนีไม่หลุด — "
                f"ใช้ 🗡️ มีดตัดเถาวัลย์/🌿 ยาถอนพิษ ผ่านปุ่ม 🕹️ เมนู แล้วกดหนีใหม่ได้ทันที!", ephemeral=True)

        flee_roll = random.randint(1, 100)
        
        # ถ้าหนีสำเร็จ
        if flee_roll <= self.m_stats["flee_chance"]:
            player_model.update_player_field(self.user_id, "current_state", "idle")
            await interaction.response.edit_message(content=f"💨 **หนีสำเร็จ!** สลัดหลุดจากมอนสเตอร์สำเร็จ!", view=AdventureView(author_id=self.user_id))
        
        # ถ้าหนีไม่สำเร็จ (โดนโจมตีสวน)
        else:
            player = player_model.get_player(self.user_id)
            damage = random.randint(15, 30)
            new_hp = max(0, player["hp"] - damage)
            
            # 🛡️ คำนวณความเสียหายของเกราะ (โดนตี = เกราะลด)
            if player.get("armor_dur", 0) > 0:
                damage_to_armor = max(1, int(damage / 10))
                new_armor_dur = max(0, player.get("armor_dur", 0) - damage_to_armor)
            else:
                # ถ้าเกราะพังอยู่แล้ว ก็ไม่ต้องลด และไม่ต้องแสดงค่าความเสื่อมสภาพ
                damage_to_armor = 0
                new_armor_dur = 0
            
            # อัปเดตข้อมูลทั้งหมดในรอบเดียว
            db_updates = {
                "hp": new_hp,
                "armor_dur": new_armor_dur,
                "current_state": "fighting"
            }
            
            if new_hp <= 0:
                db_updates["current_state"] = "dead"
                player_model.update_player_fields(self.user_id, db_updates)
                await interaction.response.edit_message(content="💥 หนีไม่พ้นและโดนตบตายคาที่!", view=RespawnView(self.user_id), **({"attachments": [f]} if (f := event_image("death")) else {}))
            else:
                player_model.update_player_fields(self.user_id, db_updates)
                next_turn = self.turn_count + 1
                msg = f"💥 หนีไม่พ้น! โดนสวนหลังฟาดกระอักเลือด `- {damage}`! (เกราะเสียหาย `- {damage_to_armor}`)"
                
                # เพิ่มข้อความแจ้งเตือนถ้าเกราะพัง
                if new_armor_dur == 0 and player.get("armor_dur", 0) > 0:
                    msg += "\n🚨 **ชุดเกราะของคุณพังยับเยิน!**"
                    
                await interaction.response.edit_message(content=msg, view=MonsterEventView(self.user_id, self.member_roles, self.monster_rank, self.monster_hp, self.active_buffs, turn_count=next_turn, monster_name=self.m_stats.get("name"), element=self.element, fight_statuses=self.statuses, infused=getattr(self, "infused", False), faction_war_side=getattr(self, "faction_war_side", None), fight_grace=getattr(self, "fight_grace", None), monster_hp_max=getattr(self, "monster_hp_max", None)))

    async def skill_callback(self, interaction: discord.Interaction):
        if not await self.interaction_check(interaction): return
        await self.process_turn(interaction, skill_used=interaction.data["custom_id"])

# 2. เหตุการณ์ หมู่บ้าน (Village)
class VillageEventView(ActionView):
    def __init__(self, user_id):
        super().__init__(timeout=600)   # หน้าหมู่บ้านเป็นหน้า "เดินดู" ไม่ใช่ไฟต์ — 60 วิสั้นไปจนปุ่มตายก่อนกด
        self.user_id = user_id

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("❌ คุณไม่ใช่เจ้าของแผงพักแรมนี้! พิมพ์ `!play` เพื่อสั่งงานบอร์ดตัวเองน้า", ephemeral=True)
            return False
        return True

    @discord.ui.button(label="🛏️ พักแรม", style=discord.ButtonStyle.primary)
    async def rest(self, interaction: discord.Interaction, button: discord.ui.Button):
        r = adventure_core.resolve_village(self.user_id, "rest")
        if r.get("error"):
            await interaction.response.send_message(r["error"], ephemeral=True)
            return
        await interaction.response.edit_message(
            content=f"{r['text']}\n----------------------------------------\nคุณต้องการไปต่อหรือไม่?",
            view=AdventureView(author_id=self.user_id))

    @discord.ui.button(label="🏪 ร้านค้าประจำ", style=discord.ButtonStyle.primary)
    async def shop(self, interaction: discord.Interaction, button: discord.ui.Button):
        # เปลี่ยนหน้าจาก Village ไปยัง Shop
        await interaction.response.edit_message(
            content="🏪 ยินดีต้อนรับสู่ร้านค้าประจำหมู่บ้าน! คุณต้องการซื้อหรือขายไอเทมอะไรดี?",
            view=ShopEventView(self.user_id) # เรียกใช้ View ร้านค้าที่ผมร่างให้ก่อนหน้านี้
        )

    @discord.ui.button(label="🏦 ธนาคาร", style=discord.ButtonStyle.secondary)
    async def village_bank(self, interaction: discord.Interaction, button: discord.ui.Button):
        """O7: จัดการเงินจากในหมู่บ้านได้เลย ไม่ต้องเดินไปห้องธนาคาร"""
        from bot.cogs.player_commands import build_bank_embed
        from bot.views.menu_view import BankActionView
        player = player_model.get_player(self.user_id)
        await interaction.response.send_message(embed=build_bank_embed(player),
                                                view=BankActionView(), ephemeral=True)

    @discord.ui.button(label="🪪 โปรไฟล์", style=discord.ButtonStyle.secondary)
    async def village_profile(self, interaction: discord.Interaction, button: discord.ui.Button):
        from bot.views.menu_view import ProfilePageView
        from bot.views.profile_embed import create_profile_embed
        player = player_model.get_player(self.user_id)
        await interaction.response.send_message(
            embed=create_profile_embed(interaction.user, player),
            view=ProfilePageView(interaction.user), ephemeral=True)

    @discord.ui.button(label="🚶 ออกเดินทางต่อ", style=discord.ButtonStyle.secondary)
    async def leave(self, interaction: discord.Interaction, button: discord.ui.Button):
        r = adventure_core.resolve_village(self.user_id, "leave")
        await interaction.response.edit_message(
            content=f"{r['text']}\n----------------------------------------\nคุณต้องการไปต่อหรือไม่?",
            view=AdventureView(author_id=self.user_id))


class DeathRespawnView(ActionView):
    def __init__(self, user_id):
        super().__init__(timeout=120) # ให้เวลาตัดสินใจ 2 นาที
        self.user_id = user_id
        self.message = None

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("❌ วิญญาณดวงนี้ไม่ใช่ของคุณ!", ephemeral=True)
            return False
        return True

    @discord.ui.button(label="🏥 กลับไปเกิดที่หมู่บ้าน (-1000 ทอง)", style=discord.ButtonStyle.danger)
    async def force_respawn(self, interaction: discord.Interaction, button: discord.ui.Button):
        # O3: ใช้ตรรกะ/หน้าจอเดียวกับการตายทางอื่น — เดิมคิดค่าคงที่ 1,000 และหน้าตาคนละแบบ
        embed, _info = respawn_player(self.user_id)
        if not embed:
            return await interaction.response.send_message("❌ ไม่พบข้อมูลตัวละคร!", ephemeral=True)
        await interaction.response.send_message(embed=embed, ephemeral=True, **file_kwargs(event_image("respawn")))
        await interaction.message.delete()
        
    async def on_timeout(self):
        for item in self.children:
            item.disabled = True
        if self.message:
            try:
                await self.message.edit(content="👻 วิญญาณของคุณยังคงล่องลอยอยู่... (หน้าต่างเกิดใหม่หมดอายุ)", view=self)
            except:
                pass

# ระบบร้านค้า      
class ShopEventView(ActionView):
    def __init__(self, user_id):
        super().__init__(timeout=600)   # เลือกของในร้านใช้เวลา — timeout สั้นทำให้กดซื้อไม่ติด
        self.user_id = user_id

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        return interaction.user.id == self.user_id

    # --- หน้าหลัก ---
    @discord.ui.button(label="💰 ซื้อไอเทม", style=discord.ButtonStyle.green)
    async def buy_menu(self, interaction: discord.Interaction, button: discord.ui.Button):
        ITEM_CONFIG = config_loader.get_all_items()
        # 🛠️ กรองแสดงเฉพาะของที่ตั้งค่า purchasable ไม่เท่ากับ False
        content = "🛒 เลือกไอเทมที่ต้องการซื้อ:\n" + "\n".join([f"**เลข {k}:** {v['name']} ({v['buy']} ทอง)" for k, v in ITEM_CONFIG.items() if v.get("purchasable", True)])
        await interaction.response.edit_message(content=content, view=BuySelectView(self.user_id))

    @discord.ui.button(label="📦 ขายไอเทม", style=discord.ButtonStyle.red)
    async def sell_menu(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.edit_message(content="เลือกไอเทมที่จะขาย:", view=SellSelectView(self.user_id))

    @discord.ui.button(label="⬅️ กลับไปหมู่บ้าน", style=discord.ButtonStyle.secondary)
    async def back(self, interaction: discord.Interaction, button: discord.ui.Button):
        village = VillageEventView(self.user_id)
        await interaction.response.edit_message(content="คุณเดินกลับไปยังจุดพักแรม...", view=village)
        village.message = interaction.message   # ให้ on_timeout เอาไว้ปิดปุ่มพร้อมบอกเหตุผลได้

# --- ระบบซื้อ ---
class BuyItemSelect(discord.ui.Select):
    """เมนูเลือกซื้อ (25 ชิ้น/อัน) — แก้บั๊กเฟส D: ปุ่มรายชิ้นชนลิมิต 25 ปุ่มของ Discord
    ทำให้ไอเทมเกิน (เลข 60+) กับปุ่มกลับหายจากหน้าร้าน"""
    def __init__(self, parent, items, page):
        options = [discord.SelectOption(label=f"เลข {iid} · {d['name']}"[:100],
                                        description=f"{d['buy']:,} ทอง", value=str(iid))
                   for iid, d in items]
        super().__init__(placeholder=f"🛒 เลือกซื้อไอเทม (ชุดที่ {page})...", options=options)
        self.parent_view = parent

    async def callback(self, interaction: discord.Interaction):
        await self.parent_view.buy_item(interaction, self.values[0])


class BuySelectView(View):
    def __init__(self, user_id):
        super().__init__(timeout=60)
        self.user_id = user_id
        ITEM_CONFIG = config_loader.get_all_items()

        try:
            purchasable = [(iid, d) for iid, d in ITEM_CONFIG.items() if d.get("purchasable", True)]
            # ponytail: Select 4 อัน (25 ชิ้น/อัน) + แถวปุ่มกลับ = เพดาน 100 ชิ้น — เกินค่อยทำแบ่งหน้า
            if len(purchasable) > 100:
                print(f"⚠️ [ร้านค้า] ของซื้อได้ {len(purchasable)} ชิ้น เกินเพดานแสดง 100 ชิ้นแรก")
            for page, i in enumerate(range(0, min(len(purchasable), 100), 25), start=1):
                self.add_item(BuyItemSelect(self, purchasable[i:i + 25], page))

            back_btn = discord.ui.Button(label="🔙 ย้อนกลับ", style=discord.ButtonStyle.secondary)
            back_btn.callback = self.back_callback
            self.add_item(back_btn)

        except Exception as e:
            print(f"ERROR: [ร้านค้า] โหลดหน้าซื้อล้มเหลว: {e}")

    # 🛒 ซื้อไอเทม — เรียกจาก BuyItemSelect
    async def buy_item(self, interaction: discord.Interaction, item_id):
        from bot.cogs.player_commands import buy_item_for
        await interaction.response.defer()

        ok, msg = buy_item_for(self.user_id, item_id)      # ตรรกะกลาง ใช้ร่วมกับหน้าร้านบนเว็บ
        if not ok:
            return await interaction.followup.send(msg, ephemeral=True)

        # รีเฟรชรายการในร้านให้เห็นเงินคงเหลือใหม่
        ITEM_CONFIG = config_loader.get_all_items()
        cash = player_model.get_player(self.user_id).get("cash", 0)
        market_list = [f"**เลข {k}:** {v['name']} ({v['buy']} ทอง)"
                       for k, v in ITEM_CONFIG.items() if v.get("purchasable", True)]
        content = f"🛒 เลือกไอเทมที่ต้องการซื้อ: (เงินคงเหลือ: {cash:,} ทอง)\n\n" + "\n".join(market_list)
        await interaction.edit_original_response(content=content, view=self)
        await interaction.followup.send(msg, ephemeral=True)

    async def back_callback(self, interaction: discord.Interaction):
        await interaction.response.edit_message(view=ShopEventView(self.user_id))

# --- ระบบขาย ---
class SellItemSelect(discord.ui.Select):
    """เมนูเลือกขาย (25 ชนิด/อัน) — คู่แฝดของ BuyItemSelect"""
    def __init__(self, parent, items, page):
        options = [discord.SelectOption(label=f"{d['name']} x{count}"[:100],
                                        description=f"ขายได้ {d.get('sell', 0):,} ทอง/ชิ้น", value=str(iid))
                   for iid, d, count in items]
        super().__init__(placeholder=f"📦 เลือกขายไอเทม (ชุดที่ {page})...", options=options)
        self.parent_view = parent

    async def callback(self, interaction: discord.Interaction):
        await self.parent_view.sell_item(interaction, self.values[0])


class SellSelectView(View):
    def __init__(self, user_id):
        super().__init__(timeout=None)
        self.user_id = user_id
        player = player_model.get_player(user_id)
        ITEM_CONFIG = config_loader.get_all_items()

        try:
            # 🛠️ ระบบกรองทำความสะอาดข้อมูลกระเป๋า
            raw_inv = player.get("inventory", "")
            clean_inv = str(raw_inv)
            for char in ["(", ")", "[", "]", "'", '"', " "]:
                clean_inv = clean_inv.replace(char, "")
                
            inv = clean_inv.split(",") if clean_inv and clean_inv not in ["None", "null"] else []
            
            # 🛠️ Select แทนปุ่มรายชิ้น (แก้บั๊กเฟส D: ของเกิน 24 ชนิด ปุ่ม+ปุ่มกลับหลุดลิมิต 25)
            unique_items = sorted({i for i in inv if i in ITEM_CONFIG}, key=lambda x: int(x) if x.isdigit() else 0)
            sellable = [(iid, ITEM_CONFIG[iid], inv.count(iid)) for iid in unique_items]
            if len(sellable) > 100:
                print(f"⚠️ [ร้านค้า] ของขายได้ {len(sellable)} ชนิด เกินเพดานแสดง 100 ชนิดแรก")
            for page, i in enumerate(range(0, min(len(sellable), 100), 25), start=1):
                self.add_item(SellItemSelect(self, sellable[i:i + 25], page))

            back_btn = discord.ui.Button(label="🔙 ย้อนกลับ", style=discord.ButtonStyle.secondary)
            back_btn.callback = self.back_callback
            self.add_item(back_btn)

        except Exception as e:
            print(f"ERROR: [ร้านค้า] โหลดหน้าขายล้มเหลว: {e}")

    # 💰 ขายไอเทม — เรียกจาก SellItemSelect
    async def sell_item(self, interaction: discord.Interaction, item_id):
        from bot.cogs.player_commands import sell_item_for
        await interaction.response.defer()

        ok, msg = sell_item_for(self.user_id, item_id)     # ตรรกะกลาง ใช้ร่วมกับหน้าร้านบนเว็บ
        if not ok:
            return await interaction.followup.send(msg, ephemeral=True)

        cash = player_model.get_player(self.user_id).get("cash", 0)
        content = f"📦 เลือกไอเทมที่จะขาย: (เงินคงเหลือ: {cash:,} ทอง)"
        await interaction.edit_original_response(content=content, view=SellSelectView(self.user_id))
        await interaction.followup.send(msg, ephemeral=True)
            
    async def back_callback(self, interaction: discord.Interaction):
        await interaction.response.edit_message(view=ShopEventView(self.user_id))
        
# 3. เหตุการณ์ กล่องสมบัติ (Treasure)
class TreasureEventView(ActionView):
    def __init__(self, user_id):
        super().__init__(timeout=60)
        self.user_id = user_id

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("❌ หีบสมบัตินี้ถูกค้นพบโดยคนอื่น! พิมพ์ `!play` เพื่อออกล่าหีบของตัวเองครับ", ephemeral=True)
            return False
        return True

    @discord.ui.button(label="📦 เปิดกล่องสมบัติ", style=discord.ButtonStyle.success)
    async def open_box(self, interaction: discord.Interaction, button: discord.ui.Button):
        is_rogue = any(role.name == "Rogue" for role in interaction.user.roles)
        r = adventure_core.resolve_treasure(self.user_id, "open", is_rogue)
        await interaction.response.edit_message(
            content=f"{r['text']}\n----------------------------------------\nคุณต้องการไปต่อหรือไม่?",
            view=AdventureView(author_id=self.user_id))

    @discord.ui.button(label="❌ เมินเฉยและเดินผ่าน", style=discord.ButtonStyle.secondary)
    async def ignore(self, interaction: discord.Interaction, button: discord.ui.Button):
        r = adventure_core.resolve_treasure(self.user_id, "ignore")
        await interaction.response.edit_message(
            content=f"{r['text']}\n----------------------------------------\nคุณต้องการไปต่อหรือไม่?",
            view=AdventureView(author_id=self.user_id))


class QuestConfirmView(ActionView):
    def __init__(self, user_id, requested_items, reward_item_id, reward_cash):
        super().__init__(timeout=60)
        self.user_id = user_id
        self.requested_items = requested_items # List ของไอเทมที่ NPC อยากได้
        self.reward_item_id = reward_item_id   # ไอเทมที่จะให้เป็นรางวัล (ถ้ามี)
        self.reward_cash = reward_cash         # เงินที่จะให้เป็นรางวัล

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("❌ ไม่ใช่ข้อเสนอของคุณ!", ephemeral=True)
            return False
        return True

    def _offer(self):
        return {"requested": self.requested_items, "reward_item": self.reward_item_id,
                "reward_cash": self.reward_cash}

    @discord.ui.button(label="✅ แลกเปลี่ยน", style=discord.ButtonStyle.success)
    async def accept(self, interaction: discord.Interaction, button: discord.ui.Button):
        r = adventure_core.npc_quest_settle(self.user_id, self._offer(), True)
        await interaction.response.edit_message(
            content=f"{r['text']}\n----------------------------------------\nคุณต้องการไปต่อหรือไม่?",
            view=AdventureView(author_id=self.user_id))

    @discord.ui.button(label="❌ ปฏิเสธ", style=discord.ButtonStyle.danger)
    async def decline(self, interaction: discord.Interaction, button: discord.ui.Button):
        r = adventure_core.npc_quest_settle(self.user_id, self._offer(), False)
        await interaction.response.edit_message(
            content=f"{r['text']}\n----------------------------------------\nคุณต้องการไปต่อหรือไม่?",
            view=AdventureView(author_id=self.user_id))


# 4. เหตุการณ์ เควส NPC
class NpcEventView(ActionView):
    def __init__(self, user_id):
        super().__init__(timeout=60)
        self.user_id = user_id

        # 🎭 Masquerade (ธีมสัปดาห์): NPC ตัวนี้อาจเป็นมอนสเตอร์ปลอมตัว — ตัดสินตอนเจอ ผู้เล่นไม่รู้
        self.masq_cfg, self.disguised = adventure_core.npc_disguise(
            player_model.get_player(user_id))
        if self.masq_cfg:
            fee = self.masq_cfg.get("inspect_fee", 1500)
            inspect_btn = discord.ui.Button(label=f"🔍 ตรวจสอบตัวตน (จ่าย {fee:,} ทอง)", style=discord.ButtonStyle.danger)
            inspect_btn.callback = self.inspect
            self.add_item(inspect_btn)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("❌ NPC กำลังสนทนากับนักผจญภัยท่านอื่นอยู่ รบกวนพิมพ์ `!play` แยกน้า", ephemeral=True)
            return False
        return True

    async def _masquerade_ambush(self, interaction: discord.Interaction):
        """🎭 มอนปลอมตัวจู่โจมคนที่ไม่ทันระวัง — ดาเมจเปิดฉากแล้วเข้าไฟต์"""
        dmg = random.randint(10, 20)
        player = player_model.get_player(self.user_id)
        new_hp = max(0, player.get("hp", 100) - dmg)
        if new_hp <= 0:
            player_model.update_player_fields(self.user_id, {"hp": 0, "current_state": "dead"})
            return await interaction.response.edit_message(
                content=f"🎭 **'NPC' ฉีกคราบออก — มันคือมอนสเตอร์ปลอมตัวมา!** จู่โจมจากระยะประชิด `-{dmg}` HP... คุณหมดสติ!",
                view=RespawnView(self.user_id), **({"attachments": [f]} if (f := event_image("death")) else {}))
        player_model.update_player_fields(self.user_id, {"hp": new_hp, "current_state": "fighting"})
        next_view = MonsterEventView(self.user_id, interaction.user.roles)
        await interaction.response.edit_message(
            content=(
                f"🎭 **'NPC' ฉีกคราบออก — มันคือมอนสเตอร์ปลอมตัวมา!**\n"
                f"💥 โดนจู่โจมเปิดฉาก `-{dmg}` HP (เหลือ {new_hp}) — เข้าสู่การต่อสู้ทั้งแบบนั้น!"
            ),
            view=next_view)

    async def inspect(self, interaction: discord.Interaction):
        """🔍 ตรวจตัวตน — มีแว่นส่องสัจจะ (id 38) ใช้แว่นฟรี ไม่มีก็จ่ายเงิน"""
        player = player_model.get_player(self.user_id)
        fee = self.masq_cfg.get("inspect_fee", 1500)

        inv = player_model.load_inventory(player.get("inventory", "[]"))
        if game_modifiers.has_status_flag(game_modifiers.parse_statuses(player), "free_inspect"):
            # 🎭 แว่นเดี่ยวหน้ากาก (อาร์ติแฟกต์): มองทะลุการอำพรางฟรีตลอดกาล
            paid_note = "🎭 แว่นเดี่ยวหน้ากากของคุณเรืองแสง มองทะลุทุกการอำพราง (ฟรี — พลังถาวร)"
        elif "38" in inv:
            inv.remove("38")
            player_model.update_player_field(self.user_id, "inventory", inv)
            paid_note = "🔍 คุณยกแว่นส่องสัจจะขึ้นส่องทะลุหน้ากาก... (ไม่เสียเงิน — เลนส์แตกสลายหลังใช้)"
        elif player.get("cash", 0) < fee:
            return await interaction.response.send_message(f"❌ เงินสดไม่พอค่าตรวจสอบ (`{fee:,}` ทอง) — หรือหาซื้อ 🔍 แว่นส่องสัจจะติดกระเป๋าไว้", ephemeral=True)
        else:
            player_model.update_player_field(self.user_id, "cash", player["cash"] - fee)
            paid_note = f"🔍 คุณจ่าย `{fee:,}` ทองให้ผู้เชี่ยวชาญส่องหน้ากาก..."

        if self.disguised:
            player_model.update_player_field(self.user_id, "current_state", "fighting")
            next_view = MonsterEventView(self.user_id, interaction.user.roles)
            await interaction.response.edit_message(
                content=(
                    f"{paid_note}\n"
                    f"🎭 **จับได้! มันคือมอนสเตอร์ปลอมตัวมา!** มันจนมุมก่อนได้ลงมือ — คุณเข้าปะทะแบบไม่เสียเปรียบ!"
                ),
                view=next_view)
        else:
            self.remove_item(next(c for c in self.children if getattr(c, "label", "").startswith("🔍")))
            await interaction.response.edit_message(
                content=f"{paid_note}\nผลออกมา: **เป็น NPC ตัวจริง!** คุยต่อได้ตามปกติ 🧓",
                view=self)

    # ==========================================
    # ปุ่ม 1: พูดคุยปกติ (สุ่มให้เงิน / ขายของ / ไม่มีอะไร)
    # ==========================================
    @discord.ui.button(label="💬 เข้าไปพูดคุย", style=discord.ButtonStyle.primary)
    async def talk(self, interaction: discord.Interaction, button: discord.ui.Button):
        # 🎭 เข้าไปคุยกับตัวปลอมโดยไม่ตรวจสอบ = โดนซุ่มทำร้าย
        if self.disguised:
            return await self._masquerade_ambush(interaction)

        r = adventure_core.npc_talk(self.user_id)
        await interaction.response.edit_message(
            content=f"{r['text']}\n----------------------------------------\nคุณต้องการไปต่อหรือไม่?",
            view=AdventureView(author_id=self.user_id))

    # ==========================================
    # ปุ่ม 2: รับเควสแลกเปลี่ยน (Gacha Exchange)
    # ==========================================
    @discord.ui.button(label="📜 ฟังข้อเสนอเควส", style=discord.ButtonStyle.success)
    async def quest_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        # 🎭 เข้าไปฟังเควสจากตัวปลอมโดยไม่ตรวจสอบ = โดนซุ่มทำร้าย
        if self.disguised:
            return await self._masquerade_ambush(interaction)

        offer = adventure_core.npc_quest_offer(self.user_id)
        if not offer:
            return await interaction.response.edit_message(
                content="🧓 NPC มองกระเป๋าที่ว่างเปล่าของคุณแล้วส่ายหัว \'เจ้าไม่มีสิ่งใดที่ข้าต้องการเลย...\' "
                        + "\n----------------------------------------\nคุณต้องการไปต่อหรือไม่?",
                view=AdventureView(author_id=self.user_id))

        await interaction.response.edit_message(
            content=offer["text"],
            view=QuestConfirmView(self.user_id, offer["requested"],
                                  offer["reward_item"], offer["reward_cash"]))

    # ==========================================
    # ปุ่ม 3: เมินใส่
    # ==========================================
    @discord.ui.button(label="🤫 เมินใส่", style=discord.ButtonStyle.secondary)
    async def ignore(self, interaction: discord.Interaction, button: discord.ui.Button):
        player_model.update_player_fields(self.user_id, {"current_state": "idle", "last_event": "npc"})
        await interaction.response.edit_message(
            content="🤫 คุณแกล้งทำเป็นมองไม่เห็นและเดินผ่าน NPC ไปอย่างรวดเร็ว\n----------------------------------------\nคุณต้องการไปต่อหรือไม่?", 
            view=AdventureView(author_id=self.user_id)
        )


# 5. เหตุการณ์ ดันเจี้ยน (Dungeon)
class DungeonEventView(ActionView):
    def __init__(self, user_id):
        super().__init__(timeout=60)
        self.user_id = user_id

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("❌ นี่คือทางเข้าดันเจี้ยนของนักผจญภัยเจ้าของคำสั่งเท่านั้นครับ!", ephemeral=True)
            return False
        return True

    @discord.ui.button(label="🚪 บุกเข้าดันเจี้ยน", style=discord.ButtonStyle.danger)
    async def enter(self, interaction: discord.Interaction, button: discord.ui.Button):
        r = adventure_core.resolve_dungeon(self.user_id, "enter")
        await interaction.response.edit_message(
            content=f"{r['text']}\n----------------------------------------\nคุณต้องการเริ่มสำรวจ (ไปต่อ) หรือไม่?",
            view=AdventureView(author_id=self.user_id))

    @discord.ui.button(label="🏃 ไม่เข้าดีกว่า", style=discord.ButtonStyle.secondary)
    async def leave(self, interaction: discord.Interaction, button: discord.ui.Button):
        r = adventure_core.resolve_dungeon(self.user_id, "leave")
        await interaction.response.edit_message(
            content=f"{r['text']}\n----------------------------------------\nคุณต้องการไปต่อหรือไม่?",
            view=AdventureView(author_id=self.user_id))


# 6. เหตุการณ์ กับดัก (Trap)
class MuggingEventView(ActionView):
    """🥷 โดนดักปล้น (spec 2026-08-06) — สู้ทอยรอบเดียว หรือหนีเสียเงินติดตัวครึ่ง | หมดเวลา = นับเป็นหนี"""

    def __init__(self, user_id):
        super().__init__(timeout=60)
        self.user_id = user_id
        self.resolved = False

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("❌ โจรล็อคเป้าคนอื่นอยู่ อย่าแย่งกันโดนปล้น!", ephemeral=True)
            return False
        return True

    def _flee(self):
        """เสียเงินติดตัว 50% + ทอยโดนฉกของ — ใช้ร่วมกันทั้งปุ่มหนีและตอนหมดเวลา คืน (เสียไป, เหลือ, โน้ตของหาย)"""
        r = robbery.resolve_mugging(self.user_id, "flee")
        return r["lost"], r["cash"], r["theft"]

    async def on_timeout(self):
        if self.resolved:
            return
        lost, left, theft_note = self._flee()
        for item in self.children:
            item.disabled = True
        try:
            await self.message.edit(
                content=f"⏳ คุณยืนตัวแข็งตัดสินใจไม่ทัน... โจรฉกถุงทองไป `{lost:,}` ทอง! (เหลือ `{left:,}`){theft_note}", view=self)
        except Exception as e:
            print(f"[ERROR] [MUGGING] แก้ข้อความตอนหมดเวลาไม่ได้: {e}")

    @discord.ui.button(label="⚔️ สู้", style=discord.ButtonStyle.danger)
    async def fight(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        self.resolved = True
        self.stop()
        r = robbery.resolve_mugging(self.user_id, "fight")
        if r["won"]:
            msg = (f"⚔️🏆 **คุณสู้จนโจรเผ่นหนี!** ริบของกลางจากโจรได้ `{r['gain']:,}` ทอง "
                   f"(ติดตัวตอนนี้ `{r['cash']:,}`)")
        else:
            msg = f"⚔️💀 **เงินถ่วงแข้งขาจนสู้ไม่ไหว...** โจรกวาดเงินติดตัวไปหมด `{r['lost']:,}` ทอง!"
        msg += r["theft"]
        await interaction.edit_original_response(
            content=f"{msg}\n----------------------------------------\nคุณต้องการไปต่อหรือไม่?",
            view=AdventureView(author_id=self.user_id))

    @discord.ui.button(label="🏃 หนี (-50% เงินติดตัว)", style=discord.ButtonStyle.secondary)
    async def flee(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        self.resolved = True
        self.stop()
        lost, left, theft_note = self._flee()
        await interaction.edit_original_response(
            content=f"🏃💨 คุณโยนถุงทองสกัดโจรแล้ววิ่งสุดชีวิต — เสีย `{lost:,}` ทอง (เหลือ `{left:,}`){theft_note}\n"
                    f"----------------------------------------\nคุณต้องการไปต่อหรือไม่?",
            view=AdventureView(author_id=self.user_id))


class TrapEventView(ActionView):
    def __init__(self, user_id, member_roles):
        super().__init__(timeout=60)
        self.user_id = user_id
        self.member_roles = member_roles

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("❌ กับดักนี้ดีดใส่ตัวละครอื่นอยู่! ตัวเองรอดแล้วอย่ามากดแทนเพื่อนน้าา", ephemeral=True)
            return False
        return True

    @discord.ui.button(label="🎲 ทอยเต๋าหลบกับดัก", style=discord.ButtonStyle.primary)
    async def dodge(self, interaction: discord.Interaction, button: discord.ui.Button):
        # 1. แจ้ง Discord ว่าบอทได้รับคำสั่งแล้วทันที (กัน Interaction ล้มเหลว)
        await interaction.response.defer()

        if not player_model.get_player(self.user_id):
            await interaction.followup.send("❌ ไม่พบข้อมูลตัวละครของคุณ!", ephemeral=True)
            return

        is_rogue = any(role.name == "Rogue" for role in self.member_roles)
        r = adventure_core.resolve_trap(self.user_id, is_rogue)
        await interaction.edit_original_response(
            content=f"{r['text']}\n----------------------------------------\nคุณต้องการไปต่อหรือไม่?",
            view=AdventureView(author_id=self.user_id))


# 🏥 VIEW พิเศษ: ฟื้นคืนชีพเมื่อผู้เล่นหมดสติ (Respawn System)
class RespawnView(ActionView):
    def __init__(self, user_id):
        super().__init__(timeout=60)
        self.user_id = user_id

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("❌ วิญญาณนี้ไม่ใช่ของคุณ! ปล่อยให้เจ้าตัวเขากดฟื้นตัวเองนะครับ", ephemeral=True)
            return False
        return True

    @discord.ui.button(label="🏥 ฟื้นตัวและกลับหมู่บ้าน", style=discord.ButtonStyle.green)
    async def respawn(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed, _info = respawn_player(self.user_id)
        if not embed:
            return await interaction.response.send_message("❌ ไม่พบข้อมูลตัวละคร!", ephemeral=True)
        village = VillageEventView(self.user_id)
        await interaction.response.edit_message(content=None, embed=embed, view=village, **({"attachments": [f]} if (f := event_image("respawn")) else {}))
        village.message = interaction.message


# 🧭 VIEW หลักในการเริ่มเดินทาง (!play)
class SpecialEventView(ActionView):
    """View กลางของอีเวนต์พิเศษ — render ปุ่มจาก data (dice_check/choice; ส่วน instant จ่ายผลตรงไม่ผ่าน View)"""

    def __init__(self, user_id, event):
        super().__init__(timeout=60)
        self.user_id = user_id
        self.event = event
        self.message = None

        if event.get("template") == "dice_check":
            btn = discord.ui.Button(label="🎲 ทอยเต๋าวัดดวง", style=discord.ButtonStyle.primary)
            btn.callback = self.roll_dice
            self.add_item(btn)
        elif event.get("template") == "choice":
            for idx, choice in enumerate(event.get("choices", [])):
                btn = discord.ui.Button(
                    label=choice["label"],
                    style=discord.ButtonStyle.primary if idx == 0 else discord.ButtonStyle.secondary,
                )
                btn.callback = self._make_choice_callback(choice)
                self.add_item(btn)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("❌ นี่ไม่ใช่เหตุการณ์ของคุณ! พิมพ์ `!play` เพื่อเปิดบอร์ดตัวเองนะจ๊ะ", ephemeral=True)
            return False
        return True

    async def on_timeout(self):
        player_model.update_player_field(self.user_id, "current_state", "idle")
        if self.message:
            try:
                await self.message.edit(content="⏳ คุณยืนลังเลนานเกินไป... เหตุการณ์ตรงหน้าผ่านพ้นไปแล้ว (พิมพ์ `!play` เพื่อเดินทางต่อ)", view=None)
            except Exception:
                pass

    def _make_choice_callback(self, choice):
        async def _callback(interaction: discord.Interaction):
            await self._finish(interaction, choice.get("outcome", {}), prefix=None)
        return _callback

    async def roll_dice(self, interaction: discord.Interaction):
        outcome, prefix = adventure_core.special_pick_outcome(self.event, None)
        await self._finish(interaction, outcome, prefix)

    async def _finish(self, interaction: discord.Interaction, outcome, prefix):
        self.stop()
        lines, died = execute_special_outcome(self.user_id, outcome)
        if prefix:
            lines = [prefix] + lines
        body = "\n".join(lines) if lines else "…ไม่มีอะไรเกิดขึ้น"
        if died:
            await interaction.response.edit_message(content=body, view=RespawnView(self.user_id), **({"attachments": [f]} if (f := event_image("death")) else {}))
        elif outcome.get("start_fight"):
            # ⚔️ เหตุการณ์ลากเข้าสู่การต่อสู้ทันที (เช่น โดนซุ่มโจมตี)
            player_model.update_player_field(self.user_id, "current_state", "fighting")
            next_view = MonsterEventView(self.user_id, interaction.user.roles)
            await interaction.response.edit_message(
                content=f"{body}\n👹 **ศัตรูไม่ให้เวลาคุณหายใจ — เข้าสู่การต่อสู้ทันที!**",
                view=next_view)
        else:
            await interaction.response.edit_message(
                content=f"{body}\n----------------------------------------\nคุณต้องการไปต่อหรือไม่?",
                view=AdventureView(author_id=self.user_id))


# 🎨 สีย้อมโปรไฟล์ (ผงสีรุ้ง) — "rainbow" = สุ่มสีทั้งสเปกตรัม
DYE_COLORS = [
    ("❤️ แดงเดือด", 0xE74C3C),
    ("💙 ฟ้าใส", 0x3498DB),
    ("💛 ทองอร่าม", 0xF1C40F),
    ("💜 ม่วงลึกลับ", 0x9B59B6),
    ("💚 เขียวมรกต", 0x2ECC71),
    ("🩷 ชมพูหวาน", 0xFF6FB5),
    ("🤍 ขาวบริสุทธิ์", 0xECF0F1),
    ("🌈 สุ่มสีรุ้ง (วัดดวง)", "rainbow"),
]


class ArtifactRemoveSelect(discord.ui.Select):
    """เลือกอาร์ติแฟกต์ที่จะถอด — ถอดแล้วของกลับเข้ากระเป๋า ไม่ได้หายไปไหน"""
    def __init__(self, worn):
        super().__init__(placeholder="เลือกอาร์ติแฟกต์ที่จะถอด...", options=[
            discord.SelectOption(label=game_modifiers.STATUS_EFFECTS[k]["label"][:100], value=k)
            for k in worn[:25]])

    async def callback(self, interaction: discord.Interaction):
        view: "ArtifactRemoveView" = self.view
        art_key = self.values[0]
        player = player_model.get_player(view.user_id)
        if not player:
            return await interaction.response.edit_message(content="❌ ไม่พบข้อมูลตัวละคร!", view=None)

        inv = player_model.load_inventory(player.get("inventory", ""))
        if view.item_id not in inv:
            return await interaction.response.edit_message(
                content="❌ ชุดถอดอาร์ติแฟกต์ไม่อยู่ในกระเป๋าแล้ว!", view=None)

        statuses = game_modifiers.parse_statuses(player)
        if art_key not in statuses:
            return await interaction.response.edit_message(
                content="❌ คุณไม่ได้สวมอาร์ติแฟกต์ชิ้นนี้อยู่แล้ว (ชุดถอดยังอยู่ในกระเป๋า)", view=None)

        # หาไอเทมต้นทางของอาร์ติแฟกต์ เพื่อคืนกลับเข้ากระเป๋า
        back_id = next((iid for iid, it in config_loader.get_all_items().items()
                        if it.get("effect") == "equip_artifact"
                        and str(it.get("effect_value")) == art_key), None)
        statuses.pop(art_key, None)
        inv.remove(view.item_id)                 # ชุดถอดถูกใช้ไป
        if back_id:
            inv.append(back_id)
        player_model.update_player_fields(view.user_id, {
            "status_effects": json.dumps(statuses),
            "inventory": json.dumps(inv),
        })
        label = game_modifiers.STATUS_EFFECTS[art_key]["label"]
        back_note = (f"\n🎒 **{config_loader.get_item_config(back_id).get('name', label)}** กลับเข้ากระเป๋าแล้ว "
                     "— เอาไปใส่ใหม่ ขาย หรือส่งต่อได้" if back_id else "")
        left = len(game_modifiers.worn_artifacts(statuses))
        slots = game_modifiers.artifact_slots(player)
        await interaction.response.edit_message(
            content=f"🔧 **ถอด {label} ออกเรียบร้อย!** (เหลือใช้ {left}/{slots} ช่อง){back_note}",
            view=None)


class ArtifactRemoveView(View):
    """🔧 ชุดถอดอาร์ติแฟกต์ — ของถูกหักตอนเลือกเท่านั้น (หมดเวลา/เปลี่ยนใจ = ของอยู่ครบ)"""
    def __init__(self, user_id, item_id, worn):
        super().__init__(timeout=60)
        self.user_id = user_id
        self.item_id = str(item_id)
        self.message = None
        self.add_item(ArtifactRemoveSelect(worn))

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("❌ นี่ไม่ใช่ของคุณ!", ephemeral=True)
            return False
        return True


class ProfileDyeView(View):
    """🎨 เมนูย้อมสีโปรไฟล์ — ผงสีถูกหักตอนยืนยันสีเท่านั้น (หมดเวลา/เปลี่ยนใจ = ผงอยู่ครบ)"""

    def __init__(self, user_id, item_id):
        super().__init__(timeout=60)
        self.user_id = user_id
        self.item_id = str(item_id)
        self.message = None

        select = discord.ui.Select(placeholder="🎨 เลือกสีที่จะย้อมโปรไฟล์...")
        for idx, (label, _color) in enumerate(DYE_COLORS):
            select.add_option(label=label, value=str(idx))
        select.callback = self.pick
        self.add_item(select)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("❌ นี่ไม่ใช่ผงสีของคุณ!", ephemeral=True)
            return False
        return True

    async def on_timeout(self):
        if self.message:
            try:
                await self.message.edit(content="⏳ ผงสีถูกเก็บกลับเข้ากระเป๋า... (ยังไม่ถูกใช้ ใช้ใหม่ได้)", view=None)
            except Exception:
                pass

    async def pick(self, interaction: discord.Interaction):
        label, color = DYE_COLORS[int(interaction.data["values"][0])]
        if color == "rainbow":
            color = random.randint(0, 0xFFFFFF)

        player = player_model.get_player(self.user_id)
        inv = player_model.load_inventory(player.get("inventory", "[]"))
        if self.item_id not in inv:
            self.stop()
            return await interaction.response.edit_message(content="❌ ผงสีไม่อยู่ในกระเป๋าแล้ว!", view=None)

        inv.remove(self.item_id)
        player_model.update_player_fields(self.user_id, {"inventory": inv, "profile_color": color})
        self.stop()

        embed = discord.Embed(
            title="🎨 ย้อมสีสำเร็จ!",
            description=f"โปรไฟล์ของคุณเปล่งประกายสีใหม่: **{label}** (`#{color:06X}`)\nลองพิมพ์ `!profile` ดูเลย!",
            color=color,
        )
        await interaction.response.edit_message(content=None, embed=embed, view=None)


class ContinentWarpView(ActionView):
    """🎫 ตั๋วเรือเหมาลำ: เมนูเลือกทวีปปลายทางเอง — ตั๋วถูกหักตอนยืนยันเลือกเท่านั้น (ยกเลิก/หมดเวลา = ตั๋วอยู่ครบ)"""

    def __init__(self, user_id, item_id):
        super().__init__(timeout=60)
        self.user_id = user_id
        self.item_id = str(item_id)
        self.message = None

        player = player_model.get_player(user_id)
        current = player.get("continent") or "main"
        select = discord.ui.Select(placeholder="🗺️ เลือกทวีปปลายทาง...")
        for key, continent in game_modifiers.CONTINENTS.items():
            if key == current:
                continue  # ไม่ให้เลือกทวีปที่ยืนอยู่
            select.add_option(label=continent["label"], value=key)
        select.callback = self.pick
        self.add_item(select)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("❌ นี่ไม่ใช่ตั๋วของคุณ!", ephemeral=True)
            return False
        return True

    async def on_timeout(self):
        if self.message:
            try:
                await self.message.edit(content="⏳ กัปตันรอไม่ไหวออกเรือไปก่อน... (ตั๋วยังอยู่ในกระเป๋า ใช้ใหม่ได้)", view=None)
            except Exception:
                pass

    async def pick(self, interaction: discord.Interaction):
        dest = interaction.data["values"][0]
        player = player_model.get_player(self.user_id)

        if player.get("current_state") in ("fighting", "dead") or player.get("dungeon_steps", 0) > 0:
            self.stop()
            return await interaction.response.edit_message(
                content="❌ ตอนนี้ออกเรือไม่ได้! (ติดการต่อสู้/อยู่ในดันเจี้ยน)", view=None)

        inv = player_model.load_inventory(player.get("inventory", "[]"))
        if self.item_id not in inv:
            self.stop()
            return await interaction.response.edit_message(content="❌ ตั๋วไม่อยู่ในกระเป๋าแล้ว!", view=None)

        inv.remove(self.item_id)
        dest_info = game_modifiers.CONTINENTS[dest]
        player_model.update_player_fields(self.user_id, {
            "inventory": inv,
            "continent": dest,
            "last_event": "none",
            "current_state": "idle",
        })
        self.stop()
        arr_f = event_image(f"arrival_{dest}")
        await interaction.response.edit_message(
            content=(
                f"🎫 **เรือเหมาลำออกเดินทาง!** กัปตันฉีกตั๋วของคุณแล้วมุ่งหน้าเต็มใบ...\n"
                f"{dest_info['arrival_text']}\n"
                f"🗺️ ถึงแล้ว: {dest_info['label']} (พิมพ์ `!play` เพื่อออกสำรวจ)"
            ),
            view=None, **({"attachments": [arr_f]} if arr_f else {}))


class TravelEventView(ActionView):
    """เหตุการณ์สุ่มเจอพาหนะข้ามทวีป — เลือกขึ้นยาน (จ่ายค่าโดยสาร วัดดวงปลายทางตามเรทพาหนะ) หรือไม่ไป"""

    def __init__(self, user_id, encounter):
        super().__init__(timeout=60)
        self.user_id = user_id
        self.encounter = encounter  # {"vehicle", "label", "fare"} จาก game_modifiers.roll_travel_encounter
        self.message = None

        board_btn = discord.ui.Button(label=f"🧳 ขึ้นยาน (จ่าย {encounter['fare']:,} ทอง)", style=discord.ButtonStyle.success)
        board_btn.callback = self.board
        self.add_item(board_btn)

        decline_btn = discord.ui.Button(label="🙅 ไม่ไป เดินทางต่อ", style=discord.ButtonStyle.secondary)
        decline_btn.callback = self.decline
        self.add_item(decline_btn)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("❌ นี่ไม่ใช่การเดินทางของคุณ! พิมพ์ `!play` เพื่อเปิดบอร์ดตัวเองนะจ๊ะ", ephemeral=True)
            return False
        return True

    async def on_timeout(self):
        player_model.update_player_field(self.user_id, "current_state", "idle")
        if self.message:
            try:
                await self.message.edit(content=f"⏳ {self.encounter['label']} ออกเดินทางไปแล้วโดยไม่มีคุณ...", view=None)
            except Exception:
                pass

    async def board(self, interaction: discord.Interaction):
        r = adventure_core.resolve_travel(self.user_id, self.encounter, "board")
        self.stop()
        if not r.get("continent"):          # เงินไม่พอ — ยานออกไปเฉย ๆ
            return await interaction.response.edit_message(
                content=f"{r['text']}\n----------------------------------------\nคุณต้องการไปต่อหรือไม่?",
                view=AdventureView(author_id=self.user_id))

        dest = r["continent"]
        embed = discord.Embed(title=f"{self.encounter['label']} ➜ {game_modifiers.CONTINENTS[dest]['label']}",
                              description=f"{game_modifiers.CONTINENTS[dest]['arrival_text']}\n\n"
                                          f"💰 จ่ายค่าโดยสาร `{r['fare']:,}` ทอง\n----------------------------------------\nคุณต้องการไปต่อหรือไม่?",
                              color=0x9f7aea)
        # ภาพทวีปปลายทางแทนภาพยานพาหนะเดิมบนข้อความ
        arr_f = event_image(f"arrival_{dest}")
        if arr_f:
            embed.set_image(url=f"attachment://arrival_{dest}.png")
        await interaction.response.edit_message(content=None, embed=embed,
                                                view=AdventureView(author_id=self.user_id),
                                                **({"attachments": [arr_f]} if arr_f else {}))

    async def decline(self, interaction: discord.Interaction):
        r = adventure_core.resolve_travel(self.user_id, self.encounter, "decline")
        self.stop()
        await interaction.response.edit_message(
            content=f"{r['text']}\n----------------------------------------\nคุณต้องการไปต่อหรือไม่?",
            view=AdventureView(author_id=self.user_id))


class AdventureView(ActionView):
    def __init__(self, author_id: int):
        super().__init__(timeout=60)
        self.author_id = author_id
        self.message = None # 💡 1. เพิ่มตัวแปรไว้เก็บข้อความเพื่อรอการ Edit

    # ==========================================
    # ⏰ ดักจับเวลาผู้เล่นไม่กดปุ่ม "เริ่มออกเดินทาง" ใน 1 นาที
    # ==========================================
    async def on_timeout(self):
        for item in self.children:
            item.disabled = True # ปิดปุ่ม
            
        if self.message:
            try:
                await self.message.edit(content="⏰ **หน้าต่างนี้หมดอายุแล้ว!** รบกวนพิมพ์คำสั่งผจญภัยเพื่อเรียกหน้าต่างใหม่นะครับ", view=self)
            except Exception:
                pass

    # ==========================================
    # ⚠️ ดักจับเวลาปุ่มพังฉุกเฉิน (Soft-lock safeguard)
    # ==========================================
    async def on_error(self, interaction: discord.Interaction, error: Exception, item: discord.ui.Item):
        print(f"🚨 ERROR [AdventureView]: {error}")
        
        # ปลดล็อกสถานะใน DB ทันที
        player_model.update_player_field(self.author_id, "current_state", "idle")
        err_msg = "⚠️ บอร์ดผจญภัยเกิดข้อผิดพลาด! ระบบได้รีเซ็ตสถานะของคุณให้กลับเป็นปกติแล้วครับ"
        
        if not interaction.response.is_done():
            await interaction.response.send_message(err_msg, ephemeral=True)
        else:
            await interaction.followup.send(err_msg, ephemeral=True)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.author_id:
            await interaction.response.send_message("❌ บอร์ดออกเดินทางนี้ไม่ใช่ของคุณ! รบกวนพิมพ์ `!play` เพื่อทริกเกอร์บอร์ดของตัวเองนะครับ", ephemeral=True)
            return False
        return True

    @discord.ui.button(label="⏩ เดินต่อ ×5", style=discord.ButtonStyle.secondary)
    async def start_adv_x5(self, interaction: discord.Interaction, button: discord.ui.Button):
        """O5: เดินรวดสูงสุด 5 ก้าว — ข้ามเฉพาะช่วงที่ไม่มีอะไรให้ตัดสินใจ (อีเวนต์สงบ)
        เจอมอน/หีบ/กับดัก/ดันเจี้ยน/พาหนะ/อีเวนต์พิเศษ หรือเลือดต่ำ = หยุดทันที"""
        await self.walk_step(interaction, button, max_steps=5)

    @discord.ui.button(label="🧭 เริ่มออกเดินทาง", style=discord.ButtonStyle.green)
    async def start_adv(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.walk_step(interaction, button, max_steps=1)

    async def walk_step(self, interaction: discord.Interaction, button: discord.ui.Button, max_steps=1):
        """ตรรกะเดินหนึ่งก้าว — ต้องเป็นเมธอดธรรมดา ห้ามครอบ @discord.ui.button
        เพราะ discord.py จะ setattr ทับชื่อด้วยอ็อบเจ็กต์ Button ทำให้เรียกเป็นฟังก์ชันไม่ได้"""
        user_id = interaction.user.id
        player = player_model.get_player(user_id)

        if player["current_state"] != "idle":
            if interaction.response.is_done():
                await interaction.followup.send("⚠️ คุณกำลังติดเหตุการณ์อื่นอยู่!", ephemeral=True)
            else:
                await interaction.response.send_message("⚠️ คุณกำลังติดเหตุการณ์อื่นอยู่!", ephemeral=True)
            return

        # ⏩ รอบเดินรวด (max_steps>1) จะวนเข้าฟังก์ชันนี้ซ้ำด้วย interaction เดิม — ตอบได้ครั้งเดียวเท่านั้น
        if not interaction.response.is_done():
            await interaction.response.edit_message(content="✨ คุณเริ่มก้าวเท้าออกเดินทางตรวจตราเส้นทาง...", view=None)

        # 1. งานต้นก้าว (คูลดาวน์/สถานะ/เลือดไหล/ฟื้น HP) — ตรรกะอยู่ใน adventure_core ใช้ร่วมกับเว็บ
        walker_elements = game_modifiers.resolve_player_elements(
            [getattr(r, "name", str(r)) for r in getattr(interaction.user, "roles", [])])
        pre = adventure_core.step_prelude(user_id, player, walker_elements)
        player, statuses, mods = pre["player"], pre["statuses"], pre["mods"]
        dg_steps, last_evt, current_cooldown = pre["dg_steps"], pre["last_evt"], pre["cooldown"]

        if pre["dead"]:
            # ตายกลางทางจากพิษ/สถานะ — เข้า flow ตายปกติ
            embed = discord.Embed(
                title="💀 คุณล้มลงกลางทาง... พิษกัดกินร่างกายจนหมดสติ",
                description="\n".join(pre["notes"]) + "\n\n📌 กดปุ่มด้านล่างเพื่อฟื้นตัวและยอมรับบทลงโทษกลับหมู่บ้าน",
                color=0xe53e3e,
            )
            await interaction.followup.send(embed=embed, view=RespawnView(user_id), **file_kwargs(event_image("death")))
            return
        if pre["notes"]:
            await interaction.followup.send("\n".join(pre["notes"]))

        # 2. เลือกเหตุการณ์ของก้าวนี้ — ตรรกะอยู่ใน adventure_core (ใช้ร่วมกับเว็บ)
        chosen_event, special_event, dg_steps = adventure_core.decide_event(
            user_id, player, statuses, mods, dg_steps, last_evt, current_cooldown)

        summon_events = adventure_core.SUMMON_EVENTS
        adventure_core.commit_event(user_id, chosen_event, last_evt)


        # ==========================================
        # 🛠️ จุดที่แก้ไข: ท่าส่งข้อความแบบฝัง Timeout ให้เหตุการณ์ถัดไป
        # ==========================================
        cur_continent = player.get("continent") or "main"

        if chosen_event == "monster":
            player_model.update_player_field(user_id, "current_state", "fighting")
            status_msg = f"*(เหลืออีก {dg_steps} ตาในดันเจี้ยน)*" if dg_steps > 0 or player.get("dungeon_steps", 0) > 0 else f"*(คูลดาวน์หมู่บ้านเหลือ: {current_cooldown} ตา)*"

            emp_note = ""
            if game_modifiers.has_status_flag(statuses, "disable_skills"):
                emp_note = "\n⚡ **คลื่น EMP รบกวนร่างกาย! สกิลถูกปิดในไฟต์นี้ — ใช้ได้แค่โจมตีปกติ**"

            # ภาพประกอบ: บอสที่ถูกอัญเชิญใช้ภาพ summon, มอนปกติใช้ภาพเงาปริศนาของทวีป
            evt_img = event_image(last_evt) if last_evt in summon_events else event_image("monster", cur_continent)

            # สร้าง View -> ส่งข้อความรอรับค่า -> ยัดข้อความกลับเข้า View
            next_view = MonsterEventView(user_id, interaction.user.roles)
            sent_msg = await interaction.followup.send(content=f"👹 มีเงาปริศนาพุ่งออกมากระโจนขวางทางคุณ! เลือกแอคชั่นหรือคลาสสกิลของคุณ: {status_msg}{emp_note}", view=next_view, wait=True, **file_kwargs(evt_img))
            next_view.message = sent_msg
            
        elif chosen_event == "village":
            player_model.update_player_field(user_id, "current_state", "village")

            cleanse_note = ""
            statuses, cleansed = game_modifiers.cleanse_statuses(statuses, "village")
            if cleansed:
                player_model.update_player_field(user_id, "status_effects", statuses)
                names = " ".join(game_modifiers.STATUS_EFFECTS[k]["label"] for k in cleansed)
                cleanse_note = f"\n✨ หมอสมุนไพรประจำหมู่บ้านรักษาคุณ — {names} หายเป็นปกติ!"

            next_view = VillageEventView(user_id)
            sent_msg = await interaction.followup.send(content=f"🏡 คุณเดินทางมาพบ **'หมู่บ้านอุ่นใจ'** เลือกแอคชั่นของคุณ:{cleanse_note}", view=next_view, wait=True, **file_kwargs(event_image("village", cur_continent)))
            next_view.message = sent_msg

        elif chosen_event == "treasure":
            player_model.update_player_field(user_id, "current_state", "treasure_choice")
            
            next_view = TreasureEventView(user_id)
            treasure_text = mods["theme_texts"].get("treasure", "📦 คุณพบ **'หีบสมบัติปริศนาลงอักขระโบราณ'**")
            sent_msg = await interaction.followup.send(content=f"{treasure_text} เลือกแอคชั่นของคุณ: *(คูลดาวน์หมู่บ้านเหลือ: {current_cooldown} ตา)*", view=next_view, wait=True, **file_kwargs(event_image("treasure", cur_continent)))
            next_view.message = sent_msg

        elif chosen_event == "npc":
            player_model.update_player_field(user_id, "current_state", "npc_choice")

            cleanse_note = ""
            statuses, cleansed = game_modifiers.cleanse_statuses(statuses, "npc")
            if cleansed:
                player_model.update_player_field(user_id, "status_effects", statuses)
                names = " ".join(game_modifiers.STATUS_EFFECTS[k]["label"] for k in cleansed)
                cleanse_note = f"\n✨ นักเดินทางแบ่งยาสมุนไพรให้คุณ — {names} หายเป็นปกติ!"

            next_view = NpcEventView(user_id)
            sent_msg = await interaction.followup.send(content=f"🧓 คุณเจอนักเดินทางพเนจร (NPC) นั่งอยู่ข้างกองไฟ เลือกแอคชั่นของคุณ: *(คูลดาวน์หมู่บ้านเหลือ: {current_cooldown} ตา)*{cleanse_note}", view=next_view, wait=True, **file_kwargs(event_image("npc", cur_continent)))
            next_view.message = sent_msg

        elif chosen_event == "dungeon":
            player_model.update_player_field(user_id, "current_state", "dungeon_choice")

            cleanse_note = ""
            statuses, cleansed = game_modifiers.cleanse_statuses(statuses, "dungeon")
            if cleansed:
                player_model.update_player_field(user_id, "status_effects", statuses)
                names = " ".join(game_modifiers.STATUS_EFFECTS[k]["label"] for k in cleansed)
                cleanse_note = f"\n🔥 ไออุ่นจากใต้พิภพแผ่ซ่านไปทั่วร่าง — {names} หายเป็นปกติ!"

            next_view = DungeonEventView(user_id)
            sent_msg = await interaction.followup.send(content=f"💀 คุณส่องเห็น **'ช่องอุโมงค์ถ้ำใต้พิภพ (Dungeon)'** เลือกแอคชั่นของคุณ: *(คูลดาวน์หมู่บ้านเหลือ: {current_cooldown} ตา)*{cleanse_note}", view=next_view, wait=True, **file_kwargs(event_image("dungeon", cur_continent)))
            next_view.message = sent_msg

        elif chosen_event == "trap":
            player_model.update_player_field(user_id, "current_state", "trap_defense")

            next_view = TrapEventView(user_id, interaction.user.roles)
            trap_text = mods["theme_texts"].get("trap", "⚠️ *แก๊ก!* คุณพลาดก้าวขาไปเกี่ยวสายสลิง **'กับดักโบราณ'** เข้าให้แล้ว!")
            sent_msg = await interaction.followup.send(content=f"{trap_text} เตรียมรับมือแอคชั่นหลบหลีก: *(คูลดาวน์หมู่บ้านเหลือ: {current_cooldown} ตา)*", view=next_view, wait=True, **file_kwargs(event_image("trap", cur_continent)))
            next_view.message = sent_msg

        elif chosen_event == "bank_robbery":
            # 🏦💥 ปล้นธนาคาร — เหตุการณ์ทันที ไม่มีปุ่มให้เลือก (spec 2026-08-06)
            _rob = robbery.resolve_bank_robbery(user_id, player)
            lost, left, theft_note = _rob["lost"], _rob["left"], _rob["theft"]
            next_view = AdventureView(author_id=user_id)
            sent_msg = await interaction.followup.send(
                content=(f"🏦💥 **โจรปล้นธนาคาร!** แก๊งโจรมือโปรเจาะตู้นิรภัยสาขาที่คุณฝากเงินไว้!\n"
                         f"เงินฝากหายไป `{lost:,}` ทอง — เหลือในบัญชี `{left:,}` ทอง{theft_note}\n"
                         f"*(กันได้ด้วย 🪪 บัตรประกัน — หาซื้อที่ร้านค้าประจำหมู่บ้าน)*\n"
                         f"----------------------------------------\nคุณต้องการไปต่อหรือไม่?"),
                view=next_view, wait=True, **file_kwargs(event_image("bank_robbery", cur_continent)))
            next_view.message = sent_msg

        elif chosen_event == "mugging":
            # 🥷 โดนดักปล้น — เลือกสู้หรือหนี (spec 2026-08-06)
            player_model.update_player_field(user_id, "current_state", "mugging")
            cash = int(player.get("cash", 0) or 0)
            win_pct = robbery.mug_win_chance(cash + int(player.get("bank", 0) or 0))
            next_view = MuggingEventView(user_id)
            sent_msg = await interaction.followup.send(
                content=(f"🥷 **โดนดักปล้น!** โจรถือมีดโผล่จากพุ่มไม้ จ้องถุงทอง `{cash:,}` ทองของคุณ!\n"
                         f"⚔️ **สู้** — ชนะริบของโจร +10% ของเงินติดตัว / แพ้โดนกวาดเงินติดตัวหมด "
                         f"*(โอกาสชนะ {win_pct}% — เงินยิ่งหนักยิ่งถ่วงแข้งขา)*\n"
                         f"🏃 **หนี** — โยนถุงทองครึ่งหนึ่งสกัดโจรแล้ววิ่ง (-50% เงินติดตัว)"),
                view=next_view, wait=True, **file_kwargs(event_image("mugging", cur_continent)))
            next_view.message = sent_msg

        elif chosen_event == "calm":
            # ไม่มีอะไรเกิดขึ้น — สถานะยังเป็น idle กดไปต่อได้ทันที
            # ⏩ O5: โหมดเดินรวด — ก้าวนี้ไม่มีอะไรให้ตัดสินใจ เดินต่อให้เลย (ยังทอยอีเวนต์ครบทุกก้าว)
            fresh = player_model.get_player(user_id) or player
            hp_ok = fresh.get("hp", 0) > fresh.get("max_hp", 100) * 0.3
            if max_steps > 1 and hp_ok:
                self._auto_walked = getattr(self, "_auto_walked", 0) + 1
                return await self.walk_step(interaction, button, max_steps=max_steps - 1)
            walked = getattr(self, "_auto_walked", 0)
            next_view = AdventureView(author_id=user_id)
            calm_text = game_modifiers.pick_calm_text()
            if walked:
                calm_text = f"⏩ **เดินรวด {walked + 1} ก้าว** — เส้นทางเงียบสงบตลอดทาง\n{calm_text}"
                self._auto_walked = 0
            elif not hp_ok and max_steps > 1:
                calm_text += "\n⚠️ **เลือดต่ำกว่า 30% — หยุดเดินรวดเพื่อความปลอดภัย** (กินยาก่อนไปต่อ!)"
            sent_msg = await interaction.followup.send(
                content=f"{calm_text}\n----------------------------------------\nคุณต้องการไปต่อหรือไม่?",
                view=next_view, wait=True, **file_kwargs(event_image("calm", cur_continent)))
            next_view.message = sent_msg

        elif chosen_event == "special":
            intro = special_event.get("intro", "✨ มีบางอย่างเกิดขึ้นตรงหน้าคุณ...")
            sp_img = event_image(special_event.get("key", ""))
            if special_event.get("template") == "instant":
                # ไม่มีสิทธิ์เลือก — จ่ายผลทันที (เช่น งานเลี้ยงบรรพชน)
                outcome = resolve_instant_special(special_event)
                lines, died = execute_special_outcome(user_id, outcome)
                body = intro + "\n" + "\n".join(lines)
                if died:
                    await interaction.followup.send(content=body, view=RespawnView(user_id), **file_kwargs(event_image("death")))
                elif outcome.get("start_fight"):
                    player_model.update_player_field(user_id, "current_state", "fighting")
                    next_view = MonsterEventView(user_id, interaction.user.roles)
                    sent_msg = await interaction.followup.send(
                        content=f"{body}\n👹 **ศัตรูไม่ให้เวลาคุณหายใจ — เข้าสู่การต่อสู้ทันที!**",
                        view=next_view, wait=True, **file_kwargs(sp_img))
                    next_view.message = sent_msg
                else:
                    next_view = AdventureView(author_id=user_id)
                    sent_msg = await interaction.followup.send(
                        content=f"{body}\n----------------------------------------\nคุณต้องการไปต่อหรือไม่?",
                        view=next_view, wait=True, **file_kwargs(sp_img))
                    next_view.message = sent_msg
            else:
                player_model.update_player_field(user_id, "current_state", "special_choice")
                next_view = SpecialEventView(user_id, special_event)
                sent_msg = await interaction.followup.send(content=intro, view=next_view, wait=True, **file_kwargs(sp_img))
                next_view.message = sent_msg

        elif chosen_event == "travel":
            player_model.update_player_field(user_id, "current_state", "travel_choice")

            encounter = game_modifiers.roll_travel_encounter(player.get("cash", 0))
            next_view = TravelEventView(user_id, encounter)
            sent_msg = await interaction.followup.send(
                content=(
                    f"🧭 ระหว่างทาง... **{encounter['label']}** ปรากฏขึ้นตรงหน้าคุณ!\n"
                    f"💰 ค่าโดยสาร: `{encounter['fare']:,}` ทอง (จ่ายจากเงินสดในกระเป๋า)\n"
                    f"🎲 ปลายทางจะรู้ก็ต่อเมื่อไปถึงแล้วเท่านั้น — จะร่วมเดินทางไหม?"
                ),
                view=next_view, wait=True, **file_kwargs(event_image(f"vehicle_{encounter['vehicle']}")))
            next_view.message = sent_msg