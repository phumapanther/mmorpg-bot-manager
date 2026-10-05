"""🌐 ดึงข้อความที่ต้องแปล + เช็คว่าแปลครบ

    python scripts/i18n_extract.py           รายงาน: ยังไม่แปล / คีย์ร้าง / ข้อความไทยที่ยังไม่ติดป้าย
    python scripts/i18n_extract.py --write   เติมคีย์ใหม่ (ค่าว่าง) ลง en/zh/ja.json ให้แปลต่อ

ข้อความไทยคือคีย์ · ที่มาของคีย์:
  .py   → tr("...")                       (bot/ core/ license_server/)
  .js   → tr("...")                       (web_static/**/*.js ยกเว้น i18n.js)
  .html → data-i18n / data-i18n-html / data-i18n-attr + tr("...") ใน <script> ของหน้า
เทส tests/test_i18n_*.py ใช้ฟังก์ชันในไฟล์นี้ตัดสิน — แก้กฎที่นี่ที่เดียว
สเปก: docs/superpowers/specs/2026-10-05-i18n-design.md
"""
import ast
import json
import re
import sys
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WEB = ROOT / "license_server" / "web_static"
LOCALES = WEB / "locales"
LANGS = ("en", "zh", "ja")
PY_DIRS = ("bot", "core", "license_server")
ADMIN_PAGES = {"admin.html"}                       # หน้าแอดมินไม่แปล (สเปกข้อ 5)
I18N_ATTRS = {"title", "placeholder", "alt", "aria-label", "content"}
VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input",
        "link", "meta", "source", "track", "wbr"}
THAI = re.compile(r"[฀-๿]")
_TR_CALL = re.compile(r"\btr\(")


def norm(s):
    """ยุบช่องว่างทุกแบบเหลือช่องเดียว — ตรงกับ i18nKey() ใน i18n.js"""
    return re.sub(r"\s+", " ", s).strip()


# ── Python ────────────────────────────────────────────────────────────────

def keys_from_py(src, name="<py>"):
    """คืน (คีย์, ปัญหา) จาก tr("...") / i18n.tr("...") ในซอร์สไพทอน"""
    keys, problems = set(), []
    if not _TR_CALL.search(src):
        return keys, problems
    for node in ast.walk(ast.parse(src)):
        if not isinstance(node, ast.Call):
            continue
        f = node.func
        fname = f.id if isinstance(f, ast.Name) else f.attr if isinstance(f, ast.Attribute) else None
        if fname != "tr":
            continue
        a = node.args[0] if node.args else None
        if isinstance(a, ast.Constant) and isinstance(a.value, str):
            keys.add(a.value)
        else:
            problems.append(f"{name}:{node.lineno} tr() ต้องรับข้อความตรง ๆ ไม่ใช่ตัวแปร")
    return keys, problems


# ── JavaScript ────────────────────────────────────────────────────────────

_JS_STR = r'''"(?:[^"\\\n]|\\.)*"|'(?:[^'\\\n]|\\.)*'|`(?:[^`\\]|\\.)*`'''
_JS_TR = re.compile(r"\btr\(\s*(" + _JS_STR + ")?", re.S)
_JS_TR_LIT = re.compile(r"\btr\(\s*(?:" + _JS_STR + r")(?:\s*\))?", re.S)   # กิน ) ปิดด้วยถ้าไม่มีตัวแปร
# คอมเมนต์ // ที่ไม่ได้ต่อจาก : (กัน https://) และ /* ... */
_JS_COMMENT = re.compile(r"/\*.*?\*/|(?<![:\\])//[^\n]*", re.S)


def _js_unescape(lit):
    body = lit[1:-1]
    return re.sub(r"\\(.)", lambda m: {"n": "\n", "t": "\t"}.get(m.group(1), m.group(1)), body, flags=re.S)


