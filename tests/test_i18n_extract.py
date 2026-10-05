"""🌐 scripts/i18n_extract.py — ดึงคีย์ให้ตรงกับที่เบราว์เซอร์/ไพทอนใช้หาคำแปลจริง"""
import subprocess
import sys

from scripts import i18n_extract as X


def test_py_เก็บคีย์และจับ_tr_ที่รับตัวแปร():
    src = 'from bot.i18n import tr\nx = tr("ทอง {n}", n=1)\ny = i18n.tr("ธนาคาร")\nz = tr(name)\nw = str(5)\n'
    keys, probs = X.keys_from_py(src, "a.py")
    assert keys == {"ทอง {n}", "ธนาคาร"}
    assert probs == ["a.py:4 tr() ต้องรับข้อความตรง ๆ ไม่ใช่ตัวแปร"]


def test_js_เก็บคีย์ทุกแบบเครื่องหมายคำพูด():
    src = r'''a(tr("ทอง"));
b(tr('เงิน "สด"'));
c(tr(`ยาว`, {n: 1}));
d(tr("บรรทัด\nใหม่"));
e(tr(label));
f(tr(`มี ${x}`));
'''
    keys, probs = X.keys_from_js(src, "a.js")
    assert keys == {"ทอง", 'เงิน "สด"', "ยาว", "บรรทัด\nใหม่"}
    assert probs == ["a.js:5 tr() ต้องรับข้อความตรง ๆ ไม่ใช่ตัวแปร",
                     "a.js:6 tr(`...${}`) ใช้ไม่ได้ — ใช้ {ชื่อ} + ตัวแปรแทน"]


def test_js_จับไทยที่ยังไม่ห่อ_ไม่นับคอมเมนต์และ_url():
    src = r'''const a = tr("ห่อแล้ว");
// คอมเมนต์ไทยไม่นับ
const b = "ยังไม่ห่อ";   // ท้ายบรรทัดก็ไม่นับ
/* บล็อก
   ไทย */
const u = "https://x.y/z"; const c = 'ไทยหลัง url';
'''
    assert X.bare_thai_js(src, "a.js") == [
        'a.js:3 ยังไม่ได้ห่อ tr(): const b = "ยังไม่ห่อ";',
        "a.js:6 ยังไม่ได้ห่อ tr(): const u = \"https://x.y/z\"; const c = 'ไทยหลัง url';",
    ]


def test_html_คีย์ข้อความ_แอตทริบิวต์_และ_html_แบบเบราว์เซอร์():
    src = '''<title data-i18n>ล็อกอิน — Fragment Rift</title>
<p data-i18n>  เงิน
   สด  </p>
<input placeholder="เช่น 100" data-i18n-attr="placeholder">
<p data-i18n-html>โอนแล้ว<b>แนบสลิป</b> ดูที่<a href='/me'>โปรไฟล์</a><br/> &amp; #<span id="qrId"></span></p>
'''
    keys, probs = X.scan_html(src, "p.html")
    assert probs == []
    assert keys == {
        "ล็อกอิน — Fragment Rift",
        "เงิน สด",
        "เช่น 100",
        'โอนแล้ว<b>แนบสลิป</b> ดูที่<a href="/me">โปรไฟล์</a><br> &amp; #<span id="qrId"></span>',
    }


def test_html_จับข้อความไทยที่ยังไม่ติดป้าย():
    src = '''<p>ยังไม่ติด</p>
<button title="ปุ่มไทย">OK</button>
<p data-i18n>มี<b>แท็ก</b></p>
<a href="/game?codex=วิธีเล่น">x</a>
<script>const a = "ไทยในสคริปต์"; const b = tr("ห่อ");</script>
<div data-i18n-html>นอก <span data-i18n>ซ้อน</span></div>
<span data-i18n></span>
'''
    keys, probs = X.scan_html(src, "p.html")
    assert "ห่อ" in keys
    assert probs == [
        "p.html:1 ข้อความไทยยังไม่ได้ติดป้าย data-i18n: ยังไม่ติด",
        "p.html:2 <button title> เป็นไทยแต่ไม่ได้ใส่ใน data-i18n-attr",
        "p.html:3 data-i18n มีแท็ก <b> ข้างใน — ใช้ data-i18n-html",
        "p.html:6 ห้ามซ้อน data-i18n ใน data-i18n-html",
        "p.html:7 data-i18n ว่างเปล่า",
        'p.html:5 ยังไม่ได้ห่อ tr(): const a = "ไทยในสคริปต์"; const b = ;',
    ]


def test_หน้าแอดมินไม่อยู่ในรายการหน้าที่ต้องแปล():
    names = [p.name for p in X.player_pages()]
    assert "admin.html" not in names
    assert "index.html" in names and "play.html" in names


def test_cli_เติมคีย์ใหม่โดยไม่ลบคำแปลเดิม(tmp_path, monkeypatch):
    for lang in X.LANGS:
        (tmp_path / f"{lang}.json").write_text('{"คีย์เก่า": "old"}', encoding="utf-8")
    monkeypatch.setattr(X, "LOCALES", tmp_path)
    monkeypatch.setattr(X, "collect", lambda: ({"คีย์เก่า", "คีย์ใหม่"}, []))
    monkeypatch.setattr(X, "player_pages", lambda: [])
    assert X.main(["--write"]) == 0
    for lang in X.LANGS:
        assert X.load(lang) == {"คีย์เก่า": "old", "คีย์ใหม่": ""}


def test_cli_รันจริงได้_ไม่พังเรื่องอักษรไทยบนคอนโซลวินโดวส์():
    r = subprocess.run([sys.executable, "scripts/i18n_extract.py"], capture_output=True)
    assert r.returncode == 0, r.stderr.decode("utf-8", "replace")
    assert "คีย์ทั้งหมด" in r.stdout.decode("utf-8")
