# license_server/api_web/adventure.py
"""ผจญภัยบนเว็บ (เว็บเกม เฟส 5.4) + กระดานทอยเต๋ารายวัน (ย้ายจาก web_api.py 09-02)

ทุกผลออกที่เซิร์ฟเวอร์ด้วย adventure_core ตัวเดียวกับ !play ในดิส
เบราว์เซอร์แค่เอาไปวาดฉากกับเล่นอนิเมชัน — ไม่รู้กฎเกมอะไรเลย

เหตุการณ์ที่เว็บยังเล่นเองไม่ได้ (มอนสเตอร์ / NPC / อีเวนต์พิเศษ) จะ "ไม่ล็อกสถานะ"
ผู้เล่นจึงไม่มีทางค้างจนเล่นไม่ได้ทั้งสองแพลตฟอร์ม — รอเฟส 5.5-5.6 มาเปิดเพิ่ม
"""
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from license_server.api_web.deps import _money_now, _user_lock, require_player

router = APIRouter()

_WEB_PLAYABLE = {                     # เหตุการณ์ -> สถานะที่ล็อกไว้ระหว่างรอผู้เล่นเลือก
    "village": "village", "treasure": "treasure_choice", "dungeon": "dungeon_choice",
    "trap": "trap_defense", "travel": "travel_choice", "mugging": "mugging",
    "npc": "npc_choice", "special": "special_choice", "monster": "fighting",
}
_WEB_INSTANT = ("calm", "bank_robbery")     # จบในตัว ไม่ต้องเลือกอะไร

# สถานะที่ถือว่า "ค้างได้แต่ปลดได้" — ตรงกับ lock_states ของ !play ในดิส
# ปลดเฉพาะตอนไม่มีเหตุการณ์รออยู่จริง ไม่งั้นจะกลายเป็นช่องให้รีเฟรชหนีกับดัก
_STALE_STATES = ("village", "npc_choice", "treasure_choice", "dungeon_choice",
                 "trap_defense", "shopping", "travel_choice", "special_choice")


def _is_rogue(player):
    return (player.get("class_name") or "") == "Rogue"


def _start_ambush_fight(uid, text):
    """เข้าไฟต์กลางคันจากเหตุการณ์อื่น (มอนปลอมตัวฉีกคราบ) — เกิดมอนแล้วส่งการ์ดให้เว็บวาด"""
    from bot import adventure_core
    data = adventure_core.spawn_monster(uid, ())
    adventure_core.set_pending(uid, "monster", data)
    return {"text": text, "pending": "monster", "monster": _monster_card(data),
            "money": _money_now(uid)}


def _finish_special(uid, out, outcome, died):
    """ปิดท้ายอีเวนต์พิเศษ — ตาย / ลากเข้าไฟต์ / จบเฉย ๆ

    กติกาชุดเดียวกับ SpecialEventView._finish() ในดิส: ถ้า outcome สั่ง start_fight
    ต้องเกิดมอนแล้วเข้าไฟต์ทันที ไม่ใช่ปล่อยผ่าน
    """
    from bot import adventure_core
    from bot.models import player_model

    if died:
        player_model.update_player_fields(uid, {"current_state": "dead", "last_event": "none"})
        adventure_core.clear_pending(uid)
        out["died"] = True
        return out

    if outcome.get("start_fight"):
        data = adventure_core.spawn_monster(uid, ())
        player_model.update_player_fields(uid, {"current_state": "fighting", "last_event": "none"})
        adventure_core.set_pending(uid, "monster", data)
        out["pending"] = "monster"
        out["monster"] = _monster_card(data)
        out["text"] += "\n👹 **ศัตรูไม่ให้เวลาคุณหายใจ — เข้าสู่การต่อสู้ทันที!**"
        return out

    player_model.update_player_fields(uid, {"current_state": "idle", "last_event": "none"})
    adventure_core.clear_pending(uid)
    return out


