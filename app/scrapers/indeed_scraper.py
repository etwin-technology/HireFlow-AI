"""Indeed scraper.

Indeed actively defends against scraping; this implementation uses Playwright
with stealth patches to render the search page, then parses the visible cards
with BeautifulSoup.
"""

from __future__ import annotations

import asyncio
import urllib.parse
from typing import AsyncIterator

from bs4 import BeautifulSoup

from app.core.constants import EventTopic
from app.scrapers.base_scraper import BaseScraper, JobRecord, ScrapeQuery
from app.utils.browser import BrowserManager
from app.utils.helpers import random_delay


class IndeedScraper(BaseScraper):
    SOURCE_NAME: str = "Indeed"
    REQUIRES_BROWSER: bool = True

    COUNTRY_DOMAINS: dict[str, str] = {
        "Morocco": "https://ma.indeed.com",
        "France": "https://fr.indeed.com",
        "Spain": "https://es.indeed.com",
        "Germany": "https://de.indeed.com",
        "UAE": "https://ae.indeed.com",
        "Saudi Arabia": "https://sa.indeed.com",
        "Qatar": "https://qa.indeed.com",
        "Canada": "https://ca.indeed.com",
        "USA": "https://www.indeed.com",
        "UK": "https://uk.indeed.com",
    }

    async def run(self, query: ScrapeQuery) -> AsyncIterator[JobRecord]:
        await self.emit(EventTopic.SCRAPE_STARTED, query=query.keyword)
        total = 0
        base = self.COUNTRY_DOMAINS.get(query.country or "", "https://www.indeed.com")

        async with BrowserManager() as browser:
            page = await browser.new_page()
            try:
                for page_num in range(query.max_pages):
                    if self.cancelled:
                        break

                    qs: dict[str, str | int] = {
                        "q": query.keyword or "developer",
                        "start": page_num * 10,
                    }
                    if query.city:
                        qs["l"] = query.city
                    elif query.remote_only:
                        qs["sc"] = "0kf:attr(DSQF7);"
                    url = f"{base}/jobs?{urllib.parse.urlencode(qs)}"

                    self.logger.debug("Indeed GET {u}", u=url)
                    try:
                        await page.goto(url, wait_until="domcontentloaded")
                        await page.wait_for_timeout(2500)
                        await BrowserManager.smooth_scroll(page, steps=4, delay_ms=300)
                    except Exception as exc:  # noqa: BLE001
                        self.logger.warning(
                            "Indeed nav failed: {e}", e=str(exc)
                        )
                        await self.emit(EventTopic.SCRAPE_ERROR, error=str(exc))
                        continue

                    html = await page.content()
                    soup = BeautifulSoup(html, "lxml")

                    cards = soup.select("div.job_seen_beacon, a.tapItem")
                    await self.emit(
                        EventTopic.SCRAPE_PAGE, page=page_num + 1, total=len(cards)
                    )
                    if not cards:
                        break

                    found_on_page = 0
                    for card in cards:
                        if self.cancelled:
                            break

                        title_node = card.select_one(
                            "h2.jobTitle span[title], h2.jobTitle a span, h2.jobTitle"
                        )
                        company_node = card.select_one(
                            "span.companyName, [data-testid='company-name'], "
                            ".companyName"
                        )
                        location_node = card.select_one(
                            ".companyLocation, [data-testid='text-location']"
                        )
                        salary_node = card.select_one(
                            ".salary-snippet-container, .estimated-salary, "
                            ".attribute_snippet"
                        )
                        desc_node = card.select_one(".job-snippet, .jobSnippet")
                        link_node = card.select_one("a.jcs-JobTitle, a.tapItem, h2 a")

                        title = self.parse_text(title_node)
                        if not title:
                            continue
                        company = self.parse_text(company_node)
                        location = self.parse_text(location_node)
                        salary = self.parse_text(salary_node) or None
                        description = self.parse_text(desc_node)

                        href = (link_node.get("href") if link_node else "") or ""
                        if href and not href.startswith("http"):
                            href = base.rstrip("/") + "/" + href.lstrip("/")

                        remote = self.detect_remote(f"{title} {location}")

                        record = JobRecord(
                            title=title,
                            company=company,
                            location=location,
                            country=query.country,
                            remote=remote,
                            salary=salary,
                            job_type=None,
                            experience_level=None,
                            description=description,
                            source=self.SOURCE_NAME,
                            url=href,
                            posted_date=None,
                        )

                        total += 1
                        found_on_page += 1
                        await self.emit(
                            EventTopic.SCRAPE_FOUND,
                            count=total,
                            title=record.title,
                        )
                        yield record

                    if found_on_page == 0:
                        break
                    await asyncio.to_thread(random_delay, 2.5, 5.0)
            finally:
                try:
                    await page.close()
                except Exception:  # noqa: BLE001
                    pass

        await self.emit(EventTopic.SCRAPE_COMPLETED, count=total)
