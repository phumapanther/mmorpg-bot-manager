"""แท็บ Panel ต้องครอบคลุมทุกหมวดที่แก้ได้ — กันเพิ่มฟีเจอร์แล้วลืมทำหน้าให้ลูกค้าแก้"""
import json
import pathlib
import re

import pytest

APP = pathlib.Path("panel/static/app.js").read_text(encoding="utf-8")
HTML = pathlib.Path("panel/static/index.html").read_text(encoding="utf-8")
CFG = json.load(open("config.example.json", encoding="utf-8"))

# หมวดใน config ที่ไม่ต้องมีหน้าใน Panel (ความลับ/ตั้งจากที่อื่น/ข้อมูลดิบของเกม)
NOT_IN_PANEL = {"bot_token", "guest_bot_token", "license_key", "guild_id", "panel_port",
                "main_guild_id", "main_server_invite", "item_catalog", "monster_ranks"}


def test_every_config_section_is_reachable_from_panel():
    missing = [k for k in CFG if k not in NOT_IN_PANEL and k not in APP]
    assert not missing, f"หมวดที่ยังไม่มีหน้าใน Panel: {missing}"


def test_retention_tab_wired_end_to_end():
    assert 'data-tab="retention"' in HTML and 'id="tab-retention"' in HTML
    assert 'id="retentionSaveBtn"' in HTML
    assert "renderRetention" in APP and "retentionSave" in APP
    assert 'getElementById("retentionSaveBtn").addEventListener' in APP


def test_every_retention_table_has_a_tbody_to_fill():
    for table_id in re.findall(r"^  (ret\w+): \{ path:", APP, re.M):
        assert f'id="{table_id}"' in HTML, f"JS อ้างตาราง {table_id} แต่ไม่มีใน HTML"


def test_table_columns_match_real_config_keys():
    """คอลัมน์ใน Panel ต้องตรงกับคีย์จริงใน config ไม่งั้นกรอกแล้วบอทไม่เห็น"""
    checks = {
        "daily_quests.quests": {"key", "label", "target", "gold", "exp"},
        "daily_quests.streak_rewards": {"day", "gold"},
        "weekly_ranking.rewards": {"gold", "exp"},
        "achievements": {"key", "label", "desc", "stat", "target", "gold", "title"},
        "pets.list": {"key", "name", "desc", "from_rank", "dice"},
    }
    for path, cols in checks.items():
        node = CFG
        for part in path.split("."):
            node = node[part]
        assert node, f"{path} ว่าง"
        assert cols <= set(node[0]), f"{path}: Panel อ้างคีย์ที่ไม่มีจริง {cols - set(node[0])}"

    tier = CFG["season_pass"]["tiers"][0]
    assert {"points", "free", "premium"} <= set(tier)
    assert "gold" in tier["free"] and "gold" in tier["premium"]


def test_status_table_has_label_and_unit_for_display():
    ov = CFG["game_balance"]["status_overrides"]
    for key, row in ov.items():
        assert row.get("label"), f"สถานะ {key} ไม่มีชื่อให้แสดงในตาราง"
        assert row.get("unit") in ("ก้าว", "ไฟต์"), f"สถานะ {key} ไม่มีหน่วยเวลา"


def test_event_weight_table_covers_every_situation():
    weights = CFG["game_balance"]["events"]["weights"]
    labels = re.search(r"EVENT_ROW_LABEL = \{(.+?)\};", APP, re.S).group(1)
    for situation in weights:
        assert situation in labels, f"ตารางใน Panel ไม่มีแถว {situation}"


def test_every_retention_field_points_at_a_real_config_key():
    """ช่องกรอกที่ชี้ path ผิด = กรอกแล้วบอทไม่เห็น และไม่มีอะไรฟ้อง"""
    block = APP[APP.index("const CFG_FIELDS = {"):APP.index("const ROW_TABLES = {")]
    for path in re.findall(r'\["([a-z_]+\.[A-Za-z_.-]+)",', block):
        node = CFG
        for k in path.split("."):
            assert isinstance(node, dict) and k in node, f"Panel อ้าง {path} แต่ config ไม่มี"
            node = node[k]


def test_render_edit_save_roundtrip_in_node():
    """รันจาวาสคริปต์จริงด้วย DOM จำลอง — จับ path/คอลัมน์ผิดที่การอ่านข้อความจับไม่ได้"""
    import shutil
    import subprocess
    if not shutil.which("node"):
        pytest.skip("ไม่มี node ในเครื่องนี้ — ข้ามเทสฝั่งเบราว์เซอร์")
    r = subprocess.run(["node", "tests/panel_retention_roundtrip.mjs"],
                       capture_output=True, text=True, encoding="utf-8")
    assert r.returncode == 0, (r.stdout or "") + (r.stderr or "")


def test_javascript_has_no_syntax_error():
    import shutil
    import subprocess
    if not shutil.which("node"):
        pytest.skip("ไม่มี node ในเครื่องนี้")
    r = subprocess.run(["node", "--check", "panel/static/app.js"],
                       capture_output=True, text=True, encoding="utf-8")
    assert r.returncode == 0, r.stderr


def test_panel_never_reads_ids_as_numbers():
    """กันบั๊กเดิม: Number() กับ snowflake ทำให้ไอดีเพี้ยนหลักท้าย"""
    for line in APP.splitlines():
        if "Number(" in line and re.search(r"role_id|guild_id|channel_id", line):
            assert False, f"ห้ามแปลงไอดี Discord เป็น Number: {line.strip()}"