@router.post("/adventure/walk")
def adventure_walk(request: Request, steps: int = 1):
    """เดินหนึ่งก้าว — ตรรกะเดียวกับปุ่ม 🧭 ในดิสทุกบรรทัด

    steps>1 = ⏩ เดินเร็ว: เดินรวดจนเจอเหตุการณ์ที่ต้องตัดสินใจจริง
    (มอน/ดันเจี้ยน/โจร/หมู่บ้าน/กับดัก/พาหนะข้ามทวีป) — กติกาเดียวกับปุ่ม ⏩ ในดิส
    """
    uid = int(require_player(request)["uid"])
    from bot import adventure_core, game_modifiers, robbery
    from bot.models import player_model

    with _user_lock(uid):
        # หน้าต่างเหตุการณ์ในดิสมี timeout ของมันเอง เว็บไม่มี จึงต้องหมดอายุเองก่อนเดินก้าวใหม่
        expired_note = adventure_core.expire_pending(uid)

        # สถานะค้างที่ "ไม่มีเหตุการณ์รออยู่จริง" = ของเก่าตกค้าง ปลดให้เหมือนที่ !play ทำ
        # (เช่นฟื้นคืนชีพเสร็จแล้วสถานะเป็น village — ถ้าไม่ปลด ผู้เล่นเดินต่อไม่ได้เลย)
        _p = player_model.get_player(uid) or {}
        if _p.get("current_state") in _STALE_STATES and not adventure_core.get_pending(uid)[0]:
            player_model.update_player_field(uid, "current_state", "idle")

        player = player_model.get_player(uid)
        if not player:
            raise HTTPException(400, "ยังไม่มีตัวละคร — ทักบอทในดิสคอร์ดก่อนหนึ่งครั้ง")
        if player["current_state"] != "idle":
            pending, data = adventure_core.get_pending(uid)
            raise HTTPException(409, f"คุณกำลังติดเหตุการณ์อื่นอยู่ ({pending or player['current_state']})")

        elements = game_modifiers.resolve_player_elements(
            [player.get("race") or "", player.get("class_name") or ""])
        # ⏩ เดินเร็ว: เดินไปเรื่อย ๆ จน "เจอเหตุการณ์ที่ต้องหยุด" เท่านั้น
        # ถ้าหลุดออกมาโดยยังไม่เจอ (เลือดต่ำ/ชนเพดานกันวน) ต้องไม่เอาเหตุการณ์ที่ข้ามมาโชว์
        # ไม่งั้นเดินเร็วจะไปโผล่หีบ/NPC/อีเวนต์พิเศษ ซึ่งผิดกติกา
        fast = int(steps or 1) > 1
        budget = adventure_core.FAST_WALK_MAX if fast else 1
        notes, walked, stopped = [], 0, not fast
        while True:
            pre = adventure_core.step_prelude(uid, player, elements)
            notes.extend(pre["notes"])
            walked += 1
            if pre["dead"]:
                return {"event": "death", "notes": notes, "walked": walked,
                        "text": "💀 คุณล้มลงกลางทาง... พิษกัดกินร่างกายจนหมดสติ"}

            player, statuses, mods = pre["player"], pre["statuses"], pre["mods"]
            event, special, dg_steps = adventure_core.decide_event(
                uid, player, statuses, mods, pre["dg_steps"], pre["last_evt"], pre["cooldown"])
            adventure_core.commit_event(uid, event, pre["last_evt"])

            if not fast:
                break
            if adventure_core.fast_walk_stops_here(event, pre["last_evt"]):
                stopped = True
                break
            if player.get("hp", 0) <= player.get("max_hp", 100) * 0.3:
                notes.append("⚠️ **เลือดต่ำกว่า 30% — หยุดเดินเร็วเพื่อความปลอดภัย** (กินยาก่อนไปต่อ!)")
                break
            if walked >= budget:
                break
            player = player_model.get_player(uid) or player

        if fast and not stopped:
            # เดินมาแล้วแต่ยังไม่เจออะไรที่ต้องหยุด — จบแบบไม่มีเหตุการณ์ (ไม่ล็อกสถานะ)
            player_model.update_player_field(uid, "current_state", "idle")
            return {"event": "fastwalk", "notes": notes, "walked": walked, "fast": True,
                    "continent": player.get("continent") or "main", "playable": True,
                    "pending": None,
                    "text": f"⏩ **เดินเร็วมาแล้ว {walked} ก้าว** — ยังไม่เจออะไรที่ต้องหยุด "
                            "กดเดินต่อได้เลย"} | {"money": _money_now(uid)}

        if expired_note:
            notes.insert(0, expired_note)

        out = {"event": event, "notes": notes, "continent": player.get("continent") or "main",
               "dungeon_steps": dg_steps, "cooldown": pre["cooldown"],
               "walked": walked, "fast": fast,   # เดินมากี่ก้าวก่อนจะเจออันนี้
               "playable": True,      # เว็บจัดการเหตุการณ์นี้เองได้ไหม
               "pending": None}       # ค้างรอผู้เล่นเลือก (None = จบในก้าวเดียว)

        if event == "calm":
            # 🧘 ไม่มีอะไรเกิดขึ้น = ได้พักหายใจ คืนเม็ดคริสตัลให้ (เต็มแล้วไม่ได้อะไร)
            mana_note, _left = adventure_core.calm_bonus(uid, player)
            out["text"] = game_modifiers.pick_calm_text() + ("\n" + mana_note if mana_note else "")
        elif event == "bank_robbery":
            r = robbery.resolve_bank_robbery(uid, player)
            out["text"] = (f"🏦💥 **โจรปล้นธนาคาร!** แก๊งโจรมือโปรเจาะตู้นิรภัยสาขาที่คุณฝากเงินไว้!\n"
                           f"เงินฝากหายไป `{r['lost']:,}` ทอง — เหลือในบัญชี `{r['left']:,}` ทอง{r['theft']}\n"
                           f"*(กันได้ด้วย 🪪 บัตรประกัน — หาซื้อที่ร้านค้าประจำหมู่บ้าน)*")
        elif event == "npc" and adventure_core.npc_disguise(player)[0]:
            # 🎭 สัปดาห์ธีม Masquerade — NPC อาจฉีกคราบเป็นมอน ตัดสินตอนนี้แล้วเก็บไว้ฝั่งเซิร์ฟเวอร์
            # (ห้ามส่งออกไปให้เบราว์เซอร์รู้ ไม่งั้นเปิดดูก็รู้ว่าตัวไหนปลอม)
            masq_cfg, disguised = adventure_core.npc_disguise(player)
            fee = int(masq_cfg.get("inspect_fee", 1500))
            data = {"disguised": disguised, "fee": fee}
            out["encounter"] = {"masquerade": True, "inspect_fee": fee}
            out["text"] = ("🧓 นักเดินทางพเนจรนั่งอยู่ข้างกองไฟ... "
                           "🎭 *สัปดาห์นี้มีธีมปลอมตัว — จ่ายเงินตรวจตัวตนก่อนก็ได้*")
            player_model.update_player_field(uid, "current_state", _WEB_PLAYABLE["npc"])
            adventure_core.set_pending(uid, "npc", data)
            out["pending"] = "npc"
        elif event == "special" and special.get("template") == "instant":
            # ไม่มีสิทธิ์เลือก — จ่ายผลทันทีเหมือนในดิส (เช่น งานเลี้ยงบรรพชน)
            outcome = adventure_core.resolve_instant_special(special)
            lines, died = adventure_core.execute_special_outcome(uid, outcome)
            out["text"] = "\n".join(
                [special.get("intro", "✨ มีบางอย่างเกิดขึ้นตรงหน้าคุณ...")] + lines)
            _finish_special(uid, out, outcome, died)
        elif event in _WEB_PLAYABLE:
            data = {}
            if event == "special":
                data = special
                out["text"] = special.get("intro", "✨ มีบางอย่างเกิดขึ้นตรงหน้าคุณ...")
                out["choices"] = ([c["label"] for c in special.get("choices", [])]
                                  if special.get("template") == "choice" else [])
            elif event == "monster":
                data = adventure_core.spawn_monster(uid, ())
                out["monster"] = _monster_card(data)
                out["text"] = "👹 มีเงาปริศนาพุ่งออกมากระโจนขวางทางคุณ!"
            elif event == "npc":
                out["text"] = "🧓 คุณเจอนักเดินทางพเนจร (NPC) นั่งอยู่ข้างกองไฟ"
            elif event == "travel":
                data = game_modifiers.roll_travel_encounter(player.get("cash", 0))
                out["encounter"] = data
                out["text"] = (f"🧭 ระหว่างทาง... **{data['label']}** ปรากฏขึ้นตรงหน้าคุณ!\n"
                               f"💰 ค่าโดยสาร: `{data['fare']:,}` ทอง (จ่ายจากเงินสดในกระเป๋า)")
            elif event == "mugging":
                total = int(player.get("cash", 0) or 0) + int(player.get("bank", 0) or 0)
                out["win_pct"] = robbery.mug_win_chance(total)
                out["text"] = (f"🥷 **โดนดักปล้น!** โจรถือมีดโผล่จากพุ่มไม้ "
                               f"จ้องถุงทอง `{player.get('cash', 0):,}` ทองของคุณ! "
                               f"*(โอกาสชนะ {out['win_pct']}% — เงินยิ่งหนักยิ่งถ่วงแข้งขา)*")
            else:
                out["text"] = {
                    "village": "🏡 คุณเดินทางมาพบ **'หมู่บ้านอุ่นใจ'**",
                    "treasure": mods["theme_texts"].get("treasure", "📦 คุณพบ **'หีบสมบัติปริศนาลงอักขระโบราณ'**"),
                    "dungeon": "💀 คุณส่องเห็น **'ช่องอุโมงค์ถ้ำใต้พิภพ (Dungeon)'**",
                    "trap": mods["theme_texts"].get("trap", "⚠️ *แก๊ก!* คุณพลาดก้าวขาไปเกี่ยวสายสลิง **'กับดักโบราณ'** เข้าให้แล้ว!"),
                }[event]
            player_model.update_player_field(uid, "current_state", _WEB_PLAYABLE[event])
            adventure_core.set_pending(uid, event, data)
            out["pending"] = event
        else:
            # มอนสเตอร์ / NPC / อีเวนต์พิเศษ — ยังไม่เปิดบนเว็บ ปล่อยสถานะ idle ไว้ ห้ามล็อก
            out["playable"] = False
            out["text"] = "🌫️ มีบางอย่างเคลื่อนไหวอยู่ในเงา... แต่คุณเดินผ่านไปเงียบ ๆ *(เหตุการณ์นี้ยังเล่นได้เฉพาะในดิสคอร์ด)*"

    return out | {"money": _money_now(uid)}


