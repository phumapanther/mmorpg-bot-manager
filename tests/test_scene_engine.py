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


def test_scene_shows_both_dice_and_the_gap():
    """ผู้เล่นต้องเห็นเต๋าทั้งสองฝั่ง + ห่างกันกี่แต้ม ไม่งั้นไม่รู้ว่าชนะเพราะอะไร"""
    assert "showRoll" in SCENE and "_drawRoll" in SCENE
    for field in ("player_roll", "monster_roll", "player_parts", "monster_parts"):
        assert field in SCENE, f"กล่องเต๋าไม่ได้ใช้ {field} จากเซิร์ฟเวอร์"
    assert "ชนะ +" in SCENE and "แพ้ -" in SCENE and "เสมอ" in SCENE, "ต้องบอกผลต่างแต้ม"
    assert "this._drawRoll();" in SCENE, "ยังไม่ได้เรียกวาดในลูปเรนเดอร์"


def test_dice_display_fields_match_core_output():
    """ชื่อฟิลด์บนจอต้องตรงกับที่ roll_combat คืนมา ไม่งั้นขึ้นค่าว่าง"""
    core = pathlib.Path("bot/adventure_core.py").read_text(encoding="utf-8")
    ret = re.search(r"return \{\"player_roll\".*?\}", core, re.S).group(0)
    for field in ("player_roll", "monster_roll", "player_parts", "monster_parts"):
        assert f'"{field}"' in ret, f"roll_combat ไม่ได้คืน {field}"


def test_web_skill_buttons_send_names_the_server_knows():
    """ปุ่มสกิลบนเว็บส่งชื่ออะไรไป fight_turn ต้องรู้จัก ไม่งั้นกดแล้วกลายเป็นตีธรรมดาเงียบ ๆ"""
    ids = set(re.findall(r"'(skill_\w+)'", re.search(r"const SKILL_ID = \{(.*?)\};", PLAY, re.S).group(1)))
    core = pathlib.Path("bot/adventure_core.py").read_text(encoding="utf-8")
    known = set(re.findall(r'skill_used == "(skill_\w+)"', core))
    assert ids, "อ่าน SKILL_ID ไม่ออก"
    missing = ids - known
    assert not missing, f"เว็บส่งชื่อสกิลที่เซิร์ฟเวอร์ไม่รู้จัก: {sorted(missing)}"


def test_every_class_skill_has_a_server_id():
    """ทุกสกิลที่ขึ้นปุ่มต้องแปลงเป็นชื่อจริงได้ ไม่งั้นปุ่มนั้นหายไปเงียบ ๆ"""
    fx_keys = {k for keys in _class_skill_fx().values() for k in keys}
    mapped = set(re.findall(r"(\w+): 'skill_", re.search(r"const SKILL_ID = \{(.*?)\};", PLAY, re.S).group(1)))
    assert not (fx_keys - mapped), f"สกิลที่ยังไม่มีชื่อจริง: {sorted(fx_keys - mapped)}"


def test_fight_screen_shows_the_monster_hp_bar():
    html = pathlib.Path("license_server/web_static/play.html").read_text(encoding="utf-8")
    assert 'id="foeBar"' in html and 'id="foeHp"' in html
    assert "paintFoe(" in PLAY, "ยังไม่ได้เรียกวาดหลอดเลือดมอน"


def test_dice_box_ignores_anything_that_is_not_a_pair_of_rolls():
    """กับดักคืน roll เป็นเลขเดี่ยว เคยหลุดเข้ากล่องเต๋าจนขึ้น undefined / -NaN แต้ม"""
    assert "typeof roll !== 'object'" in SCENE
    assert "Number.isFinite(+roll.player_roll)" in SCENE


def test_trap_and_mugging_send_their_own_dice_labels():
    """สองอันนี้ทอยแล้ว 'ต่ำกว่าเกณฑ์ = รอด' สวนทางกับเต๋าไฟต์ ป้ายกับข้อสรุปต้องมาจากเซิร์ฟเวอร์"""
    api = pathlib.Path("license_server/web_api.py").read_text(encoding="utf-8")
    assert '"labels": ["🎲 ทอยหลบ", "🛡️ ค่าเกราะ"]' in api
    assert '"labels": ["🎲 ทอยสู้", "🥷 โอกาสชนะ"]' in api
    assert "r.verdict ||" in SCENE, "ฉากต้องยอมให้เซิร์ฟเวอร์กำหนดข้อสรุปเอง"


def test_monster_death_has_an_animation():
    """ล้มมอนแล้วต้องมีฉากตาย ไม่ใช่หายวับไปเฉย ๆ"""
    assert "killFoe()" in SCENE and "_drawDeath()" in SCENE
    assert "this._drawDeath();" in SCENE, "ยังไม่ได้เรียกวาดในลูปเรนเดอร์"
    assert "SCENE.killFoe();" in PLAY, "หน้าเว็บยังไม่ได้เรียกตอนชนะ"


