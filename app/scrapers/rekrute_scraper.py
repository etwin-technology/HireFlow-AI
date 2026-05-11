"""Rekrute.com (Morocco) scraper.

Rekrute serves traditional server-rendered HTML pages, so we can use httpx +
BeautifulSoup directly.
"""

from __future__ import annotations

import asyncio
import urllib.parse
from typing import AsyncIterator

from app.core.constants import EventTopic
from app.scrapers.base_scraper import BaseScraper, JobRecord, ScrapeQuery


class RekruteScraper(BaseScraper):
    SOURCE_NAME: str = "Rekrute"
    BASE_URL: str = "https://www.rekrute.com"
    SEARCH_URL: str = "https://www.rekrute.com/offres.html"

    async def run(self, query: ScrapeQuery) -> AsyncIterator[JobRecord]:
        await self.emit(EventTopic.SCRAPE_STARTED, query=query.keyword)
        total = 0
        keyword = query.keyword.strip()

        for page in range(1, query.max_pages + 1):
            if self.cancelled:
                break

            params: dict = {"p": page}
            if keyword:
                params["s"] = keyword

            url = f"{self.SEARCH_URL}?{urllib.parse.urlencode(params)}"
            try:
                soup = await self.fetch_html(url)
            except Exception as exc:  # noqa: BLE001
                self.logger.warning(
                    "Rekrute page {p} failed: {e}", p=page, e=str(exc)
                )
                await self.emit(EventTopic.SCRAPE_ERROR, error=str(exc), page=page)
                continue

            cards = soup.select("li.post-id")
            if not cards:
                # Alternative layout
                cards = soup.select("div.section.post-id, ul.liste-offres > li")
            await self.emit(EventTopic.SCRAPE_PAGE, page=page, total=len(cards))

            if not cards:
                break

            found_on_page = 0
            for card in cards:
                if self.cancelled:
                    break

                title_node = card.select_one("h2 a, h3 a, .titreJob")
                company_node = card.select_one("a.nomSociete, .nomSociete, .holder a")
                desc_node = card.select_one(".description, .holder")
                meta_nodes = card.select("ul.list-unstyled li, .infoOffre li")
                date_node = card.select_one("em.date, time, .dateAjout")

                title = self.parse_text(title_node)
                if not title:
                    continue
                href = (title_node.get("href") if title_node else "") or ""
                if href and not href.startswith("http"):
                    href = self.BASE_URL.rstrip("/") + "/" + href.lstrip("/")

                company = self.parse_text(company_node)
                description = self.parse_text(desc_node)

                location = "Morocco"
                job_type = None
                experience_level = None
                for meta in meta_nodes:
                    label = self.parse_text(meta).lower()
                    if any(k in label for k in ("contrat", "cdi", "cdd", "stage")):
                        job_type = self.parse_text(meta)
                    elif "expérience" in label or "experience" in label:
                        experience_level = self.parse_text(meta)
                    elif "ville" in label or "région" in label or "region" in label:
                        location = self.parse_text(meta)

                record = JobRecord(
                    title=title,
                    company=company,
                    location=location,
                    country="Morocco",
                    remote=self.detect_remote(f"{title} {description}"),
                    salary=None,
                    job_type=job_type,
                    experience_level=experience_level,
                    description=description,
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