class ActBody(BaseModel):
    action: str = ""


@router.post("/adventure/act")
def adventure_act(body: ActBody, request: Request):
    """ตอบเหตุการณ์ที่ค้างอยู่ — ปุ่มบนเว็บส่ง action มาที่นี่ตัวเดียว"""
    uid = int(require_player(request)["uid"])
    from bot import adventure_core, robbery
    from bot.models import player_model

    with _user_lock(uid):
        event, data = adventure_core.get_pending(uid)
        if not event:
            raise HTTPException(409, "ไม่มีเหตุการณ์ค้างอยู่")
        player = player_model.get_player(uid) or {}
        # กันกดซ้ำ: สถานะต้องยังตรงกับเหตุการณ์ที่ค้างอยู่จริง
        # (ถ้าไม่เช็ค แล้วมีอะไรปลดสถานะไปก่อน จะเปิดหีบ/พักแรมซ้ำได้ฟรี ๆ)
        expected = _WEB_PLAYABLE.get("npc" if event == "npc_quest" else event)
        if player.get("current_state") != expected:
            adventure_core.clear_pending(uid)
            raise HTTPException(409, "เหตุการณ์นี้จบไปแล้ว — กดออกเดินทางใหม่ได้เลย")
        rogue = _is_rogue(player)

        if event == "village":
            r = adventure_core.resolve_village(uid, body.action)
        elif event == "treasure":
            r = adventure_core.resolve_treasure(uid, body.action, rogue)
        elif event == "dungeon":
            r = adventure_core.resolve_dungeon(uid, body.action)
        elif event == "trap":
            r = adventure_core.resolve_trap(uid, rogue)
            # หน้าตากับดักต่างกันตามทวีป — ฝั่งเซิร์ฟเวอร์เป็นคนบอก เบราว์เซอร์แค่วาดตาม
            r["fx"] = {"kind": player.get("continent") or "main", "hit": not r.get("dodged")}
            if "roll" in r:      # ทอยต่ำกว่าค่าหลบของเกราะ = รอด (กติกาสวนทางกับเต๋าไฟต์)
                r["roll"] = {"player_roll": r["roll"], "monster_roll": r["eva"],
                             "labels": ["🎲 ทอยหลบ", "🛡️ ค่าเกราะ"], "win": r["dodged"],
                             "verdict": "หลบพ้น!" if r["dodged"] else "โดนเต็ม ๆ",
                             "player_parts": ["ทอยได้"], "monster_parts": ["ต้องทอยไม่เกินนี้"]}
        elif event == "travel":
            r = adventure_core.resolve_travel(uid, data, body.action)
        elif event == "npc":
            # 🎭 สัปดาห์ปลอมตัว: เข้าไปคุย/ฟังเควสกับตัวปลอม = โดนซุ่มตีก่อนแล้วเข้าไฟต์
            masq = bool((data or {}).get("disguised"))
            if body.action == "inspect":
                r = adventure_core.npc_inspect(uid, masq, (data or {}).get("fee", 1500))
                if not r["ok"]:                       # เงินไม่พอ ยังยืนอยู่ที่เดิม กดใหม่ได้
                    raise HTTPException(400, r["text"])
                if not r["start_fight"]:              # เป็นตัวจริง — คุยต่อได้ ยังไม่จบเหตุการณ์
                    return {"text": r["text"], "pending": "npc",
                            "encounter": {"masquerade": False}, "money": _money_now(uid)}
                return _start_ambush_fight(uid, r["text"])
            if masq and body.action in ("talk", "quest"):
                a = adventure_core.npc_ambush(uid)
                if a["died"]:
                    adventure_core.clear_pending(uid)
                    return {"text": a["text"], "died": True, "money": _money_now(uid)}
                return _start_ambush_fight(uid, a["text"])
            if body.action == "talk":
                r = adventure_core.npc_talk(uid)
            elif body.action == "quest":
                offer = adventure_core.npc_quest_offer(uid)
                if not offer:
                    r = {"text": "🧓 NPC มองกระเป๋าที่ว่างเปล่าของคุณแล้วส่ายหัว "
                                 "'เจ้าไม่มีสิ่งใดที่ข้าต้องการเลย...'"}
                else:
                    # ข้อเสนอเป็นขั้นที่สอง — เก็บไว้ฝั่งเซิร์ฟเวอร์ ห้ามให้เบราว์เซอร์ส่งกลับมาเอง
                    adventure_core.set_pending(uid, "npc_quest", offer)
                    return {"text": offer["text"], "pending": "npc_quest",
                            "money": _money_now(uid)}
            else:
                adventure_core._done(uid, "npc")
                r = {"text": "🤫 คุณแกล้งทำเป็นมองไม่เห็นและเดินผ่าน NPC ไปอย่างรวดเร็ว"}
        elif event == "monster":
            return _fight_action(uid, data, body.action)
        elif event == "npc_quest":
            r = adventure_core.npc_quest_settle(uid, data, body.action == "accept")
        elif event == "special":
            outcome, prefix = adventure_core.special_pick_outcome(data, body.action)
            lines, died = adventure_core.execute_special_outcome(uid, outcome)
            if prefix:
                lines.insert(0, prefix)
            r = {"text": "\n".join(lines) or "…ไม่มีอะไรเกิดขึ้น", "died": died}
            _finish_special(uid, r, outcome, died)
            if r.get("pending") == "monster":
                # ลากเข้าไฟต์ต่อทันที — ห้ามให้ clear_pending ท้ายฟังก์ชันมาล้างมอนทิ้ง
                return r | {"money": _money_now(uid)}
        elif event == "mugging":
            m = robbery.resolve_mugging(uid, body.action)
            if body.action == "flee":
                r = {"text": f"🏃💨 คุณโยนถุงทองสกัดโจรแล้ววิ่งสุดชีวิต — เสีย `{m['lost']:,}` ทอง "
                             f"(เหลือ `{m['cash']:,}`){m['theft']}"}
            elif m["won"]:
                r = {"text": f"⚔️🏆 **คุณสู้จนโจรเผ่นหนี!** ริบของกลางจากโจรได้ `{m['gain']:,}` ทอง "
                             f"(ติดตัวตอนนี้ `{m['cash']:,}`){m['theft']}"}
            else:
                r = {"text": f"⚔️💀 **เงินถ่วงแข้งขาจนสู้ไม่ไหว...** "
                             f"โจรกวาดเงินติดตัวไปหมด `{m['lost']:,}` ทอง!{m['theft']}"}
            r |= m
            if m.get("roll"):
                r["roll"] = {"player_roll": m["roll"], "monster_roll": m["win_pct"],
                             "labels": ["🎲 ทอยสู้", "🥷 โอกาสชนะ"], "win": m["won"],
                             "verdict": "ชนะโจร!" if m["won"] else "สู้ไม่ไหว...",
                             "player_parts": ["ทอยได้"], "monster_parts": ["ต้องทอยไม่เกินนี้"]}
        else:
            raise HTTPException(400, f"เหตุการณ์ {event} ยังเล่นบนเว็บไม่ได้")

        if r.get("error"):                     # เงินไม่พอ ฯลฯ — ยังค้างอยู่ที่เดิม กดใหม่ได้
            raise HTTPException(400, r["error"])
        adventure_core.clear_pending(uid)

    return r | {"money": _money_now(uid)}


