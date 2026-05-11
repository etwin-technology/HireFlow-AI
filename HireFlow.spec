# HireFlow AI — PyInstaller spec file
#
# Build:
#   .venv\Scripts\activate
#   pyinstaller HireFlow.spec --clean --noconfirm
#
# Output:
#   dist\HireFlow\HireFlow.exe   (one-folder distribution)
#
# To make a single-file build instead, see the bottom of this file.

# ruff: noqa
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

block_cipher = None


# ---------------------------------------------------------------------------
# Data files bundled with the executable
# ---------------------------------------------------------------------------
datas = []
datas += collect_data_files("customtkinter")
datas += collect_data_files("ttkbootstrap")
datas += collect_data_files("fake_useragent")
datas += [("app/gui/assets", "app/gui/assets")]


# ---------------------------------------------------------------------------
# Hidden imports — modules PyInstaller's static analysis can miss.
# ---------------------------------------------------------------------------
hiddenimports = [
    "customtkinter",
    "ttkbootstrap",
    "loguru",
    "tenacity",
    "fake_useragent",
    "pydantic",
    "pydantic_settings",
    "pydantic_core",
    "apscheduler.schedulers.background",
    "apscheduler.triggers.interval",
    "apscheduler.triggers.cron",
    "sqlalchemy.dialects.sqlite",
    "uvicorn.logging",
    "uvicorn.loops",
    "uvicorn.loops.auto",
    "uvicorn.protocols",
    "uvicorn.protocols.http",
    "uvicorn.protocols.http.auto",
    "uvicorn.protocols.websockets",
    "uvicorn.protocols.websockets.auto",
    "uvicorn.lifespan",
    "uvicorn.lifespan.on",
    "plyer.platforms.win.notification",
    "plyer.facades.notification",
    "PIL._tkinter_finder",
]
hiddenimports += collect_submodules("pydantic")
hiddenimports += collect_submodules("apscheduler")


# ---------------------------------------------------------------------------
# Modules we deliberately exclude to shrink the bundle.
# ---------------------------------------------------------------------------
excludes = [
    "matplotlib.tests",
    "pandas.tests",
    "numpy.tests",
    "PyInstaller",
    "test",
    "unittest",
    "pytest",
]


a = Analysis(
    ["launcher.py"],
    pathex=["."],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=excludes,
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)


# ---------------------------------------------------------------------------
# Executable — one-FOLDER distribution (recommended).
# Faster startup than one-file, easier to inspect / repair.
# ---------------------------------------------------------------------------
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="HireFlow",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,            # set True if UPX is on PATH and you want compression
    console=False,        # windowed app (no console)
    disable_windowed_traceback=False,
    icon="app/gui/assets/icon.ico",
    version=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="HireFlow",
)


# ---------------------------------------------------------------------------
# One-FILE alternative — uncomment if you want a single .exe instead.
# (~150-200 MB; slower first launch because it extracts to %TEMP%.)
# ---------------------------------------------------------------------------
# exe = EXE(
#     pyz,
#     a.scripts,
#     a.binaries,
#     a.zipfiles,
#     a.datas,
#     [],
#     name="HireFlow",
#     debug=False,
#     bootloader_ignore_signals=False,
#     strip=False,
#     upx=False,
#     runtime_tmpdir=None,
#     console=False,
#     icon="app/gui/assets/icon.ico",
# )
