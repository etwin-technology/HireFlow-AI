"""TheMuse scraper using their public Jobs API.

Docs: https://www.themuse.com/developers/api/v2
"""

from __future__ import annotations

import asyncio
from typing import AsyncIterator

from app.core.constants import EventTopic
from app.scrapers.base_scraper import BaseScraper, JobRecord, ScrapeQuery


class MuseScraper(BaseScraper):
    SOURCE_NAME: str = "TheMuse"
    API_URL: str = "https://www.themuse.com/api/public/jobs"

    LEVEL_MAP = {
        "internship": "Internship",
        "entry": "Entry level",
        "entry level": "Entry level",
        "mid": "Mid-Senior",
        "mid level": "Mid-Senior",
        "senior": "Senior",
        "senior level": "Senior",
        "manager": "Director",
        "director": "Director",
    }

    async def run(self, query: ScrapeQuery) -> AsyncIterator[JobRecord]:
        await self.emit(EventTopic.SCRAPE_STARTED, query=query.keyword)
        keyword = query.keyword.lower().strip()
        total = 0

        for page in range(1, query.max_pages + 1):
            if self.cancelled:
                break

            params = {"page": page, "descending": "true"}
            if query.country and query.country != "Remote":
                params["location"] = query.country
            if query.remote_only:
                params["flexibility"] = "Flexible / Remote"

            try:
                data = await self.fetch_json(self.API_URL, params=params)
            except Exception as exc:  # noqa: BLE001
                self.logger.error(
                    "TheMuse page {p} failed: {e}", p=page, e=str(exc)
                )
                await self.emit(EventTopic.SCRAPE_ERROR, error=str(exc), page=page)
                continue

            if not isinstance(data, dict):
                break

            results = data.get("results") or []
            if not results:
                break

            await self.emit(EventTopic.SCRAPE_PAGE, page=page, total=len(results))

            for entry in results:
                if self.cancelled:
                    break

                title = (entry.get("name") or "").strip()
                company = ((entry.get("company") or {}).get("name") or "").strip()
                contents = entry.get("contents") or ""
                tags = [
                    t.get("name", "")
                    for t in (entry.get("tags") or [])
                    if isinstance(t, dict)
                ]
                levels = [
                    lvl.get("name", "")
                    for lvl in (entry.get("levels") or [])
                    if isinstance(lvl, dict)
                ]

                haystack = " ".join(
                    [title.lower(), company.lower(), contents.lower()]
                    + [t.lower() for t in tags]
                )
                if keyword and keyword not in haystack:
                    continue

                locations = entry.get("locations") or []
                first_loc = (
                    locations[0].get("name", "") if locations and isinstance(locations[0], dict) else ""
                )
                remote = "remote" in first_loc.lower() or "flexible" in first_loc.lower()
                country = self._detect_country(first_loc, remote)

                refs = entry.get("refs") or {}
                url = refs.get("landing_page") or ""

                experience = None
                if levels:
                    raw_level = levels[0].lower()
                    experience = self.LEVEL_MAP.get(raw_level, levels[0])

                record = JobRecord(
                    title=title,
                    company=company,
                    location=first_loc,
                    country=country,
                    remote=remote,
                    salary=None,
                    job_type=tags[0] if tags else None,
                    experience_level=experience,
                    description=contents,
                    source=self.SOURCE_NAME,
                    url=url,
                    posted_date=self.parse_date(entry.get("publication_date")),
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
        if not location:
            return "Remote" if remote else "Other"
        text = location.lower()
        if "remote" in text or "flexible" in text:
            return "Remote"
        for needle, name in (
            ("united states", "USA"),
            ("usa", "USA"),
            ("canada", "Canada"),
            ("united kingdom", "UK"),
            ("germany", "Germany"),
            ("france", "France"),
            ("spain", "Spain"),
            ("morocco", "Morocco"),
        ):
            if needle in text:
                return name
        return "Other"
