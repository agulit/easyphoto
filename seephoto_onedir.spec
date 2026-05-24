# PyInstaller — onedir 应用本体（供启动器解压缓存，不直接分发）
# Build: pyinstaller seephoto_onedir.spec

from pathlib import Path

from PyInstaller.utils.hooks import collect_all, collect_submodules

block_cipher = None
root = Path(SPECPATH)

datas = []
binaries = []
hiddenimports = collect_submodules("rawpy") + [
    "numpy", "PIL", "PIL.Image", "seephoto", "seephoto.formats", "seephoto.gallery",
    "seephoto.loader", "seephoto.mainwindow", "seephoto.theme", "seephoto.viewer",
    "seephoto.viewer_pane", "seephoto.filmstrip", "seephoto.display_loader",
    "seephoto.cache", "seephoto.drop_handler", "seephoto.toolbar", "seephoto.image_info",
    "seephoto.crop_dialog", "seephoto.actions", "seephoto.win_utils",
    "seephoto.about_dialog", "seephoto.shell_register", "seephoto.adjustments",
    "seephoto.adjust_dialog",
]

for pkg in ("rawpy",):
    try:
        tmp = collect_all(pkg)
        datas += tmp[0]
        binaries += tmp[1]
        hiddenimports += tmp[2]
    except Exception:
        pass

assets_src = str(root / "assets")
datas += [(assets_src, "assets")]

a = Analysis(
    [str(root / "run_seephoto.py")],
    pathex=[str(root)],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        "matplotlib", "scipy", "pandas", "tkinter",
        "PySide6.Qt3DAnimation", "PySide6.Qt3DCore", "PySide6.Qt3DExtras",
        "PySide6.Qt3DInput", "PySide6.Qt3DLogic", "PySide6.Qt3DRender",
        "PySide6.QtCharts", "PySide6.QtDataVisualization",
        "PySide6.QtGraphs", "PySide6.QtGraphsWidgets",
        "PySide6.QtLocation", "PySide6.QtMultimedia", "PySide6.QtMultimediaWidgets",
        "PySide6.QtNetworkAuth", "PySide6.QtNfc", "PySide6.QtPositioning",
        "PySide6.QtQuick", "PySide6.QtQuick3D", "PySide6.QtQuickControls2",
        "PySide6.QtQuickWidgets", "PySide6.QtRemoteObjects", "PySide6.QtSensors",
        "PySide6.QtSerialPort", "PySide6.QtStateMachine", "PySide6.QtTextToSpeech",
        "PySide6.QtWebChannel", "PySide6.QtWebEngine", "PySide6.QtWebEngineCore",
        "PySide6.QtWebEngineWidgets", "PySide6.QtWebSockets",
        "PySide6.QtBluetooth", "PySide6.QtPdf", "PySide6.QtPdfWidgets",
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="易图",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=str(root / "assets" / "icon.ico"),
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="yitu_app",
)
