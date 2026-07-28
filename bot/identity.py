# 🧬 เผ่า/คลาสของผู้เล่น (P8) — ที่เดียวที่ตัดสินว่าใครเป็นเผ่าอะไร คลาสอะไร
# กติกา: 1) มียศจริงในเซิร์ฟ → ใช้ยศ + ซิงก์ลง DB   2) ไม่มียศ (เซิร์ฟรอง) → ใช้ค่าใน DB
#        3) ไม่มีทั้งคู่ → สุ่มให้ + เก็บ DB (เซิร์ฟหลักแจกยศจริงเพิ่ม)
import random

import bot.models.player_model as player_model
from bot.views.profile_embed import GAME_CLASSES, GAME_RACES, MONSTER_RACES

ALL_RACES = GAME_RACES + MONSTER_RACES


def _names(role_objs):
    return [getattr(r, "name", str(r)) for r in (role_objs or [])]


def detect_from_roles(role_names):
    """หาเผ่า/คลาสจากชื่อยศ (ตรงเป๊ะตามตาราง) — ไม่เจอ = None"""
    race = next((r for r in ALL_RACES if r in role_names), None)
    cls = next((c for c in GAME_CLASSES if c in role_names), None)
    return race, cls


def roll_identity(rng=None):
    """สุ่มเผ่า+คลาสให้ผู้เล่นใหม่"""
    rng = rng or random
    return rng.choice(ALL_RACES), rng.choice(GAME_CLASSES)


def effective_role_names(role_objs, player):
    """ชื่อยศ 'ที่มีผลจริง' สำหรับคิดธาตุ/สกิล/ฝ่าย — มียศจริงใช้ยศ ไม่มีก็เติมค่าจาก DB เข้าไปแทน
    (ทำให้ทุกระบบเดิมที่อ่านจากชื่อยศทำงานต่อได้ทั้งเซิร์ฟหลักและเซิร์ฟรอง)"""
    names = _names(role_objs)
    race, cls = detect_from_roles(names)
    extra = []
    if not race and (player or {}).get("race"):
        extra.append(player["race"])
    if not cls and (player or {}).get("class_name"):
        extra.append(player["class_name"])
    return names + extra


async def ensure_identity(member, player, on_main_server):
    """เรียกตอน !play — จัดเผ่า/คลาสให้ครบตามกติกา คืนข้อความประกาศ (None = ไม่มีอะไรเปลี่ยน)

    เซิร์ฟหลัก: ไม่มียศเผ่า/คลาส → สุ่มใหม่ + แจกยศจริง + อัปเดต DB (ตามสเปกผู้ใช้)
    เซิร์ฟรอง : ไม่มีค่าใน DB → สุ่มเก็บ DB (ไม่แตะยศ เพราะเซิร์ฟรองไม่มีระบบยศ)
    """
    uid = member.id
    role_names = _names(getattr(member, "roles", []))
    race, cls = detect_from_roles(role_names)

    # มียศจริง → ยศคือความจริง ซิงก์ลง DB ให้เซิร์ฟรองใช้ต่อ
    if race or cls:
        updates = {}
        if race and (player or {}).get("race") != race:
            updates["race"] = race
        if cls and (player or {}).get("class_name") != cls:
            updates["class_name"] = cls
        if updates:
            player_model.update_player_fields(uid, updates)
        return None

    if not on_main_server:
        # เซิร์ฟรอง: มีค่าใน DB อยู่แล้วก็ใช้ต่อ ไม่ต้องทำอะไร
        if (player or {}).get("race") and (player or {}).get("class_name"):
            return None
        new_race, new_class = roll_identity()
        player_model.update_player_fields(uid, {"race": new_race, "class_name": new_class})
        return (f"🎲 **โชคชะตากำหนดชะตากรรมของคุณ!**\n"
                f"🧬 เผ่าพันธุ์: **{new_race}**\n⚔️ คลาสอาชีพ: **{new_class}**\n"
                f"*(เข้าเซิร์ฟหลักเพื่อรับยศจริงและปลดล็อกระบบเต็ม)*")

    # เซิร์ฟหลักแต่ยังไม่มียศ → สุ่มใหม่ + แจกยศจริง
    new_race, new_class = roll_identity()
    player_model.update_player_fields(uid, {"race": new_race, "class_name": new_class})
    given = []
    for wanted in (new_race, new_class):
        role = next((r for r in member.guild.roles if r.name == wanted), None)
        if role:
            try:
                await member.add_roles(role, reason="สุ่มเผ่า/คลาสอัตโนมัติ (P8)")
                given.append(wanted)
            except Exception:
                pass
    note = "✅ ได้รับยศจริงในเซิร์ฟแล้ว!" if len(given) == 2 else "⚠️ บางยศยังแจกไม่ได้ (แจ้งแอดมินตรวจสิทธิ์บอท/ชื่อยศ)"
    return (f"🎲 **พิธีกำเนิดในโลกหลัก!**\n"
            f"🧬 เผ่าพันธุ์: **{new_race}**\n⚔️ คลาสอาชีพ: **{new_class}**\n{note}")
