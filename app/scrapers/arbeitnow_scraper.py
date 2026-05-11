"""Arbeitnow scraper using the official Job Board API.

Docs: https://www.arbeitnow.com/api/job-board-api
"""

from __future__ import annotations

import asyncio
from typing import AsyncIterator

from app.core.constants import EventTopic
from app.scrapers.base_scraper import BaseScraper, JobRecord, ScrapeQuery


class ArbeitnowScraper(BaseScraper):
    SOURCE_NAME: str = "Arbeitnow"
    API_URL: str = "https://www.arbeitnow.com/api/job-board-api"

    async def run(self, query: ScrapeQuery) -> AsyncIterator[JobRecord]:
        await self.emit(EventTopic.SCRAPE_STARTED, query=query.keyword)
        keyword = query.keyword.lower().strip()
        total = 0

        for page in range(1, query.max_pages + 1):
            if self.cancelled:
                break

            try:
                data = await self.fetch_json(self.API_URL, params={"page": page})
            except Exception as exc:  # noqa: BLE001
                self.logger.error(
                    "Arbeitnow page {p} failed: {e}", p=page, e=str(exc)
                )
                await self.emit(EventTopic.SCRAPE_ERROR, error=str(exc), page=page)
                continue

            if not isinstance(data, dict):
                break

            items = data.get("data") or []
            if not items:
                break

            await self.emit(EventTopic.SCRAPE_PAGE, page=page, total=len(items))

            for entry in items:
                if self.cancelled:
                    break

                title = (entry.get("title") or "").strip()
                company = (entry.get("company_name") or "").strip()
                description = entry.get("description") or ""
                tags = entry.get("tags") or []

                haystack = " ".join(
                    [title.lower(), company.lower(), description.lower()]
                    + [str(t).lower() for t in tags]
                )
                if keyword and keyword not in haystack:
                    continue

                remote = bool(entry.get("remote", False))
                location = entry.get("location") or ("Remote" if remote else "")
                country = self._detect_country(location, remote)
                job_types = entry.get("job_types") or []

                record = JobRecord(
                    title=title,
                    company=company,
                    location=location,
                    country=country,
                    remote=remote,
                    salary=None,
                    job_type=", ".join(job_types[:2]) if job_types else None,
                    description=description,
                    source=self.SOURCE_NAME,
                    url=entry.get("url") or "",
                    posted_date=self.parse_date(entry.get("created_at")),
                )

                total += 1
                await self.emit(
                    EventTopic.SCRAPE_FOUND, count=total, title=record.title
                )
                yield record

            await asyncio.sleep(0.5)

        await self.emit(EventTopic.SCRAPE_COMPLETED, count=total)

    @staticmethod
    def _detect_country(location: str, remote: bool) -> str:
        if remote and (not location or "remote" in location.lower()):
            return "Remote"
        text = (location or "").lower()
        if "germany" in text or "deutschland" in text or "berlin" in text:
            return "Germany"
        if "france" in text or "paris" in text:
            return "France"
        if "uk" in text or "london" in text or "england" in text:
            return "UK"
        if "spain" in text or "madrid" in text or "barcelona" in text:
            return "Spain"
        if "usa" in text or "united states" in text:
            return "USA"
        return "Other"