def keys_from_js(src, name="<js>", line0=1):
    """คืน (คีย์, ปัญหา) จาก tr("...") ในซอร์ส JS · line0 = เลขบรรทัดของบรรทัดแรกใน src"""
    keys, problems = set(), []
    for m in _JS_TR.finditer(src):
        line = line0 + src.count("\n", 0, m.start())
        lit = m.group(1)
        if not lit:
            problems.append(f"{name}:{line} tr() ต้องรับข้อความตรง ๆ ไม่ใช่ตัวแปร")
        elif lit.startswith("`") and "${" in lit:
            problems.append(f"{name}:{line} tr(`...${{}}`) ใช้ไม่ได้ — ใช้ {{ชื่อ}} + ตัวแปรแทน")
        else:
            keys.add(_js_unescape(lit))
    return keys, problems


def _blank(m):
    return "\n" * m.group(0).count("\n")          # ลบแต่คงเลขบรรทัดไว้


def bare_thai_js(src, name="<js>", line0=1):
    """ข้อความไทยที่ยังไม่ได้ห่อ tr() (ไม่นับคอมเมนต์)"""
    s = _JS_TR_LIT.sub(_blank, src)
    s = _JS_COMMENT.sub(_blank, s)
    out = []
    for i, line in enumerate(s.split("\n"), line0):
        if THAI.search(line):
            out.append(f"{name}:{i} ยังไม่ได้ห่อ tr(): {line.strip()[:80]}")
    return out


# ── HTML ──────────────────────────────────────────────────────────────────
# serialize แบบเดียวกับที่เบราว์เซอร์คืนจาก innerHTML — ไม่งั้นคีย์ไม่ตรง บล็อกนั้นไม่แปลเงียบ ๆ

def _esc_text(s):
    return s.replace("&", "&amp;").replace("\xa0", "&nbsp;").replace("<", "&lt;").replace(">", "&gt;")


def _esc_attr(s):
    return s.replace("&", "&amp;").replace("\xa0", "&nbsp;").replace('"', "&quot;")


def _start(tag, attrs):
    return "<" + tag + "".join(f' {k}="{_esc_attr(v or "")}"' for k, v in attrs) + ">"


class _Page(HTMLParser):
    """อ่านหน้า HTML: เก็บคีย์จากป้าย data-i18n* + จับข้อความไทยที่ยังไม่ติดป้าย"""

    def __init__(self, name):
        super().__init__(convert_charrefs=True)
        self.name = name
        self.keys, self.problems, self.scripts = set(), [], []
        self.stack = []          # แท็กที่เปิดอยู่
        self.region = None       # [โหมด "text"/"html", ความลึกของเจ้าของป้าย, ชิ้นส่วนที่เก็บ]
        self.raw = 0             # อยู่ใน <script>/<style> กี่ชั้น

    def _at(self):
        return f"{self.name}:{self.getpos()[0]}"

    def _attrs(self, tag, a):
        wanted = {x.strip() for x in (a.get("data-i18n-attr") or "").split(",") if x.strip()}
        for k in sorted(wanted):
            v = norm(a.get(k) or "")
            if v:
                self.keys.add(v)
            else:
                self.problems.append(f"{self._at()} data-i18n-attr บอก {k} แต่ไม่มีค่า")
        for k in sorted(I18N_ATTRS - wanted):
            if THAI.search(a.get(k) or ""):
                self.problems.append(f"{self._at()} <{tag} {k}> เป็นไทยแต่ไม่ได้ใส่ใน data-i18n-attr")

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        self._attrs(tag, a)
        r = self.region
        if r:
            if r[0] == "text":
                self.problems.append(f"{self._at()} data-i18n มีแท็ก <{tag}> ข้างใน — ใช้ data-i18n-html")
            elif "data-i18n" in a or "data-i18n-html" in a:
                self.problems.append(f"{self._at()} ห้ามซ้อน data-i18n ใน data-i18n-html")
            r[2].append(_start(tag, attrs))
        if tag in VOID:
            return
        self.stack.append(tag)
        if tag in ("script", "style"):
            self.raw += 1
        if not r and ("data-i18n" in a or "data-i18n-html" in a):
            self.region = ["html" if "data-i18n-html" in a else "text", len(self.stack), []]

    def handle_endtag(self, tag):
        if tag in VOID or tag not in self.stack:
            return
        while self.stack:
            t = self.stack.pop()
            if t in ("script", "style"):
                self.raw -= 1
            r = self.region
            if r and len(self.stack) < r[1]:           # ปิดตัวเจ้าของป้ายแล้ว
                key = norm("".join(r[2]))
                if key:
                    self.keys.add(key)
                else:
                    self.problems.append(f"{self._at()} data-i18n ว่างเปล่า")
                self.region = None
            elif r and r[0] == "html":
                r[2].append(f"</{t}>")
            if t == tag:
                break

    def handle_data(self, data):
        if self.raw:
            if self.stack and self.stack[-1] == "script":
                self.scripts.append((self.getpos()[0], data))
            return
        r = self.region
        if r:
            r[2].append(data if r[0] == "text" else _esc_text(data))
        elif THAI.search(data):
            self.problems.append(f"{self._at()} ข้อความไทยยังไม่ได้ติดป้าย data-i18n: {norm(data)[:60]}")

    def handle_comment(self, data):
        if self.region and self.region[0] == "html":
            self.region[2].append(f"<!--{data}-->")


