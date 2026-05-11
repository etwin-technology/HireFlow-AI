"""RemoteOK scraper using their public JSON feed.

API: https://remoteok.com/api  — returns a JSON array (first element is meta).
"""

from __future__ import annotations

from typing import AsyncIterator

from app.core.constants import EventTopic
from app.scrapers.base_scraper import BaseScraper, JobRecord, ScrapeQuery


class RemoteOKScraper(BaseScraper):
    SOURCE_NAME: str = "RemoteOK"
    BASE_URL: str = "https://remoteok.com"
    API_URL: str = "https://remoteok.com/api"

    async def run(self, query: ScrapeQuery) -> AsyncIterator[JobRecord]:
        await self.emit(EventTopic.SCRAPE_STARTED, query=query.keyword)
        keyword = query.keyword.lower().strip()

        try:
            data = await self.fetch_json(
                self.API_URL,
                headers={"User-Agent": "JobHunterPro/1.0"},
            )
        except Exception as exc:  # noqa: BLE001
            self.logger.error("RemoteOK fetch failed: {e}", e=str(exc))
            await self.emit(EventTopic.SCRAPE_ERROR, error=str(exc))
            return

        if not isinstance(data, list) or len(data) < 2:
            await self.emit(EventTopic.SCRAPE_COMPLETED, count=0)
            return

        # First entry is metadata - skip it.
        listings = data[1:]
        await self.emit(EventTopic.SCRAPE_PAGE, page=1, total=len(listings))
        count = 0

        for entry in listings:
            if self.cancelled:
                break
            if not isinstance(entry, dict):
                continue

            position = entry.get("position") or entry.get("title") or ""
            company = entry.get("company") or ""
            description = entry.get("description") or ""
            tags = entry.get("tags") or []
            haystack = " ".join(
                [position.lower(), company.lower(), description.lower()]
                + [str(t).lower() for t in tags]
            )

            if keyword and keyword not in haystack:
                continue

            url = entry.get("url") or entry.get("apply_url") or ""
            if url and not url.startswith("http"):
                url = self.absolute_url(self.BASE_URL, url)

            salary_min = entry.get("salary_min")
            salary_max = entry.get("salary_max")
            salary = None
            if salary_min and salary_max:
                salary = f"${salary_min:,} - ${salary_max:,}"
            elif salary_min:
                salary = f"${salary_min:,}+"

            record = JobRecord(
                title=position.strip(),
                company=company.strip(),
                location=(entry.get("location") or "Remote").strip(),
                country="Remote",
                remote=True,
                salary=salary,
                job_type=", ".join(tags[:3]) if tags else None,
                description=description,
                source=self.SOURCE_NAME,
                url=url,
                posted_date=self.parse_date(entry.get("date") or entry.get("epoch")),
            )

            count += 1
            await self.emit(EventTopic.SCRAPE_FOUND, count=count, title=record.title)
            yield record

        await self.emit(EventTopic.SCRAPE_COMPLETED, count=count)
