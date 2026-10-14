"""🧪 ห้องแล็บเอฟเฟกต์ (/fxlab) — เรียกโค้ดวาดจริงใน sprite.js + ไลบรารี FX มาพรีวิวสด

หน้านี้ไม่มี logic เกม แค่ "ต่อสาย" กับโค้ดวาด — เทสกันสายหลุด:
ถ้ามีคนเปลี่ยนชื่อ FASHION_AURA / drawCharacter / FX หรือลืม register /fxlab หน้านี้จะพังเงียบ ๆ
(รัน JS ในเบราว์เซอร์เทสไม่ได้ จึงคุม "สัญญา" ระหว่างไฟล์แทน — ส่วนการรันจริงเช็กด้วย node ตอนประกอบ)
"""
import pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent
WEB = ROOT / "license_server" / "web_static"
FX_KEYS = ("slash", "lightning", "crystal", "petal", "meteor", "runecircle")


def test_fxlab_ต่อสายกับ_sprite_และ_fx():
    html = (WEB / "fxlab.html").read_text(encoding="utf-8")
    sprite = (WEB / "sprite.js").read_text(encoding="utf-8")

    assert '<script src="/sprite.js">' in html
    assert '<script src="/games/fx_effects.js">' in html
    for name in ("FASHION_AURA", "drawCharacter", "drawAura", "RACE_LOOK", "CLASS_LOOK", "WEAPON_LOOK"):
        assert name in html and name in sprite, f"ต้องมี {name} ทั้งใน fxlab และ sprite.js"
    assert "FASHION_AURA.__preview" in html
    assert "FASHION_AURA[key]" in sprite, "drawAura ต้อง lookup ด้วย key — ไม่งั้น __preview ใช้ไม่ได้"
    assert "window.FX" in html, "fxlab อ่านไลบรารีจาก window.FX"


def test_ไลบรารี_fx_ครบและถูกสัญญา():
    js = (WEB / "games" / "fx_effects.js").read_text(encoding="utf-8")
    assert "window.FX = window.FX || {}" in js
    for k in FX_KEYS:
        assert f"FX.{k} = {{" in js, f"ขาดเอฟเฟกต์ {k}"
        block = js.split(f"FX.{k} = {{", 1)[1].split("\n};", 1)[0]
        for field in ("label:", "loop:", "params:", "colors:", "draw("):
            assert field in block, f"{k} ขาด {field}"
    # 'loop' เป็น property ของเอฟเฟกต์ ไม่ได้อยู่ใน p ที่ draw รับ — อ้าง p.loop = วาดไม่ออก (เคยพลาดมาแล้ว)
    assert "p.loop" not in js, "draw ห้ามอ้าง p.loop (loop ไม่ได้อยู่ใน p)"


def test_fxlab_ลงทะเบียนเส้นทาง():
    api = (ROOT / "license_server" / "api.py").read_text(encoding="utf-8")
    assert '"fxlab"' in api, "/fxlab ต้องอยู่ในลิสต์หน้าเพจ (ไม่งั้นเข้าแบบ URL สวยไม่ได้)"