def scan_html(src, name="<html>"):
    """คืน (คีย์, ปัญหา) ของหน้า HTML — รวม tr() และไทยที่ยังไม่ห่อใน <script> ของหน้าด้วย"""
    p = _Page(name)
    p.feed(src)
    p.close()
    keys, problems = set(p.keys), list(p.problems)
    for line0, js in p.scripts:
        k, pr = keys_from_js(js, name, line0)
        keys |= k
        problems += pr + bare_thai_js(js, name, line0)
    return keys, problems


# ── ทั้งโปรเจ็ค ────────────────────────────────────────────────────────────

def player_pages():
    return sorted(p for p in WEB.glob("*.html") if p.name not in ADMIN_PAGES)


def collect():
    """คืน (คีย์ทั้งหมด, tr() ที่ใช้ผิด) — ปัญหาติดป้ายในหน้าดูได้จาก scan_html ทีละหน้า"""
    keys, problems = set(), []
    for d in PY_DIRS:
        for f in sorted((ROOT / d).rglob("*.py")):
            if "__pycache__" in f.parts:
                continue
            k, p = keys_from_py(f.read_text(encoding="utf-8"), f.relative_to(ROOT).as_posix())
            keys |= k
            problems += p
    for f in sorted(WEB.rglob("*.js")):
        if f.name == "i18n.js":
            continue
        k, p = keys_from_js(f.read_text(encoding="utf-8"), f.relative_to(ROOT).as_posix())
        keys |= k
        problems += p
    for f in player_pages():
        keys |= scan_html(f.read_text(encoding="utf-8"), f.relative_to(ROOT).as_posix())[0]
    return keys, problems


def load(lang):
    f = LOCALES / f"{lang}.json"
    return json.loads(f.read_text(encoding="utf-8")) if f.exists() else {}


def save(lang, table):
    (LOCALES / f"{lang}.json").write_text(
        json.dumps(table, ensure_ascii=False, indent=1, sort_keys=True) + "\n", encoding="utf-8")


def main(argv):
    keys, problems = collect()
    for f in player_pages():
        problems += scan_html(f.read_text(encoding="utf-8"), f.relative_to(ROOT).as_posix())[1]
    print(f"🔑 คีย์ทั้งหมด {len(keys)}")
    for lang in LANGS:
        table = load(lang)
        missing = sorted(k for k in keys if not table.get(k))
        unused = sorted(set(table) - keys)
        print(f"[{lang}] ยังไม่แปล {len(missing)} · คีย์ร้าง {len(unused)}")
        for k in unused:
            print(f"   ร้าง: {k[:70]}")
        if "--write" in argv:
            for k in missing:
                table.setdefault(k, "")
            save(lang, table)
    for p in sorted(set(problems)):
        print("⚠️ ", p)
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")      # คอนโซลวินโดวส์ไม่ใช่ UTF-8 → พิมพ์ไทย/emoji แล้วพัง
    sys.exit(main(sys.argv[1:]))
