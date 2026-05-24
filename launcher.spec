# PyInstaller — 单文件启动器（内嵌 onedir 压缩包，首次解压到 AppData）
# 由 build.ps1 调用；需先存在 build/yitu_bundle.zip 与 build/VERSION

from pathlib import Path

root = Path(SPECPATH)
build = root / "build"

a = Analysis(
    [str(root / "launch_yitu.py")],
    pathex=[str(root)],
    binaries=[],
    datas=[
        (str(build / "yitu_bundle.zip"), "."),
        (str(build / "VERSION"), "."),
    ],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=None,
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
    exclude_binaries=False,
    name="易图",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=str(root / "assets" / "icon.ico"),
)
