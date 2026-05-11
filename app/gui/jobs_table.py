"""Jobs table widget — filters, sorting, pagination, follow-up tracking, deletes."""

from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, ttk
from typing import Callable, Optional

import customtkinter as ctk

from app.core.constants import (
    COUNTRIES,
    FOLLOW_UP_STATUSES,
    JOB_SOURCES,
    JOB_STATUSES,
    JOB_TABLE_COLUMNS,
    STATUS_LABELS,
    JobStatus,
)
from app.database.models import Job
from app.database.repositories import JobRepository
from app.gui.dialogs import FollowUpDialog, NotesDialog
from app.gui.themes import COLORS, refresh_ttk_styles
from app.utils.file_manager import FileManager
from app.utils.logger import get_logger

logger = get_logger(__name__)


PAGE_SIZE: int = 100

STATUS_FILTER_OPTIONS: list[str] = [
    "All statuses",
    "Follow-ups (active)",
    *[STATUS_LABELS[s] for s in JOB_STATUSES],
]


class JobsTable(ctk.CTkFrame):
    """Filterable, sortable, paginated table of saved jobs."""

    def __init__(
        self,
        parent,
        *,
        repo: Optional[JobRepository] = None,
        on_export_selected: Optional[Callable[[list[Job]], None]] = None,
        on_change: Optional[Callable[[], None]] = None,
    ) -> None:
        super().__init__(parent, fg_color="transparent")
        self._repo = repo or JobRepository()
        self._on_export_selected = on_export_selected
        self._on_change = on_change

        self._page: int = 1
        self._total: int = 0
        self._sort_col: str = "scraped_at"
        self._sort_desc: bool = True
        self._jobs_cache: dict[str, Job] = {}

        self._build()
        self.refresh()

    # ---------------- UI ----------------
    def _build(self) -> None:
        self._build_filters()
        self._build_action_bar()
        self._build_treeview()
        self._build_pagination()

    def _build_filters(self) -> None:
        filters = ctk.CTkFrame(
            self, fg_color=COLORS.surface, corner_radius=12,
            border_color=COLORS.border, border_width=1,
        )
        filters.pack(fill="x", padx=2, pady=(0, 8))

        row = ctk.CTkFrame(filters, fg_color="transparent")
        row.pack(fill="x", padx=14, pady=12)
        for col in range(8):
            row.grid_columnconfigure(col, weight=1)

        self._keyword_var = ctk.StringVar()
        self._country_var = ctk.StringVar(value="All countries")
        self._source_var = ctk.StringVar(value="All sources")
        self._status_var = ctk.StringVar(value=STATUS_FILTER_OPTIONS[0])
        self._remote_var = ctk.BooleanVar(value=False)
        self._last_search_var = ctk.BooleanVar(value=False)
        self._sponsorship_var = ctk.BooleanVar(value=False)

        # Row 0 — text + selects
        ctk.CTkEntry(
            row, placeholder_text="Search keyword (title / company / description)…",
            textvariable=self._keyword_var,
        ).grid(row=0, column=0, columnspan=2, sticky="ew", padx=4, pady=2)

        ctk.CTkOptionMenu(
            row, variable=self._country_var,
            values=["All countries", *COUNTRIES.keys()],
        ).grid(row=0, column=2, sticky="ew", padx=4, pady=2)

        ctk.CTkOptionMenu(
            row, variable=self._source_var,
            values=["All sources", *JOB_SOURCES],
        ).grid(row=0, column=3, sticky="ew", padx=4, pady=2)

        ctk.CTkOptionMenu(
            row, variable=self._status_var,
            values=STATUS_FILTER_OPTIONS, width=180,
        ).grid(row=0, column=4, sticky="ew", padx=4, pady=2)

        # Row 1 — checkboxes + buttons
        ctk.CTkCheckBox(
            row, text="Remote only", variable=self._remote_var
        ).grid(row=1, column=0, sticky="w", padx=8, pady=(8, 2))

        ctk.CTkCheckBox(
            row, text="Last search only", variable=self._last_search_var
        ).grid(row=1, column=1, sticky="w", padx=8, pady=(8, 2))

        ctk.CTkCheckBox(
            row, text="🛂 Visa sponsorship", variable=self._sponsorship_var
        ).grid(row=1, column=2, sticky="w", padx=8, pady=(8, 2))

        ctk.CTkButton(
            row, text="Apply", width=100, command=self._apply_filters,
            fg_color=COLORS.primary, hover_color=COLORS.primary_hover,
            text_color=COLORS.on_primary,
        ).grid(row=1, column=5, sticky="ew", padx=4, pady=(8, 2))

        ctk.CTkButton(
            row, text="↻ Reset", width=90,
            fg_color="transparent", border_color=COLORS.border, border_width=1,
            text_color=COLORS.text, command=self._reset_filters,
        ).grid(row=1, column=6, sticky="ew", padx=4, pady=(8, 2))

        ctk.CTkButton(
            row, text="↓ Export selected", width=140,
            fg_color=COLORS.success, hover_color=("#16823A", "#2E9244"),
            text_color=COLORS.on_primary,
            command=self._handle_export_selected,
        ).grid(row=1, column=7, sticky="ew", padx=4, pady=(8, 2))

    def _build_action_bar(self) -> None:
        bar = ctk.CTkFrame(self, fg_color="transparent")
        bar.pack(fill="x", padx=2, pady=(0, 6))

        ctk.CTkLabel(
            bar, text="Quick status:", text_color=COLORS.text_muted,
            font=("Segoe UI", 11),
        ).pack(side="left", padx=(0, 4))

        quick_styles = [
            (JobStatus.BOOKMARKED, COLORS.info),
            (JobStatus.APPLIED, COLORS.primary),
            (JobStatus.INTERVIEW, COLORS.warning),
            (JobStatus.OFFER, COLORS.success),
            (JobStatus.REJECTED, COLORS.danger),
        ]
        for status, color in quick_styles:
            ctk.CTkButton(
                bar, text=STATUS_LABELS[status], height=28, width=120,
                fg_color=color, text_color=COLORS.on_primary,
                font=("Segoe UI", 10, "bold"),
                command=lambda s=status: self._mark_selected_as(s),
            ).pack(side="left", padx=2)

        # Right side: delete actions
        ctk.CTkButton(
            bar, text="🗑 Delete all", height=28, width=120,
            fg_color="transparent", border_color=COLORS.danger, border_width=1,
            text_color=COLORS.danger, hover_color=("#FBE9E9", "#3A1F1F"),
            command=self._handle_delete_all,
        ).pack(side="right", padx=2)

        ctk.CTkButton(
            bar, text="🗑 Delete selected", height=28, width=140,
            fg_color=COLORS.danger, text_color=COLORS.on_primary,
            hover_color=("#B73B33", "#B73B33"),
            command=self._handle_delete_selected,
        ).pack(side="right", padx=2)

    def _build_treeview(self) -> None:
        # ttk styling lives in themes.py so it can be re-applied on theme switch.
        refresh_ttk_styles()

        wrapper = ctk.CTkFrame(
            self, fg_color=COLORS.surface, corner_radius=12,
            border_color=COLORS.border, border_width=1,
        )
        wrapper.pack(fill="both", expand=True)

        columns = [c[0] for c in JOB_TABLE_COLUMNS]
        self._tree = ttk.Treeview(
            wrapper, columns=columns, show="headings",
            style="JobHunter.Treeview", selectmode="extended",
        )

        for attr, display, width in JOB_TABLE_COLUMNS:
            self._tree.heading(
                attr, text=display,
                command=lambda c=attr: self._handle_sort(c),
            )
            self._tree.column(attr, width=width, anchor="w", stretch=True)

        vsb = ttk.Scrollbar(wrapper, orient="vertical", command=self._tree.yview)
        self._tree.configure(yscrollcommand=vsb.set)

        self._tree.pack(side="left", fill="both", expand=True, padx=(8, 0), pady=8)
        vsb.pack(side="right", fill="y", pady=8)

        # Row-tag colors (one per status) — applied on every row insert.
        self._configure_row_tags()

        self._tree.bind("<Double-1>", self._handle_double_click)
        self._tree.bind("<Button-3>", self._handle_right_click)
        self._tree.bind("<Delete>", lambda _e: self._handle_delete_selected())

        # Context menu
        self._build_context_menu()

    def _configure_row_tags(self) -> None:
        from app.gui.themes import resolve

        surface = resolve(COLORS.surface)
        row_alt = resolve(COLORS.row_alt)

        # Per-status foreground colors — tuned for both light + dark modes.
        self._tree.tag_configure(
            "status_bookmarked", foreground=resolve(COLORS.tag_bookmarked)
        )
        self._tree.tag_configure(
            "status_applied", foreground=resolve(COLORS.tag_applied)
        )
        self._tree.tag_configure(
            "status_interview", foreground=resolve(COLORS.tag_interview)
        )
        self._tree.tag_configure(
            "status_offer", foreground=resolve(COLORS.tag_offer)
        )
        self._tree.tag_configure(
            "status_rejected", foreground=resolve(COLORS.tag_rejected)
        )
        self._tree.tag_configure(
            "status_new", foreground=resolve(COLORS.text)
        )

        # Alternating row backgrounds for readability.
        self._tree.tag_configure("row_even", background=surface)
        self._tree.tag_configure("row_odd", background=row_alt)

    def _build_context_menu(self) -> None:
        self._menu = tk.Menu(self._tree, tearoff=0)
        self._menu.add_command(label="Open URL", command=self._action_open)
        self._menu.add_command(label="Copy row", command=self._action_copy)
        self._menu.add_separator()

        status_menu = tk.Menu(self._menu, tearoff=0)
        for status in JOB_STATUSES:
            status_menu.add_command(
                label=STATUS_LABELS[status],
                command=lambda s=status: self._mark_selected_as(s),
            )
        self._menu.add_cascade(label="Mark as…", menu=status_menu)

        self._menu.add_command(label="Edit notes…", command=self._action_notes)
        self._menu.add_command(
            label="Set follow-up date…", command=self._action_set_follow_up
        )
        self._menu.add_separator()
        self._menu.add_command(
            label="Export selected", command=self._handle_export_selected
        )
        self._menu.add_separator()
        self._menu.add_command(
            label="Delete selected", command=self._handle_delete_selected
        )

    def _build_pagination(self) -> None:
        bar = ctk.CTkFrame(self, fg_color="transparent")
        bar.pack(fill="x", padx=2, pady=(8, 0))

        self._summary = ctk.CTkLabel(
            bar, text="0 jobs", font=("Segoe UI", 11), text_color=COLORS.text_muted
        )
        self._summary.pack(side="left")

        right = ctk.CTkFrame(bar, fg_color="transparent")
        right.pack(side="right")

        self._prev_btn = ctk.CTkButton(
            right, text="◀ Prev", width=80, command=self._prev_page
        )
        self._prev_btn.pack(side="left", padx=4)

        self._page_label = ctk.CTkLabel(
            right, text="Page 1", font=("Segoe UI", 11), text_color=COLORS.text
        )
        self._page_label.pack(side="left", padx=8)

        self._next_btn = ctk.CTkButton(
            right, text="Next ▶", width=80, command=self._next_page
        )
        self._next_btn.pack(side="left", padx=4)

    # =====================================================================
    # Data loading
    # =====================================================================
    def refresh(self) -> None:
        # Re-apply ttk styles + tag colors so theme switches take effect.
        refresh_ttk_styles()
        self._configure_row_tags()

        self._jobs_cache.clear()
        for item_id in self._tree.get_children():
            self._tree.delete(item_id)

        filters = self._collect_filters()
        offset = (self._page - 1) * PAGE_SIZE

        try:
            jobs = self._repo.list_jobs(
                limit=PAGE_SIZE,
                offset=offset,
                order_by=self._sort_col,
                descending=self._sort_desc,
                **filters,
            )
            self._total = self._repo.count_filtered(
                keyword=filters.get("keyword"),
                country=filters.get("country"),
                source=filters.get("source"),
                remote_only=filters.get("remote_only", False),
                status=filters.get("status"),
                statuses=filters.get("statuses"),
                scrape_run_id=filters.get("scrape_run_id"),
                sponsorship_only=filters.get("sponsorship_only", False),
            )
        except Exception as exc:  # noqa: BLE001
            logger.exception("JobsTable refresh failed: {e}", e=str(exc))
            jobs = []
            self._total = 0

        for index, job in enumerate(jobs):
            iid = str(job.id)
            self._jobs_cache[iid] = job
            stripe = "row_odd" if index % 2 else "row_even"
            self._tree.insert(
                "", "end", iid=iid,
                values=self._row_values(job),
                tags=(stripe, f"status_{job.status}"),
            )

        self._summary.configure(text=f"{self._total:,} jobs match")
        self._page_label.configure(text=f"Page {self._page}")

    @staticmethod
    def _row_values(job: Job) -> tuple:
        # Order must match JOB_TABLE_COLUMNS
        # Posted date: use the source date if known, else fall back to the
        # date we scraped it (suffixed with "*" so the user knows).
        if job.posted_date:
            posted = job.posted_date.strftime("%Y-%m-%d")
        elif job.scraped_at:
            posted = f"{job.scraped_at.strftime('%Y-%m-%d')} *"
        else:
            posted = "—"

        return (
            STATUS_LABELS.get(job.status, job.status or "—"),
            job.title,
            job.company,
            job.location,
            job.source,
            "🛂 Yes" if job.sponsorship else "—",
            job.salary or "—",
            posted,
            job.follow_up_date.strftime("%Y-%m-%d") if job.follow_up_date else "—",
        )

    def _collect_filters(self) -> dict:
        filters: dict = {}
        if kw := self._keyword_var.get().strip():
            filters["keyword"] = kw
        country = self._country_var.get()
        if country and country != "All countries":
            filters["country"] = country
        source = self._source_var.get()
        if source and source != "All sources":
            filters["source"] = source
        if self._remote_var.get():
            filters["remote_only"] = True

        # Status filter
        chosen = self._status_var.get()
        if chosen == "Follow-ups (active)":
            filters["statuses"] = FOLLOW_UP_STATUSES
        elif chosen != STATUS_FILTER_OPTIONS[0]:
            # Reverse lookup from label to status key
            for key, label in STATUS_LABELS.items():
                if label == chosen:
                    filters["status"] = key
                    break

        # Last search filter
        if self._last_search_var.get():
            last_id = self._repo.last_run_id()
            if last_id is not None:
                filters["scrape_run_id"] = last_id

        # Visa sponsorship filter
        if self._sponsorship_var.get():
            filters["sponsorship_only"] = True

        return filters

    def _apply_filters(self) -> None:
        self._page = 1
        self.refresh()

    def _reset_filters(self) -> None:
        self._keyword_var.set("")
        self._country_var.set("All countries")
        self._source_var.set("All sources")
        self._status_var.set(STATUS_FILTER_OPTIONS[0])
        self._remote_var.set(False)
        self._last_search_var.set(False)
        self._sponsorship_var.set(False)
        self._page = 1
        self.refresh()

    # =====================================================================
    # Public helpers
    # =====================================================================
    def set_status_filter(self, label: str) -> None:
        """Programmatically apply a status filter (used by Follow-ups page)."""
        if label in STATUS_FILTER_OPTIONS:
            self._status_var.set(label)
            self._page = 1
            self.refresh()

    def selected_jobs(self) -> list[Job]:
        return [
            self._jobs_cache[iid]
            for iid in self._tree.selection()
            if iid in self._jobs_cache
        ]

    # =====================================================================
    # Sorting / paging
    # =====================================================================
    def _handle_sort(self, column: str) -> None:
        # Status column is a display label; sort on the underlying field name.
        if self._sort_col == column:
            self._sort_desc = not self._sort_desc
        else:
            self._sort_col = column
            self._sort_desc = True
        self._page = 1
        self.refresh()

    def _prev_page(self) -> None:
        if self._page > 1:
            self._page -= 1
            self.refresh()

    def _next_page(self) -> None:
        max_page = max(1, (self._total + PAGE_SIZE - 1) // PAGE_SIZE)
        if self._page < max_page:
            self._page += 1
            self.refresh()

    # =====================================================================
    # Actions
    # =====================================================================
    def _handle_double_click(self, _event=None) -> None:
        self._action_open()

    def _handle_right_click(self, event) -> None:
        rowid = self._tree.identify_row(event.y)
        if rowid and rowid not in self._tree.selection():
            self._tree.selection_set(rowid)
        if not self._tree.selection():
            return
        try:
            self._menu.tk_popup(event.x_root, event.y_root)
        finally:
            self._menu.grab_release()

    def _action_open(self) -> None:
        for job in self.selected_jobs():
            if job.url:
                FileManager.open_url(job.url)
                break

    def _action_copy(self) -> None:
        rows = self.selected_jobs()
        if not rows:
            return
        text = "\n".join(
            f"{j.title}\t{j.company}\t{j.location}\t{j.source}\t{j.url}\t{j.status}"
            for j in rows
        )
        try:
            self.clipboard_clear()
            self.clipboard_append(text)
            self.update()
        except Exception as exc:  # noqa: BLE001
            logger.warning("Copy to clipboard failed: {e}", e=str(exc))

    def _action_notes(self) -> None:
        rows = self.selected_jobs()
        if len(rows) != 1:
            messagebox.showinfo(
                "Notes", "Select exactly one job to edit its notes."
            )
            return
        job = rows[0]
        result = NotesDialog(
            self.winfo_toplevel(),
            title=f"Notes — {job.title[:40]}",
            initial=job.notes or "",
        ).show()
        if result is None:
            return
        try:
            self._repo.update_notes(job.id, result or None)
            self.refresh()
            self._fire_change()
        except Exception as exc:  # noqa: BLE001
            logger.exception("update_notes failed: {e}", e=str(exc))
            messagebox.showerror("Notes", f"Failed to save notes:\n{exc}")

    def _action_set_follow_up(self) -> None:
        rows = self.selected_jobs()
        if not rows:
            return
        # Use the first selection as the initial date.
        initial = rows[0].follow_up_date
        when, cleared = FollowUpDialog(
            self.winfo_toplevel(), initial=initial
        ).show()
        if when is None and not cleared:
            return  # user cancelled
        try:
            for job in rows:
                self._repo.set_follow_up(job.id, when)
            self.refresh()
            self._fire_change()
        except Exception as exc:  # noqa: BLE001
            logger.exception("set_follow_up failed: {e}", e=str(exc))
            messagebox.showerror("Follow-up", f"Failed to save:\n{exc}")

    def _mark_selected_as(self, status: str) -> None:
        rows = self.selected_jobs()
        if not rows:
            return
        try:
            self._repo.update_status_many([j.id for j in rows], status)
            self.refresh()
            self._fire_change()
        except Exception as exc:  # noqa: BLE001
            logger.exception("update_status failed: {e}", e=str(exc))
            messagebox.showerror("Update status", f"Failed:\n{exc}")

    def _handle_delete_selected(self) -> None:
        rows = self.selected_jobs()
        if not rows:
            return
        if not messagebox.askyesno(
            "Delete jobs",
            f"Permanently delete {len(rows)} selected job"
            f"{'s' if len(rows) != 1 else ''}?",
        ):
            return
        try:
            deleted = self._repo.delete_many([j.id for j in rows])
            self.refresh()
            self._fire_change()
            logger.info("Deleted {n} jobs", n=deleted)
        except Exception as exc:  # noqa: BLE001
            logger.exception("delete_many failed: {e}", e=str(exc))
            messagebox.showerror("Delete jobs", f"Failed:\n{exc}")

    def _handle_delete_all(self) -> None:
        total = self._total
        if total == 0:
            messagebox.showinfo("Delete all", "There are no jobs to delete.")
            return
        if not messagebox.askyesno(
            "Delete ALL jobs",
            f"This will permanently delete EVERY job in the database "
            f"({self._repo.count():,} rows).\n\nThis cannot be undone.\n\n"
            f"Are you sure?",
        ):
            return
        # Double-confirm for safety
        if not messagebox.askyesno(
            "Confirm again",
            "Really delete every job? This is your last chance to cancel.",
        ):
            return
        try:
            deleted = self._repo.clear_all()
            self.refresh()
            self._fire_change()
            messagebox.showinfo("Done", f"Deleted {deleted:,} jobs.")
            logger.info("Cleared all {n} jobs from the database.", n=deleted)
        except Exception as exc:  # noqa: BLE001
            logger.exception("clear_all failed: {e}", e=str(exc))
            messagebox.showerror("Delete all", f"Failed:\n{exc}")

    def _handle_export_selected(self) -> None:
        rows = self.selected_jobs()
        if not rows:
            messagebox.showinfo(
                "Export selected", "Select at least one row first."
            )
            return
        if self._on_export_selected is not None:
            self._on_export_selected(rows)

    def _fire_change(self) -> None:
        if self._on_change is not None:
            try:
                self._on_change()
            except Exception:  # noqa: BLE001
                pass
