"""🔊 เสียงประกอบเว็บเกม — เสียงพังห้ามทำให้เกมพัง และห้ามมีเสียงที่เรียกแล้วเงียบ

เสียงเป็นของที่เทสอัตโนมัติไม่ได้ว่า "เพราะไหม" แต่เทสได้ว่า
(1) ทุกชื่อที่หน้าเว็บเรียกมีอยู่จริง (2) เรียกแล้วมีการสั่งเล่นเสียงออกมาจริง
(3) เพลงพื้นหลังต่อท่อนได้ไม่ขาด และสั่งหยุดแล้วหยุดจริง
"""
import json
import pathlib
import re
import shutil
import subprocess

import pytest

WEB = pathlib.Path("license_server/web_static")
SFX = (WEB / "sfx.js").read_text(encoding="utf-8")
PLAY = (WEB / "play.js").read_text(encoding="utf-8")

# เบราว์เซอร์จำลองแบบบางที่สุดที่ sfx.js ต้องใช้ — นับว่ามีการจองเสียงกี่ครั้ง
HARNESS = r"""
let scheduled = 0, oscs = 0, srcs = 0;
const node = () => ({
  connect() {}, disconnect() {},
  gain: { value: 0, setValueAtTime() {}, linearRampToValueAtTime() {},
          exponentialRampToValueAtTime() {} },
  frequency: { value: 0, setValueAtTime() {}, exponentialRampToValueAtTime() {} },
  type: '',
});
class FakeCtx {
  constructor() { this.currentTime = 0; this.sampleRate = 44100;
                  this.destination = node(); this.state = 'running'; }
  resume() { this.state = 'running'; }
  createGain() { return node(); }
  createBiquadFilter() { return node(); }
  createOscillator() { oscs++; return Object.assign(node(),
    { start(t) { scheduled++; if (t < 0) throw new Error('จองเสียงย้อนเวลา'); }, stop() {} }); }
  createBufferSource() { srcs++; return Object.assign(node(),
    { buffer: null, start(t) { scheduled++; if (t < 0) throw new Error('จองเสียงย้อนเวลา'); } }); }
  createBuffer(ch, len) { return { getChannelData: () => new Float32Array(len) }; }
}
const store = {};
globalThis.localStorage = { getItem: k => (k in store ? store[k] : null),
                            setItem: (k, v) => { store[k] = String(v); } };
globalThis.window = { AudioContext: FakeCtx };
const timers = [];
globalThis.setTimeout = (fn, ms) => { timers.push([fn, ms]); return timers.length; };
globalThis.clearTimeout = () => {};
const loops = [];
globalThis.setInterval = (fn, ms) => { loops.push([fn, ms]); return loops.length; };
globalThis.clearInterval = id => { if (id) loops[id - 1] = null; };
const running = () => loops.filter(Boolean);
globalThis.document = { addEventListener() {}, removeEventListener() {} };

__SFX_SRC__

const report = { names: SFX.names(), tracks: SFX.tracks(), sounds: {}, music: {} };

for (const n of SFX.names()) {
  const before = scheduled;
  SFX.play(n);
  report.sounds[n] = scheduled - before;
}

// ชื่อที่ไม่มีอยู่จริงต้องเงียบเฉย ๆ ไม่ใช่โยน error ใส่หน้าเกม
const q = scheduled; SFX.play('ไม่มีเสียงนี้'); report.unknownSilent = scheduled === q;

// 👣 ฝีเท้า: ก้าวแรกดังทันที แล้วเดินต่อไปเรื่อย ๆ จนกว่าจะสั่งหยุด
const w0 = scheduled;
SFX.walking(true);
report.walkFirstStepIsInstant = scheduled > w0;          // ไม่ต้องรอ 300ms ถึงจะได้ยินก้าวแรก
report.walkLoops = running().length === 1;
const w1 = scheduled;
running()[0][0](); running()[0][0]();
report.walkKeepsGoing = scheduled > w1;
SFX.walking(false);
report.walkStops = running().length === 0;
SFX.walking(true); SFX.walking(true);                    // สั่งซ้ำต้องไม่ได้สองขา
report.walkNoDoubleLoop = running().length === 1;
SFX.walking(false);

for (const t of SFX.tracks()) {
  SFX.music(null);
  const before = scheduled, tick = timers.length;
  SFX.music(t);
  report.music[t] = { notes: scheduled - before, queuedNext: timers.length > tick };
}

// สั่งเพลงเดิมซ้ำต้องไม่รีสตาร์ท (ไม่งั้นเดินทุกก้าวเพลงจะกระตุกใหม่ทุกที)
const cur = SFX.tracks()[0];
SFX.music(null); SFX.music(cur);
const s2 = scheduled; SFX.music(cur); report.repeatIsNoop = scheduled === s2;

// ปิดเสียงแล้วต้องไม่มีอะไรถูกจองเพิ่มอีก
SFX.music(null); SFX.toggle();
const s3 = scheduled;
SFX.names().forEach(n => SFX.play(n));
SFX.music(cur);
SFX.walking(true);
report.mutedIsSilent = scheduled === s3 && running().length === 0;
SFX.toggle();

// ปิดเฉพาะเพลง เอฟเฟกต์ต้องยังดังอยู่
SFX.music(null); SFX.toggleMusic();
const s4 = scheduled; SFX.music(cur); const musOff = scheduled === s4;
SFX.play('click'); report.bgmOffKeepsSfx = musOff && scheduled > s4;

console.log(JSON.stringify(report));
"""


