"""ตรวจเทมเพลตมินิเกม (templates/minigame/) — คุมว่าเทมเพลตยัง "รันได้จริง"

ไฟล์นี้ไม่เกี่ยวกับตรรกะเกมทายเลขโดยตรง (เทสตรรกะเกมอยู่ที่
templates/minigame/tests/) หน้าที่ของไฟล์นี้คือคุมว่า: ไฟล์ครบตาม README ·
import ได้ · เล่นจนจบได้ · ไม่มี discord/bot.cogs · เทสในเทมเพลตเองรันผ่าน ·
view() ไม่ส่งเลขลับหลุดออกมาก่อนเกมจบ (คุม 2 ชั้น: ฟังก์ชัน + คำตอบ HTTP)
"""
import importlib.machinery
import importlib.util
import pathlib
import random
import subprocess
import sys

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
TEMPLATE_ROOT = REPO_ROOT / "templates" / "minigame"

sys.path.insert(0, str(REPO_ROOT))     # กัน `python -m pytest tests/test_template_minigame.py` เดี่ยว ๆ


# ── 1. ไฟล์ในเทมเพลตครบตามที่ README บอก ──

def test_ไฟล์ในเทมเพลตครบตามที่_README_บอก():
    readme = (TEMPLATE_ROOT / "README.md").read_text(encoding="utf-8")
    expected = [
        "core/__init__.py", "core/rules.py", "core/engine.py", "core/bot_ai.py",
        "core/table.py", "core/room.py",
        "web/game.js", "web/panel.html.snippet",
        "api/routes.py.snippet",
        "tests/test_rules.py", "tests/test_engine.py", "tests/test_room.py",
    ]
    for rel in expected:
        assert (TEMPLATE_ROOT / rel).is_file(), f"README บอกว่ามี {rel} แต่หาไม่เจอไฟล์จริง"
        assert rel in readme, f"มีไฟล์ {rel} จริง แต่ README ไม่ได้พูดถึง — แก้ README ให้ตรงโครงไฟล์"


# ── 2. โค้ดในเทมเพลตรันได้จริง — import ได้ · เล่นเกมทายเลขจนจบได้ ──

def test_เล่นเกมทายเลขกับบอทจนจบได้():
    from templates.minigame.core import bot_ai as B
    from templates.minigame.core import engine as E

    rng = random.Random(1)
    st = E.new_game(["คน", "🤖 บอท"], rng=rng)
    for _ in range(E.MAX_GUESSES + 2):
        if st["over"]:
            break
        if st["turn"] == 0:
            E.guess(st, st["secret"])      # จำลองคนจริงทายถูกทันที
        else:
            B.take_turn(E, st, rng)
    assert st["over"], "เล่นจนครบตาสูงสุดแล้วเกมยังไม่จบ — engine ต้องค้ำประกันว่าจบได้เสมอ"


# ── 3. เทมเพลตไม่ import discord และไม่ import จาก bot/cogs/ ──

def test_เทมเพลตไม่_import_discord_หรือ_bot_cogs():
    py_files = list((TEMPLATE_ROOT / "core").rglob("*.py")) + \
        list((TEMPLATE_ROOT / "tests").rglob("*.py"))
    for py_file in py_files:
        src = py_file.read_text(encoding="utf-8")
        assert "import discord" not in src, f"{py_file} import discord — core ต้องเป็นแกนล้วน"
        assert "bot.cogs" not in src, f"{py_file} อ้างถึง bot.cogs — core ห้ามพึ่ง cog"


# ── 4. เทสในเทมเพลตเองรันผ่าน ──

def test_รัน_pytest_บนโฟลเดอร์เทมเพลตได้():
    result = subprocess.run(
        [sys.executable, "-m", "pytest", str(TEMPLATE_ROOT / "tests"), "-q"],
        cwd=str(REPO_ROOT), capture_output=True, text=True,
        encoding="utf-8", errors="replace",
    )
    assert result.returncode == 0, (
        f"pytest บน templates/minigame/tests ไม่ผ่าน:\n"
        f"STDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}")


# ── 5. view() ไม่ส่งเลขลับก่อนเกมจบ — เทส 2 ชั้น ──

def test_view_ไม่ส่งเลขลับก่อนเกมจบ_ชั้นฟังก์ชัน(tmp_path, monkeypatch):
    import bot.models.player_model as player_model
    from templates.minigame.core import table as T

    monkeypatch.setattr(player_model, "DB_NAME", str(tmp_path / "t.db"))
    T.start(999001, name="คน", bots=1, rng=random.Random(1))
    view = T.view(999001)
    assert view["playing"]
    if not view["over"]:
        assert "secret" not in view, "เกมยังไม่จบ แต่ view() มีเลขลับหลุดออกมา"
    T.clear(999001)


def test_view_ไม่ส่งเลขลับก่อนเกมจบ_ชั้น_HTTP_response(tmp_path, monkeypatch):
    """ชั้นที่ 2 — เทียบกับ dict ที่ endpoint (api/routes.py.snippet) จะตอบกลับจริง"""
    import bot.models.player_model as player_model

    monkeypatch.setattr(player_model, "DB_NAME", str(tmp_path / "t2.db"))

    path = TEMPLATE_ROOT / "api" / "routes.py.snippet"
    loader = importlib.machinery.SourceFileLoader("guessnum_routes_snippet", str(path))
    spec = importlib.util.spec_from_file_location("guessnum_routes_snippet", str(path), loader=loader)
    mod = importlib.util.module_from_spec(spec)
    loader.exec_module(mod)

    class FakeRequest:
        headers = {"x-uid": "999002"}

    out = mod.guessnum(mod.GuessBody(action="start", bots=1), FakeRequest())
    assert out["ok"] and out["table"]["playing"]
    if not out["table"]["over"]:
        assert "secret" not in out["table"], (
            "เกมยังไม่จบ แต่คำตอบ HTTP จาก endpoint มีเลขลับหลุดออกมา")
