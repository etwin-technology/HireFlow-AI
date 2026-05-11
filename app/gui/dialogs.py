"""Small modal dialogs used across the GUI.

All dialogs are blocking-style: ``.show()`` returns the result (or None on
cancel) and disposes of the window.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Optional

import customtkinter as ctk

from app.gui.themes import COLORS


class NotesDialog(ctk.CTkToplevel):
    """Modal multiline text editor."""

    def __init__(
        self,
        parent,
        *,
        title: str = "Notes",
        initial: str = "",
        placeholder: str = "Write any notes about this job…",
    ) -> None:
        super().__init__(parent)
        self.title(title)
        self.transient(parent)
        self.resizable(True, True)
        self.geometry("520x340")
        self.configure(fg_color=COLORS.bg)
        self._result: Optional[str] = None

        ctk.CTkLabel(
            self, text=title, font=("Segoe UI", 14, "bold"),
            text_color=COLORS.text, anchor="w",
        ).pack(fill="x", padx=18, pady=(14, 4))

        self._textbox = ctk.CTkTextbox(
            self, fg_color=COLORS.surface, text_color=COLORS.text,
            border_color=COLORS.border, border_width=1, corner_radius=8,
            font=("Segoe UI", 11), wrap="word",
        )
        self._textbox.pack(fill="both", expand=True, padx=18, pady=8)
        if initial:
            self._textbox.insert("1.0", initial)
        else:
            # Visual hint using a faded label overlay would be overkill — leave blank.
            pass

        bar = ctk.CTkFrame(self, fg_color="transparent")
        bar.pack(fill="x", padx=18, pady=(4, 14))
        ctk.CTkButton(
            bar, text="Cancel", width=110,
            fg_color="transparent", border_color=COLORS.border, border_width=1,
            text_color=COLORS.text, command=self._cancel,
        ).pack(side="right", padx=4)
        ctk.CTkButton(
            bar, text="Save", width=110,
            fg_color=COLORS.primary, hover_color=COLORS.primary_hover,
            text_color=COLORS.on_primary, command=self._save,
        ).pack(side="right", padx=4)

        self.protocol("WM_DELETE_WINDOW", self._cancel)
        self.bind("<Escape>", lambda _e: self._cancel())
        self._textbox.focus_set()

    def _save(self) -> None:
        self._result = self._textbox.get("1.0", "end").strip()
        self.destroy()

    def _cancel(self) -> None:
        self._result = None
        self.destroy()

    def show(self) -> Optional[str]:
        self.grab_set()
        self.wait_window()
        return self._result


class FollowUpDialog(ctk.CTkToplevel):
    """Pick a follow-up date (a few quick presets + manual YYYY-MM-DD)."""

    PRESETS: list[tuple[str, int]] = [
        ("Tomorrow", 1),
        ("In 3 days", 3),
        ("In 1 week", 7),
        ("In 2 weeks", 14),
        ("In 1 month", 30),
    ]

    def __init__(
        self,
        parent,
        *,
        initial: Optional[datetime] = None,
    ) -> None:
        super().__init__(parent)
        self.title("Set follow-up date")
        self.transient(parent)
        self.resizable(False, False)
        self.geometry("380x360")
        self.configure(fg_color=COLORS.bg)
        self._result: Optional[datetime] = None
        self._cleared: bool = False

        ctk.CTkLabel(
            self, text="Set follow-up date", font=("Segoe UI", 14, "bold"),
            text_color=COLORS.text, anchor="w",
        ).pack(fill="x", padx=18, pady=(14, 8))

        # Presets
        preset_box = ctk.CTkFrame(self, fg_color="transparent")
        preset_box.pack(fill="x", padx=18, pady=4)
        for label, days in self.PRESETS:
            ctk.CTkButton(
                preset_box, text=label, height=32,
                fg_color=COLORS.surface_alt, hover_color=COLORS.surface,
                text_color=COLORS.text,
                command=lambda d=days: self._pick(d),
            ).pack(side="top", fill="x", pady=2)

        # Manual date entry
        ctk.CTkLabel(
            self, text="Or enter a date (YYYY-MM-DD):",
            font=("Segoe UI", 11), text_color=COLORS.text_muted, anchor="w",
        ).pack(fill="x", padx=18, pady=(10, 2))

        self._entry_var = ctk.StringVar(
            value=initial.strftime("%Y-%m-%d") if initial else ""
        )
        ctk.CTkEntry(
            self, textvariable=self._entry_var,
            placeholder_text="2026-06-15",
        ).pack(fill="x", padx=18, pady=2)

        bar = ctk.CTkFrame(self, fg_color="transparent")
        bar.pack(fill="x", padx=18, pady=(14, 14))
        ctk.CTkButton(
            bar, text="Clear", width=80,
            fg_color="transparent", border_color=COLORS.danger, border_width=1,
            text_color=COLORS.danger, command=self._clear,
        ).pack(side="left", padx=2)
        ctk.CTkButton(
            bar, text="Cancel", width=90,
            fg_color="transparent", border_color=COLORS.border, border_width=1,
            text_color=COLORS.text, command=self._cancel,
        ).pack(side="right", padx=2)
        ctk.CTkButton(
            bar, text="Save", width=110,
            fg_color=COLORS.primary, hover_color=COLORS.primary_hover,
            text_color=COLORS.on_primary, command=self._save,
        ).pack(side="right", padx=2)

        self.protocol("WM_DELETE_WINDOW", self._cancel)
        self.bind("<Escape>", lambda _e: self._cancel())

    def _pick(self, days_from_now: int) -> None:
        target = datetime.now() + timedelta(days=days_from_now)
        self._entry_var.set(target.strftime("%Y-%m-%d"))

    def _save(self) -> None:
        text = (self._entry_var.get() or "").strip()
        if not text:
            self._result = None
            self._cleared = True
            self.destroy()
            return
        try:
            self._result = datetime.strptime(text, "%Y-%m-%d")
        except ValueError:
            # Leave the dialog open so user can fix the date.
            return
        self.destroy()

    def _clear(self) -> None:
        self._result = None
        self._cleared = True
        self.destroy()

    def _cancel(self) -> None:
        self._result = None
        self._cleared = False  # caller distinguishes cancel vs clear
        self.destroy()

    def show(self) -> tuple[Optional[datetime], bool]:
        """Return ``(date_or_none, was_cleared)``.

        ``was_cleared`` distinguishes "user clicked Clear" (apply None) from
        "user cancelled" (don't apply anything).
        """
        self.grab_set()
        self.wait_window()
        return self._result, self._cleared
