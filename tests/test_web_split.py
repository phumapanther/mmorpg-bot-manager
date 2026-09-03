"""🪓 คุมความถูกต้องของการผ่า play.js (เว็บเกม รื้อโครงสร้าง ขั้นที่ 5, 09-02)

play.js เดิม 4,265 บรรทัด — 90 ฟังก์ชัน wm* (สนามรบ) ถูกย้ายไป games/worms_ui.js
(ร่วมกับ fillWorms ที่ไม่ได้ขึ้นต้น wm) เทสไฟล์นี้คุม 3 เรื่อง:
  1. play.html ยังโหลดไฟล์ JS ที่มีอยู่จริงครบ ไม่ตกหล่น ไม่ลืมใส่ <script>
  2. ไม่มีฟังก์ชันหายไประหว่างย้าย — เทียบกับ snapshot ชื่อฟังก์ชันทั้ง 175 ตัว (เก็บไว้ก่อนย้าย)
  3. เว็บโหลดได้จริงใน vm ไม่ใช่แค่ "ไฟล์มีอยู่" — กัน ReferenceError จากตัวแปร/ฟังก์ชันที่ลืมย้าย
"""
import pathlib
import re
import shutil
import subprocess

import pytest

from tests import conftest

WEB = pathlib.Path("license_server/web_static")
HTML = (WEB / "play.html").read_text(encoding="utf-8")

# 📸 snapshot ชื่อฟังก์ชันทั้งหมดใน play.js ก่อนผ่า (09-02) — ต้องอยู่ครบ 175 ตัวตลอดไป
# ไม่ว่าจะย้ายไปไฟล์ไหนก็ตาม (เทียบกับ conftest.play_js_source() ที่รวมทุกไฟล์เข้าด้วยกัน)
FUNCS_BEFORE_SPLIT = {
    'addFriend', 'advAct', 'advIdleButton', 'advPaint', 'advRespawn', 'advRespawnButton',
    'advWalk', 'animateHilo', 'animateSlots', 'askNumber', 'auraRepaint', 'bindInviteButtons',
    'bjAct', 'bjCards', 'bjPaint', 'bjRestore', 'boot', 'botOfflineBanner', 'buildChips',
    'buyRole', 'casinoPlay', 'chipRow', 'confirmAction', 'delFriend', 'drawFriend', 'drawSprite',
    'dropItem', 'fashOff', 'fashPreview', 'fashTry', 'fashWear', 'fgExchange', 'fgFeatPreview',
    'fgPull', 'fillAchv', 'fillAtlas', 'fillBars', 'fillBoard', 'fillBooks', 'fillCraft',
    'fillDaily', 'fillElemBook', 'fillFashion', 'fillFashionGacha', 'fillFriends', 'fillGacha',
    'fillMarket', 'fillPartner', 'fillPets', 'fillQuick', 'fillRoleShop', 'fillSeason',
    'fillShop', 'fillWorms', 'hopTo', 'initScene', 'inviteFriendsHtml', 'marketBuy',
    'marketCancel', 'marketSell', 'mdLite', 'openDialog', 'openItemMenu', 'paint', 'paintAdvHud',
    'paintBag', 'paintBoard', 'paintFashion', 'paintFoe', 'paintFriends', 'paintGacha',
    'paintMarketBuy', 'paintMarketMine', 'paintMarketSell', 'paintProfile', 'reload',
    'rollBoard', 'sceneMusic', 'seeFriend', 'shopAction', 'showPanel', 'spinGacha', 'toast',
    'useItem', 'waitTicket', 'wmApply', 'wmAttack', 'wmBackoff', 'wmBindAim', 'wmBoom',
    'wmBreakProps', 'wmBuffFx', 'wmBump', 'wmBusyFx', 'wmCallDeaths', 'wmChestFx', 'wmChunk',
    'wmClock', 'wmDie', 'wmDo', 'wmDrawAim', 'wmDrawFighter', 'wmDrawFx', 'wmDrawSpawns',
    'wmDrawTrail', 'wmDust', 'wmEndTurn', 'wmFitCanvas', 'wmFlames', 'wmFocus', 'wmFxIdle',
    'wmGiveUp', 'wmHideOutcome', 'wmHoldAt', 'wmHoldOn', 'wmHoldStart', 'wmHoldStop',
    'wmJumpFire', 'wmJumpPower', 'wmLand', 'wmLean', 'wmMe', 'wmNewMatch', 'wmOpenChest',
    'wmPaintHud', 'wmPaintItems', 'wmPaintOver', 'wmPaintRoom', 'wmPaintSkills', 'wmPaintWind',
    'wmPeekTurn', 'wmPickSkill', 'wmPlayAttack', 'wmPlayBotShots', 'wmPlayDeaths',
    'wmPlayKnocks', 'wmPlayVictims', 'wmPop', 'wmPropsNow', 'wmQueueBot', 'wmQueueOther',
    'wmReconcile', 'wmRevealAll', 'wmRevealOne', 'wmRideFerry', 'wmRoomDo', 'wmRoomWatch',
    'wmRunSteps', 'wmSeenTurn', 'wmSettleVictim', 'wmShowAim', 'wmShowDrop', 'wmShowGate',
    'wmShowHit', 'wmShutOver', 'wmSnapshot', 'wmSpec', 'wmSplash', 'wmStartLoop', 'wmStartTour',
    'wmStep', 'wmStepsBusy', 'wmStepsClear', 'wmSwing', 'wmSyncLock', 'wmTick', 'wmTrapFx',
    'wmWaiting', 'wmWalkFlush', 'wmWalkStart', 'wmWalkStop', 'wmWalkTick', 'wmWarnDisaster',
    'wmWarpFx', 'wmZoom',
}
assert len(FUNCS_BEFORE_SPLIT) == 175, "snapshot เพี้ยน — ต้องมี 175 ชื่อเป๊ะ"
WM_FUNCS_BEFORE_SPLIT = {n for n in FUNCS_BEFORE_SPLIT if re.match(r"^wm[A-Z]", n)}
assert len(WM_FUNCS_BEFORE_SPLIT) == 90, "ต้องมีฟังก์ชัน wm* เป๊ะ 90 ตัว"


