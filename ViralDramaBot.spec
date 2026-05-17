# -*- mode: python ; coding: utf-8 -*-

import os
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

_spec_dir = os.path.dirname(os.path.abspath(SPEC))
webview_hiddenimports = collect_submodules(
    'webview',
    filter=lambda name: not name.startswith('webview.platforms.android'),
)
webview_datas = collect_data_files('webview')

a = Analysis(
    ['run_packaged.py'],
    pathex=[],
    binaries=[],
    datas=[('frontend', 'frontend'), ('src', 'src')] + webview_datas,
    hiddenimports=webview_hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'PyQt5',
        'PyQt6',
        'PySide2',
        'PySide6',
        'cefpython3',
    ],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='ViralDramaBot',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=os.path.join(_spec_dir, 'frontend', 'logo.ico'),
)
