# -*- mode: python ; coding: utf-8 -*-
#
# PyInstaller spec for MMORPG Bot Manager
# Builds a one-file executable that bundles the bot and web panel

from PyInstaller.utils.hooks import collect_submodules

a = Analysis(
    ['launcher.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('panel/static', 'panel/static'),
        ('config.example.json', '.'),
    ],
    hiddenimports=[
        # discord.py dynamic imports
        *collect_submodules('discord'),
        # fastapi and uvicorn
        *collect_submodules('fastapi'),
        *collect_submodules('uvicorn'),
        # Uvicorn loop and protocol selection (auto-select modules)
        'uvicorn.logging',
        'uvicorn.loops.auto',
        'uvicorn.protocols.http.auto',
        'uvicorn.protocols.websockets.auto',
        'uvicorn.lifespan.on',
        # App submodules (bot cogs and panel routes)
        *collect_submodules('bot'),
        *collect_submodules('panel'),
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludedimports=[],
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=None)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='BotManager',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    onefile=True,
)