@pytest.fixture(scope="module")
def report():
    node = shutil.which("node")
    if not node:
        pytest.skip("ไม่มี node ในเครื่องนี้ — ข้ามเทสรันจริงของเสียง")
    src = HARNESS.replace("__SFX_SRC__", SFX)
    out = subprocess.run([node, "--input-type=module", "-e", src],
                         capture_output=True, text=True, encoding="utf-8", timeout=60)
    assert out.returncode == 0, f"sfx.js รันไม่ผ่าน:\n{out.stderr}"
    return json.loads(out.stdout.strip().splitlines()[-1])


def _played_names():
    """ชื่อเสียงทุกตัวที่หน้าเว็บเรียกจริง (รวมที่เลือกด้วยเงื่อนไขในวงเล็บเดียวกัน)"""
    out = set()
    for call in re.findall(r"SFX\.play\(([^();]*)\)", PLAY):
        out |= set(re.findall(r"'(\w+)'", call))
    return out


def test_every_sound_the_page_asks_for_exists(report):
    missing = _played_names() - set(report["names"])
    assert not missing, f"หน้าเว็บเรียกเสียงที่ไม่มีอยู่จริง: {sorted(missing)}"


def test_every_sound_actually_makes_noise(report):
    """มีชื่ออย่างเดียวไม่พอ — กดแล้วต้องมีเสียงถูกจองออกมาจริง"""
    silent = [n for n, c in report["sounds"].items() if c < 1]
    assert not silent, f"เสียงที่เรียกแล้วเงียบ: {silent}"


def test_the_new_sounds_the_player_asked_for_are_there(report):
    """รายการที่ผู้เล่นสั่งไว้ — ครบทุกช่องไหม"""
    want = {"item", "trap", "caught", "use", "equip", "craft", "reward",
            "slot", "reel", "card", "bust", "bank", "gold", "buy", "pet", "chest",
            "foehit", "foecrit"}
    assert want <= set(report["names"]), f"ยังขาดเสียง: {sorted(want - set(report['names']))}"
    assert want <= _played_names(), \
        f"มีเสียงแต่ไม่มีใครเรียกใช้: {sorted(want - _played_names())}"


def test_an_unknown_sound_name_stays_quiet_instead_of_crashing(report):
    assert report["unknownSilent"], "เรียกชื่อเสียงที่ไม่มี แล้วดันไปเล่นอย่างอื่นแทน"


