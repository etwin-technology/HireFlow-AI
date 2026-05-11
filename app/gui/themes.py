"""Centralized theme + color palette.

Every color is a ``(light, dark)`` tuple — CustomTkinter auto-selects the
right side based on ``ctk.set_appearance_mode``. Use ``resolve()`` when you
need a single hex value (for raw ``tkinter`` / ``ttk`` widgets).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Tuple

import customtkinter as ctk


Color = Tuple[str, str]  # (light_hex, dark_hex)


@dataclass(frozen=True)
class Palette:
    # surfaces
    bg: Color = ("#F3F5F8", "#0F1115")
    surface: Color = ("#FFFFFF", "#171A21")
    surface_alt: Color = ("#EFF1F5", "#1F232C")
    # row_alt = subtle stripe color used by the Treeview for odd rows
    row_alt: Color = ("#F7F8FB", "#1A1E26")
    border: Color = ("#D8DCE3", "#2A2F3A")

    # text
    text: Color = ("#1A1D24", "#E6E7EB")
    text_muted: Color = ("#5C616C", "#8A8F9C")

    # brand
    primary: Color = ("#1F6FEB", "#1F6FEB")
    primary_hover: Color = ("#1858C4", "#1858C4")

    # semantic (tuned for high contrast in BOTH modes)
    success: Color = ("#0E7C39", "#3FB950")
    warning: Color = ("#B57000", "#E5A437")
    danger: Color = ("#C72929", "#F85149")
    info: Color = ("#0F6EAA", "#5BC0F8")

    # Status tag colors specifically tuned for table rows
    # (foreground on row_alt / surface — must be readable on both)
    tag_bookmarked: Color = ("#0B6E9E", "#5BC0F8")
    tag_applied: Color = ("#1857BE", "#6FA8FF")
    tag_interview: Color = ("#9C5B00", "#E5A437")
    tag_offer: Color = ("#0E7C39", "#4ED167")
    tag_rejected: Color = ("#A82424", "#F36E66")

    # selection (used by ttk Treeview)
    selection: Color = ("#1F6FEB", "#1F6FEB")
    on_primary: Color = ("#FFFFFF", "#FFFFFF")

    # Header (Treeview heading) — stronger contrast than surface_alt
    table_header_bg: Color = ("#E2E7EF", "#252A35")
    table_header_fg: Color = ("#0A0D14", "#FFFFFF")


COLORS: Palette = Palette()


# ---------------------------------------------------------------------------
# Theme application
# ---------------------------------------------------------------------------
def apply_theme(theme: str = "dark", color_theme: str = "blue", scaling: float = 1.0) -> None:
    """Configure CustomTkinter appearance, color theme, and widget scaling.

    Pass ``"system"`` to follow the OS preference.
    """
    mode = theme.lower()
    appearance = {"dark": "Dark", "light": "Light"}.get(mode, "System")
    ctk.set_appearance_mode(appearance)

    valid_color_themes = {"blue", "green", "dark-blue"}
    if color_theme not in valid_color_themes:
        color_theme = "blue"
    ctk.set_default_color_theme(color_theme)

    if 0.5 <= scaling <= 2.0:
        ctk.set_widget_scaling(scaling)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def is_dark() -> bool:
    """Return True if the current appearance mode resolves to dark."""
    mode = ctk.get_appearance_mode().lower()
    return mode.startswith("dark")


def resolve(color: Color | str) -> str:
    """Return a single hex value for the current appearance mode."""
    if isinstance(color, str):
        return color
    light, dark = color
    return dark if is_dark() else light


# ---------------------------------------------------------------------------
# ttk style refresh — re-apply Treeview styles when the theme switches.
# ---------------------------------------------------------------------------
def refresh_ttk_styles() -> None:
    """Re-apply ttk.Treeview styles so it matches the current appearance mode."""
    from tkinter import ttk

    style = ttk.Style()
    try:
        style.theme_use("default")
    except Exception:  # noqa: BLE001
        pass

    style.configure(
        "JobHunter.Treeview",
        background=resolve(COLORS.surface),
        fieldbackground=resolve(COLORS.surface),
        foreground=resolve(COLORS.text),
        rowheight=30,
        borderwidth=0,
        font=("Segoe UI", 10),
    )
    style.configure(
        "JobHunter.Treeview.Heading",
        background=resolve(COLORS.table_header_bg),
        foreground=resolve(COLORS.table_header_fg),
        font=("Segoe UI", 10, "bold"),
        borderwidth=0,
        relief="flat",
        padding=(8, 6),
    )
    style.map(
        "JobHunter.Treeview.Heading",
        background=[("active", resolve(COLORS.surface_alt))],
    )
    style.map(
        "JobHunter.Treeview",
        background=[("selected", resolve(COLORS.selection))],
        foreground=[("selected", resolve(COLORS.on_primary))],
    )

    # Vertical scrollbar — match the theme.
    style.configure(
        "Vertical.TScrollbar",
        background=resolve(COLORS.surface_alt),
        troughcolor=resolve(COLORS.surface),
        bordercolor=resolve(COLORS.border),
        arrowcolor=resolve(COLORS.text_muted),
        relief="flat",
    )


# ---------------------------------------------------------------------------
# Common font helpers
# ---------------------------------------------------------------------------
def heading_font() -> tuple[str, int, str]:
    return ("Segoe UI", 22, "bold")


def subheading_font() -> tuple[str, int, str]:
    return ("Segoe UI", 16, "bold")


def body_font() -> tuple[str, int]:
    return ("Segoe UI", 12)


def small_font() -> tuple[str, int]:
    return ("Segoe UI", 10)


# Backwards-compat: ``THEMES`` dict still imported by app/gui/__init__.py.
THEMES: dict[str, Palette] = {"dark": COLORS, "light": COLORS}
