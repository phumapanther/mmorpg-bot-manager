"""สถานะร้ายทุกตัวต้องมีทางแก้ ไม่มีทางตัน

เคสจริง (2026-07-30): 🍄 เห็ดงอกทั่วร่าง (เสีย 5% MaxHP ต่อก้าว 6 ก้าว + เต๋า -1)
ไม่มีไอเทมไหนล้างได้เลยแม้แต่ยาครอบจักรวาล — ติดแล้วได้แต่รอหมดเอง
"""
from bot import config_loader
from bot import game_modifiers as gm

# สัญญาณว่าสถานะนี้ "ทำร้ายผู้เล่น" — มีอย่างใดอย่างหนึ่ง = ต้องมีทางแก้
HARM_KEYS = ("step_damage", "step_damage_pct", "combat_pct_damage", "disable_skills",
             "seal_high_roll", "fumble_chance", "monster_dice_bonus", "skill_fail_chance",
             "curse_parity", "transform_to", "block_flee")


def _is_harmful(cfg):
    if cfg.get("artifact"):
        return False
    if any(cfg.get(k) for k in HARM_KEYS):
        return True
    return cfg.get("roll_bonus", 0) < 0 or cfg.get("player_dmg_mult", 1.0) < 1.0


def _cure_map():
    """{คีย์สถานะ: [ทางแก้...]} — รวมทั้งไอเทมและการเจออีเวนต์"""
    out = {}
    for iid, it in config_loader.get_all_items().items():
        if it.get("effect") != "cure_status":
            continue
        val = it.get("effect_value")
        for v in (val if isinstance(val, list) else [val]):
            out.setdefault(str(v), []).append(f"ไอเทม {iid}")
    for key, cfg in gm.STATUS_EFFECTS.items():
        for trigger in cfg.get("cleanse_on", []):
            out.setdefault(key, []).append(f"เจอ {trigger}")
        for other, ocfg in gm.STATUS_EFFECTS.items():
            if key in ocfg.get("cleanse_on_apply", []):
                out.setdefault(key, []).append(f"ติด {other} ทับ")
    return out


def test_every_harmful_status_has_at_least_one_cure():
    cures = _cure_map()
    stuck = [f"{cfg['label']} ({key})" for key, cfg in gm.STATUS_EFFECTS.items()
             if _is_harmful(cfg) and not cures.get(key)]
    assert not stuck, ("สถานะร้ายที่ติดแล้วแก้ไม่ได้เลย — ต้องเพิ่มไอเทมล้าง "
                       "หรือใส่ในลิสต์ของยาครอบจักรวาล:\n  " + "\n  ".join(stuck))


# สถานะร้ายที่ "ตั้งใจ" ไม่ให้ยาครอบจักรวาลล้าง — ต้องมีของเฉพาะทางแก้แทน
# (เป็นการตัดสินใจเชิงบาลานซ์ ไม่ใช่ของหลุด — เพิ่ม/ลบรายการนี้ได้ตามที่อยากให้เกมเป็น)
UNIVERSAL_EXCLUDES = {
    "bleed": "🩹 ผ้าพันแผล (61) เท่านั้น",
    "spores": "🌿 ยาถอนพิษพงไพร (30) เท่านั้น — ปล่อยจนบานค่อยใช้ยาครอบจักรวาล",
}


def test_universal_cure_covers_everything_except_the_documented_list():
    """ยาครอบจักรวาลต้องล้างสถานะร้ายทุกตัว ยกเว้นที่จดไว้ว่าตั้งใจไม่ให้ล้าง"""
    universal = None
    item_cured = set()
    for iid, it in config_loader.get_all_items().items():
        if it.get("effect") != "cure_status":
            continue
        val = it.get("effect_value")
        vals = set(str(v) for v in (val if isinstance(val, list) else [val]))
        item_cured |= vals
        if len(vals) > (len(universal[1]) if universal else 0):
            universal = (iid, vals)

    assert universal, "ไม่มีไอเทมล้างสถานะเลย"
    harmful_curable = {k for k in item_cured if _is_harmful(gm.STATUS_EFFECTS.get(k, {}))}
    missing = sorted(harmful_curable - universal[1] - set(UNIVERSAL_EXCLUDES))
    assert not missing, (
        f"ยาครอบจักรวาล (ไอเทม {universal[0]}) ล้างไม่ได้: {missing}\n"
        "→ ถ้าตั้งใจ ให้ใส่ใน UNIVERSAL_EXCLUDES พร้อมเหตุผล ถ้าไม่ตั้งใจให้เพิ่มในลิสต์ยา")
    assert not (set(UNIVERSAL_EXCLUDES) & universal[1]), \
        "มีสถานะที่จดว่า 'ตั้งใจไม่ให้ล้าง' แต่ดันอยู่ในลิสต์ยาครอบจักรวาล — เอกสารกับของจริงไม่ตรงกัน"


def test_mushroom_bloom_specifically():
    """เคสที่เจอจริง — ตรึงไว้ไม่ให้หลุดอีก"""
    cfg = gm.STATUS_EFFECTS["mushroom_bloom"]
    assert _is_harmful(cfg), "ถ้าตัวนี้ไม่ถูกนับว่าร้าย เทสข้างบนจะกลายเป็นเทสหลอก"
    assert "mushroom_bloom" in _cure_map(), "🍄 เห็ดงอกทั่วร่าง ต้องมีทางแก้"
