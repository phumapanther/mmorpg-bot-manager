# license_server/api_web/misc.py
"""ข้อมูลเกมทั่วไป + คู่มือเกม (ย้ายจาก web_api.py 09-02)"""
from fastapi import APIRouter, Request

from license_server.api_web.deps import require_player

router = APIRouter()

# ── ข้อมูลเกม (อ่านจากข้อมูลเกมจริง — อัพเดทเกมแล้วเว็บตรงเสมอ) ──

_ELEMENT_DESC = {
    "fire": "สายบู๊ ตีแรงขึ้น 50%", "water": "ดูดเลือดคืน 35% ของดาเมจ",
    "earth": "ถึกอึด เลือดหนา 2 เท่า", "wind": "ไวเป็นพายุ โบนัสแต้มเต๋า",
    "wood": "รากพันธนาการล็อกเต๋าศัตรู", "dark": "คลั่งตั้งแต่เทิร์นแรก",
    "light": "หายากสุด ล้มได้ทองมหาศาล",
}


@router.get("/gamedata")
def gamedata():
    from bot.game_data import CONTINENTS, WEEKLY_THEMES
    from bot.game_modifiers import ELEMENTS
    from bot import config_loader

    continents = []
    for key, c in CONTINENTS.items():
        pool = c.get("mods", {}).get("monster_pool", {})
        monsters = [{"name": n, "rank": rank} for rank, names in pool.items() for n in names]
        continents.append({"key": key, "label": c["label"],
                           "arrival_text": c.get("arrival_text", ""), "monsters": monsters})
    elements = [{"key": k, "label": v["label"], "desc": _ELEMENT_DESC.get(k, "")}
                for k, v in ELEMENTS.items()]
    themes = [{"key": t["key"], "label": t["label"], "description": t.get("description", "")}
              for t in WEEKLY_THEMES]
    return {"continents": continents, "elements": elements, "themes": themes,
            "invite": config_loader.get_main_server_invite() or ""}


@router.get("/continents")
def continents_summary(request: Request):
    """🗺️ สรุปทุกทวีป — ธาตุชุกชุม สถานะประจำถิ่น มอนประจำแรงค์ อีเวนต์พิเศษ ตัวคูณรางวัล

    อ่านจาก game_data ตัวเดียวกับที่ใช้ตอนเดินจริง — ตัวเลขที่โชว์คือตัวเลขที่ใช้จริง
    """
    uid = int(require_player(request)["uid"])
    from bot.game_data import CONTINENTS
    from bot.game_modifiers import ELEMENTS, STATUS_EFFECTS
    from bot.models import player_model

    here = (player_model.get_player(uid) or {}).get("continent") or "main"
    # ล้มมอนในทวีปนั้นไปแล้วกี่ตัว — เอามาจากสมุดล่ามอนเล่มเดียวกับในดิส
    seen = {}
    for (cont, _rank), n in (player_model.get_bestiary(uid) or {}).items():
        seen[cont] = seen.get(cont, 0) + int(n or 0)

    out = []
    for key, c in CONTINENTS.items():
        m = c.get("mods") or {}
        weights = m.get("element_weights") or {}
        elems = [{"key": k, "label": ELEMENTS.get(k, {}).get("label", k), "weight": w}
                 for k, w in sorted(weights.items(), key=lambda kv: -kv[1])]
        hit = m.get("on_hit_status") or {}
        status = STATUS_EFFECTS.get(hit.get("key"), {})
        pool = m.get("monster_pool") or {}
        out.append({
            "key": key, "label": c["label"], "here": key == here,
            "arrival_text": c.get("arrival_text", ""),
            "elements": elems,
            "status": ({"label": status.get("label", hit.get("key", "")),
                        "chance": int(hit.get("chance", 0))} if hit else None),
            "monsters": [{"rank": rank, "names": names} for rank, names in pool.items()],
            "specials": [{"key": s.get("key", ""), "chance": int(s.get("chance", 0)),
                          "intro": (s.get("intro") or "")[:120]}
                         for s in (m.get("special_events") or [])],
            "mult": {"hp": float(m.get("monster_hp_mult", 1) or 1),
                     "gold": float(m.get("monster_gold_mult", 1) or 1),
                     "exp": float(m.get("monster_exp_mult", 1) or 1)},
            "killed": int(seen.get(key, 0)),
        })
    return {"continents": out, "here": here}


# ── Codex (คู่มือเกมชุดเดียวกับ !codex ในเกม — เว็บตรงกับเกมเสมอ) ──

@router.get("/codex")
def codex():
    from core.services.codex import codex_topics
    return {"topics": codex_topics()}
