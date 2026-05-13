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
import os

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
# Bundle the Playwright Chromium browser, if it has been pre-downloaded to
# ``build/ms-playwright/``. tools/build_exe.ps1 does this step before
# invoking PyInstaller. Without it the .exe still works — the launcher will
# download Chromium on first run — but bundling avoids a ~150 MB first-run
# download for end users.
#
# The bundle path is ``_internal/ms-playwright`` at runtime; the launcher
# (launcher.py::_configure_playwright_paths) copies these files into a
# writable per-user dir and sets PLAYWRIGHT_BROWSERS_PATH there.
# ---------------------------------------------------------------------------
_browsers_src = os.path.join(os.path.abspath(SPECPATH), "build", "ms-playwright")
if os.path.isdir(_browsers_src):
    datas += [(_browsers_src, "ms-playwright")]


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
# Native splash screen — shown by the PyInstaller bootloader IMMEDIATELY,
# before any Python interpreter starts. The launcher closes it once the
# main window is ready (see launcher.py).
# ---------------------------------------------------------------------------
splash = Splash(
    "app/gui/assets/logo_256.png",
    binaries=a.binaries,
    datas=a.datas,
    text_pos=(10, 280),
    text_size=11,
    text_color="white",
    minify_script=True,
    always_on_top=True,
)


# ---------------------------------------------------------------------------
# Executable — one-FOLDER distribution (recommended).
# Faster startup than one-file, easier to inspect / repair.
# ---------------------------------------------------------------------------
exe = EXE(
    pyz,
    a.scripts,
    splash,                  # include splash in the bootloader
    [],
    exclude_binaries=True,
    name="HireFlow",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,           # production: no terminal window
    disable_windowed_traceback=False,
    icon="app/gui/assets/icon.ico",
    version="tools/version_info.txt",
)

coll = COLLECT(
    exe,
    splash.binaries,         # include splash binaries
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