def test_every_continent_has_background_music(report):
    """ทวีปใหม่โผล่มาแล้วลืมใส่เพลง = เดินเข้าไปแล้วเงียบกริบ"""
    from bot.game_data import CONTINENTS
    moods = dict(re.findall(r"(\w+):\s*'(\w+)'",
                            re.search(r"const CONT_MOOD = \{(.*?)\};", PLAY, re.S).group(1)))
    missing = set(CONTINENTS) - set(moods)
    assert not missing, f"ทวีปที่ยังไม่มีเพลงพื้นหลัง: {sorted(missing)}"
    unknown = set(moods.values()) - set(report["tracks"])
    assert not unknown, f"ชี้ไปเพลงที่ไม่มีอยู่จริง: {sorted(unknown)}"


def test_music_the_page_asks_for_exists(report):
    asked = set(re.findall(r"SFX\.music\('(\w+)'\)", PLAY))
    missing = asked - set(report["tracks"])
    assert not missing, f"หน้าเว็บสั่งเปิดเพลงที่ไม่มี: {sorted(missing)}"


def test_every_track_plays_and_queues_the_next_bar(report):
    """เพลงต้องต่อท่อนเองได้ ไม่ใช่ดังท่อนเดียวแล้วเงียบ"""
    for name, info in report["music"].items():
        assert info["notes"] > 0, f"เพลง {name} ไม่มีโน้ตเลย"
        assert info["queuedNext"], f"เพลง {name} ไม่ได้จองท่อนถัดไป — จะขาดตอนจบท่อน"


def test_asking_for_the_same_track_again_does_not_restart_it(report):
    assert report["repeatIsNoop"], "สั่งเพลงเดิมซ้ำแล้วรีสตาร์ท — เดินทุกก้าวเพลงจะกระตุก"


def test_muting_really_mutes(report):
    assert report["mutedIsSilent"], "ปิดเสียงแล้วยังมีเสียงเล็ดลอดออกมา"


def test_footsteps_start_instantly_loop_and_can_be_stopped(report):
    """เดินทางใช้เวลาไม่แน่นอน ฝีเท้าจึงต้องวนเองและสั่งหยุดได้ตรงเวลา"""
    assert report["walkFirstStepIsInstant"], "ก้าวแรกต้องดังทันทีที่ออกเดิน ไม่ใช่รอรอบถัดไป"
    assert report["walkLoops"], "ฝีเท้าไม่ได้วน — ดังชุดเดียวแล้วเงียบทั้งที่ยังเดินอยู่"
    assert report["walkKeepsGoing"], "วนแล้วแต่ไม่มีเสียงออกมาในรอบถัดไป"
    assert report["walkStops"], "สั่งหยุดแล้วยังเดินไม่หยุด"
    assert report["walkNoDoubleLoop"], "กดเดินซ้ำแล้วได้ฝีเท้าซ้อนกันสองชุด"


def test_every_walk_that_starts_is_guaranteed_to_stop():
    """ฝีเท้าที่ไม่มีคนสั่งหยุดจะดังค้างทั้งเกม — ต้องหยุดใน finally เสมอ"""
    assert "SFX.walking(true)" in PLAY, "ไม่มีใครสั่งเริ่มเดินเลย"
    assert PLAY.count("SFX.walking(false)") >= PLAY.count("SFX.walking(true)")
    tail = PLAY[PLAY.index("SFX.walking(true)"):]
    fin = tail.index("} finally {")
    assert "SFX.walking(false)" in tail[fin:fin + 200], \
        "ต้องหยุดฝีเท้าใน finally ไม่งั้นเน็ตหลุดแล้วเดินค้างตลอดกาล"


def test_turning_off_music_keeps_the_sound_effects(report):
    """สองปุ่มต้องแยกกันจริง — คนที่อยากได้เสียงตีมอนแต่ไม่เอาเพลงคลอมีอยู่"""
    assert report["bgmOffKeepsSfx"], "ปิดเพลงพื้นหลังแล้วเอฟเฟกต์เงียบไปด้วย"


def test_the_page_has_a_button_for_each_switch():
    html = (WEB / "play.html").read_text(encoding="utf-8")
    assert 'id="playSfx"' in html and 'id="playBgm"' in html, "ไม่มีปุ่มเปิด/ปิดครบสองอย่าง"
    assert "SFX.toggleMusic()" in PLAY, "ปุ่มเพลงไม่ได้ต่อกับตัวสลับจริง"
