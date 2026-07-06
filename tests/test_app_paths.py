import os
import sys

import app_paths


def test_dev_mode_returns_repo_root():
    root = app_paths.get_app_root()
    assert os.path.isfile(os.path.join(root, "config.example.json"))


def test_frozen_mode_returns_executable_dir_not_file_dir(monkeypatch, tmp_path):
    """Regression test: PyInstaller onefile extracts to a temp dir at runtime, so a plain
    __file__-based path would silently point into that ephemeral temp dir instead of the
    real install folder -- causing config.json/game_data.db to be lost on every restart.
    get_app_root() must use sys.executable's directory when frozen, not __file__.
    """
    fake_install_dir = tmp_path / "BotManager"
    fake_install_dir.mkdir()
    fake_exe = fake_install_dir / "BotManager.exe"
    fake_exe.write_text("", encoding="utf-8")

    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "executable", str(fake_exe))

    assert app_paths.get_app_root() == str(fake_install_dir)
