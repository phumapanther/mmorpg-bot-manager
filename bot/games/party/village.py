"""🏡 หมู่บ้าน — พื้นที่ปลอดภัย พักฟื้นแบบสลับเทิร์น (เฟส 10b)

สเปกข้อ 3.2: สลับเทิร์นทีละคน กด "พักผ่อน" แล้วฟื้น 100% HP + MP

⚠️ **คิดค่านอนพักตามเกมหลัก** (`adventure_core.rest_cost` · ตั้งได้ที่ Panel)
   เจ้าของเกมเคาะ 2026-09-05 — สอดคล้องกับหมู่บ้านในโหมดเดี่ยว
   เงินไม่พอก็พักไม่ได้ ต้องเดินต่อทั้งที่เลือดน้อย

⚠️ ไฟล์นี้แตะฐานข้อมูลผู้เล่น (เลือด/เม็ด/เงิน) แต่ **ไม่รู้จักการวาดภาพ**
   ผลลัพธ์ออกไปเป็นข้อความใน `log` ให้หน้าเว็บเอาไปแสดงเอง
"""
from bot import adventure_core
from bot.games.party import encounter

ACTIONS = ("rest", "walk")


def start(members, rng=None):
    """เปิดฉากหมู่บ้าน — คืนสถานะเหตุการณ์"""
    ev = encounter.new_state("village", members, art="village")
    encounter.say(ev, "🏡 ปาร์ตี้เดินเข้าหมู่บ้านเล็ก ๆ กลิ่นซุปลอยมาจากโรงเตี๊ยม")
    return ev


def cost_for(uid):
    """ค่านอนพักของคนนี้ — สูตรเดียวกับหมู่บ้านในโหมดเดี่ยว"""
    from bot.models import player_model
    p = player_model.get_player(int(uid)) or {}
    return int(adventure_core.rest_cost(p))


def options(ev, unit_id, is_host=False):
    """ปุ่มที่คนนี้กดได้ — บอกราคาไปด้วยเลย ไม่ให้กดแล้วค่อยรู้"""
    m = encounter.member(ev, unit_id) or {}
    price = cost_for(m.get("uid") or 0) if m.get("uid") else 0
    return [
        {"key": "rest", "name": f"💤 พักผ่อน ({price:,} ทอง)",
         "hint": "ฟื้นเลือดกับเม็ดคริสตัลเต็ม"},
        {"key": "walk", "name": "🚶 เดินต่อ", "hint": "ไม่เสียเงิน แต่ไม่ได้ฟื้น"},
    ]


def act(ev, unit_id, action, rng=None, is_host=False):
    """คนนี้เลือกทำอะไร — คืน (ok, ข้อความผิดพลาด|None)

    🔒 ด่านเดียวที่ตัดสินว่าสั่งได้ไหม (ถึงตาจริงไหม · เลือกไปแล้วหรือยัง)
    """
    if ev.get("over"):
        return False, "เหตุการณ์นี้จบไปแล้ว"
    if action not in ACTIONS:
        return False, "ไม่รู้จักคำสั่งนี้"
    if encounter.current(ev) != unit_id:
        return False, "ยังไม่ถึงตาคุณ"

    m = encounter.member(ev, unit_id)
    if not m:
        return False, "คุณไม่ได้อยู่ในเหตุการณ์นี้"
    if m.get("done"):
        return False, "คุณเลือกไปแล้ว"

    if action == "walk":
        m["done"], m["choice"] = True, "walk"
        encounter.say(ev, f"🚶 {m['name']} เดินผ่านโรงเตี๊ยมไปเฉย ๆ")
        return True, None

    ok, note = _rest(m)
    m["done"], m["choice"] = True, "rest" if ok else "walk"
    encounter.say(ev, note)
    return True, None


def _rest(m):
    """จ่ายค่าห้องแล้วฟื้นเต็ม — เงินไม่พอก็พักไม่ได้ คืน (ฟื้นไหม, ข้อความ)"""
    from bot import mana as _mana
    from bot.games.party import room as _room
    from bot.models import player_model

    uid = int(m.get("uid") or 0)
    if not uid:
        return False, f"🚶 {m['name']} ไม่ได้พัก"
    p = player_model.get_player(uid) or {}
    price = int(adventure_core.rest_cost(p))
    cash = int(p.get("cash") or 0)
    if cash < price:
        return False, (f"💸 {m['name']} เงินไม่พอค่าห้อง "
                       f"(มี {cash:,} ต้องมี {price:,}) — เดินต่อทั้งที่เลือดน้อย")

    full = _room.gear_stats(p)[1]
    player_model.update_player_fields(uid, {"cash": cash - price, "hp": full})
    try:
        _mana.refill(uid)
    except Exception as e:
        print(f"⚠️ [party] เติมเม็ดที่หมู่บ้านไม่ได้ uid={uid}: {e}")
    m["hp"] = full
    m["hp_max"] = full
    return True, (f"💤 {m['name']} นอนพักจนเช้า ฟื้นเต็ม {full:,} เลือด "
                  f"(จ่าย {price:,} ทอง)")


def bot_pick(ev, unit_id):
    """บอทเลือกแทนคน AFK — เลือดไม่เต็มและเงินพอก็พัก ไม่งั้นเดินต่อ"""
    m = encounter.member(ev, unit_id) or {}
    if int(m.get("hp") or 0) >= int(m.get("hp_max") or 1):
        return "walk"
    uid = m.get("uid")
    if not uid:
        return "walk"
    from bot.models import player_model
    p = player_model.get_player(int(uid)) or {}
    return "rest" if int(p.get("cash") or 0) >= cost_for(uid) else "walk"
