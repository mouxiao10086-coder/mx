# -*- mode: python ; coding: utf-8 -*-
# Windows 版本 PyInstaller spec 文件
# 构建命令: pyinstaller --clean --noconfirm 甲方后台定时查询工具_win.spec

a = Analysis(
    ['app.py'],
    pathex=[],
    binaries=[],
    datas=[('web', 'web'), ('fetch_reports.py', '.'), ('api.py', '.'), ('server.py', '.')],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
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
    name='甲方后台定时查询工具',
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
    icon=None,
)
