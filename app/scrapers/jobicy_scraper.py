"""Jobicy.com scraper using their public JSON API.

Endpoint: https://jobicy.com/api/v2/remote-jobs
Free, no API key required. Returns a JSON object with a ``jobs`` array.
"""

from __future__ import annotations

from typing import AsyncIterator

from app.core.constants import EventTopic
from app.scrapers.base_scraper import BaseScraper, JobRecord, ScrapeQuery


class JobicyScraper(BaseScraper):
    SOURCE_NAME: str = "Jobicy"
    API_URL: str = "https://jobicy.com/api/v2/remote-jobs"

    # Map our country names to Jobicy's ``geo`` filter values.
    GEO_MAP: dict[str, str] = {
        "USA": "usa",
        "UK": "uk",
        "Canada": "canada",
        "Germany": "germany",
        "France": "france",
        "Spain": "spain",
    }

    async def run(self, query: ScrapeQuery) -> AsyncIterator[JobRecord]:
        await self.emit(EventTopic.SCRAPE_STARTED, query=query.keyword)
        keyword = query.keyword.lower().strip()
        total = 0

        # Jobicy's API returns the latest N jobs in a single call — there's
        # no working ``page`` parameter (passing it causes 0 results). We
        # honor ``max_pages`` by scaling ``count`` instead.
        if self.cancelled:
            await self.emit(EventTopic.SCRAPE_COMPLETED, count=0)
            return

        # Jobicy's ``tag`` filter is exact-match on their taxonomy
        # (javascript, python, ...) so it's too strict for free-form
        # keywords like "developer". We pull a broad set and filter
        # client-side instead.
        count = max(20, min(100, query.max_pages * 50))
        params: dict[str, str | int] = {"count": count}
        geo = self.GEO_MAP.get(query.country or "", "")
        if geo:
            params["geo"] = geo

        try:
            data = await self.fetch_json(self.API_URL, params=params)
        except Exception as exc:  # noqa: BLE001
            self.logger.warning("Jobicy fetch failed: {e}", e=str(exc))
            await self.emit(EventTopic.SCRAPE_ERROR, error=str(exc))
            await self.emit(EventTopic.SCRAPE_COMPLETED, count=0)
            return

        jobs = data.get("jobs") if isinstance(data, dict) else None
        if not jobs:
            await self.emit(EventTopic.SCRAPE_COMPLETED, count=0)
            return

        await self.emit(EventTopic.SCRAPE_PAGE, page=1, total=len(jobs))

        for entry in jobs:
            if self.cancelled:
                break

            title = (entry.get("jobTitle") or "").strip()
            company = (entry.get("companyName") or "").strip()
            description = entry.get("jobDescription") or ""

            if keyword:
                haystack = " ".join(
                    [title.lower(), company.lower(), description.lower()]
                )
                if keyword not in haystack:
                    continue

            geo_list = entry.get("jobGeo") or []
            geo_str = (
                geo_list if isinstance(geo_list, str) else ", ".join(geo_list)
            )
            country = self._detect_country(geo_str) or "Remote"

            level = entry.get("jobLevel")
            job_types = entry.get("jobType") or []
            if isinstance(job_types, list):
                job_type = ", ".join(job_types[:2]) if job_types else None
            else:
                job_type = str(job_types) if job_types else None

            posted = self.parse_date(entry.get("pubDate"))

            record = JobRecord(
                title=title,
                company=company,
                location=geo_str or "Remote",
                country=country,
                remote=True,
                salary=entry.get("annualSalaryRange") or None,
                job_type=job_type,
                experience_level=level,
                description=description,
                source=self.SOURCE_NAME,
                url=entry.get("url") or "",
                posted_date=posted,
                sponsorship=self.detect_sponsorship(title, description),
            )

            total += 1
            await self.emit(
                EventTopic.SCRAPE_FOUND, count=total, title=record.title
            )
            yield record

        await self.emit(EventTopic.SCRAPE_COMPLETED, count=total)

    @staticmethod
    def _detect_country(geo: str) -> str:
        if not geo:
            return "Remote"
        text = geo.lower()
        for needle, name in (
            ("usa", "USA"), ("united states", "USA"),
            ("canada", "Canada"),
            ("uk", "UK"), ("united kingdom", "UK"),
            ("germany", "Germany"),
            ("france", "France"),
            ("spain", "Spain"),
            ("anywhere", "Remote"), ("worldwide", "Remote"),
        ):
            if needle in text:
                return name
        return "Remote"
