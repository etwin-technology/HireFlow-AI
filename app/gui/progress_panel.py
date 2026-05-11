"""Live progress panel — bar, counters, current source, log tail.

Responsive:
- the metric strip wraps to two rows on narrow widths
- the activity log fills any remaining vertical space
"""

from __future__ import annotations

from typing import Optional

import customtkinter as ctk

from app.gui.themes import COLORS


class ProgressPanel(ctk.CTkFrame):
    """Composite widget showing real-time scraping telemetry."""

    _COMPACT_BREAKPOINT_PX: int = 540

    def __init__(self, parent) -> None:
        super().__init__(
            parent,
            corner_radius=14,
            fg_color=COLORS.surface,
            border_color=COLORS.border,
            border_width=1,
        )
        self._metric_labels: dict[str, ctk.CTkLabel] = {}
        self._metric_cells: dict[str, ctk.CTkFrame] = {}
        self._compact: Optional[bool] = None
        self._build()
        self.bind("<Configure>", self._on_resize)

    # ---------------- UI ----------------
    def _build(self) -> None:
        # Header row
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=18, pady=(14, 6))
        ctk.CTkLabel(
            header, text="Live Scraping", font=("Segoe UI", 14, "bold"),
            text_color=COLORS.text, anchor="w",
        ).pack(side="left")
        self._status_label = ctk.CTkLabel(
            header, text="Idle", font=("Segoe UI", 11, "bold"),
            text_color=COLORS.text_muted,
        )
        self._status_label.pack(side="right")

        # Progress bar
        self._bar = ctk.CTkProgressBar(
            self, mode="determinate", height=10, corner_radius=6,
            progress_color=COLORS.primary,
        )
        self._bar.set(0.0)
        self._bar.pack(fill="x", padx=18, pady=(8, 4))

        # Live metrics
        self._metrics = ctk.CTkFrame(self, fg_color="transparent")
        self._metrics.pack(fill="x", padx=18, pady=(8, 10))

        self._build_metric("Source", "—", "source")
        self._build_metric("Page", "0", "page")
        self._build_metric("Found", "0", "found")
        self._build_metric("Errors", "0", "errors")
        self._layout_metrics(compact=False)

        # Activity label
        ctk.CTkLabel(
            self, text="Activity", font=("Segoe UI", 11, "bold"),
            text_color=COLORS.text_muted, anchor="w",
        ).pack(fill="x", padx=18, pady=(6, 4))

        # Activity log — expands to fill remaining space.
        self._log = ctk.CTkTextbox(
            self, corner_radius=8, fg_color=COLORS.surface_alt,
            text_color=COLORS.text, border_color=COLORS.border, border_width=1,
            font=("Consolas", 10), wrap="word",
        )
        self._log.pack(fill="both", expand=True, padx=18, pady=(0, 16))
        self._log.configure(state="disabled")

    def _build_metric(self, label: str, value: str, key: str) -> None:
        cell = ctk.CTkFrame(self._metrics, fg_color=COLORS.surface_alt, corner_radius=10)
        ctk.CTkLabel(
            cell, text=label, font=("Segoe UI", 10), text_color=COLORS.text_muted,
        ).pack(pady=(8, 0))
        val = ctk.CTkLabel(
            cell, text=value, font=("Segoe UI", 16, "bold"), text_color=COLORS.text,
        )
        val.pack(pady=(0, 8))
        self._metric_cells[key] = cell
        self._metric_labels[key] = val

    # ---------------- Responsive metric layout ----------------
    def _layout_metrics(self, *, compact: bool) -> None:
        if self._compact == compact:
            return
        self._compact = compact

        # Reset
        for cell in self._metric_cells.values():
            cell.grid_forget()

        if compact:
            # 2-column / 2-row layout
            for col in range(2):
                self._metrics.grid_columnconfigure(col, weight=1, uniform="m")
            self._metrics.grid_columnconfigure(2, weight=0)
            self._metrics.grid_columnconfigure(3, weight=0)
            keys = ["source", "page", "found", "errors"]
            for idx, key in enumerate(keys):
                row, col = divmod(idx, 2)
                self._metric_cells[key].grid(
                    row=row, column=col, padx=4, pady=4, sticky="ew"
                )
        else:
            for col in range(4):
                self._metrics.grid_columnconfigure(col, weight=1, uniform="m")
            for idx, key in enumerate(["source", "page", "found", "errors"]):
                self._metric_cells[key].grid(
                    row=0, column=idx, padx=4, pady=4, sticky="ew"
                )

    def _on_resize(self, _event=None) -> None:
        width = self.winfo_width()
        if width <= 1:
            return
        self._layout_metrics(compact=width < self._COMPACT_BREAKPOINT_PX)

    # ---------------- API ----------------
    def set_status(self, label: str, color=None) -> None:
        self._status_label.configure(text=label, text_color=color or COLORS.text_muted)

    def set_progress(self, fraction: float) -> None:
        try:
            fraction = max(0.0, min(1.0, fraction))
            self._bar.set(fraction)
        except Exception:  # noqa: BLE001
            pass

    def set_indeterminate(self, on: bool = True) -> None:
        try:
            if on:
                self._bar.configure(mode="indeterminate")
                self._bar.start()
            else:
                self._bar.stop()
                self._bar.configure(mode="determinate")
        except Exception:  # noqa: BLE001
            pass

    def set_metric(self, key: str, value: str) -> None:
        if key in self._metric_labels:
            self._metric_labels[key].configure(text=value)

    def append_log(self, line: str) -> None:
        try:
            self._log.configure(state="normal")
            self._log.insert("end", line.rstrip() + "\n")
            self._log.see("end")
            self._log.configure(state="disabled")
        except Exception:  # noqa: BLE001
            pass

    def clear_log(self) -> None:
        try:
            self._log.configure(state="normal")
            self._log.delete("1.0", "end")
            self._log.configure(state="disabled")
        except Exception:  # noqa: BLE001
            pass

    def reset(self) -> None:
        self.set_progress(0)
        self.set_indeterminate(False)
        self.set_status("Idle")
        for key in ("page", "found", "errors"):
            self.set_metric(key, "0")
        self.set_metric("source", "—")
