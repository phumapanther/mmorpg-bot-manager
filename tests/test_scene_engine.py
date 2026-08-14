"""เอนจินฉากพิกเซล (เฟส 4) — ข้อมูลฉากต้องครอบคลุมของจริงในเกม

ถ้าเกมเพิ่มทวีป/ธาตุ/สกิลใหม่แล้วลืมเพิ่มในฉาก ผู้เล่นจะเห็นฉากผิดหรือฉากว่าง
เทสนี้อ่าน scene.js/play.js เทียบกับข้อมูลเกมจริง
"""
import pathlib
import re

SCENE = pathlib.Path("license_server/web_static/scene.js").read_text(encoding="utf-8")
PLAY = pathlib.Path("license_server/web_static/play.js").read_text(encoding="utf-8")


def _keys(src, block):
    m = re.search(block + r"\s*=\s*\{(.*?)\n\};", src, re.S)
    assert m, f"หาบล็อก {block} ไม่เจอ"
    return set(re.findall(r"^\s{2}(\w+):", m.group(1), re.M))


def test_every_continent_has_scene_colours():
    from bot.game_data import CONTINENTS
    missing = set(CONTINENTS) - _keys(SCENE, "const MAPS")
    assert not missing, f"ทวีปที่ยังไม่มีสีในฉาก: {sorted(missing)}"


def test_every_element_has_monster_colours():
    from bot.game_modifiers import ELEMENTS
    missing = set(ELEMENTS) - _keys(SCENE, "const ELEMENT_COLOR")
    assert not missing, f"ธาตุที่ยังไม่มีสีมอน: {sorted(missing)}"


def _class_skill_fx():
    """{คลาส: [คีย์เอฟเฟกต์...]} จากบล็อก CLASS_SKILL_FX ใน play.js"""
    block = re.search(r"const CLASS_SKILL_FX = \{(.*?)\n\};", PLAY, re.S)
    assert block, "หาบล็อก CLASS_SKILL_FX ไม่เจอ"
    out = {}
    for line in block.group(1).splitlines():
        m = re.match(r"\s*(\w+):\s*(\[.*\]),?\s*$", line)
        if m:
            out[m.group(1)] = re.findall(r"\['(\w+)',", m.group(2))
    return out


def test_scene_covers_every_class_skill():
    """ปุ่มสกิลบนเว็บต้องมีครบทุกคลาส/ทุกสกิลตามเกม"""
    from bot.views.profile_embed import CLASS_SKILLS, GAME_CLASSES
    fx = _class_skill_fx()
    for cls in GAME_CLASSES:
        assert cls in fx, f"ไม่มีสกิลของคลาส {cls} ในหน้าเว็บ"
        assert len(fx[cls]) == len(CLASS_SKILLS[cls]), \
            f"คลาส {cls} มี {len(CLASS_SKILLS[cls])} สกิลในเกม แต่เว็บมี {len(fx[cls])}"


def test_every_skill_effect_has_a_duration():
    """สกิลที่ปุ่มเรียก ต้องมีเอฟเฟกต์รองรับ ไม่งั้นกดแล้วเงียบ"""
    durations = set(re.findall(r"(\w+):\d+",
                               re.search(r"const dur = \{(.*?)\}", SCENE, re.S).group(1)))
    used = {k for keys in _class_skill_fx().values() for k in keys}
    assert used, "ไม่พบคีย์สกิลเลย — regex อ่านไม่ออก"
    missing = used - durations
    assert not missing, f"สกิลที่ยังไม่มีเอฟเฟกต์: {sorted(missing)}"


def test_event_art_lookup_prefers_continent_then_falls_back():
    assert "${continent}_${eventKey}.png" in SCENE
    assert "/assets/events/${eventKey}.png" in SCENE


def test_real_event_art_exists_for_every_continent():
    """ภาพจริงต้องมีครบทุกทวีป × เหตุการณ์หลัก ไม่งั้นฉากจะว่าง"""
    from bot.game_data import CONTINENTS
    art = pathlib.Path("assets/events")
    if not art.is_dir():
        return                                    # เครื่องที่ไม่มีชุดภาพ = ข้าม
    missing = [f"{c}_{e}" for c in CONTINENTS
               for e in ("village", "monster", "treasure", "trap", "npc", "dungeon", "calm")
               if not (art / f"{c}_{e}.png").is_file()]
    assert not missing, f"ภาพฉากที่ขาด: {missing[:8]}"
