"""🧓 NPC — พ่อค้าเดินทาง / นักปราชญ์ปริศนา (เฟส 10c)

สเปกข้อ 3.6: สลับเทิร์นให้แต่ละคนเลือก
  💬 คุย — ยืม `adventure_core.npc_talk` ของเกมหลักทั้งดุ้น (ของขวัญ/ยัดขาย/ไม่มีอะไร)
  🛒 ซื้อของ — ยืม `core.services.items.buy_item_for` ตัวเดียวกับร้านค้าในดิสและบนเว็บ

⚠️ **ไม่ตั้งราคาเองและไม่สุ่มผลเอง** — ทั้งสองอย่างมีของกลางอยู่แล้ว
   ตั้งใหม่เมื่อไหร่ = ปรับที่ Panel แล้วสองโหมดไม่ตรงกัน

⚠️ NPC ล้างสถานะติดลบให้ ตามที่เกมหลักกำหนดไว้ใน `cleanse_on` ของแต่ละสถานะ
"""
import random

from bot import adventure_core, config_loader
from bot.games.party import encounter

# ของที่พ่อค้าเร่หยิบมาขาย — สุ่มจากของที่ซื้อได้จริงในเกม
STOCK_SIZE = 3


def start(members, rng=None):
    rng = rng or random.Random()
    ev = encounter.new_state("npc", members, art="npc")
    ev["stock"] = _stock(rng)
    encounter.say(ev, "🧓 ชายชราสะพายเป้ใบใหญ่โบกมือทักจากข้างทาง")
    return ev


def _stock(rng):
    """ของในเป้พ่อค้า — เอาจากของที่ `purchasable` จริงในคอนฟิกเกมหลัก

    ⚠️ ครอบทั้งก้อน เพราะคอนฟิกแก้ได้จาก Panel — พิมพ์ราคาเป็นตัวหนังสือ
       แล้วปาร์ตี้ทั้งห้องค้างเพราะเปิดฉาก NPC ไม่ได้ ไม่คุ้มกัน
       ไม่มีของขายก็ยังคุยได้ เหตุการณ์ไม่พัง
    """
    try:
        items = config_loader.get_all_items() or {}
        pool = sorted(((str(i), d) for i, d in items.items()
                       if d.get("purchasable", True) and int(d.get("buy") or 0) > 0),
                      key=lambda x: x[0])
        if not pool:
            return []
        return [{"id": i, "name": d.get("name", i), "price": int(d["buy"])}
                for i, d in rng.sample(pool, min(STOCK_SIZE, len(pool)))]
    except Exception as e:
        print(f"⚠️ [party] จัดของในเป้พ่อค้าไม่ได้: {e}")
        return []


def options(ev, unit_id, is_host=False):
    out = [{"key": "talk", "name": "💬 คุยด้วย", "hint": "อาจได้ของขวัญหรือคำใบ้"}]
    for it in ev.get("stock") or []:
        out.append({"key": f"buy:{it['id']}",
                    "name": f"🛒 {it['name']} ({it['price']:,})",
                    "hint": "ซื้อด้วยเงินสดที่พกติดตัว"})
    # ⚠️ ห้ามใช้คีย์ "leave" — ชนกับคำสั่ง "ออกจากปาร์ตี้" ของ API
    out.append({"key": "bye", "name": "🚶 ลาไปก่อน", "hint": "ไม่เอาอะไร"})
    return out


def act(ev, unit_id, action, rng=None, is_host=False):
    """คนนี้เลือกทำอะไรกับ NPC — คืน (ok, ข้อความผิดพลาด|None)"""
    if ev.get("over"):
        return False, "เหตุการณ์นี้จบไปแล้ว"
    if encounter.current(ev) != unit_id:
        return False, "ยังไม่ถึงตาคุณ"
    m = encounter.member(ev, unit_id)
    if not m or m.get("done"):
        return False, "คุณเลือกไปแล้ว"

    rng = rng or random.Random()
    if action == "bye":
        m["done"], m["choice"] = True, "bye"
        encounter.say(ev, f"🚶 {m['name']} โบกมือลาแล้วเดินต่อ")
    elif action == "talk":
        encounter.say(ev, _talk(m, rng))
        m["done"], m["choice"] = True, "talk"
    elif str(action).startswith("buy:"):
        ok, note = _buy(ev, m, str(action)[4:])
        encounter.say(ev, note)
        if not ok:
            return True, None          # ซื้อไม่สำเร็จก็ยังเลือกใหม่ได้
        m["done"], m["choice"] = True, "buy"
    else:
        return False, "ไม่รู้จักคำสั่งนี้"

    if encounter.all_done(ev):
        ev["over"] = True
    return True, None


def _talk(m, rng):
    """คุยกับ NPC — ยืมผลลัพธ์ของเกมหลักทั้งดุ้น"""
    uid = m.get("uid")
    if not uid:
        return f"💤 {m['name']} คุยไม่รู้เรื่อง"
    try:
        got = adventure_core.npc_talk(int(uid), rng) or {}
        return f"🧓 {m['name']}: " + str(got.get("text") or "คุยกันเฉย ๆ")
    except Exception as e:
        print(f"⚠️ [party] คุยกับ NPC ไม่ได้ uid={uid}: {e}")
        return f"💤 {m['name']} คุยกับชายชราอยู่พักหนึ่ง"


def _buy(ev, m, item_id):
    """ซื้อของจากพ่อค้า — ใช้ตัวกลางเดียวกับร้านค้าในเกม"""
    uid = m.get("uid")
    if not uid:
        return False, "ซื้อไม่ได้"
    if not any(str(it["id"]) == str(item_id) for it in ev.get("stock") or []):
        return False, "🧓 ชายชราส่ายหน้า — ของชิ้นนี้ไม่มีในเป้"
    from core.services import items as _items
    try:
        ok, note = _items.buy_item_for(int(uid), item_id, 1)
        return bool(ok), f"{m['name']} — {note}"
    except Exception as e:
        print(f"⚠️ [party] ซื้อของจาก NPC ไม่ได้ uid={uid}: {e}")
        return False, "🧓 ซื้อขายไม่สำเร็จ"


def bot_pick(ev, unit_id):
    """บอทเลือกแทนคน AFK — คุยเฉย ๆ ไม่ใช้เงินของคนอื่น"""
    return "talk"
