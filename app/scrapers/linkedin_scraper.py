"""LinkedIn Jobs scraper using the public guest endpoint.

Notes:
- We use LinkedIn's unauthenticated guest API which returns rendered HTML
  for a given page of results.
- LinkedIn aggressively rate-limits — we throttle hard and rotate UAs.
"""

from __future__ import annotations

import asyncio
import urllib.parse
from typing import AsyncIterator

from app.core.constants import EventTopic
from app.scrapers.base_scraper import BaseScraper, JobRecord, ScrapeQuery


class LinkedInScraper(BaseScraper):
    SOURCE_NAME: str = "LinkedIn"
    SEARCH_URL: str = (
        "https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search"
    )

    GEO_IDS: dict[str, str] = {
        "Morocco": "102787409",
        "France": "105015875",
        "Spain": "105646813",
        "Germany": "101282230",
        "UAE": "104305776",
        "Saudi Arabia": "100459316",
        "Qatar": "104170880",
        "Canada": "101174742",
        "USA": "103644278",
        "UK": "101165590",
    }

    async def run(self, query: ScrapeQuery) -> AsyncIterator[JobRecord]:
        await self.emit(EventTopic.SCRAPE_STARTED, query=query.keyword)
        total = 0

        for page in range(1, query.max_pages + 1):
            if self.cancelled:
                break

            params: dict[str, str | int] = {
                "keywords": query.keyword or "developer",
                "start": (page - 1) * 25,
            }
            if query.country and query.country in self.GEO_IDS:
                params["geoId"] = self.GEO_IDS[query.country]
            if query.city:
                params["location"] = query.city
            if query.remote_only:
                # LinkedIn's "Remote" workplace filter
                params["f_WT"] = 2

            try:
                soup = await self.fetch_html(self.SEARCH_URL, params=params)
            except Exception as exc:  # noqa: BLE001
                self.logger.warning(
                    "LinkedIn page {p} fetch failed: {e}", p=page, e=str(exc)
                )
                await self.emit(EventTopic.SCRAPE_ERROR, error=str(exc), page=page)
                await self._throttle()
                continue

            cards = soup.select("li, div.job-search-card")
            results_on_page = 0
            await self.emit(EventTopic.SCRAPE_PAGE, page=page, total=len(cards))

            for card in cards:
                if self.cancelled:
                    break

                title_node = card.select_one(
                    "h3.base-search-card__title, .base-search-card__title, "
                    ".sr-only, h3"
                )
                company_node = card.select_one(
                    "h4.base-search-card__subtitle a, "
                    ".base-search-card__subtitle a, h4"
                )
                location_node = card.select_one(
                    ".job-search-card__location, .job-result-card__location"
                )
                link_node = card.select_one("a.base-card__full-link, a")
                time_node = card.select_one("time, .job-search-card__listdate")

                title = self.parse_text(title_node)
                if not title:
                    continue
                company = self.parse_text(company_node)
                location = self.parse_text(location_node)
                href = (link_node.get("href") if link_node else "") or ""
                if "?" in href:
                    href = href.split("?")[0]
                if href and not href.startswith("http"):
                    href = "https://www.linkedin.com" + href

                remote = self.detect_remote(f"{title} {location}")

                record = JobRecord(
                    title=title,
                    company=company,
                    location=location,
                    country=query.country or self._detect_country(location),
                    remote=remote,
                    salary=None,
                    job_type=None,
                    experience_level=None,
                    description=None,
                    source=self.SOURCE_NAME,
                    url=href,
                    posted_date=self.parse_date(
                        (time_node.get("datetime") if time_node else None)
                        or self.parse_text(time_node)
                    ),
                )

                total += 1
                results_on_page += 1
                await self.emit(
                    EventTopic.SCRAPE_FOUND, count=total, title=record.title
                )
                yield record

            if results_on_page == 0:
                self.logger.info(
                    "LinkedIn page {p} returned no cards — stopping.", p=page
                )
                break

            await self._throttle()
            await asyncio.sleep(0)  # cooperative checkpoint

        await self.emit(EventTopic.SCRAPE_COMPLETED, count=total)

    @staticmethod
    def _detect_country(location: str) -> str:
        if not location:
            return "Other"
        text = location.lower()
        if "morocco" in text or "maroc" in text:
            return "Morocco"
        if "france" in text or "paris" in text:
            return "France"
        if "germany" in text or "berlin" in text:
            return "Germany"
        if "spain" in text or "madrid" in text:
            return "Spain"
        if "united kingdom" in text or "london" in text or " uk" in text:
            return "UK"
        if "united states" in text or "usa" in text:
            return "USA"
        if "canada" in text:
            return "Canada"
        if "uae" in text or "dubai" in text or "abu dhabi" in text:
            return "UAE"
        if "saudi" in text or "riyadh" in text:
            return "Saudi Arabia"
        if "qatar" in text or "doha" in text:
            return "Qatar"
        return "Other"
