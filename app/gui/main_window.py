"""Main application window. Coordinates pages, services, and event loop."""

from __future__ import annotations

import queue
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from typing import Optional

import customtkinter as ctk

from app.core.config import settings
from app.core.constants import EventTopic, JOB_SOURCES
from app.database.db import init_database
from app.database.models import Job
from app.database.repositories import (
    ExportRepository,
    JobRepository,
    ScrapeRunRepository,
)
from app.gui.branding import load_ctk_image, set_window_icon
from app.gui.dashboard import Dashboard
from app.gui.jobs_table import JobsTable
from app.gui.settings_panel import SettingsPanel
from app.gui.sidebar import Sidebar
from app.gui.themes import COLORS, apply_theme, heading_font, refresh_ttk_styles
from app.services.analytics_service import AnalyticsService
from app.services.export_service import ExportService
from app.services.notification_service import NotificationService
from app.services.scheduler_service import SchedulerService
from app.services.scraping_service import ScrapingResult, ScrapingService
from app.services.settings_service import SettingsService
from app.utils.file_manager import FileManager
from app.utils.logger import get_logger

logger = get_logger(__name__)


class MainWindow(ctk.CTk):
    """Top-level application window."""

    POLL_INTERVAL_MS: int = 80

    def __init__(self) -> None:
        super().__init__()

        # Layer persisted user preferences on top of env defaults BEFORE
        # we apply the theme so the right palette is picked from the start.
        self._settings_service = SettingsService()
        self._settings_service.load_and_apply()

        apply_theme(settings.gui_theme, settings.gui_color_theme, settings.gui_scaling)

        init_database()

        self.title(f"{settings.app_name} v{settings.app_version}")
        self.geometry("1380x840")
        self.minsize(1100, 700)
        self.configure(fg_color=COLORS.bg)
        self.protocol("WM_DELETE_WINDOW", self._handle_close)

        # Window / taskbar icon (multi-resolution .ico)
        set_window_icon(self)

        # ---------------- Service wiring ----------------
        self._job_repo = JobRepository()
        self._run_repo = ScrapeRunRepository()
        self._export_repo = ExportRepository()
        self._event_queue: queue.Queue = queue.Queue()
        self._scraping = ScrapingService(self._event_queue)
        self._export = ExportService(self._job_repo, self._export_repo)
        self._scheduler = SchedulerService()
        self._notify = NotificationService()
        self._analytics = AnalyticsService(self._job_repo, self._run_repo)

        # ---------------- Layout ----------------
        self.grid_columnconfigure(0, weight=0)
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self._sidebar = Sidebar(
            self,
            on_navigate=self._show_page,
            on_toggle_theme=self._handle_theme_toggle,
        )
        self._sidebar.grid(row=0, column=0, sticky="nsw")

        self._content_host = ctk.CTkFrame(self, fg_color=COLORS.bg)
        self._content_host.grid(row=0, column=1, sticky="nsew", padx=18, pady=14)
        self._content_host.grid_rowconfigure(0, weight=1)
        self._content_host.grid_columnconfigure(0, weight=1)

        self._pages: dict[str, ctk.CTkFrame] = {}
        self._build_pages()
        self._show_page("Dashboard")

        # Schedule periodic UI tasks.
        self.after(self.POLL_INTERVAL_MS, self._drain_events)
        self.after(2000, self._refresh_export_count)

        if settings.scheduler_enabled:
            self._configure_scheduler()

    # =====================================================================
    # Pages
    # =====================================================================
    def _build_pages(self) -> None:
        self._pages["Dashboard"] = Dashboard(
            self._content_host,
            on_start_scrape=self._start_scrape,
            on_cancel_scrape=self._cancel_scrape,
            on_export_now=self._export_now,
            repo=self._job_repo,
            run_repo=self._run_repo,
        )
        self._pages["Jobs"] = JobsTable(
            self._content_host,
            repo=self._job_repo,
            on_export_selected=self._export_selected,
            on_change=self._on_jobs_changed,
        )
        self._pages["Follow-ups"] = self._build_followups_page()
        self._pages["Exports"] = self._build_exports_page()
        self._pages["Logs"] = self._build_logs_page()
        self._pages["Analytics"] = self._build_analytics_page()
        self._pages["Settings"] = SettingsPanel(
            self._content_host, on_save=self._on_settings_saved
        )
        self._pages["About"] = self._build_about_page()

    def _show_page(self, name: str) -> None:
        for n, frame in self._pages.items():
            frame.grid_remove()
        page = self._pages.get(name)
        if page is None:
            return
        page.grid(row=0, column=0, sticky="nsew")
        if name == "Dashboard":
            page.refresh_stats()
        elif name == "Jobs":
            page.refresh()
        elif name == "Follow-ups":
            page.refresh()
        elif name == "Exports":
            self._refresh_exports_list()
        elif name == "Logs":
            self._refresh_logs_view()
        elif name == "Analytics":
            self._refresh_analytics_view()

    # =====================================================================
    # Follow-ups page (specialized JobsTable with stats banner)
    # =====================================================================
    def _build_followups_page(self) -> ctk.CTkFrame:
        from app.core.constants import FOLLOW_UP_STATUSES, STATUS_LABELS, JobStatus
        from app.gui.stats_cards import StatCard

        page = ctk.CTkFrame(self._content_host, fg_color="transparent")

        # Header
        head = ctk.CTkFrame(page, fg_color="transparent")
        head.pack(fill="x", pady=(0, 8))
        ctk.CTkLabel(
            head, text="Follow-ups", font=heading_font(),
            text_color=COLORS.text, anchor="w",
        ).pack(side="left")
        ctk.CTkLabel(
            head,
            text=" — track applications, interviews, and offers",
            font=("Segoe UI", 12),
            text_color=COLORS.text_muted,
        ).pack(side="left", padx=6, pady=(8, 0))

        ctk.CTkButton(
            head,
            text="↓ Export follow-ups (Excel)",
            height=32,
            fg_color=COLORS.success,
            hover_color=("#16823A", "#2E9244"),
            text_color=COLORS.on_primary,
            font=("Segoe UI", 11, "bold"),
            command=self._export_follow_ups,
        ).pack(side="right", padx=4)

        # Stat strip (5 small cards — Bookmarked / Applied / Interview / Offer / Rejected)
        stats_wrap = ctk.CTkFrame(page, fg_color="transparent")
        stats_wrap.pack(fill="x", pady=(0, 10))
        for col in range(5):
            stats_wrap.grid_columnconfigure(col, weight=1, uniform="fu_cards")

        accents = {
            JobStatus.BOOKMARKED: COLORS.info,
            JobStatus.APPLIED: COLORS.primary,
            JobStatus.INTERVIEW: COLORS.warning,
            JobStatus.OFFER: COLORS.success,
            JobStatus.REJECTED: COLORS.danger,
        }

        self._followup_cards: dict[str, StatCard] = {}
        for idx, status in enumerate(
            FOLLOW_UP_STATUSES + [JobStatus.REJECTED]
        ):
            card = StatCard(
                stats_wrap,
                title=STATUS_LABELS[status].split(" ", 1)[-1],
                value="0",
                icon=STATUS_LABELS[status].split(" ", 1)[0],
                accent=accents[status],
            )
            card.grid(row=0, column=idx, padx=4, sticky="nsew")
            self._followup_cards[status] = card

        # Embedded JobsTable, pre-filtered to active follow-ups
        from app.gui.jobs_table import JobsTable as _JT

        self._followups_table = _JT(
            page,
            repo=self._job_repo,
            on_export_selected=self._export_selected,
            on_change=self._on_jobs_changed,
        )
        self._followups_table.pack(fill="both", expand=True)
        self._followups_table.set_status_filter("Follow-ups (active)")

        # Attach refresh() method to the page so _show_page can call it.
        def page_refresh() -> None:
            self._followups_table.refresh()
            self._refresh_followup_cards()

        page.refresh = page_refresh  # type: ignore[attr-defined]
        return page

    def _refresh_followup_cards(self) -> None:
        cards = getattr(self, "_followup_cards", None)
        if not cards:
            return
        for status, card in cards.items():
            try:
                n = self._job_repo.count_filtered(status=status)
                card.set_value(str(n))
            except Exception as exc:  # noqa: BLE001
                logger.debug("followup card refresh failed: {e}", e=str(exc))

    def _on_jobs_changed(self) -> None:
        """Called by JobsTable / Follow-ups table when rows change."""
        try:
            self._refresh_followup_cards()
            self._pages["Dashboard"].refresh_stats()
        except Exception as exc:  # noqa: BLE001
            logger.debug("on_jobs_changed failed: {e}", e=str(exc))

    # =====================================================================
    # Exports page
    # =====================================================================
    def _build_exports_page(self) -> ctk.CTkFrame:
        page = ctk.CTkFrame(self._content_host, fg_color="transparent")
        ctk.CTkLabel(
            page, text="Exports", font=heading_font(), text_color=COLORS.text, anchor="w"
        ).pack(fill="x", pady=(0, 8))

        bar = ctk.CTkFrame(page, fg_color="transparent")
        bar.pack(fill="x", pady=(0, 8))
        ctk.CTkButton(
            bar,
            text=f"↓ Export all to {settings.export_default_format.upper()}",
            fg_color=COLORS.primary,
            hover_color=COLORS.primary_hover,
            command=self._export_now,
        ).pack(side="left", padx=4)
        ctk.CTkButton(
            bar,
            text="Open exports folder",
            fg_color="transparent",
            text_color=COLORS.text,
            border_color=COLORS.border,
            border_width=1,
            command=lambda: FileManager.open_in_explorer(settings.export_path),
        ).pack(side="left", padx=4)
        ctk.CTkButton(
            bar,
            text="↻ Refresh",
            fg_color="transparent",
            text_color=COLORS.text,
            border_color=COLORS.border,
            border_width=1,
            command=self._refresh_exports_list,
        ).pack(side="left", padx=4)

        wrapper = ctk.CTkFrame(
            page,
            fg_color=COLORS.surface,
            corner_radius=12,
            border_color=COLORS.border,
            border_width=1,
        )
        wrapper.pack(fill="both", expand=True)

        cols = ("file", "rows", "format", "created")
        tree = ttk.Treeview(
            wrapper,
            columns=cols,
            show="headings",
            style="JobHunter.Treeview",
        )
        tree.heading("file", text="File")
        tree.heading("rows", text="Rows")
        tree.heading("format", text="Format")
        tree.heading("created", text="Created")
        tree.column("file", width=420)
        tree.column("rows", width=80, anchor="e")
        tree.column("format", width=80, anchor="center")
        tree.column("created", width=180, anchor="center")
        tree.pack(fill="both", expand=True, padx=8, pady=8)
        tree.bind("<Double-1>", lambda _e: self._open_selected_export(tree))
        self._exports_tree = tree
        return page

    def _refresh_exports_list(self) -> None:
        tree = getattr(self, "_exports_tree", None)
        if tree is None:
            return
        for iid in tree.get_children():
            tree.delete(iid)
        try:
            records = self._export_repo.recent(limit=200)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Exports list refresh failed: {e}", e=str(exc))
            records = []
        for rec in records:
            created = rec.created_at.strftime("%Y-%m-%d %H:%M") if rec.created_at else "—"
            tree.insert(
                "",
                "end",
                iid=str(rec.id),
                values=(rec.file_path, rec.rows, rec.format, created),
            )

    def _open_selected_export(self, tree) -> None:
        sel = tree.selection()
        if not sel:
            return
        item = tree.item(sel[0])
        path = item["values"][0]
        FileManager.open_in_explorer(__import__("pathlib").Path(path))

    # =====================================================================
    # Logs page
    # =====================================================================
    def _build_logs_page(self) -> ctk.CTkFrame:
        page = ctk.CTkFrame(self._content_host, fg_color="transparent")
        ctk.CTkLabel(
            page, text="Logs", font=heading_font(), text_color=COLORS.text, anchor="w"
        ).pack(fill="x", pady=(0, 8))

        bar = ctk.CTkFrame(page, fg_color="transparent")
        bar.pack(fill="x", pady=(0, 8))
        ctk.CTkButton(bar, text="↻ Refresh", command=self._refresh_logs_view).pack(
            side="left", padx=4
        )
        ctk.CTkButton(
            bar,
            text="Open log file",
            command=lambda: FileManager.open_in_explorer(
                settings.log_path / settings.log_file
            ),
        ).pack(side="left", padx=4)
        ctk.CTkButton(
            bar,
            text="Clear",
            fg_color=COLORS.danger,
            hover_color="#B73B33",
            command=self._handle_clear_logs,
        ).pack(side="left", padx=4)

        self._logs_box = ctk.CTkTextbox(
            page,
            fg_color=COLORS.surface,
            text_color=COLORS.text,
            border_color=COLORS.border,
            border_width=1,
            corner_radius=8,
            font=("Consolas", 10),
        )
        self._logs_box.pack(fill="both", expand=True)
        self._logs_box.configure(state="disabled")
        return page

    def _refresh_logs_view(self) -> None:
        if not hasattr(self, "_logs_box"):
            return
        text = FileManager.read_log_tail(lines=600)
        self._logs_box.configure(state="normal")
        self._logs_box.delete("1.0", "end")
        self._logs_box.insert("end", text or "No logs yet.")
        self._logs_box.see("end")
        self._logs_box.configure(state="disabled")

    def _handle_clear_logs(self) -> None:
        if messagebox.askyesno("Confirm", "Clear the log file?"):
            FileManager.clear_logs()
            self._refresh_logs_view()

    # =====================================================================
    # Analytics page
    # =====================================================================
    def _build_analytics_page(self) -> ctk.CTkFrame:
        page = ctk.CTkFrame(self._content_host, fg_color="transparent")
        ctk.CTkLabel(
            page,
            text="Analytics",
            font=heading_font(),
            text_color=COLORS.text,
            anchor="w",
        ).pack(fill="x", pady=(0, 8))

        ctk.CTkButton(page, text="↻ Refresh", command=self._refresh_analytics_view).pack(
            anchor="e", pady=(0, 8)
        )

        self._analytics_box = ctk.CTkTextbox(
            page,
            fg_color=COLORS.surface,
            text_color=COLORS.text,
            border_color=COLORS.border,
            border_width=1,
            corner_radius=8,
            font=("Consolas", 11),
        )
        self._analytics_box.pack(fill="both", expand=True)
        self._analytics_box.configure(state="disabled")
        return page

    def _refresh_analytics_view(self) -> None:
        if not hasattr(self, "_analytics_box"):
            return
        sections: list[str] = []

        try:
            summary = self._analytics.summary()
            sections.append("== SUMMARY ==")
            sections.append(f"Total jobs : {summary['total_jobs']:,}")
            sections.append(f"New (24h)  : {summary['new_24h']:,}")
            last = summary.get("last_run") or {}
            if last:
                sections.append(
                    f"Last run   : {last.get('finished_at', '—')} "
                    f"(new={last.get('new_jobs', 0)}, "
                    f"dup={last.get('duplicates', 0)}, err={last.get('errors', 0)})"
                )

            sections.append("\n== JOBS PER SOURCE ==")
            for src, count in sorted(
                self._analytics.jobs_per_source().items(),
                key=lambda kv: kv[1],
                reverse=True,
            ):
                sections.append(f"  {src:<22} {self._bar(count, 50)}  {count}")

            sections.append("\n== JOBS PER COUNTRY ==")
            for country, count in sorted(
                self._analytics.jobs_per_country().items(),
                key=lambda kv: kv[1],
                reverse=True,
            ):
                sections.append(f"  {country:<22} {self._bar(count, 50)}  {count}")

            sections.append("\n== TOP COMPANIES ==")
            for name, count in self._analytics.top_companies(limit=10):
                sections.append(f"  {(name or '—')[:30]:<30}  {count}")

            sections.append("\n== REMOTE vs ON-SITE ==")
            for label, count in self._analytics.remote_vs_onsite().items():
                sections.append(f"  {label:<10} {self._bar(count, 40)}  {count}")

            sections.append("\n== JOBS OVER TIME (14 days) ==")
            for day, count in self._analytics.jobs_over_time(days=14):
                sections.append(f"  {day}  {self._bar(count, 40)}  {count}")
        except Exception as exc:  # noqa: BLE001
            sections.append(f"Failed to load analytics: {exc}")

        self._analytics_box.configure(state="normal")
        self._analytics_box.delete("1.0", "end")
        self._analytics_box.insert("end", "\n".join(sections))
        self._analytics_box.configure(state="disabled")

    @staticmethod
    def _bar(value: int, width: int) -> str:
        if value <= 0:
            return ""
        return "█" * min(width, max(1, int(value / 5)))

    # =====================================================================
    # About page
    # =====================================================================
    def _build_about_page(self) -> ctk.CTkFrame:
        page = ctk.CTkFrame(self._content_host, fg_color="transparent")
        ctk.CTkLabel(
            page,
            text="About",
            font=heading_font(),
            text_color=COLORS.text,
            anchor="w",
        ).pack(fill="x", pady=(0, 8))

        card = ctk.CTkFrame(
            page,
            fg_color=COLORS.surface,
            corner_radius=12,
            border_color=COLORS.border,
            border_width=1,
        )
        card.pack(fill="x", pady=8)

        # Logo at the top of the About card
        logo_img = load_ctk_image(128)
        if logo_img is not None:
            ctk.CTkLabel(card, image=logo_img, text="").pack(pady=(22, 6))

        text = (
            f"{settings.app_name} v{settings.app_version}\n"
            f"by {settings.app_vendor}\n\n"
            "AI-powered job aggregation platform.\n\n"
            "Sources:\n"
            "  • " + "\n  • ".join(JOB_SOURCES) + "\n\n"
            "Built with Python, CustomTkinter, Playwright, SQLAlchemy and FastAPI.\n"
            f"© {settings.app_vendor}. All rights reserved."
        )
        ctk.CTkLabel(
            card,
            text=text,
            justify="left",
            anchor="w",
            font=("Segoe UI", 12),
            text_color=COLORS.text,
        ).pack(fill="x", padx=22, pady=22)
        return page

    # =====================================================================
    # Scraping actions
    # =====================================================================
    def _start_scrape(self, payload: dict) -> None:
        if self._scraping.is_running:
            self._notify.info("JobHunter Pro", "A scrape is already running.")
            return

        self._pages["Dashboard"].on_scrape_started()
        self._scraping.start(
            keyword=payload["keyword"] or "developer",
            sources=payload.get("sources") or JOB_SOURCES,
            country=payload.get("country"),
            city=payload.get("city"),
            remote_only=payload.get("remote_only", False),
            on_complete=self._handle_scrape_complete,
        )

    def _cancel_scrape(self) -> None:
        self._scraping.cancel()
        self._notify.info("JobHunter Pro", "Cancellation requested…")

    def _handle_scrape_complete(self, result: ScrapingResult) -> None:
        # Runs on the scraper thread - schedule UI updates on the main thread.
        def update_ui() -> None:
            self._pages["Dashboard"].on_scrape_finished()
            self._pages["Jobs"].refresh()
            kind = "success" if not result.cancelled and result.errors == 0 else "info"
            title = (
                "Scraping finished"
                if not result.cancelled
                else "Scraping cancelled"
            )
            msg = (
                f"New: {result.new_jobs}   Duplicates: {result.duplicates}   "
                f"Errors: {result.errors}"
            )
            self._notify.notify(title, msg, kind=kind)

        self.after(0, update_ui)

    # =====================================================================
    # Export actions
    # =====================================================================
    def _export_follow_ups(self) -> None:
        """One-click Excel export of active follow-up jobs."""
        try:
            path = self._export.export_follow_ups(fmt="xlsx")
            self._refresh_exports_list()
            self._refresh_export_count()
            self._notify.success(
                "Follow-ups exported", f"Saved {path.name} → {path.parent}"
            )
            if settings.export_auto_open:
                FileManager.open_in_explorer(path)
        except Exception as exc:  # noqa: BLE001
            logger.exception("Follow-ups export failed: {e}", e=str(exc))
            self._notify.error("Export failed", str(exc))

    def _export_now(self) -> None:
        try:
            fmt = settings.export_default_format
            path = self._export.export(fmt=fmt)
            self._refresh_exports_list()
            self._refresh_export_count()
            self._notify.success(
                "Export complete", f"Saved {path.name}"
            )
            if settings.export_auto_open:
                FileManager.open_in_explorer(path)
        except Exception as exc:  # noqa: BLE001
            logger.exception("Export failed: {e}", e=str(exc))
            self._notify.error("Export failed", str(exc))

    def _export_selected(self, rows: list[Job]) -> None:
        try:
            fmt = filedialog.asksaveasfilename(
                title="Save export",
                defaultextension=f".{settings.export_default_format}",
                filetypes=(
                    ("Excel workbook", "*.xlsx"),
                    ("CSV file", "*.csv"),
                    ("JSON file", "*.json"),
                ),
                initialdir=str(settings.export_path),
                initialfile=FileManager.timestamped_filename(
                    "selected_jobs", settings.export_default_format
                ),
            )
            if not fmt:
                return
            extension = fmt.rsplit(".", 1)[-1].lower()
            path = self._export.export_selected(rows, fmt=extension)
            self._notify.success("Export complete", f"Saved {path.name}")
            self._refresh_exports_list()
            self._refresh_export_count()
        except Exception as exc:  # noqa: BLE001
            logger.exception("Export selected failed: {e}", e=str(exc))
            self._notify.error("Export failed", str(exc))

    def _refresh_export_count(self) -> None:
        try:
            count = self._export_repo.count()
            self._pages["Dashboard"].update_exports_count(count)
        except Exception as exc:  # noqa: BLE001
            logger.debug("export count refresh failed: {e}", e=str(exc))

    # =====================================================================
    # Event drain
    # =====================================================================
    def _drain_events(self) -> None:
        dashboard: Dashboard = self._pages["Dashboard"]  # type: ignore[assignment]
        progress = dashboard.progress

        try:
            while True:
                event = self._event_queue.get_nowait()
                topic = event.get("topic")

                if topic == EventTopic.SCRAPE_STARTED:
                    progress.set_status("Running", color=COLORS.success)
                    progress.append_log(
                        f"▶  Started: {event.get('keyword') or '(any)'} "
                        f"on {len(event.get('sources') or [])} source(s)"
                    )

                elif topic == EventTopic.SCRAPE_PAGE:
                    src = event.get("source", "?")
                    page = event.get("page", "?")
                    total = event.get("total", 0)
                    progress.set_metric("source", str(src))
                    progress.set_metric("page", str(page))
                    progress.append_log(
                        f"  · {src}: page {page} ({total} cards)"
                    )

                elif topic == EventTopic.SCRAPE_FOUND:
                    progress.set_metric("found", str(event.get("count", "?")))

                elif topic == EventTopic.SCRAPE_PROGRESS:
                    new_jobs = event.get("new_jobs")
                    progress.set_metric("found", str(new_jobs))

                elif topic == EventTopic.SCRAPE_ERROR:
                    progress.append_log(
                        f"  ⚠ Error ({event.get('source', '?')}): "
                        f"{event.get('message', event.get('error', '—'))}"
                    )
                    cur = progress._metric_labels.get("errors")  # noqa: SLF001
                    if cur is not None:
                        try:
                            current = int(cur.cget("text"))
                        except (TypeError, ValueError):
                            current = 0
                        progress.set_metric("errors", str(current + 1))

                elif topic == EventTopic.SCRAPE_COMPLETED:
                    new_jobs = event.get("new_jobs", "?")
                    duplicates = event.get("duplicates", "?")
                    errors = event.get("errors", 0)
                    cancelled = event.get("cancelled", False)
                    progress.append_log(
                        f"✓ Completed | new={new_jobs}  dup={duplicates}  err={errors}"
                        + ("  (cancelled)" if cancelled else "")
                    )
                    progress.set_status(
                        "Cancelled" if cancelled else "Done",
                        color=COLORS.warning if cancelled else COLORS.success,
                    )
        except queue.Empty:
            pass
        finally:
            self.after(self.POLL_INTERVAL_MS, self._drain_events)

    # =====================================================================
    # Scheduler
    # =====================================================================
    def _configure_scheduler(self) -> None:
        try:
            self._scheduler.start()
            self._scheduler.schedule_interval(
                "auto-scrape",
                self._scheduled_scrape,
                minutes=settings.scheduler_interval_minutes,
            )
            if settings.scheduler_run_on_startup:
                self.after(5_000, self._scheduled_scrape)
            logger.info("Scheduler configured.")
        except Exception as exc:  # noqa: BLE001
            logger.warning("Scheduler init failed: {e}", e=str(exc))

    def _scheduled_scrape(self) -> None:
        if self._scraping.is_running:
            return
        logger.info("Scheduled scrape triggered.")
        self._scraping.start(
            keyword="developer",
            sources=list(JOB_SOURCES),
            country=None,
            trigger="scheduler",
        )

    def _on_settings_saved(self, values: dict) -> None:
        """Apply, persist, and live-reconfigure subsystems."""
        try:
            applied = self._settings_service.apply(values)
            self._settings_service.save(values)

            # Theme — apply and restyle ttk if it changed.
            if "gui_theme" in applied:
                apply_theme(applied["gui_theme"])
                refresh_ttk_styles()
                try:
                    self._pages["Jobs"].refresh()
                except Exception:  # noqa: BLE001
                    pass

            # Scheduler — live start/stop/reconfigure.
            self._reconfigure_scheduler()

            self._notify.success(
                "Settings saved",
                f"{len(applied)} preferences applied and saved to disk.",
            )
        except Exception as exc:  # noqa: BLE001
            logger.exception("Settings save failed: {e}", e=str(exc))
            self._notify.error("Settings save failed", str(exc))

    def _reconfigure_scheduler(self) -> None:
        """Bring the scheduler in sync with the current settings."""
        try:
            self._scheduler.remove("auto-scrape")
        except Exception:  # noqa: BLE001
            pass

        if not settings.scheduler_enabled:
            self._scheduler.shutdown(wait=False)
            logger.info("Scheduler disabled by user.")
            return

        self._scheduler.schedule_interval(
            "auto-scrape",
            self._scheduled_scrape,
            minutes=settings.scheduler_interval_minutes,
        )
        logger.info(
            "Scheduler re-armed: every {m} min", m=settings.scheduler_interval_minutes
        )

    # =====================================================================
    # Theme toggle (sidebar callback)
    # =====================================================================
    def _handle_theme_toggle(self, dark: bool) -> None:
        target = "dark" if dark else "light"
        settings.gui_theme = target
        apply_theme(target, settings.gui_color_theme, settings.gui_scaling)
        refresh_ttk_styles()
        # Refresh ttk-styled tables so they pick up the new theme.
        try:
            self._pages["Jobs"].refresh()
        except Exception:  # noqa: BLE001
            pass
        self._refresh_exports_list()
        logger.info("Theme switched to {t}", t=target)

    # =====================================================================
    # Shutdown
    # =====================================================================
    def _handle_close(self) -> None:
        try:
            if self._scraping.is_running:
                if not messagebox.askyesno(
                    "Confirm exit",
                    "A scrape is still running. Cancel and exit?",
                ):
                    return
                self._scraping.cancel()
                self._scraping.wait(timeout=2.0)
        except Exception:  # noqa: BLE001
            pass
        try:
            self._scheduler.shutdown(wait=False)
        except Exception:  # noqa: BLE001
            pass
        self.destroy()


def launch_gui() -> None:
    """Launch the GUI from outside (used by app.main)."""
    app = MainWindow()
    app.mainloop()