def test_death_effect_uses_the_monster_element_colour():
    block = SCENE[SCENE.index("killFoe()"):SCENE.index("_drawDeath()")]
    assert "ELEMENT_COLOR[this.foe.element]" in block, "เศษร่างต้องเป็นสีตามธาตุของมอนตัวนั้น"


def test_death_animation_cleans_itself_up():
    """ฉากตายต้องจบเองเสมอ ไม่งั้นเศษค้างบนจอทั้งเกม"""
    block = SCENE[SCENE.index("_drawDeath()"):]
    assert "this.death = null;" in block[:1200]
    assert "this.foe = null;" in block[:1200], "ร่างมอนต้องหายหลังแฟลชจบ"


def _trap_kinds():
    block = re.search(r"const TRAP_FX = \{(.*?)\};", SCENE, re.S).group(1)
    return set(re.findall(r"(\w+): 1", block))


def test_every_continent_has_its_own_trap_effect():
    """กับดักหน้าตาต่างกันตามทวีป — ทวีปที่ขาดจะตกไปใช้หนามแหลมกลางแบบเงียบ ๆ"""
    from bot.game_data import CONTINENTS
    missing = set(CONTINENTS) - _trap_kinds()
    assert not missing, f"ทวีปที่ยังไม่มีเอฟเฟกต์กับดัก: {sorted(missing)}"


def test_every_trap_effect_is_actually_drawn():
    """ทุกชนิดที่ประกาศไว้ต้องมีสาขาวาดจริงใน _drawTrap ไม่งั้นลั่นแล้วจอเงียบ"""
    block = SCENE[SCENE.index("_drawTrap(f, p) {"):SCENE.index("  _tick() {")]
    drawn = set(re.findall(r"case '(\w+)':", block))
    missing = _trap_kinds() - drawn - {"main"}          # main ใช้สาขา default
    assert not missing, f"ชนิดที่ประกาศแต่ไม่มีภาพ: {sorted(missing)}"
    assert "default:" in block, "ทวีปที่ไม่มีภาพเฉพาะต้องมีหนามแหลมกลางรองรับ"


def test_trap_kind_comes_from_the_server():
    """เบราว์เซอร์ต้องไม่เดาเองว่าอยู่ทวีปไหน (กติกาข้อ 1)"""
    api = pathlib.Path("license_server/web_api.py").read_text(encoding="utf-8")
    assert 'r["fx"] = {"kind": player.get("continent")' in api
    assert "SCENE.playTrap(r.fx.kind, r.fx.hit)" in PLAY


def test_monster_flee_and_player_death_both_have_effects():
    """สองเหตุการณ์จบไฟต์ที่เหลือ ต้องมีภาพ ไม่ใช่หายวับ/จอเงียบ"""
    for fn in ("fleeFoe()", "_drawFlee()", "killHero()", "_drawKo()"):
        assert fn in SCENE, f"ยังไม่มี {fn}"
    assert "this._drawFlee();" in SCENE and "this._drawKo();" in SCENE, "ยังไม่ได้เรียกในลูป"
    assert "SCENE.fleeFoe()" in PLAY and "SCENE.killHero()" in PLAY


def test_death_screen_restores_the_character_afterwards():
    """จอมืด/ตัวทรุดต้องคืนค่าเมื่อจบ ไม่งั้นตัวละครจมพื้นจางค้างทั้งเกม"""
    block = SCENE[SCENE.index("_drawKo() {"):]
    end = block[:block.index("\n  ")]
    assert "this.heroFall = 0" in block[:900] and "this.heroAlpha = 1" in block[:900]


def test_dying_on_the_road_also_shows_the_death_screen():
    """ตายจากพิษระหว่างเดิน/อีเวนต์พิเศษ ไม่ใช่แค่ในไฟต์ ก็ต้องเห็นฉากตาย + ปุ่มฟื้น"""
    block = PLAY[PLAY.index("if (g.event === 'death' || g.died)"):]
    assert "SCENE.killHero();" in block[:200]
    assert "advRespawnButton(" in block[:400], "ตายกลางทางก็ต้องมีปุ่มฟื้น"

    # อีเวนต์พิเศษที่เล่นแล้วตายคาที่ (act) ต้องมีปุ่มฟื้นเหมือนกัน ไม่ใช่ค้างจอ
    act = PLAY[PLAY.index("if (r.died) {"):]
    assert "advRespawnButton(" in act[:400], "ตายจากอีเวนต์พิเศษแล้วไม่มีปุ่มฟื้น"


