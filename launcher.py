"""Thin launcher script used as the PyInstaller entry-point.

Running ``python launcher.py`` from the project root launches the GUI.

This module ALSO sets up an early-stage crash log written to a guaranteed
writable location (``%LOCALAPPDATA%\\HireFlow-AI\\crash.log`` on Windows) so
that any startup failure in the packaged .exe leaves a forensic trail the
user can send us.
"""

from __future__ import annotations

import multiprocessing
import os
import subprocess
import sys
import traceback
from datetime import datetime
from pathlib import Path


# ---------------------------------------------------------------------------
# Writable user-data directory — picked BEFORE we touch the app code so even
# a crash in ``app.core.config`` ends up logged somewhere we can read.
# ---------------------------------------------------------------------------
def _user_data_dir() -> Path:
    """Return a per-user, always-writable directory for app data + logs."""
    if sys.platform == "win32":
        root = os.environ.get("LOCALAPPDATA") or os.environ.get("APPDATA")
        if root:
            return Path(root) / "HireFlow-AI"
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "HireFlow-AI"
    return Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local/share")) / "HireFlow-AI"


USER_DATA_DIR = _user_data_dir()
try:
    USER_DATA_DIR.mkdir(parents=True, exist_ok=True)
except OSError:
    # If even that fails we fall back to %TEMP%.
    import tempfile
    USER_DATA_DIR = Path(tempfile.gettempdir()) / "HireFlow-AI"
    USER_DATA_DIR.mkdir(parents=True, exist_ok=True)


def _is_frozen() -> bool:
    return bool(getattr(sys, "frozen", False))


def _configure_frozen_paths() -> None:
    """Tell the app to read/write user data from %LOCALAPPDATA% when packaged.

    Pydantic-settings reads from environment first, so setting these env vars
    BEFORE importing ``app.core.config`` causes them to win over the defaults
    that point at relative paths like ``data/``.
    """
    if not _is_frozen():
        return

    db_path = USER_DATA_DIR / "jobhunter.db"
    os.environ.setdefault("DATABASE_URL", f"sqlite:///{db_path}")
    os.environ.setdefault("LOG_DIR", str(USER_DATA_DIR / "logs"))
    os.environ.setdefault("EXPORT_DIR", str(USER_DATA_DIR / "exports"))
    os.environ.setdefault("APP_ENV", "production")

    # Ensure the subdirectories exist before SQLAlchemy / Loguru open files.
    for sub in ("logs", "exports"):
        (USER_DATA_DIR / sub).mkdir(parents=True, exist_ok=True)


# ---------------------------------------------------------------------------
# Playwright browser bootstrap.
#
# Playwright stores its Chromium binary in either
#   (a) the package's own ``.local-browsers`` folder (default for pip
#       installs), OR
#   (b) the directory pointed to by ``PLAYWRIGHT_BROWSERS_PATH``.
#
# When PyInstaller freezes the app the package folder is read-only and
# usually missing the browser binaries — they're a separate ~150 MB download
# triggered by ``playwright install``. Two problems follow:
#   * The browsers may not have been bundled at build time.
#   * Even if they were, when the .exe is run from a transient extraction
#     dir (WinRAR self-extract, %TEMP%, Windows Defender sandbox, …) the
#     paths shift and Playwright can't find them.
#
# Fix: pin ``PLAYWRIGHT_BROWSERS_PATH`` to a persistent per-user location,
# prefer the bundled copy on first run, and fall back to downloading on
# demand. Setting the env var BEFORE any ``playwright`` import is critical.
# ---------------------------------------------------------------------------
PLAYWRIGHT_BROWSERS_DIR = USER_DATA_DIR / "browsers"


def _bundled_browsers_dir() -> Path | None:
    """Return the bundled ms-playwright dir if it was shipped with the .exe."""
    if not _is_frozen():
        return None
    base = getattr(sys, "_MEIPASS", None)
    if not base:
        return None
    candidate = Path(base) / "ms-playwright"
    return candidate if candidate.is_dir() else None


