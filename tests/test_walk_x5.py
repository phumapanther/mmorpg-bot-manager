"""O5: ปุ่ม ⏩ เดินต่อ ×5 — เดินรวดเฉพาะช่วงที่ไม่มีอะไรให้ตัดสินใจ"""
import pathlib

import bot.views.game_views as gv


def test_button_exists():
    labels = [b.label for b in gv.AdventureView(1).children]
    assert any("เดินต่อ" in l for l in labels) and any("เริ่มออกเดินทาง" in l for l in labels)


def test_walk_logic_rules():
    """กติกาที่ต้องคงไว้: วนซ้ำเฉพาะอีเวนต์สงบ + หยุดเมื่อเลือดต่ำกว่า 30%"""
    src = pathlib.Path("bot/views/game_views.py").read_text(encoding="utf-8")
    calm = src[src.index('elif chosen_event == "calm":'):src.index('elif chosen_event == "special":')]
    assert "max_steps=max_steps - 1" in calm, "ต้องนับก้าวถอยหลัง (กันวนไม่รู้จบ)"
    assert "max_hp" in calm and "0.3" in calm, "ต้องหยุดเมื่อเลือดต่ำ"
    assert "walk_step(interaction, button, max_steps=" in calm

    # อีเวนต์อื่นต้องไม่มีการวนซ้ำเลย (เจอแล้วหยุดทันที) — ตัดบล็อกถึงสาขาถัดไปเท่านั้น
    import re
    for event in ("monster", "treasure", "trap", "dungeon", "npc", "travel"):
        start = src.index(f'elif chosen_event == "{event}"') if f'elif chosen_event == "{event}"' in src \
            else src.index(f'if chosen_event == "{event}"')
        nxt = re.search(r'\n        elif chosen_event ==', src[start + 10:])
        block = src[start:start + 10 + (nxt.start() if nxt else 1500)]
        assert "max_steps=max_steps - 1" not in block, f"อีเวนต์ {event} ต้องหยุดเดินรวด"


def test_default_single_step():
    """ปุ่มเดิมต้องยังเดินทีละก้าวเหมือนเดิม (max_steps=1)"""
    src = pathlib.Path("bot/views/game_views.py").read_text(encoding="utf-8")
    # ตรรกะเดินอยู่ในเมธอดธรรมดา (walk_step) ปุ่มทั้งสองเป็นแค่ตัวเรียก — ห้ามเรียกปุ่มเป็นฟังก์ชัน
    assert "async def walk_step(self, interaction: discord.Interaction, button: discord.ui.Button, max_steps=1):" in src
    assert "await self.walk_step(interaction, button, max_steps=5)" in src
    assert "await self.walk_step(interaction, button, max_steps=1)" in src
