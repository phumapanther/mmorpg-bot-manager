import aiohttp
import discord
from discord.ext import commands

from bot import bot_registry
import asyncio
import sys

# ponytail: การส่ง env PYTHONIOENCODING=utf-8 ตอน spawn subprocess (ใน process_manager.py) ไม่ชัวร์
# ว่าจะมีผลตอนบอทถูกแพ็กเป็น onefile exe แล้ว re-exec ตัวเอง (--run-bot) — reconfigure ตรงนี้ชัวร์กว่า
# ไม่งั้น print ข้อความไทย/emoji จะพัง UnicodeEncodeError บน Windows locale ที่ไม่ใช่ UTF-8
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")

import bot.models.player_model as player_model
from bot import config_loader

# 🔒 ดึงค่า Token จาก config.json ผ่าน Panel
TOKEN_GAME = config_loader.get_token()

def create_bot(bot_type: str):
    """ฟังก์ชันเสกอินสแตนซ์บอทตามประเภทหน้าที่"""
    intents = discord.Intents.default()
    intents.message_content = True
    intents.members = True
    intents.voice_states = True # 🌟 เปิดสิทธิ์แสกนรายชื่อในห้อง Voice
    intents.presences = True        # จำเป็นสำหรับการเช็ก Online/Offline

    bot = commands.Bot(command_prefix="!", intents=intents)
    bot.CURRENT_EVENT_MULTIPLIER = 1.0  # เก็บไว้ที่ตัวบอทเลย
    bot.bot_type = bot_type
    bot_registry.register(bot)   # ให้ปุ่ม Stop ปิดได้ครบทุกตัว
    @bot.event
    async def on_command_error(ctx, error):
        # ตรวจสอบว่า Error ที่เกิดขึ้นคือ CheckFailure ที่มาจากไฟล์ utils.py หรือไม่
        if isinstance(error, commands.CheckFailure) and str(error) == "arrested":
            await ctx.send("❌ **[ปฏิเสธคำสั่ง]** คุณถูกจับกุมอยู่! ไม่สามารถใช้คำสั่งได้จนกว่าจะพ้นโทษ 🔗⛓️")
        elif isinstance(error, commands.MissingPermissions):
            await ctx.send("❌ คำสั่งนี้ใช้ได้เฉพาะแอดมินของเซิร์ฟเวอร์นี้เท่านั้น")
        elif isinstance(error, commands.CheckFailure):
            # ด่านต่าง ๆ (ผิดห้อง/ไม่ใช่เซิร์ฟหลัก/ไม่มีสิทธิ์) ตอบผู้ใช้ไปเองแล้ว — ไม่ต้องพ่น traceback ให้ log รก
            print(f"🔒 [BLOCKED] {ctx.author.name} ใช้ !{ctx.command} ไม่ผ่านด่านตรวจ ({ctx.guild.name if ctx.guild else 'DM'})")
        else:
            # ถ้าเป็น Error อื่นๆ ให้แสดงออกมาตามปกติ (เพื่อใช้ดีบั๊ก)
            raise error

    # 🔗⛓️ [เพิ่มระบบระบบดักกลางอากาศ]: ล็อกสิทธิ์ไม่ให้ผู้เล่นติดสถานะจับกุมพิมพ์คำสั่ง
    @bot.before_invoke
    async def global_before_invoke(ctx):
        import time

        if ctx.command.cog and ctx.command.cog.qualified_name == "AdminCommands":
            return

        if ctx.author.guild_permissions.administrator or ctx.author.id == ctx.guild.owner_id:
            return

        player = player_model.get_player(ctx.author.id)
        if player and player.get("current_state") == "arrested":
            arrest_until = player.get("arrest_until", 0)
            current_time = int(time.time())

            # ⏳ เช็กว่าหมดเวลาติดคุกหรือยัง
            if arrest_until and current_time >= int(arrest_until):
                # 🎉 หมดเวลาแล้ว! ปลดปล่อยตัวอัตโนมัติกลางอากาศเลย
                player_model.update_player_field(ctx.author.id, "current_state", "idle")
                player_model.update_player_field(ctx.author.id, "arrest_until", 0)
                print(f"🕊️ [BEFORE INVOKE] ผู้เล่น {ctx.author.name} หมดเวลาขังคุก สั่งปล่อยตัวอัตโนมัติ")
                return # ผ่านให้ใช้คำสั่งที่พิมพ์มาได้เลย!

            # 🔗 ถ้ายังไม่หมดเวลา ให้ดีดแจ้งเตือนและบอกเวลาที่เหลือ
            remaining_seconds = int(arrest_until) - current_time
            remaining_mins = max(1, remaining_seconds // 60) # แปลงวินาทีเป็นนาทีคร่าวๆ

            await ctx.send(f"❌ **[ปฏิเสธคำสั่ง]** คุณถูกจับกุมอยู่! เหลือเวลาติดคุกอีกประมาณ `{remaining_mins}` นาที 🔗⛓️")
            raise commands.CommandError("Player is currently arrested.")
        

    @bot.event
    async def on_ready():
        player_model.init_db()
        player_model.auto_update_schema()

        # 🕹️ ลงทะเบียนปุ่มเมนูแบบ persistent ให้กดใช้ได้ตลอดแม้บอทรีสตาร์ท
        from bot.views.menu_view import GameMenuView
        bot.add_view(GameMenuView())

        # 🔄 สั่งให้บอทลงทะเบียนและอัปเดตระบบสแลชคำสั่งเข้าเซิร์ฟเวอร์จริง
        try:
            synced = await bot.tree.sync()
            print(f"📊 [SYSTEM] ซิงค์ระบบคำสั่งสแลชสำเร็จทั้งหมด {len(synced)} คำสั่ง!")
        except Exception as e:
            print(f"⚠️ การซิงค์คำสั่งสแลชขัดข้อง: {e}")
            
        print(f"🟢 [SYSTEM ONLINE] บอทร่าง [{bot_type.upper()}] ออนไลน์แล้ว!")

    @bot.event
    async def on_setup():
        """โหลดโมดูลแยกตามสถานะการบายพาส"""
        try:
            # 🔄 [โหมดบายพาส] ถ้าเป็นบอทเกม (Arthur) ให้โหลดทั้งระบบเกม, ระบบแอดมิน และระบบเสียงควบรวมกันเลย!
            if bot_type == "game":
                await bot.load_extension("bot.cogs.game_commands")
                print("⚔️ [Game Bot] โหลดระบบคำสั่งคอมแบทและร้านค้าสำเร็จ!")
                
                await bot.load_extension("bot.cogs.admin_commands")
                print("👑 [Admin Commands] โหลดระบบคำสั่งผู้ดูแลระบบสำเร็จ!")

                await bot.load_extension("bot.cogs.player_commands")
                print("🕺[Player Commands] โหลดระบบคำสั่งผู้เล่นสำเร็จ!")

                await bot.load_extension("bot.apps.bot_worker.voice_chat_tracker")
                print("🎙️ [Bypass Mode] โน้ตระบบลูปห้องเสียงและฟาร์มแชทมาให้ Arthur รันแทนชั่วคราวสำเร็จ!")
                
                await bot.load_extension('bot.cogs.owner_announce')
                print("📢 [Owner Announce] โหลดระบบประกาศข่าวสารสำเร็จ!")

                await bot.load_extension('bot.cogs.adventure_zone')
                print("🌌 [Adventure Zone] โหลดระบบห้องผจญภัยส่วนตัวสำเร็จ!")

                await bot.load_extension("bot.cogs.private_room")
                print("🏠 [Private Room Bot] โหลดระบบคำสั่ง สร้างห้อง สำเร็จ!")
                
                await bot.load_extension("bot.cogs.pvp_duel")
                print("⚔️ [PVP Commands] โหลดระบบคำสั่ง PVP สำเร็จ!")

                await bot.load_extension("bot.cogs.world_boss")
                print("👿[World Boss Commands] โหลดระบบคำสั่ง Boss สำเร็จ!")

                await bot.load_extension("bot.cogs.casino")
                print("🎰[Casino] โหลดระบบคำสั่ง casino สำเร็จ!")

                await bot.load_extension("bot.cogs.blackjack")
                print("🃏[Blackjack Commands] โหลดระบบคำสั่ง เทรนบอท blackjack ")

                await bot.load_extension("bot.cogs.role_shop")
                print("💸[Buy] โหลดระบบคำสั่ง ซื้อยศออนไลน์!")

                await bot.load_extension("bot.apps.bot_worker.role_grant_worker")
                print("🌉[RoleQueue] โหลดสะพานแจกยศจากเว็บ สำเร็จ!")

                await bot.load_extension("bot.cogs.dice_board_cmd")
                print("🎲[Board] โหลดกระดานทอยเต๋ารายวัน สำเร็จ!")

                await bot.load_extension("bot.cogs.payment")
                print("💳[Payment] โหลดระบบคำสั่ง เติมเงิน สำเร็จ!")

                await bot.load_extension("bot.apps.bot_worker.weekly_event")
                print("🎪[Weekly Event] โหลดระบบประกาศอีเวนต์ประจำสัปดาห์สำเร็จ!")

                await bot.load_extension("bot.cogs.world_admin")
                print("🛠️[World Admin] โหลดคำสั่งแอดมินควบคุมโลกสำเร็จ!")

                await bot.load_extension("bot.apps.bot_worker.db_backup")
                print("💾[DB Backup] โหลดระบบสำรองฐานข้อมูลรายวันสำเร็จ!")

                await bot.load_extension("bot.cogs.guild")
                print("🏰[Guild] โหลดระบบกิลด์สำเร็จ!")

                await bot.load_extension("bot.apps.bot_worker.server_status")
                print("📡[Server Status] โหลดระบบแจ้งเตือนเปิด-ปิดเซิร์ฟสำเร็จ!")

                await bot.load_extension("bot.cogs.guild_war")
                print("⚔️[Guild War] โหลดระบบกิลด์วอร์สำเร็จ!")

                await bot.load_extension("bot.cogs.web_link")
                print("🌐[Web] โหลดสะพานเว็บไซต์ (!web / !weblogin) สำเร็จ!")

                await bot.load_extension("bot.apps.bot_worker.lobby_invite")
                print("🎴[LobbyInvite] โหลดสะพานชวนเพื่อนเข้าห้อง (DM) สำเร็จ!")

            # 🌍 [P8] บอทแจกสำหรับเซิร์ฟรอง — เล่นผจญภัยได้อย่างเดียว ไม่มีร้านค้า/คาสิโน/กิลด์/แอดมิน
            elif bot_type == "guest":
                await bot.load_extension("bot.cogs.game_commands")     # !play (+ !shop ล็อกเซิร์ฟหลักในตัว)
                await bot.load_extension("bot.cogs.player_commands")   # !bag !use !codex !bestiary (คำสั่งเซิร์ฟหลักถูกล็อกรายตัว)
                await bot.load_extension("bot.cogs.adventure_zone")    # !adv
                await bot.load_extension("bot.cogs.web_link")          # 🌐 !web !weblogin !slip + ปุ่มเติมเงิน (เครื่องไม่มี license_server = ข้ามเอง)
                await bot.load_extension("bot.cogs.guest_server")      # ด่านห้อง + !set_adv_channel
                print("🌍 [Guest Bot] โหลดโหมดเซิร์ฟรอง (ผจญภัยอย่างเดียว) สำเร็จ!")

            elif bot_type == "chat":
                await bot.load_extension("bot.apps.bot_worker.voice_chat_tracker")
                print("🎙️ [Chat/Voice Bot] โหลดระบบลูปห้องเสียงและฟาร์มแชทสำเร็จ!")
                
            elif bot_type == "admin":
                print("👑 [Admin Bot] บอทตรวจสอบระบบ Standby พร้อมทำงาน!")
                
        except Exception as e:
            print(f"❌ [{bot_type.upper()}] โดนสกัดการโหลดโมดูล: {e}")

    async def custom_start(token):
        if not token:
            print(f"⚠️ [ERROR] ไม่พบค่า Token สำหรับบอทประเภท: {bot_type.upper()}")
            return
        async with bot:
            await on_setup()
            await bot.start(token)

    return custom_start

RETRY_DELAY_START = 15      # วินาที — เน็ตหลุดตอนล็อกอิน รอเท่านี้แล้วลองใหม่
RETRY_DELAY_MAX = 300       # เพดานถอยหลัง 5 นาที (เน็ตล่มยาวก็ไม่สแปม log)


async def run_with_retry(bot_type, token, label):
    """เปิดบอทและลองใหม่เองเมื่อเน็ต/DNS ล่มชั่วคราว

    เคสจริง (2026-08-10): DNS resolve discord.com ไม่ได้ตอนสตาร์ท → ทั้งโปรเซสตายคาที่
    ต้องมานั่งกดเปิดใหม่เอง ทั้งที่เน็ตกลับมาเองใน 1 นาที

    โทเค็นผิด/ไม่ได้เปิด intents = หยุดเลย ไม่ต้องลองใหม่ (ต้องให้คนไปแก้ ลองกี่รอบก็ไม่ติด)
    ต้องเรียก create_bot ใหม่ทุกรอบ — discord.py ปิด Client แล้วเปิดตัวเดิมซ้ำไม่ได้
    """
    delay = RETRY_DELAY_START
    while True:
        try:
            await create_bot(bot_type)(token)
            return                              # ปิดปกติ (เช่นสั่งปิดจาก Panel)
        except discord.LoginFailure:
            print(f"❌ [{label}] เปิดไม่ได้: โทเค็นไม่ถูกต้อง (แก้ที่ Panel แล้วเปิดใหม่)")
            return
        except discord.PrivilegedIntentsRequired:
            print(f"❌ [{label}] เปิดไม่ได้: ยังไม่ได้เปิด Privileged Intents ให้บอทตัวนี้!\n"
                  "   → Discord Developer Portal → เลือกแอปบอท → Bot →\n"
                  "     เปิด MESSAGE CONTENT / SERVER MEMBERS / PRESENCE ทั้ง 3 อัน แล้วรีสตาร์ท")
            return
        except (aiohttp.ClientError, OSError) as e:
            # สั่งปิดจาก Panel แล้ว = อย่าลองใหม่ ไม่งั้นโปรเซสไม่มีวันจบ
            # (ตอนปิดคอนเนกชัน discord.py โยน error สายเน็ตออกมาได้ ถ้าจับไว้แล้วรอเปิดใหม่
            #  พาแนลจะต้องรอหมดเวลา 6 วิแล้วบังคับฆ่า ปุ่ม Stop เลยดูเหมือนค้าง)
            if bot_registry.is_shutting_down():
                print(f"🛑 [{label}] ปิดตามคำสั่งจาก Panel")
                return
            # เน็ตหลุด/DNS ล่ม/เราเตอร์รีบูต — รอแล้วลองใหม่ ไม่ต้องให้คนมากดเอง
            print(f"⚠️ [{label}] ต่อ Discord ไม่ได้ ({type(e).__name__}: {e}) — ลองใหม่ในอีก {delay} วินาที")
            await asyncio.sleep(delay)
            delay = min(delay * 2, RETRY_DELAY_MAX)
        except Exception as e:
            print(f"❌ [{label}] เปิดไม่ได้: {type(e).__name__}: {e}")
            return


# 🚀 3. ฟังก์ชันควบคุมการจุดระเบิดเปิดบอ
async def main():
    if not TOKEN_GAME:
        print("⚠️ ยังไม่ได้ตั้ง token — เปิดหน้า Panel แล้วใส่ token ก่อน")
        return

    # 🔐 เช็ค License Key กับ License Server ทุกครั้งที่สตาร์ท (ต้องเปิดโปรแกรม License Server ทิ้งไว้)
    from bot import license_client
    license_ok, license_msg = license_client.check_license(config_loader.get_license_key(), TOKEN_GAME)
    print(license_msg)
    if not license_ok:
        return

    print("⏳ กำลังเตรียมการเปิดระบบในโหมดบายพาส (บอทแรกตัวเดียว)...")

    # สั่งสร้างตัวรันบอทเกม (Arthur) — เน็ตหลุดตอนเปิด ลองใหม่เองจนติด
    runners = [run_with_retry("game", TOKEN_GAME, "GAME")]

    # 🌍 [P8] บอทแจกสำหรับเซิร์ฟรอง — รันคู่กันถ้าตั้ง guest_bot_token ไว้ (ไม่ตั้ง = ข้าม)
    guest_token = config_loader.get_guest_token()
    main_gid = config_loader.get_main_guild_id()
    print(f"🌍 [P8] เซิร์ฟหลัก: {main_gid or '⚠️ ยังไม่ตั้ง (ทุกเซิร์ฟถูกนับเป็นเซิร์ฟหลัก!)'} | "
          f"บอทแจก: {'✅ ตั้งโทเค็นแล้ว' if guest_token else '➖ ไม่ได้ใช้'}")
    if guest_token and not main_gid:
        print("⚠️ [P8] เตือน: เปิดบอทแจกแต่ไม่ได้ตั้ง Main Guild ID — "
              "เซิร์ฟรองจะใช้ได้ทุกฟีเจอร์รวมคำสั่งแอดมิน! กรอกไอดีเซิร์ฟหลักใน Panel ก่อนเปิดใช้จริง")
    if guest_token:
        print("🌍 กำลังเปิดบอทแจก (โหมดเซิร์ฟรอง) คู่ไปด้วย...")

        # บอทแจกล้มต้องไม่ลากบอทหลักตายไปด้วย — run_with_retry จับ error ให้ครบแล้ว
        runners.append(run_with_retry("guest", guest_token, "Guest Bot"))

    # 🔥 [สั่งรันเฉพาะบอทแรก] บายพาสตัวที่ 2 และ 3 ออกไปก่อนชั่วคราว
    await asyncio.gather(
        *runners,
        # run_game_bot(TOKEN_CHAT_VOICE), # 💤 ปิดคอมเมนต์ไว้ชั่วคราว
        # run_game_bot(TOKEN_ADMIN)      # 💤 ปิดคอมเมนต์ไว้ชั่วคราว
    )

if __name__ == "__main__":
    if sys.platform == "win32":
        import ctypes
        # บอก Windows ว่า process นี้ต้องรันต่อเนื่องแม้จอดับ (Modern Standby / S0)
        ES_CONTINUOUS      = 0x80000000
        ES_SYSTEM_REQUIRED = 0x00000001
        ctypes.windll.kernel32.SetThreadExecutionState(ES_CONTINUOUS | ES_SYSTEM_REQUIRED)
        ctypes.windll.winmm.timeBeginPeriod(1)
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n🛑 ปิดระบบการทำงานของบอทเรียบร้อยแล้วครับคุณอาเธอร์")
    except asyncio.CancelledError:
        # ปิดสุภาพจากปุ่ม Stop (server_status สั่ง bot.close จากข้างใน) — ไม่ใช่ crash อย่าพ่น traceback
        print("\n🛑 ปิดเซิร์ฟเวอร์เรียบร้อย (คำสั่งปิดจาก Panel)")