def _chromium_present(browsers_dir: Path) -> bool:
    """Heuristic check: is *some* Chromium build present under ``browsers_dir``?

    We accept either ``chromium-*`` (full Chromium) or
    ``chromium_headless_shell-*`` (the lighter headless build Playwright
    1.45+ prefers for ``headless=True``).
    """
    if not browsers_dir.is_dir():
        return False
    for child in browsers_dir.iterdir():
        name = child.name.lower()
        if name.startswith("chromium-") or name.startswith("chromium_headless_shell-"):
            return True
    return False


def _configure_playwright_paths() -> None:
    """Point Playwright at a stable, writable browsers directory.

    Strategy:
      1. If the build bundled browsers into ``_MEIPASS/ms-playwright`` and the
         user-data copy is empty, copy them once into the user-data dir.
         Using the persistent location avoids re-extracting hundreds of MB on
         every launch when the exe is run from a self-extracting archive.
      2. Always export ``PLAYWRIGHT_BROWSERS_PATH`` to the user-data dir, so
         all Playwright invocations look in the same place.
    """
    if not _is_frozen():
        return

    PLAYWRIGHT_BROWSERS_DIR.mkdir(parents=True, exist_ok=True)
    os.environ["PLAYWRIGHT_BROWSERS_PATH"] = str(PLAYWRIGHT_BROWSERS_DIR)

    bundled = _bundled_browsers_dir()
    if bundled is not None and not _chromium_present(PLAYWRIGHT_BROWSERS_DIR):
        import shutil

        try:
            for item in bundled.iterdir():
                dest = PLAYWRIGHT_BROWSERS_DIR / item.name
                if dest.exists():
                    continue
                if item.is_dir():
                    shutil.copytree(item, dest)
                else:
                    shutil.copy2(item, dest)
        except OSError:
            # Non-fatal: we'll try the network download path below.
            pass


class _FirstRunDialog:
    """Minimal Tk modal shown while Playwright downloads its Chromium build.

    The .app on macOS does not have a PyInstaller splash (Splash is
    Windows/Linux only), so without this dialog the user would double-click
    HireFlow.app and stare at a frozen Dock icon for two minutes during the
    first-run download. The dialog is intentionally tiny and dependency-free
    (stdlib tkinter only) so it can show BEFORE any heavy app imports run.
    """

    def __init__(self) -> None:
        self._tk = None
        self._label = None
        self._bar = None

    def open(self) -> None:
        try:
            import tkinter as tk
            from tkinter import ttk
        except Exception:  # noqa: BLE001
            return

        try:
            root = tk.Tk()
            root.title("HireFlow AI — First-time setup")
            root.geometry("440x150")
            root.resizable(False, False)
            # Center on screen
            root.update_idletasks()
            sw, sh = root.winfo_screenwidth(), root.winfo_screenheight()
            x = (sw - 440) // 2
            y = (sh - 150) // 2
            root.geometry(f"440x150+{x}+{y}")

            header = tk.Label(
                root,
                text="Setting up HireFlow AI",
                font=("Helvetica", 14, "bold"),
                pady=8,
            )
            header.pack()

            self._label = tk.Label(
                root,
                text="Downloading browser engine (one-time, ≈150 MB)…",
                font=("Helvetica", 10),
                wraplength=400,
            )
            self._label.pack(pady=(4, 8))

            self._bar = ttk.Progressbar(root, mode="indeterminate", length=380)
            self._bar.pack(pady=(0, 10))
            self._bar.start(12)

            root.update()
            self._tk = root
        except Exception:  # noqa: BLE001
            self._tk = None

    def set_text(self, msg: str) -> None:
        if self._tk is None or self._label is None:
            return
        try:
            self._label.config(text=msg)
            self._tk.update()
        except Exception:  # noqa: BLE001
            pass

    def close(self) -> None:
        if self._tk is None:
            return
        try:
            if self._bar is not None:
                self._bar.stop()
            self._tk.destroy()
        except Exception:  # noqa: BLE001
            pass
        self._tk = None


