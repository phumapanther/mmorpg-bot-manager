"""ค่าลับอ่านจาก env var ได้ — สำหรับรันบนคลาวด์ที่ไม่มี config.json (เจ้าของเกมสั่ง 09-01)

บนคลาวด์เราไม่ส่ง config.json ขึ้นไป (อยู่ใน .gitignore) จึงต้องส่งผ่าน env แทน
แต่รันในเครื่องตัวเองต้องเหมือนเดิมเป๊ะ — ไม่ตั้ง env ก็อ่าน config.json ต่อได้
"""
import importlib
import pytest

from bot import config_loader


@pytest.fixture
def cfg(monkeypatch):
    """คุม config.json ปลอม + ล้าง env ให้สะอาดทุกเทส"""
    def _setup(data):
        monkeypatch.setattr(config_loader, "_cache", dict(data))
        return config_loader
    for k in ("DISCORD_BOT_TOKEN", "DISCORD_GUEST_TOKEN", "LICENSE_KEY"):
        monkeypatch.delenv(k, raising=False)
    return _setup


CASES = [
    ("get_token", "DISCORD_BOT_TOKEN", "bot_token"),
    ("get_guest_token", "DISCORD_GUEST_TOKEN", "guest_bot_token"),
    ("get_license_key", "LICENSE_KEY", "license_key"),
]


@pytest.mark.parametrize("fn,env_key,cfg_key", CASES)
def test_env_ชนะ_config(cfg, monkeypatch, fn, env_key, cfg_key):
    c = cfg({cfg_key: "ค่าในไฟล์"})
    monkeypatch.setenv(env_key, "ค่าจาก-env")
    assert getattr(c, fn)() == "ค่าจาก-env"


@pytest.mark.parametrize("fn,env_key,cfg_key", CASES)
def test_ไม่ตั้ง_env_ใช้_config_เหมือนเดิม(cfg, fn, env_key, cfg_key):
    c = cfg({cfg_key: "ค่าในไฟล์"})
    assert getattr(c, fn)() == "ค่าในไฟล์", "รันในเครื่องต้องไม่พัง"


@pytest.mark.parametrize("fn,env_key,cfg_key", CASES)
def test_ไม่มีทั้งคู่ได้ค่าว่าง(cfg, fn, env_key, cfg_key):
    c = cfg({})
    assert getattr(c, fn)() == ""


@pytest.mark.parametrize("fn,env_key,cfg_key", CASES)
def test_env_ว่างไม่บังของจริง(cfg, monkeypatch, fn, env_key, cfg_key):
    # docker-compose ที่ไม่ได้ตั้งค่าจะส่ง env ว่างมา ต้องไม่ทำให้ token หาย
    c = cfg({cfg_key: "ค่าในไฟล์"})
    monkeypatch.setenv(env_key, "")
    assert getattr(c, fn)() == "ค่าในไฟล์"


def test_แต่ละค่าไม่ปนกัน(cfg, monkeypatch):
    c = cfg({})
    monkeypatch.setenv("DISCORD_BOT_TOKEN", "หลัก")
    monkeypatch.setenv("DISCORD_GUEST_TOKEN", "แจก")
    monkeypatch.setenv("LICENSE_KEY", "คีย์")
    assert (c.get_token(), c.get_guest_token(), c.get_license_key()) == ("หลัก", "แจก", "คีย์")


def test_admin_secret_จาก_env(monkeypatch):
    from license_server import api
    monkeypatch.setenv("ADMIN_SECRET", "ความลับจากคลาวด์")
    assert api.get_or_create_admin_secret() == "ความลับจากคลาวด์"


def test_admin_secret_ไม่ตั้ง_env_ใช้ไฟล์เหมือนเดิม(monkeypatch, tmp_path):
    from license_server import api
    monkeypatch.delenv("ADMIN_SECRET", raising=False)
    f = tmp_path / "admin_secret.txt"
    f.write_text("ความลับในไฟล์", encoding="utf-8")
    monkeypatch.setattr(api, "_SECRET_PATH", str(f))
    assert api.get_or_create_admin_secret() == "ความลับในไฟล์"


def test_admin_secret_env_ว่างไม่บังไฟล์(monkeypatch, tmp_path):
    from license_server import api
    monkeypatch.setenv("ADMIN_SECRET", "   ")
    f = tmp_path / "admin_secret.txt"
    f.write_text("ความลับในไฟล์", encoding="utf-8")
    monkeypatch.setattr(api, "_SECRET_PATH", str(f))
    assert api.get_or_create_admin_secret() == "ความลับในไฟล์"


# ===== path ฐานข้อมูล: ตั้ง env ให้ชี้เข้า volume ได้ =====
# ถ้าข้อนี้พัง = ข้อมูลผู้เล่นหายทุกครั้งที่ deploy ใหม่

import importlib
import os


PATH_CASES = [
    ("bot.controller.db_manager", "DB_NAME", "GAME_DB_PATH", "game_data.db"),
    ("license_server.web_db", "DB_PATH", "WEB_DB_PATH", "web.db"),
    ("license_server.db", "DB_PATH", "LICENSE_DB_PATH", "licenses.db"),
    ("license_server.web_api", "UPLOAD_DIR", "UPLOAD_DIR", "web_uploads"),
]


@pytest.mark.parametrize("mod_name,attr,env_key,default_name", PATH_CASES)
def test_path_ตาม_env(monkeypatch, tmp_path, mod_name, attr, env_key, default_name):
    target = tmp_path / "volume" / default_name
    monkeypatch.setenv(env_key, str(target))
    mod = importlib.reload(importlib.import_module(mod_name))
    try:
        assert str(getattr(mod, attr)) == str(target)
    finally:
        monkeypatch.delenv(env_key, raising=False)
        importlib.reload(mod)


@pytest.mark.parametrize("mod_name,attr,env_key,default_name", PATH_CASES)
def test_path_ไม่ตั้ง_env_ใช้_ที่เดิม(monkeypatch, mod_name, attr, env_key, default_name):
    monkeypatch.delenv(env_key, raising=False)
    mod = importlib.reload(importlib.import_module(mod_name))
    got = str(getattr(mod, attr))
    assert got.endswith(default_name), f"{got} ควรลงท้าย {default_name}"
    assert os.path.isabs(got), "ต้องเป็น path เต็ม ไม่งั้นแต่ละโปรเซสเห็นคนละไฟล์"


def test_ทุก_db_แยกไฟล์กัน(monkeypatch, tmp_path):
    # เคยพลาดได้ง่าย: ก๊อป env key ผิดแล้ว db ทับกัน
    for _, _, env_key, name in PATH_CASES:
        monkeypatch.setenv(env_key, str(tmp_path / name))
    mods = [importlib.reload(importlib.import_module(m)) for m, *_ in PATH_CASES]
    paths = [str(getattr(mod, attr)) for mod, (_, attr, _, _) in zip(mods, PATH_CASES)]
    assert len(set(paths)) == len(paths), f"path ซ้ำกัน: {paths}"
    for _, _, env_key, _ in PATH_CASES:
        monkeypatch.delenv(env_key, raising=False)
    for m, *_ in PATH_CASES:
        importlib.reload(importlib.import_module(m))
