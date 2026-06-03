# -*- mode: python ; coding: utf-8 -*-
# onedir 分发：避免 onefile 每次启动把 ~100MB 解压到 %TEMP%，显著缩短双击后第一段等待。

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
        # GUI 框架（pywebview 用 WebView2，不需要这些）
        'PyQt5', 'PyQt6', 'PySide2', 'PySide6', 'wx', 'gi', 'cefpython3',
        # 科学计算（未使用，但被间接依赖带入）
        'numpy', 'scipy', 'pandas', 'matplotlib',
        'sklearn', 'skimage', 'cv2',
        # AWS SDK（APScheduler 可选依赖，未使用）
        'boto3', 'botocore', 's3transfer', 'aiobotocore',
        # 其他未用到的大包
        'sqlalchemy', 'alembic',
        'IPython', 'ipykernel', 'jupyter',
        'docutils', 'sphinx',
        'PIL',                  # 仅开发工具用，运行时不需要
        'test', 'tests', 'testing',
        'watchfiles',           # uvicorn 热重载，生产包不需要
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
    name='ViralDramaBot',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
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
    upx=True,
    upx_exclude=[
        # WebView2 的 COM DLL 不能压，压了会导致加载失败
        'WebView2Loader.dll',
        'webview2loader.dll',
    ],
    name='ViralDramaBot',
)
