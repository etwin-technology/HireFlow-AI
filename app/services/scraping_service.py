"""Scraping orchestrator.

Runs N scrapers concurrently with a bounded semaphore, applies deduplication,
persists results, and surfaces a stream of GUI-friendly progress events
through a thread-safe ``queue.Queue``.

Designed to run on a dedicated background thread so the Tkinter event loop
remains responsive.
"""

from __future__ import annotations

import asyncio
import queue
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

from app.core.config import settings
from app.core.constants import EventTopic, JOB_SOURCES
from app.database.models import Job
from app.database.repositories import JobRepository, ScrapeRunRepository
from app.scrapers import SCRAPER_REGISTRY
from app.scrapers.base_scraper import BaseScraper, ScrapeQuery
from app.services.deduplication_service import DeduplicationService
from app.utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class ScrapingResult:
    started_at: datetime
    finished_at: Optional[datetime] = None
    total_found: int = 0
    new_jobs: int = 0
    duplicates: int = 0
    errors: int = 0
    per_source: dict[str, int] = field(default_factory=dict)
    error_messages: list[str] = field(default_factory=list)
    cancelled: bool = False

    @property
    def duration_seconds(self) -> float:
        if self.finished_at is None:
            return 0.0
        return (self.finished_at - self.started_at).total_seconds()

    def to_dict(self) -> dict:
        return {
            "started_at": self.started_at.isoformat(),
            "finished_at": self.finished_at.isoformat() if self.finished_at else None,
            "total_found": self.total_found,
            "new_jobs": self.new_jobs,
            "duplicates": self.duplicates,
            "errors": self.errors,
            "per_source": dict(self.per_source),
            "duration_seconds": self.duration_seconds,
            "cancelled": self.cancelled,
        }


