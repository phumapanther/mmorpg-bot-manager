"""🔒 โดเมนถาวร vs quick tunnel — Panel ต้องแยกออกว่าตอนนี้ใช้แบบไหน

เจ้าของเกมตั้ง Cloudflare named tunnel ผูก fragmentrift.com ไว้แล้ว (2026-09-24)
ก่อนหน้านี้ Panel เปิด quick tunnel ทุกครั้งที่เปิดโปรแกรม แล้ว**เขียนลิงก์สุ่ม
ทับ LICENSE_SERVER_URL.txt** — ถ้าไม่ดัก โดเมนถาวรจะถูกลบทิ้งทุกครั้งที่เปิด Panel
แล้วชุดที่ build ต่อจากนั้นจะชี้ไปลิงก์สุ่มที่ตายไปแล้ว ลูกค้าสตาร์ทบอทไม่ได้ทั้งหมด
"""
import pathlib

from license_server import keygen_gui


def _write(tmp_path, text):
    p = tmp_path / "LICENSE_SERVER_URL.txt"
    p.write_text(text, encoding="utf-8")
    return str(p)


# ── ตัวตัดสิน ──

def test_โดเมนถาวรถูกมองว่าตั้งเองแล้ว(tmp_path):
    assert keygen_gui.fixed_url(_write(tmp_path, "https://fragmentrift.com")) \
        == "https://fragmentrift.com"


def test_ลิงก์_quick_tunnel_ไม่นับว่าตั้งเอง(tmp_path):
    """⭐ ใจความทั้งหมด — ลิงก์สุ่มต้องยังถูกเขียนทับได้เหมือนเดิม"""
    got = _write(tmp_path, "https://bit-ind-articles-address.trycloudflare.com")
    assert keygen_gui.fixed_url(got) is None


def test_ไฟล์ว่างหรือไม่มีไฟล์ก็ไม่นับ(tmp_path):
    assert keygen_gui.fixed_url(_write(tmp_path, "")) is None
    assert keygen_gui.fixed_url(_write(tmp_path, "\n  \n")) is None
    assert keygen_gui.fixed_url(str(tmp_path / "ไม่มีไฟล์นี้.txt")) is None


def test_placeholder_ไม่นับ(tmp_path):
    """ชุดที่ยังไม่ตั้งค่าก่อน build — ต้องไม่ถูกหลอกว่าเป็นโดเมนจริง"""
    assert keygen_gui.fixed_url(
        _write(tmp_path, "http://YOUR-LICENSE-SERVER-ADDRESS:8790")) is None
    assert keygen_gui.fixed_url(
        _write(tmp_path, "https://YOUR-LICENSE-SERVER-ADDRESS:8790")) is None


def test_http_ธรรมดาไม่นับ(tmp_path):
    """🔒 บอทส่งคีย์ผ่านลิงก์นี้ — ยอมให้เป็น http ธรรมดา = คีย์วิ่งโล่ง"""
    assert keygen_gui.fixed_url(_write(tmp_path, "http://fragmentrift.com")) is None


def test_ขึ้นบรรทัดใหม่ท้ายไฟล์ไม่กวน(tmp_path):
    """ไฟล์ที่โปรแกรมเขียนเองมี \\n ท้ายเสมอ"""
    assert keygen_gui.fixed_url(_write(tmp_path, "https://fragmentrift.com\n")) \
        == "https://fragmentrift.com"


def test_quick_tunnel_ที่มี_slash_ต่อท้ายก็ยังนับว่า_quick_tunnel(tmp_path):
    """⭐ เทียบทั้งสตริงจะพลาดข้อนี้ — แล้วลิงก์สุ่มที่ตายแล้วจะถูกล็อกไว้ถาวร

    (เจอตอนย้อนเทส 2026-09-24 — เทสชุดแรกเขียนไว้แล้วจับไม่ได้)
    """
    for url in ("https://abc-def.trycloudflare.com/",
                "https://abc-def.trycloudflare.com/api/web",
                "https://ABC-DEF.TRYCLOUDFLARE.COM"):
        assert keygen_gui.fixed_url(_write(tmp_path, url)) is None, url


def test_โดเมนที่มีคำว่า_trycloudflare_ปนแต่ไม่ใช่(tmp_path):
    """เทียบที่ชื่อโฮสต์ ไม่ใช่หาคำในสตริง"""
    for url in ("https://trycloudflare.com.fragmentrift.com",
                "https://fragmentrift.com/trycloudflare.com"):
        assert keygen_gui.fixed_url(_write(tmp_path, url)) == url


# ── ต่อเข้าโปรแกรมจริงแล้วหรือยัง ──

SRC = pathlib.Path("license_server/keygen_gui.py").read_text(encoding="utf-8")


def _body(name):
    """เนื้อในของเมธอดหนึ่งตัว — ตัดที่ 'def ' ตัวถัดไปที่ย่อหน้าเท่ากัน"""
    start = SRC.index(f"    def {name}(")
    nxt = SRC.find("\n    def ", start + 1)
    return SRC[start:nxt if nxt > 0 else len(SRC)]


def test_ตั้งโดเมนถาวรแล้วไม่เปิด_quick_tunnel_ซ้อน():
    """⭐ เขียนฟังก์ชันไว้แต่ไม่มีใครเรียก = โดเมนถูกเขียนทับเหมือนเดิม

    ต้องคืนค่าออกไปก่อนถึงบรรทัด Popen ไม่ใช่แค่โชว์ข้อความแล้วเปิดต่อ
    """
    body = _body("start_tunnel")
    assert "fixed_url()" in body, "ไม่ได้เช็คโดเมนถาวรเลย"
    assert body.index("fixed_url()") < body.index("Popen"), \
        "เช็คทีหลัง Popen — tunnel เปิดไปแล้ว"
    assert "return" in body[body.index("fixed_url()"):body.index("Popen")], \
        "เจอโดเมนถาวรแล้วไม่ return — เปิด tunnel ต่ออยู่ดี"


def test_ปุ่ม_build_ไม่เตือนตอนใช้โดเมนถาวร():
    """ด่านเตือนมีไว้กันลิงก์สุ่มไม่ตรงไฟล์ — โดเมนถาวรไม่มีปัญหานั้น"""
    assert "fixed_url()" in _body("start_build"), "ปุ่ม build ยังเตือนทุกครั้ง"


def test_quick_tunnel_ยังเขียนทับไฟล์ได้เหมือนเดิม():
    """⭐ กันแก้เกิน — เครื่องที่ยังไม่มีโดเมนต้องทำงานเหมือนเดิมทุกอย่าง"""
    assert "_save_url_file(url)" in _body("_watch_tunnel_output")
    assert 'f.write(url + "\\n")' in _body("_save_url_file")
