"""Stat-card widgets used on the dashboard."""

from __future__ import annotations

from typing import Optional, Union

import customtkinter as ctk

from app.gui.themes import COLORS

Color = Union[str, tuple[str, str]]


class StatCard(ctk.CTkFrame):
    """A single dashboard metric card.

    The card uses a thin colored accent bar on the left to highlight category.
    All colors accept either a hex string or a ``(light, dark)`` tuple.
    """

    def __init__(
        self,
        parent,
        *,
        title: str,
        value: str = "0",
        accent: Optional[Color] = None,
        icon: str = "•",
        subtitle: str = "",
    ) -> None:
        super().__init__(
            parent,
            corner_radius=14,
            fg_color=COLORS.surface,
            border_color=COLORS.border,
            border_width=1,
            height=120,
        )
        self.pack_propagate(False)
        self._accent: Color = accent or COLORS.primary

        # Left accent bar
        self._bar = ctk.CTkFrame(self, width=4, fg_color=self._accent, corner_radius=0)
        self._bar.pack(side="left", fill="y")

        content = ctk.CTkFrame(self, fg_color="transparent")
        content.pack(side="left", fill="both", expand=True, padx=16, pady=12)

        header = ctk.CTkFrame(content, fg_color="transparent")
        header.pack(fill="x")

        self._icon_label = ctk.CTkLabel(
            header,
            text=icon,
            text_color=self._accent,
            font=("Segoe UI", 18, "bold"),
        )
        self._icon_label.pack(side="left")

        self._title_label = ctk.CTkLabel(
            header,
            text=title,
            text_color=COLORS.text_muted,
            font=("Segoe UI", 11, "bold"),
            anchor="w",
        )
        self._title_label.pack(side="left", padx=(8, 0))

        self._value_label = ctk.CTkLabel(
            content,
            text=value,
            text_color=COLORS.text,
            font=("Segoe UI", 26, "bold"),
            anchor="w",
        )
        self._value_label.pack(fill="x", pady=(6, 0))

        self._subtitle_label = ctk.CTkLabel(
            content,
            text=subtitle,
            text_color=COLORS.text_muted,
            font=("Segoe UI", 10),
            anchor="w",
        )
        self._subtitle_label.pack(fill="x")

    # ---------------- API ----------------
    def set_value(self, value: str, subtitle: str = "") -> None:
        self._value_label.configure(text=value)
        if subtitle:
            self._subtitle_label.configure(text=subtitle)

    def set_subtitle(self, subtitle: str) -> None:
        self._subtitle_label.configure(text=subtitle)

    def set_accent(self, color: Color) -> None:
        self._accent = color
        self._bar.configure(fg_color=color)
        self._icon_label.configure(text_color=color)