class ScrapingService:
    """Coordinates job scraping across multiple sources."""

    def __init__(
        self,
        event_queue: Optional[queue.Queue] = None,
        *,
        job_repo: Optional[JobRepository] = None,
        run_repo: Optional[ScrapeRunRepository] = None,
        dedup: Optional[DeduplicationService] = None,
    ) -> None:
        self._event_queue = event_queue or queue.Queue()
        self._job_repo = job_repo or JobRepository()
        self._run_repo = run_repo or ScrapeRunRepository()
        self._dedup = dedup or DeduplicationService(self._job_repo)
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._async_stop: Optional[asyncio.Event] = None
        self._is_running = threading.Event()

    # ---------------- Public API ----------------
    @property
    def is_running(self) -> bool:
        return self._is_running.is_set()

    @property
    def event_queue(self) -> queue.Queue:
        return self._event_queue

    def start(
        self,
        *,
        keyword: str,
        sources: Optional[list[str]] = None,
        country: Optional[str] = None,
        city: Optional[str] = None,
        remote_only: bool = False,
        max_pages: Optional[int] = None,
        trigger: str = "manual",
        on_complete=None,
    ) -> None:
        """Kick off a scraping run on a background thread."""
        if self.is_running:
            self._publish(EventTopic.SCRAPE_ERROR, message="A scrape is already running.")
            return

        sources = sources or list(JOB_SOURCES)
        query = ScrapeQuery(
            keyword=keyword.strip(),
            country=country,
            city=city,
            remote_only=remote_only,
            max_pages=max_pages or settings.scraper_max_pages,
        )

        self._stop_event.clear()
        self._is_running.set()
        self._thread = threading.Thread(
            target=self._thread_target,
            args=(query, sources, trigger, on_complete),
            name="ScrapingServiceThread",
            daemon=True,
        )
        self._thread.start()

    def cancel(self) -> None:
        """Signal cancellation of the current scrape (cooperative)."""
        if not self.is_running:
            return
        self._stop_event.set()
        if self._loop is not None and self._async_stop is not None:
            self._loop.call_soon_threadsafe(self._async_stop.set)
        logger.info("Cancellation requested.")

    def wait(self, timeout: Optional[float] = None) -> None:
        if self._thread is not None:
            self._thread.join(timeout=timeout)

    # ---------------- Internals ----------------
    def _publish(self, topic: str, **payload) -> None:
        payload["topic"] = topic
        payload.setdefault("ts", time.time())
        try:
            self._event_queue.put_nowait(payload)
        except queue.Full:  # pragma: no cover - unbounded queue by default
            logger.warning("Event queue is full; dropping event {t}", t=topic)

    def _thread_target(
        self,
        query: ScrapeQuery,
        sources: list[str],
        trigger: str,
        on_complete,
    ) -> None:
        try:
            asyncio.run(self._run_async(query, sources, trigger, on_complete))
        except Exception as exc:  # noqa: BLE001
            logger.exception("Scraping thread crashed: {e}", e=str(exc))
            self._publish(EventTopic.SCRAPE_ERROR, message=str(exc))
        finally:
            self._is_running.clear()

    async def _run_async(
        self,
        query: ScrapeQuery,
        sources: list[str],
        trigger: str,
        on_complete,
    ) -> None:
        self._loop = asyncio.get_running_loop()
        self._async_stop = asyncio.Event()

        result = ScrapingResult(started_at=datetime.now(timezone.utc))
        run = self._run_repo.create(
            keyword=query.keyword,
            country=query.country,
            city=query.city,
            remote_only=query.remote_only,
            sources=sources,
            trigger=trigger,
        )

        self._publish(
            EventTopic.SCRAPE_STARTED,
            run_id=run.id,
            sources=sources,
            keyword=query.keyword,
            country=query.country,
        )

        semaphore = asyncio.Semaphore(settings.scraper_concurrent_limit)

        async def progress_cb(event: str, payload: dict) -> None:
            self._publish(event, **payload)

        async def run_one(source_name: str) -> None:
            if source_name not in SCRAPER_REGISTRY:
                logger.warning("Unknown source: {s}", s=source_name)
                return
            scraper_cls = SCRAPER_REGISTRY[source_name]
            async with semaphore:
                try:
                    async with scraper_cls(
                        progress=progress_cb, stop_event=self._async_stop
                    ) as scraper:  # type: BaseScraper
                        await self._consume_scraper(
                            scraper, query, source_name, result, run.id
                        )
                except Exception as exc:  # noqa: BLE001
                    logger.exception(
                        "Source {s} failed: {e}", s=source_name, e=str(exc)
                    )
                    result.errors += 1
                    result.error_messages.append(f"{source_name}: {exc}")
                    self._publish(
                        EventTopic.SCRAPE_ERROR,
                        source=source_name,
                        message=str(exc),
                    )

        tasks = [asyncio.create_task(run_one(name)) for name in sources]
        try:
            await asyncio.gather(*tasks)
        finally:
            result.finished_at = datetime.now(timezone.utc)
            result.cancelled = self._stop_event.is_set()
            self._run_repo.finish(
                run.id,
                total_found=result.total_found,
                new_jobs=result.new_jobs,
                duplicates=result.duplicates,
                errors=result.errors,
                status="cancelled" if result.cancelled else "completed",
            )
            self._publish(
                EventTopic.SCRAPE_COMPLETED,
                **result.to_dict(),
                run_id=run.id,
            )
            if on_complete is not None:
                try:
                    on_complete(result)
                except Exception as exc:  # noqa: BLE001
                    logger.warning("on_complete callback failed: {e}", e=str(exc))

    async def _consume_scraper(
        self,
        scraper: BaseScraper,
        query: ScrapeQuery,
        source_name: str,
        result: ScrapingResult,
        run_id: int,
    ) -> None:
        per_source = result.per_source.setdefault(source_name, 0)  # noqa: F841
        async for record in scraper.run(query):
            if self._stop_event.is_set():
                break
            result.total_found += 1
            result.per_source[source_name] = result.per_source.get(source_name, 0) + 1

            h = self._dedup.compute_hash(record.title, record.company, record.url)
            if self._job_repo.exists(h):
                result.duplicates += 1
                continue

            # If the scraper didn't flag sponsorship explicitly, infer it from
            # the combined title + description + location.
            if record.sponsorship is None:
                sponsorship = BaseScraper.detect_sponsorship(
                    record.title, record.description, record.location
                )
            else:
                sponsorship = bool(record.sponsorship)

            job = Job(
                hash_id=h,
                title=record.title or "(untitled)",
                company=record.company or "",
                location=record.location or "",
                country=record.country,
                remote=bool(record.remote),
                salary=record.salary,
                job_type=record.job_type,
                experience_level=record.experience_level,
                description=record.description,
                source=record.source,
                url=record.url or "",
                posted_date=record.posted_date,
                sponsorship=sponsorship,
                status="new",
                scrape_run_id=run_id,
            )
            try:
                self._job_repo.add(job)
                result.new_jobs += 1
                self._publish(
                    EventTopic.SCRAPE_PROGRESS,
                    source=source_name,
                    total_found=result.total_found,
                    new_jobs=result.new_jobs,
                    duplicates=result.duplicates,
                    title=record.title,
                )
            except Exception as exc:  # noqa: BLE001
                # Race: a parallel scraper inserted the same hash first.
                result.duplicates += 1
                logger.debug("dedupe race on hash {h}: {e}", h=h, e=str(exc))
