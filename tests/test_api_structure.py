# tests/test_api_structure.py
"""เทสคุมโครงสร้างตอนผ่า license_server/web_api.py เป็น controller (รื้อโครงสร้าง 09-02 ขั้นที่ 4)

กันเคสที่อันตรายที่สุดของงานนี้: ย้าย route แล้ว "หายไปเงียบ ๆ" เพราะลืมรวม router ย่อย
เว็บจะไม่ 404 ให้เห็นตอนรันเทส แต่จะ 404 ตอนรันจริง — เทสชุดนี้จับก่อนถึงมือผู้เล่น
"""
import pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent

# เส้นฐานจริงที่วัดไว้ก่อนเริ่มรื้อ (2026-09-03): len(web_api.router.routes) == 81
EXPECTED_ROUTES = {
    ('/api/web/admin/cmdlog', ('GET',)),
    ('/api/web/admin/login', ('POST',)),
    ('/api/web/admin/logout', ('POST',)),
    ('/api/web/admin/news', ('POST',)),
    ('/api/web/admin/news/{news_id}', ('DELETE',)),
    ('/api/web/admin/news/{news_id}', ('PUT',)),
    ('/api/web/admin/ping', ('GET',)),
    ('/api/web/admin/topups', ('GET',)),
    ('/api/web/admin/topups/{topup_id}/approve', ('POST',)),
    ('/api/web/admin/topups/{topup_id}/reject', ('POST',)),
    ('/api/web/adventure/act', ('POST',)),
    ('/api/web/adventure/respawn', ('POST',)),
    ('/api/web/adventure/state', ('GET',)),
    ('/api/web/adventure/walk', ('POST',)),
    ('/api/web/bag/junk-preview', ('GET',)),
    ('/api/web/bag/sell-junk', ('POST',)),
    ('/api/web/bank', ('POST',)),
    ('/api/web/bank/fee', ('GET',)),
    ('/api/web/blackjack', ('GET',)),
    ('/api/web/blackjack', ('POST',)),
    ('/api/web/board', ('GET',)),
    ('/api/web/board/roll', ('POST',)),
    ('/api/web/casino', ('POST',)),
    ('/api/web/codex', ('GET',)),
    ('/api/web/continents', ('GET',)),
    ('/api/web/craft', ('POST',)),
    ('/api/web/craft/list', ('GET',)),
    ('/api/web/fashion/gacha', ('GET',)),
    ('/api/web/fashion/gacha', ('POST',)),
    ('/api/web/friends/{target_id}/profile', ('GET',)),
    ('/api/web/gamedata', ('GET',)),
    ('/api/web/goldbar', ('POST',)),
    ('/api/web/goldbar/prices', ('GET',)),
    ('/api/web/item/drop', ('POST',)),
    ('/api/web/item/use', ('POST',)),
    ('/api/web/lobby/invite', ('POST',)),
    ('/api/web/login/code', ('POST',)),
    ('/api/web/login/status', ('GET',)),
    ('/api/web/login/t/{token}', ('GET',)),
    ('/api/web/logout', ('POST',)),
    ('/api/web/market', ('GET',)),
    ('/api/web/market', ('POST',)),
    ('/api/web/me/achievements', ('GET',)),
    ('/api/web/me/books', ('GET',)),
    ('/api/web/me/daily', ('GET',)),
    ('/api/web/me/daily/claim', ('POST',)),
    ('/api/web/me/fashion', ('GET',)),
    ('/api/web/me/fashion', ('POST',)),
    ('/api/web/me/friends', ('GET',)),
    ('/api/web/me/friends', ('POST',)),
    ('/api/web/me/game', ('GET',)),
    ('/api/web/me/partner', ('GET',)),
    ('/api/web/me/pets', ('GET',)),
    ('/api/web/me/pets', ('POST',)),
    ('/api/web/me/profile', ('GET',)),
    ('/api/web/me/season', ('GET',)),
    ('/api/web/me/season/claim', ('POST',)),
    ('/api/web/me/season/premium', ('POST',)),
    ('/api/web/me/session', ('GET',)),
    ('/api/web/me/title', ('POST',)),
    ('/api/web/news', ('GET',)),
    ('/api/web/news/{news_id}', ('GET',)),
    ('/api/web/pvp/worms/map', ('GET',)),
    ('/api/web/pvp/worms/match', ('GET',)),
    ('/api/web/pvp/worms/match', ('POST',)),
    ('/api/web/pvp/worms/room', ('GET',)),
    ('/api/web/pvp/worms/room', ('POST',)),
    ('/api/web/roleshop', ('GET',)),
    ('/api/web/roleshop', ('POST',)),
    ('/api/web/roleshop/ticket/{ticket_id}', ('GET',)),
    ('/api/web/shop', ('POST',)),
    ('/api/web/shop/items', ('GET',)),
    ('/api/web/topup', ('POST',)),
    ('/api/web/topup/rate', ('GET',)),
    ('/api/web/topup/{topup_id}/qr', ('GET',)),
    ('/api/web/topup/{topup_id}/slip', ('GET',)),
    ('/api/web/topup/{topup_id}/slip', ('POST',)),
    ('/api/web/uno', ('GET',)),
    ('/api/web/uno', ('POST',)),
    ('/api/web/uno/room', ('GET',)),
    ('/api/web/uno/room', ('POST',)),
}


