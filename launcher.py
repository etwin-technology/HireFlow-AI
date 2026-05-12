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
