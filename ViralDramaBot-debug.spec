# -*- mode: python ; coding: utf-8 -*-
# 调试版 onedir，带控制台。

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
        'PyQt5', 'PyQt6', 'PySide2', 'PySide6', 'wx', 'gi', 'cefpython3',
        'numpy', 'scipy', 'pandas', 'matplotlib',
        'sklearn', 'skimage', 'cv2',
        'boto3', 'botocore', 's3transfer', 'aiobotocore',
        'sqlalchemy', 'alembic',
        'IPython', 'ipykernel', 'jupyter',
        'docutils', 'sphinx',
        'PIL',
        'test', 'tests', 'testing',
        'watchfiles',
        'unittest',
    ],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='ViralDramaBot-debug',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=os.path.join(_spec_dir, 'frontend', 'logo.ico'),
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name='ViralDramaBot-debug',
)
