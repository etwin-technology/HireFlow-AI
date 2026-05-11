"""Analytics service — aggregations used by the dashboard and Analytics page."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional

from app.database.repositories import JobRepository, ScrapeRunRepository
from app.utils.logger import get_logger

logger = get_logger(__name__)


class AnalyticsService:
    """High-level aggregations across the jobs table."""

    def __init__(
        self,
        repo: Optional[JobRepository] = None,
        runs_repo: Optional[ScrapeRunRepository] = None,
    ) -> None:
        self._repo = repo or JobRepository()
        self._runs_repo = runs_repo or ScrapeRunRepository()

    # ---------------- Summary ----------------
    def summary(self) -> dict:
        total = self._repo.count()
        new_24h = self._repo.count_since(
            datetime.now(timezone.utc) - timedelta(hours=24)
        )
        last_run = self._runs_repo.last_completed()
        return {
            "total_jobs": total,
            "new_24h": new_24h,
            "last_run": last_run.to_dict() if last_run else None,
        }

    # ---------------- Distributions ----------------
    def jobs_per_source(self) -> dict[str, int]:
        return self._repo.count_by_source()

    def jobs_per_country(self) -> dict[str, int]:
        return self._repo.count_by_country()

    def top_companies(self, limit: int = 10) -> list[tuple[str, int]]:
        return self._repo.top_companies(limit=limit)

    def remote_vs_onsite(self) -> dict[str, int]:
        return self._repo.remote_vs_onsite()

    def jobs_over_time(self, days: int = 14) -> list[tuple[str, int]]:
        return self._repo.jobs_over_time(days=days)
