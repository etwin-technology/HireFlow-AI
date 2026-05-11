"""Thin launcher script used as the PyInstaller entry-point.

Running ``python launcher.py`` from the project root launches the GUI.
"""

from __future__ import annotations

import multiprocessing
import sys
import traceback


def main() -> None:
    try:
        multiprocessing.freeze_support()  # required for PyInstaller on Windows
        from app.main import main as app_main

        app_main()
    except Exception:  # noqa: BLE001
        # Surface a friendly message on cold-launch crash.
        try:
            import tkinter as tk
            from tkinter import messagebox

            root = tk.Tk()
            root.withdraw()
            messagebox.showerror(
                "HireFlow AI — startup error",
                "Failed to start the application:\n\n" + traceback.format_exc(),
            )
        except Exception:  # noqa: BLE001
            traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
