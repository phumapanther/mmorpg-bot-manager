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
from tests import conftest

WEB = pathlib.Path("license_server/web_static")
SFX = (WEB / "sfx.js").read_text(encoding="utf-8")
PLAY = conftest.play_js_source()

# เบราว์เซอร์จำลองแบบบางที่สุดที่ sfx.js ต้องใช้ — นับว่ามีการจองเสียงกี่ครั้ง
HARNESS = r"""
let scheduled = 0, oscs = 0, srcs = 0;
let freqs = [], gains = [];            // ค่าที่ถูกจองจริง — ใช้ตรวจการแปรผันและแรงกระแทก
const node = () => ({
  connect() {}, disconnect() {},
  gain: { value: 0, setValueAtTime(v) { gains.push(v); }, linearRampToValueAtTime() {},
          exponentialRampToValueAtTime() {} },
  frequency: { value: 0, setValueAtTime(v) { freqs.push(v); },
               exponentialRampToValueAtTime() {} },
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

// 🎲 เสียงเดิมเล่นซ้ำต้องไม่เหมือนเดิมเป๊ะ (mutate ของ jsfxr)
freqs = [];
for (let i = 0; i < 20; i++) SFX.play('hit');
report.repeatVaries = new Set(freqs.map(f => f.toFixed(4))).size;

// แต่เพลงคลอห้ามเพี้ยนคีย์ — เปิดเพลงเดิมสองรอบต้องได้โน้ตชุดเดิมเป๊ะ
if (!SFX.musicEnabled) SFX.toggleMusic();     // ด้านบนปิดเพลงค้างไว้ ต้องเปิดคืนก่อน
SFX.music(null); freqs = []; SFX.music(cur); const bar1 = freqs.slice();
report.musicBarNotes = bar1.length;
SFX.music(null); freqs = []; SFX.music(cur);
report.musicStaysInTune = JSON.stringify(bar1) === JSON.stringify(freqs);

// 💥 punch = ดังทะลุระดับปกติตอนต้น (p_env_punch ของ jsfxr)
gains = []; SFX.play('boom');  report.boomPeak = Math.max(...gains);
gains = []; SFX.play('hit');   report.plainPeak = Math.max(...gains);

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


def _event_sfx():
    """{เหตุการณ์: ชื่อเสียง} จากตาราง EVENT_SFX ใน play.js"""
    block = re.search(r"const EVENT_SFX = \{(.*?)\};", PLAY, re.S)
    assert block, "หาตาราง EVENT_SFX ไม่เจอ"
    return dict(re.findall(r"(\w+):\s*'(\w+)'", block.group(1)))


def _vehicles():
    from bot.game_modifiers import VEHICLES
    return set(VEHICLES)


def _played_names():
    """ชื่อเสียงทุกตัวที่หน้าเว็บเรียกจริง — ทั้งที่เขียนตรง ๆ และที่มาจากตาราง"""
    out = set()
    for call in re.findall(r"SFX\.play\(([^();]*)\)", PLAY):
        # ตัดฝั่งที่เป็นการ "เทียบค่า" ออกก่อน — `x === 'travel' ? ...` ไม่ใช่ชื่อเสียง
        out |= set(re.findall(r"'(\w+)'", re.sub(r"[=!]==?\s*'\w+'", "", call)))
    out.discard("veh_")                       # ตัวต่อหน้าชื่อพาหนะ ไม่ใช่ชื่อเสียง
    out |= set(_event_sfx().values())
    out |= {"veh_" + v for v in _vehicles()}
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
            "foehit", "foecrit", "sellall", "gacha", "rest", "revive"}
    assert want <= set(report["names"]), f"ยังขาดเสียง: {sorted(want - set(report['names']))}"
    assert want <= _played_names(), \
        f"มีเสียงแต่ไม่มีใครเรียกใช้: {sorted(want - _played_names())}"


def test_the_same_sound_never_plays_exactly_the_same_twice(report):
    """ยืมแนวคิด mutate() ของ jsfxr — เสียงเดิมเป๊ะทุกครั้งฟังเป็นหุ่นยนต์

    ในสนามรบ เสียงโดนตี/ฝีเท้า/ระเบิด ดังกันนับสิบครั้งต่อแมตช์
    ถ้าเหมือนกันเป๊ะทุกใบ หูจับได้ทันทีว่าเป็นเสียงอัดซ้ำ
    """
    assert report["repeatVaries"] > 10,         f"เล่นเสียงเดิม 20 ครั้งได้ความถี่ต่างกันแค่ {report['repeatVaries']} ค่า"


def test_the_background_music_never_goes_out_of_tune(report):
    """แปรผันได้เฉพาะเอฟเฟกต์ — เพลงคลอเพี้ยนคีย์คือฟังไม่ได้เลย"""
    assert report["musicBarNotes"] > 4,         f"เทสนี้วัดอะไรไม่ได้เลย — เปิดเพลงแล้วได้โน้ตแค่ {report['musicBarNotes']} ตัว"
    assert report["musicStaysInTune"], "เพลงพื้นหลังโดนสุ่มความถี่ไปด้วย คีย์เพี้ยน"


def test_the_explosion_hits_harder_than_a_normal_sound(report):
    """punch ของ jsfxr — ดังทะลุระดับปกติตอนต้นแล้วยุบทันที

    ไม่มีตัวนี้ เสียงระเบิดจะเป็น "ซ่า" เฉย ๆ ไม่ใช่ "ตูม"
    """
    assert report["boomPeak"] > 1, f"เสียงระเบิดไม่มีแรงกระแทก (ยอด {report['boomPeak']})"
    assert report["plainPeak"] <= 1,         f"เสียงธรรมดาก็ดังทะลุเพดาน ({report['plainPeak']}) — punch ไปโดนทุกเสียง"


def test_the_arena_stopped_borrowing_the_trap_sound_for_everything(report):
    """เดิมระเบิด/ของสปอน/กระโดด/ขึ้นเรือ ยืมเสียงกับดักกับเสียงสกิลมาใช้หมด
    ฟังแล้วแยกไม่ออกว่าเกิดอะไรขึ้นถ้าไม่มองจอ
    """
    for name in ("boom", "jump", "ferry"):
        assert name in report["names"], f"ยังไม่มีเสียง {name}"
        assert report["sounds"][name] > 0, f"เสียง {name} มีชื่อแต่เรียกแล้วเงียบ"
    # ต้องดูในตัวฟังก์ชันที่เกี่ยวข้องจริง ไม่ใช่ค้นทั้งไฟล์ — ไม่งั้นมีที่อื่นเรียกอยู่ก็ผ่าน
    nl = chr(10)
    def body(head):
        a = PLAY.index(head)
        return PLAY[a:PLAY.index(nl + "}" + nl, a)]

    assert "SFX.play('boom')" in body("function wmLand("), "ระเบิดยังไม่ได้ใช้เสียงระเบิด"
    assert "SFX.play('jump')" in body("async function wmDo("), "กระโดดยังไม่ได้ใช้เสียงกระโดด"
    assert "SFX.play('ferry')" in body("function wmRideFerry("),         "ขึ้นเรือเหาะยังไม่ได้ใช้เสียงเรือเหาะ"


def test_every_event_you_can_run_into_has_its_own_sound(report):
    """เจอ NPC กับเจอดันเจี้ยนต้องฟังออกว่าคนละเรื่อง ไม่ใช่ตุ๊งเดียวกันหมด"""
    labels = set(re.findall(r"(\w+):\s*'",
                            re.search(r"const ADV_LABEL = \{(.*?)\};", PLAY, re.S).group(1)))
    ev = _event_sfx()
    # death = ตายแล้ว มีเสียงของตัวเอง · travel = แยกเสียงตามพาหนะ
    # fastwalk = ไม่ใช่เหตุการณ์ แต่คือ "เดินเร็วแล้วยังไม่เจออะไร" (ฝีเท้าดังอยู่แล้วตลอดทาง)
    missing = labels - set(ev) - {"death", "travel", "fastwalk"}
    assert not missing, f"เหตุการณ์ที่เจอแล้วเงียบ: {sorted(missing)}"
    unknown = set(ev.values()) - set(report["names"])
    assert not unknown, f"ชี้ไปเสียงที่ไม่มีอยู่จริง: {sorted(unknown)}"

    # ห้ามใช้เสียงเดียวกันหลายเหตุการณ์ ยกเว้น danger (โจรปล้น/โดนปล้น = อันตรายเหมือนกัน)
    used = [s for e, s in ev.items() if s != "danger"]
    assert len(used) == len(set(used)), f"มีเหตุการณ์ใช้เสียงซ้ำกัน: {sorted(ev.items())}"


def test_every_vehicle_sounds_different(report):
    """พาหนะใหม่โผล่มาแล้วลืมใส่เสียง = ขึ้นยานแล้วเงียบ"""
    missing = {v for v in _vehicles() if "veh_" + v not in report["names"]}
    assert not missing, f"พาหนะที่ยังไม่มีเสียง: {sorted(missing)}"
    assert "'veh_' + g.encounter.vehicle" in PLAY, "หน้าเว็บไม่ได้เลือกเสียงตามพาหนะ"


# ทุกปุ่มที่ขยับเงิน/ของ ต้องมีเสียงตอบรับ
# เจอบ่อยว่าเพิ่มปุ่มใหม่แล้วลืมใส่เสียง ผู้เล่นกดแล้วไม่รู้ว่าติดไหม
GOLD_ENDPOINTS = [
    "/api/web/bank",              # ฝาก/ถอน/โอน
    "/api/web/goldbar",           # ซื้อ/ขายทองคำแท่ง
    "/api/web/shop",              # ซื้อ/ขายกับร้าน
    "/api/web/craft",             # คราฟของ
    "/api/web/bag/sell-junk",     # เทขายวัสดุทั้งกระเป๋า
    "/api/web/item/use",          # ใช้/สวมไอเทม
    "/api/web/roleshop",          # ซื้อยศ + กดกาชา
    "/api/web/board/roll",        # ทอยเต๋ารับของรายวัน
    "/api/web/me/daily/claim",    # รับรางวัลภารกิจ
    "/api/web/me/season/claim",   # รับรางวัลซีซั่นพาส
    "/api/web/me/season/premium",  # ซื้อสายพรีเมียม
]


def test_every_action_that_moves_gold_makes_a_sound():
    for path in GOLD_ENDPOINTS:
        # ต้องปิดท้ายด้วยเครื่องหมายคำพูด — ไม่งั้น /bank ไปชนกับ /bank/fee ที่แค่ดูค่าธรรมเนียม
        for i in [m.start() for m in re.finditer(re.escape(path) + r"[\"']", PLAY)]:
            window = PLAY[max(0, i - 400):i + 700]
            assert "SFX." in window, f"กด {path} แล้วเงียบ — ไม่รู้ว่าติดหรือไม่ติด"


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
