"""✨ ออร่าแฟชั่นต้องขยับตลอด ทุกจอ ทุกโหมด

จุดที่พังง่ายมี 2 อย่างและไม่มีอะไรฟ้องเลย:
  1. วาดออร่าโดยไม่ส่งเลขเฟรม → t=0 ตลอด = ภาพนิ่งสนิท
  2. จอที่วาดครั้งเดียวแล้วไม่วาดซ้ำ (โปรไฟล์/หน้าผจญภัย/การ์ดใหญ่) = นิ่งเหมือนกัน
เทสนี้รัน sprite.js จริงใน node แล้วเทียบพิกเซลระหว่างเฟรม
"""
import json
import pathlib
import re
import shutil
import subprocess

import pytest
from tests import conftest

WEB = pathlib.Path("license_server/web_static")
SPRITE = (WEB / "sprite.js").read_text(encoding="utf-8")
PLAY = conftest.play_js_source()
SCENE = (WEB / "scene.js").read_text(encoding="utf-8")

CHAR = ("{race:'Human',cls:'Warrior',armor:'None',weapon:'Iron_Weapon',pose:'idle',"
        "fashion:{aura:'light_halo'}}")

# canvas จำลองแบบบางที่สุด — เก็บแค่ "วาดอะไรลงตรงไหนด้วยสีอะไร" ไว้เทียบเฟรม
HARNESS = r"""
let out = [], _fill = '#000';
const ctx = {
  set fillStyle(v) { _fill = v; }, get fillStyle() { return _fill; },
  set strokeStyle(v) {}, set lineWidth(v) {}, set globalAlpha(v) {}, get globalAlpha() { return 1; },
  fillRect(x, y, w, h) { out.push([Math.round(x), Math.round(y), Math.round(w), Math.round(h), _fill]); },
  save() {}, restore() {}, clearRect() {}, beginPath() {}, closePath() {},
  ellipse() {}, arc() {}, rect() {}, moveTo() {}, lineTo() {}, fill() {}, stroke() {},
};
let CLOCK = 0;
globalThis.performance = { now: () => CLOCK };

__SPRITE__

const snap = fn => { out = []; fn(); return JSON.stringify(out); };
const report = {};

// ① ส่งเลขเฟรมต่างกัน ภาพต้องต่างกัน (ออร่าทุกแบบในแคตตาล็อก)
report.auraFrames = {};
for (const key of Object.keys(FASHION_AURA)) {
  const shots = [0, 7, 15, 31, 60].map(f => snap(() => drawAura(ctx, 0, 0, 4, key, f)));
  report.auraFrames[key] = new Set(shots).size;
}

// ② วาดตัวละครโดย "ไม่ส่ง" เลขเฟรม — ต้องเดินตามนาฬิกากลางเอง
CLOCK = 0;
const a = snap(() => drawCharacter(ctx, 0, 0, 4, __CHAR__));
CLOCK = 1000;
const b = snap(() => drawCharacter(ctx, 0, 0, 4, __CHAR__));
report.movesWithoutFrame = a !== b;

// ③ ส่งเลขเฟรมมาเอง ต้องชนะนาฬิกากลาง (ฉากผจญภัยคุมจังหวะเองได้)
CLOCK = 0;
const c = snap(() => drawCharacter(ctx, 0, 0, 4, { ...__CHAR__, frame: 5 }));
CLOCK = 999999;
const d = snap(() => drawCharacter(ctx, 0, 0, 4, { ...__CHAR__, frame: 5 }));
report.frameWins = c === d;

// ④ ไม่ได้ใส่ออร่า = ต้องไม่มีอะไรเพิ่ม (ไม่มีลูปเปล่า ๆ กินแบต)
const plain = { ...__CHAR__, fashion: {} };
CLOCK = 0; const e = snap(() => drawCharacter(ctx, 0, 0, 4, plain));
CLOCK = 5000; const g = snap(() => drawCharacter(ctx, 0, 0, 4, plain));
report.noAuraNoMotion = e === g;

console.log(JSON.stringify(report));
"""


@pytest.fixture(scope="module")
def report(tmp_path_factory):
    node = shutil.which("node")
    if not node:
        pytest.skip("ไม่มี node ในเครื่องนี้")
    src = HARNESS.replace("__SPRITE__", SPRITE).replace("__CHAR__", CHAR)
    f = tmp_path_factory.mktemp("aura") / "aura.mjs"
    f.write_text(src, encoding="utf-8")
    r = subprocess.run([node, str(f)], capture_output=True, text=True, encoding="utf-8")
    assert r.returncode == 0, f"รัน sprite.js ไม่ผ่าน:\n{r.stderr[-2000:]}"
    return json.loads(r.stdout.strip().splitlines()[-1])


def test_every_aura_looks_different_each_frame(report):
    """ออร่าที่ภาพเหมือนเดิมทุกเฟรม = ผู้เล่นเห็นเป็นภาพนิ่ง"""
    for key, distinct in report["auraFrames"].items():
        assert distinct >= 4, f"ออร่า {key} วาดออกมาซ้ำกัน ({distinct}/5 เฟรมที่ต่างกัน)"


def test_aura_moves_even_when_nobody_passes_a_frame(report):
    """จุดที่วาดตัวละครแบบไม่ส่ง frame (โปรไฟล์/การ์ด/PVP ในอนาคต) ก็ต้องขยับ"""
    assert report["movesWithoutFrame"], "ไม่ส่งเลขเฟรมแล้วออร่านิ่งสนิท"


def test_an_explicit_frame_still_wins(report):
    """ฉากผจญภัยส่งเฟรมของตัวเองมา ต้องได้จังหวะตรงกับฉาก ไม่ใช่นาฬิกากลาง"""
    assert report["frameWins"], "ส่ง frame มาแล้วยังโดนนาฬิกากลางแทรก"


def test_no_aura_means_no_movement(report):
    assert report["noAuraNoMotion"], "ไม่ได้ใส่ออร่าแต่ภาพยังเปลี่ยนเอง"


# ── ฝั่งการต่อสาย: จอที่วาดครั้งเดียวต้องถูกวาดซ้ำ ──

def test_static_canvases_repaint():
    """ทุกจอที่วาด drawCharacter แบบครั้งเดียว ต้องอยู่ในลูป auraRepaint"""
    assert "function auraRepaint" in PLAY, "ไม่มีลูปวาดซ้ำใน play.js"
    calls = len(re.findall(r"\bauraRepaint\(", PLAY))
    assert calls >= 4, f"ต่อลูปวาดซ้ำแค่ {calls - 1} จอ (ต้องครบ 3 จอ: โปรไฟล์/ผจญภัย/การ์ดใหญ่)"


def test_repaint_loop_stops_when_the_aura_comes_off():
    """ไม่มีออร่าแล้วยังหมุน rAF ทิ้งไว้ = กินแบตมือถือฟรี ๆ"""
    fn = PLAY[PLAY.index("function auraRepaint("):]
    fn = fn[:fn.index("\n}\n")]
    assert re.search(r"if \(!\(\(CHAR\.fashion \|\| \{\}\)\.aura\)\).*auraLoop = 0", fn), \
        "ลูปวาดซ้ำไม่มีทางหยุด"


def test_the_adventure_scene_drives_the_aura_with_its_own_frame():
    """ฉากผจญภัยวาดใหม่ทุกเฟรมอยู่แล้ว ต้องส่งเลขเฟรมไปให้ออร่าจังหวะตรงกัน"""
    assert "frame: this.frame" in SCENE, "ฉากผจญภัยไม่ได้ส่งเลขเฟรมให้ตัวละคร"