def _flatten(routes, prefix=""):
    """คลี่ route ให้เป็น (path, methods) แบน ๆ พร้อมต่อ prefix ให้ครบ

    ⚠️ กับดักที่บรีฟเตือนไว้: FastAPI เวอร์ชันนี้ห่อ route ที่มาจาก include_router()
    (ทั้ง app.include_router และ router.include_router ที่ซ้อนกันในนี้ตอนรวม controller
    ย่อยเข้า api_web.router) เป็น `_IncludedRouter` ซึ่งไม่มี .path/.methods ตรง ๆ
    และ .path ของ route ข้างในเป็น path สัมพัทธ์ (ไม่มี prefix ของ router ที่ include มัน)
    ต้องคลี่ผ่าน .original_router.routes แล้วต่อ prefix จาก .include_context เอง
    """
    out = []
    for r in routes:
        if hasattr(r, "original_router"):
            sub_prefix = getattr(r.include_context, "prefix", "") or ""
            out.extend(_flatten(r.original_router.routes, prefix + sub_prefix))
        elif hasattr(r, "path") and hasattr(r, "methods"):
            out.append((prefix + r.path, tuple(sorted(r.methods))))
    return out


def _route_set():
    from license_server import web_api
    routes = list(web_api.router.routes)
    seen = _flatten(routes)
    return routes, seen


def test_endpoint_ครบเท่าเดิม():
    """เส้นฐานจริงที่วัดไว้ก่อนรื้อ: 81 endpoint จริง — ตัวเลขห้ามลด

    ⚠️ นับจาก web_api.router.routes ตรง ๆ ใช้ไม่ได้อีกต่อไปหลังเริ่มรวม controller ย่อย
    (route ที่มาจาก include_router ถูกห่อเป็น _IncludedRouter 1 ก้อนต่อ 1 sub-router
    ไม่ใช่ 1 ก้อนต่อ 1 endpoint) ต้องคลี่ด้วย _flatten() ก่อนนับเสมอ
    """
    _, seen = _route_set()
    assert len(seen) >= 81, f"endpoint หายไป เหลือ {len(seen)} (ก่อนรื้อมี 81)"


def test_เซตของpathตรงเป๊ะกับก่อนรื้อ():
    """เทียบเป็นเซต (path, methods) ไม่ใช่แค่จำนวน — กันเคสจำนวนตรงแต่ path เพี้ยน"""
    _, seen = _route_set()
    assert set(seen) == EXPECTED_ROUTES, (
        f"หายไป: {EXPECTED_ROUTES - set(seen)} | เกินมา: {set(seen) - EXPECTED_ROUTES}"
    )


def test_router_ตัวเดียวกับสะพาน():
    """สะพาน web_api.router ต้องเป็นตัวเดียวกับ api_web.router เป๊ะ (ไม่ใช่แค่หน้าตาเหมือน)"""
    from license_server import web_api
    from license_server import api_web
    assert web_api.router is api_web.router


def test_ทุกไฟล์ควบคุมมีrouterของตัวเอง():
    """แต่ละไฟล์ใน api_web/ (ยกเว้น deps.py/__init__.py) ต้องมี router เป็น APIRouter"""
    from fastapi import APIRouter
    import importlib
    pkg_dir = ROOT / "license_server" / "api_web"
    if not pkg_dir.is_dir():
        return
    skip = {"__init__.py", "deps.py", "__pycache__"}
    mods = []
    for f in pkg_dir.glob("*.py"):
        if f.name in skip:
            continue
        mods.append(f"license_server.api_web.{f.stem}")
    for f in (pkg_dir / "games").glob("*.py") if (pkg_dir / "games").is_dir() else []:
        if f.name in skip:
            continue
        mods.append(f"license_server.api_web.games.{f.stem}")
    # commit แรกยังไม่มี controller ย้ายมา (มีแค่ deps.py) — ไฟล์ที่มีอยู่ต้องถูกต้องเท่านั้น
    for modname in mods:
        mod = importlib.import_module(modname)
        assert hasattr(mod, "router"), f"{modname} ไม่มี router"
        assert isinstance(mod.router, APIRouter), f"{modname}.router ไม่ใช่ APIRouter"


def test_controllerห้ามimportweb_apiย้อนกลับ():
    """ไฟล์ย่อยห้าม import web_api (สะพาน) กลับ — กัน import วน"""
    pkg_dir = ROOT / "license_server" / "api_web"
    if not pkg_dir.is_dir():
        return
    bad = []
    for f in list(pkg_dir.rglob("*.py")):
        if f.name == "__init__.py" and f.parent == pkg_dir:
            continue
        src = f.read_text(encoding="utf-8")
        if "import web_api" in src or "from license_server import web_api" in src:
            bad.append(str(f.relative_to(ROOT)))
    assert not bad, f"ไฟล์เหล่านี้ import web_api ย้อนกลับ (ห้าม): {bad}"


def test_depsห้ามimportcontrollerอื่น():
    """deps.py ต้องเป็นชั้นล่างสุด ห้ามพึ่งไฟล์ควบคุมตัวไหนเลย"""
    deps = ROOT / "license_server" / "api_web" / "deps.py"
    if not deps.is_file():
        return
    src = deps.read_text(encoding="utf-8")
    for bad_mod in ("auth", "player", "bank", "shop", "topup", "adventure",
                     "admin", "misc", ".games"):
        assert f"api_web.{bad_mod}" not in src and f"api_web import {bad_mod}" not in src, (
            f"deps.py พึ่ง controller {bad_mod} — ต้องกลับด้าน"
        )
