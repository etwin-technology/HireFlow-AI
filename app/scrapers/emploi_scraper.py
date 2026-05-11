"""Emploi.ma (Morocco) scraper."""

from __future__ import annotations

import urllib.parse
from typing import AsyncIterator

from app.core.constants import EventTopic
from app.scrapers.base_scraper import BaseScraper, JobRecord, ScrapeQuery


class EmploiScraper(BaseScraper):
    SOURCE_NAME: str = "Emploi.ma"
    BASE_URL: str = "https://www.emploi.ma"
    SEARCH_URL: str = "https://www.emploi.ma/recherche-jobs-maroc"

    async def run(self, query: ScrapeQuery) -> AsyncIterator[JobRecord]:
        await self.emit(EventTopic.SCRAPE_STARTED, query=query.keyword)
        total = 0
        keyword = query.keyword.strip()

        for page in range(1, query.max_pages + 1):
            if self.cancelled:
                break

            if keyword:
                slug = "-".join(keyword.lower().split())
                base_path = f"/recherche-jobs-maroc/{urllib.parse.quote(slug)}"
            else:
                base_path = "/recherche-jobs-maroc"
            url = f"{self.BASE_URL}{base_path}?page={page}"

            try:
                soup = await self.fetch_html(url)
            except Exception as exc:  # noqa: BLE001
                self.logger.warning(
                    "Emploi.ma page {p} failed: {e}", p=page, e=str(exc)
                )
                await self.emit(EventTopic.SCRAPE_ERROR, error=str(exc), page=page)
                continue

            cards = soup.select("div.card-job, li.card-job, .job-item")
            await self.emit(EventTopic.SCRAPE_PAGE, page=page, total=len(cards))
            if not cards:
                break

            found_on_page = 0
            for card in cards:
                if self.cancelled:
                    break

                title_node = card.select_one("h3 a, h2 a, a.title")
                company_node = card.select_one(
                    "a.card-job-company, .card-job-company, .company"
                )
                location_node = card.select_one("ul.card-job-detail li, .location")
                desc_node = card.select_one("div.card-job-description, .description")
                date_node = card.select_one("time, .date")

                title = self.parse_text(title_node)
                if not title:
                    continue
                href = (title_node.get("href") if title_node else "") or ""
                if href and not href.startswith("http"):
                    href = self.BASE_URL.rstrip("/") + "/" + href.lstrip("/")

                record = JobRecord(
                    title=title,
                    company=self.parse_text(company_node),
                    location=self.parse_text(location_node) or "Morocco",
                    country="Morocco",
                    remote=self.detect_remote(
                        f"{title} {self.parse_text(desc_node)}"
                    ),
                    salary=None,
                    job_type=None,
                    experience_level=None,
                    description=self.parse_text(desc_node),
                    source=self.SOURCE_NAME,
                    url=href,
                    posted_date=self.parse_date(self.parse_text(date_node)),
                )

                total += 1
                found_on_page += 1
                await self.emit(
                    EventTopic.SCRAPE_FOUND, count=total, title=record.title
                )
                yield record

            if found_on_page == 0:
                break
            await self._throttle()

        await self.emit(EventTopic.SCRAPE_COMPLETED, count=total)
