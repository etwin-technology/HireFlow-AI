"""Abstract base scraper and shared dataclasses.

Every concrete scraper subclasses ``BaseScraper`` and implements ``run()``
(async) which yields ``JobRecord`` instances.

The base class provides:
- HTTP client (httpx) with rotating user agents, retries, throttling
- helpers for parsing HTML (bs4 / lxml)
- a uniform ``progress`` callback so the GUI/service layer can stream events
- timeouts, retries (tenacity), rate-limit awareness
"""

from __future__ import annotations

import asyncio
import random
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import AsyncIterator, Awaitable, Callable, Optional

import httpx
from bs4 import BeautifulSoup
from tenacity import (
    AsyncRetrying,
    RetryError,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential_jitter,
)

from app.core.config import settings
from app.core.exceptions import RateLimitError, ScraperError, ScraperTimeoutError
from app.utils.browser import pick_user_agent
from app.utils.helpers import parse_posted_date, random_delay, safe_text
from app.utils.logger import get_logger


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------
@dataclass
class ScrapeQuery:
    """Search parameters passed to each scraper."""

    keyword: str = ""
    country: Optional[str] = None
    city: Optional[str] = None
    remote_only: bool = False
    max_pages: int = field(default_factory=lambda: settings.scraper_max_pages)
    extra: dict = field(default_factory=dict)


@dataclass
class JobRecord:
    """Normalized job posting as yielded by scrapers."""

    title: str
    company: str
    location: str
    url: str
    source: str
    country: Optional[str] = None
    remote: bool = False
    salary: Optional[str] = None
    job_type: Optional[str] = None
    experience_level: Optional[str] = None
    description: Optional[str] = None
    posted_date: Optional[datetime] = None
    sponsorship: Optional[bool] = None  # ``None`` = unknown; service layer will infer.

    def to_dict(self) -> dict:
        return {
            "title": self.title,
            "company": self.company,
            "location": self.location,
            "url": self.url,
            "source": self.source,
            "country": self.country,
            "remote": self.remote,
            "salary": self.salary,
            "job_type": self.job_type,
            "experience_level": self.experience_level,
            "description": self.description,
            "posted_date": self.posted_date.isoformat() if self.posted_date else None,
            "sponsorship": self.sponsorship,
        }


# Optional async progress callback signature: (event_name, payload) -> None
ProgressCallback = Callable[[str, dict], Awaitable[None] | None]


