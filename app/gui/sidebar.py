"""Sidebar navigation widget — anchored footer that's always visible."""

from __future__ import annotations

from typing import Callable, Optional

import customtkinter as ctk

from app.core.config import settings
from app.core.constants import GUI_PAGES
from app.gui.themes import COLORS


PAGE_ICONS: dict[str, str] = {
    "Dashboard": "⌂",
    "Jobs": "≡",
    "Follow-ups": "★",
    "Exports": "↓",
    "Logs": "✎",
    "Analytics": "◐",
    "Settings": "⚙",
    "About": "ⓘ",
}


class Sidebar(ctk.CTkFrame):
    """Vertical navigation bar.

    Layout uses a 3-row grid:
        row 0 = brand (fixed)
        row 1 = nav buttons (expands)
        row 2 = footer (fixed, anchored to the bottom)

    This guarantees the footer (theme toggle + copyright) is always visible
    no matter the window height.
    """

    WIDTH: int = 220

    def __init__(
        self,
        parent,
        on_navigate: Callable[[str], None],
        on_toggle_theme: Optional[Callable[[bool], None]] = None,
    ) -> None:
        super().__init__(
            parent,
            width=self.WIDTH,
            corner_radius=0,
            fg_color=COLORS.surface,
            border_width=0,
        )
        self.grid_propagate(False)
        # Fixed width — let height be governed by parent.
        self.configure(width=self.WIDTH)

        self._on_navigate = on_navigate
        self._on_toggle_theme = on_toggle_theme
        self._buttons: dict[str, ctk.CTkButton] = {}
        self._active: str = GUI_PAGES[0]

        # 5 rows: brand | separator | nav (expands) | separator | footer
        self.grid_rowconfigure(0, weight=0)
        self.grid_rowconfigure(1, weight=0)
        self.grid_rowconfigure(2, weight=1)  # nav fills remaining
        self.grid_rowconfigure(3, weight=0)
        self.grid_rowconfigure(4, weight=0)
        self.grid_columnconfigure(0, weight=1)

        self._build_brand()
        self._build_nav()
        self._build_footer()
        self.set_active(self._active)

    # ---------------- Brand ----------------
    def _build_brand(self) -> None:
        brand_frame = ctk.CTkFrame(self, fg_color="transparent")
        brand_frame.grid(row=0, column=0, sticky="ew", padx=18, pady=(20, 12))

        ctk.CTkLabel(
            brand_frame,
            text="HireFlow",
            font=("Segoe UI", 20, "bold"),
            text_color=COLORS.text,
            anchor="w",
        ).pack(fill="x")

        ctk.CTkLabel(
            brand_frame,
            text="AI",
            font=("Segoe UI", 11, "bold"),
            text_color=COLORS.primary,
            anchor="w",
        ).pack(fill="x")

        ctk.CTkLabel(
            brand_frame,
            text=f"by {settings.app_vendor} · v{settings.app_version}",
            font=("Segoe UI", 9),
            text_color=COLORS.text_muted,
            anchor="w",
        ).pack(fill="x", pady=(4, 0))

        # Separator below brand (own row 1).
        ctk.CTkFrame(self, height=1, fg_color=COLORS.border).grid(
            row=1, column=0, sticky="ew", padx=12
        )

    # ---------------- Navigation ----------------
    def _build_nav(self) -> None:
        nav_container = ctk.CTkScrollableFrame(
            self,
            fg_color="transparent",
            scrollbar_button_color=COLORS.border,
            scrollbar_button_hover_color=COLORS.primary,
        )
        nav_container.grid(row=2, column=0, sticky="nsew", padx=8, pady=(6, 6))

        for page in GUI_PAGES:
            label = f"  {PAGE_ICONS.get(page, '•')}    {page}"
            btn = ctk.CTkButton(
                nav_container,
                text=label,
                anchor="w",
                height=42,
                corner_radius=8,
                fg_color="transparent",
                hover_color=COLORS.surface_alt,
                text_color=COLORS.text,
                font=("Segoe UI", 13),
                command=lambda p=page: self._handle_click(p),
            )
            btn.pack(fill="x", pady=2, padx=2)
            self._buttons[page] = btn

    # ---------------- Footer (always visible) ----------------
    def _build_footer(self) -> None:
        # Top border line on its own row so it doesn't overlap the footer.
        ctk.CTkFrame(self, height=1, fg_color=COLORS.border).grid(
            row=3, column=0, sticky="ew", padx=12
        )

        footer = ctk.CTkFrame(self, fg_color="transparent")
        footer.grid(row=4, column=0, sticky="ew", padx=14, pady=(10, 14))

        # Light / Dark switch
        toggle_row = ctk.CTkFrame(footer, fg_color="transparent")
        toggle_row.pack(fill="x", pady=(0, 6))

        ctk.CTkLabel(
            toggle_row,
            text="☼  Light / Dark",
            font=("Segoe UI", 11),
            text_color=COLORS.text_muted,
            anchor="w",
        ).pack(side="left")

        is_dark_now = ctk.get_appearance_mode().lower().startswith("dark")
        self._theme_var = ctk.BooleanVar(value=is_dark_now)
        self._theme_switch = ctk.CTkSwitch(
            toggle_row,
            text="",
            width=42,
            variable=self._theme_var,
            command=self._handle_theme_toggle,
        )
        self._theme_switch.pack(side="right")

        ctk.CTkLabel(
            footer,
            text=f"© {settings.app_vendor}",
            font=("Segoe UI", 10),
            text_color=COLORS.text_muted,
            anchor="w",
        ).pack(fill="x")

    # ---------------- Behavior ----------------
    def _handle_click(self, page: str) -> None:
        if page == self._active:
            return
        self.set_active(page)
        self._on_navigate(page)

    def set_active(self, page: str) -> None:
        for name, button in self._buttons.items():
            if name == page:
                button.configure(
                    fg_color=COLORS.primary,
                    text_color=COLORS.on_primary,
                    hover_color=COLORS.primary_hover,
                )
            else:
                button.configure(
                    fg_color="transparent",
                    text_color=COLORS.text,
                    hover_color=COLORS.surface_alt,
                )
        self._active = page

    def _handle_theme_toggle(self) -> None:
        if self._on_toggle_theme is None:
            return
        self._on_toggle_theme(bool(self._theme_var.get()))
