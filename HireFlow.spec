# HireFlow AI — PyInstaller spec file (cross-platform)
#
# Build:
#   Windows:   .venv\Scripts\activate ; pyinstaller HireFlow.spec --clean --noconfirm
#   macOS:     source .venv/bin/activate ; pyinstaller HireFlow.spec --clean --noconfirm
#
# Output:
#   Windows:   dist\HireFlow\HireFlow.exe   (one-folder distribution)
#   macOS:     dist/HireFlow.app            (native .app bundle alongside dist/HireFlow/)

# ruff: noqa
import os
import sys

from PyInstaller.utils.hooks import collect_data_files, collect_submodules

block_cipher = None

# Platform feature flags — used to gate Windows-only / macOS-only spec pieces.
IS_WINDOWS = sys.platform.startswith("win")
IS_MACOS = sys.platform == "darwin"


# ---------------------------------------------------------------------------
# Data files bundled with the executable
# ---------------------------------------------------------------------------
datas = []
datas += collect_data_files("customtkinter")
datas += collect_data_files("ttkbootstrap")
datas += collect_data_files("fake_useragent")
datas += [("app/gui/assets", "app/gui/assets")]
# Bundle the PWA frontend so the API server inside the .exe can serve
# it when the user enables API_ENABLED=true. Resolved at runtime via
# sys._MEIPASS + "app/web" in app.api.main._web_root_path().
datas += [("app/web", "app/web")]


# ---------------------------------------------------------------------------
# Bundle the Playwright Chromium browser into the dist (Windows + Linux).
#
# On macOS we DELIBERATELY skip this: Playwright's macOS Chromium download
# is a nested ``Chromium.app/`` — a code-signed .app bundle whose
# ``*.framework/`` directories contain symlinks pointing back into
# ``Versions/A/``. PyInstaller's COLLECT step cannot copy this layout
# (follows the symlinks, breaks the code signature, exits non-zero), and
# even if it succeeded, stuffing a signed .app inside another .app would
# trip Gatekeeper at runtime. On macOS the launcher's first-run downloader
# (launcher.py::_ensure_playwright_browsers) handles it instead — the same
# code path that runs as a fallback on Windows when bundling was skipped.
# ---------------------------------------------------------------------------
if not IS_MACOS:
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
    # GUI / asyncio plumbing PyInstaller's static analysis sometimes
    # misses on Windows — without these the .exe boots but the main
    # window never appears (silent NotImplementedError from asyncio,
    # or a Tk_Init failure from a missing _tkinter helper).
    "_tkinter",
    "tkinter",
    "tkinter.ttk",
    "tkinter.font",
    "tkinter.filedialog",
    "tkinter.messagebox",
    "tkinter.scrolledtext",
    "asyncio",
    "asyncio.windows_events",
    "asyncio.windows_utils",
    "asyncio.proactor_events",
    "asyncio.selector_events",
    "selectors",
    "encodings.idna",
    "encodings.utf_8",
    "encodings.cp1252",
    "PIL.ImageTk",
]
hiddenimports += collect_submodules("pydantic")
hiddenimports += collect_submodules("apscheduler")
hiddenimports += collect_submodules("customtkinter")


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
#
# Splash is Windows + Linux only — PyInstaller does NOT support it on macOS.
# We skip it on Darwin and rely on the .app launching quickly enough that no
# splash is needed.
# ---------------------------------------------------------------------------
splash = None
if not IS_MACOS:
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
# Per-platform icon + Windows-only version resource.
# ---------------------------------------------------------------------------
if IS_MACOS:
    icon_path = "app/gui/assets/icon.icns"
elif IS_WINDOWS:
    icon_path = "app/gui/assets/icon.ico"
else:
    icon_path = "app/gui/assets/logo_256.png"

version_resource = "tools/version_info.txt" if IS_WINDOWS else None


# ---------------------------------------------------------------------------
# Executable — one-FOLDER distribution (recommended).
# Faster startup than one-file, easier to inspect / repair.
# ---------------------------------------------------------------------------
_exe_args = [pyz, a.scripts]
if splash is not None:
    _exe_args.append(splash)          # include splash in the bootloader
_exe_args.append([])

exe = EXE(
    *_exe_args,
    exclude_binaries=True,
    name="HireFlow",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,           # production: no terminal window
    disable_windowed_traceback=False,
    icon=icon_path,
    version=version_resource,
)

_coll_args = [exe]
if splash is not None:
    _coll_args.append(splash.binaries)  # include splash binaries
_coll_args += [a.binaries, a.zipfiles, a.datas]

coll = COLLECT(
    *_coll_args,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="HireFlow",
)


# ---------------------------------------------------------------------------
# macOS .app bundle — wraps ``coll`` in the standard .app directory layout
# (Contents/MacOS, Contents/Resources, Info.plist, etc). Without this step
# you'd end up with a bare CLI binary that Finder can't double-click.
# ---------------------------------------------------------------------------
if IS_MACOS:
    app = BUNDLE(
        coll,
        name="HireFlow.app",
        icon=icon_path,
        bundle_identifier="com.etwintechnology.hireflow",
        version="1.2.0",
        info_plist={
            "CFBundleName": "HireFlow AI",
            "CFBundleDisplayName": "HireFlow AI",
            "CFBundleShortVersionString": "1.2.0",
            "CFBundleVersion": "1.2.0",
            "CFBundleIdentifier": "com.etwintechnology.hireflow",
            "NSHighResolutionCapable": True,
            "LSMinimumSystemVersion": "11.0",
            "LSApplicationCategoryType": "public.app-category.business",
            "NSHumanReadableCopyright": "Copyright (c) Etwin Technology",
            # We need network for scraping, and the user-data dir for the
            # SQLite database + Playwright browser cache.
            "NSAppTransportSecurity": {"NSAllowsArbitraryLoads": True},
        },
    )