def test_action_buttons_sit_above_the_log():
    """ข้อความยาวต้องไม่ดันปุ่มหนีมือ — ปุ่มอยู่บน ข้อความอยู่ล่างในกล่องที่เลื่อนเองได้"""
    html = pathlib.Path("license_server/web_static/play.html").read_text(encoding="utf-8")
    card = html[html.index('<div class="bet-row" id="advActions">'):html.index('</div>\n      </div>')]
    assert html.index('id="advActions"') < html.index('id="advLog"'), "ปุ่มต้องอยู่เหนือข้อความ"
    css = pathlib.Path("license_server/web_static/play.css").read_text(encoding="utf-8")
    assert ".adv-log" in css and "max-height" in css[css.index(".adv-log"):css.index(".adv-log") + 200]
    assert "advLog').scrollTop = 0" in PLAY, "ข้อความใหม่ต้องเริ่มอ่านจากบนสุด"


def test_every_menu_button_has_intact_markup():
    """กันมาร์กอัปพังเงียบ ๆ — เคยแก้ป้ายเฟสด้วย regex แล้วกิน <span> ของปุ่มกาชาไปด้วย
    ผลคือหน้าเว็บโชว์โค้ดดิบ `class="sub">...` ให้ผู้เล่นเห็น"""
    html = pathlib.Path("license_server/web_static/play.html").read_text(encoding="utf-8")
    bad = []
    for m in re.finditer(r'<button[^>]*class="g-tile[^"]*"[^>]*>(.*?)</button>', html, re.S):
        body = m.group(1)
        # IDE จัดรูปแบบใหม่แทรกช่องว่าง/ขึ้นบรรทัดใหม่ระหว่างแท็กกับแอตทริบิวต์ได้
        # (เช่น "<span\n  class=" หรือ "</span\n  >") — ยุบเหลือช่องว่างเดียวก่อนเช็ค
        # เพื่อให้ทนการจัดรูปแบบ แต่ยังจับมาร์กอัปพังจริงได้เหมือนเดิม
        flat = re.sub(r"\s+", " ", body)
        flat = re.sub(r"<\s+", "<", flat)
        flat = re.sub(r"\s+>", ">", flat)
        go = re.search(r'data-go="(\w+)"', m.group(0))
        name = go.group(1) if go else "(ไม่มี data-go)"
        if flat.count("<span") != flat.count("</span>"):
            bad.append(f"{name}: span ไม่สมดุล")
        elif re.search(r'(?<!<span )class="(ic|sub|tag)"', flat):
            bad.append(f"{name}: มี class= ลอยไม่มีแท็กเปิด")
    assert not bad, f"ปุ่มเมนูมาร์กอัปพัง: {bad}"


def test_no_raw_markup_leaks_into_visible_text():
    """ข้อความที่ผู้เล่นเห็นต้องไม่มีเศษโค้ด HTML ปน"""
    html = pathlib.Path("license_server/web_static/play.html").read_text(encoding="utf-8")
    visible = re.sub(r"<[^>]+>", "", html)
    for junk in ('class="', "</span", "<span", "data-go="):
        assert junk not in visible, f"มีเศษโค้ดโผล่ให้ผู้เล่นเห็น: {junk}"


def test_every_pet_in_the_game_can_be_drawn():
    """เพิ่มสัตว์เลี้ยงในคอนฟิกแล้วลืมทำภาพ = พาไปด้วยแล้วไม่มีอะไรโผล่บนจอ"""
    from bot import pets
    look = set(re.findall(r"^  (\w+):\s*\{", re.search(r"const PET_LOOK = \{(.*?)\n\};",
                                                       SCENE, re.S).group(1), re.M))
    missing = {p["key"] for p in pets.all_pets()} - look
    assert not missing, f"สัตว์เลี้ยงที่ยังไม่มีภาพ: {sorted(missing)}"


def test_the_pet_walks_along_and_joins_the_attack():
    for fn in ("Scene.prototype.setPet", "_drawPet", "petAttack"):
        assert fn in SCENE, f"ยังไม่มี {fn}"
    assert "this._drawPet();" in SCENE, "ยังไม่ได้เรียกวาดในลูป"
    assert "SCENE.petAttack();" in PLAY, "กดโจมตีแล้วสัตว์เลี้ยงต้องออกท่าด้วย"
    assert "SCENE.setPet(" in PLAY


def test_the_pet_shown_is_the_one_the_server_says():
    """เบราว์เซอร์ต้องไม่เดาเองว่าพาตัวไหนไป"""
    api = pathlib.Path("license_server/web_api.py").read_text(encoding="utf-8")
    assert '"pet": p.get("pet") or ""' in api
    assert "SCENE.setPet(v.pet" in PLAY or "SCENE.setPet((LAST" in PLAY


# ── ⚔️ อาวุธรายคลาส + 🔊 เสียง + 📱 จอเล็ก (2026-08-14) ─────────────────────