def _script_srcs():
    return re.findall(r'<script src="([^"]+)"></script>', HTML)


def test_ทุกสคริปต์ที่_play_html_อ้างถึงต้องมีไฟล์จริง():
    for src in _script_srcs():
        p = WEB / src.lstrip("/")
        assert p.exists(), f"play.html อ้างถึง {src} แต่ไม่มีไฟล์จริง"


def test_ถ้ามี_games_worms_ui_js_ต้องถูกอ้างถึงหลัง_play_js():
    """decision: worms_ui.js ต้องโหลดหลัง play.js (play.js มีตัวช่วยกลาง 4 ตัวที่ worms* เรียกใช้)"""
    worms_ui = WEB / "games" / "worms_ui.js"
    if not worms_ui.exists():
        pytest.skip("ยังไม่ถึงขั้นตอนแยก games/worms_ui.js")
    srcs = _script_srcs()
    assert "/games/worms_ui.js" in srcs, "play.html ยังไม่ได้ใส่ <script> โหลด games/worms_ui.js"
    assert srcs.index("/games/worms_ui.js") > srcs.index("/play.js"), \
        "games/worms_ui.js ต้องโหลดหลัง play.js"


def test_ฟังก์ชัน_wm_ต้องไม่หายระหว่างย้าย():
    """เทียบกับ snapshot 90 ตัวก่อนผ่า play.js (09-02)

    ⚠️ เช็คแค่ "ไม่หาย" ไม่ล็อกจำนวนเป๊ะ 90 — เพิ่มฟังก์ชัน wm* ใหม่เป็นเรื่องปกติ
    (เช่น wmGameArea ที่เพิ่ม 09-03 ตอนแก้จอเกมโผล่คาหน้าเลือกโหมด)
    ล็อกจำนวนไว้จะทำให้แก้บั๊กทีไรเทสแดงทุกที ทั้งที่ไม่มีอะไรเสียหาย
    """
    src = conftest.play_js_source()
    found = set(re.findall(r"^(?:async )?function (wm[A-Z][A-Za-z0-9_]*)\(", src, re.MULTILINE))
    missing = WM_FUNCS_BEFORE_SPLIT - found
    assert not missing, f"ฟังก์ชัน wm* หายไประหว่างย้าย: {sorted(missing)}"
    assert len(found) >= 90, f"ฟังก์ชัน wm* น้อยกว่าเดิม: เจอ {len(found)} ตัว (เคยมี 90)"


def test_ไม่มีฟังก์ชันไหนหายไปทั้งหมด175ตัว():
    """เทียบกับ snapshot ก่อนผ่า play.js (09-02) — กันย้ายโค้ดแล้วทำฟังก์ชันหายเงียบ ๆ"""
    src = conftest.play_js_source()
    found = set(re.findall(r"^(?:async )?function ([A-Za-z_$][A-Za-z0-9_$]*)\(", src, re.MULTILINE))
    missing = FUNCS_BEFORE_SPLIT - found
    assert not missing, f"ฟังก์ชันหายไปหลังผ่าไฟล์: {sorted(missing)}"


def test_ไฟล์_web_static_ห้ามมี_import_หรือ_export():
    """ไฟล์พวกนี้เป็น script ธรรมดาโหลดผ่าน <script src> — ไม่ใช่ ES module"""
    for f in WEB.rglob("*.js"):
        text = f.read_text(encoding="utf-8")
        for i, line in enumerate(text.split("\n"), start=1):
            stripped = line.strip()
            assert not re.match(r"^(import\s|export\s|export\{)", stripped), \
                f"{f}:{i} มี import/export — ไฟล์นี้ต้องเป็น script ธรรมดา"


def test_เว็บสนามรบโหลดได้จริงและวาดเฟรมได้ไม่พัง():
    """โหลด web.js..uno.js ตามลำดับใน play.html เข้า vm จริง แล้ววาดหลายเฟรมด้วย wmStartLoop

    จับ ReferenceError ที่เทสอ่านข้อความมองไม่เห็น (เช่นย้ายฟังก์ชัน wm* แล้วลืมย้าย
    ตัวแปร global คู่กัน — พังตอนรันจริงแต่เทสอ่านข้อความผ่านหมด)
    """
    if not shutil.which("node"):
        pytest.skip("เครื่องนี้ไม่มี node")
    r = subprocess.run(["node", "tests/worms_boot.js"],
                       capture_output=True, text=True, encoding="utf-8")
    assert r.returncode == 0, r.stdout + r.stderr