@router.get("/adventure/state")
def adventure_state(request: Request):
    """เหตุการณ์ที่ค้างอยู่ — เว็บเรียกตอนเปิดหน้า/รีเฟรช จะได้กลับมาเล่นต่อจุดเดิมได้

    ไม่มีอันนี้ = รีเฟรชแล้วสถานะค้างจนเล่นไม่ได้ทั้งเว็บและดิส
    """
    uid = int(require_player(request)["uid"])
    from bot import adventure_core
    from bot.models import player_model

    adventure_core.expire_pending(uid)
    event, data = adventure_core.get_pending(uid)
    state = (player_model.get_player(uid) or {}).get("current_state", "idle")
    if not event:
        return {"pending": None, "state": state}
    if event == "npc" and isinstance(data, dict) and "disguised" in data:
        # 🎭 ห้ามส่งคำเฉลยออกไป — เปิด devtools ดูก็รู้ทันทีว่าตัวไหนปลอม
        data = {"masquerade": True, "inspect_fee": data.get("fee", 1500)}
    return {"pending": event, "data": data, "state": state}


def _monster_card(f):
    """ข้อมูลมอนที่หน้าจอต้องใช้ — ชื่อ แรงค์ ธาตุ หลอดเลือด (ไม่ส่งสถานะภายในออกไป)"""
    return {"name": f["stats"].get("name", "มอนสเตอร์"), "rank": f["rank"],
            "element": f.get("element"), "hp": f["hp"], "hp_max": f.get("hp_max", f["hp"]),
            "turn": f.get("turn", 1)}


