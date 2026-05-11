"""Dashboard page — filters, presets, stats, progress, recent activity.

Layout is responsive:
- stat cards use a 3-column grid that wraps to 2 rows automatically
- source checkboxes wrap across multiple rows when the window is narrow
- the live-scraping panel uses fill+expand so its log grows with the window
"""

from __future__ import annotations

from datetime import timezone
from typing import Callable, Optional

import customtkinter as ctk

from app.core.constants import COUNTRIES, JOB_SOURCES, PRESET_FILTERS
from app.database.repositories import JobRepository, ScrapeRunRepository
from app.gui.progress_panel import ProgressPanel
from app.gui.stats_cards import StatCard
from app.gui.themes import COLORS, heading_font, subheading_font
from app.services.analytics_service import AnalyticsService
from app.utils.helpers import humanize_count
from app.utils.logger import get_logger

logger = get_logger(__name__)


# Number of columns the search-row grid uses on a wide layout.
_SEARCH_GRID_COLS = 6


class Dashboard(ctk.CTkFrame):
    """Main dashboard surface."""

    # Width at or below which we switch to compact (single-column) layouts.
    _BREAKPOINT_PX: int = 1100

    def __init__(
        self,
        parent,
        *,
        on_start_scrape: Callable[[dict], None],
        on_cancel_scrape: Callable[[], None],
        on_export_now: Callable[[], None],
        repo: Optional[JobRepository] = None,
        run_repo: Optional[ScrapeRunRepository] = None,
    ) -> None:
        super().__init__(parent, fg_color="transparent")
        self._on_start_scrape = on_start_scrape
        self._on_cancel_scrape = on_cancel_scrape
        self._on_export_now = on_export_now
        self._analytics = AnalyticsService(repo, run_repo)

        # Holders for responsive items
        self._stat_cards: list[StatCard] = []
        self._source_checkboxes: list[ctk.CTkCheckBox] = []
        self._last_layout: str = ""  # "wide" | "compact"

        self._build()
        self.bind("<Configure>", self._on_resize)

    # ---------------- UI ----------------
    def _build(self) -> None:
        # Heading stays OUTSIDE the scroll area so it's always visible.
        head = ctk.CTkFrame(self, fg_color="transparent")
        head.pack(fill="x", pady=(0, 6))
        ctk.CTkLabel(
            head, text="Dashboard", font=heading_font(), text_color=COLORS.text,
            anchor="w",
        ).pack(side="left")
        ctk.CTkLabel(
            head, text=" — your job hunting cockpit", font=("Segoe UI", 12),
            text_color=COLORS.text_muted,
        ).pack(side="left", padx=6, pady=(8, 0))

        # Everything else lives in a scrollable container so users can always
        # reach the stat cards and the live progress panel, even on small
        # laptop screens (1366×768 etc.).
        self._scroll = ctk.CTkScrollableFrame(
            self, fg_color="transparent",
            scrollbar_button_color=COLORS.border,
            scrollbar_button_hover_color=COLORS.primary,
        )
        self._scroll.pack(fill="both", expand=True)

        # Build sections (order matters) — parent is now the scrollable frame.
        self._build_search_card()
        self._build_presets()
        self._build_stat_cards()
        self._build_lower_split()

        self.refresh_stats()

    # ----------------- Search card -----------------
    def _build_search_card(self) -> None:
        card = ctk.CTkFrame(
            self._scroll, corner_radius=14, fg_color=COLORS.surface,
            border_color=COLORS.border, border_width=1,
        )
        card.pack(fill="x", pady=(8, 14))

        wrap = ctk.CTkFrame(card, fg_color="transparent")
        wrap.pack(fill="x", padx=18, pady=14)

        ctk.CTkLabel(
            wrap, text="Run a new search", font=subheading_font(),
            text_color=COLORS.text, anchor="w",
        ).grid(row=0, column=0, columnspan=_SEARCH_GRID_COLS, sticky="w")

        for col in range(_SEARCH_GRID_COLS):
            wrap.grid_columnconfigure(col, weight=1)

        self._kw_var = ctk.StringVar()
        self._country_var = ctk.StringVar(value="Morocco")
        self._city_var = ctk.StringVar()
        self._remote_var = ctk.BooleanVar(value=False)
        self._source_vars: dict[str, ctk.BooleanVar] = {
            s: ctk.BooleanVar(value=True) for s in JOB_SOURCES
        }

        # Row 1: field labels
        for col, label in enumerate(["Keyword", "", "Country", "City", "", ""]):
            ctk.CTkLabel(
                wrap, text=label, anchor="w", text_color=COLORS.text_muted
            ).grid(row=1, column=col, padx=4, pady=(14, 2), sticky="w")

        # Row 2: inputs
        ctk.CTkEntry(
            wrap, placeholder_text="e.g. Python Developer", textvariable=self._kw_var,
        ).grid(row=2, column=0, columnspan=2, padx=4, sticky="ew")
        ctk.CTkOptionMenu(
            wrap, variable=self._country_var, values=list(COUNTRIES.keys()),
        ).grid(row=2, column=2, padx=4, sticky="ew")
        ctk.CTkEntry(wrap, textvariable=self._city_var).grid(
            row=2, column=3, padx=4, sticky="ew"
        )
        ctk.CTkCheckBox(wrap, text="Remote only", variable=self._remote_var).grid(
            row=2, column=4, columnspan=2, padx=8, sticky="w"
        )

        # Sources block — wraps responsively
        ctk.CTkLabel(
            wrap, text="Sources", anchor="w", text_color=COLORS.text_muted,
        ).grid(row=3, column=0, padx=4, pady=(14, 2), sticky="w")

        self._sources_frame = ctk.CTkFrame(wrap, fg_color="transparent")
        self._sources_frame.grid(
            row=4, column=0, columnspan=_SEARCH_GRID_COLS, sticky="ew", padx=4
        )
        self._build_source_checkboxes(per_row=4)  # initial; resize will adjust

        # Action buttons
        btns = ctk.CTkFrame(wrap, fg_color="transparent")
        btns.grid(row=5, column=0, columnspan=_SEARCH_GRID_COLS, sticky="ew", pady=(18, 0))

        self._start_btn = ctk.CTkButton(
            btns, text="▶  Start scraping", width=160, height=40,
            font=("Segoe UI", 12, "bold"),
            fg_color=COLORS.primary, hover_color=COLORS.primary_hover,
            text_color=COLORS.on_primary, command=self._handle_start,
        )
        self._start_btn.pack(side="left", padx=4)

        self._cancel_btn = ctk.CTkButton(
            btns, text="■ Cancel", width=120, height=40,
            fg_color=COLORS.danger, hover_color=("#B73B33", "#B73B33"),
            text_color=COLORS.on_primary, state="disabled",
            command=self._on_cancel_scrape,
        )
        self._cancel_btn.pack(side="left", padx=4)

        ctk.CTkButton(
            btns, text="↓ Export now", width=140, height=40,
            fg_color="transparent", border_color=COLORS.border, border_width=1,
            text_color=COLORS.text, command=self._on_export_now,
        ).pack(side="left", padx=4)

    def _build_source_checkboxes(self, *, per_row: int) -> None:
        # Tear down any existing checkboxes so resize can rebuild cleanly.
        for cb in self._source_checkboxes:
            cb.destroy()
        self._source_checkboxes.clear()

        # Configure the parent grid to evenly distribute columns.
        for col in range(per_row):
            self._sources_frame.grid_columnconfigure(col, weight=1, uniform="sources")

        for idx, src in enumerate(JOB_SOURCES):
            row, col = divmod(idx, per_row)
            cb = ctk.CTkCheckBox(
                self._sources_frame,
                text=src,
                variable=self._source_vars[src],
                text_color=COLORS.text,
            )
            cb.grid(row=row, column=col, padx=6, pady=4, sticky="w")
            self._source_checkboxes.append(cb)

    # ----------------- Presets -----------------
    def _build_presets(self) -> None:
        wrap = ctk.CTkFrame(self._scroll, fg_color="transparent")
        wrap.pack(fill="x", pady=(0, 14))

        ctk.CTkLabel(
            wrap, text="Quick presets:", font=("Segoe UI", 11, "bold"),
            text_color=COLORS.text_muted, anchor="w",
        ).pack(side="left", padx=(0, 8))

        # Use a scrollable frame so presets never overflow horizontally.
        for label in PRESET_FILTERS:
            ctk.CTkButton(
                wrap, text=label, height=30, width=130,
                fg_color=COLORS.surface_alt, hover_color=COLORS.surface,
                text_color=COLORS.text, font=("Segoe UI", 11),
                command=lambda l=label: self._apply_preset(l),
            ).pack(side="left", padx=4)

    # ----------------- Stat cards (3x2 grid) -----------------
    def _build_stat_cards(self) -> None:
        wrap = ctk.CTkFrame(self._scroll, fg_color="transparent")
        wrap.pack(fill="x", pady=(0, 14))

        # 3-column grid → 2 rows of 3 cards
        for col in range(3):
            wrap.grid_columnconfigure(col, weight=1, uniform="cards")

        self._card_total = StatCard(wrap, title="Total jobs", value="0", icon="◆")
        self._card_new = StatCard(
            wrap, title="New (24h)", value="0", icon="✦", accent=COLORS.success
        )
        self._card_dup = StatCard(
            wrap, title="Duplicates removed", value="0", icon="⊘", accent=COLORS.warning
        )
        self._card_sources = StatCard(
            wrap, title="Active sources", value=str(len(JOB_SOURCES)), icon="◎",
            accent=COLORS.info,
        )
        self._card_exports = StatCard(
            wrap, title="Exports", value="0", icon="↓", accent=COLORS.primary
        )
        self._card_last = StatCard(
            wrap, title="Last scrape", value="—", icon="⏱", accent=COLORS.text_muted,
        )

        cards = [
            self._card_total, self._card_new, self._card_dup,
            self._card_sources, self._card_exports, self._card_last,
        ]
        for idx, card in enumerate(cards):
            row, col = divmod(idx, 3)
            card.grid(row=row, column=col, padx=5, pady=5, sticky="nsew")

        self._stat_cards = cards

    # ----------------- Lower split -----------------
    def _build_lower_split(self) -> None:
        # Give the lower split a min height so it always shows even if the
        # window is tall (the scrollable parent will grow as needed).
        self._split = ctk.CTkFrame(self._scroll, fg_color="transparent", height=380)
        self._split.pack(fill="both", expand=True, pady=(0, 8))
        # Prevent the inner content from collapsing the explicit height.
        self._split.pack_propagate(False)
        # Default wide-layout weights
        self._split.grid_columnconfigure(0, weight=2)
        self._split.grid_columnconfigure(1, weight=1)
        self._split.grid_rowconfigure(0, weight=1)

        self._progress = ProgressPanel(self._split)
        self._progress.grid(row=0, column=0, padx=(0, 6), pady=0, sticky="nsew")

        self._recent_runs = ctk.CTkFrame(
            self._split, corner_radius=14, fg_color=COLORS.surface,
            border_color=COLORS.border, border_width=1,
        )
        self._recent_runs.grid(row=0, column=1, padx=(6, 0), pady=0, sticky="nsew")

        ctk.CTkLabel(
            self._recent_runs, text="Recent runs", font=("Segoe UI", 14, "bold"),
            text_color=COLORS.text, anchor="w",
        ).pack(fill="x", padx=18, pady=(14, 4))

        self._runs_box = ctk.CTkTextbox(
            self._recent_runs, corner_radius=8, fg_color=COLORS.surface_alt,
            text_color=COLORS.text, font=("Consolas", 10),
            border_width=1, border_color=COLORS.border,
        )
        self._runs_box.pack(fill="both", expand=True, padx=18, pady=(0, 16))
        self._runs_box.configure(state="disabled")

    # =====================================================================
    # Responsive resize
    # =====================================================================
    def _on_resize(self, event=None) -> None:
        width = self.winfo_width()
        if width <= 1:  # not yet realized
            return

        # 1. Source checkboxes — fit roughly one per 150 px of dashboard width.
        per_row = max(2, min(len(JOB_SOURCES), width // 150))
        if not self._source_checkboxes or len(self._source_checkboxes) != len(JOB_SOURCES):
            self._build_source_checkboxes(per_row=per_row)
        else:
            # Adjust grid placement without rebuilding widgets.
            current_per_row = self._source_checkboxes[0].grid_info().get("row") is not None
            for col in range(per_row):
                self._sources_frame.grid_columnconfigure(col, weight=1, uniform="sources")
            for idx, cb in enumerate(self._source_checkboxes):
                row, col = divmod(idx, per_row)
                cb.grid_configure(row=row, column=col)

        # 2. Lower split → stack vertically on narrow windows.
        layout = "compact" if width < self._BREAKPOINT_PX else "wide"
        if layout != self._last_layout:
            self._apply_split_layout(layout)
            self._last_layout = layout

    def _apply_split_layout(self, layout: str) -> None:
        # Reset grid configuration first.
        for col in (0, 1):
            self._split.grid_columnconfigure(col, weight=0)
        self._split.grid_rowconfigure(0, weight=0)
        self._split.grid_rowconfigure(1, weight=0)

        if layout == "compact":
            # Stack vertically: progress on top, recent runs below.
            self._split.grid_columnconfigure(0, weight=1)
            self._split.grid_rowconfigure(0, weight=2)
            self._split.grid_rowconfigure(1, weight=1)
            self._progress.grid_configure(row=0, column=0, columnspan=1, padx=0, pady=(0, 6))
            self._recent_runs.grid_configure(row=1, column=0, columnspan=1, padx=0, pady=(6, 0))
        else:
            # Side by side: progress left (2x), recent runs right (1x).
            self._split.grid_columnconfigure(0, weight=2)
            self._split.grid_columnconfigure(1, weight=1)
            self._split.grid_rowconfigure(0, weight=1)
            self._progress.grid_configure(row=0, column=0, columnspan=1, padx=(0, 6), pady=0)
            self._recent_runs.grid_configure(row=0, column=1, columnspan=1, padx=(6, 0), pady=0)

    # =====================================================================
    # Presets / actions / public API (unchanged)
    # =====================================================================
    def _apply_preset(self, name: str) -> None:
        preset = PRESET_FILTERS.get(name, {})
        self._kw_var.set(preset.get("keyword", ""))
        if "country" in preset:
            country = preset["country"]
            if country in COUNTRIES:
                self._country_var.set(country)
        self._remote_var.set(bool(preset.get("remote", False)))

    @property
    def progress(self) -> ProgressPanel:
        return self._progress

    def on_scrape_started(self) -> None:
        self._start_btn.configure(state="disabled", text="Scraping…")
        self._cancel_btn.configure(state="normal")
        self._progress.reset()
        self._progress.set_status("Running", color=COLORS.success)
        self._progress.set_indeterminate(True)

    def on_scrape_finished(self) -> None:
        self._start_btn.configure(state="normal", text="▶  Start scraping")
        self._cancel_btn.configure(state="disabled")
        self._progress.set_indeterminate(False)
        self._progress.set_progress(1.0)
        self._progress.set_status("Done", color=COLORS.success)
        self.refresh_stats()

    def refresh_stats(self) -> None:
        try:
            summary = self._analytics.summary()
            self._card_total.set_value(humanize_count(summary["total_jobs"]))
            self._card_new.set_value(humanize_count(summary["new_24h"]))
            last_run = summary.get("last_run")
            if last_run and last_run.get("finished_at"):
                finished_at = last_run["finished_at"][:19].replace("T", " ")
                self._card_last.set_value(finished_at)
                self._card_dup.set_value(humanize_count(last_run.get("duplicates", 0)))
            else:
                self._card_last.set_value("—")
            self._refresh_recent_runs()
        except Exception as exc:  # noqa: BLE001
            logger.warning("refresh_stats failed: {e}", e=str(exc))

    def update_exports_count(self, count: int) -> None:
        self._card_exports.set_value(humanize_count(count))

    def _refresh_recent_runs(self) -> None:
        try:
            runs = ScrapeRunRepository().recent(limit=8)
        except Exception as exc:  # noqa: BLE001
            logger.warning("recent runs failed: {e}", e=str(exc))
            return

        lines: list[str] = []
        for run in runs:
            started = run.started_at.astimezone(timezone.utc).strftime("%H:%M")
            kw = (run.keyword or "(any)")[:24]
            lines.append(
                f"{started}  {run.status:<9}  {kw:<25}  "
                f"new={run.new_jobs}  dup={run.duplicates}  err={run.errors}"
            )
        if not lines:
            lines.append("No runs yet — kick off your first search above.")

        self._runs_box.configure(state="normal")
        self._runs_box.delete("1.0", "end")
        self._runs_box.insert("end", "\n".join(lines))
        self._runs_box.configure(state="disabled")

    def _handle_start(self) -> None:
        sources = [src for src, var in self._source_vars.items() if var.get()]
        if not sources:
            return
        payload = {
            "keyword": self._kw_var.get().strip(),
            "country": self._country_var.get() or None,
            "city": self._city_var.get().strip() or None,
            "remote_only": bool(self._remote_var.get()),
            "sources": sources,
        }
        self._on_start_scrape(payload)
