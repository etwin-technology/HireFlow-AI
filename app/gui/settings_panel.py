"""Settings page — runtime preferences (in-memory; not persisted to .env)."""

from __future__ import annotations

from pathlib import Path
from tkinter import filedialog
from typing import Callable, Optional

import customtkinter as ctk

from app.core.config import settings
from app.gui.themes import COLORS, apply_theme
from app.utils.file_manager import FileManager


class SettingsPanel(ctk.CTkFrame):
    """User-modifiable settings."""

    def __init__(
        self,
        parent,
        *,
        on_save: Optional[Callable[[dict], None]] = None,
    ) -> None:
        super().__init__(parent, fg_color="transparent")
        self._on_save = on_save
        self._vars: dict[str, ctk.Variable] = {}
        self._build()

    # ---------------- UI ----------------
    def _build(self) -> None:
        scroll = ctk.CTkScrollableFrame(self, fg_color="transparent")
        scroll.pack(fill="both", expand=True)

        self._add_section(scroll, "Scraping")
        self._add_int(scroll, "Max pages per source", "max_pages", settings.scraper_max_pages, 1, 50)
        self._add_int(scroll, "Retry count", "retry_count", settings.scraper_retry_count, 0, 10)
        self._add_float(scroll, "Min delay (s)", "min_delay", settings.scraper_min_delay, 0.0, 30.0)
        self._add_float(scroll, "Max delay (s)", "max_delay", settings.scraper_max_delay, 0.0, 60.0)
        self._add_int(scroll, "Concurrent sources", "concurrent", settings.scraper_concurrent_limit, 1, 8)
        self._add_bool(scroll, "Headless browser", "headless", settings.scraper_headless)
        self._add_bool(
            scroll,
            "Rotate user-agents",
            "ua_rotate",
            settings.scraper_user_agent_rotate,
        )

        self._add_section(scroll, "Export")
        self._add_option(
            scroll,
            "Default format",
            "export_format",
            settings.export_default_format,
            ["xlsx", "csv", "json"],
        )
        self._add_bool(
            scroll, "Auto-open file after export", "export_auto_open", settings.export_auto_open
        )
        self._add_path_picker(
            scroll,
            label="Export directory",
            key="export_dir",
            value=str(settings.export_path),
        )

        self._add_section(scroll, "Scheduler")
        self._add_bool(scroll, "Enable scheduler", "scheduler_enabled", settings.scheduler_enabled)
        self._add_int(
            scroll,
            "Interval (minutes)",
            "scheduler_interval",
            settings.scheduler_interval_minutes,
            5,
            1440,
        )
        self._add_text(
            scroll,
            "Daily run time (HH:MM)",
            "scheduler_daily",
            settings.scheduler_daily_time,
        )
        self._add_bool(
            scroll,
            "Run on startup",
            "scheduler_on_startup",
            settings.scheduler_run_on_startup,
        )

        self._add_section(scroll, "Notifications")
        self._add_bool(
            scroll,
            "Enable notifications",
            "notifications_enabled",
            settings.notifications_enabled,
        )
        self._add_bool(
            scroll,
            "Notify on scrape complete",
            "notify_complete",
            settings.notify_on_complete,
        )
        self._add_bool(
            scroll, "Notify on errors", "notify_error", settings.notify_on_error
        )

        self._add_section(scroll, "Appearance")
        self._add_option(
            scroll, "Theme", "theme", settings.gui_theme, ["dark", "light"]
        )

        # Save bar
        bar = ctk.CTkFrame(self, fg_color="transparent")
        bar.pack(fill="x", pady=12)
        ctk.CTkButton(
            bar,
            text="Save settings",
            width=160,
            fg_color=COLORS.primary,
            hover_color=COLORS.primary_hover,
            command=self._handle_save,
        ).pack(side="right", padx=4)
        ctk.CTkButton(
            bar,
            text="Reset to defaults",
            width=160,
            fg_color="transparent",
            border_color=COLORS.border,
            border_width=1,
            text_color=COLORS.text,
            command=self._handle_reset,
        ).pack(side="right", padx=4)

    # ---------------- Row helpers ----------------
    def _add_section(self, parent, title: str) -> None:
        ctk.CTkLabel(
            parent,
            text=title,
            font=("Segoe UI", 14, "bold"),
            text_color=COLORS.text,
            anchor="w",
        ).pack(fill="x", padx=12, pady=(18, 6))

    def _row(self, parent, label: str) -> ctk.CTkFrame:
        frame = ctk.CTkFrame(
            parent,
            corner_radius=10,
            fg_color=COLORS.surface,
            border_color=COLORS.border,
            border_width=1,
        )
        frame.pack(fill="x", padx=12, pady=4)
        inner = ctk.CTkFrame(frame, fg_color="transparent")
        inner.pack(fill="x", padx=14, pady=10)
        ctk.CTkLabel(
            inner,
            text=label,
            font=("Segoe UI", 12),
            text_color=COLORS.text,
            anchor="w",
        ).pack(side="left", fill="x", expand=True)
        return inner

    def _add_int(self, parent, label, key, value, lo, hi):
        inner = self._row(parent, label)
        var = ctk.IntVar(value=int(value))
        ctk.CTkEntry(inner, width=120, textvariable=var).pack(side="right")
        self._vars[key] = var

    def _add_float(self, parent, label, key, value, lo, hi):
        inner = self._row(parent, label)
        var = ctk.DoubleVar(value=float(value))
        ctk.CTkEntry(inner, width=120, textvariable=var).pack(side="right")
        self._vars[key] = var

    def _add_text(self, parent, label, key, value):
        inner = self._row(parent, label)
        var = ctk.StringVar(value=str(value))
        ctk.CTkEntry(inner, width=160, textvariable=var).pack(side="right")
        self._vars[key] = var

    def _add_bool(self, parent, label, key, value):
        inner = self._row(parent, label)
        var = ctk.BooleanVar(value=bool(value))
        ctk.CTkSwitch(inner, text="", variable=var).pack(side="right")
        self._vars[key] = var

    def _add_option(self, parent, label, key, value, options):
        inner = self._row(parent, label)
        var = ctk.StringVar(value=str(value))
        ctk.CTkOptionMenu(inner, variable=var, values=options, width=160).pack(
            side="right"
        )
        self._vars[key] = var

    def _add_path_picker(self, parent, *, label: str, key: str, value: str) -> None:
        """Folder picker row. Stores the chosen path in self._vars[key]."""
        frame = ctk.CTkFrame(
            parent, corner_radius=10, fg_color=COLORS.surface,
            border_color=COLORS.border, border_width=1,
        )
        frame.pack(fill="x", padx=12, pady=4)

        top = ctk.CTkFrame(frame, fg_color="transparent")
        top.pack(fill="x", padx=14, pady=(10, 4))
        ctk.CTkLabel(
            top, text=label, font=("Segoe UI", 12),
            text_color=COLORS.text, anchor="w",
        ).pack(side="left", fill="x", expand=True)

        var = ctk.StringVar(value=value)
        self._vars[key] = var

        controls = ctk.CTkFrame(frame, fg_color="transparent")
        controls.pack(fill="x", padx=14, pady=(0, 10))

        entry = ctk.CTkEntry(controls, textvariable=var)
        entry.pack(side="left", fill="x", expand=True, padx=(0, 6))

        ctk.CTkButton(
            controls, text="Browse…", width=90,
            fg_color=COLORS.primary, hover_color=COLORS.primary_hover,
            text_color=COLORS.on_primary,
            command=lambda: self._pick_directory(var, label),
        ).pack(side="left", padx=2)

        ctk.CTkButton(
            controls, text="Open", width=70,
            fg_color="transparent", border_color=COLORS.border, border_width=1,
            text_color=COLORS.text,
            command=lambda: FileManager.open_in_explorer(Path(var.get())),
        ).pack(side="left", padx=2)

    @staticmethod
    def _pick_directory(var: ctk.StringVar, title: str) -> None:
        current = var.get().strip() or str(settings.export_path)
        chosen = filedialog.askdirectory(
            title=f"Pick {title}", initialdir=current, mustexist=False
        )
        if chosen:
            var.set(chosen)

    # ---------------- Save / reset ----------------
    # Map GUI variable keys -> settings.* attribute names.
    _SETTING_KEY_MAP: dict[str, str] = {
        "max_pages": "scraper_max_pages",
        "retry_count": "scraper_retry_count",
        "min_delay": "scraper_min_delay",
        "max_delay": "scraper_max_delay",
        "concurrent": "scraper_concurrent_limit",
        "headless": "scraper_headless",
        "ua_rotate": "scraper_user_agent_rotate",
        "export_format": "export_default_format",
        "export_auto_open": "export_auto_open",
        "export_dir": "export_dir",
        "scheduler_enabled": "scheduler_enabled",
        "scheduler_interval": "scheduler_interval_minutes",
        "scheduler_daily": "scheduler_daily_time",
        "scheduler_on_startup": "scheduler_run_on_startup",
        "notifications_enabled": "notifications_enabled",
        "notify_complete": "notify_on_complete",
        "notify_error": "notify_on_error",
        "theme": "gui_theme",
    }

    def collect(self) -> dict:
        """Return the form values keyed by ``settings.*`` attribute names."""
        out: dict = {}
        for gui_key, var in self._vars.items():
            settings_key = self._SETTING_KEY_MAP.get(gui_key, gui_key)
            out[settings_key] = var.get()
        return out

    def _handle_save(self) -> None:
        values = self.collect()
        # Apply theme immediately for instant feedback.
        target_theme = str(values.get("gui_theme", settings.gui_theme))
        if target_theme != settings.gui_theme:
            apply_theme(target_theme)
        # Hand off everything else to MainWindow → SettingsService.
        if self._on_save is not None:
            self._on_save(values)

    def _handle_reset(self) -> None:
        defaults = {
            "max_pages": 5,
            "retry_count": 3,
            "min_delay": 1.5,
            "max_delay": 4.0,
            "concurrent": 3,
            "headless": True,
            "ua_rotate": True,
            "export_format": "xlsx",
            "export_auto_open": False,
            "export_dir": "exports",
            "scheduler_enabled": False,
            "scheduler_interval": 120,
            "scheduler_daily": "08:00",
            "scheduler_on_startup": False,
            "notifications_enabled": True,
            "notify_complete": True,
            "notify_error": True,
            "theme": "dark",
        }
        for key, value in defaults.items():
            if key in self._vars:
                self._vars[key].set(value)
