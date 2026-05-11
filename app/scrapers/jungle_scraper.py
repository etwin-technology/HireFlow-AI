"""WelcomeToTheJungle scraper.

The Welcome-to-the-Jungle site is a React SPA. We use Playwright to render
search results, then extract data from the embedded ``__NUXT_DATA__`` /
``__NEXT_DATA__`` payload or fall back to DOM parsing.
"""

from __future__ import annotations

import json
import urllib.parse
from typing import AsyncIterator

from bs4 import BeautifulSoup

from app.core.constants import EventTopic
from app.scrapers.base_scraper import BaseScraper, JobRecord, ScrapeQuery
from app.utils.browser import BrowserManager


class JungleScraper(BaseScraper):
    SOURCE_NAME: str = "WelcomeToTheJungle"
    REQUIRES_BROWSER: bool = True
    SEARCH_URL: str = "https://www.welcometothejungle.com/en/jobs"

    COUNTRY_FILTER = {
        "France": "France",
        "Spain": "Spain",
        "Germany": "Germany",
        "Morocco": "Morocco",
        "UK": "United Kingdom",
        "USA": "United States",
        "Canada": "Canada",
    }

    async def run(self, query: ScrapeQuery) -> AsyncIterator[JobRecord]:
        await self.emit(EventTopic.SCRAPE_STARTED, query=query.keyword)
        total = 0
        keyword = query.keyword.strip() or "developer"

        params: dict[str, str] = {"query": keyword}
        if query.country and query.country in self.COUNTRY_FILTER:
            params["refinementList[offices.country_code][0]"] = self.COUNTRY_FILTER[
                query.country
            ]
        if query.remote_only:
            params["refinementList[remote][0]"] = "fulltime"

        async with BrowserManager() as browser:
            page = await browser.new_page()
            try:
                for page_num in range(1, query.max_pages + 1):
                    if self.cancelled:
                        break

                    params["page"] = str(page_num)
                    url = f"{self.SEARCH_URL}?{urllib.parse.urlencode(params)}"
                    self.logger.debug("WTTJ GET {u}", u=url)

                    try:
                        await page.goto(url, wait_until="domcontentloaded")
                        await page.wait_for_timeout(3000)
                        await BrowserManager.smooth_scroll(page, steps=5, delay_ms=350)
                    except Exception as exc:  # noqa: BLE001
                        self.logger.warning("WTTJ nav failed: {e}", e=str(exc))
                        await self.emit(EventTopic.SCRAPE_ERROR, error=str(exc))
                        continue

                    html = await page.content()
                    soup = BeautifulSoup(html, "lxml")

                    cards = soup.select(
                        "li[data-testid='job-card'], a[href*='/jobs/'], "
                        "div[role='listitem']"
                    )

                    await self.emit(
                        EventTopic.SCRAPE_PAGE, page=page_num, total=len(cards)
                    )
                    if not cards:
                        break

                    found_on_page = 0
                    seen_urls: set[str] = set()

                    for card in cards:
                        if self.cancelled:
                            break

                        link = card if card.name == "a" else card.find("a")
                        if not link or not link.get("href"):
                            continue
                        href = link.get("href")
                        if "/jobs/" not in href:
                            continue
                        if not href.startswith("http"):
                            href = "https://www.welcometothejungle.com" + href
                        if href in seen_urls:
                            continue
                        seen_urls.add(href)

                        title_node = card.select_one(
                            "h4, h3, [data-testid='job-title'], "
                            "[class*='title' i]"
                        )
                        company_node = card.select_one(
                            "span[data-testid='job-organization'], "
                            "[class*='organization' i], [class*='company' i]"
                        )
                        location_node = card.select_one(
                            "[data-testid='job-metadata-location'], "
                            "[class*='location' i]"
                        )

                        title = self.parse_text(title_node)
                        if not title:
                            continue
                        company = self.parse_text(company_node)
                        location = self.parse_text(location_node)

                        record = JobRecord(
                            title=title,
                            company=company,
                            location=location,
                            country=query.country,
                            remote=self.detect_remote(f"{title} {location}"),
                            salary=None,
                            job_type=None,
                            experience_level=None,
                            description=None,
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
            finally:
                try:
                    await page.close()
                except Exception:  # noqa: BLE001
                    pass

        await self.emit(EventTopic.SCRAPE_COMPLETED, count=total)