# ---------------------------------------------------------------------------
# Base scraper
# ---------------------------------------------------------------------------
class BaseScraper(ABC):
    """Common base class for all source scrapers."""

    #: The display name of this source (e.g. "LinkedIn").
    SOURCE_NAME: str = "Base"

    #: Whether this scraper requires Playwright (vs. plain httpx + bs4).
    REQUIRES_BROWSER: bool = False

    def __init__(
        self,
        *,
        progress: Optional[ProgressCallback] = None,
        stop_event: Optional[asyncio.Event] = None,
    ) -> None:
        self.logger = get_logger(self.__class__.__name__)
        self._progress = progress
        self._stop_event = stop_event
        self._client: Optional[httpx.AsyncClient] = None

    # ---------------- Lifecycle ----------------
    async def __aenter__(self) -> "BaseScraper":
        self._client = httpx.AsyncClient(
            timeout=settings.scraper_timeout,
            follow_redirects=True,
            headers=self._default_headers(),
        )
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        if self._client is not None:
            await self._client.aclose()
        self._client = None

    # ---------------- API ----------------
    @abstractmethod
    async def run(self, query: ScrapeQuery) -> AsyncIterator[JobRecord]:
        """Yield ``JobRecord`` instances for the given query.

        Implementations must:
        - respect ``query.max_pages``
        - respect cancellation via ``self.cancelled``
        - emit progress events through ``self.emit(...)``
        - handle retries / rate-limits
        """
        raise NotImplementedError
        yield  # pragma: no cover  (informs the type checker this is a generator)

    # ---------------- Helpers ----------------
    @property
    def cancelled(self) -> bool:
        return self._stop_event is not None and self._stop_event.is_set()

    async def emit(self, event: str, **payload) -> None:
        if not self._progress:
            return
        try:
            payload.setdefault("source", self.SOURCE_NAME)
            res = self._progress(event, payload)
            if asyncio.iscoroutine(res):
                await res
        except Exception as exc:  # noqa: BLE001
            self.logger.debug("progress callback failed: {e}", e=str(exc))

    def _default_headers(self) -> dict:
        return {
            "User-Agent": pick_user_agent(),
            "Accept": (
                "text/html,application/xhtml+xml,application/xml;q=0.9,"
                "image/avif,image/webp,*/*;q=0.8"
            ),
            "Accept-Language": "en-US,en;q=0.7,fr-FR;q=0.6",
            "Accept-Encoding": "gzip, deflate",
            "DNT": "1",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
        }

    async def _rotate_ua(self) -> None:
        if not settings.scraper_user_agent_rotate or self._client is None:
            return
        self._client.headers["User-Agent"] = pick_user_agent()

    async def _throttle(self) -> None:
        """Sleep a random duration to space out HTTP requests."""
        await asyncio.to_thread(random_delay)

    # ---------------- HTTP fetch with retry ----------------
    async def fetch(
        self,
        url: str,
        *,
        params: Optional[dict] = None,
        headers: Optional[dict] = None,
        method: str = "GET",
        data: Optional[dict] = None,
        json_payload: Optional[dict] = None,
    ) -> httpx.Response:
        """Perform an HTTP request with retries and throttling."""
        if self._client is None:
            raise ScraperError("HTTP client not initialized — use 'async with' on scraper")

        await self._rotate_ua()
        merged_headers = dict(self._client.headers)
        if headers:
            merged_headers.update(headers)

        try:
            async for attempt in AsyncRetrying(
                stop=stop_after_attempt(settings.scraper_retry_count),
                wait=wait_exponential_jitter(initial=1.5, max=10),
                retry=retry_if_exception_type(
                    (
                        httpx.ConnectError,
                        httpx.ReadTimeout,
                        httpx.RemoteProtocolError,
                        httpx.ConnectTimeout,
                        RateLimitError,
                    )
                ),
                reraise=True,
            ):
                with attempt:
                    response = await self._client.request(
                        method,
                        url,
                        params=params,
                        headers=merged_headers,
                        data=data,
                        json=json_payload,
                    )
                    if response.status_code == 429:
                        retry_after = response.headers.get("Retry-After", "5")
                        try:
                            wait_s = float(retry_after)
                        except ValueError:
                            wait_s = 5.0
                        self.logger.warning(
                            "Rate limited by {src}; sleeping {s}s",
                            src=self.SOURCE_NAME,
                            s=wait_s,
                        )
                        await asyncio.sleep(min(wait_s, 30.0))
                        raise RateLimitError(
                            f"{self.SOURCE_NAME} returned HTTP 429"
                        )
                    if response.status_code >= 500:
                        raise httpx.RemoteProtocolError(
                            f"{self.SOURCE_NAME} server error {response.status_code}"
                        )
                    return response
        except httpx.TimeoutException as exc:
            raise ScraperTimeoutError(f"Timeout fetching {url}", cause=exc) from exc
        except RetryError as exc:
            raise ScraperError(
                f"All retries exhausted for {url}", cause=exc
            ) from exc

        raise ScraperError(f"Unreachable: failed to fetch {url}")

    async def fetch_html(self, url: str, **kwargs) -> BeautifulSoup:
        response = await self.fetch(url, **kwargs)
        return BeautifulSoup(response.text, "lxml")

    async def fetch_json(self, url: str, **kwargs) -> dict | list:
        response = await self.fetch(url, **kwargs)
        try:
            return response.json()
        except ValueError as exc:
            raise ScraperError(f"Non-JSON response from {url}", cause=exc) from exc

    # ---------------- Parsing helpers ----------------
    @staticmethod
    def parse_text(node) -> str:
        if node is None:
            return ""
        return safe_text(node.get_text(" ", strip=True))

    @staticmethod
    def parse_date(text: Optional[str]) -> Optional[datetime]:
        return parse_posted_date(text)

    @staticmethod
    def detect_remote(text: str) -> bool:
        if not text:
            return False
        lowered = text.lower()
        return any(
            token in lowered
            for token in ("remote", "télétravail", "teletravail", "work from home")
        )

    # Compiled once — matches multilingual phrases that indicate the employer
    # offers visa sponsorship or relocation support.
    _SPONSORSHIP_RE = re.compile(
        r"(?:"
        r"visa\s+sponsor(?:ship)?"        # English explicit
        r"|sponsor(?:ed)?\s+visa"
        r"|sponsor(?:ed|ship)?(?:\s+for)?\s+work\s+permit"
        r"|h-?1b\b"
        r"|tier[- ]?2\s+visa"
        r"|relocation\s+(?:assistance|package|support|offered|provided)"
        r"|work\s+permit\s+(?:offered|sponsored|provided)"
        r"|skilled\s+worker\s+visa"
        r"|eu\s+blue\s+card|blue[- ]card"  # Germany
        r"|aufenthaltsgenehmigung"
        r"|visum\s+(?:wird\s+)?gesponsert"
        r"|sponsoring\s+visa"             # French
        r"|parrainage\s+visa"
        r"|patrocinio\s+de\s+visa"        # Spanish
        r"|kafala|iqama|ejada"             # GCC-specific terms
        r")",
        re.IGNORECASE,
    )

    @classmethod
    def detect_sponsorship(cls, *texts: str | None) -> bool:
        """Return True if any of ``texts`` mentions visa sponsorship/relocation."""
        haystack = " ".join(t for t in texts if t)
        if not haystack:
            return False
        return bool(cls._SPONSORSHIP_RE.search(haystack))

    @staticmethod
    def absolute_url(base: str, href: str) -> str:
        if not href:
            return ""
        if href.startswith(("http://", "https://")):
            return href
        return base.rstrip("/") + "/" + href.lstrip("/")