def _ensure_playwright_browsers() -> None:
    """Make sure Chromium is installed before any scraper tries to launch it.

    Runs only when frozen AND the configured browsers dir is still empty
    after the bundle-copy step. Triggers Playwright's own installer via the
    driver's ``node`` binary, which is what ``python -m playwright install``
    does under the hood — except we can't rely on ``python -m`` in a frozen
    app because there is no separate interpreter on disk.
    """
    if not _is_frozen():
        return
    if _chromium_present(PLAYWRIGHT_BROWSERS_DIR):
        return

    # Splash works on Windows but not macOS; the Tk dialog covers both.
    _splash_update("Downloading browser engine (one-time, ~150 MB)…")
    dialog = _FirstRunDialog()
    dialog.open()

    try:
        try:
            from playwright._impl._driver import compute_driver_executable
        except Exception:  # noqa: BLE001
            return

        try:
            driver_executable, driver_cli = compute_driver_executable()
        except Exception:  # noqa: BLE001
            return

        env = os.environ.copy()
        env["PLAYWRIGHT_BROWSERS_PATH"] = str(PLAYWRIGHT_BROWSERS_DIR)

        try:
            subprocess.run(
                [driver_executable, driver_cli, "install", "chromium"],
                env=env,
                check=True,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
        except (OSError, subprocess.SubprocessError) as exc:
            # Don't crash the app — surface the error in the crash log and
            # let the scraper fail with a clearer message on first use.
            _write_crash(
                f"Playwright browser install failed: {exc!r}\n"
                f"PLAYWRIGHT_BROWSERS_PATH={PLAYWRIGHT_BROWSERS_DIR}\n"
            )
    finally:
        dialog.close()


def _write_crash(exc_text: str) -> Path:
    """Persist a crash report so we can debug failures from the field."""
    crash_path = USER_DATA_DIR / "crash.log"
    try:
        with crash_path.open("a", encoding="utf-8") as fh:
            fh.write(f"\n\n===== {datetime.now().isoformat()} =====\n")
            fh.write(f"Python: {sys.version}\n")
            fh.write(f"Executable: {sys.executable}\n")
            fh.write(f"Frozen: {_is_frozen()}\n")
            fh.write(f"USER_DATA_DIR: {USER_DATA_DIR}\n")
            fh.write(exc_text)
    except OSError:
        pass
    return crash_path


def _show_error_dialog(crash_path: Path, exc_text: str) -> None:
    """Show a Tk message box with the error (best-effort)."""
    try:
        import tkinter as tk
        from tkinter import messagebox

        root = tk.Tk()
        root.withdraw()
        # Keep the dialog short; full trace is in the crash log.
        short = "\n".join(exc_text.strip().splitlines()[-6:])
        messagebox.showerror(
            "HireFlow AI — startup error",
            f"Failed to start the application.\n\n"
            f"{short}\n\n"
            f"Full trace saved to:\n{crash_path}",
        )
        try:
            root.destroy()
        except Exception:  # noqa: BLE001
            pass
    except Exception:  # noqa: BLE001
        # Last resort — write to stderr (visible if console=True).
        sys.stderr.write(exc_text)


def _splash_update(message: str) -> None:
    """Show progress on the PyInstaller splash, if present."""
    try:
        import pyi_splash  # type: ignore

        if pyi_splash.is_alive():
            pyi_splash.update_text(message)
    except Exception:  # noqa: BLE001
        pass


def _splash_close() -> None:
    try:
        import pyi_splash  # type: ignore

        if pyi_splash.is_alive():
            pyi_splash.close()
    except Exception:  # noqa: BLE001
        pass


def main() -> None:
    multiprocessing.freeze_support()  # required for PyInstaller on Windows
    _splash_update("Preparing environment…")
    _configure_frozen_paths()
    _configure_playwright_paths()
    _ensure_playwright_browsers()

    try:
        _splash_update("Loading core libraries…")
        from app.main import main as app_main

        # We don't want to swap out app.main's main() entirely — just close
        # the splash right before the GUI mainloop. The cleanest hook is to
        # close it BEFORE handing over; the main window paints in <100ms once
        # the heavy imports are done.
        _splash_update("Starting HireFlow AI…")
        _splash_close()
        app_main()
    except SystemExit:
        _splash_close()
        raise
    except BaseException:  # noqa: BLE001
        _splash_close()
        exc_text = traceback.format_exc()
        crash_path = _write_crash(exc_text)
        _show_error_dialog(crash_path, exc_text)
        sys.exit(1)


if __name__ == "__main__":
    main()