SPRITE = pathlib.Path("license_server/web_static/sprite.js").read_text(encoding="utf-8")
SFX = pathlib.Path("license_server/web_static/sfx.js").read_text(encoding="utf-8")


def test_every_class_holds_a_different_weapon():
    """คลาสต่างกันต้องถือทรงอาวุธคนละแบบ ไม่ใช่ดาบเหมือนกันหมด"""
    from bot.views.profile_embed import GAME_CLASSES
    block = re.search(r"const CLASS_WEAPON = \{(.*?)\};", SPRITE, re.S).group(1)
    mapping = dict(re.findall(r"(\w+):\s*'(\w+)'", block))
    missing = set(GAME_CLASSES) - set(mapping)
    assert not missing, f"คลาสที่ยังไม่มีทรงอาวุธ: {sorted(missing)}"
    assert len(set(mapping.values())) == len(mapping), \
        f"มีคลาสถือทรงซ้ำกัน: {mapping}"


def test_every_weapon_shape_is_actually_drawn():
    """ทรงอาวุธย้ายจาก switch/case มาเป็นตารางพิกเซลแล้ว (2026-08-15)
    ทรงที่คลาสชี้ไปต้องมีตารางจริง ไม่งั้นถืออาวุธผิดแบบ"""
    art = re.search(r"const WEAPON_ART = \{(.*?)\n\};", SPRITE, re.S)
    assert art, "หาตารางพิกเซลอาวุธไม่เจอ"
    shapes = set(re.findall(r"^\s{2}(\w+):\s*\[", art.group(1), re.M))
    declared = set(re.findall(r":\s*'(\w+)'",
                              re.search(r"const CLASS_WEAPON = \{(.*?)\};", SPRITE, re.S).group(1)))
    assert declared <= shapes, f"ทรงที่ประกาศแต่ไม่มีตาราง: {sorted(declared - shapes)}"
    assert "WEAPON_ART.sword" in SPRITE, "คลาสที่ไม่รู้จักต้องมีดาบมาตรฐานรองรับ"


def test_the_sound_engine_needs_no_external_files():
    """สังเคราะห์เสียงเอง — โหลดไฟล์เสียงจากภายนอกไม่ได้

    เช็คของที่ 'ดึงไฟล์จริง ๆ' ไม่ใช่ไล่หาสตริงลอย ๆ
    (เคยพังเพราะ `t.wave` ในเอนจินเพลงไปชนกับการหา '.wav')
    """
    assert "createOscillator" in SFX and "createBuffer" in SFX
    for bad in ("new Audio(", "fetch(", "XMLHttpRequest", "http://", "https://",
                ".mp3", ".ogg", ".wav'", '.wav"'):
        assert bad not in SFX, f"เอนจินเสียงไปดึงไฟล์ภายนอก: {bad}"


def test_sound_can_be_muted_and_remembers_the_choice():
    assert "localStorage" in SFX and "toggle()" in SFX
    assert 'id="playSfx"' in pathlib.Path("license_server/web_static/play.html").read_text(encoding="utf-8")


def test_a_broken_sound_never_breaks_the_game():
    """เสียงพังห้ามทำให้เกมพัง — ต้องมี try/catch ครอบ"""
    play = SFX[SFX.index("play(name)"):]
    assert "try {" in play[:200] and "catch" in play[:200]


def test_key_moments_all_have_a_sound():
    """เสียงที่ทำไว้ต้องถูกใช้จริง ไม่ใช่ประกาศทิ้งไว้เฉย ๆ"""
    # เก็บชื่อเสียงจากทุกบรรทัดที่เรียก SFX.play (รวมที่ซ่อนในเงื่อนไข ternary)
    called = {n for line in PLAY.splitlines() if "SFX.play(" in line
              for n in re.findall(r"'(\w+)'", line)}
    for name in ("hit", "hurt", "win", "lose", "coin", "dice", "levelup", "skill"):
        assert f"{name}:" in SFX, f"ยังไม่มีเสียง {name}"
        assert name in called, f"เสียง {name} ประกาศไว้แต่ไม่มีใครเรียก"


def test_action_buttons_shrink_on_narrow_screens():
    """จอ 480px ปุ่ม 'สู้ต่อ (ทอยเต๋าปกติ)' เคยตัดเป็นสามบรรทัด"""
    assert "const NARROW = () =>" in PLAY
    assert "NARROW() ? '⚔️ สู้ต่อ'" in PLAY
    css = pathlib.Path("license_server/web_static/play.css").read_text(encoding="utf-8")
    assert "#advActions .g-tile" in css, "จอแคบยังไม่ได้จัดปุ่มแอคชั่น"
    i = css.index("#advActions .g-tile")
    assert "@media (max-width: 480px)" in css[:i], "กฎปุ่มแคบต้องอยู่ใน media query"
