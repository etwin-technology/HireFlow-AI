"""Animated splash screen displayed during cold-start."""

from __future__ import annotations

import tkinter as tk
from typing import Callable, Optional

import customtkinter as ctk

from app.core.config import settings
from app.gui.themes import COLORS, heading_font, small_font


class SplashScreen(ctk.CTkToplevel):
    """A borderless, centered splash window with a moving progress bar."""

    def __init__(
        self,
        parent: Optional[tk.Tk] = None,
        *,
        on_complete: Optional[Callable[[], None]] = None,
        duration_ms: int = 1500,
    ) -> None:
        super().__init__(parent)
        self._on_complete = on_complete
        self._duration_ms = duration_ms

        self.overrideredirect(True)
        self.configure(fg_color=COLORS.bg)
        self.attributes("-topmost", True)

        width, height = 520, 320
        x = self.winfo_screenwidth() // 2 - width // 2
        y = self.winfo_screenheight() // 2 - height // 2
        self.geometry(f"{width}x{height}+{x}+{y}")

        self._build_ui()
        self._animate_progress()
        self.after(duration_ms, self._close)

    # ---------------- UI ----------------
    def _build_ui(self) -> None:
        container = ctk.CTkFrame(
            self,
            corner_radius=18,
            fg_color=COLORS.surface,
            border_color=COLORS.border,
            border_width=1,
        )
        container.pack(fill="both", expand=True, padx=20, pady=20)

        ctk.CTkLabel(
            container,
            text="HireFlow AI",
            font=heading_font(),
            text_color=COLORS.text,
        ).pack(pady=(60, 6))

        ctk.CTkLabel(
            container,
            text=f"by {settings.app_vendor} · v{settings.app_version}",
            font=small_font(),
            text_color=COLORS.text_muted,
        ).pack()

        ctk.CTkLabel(
            container,
            text="AI-powered job aggregation platform",
            font=("Segoe UI", 12),
            text_color=COLORS.text_muted,
        ).pack(pady=(20, 0))

        self._progress = ctk.CTkProgressBar(
            container,
            mode="indeterminate",
            height=8,
            corner_radius=4,
            progress_color=COLORS.primary,
        )
        self._progress.pack(pady=(40, 6), padx=60, fill="x")

        self._status = ctk.CTkLabel(
            container,
            text="Loading components…",
            font=small_font(),
            text_color=COLORS.text_muted,
        )
        self._status.pack(pady=(8, 20))

    # ---------------- Animation ----------------
    def _animate_progress(self) -> None:
        try:
            self._progress.start()
        except Exception:  # noqa: BLE001
            pass

    def update_status(self, message: str) -> None:
        try:
            self._status.configure(text=message)
            self.update_idletasks()
        except Exception:  # noqa: BLE001
            pass

    def _close(self) -> None:
        try:
            self._progress.stop()
        except Exception:  # noqa: BLE001
            pass
        if self._on_complete is not None:
            try:
                self._on_complete()
            except Exception:  # noqa: BLE001
                pass
        try:
            self.destroy()
        except Exception:  # noqa: BLE001
            pass
