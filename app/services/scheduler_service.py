"""APScheduler wrapper for periodic scraping."""

from __future__ import annotations

from typing import Callable, Optional

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from app.core.config import settings
from app.core.exceptions import SchedulerError
from app.utils.logger import get_logger

logger = get_logger(__name__)


class SchedulerService:
    """Manages APScheduler jobs for scheduled scraping runs."""

    def __init__(self) -> None:
        self._scheduler = BackgroundScheduler(
            timezone="UTC",
            job_defaults={
                "coalesce": True,
                "max_instances": 1,
                "misfire_grace_time": 60,
            },
        )
        self._jobs: dict[str, str] = {}  # job_id -> description
        self._started = False

    # ---------------- Lifecycle ----------------
    def start(self) -> None:
        if self._started:
            return
        try:
            self._scheduler.start()
            self._started = True
            logger.info("Scheduler started.")
        except Exception as exc:  # noqa: BLE001
            raise SchedulerError("Failed to start scheduler", cause=exc) from exc

    def shutdown(self, wait: bool = False) -> None:
        if not self._started:
            return
        try:
            self._scheduler.shutdown(wait=wait)
            self._started = False
            logger.info("Scheduler stopped.")
        except Exception as exc:  # noqa: BLE001
            logger.warning("Scheduler shutdown error: {e}", e=str(exc))

    # ---------------- Job registration ----------------
    def schedule_interval(
        self,
        job_id: str,
        callable_: Callable,
        *,
        minutes: Optional[int] = None,
        args: Optional[list] = None,
    ) -> None:
        minutes = minutes or settings.scheduler_interval_minutes
        self._add_job(
            job_id,
            callable_,
            IntervalTrigger(minutes=minutes),
            description=f"interval / every {minutes}m",
            args=args,
        )

    def schedule_daily(
        self,
        job_id: str,
        callable_: Callable,
        *,
        time_hhmm: Optional[str] = None,
        args: Optional[list] = None,
    ) -> None:
        time_hhmm = time_hhmm or settings.scheduler_daily_time
        try:
            hour, minute = (int(p) for p in time_hhmm.split(":"))
        except ValueError as exc:
            raise SchedulerError(
                f"Invalid daily time '{time_hhmm}', expected HH:MM"
            ) from exc

        trigger = CronTrigger(hour=hour, minute=minute)
        self._add_job(
            job_id,
            callable_,
            trigger,
            description=f"daily / {time_hhmm}",
            args=args,
        )

    def run_now(self, callable_: Callable, *args) -> None:
        """Run ``callable_`` immediately on the scheduler executor."""
        if not self._started:
            self.start()
        self._scheduler.add_job(
            callable_,
            args=args,
            id=f"runnow-{id(callable_)}",
            replace_existing=True,
        )

    # ---------------- Helpers ----------------
    def _add_job(
        self,
        job_id: str,
        callable_: Callable,
        trigger,
        *,
        description: str,
        args: Optional[list] = None,
    ) -> None:
        if not self._started:
            self.start()
        self._scheduler.add_job(
            callable_,
            trigger=trigger,
            id=job_id,
            args=args or [],
            replace_existing=True,
        )
        self._jobs[job_id] = description
        logger.info("Scheduled job {id} ({desc})", id=job_id, desc=description)

    def remove(self, job_id: str) -> None:
        try:
            self._scheduler.remove_job(job_id)
            self._jobs.pop(job_id, None)
            logger.info("Removed scheduled job {id}", id=job_id)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Failed to remove job {id}: {e}", id=job_id, e=str(exc))

    def list_jobs(self) -> list[dict]:
        out = []
        for job in self._scheduler.get_jobs():
            out.append(
                {
                    "id": job.id,
                    "description": self._jobs.get(job.id, "scheduled"),
                    "next_run": (
                        job.next_run_time.isoformat() if job.next_run_time else None
                    ),
                    "trigger": str(job.trigger),
                }
            )
        return out