def _fight_action(uid, fight, action):
    """หนึ่งการกระทำในไฟต์บนเว็บ — โจมตี / สกิล / หนี

    ผลทั้งหมดออกที่ adventure_core ตัวเดียวกับปุ่มในดิส เบราว์เซอร์แค่เอาไปเล่นอนิเมชัน
    ยศแรงค์ที่เลื่อนขั้นบนเว็บให้เองไม่ได้ — บอทจะซิงก์ให้ตอนผู้เล่นเข้าเซิร์ฟดิสครั้งถัดไป
    """
    from bot import adventure_core
    from bot.models import player_model

    if action == "flee":
        r = adventure_core.fight_flee(uid, fight)
        if r["outcome"] == "blocked":
            raise HTTPException(400, r["text"])

        # 🎲 โชว์เต๋าที่ทอยจริงเสมอ — เดิมหนีแล้วไม่เห็นอะไรเลย ไม่รู้ว่าเฉียดหรือห่าง
        # (กติกาสวนทางกับเต๋าไฟต์: ทอย "ไม่เกิน" ค่าโอกาสหนี = รอด แบบเดียวกับกับดัก)
        out = {"text": r["text"], "money": _money_now(uid)}
        if "roll" in r:
            fled = r["outcome"] == "fled"
            out["roll"] = {"player_roll": r["roll"], "monster_roll": r["need"],
                           "labels": ["🎲 ทอยหนี", "🏃 โอกาสรอด"], "win": fled,
                           "verdict": "หนีรอด!" if fled else "หนีไม่พ้น!",
                           "player_parts": ["ทอยได้"], "monster_parts": ["ต้องทอยไม่เกินนี้"]}

        if r["outcome"] == "hit":                       # หนีไม่พ้น สู้ต่อ
            adventure_core.set_pending(uid, "monster", r["fight"])
            return out | {"pending": "monster", "outcome": "continue",
                          "monster": _monster_card(r["fight"])}
        adventure_core.clear_pending(uid)
        return out | {"outcome": r["outcome"]}

    skill = action if action.startswith("skill_") else None
    if action != "attack" and not skill:
        raise HTTPException(400, "ไม่รู้จักแอคชั่นนี้")

    t = adventure_core.fight_turn(uid, fight, (), skill)
    if t["outcome"] in ("no_player", "no_mana"):     # ไม่กินเทิร์น กดปุ่มอื่นต่อได้เลย
        raise HTTPException(400, t["text"])

    out = {"outcome": t["outcome"], "monster": _monster_card(t.get("fight", fight)),
           "log": (t.get("skill_log", "") + t.get("combat_log", "")).strip(),
           "roll": {"player_roll": t.get("player_roll", 0), "monster_roll": t.get("monster_roll", 0),
                    "player_parts": t.get("player_parts", []),
                    "monster_parts": t.get("monster_parts", [])},
           "damage_to_monster": t.get("damage_to_monster", 0),
           "damage_to_player": t.get("damage_to_player", 0),
           "healed": t.get("healed", 0), "mana": t.get("mana"),
           "mana_spent": t.get("mana_spent", 0),
           "player_hp": t.get("player_hp", 0)}

    if t["outcome"] in ("monster_fled", "player_fled"):
        adventure_core.clear_pending(uid)
        out["text"] = t["text"]
        return out | {"money": _money_now(uid)}

    if t["outcome"] == "win":
        # carry = ผลของเทิร์นที่ล้มมอน (เลือดที่เพิ่งฮีล/เกราะที่เพิ่งสึก) ต้องเขียนด้วย
        v = adventure_core.fight_victory(uid, t["fight"], carry=t.get("db_updates"))
        adventure_core.clear_pending(uid)
        # โชว์ผลเทิร์นสุดท้ายก่อนสรุปชัยชนะ — ผู้เล่นต้องเห็นว่าตีไปเท่าไหร่ถึงล้ม
        # (ดิสโชว์อยู่ในช่อง "📜 เทิร์นสุดท้าย" ของ embed ชนะ เว็บเคยข้ามไปเลย)
        out["text"] = ((out["log"] + "\n" if out["log"] else "")
                       + f"🏅 **โค่น {t['fight']['stats'].get('name', 'มอนสเตอร์')} สำเร็จ!**\n"
                       f"💰 **+{v['reward']:,}** ทอง   🔷 **+{v['exp']:,}** EXP"
                       + ("\n✨🎉 **LEVEL UP!!** เลเวลเพิ่มเป็น Lv." + str(v["level"]) if v["level_up"] else "")
                       + v["rank_msg"] + v["drops"] + v["battle_end_log"])
        out["reward"] = {"gold": v["reward"], "exp": v["exp"], "level": v["level"],
                         "level_up": v["level_up"]}
        out["got_item"] = bool(v.get("drops"))    # มอนดรอปของ — หน้าเว็บจะได้เล่นเสียงเก็บของ
        return out | {"money": _money_now(uid)}

    if t["outcome"] == "lose":
        player_model.update_player_fields(uid, dict(t.get("db_updates") or {}, current_state="dead"))
        adventure_core.clear_pending(uid)
        out["text"] = "💀 **คุณหมดสติลงกลางสนามรบ...** กดฟื้นคืนชีพเพื่อกลับหมู่บ้าน"
        return out | {"money": _money_now(uid)}

    player_model.update_player_fields(uid, t.get("db_updates") or {})
    adventure_core.set_pending(uid, "monster", t["fight"])
    out["pending"] = "monster"
    out["text"] = out["log"] or "⚔️ ยังไม่มีใครล้ม — สู้ต่อ!"
    return out | {"money": _money_now(uid)}


