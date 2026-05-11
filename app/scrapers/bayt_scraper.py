"""Bayt.com scraper — the dominant Middle East job board.

Covers UAE, Saudi Arabia, Qatar, Bahrain, Kuwait, Oman, Egypt, Jordan, etc.

Bayt actively returns HTTP 403 to plain HTTP scrapers, so we use Playwright
with stealth to render the search page like a real browser, then parse the
visible cards with BeautifulSoup.
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


class BaytScraper(BaseScraper):
    SOURCE_NAME: str = "Bayt"
    REQUIRES_BROWSER: bool = True
    BASE_URL: str = "https://www.bayt.com"

    COUNTRY_PATHS: dict[str, str] = {
        "UAE": "uae",
        "Saudi Arabia": "saudi-arabia",
        "Qatar": "qatar",
        "Bahrain": "bahrain",
        "Kuwait": "kuwait",
        "Oman": "oman",
        "Egypt": "egypt",
        "Jordan": "jordan",
        "Lebanon": "lebanon",
        "Morocco": "morocco",
    }

    async def run(self, query: ScrapeQuery) -> AsyncIterator[JobRecord]:
        await self.emit(EventTopic.SCRAPE_STARTED, query=query.keyword)
        total = 0

        country_path = self.COUNTRY_PATHS.get(query.country or "", "uae")
        country_name = next(
            (k for k, v in self.COUNTRY_PATHS.items() if v == country_path),
            query.country,
        )
        keyword_slug = self._slug(query.keyword or "developer")

        async with BrowserManager() as browser:
            page = await browser.new_page()
            try:
                for page_num in range(1, query.max_pages + 1):
                    if self.cancelled:
                        break

                    path = f"/en/{country_path}/jobs/{keyword_slug}-jobs/"
                    url = (
                        f"{self.BASE_URL}{path}?{urllib.parse.urlencode({'page': page_num})}"
                    )
                    self.logger.debug("Bayt GET {u}", u=url)

                    try:
                        await page.goto(url, wait_until="domcontentloaded")
                        await page.wait_for_timeout(2500)
                        await BrowserManager.smooth_scroll(page, steps=4, delay_ms=300)
                    except Exception as exc:  # noqa: BLE001
                        self.logger.warning("Bayt nav failed: {e}", e=str(exc))
                        await self.emit(EventTopic.SCRAPE_ERROR, error=str(exc))
                        continue

                    html = await page.content()
                    soup = BeautifulSoup(html, "lxml")

                    cards = soup.select(
                        "li[data-js-job], li.has-pointer-d, div.has-pointer-d, "
                        "h2.m0 > a[data-js-aid='jobID']"
                    )
                    # Fall back to broader selectors if the primary one missed.
                    if not cards:
                        cards = [
                            a.find_parent("li") or a.find_parent("div") or a
                            for a in soup.select("a[data-js-aid='jobID']")
                        ]
                        cards = [c for c in cards if c is not None]

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

                        title_node = card.select_one(
                            "h2 a, h2.m0 a, a[data-js-aid='jobID'], a.t-default"
                        )
                        if title_node is None:
                            continue
                        title = self.parse_text(title_node)
                        if not title:
                            continue

                        href = title_node.get("href") or ""
                        if href and not href.startswith("http"):
                            href = self.BASE_URL.rstrip("/") + "/" + href.lstrip("/")
                        if href in seen_urls:
                            continue
                        seen_urls.add(href)

                        company_node = card.select_one(
                            "div.t-nowrap b, .t-nowrap a, .company-name, "
                            "[data-js-aid='jb-company'], b.t-nowrap"
                        )
                        location_node = card.select_one(
                            "div.t-mute, span.t-mute, [data-js-aid='jb-loc'], "
                            ".location"
                        )
                        date_node = card.select_one(
                            "div.t-small.t-mute span, time, "
                            "[data-js-aid='jb-postedDate'], .t-small span"
                        )
                        desc_node = card.select_one(
                            "div.jb-descr, .t-small.t-default p, .job-description"
                        )

                        location = self.parse_text(location_node) or country_name or ""
                        description = self.parse_text(desc_node)

                        record = JobRecord(
                            title=title,
                            company=self.parse_text(company_node),
                            location=location,
                            country=country_name,
                            remote=self.detect_remote(
                                f"{title} {location} {description}"
                            ),
                            salary=None,
                            job_type=None,
                            experience_level=None,
                            description=description,
                            source=self.SOURCE_NAME,
                            url=href,
                            posted_date=self.parse_date(self.parse_text(date_node)),
                            sponsorship=self.detect_sponsorship(title, description),
                        )

                        total += 1
                        found_on_page += 1
                        await self.emit(
                            EventTopic.SCRAPE_FOUND, count=total, title=record.title
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

    @staticmethod
    def _slug(text: str) -> str:
        cleaned = "-".join(text.lower().split())
        return urllib.parse.quote(cleaned)