@router.post("/adventure/respawn")
def adventure_respawn(request: Request):
    """💀 ฟื้นคืนชีพกลับหมู่บ้าน — ตรรกะเดียวกับปุ่มฟื้นในดิส

    ตายบนเว็บแล้วเดิมไม่มีทางฟื้น ค้างที่สถานะ dead จนต้องไปกด !play ในดิส
    """
    uid = int(require_player(request)["uid"])
    from bot import adventure_core
    from bot.models import player_model

    with _user_lock(uid):
        player = player_model.get_player(uid) or {}
        if player.get("current_state") != "dead" and player.get("hp", 1) > 0:
            raise HTTPException(400, "ยังไม่ได้หมดสติ ไม่ต้องฟื้น")
        r = adventure_core.respawn(uid)
        if not r:
            raise HTTPException(400, "ไม่พบข้อมูลตัวละคร")
        # ฟื้นแล้วยืนอยู่ในหมู่บ้านจริง ๆ — เปิดเมนูหมู่บ้านให้เลย จะได้พักแรมฟื้นเลือดต่อได้
        # (เกิดใหม่ได้แค่ 30% ของเลือดเต็ม ไม่ให้เมนูก็ต้องออกเดินทางทั้งที่เลือดน้อย)
        adventure_core.set_pending(uid, "village", {})

    return {"ok": True, "money": _money_now(uid), "hp": r["hp"], "fee": r["fee"],
            "pending": "village",
            "text": (f"🏥 **หมอผีประจำหมู่บ้านดึงวิญญาณคุณกลับมา**\n"
                     f"❤️ ฟื้นที่ `{r['hp']:,}/{r['max_hp']:,}` HP ({r['hp_pct']}% ของเลือดเต็ม)\n"
                     f"💰 ค่าทำพิธี `{r['fee']:,}` ทอง (เหลือ `{r['cash']:,}`)"
                     + (f"\n💀 ความคืบหน้าในดันเจี้ยนหายไป {r['lost_steps']} ตา"
                        if r["lost_steps"] else "")
                     + "\n💎 เม็ดคริสตัลเต็มอีกครั้ง")}


# ─────────────────────────────────────────────────────────────────────────────
# 🎲 กระดานทอยเต๋ารายวัน (เว็บเกม เฟส 8.4)
# โควตา 3 ครั้ง/วัน ใช้ร่วมกับ !board ในดิส — ทอยที่ไหนก็หักโควตาเดียวกัน
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/board")
def board_state(request: Request):
    """กระดานของสัปดาห์นี้ + ตำแหน่งหมาก + โควตาที่เหลือ (อ่านอย่างเดียว)"""
    uid = int(require_player(request)["uid"])
    from bot import dice_board
    return dice_board.state(uid)


@router.post("/board/roll")
def board_roll(request: Request):
    """ทอยหนึ่งครั้ง — โควตาถูกหักในจังหวะเดียวกับการทอย กดรัวไม่ได้ของเกิน"""
    uid = int(require_player(request)["uid"])
    from bot import dice_board
    with _user_lock(uid):
        ok, r = dice_board.roll(uid)
    if not ok:
        raise HTTPException(400, r["error"])
    return r | {"money": _money_now(uid)}
